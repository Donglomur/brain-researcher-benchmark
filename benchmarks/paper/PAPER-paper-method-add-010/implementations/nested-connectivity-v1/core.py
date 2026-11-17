"""Prospective nested participant selection over an explicitly supplied FC domain.

This is an operator-side reference component, not a sandbox or a paper replica.
Targets never enter fit_predict_fold except for its exact outer training rows.
Scientific source identities and biological/feature provenance remain external.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import warnings

TASK_ID = "PAPER-paper-method-add-010"
MEASURES = 246


class Refusal(ValueError):
    """The declared protocol or complete supplied support is not admissible."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def digest(value):
    try:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise Refusal("Value is not finite canonical JSON") from exc
    return hashlib.sha256(body).hexdigest()


def keys(value, expected, context):
    require(isinstance(value, dict) and set(value) == set(expected),
            context + " has incorrect fields")


def identifier(value):
    require(isinstance(value, str) and 0 < len(value) <= 200
            and value == value.strip() and not any(ord(c) < 32 for c in value),
            "Invalid identifier")
    return value


def names(value, context, minimum=1):
    require(isinstance(value, list) and len(value) >= minimum, context + " must be a nonempty array")
    result = [identifier(x) for x in value]
    require(len(set(result)) == len(result), context + " contains duplicates")
    return result


def finite(value, context):
    require(type(value) in (int, float), context + " must be a real JSON number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise Refusal(context + " is not representable as binary64") from exc
    require(math.isfinite(result), context + " must be finite")
    require(type(value) is not int or result == value, context + " integer loses precision in binary64")
    return result


def sha(value):
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256")


def runtime_versions():
    from importlib.metadata import version
    return {"python": platform.python_version(),
            **{name: version(name) for name in ("numpy", "scipy", "scikit-learn")}}


def validate_protocol(p):
    keys(p, ("schema", "task_id", "purpose", "measure_ids", "participants",
             "participant_aliases", "endpoints", "expected_observations", "outer_folds",
             "estimator", "selection", "source_policy", "execution_limits"), "Protocol")
    require(p["schema"] == "meg_nested_protocol_v1" and p["task_id"] == TASK_ID
            and p["purpose"] == "prospective_method_evaluation", "Wrong protocol scope")
    measures = names(p["measure_ids"], "measure_ids")
    require(len(measures) == MEASURES, "Exactly 246 explicitly selected measures are required")
    participants = set(names(p["participants"], "participants", 3))
    aliases = p["participant_aliases"]
    require(isinstance(aliases, dict) and aliases, "Explicit participant aliases required")
    for alias, person in aliases.items():
        identifier(alias)
        require(identifier(person) in participants, "Unknown canonical participant")
    require(set(aliases.values()) == participants, "Every participant needs an alias")
    # A biological participant's canonical name cannot mean a different person.
    require(all(k not in participants or k == v for k, v in aliases.items()), "Canonical alias conflict")
    require(isinstance(p["endpoints"], list) and p["endpoints"], "Endpoints required")
    endpoints = {}
    for e in p["endpoints"]:
        keys(e, ("id", "classes", "region_pair", "task_relevance", "time_window"), "Endpoint")
        key = identifier(e["id"])
        require(key not in endpoints, "Duplicate endpoint")
        require(len(names(e["classes"], "classes")) == 2, "Every endpoint must declare two ordered classes")
        require(len(names(e["region_pair"], "region_pair")) == 2, "Directed region pair required")
        identifier(e["task_relevance"])
        identifier(e["time_window"])
        endpoints[key] = e
    expected = p["expected_observations"]
    require(isinstance(expected, dict) and set(expected) == set(endpoints), "Complete endpoint ledger required")
    all_ids = set()
    for endpoint, rows in expected.items():
        require(isinstance(rows, list) and rows, "Empty expected observation ledger")
        seen_people = set()
        for row in rows:
            keys(row, ("id", "participant"), "Expected observation")
            oid, person = identifier(row["id"]), identifier(row["participant"])
            require(oid not in all_ids, "Observation ID occurs more than once")
            require(person in participants, "Expected observation has unknown participant")
            all_ids.add(oid)
            seen_people.add(person)
        require(seen_people == participants, "Every endpoint must cover every declared participant")
    require(isinstance(p["outer_folds"], list) and len(p["outer_folds"]) >= 2, "Outer folds required")
    fold_ids, outer_seen = set(), set()
    for fold in p["outer_folds"]:
        keys(fold, ("id", "test_participants", "inner_validation_participants"), "Outer fold")
        fid = identifier(fold["id"])
        require(fid not in fold_ids, "Duplicate outer fold")
        fold_ids.add(fid)
        test = set(names(fold["test_participants"], "test_participants"))
        require(test <= participants and not test & outer_seen, "Outer test membership is invalid or repeated")
        outer_seen |= test
        train = participants - test
        require(len(train) >= 2, "Outer training needs at least two participants")
        inner = fold["inner_validation_participants"]
        require(isinstance(inner, list) and len(inner) >= 2, "Inner participant folds required")
        inner_seen = set()
        for values in inner:
            validation = set(names(values, "inner validation participants"))
            require(validation < train and not validation & inner_seen,
                    "Inner validation must partition outer training, without outer test participants")
            inner_seen |= validation
        require(inner_seen == train, "Inner validation omits outer-training participants")
    require(outer_seen == participants, "Outer test folds do not cover every participant once")
    e = p["estimator"]
    keys(e, ("family", "normalization", "C", "seed", "tol", "max_iter"), "Estimator")
    require(e["family"] == "balanced_l1_logistic" and e["normalization"] == "training_standardization",
            "Unsupported prospective estimator")
    require(isinstance(e["C"], list) and e["C"], "Explicit C grid required")
    cs = [finite(x, "C") for x in e["C"]]
    require(min(cs) > 0 and len(set(cs)) == len(cs), "C values must be distinct and positive")
    require(type(e["seed"]) is int and 0 <= e["seed"] < 2**32, "Invalid explicit random seed")
    require(0 < finite(e["tol"], "tol") < 1, "Tolerance must be between zero and one")
    require(type(e["max_iter"]) is int and e["max_iter"] > 0, "Positive max_iter required")
    s = p["selection"]
    keys(s, ("metric", "tie", "missing_features", "constant_features", "nonconvergence"), "Selection")
    require(s["metric"] in ("participant_mean_accuracy", "participant_mean_balanced_accuracy"),
            "Unsupported explicit metric")
    require(s["tie"] == "measure_then_C_order" and s["missing_features"] == "refuse"
            and s["constant_features"] == "balanced_intercept_only"
            and s["nonconvergence"] == "refuse", "Unsupported selection policy")
    source = p["source_policy"]
    keys(source, ("source_version", "source_manifest_sha256", "measure_domain_sha256",
                  "corrected_supplement_sha256"), "Source policy")
    require(source["source_version"] in ("generated", "zenodo:15315238"),
            "Source version is outside this canonical v1 construction; no silent v2 substitution")
    sha(source["source_manifest_sha256"])
    sha(source["measure_domain_sha256"])
    require(source["measure_domain_sha256"] == digest(measures), "Measure-domain identity differs")
    if source["corrected_supplement_sha256"] is not None:
        sha(source["corrected_supplement_sha256"])
    limits = p["execution_limits"]
    keys(limits, ("max_fit_calls", "max_ledger_records", "max_observations"), "Execution limits")
    require(all(type(v) is int and v > 0 for v in limits.values()), "Explicit positive integer execution limits required")
    return p


def validate_dataset(data, p):
    validate_protocol(p)
    keys(data, ("schema", "measure_ids", "sampling", "source_manifest_sha256", "observations"), "Feature table")
    require(data["schema"] == "meg_feature_table_v1", "Wrong feature-table schema")
    require(data["sampling"] == "label_independent_observations",
            "Known-condition averages cannot enter prospective unknown-category prediction")
    require(data["measure_ids"] == p["measure_ids"], "The full ordered measure domain must match")
    require(data["source_manifest_sha256"] == p["source_policy"]["source_manifest_sha256"],
            "Source manifest identity differs")
    expected = {r["id"]: (endpoint, r["participant"])
                for endpoint, rows in p["expected_observations"].items() for r in rows}
    rows = data["observations"]
    require(isinstance(rows, list) and len(rows) == len(expected), "Full observation support required")
    require(len(rows) <= p["execution_limits"]["max_observations"], "Workload exceeds max_observations")
    admitted = {}
    for row in rows:
        keys(row, ("id", "participant", "endpoint", "values"), "Observation")
        oid = identifier(row["id"])
        require(oid in expected and oid not in admitted, "Unexpected or duplicate observation")
        alias = row["participant"]
        require(isinstance(alias, str) and alias in p["participant_aliases"], "Unrecognized participant alias")
        person = p["participant_aliases"][alias]
        require((row["endpoint"], person) == expected[oid], "Observation endpoint or biological identity differs")
        require(isinstance(row["values"], list) and len(row["values"]) == MEASURES,
                "Complete 246-value observation required")
        values = [finite(x, "Feature") for x in row["values"]]
        admitted[oid] = {"id": oid, "participant": person, "endpoint": row["endpoint"], "values": values}
    require(set(admitted) == set(expected), "Observation support differs")
    return admitted


def preflight(data, p, fold_id=None):
    """Bound logical work/records before importing a solver or fitting any model.

    A ledger record is a candidate, inner model, outer model, inner partition,
    endpoint result, fold result, or predicted observation. This count is not an
    estimate of Python object memory, native allocations, JSON bytes, or time.
    """
    rows = validate_dataset(data, p)
    folds = p["outer_folds"] if fold_id is None else [f for f in p["outer_folds"] if f["id"] == fold_id]
    require(folds, "Unknown outer fold")
    candidates = MEASURES * len(p["estimator"]["C"])
    endpoints = len(p["endpoints"])
    fits = sum(endpoints * (candidates * len(f["inner_validation_participants"]) + 1) for f in folds)
    predicted = sum(sum(row["participant"] in set(f["test_participants"]) for row in rows.values()) for f in folds)
    records = sum(endpoints * (candidates * (1 + len(f["inner_validation_participants"]))
                              + 2 + len(f["inner_validation_participants"])) + 1 for f in folds) + predicted
    estimate = {"fit_calls": fits, "ledger_records": records, "observations": len(rows),
                "logical_counts_only": True}
    for field, cap in (("fit_calls", "max_fit_calls"), ("ledger_records", "max_ledger_records"),
                       ("observations", "max_observations")):
        require(estimate[field] <= p["execution_limits"][cap], "Workload exceeds " + cap)
    return estimate


def _labels(labels, rows, endpoints, expected):
    require(isinstance(labels, dict) and set(labels) == set(expected), "Label keys must exactly equal admitted role support")
    result = {}
    for oid in expected:
        value = labels[oid]
        classes = endpoints[rows[oid]["endpoint"]]["classes"]
        require(isinstance(value, str) and value in classes, "Invalid endpoint class")
        result[oid] = classes.index(value)
    return result


def fit_model(values, classes01, c, estimator):
    """Fit one scalar feature with class order fixed externally as 0 and 1.

    Transform parameters use training rows only. Constant training features have
    the exact balanced intercept-only solution, probability 1/2 and class 0 tie.
    """
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression

    require(values and len(values) == len(classes01) and set(classes01) == {0, 1},
            "A fit needs both classes on its training support")
    x = np.asarray([finite(v, "Training feature") for v in values], dtype=np.float64)
    magnitude = float(np.max(np.abs(x))) or 1.0
    scaled = x / magnitude
    mean = math.fsum(float(v) for v in scaled) / len(scaled)
    centered = scaled - mean
    sd = math.sqrt(math.fsum(float(v) ** 2 for v in centered) / len(centered))
    base = {"magnitude": magnitude, "mean_scaled": mean, "sd_scaled": sd,
            "constant": sd == 0.0, "coefficient": 0.0, "intercept": 0.0,
            "iterations": 0, "C": float(c), "training_rows": len(values)}
    if sd == 0.0:
        return base
    transformed = centered / sd
    require(bool(np.isfinite(transformed).all()), "Training normalization exceeded binary64 range")
    model = LogisticRegression(l1_ratio=1.0, C=float(c), solver="liblinear",
                               class_weight="balanced", random_state=estimator["seed"],
                               tol=float(estimator["tol"]), max_iter=estimator["max_iter"],
                               fit_intercept=True, intercept_scaling=1.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            model.fit(transformed.reshape(-1, 1), np.asarray(classes01, dtype=np.int64))
        except ConvergenceWarning as exc:
            raise Refusal("Logistic solver did not converge under the frozen policy") from exc
    require(model.classes_.tolist() == [0, 1], "Unexpected estimator class order")
    coefficient, intercept = float(model.coef_[0, 0]), float(model.intercept_[0])
    require(math.isfinite(coefficient) and math.isfinite(intercept), "Nonfinite fitted parameter")
    base.update(coefficient=coefficient, intercept=intercept, iterations=int(model.n_iter_[0]))
    return base


def predict_model(model, values):
    """Predict using only frozen training statistics; independent of batch peers."""
    probabilities = []
    for value in values:
        x = finite(value, "Prediction feature")
        if model["constant"] or model["coefficient"] == 0.0:
            score = model["intercept"]
        else:
            z = (x / model["magnitude"] - model["mean_scaled"]) / model["sd_scaled"]
            require(math.isfinite(z), "Prediction normalization exceeded binary64 range")
            score = model["coefficient"] * z + model["intercept"]
            require(math.isfinite(score), "Prediction logit exceeded binary64 range")
        if score >= 0:
            probability = 1.0 / (1.0 + math.exp(-score))
        else:
            exponential = math.exp(score)
            probability = exponential / (1.0 + exponential)
        probabilities.append(probability)
    return probabilities


def _summarize(rows, labels01, predicted01, ids):
    people = {}
    for oid in ids:
        person = rows[oid]["participant"]
        matrix = people.setdefault(person, [[0, 0], [0, 0]])
        matrix[labels01[oid]][predicted01[oid]] += 1
    records = []
    for person in sorted(people):
        matrix = people[person]
        n0, n1 = sum(matrix[0]), sum(matrix[1])
        recalls = [matrix[0][0] / n0 if n0 else None, matrix[1][1] / n1 if n1 else None]
        records.append({"participant": person, "confusion": matrix, "rows": n0 + n1,
                        "accuracy": (matrix[0][0] + matrix[1][1]) / (n0 + n1),
                        "class_recall": recalls,
                        "balanced_accuracy": sum(recalls) / 2 if n0 and n1 else None})
    require(records, "Empty metric support")
    correct = sum(r["confusion"][0][0] + r["confusion"][1][1] for r in records)
    count = sum(r["rows"] for r in records)
    balanced = [r["balanced_accuracy"] for r in records]
    return {"participants": records, "rows": count,
            "participant_mean_accuracy": math.fsum(r["accuracy"] for r in records) / len(records),
            "participant_mean_balanced_accuracy": math.fsum(balanced) / len(balanced) if all(x is not None for x in balanced) else None,
            "pooled_accuracy": correct / count,
            "undefined_balanced_accuracy_participants": [r["participant"] for r in records if r["balanced_accuracy"] is None]}


def fit_predict_fold(data, training_labels, p, fold_id):
    """Fit and select with only outer-training labels, then predict outer test."""
    work = preflight(data, p, fold_id)
    rows = validate_dataset(data, p)
    endpoints = {e["id"]: e for e in p["endpoints"]}
    matches = [f for f in p["outer_folds"] if f["id"] == fold_id]
    require(len(matches) == 1, "Unknown outer fold")
    fold = matches[0]
    test_people = set(fold["test_participants"])
    train_ids = sorted(oid for oid, row in rows.items() if row["participant"] not in test_people)
    labels01 = _labels(training_labels, rows, endpoints, train_ids)
    estimator, metric = p["estimator"], p["selection"]["metric"]
    endpoint_results, predictions = [], {}
    for eid in sorted(endpoints):
        eligible = sorted(oid for oid in train_ids if rows[oid]["endpoint"] == eid)
        test_ids = sorted(oid for oid, row in rows.items() if row["endpoint"] == eid and row["participant"] in test_people)
        partitions = []
        for inner_index, validation_people in enumerate(fold["inner_validation_participants"]):
            validation = set(validation_people)
            partitions.append({"inner_index": inner_index,
                               "fit_ids": [oid for oid in eligible if rows[oid]["participant"] not in validation],
                               "validation_ids": [oid for oid in eligible if rows[oid]["participant"] in validation]})
        candidates = []
        for feature, measure in enumerate(p["measure_ids"]):
            for c in estimator["C"]:
                inner_predictions, inner_models = {}, []
                for partition in partitions:
                    fit_ids, validation_ids = partition["fit_ids"], partition["validation_ids"]
                    model = fit_model([rows[oid]["values"][feature] for oid in fit_ids],
                                      [labels01[oid] for oid in fit_ids], c, estimator)
                    probs = predict_model(model, [rows[oid]["values"][feature] for oid in validation_ids])
                    inner_predictions.update({oid: int(prob > 0.5) for oid, prob in zip(validation_ids, probs)})
                    inner_models.append(model)
                require(set(inner_predictions) == set(eligible), "Incomplete inner out-of-fold predictions")
                summary = _summarize(rows, labels01, inner_predictions, eligible)
                value = summary[metric]
                require(value is not None, "Selected metric undefined for a declared validation participant")
                candidates.append({"measure": measure, "feature_index": feature, "C": float(c),
                                   "score": value, "inner_models": inner_models})
        # max is stable: exact ties retain declared measure order, then C order.
        chosen = max(candidates, key=lambda row: row["score"])
        feature = chosen["feature_index"]
        model = fit_model([rows[oid]["values"][feature] for oid in eligible],
                          [labels01[oid] for oid in eligible], chosen["C"], estimator)
        probabilities = predict_model(model, [rows[oid]["values"][feature] for oid in test_ids])
        classes = endpoints[eid]["classes"]
        for oid, probability in zip(test_ids, probabilities):
            predictions[oid] = {"predicted_class": classes[int(probability > 0.5)],
                                "probability_class1": probability}
        endpoint_results.append({"endpoint": eid, "selected_measure": chosen["measure"],
                                 "selected_C": chosen["C"], "inner_score": chosen["score"],
                                 "selection_metric": metric, "fit_ids": eligible, "test_ids": test_ids,
                                 "model": model, "inner_partitions": partitions, "candidates": candidates})
    return {"fold_id": fold_id, "protocol_sha256": digest(p), "feature_table_sha256": digest(data),
            "runtime_versions": runtime_versions(),
            "training_label_ids": train_ids, "test_participants": sorted(test_people),
            "endpoints": endpoint_results, "predictions": predictions, "workload": work,
            "outer_test_labels_available_to_fit": False,
            "physical_input_provenance_verified": False,
            "candidate_process_isolated": False, "scientific_qualification": False}


def score_predictions(data, labels, predictions, p):
    rows = validate_dataset(data, p)
    endpoints = {e["id"]: e for e in p["endpoints"]}
    labels01 = _labels(labels, rows, endpoints, rows)
    require(isinstance(predictions, dict) and set(predictions) == set(rows), "Predictions must cover every observation exactly once")
    predicted01 = {}
    for oid, prediction in predictions.items():
        keys(prediction, ("predicted_class", "probability_class1"), "Prediction")
        classes = endpoints[rows[oid]["endpoint"]]["classes"]
        probability = finite(prediction["probability_class1"], "Prediction probability")
        require(0 <= probability <= 1, "Prediction probability outside [0,1]")
        predicted = classes[int(probability > 0.5)]
        require(prediction["predicted_class"] == predicted, "Prediction class disagrees with declared 1/2 tie rule")
        predicted01[oid] = classes.index(predicted)
    result = {}
    for eid in sorted(endpoints):
        ids = sorted(oid for oid, row in rows.items() if row["endpoint"] == eid)
        result[eid] = _summarize(rows, labels01, predicted01, ids)
    return {"endpoints": result, "protocol_sha256": digest(p),
            "complete_supplied_protocol_support": True,
            "scientific_qualification": False, "whole_task_complete": False}


def run_nested(data, labels, p):
    """Operator reference convenience; holds all labels and is NOT an isolation boundary."""
    work = preflight(data, p)
    rows = validate_dataset(data, p)
    endpoints = {e["id"]: e for e in p["endpoints"]}
    _labels(labels, rows, endpoints, rows)
    folds, predictions = [], {}
    for fold in p["outer_folds"]:
        test = set(fold["test_participants"])
        training = {oid: labels[oid] for oid, row in rows.items() if row["participant"] not in test}
        fitted = fit_predict_fold(data, training, p, fold["id"])
        require(not set(predictions) & set(fitted["predictions"]), "Repeated outer prediction")
        predictions.update(fitted["predictions"])
        folds.append(fitted)
    return {"schema": "meg_nested_result_v1", "task_id": TASK_ID,
            "runtime_versions": runtime_versions(),
            "protocol_sha256": digest(p), "feature_table_sha256": digest(data),
            "workload": work,
            "folds": folds, "predictions": predictions,
            "scores": score_predictions(data, labels, predictions, p),
            "scientific_qualification": False, "whole_task_complete": False,
            "held_out_data_globally_unseen": False,
            "candidate_process_isolated": False,
            "source_time_series_to_features_verified": False,
            "corrected_supplement_join_verified": False,
            "measure_domain_matches_paper_verified": False,
            "complete_authentic_cohort_verified": False,
            "scope": "Conditional prospective nested scalar-FC classifier; not paper reconstruction or a protected candidate harness."}
