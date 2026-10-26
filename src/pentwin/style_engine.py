"""Local, non-generative author-style measurements and rewrite guidance.

Only aggregate, closed-vocabulary features leave this module. Source passages,
identifiers, and learned word sequences are never returned to an MCP client.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from statistics import median

from pentwin.cli import CorpusError, MOVES


WORD = re.compile(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
HEDGES = re.compile(r"\b(?:may|might|could|suggest(?:s|ed)?|appear(?:s|ed)?|potentially|possibly)\b", re.I)
FIRST_PERSON = re.compile(r"\b(?:we|our|us)\b", re.I)
PASSIVE = re.compile(r"\b(?:was|were|is|are|been|be)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.I)
CITATION = re.compile(r"\[(?:\d+[ ,;\-]*)+\]|\((?:[A-Z][A-Za-z'-]+\s+et\s+al\.,?\s*)?\d{4}[a-z]?\)")
CONNECTORS = ("however", "therefore", "thus", "moreover", "furthermore", "notably",
              "in contrast", "by contrast", "in addition", "taken together", "whereas")
STANCE = ("suggest", "indicate", "demonstrate", "show", "reveal", "support", "observe", "report")
FUNCTION_WORDS = ("although", "because", "but", "for", "if", "of", "or", "that", "the", "therefore", "this", "to", "which", "while", "with", "would")
RHETORICAL = {
    "contrast": re.compile(r"\b(?:although|however|whereas|but|in contrast|by contrast)\b", re.I),
    "reason": re.compile(r"\b(?:because|therefore|thus|since|consequently)\b", re.I),
    "limitation": re.compile(r"\b(?:limitation|limited|uncertain|caution|cannot|could not)\b", re.I),
}
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
    words = [word.lower() for sentence in sentences for word in WORD.findall(sentence)]
    word_counts = Counter(words)
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
            "question_rate": sum("?" in s for s in sentences) / total,
            **{f"rhetoric:{name}": sum(bool(pattern.search(s)) for s in sentences) / total
               for name, pattern in RHETORICAL.items()},
            **{f"function:{word}": word_counts[word] / max(1, tokens) for word in FUNCTION_WORDS},
            **{f"connector:{word}": counts[word] / total for word in CONNECTORS},
            **{f"stance:{word}": counts[word] / total for word in STANCE},
            "_sentences": float(total), "_tokens": float(tokens)}


def development_rows(rows: list[dict], section: str = "", move: str = "") -> list[dict]:
    if section and section not in SECTIONS:
        raise CorpusError("Unknown section")
    if move and move not in MOVES:
        raise CorpusError("Unknown rhetorical move")
    # The seal already enforces visual review and confirmed primary authorship.
    # Permission controls raw model-facing excerpts, not private local statistics.
    return [row for row in rows if row["split"] == "development" and
            (not section or row["section"] == section) and (not move or row.get("move") == move)]


def fingerprint(rows: list[dict]) -> str:
    identifiers = sorted(f"{r['candidate_id']}:{r['source_sha256']}" for r in rows)
    return hashlib.sha256("\n".join(identifiers).encode()).hexdigest()


def aggregate(rows: list[dict], section: str = "", move: str = "") -> dict:
    chosen = development_rows(rows, section, move)
    groups: dict[str, list[str]] = defaultdict(list)
    for row in chosen:
        if "\x00" not in row["text"] and "\ufffd" not in row["text"]:
            groups[row["family_id"]].append(row["text"])
    measured = {family: _measurement(texts) for family, texts in groups.items()}
    measured = {family: data for family, data in measured.items() if data.get("_sentences", 0) >= 2}
    if len(measured) < 2:
        return {"status": "insufficient_evidence", "section": section or "all", "move": move or "all",
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
    return {"status": "provisional", "section": section or "all", "move": move or "all", "families": len(measured),
            "passages": sum(len(groups[f]) for f in measured),
            "sentences": int(sum(data["_sentences"] for data in measured.values())),
            "target": {k: v for k, v in target.items() if not k.startswith(("connector:", "stance:"))},
            "between_paper_range": {k: v for k, v in spread.items() if not k.startswith(("connector:", "stance:"))},
            "common_connectors": [word for word, _ in connector],
            "common_stance_verbs": [word for word, _ in stance],
            "profile_digest": fingerprint([r for r in chosen if r["family_id"] in measured]),
            "note": "Local descriptive measurements only. The vocabulary is a fixed list of generic academic words; no source phrase or original sentence is returned."}


def _distance(actual: dict, target: dict) -> dict[str, float]:
    scales = {"sentence_words": 12.0, "paragraph_sentences": 2.0}
    def scale(key: str) -> float:
        if key.startswith("function:"):
            return 0.025
        return scales.get(key, 0.35)
    return {key: round(abs(actual[key] - expected) / scale(key), 3)
            for key, expected in target.items() if key in actual}


def guidance(rows: list[dict], draft: str, section: str, move: str = "") -> dict:
    if not draft.strip() or len(draft) > 30_000:
        raise CorpusError("Provide a nonempty English draft of at most 30,000 characters")
    target = aggregate(rows, section, move)
    if target["status"] == "insufficient_evidence":
        return {"status": "insufficient_evidence", "section": target["section"], "move": target["move"],
                "reason": target["reason"] + " Requested scope was not replaced with a broader profile."}
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
        "question_rate": ("reduce rhetorical questions", "consider a question only where it serves the argument"),
        "rhetoric:contrast": ("make contrasts more selective", "make evidence-based contrasts explicit"),
        "rhetoric:reason": ("use causal transitions more selectively", "make the reasoning between claims explicit where supported"),
        "rhetoric:limitation": ("avoid redundant limitation language", "state relevant limitations explicitly without inventing uncertainty"),
    }
    for key in sorted(descriptors, key=lambda name: -differences.get(name, 0)):
        if differences.get(key, 0) < 0.22:
            continue
        spread = target["between_paper_range"].get(key, 0)
        if spread > (8 if key == "sentence_words" else 0.7):
            continue  # Papers disagree; no author-wide target is defensible.
        direction = 0 if actual[key] > target["target"][key] else 1
        directions.append(descriptors[key][direction])
        if len(directions) >= 4:
            break
    return {"status": "rewrite_guidance", "section": section, "move": move,
            "profile_digest": target["profile_digest"], "draft_sha256": hashlib.sha256(draft.encode()).hexdigest(),
            "evidence": {k: target[k] for k in ("families", "passages", "sentences")},
            "target": {k: v for k, v in target["target"].items() if not k.startswith("function:")},
            "draft_measurements": {k: round(actual[k], 3) for k in target["target"] if not k.startswith("function:")},
            "diagnostic_features_excluded_from_rewrite": ["function_word_rates"],
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


def assess(rows: list[dict], original: str, revised: str, section: str, move: str = "") -> dict:
    if not original.strip() or not revised.strip() or max(len(original), len(revised)) > 30_000:
        raise CorpusError("Provide both English texts of at most 30,000 characters")
    profile = aggregate(rows, section, move)
    if profile["status"] == "insufficient_evidence":
        return profile
    base, output = _measurement([original]), _measurement([revised])
    if not base or not output:
        return {"status": "insufficient_draft"}
    target = profile["target"]
    before, after = _distance(base, target), _distance(output, target)
    selected = ("sentence_words", "paragraph_sentences", "hedge_rate", "first_person_rate",
                "passive_rate", "semicolon_rate", "parenthesis_rate", "question_rate",
                "rhetoric:contrast", "rhetoric:reason", "rhetoric:limitation")
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
