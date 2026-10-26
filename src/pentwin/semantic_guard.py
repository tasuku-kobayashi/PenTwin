"""Optional local SBERT guard on candidate continuations; no network fallback."""

from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path

from pentwin.cli import CorpusError


MAX_DROP = 0.05
MIN_BASELINE = 0.70  # Engineering floor, not a result transferred from Wang et al.


def load_local_encoder(model_dir: Path):
    if not model_dir.is_dir():
        raise CorpusError("An existing local SBERT model directory is required")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise CorpusError("Install the optional semantic extra and provide a local SBERT model") from error
    try:
        return SentenceTransformer(str(model_dir.resolve()), local_files_only=True, trust_remote_code=False)
    except (OSError, ValueError, RuntimeError) as error:
        raise CorpusError("Local SBERT model could not be loaded; semantic scoring is unavailable") from error


def _cosine(a, b) -> float:
    aa, bb = list(a), list(b)
    if len(aa) != len(bb) or not aa or any(not math.isfinite(float(x)) for x in aa + bb):
        raise CorpusError("Invalid SBERT embeddings")
    denominator = math.sqrt(sum(float(x) ** 2 for x in aa) * sum(float(x) ** 2 for x in bb))
    if denominator <= 0:
        raise CorpusError("Zero-length SBERT embedding")
    return sum(float(x) * float(y) for x, y in zip(aa, bb)) / denominator


def semantic_guard(reference: str, baseline: str, candidates: dict[str, str], encoder) -> dict:
    if not reference.strip() or not baseline.strip() or not candidates:
        raise CorpusError("Provide reference content, generic baseline and candidate continuations")
    if any(not isinstance(v, str) or not v.strip() for v in candidates.values()):
        raise CorpusError("Candidates must be nonempty passages")
    names = sorted(candidates)
    values = [reference, baseline] + [candidates[name] for name in names]
    vectors = encoder.encode(values, convert_to_numpy=True)
    if len(vectors) != len(values):
        raise CorpusError("SBERT returned an unexpected number of embeddings")
    baseline_score = _cosine(vectors[0], vectors[1])
    scores = {name: _cosine(vectors[0], vectors[index]) for index, name in enumerate(names, 2)}
    return _decision(baseline_score, scores, "local_sbert")


def _decision(baseline_score: float, scores: dict[str, float], provenance: str) -> dict:
    if any(not math.isfinite(score) or score < -1 or score > 1 for score in [baseline_score, *scores.values()]):
        raise CorpusError("Semantic cosine scores must be finite and in [-1, 1]")
    threshold = max(MIN_BASELINE, baseline_score - MAX_DROP)
    assessed = {name: {"similarity": round(score, 4), "pass": score >= threshold and baseline_score >= MIN_BASELINE}
                for name, score in scores.items()}
    return {"baseline_similarity": round(baseline_score, 4),
            "baseline_adequate": baseline_score >= MIN_BASELINE,
            "threshold": round(threshold, 4), "max_drop": MAX_DROP,
            "candidates": assessed,
            "provenance": provenance,
            "status": "scored" if baseline_score >= MIN_BASELINE else "baseline_inadequate",
            "limits": "Cosine similarity to the same content reference is a semantic screen, not a scientific factuality or logical validity certificate. A 0.05 relative drop and 0.70 baseline floor are provisional engineering thresholds, not calibrated life-science cutoffs."}


def load_semantic_scores(path: Path) -> dict:
    if any((parent / ".git").exists() for parent in (path.resolve(), *path.resolve().parents)):
        raise CorpusError("Private semantic scores must remain outside Git working trees")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("metric") != "cosine" or not isinstance(payload.get("model"), str) or not payload["model"].strip() or payload["model"].startswith("REPLACE_"):
        raise CorpusError("Score file needs model and metric=cosine")
    records = payload.get("cases")
    if not isinstance(records, list) or not records:
        raise CorpusError("Score file needs a nonempty cases list")
    indexed = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("case_id"), str) or record["case_id"] in indexed:
            raise CorpusError("Semantic case IDs must be unique strings")
        indexed[record["case_id"]] = record
    return {"model": payload["model"], "cases": indexed}


def make_semantic_template(cases_path: Path, destination: Path) -> dict:
    for path in (cases_path, destination):
        if any((parent / ".git").exists() for parent in (path.resolve(), *path.resolve().parents)):
            raise CorpusError("Semantic inputs and template must remain outside Git working trees")
    if destination.exists():
        raise CorpusError("Use a new private destination for the score template")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    if not isinstance(cases, list) or not cases:
        raise CorpusError("At least one case is needed for a semantic template")
    records = []
    for case in cases:
        if not isinstance(case, dict) or not all(isinstance(case.get(k), str) and case[k].strip()
                                                for k in ("case_id", "content_brief", "baseline")) or not isinstance(case.get("variants"), dict):
            raise CorpusError("Cases need IDs, content briefs, baseline and variants")
        drafts = {"none": case["baseline"], **case["variants"]}
        records.append({"case_id": case["case_id"],
                        "reference_sha256": hashlib.sha256(case["content_brief"].encode()).hexdigest(),
                        "scores": {label: {"sha256": hashlib.sha256(body.encode()).hexdigest(), "similarity": None}
                                   for label, body in drafts.items()}})
    destination.write_text(json.dumps({"model": "REPLACE_WITH_EXACT_LOCAL_SBERT_MODEL", "metric": "cosine",
                                       "cases": records}, indent=2), encoding="utf-8")
    return {"status": "private_template_created", "cases": len(records),
            "note": "Fill every score and the exact model identifier; hashes bind values to texts but do not authenticate an external scorer."}


def semantic_guard_from_scores(reference: str, baseline: str, candidates: dict[str, str],
                               case_id: str, payload: dict) -> dict:
    record = payload["cases"].get(case_id)
    texts = {"none": baseline, **candidates}
    if not isinstance(record, dict) or record.get("reference_sha256") != hashlib.sha256(reference.encode()).hexdigest():
        raise CorpusError("Semantic reference hash mismatch or missing case")
    imported = record.get("scores")
    if not isinstance(imported, dict) or set(imported) != set(texts):
        raise CorpusError("Score file must cover the baseline and every variant exactly")
    values = {}
    for label, body in texts.items():
        item = imported[label]
        if not isinstance(item, dict) or item.get("sha256") != hashlib.sha256(body.encode()).hexdigest() or type(item.get("similarity")) not in (float, int):
            raise CorpusError("Semantic score text hash mismatch or invalid score")
        values[label] = float(item["similarity"])
    result = _decision(values["none"], {label: value for label, value in values.items() if label != "none"}, "imported_sbert")
    result["model"] = payload["model"]
    result["trust"] = "External scores were matched to text hashes; model identity and score correctness were not independently verified."
    return result
