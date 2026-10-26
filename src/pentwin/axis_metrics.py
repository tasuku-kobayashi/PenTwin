"""Prespecified axis-specific proxies, evaluated on 200+ word passages.

Content word overlap is topic-sensitive. Cue-order and final-ten-word patterns
are surface proxies, not parsed syntax or an authorship certificate.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pentwin.ablation_protocol import DIRECT
from pentwin.cli import CorpusError
from pentwin.exploratory_card import _cue
from pentwin.paper_grounded_eval import MIN_WORDS, _window
from pentwin.style_engine import FUNCTION_WORDS, HEDGES, PASSIVE, WORD, _sentences
from pentwin.validation import diagnose


STOP = set(FUNCTION_WORDS) | {"a", "an", "and", "as", "at", "by", "from", "in", "is",
                              "it", "on", "our", "was", "we", "were", "are", "be"}
AXIS_METRICS = {"lexical": "content_jaccard", "ending": "function_and_ending",
                "order": "discourse_transitions"}
ACADEMIC = re.compile(r"\b(?:in this study|taken together|these findings|further studies|in contrast)\b", re.I)


def measure(text: str) -> dict:
    sentences = _sentences(text)
    words = [w.lower() for sentence in sentences for w in WORD.findall(sentence)]
    if len(words) < MIN_WORDS:
        raise CorpusError("Every evaluated passage needs at least 200 measurable English words")
    tails = [" ".join(WORD.findall(sentence)[-10:]) for sentence in sentences]
    cues = [cue for sentence in sentences if (cue := _cue(sentence))]
    edges = Counter(zip(cues, cues[1:]))
    return {"content": set(words) - STOP, "tokens": words,
            "function": {w: words.count(w) / len(words) for w in FUNCTION_WORDS},
            "ending": {"qualified": sum(bool(HEDGES.search(t)) for t in tails) / len(tails),
                       "direct": sum(bool(DIRECT.search(t)) for t in tails) / len(tails)},
            "edges": {edge: count / sum(edges.values()) for edge, count in edges.items()},
            "edge_count": sum(edges.values()), "words": len(words),
            "passive_rate": sum(bool(PASSIVE.search(s)) for s in sentences) / len(sentences),
            "formulaic_rate": sum(bool(ACADEMIC.search(s)) for s in sentences) / len(sentences)}


def profile(samples: list[dict]) -> dict:
    if len(samples) != 2:
        raise CorpusError("Each profile needs exactly two independent reference papers")
    return {"content": samples[0]["content"] | samples[1]["content"],
            "recurring_terms": samples[0]["content"] & samples[1]["content"],
            "function": {w: sum(s["function"][w] for s in samples) / 2 for w in FUNCTION_WORDS},
            "ending": {w: sum(s["ending"][w] for s in samples) / 2 for w in ("qualified", "direct")},
            "edges": {e: sum(s["edges"].get(e, 0) for s in samples) / 2
                      for e in samples[0]["edges"].keys() | samples[1]["edges"].keys()},
            "edge_count": sum(s["edge_count"] for s in samples)}


def _l1(a: dict, b: dict) -> float:
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in a.keys() | b.keys())


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def margins(candidate: dict, own: dict, rival: dict) -> dict[str, float | None]:
    lexical = _jaccard(candidate["content"], own["content"]) - _jaccard(candidate["content"], rival["content"])
    function = (_l1(candidate["function"], rival["function"]) -
                _l1(candidate["function"], own["function"]))
    ending = (_l1(candidate["ending"], rival["ending"]) -
              _l1(candidate["ending"], own["ending"]))
    # Do not let the much larger function-word vector silently drown the ending.
    combined = (function + ending) / 2
    order = None
    if candidate["edge_count"] >= 2 and own["edge_count"] >= 2 and rival["edge_count"] >= 2:
        order = _l1(candidate["edges"], rival["edges"]) - _l1(candidate["edges"], own["edges"])
    return {"lexical": round(lexical, 5), "ending": round(combined, 5),
            "order": round(order, 5) if order is not None else None,
            "function_component": round(function, 5), "ending_component": round(ending, 5)}


def technical_term_coverage(candidate: dict, reviewed_terms: list[str]) -> float | None:
    """Optional controlled vocabulary, reviewed outside this module; never infer terms from a topic."""
    if not reviewed_terms:
        return None
    terms = {tuple(w.lower() for w in WORD.findall(term)) for term in reviewed_terms if term.strip()}
    if not terms or () in terms:
        raise CorpusError("Reviewed technical terms need English word tokens")
    tokens = candidate["tokens"]
    hits = sum(any(tuple(tokens[i:i + len(term)]) == term
                   for i in range(len(tokens) - len(term) + 1)) for term in terms)
    return round(hits / len(terms), 4)


def calibrate(manifest: Path) -> dict:
    audit = diagnose(manifest)
    papers = json.loads(manifest.read_text(encoding="utf-8"))["papers"]
    groups = defaultdict(list)
    for paper in papers:
        body = (manifest.parent / paper["path"]).resolve().read_text(encoding="utf-8")
        # Shared passage selection; subsequent measurement keeps the entire
        # selected sentence so punctuation and cue windows align.
        _window(body)
        selected = []
        for sentence in _sentences(body):
            selected.append(sentence)
            if sum(len(WORD.findall(s)) for s in selected) >= MIN_WORDS:
                break
        groups[paper["author_id"]].append((paper["paper_id"], measure(" ".join(selected))))
    authors = sorted(groups)
    rows = []
    for author in authors:
        rival = next(a for a in authors if a != author)
        for index, (paper_id, held) in enumerate(groups[author]):
            own = profile([sample for j, (_, sample) in enumerate(groups[author]) if j != index])
            other = profile([sample for j, (_, sample) in enumerate(groups[rival]) if j != index])
            rows.append({"author_id": author, "paper_id": paper_id, "words": held["words"],
                         "edge_count": held["edge_count"], "margins": margins(held, own, other)})
    totals = {axis: {author: {"correct": sum(row["author_id"] == author and row["margins"][axis] is not None
                                            and row["margins"][axis] > 0 for row in rows),
                              "available": sum(row["author_id"] == author and row["margins"][axis] is not None
                                               for row in rows)} for author in authors} for axis in AXIS_METRICS}
    domain = {author: {key: round(sum(sample[key] for _, sample in groups[author]) / 3, 3)
                       for key in ("passive_rate", "formulaic_rate")}
              for author in authors}
    return {"metrics": AXIS_METRICS, "per_author": totals, "cases": rows,
            "domain_diagnostics": domain,
            "confounds": audit["confounds"]["reported_risks"],
            "limitations": "Topic and section can dominate content Jaccard. Ending and order use fixed surface patterns and may abstain; no POS tagger or syntactic parser is used."}
