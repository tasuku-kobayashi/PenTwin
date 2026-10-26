"""Section-scoped, role-conditioned style candidates from reviewed local rows.

The output is a closed vocabulary of generic words and approved move labels.
It never returns source passages or learns arbitrary n-grams from papers.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import median

from pentwin.style_engine import FIRST_PERSON, HEDGES, PASSIVE, _sentences, development_rows, fingerprint

CONNECTIVE_PATTERNS = {
    word: re.compile(r"(?<!\w)" + re.escape(word) + r"(?!\w)", re.I)
    for word in ("however", "therefore", "thus", "moreover", "furthermore",
                 "notably", "in contrast", "by contrast", "in addition",
                 "taken together", "whereas")
}
STANCE_PATTERNS = {
    "suggest": r"suggest(?:s|ed|ing)?", "indicate": r"indicat(?:e|es|ed|ing)",
    "demonstrate": r"demonstrat(?:e|es|ed|ing)", "show": r"show(?:s|ed|n|ing)?",
    "reveal": r"reveal(?:s|ed|ing)?", "support": r"support(?:s|ed|ing)?",
    "observe": r"observ(?:e|es|ed|ing)", "report": r"report(?:s|ed|ing)?",
    "find": r"(?:find|finds|found)", "propose": r"propos(?:e|es|ed|ing)",
}
STANCE_PATTERNS = {name: re.compile(r"(?<!\w)(?:" + regex + r")(?!\w)", re.I)
                   for name, regex in STANCE_PATTERNS.items()}
STANCE_CUES = {"hedge_rate": HEDGES, "first_person_rate": FIRST_PERSON, "passive_rate": PASSIVE}


def build_style_card(rows: list[dict], section: str, move: str = "") -> dict:
    """Abstain for a role unless at least two development families support it."""
    # Validate scope through the same public gate as the numeric profile.
    development_rows(rows, section, move)  # Validate the requested move.
    selected = development_rows(rows, section)
    if not section:
        return {"status": "insufficient_role_evidence", "section": "all", "move": move or "all",
                "roles": {}, "flow": [], "development_families": 0,
                "profile_digest": fingerprint(selected),
                "reason": "A reviewed section is required for role-conditioned style."}
    families: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    sequences: dict[str, list[str]] = defaultdict(list)
    for row in selected:
        body = row["text"]
        if "\x00" in body or "\ufffd" in body:
            continue
        family, role = row["family_id"], row.get("move", "")
        if role in {"", "other"}:
            continue
        sentences = _sentences(body)
        if sentences:
            families[family][role].extend(sentences)
            if not sequences[family] or sequences[family][-1] != role:
                sequences[family].append(role)
    roles = {}
    eligible_roles = {role for per_family in families.values() for role in per_family
                      if sum(len(other.get(role, [])) >= 5 for other in families.values()) >= 2}
    for role in sorted(eligible_roles):
        eligible = {family: sentences for family, per_family in families.items()
                    if len(sentences := per_family.get(role, [])) >= 5}
        if len(eligible) < 2:
            continue
        wording = {}
        for category, patterns in (("connectors", CONNECTIVE_PATTERNS), ("stance_verbs", STANCE_PATTERNS)):
            candidates = []
            for term, pattern in patterns.items():
                counts = {family: sum(len(pattern.findall(sentence)) for sentence in sentences)
                          for family, sentences in eligible.items()}
                support = sum(count >= 2 for count in counts.values())
                if support < 2:
                    continue
                rates = [counts[family] / len(sentences) for family, sentences in eligible.items()]
                if max(rates) - min(rates) > 0.25:
                    continue
                candidates.append((term, round(median(rates), 3), support))
            wording[category] = [
                {"term": term, "per_sentence": rate, "families": support}
                for term, rate, support in sorted(candidates, key=lambda item: (-item[1], item[0]))[:2]
            ]
        stance = {}
        for label, pattern in STANCE_CUES.items():
            rates = [sum(bool(pattern.search(s)) for s in sentences) / len(sentences)
                     for sentences in eligible.values()]
            if max(rates) - min(rates) <= 0.15:
                stance[label] = round(median(rates), 3)
        roles[role] = {"families": len(eligible), "wording": wording,
                       "stance": stance, "sentences": sum(map(len, eligible.values()))}
    # Keep stance only when its use differs between supported roles. An overall
    # percentage belongs to the numeric profile, not a conditional style card.
    if len(roles) >= 2:
        for label in STANCE_CUES:
            values = [details["stance"][label] for details in roles.values() if label in details["stance"]]
            if len(values) < 2 or max(values) - min(values) < 0.1:
                for details in roles.values():
                    details["stance"].pop(label, None)
    else:
        for details in roles.values():
            details["stance"].clear()
    roles = {role: details for role, details in roles.items()
             if any(details["wording"].values()) or details["stance"]}
    transitions = Counter()
    if not move:
        for sequence in sequences.values():
            transitions.update(set(zip(sequence, sequence[1:])))
    flow = [{"from": start, "to": end, "families": support}
            for (start, end), support in sorted(transitions.items(), key=lambda item: (-item[1], item[0]))
            if support >= 2][:3]
    if move:
        roles = {move: roles[move]} if move in roles else {}
    status = "provisional" if roles or flow else "insufficient_role_evidence"
    return {"status": status, "section": section or "all", "move": move or "all",
            "roles": roles, "flow": flow, "development_families": len(families),
            "profile_digest": fingerprint(selected),
            "limitations": "Candidates require at least two reviewed development paper families. A repeated generic word is not necessarily distinctive from other writers. Move order follows reviewed corpus row order; it is not inferred from scientific meaning. No source passage is returned."}


def card_instructions(card: dict, move: str = "") -> list[str]:
    if card["status"] != "provisional":
        return []
    instructions = []
    if card["flow"]:
        transitions = ", ".join(f"{edge['from']} → {edge['to']}" for edge in card["flow"])
        instructions.append(f"When the draft covers these roles, favor the observed explanation order: {transitions}.")
    for role, details in card["roles"].items():
        if move and role != move:
            continue
        for category, label in (("connectors", "transitions"), ("stance_verbs", "reporting verbs")):
            terms = [item["term"] for item in details["wording"][category]]
            if terms:
                instructions.append(f"In {role} passages, consider the writer's recurring {label}: {', '.join(terms)}.")
        rates = details["stance"]
        if rates:
            pieces = ", ".join(f"{name.replace('_rate', '').replace('_', ' ')} {rate:.0%}"
                               for name, rate in rates.items())
            instructions.append(f"In {role} passages, use these as soft stance tendencies: {pieces}.")
    return instructions[:8]


def contrast_style_cards(target: dict, rival: dict) -> dict:
    """Keep supported features that differ from a same-section comparison writer."""
    if target["section"] != rival["section"] or target["move"] != rival["move"]:
        raise ValueError("Style cards must have the same section and move scope")
    unique_flow = [edge for edge in target["flow"] if
                   (edge["from"], edge["to"]) not in
                   {(other["from"], other["to"]) for other in rival["flow"]}]
    distinctions = {}
    for role, details in target["roles"].items():
        other = rival["roles"].get(role)
        if other is None:
            continue  # A different role inventory cannot identify a lexical habit.
        words = {}
        for category in ("connectors", "stance_verbs"):
            rival_terms = {entry["term"] for entry in other["wording"][category]}
            words[category] = [entry for entry in details["wording"][category]
                               if entry["term"] not in rival_terms]
        stance = {label: {"target": rate, "rival": other["stance"][label]}
                  for label, rate in details["stance"].items()
                  if label in other["stance"] and abs(rate - other["stance"][label]) >= 0.12}
        if any(words.values()) or stance:
            distinctions[role] = {"wording": words, "stance": stance}
    return {"status": "candidate_distinctions" if unique_flow or distinctions else "insufficient_distinctive_evidence",
            "section": target["section"], "move": target["move"], "flow": unique_flow,
            "roles": distinctions,
            "limitations": "Comparison is conditional on two reviewed corpora with matched sections and writing roles. Differences are candidates, not proof of personal authorship; test on untouched writers and content."}
