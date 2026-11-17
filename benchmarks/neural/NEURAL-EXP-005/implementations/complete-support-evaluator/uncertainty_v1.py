"""Paired infant bootstrap of already frozen complete-support score reports.

This is conditional uncertainty for the observed 79 infant losses. It does not
refit predictors, rerun cases, or estimate training-set/model-selection variation.
Reports and identities are assessor-private, just like evaluate.py outputs.
"""

import hashlib
import math

from evaluate import compare
from protocol import ContractError, _finite, _text, canonical_bytes, digest


METHOD = "helsinki-paired-infant-percentile-bootstrap-v1"


def _indices(seed):
    """Versioned, unbiased uniform 0..78 draws, independent of Python PRNGs.

    SHA256 blocks bind the UTF-8 canonical JSON domain/seed and an eight-byte
    big-endian counter. Read eight unsigned big-endian 32-bit words per block;
    reject the incomplete final multiple of 79 before taking the remainder.
    """
    prefix = canonical_bytes([METHOD, seed])
    limit = (2**32 // 79) * 79
    counter = 0
    while True:
        block = hashlib.sha256(prefix + counter.to_bytes(8, "big")).digest()
        counter += 1
        for offset in range(0, 32, 4):
            word = int.from_bytes(block[offset:offset + 4], "big")
            if word < limit:
                yield word % 79


def _quantile(ordered, probability):
    """Linear interpolation at (B-1)*p, including both finite endpoints."""
    index = (len(ordered) - 1) * probability
    lo = math.floor(index)
    hi = min(lo + 1, len(ordered) - 1)
    weight = index - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def paired_infant_bootstrap(left, right, *, seed, resamples=10000, confidence=0.95):
    """Resample 79 paired infant losses with replacement, equally weighted.

    Inputs must be original complete reports returned by evaluate(). Existing
    compare() checks the frozen reference, all identities, folds, case support,
    and the primary mean before any resampling. Freeze seed, confidence and
    resample count before results; this helper cannot enforce that chronology.
    A negative right-minus-left loss favors the right arm. No p-value or
    superiority decision is produced.
    """
    _text(seed, "bootstrap seed")
    if type(resamples) is not int or resamples < 2:
        raise ContractError("resamples must be an integer of at least two")
    _finite(confidence, "confidence")
    if not 0 < confidence < 1:
        raise ContractError("confidence must be strictly between zero and one")
    paired = compare(left, right)
    deltas = [row["right_minus_left_soft_vote_brier"] for row in paired["infants"]]
    draws = _indices(seed)
    replicates = [math.fsum(deltas[next(draws)] for _ in range(79)) / 79
                  for _ in range(resamples)]
    replicate_mean = math.fsum(replicates) / resamples
    standard_error = math.sqrt(math.fsum((x - replicate_mean)**2 for x in replicates)
                               / (resamples - 1))
    ordered = sorted(replicates)
    tail = (1 - confidence) / 2
    specification = {
        "method": METHOD, "seed": seed, "resamples": resamples,
        "confidence": confidence, "resampling_unit": "infant",
        "infants_per_resample": 79, "replacement": True,
        "weighting": "equal infant weights; paired right-minus-left losses",
        "quantile": "linear interpolation at (B-1)*p",
        "left_report_sha256": digest(left), "right_report_sha256": digest(right),
    }
    return {
        "schema": METHOD,
        "reference_sha256": paired["reference_sha256"],
        "assessment_id": left["assessment_id"], "protocol_id": left["protocol_id"],
        "n_infants": 79, "n_cases": left["n_cases"],
        "point_right_minus_left_soft_vote_brier": paired["macro_right_minus_left_soft_vote_brier"],
        "percentile_interval": {"confidence": confidence,
                                "lower": _quantile(ordered, tail),
                                "upper": _quantile(ordered, 1 - tail)},
        "bootstrap_standard_error": standard_error,
        "specification": specification, "specification_sha256": digest(specification),
        "replicate_sha256": digest(replicates),
        "scope": "conditional on the supplied frozen predictions and observed infant cohort",
        "limitations": [
            "Overlapping cross-validation training sets can induce dependence between infant losses.",
            "No predictor refitting, training-set variation or model-selection uncertainty is included.",
            "This interval alone does not establish population coverage, superiority or clinical validity.",
            "Source admission, contamination limits and all participant-access qualifications remain external.",
        ],
    }
