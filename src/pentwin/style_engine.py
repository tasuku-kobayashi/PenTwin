"""Local, non-generative author-style measurements and rewrite guidance.

Only aggregate, closed-vocabulary features leave this module. Source passages,
identifiers, and learned word sequences are never returned to an MCP client.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from statistics import median

from pentwin.cli import CorpusError


WORD = re.compile(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
HEDGES = re.compile(r"\b(?:may|might|could|suggest(?:s|ed)?|appear(?:s|ed)?|potentially|possibly)\b", re.I)
FIRST_PERSON = re.compile(r"\b(?:we|our|us)\b", re.I)
PASSIVE = re.compile(r"\b(?:was|were|is|are|been|be)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.I)
CITATION = re.compile(r"\[(?:\d+[ ,;\-]*)+\]|\((?:[A-Z][A-Za-z'-]+\s+et\s+al\.,?\s*)?\d{4}[a-z]?\)")
CONNECTORS = ("however", "therefore", "thus", "moreover", "furthermore", "notably",
              "in contrast", "by contrast", "in addition", "taken together", "whereas")
STANCE = ("suggest", "indicate", "demonstrate", "show", "reveal", "support", "observe", "report")
SECTIONS = {"abstract", "introduction", "methods", "results", "discussion", "conclusion"}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE.split(text.strip()) if len(WORD.findall(part)) >= 5]


def _measurement(texts: list[str]) -> dict[str, float]:
    paragraphs = [part.strip() for text in texts for part in re.split(r"\n\s*\n", text) if part.strip()]
    sentences = [sentence for part in paragraphs for sentence in _sentences(part)]
    if not sentences:
        return {}
    lengths = [len(WORD.findall(sentence)) for sentence in sentences]
    total = len(sentences)
    tokens = sum(lengths)
    combined = " ".join(sentences).lower()
    counts = Counter()
    for phrase in CONNECTORS + STANCE:
        counts[phrase] = len(re.findall(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", combined))
    return {"sentence_words": float(median(lengths)),
            "paragraph_sentences": len(sentences) / max(1, len(paragraphs)),
            "hedge_rate": sum(bool(HEDGES.search(s)) for s in sentences) / total,
            "first_person_rate": sum(bool(FIRST_PERSON.search(s)) for s in sentences) / total,
            "passive_rate": sum(bool(PASSIVE.search(s)) for s in sentences) / total,
            "citation_rate": sum(bool(CITATION.search(s)) for s in sentences) / total,
            "semicolon_rate": sum(";" in s for s in sentences) / total,
            "parenthesis_rate": sum("(" in s for s in sentences) / total,
            **{f"connector:{word}": counts[word] / total for word in CONNECTORS},
            **{f"stance:{word}": counts[word] / total for word in STANCE},
            "_sentences": float(total), "_tokens": float(tokens)}


def development_rows(rows: list[dict], section: str = "") -> list[dict]:
    if section and section not in SECTIONS:
        raise CorpusError("Unknown section")
    # The seal already enforces visual review and confirmed primary authorship.
    # Permission controls raw model-facing excerpts, not private local statistics.
    return [row for row in rows if row["split"] == "development" and
            (not section or row["section"] == section)]


def fingerprint(rows: list[dict]) -> str:
    identifiers = sorted(f"{r['candidate_id']}:{r['source_sha256']}" for r in rows)
    return hashlib.sha256("\n".join(identifiers).encode()).hexdigest()


def aggregate(rows: list[dict], section: str = "") -> dict:
    chosen = development_rows(rows, section)
    groups: dict[str, list[str]] = defaultdict(list)
    for row in chosen:
        if "\x00" not in row["text"] and "\ufffd" not in row["text"]:
            groups[row["family_id"]].append(row["text"])
    measured = {family: _measurement(texts) for family, texts in groups.items()}
    measured = {family: data for family, data in measured.items() if data.get("_sentences", 0) >= 2}
    if len(measured) < 2:
        return {"status": "insufficient_evidence", "section": section or "all",
                "reason": "At least two reviewed development paper families with two sentences each are needed."}
    keys = [key for key in next(iter(measured.values())) if not key.startswith("_")]
    # One paper has one vote, regardless of its length or number of paragraphs.
    target = {key: round(median(data[key] for data in measured.values()), 3) for key in keys}
    spread = {key: round(max(data[key] for data in measured.values()) - min(data[key] for data in measured.values()), 3)
              for key in keys}
    connector = sorted(((key.split(":", 1)[1], value) for key, value in target.items()
                        if key.startswith("connector:") and value > 0), key=lambda item: (-item[1], item[0]))[:3]
    stance = sorted(((key.split(":", 1)[1], value) for key, value in target.items()
                     if key.startswith("stance:") and value > 0), key=lambda item: (-item[1], item[0]))[:3]
    return {"status": "provisional", "section": section or "all", "families": len(measured),
            "passages": sum(len(groups[f]) for f in measured),
            "sentences": int(sum(data["_sentences"] for data in measured.values())),
            "target": {k: v for k, v in target.items() if ":" not in k},
            "between_paper_range": {k: v for k, v in spread.items() if ":" not in k},
            "common_connectors": [word for word, _ in connector],
            "common_stance_verbs": [word for word, _ in stance],
            "profile_digest": fingerprint([r for r in chosen if r["family_id"] in measured]),
            "note": "Local descriptive measurements only. The vocabulary is a fixed list of generic academic words; no source phrase or original sentence is returned."}


def _distance(actual: dict, target: dict) -> dict[str, float]:
    scales = {"sentence_words": 12.0, "paragraph_sentences": 2.0}
    return {key: round(abs(actual[key] - expected) / scales.get(key, 0.35), 3)
            for key, expected in target.items() if key in actual}


def guidance(rows: list[dict], draft: str, section: str) -> dict:
    if not draft.strip() or len(draft) > 30_000:
        raise CorpusError("Provide a nonempty English draft of at most 30,000 characters")
    target = aggregate(rows, section)
    fallback = False
    if target["status"] == "insufficient_evidence" and section:
        target = aggregate(rows)
        fallback = True
    if target["status"] == "insufficient_evidence":
        return {"status": "insufficient_evidence", "reason": target["reason"]}
    actual = _measurement([draft])
    if not actual:
        return {"status": "insufficient_draft", "reason": "The draft needs at least one complete sentence."}
    differences = _distance(actual, target["target"])
    directions = []
    descriptors = {
        "sentence_words": ("shorten sentence structure", "lengthen sentence structure where clarity permits"),
        "paragraph_sentences": ("use fewer sentences per paragraph", "connect related sentences into fuller paragraphs"),
        "hedge_rate": ("avoid adding unnecessary uncertainty", "use calibrated uncertainty only where the evidence supports it"),
        "first_person_rate": ("use less first-person phrasing", "use first-person phrasing only for actions the authors actually performed"),
        "passive_rate": ("prefer direct active phrasing where scientifically accurate", "use passive constructions selectively without obscuring the actor"),
        "semicolon_rate": ("reduce semicolons", "consider semicolons only where they clarify closely linked statements"),
        "parenthesis_rate": ("reduce parenthetical asides", "consider short parenthetical qualifications where useful"),
    }
    for key in sorted(descriptors, key=lambda name: -differences.get(name, 0)):
        if differences.get(key, 0) < 0.22:
            continue
        spread = target["between_paper_range"][key]
        if spread > (8 if key == "sentence_words" else 0.7):
            continue  # Papers disagree; no author-wide target is defensible.
        direction = 0 if actual[key] > target["target"][key] else 1
        directions.append(descriptors[key][direction])
        if len(directions) >= 4:
            break
    return {"status": "rewrite_guidance", "section": section, "section_fallback": fallback,
            "profile_digest": target["profile_digest"], "draft_sha256": hashlib.sha256(draft.encode()).hexdigest(),
            "evidence": {k: target[k] for k in ("families", "passages", "sentences")},
            "target": target["target"], "draft_measurements": {k: round(actual[k], 3) for k in target["target"]},
            "prioritized_edits": directions,
            "wording_preferences": {"connectors": target["common_connectors"],
                                    "stance_verbs": target["common_stance_verbs"]},
            "rewrite_contract": [
                "Rewrite the user's English draft to match the supplied stylistic tendencies, not its topic or findings.",
                "Keep each assertion, comparison, group, direction, number, unit, citation, negation and level of certainty grounded in the original and fact sheet.",
                "Do not add findings, references or claims. Do not quote, retrieve or imitate any source passage verbatim.",
                "When a style preference conflicts with factual precision or clarity, preserve meaning and mark the uncertainty for the author.",
                "After writing, call assess_revision with the exact original and exact proposed text; a tool check never replaces author review.",
            ],
            "limitations": "A model may ignore this plan or alter the text after checking. Measurements do not prove author likeness."}


def assess(rows: list[dict], original: str, revised: str, section: str) -> dict:
    if not original.strip() or not revised.strip() or max(len(original), len(revised)) > 30_000:
        raise CorpusError("Provide both English texts of at most 30,000 characters")
    profile = aggregate(rows, section)
    if profile["status"] == "insufficient_evidence":
        return profile
    base, output = _measurement([original]), _measurement([revised])
    if not base or not output:
        return {"status": "insufficient_draft"}
    target = profile["target"]
    before, after = _distance(base, target), _distance(output, target)
    selected = ("sentence_words", "paragraph_sentences", "hedge_rate", "first_person_rate",
                "passive_rate", "semicolon_rate", "parenthesis_rate")
    # Diagnostic only: no optimizing or claiming success based on this aggregate.
    style = {"before": round(sum(before[k] for k in selected) / len(selected), 3),
             "after": round(sum(after[k] for k in selected) / len(selected), 3)}
    from pentwin.server import audit_draft
    alarms = audit_draft(original, revised)
    negation = re.compile(r"\b(?:not|no|never|neither|without|failed to)\b", re.I)
    uncertainty = re.compile(r"\b(?:may|might|could|suggest(?:s|ed)?|possibly|potentially)\b", re.I)
    alarm_counts = {name: {"original": len(pattern.findall(original)), "revision": len(pattern.findall(revised))}
                    for name, pattern in (("negation", negation), ("uncertainty", uncertainty), ("citations", CITATION))}
    original_citations, revised_citations = set(CITATION.findall(original)), set(CITATION.findall(revised))
    return {"status": "needs_human_review", "profile_digest": profile["profile_digest"],
            "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "revision_sha256": hashlib.sha256(revised.encode()).hexdigest(),
            "style_distance_diagnostic": style, "lexical_alarms": alarms,
            "count_changes": {k: v for k, v in alarm_counts.items() if v["original"] != v["revision"]},
            "citation_token_changes": {"added": sorted(revised_citations - original_citations),
                                       "removed": sorted(original_citations - revised_citations)},
            "limitations": "Style distance is not author likeness. Equal counts do not preserve meaning. Verify claims, citations, terminology and naturalness manually."}
