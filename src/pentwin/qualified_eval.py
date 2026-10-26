"""Frozen two-cohort eligibility screen for exploratory style experiments.

Both cohorts are human-authored. They are not an independent confirmation set
when their texts or results were already inspected while designing features.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.axis_metrics import AXIS_METRICS, calibrate, margins, measure, profile, technical_term_coverage
from pentwin.paper_grounded_eval import MIN_WORDS
from pentwin.style_engine import _sentences, WORD
from pentwin.semantic_guard import load_semantic_scores, semantic_guard, semantic_guard_from_scores
from pentwin.ablation_protocol import AXES, CONDITIONS
from collections import defaultdict


# Operational permission to *explore* a matching axis, not an estimate of
# out-of-sample attribution or a threshold on generated-text quality.
PAPERS_PER_AUTHOR = 5
MIN_CORRECT = 7
MIN_EACH_AUTHOR = 3


def _digests(manifest: Path) -> set[str]:
    data = json.loads(manifest.read_text(encoding="utf-8"))["papers"]
    return {hashlib.sha256((manifest.parent / row["path"]).resolve().read_bytes()).hexdigest()
            for row in data}


def qualify_evaluators(first: Path, second: Path) -> dict:
    for manifest in (first, second):
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("papers"), list) or len(payload["papers"]) != 2 * PAPERS_PER_AUTHOR:
            raise CorpusError("The 7/10 evaluator gate requires ten human papers per cohort, five per author")
    if first.resolve() == second.resolve() or _digests(first) & _digests(second):
        raise CorpusError("Calibration cohorts must not reuse a paper")
    a, b = calibrate(first), calibrate(second)
    axes = {}
    for axis in AXIS_METRICS:
        counts = [report["per_author"][axis] for report in (a, b)]
        qualified = all(sum(item["correct"] for item in cohort.values()) >= MIN_CORRECT and
                        all(item["correct"] >= MIN_EACH_AUTHOR and item["available"] == PAPERS_PER_AUTHOR
                            for item in cohort.values()) for cohort in counts)
        content_counts = [report["per_author"]["content_jaccard"] for report in (a, b)] if axis == "lexical" else None
        if content_counts is not None:
            qualified = qualified and all(sum(item["correct"] for item in cohort.values()) >= MIN_CORRECT and
                                          all(item["correct"] >= MIN_EACH_AUTHOR and item["available"] == PAPERS_PER_AUTHOR
                                              for item in cohort.values()) for cohort in content_counts)
        axes[axis] = {"metric": AXIS_METRICS[axis],
                      "correct": [sum(item["correct"] for item in cohort.values()) for cohort in counts],
                      "available": [sum(item["available"] for item in cohort.values()) for cohort in counts],
                      "per_author": [[item["correct"] for item in sorted(cohort.values(), key=lambda x: x["correct"])]
                                     for cohort in counts],
                      "writer_imbalance": [max(item["correct"] for item in cohort.values()) -
                                           min(item["correct"] for item in cohort.values()) >= 3
                                           for cohort in counts],
                      "content_jaccard_correct": ([sum(item["correct"] for item in cohort.values())
                                                   for cohort in content_counts] if content_counts else None),
                      "eligible_for_exploratory_scoring": qualified}
    eligible = [axis for axis, item in axes.items() if item["eligible_for_exploratory_scoring"]]
    journal = []
    for report in (a, b):
        control = report["journal_only_control"]
        journal.append(None if control is None else {
            "correct": sum(item["correct"] for item in control.values()),
            "available": sum(item["available"] for item in control.values()),
            "per_author": sorted(item["correct"] for item in control.values())})
    lexical_confounded = any(control is not None and control["available"] >= 2 * PAPERS_PER_AUTHOR - 1 and
                             control["correct"] >= axes["lexical"]["correct"][i]
                             for i, control in enumerate(journal))
    return {"status": "exploratory_eligible" if len(eligible) == len(axes) else
            "partial_exploratory_eligible" if eligible else "ineligible",
            "threshold": {"per_cohort": "at least 7/10", "per_author": "at least 3/5", "cohorts_required": 2},
            "axes": axes, "matrix": AXIS_METRICS,
            "risks": [a["confounds"], b["confounds"]],
            "journal_only_control": journal,
            "lexical_journal_confound_warning": lexical_confounded,
            "domain_diagnostics": [a["domain_diagnostics"], b["domain_diagnostics"]],
            "interpretation": "Each style axis is judged only by its matching metric; lexical needs both the fixed generation-card vocabulary and raw content overlap to pass. The journal-only comparator reports correct among available decisions; ties abstain. A journal control matching lexical discrimination flags confounding but cannot prove its cause. All ten human papers per cohort must be measurable. Seven of ten is an operational exploration gate, not a validated accuracy estimate; five-plus-two writer splits fail the 3/5 per-writer requirement. A fair two-choice guess reaches at least seven in 176/1024 independent trials, but overlapping leave-one-out cases are not independent. Previously inspected cohorts do not establish external validity. Failed axes abstain from generation acceptance."}


def _required_variants(eligible_axes: list[str]) -> set[str]:
    """The complete factorial over eligible axes, using the public labels."""
    selected = set(eligible_axes)
    return {label for label in CONDITIONS if label != "none" and
            set(AXES if label == "all" else label.split("_")) <= selected}


def evaluate_factorial(first: Path, second: Path, cases_path: Path, encoder=None,
                       semantic_scores_path: Path | None = None) -> dict:
    """Score a full 2^3 experiment; no winning condition without SBERT."""
    if encoder is not None and semantic_scores_path is not None:
        raise CorpusError("Choose either local SBERT or imported semantic scores")
    if any((parent / ".git").exists() for path in (first, second, cases_path)
           for parent in (path.resolve(), *path.resolve().parents)):
        raise CorpusError("Private evaluation inputs must remain outside Git working trees")
    imported = load_semantic_scores(semantic_scores_path) if semantic_scores_path else None
    gate = qualify_evaluators(first, second)
    papers = json.loads(first.read_text(encoding="utf-8"))["papers"]
    groups = defaultdict(list)
    for paper in papers:
        if len(groups[paper["author_id"]]) >= PAPERS_PER_AUTHOR - 1:
            continue
        body = (first.parent / paper["path"]).resolve().read_text(encoding="utf-8")
        selected = []
        words = 0
        for sentence in _sentences(body):
            selected.append(sentence)
            words += len(WORD.findall(sentence))
            if words >= MIN_WORDS:
                break
        groups[paper["author_id"]].append(measure(" ".join(selected)))
    authors = sorted(groups)
    profiles = {a: profile(groups[a]) for a in authors}
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise CorpusError("Need a nonempty cases list")
    paired = defaultdict(dict)
    seen = set()
    full = set(CONDITIONS) - {"none"}
    reduced = _required_variants([axis for axis, item in gate["axes"].items()
                                  if item["eligible_for_exploratory_scoring"]])
    allowed_plans = {frozenset(full)}
    if reduced:
        allowed_plans.add(frozenset(reduced))
    common_labels = None
    for case in cases:
        fields = ("case_id", "author_id", "content_id", "model", "section", "content_brief", "baseline")
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip()
                                             for k in fields):
            raise CorpusError("Cases need identifiers, model, discussion section, content brief and baseline")
        if case["case_id"] in seen or case["author_id"] not in authors or case["section"] != "discussion":
            raise CorpusError("Invalid case ID, author or section")
        seen.add(case["case_id"])
        variants = case.get("variants")
        if not isinstance(variants, dict):
            raise CorpusError("Variants must contain the full factorial or every eligible-axis condition")
        snippet = {label for label in variants if label.endswith("_snippet")}
        base_labels = set(variants) - snippet
        if frozenset(base_labels) not in allowed_plans or len(snippet) > 1 or any(
                label[:-8] not in base_labels for label in snippet):
            raise CorpusError("Variants need all seven card conditions or a complete eligible-axis factorial, plus an optional matching snippet")
        if common_labels is None:
            common_labels = set(variants)
        elif set(variants) != common_labels:
            raise CorpusError("Use identical variant labels across all cases")
        if any(not isinstance(v, str) or not v.strip() for v in variants.values()):
            raise CorpusError("Every variant needs nonempty continuation text")
        if snippet:
            anchor = case.get("snippet_anchor")
            if not isinstance(anchor, str) or not anchor.strip():
                raise CorpusError("Snippet condition requires its private human-authored anchor")
            if variants[next(iter(snippet))].lstrip().startswith(anchor.strip()):
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
    if imported and set(imported["cases"]) != seen:
        raise CorpusError("Semantic score case IDs must exactly match the generated cases")
    reviewed_terms = data.get("reviewed_technical_terms", [])
    if not isinstance(reviewed_terms, list) or any(not isinstance(t, str) for t in reviewed_terms):
        raise CorpusError("reviewed_technical_terms must be a list of strings")
    details = []
    for case in cases:
        author = case["author_id"]
        rival = next(a for a in authors if a != author)
        labels = ["none"] + sorted(case["variants"])
        drafts = {"none": case["baseline"], **case["variants"]}
        measures = {label: measure(drafts[label]) for label in labels}
        base_margins = margins(measures["none"], profiles[author], profiles[rival])
        scores = {axis: {} for axis in AXIS_METRICS}
        for label in case["variants"]:
            current = margins(measures[label], profiles[author], profiles[rival])
            for axis in AXIS_METRICS:
                before, after = base_margins[axis], current[axis]
                scores[axis][label] = round(after - before, 5) if before is not None and after is not None else None
        semantics = (semantic_guard_from_scores(case["content_brief"], case["baseline"], case["variants"], case["case_id"], imported)
                     if imported else semantic_guard(case["content_brief"], case["baseline"], case["variants"], encoder)
                     if encoder else None)
        details.append({"case_id": case["case_id"], "author_id": author, "content_id": case["content_id"],
                        "margin_changes": scores, "semantic": semantics,
                        "technical_term_coverage": {label: technical_term_coverage(measures[label], reviewed_terms)
                                                    for label in labels}})
    summary = {}
    for label in sorted(cases[0]["variants"]):
        summary[label] = {axis: {"improved": sum(d["margin_changes"][axis][label] is not None and
                                                 d["margin_changes"][axis][label] > 0 for d in details),
                                 "measurable": sum(d["margin_changes"][axis][label] is not None for d in details),
                                 "of": len(details),
                                 "eligible": gate["axes"][axis]["eligible_for_exploratory_scoring"],
                                 "improved_and_semantic_pass": (sum(
                                     d["margin_changes"][axis][label] is not None and
                                     d["margin_changes"][axis][label] > 0 and
                                     d["semantic"]["candidates"][label]["pass"] for d in details)
                                     if (encoder or imported) and gate["axes"][axis]["eligible_for_exploratory_scoring"]
                                     else None)}
                          for axis in AXIS_METRICS}
        summary[label]["semantic_pass"] = (sum(d["semantic"]["status"] == "scored" and
                                              d["semantic"]["candidates"][label]["pass"] for d in details)
                                           if encoder or imported else None)
    return {"status": "evaluator_ineligible" if gate["status"] == "ineligible" else
            "descriptive_only" if encoder or imported else "semantic_unavailable",
            "gate": gate, "cases": len(cases), "summary": summary, "details": details,
            "condition_set": "full_factorial" if set(cases[0]["variants"]) -
            {label for label in cases[0]["variants"] if label.endswith("_snippet")} == full else "eligible_axes_only",
            "eligible_axes": [axis for axis, item in gate["axes"].items()
                              if item["eligible_for_exploratory_scoring"]],
            "excluded_axes": [axis for axis, item in gate["axes"].items()
                              if not item["eligible_for_exploratory_scoring"]],
            "limits": "All outputs remain descriptive until a fresh unseen human cohort and independent GPT/Claude generations confirm the protocol. The baseline and every factorial condition must share a content brief. SBERT failure disqualifies a style gain; no encoder means no decision. +Snippet continuation must exclude the anchor."}
