"""Private, whole-paper style diagnostics. No source text leaves this process."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.style_engine import FUNCTION_WORDS, _distance, _measurement, aggregate


LENGTH = ("sentence_words", "paragraph_sentences")
SEVEN = LENGTH + ("hedge_rate", "first_person_rate", "passive_rate",
                  "semicolon_rate", "parenthesis_rate")
RHETORIC = SEVEN + ("question_rate", "rhetoric:contrast", "rhetoric:reason",
                    "rhetoric:limitation")
FEATURES = {"length": LENGTH, "seven": SEVEN, "rhetoric": RHETORIC,
            "function": tuple("function:" + word for word in FUNCTION_WORDS)}
CONFOUND_FIELDS = ("publication_month", "topic_id", "journal", "genre", "section", "primary_drafter_verified")


def _confound_audit(groups: dict[str, list[dict]], authors: list[str]) -> dict:
    papers = [paper for author in authors for paper in groups[author]]
    missing = [field for field in CONFOUND_FIELDS if any(field not in p["metadata"] for p in papers)]
    risks = []
    if missing:
        risks.append("missing_confound_metadata")
    for field in ("journal", "genre", "section"):
        if field not in missing and len({p["metadata"][field] for p in papers}) != 1:
            risks.append("different_" + field)
    if "primary_drafter_verified" not in missing and not all(
            p["metadata"]["primary_drafter_verified"] is True for p in papers):
        risks.append("primary_drafter_not_verified")
    if "topic_id" not in missing:
        shared = set(p["metadata"]["topic_id"] for p in groups[authors[0]]) & set(
            p["metadata"]["topic_id"] for p in groups[authors[1]])
        if not shared:
            risks.append("no_reported_cross_author_topic_overlap")
    if "publication_month" not in missing:
        months = [[p["metadata"]["publication_month"] for p in groups[author]] for author in authors]
        if any(not isinstance(month, str) or not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", month)
               for group in months for month in group):
            raise CorpusError("publication_month must have YYYY-MM format")
        if max(min(group) for group in months) > min(max(group) for group in months):
            risks.append("nonoverlapping_author_publication_periods")
    return {"reported_risks": risks, "missing_fields": missing,
            "interpretation": "Metadata can reveal visible confounds but cannot prove an author effect or rule out unrecorded editing and topic effects."}


def diagnose(manifest_path: Path) -> dict:
    """Compare two anonymous authors with three or five independent papers each.

    The report is descriptive, not a generation-quality or authorship certificate.
    File paths, paper text and digests never appear in the returned JSON.
    """
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("papers") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) not in (6, 10):
        raise CorpusError("Diagnostic requires six or ten papers: three or five per anonymous author")
    per_author_required = len(items) // 2
    groups: dict[str, list[dict]] = defaultdict(list)
    seen_ids, seen_paths, seen_hashes, strata = set(), set(), set(), set()
    for item in items:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                             for k in ("author_id", "paper_id", "stratum", "path")):
            raise CorpusError("Each paper needs author_id, paper_id, stratum and path")
        if any(field in item and (not isinstance(item[field], str) or not item[field].strip())
               for field in CONFOUND_FIELDS if field != "primary_drafter_verified") or (
                "primary_drafter_verified" in item and not isinstance(item["primary_drafter_verified"], bool)):
            raise CorpusError("Confound metadata needs nonempty strings and a Boolean writing-role confirmation")
        author, paper_id = item["author_id"], item["paper_id"]
        if paper_id in seen_ids:
            raise CorpusError("paper_id must be unique")
        seen_ids.add(paper_id)
        strata.add(item["stratum"])
        path = (manifest_path.parent / item["path"]).resolve()
        if path in seen_paths:
            raise CorpusError("Paper paths must be independent")
        seen_paths.add(path)
        body = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(" ".join(body.split()).encode()).hexdigest()
        if digest in seen_hashes:
            raise CorpusError("Duplicate paper text is not an independent family")
        seen_hashes.add(digest)
        if len(body.split()) < 100 or not _measurement([body]):
            raise CorpusError("Each paper needs at least 100 words of reviewed body text")
        groups[author].append({"id": paper_id, "text": body, "metadata": item})
    if len(groups) != 2 or any(len(papers) != per_author_required for papers in groups.values()) or len(strata) != 1:
        raise CorpusError(f"Use two authors with {per_author_required} papers each in one matched stratum")

    def profile(papers: list[dict]) -> dict:
        rows = [{"candidate_id": paper["id"], "source_sha256": paper["id"],
                 "family_id": paper["id"], "split": "development", "section": "discussion",
                 "text": paper["text"]} for paper in papers]
        result = aggregate(rows, "discussion")
        if result["status"] != "provisional":
            raise CorpusError("Each reference paper needs at least two measured sentences")
        return result["target"]

    authors = sorted(groups)
    cases = []
    for author in authors:
        rival = authors[1] if author == authors[0] else authors[0]
        for position, paper in enumerate(groups[author]):
            own = profile([p for i, p in enumerate(groups[author]) if i != position])
            other = profile([p for i, p in enumerate(groups[rival]) if i != position])
            actual = _measurement([paper["text"]])
            own_dist, other_dist = _distance(actual, own), _distance(actual, other)
            scores = {}
            for name, keys in FEATURES.items():
                a = sum(own_dist[key] for key in keys) / len(keys)
                b = sum(other_dist[key] for key in keys) / len(keys)
                scores[name] = {"own": round(a, 3), "rival": round(b, 3),
                                "result": "own" if a < b else "rival" if b < a else "tie"}
            cases.append({"author_id": author, "paper_id": paper["id"], "scores": scores})
    per_author = {author: {name: sum(c["scores"][name]["result"] == "own" for c in cases
                                     if c["author_id"] == author) for name in FEATURES} for author in authors}
    total = {name: sum(counts[name] for counts in per_author.values()) for name in FEATURES}
    paired = {name: {"gain_over_length": sum(c["scores"][name]["result"] == "own" and
                                         c["scores"]["length"]["result"] != "own" for c in cases),
                     "loss_to_length": sum(c["scores"][name]["result"] != "own" and
                                           c["scores"]["length"]["result"] == "own" for c in cases)}
              for name in FEATURES if name != "length"}
    return {"status": "diagnostic_only", "stratum": next(iter(strata)), "papers": len(items),
            "feature_sets": {name: list(keys) for name, keys in FEATURES.items()},
            "per_author_correct": per_author, "total_correct": total,
            "increment_over_length": {name: total[name] - total["length"] for name in FEATURES if name != "length"},
            "paired_vs_length": paired, "confounds": _confound_audit(groups, authors),
            "cases": cases,
            "limitations": "Two authors and a small corpus cannot establish author likeness. Match genre, section, topic and time where possible; inspect source extraction and report confounds. This does not evaluate generated text."}
