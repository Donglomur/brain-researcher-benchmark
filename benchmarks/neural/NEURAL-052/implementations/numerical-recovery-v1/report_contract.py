"""Complete NEURAL-052 candidate-report admission, before numeric data access.

This module uses only caller-supplied DESIGN identity metadata. It neither
imports the encoding core nor opens any packet, predictions or neural arrays.
The public schema supplies exact shape/constants; relations between counts,
nulls and statuses are additionally enforced here. Values are not checked
against reference effects or fitted outputs: scientifically wrong but valid
finite answers remain admissible for numerical comparison by the grader.

API: validate_report(envelope, design) -> None; candidate faults raise the
shared interface.Invalid. Invalid operator DESIGN metadata raises ValueError.
"""
from __future__ import annotations

import hashlib
import math
import re

from interface import Invalid

SUBJECTS = ("01", "02", "03")
ROIS = ("V1", "IT")
METHODS = ("macro_primary", "unweighted_pooled", "reliability_weighted_pooled", "reliability_adjustment")
METRICS = ("animacy_given_size", "size_given_animacy", "joint")
BINS = ("[-1,0)", "[0,0.25)", "[0.25,0.5)", "[0.5,0.75)", "[0.75,1]")
BLOCKS = ([1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12])
FEATURES = ["session", "run", "within_run_position"] + [f"image_{i}" for i in range(15)] + ["animacy", "size"]
ROI_COUNTS = {"01": {"V1": 1049, "IT": 4081}, "02": {"V1": 1104, "IT": 3858}, "03": {"V1": 839, "IT": 3379}}
# Pure PCG64 schedule over 100 concepts, not an authentic-response checksum.
SCHEDULE_SHA = "a088607ec58ce1dab4e9fdc884f2fefb2b8ef39bb4bc1b02f02216e6f256fd05"


def _obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _const(value):
    return {"const": value}


def _int(lo=0, hi=1000):
    return {"type": "integer", "minimum": lo, "maximum": hi}


def _ref(name):
    return {"$ref": f"#/$defs/{name}"}


def _tuple(items):
    return {"type": "array", "prefixItems": items, "minItems": len(items), "maxItems": len(items)}


def _metrics(summary):
    return _obj({m: summary for m in METRICS})


def _design_concepts(design):
    if (type(design) is not dict or type(design.get("concept_features")) is not dict
            or len(design["concept_features"]) != 100
            or any(type(c) is not str or not c for c in design["concept_features"])
            or type(design.get("feature_names")) is not list or len(design["feature_names"]) != 15):
        raise ValueError("operator DESIGN must bind 100 concepts and 15 image features")
    subjects = design.get("subjects")
    if (type(subjects) is not list or len(subjects) != 3
            or any(type(s) is not dict for s in subjects)
            or [s.get("subject_id") for s in subjects] != list(SUBJECTS)):
        raise ValueError("operator DESIGN participant identities differ")
    return sorted(design["concept_features"])


def build_schema(design):
    """Build the public static schema using identity metadata, no scalar labels."""
    concepts = _design_concepts(design)
    order = sorted(concepts, key=lambda c: (hashlib.sha256(("52052\0" + c).encode()).digest(), c))
    folds = {c: i % 5 for i, c in enumerate(order)}
    nullable = {"type": ["number", "null"]}
    interval = _obj({
        "requested_draws": _const(1000), "defined_draws": _int(), "undefined_draws": _int(),
        "level": _const(.95), "quantile_method": _const("linear"), "lower": nullable, "upper": nullable,
        "status": {"enum": ["defined", "undefined_point_estimate", "undefined_resample_support"]}})

    def summary(undefined, diagnostic=False, group=False):
        p = {"status": {"enum": ["defined", *undefined]}, "value": nullable,
             "conditional_concept_bootstrap": _ref("interval")}
        if diagnostic:
            p["defined_voxel_mean_diagnostic"] = nullable
        if group:
            p.update(participants_total=_const(3), participants_defined=_int(0, 3))
        return _obj(p)

    defs = {"interval": interval,
            "macro": summary(["undefined_voxel_sst"], diagnostic=True),
            "pooled": summary(["undefined_zero_total_sst"]),
            "weighted": summary(["undefined_zero_total_sst", "undefined_common_reliability_bins"]),
            "difference": summary(["undefined_support"]),
            "group": summary(["undefined_participant_support"], group=True)}
    summaries = {"macro_primary": _ref("macro"), "unweighted_pooled": _ref("pooled"),
                 "reliability_weighted_pooled": _ref("weighted"), "reliability_adjustment": _ref("difference")}
    participants = []
    for sid in SUBJECTS:
        totals = ROI_COUNTS[sid]
        roi_counts = _obj({r: _int(0, totals[r]) for r in ROIS})
        reliability = _obj({
            "supported": {"type": "boolean"},
            "common_bins": {"type": "array", "items": {"enum": list(BINS)}, "uniqueItems": True, "maxItems": 5},
            "bin_counts": _obj({r: _obj({b: _int(0, totals[r]) for b in BINS}) for r in ROIS}),
            "undefined_reliability_voxels": roi_counts, "weighted_voxels": roi_counts, "zero_weight_voxels": roi_counts})
        support_rows = []
        for fold in range(5):
            for block in BLOCKS:
                support_rows.append(_obj({
                    "concept_fold": _const(fold), "heldout_sessions": _const(block),
                    "training_rows": _const(640), "query_rows": _const(80),
                    "training_concepts": _const(80), "query_concepts": _const(20),
                    "constant_training_predictors": {"type": "array", "items": {"enum": FEATURES},
                                                     "uniqueItems": True, "maxItems": len(FEATURES)},
                    "reliability": reliability}))
        participants.append(_obj({
            "subject_id": _const(sid), "rows": _const(1200), "roi_overlap_voxels": _const(0),
            "voxel_support": _obj({r: _obj({"all_voxels": _const(totals[r]),
                "positive_sst_voxels": _int(0, totals[r]), "zero_sst_voxels": _int(0, totals[r])}) for r in ROIS}),
            "roi_metrics": _obj({method: _obj({r: _metrics(summaries[method]) for r in ROIS}) for method in METHODS}),
            "it_minus_v1": _obj({method: _metrics(_ref("difference")) for method in METHODS}),
            "reliability_control_support": _obj({"all_folds_supported": {"type": "boolean"},
                "folds_total": _const(15), "folds_with_common_bins": _int(0, 15)}),
            "fold_support": _tuple(support_rows)}))
    analysis = _obj({
        "policy": _const("neural052_property_increment_draft_v1"), "strict_benchmark_panel": _const(True),
        "cohort": _const({"subject_ids": list(SUBJECTS), "concept_count": 100, "sessions": list(range(1, 13))}),
        "split": _const({"concept_seed": 52052, "concept_folds": folds, "session_blocks": list(BLOCKS),
                         "query_coverage": "each row exactly once"}),
        "model": _const({"ridge_lambda": 1.0, "intercept": "unpenalized", "predictor_scale": "training population SD",
                         "constant_scale": 1.0, "feature_order": FEATURES, "response_transformation": "training mean only"}),
        "participants": _tuple(participants),
        "group_descriptive": _obj({
            "roi_metrics": _obj({method: _obj({r: _metrics(_ref("group")) for r in ROIS}) for method in METHODS}),
            "it_minus_v1": _obj({method: _metrics(_ref("group")) for method in METHODS}),
            "weighting": _const("equal participant; no subject/ROI exclusion")}),
        "bootstrap": _const({"unit": "concept, all 12 repetitions together", "draws": 1000, "seed": 52053,
            "generator": "numpy.PCG64", "concept_order": concepts, "multiplicities_sha256": SCHEDULE_SHA,
            "refit": False, "undefined_policy": "retain; interval null if any requested draw undefined",
            "scope": "conditional fixed-prediction concept uncertainty for these participants"}),
        "estimands": _const({
            "macro_primary": "equal-voxel mean of pooled per-voxel incremental-SSE/SST ratios",
            "unweighted_pooled": "sum incremental SSE / sum SST over every ROI voxel",
            "reliability_weighted_pooled": "sum training-common-bin-weighted incremental SSE / weighted SST",
            "reliability_adjustment": "reliability-weighted pooled minus unweighted pooled; like-estimand comparison"}),
        "limits": _const([
            "new prospective analysis, not source-notebook or full-paper reproduction",
            "no cross-participant voxel matching or voxel-independent population inference",
            "training reliability is raw Pearson, not a noise ceiling; coarse shared-bin weighting is descriptive",
            "macro primary is not replaced by its defined-voxel diagnostic or by pooled-error controls",
            "semantic increments are predictive associations conditional on these descriptors, not causal semantic effects"])})
    schema = _obj({"task_id": _const("NEURAL-052"), "input_manifest_sha256": {
        "type": "string", "minLength": 64, "maxLength": 64, "pattern": "^[0-9a-f]{64}$"}, "analysis": analysis})
    schema.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": defs,
        "title": "NEURAL-052 complete protocol report",
        "$comment": "All fields required. Runtime report_contract additionally requires finite float64-representable numbers, strict JSON integer types, ordered predictor subsets, exact count partitions/common bins and support/status/null relationships. It does not validate fitted effect values. Manifest SHA is syntactic here and bound to the actual packet by the grader after complete report admission."})
    return schema


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _same(actual, expected):
    """JSON equality without Python's True == 1 loophole."""
    if type(expected) is float:
        return _finite(actual) and actual == expected
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(_same(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(_same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _shape(value, spec, defs, path):
    if "$ref" in spec:
        return _shape(value, defs[spec["$ref"].rsplit("/", 1)[1]], defs, path)
    if "const" in spec:
        if not _same(value, spec["const"]):
            raise Invalid(path + ": fixed protocol value differs")
        return
    if "enum" in spec and not any(_same(value, x) for x in spec["enum"]):
        raise Invalid(path + ": invalid status or enumerated value")
    kinds = spec.get("type", [])
    kinds = [kinds] if type(kinds) is str else kinds
    matched = {"object": type(value) is dict, "array": type(value) is list,
               "string": type(value) is str, "boolean": type(value) is bool,
               "integer": type(value) is int, "number": _finite(value), "null": value is None}
    if kinds and not any(matched[k] for k in kinds):
        raise Invalid(path + ": wrong type or nonfinite/unrepresentable number")
    if type(value) is dict:
        properties = spec.get("properties", {})
        if set(value) != set(properties):
            raise Invalid(path + ": incomplete or extra fields")
        for key, sub in properties.items():
            _shape(value[key], sub, defs, path + "/" + key)
    elif type(value) is list:
        if not spec.get("minItems", 0) <= len(value) <= spec.get("maxItems", len(value)):
            raise Invalid(path + ": wrong array length")
        if spec.get("uniqueItems") and any(value[i] == value[j] for i in range(len(value)) for j in range(i)):
            raise Invalid(path + ": duplicate member")
        for i, item in enumerate(value):
            sub = spec["prefixItems"][i] if "prefixItems" in spec else spec["items"]
            _shape(item, sub, defs, path + "/" + str(i))
    elif type(value) is str:
        if not spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", len(value)):
            raise Invalid(path + ": wrong string length")
        if "pattern" in spec and re.fullmatch(spec["pattern"], value) is None:
            raise Invalid(path + ": malformed string")
    elif type(value) in (int, float):
        if not _finite(value) or ("minimum" in spec and value < spec["minimum"]) or ("maximum" in spec and value > spec["maximum"]):
            raise Invalid(path + ": number outside allowed domain")


def _require(condition, path, reason):
    if not condition:
        raise Invalid(path + ": " + reason)


def _summary(value, path):
    defined = value["value"] is not None
    _require((value["status"] == "defined") == defined, path, "status/value availability disagree")
    ci = value["conditional_concept_bootstrap"]
    _require(ci["defined_draws"] + ci["undefined_draws"] == 1000, path, "bootstrap counts do not partition all draws")
    status = "undefined_point_estimate" if not defined else ("undefined_resample_support" if ci["undefined_draws"] else "defined")
    _require(ci["status"] == status, path, "bootstrap disposition disagrees with support")
    if status == "defined":
        _require(ci["lower"] is not None and ci["upper"] is not None and ci["lower"] <= ci["upper"], path, "finite ordered interval required")
    else:
        _require(ci["lower"] is None and ci["upper"] is None, path, "undefined interval must have two null bounds")


def _availability(value, defined, reason, path):
    _require(value["status"] == ("defined" if defined else reason), path, "reported status contradicts declared support")


def validate_report(envelope, design):
    """Admit all candidate structure before any private numeric data is loaded."""
    schema = build_schema(design)
    _shape(envelope, schema, schema["$defs"], "submission")
    a = envelope["analysis"]
    for p in a["participants"]:
        where = "analysis/participants/" + p["subject_id"]
        for r in ROIS:
            s = p["voxel_support"][r]
            _require(s["positive_sst_voxels"] + s["zero_sst_voxels"] == s["all_voxels"], where, "SST counts do not partition ROI")
        supported = 0
        for i, fold in enumerate(p["fold_support"]):
            fp = where + "/fold_support/" + str(i)
            cp = fold["constant_training_predictors"]
            _require(cp == [f for f in FEATURES if f in cp], fp, "constant predictors must retain canonical order")
            rel = fold["reliability"]
            common = [b for b in BINS if all(rel["bin_counts"][r][b] > 0 for r in ROIS)]
            _require(rel["common_bins"] == common and rel["supported"] == bool(common), fp, "common-bin support disagrees with counts")
            supported += int(rel["supported"])
            for r in ROIS:
                total = p["voxel_support"][r]["all_voxels"]
                weighted = sum(rel["bin_counts"][r][b] for b in common)
                _require(sum(rel["bin_counts"][r].values()) + rel["undefined_reliability_voxels"][r] == total, fp, "reliability counts do not partition ROI")
                _require(rel["weighted_voxels"][r] == weighted and rel["zero_weight_voxels"][r] == total - weighted, fp, "weighted support disagrees with common bins")
        control = p["reliability_control_support"]
        _require(control["folds_with_common_bins"] == supported and control["all_folds_supported"] == (supported == 15), where, "fold-control support mismatch")
        for method in METHODS:
            for r in ROIS:
                for m in METRICS:
                    s = p["roi_metrics"][method][r][m]
                    path = where + "/roi_metrics/" + method + "/" + r + "/" + m
                    _summary(s, path)
                    vs = p["voxel_support"][r]
                    if method == "macro_primary":
                        _availability(s, vs["zero_sst_voxels"] == 0, "undefined_voxel_sst", path)
                        _require((s["defined_voxel_mean_diagnostic"] is not None) == (vs["positive_sst_voxels"] > 0), path, "defined-voxel diagnostic availability mismatch")
                    elif method == "unweighted_pooled":
                        _availability(s, vs["positive_sst_voxels"] > 0, "undefined_zero_total_sst", path)
                    elif method == "reliability_weighted_pooled":
                        if supported < 15:
                            _availability(s, False, "undefined_common_reliability_bins", path)
                            _require(s["conditional_concept_bootstrap"]["defined_draws"] == 0, path, "unsupported common bins cannot have defined draws")
                        else:
                            _require(s["status"] != "undefined_common_reliability_bins", path, "common bins are supported")
                            if vs["positive_sst_voxels"] == 0:
                                _availability(s, False, "undefined_zero_total_sst", path)
                    else:
                        available = all(p["roi_metrics"][k][r][m]["value"] is not None for k in ("unweighted_pooled", "reliability_weighted_pooled"))
                        _availability(s, available, "undefined_support", path)
                    # Nonnegative SST: a zero total cannot become positive by resampling.
                    if s["status"] in ("undefined_voxel_sst", "undefined_zero_total_sst"):
                        _require(s["conditional_concept_bootstrap"]["defined_draws"] == 0, path, "zero-SST support cannot become defined by resampling")
            for m in METRICS:
                s = p["it_minus_v1"][method][m]
                path = where + "/it_minus_v1/" + method + "/" + m
                _summary(s, path)
                _availability(s, all(p["roi_metrics"][method][r][m]["value"] is not None for r in ROIS), "undefined_support", path)
        for m in METRICS:
            for r in ROIS:
                s = p["roi_metrics"]["reliability_adjustment"][r][m]
                if supported < 15:
                    _require(s["conditional_concept_bootstrap"]["defined_draws"] == 0, where, "unsupported adjustment cannot have defined draws")
    group = a["group_descriptive"]
    for method in METHODS:
        for r in (*ROIS, None):
            for m in METRICS:
                if r is None:
                    s = group["it_minus_v1"][method][m]
                    sources = [p["it_minus_v1"][method][m] for p in a["participants"]]
                    path = "analysis/group_descriptive/it_minus_v1/" + method + "/" + m
                else:
                    s = group["roi_metrics"][method][r][m]
                    sources = [p["roi_metrics"][method][r][m] for p in a["participants"]]
                    path = "analysis/group_descriptive/roi_metrics/" + method + "/" + r + "/" + m
                _summary(s, path)
                n = sum(v["value"] is not None for v in sources)
                _require(s["participants_defined"] == n, path, "participant support count mismatch")
                _availability(s, n == 3, "undefined_participant_support", path)
    return None
