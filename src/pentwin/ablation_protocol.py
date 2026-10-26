"""Factorial card conditions with a separately measured sentence-ending axis."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from statistics import median

from pentwin.cli import CorpusError
from pentwin.exploratory_card import build_exploratory_card, exploratory_instructions
from pentwin.style_engine import HEDGES, WORD, _sentences, development_rows


AXES = ("lexical", "ending", "order")
CONDITIONS = ("none", "lexical", "ending", "order", "lexical_ending",
              "lexical_order", "ending_order", "all")
DIRECT = re.compile(r"\b(?:show|shows|showed|demonstrate|demonstrates|demonstrated|establish|establishes)\b", re.I)


def ending_instructions(rows: list[dict], section: str, move: str = "") -> list[str]:
    groups = defaultdict(list)
    for row in development_rows(rows, section, move):
        groups[row["family_id"]].extend(_sentences(row["text"]))
    if len(groups) < 2 or any(len(s) < 5 for s in groups.values()):
        return []
    rates = []
    for sentences in groups.values():
        tails = [" ".join(WORD.findall(s)[-10:]) for s in sentences]
        rates.append((sum(bool(HEDGES.search(t)) for t in tails) / len(tails),
                      sum(bool(DIRECT.search(t)) for t in tails) / len(tails)))
    hedged, direct = (median(row[i] for row in rates) for i in (0, 1))
    if max(hedged, direct) == 0:
        return []
    return [f"In the last ten words of a sentence, consider qualified claims in about {hedged:.0%} and direct claims in about {direct:.0%} of sentences, only when warranted; these are weak style observations from {len(groups)} papers, not wording to copy."]


def snippet_from_target(target_text: str) -> str:
    """First min(50 words, 20% of the human target), as in Wang et al."""
    words = target_text.split()
    if len(words) < 50 or len(target_text) > 30_000:
        raise CorpusError("The separately supplied human target needs at least 50 words and at most 30,000 characters")
    return " ".join(words[:min(50, max(1, len(words) // 5))])


def conditions(rows: list[dict], section: str, move: str = "", target_text: str = "",
               confirmed_author_written: bool = False, lexical_only: bool = False) -> dict:
    card = build_exploratory_card(rows, section, move)
    axes = {"lexical": exploratory_instructions(card, ("wording",)),
            "ending": ending_instructions(rows, section, move),
            "order": exploratory_instructions(card, ("cue_order",))}
    base = "Write an English academic passage for the section from the same content brief and word count. Return prose only."
    plans = {}
    selected_conditions = ("none", "lexical") if lexical_only else CONDITIONS
    for condition in selected_conditions:
        selected = () if condition == "none" else AXES if condition == "all" else tuple(condition.split("_"))
        missing = [axis for axis in selected if not axes[axis]]
        plans[condition] = {"available": not missing, "missing_axes": missing,
                            "instructions": [base] + [item for axis in selected for item in axes[axis]]}
    if target_text:
        if not confirmed_author_written:
            raise CorpusError("Confirm that the separately provided target opening was authored by the target writer")
        anchor = snippet_from_target(target_text)
        # Prevent using a paper in the sealed calibration corpus as a target.
        if any(anchor in " ".join(row["text"].split()) for row in rows):
            raise CorpusError("Snippet target must be separate from development and calibration papers")
        snippet_condition = "lexical_snippet" if lexical_only else "all_snippet"
        snippet_axes = ("lexical",) if lexical_only else AXES
        base_condition = "lexical" if lexical_only else "all"
        plans[snippet_condition] = {"available": plans[base_condition]["available"],
                                "missing_axes": plans[base_condition]["missing_axes"],
                                "instructions": [base, "Continue after this exact human-authored opening; output only the continuation. Do not repeat or rewrite the opening.",
                                                 anchor] + [item for axis in snippet_axes for item in axes[axis]],
                                "anchor_words": len(anchor.split()),
                                "anchor_sha256": hashlib.sha256(anchor.encode()).hexdigest()}
    return {"status": "experimental_plan", "section": section, "move": move,
            "condition_set": "lexical_only" if lexical_only else "full_factorial",
            "profile_digest": card.get("profile_digest"), "axis_available": {k: bool(v) for k, v in axes.items()},
            "shared_control": "Same brief, target length, host model and settings for every condition. Separate target authored text is needed only for +Snippet. Score only the continuation, excluding the anchor.",
            "conditions": plans,
            "limits": "+Snippet in Wang et al. improved AI-detector human-likeness most consistently, not every authorship or style metric. A target-paper prefix is not interchangeable with a different paper's opening. These conditions have not been validated on independently generated drafts."}
