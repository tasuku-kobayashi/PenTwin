"""Private, whole-paper style diagnostics. No source text leaves this process."""

from __future__ import annotations

import hashlib
import json
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


def diagnose(manifest_path: Path) -> dict:
    """Compare two anonymous authors, exactly three independent papers each.

    The report is descriptive, not a generation-quality or authorship certificate.
    File paths, paper text and digests never appear in the returned JSON.
    """
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("papers") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) != 6:
        raise CorpusError("Diagnostic requires exactly six papers: three per anonymous author")
    groups: dict[str, list[dict]] = defaultdict(list)
    seen_ids, seen_paths, seen_hashes, strata = set(), set(), set(), set()
    for item in items:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                             for k in ("author_id", "paper_id", "stratum", "path")):
            raise CorpusError("Each paper needs author_id, paper_id, stratum and path")
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
        groups[author].append({"id": paper_id, "text": body})
    if len(groups) != 2 or any(len(papers) != 3 for papers in groups.values()) or len(strata) != 1:
        raise CorpusError("Use two authors with three papers each in one matched stratum")

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
    return {"status": "diagnostic_only", "stratum": next(iter(strata)), "papers": 6,
            "feature_sets": {name: list(keys) for name, keys in FEATURES.items()},
            "per_author_correct": per_author, "total_correct": total,
            "increment_over_length": {name: total[name] - total["length"] for name in FEATURES if name != "length"},
            "cases": cases,
            "limitations": "Two authors and six papers cannot establish author likeness. Match genre, section, topic and time where possible; inspect source extraction and report confounds. This does not evaluate generated text."}
