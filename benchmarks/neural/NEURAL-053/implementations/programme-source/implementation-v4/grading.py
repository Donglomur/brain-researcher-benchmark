"""Full-support panel admission before protected answer access; paired metrics.

Array controls are permitted only with an explicit engineering profile. This
module neither creates target files nor grants scientific execution authority.
"""
import itertools
import hashlib
from cohort import CANONICAL, ARMS, MODES, require, canonical_profile
from io_support import object_digest, admit_full_run
from selection import ReferenceSelection, admit_reference_selection

FAMILIES = ("ridge", "lda", "fourier_ridge", "centroid")


def array_digest(values):
    """Canonical shape/dtype/content binding; ordinary artifact pins are additional."""
    import numpy as np
    digest = hashlib.sha256()
    digest.update(object_digest({"shape": list(values.shape), "dtype": values.dtype.str}).encode())
    for start in range(0, len(values), 128):
        digest.update(np.ascontiguousarray(values[start:start + 128]).tobytes())
    return digest.hexdigest()


def required_case_keys():
    candidates = [(mode, rep, fold, arm) for mode in MODES for rep in range(3)
                  for fold in range(4) for arm in ARMS]
    references = [("independent_reference", family, fold, arm) for family in FAMILIES
                  for fold in range(4) for arm in ARMS]
    return tuple(candidates + references)


def probability_check(values, rows, classes):
    import numpy as np
    require(isinstance(values, np.ndarray) and values.shape == (rows, classes) and
            values.dtype.kind == "f" and values.dtype.itemsize in (4, 8),
            "Exact complete float32/64 probability matrix")
    for start in range(0, rows, 128):
        block = values[start:start + 128].astype(np.float64)
        require(np.isfinite(block).all() and (block >= 0).all() and (block <= 1).all(),
                "Finite probabilities in [0,1]")
        require((abs(block.sum(axis=1) - 1) <= 1e-6).all(), "Exact stored row sums, no repair")


def validate_complete_panels(records, query_descriptors, approved_method_digests,
                             reference_selection, approved_execution_digests, profile=CANONICAL):
    required = set(required_case_keys())
    require(set(records) == required and set(query_descriptors) == required,
            "All96 candidate and64 reference matrices; no partial promotion")
    require(type(reference_selection) is ReferenceSelection, "Immutable authenticated pre-query reference selection")
    selected_references = reference_selection.families
    require(set(selected_references) == {(f, a) for f in range(4) for a in ARMS},
            "All16 training-selected primary reference families")
    require(all(value in FAMILIES[:3] for value in selected_references.values()),
            "Primary reference selected among three competent-family candidates")
    require(isinstance(approved_method_digests, frozenset), "Operator-approved method receipts")
    require(isinstance(approved_execution_digests, frozenset), "Independently observed completed executions")
    for key in required_case_keys():
        record, expected = records[key], query_descriptors[key]
        require(record["method_admission_digest"] in approved_method_digests,
                "Exact independent method admission before grading")
        require(record["context_key"] == list(key), "No case/mode/family substitution")
        require(expected["classes"] == list(range(1, profile.classes + 1)) and
                len(expected["query_ids"]) == profile.query_rows and
                len(set(expected["query_ids"])) == profile.query_rows, "Complete expected query/class support")
        require(record["query_ids"] == expected["query_ids"] and
                record["classes"] == expected["classes"] and
                record["query_descriptor_digest"] == object_digest(expected),
                "Exact ordered opaque query/class identity")
        require(record["reference_selection_digest"] == reference_selection.digest,
                "Actual observed output joins independently admitted pre-query training selection")
        probability_check(record["probabilities"], profile.query_rows, profile.classes)
        output_digest = array_digest(record["probabilities"])
        execution = record["execution_receipt"]
        require(object_digest(execution) in approved_execution_digests and
                execution.get("schema") == "neural053_prediction_execution_v1" and
                execution.get("context_key") == list(key) and
                execution.get("method_admission_digest") == record["method_admission_digest"] and
                execution.get("query_descriptor_digest") == record["query_descriptor_digest"] and
                execution.get("reference_selection_digest") == reference_selection.digest and
                execution.get("probabilities_digest") == output_digest and
                type(execution.get("natural_exit_code")) is int and execution["natural_exit_code"] == 0 and
                execution.get("source_state_unchanged") is True,
                "Exact independently admitted natural completion/output/state lineage")
    return True


def case_metrics(probabilities, labels, profile=CANONICAL):
    import numpy as np
    labels = np.asarray(labels)
    require(labels.shape == (profile.query_rows,) and labels.dtype.kind in "iu" and
            (labels >= 1).all() and (labels <= profile.classes).all() and
            np.array_equal(np.bincount(labels.astype(np.int64), minlength=profile.classes + 1),
                           np.r_[0, np.full(profile.classes, 2)]),
            "Exact protected two-query-image support for every class")
    correct = np.zeros(profile.classes, np.int64)
    top5 = np.zeros(profile.classes, np.int64)
    loss = np.zeros(profile.classes, np.float64)
    for start in range(0, len(labels), 128):
        p = probabilities[start:start + 128].astype(np.float64)
        y = labels[start:start + 128].astype(np.int64) - 1
        # Stable descending sort resolves ties toward lower canonical class ID.
        rank = np.argsort(-p, axis=1, kind="stable")
        first = rank[:, 0] == y
        five = (rank[:, :min(5, profile.classes)] == y[:, None]).any(axis=1)
        true_p = p[np.arange(len(y)), y]
        with np.errstate(divide="ignore"):
            logloss = -np.log(true_p)
        np.add.at(correct, y, first)
        np.add.at(top5, y, five)
        np.add.at(loss, y, logloss)
    return {"top1": float(np.mean(correct / 2)), "top5": float(np.mean(top5 / 2)),
            "log_loss": float(np.mean(loss / 2)), "classes": profile.classes,
            "query_rows": profile.query_rows}


def paired_person_interval(values):
    import numpy as np
    require(len(values) == 4 and np.isfinite(values).all(), "Four finite paired-person differences")
    resamples = [sum(values[i] for i in choice) / 4 for choice in itertools.product(range(4), repeat=4)]
    limits = np.quantile(np.asarray(resamples), [.025, .975], method="linear")
    return {"low": float(limits[0]), "high": float(limits[1]), "resamples": 256,
            "interpretation": "descriptive paired-person resampling; four biological people"}


def json_metric(value):
    import math
    if isinstance(value, float) and math.isinf(value):
        return {"state": "positive_infinity" if value > 0 else "negative_infinity"}
    if isinstance(value, dict):
        return {str(k): json_metric(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_metric(v) for v in value]
    return value


def grade_admitted_arrays(records, query_descriptors, approved_method_digests,
                          reference_selection, approved_execution_digests,
                          targets_loader, profile=CANONICAL):
    """Trusted grader primitive; loader is called only after all160 admissions.

    targets_loader receives only the exact protected support descriptors and
    returns a context-keyed target mapping. Real target custody/isolation must be
    independently qualified; no loader or real answers are supplied here.
    """
    import numpy as np
    validate_complete_panels(records, query_descriptors, approved_method_digests,
                             reference_selection, approved_execution_digests, profile)
    selected_references = reference_selection.families
    targets = targets_loader(query_descriptors)
    require(set(targets) == set(required_case_keys()), "Complete protected target support")
    metrics = {key: case_metrics(records[key]["probabilities"], targets[key], profile)
               for key in required_case_keys()}
    primary, contrasts = [], []
    for mode in MODES:
        rep_scores = []
        for rep in range(3):
            person = [metrics[mode, rep, f, "neural"]["top1"] for f in range(4)]
            rep_scores.append(sum(person) / 4)
            primary.append({"mode": mode, "replication": rep, "people": person,
                            "equal_person_class_balanced_neural_top1": sum(person) / 4})
            for label, left, right in [("neural_minus_ocular", "neural", "ocular"),
                                       ("joint_minus_ocular", "joint", "ocular"),
                                       ("neural_minus_availability", "neural", "neural_availability")]:
                differences = [metrics[mode, rep, f, left]["top1"] -
                               metrics[mode, rep, f, right]["top1"] for f in range(4)]
                contrasts.append({"mode": mode, "replication": rep, "contrast": label,
                                  "person_differences": differences, "mean": sum(differences) / 4,
                                  "interval": paired_person_interval(differences), "causal": False})
            differences = [metrics[mode, rep, f, "neural"]["top1"] -
                           metrics["independent_reference", selected_references[f, "neural"], f, "neural"]["top1"]
                           for f in range(4)]
            contrasts.append({"mode": mode, "replication": rep, "contrast": "candidate_minus_training_selected_reference",
                              "person_differences": differences, "mean": sum(differences) / 4,
                              "interval": paired_person_interval(differences)})
        primary.append({"mode": mode, "three_replication_mean": sum(rep_scores) / 3,
                        "replication_scores": rep_scores})
    for rep in range(3):
        differences = [metrics["training_investigation", rep, f, "neural"]["top1"] -
                       metrics["fixed_program", rep, f, "neural"]["top1"] for f in range(4)]
        contrasts.append({"replication": rep, "contrast": "training_investigation_minus_fixed_program",
                          "person_differences": differences, "mean": sum(differences) / 4,
                          "interval": paired_person_interval(differences)})
    # A qualified readonly namespace is still required. Rechecking content catches
    # a changed mapped output before any result is returned; it does not claim a
    # universal defense against a malicious filesystem racing individual reads.
    for key in required_case_keys():
        require(array_digest(records[key]["probabilities"]) ==
                records[key]["execution_receipt"]["probabilities_digest"],
                "Prediction artifact changed after full admission")
    prior_value = float(np.float32(1 / profile.classes))
    priors = {"uniform": {"top1": 1 / profile.classes, "top5": min(5, profile.classes) / profile.classes,
                           "log_loss": float(-np.log(prior_value)), "stored_float32_probability": prior_value},
              "training_frequency": {"same_metrics_as": "uniform",
                  "basis": "Complete30-per-class training support; independently computed count/vector evidence retained in each reference case"},
              "metric_basis": "Closed-form after complete equal two-query-images/class support admission; lower-class tie rule",
              "additional_fitted_models": 0}
    return json_metric({"schema": "neural053_full_panel_metrics_v1", "primary": primary,
                        "cases": [{"context": list(key), **value} for key, value in metrics.items()],
                        "contrasts": contrasts, "unfitted_prior_controls": priors, "biological_people": 4,
                        "engineering_profile": profile.engineering,
                        "scientific_qualification_conferred": False,
                        "raw_waveform_or_unseen_label_claim": False})


def grade_full_run(records_loader, query_descriptors, approved_method_digests,
                   selection_pin, program_pin, approved_execution_digests, targets_loader, permit, expected_bindings,
                   approved_receipts, budget):
    # No caller-selected engineering profile or absent-receipt production bypass.
    admit_full_run(permit, expected_bindings, approved_receipts, "grade_all")
    require(expected_bindings.get("reference_program_output_sha256") == program_pin["sha256"],
            "Actual reference-program output matches approved training upstream")
    selection = admit_reference_selection(selection_pin, program_pin,
                                           expected_bindings["reference_selection_sha256"], budget)
    require(expected_bindings.get("query_descriptors") == object_digest(
        [{"key": list(k), "descriptor": query_descriptors[k]} for k in required_case_keys()]),
        "Full protected support binding")
    budget.check_clock()
    records = records_loader()
    result = grade_admitted_arrays(records, query_descriptors, approved_method_digests,
                                   selection, approved_execution_digests, targets_loader, CANONICAL)
    budget.check_clock()
    return result
