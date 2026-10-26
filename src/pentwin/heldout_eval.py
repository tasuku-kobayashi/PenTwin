"""Exploratory same-content ablations scored against unseen paper text.

Holdout features never select a style card; they are only read for scoring.
This is a descriptive proxy and requires independent future validation.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.exploratory_card import _cue
from pentwin.style_card import CONNECTIVE_PATTERNS, STANCE_CUES, STANCE_PATTERNS
from pentwin.style_engine import _sentences
from pentwin.validation import diagnose

AXES = ("wording", "cue_order", "stance", "combined")
PATTERNS = {**CONNECTIVE_PATTERNS, **STANCE_PATTERNS}


def _features(text: str) -> dict:
    sentences = _sentences(text)
    if len(sentences) < 2:
        raise CorpusError("Generated and held-out texts need at least two measurable sentences")
    lexical = {term: sum(bool(pattern.search(s)) for s in sentences) / len(sentences)
               for term, pattern in PATTERNS.items()}
    stance = {name: sum(bool(pattern.search(s)) for s in sentences) / len(sentences)
              for name, pattern in STANCE_CUES.items()}
    labels = [label for s in sentences if (label := _cue(s))]
    edges = Counter(zip(labels, labels[1:]))
    total_edges = sum(edges.values())
    return {"wording": lexical, "stance": stance,
            "cue_order": {edge: count / len(sentences) for edge, count in edges.items()},
            "cue_edges": total_edges}


def _margin(candidate: dict, own: dict, rival: dict, axis: str) -> float | None:
    def distance(anchor: dict) -> float | None:
        # An empty cue sequence is an observed zero rate, not an error or an
        # instruction to invent a transition.
        own_features, reference = candidate[axis], anchor[axis]
        keys = set(own_features) | set(reference)
        return sum(abs(own_features.get(key, 0) - reference.get(key, 0)) for key in keys)
    a, b = distance(own), distance(rival)
    return None if a is None or b is None else round(b - a, 3)


def evaluate_heldout_axes(manifest_path: Path, cases_path: Path) -> dict:
    for path in (manifest_path, cases_path):
        if any((parent / ".git").exists() for parent in (path.resolve(), *path.resolve().parents)):
            raise CorpusError("Private evaluation inputs must remain outside Git working trees")
    source_report = diagnose(manifest_path)
    papers = json.loads(manifest_path.read_text(encoding="utf-8"))["papers"]
    authors = sorted({paper["author_id"] for paper in papers})
    groups: dict[str, list[dict]] = defaultdict(list)
    for paper in papers:
        groups[paper["author_id"]].append(paper)
    holdout = {author: _features((manifest_path.parent / groups[author][2]["path"]).resolve().read_text(encoding="utf-8"))
               for author in authors}
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases:
        raise CorpusError("Need a private generated cases list")
    seen, paired = set(), defaultdict(dict)
    for case in cases:
        fields = ("case_id", "content_id", "author_id", "axis", "model", "baseline", "guided")
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip() for k in fields):
            raise CorpusError("Each case needs case_id, content_id, author_id, axis, model, baseline and guided")
        if case["case_id"] in seen or case["axis"] not in AXES or case["author_id"] not in authors:
            raise CorpusError("Invalid or duplicate case")
        seen.add(case["case_id"])
        key = (case["content_id"], case["axis"])
        if case["author_id"] in paired[key]:
            raise CorpusError("Each content/axis pair needs one draft per author")
        paired[key][case["author_id"]] = case
    if len({content for content, _ in paired}) < 2 or any(set(group) != set(authors) for group in paired.values()):
        raise CorpusError("At least two content items, with both authors per tested axis, are required")
    baselines = defaultdict(set)
    for (content, axis), group in paired.items():
        for case in group.values():
            baselines[content].add((case["baseline"], case["model"]))
    if any(len(values) != 1 for values in baselines.values()):
        raise CorpusError("Use exactly the same baseline and model across authors and axes for a content item")
    summary = {axis: {"cases": 0, "improved": 0, "target_closer_guided": 0, "abstained": 0}
               for axis in AXES}
    by_author = {author: {axis: {"improved": 0, "abstained": 0} for axis in AXES} for author in authors}
    detail = []
    for case in cases:
        author, axis = case["author_id"], case["axis"]
        rival = authors[1] if author == authors[0] else authors[0]
        if min(len(case["baseline"].split()), len(case["guided"].split())) < 50:
            raise CorpusError("Each generated passage needs at least 50 words")
        before, after = _features(case["baseline"]), _features(case["guided"])
        dimensions = ("wording", "cue_order", "stance") if axis == "combined" else (axis,)
        margins = {}
        for label, features in (("baseline", before), ("guided", after)):
            parts = [_margin(features, holdout[author], holdout[rival], dimension) for dimension in dimensions]
            available = [value for value in parts if value is not None]
            margins[label] = round(sum(available) / len(available), 3) if available else None
        bucket, per_writer = summary[axis], by_author[author][axis]
        bucket["cases"] += 1
        if margins["baseline"] is None or margins["guided"] is None:
            bucket["abstained"] += 1
            per_writer["abstained"] += 1
            outcome = "abstained"
        else:
            gain = margins["guided"] - margins["baseline"]
            bucket["improved"] += gain > 0
            per_writer["improved"] += gain > 0
            bucket["target_closer_guided"] += margins["guided"] > 0
            outcome = "improved" if gain > 0 else "not_improved"
        detail.append({"case_id": case["case_id"], "author_id": author, "content_id": case["content_id"],
                       "axis": axis, "baseline_margin": margins["baseline"], "guided_margin": margins["guided"],
                       "outcome": outcome})
    return {"status": "exploratory_heldout_proxy", "cases": len(cases), "summary": summary,
            "by_author": by_author, "cases_detail": detail,
            "source_confound_risks": source_report["confounds"]["reported_risks"],
            "limitations": "Scores compare fixed surface cues in short outputs with whole held-out articles. A zero cue-transition rate is retained as evidence, but a single observed transition is highly unstable. These are not independent author-likeness judgments. This cohort and scoring choices were inspected during development; topic, period and drafting-role confounds remain."}
