"""Small-corpus, human-text-calibrated evaluation inspired by Wang et al. (2025).

This is a transparent proxy, not their trained AA/AV or LIWC/WritePrint model.
Private source texts and generated passages never appear in the report.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.style_engine import FUNCTION_WORDS, _distance, _measurement, _sentences
from pentwin.validation import diagnose


# Frozen independently of the pilot's results. Function rates are withheld from
# rewrite_plan; the structural set is a separate, partly overlapping diagnostic.
FEATURES = {
    "function_words": tuple("function:" + word for word in FUNCTION_WORDS),
    "surface_structure": ("sentence_words", "semicolon_rate", "parenthesis_rate", "question_rate"),
}
WINDOW_SENTENCES = 7
MIN_WORDS = 50


def _window(body: str) -> dict:
    sentences = _sentences(body)
    measure = _measurement([" ".join(sentences[:WINDOW_SENTENCES])])
    if not measure or measure["_tokens"] < MIN_WORDS:
        raise CorpusError("Each source needs at least 50 measurable words in its first seven sentences")
    return measure


def _reference(rows: list[dict]) -> dict:
    # A whole paper has one vote. Windows use the same unit as short drafts.
    keys = [key for key in rows[0]["measurement"] if not key.startswith("_")]
    return {key: sum(row["measurement"][key] for row in rows) / len(rows) for key in keys}


def _margin(measure: dict, own: dict, rival: dict, keys: tuple[str, ...]) -> float:
    a, b = _distance(measure, own), _distance(measure, rival)
    return (sum(b[key] - a[key] for key in keys) / len(keys))


def evaluate_paper_grounded(manifest_path: Path, cases_path: Path | None = None) -> dict:
    """Calibrate on whole-paper splits, then score optional paired generations.

    The first two papers per author are the generation reference. The third is
    reserved for future confirmation; LOPO calibration is exploratory when
    the cohort has already been inspected during development.
    """
    paths = [manifest_path] + ([cases_path] if cases_path else [])
    if any((parent / ".git").exists() for path in paths
           for parent in (path.resolve(), *path.resolve().parents)):
        raise CorpusError("Private evaluation inputs must remain outside Git working trees")
    source = diagnose(manifest_path)  # also checks independent text and matched stratum
    items = json.loads(manifest_path.read_text(encoding="utf-8"))["papers"]
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        body = (manifest_path.parent / item["path"]).resolve().read_text(encoding="utf-8")
        groups[item["author_id"]].append({"id": item["paper_id"], "measurement": _window(body)})
    authors = sorted(groups)
    calibration = []
    for author in authors:
        rival = next(name for name in authors if name != author)
        for i, held in enumerate(groups[author]):
            own = _reference([row for j, row in enumerate(groups[author]) if j != i])
            other = _reference([row for j, row in enumerate(groups[rival]) if j != i])
            margins = {name: round(_margin(held["measurement"], own, other, keys), 3)
                       for name, keys in FEATURES.items()}
            calibration.append({"author_id": author, "paper_id": held["id"], "margins": margins})
    counts = {name: {author: sum(row["author_id"] == author and row["margins"][name] > 0
                                 for row in calibration) for author in authors} for name in FEATURES}
    # 5/6 is an operational screen, not a significance or likeness threshold.
    ready = {name: sum(counts[name].values()) >= 5 and min(counts[name].values()) >= 2
             for name in FEATURES}
    report = {"status": "human_calibration_only", "source_papers": 6,
              "unit": "first seven measurable sentences per paper, minimum 50 words",
              "features": {name: list(keys) for name, keys in FEATURES.items()},
              "calibration": {"correct_by_author": counts, "passes_exploratory_screen": ready,
                              "cases": calibration},
              "source_confound_risks": source["confounds"]["reported_risks"],
              "limits": "A 5/6 operational screen on six related papers is not statistical proof. LOPO tests text attribution, not generated voice; this cohort may have been inspected before. Structure includes length and may reflect journal or era. No trained AA/AV, LIWC, AI detector or human judgment is used."}
    if cases_path is None:
        return report
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases:
        raise CorpusError("Cases must contain a nonempty list")
    profiles = {author: _reference(groups[author][:2]) for author in authors}
    paired: dict[str, dict] = defaultdict(dict)
    seen = set()
    for case in cases:
        fields = ("case_id", "content_id", "author_id", "model", "section", "baseline", "guided")
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip()
                                             for k in fields):
            raise CorpusError("Cases require nonempty case_id, content_id, author_id, model, section, baseline and guided")
        if case["case_id"] in seen or case["author_id"] not in authors or case["section"] != "discussion":
            raise CorpusError("Cases need distinct IDs, known authors and discussion section")
        seen.add(case["case_id"])
        if case["author_id"] in paired[case["content_id"]]:
            raise CorpusError("Each content item needs one case per author")
        paired[case["content_id"]][case["author_id"]] = case
    if len(paired) < 2 or any(set(group) != set(authors) for group in paired.values()):
        raise CorpusError("At least two matched content items with both authors are required")
    for group in paired.values():
        left, right = (group[author] for author in authors)
        if (left["model"], left["section"], left["baseline"]) != (right["model"], right["section"], right["baseline"]):
            raise CorpusError("Both authors need the exact same model, section and baseline per content item")
    results = []
    for case in cases:
        author = case["author_id"]
        rival = next(name for name in authors if name != author)
        measurements = {label: _measurement([case[label]]) for label in ("baseline", "guided")}
        if any(not m or m["_tokens"] < MIN_WORDS for m in measurements.values()):
            raise CorpusError("Each generated passage needs at least 50 measurable words")
        scores = {}
        for name, keys in FEATURES.items():
            margins = {label: round(_margin(m, profiles[author], profiles[rival], keys), 3)
                       for label, m in measurements.items()}
            scores[name] = {"baseline_margin": margins["baseline"], "guided_margin": margins["guided"],
                            "improved": margins["guided"] > margins["baseline"]}
        results.append({"case_id": case["case_id"], "content_id": case["content_id"],
                        "author_id": author, "scores": scores})
    summary = {name: {"improved": sum(row["scores"][name]["improved"] for row in results),
                      "of": len(results)} for name in FEATURES}
    report.update({"status": "single_cohort_proxy_unqualified" if all(ready.values()) else "calibration_inadequate",
                   "generated": {"cases": len(results), "summary": summary, "cases_detail": results,
                                 "interpretation": "Descriptive distances only; no author-likeness conclusion."}})
    return report
