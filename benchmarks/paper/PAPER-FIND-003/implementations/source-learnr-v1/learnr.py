"""Pre-outlier channel Learn-R construction; no paper-success decision.

The public source supplies the eligibility, Spearman and Fisher operations.
This component stops before channel outliers, subject means and behavior fits.
Its JSON digest identifies the input representation, not the original CSV.
"""
from __future__ import annotations

import hashlib
import json
import math

PHASES = ("stimulus", "feedback", "interval")
FIELDS = frozenset(("channel", "subject", "trial", "ACC", "phase", "ripple"))
MAX_ROWS = 1_000_000  # Refuse over-limit input; never truncate scientific support.


def _number(value, label):
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError(label + " must be a finite number or null")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(label + " is outside the finite numeric domain") from exc
    if not math.isfinite(value):
        raise ValueError(label + " must be finite; null represents missing")
    return value


def _text(value, label):
    if type(value) is not str or not value or len(value) > 256:
        raise ValueError(label + " must be nonempty bounded text")
    return value


def _rank2(values):
    """Twice the average one-based ranks: ties have exact integer ranks."""
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for position in order[start:end]:
            result[position] = start + 1 + end
        start = end
    return result


def learn_r_group(trials, ripple_rates):
    """Source computeLearnR operations on one already selected channel/phase.

    null stands for source missing values. Missing observations remain in the
    eligibility denominator and make corr's default all-row result undefined.
    Infinite Fisher values are tagged rather than written as invalid JSON.
    """
    if type(trials) is not list or type(ripple_rates) is not list:
        raise ValueError("trial and ripple inputs must be lists")
    if len(trials) != len(ripple_rates) or len(trials) > MAX_ROWS:
        raise ValueError("equal bounded observation support is required")
    x = [_number(v, "trial") for v in trials]
    y = [_number(v, "ripple") for v in ripple_rates]
    n = len(x)
    positive = sum(v is not None and v > 0 for v in y)
    missing = sum(a is None or b is None for a, b in zip(x, y))
    result = {
        "n_observations": n,
        "n_positive_rates": positive,
        "n_missing_pairs": missing,
        "positive_fraction": positive / n if n else None,
        "eligibility": "eligible",
        "spearman_r": None,
        "fisher_z": None,
        "state": None,
    }
    # These gates precede corr in the author function, including for missing data.
    if n < 10 or positive * 10 < n:
        result["eligibility"] = "ineligible"
        result["state"] = "source_eligibility_nan"
        return result
    if missing:
        result["state"] = "source_missing_nan"
        return result
    rx, ry = _rank2(x), _rank2(y)
    sx, sy = sum(rx), sum(ry)
    ax, ay = [n * v - sx for v in rx], [n * v - sy for v in ry]
    xx, yy = sum(v * v for v in ax), sum(v * v for v in ay)
    if xx == 0 or yy == 0:
        result["state"] = "source_constant_nan"
        return result
    xy = sum(a * b for a, b in zip(ax, ay))
    product = xx * yy
    if xy * xy == product:
        r = 1.0 if xy > 0 else -1.0
        result["spearman_r"] = r
        result["state"] = "positive_infinite_fisher" if r > 0 else "negative_infinite_fisher"
        return result
    r = xy / math.sqrt(product)
    if not -1.0 < r < 1.0:
        # Do not clip a rounded boundary or invent a finite Fisher estimate.
        result["state"] = "floating_boundary_unresolved"
        return result
    result["spearman_r"] = r
    result["fisher_z"] = 0.5 * math.log((1.0 + r) / (1.0 - r))
    result["state"] = "finite"
    return result


def _positive_p99(values):
    """The existing task's explicitly declared Hyndman-Fan type-5 percentile."""
    positive = sorted(v for v in values if v is not None and v > 0)
    if not positive:
        return None
    h = len(positive) * 0.99 + 0.5
    if h <= 1:
        return positive[0]
    if h >= len(positive):
        return positive[-1]
    left = math.floor(h)
    fraction = h - left
    # Weighted interpolation avoids overflowing a difference of finite numbers.
    return positive[left - 1] * (1.0 - fraction) + positive[left] * fraction


def analyze_rows(raw_rows):
    """Build keyed pre-outlier Learn-R records from the original six-column ABI.

    Raw IDs are assigned in input order before phase-wise exclusions. All rows
    occur exactly once in excluded, retained-wrong, or a correct-trial group.
    This checks local bookkeeping, not authenticity, original first-session
    membership, full source inferential parity or paper reproduction.
    """
    if type(raw_rows) is not list or not 0 < len(raw_rows) <= MAX_ROWS:
        raise ValueError("nonempty complete input within the explicit row limit required")
    rows = []
    channel_subject = {}
    cells = set()
    for row_id, source in enumerate(raw_rows, 1):
        if type(source) is not dict or set(source) != FIELDS:
            raise ValueError("exact source six-column row required")
        row = dict(source)
        for key in ("channel", "subject", "ACC", "phase"):
            _text(row[key], key)
        if row["ACC"] not in ("correct", "wrong") or row["phase"] not in PHASES:
            raise ValueError("source accuracy and phase vocabulary required")
        for key in ("trial", "ripple"):
            row[key] = _number(row[key], key)
        channel, subject = row["channel"], row["subject"]
        if channel in channel_subject and channel_subject[channel] != subject:
            raise ValueError("source channel grouping would merge distinct subjects")
        channel_subject[channel] = subject
        cell = (channel, subject, row["trial"], row["ACC"], row["phase"])
        if cell in cells:
            raise ValueError("duplicate source cell outside the qualified source domain")
        cells.add(cell)
        row["raw_row_id"] = row_id
        rows.append(row)
    if {r["phase"] for r in rows} != set(PHASES):
        raise ValueError("all three original phases are required; do not score a subset")
    thresholds = {
        phase: _positive_p99([r["ripple"] for r in rows if r["phase"] == phase])
        for phase in PHASES
    }
    excluded, wrong, groups = [], [], {}
    for row in rows:
        threshold, rate = thresholds[row["phase"]], row["ripple"]
        if rate is not None and threshold is not None and rate > threshold:
            excluded.append(row["raw_row_id"])
        elif row["ACC"] == "wrong":
            wrong.append(row["raw_row_id"])
        else:
            groups.setdefault((row["channel"], row["phase"]), []).append(row)
    records = []
    for (channel, phase), members in sorted(groups.items()):
        values = learn_r_group([r["trial"] for r in members], [r["ripple"] for r in members])
        records.append({
            "channel": channel,
            "subject_as_recorded": channel_subject[channel],
            "phase": phase,
            "raw_row_ids": [r["raw_row_id"] for r in members],
            **values,
        })
    original_representation = [{k: r[k] for k in sorted(FIELDS)} for r in rows]
    encoded = json.dumps(original_representation, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return {
        "schema_version": "ripple-channel-learnr-stage/v1",
        "task_id": "PAPER-FIND-003",
        "scope": "post_source99_correct_trial_channel_learnr_before_outliers",
        "input_representation_sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_row_count": len(rows),
        "phase_positive_p99": thresholds,
        "source99_excluded_raw_row_ids": excluded,
        "retained_wrong_raw_row_ids": wrong,
        "channel_records": records,
        "downstream_status": "not_computed",
        "scientific_qualification": "unestablished",
    }
