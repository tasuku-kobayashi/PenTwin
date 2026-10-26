"""Optional local SBERT guard on candidate continuations; no network fallback."""

from __future__ import annotations

import math
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
    threshold = max(MIN_BASELINE, baseline_score - MAX_DROP)
    assessed = {}
    for index, name in enumerate(names, 2):
        score = _cosine(vectors[0], vectors[index])
        assessed[name] = {"similarity": round(score, 4), "pass": score >= threshold}
    return {"baseline_similarity": round(baseline_score, 4),
            "baseline_adequate": baseline_score >= MIN_BASELINE,
            "threshold": round(threshold, 4), "max_drop": MAX_DROP,
            "candidates": assessed,
            "status": "scored" if baseline_score >= MIN_BASELINE else "baseline_inadequate",
            "limits": "Cosine similarity to the same content reference is a semantic screen, not a scientific factuality or logical validity certificate. A 0.05 relative drop and 0.70 baseline floor are provisional engineering thresholds, not calibrated life-science cutoffs."}
