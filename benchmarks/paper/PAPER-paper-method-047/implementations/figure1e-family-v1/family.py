"""Complete Figure 1e prepared-rate family; no cohort or paper-win inference.

The operator supplies already prepared rates, an ordered source roster and fixed
eligibility/support. This is an arithmetic/identity interface, not an attestation
that its inputs came from the original paper or an uncontaminated model.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path
import re


TASK = "PAPER-paper-method-047"
VARIANTS = ("gcamp8f", "gcamp8m", "gcamp8s")
METHODS = (
    "raw-fluorescence", "default-cascade", "gc8-pooled-cascade",
    "gc8-variant-cascade", "default-oasis", "tuned-oasis",
    "default-mlspike", "tuned-mlspike",
)
METRIC_SHA256 = "222cf71530a1e02c89eeee59db02811cfeba96f31c41d0c09a3a7a506df41e05"
METRIC_PATH = Path(__file__).resolve().parent.parent / "author-rate-metrics-v1" / "metrics.py"


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _keys(value, names, label):
    _need(type(value) is dict and set(value) == set(names), label + ": exact fields required")


def _text(value, label):
    _need(type(value) is str and 0 < len(value) <= 512 and value.strip() == value,
          label + ": nonempty bounded text required")
    return value


def _digest(value, label):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
          label + ": lowercase SHA256 required")
    return value


def _metrics():
    body = METRIC_PATH.read_bytes()
    _need(hashlib.sha256(body).hexdigest() == METRIC_SHA256,
          "prepared-rate metric dependency changed")
    # Execute the exact captured, checked body rather than reopen its path.
    spec = importlib.util.spec_from_loader("gcamp8_figure1e_metric_dependency", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(METRIC_PATH)
    exec(compile(body, str(METRIC_PATH), "exec"), module.__dict__)
    return module


def _manifest(manifest):
    _keys(manifest, {"schema", "task_id", "source_manifest_sha256", "condition",
                     "neurons", "eligibility"}, "manifest")
    _need(manifest["schema"] == "gcamp8-figure1e-support/v1" and manifest["task_id"] == TASK,
          "Figure 1e task schema required")
    _digest(manifest["source_manifest_sha256"], "source manifest identity")
    condition = manifest["condition"]
    _keys(condition, {"sampling_rate_hz", "smoothing_seconds", "noise_level",
                      "target_rate_units", "alignment_source_sha256"}, "condition")
    for name, expected in (("sampling_rate_hz", 30), ("smoothing_seconds", 0.05),
                           ("noise_level", 8)):
        _need(type(condition[name]) in (int, float) and condition[name] == expected,
              "Figure 1e declared condition differs: " + name)
    _text(condition["target_rate_units"], "prepared target-rate units")
    _digest(condition["alignment_source_sha256"], "alignment identity")
    rows = manifest["neurons"]
    _need(type(rows) is list and len(rows) > 0, "complete explicit operator neuron roster required")
    neurons = {}
    for row in rows:
        _keys(row, {"neuron_id", "variant", "sample_ids"}, "neuron")
        identity = _text(row["neuron_id"], "neuron identity")
        _need(identity not in neurons, "duplicate neuron identity")
        _need(row["variant"] in VARIANTS, "unknown GCaMP8 variant")
        samples = row["sample_ids"]
        _need(type(samples) is list and len(samples) > 0,
              "complete ordered prepared sample identities required")
        for sample in samples:
            _text(sample, "sample identity")
        _need(len(set(samples)) == len(samples), "duplicate prepared sample identity")
        neurons[identity] = row
    _need({n["variant"] for n in rows} == set(VARIANTS), "all three variants required")
    eligibility = manifest["eligibility"]
    _need(type(eligibility) is list, "explicit complete method/neuron eligibility required")
    policies = {}
    for row in eligibility:
        _keys(row, {"method", "neuron_id", "status", "reason", "source_sha256", "valid_mask",
                    "output_units"}, "eligibility")
        _need(type(row["method"]) is str and row["method"] in METHODS and
              type(row["neuron_id"]) is str and row["neuron_id"] in neurons,
              "unknown method/neuron eligibility")
        key = (row["method"], row["neuron_id"])
        _need(key not in policies, "duplicate method/neuron eligibility")
        _digest(row["source_sha256"], "eligibility source identity")
        _text(row["output_units"], "method output units")
        _need(row["status"] in ("evaluate", "source_excluded"), "explicit eligibility status required")
        if row["status"] == "evaluate":
            _need(row["reason"] is None, "evaluated row cannot carry an exclusion reason")
            mask = row["valid_mask"]
            _need(type(mask) is list and len(mask) == len(neurons[row["neuron_id"]]["sample_ids"]) and
                  all(type(v) is bool for v in mask), "fixed per-method boolean support required")
        else:
            _text(row["reason"], "source exclusion reason")
            _need(row["valid_mask"] is None, "excluded row must have an explicit null support")
        policies[key] = row
    _need(set(policies) == {(m, n) for m in METHODS for n in neurons},
          "complete eight-method neuron eligibility panel required")
    return neurons, policies


def _packet(packet, neuron, mask, label):
    _keys(packet, {"sample_ids", "values"}, label)
    _need(packet["sample_ids"] == neuron["sample_ids"], label + ": sample identity/order differs")
    values = packet["values"]
    _need(type(values) is list and len(values) == len(neuron["sample_ids"]),
          label + ": complete prepared vector required")
    normalized = []
    for value, selected in zip(values, mask):
        if value is None:
            _need(not selected, label + ": missing value on fixed support")
            normalized.append(float("nan"))
        else:
            _need(type(value) in (int, float) and math.isfinite(value),
                  label + ": finite real value or off-support null required")
            normalized.append(value)
    return normalized


def _primary(metric, prediction, target, mask):
    """Source Pearson only: raw fluorescence and spike rates need not share units.

    Reuse the pinned scorer's exact vector/support validation. Its Gaussian
    error and bias diagnostics require commensurate rate units and must not be
    applied to the raw-fluorescence comparator in this family.
    """
    pred, truth, support = metric._inputs(prediction, target, mask)
    result = {"pearson": None, "pearson_reason": None,
              "samples_total": int(support.size), "samples_scored": int(pred.size),
              "support_sha256": hashlib.sha256(support.tobytes()).hexdigest(),
              "extra_smoothing": False, "lag_search": False, "prediction_clipping": False}
    if pred.size == 0:
        result["pearson_reason"] = "no_valid_samples"
    elif pred.size < 2:
        result["pearson_reason"] = "fewer_than_two_samples"
    elif metric.np.ptp(truth) == 0:
        result["pearson_reason"] = "constant_target"
    elif metric.np.ptp(pred) == 0:
        result["pearson_reason"] = "constant_prediction"
    else:
        with metric.np.errstate(over="raise", invalid="raise", divide="raise"):
            correlation = float(metric.np.corrcoef(truth, pred)[0, 1])
        _need(math.isfinite(correlation) and -1 <= correlation <= 1, "invalid computed Pearson")
        result["pearson"] = correlation
    return result


def assemble_family(manifest, targets, predictions):
    """Recompute all24 method/variant vectors on operator-owned prepared support.

    Mapping order cannot create correspondence: neuron IDs join records and
    sample IDs must match the fixed order exactly. No aggregate or win is made.
    Source exclusions are an explicit operator policy, never prediction-derived.
    """
    neurons, policies = _manifest(manifest)
    _need(type(targets) is dict and set(targets) == set(neurons),
          "targets must cover the complete explicit neuron roster")
    _need(type(predictions) is dict and set(predictions) == set(METHODS),
          "all eight named method prediction mappings required")
    # Validate targets wherever ANY declared method evaluates them. This union
    # is only a missing-value check: it is never substituted as scoring support.
    truth = {}
    for identity, neuron in neurons.items():
        masks = [policies[method, identity]["valid_mask"] for method in METHODS
                 if policies[method, identity]["status"] == "evaluate"]
        required = [any(mask[i] for mask in masks) for i in range(len(neuron["sample_ids"]))]
        truth[identity] = _packet(targets[identity], neuron, required, "target " + identity)
    for method in METHODS:
        expected = {n for n in neurons if policies[method, n]["status"] == "evaluate"}
        _need(type(predictions[method]) is dict and set(predictions[method]) == expected,
              method + ": prediction identities do not equal frozen eligible support")
    metric = _metrics()
    condition = manifest["condition"]
    members = []
    for method in METHODS:
        for variant in VARIANTS:
            records = []
            for identity, neuron in neurons.items():
                if neuron["variant"] != variant:
                    continue
                policy = policies[method, identity]
                record = {"neuron_id": identity, "eligibility": policy["status"],
                          "exclusion_reason": policy["reason"],
                          "output_units": policy["output_units"],
                          "eligibility_source_sha256": policy["source_sha256"], "metrics": None}
                if policy["status"] == "evaluate":
                    prediction = _packet(predictions[method][identity], neuron, policy["valid_mask"],
                                         "prediction " + method + "/" + identity)
                    record["metrics"] = _primary(metric, prediction, truth[identity], policy["valid_mask"])
                records.append(record)
            members.append({"manifest_key": f"figure1e/{method}/{variant}/pearson_per_neuron",
                            "method": method, "variant": variant, "records": records})
    return {"schema": "gcamp8-figure1e-prepared-rate-family/v1", "task_id": TASK,
            "source_manifest_sha256": manifest["source_manifest_sha256"],
            "condition": dict(condition), "metric_source_sha256": METRIC_SHA256,
            "libraries": {"numpy": metric.np.__version__, "scipy": metric.scipy.__version__},
            "members": members, "aggregate": None, "paper_win": None,
            "source_authenticity_established": False,
            "original_cohort_equivalence_established": False,
            "scientific_qualification_added": False,
            "scope": "Prepared-rate Figure1e arithmetic only; Figure1g and historical preprocessing/model provenance unresolved."}
