"""Weak, graded section-level style clues for exploratory generation.

Every value is descriptive, and model-facing vocabulary is fixed in code.
This can be used when strict move-conditioned cards abstain.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from pentwin.style_card import CONNECTIVE_PATTERNS, STANCE_CUES, STANCE_PATTERNS
from pentwin.style_engine import RHETORICAL, _sentences, development_rows, fingerprint


def _cue(sentence: str) -> str:
    if RHETORICAL["limitation"].search(sentence):
        return "limitation_cue"
    if RHETORICAL["contrast"].search(sentence):
        return "contrast_cue"
    if any(STANCE_PATTERNS[word].search(sentence) for word in ("suggest", "indicate", "propose")):
        return "interpretation_cue"
    if any(STANCE_PATTERNS[word].search(sentence) for word in ("observe", "report", "find")):
        return "observation_cue"
    return ""


def build_exploratory_card(rows: list[dict], section: str, move: str = "") -> dict:
    selected = development_rows(rows, section, move)
    if not section:
        return {"status": "insufficient_evidence", "reason": "A reviewed section is required.",
                "section": "all", "move": move or "all"}
    groups: dict[str, list[str]] = defaultdict(list)
    for row in selected:
        if "\x00" not in row["text"] and "\ufffd" not in row["text"]:
            groups[row["family_id"]].extend(_sentences(row["text"]))
    groups = {family: sentences for family, sentences in groups.items() if len(sentences) >= 5}
    if len(groups) < 2:
        return {"status": "insufficient_evidence", "reason": "Need five measurable sentences from each of at least two development paper families in this section.",
                "section": section, "move": move or "all"}
    lexical = {}
    for category, patterns in (("connectors", CONNECTIVE_PATTERNS), ("stance_verbs", STANCE_PATTERNS)):
        candidates = []
        for term, pattern in patterns.items():
            counts = {family: sum(bool(pattern.search(sentence)) for sentence in sentences)
                      for family, sentences in groups.items()}
            total = sum(counts.values())
            if total == 0:
                continue
            rates = [counts[family] / len(sentences) for family, sentences in groups.items()]
            support = sum(count > 0 for count in counts.values())
            candidates.append({"term": term, "support": support, "families": len(groups),
                               "median_rate": round(median(rates), 3),
                               "range": round(max(rates) - min(rates), 3),
                               "confidence": "moderate" if support >= 2 and max(rates) - min(rates) <= 0.25 else "low"})
        lexical[category] = sorted(candidates, key=lambda c: (-c["support"], -c["median_rate"], c["term"]))[:6]
    stance = {}
    for name, pattern in STANCE_CUES.items():
        rates = [sum(bool(pattern.search(s)) for s in sentences) / len(sentences)
                 for sentences in groups.values()]
        stance[name] = {"median_rate": round(median(rates), 3),
                        "range": round(max(rates) - min(rates), 3),
                        "families": len(groups)}
    cue_sequences = {}
    for family, sentences in groups.items():
        cue_sequences[family] = [cue for sentence in sentences if (cue := _cue(sentence))]
    support = Counter()
    for sequence in cue_sequences.values():
        support.update(set(zip(sequence, sequence[1:])))
    cue_order = [{"from": before, "to": after, "families": count,
                  "confidence": "moderate" if count >= 2 else "low"}
                 for (before, after), count in sorted(support.items(), key=lambda item: (-item[1], item[0]))][:3]
    return {"status": "exploratory", "section": section, "move": move or "all",
            "families": len(groups), "profile_digest": fingerprint(selected),
            "wording": lexical, "stance": stance, "cue_order": cue_order,
            "limitations": "Weak clues can be genre, topic, period or extraction artifacts. A cue order is a sequence of surface markers, not a verified explanation plan. One-paper lexical support is low confidence. No original source word sequence leaves the local process."}


def exploratory_instructions(card: dict, dimensions: tuple[str, ...] = ("wording", "cue_order", "stance")) -> list[str]:
    if card["status"] != "exploratory":
        return []
    instructions = []
    if "cue_order" in dimensions:
        for edge in card["cue_order"][:2]:
            instructions.append(f"Consider a {edge['from']} before a {edge['to']} when both fit; support {edge['families']}/{card['families']} papers ({edge['confidence']} confidence).")
    if "wording" in dimensions:
        for category, label in (("connectors", "transition"), ("stance_verbs", "reporting verb")):
            candidates = card["wording"][category]
            selected = candidates[:1] + [item for item in candidates[1:] if item["confidence"] == "low"][:1]
            for item in selected:
                instructions.append(f"Consider {item['term']} as a {label} where it fits; support {item['support']}/{item['families']} papers ({item['confidence']} confidence).")
    if "stance" in dimensions:
        for name in ("first_person_rate", "hedge_rate", "passive_rate"):
            item = card["stance"][name]
            instructions.append(f"Treat {name.replace('_rate', '').replace('_', ' ')} as a soft tendency around {item['median_rate']:.0%} of sentences; between-paper range {item['range']:.0%}.")
    return instructions
