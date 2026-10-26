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
    # A word used by only one paper is not evidence of a writer-wide preference.
    supported = {key for key in keys if sum(data[key] > 0 for data in measured.values()) >= 2}
    connector = sorted(((key.split(":", 1)[1], value) for key, value in target.items()
                        if key.startswith("connector:") and key in supported), key=lambda item: (-item[1], item[0]))[:3]
    stance = sorted(((key.split(":", 1)[1], value) for key, value in target.items()
                     if key.startswith("stance:") and key in supported), key=lambda item: (-item[1], item[0]))[:3]
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
    stable = {}
    for key, limit in (("sentence_words", 8), ("paragraph_sentences", 0.7),
                       ("hedge_rate", 0.15), ("first_person_rate", 0.15),
                       ("passive_rate", 0.15), ("rhetoric:contrast", 0.15),
                       ("rhetoric:reason", 0.15), ("rhetoric:limitation", 0.15)):
        if target["between_paper_range"].get(key, float("inf")) <= limit:
            stable[key] = target["target"][key]
    descriptors = {
        "sentence_words": ("shorten sentence structure", "lengthen sentence structure where clarity permits"),
        "paragraph_sentences": ("use fewer sentences per paragraph", "connect related sentences into fuller paragraphs"),
        "hedge_rate": ("use fewer hedging expressions", "use more hedging expressions in the author's typical phrasing"),
        "first_person_rate": ("use less first-person phrasing", "use first-person phrasing more often"),
        "passive_rate": ("prefer direct active phrasing", "use passive constructions more often"),
        "semicolon_rate": ("reduce semicolons", "consider semicolons only where they clarify closely linked statements"),
        "parenthesis_rate": ("reduce parenthetical asides", "consider short parenthetical qualifications where useful"),
        "question_rate": ("reduce rhetorical questions", "consider a question only where it serves the argument"),
        "rhetoric:contrast": ("make contrast markers more selective", "make contrasts more explicit"),
        "rhetoric:reason": ("use reasoning transitions more selectively", "make transitions between reasons more explicit"),
        "rhetoric:limitation": ("use limitation markers more selectively", "use limitation markers more often"),
    }
    for key in sorted(descriptors, key=lambda name: -differences.get(name, 0)):
        if differences.get(key, 0) < 0.22:
            continue
        if key not in stable and key in ("sentence_words", "paragraph_sentences", "hedge_rate",
                                          "first_person_rate", "passive_rate", "rhetoric:contrast",
                                          "rhetoric:reason", "rhetoric:limitation"):
            continue  # Papers disagree; no author-wide target is defensible.
        direction = 0 if actual[key] > target["target"][key] else 1
        label = descriptors[key][direction]
        if key in stable:
            value = stable[key]
            if key in ("sentence_words", "paragraph_sentences"):
                unit = "words per sentence" if key == "sentence_words" else "sentences per paragraph"
                label += f" (author median about {value:g} {unit}; draft {actual[key]:.1f})"
            else:
                label += f" (author rate about {value * 100:.0f}% of sentences; draft {actual[key] * 100:.0f}%)"
        directions.append(label)
        if len(directions) >= 4:
            break
    return {"status": "rewrite_guidance", "section": section, "move": move,
            "profile_digest": target["profile_digest"], "draft_sha256": hashlib.sha256(draft.encode()).hexdigest(),
            "evidence": {k: target[k] for k in ("families", "passages", "sentences")},
            "target": {k: v for k, v in target["target"].items() if not k.startswith("function:")},
            "draft_measurements": {k: round(actual[k], 3) for k in target["target"] if not k.startswith("function:")},
            "diagnostic_features_excluded_from_rewrite": ["function_word_rates"],
            "prioritized_edits": directions,
            "stable_style_signature": stable,
            "wording_preferences": {"connectors": target["common_connectors"],
                                    "stance_verbs": target["common_stance_verbs"]},
            "rewrite_contract": [
                "Rewrite the user's English draft toward the supplied author-style tendencies, focusing on rhythm, wording, stance and argument flow.",
                "Use the numeric tendencies in prioritized_edits as soft targets, never as a sentence-by-sentence quota; skip an instruction if it does not fit this passage.",
                "Avoid generic academic polish that erases distinctive habits. Do not quote or imitate any source passage verbatim.",
                "Treat style guidance as suggestions; this tool does not evaluate scientific claims or preserve their meaning.",
                "After writing, call assess_revision with the exact original and proposed text to inspect style movement; do not call its score author likeness.",
            ],
            "scope": "Authorial style only. Scientific claims, citations and meaning need an independent verifier outside PenTwin.",
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
    short_keys = tuple(key for key in selected if key != "paragraph_sentences")
    short_style = {"before": round(sum(before[k] for k in short_keys) / len(short_keys), 3),
                   "after": round(sum(after[k] for k in short_keys) / len(short_keys), 3)}
    return {"status": "style_diagnostic_only", "profile_digest": profile["profile_digest"],
            "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "revision_sha256": hashlib.sha256(revised.encode()).hexdigest(),
            "style_distance_diagnostic": style,
            "short_passage_style_distance_diagnostic": short_style,
            "scope": "Measures the selected style features only; scientific content is outside PenTwin.",
            "limitations": "Whole-paper paragraph length can dominate a short draft. The short-passage diagnostic excludes that feature. Both distances reuse guidance features and neither proves that a reader recognizes the author."}
