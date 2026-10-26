"""Read-only local MCP tools for a sealed, manually reviewed corpus."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server import MCPServer

from pentwin.cli import CorpusError, sha256
from pentwin.style_engine import aggregate, assess, guidance


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


def audit_draft(source_facts: str, draft: str) -> dict:
    """Small lexical alarm, never a semantic or publication approval."""
    if not source_facts.strip() or not draft.strip() or max(len(source_facts), len(draft)) > 30_000:
        raise CorpusError("Provide nonempty texts of at most 30,000 characters each")
    import re
    pattern = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?\s*(?:%|mg|kg|µg|μg|mL|mm|cm|nM|p\s*[<=>]\s*\d+(?:\.\d+)?)?", re.I)
    numbers = lambda text: {re.sub(r"\s+", "", n).lower() for n in pattern.findall(text)}
    original, proposed = numbers(source_facts), numbers(draft)
    return {"status": "needs_human_review", "new_numeric_tokens": sorted(proposed - original),
            "omitted_numeric_tokens": sorted(original - proposed),
            "limitations": "Lexical alarms can miss changed direction, negation, causality, populations, units, citations and claims. A human must verify every statement against the fact sheet and sources."}


def build_server(run: Path) -> MCPServer:
    # Fail before advertising tools if a run is missing or not sealed.
    load_corpus(run)
    server = MCPServer("PenTwin", version="0.4.0", instructions="For writing, call rewrite_plan and then assess_revision on the exact proposed draft. Never infer that a diagnostic score proves author likeness or factual accuracy.")

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
    def style_profile(section: str = "") -> dict:
        """Return locally measured author-style tendencies without returning any source passage, including when excerpt permission is no."""
        return aggregate(load_corpus(run), section)

    @server.tool()
    def rewrite_plan(draft: str, section: str) -> dict:
        """Compare an English draft with local, family-balanced author style and tell the host LLM how to rewrite it without source excerpts."""
        return guidance(load_corpus(run), draft, section)

    @server.tool()
    def assess_revision(original: str, revised: str, section: str) -> dict:
        """Measure style movement and flag lexical meaning changes; return text hashes, never an automatic factual approval."""
        return assess(load_corpus(run), original, revised, section)

    @server.tool()
    def review_draft(source_facts: str, draft: str) -> dict:
        """Flag numeric changes in a draft against a supplied fact sheet; always requires human meaning and citation review."""
        load_corpus(run)
        return audit_draft(source_facts, draft)

    return server


def serve(run: Path) -> None:
    build_server(run).run(transport="stdio")
