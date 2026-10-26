"""Read-only local MCP tools for a sealed, manually reviewed corpus."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server import MCPServer

from pentwin.cli import CorpusError, sha256
from pentwin.style_engine import aggregate, assess, guidance
from pentwin.style_card import build_style_card


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
    server = MCPServer("PenTwin", version="0.8.0", instructions="For authorial style, inspect author_style_card, call rewrite_plan and then assess_revision on the exact proposed draft. Unsupported role preferences must be omitted. Diagnostic distance is not proof of author likeness. Scientific meaning and citations require an independent verifier outside PenTwin.")

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
    def author_style_card(section: str, move: str = "") -> dict:
        """Return supported role-conditioned wording, stance and move transitions; never return original passages."""
        return build_style_card(load_corpus(run), section, move)

    @server.tool()
    def rewrite_plan(draft: str, section: str, move: str = "") -> dict:
        """Compare an English draft with local, family-balanced author style and tell the host LLM how to rewrite it without source excerpts."""
        return guidance(load_corpus(run), draft, section, move)

    @server.tool()
    def assess_revision(original: str, revised: str, section: str, move: str = "") -> dict:
        """Measure aggregate style movement and return text hashes; never certify author likeness."""
        return assess(load_corpus(run), original, revised, section, move)

    return server


def serve(run: Path) -> None:
    build_server(run).run(transport="stdio")
