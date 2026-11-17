"""Summarize the complete MegNIST author baseline, for evaluator-private use.

This is the seven-width, ten-seed *reference* scope. It does not impose that
architecture grid on an improvement candidate or decide scientific success.
The separately returned representative seed uses the author's post-hoc test
tie-break and must never select an improvement candidate.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from numbers import Integral, Real

import numpy as np

PAPER_HIDDEN_SIZES = (32, 64, 128, 256, 512, 1024, 2048)
PAPER_SEEDS = tuple(range(42, 52))


def _identifier(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer, not a coerced identifier")
    return int(value)


def _accuracy(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite numeric percentage")
    value = float(value)
    if not np.isfinite(value) or not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be a finite percentage in [0, 100]")
    return value


def summarize_reference(records: Iterable[Mapping[str, object]]) -> dict:
    """Validate all 70 cells and apply the original NumPy selection arithmetic.

    Each record needs ``hidden_size``, ``seed``, ``val_acc`` and ``test_acc``.
    Other source run metadata is allowed but is not interpreted here. Input
    order cannot change the original width/seed tie ordering. No SD, tolerance,
    significance threshold or improvement result is inferred from these values.
    """
    if isinstance(records, (str, bytes, Mapping)):
        raise ValueError("records must be a sequence of individual run records")
    by_key: dict[tuple[int, int], dict] = {}
    for index, record in enumerate(records):
        if index >= 70:
            raise ValueError("The reference grid contains more than 70 records")
        if not isinstance(record, Mapping):
            raise ValueError("Each reference run must be a mapping")
        required = {"hidden_size", "seed", "val_acc", "test_acc"}
        if not required <= record.keys():
            raise ValueError("Each run requires hidden_size, seed, val_acc and test_acc")
        width = _identifier(record["hidden_size"], "hidden_size")
        seed = _identifier(record["seed"], "seed")
        if width not in PAPER_HIDDEN_SIZES or seed not in PAPER_SEEDS:
            raise ValueError("Run lies outside the original reference width/seed grid")
        key = (width, seed)
        if key in by_key:
            raise ValueError("Duplicate reference width/seed cell")
        by_key[key] = {
            "hidden_size": width,
            "seed": seed,
            "val_acc": _accuracy(record["val_acc"], "val_acc"),
            "test_acc": _accuracy(record["test_acc"], "test_acc"),
        }

    expected = {(width, seed) for width in PAPER_HIDDEN_SIZES for seed in PAPER_SEEDS}
    if set(by_key) != expected:
        raise ValueError("The complete original 7-width by 10-seed reference grid is required")
    ordered = [by_key[(width, seed)] for width in PAPER_HIDDEN_SIZES for seed in PAPER_SEEDS]
    validation = {
        width: np.asarray([by_key[(width, seed)]["val_acc"] for seed in PAPER_SEEDS], dtype=float)
        for width in PAPER_HIDDEN_SIZES
    }
    test = {
        width: np.asarray([by_key[(width, seed)]["test_acc"] for seed in PAPER_SEEDS], dtype=float)
        for width in PAPER_HIDDEN_SIZES
    }
    means = [(width, float(validation[width].mean())) for width in PAPER_HIDDEN_SIZES]
    # max retains the first canonical width on an exact mean-validation tie,
    # matching the author's ordered all_results dictionary.
    selected_width = max(means, key=lambda item: item[1])[0]
    vals = validation[selected_width]
    tests = test[selected_width]
    distances = np.abs(vals - np.median(vals))
    tied = np.flatnonzero(distances == distances.min())
    used_test = len(tied) > 1
    if used_test:
        test_distances = np.abs(tests[tied] - np.median(tests))
        selected_index = int(tied[np.argmin(test_distances)])
    else:
        selected_index = int(tied[0])

    return {
        "scope": "complete_original_reference_baseline_grid",
        "visibility": "evaluator_private_contains_reference_test_results",
        "widths": list(PAPER_HIDDEN_SIZES),
        "seeds": list(PAPER_SEEDS),
        "records": ordered,
        "mean_validation_accuracy_by_width": {str(width): mean for width, mean in means},
        "mean_test_accuracy_by_width": {
            str(width): float(test[width].mean()) for width in PAPER_HIDDEN_SIZES
        },
        "selected_width": selected_width,
        "width_selection": "maximum_mean_validation_accuracy_first_original_width_on_exact_tie",
        "posthoc_representative": {
            "seed": PAPER_SEEDS[selected_index],
            "seed_index": selected_index,
            "val_acc": float(vals[selected_index]),
            "test_acc": float(tests[selected_index]),
            "used_test_tiebreak": used_test,
            "role": "posthoc_reference_metadata_only",
            "eligible_candidate_selection": False,
            "rule": "nearest_median_validation_then_nearest_median_test_then_first_original_seed",
        },
        "candidate_grid_required": False,
        "scientific_qualification": False,
        "runtime_isolation_qualified": False,
        "reproduction_status": "unknown",
        "improvement_status": "unknown",
        "uncertainty": "No SD convention, inferential interval or comparison threshold is supplied.",
    }
