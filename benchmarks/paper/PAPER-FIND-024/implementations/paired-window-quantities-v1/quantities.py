"""Source Fig. 3 paired integration-window quantities, without neural fitting.

The finite input domain, source order and missing scientific qualification are
described in README.md. No cohort selection or population reduction is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


SCHEMA = "find024-paired-window-input/v1"
RESULT_SCHEMA = "find024-paired-window-quantities/v1"
VECTOR_FIELDS = (
    "slow_tied_width_sec", "fast_tied_width_sec", "overall_width_sec",
    "slow_logP_gaussfit", "fast_logP_gaussfit",
)


class QuantityError(ValueError):
    """The supplied source-shaped panel cannot be transformed without omission."""


def _require(condition, message):
    if not condition:
        raise QuantityError(message)


def _name(value, field):
    _require(isinstance(value, str) and bool(value.strip()),
             f"{field} must be a nonempty string")
    return value


def _number(value, field, *, positive=False):
    _require(type(value) in (int, float), f"{field} must be real numeric")
    try:
        value = float(value)
    except OverflowError as exc:
        raise QuantityError(f"{field} must be finite float64") from exc
    _require(math.isfinite(value), f"{field} must be finite float64")
    _require(not positive or value > 0, f"{field} must be positive")
    return value


def paired_quantities(panel):
    """Keep every supplied source participant/electrode row in its input order.

    Input order and supplied identities are preserved, not authenticated. Widths
    are seconds. The independently fitted overall width is never replaced with
    an average of the rate-specific tied widths. Only finite values and strictly
    positive widths are supported; an invalid row rejects the entire panel.
    """
    _require(isinstance(panel, dict) and set(panel) == {"schema", "participants"},
             "panel must contain exactly schema and participants")
    _require(panel["schema"] == SCHEMA, f"schema must be {SCHEMA}")
    participants = panel["participants"]
    _require(isinstance(participants, list) and bool(participants),
             "participants must be a nonempty ordered list")
    participant_ids = set()
    rows = []
    for participant in participants:
        expected = {"participant_id", "electrode_ids", *VECTOR_FIELDS}
        _require(isinstance(participant, dict) and set(participant) == expected,
                 "participant must contain identity and the five documented vectors")
        participant_id = _name(participant["participant_id"], "participant_id")
        _require(participant_id not in participant_ids, "duplicate participant_id")
        participant_ids.add(participant_id)
        electrodes = participant["electrode_ids"]
        _require(isinstance(electrodes, list) and bool(electrodes),
                 "electrode_ids must be a nonempty ordered list")
        for electrode in electrodes:
            _name(electrode, "electrode_id")
        _require(len(set(electrodes)) == len(electrodes),
                 "duplicate electrode_id within participant")
        values = {}
        for field in VECTOR_FIELDS:
            vector = participant[field]
            _require(isinstance(vector, list) and len(vector) == len(electrodes),
                     f"{field} must cover exactly the ordered electrodes")
            values[field] = [_number(value, field, positive=field.endswith("width_sec"))
                             for value in vector]
        for index, electrode in enumerate(electrodes):
            slow = values["slow_tied_width_sec"][index]
            fast = values["fast_tied_width_sec"][index]
            overall = values["overall_width_sec"][index]
            slow_quality = values["slow_logP_gaussfit"][index]
            fast_quality = values["fast_logP_gaussfit"][index]
            # Source intwin_maps.m adds the two half-scaled quality values.
            quality = slow_quality / 2 + fast_quality / 2
            # Difference of logarithms matches source and avoids forming a
            # possibly overflowing/underflowing ratio of valid positive widths.
            yoking = (math.log2(slow) - math.log2(fast)) / math.log2(3)
            rows.append({
                "participant_id": participant_id,
                "electrode_id": electrode,
                "slow_tied_width_sec": slow,
                "fast_tied_width_sec": fast,
                "overall_width_sec": overall,
                "log2_overall_width_sec": math.log2(overall),
                "slow_logP_gaussfit": slow_quality,
                "fast_logP_gaussfit": fast_quality,
                "mean_rate_fit_quality": quality,
                "source_fit_eligible": quality > 3,
                "structure_yoking": yoking,
            })
    return {
        "schema": RESULT_SCHEMA,
        "task_id": "PAPER-FIND-024",
        "rows": rows,
        "participant_count": len(participants),
        "electrode_count": len(rows),
        "scientific_qualification": "unknown",
        "native_parity_verified": False,
        "scope": "Finite source-shaped window transformation only; no neural fitting, cohort authentication, anatomical join, population inference or paper success criterion.",
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise QuantityError(f"nonfinite JSON constant: {value}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True,
                        help="Operator-frozen hash; identifies input bytes, not source authenticity")
    args = parser.parse_args(argv)
    raw = args.panel.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    _require(digest == args.expected_sha256, "panel SHA256 mismatch")
    panel = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    result = paired_quantities(panel)
    result["input_sha256"] = digest
    result["input_bytes"] = len(raw)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
