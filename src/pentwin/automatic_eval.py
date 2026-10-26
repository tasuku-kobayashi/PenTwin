"""Private, deterministic comparison of generated prose against two author profiles.

This is a proxy experiment, not a human author-likeness judgment. No paper or
generated passage is returned in the report.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.style_engine import _distance, _measurement, aggregate
from pentwin.validation import FEATURES, diagnose

SCORE_SETS = {**FEATURES,
              "sentence_only": ("sentence_words",),
              "short_passage": ("sentence_words", "hedge_rate", "first_person_rate",
                                "passive_rate", "semicolon_rate", "parenthesis_rate",
                                "question_rate", "rhetoric:contrast", "rhetoric:reason",
                                "rhetoric:limitation")}


def evaluate_generations(manifest_path: Path, cases_path: Path) -> dict:
    if any((parent / ".git").exists() for path in (manifest_path, cases_path)
           for parent in (path.resolve(), *path.resolve().parents)):
        raise CorpusError("Evaluation inputs must remain outside Git working trees")
    source_report = diagnose(manifest_path)
    papers = json.loads(manifest_path.read_text(encoding="utf-8"))["papers"]
    authors = sorted({p["author_id"] for p in papers})
    references: dict[str, list[dict]] = defaultdict(list)
    for paper in papers:
        # The third item per author is reserved for whole-paper diagnostic,
        # never for the generated-text profile.
        if len(references[paper["author_id"]]) >= 2:
            continue
        body = (manifest_path.parent / paper["path"]).resolve().read_text(encoding="utf-8")
        references[paper["author_id"]].append({
            "candidate_id": paper["paper_id"], "source_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "family_id": paper["paper_id"], "split": "development",
            "section": "discussion", "move": "background", "text": body,
        })
    profiles = {author: aggregate(references[author], "discussion") for author in authors}
    if any(p["status"] != "provisional" for p in profiles.values()):
        raise CorpusError("Each author requires two usable reference papers")
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases:
        raise CorpusError("At least one matched generated case is required")
    grouped: dict[str, dict] = defaultdict(dict)
    seen = set()
    for case in cases:
        fields = ("case_id", "content_id", "author_id", "model", "section", "baseline", "guided")
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip() for k in fields):
            raise CorpusError("Cases need nonempty case_id, content_id, author_id, model, section, baseline and guided")
        if case["case_id"] in seen or case["author_id"] not in authors or case["section"] != "discussion":
            raise CorpusError("Cases need distinct IDs, known authors and the discussion section")
        seen.add(case["case_id"])
        group = grouped[case["content_id"]]
        if case["author_id"] in group:
            raise CorpusError("Each content item needs one case per author")
        group[case["author_id"]] = case
    if len(grouped) < 2 or any(set(group) != set(authors) for group in grouped.values()):
        raise CorpusError("At least two content items must each have one case for both authors")
    for group in grouped.values():
        a, b = (group[author] for author in authors)
        if (a["model"], a["section"], a["baseline"]) != (b["model"], b["section"], b["baseline"]):
            raise CorpusError("Both authors must use the same model, section and exact baseline on each content item")

    summaries = {name: {"margin_improved": 0, "target_closer_baseline": 0,
                        "target_closer_guided": 0, "margin_changes": []} for name in SCORE_SETS}
    by_author = {author: {name: {"margin_improved": 0, "target_closer_guided": 0} for name in SCORE_SETS}
                 for author in authors}
    details = []
    for case in cases:
        author = case["author_id"]
        rival = authors[1] if author == authors[0] else authors[0]
        measurements = {label: _measurement([case[label]]) for label in ("baseline", "guided")}
        if any(not measure or measure["_tokens"] < 50 for measure in measurements.values()):
            raise CorpusError("Each draft needs at least 50 measurable words")
        scores = {}
        for name, keys in SCORE_SETS.items():
            margins = {}
            for label, measure in measurements.items():
                own = _distance(measure, profiles[author]["target"])
                other = _distance(measure, profiles[rival]["target"])
                margins[label] = round(sum(other[k] - own[k] for k in keys) / len(keys), 3)
            change = round(margins["guided"] - margins["baseline"], 3)
            scores[name] = {"baseline_margin": margins["baseline"], "guided_margin": margins["guided"],
                            "guided_minus_baseline": change}
            bucket = summaries[name]
            bucket["margin_changes"].append(change)
            bucket["margin_improved"] += change > 0
            bucket["target_closer_baseline"] += margins["baseline"] > 0
            bucket["target_closer_guided"] += margins["guided"] > 0
            by_author[author][name]["margin_improved"] += change > 0
            by_author[author][name]["target_closer_guided"] += margins["guided"] > 0
        details.append({"case_id": case["case_id"], "author_id": author, "model": case["model"],
                        "content_id": case["content_id"], "scores": scores})
    for bucket in summaries.values():
        changes = bucket.pop("margin_changes")
        bucket["mean_margin_change"] = round(sum(changes) / len(changes), 3)
    return {"status": "automated_proxy_only", "cases": len(cases), "content_items": len(grouped),
            "authors": len(authors), "features": {k: list(v) for k, v in SCORE_SETS.items()},
            "source_diagnostic": {"total_correct": source_report["total_correct"],
                                  "confounds": source_report["confounds"]},
            "summary": summaries, "by_author": by_author, "cases_detail": details,
            "limitations": "Raw length includes paragraph sentences measured on full papers, which is mismatched to short drafts. Short_passage excludes that component but was added after inspecting this pilot; its success is exploratory. Scores reuse guidance features and can be gamed. Source writer, era and topic may be confounded. No human or independent LLM judge was used; this does not establish recognizable author voice, scientific correctness, or generalization."}
