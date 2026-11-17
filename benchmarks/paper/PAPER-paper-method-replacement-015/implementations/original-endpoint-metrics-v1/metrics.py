"""Per-neuron spike-rate metrics; no source preparation or model execution.

The operator supplies already aligned, already smoothed target rates and a fixed
support shared by all methods. See README.md for the unresolved source protocol.
Only the Python standard library is required.
"""

from dataclasses import dataclass
import math


SOURCE_CONTROLS = (
    "raw_fluorescence",
    "oasis",
    "default_cascade",
    "glutamatergic_cascade",
    "gabaergic_cascade",
)
RATE_METHODS = frozenset(SOURCE_CONTROLS[2:] + ("candidate",))
WITHIN_DATASET = {
    "glutamatergic": "glutamatergic_cascade",
    "gabaergic": "gabaergic_cascade",
    "cortex": "default_cascade",
}
# Article Methods, Quantification of spike rate inference performance. The
# matched-precision control in Extended Data Fig. 4-3c is a distinct condition.
SOURCE_SIGMA_SECONDS = {2.5: 0.4, 5: 0.2, 10: 0.1, 15: 0.1,
                        20: 0.1, 25: 0.05, 30: 0.05}


@dataclass(frozen=True)
class Prediction:
    values: tuple
    unit: str  # hz, expected_spikes_per_bin, or arbitrary


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: a real number is required")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name}: unrepresentable number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name}: a finite number is required")
    return result


def _pearson(target, prediction):
    """Pearson over uniform bins, without pooling neurons or changing support."""
    if len(target) < 2:
        return {"value": None, "status": "insufficient_support"}
    if min(target) == max(target):
        return {"value": None, "status": "constant_target"}
    if min(prediction) == max(prediction):
        return {"value": None, "status": "constant_prediction"}
    # Scale each operand independently before centering to avoid squaring large
    # finite rates. Positive scaling does not change Pearson correlation.
    target_scale = max(abs(x) for x in target)
    prediction_scale = max(abs(x) for x in prediction)
    x = [v / target_scale for v in target]
    y = [v / prediction_scale for v in prediction]
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    x, y = [v - mx for v in x], [v - my for v in y]
    xx, yy = math.fsum(v * v for v in x), math.fsum(v * v for v in y)
    if xx == 0 or yy == 0:
        return {"value": None, "status": "unrepresentable_variation"}
    value = math.fsum(a * b for a, b in zip(x, y)) / math.sqrt(xx) / math.sqrt(yy)
    if not math.isfinite(value):
        return {"value": None, "status": "unrepresentable_correlation"}
    return {"value": max(-1.0, min(1.0, value)), "status": "defined"}


def _rate_diagnostics(target, prediction):
    if not target:
        return {"normalized_l1": None, "signed_bias": None,
                "status": "insufficient_support"}
    # A common scale preserves sum(abs(p-y))/sum(y) and sum(p-y)/sum(y).
    scale = max(max(abs(v) for v in target), max(abs(v) for v in prediction))
    if max(target) == 0:
        return {"normalized_l1": None, "signed_bias": None,
                "status": "zero_target_signal"}
    signal = math.fsum(v / scale for v in target)
    if signal == 0:
        return {"normalized_l1": None, "signed_bias": None,
                "status": "unrepresentable_diagnostics"}
    differences = [p / scale - y / scale for y, p in zip(target, prediction)]
    error = math.fsum(abs(v) for v in differences) / signal
    bias = math.fsum(differences) / signal
    if not math.isfinite(error) or not math.isfinite(bias):
        return {"normalized_l1": None, "signed_bias": None,
                "status": "unrepresentable_diagnostics"}
    return {"normalized_l1": error, "signed_bias": bias, "status": "defined"}


def score_neuron(*, target_hz, controls, support, sampling_rate_hz, candidate=None):
    """Score one neuron in one frozen condition against five operator controls.

    ``controls`` must be supplied from an independently selected operator source;
    this in-memory kernel cannot authenticate its provenance. ``candidate`` has
    no field that can replace a control. Support is a same-length sequence of
    literal bools selected by the operator before prediction inspection.
    Nonfinite scored predictions are rejected, never converted into a mask.
    Context values outside support may be nonfinite. No smoothing, resampling,
    clipping, temporal shift or fitting occurs here.
    """
    rate = _number(sampling_rate_hz, "sampling_rate_hz")
    if rate <= 0:
        raise ValueError("sampling_rate_hz must be positive")
    if set(controls) != set(SOURCE_CONTROLS):
        raise ValueError("all five separate original controls are required")
    target_hz, support = tuple(target_hz), tuple(support)
    if len(support) != len(target_hz) or any(type(v) is not bool for v in support):
        raise ValueError("support must contain one literal bool per target bin")
    target = [_number(v, "target_hz") for v, keep in zip(target_hz, support) if keep]
    if any(v < 0 for v in target):
        raise ValueError("target_hz must be a nonnegative spike rate")
    methods = {}
    operands = [(method, controls[method]) for method in SOURCE_CONTROLS]
    if candidate is not None:
        operands.append(("candidate", candidate))
    for method, prediction in operands:
        if not isinstance(prediction, Prediction):
            raise ValueError(f"{method}: Prediction required")
        values = tuple(prediction.values)
        if len(values) != len(target_hz):
            raise ValueError(f"{method}: complete identical bin count required")
        allowed = {"hz", "expected_spikes_per_bin"} if method in RATE_METHODS else {"arbitrary"}
        if prediction.unit not in allowed:
            raise ValueError(f"{method}: invalid unit {prediction.unit!r}")
        converted = []
        for value, keep in zip(values, support):
            if keep:
                v = _number(value, method)
                if prediction.unit == "expected_spikes_per_bin":
                    v = _number(v * rate, f"{method} converted to Hz")
                converted.append(v)
        methods[method] = {
            "correlation": _pearson(target, converted),
            "rate_diagnostics": (_rate_diagnostics(target, converted) if method in RATE_METHODS
                                 else {"normalized_l1": None, "signed_bias": None,
                                       "status": "amplitude_not_calibrated"}),
        }
    return {"total_bins": len(target_hz), "scored_bins": len(target),
            "sampling_rate_hz": rate, "methods": methods}


def _summary(values):
    defined = [v for v in values if v is not None]
    mean = middle = None
    if defined:
        scale = max(abs(v) for v in defined)
        mean = (math.fsum(v / scale for v in defined) / len(defined)) * scale if scale else 0.0
        ordered = sorted(defined)
        half = len(ordered) // 2
        middle = (ordered[half] if len(ordered) % 2
                  else ordered[half - 1] / 2 + ordered[half] / 2)
    return {"expected_neurons": len(values), "defined_neurons": len(defined),
            "undefined_neurons": len(values) - len(defined),
            "mean": mean, "median": middle}


def score_condition(*, expected_neurons, observations, sampling_rate_hz):
    """Evaluate all supplied frozen neuron identities in one condition.

    ``expected_neurons`` maps operator-selected neuron IDs to the original cohort
    names. Each observation contains neuron_id and score_neuron's target_hz,
    controls, candidate and support operands. The exact roster must be recovered
    separately: cardinality is not evidence that a source cohort is complete.
    Returns per-neuron outcomes and descriptive summaries; no win decision or
    pooled-cell-type summary. Calling this for one condition is not a full-panel
    evaluation. All original conditions and cortex controls remain required by
    the paper contract.
    """
    if not expected_neurons or any(not isinstance(k, str) or not k for k in expected_neurons):
        raise ValueError("nonempty frozen neuron identity map required")
    if any(group not in WITHIN_DATASET for group in expected_neurons.values()):
        raise ValueError("unknown cohort")
    rows = {}
    candidate_presence = set()
    for observation in observations:
        required = {"neuron_id", "target_hz", "controls", "support"}
        if not required <= set(observation) or set(observation) - required - {"candidate"}:
            raise ValueError("exact per-neuron observation fields required")
        identity = observation["neuron_id"]
        if not isinstance(identity, str) or identity not in expected_neurons or identity in rows:
            raise ValueError("unknown or repeated neuron identity")
        operands = {k: v for k, v in observation.items() if k != "neuron_id"}
        candidate_presence.add(operands.get("candidate") is not None)
        rows[identity] = score_neuron(**operands, sampling_rate_hz=sampling_rate_hz)
    if set(rows) != set(expected_neurons):
        raise ValueError("every frozen neuron is required; omissions are not zero scores")
    if len(candidate_presence) != 1:
        raise ValueError("candidate predictions must cover every neuron or none")
    with_candidate = True in candidate_presence
    cohorts = {}
    for cohort in sorted(set(expected_neurons.values())):
        identities = sorted(k for k, group in expected_neurons.items() if group == cohort)
        summaries = {}
        for method in SOURCE_CONTROLS + (("candidate",) if with_candidate else ()):
            summaries[method] = {
                "correlation": _summary([rows[k]["methods"][method]["correlation"]["value"] for k in identities]),
                "normalized_l1": _summary([rows[k]["methods"][method]["rate_diagnostics"]["normalized_l1"] for k in identities]),
                "signed_bias": _summary([rows[k]["methods"][method]["rate_diagnostics"]["signed_bias"] for k in identities]),
            }
        cohorts[cohort] = {"neuron_ids": identities, "methods": summaries}
        if not with_candidate:
            continue
        comparator = WITHIN_DATASET[cohort]
        deltas = {}
        for identity in identities:
            methods = rows[identity]["methods"]
            candidate_corr = methods["candidate"]["correlation"]["value"]
            reference_corr = methods[comparator]["correlation"]["value"]
            deltas[identity] = (candidate_corr - reference_corr
                                if candidate_corr is not None and reference_corr is not None else None)
        cohorts[cohort]["paired_candidate_minus_reference"] = {
            "reference_method": comparator,
            "per_neuron_correlation_delta": deltas,
            "correlation_delta": _summary(list(deltas.values())),
        }
    return {"per_neuron": dict(sorted(rows.items())), "cohorts": cohorts}
