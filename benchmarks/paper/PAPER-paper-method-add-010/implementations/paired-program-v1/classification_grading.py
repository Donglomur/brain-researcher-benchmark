"""Private grading for the fixed Generic-feature classification endpoint.

This pure module performs no I/O, execution, feature production, fitting or
authentication. Its caller must authenticate the reference and binding outside
participant execution, collect both complete arms after closure, and keep these
documents outside candidate mounts. Submitted aggregate metrics are never read.

``grade_classification(arms, reference, reference_binding)`` accepts two minimal
arm objects, A and B, each exactly ``observations`` and ``probabilities_object``.
Observations have exactly id, participant, label and fold. The reference binding
has exactly input_mode, source_inventory_sha256, truth_encoding and rows. Its rows map canonical Generic
source IDs to objects containing row_key, participant, label and fold. Accepted
truth encodings are ``face_object_strings`` and ``integer_face0_object1``; their
types are strict, so booleans and numeric strings are not binary integers. The
authentic production reference uses face_object_strings; the integer option is
available only for an explicitly declared reference with literal integer truth.
The binding's source inventory hash must equal the reference's input_sha256.

The selected reference report is the unique fixed arm/orientation below in a
meg-fresh-reference-result-v1 document. Only row probabilities determine predicted
classes: p_object > 0.5 means object; equality means face. Stored reference
prediction and aggregate metrics are deliberately ignored.

Published-precision compatibility concerns the mean/SD classifier summary only.
It is not per-case equivalence, raw-feature reproduction, a statistical test,
distributional validation, AUC qualification or whole-paper reproduction.
"""

from fractions import Fraction
import math


INPUT_MODE = "generic_feature_classification_v1"
REFERENCE_ARM = "author-batch-range-logistic-reference-v1"
REFERENCE_ORIENTATION = ["Category_Selective", "Prefrontal_Cortex"]
EXPECTED_REFERENCE_MEAN = Fraction(1157, 1800)
EXPECTED_REFERENCE_VARIANCE = Fraction(28501, 3240000)
PAPER_MEAN = Fraction(643, 1000)
PAPER_SD = Fraction(47, 500)
MEAN_LOWER, MEAN_UPPER = Fraction(257, 400), Fraction(1287, 2000)
VARIANCE_LOWER = Fraction(187, 2000) ** 2
VARIANCE_UPPER = Fraction(189, 2000) ** 2
TRUTH_ENCODINGS = ("face_object_strings", "integer_face0_object1")


class ClassificationGradingError(ValueError):
    """Private collected support or reference binding is inconsistent."""


def _require(condition, message):
    if not condition:
        raise ClassificationGradingError(message)


def _fields(value, expected, name):
    _require(type(value) is dict and set(value) == set(expected),
             name + " has invalid fields")


def _name(value, name):
    _require(type(value) is str and 0 < len(value) <= 512
             and value == value.strip() and not any(ord(c) < 32 for c in value),
             name + " must be a bounded nonempty string")
    return value


def _fold(value):
    _require(type(value) is int and 0 <= value < 10,
             "fold must be an integer from zero through nine")
    return value


def _label(value):
    _require(type(value) is str and value in ("face", "object"),
             "label must be face or object")
    return value


def _probability(value):
    _require(type(value) in (int, float) and 0 <= value <= 1,
             "probability must be a real number in [0,1], not bool")
    _require(math.isfinite(value), "probability must be finite")
    return Fraction(value)


def _fraction(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def _source_id(participant, label):
    _name(participant, "participant")
    _require("|" not in participant, "participant must not contain a separator")
    _label(label)
    return (f"{participant}|{label}|Irrelevant|1000ms|on|Generic|"
            "CS-PFC|bary-sq_dtw_max")


def _observations(rows):
    _require(type(rows) is list and len(rows) == 188,
             "exactly 188 private observations are required")
    indexed, people = {}, {}
    for row in rows:
        _fields(row, ("id", "participant", "label", "fold"), "observation")
        identifier = _name(row["id"], "source ID")
        participant, label, fold = row["participant"], _label(row["label"]), _fold(row["fold"])
        _require(identifier == _source_id(participant, label),
                 "source ID is outside the fixed Generic namespace")
        _require(identifier not in indexed, "duplicate source ID")
        indexed[identifier] = dict(row)
        state = people.setdefault(participant, {"fold": fold, "labels": set()})
        _require(state["fold"] == fold, "participant crosses held-out folds")
        _require(label not in state["labels"], "participant/category repeats")
        state["labels"].add(label)
    _require(len(people) == 94 and all(p["labels"] == {"face", "object"}
                                     for p in people.values()),
             "94 complete participant face/object pairs are required")
    _require({p["fold"] for p in people.values()} == set(range(10)),
             "all ten held folds must be represented")
    return indexed


def _collected(value):
    _fields(value, ("observations", "probabilities_object"), "collected arm")
    observations = _observations(value["observations"])
    probabilities = value["probabilities_object"]
    _require(type(probabilities) is dict and set(probabilities) == set(observations),
             "probabilities must cover every and only selected source ID")
    return observations, {key: _probability(probabilities[key]) for key in observations}


def _binding(value, observations):
    _fields(value, ("input_mode", "source_inventory_sha256", "truth_encoding", "rows"),
            "reference binding")
    _require(value["input_mode"] == INPUT_MODE, "explicit Generic input mode required")
    inventory_sha256 = value["source_inventory_sha256"]
    _require(type(inventory_sha256) is str and len(inventory_sha256) == 64
             and all(char in "0123456789abcdef" for char in inventory_sha256),
             "source inventory binding must be lowercase SHA256 hex")
    encoding = value["truth_encoding"]
    _require(type(encoding) is str and encoding in TRUTH_ENCODINGS,
             "explicit supported strict truth encoding required")
    rows = value["rows"]
    _require(type(rows) is dict and set(rows) == set(observations),
             "reference binding must cover exactly selected source IDs")
    keys = set()
    for identifier, row in rows.items():
        _fields(row, ("row_key", "participant", "label", "fold"), "reference row binding")
        key = _name(row["row_key"], "reference row key")
        _require(key not in keys, "reference row keys must form a bijection")
        keys.add(key)
        _label(row["label"])
        _fold(row["fold"])
        _require(identifier == _source_id(row["participant"], row["label"]),
                 "reference source ID is outside the Generic namespace")
        _require({"id": identifier, "participant": row["participant"],
                  "label": row["label"], "fold": row["fold"]} == observations[identifier],
                 "reference binding differs from collected participant/label/fold")
    return rows, encoding


def _truth(value, encoding):
    if encoding == "face_object_strings":
        return _label(value)
    _require(type(value) is int and value in (0, 1),
             "binary reference truth must be integer zero or one, not bool/string")
    return "object" if value == 1 else "face"


def _reference_probabilities(reference, binding_rows, encoding, inventory_sha256):
    _require(type(reference) is dict
             and reference.get("schema") == "meg-fresh-reference-result-v1"
             and reference.get("status") == "success", "successful private reference document required")
    _require(reference.get("input_sha256") == inventory_sha256,
             "reference input inventory differs from explicit source binding")
    reports = reference.get("results")
    _require(type(reports) is list and all(type(r) is dict for r in reports),
             "reference results must be a list of report objects")
    selected = [r for r in reports if r.get("arm") == REFERENCE_ARM
                and r.get("orientation") == REFERENCE_ORIENTATION]
    _require(len(selected) == 1, "exactly one fixed reference arm/orientation is required")
    report = selected[0]
    _require({"arm", "orientation", "predictions", "metrics", "fits", "test_batch_access"}
             <= set(report), "selected reference report is incomplete")
    rows = report["predictions"]
    _require(type(rows) is list and len(rows) == 188, "reference must contain 188 predictions")
    by_key = {}
    for row in rows:
        _fields(row, ("row_key", "participant", "truth", "prediction", "p_object", "fold"),
                "reference prediction")
        key = _name(row["row_key"], "reference row key")
        _require(key not in by_key, "duplicate reference prediction row key")
        _name(row["participant"], "reference participant")
        _fold(row["fold"])
        by_key[key] = row
    _require(set(by_key) == {row["row_key"] for row in binding_rows.values()},
             "reference prediction support differs from explicit binding")
    probabilities = {}
    for identifier, binding in binding_rows.items():
        row = by_key[binding["row_key"]]
        _require(row["participant"] == binding["participant"]
                 and row["fold"] == binding["fold"]
                 and _truth(row["truth"], encoding) == binding["label"],
                 "reference participant/truth/fold differs from explicit binding")
        probabilities[identifier] = _probability(row["p_object"])
    return probabilities


def _score(observations, probabilities):
    """Exact counterpart of original score_cell's mean and population variance."""
    counts, correct, people, hits = [0] * 10, [0] * 10, {}, {}
    for identifier, row in observations.items():
        prediction = "object" if probabilities[identifier] > Fraction(1, 2) else "face"
        hit = int(prediction == row["label"])
        hits[identifier] = hit
        fold, participant = row["fold"], row["participant"]
        counts[fold] += 1
        correct[fold] += hit
        people[participant] = people.get(participant, 0) + hit
    accuracies = [Fraction(correct[f], counts[f]) for f in range(10)]
    mean = sum(accuracies, Fraction()) / 10
    variance = sum(((accuracy - mean) ** 2 for accuracy in accuracies), Fraction()) / 10
    return {"counts": counts, "correct": correct, "accuracies": accuracies,
            "mean": mean, "variance": variance, "people": people, "hits": hits}


def _published_precision(score):
    return (MEAN_LOWER <= score["mean"] < MEAN_UPPER
            and VARIANCE_LOWER <= score["variance"] < VARIANCE_UPPER)


def _summary(score):
    return {"mean_fold_accuracy": float(score["mean"]),
            "mean_fold_accuracy_exact": _fraction(score["mean"]),
            "population_fold_variance_exact": _fraction(score["variance"]),
            "population_fold_sd": math.sqrt(float(score["variance"])),
            "paper_mean_difference_exact": _fraction(score["mean"] - PAPER_MEAN),
            "paper_sd_difference": math.sqrt(float(score["variance"])) - float(PAPER_SD),
            "pooled_accuracy_descriptive_exact": _fraction(Fraction(sum(score["correct"]), 188))}


def _comparison(observations, probabilities, score, reference_probabilities, reference_score):
    delta = score["mean"] - reference_score["mean"]
    discrepancies = [abs(probabilities[key] - reference_probabilities[key]) for key in observations]
    max_discrepancy = max(discrepancies)
    mean_discrepancy = sum(discrepancies, Fraction()) / 188
    folds = []
    for fold in range(10):
        difference = score["accuracies"][fold] - reference_score["accuracies"][fold]
        folds.append({"fold": fold, "observations": score["counts"][fold],
            "candidate_observations": score["counts"][fold],
            "reference_observations": reference_score["counts"][fold],
            "observation_count_difference": score["counts"][fold] - reference_score["counts"][fold],
            "candidate_correct": score["correct"][fold],
            "reference_correct": reference_score["correct"][fold],
            "correct_difference": score["correct"][fold] - reference_score["correct"][fold],
            "candidate_accuracy_exact": _fraction(score["accuracies"][fold]),
            "reference_accuracy_exact": _fraction(reference_score["accuracies"][fold]),
            "accuracy_difference_exact": _fraction(difference)})
    participant_folds = {row["participant"]: row["fold"] for row in observations.values()}
    participants = []
    for participant in sorted(score["people"]):
        candidate_correct = score["people"][participant]
        reference_correct = reference_score["people"][participant]
        participants.append({"participant": participant, "fold": participant_folds[participant],
            "observations": 2, "candidate_correct": candidate_correct,
            "reference_correct": reference_correct, "correct_difference": candidate_correct - reference_correct,
            "candidate_accuracy_exact": _fraction(Fraction(candidate_correct, 2)),
            "reference_accuracy_exact": _fraction(Fraction(reference_correct, 2)),
            "accuracy_difference_exact": _fraction(Fraction(candidate_correct - reference_correct, 2))})
    return {**_summary(score),
        "valid_same_case_evaluation": True,
        "published_precision_numerical_reproduction": _published_precision(score),
        "reference_score_exceeded": delta > 0,
        "scientific_superiority_established": None,
        "candidate_minus_reference_mean_exact": _fraction(delta),
        "fold_comparisons": folds, "participant_paired_effects": participants,
        "participant_effect_counts": {
            "improved": sum(row["correct_difference"] > 0 for row in participants),
            "unchanged": sum(row["correct_difference"] == 0 for row in participants),
            "worsened": sum(row["correct_difference"] < 0 for row in participants)},
        "probability_discrepancies": {
            "maximum_absolute": float(max_discrepancy), "mean_absolute": float(mean_discrepancy),
            "maximum_absolute_exact": _fraction(max_discrepancy),
            "mean_absolute_exact": _fraction(mean_discrepancy)},
        "hard_prediction_disagreements": sum(
            (probabilities[key] > Fraction(1, 2)) != (reference_probabilities[key] > Fraction(1, 2))
            for key in observations),
        "raw_feature_reproduction": None, "distributional_equivalence": None,
        "auc_qualification": None, "whole_paper_reproduction": None}


def grade_classification(arms, reference, reference_binding):
    """Grade two fully closed arms against one externally authenticated reference.

    Invalid support raises ClassificationGradingError; no partial arm evaluation
    is returned. Row sequence is irrelevant because all comparisons use the
    explicit canonical source-ID/reference-row-key bijection. Input objects are
    not modified. The published 94-person roster and original bytes are bound by
    the authenticated private reference/binding, not inferred from count alone.
    """
    _fields(arms, ("A", "B"), "collected assistance arms")
    collected = {role: _collected(arms[role]) for role in ("A", "B")}
    observations = collected["A"][0]
    _require(observations == collected["B"][0], "assistance arms must have identical private case support")
    binding_rows, encoding = _binding(reference_binding, observations)
    reference_probabilities = _reference_probabilities(reference, binding_rows, encoding,
                                                      reference_binding["source_inventory_sha256"])
    reference_score = _score(observations, reference_probabilities)
    _require(reference_score["mean"] == EXPECTED_REFERENCE_MEAN
             and reference_score["variance"] == EXPECTED_REFERENCE_VARIANCE,
             "selected reference does not reproduce the bound mean/population variance")
    scores = {role: _score(observations, collected[role][1]) for role in ("A", "B")}
    return {"schema": "meg-generic-classification-score/v1", "input_mode": INPUT_MODE,
        "source_inventory_sha256": reference_binding["source_inventory_sha256"],
        "scope": {"input_mode": INPUT_MODE, "reference_preprocessing_arm": REFERENCE_ARM,
                  "selected_input": "fixed Generic CS-PFC bary-sq_dtw_max scalar",
                  "reference_transform": "author mixed-sigmoid with held-batch range",
                  "raw_feature_extraction_assessed": False},
        "observations_per_arm": 188, "participants": 94, "folds": 10,
        "reference_selector": {"arm": REFERENCE_ARM, "orientation": list(REFERENCE_ORIENTATION)},
        "truth_encoding": encoding,
        "reference": _comparison(observations, reference_probabilities, reference_score,
                                 reference_probabilities, reference_score),
        "arms": {role: _comparison(observations, collected[role][1], scores[role],
                                   reference_probabilities, reference_score) for role in ("A", "B")},
        "B_minus_A_mean_fold_accuracy_exact": _fraction(scores["B"]["mean"] - scores["A"]["mean"]),
        "published_precision_rule": {
            "mean_lower_inclusive": _fraction(MEAN_LOWER), "mean_upper_exclusive": _fraction(MEAN_UPPER),
            "population_variance_lower_inclusive": _fraction(VARIANCE_LOWER),
            "population_variance_upper_exclusive": _fraction(VARIANCE_UPPER)},
        "interpretation": "Published-precision numerical reproduction is classifier-summary compatibility only, not per-case equivalence. Positive reference score difference is descriptive, not established scientific superiority. Raw features, distributions, AUC and whole-paper reproduction remain unassessed.",
        "external_reference_authentication_performed_here": False}
