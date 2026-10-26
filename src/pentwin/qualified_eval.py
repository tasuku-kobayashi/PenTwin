"""Frozen two-cohort eligibility screen for exploratory style experiments.

Both cohorts are human-authored. They are not an independent confirmation set
when their texts or results were already inspected while designing features.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.paper_grounded_eval import evaluate_paper_grounded
from pentwin.paper_grounded_eval import FEATURES, MIN_WORDS, _margin, _reference
from pentwin.style_engine import _measurement
from pentwin.semantic_guard import semantic_guard
from pentwin.ablation_protocol import CONDITIONS
from collections import defaultdict


MIN_CORRECT = 5
MIN_EACH_AUTHOR = 2


def _digests(manifest: Path) -> set[str]:
    data = json.loads(manifest.read_text(encoding="utf-8"))["papers"]
    return {hashlib.sha256((manifest.parent / row["path"]).resolve().read_bytes()).hexdigest()
            for row in data}


def qualify_evaluators(first: Path, second: Path) -> dict:
    if first.resolve() == second.resolve() or _digests(first) & _digests(second):
        raise CorpusError("Calibration cohorts must not reuse a paper")
    a, b = evaluate_paper_grounded(first), evaluate_paper_grounded(second)
    names = a["features"].keys() & b["features"].keys()
    features = {}
    for name in sorted(names):
        counts = [report["calibration"]["correct_by_author"][name] for report in (a, b)]
        qualified = all(sum(item.values()) >= MIN_CORRECT and
                        min(item.values()) >= MIN_EACH_AUTHOR for item in counts)
        features[name] = {"correct": [sum(item.values()) for item in counts],
                          "per_author": [sorted(item.values()) for item in counts],
                          "eligible_for_exploratory_scoring": qualified}
    return {"status": "exploratory_eligible" if features.get("function_words", {}).get("eligible_for_exploratory_scoring") else "ineligible",
            "threshold": {"per_cohort": "at least 5/6", "per_author": "at least 2/3", "cohorts_required": 2},
            "features": features,
            "axis_coverage": {"lexical": "not_established", "ending": "partial_proxy_only",
                              "order": "not_established"},
            "risks": [a["source_confound_risks"], b["source_confound_risks"]],
            "interpretation": "Eligibility allows descriptive scoring only. Previously inspected cohorts cannot establish a validated evaluator. Function-word rates can miss lexical and order changes entirely; no axis-specific generation success may be certified. A failed feature cannot enter the primary score."}


def evaluate_factorial(first: Path, second: Path, cases_path: Path, encoder=None) -> dict:
    """Score a full 2^3 experiment; no winning condition without SBERT."""
    if any((parent / ".git").exists() for path in (first, second, cases_path)
           for parent in (path.resolve(), *path.resolve().parents)):
        raise CorpusError("Private evaluation inputs must remain outside Git working trees")
    gate = qualify_evaluators(first, second)
    papers = json.loads(first.read_text(encoding="utf-8"))["papers"]
    from pentwin.paper_grounded_eval import _window
    groups = defaultdict(list)
    for paper in papers:
        if len(groups[paper["author_id"]]) >= 2:
            continue
        body = (first.parent / paper["path"]).resolve().read_text(encoding="utf-8")
        groups[paper["author_id"]].append({"measurement": _window(body)})
    authors = sorted(groups)
    profiles = {a: _reference(groups[a]) for a in authors}
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise CorpusError("Need a nonempty cases list")
    paired = defaultdict(dict)
    seen = set()
    required = set(CONDITIONS) - {"none"}
    for case in cases:
        fields = ("case_id", "author_id", "content_id", "model", "section", "content_brief", "baseline")
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip()
                                             for k in fields):
            raise CorpusError("Cases need identifiers, model, discussion section, content brief and baseline")
        if case["case_id"] in seen or case["author_id"] not in authors or case["section"] != "discussion":
            raise CorpusError("Invalid case ID, author or section")
        seen.add(case["case_id"])
        variants = case.get("variants")
        if not isinstance(variants, dict) or not required <= variants.keys() or set(variants) - required - {"all_snippet"}:
            raise CorpusError("All seven card conditions, and optionally all_snippet, are required")
        if any(not isinstance(v, str) or not v.strip() for v in variants.values()):
            raise CorpusError("Every variant needs nonempty continuation text")
        if "all_snippet" in variants:
            anchor = case.get("snippet_anchor")
            if not isinstance(anchor, str) or not anchor.strip():
                raise CorpusError("Snippet condition requires its private human-authored anchor")
            if variants["all_snippet"].lstrip().startswith(anchor.strip()):
                raise CorpusError("Score only the continuation; remove the human-authored anchor")
        if case["author_id"] in paired[case["content_id"]]:
            raise CorpusError("One case per author and content brief")
        paired[case["content_id"]][case["author_id"]] = case
    if len(paired) < 2 or any(set(group) != set(authors) for group in paired.values()):
        raise CorpusError("At least two complete briefs with both authors are required")
    for group in paired.values():
        a, b = (group[author] for author in authors)
        if (a["content_brief"], a["baseline"], a["model"], a["section"]) != (
                b["content_brief"], b["baseline"], b["model"], b["section"]):
            raise CorpusError("Use the same brief, baseline, model and section for both authors")
        if set(a["variants"]) != set(b["variants"]):
            raise CorpusError("Compare the same conditions for both authors")
    details = []
    for case in cases:
        author = case["author_id"]
        rival = next(a for a in authors if a != author)
        labels = ["none"] + sorted(case["variants"])
        drafts = {"none": case["baseline"], **case["variants"]}
        measures = {label: _measurement([drafts[label]]) for label in labels}
        if any(not m or m["_tokens"] < MIN_WORDS for m in measures.values()):
            raise CorpusError("Baseline and continuations need at least 50 measurable words")
        scores = {}
        for name, keys in FEATURES.items():
            baseline = _margin(measures["none"], profiles[author], profiles[rival], keys)
            scores[name] = {label: round(_margin(measures[label], profiles[author], profiles[rival], keys) - baseline, 3)
                            for label in case["variants"]}
        semantics = semantic_guard(case["content_brief"], case["baseline"], case["variants"], encoder) if encoder else None
        details.append({"case_id": case["case_id"], "author_id": author, "content_id": case["content_id"],
                        "margin_changes": scores, "semantic": semantics})
    summary = {}
    for label in sorted(cases[0]["variants"]):
        summary[label] = {name: {"improved": sum(d["margin_changes"][name][label] > 0 for d in details),
                                  "of": len(details)} for name in FEATURES}
        summary[label]["semantic_pass"] = (sum(d["semantic"]["status"] == "scored" and
                                              d["semantic"]["candidates"][label]["pass"] for d in details)
                                           if encoder else None)
    return {"status": "descriptive_only" if encoder else "semantic_unavailable",
            "gate": gate, "cases": len(cases), "summary": summary, "details": details,
            "primary_metric": "function_words" if gate["features"]["function_words"]["eligible_for_exploratory_scoring"] else None,
            "excluded_from_primary": [name for name, item in gate["features"].items()
                                      if not item["eligible_for_exploratory_scoring"]],
            "limits": "All outputs remain descriptive until a fresh unseen human cohort and independent GPT/Claude generations confirm the protocol. The baseline and every factorial condition must share a content brief. SBERT failure disqualifies a style gain; no encoder means no decision. +Snippet continuation must exclude the anchor."}
