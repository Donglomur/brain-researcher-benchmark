"""FAST Figure 3b/3f correlation vectors on an operator-frozen supplied panel.

This arithmetic component neither authenticates a source panel nor adopts a
benchmark. It does not choose pixels, align signals, fit a baseline, or average
away the original per-neuron/per-pixel coefficients.
"""
from __future__ import annotations

import hashlib
import json
import math
from numbers import Real
import struct


TASK_ID = "PAPER-paper-method-031"
SOURCE_COMMIT = "6f92663f7a36589507cac57c8d24cfd8adbce7b1"
SCHEMA = "fast-original-correlation-panels/v1"
SYNTHETIC_METHODS = ("raw", "DeepCAD-RT", "SRDTrans", "DeepVid", "SUPPORT", "FAST")
VOLTAGE_METHODS = ("raw", "FAST")
CONDITIONS = {"synthetic_fig3b": ("2ms", "4ms", "6ms", "8ms"),
              "voltage_fig3f": ("real_voltage",)}


class PanelError(ValueError):
    """The supplied panel does not satisfy this component's declared support."""


def _require(condition, message):
    if not condition:
        raise PanelError(message)


def _keys(value, expected, label):
    _require(isinstance(value, dict) and set(value) == set(expected),
             label + " fields differ")


def _name(value, label):
    _require(isinstance(value, str) and value.strip() == value and bool(value),
             label + " must be a nonempty trimmed string")
    return value


def _ids(value, label, expected_count=None):
    _require(isinstance(value, list), label + " must be a list")
    for item in value:
        _name(item, label)
    _require(len(value) >= 2 and len(set(value)) == len(value),
             label + " must contain distinct identities")
    if expected_count is not None:
        _require(len(value) == expected_count, label + " extent differs")
    return value


def support_sha256(support):
    """Validate the numerical-panel roster and return its canonical commitment.

    A commitment establishes byte/ordering identity, not original-paper lineage.
    ``source_provenance`` is an external operator-record identifier, not a claim
    that this component has verified the record or resolved its unknowns.
    """
    _keys(support, ("schema", "task_id", "family", "source_commit",
                    "source_provenance", "strata"), "support")
    _require(support["schema"] == SCHEMA and support["task_id"] == TASK_ID,
             "support schema/task differs")
    _require(support["source_commit"] == SOURCE_COMMIT, "author-code anchor differs")
    _name(support["source_provenance"], "source_provenance")
    family = support["family"]
    _require(isinstance(family, str) and family in CONDITIONS, "unknown panel family")
    strata = support["strata"]
    _require(isinstance(strata, list) and len(strata) == len(CONDITIONS[family]),
             "complete condition roster required")
    for row, condition in zip(strata, CONDITIONS[family]):
        _keys(row, ("condition_id", "recording_id", "frame_ids", "unit_ids"), "stratum")
        _require(row["condition_id"] == condition, "condition identity/order differs")
        _name(row["recording_id"], "recording_id")
        _ids(row["frame_ids"], "frame_ids", 4982 if family == "voltage_fig3f" else None)
        _ids(row["unit_ids"], "unit_ids", 100 if family == "voltage_fig3f" else 10)
    raw = json.dumps(support, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _trace(value, count, label):
    _require(isinstance(value, (list, tuple)) and len(value) == count,
             label + " must contain every original frame")
    result = []
    for item in value:
        _require(isinstance(item, Real) and not isinstance(item, bool),
                 label + " contains a nonnumeric value")
        try:
            item = float(item)
        except (OverflowError, TypeError, ValueError) as exc:
            raise PanelError(label + " cannot be represented as finite float64") from exc
        _require(math.isfinite(item), label + " contains a nonfinite value")
        result.append(item)
    return tuple(result)


def _prepared_trace(values):
    """Scale before centering so finite large-magnitude operands do not overflow."""
    scale = max(abs(x) for x in values)
    scaled = tuple(x / scale for x in values) if scale else values
    mean = math.fsum(scaled) / len(scaled)
    centered = tuple(x - mean for x in scaled)
    energy = math.fsum(x * x for x in centered)
    digest = hashlib.sha256(b"float64-big-endian-trace/v1\0")
    for value in values:
        digest.update(struct.pack(">d", value))
    return centered, energy, digest.hexdigest()


def _correlation(prepared_prediction, prepared_reference):
    left, left_ss, _ = prepared_prediction
    right, right_ss, _ = prepared_reference
    if left_ss == 0 or right_ss == 0:
        reason = ("constant_both" if left_ss == 0 and right_ss == 0 else
                  "constant_prediction" if left_ss == 0 else "constant_reference")
        return None, reason
    coefficient = math.fsum(a * b for a, b in zip(left, right)) / (
        math.sqrt(left_ss) * math.sqrt(right_ss))
    _require(math.isfinite(coefficient) and abs(coefficient) <= 1 + 1e-12,
             "unstable correlation arithmetic")
    # Only floating roundoff outside the mathematical range is clamped.
    return max(-1.0, min(1.0, coefficient)), "defined"


def _packet(packet, support, commitment, reference=False):
    _keys(packet, ("support_sha256", "strata"), "trace packet")
    _require(packet["support_sha256"] == commitment, "support commitment differs")
    rows = packet["strata"]
    _require(isinstance(rows, list) and len(rows) == len(support["strata"]),
             "packet condition coverage differs")
    result = []
    for row, frozen in zip(rows, support["strata"]):
        _keys(row, ("condition_id", "recording_id", "frame_ids", "unit_ids", "traces"),
              "trace stratum")
        for key in ("condition_id", "recording_id", "frame_ids"):
            _require(row[key] == frozen[key], key + " differs from frozen support")
        wanted = (["synchronized_electrophysiology"]
                  if reference and support["family"] == "voltage_fig3f"
                  else frozen["unit_ids"])
        _require(row["unit_ids"] == wanted, "unit identities/order differ")
        traces = row["traces"]
        _require(isinstance(traces, list) and len(traces) == len(wanted),
                 "trace roster differs")
        result.append([_prepared_trace(_trace(trace, len(frozen["frame_ids"]), "trace"))
                       for trace in traces])
    return result


def evaluate_panel(support, reference, methods, candidate=None):
    """Recompute all original correlation vectors and optional paired deltas.

    Inputs are source-preprocessed, synchronized ΔF/F traces and either clean
    synthetic traces or the real simultaneous electrophysiology trace. This
    component never chooses or fits these transformations. Reference/operator
    custody and candidate freeze must be enforced externally.

    Each packet carries the frozen condition, recording, ordered frame and unit
    roster. Candidate is a separate packet, never a replacement for source FAST.
    Undefined coefficients remain explicit at their original identities. There
    is no aggregate score, uncertainty test, source-paper win or binary reward.
    """
    commitment = support_sha256(support)
    family = support["family"]
    expected = VOLTAGE_METHODS if family == "voltage_fig3f" else SYNTHETIC_METHODS
    _require(isinstance(methods, dict) and set(methods) == set(expected),
             "all original methods must be supplied exactly once")
    ref = _packet(reference, support, commitment, reference=True)
    measured = {name: _packet(methods[name], support, commitment) for name in expected}
    if candidate is not None:
        measured["candidate"] = _packet(candidate, support, commitment)
    strata = []
    for index, frozen in enumerate(support["strata"]):
        units = []
        for unit_index, unit_id in enumerate(frozen["unit_ids"]):
            target = ref[index][0 if family == "voltage_fig3f" else unit_index]
            outputs = {}
            for name, values in measured.items():
                trace = values[index][unit_index]
                correlation, status = _correlation(trace, target)
                outputs[name] = {"pearson_r": correlation, "status": status,
                                 "trace_float64_sha256": trace[2]}
            delta = None
            if candidate is not None:
                author_r = outputs["FAST"]["pearson_r"]
                candidate_r = outputs["candidate"]["pearson_r"]
                delta = (candidate_r - author_r
                         if candidate_r is not None and author_r is not None else None)
            units.append({"unit_id": unit_id, "reference_float64_sha256": target[2],
                          "methods": outputs,
                          "candidate_minus_FAST_r": delta})
        strata.append({"condition_id": frozen["condition_id"],
                       "recording_id": frozen["recording_id"],
                       "original_frames": len(frozen["frame_ids"]),
                       "units": units})
    count = sum(len(row["unit_ids"]) for row in support["strata"]) * len(expected)
    undefined = sum(unit["methods"][method]["pearson_r"] is None
                    for row in strata for unit in row["units"] for method in expected)
    return {"schema": SCHEMA, "task_id": TASK_ID, "family": family,
            "support_sha256": commitment, "source_commit": SOURCE_COMMIT,
            "status": "supplied_original_panel_arithmetic_only",
            "original_coefficient_count": count,
            "undefined_original_coefficients": undefined,
            "strata": strata,
            "qualification": {"source_lineage_verified": False,
                              "source_preprocessing_verified": False,
                              "full_paper_panel_complete": False,
                              "reproduction": "not_assessed",
                              "same_task_improvement": "not_assessed",
                              "paper_win": None, "binary_reward": None},
            "limits": ["Ordered supplied support is not authenticated original support.",
                       "Zero-lag signed Pearson correlation cannot establish amplitude fidelity.",
                       "The 100 quantitative pixels are not independent animals.",
                       "The separate 1000 displayed pixels are not substituted or evaluated here.",
                       "Calcium segmentation, morphology, timing and companion controls remain separate."]}
