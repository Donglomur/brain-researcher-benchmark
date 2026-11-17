"""Complete-supplied-output scoring, with protected targets loaded last.

No file loader, model, provider, key or source dataset is imported by this module.
The production caller must first establish operator authority/process closure.
"""
import math
from .strict import need, digest
from .programme import CONFIGS, REGIMES, ACTORS
from .units import require_hz


def finite_prediction(value, shape):
    import numpy as np
    need(isinstance(value, np.ndarray) and value.dtype.kind == "f" and
         value.dtype.itemsize in (4, 8) and value.shape == tuple(shape) and
         value.flags.c_contiguous, "prediction", "Exact finite C-order floating prediction required")
    need(np.isfinite(value).all(), "prediction", "Every prediction value must be finite")
    return value.astype(np.float64, copy=False)


def configuration_risk(prediction, target, familiarity, support=None):
    """Equal original rows within familiarity, then equal cell/time dimensions.

    This reducer is generic for invented engineering tests. Production coverage
    and real source-defined support are checked by grade_complete below.
    """
    import numpy as np
    need(isinstance(target, np.ndarray) and target.ndim in (2, 3), "target", "Response target shape required")
    p = finite_prediction(prediction, target.shape)
    t = np.asarray(target, dtype=np.float64)
    f = np.asarray(familiarity)
    need(f.shape == (len(t),) and f.dtype.kind in "biu" and set(f.tolist()) == {0, 1},
         "support", "Both complete familiarity strata required")
    mask = np.ones(t.shape, dtype=bool) if support is None else np.asarray(support)
    need(mask.shape == t.shape and mask.dtype == np.dtype(bool) and np.isfinite(t[mask]).all(),
         "target", "Fixed valid target support required")
    risks = []
    for stratum in (0, 1):
        part = f == stratum
        counts = mask[part].sum(axis=0)
        need((counts > 0).all(), "unscorable", "A required output lacks source support in a stratum")
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                difference = np.subtract(p[part], t[part], where=mask[part], out=np.zeros_like(p[part]))
                squared = np.multiply(difference, difference)
                mean = squared.sum(axis=0, dtype=np.float64) / counts
        except FloatingPointError as error:
            raise ValueError("Unsupported risk arithmetic; no clipped or partial score") from error
        need(np.isfinite(mean).all(), "unscorable", "Finite complete risk required")
        risks.append(float(math.fsum(float(x) for x in mean.flat) / mean.size))
    return {"risk": math.fsum(risks) / 2, "unfamiliar_risk": risks[0], "familiar_risk": risks[1],
            "rows": len(t), "source_defined_values": int(mask.sum()), "source_undefined_values": int(mask.size-mask.sum())}


def biological_risk(case_risks):
    need(type(case_risks) is dict and set(case_risks) == set(CONFIGS), "coverage", "All fourteen case risks required")
    people = {}
    pooled = {}
    for name, (animal, _, _) in CONFIGS.items():
        value = case_risks[name]
        need(type(value) in (float, int) and type(value) is not bool and math.isfinite(value) and value >= 0,
             "metric", "Every original case requires a nonnegative finite risk")
        if animal == "pooled":
            pooled[name] = float(value)
        else:
            people.setdefault(animal, []).append(float(value))
    need(set(people) == set("ABCDE"), "coverage", "All five animals required")
    means = {a: math.fsum(v)/len(v) for a, v in sorted(people.items())}
    return {"risk": math.fsum(means.values())/5, "animals": means, "pooled_diagnostics": pooled}


def prediction_keys(controls=range(-1, 20)):
    return {(a, r, f, c, k) for a in ACTORS for r in REGIMES for f in range(6)
            for c in controls for k in CONFIGS}


def validate_prediction_bundle(bundle, expected):
    """Validate all values/IDs/shapes before any protected target callback."""
    need(type(bundle) is dict and type(expected) is dict and set(bundle) == set(expected),
         "coverage", "Exact complete candidate and reference prediction bundle required")
    out = {}
    for key in sorted(expected):
        record, spec = bundle[key], expected[key]
        need(type(spec) is dict and set(spec) == {"row_ids", "time_shape", "static_shape", "model_digest", "fit_receipt_digest", "response_units"},
             "schema", "Exact independently admitted prediction schema required")
        from .strict import sha
        sha(spec["model_digest"]); sha(spec["fit_receipt_digest"])
        require_hz(spec["response_units"])
        need(type(record) is dict and set(record) == {"row_ids", "time", "static", "model_digest", "fit_receipt_digest", "response_units"},
             "prediction", "Exact prediction record fields required")
        need(type(record["row_ids"]) is list and record["row_ids"] == spec["row_ids"]
             and len(set(record["row_ids"])) == len(record["row_ids"]), "identity", "Exact opaque query order required")
        need(record["model_digest"] == spec["model_digest"] and record["fit_receipt_digest"] == spec["fit_receipt_digest"],
             "seal", "Prediction does not bind the independently closed frozen fit")
        need(record["response_units"] == spec["response_units"], "units", "Prediction units/provenance differ from its source/fit")
        out[key] = {"row_ids": list(record["row_ids"]),
                    "time": finite_prediction(record["time"], spec["time_shape"]),
                    "static": finite_prediction(record["static"], spec["static_shape"]),
                    "response_units":spec["response_units"]}
    return out


def prediction_bundle_digest(bundle, expected):
    from .native_scoring import array_digest
    return digest([{"key": list(k), "spec": expected[k], "time": array_digest(bundle[k]["time"]),
                    "static": array_digest(bundle[k]["static"])} for k in sorted(expected)])


def expected_prediction_digest(expected):
    return digest([{"key": list(k), "spec": expected[k]} for k in sorted(expected)])


def repeat_diagnostics(prediction, target, familiarity, repeat_role, support):
    """Mandatory low/high-repeat unfamiliar diagnostics, separate from main risk."""
    import numpy as np
    role = np.asarray(repeat_role)
    fam = np.asarray(familiarity)
    need(role.shape == fam.shape and role.dtype.kind == "U" and set(role.tolist()) <= {"standard", "low", "high"},
         "target", "Exact original repeat roles required")
    out = {}
    for label in sorted(set(role.tolist())):
        if not np.any((fam == 0) & (role == label)):
            continue
        selection = ((fam == 0) & (role == label)) | (fam == 1)
        risk = configuration_risk(prediction[selection], target[selection], fam[selection], support[selection])
        out[label] = {"unfamiliar_risk": risk["unfamiliar_risk"], "familiar_comparator_risk": risk["familiar_risk"],
                      "unfamiliar_rows": int(np.sum((fam == 0) & (role == label))),
                      "familiar_rows": int(np.sum(fam == 1))}
    return out


def grade_complete(bundle, expected, load_targets, *, independent_closure, controls=range(-1, 20)):
    """Whole-study protected grading; partial completion never loads targets.

    Controls are fixed to all twenty in production. The private lower-level
    reducers can be tested on invented arrays without a scientific run.
    """
    import numpy as np
    need(list(controls) == list(range(-1, 20)), "coverage", "Observed and all twenty null conditions required")
    need(set(expected) == prediction_keys(controls), "coverage", "All actors/regimes/folds/controls/configurations required")
    validated = validate_prediction_bundle(bundle, expected)
    need(type(independent_closure) is dict and independent_closure.get("natural_complete") is True
         and independent_closure.get("all_descendants_closed") is True
         and independent_closure.get("resources_passed") is True
         and independent_closure.get("expected_bundle_digest") == expected_prediction_digest(expected)
         and independent_closure.get("prediction_bundle_digest") == prediction_bundle_digest(bundle, expected),
         "closure", "Independent complete process/resource closure required before targets")
    need(callable(load_targets), "authority", "Trusted protected-target callback required")
    targets = load_targets()  # The first and only protected-target callback.
    need(type(targets) is dict and set(targets) == {(r, f, k) for r in REGIMES for f in range(6) for k in CONFIGS},
         "target", "Complete protected target universe required")
    output = {}
    for regime in REGIMES:
        for control in controls:
            summaries = {}
            for actor in ACTORS:
                case_time, case_static, repeat_details, support_details = {}, {}, {}, {}
                for case in CONFIGS:
                    records = [validated[(actor, regime, f, control, case)] for f in range(6)]
                    truths = [targets[(regime, f, case)] for f in range(6)]
                    all_ids = [i for row in records for i in row["row_ids"]]
                    need(len(set(all_ids)) == len(all_ids), "identity", "A face row was queried in multiple outer folds")
                    expected_count = 1036 if CONFIGS[case][2] == 2 else 1080
                    need(len(all_ids) == expected_count, "coverage", "Full original face count required")
                    for record, truth in zip(records, truths):
                        need(type(truth) is dict and set(truth) == {"row_ids", "familiarity", "repeat_role", "time", "static", "time_support", "static_support", "response_units"},
                             "target", "Complete exact private target fields required")
                        need(truth["row_ids"] == record["row_ids"], "identity", "Private target/order mismatch")
                        require_hz(truth["response_units"])
                        need(truth["response_units"] == record["response_units"], "units", "Protected target and fit/prediction unit join differs")
                    fam = np.concatenate([x["familiarity"] for x in truths])
                    repeat = np.concatenate([x["repeat_role"] for x in truths])
                    need(int(np.sum(fam == 1)) == 36, "coverage", "All original familiar rows required")
                    expected_roles = {"standard": 1036} if CONFIGS[case][2] == 2 else {"low": 1008, "high": 72}
                    need({str(x): int(np.sum(repeat == x)) for x in set(repeat.tolist())} == expected_roles,
                         "coverage", "Complete original repeat partitions required")
                    for kind, destination in (("time", case_time), ("static", case_static)):
                        prediction = np.concatenate([x[kind] for x in records], axis=0)
                        target = np.concatenate([x[kind] for x in truths], axis=0)
                        support = np.concatenate([x[kind+"_support"] for x in truths], axis=0)
                        detail = configuration_risk(prediction, target, fam, support)
                        destination[case] = detail["risk"]
                        support_details[f"{case}/{kind}"] = detail
                        repeat_details[f"{case}/{kind}"] = repeat_diagnostics(prediction, target, fam, repeat, support)
                summaries[actor] = {"time": biological_risk(case_time), "static": biological_risk(case_static),
                                    "case_time": case_time, "case_static": case_static,
                                    "repeat_diagnostics": repeat_details, "source_support": support_details}
            reference = summaries["reference"]["time"]["risk"]
            comparisons = {}
            for actor in ("A", "B"):
                candidate = summaries[actor]["time"]["risk"]
                comparisons[actor] = {"gain_Hz2": reference-candidate,
                                      "relative_skill": None if reference == 0 else 1-candidate/reference,
                                      "relative_skill_state": "undefined_zero_reference" if reference == 0 else "defined",
                                      "paired_animals": {a: summaries["reference"]["time"]["animals"][a]-summaries[actor]["time"]["animals"][a] for a in "ABCDE"}}
            output[f"{regime}/{control}"] = {"actors": summaries, "comparisons": comparisons}
    return {"status": "complete", "primary": output["calibrated_held_face/-1"]["comparisons"],
            "conditions": output, "new_canonical_ids": 0, "scientific_success_reward": None,
            "qualification_claim": False, "population_inference": "Five actual animals; no naive row/window confidence interval"}


def grade_study(predictions, expected_predictions, reproduction, protected_loader, *, expected_native_schemas, independent_closure):
    """Single protected loader after every candidate/reference artifact is checked.

    A trusted operator must already have admitted authority and independently
    closed every job. This pure scoring function is not an authorization entry.
    """
    from .native_scoring import validate_native_bundle, grade_native, native_schemas_digest
    need(set(expected_predictions) == prediction_keys(), "coverage", "Whole prediction study required")
    validate_prediction_bundle(predictions, expected_predictions)
    prediction_hash = prediction_bundle_digest(predictions, expected_predictions)
    native_hash = validate_native_bundle(reproduction, expected_native_schemas)
    need(type(independent_closure) is dict and independent_closure.get("natural_complete") is True
         and independent_closure.get("all_descendants_closed") is True
         and independent_closure.get("resources_passed") is True
         and independent_closure.get("prediction_bundle_digest") == prediction_hash
         and independent_closure.get("native_bundle_digest") == native_hash
         and independent_closure.get("native_schema_digest") == native_schemas_digest(expected_native_schemas)
         and independent_closure.get("expected_bundle_digest") == expected_prediction_digest(expected_predictions),
         "closure", "Exact complete immutable outputs and independent process closure required")
    need(callable(protected_loader), "authority", "Protected operator loader required")
    protected = protected_loader()  # Exactly one real protected-reader invocation.
    need(type(protected) is dict and set(protected) == {"prediction", "reproduction"}, "target", "Both complete protected tracks required")
    native = grade_native(reproduction, protected["reproduction"])
    prediction = grade_complete(predictions, expected_predictions, lambda: protected["prediction"],
                                independent_closure=independent_closure)
    return {"status": "complete", "prediction": prediction, "reproduction": native,
            "protected_reader_calls": 1, "new_canonical_ids": 0, "qualification_claim": False}
