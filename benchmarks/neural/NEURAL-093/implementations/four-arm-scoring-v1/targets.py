"""Recovered stimulus target and chronological split, independent of behavior.

Adapted from full-cohort-schema-v3/worker.py functions targets and partitions.
This operator-only arithmetic does not create observation packets, read files,
verify recording coverage, or make eligible rows into independent animals.
"""

CLASS_ORDER = ("left_stronger", "equal", "right_stronger")


def target_classes(left, right, np):
    """Return int8 labels (-1 invalid) and validity for finite contrasts in [0,1]."""
    left, right = np.asarray(left), np.asarray(right)
    if (left.ndim != 1 or left.shape != right.shape
            or left.dtype.kind not in "fiu" or right.dtype.kind not in "fiu"):
        raise ValueError("matched numeric source contrast vectors")
    valid = np.isfinite(left) & np.isfinite(right) & (left >= 0) & (left <= 1)
    valid &= (right >= 0) & (right <= 1)
    labels = np.full(len(left), -1, dtype=np.int8)
    labels[valid & (left > right)] = 0
    labels[valid & (left == right)] = 1
    labels[valid & (left < right)] = 2
    return labels, valid


def partitions(original_trial_count):
    """Source-row boundaries BEFORE eligibility; retain the original remainder."""
    if type(original_trial_count) is not int or original_trial_count < 0:
        raise ValueError("nonnegative original trial count")
    n = original_trial_count
    fit_end = (3 * n) // 5
    validation_end = fit_end + n // 5
    return {"fit": (0, fit_end), "validation": (fit_end, validation_end),
            "query": (validation_end, n)}


def eligible_split_rows(original_trial_count, eligibility, np):
    """Intersect a previously justified eligibility mask with original rows.

    Does not invent eligibility: the original geometry also requires valid
    trial intervals, valid contrasts and the full fixed [onset,onset+.1) window.
    """
    bounds = partitions(original_trial_count)
    mask = np.asarray(eligibility)
    if mask.shape != (original_trial_count,) or mask.dtype.kind != "b":
        raise ValueError("one Boolean eligibility flag per original trial")
    rows = np.flatnonzero(mask)
    return {name: rows[(rows >= start) & (rows < stop)]
            for name, (start, stop) in bounds.items()}
