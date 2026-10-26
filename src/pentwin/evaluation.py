"""Blind paired review of same-content drafts. No model calls or corpus access."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path

from pentwin.cli import CorpusError

RATING_FIELDS = ["case_id", "model", "section", "draft_a", "draft_b", "preferred", "likeness_a", "likeness_b",
                 "naturalness_a", "naturalness_b", "facts_a", "facts_b", "comments"]


def make_blind_pairs(inputs: Path, output: Path, seed: str) -> dict:
    if any((parent / ".git").exists() for parent in (inputs.resolve(), *inputs.resolve().parents)):
        raise CorpusError("Private evaluation inputs must be outside every Git working tree")
    if any((parent / ".git").exists() for parent in (output.resolve(), *output.resolve().parents)):
        raise CorpusError("Private evaluation output must be outside every Git working tree")
    if output.exists() and any(output.iterdir()):
        raise CorpusError("Evaluation output must be empty")
    cases = json.loads(inputs.read_text(encoding="utf-8"))["cases"]
    if not isinstance(cases, list) or not cases:
        raise CorpusError("At least one same-content case is required")
    ids, rows, key, locked = set(), [], {}, {}
    for case in cases:
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip()
                                              for k in ("case_id", "model", "section", "baseline", "guided")):
            raise CorpusError("Each case needs case_id, model, section, baseline, and guided text")
        cid = case["case_id"]
        if cid in ids:
            raise CorpusError("Duplicate case_id")
        ids.add(cid)
        rng = random.Random(int(hashlib.sha256(f"{seed}:{cid}".encode()).hexdigest(), 16))
        guided_at = rng.choice(("A", "B"))
        key[cid] = guided_at
        rows.append({"case_id": cid, "model": case["model"], "section": case["section"],
                     "draft_a": case["guided"] if guided_at == "A" else case["baseline"],
                     "draft_b": case["baseline"] if guided_at == "A" else case["guided"],
                     **{k: "" for k in RATING_FIELDS[5:]}})
        locked[cid] = hashlib.sha256(json.dumps({k: rows[-1][k] for k in RATING_FIELDS[:5]},
                                             sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "rating.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RATING_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (output / "private_key.json").write_text(json.dumps({"seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
                                                         "guided_at": key, "locked": locked}, indent=2) + "\n", encoding="utf-8")
    return {"cases": len(rows), "rating_sheet": str(output / "rating.csv"), "private_key": str(output / "private_key.json")}


def summarize(output: Path) -> dict:
    metadata = json.loads((output / "private_key.json").read_text(encoding="utf-8"))
    key, locked = metadata["guided_at"], metadata["locked"]
    with (output / "rating.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != RATING_FIELDS:
            raise CorpusError("Rating columns changed")
        rows = list(reader)
    if {r["case_id"] for r in rows} != set(key) or len(rows) != len(key):
        raise CorpusError("Rating rows changed")
    tally = {"guided": 0, "baseline": 0, "tie": 0}
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        fingerprint = hashlib.sha256(json.dumps({k: row[k] for k in RATING_FIELDS[:5]},
                                                sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if fingerprint != locked[row["case_id"]]:
            raise CorpusError("Blinded draft or provenance changed")
        if row["preferred"] not in {"A", "B", "tie"}:
            raise CorpusError("Every case needs preferred=A/B/tie")
        for field in ("likeness_a", "likeness_b", "naturalness_a", "naturalness_b", "facts_a", "facts_b"):
            if row[field] not in {"1", "2", "3", "4", "5"}:
                raise CorpusError(f"Every case needs a 1-5 rating for {field}")
        winner = "tie" if row["preferred"] == "tie" else "guided" if row["preferred"] == key[row["case_id"]] else "baseline"
        tally[winner] += 1
        grouped.setdefault(row["model"], {"guided": 0, "baseline": 0, "tie": 0})[winner] += 1
    return {"cases": len(rows), "preference": tally, "by_model": grouped,
            "interpretation": "Descriptive paired preferences only. Human fact checking, independent raters, and more papers are required before claiming author likeness."}
