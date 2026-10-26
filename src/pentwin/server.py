"""Read-only local MCP tools for a sealed, manually reviewed corpus."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server import MCPServer

from pentwin.cli import CorpusError, sha256
from pentwin.style_engine import aggregate, assess, guidance
from pentwin.style_card import build_style_card
from pentwin.exploratory_card import build_exploratory_card, exploratory_instructions


def load_corpus(run: Path) -> list[dict]:
    if not run.is_absolute():
        raise CorpusError("The private run path must be absolute")
    target = run / "corpus.jsonl"
    digest = run / "corpus.sha256"
    if not target.is_file() or not digest.is_file():
        raise CorpusError("A sealed run with corpus.jsonl and corpus.sha256 is required")
    if digest.read_text(encoding="ascii").strip() != sha256(target):
        raise CorpusError("Sealed corpus changed since review")
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise CorpusError("Invalid sealed corpus")
    required = {"paper_id", "family_id", "split", "section", "move", "text", "status", "model_excerpt_permission"}
    if any(not required <= row.keys() or row["split"] not in {"development", "holdout"}
           or row["status"] not in {"published", "unpublished"}
           or row["model_excerpt_permission"] not in {"yes", "no"}
           or not isinstance(row["text"], str) for row in rows):
        raise CorpusError("Invalid sealed corpus schema")
    dev = {r["family_id"] for r in rows if r["split"] == "development"}
    holdout = {r["family_id"] for r in rows if r["split"] == "holdout"}
    if len(dev) < 2 or not holdout or dev & holdout:
        raise CorpusError("Invalid development/holdout family split")
    return rows


def build_server(run: Path) -> MCPServer:
    # Fail before advertising tools if a run is missing or not sealed.
    load_corpus(run)
    server = MCPServer("PenTwin", version="0.14.0", instructions="Use generation_protocol for factorial style conditions and a separate authored target opening for +Snippet. Use offline_evaluate to score private external drafts and hash-bound semantic scores. Each axis needs its own eligible 200-word evaluator on two ten-paper human cohorts; the 7/10 threshold permits exploration only, and failed axes abstain. Scientific claims and citations require an independent verifier outside PenTwin.")

    @server.tool()
    def corpus_status() -> dict:
        """Show private corpus readiness and aggregate counts without revealing paper identity or text."""
        rows = load_corpus(run)
        local_style = aggregate(rows)
        return {"sealed": True, "development_families": len({r["family_id"] for r in rows if r["split"] == "development"}),
                "holdout_families": len({r["family_id"] for r in rows if r["split"] == "holdout"}),
                "style_ready": local_style["status"] == "provisional",
                "style_mode": "local_aggregate_only",
                "note": "Readiness is a data gate, not a validated writing quality score."}

    @server.tool()
    def style_profile(section: str = "", move: str = "") -> dict:
        """Return locally measured author-style tendencies without returning any source passage, including when excerpt permission is no."""
        profile = aggregate(load_corpus(run), section, move)
        if profile["status"] == "provisional":
            for field in ("target", "between_paper_range"):
                profile[field] = {key: value for key, value in profile[field].items()
                                  if not key.startswith("function:")}
            profile["diagnostic_features_excluded_from_mcp"] = ["function_word_rates"]
        return profile

    @server.tool()
    def author_style_card(section: str, move: str = "", evidence_mode: str = "exploratory") -> dict:
        """Return weak graded clues by default, or strict role evidence; never return original passages."""
        rows = load_corpus(run)
        if evidence_mode == "exploratory":
            return build_exploratory_card(rows, section, move)
        if evidence_mode == "strict":
            return build_style_card(rows, section, move)
        raise CorpusError("evidence_mode must be exploratory or strict")

    @server.tool()
    def rewrite_plan(draft: str, section: str, move: str = "") -> dict:
        """Compare an English draft with local, family-balanced author style and tell the host LLM how to rewrite it without source excerpts."""
        return guidance(load_corpus(run), draft, section, move)

    @server.tool()
    def axis_plan(draft: str, section: str, axis: str, move: str = "") -> dict:
        """Isolate one weak style axis or a combined plan for controlled generation comparisons."""
        import hashlib
        if not draft.strip() or len(draft) > 30_000:
            raise CorpusError("Provide a nonempty draft of at most 30,000 characters")
        axes = {"wording": ("wording",), "cue_order": ("cue_order",), "stance": ("stance",),
                "combined": ("wording", "cue_order", "stance"), "none": ()}
        if axis not in axes:
            raise CorpusError("axis must be wording, cue_order, stance, combined or none")
        card = build_exploratory_card(load_corpus(run), section, move)
        return {"status": "experimental_plan" if card["status"] == "exploratory" else "insufficient_evidence",
                "axis": axis, "section": section, "move": move,
                "draft_sha256": hashlib.sha256(draft.encode()).hexdigest(),
                "profile_digest": card.get("profile_digest"),
                "instructions": exploratory_instructions(card, axes[axis]),
                "limitations": "Experimental weak clues. Compare same-content outputs against a generic academic baseline; no axis score proves author likeness."}

    @server.tool()
    def generation_protocol(section: str, move: str = "", target_text: str = "",
                            confirmed_author_written: bool = False) -> dict:
        """Provide eight factorial conditions; optionally use a separate human target's opening."""
        from pentwin.ablation_protocol import conditions
        return conditions(load_corpus(run), section, move, target_text, confirmed_author_written)

    @server.tool()
    def offline_evaluate(first_manifest: str, second_manifest: str, cases_file: str,
                         semantic_scores_file: str = "") -> dict:
        """Evaluate locally injected GPT/Claude drafts and hash-bound SBERT scores without API calls."""
        from pentwin.qualified_eval import evaluate_factorial
        paths = [Path(first_manifest), Path(second_manifest), Path(cases_file)]
        if any(not p.is_absolute() for p in paths) or (semantic_scores_file and not Path(semantic_scores_file).is_absolute()):
            raise CorpusError("Offline inputs need absolute private paths")
        return evaluate_factorial(*paths, semantic_scores_path=Path(semantic_scores_file) if semantic_scores_file else None)

    @server.tool()
    def assess_revision(original: str, revised: str, section: str, move: str = "") -> dict:
        """Measure aggregate style movement and return text hashes; never certify author likeness."""
        return assess(load_corpus(run), original, revised, section, move)

    return server


def serve(run: Path) -> None:
    build_server(run).run(transport="stdio")
