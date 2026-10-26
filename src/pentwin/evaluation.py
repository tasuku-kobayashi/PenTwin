"""Blind paired author-voice review. No model calls or corpus access."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path

from pentwin.cli import CorpusError

RATING_FIELDS = ["case_id", "author_id", "model", "section", "draft_a", "draft_b",
                 "preferred", "likeness_a", "likeness_b", "distinctiveness_a", "distinctiveness_b",
                 "naturalness_a", "naturalness_b", "comments"]
LOCKED_FIELDS = RATING_FIELDS[:6]
DIMENSIONS = ("likeness", "distinctiveness", "naturalness")


def make_blind_pairs(inputs: Path, output: Path, seed: str) -> dict:
    for path in (inputs, output):
        if any((parent / ".git").exists() for parent in (path.resolve(), *path.resolve().parents)):
            raise CorpusError("Private evaluation files must be outside every Git working tree")
    if output.exists() and any(output.iterdir()):
        raise CorpusError("Evaluation output must be empty")
    cases = json.loads(inputs.read_text(encoding="utf-8"))["cases"]
    if not isinstance(cases, list) or not cases:
        raise CorpusError("At least one same-content case is required")
    ids, rows, key, locked = set(), [], {}, {}
    for case in cases:
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip()
                                              for k in ("case_id", "author_id", "model", "section", "baseline", "guided")):
            raise CorpusError("Each case needs case_id, anonymous author_id, model, section, baseline and guided text")
        cid = case["case_id"]
        if cid in ids:
            raise CorpusError("Duplicate case_id")
        ids.add(cid)
        rng = random.Random(int(hashlib.sha256(f"{seed}:{cid}".encode()).hexdigest(), 16))
        guided_at = rng.choice(("A", "B"))
        key[cid] = guided_at
        rows.append({"case_id": cid, "author_id": case["author_id"], "model": case["model"],
                     "section": case["section"],
                     "draft_a": case["guided"] if guided_at == "A" else case["baseline"],
                     "draft_b": case["baseline"] if guided_at == "A" else case["guided"],
                     **{k: "" for k in RATING_FIELDS[len(LOCKED_FIELDS):]}})
        locked[cid] = hashlib.sha256(json.dumps({k: rows[-1][k] for k in LOCKED_FIELDS},
                                             sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "rating.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RATING_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (output / "private_key.json").write_text(json.dumps({"seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
                                                         "guided_at": key, "locked": locked}, indent=2) + "\n", encoding="utf-8")
    return {"cases": len(rows), "rating_sheet": str(output / "rating.csv"), "private_key": str(output / "private_key.json")}


def _blank_tally() -> dict[str, int]:
    return {"guided": 0, "baseline": 0, "tie": 0}


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
    tally = _blank_tally()
    by_author: dict[str, dict[str, int]] = {}
    by_model: dict[str, dict[str, int]] = {}
    paired = {name: _blank_tally() for name in DIMENSIONS}
    differences = {name: [] for name in DIMENSIONS}
    for row in rows:
        fingerprint = hashlib.sha256(json.dumps({k: row[k] for k in LOCKED_FIELDS},
                                                sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if fingerprint != locked[row["case_id"]]:
            raise CorpusError("Blinded draft or provenance changed")
        if row["preferred"] not in {"A", "B", "tie"}:
            raise CorpusError("Every case needs preferred=A/B/tie")
        for name in DIMENSIONS:
            for side in ("a", "b"):
                if row[f"{name}_{side}"] not in {"1", "2", "3", "4", "5"}:
                    raise CorpusError(f"Every case needs a 1-5 rating for {name}_{side}")
        winner = "tie" if row["preferred"] == "tie" else "guided" if row["preferred"] == key[row["case_id"]] else "baseline"
        tally[winner] += 1
        by_author.setdefault(row["author_id"], _blank_tally())[winner] += 1
        by_model.setdefault(row["model"], _blank_tally())[winner] += 1
        for name in DIMENSIONS:
            guided = int(row[f"{name}_{key[row['case_id']].lower()}"])
            baseline = int(row[f"{name}_{'b' if key[row['case_id']] == 'A' else 'a'}"])
            difference = guided - baseline
            differences[name].append(difference)
            paired[name]["guided" if difference > 0 else "baseline" if difference < 0 else "tie"] += 1
    return {"cases": len(rows), "preference": tally, "by_author": by_author, "by_model": by_model,
            "paired_dimensions": paired,
            "mean_guided_minus_baseline": {name: round(sum(values) / len(values), 3) for name, values in differences.items()},
            "interpretation": "Descriptive blinded ordinal ratings of author voice, distinctiveness and naturalness. These are not calibrated probabilities. Aggregate style distance cannot replace independent human judgments across authors and sections. Scientific content is outside PenTwin."}
