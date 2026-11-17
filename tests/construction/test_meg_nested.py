"""Independent generated controls for the conditional MEG evaluation component.

The expectations were derived from the canonical information boundary, hand
computed confusion counts and algebraic invariances before inspecting core.py.
These controls establish no authentic MEG, paper or protected-execution result.
"""
import copy
import hashlib
import importlib.util
import json
import marshal
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "benchmarks/paper/PAPER-paper-method-add-010/implementations/"
          "nested-connectivity-v1/core.py")
SPEC = importlib.util.spec_from_file_location("meg_nested_independent_source", SOURCE)
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)
PACKAGE = SOURCE.parent


def load_source(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


design = load_source("meg_nested_independent_design", "design.py")
runner = load_source("meg_nested_independent_runner", "run.py")


def canonical_hash(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def generated_fixture(people_count=4):
    """One informative measure, one held-out lure and 244 constant measures."""
    measures = [f"measure-{index:03d}" for index in range(246)]
    people = [f"p{index}" for index in range(people_count)]
    expected, rows, labels = [], [], {}
    for index, person in enumerate(people):
        for category, label in enumerate(("face", "object")):
            oid = f"{person}-{category}"
            values = [0.0] * 246
            sign = -1 if category == 0 else 1
            values[0] = sign * (index + 1)
            values[1] = sign * 1000.0 if index == 3 else 0.0
            expected.append({"id": oid, "participant": person})
            rows.append({"id": oid, "participant": person, "endpoint": "vision",
                         "values": values})
            labels[oid] = label
    protocol = {
        "schema": "meg_nested_protocol_v1", "task_id": "PAPER-paper-method-add-010",
        "purpose": "prospective_method_evaluation", "measure_ids": measures,
        "participants": people, "participant_aliases": {p: p for p in people},
        "endpoints": [{"id": "vision", "classes": ["face", "object"],
                       "region_pair": ["region-a", "region-b"],
                       "task_relevance": "relevant", "time_window": "on"}],
        "expected_observations": {"vision": expected},
        "outer_folds": [{"id": "outer-" + p, "test_participants": [p],
                         "inner_validation_participants": [[q] for q in people if q != p]}
                        for p in people],
        "estimator": {"family": "balanced_l1_logistic",
                      "normalization": "training_standardization", "C": [10.0],
                      "seed": 7, "tol": 1e-8, "max_iter": 10000},
        "selection": {"metric": "participant_mean_accuracy", "tie": "measure_then_C_order",
                      "missing_features": "refuse", "constant_features": "balanced_intercept_only",
                      "nonconvergence": "refuse"},
        "execution_limits": {"max_fit_calls": 10000, "max_ledger_records": 30000,
                             "max_observations": 100},
        "source_policy": {"source_version": "generated", "source_manifest_sha256": "a" * 64,
                          "measure_domain_sha256": canonical_hash(measures),
                          "corrected_supplement_sha256": None},
    }
    dataset = {"schema": "meg_feature_table_v1", "measure_ids": measures.copy(),
               "sampling": "label_independent_observations",
               "source_manifest_sha256": "a" * 64, "observations": rows}
    return protocol, dataset, labels


def outer_training_labels(labels, excluded="p3"):
    return {oid: value for oid, value in labels.items() if not oid.startswith(excluded + "-")}


class MEGNestedIndependentControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, cls.data, cls.labels = generated_fixture()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            cls.result = core.run_nested(cls.data, cls.labels, cls.protocol)
        cls.last_fold = next(f for f in cls.result["folds"] if f["fold_id"] == "outer-p3")

    def fit_last(self, data=None, protocol=None, labels=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            return core.fit_predict_fold(
                self.data if data is None else data,
                outer_training_labels(self.labels) if labels is None else labels,
                self.protocol if protocol is None else protocol, "outer-p3")

    def test_complete_domain_nested_ledger_and_perfect_reference(self):
        self.assertEqual(set(self.result["predictions"]), set(self.labels))
        self.assertEqual(len(self.result["folds"]), 4)
        for oid, prediction in self.result["predictions"].items():
            self.assertEqual(prediction["predicted_class"], self.labels[oid])
        score = self.result["scores"]["endpoints"]["vision"]
        self.assertEqual(score["rows"], 8)
        self.assertEqual(score["participant_mean_accuracy"], 1.0)
        self.assertEqual(score["participant_mean_balanced_accuracy"], 1.0)
        for fold in self.result["folds"]:
            endpoint = fold["endpoints"][0]
            self.assertEqual(endpoint["selected_measure"], "measure-000")
            self.assertEqual(endpoint["selected_C"], 10.0)
            self.assertEqual(endpoint["inner_score"], 1.0)
            self.assertEqual(len(endpoint["candidates"]), 246)
            self.assertEqual(endpoint["model"]["training_rows"], 6)
            outer_test = set(endpoint["test_ids"])
            self.assertEqual(len(outer_test), 2)
            self.assertEqual(len(endpoint["inner_partitions"]), 3)
            seen_validation = set()
            for partition in endpoint["inner_partitions"]:
                fit_ids, validation_ids = set(partition["fit_ids"]), set(partition["validation_ids"])
                self.assertEqual(len(fit_ids), 4)
                self.assertEqual(len(validation_ids), 2)
                self.assertFalse(fit_ids & validation_ids)
                self.assertFalse((fit_ids | validation_ids) & outer_test)
                self.assertFalse(seen_validation & validation_ids)
                seen_validation |= validation_ids
            self.assertEqual(seen_validation, set(endpoint["fit_ids"]))
            for candidate in endpoint["candidates"]:
                self.assertEqual(len(candidate["inner_models"]), 3)
                self.assertTrue(all(model["training_rows"] == 4 for model in candidate["inner_models"]))

    def test_training_api_refuses_outer_targets_and_missing_training_targets(self):
        with self.assertRaises(core.Refusal):
            self.fit_last(labels=self.labels)
        training = outer_training_labels(self.labels)
        training.pop("p0-0")
        with self.assertRaises(core.Refusal):
            self.fit_last(labels=training)

    def test_outer_labels_do_not_change_its_selected_model_or_predictions(self):
        changed = dict(self.labels, **{"p3-0": "object", "p3-1": "face"})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            result = core.run_nested(self.data, changed, self.protocol)
        last = next(f for f in result["folds"] if f["fold_id"] == "outer-p3")
        self.assertEqual(last, self.last_fold)
        original_predictions = self.result["predictions"]
        rescored = core.score_predictions(self.data, changed, original_predictions, self.protocol)
        self.assertEqual(rescored["endpoints"]["vision"]["participant_mean_accuracy"], 0.75)

    def test_outer_features_do_not_change_selection_or_training_state(self):
        changed = copy.deepcopy(self.data)
        for row in changed["observations"]:
            if row["participant"] == "p3":
                row["values"][0] *= -100.0
                row["values"][1] *= -1000.0
        result = self.fit_last(data=changed)
        self.assertEqual(result["endpoints"], self.last_fold["endpoints"])
        self.assertNotEqual(result["predictions"], self.last_fold["predictions"])

    def test_row_order_does_not_change_fold_result(self):
        changed = copy.deepcopy(self.data)
        changed["observations"].reverse()
        actual = self.fit_last(data=changed)
        expected = copy.deepcopy(self.last_fold)
        self.assertEqual(actual.pop("feature_table_sha256"), canonical_hash(changed))
        self.assertEqual(expected.pop("feature_table_sha256"), canonical_hash(self.data))
        self.assertEqual(actual, expected)

    def test_heldout_batch_peers_do_not_change_frozen_prediction(self):
        model = self.last_fold["endpoints"][0]["model"]
        alone = core.predict_model(model, [0.5])[0]
        peers = core.predict_model(model, [0.5, -10000.0, 10000.0])
        reordered = core.predict_model(model, [10000.0, 0.5, -10000.0])
        self.assertEqual(alone, peers[0])
        self.assertEqual(alone, reordered[1])

    def test_logistic_fit_matches_an_independent_closed_form_optimum(self):
        # Equal class weights and z = [-1,-1,1,1] give objective
        # |b| + 40*log(1+exp(-b)); its positive stationary point is log(39).
        # Symmetry gives intercept zero. This derives the expected solver result
        # without using any fitted coefficient or implementation calculation.
        estimator = dict(self.protocol["estimator"], tol=1e-10)
        model = core.fit_model([-1, -1, 1, 1], [0, 0, 1, 1], 10.0, estimator)
        self.assertAlmostEqual(model["coefficient"], math.log(39), delta=1e-6)
        self.assertAlmostEqual(model["intercept"], 0.0, delta=1e-6)
        probabilities = core.predict_model(model, [-1, 1])
        self.assertAlmostEqual(probabilities[0], 1 / 40, delta=1e-7)
        self.assertAlmostEqual(probabilities[1], 39 / 40, delta=1e-7)

    def test_known_condition_averages_are_refused(self):
        for sampling in ("known_condition_average", "per_category_mean"):
            with self.subTest(sampling=sampling):
                changed = copy.deepcopy(self.data)
                changed["sampling"] = sampling
                with self.assertRaises(core.Refusal):
                    core.validate_dataset(changed, self.protocol)

    def test_exact_246_measure_domain_and_order_are_required(self):
        changed = copy.deepcopy(self.protocol)
        changed["measure_ids"].pop()
        with self.assertRaises(core.Refusal):
            core.validate_protocol(changed)
        changed = copy.deepcopy(self.protocol)
        changed["measure_ids"][1] = changed["measure_ids"][0]
        with self.assertRaises(core.Refusal):
            core.validate_protocol(changed)
        changed = copy.deepcopy(self.data)
        changed["measure_ids"].reverse()
        with self.assertRaises(core.Refusal):
            core.validate_dataset(changed, self.protocol)

    def test_exact_full_observation_support_required(self):
        changes = []
        missing = copy.deepcopy(self.data)
        missing["observations"].pop()
        changes.append(missing)
        duplicate = copy.deepcopy(self.data)
        duplicate["observations"][1] = copy.deepcopy(duplicate["observations"][0])
        changes.append(duplicate)
        extra = copy.deepcopy(self.data)
        extra["observations"][0]["id"] = "not-declared"
        changes.append(extra)
        for changed in changes:
            with self.subTest(observations=[r["id"] for r in changed["observations"]]):
                with self.assertRaises(core.Refusal):
                    core.validate_dataset(changed, self.protocol)

    def test_canonical_aliases_resolve_and_conflicts_are_rejected(self):
        protocol, data = copy.deepcopy(self.protocol), copy.deepcopy(self.data)
        protocol["participant_aliases"]["p0-session-alias"] = "p0"
        for row in data["observations"]:
            if row["participant"] == "p0":
                row["participant"] = "p0-session-alias"
        admitted = core.validate_dataset(data, protocol)
        self.assertEqual(admitted["p0-0"]["participant"], "p0")
        protocol["participant_aliases"]["p0"] = "p1"
        with self.assertRaises(core.Refusal):
            core.validate_protocol(protocol)

    def test_outer_and_inner_partitions_cannot_overlap_or_omit_people(self):
        mutations = []
        p = copy.deepcopy(self.protocol)
        p["outer_folds"].pop()
        mutations.append(p)
        p = copy.deepcopy(self.protocol)
        p["outer_folds"][1]["test_participants"] = ["p0"]
        mutations.append(p)
        p = copy.deepcopy(self.protocol)
        p["outer_folds"][0]["inner_validation_participants"][0] = ["p0"]
        mutations.append(p)
        for protocol in mutations:
            with self.subTest(folds=protocol["outer_folds"]):
                with self.assertRaises(core.Refusal):
                    core.validate_protocol(protocol)

    def test_malformed_numeric_features_are_refused(self):
        for bad in (float("nan"), float("inf"), -float("inf"), True, "1", 10 ** 500):
            with self.subTest(value_type=type(bad).__name__):
                changed = copy.deepcopy(self.data)
                changed["observations"][0]["values"][0] = bad
                with self.assertRaises(core.Refusal):
                    core.validate_dataset(changed, self.protocol)

    def test_integer_features_preserve_exact_value_before_float_conversion(self):
        for value in (2 ** 53 - 1, 2 ** 53, 2 ** 53 + 2, 2 ** 54, -(2 ** 54)):
            with self.subTest(accepted=value):
                changed = copy.deepcopy(self.data)
                changed["observations"][0]["values"][0] = value
                admitted = core.validate_dataset(changed, self.protocol)
                self.assertEqual(int(admitted["p0-0"]["values"][0]), value)
        for value in (2 ** 53 + 1, -(2 ** 53 + 1), 2 ** 54 + 1):
            with self.subTest(refused=value):
                changed = copy.deepcopy(self.data)
                changed["observations"][0]["values"][0] = value
                with self.assertRaises(core.Refusal):
                    core.validate_dataset(changed, self.protocol)

    def test_constant_class_balancing_and_exact_selection_tie_order(self):
        model = core.fit_model([7, 7, 7, 7], [0, 0, 0, 1], 10, self.protocol["estimator"])
        self.assertEqual(core.predict_model(model, [-100, 7, 100]), [0.5, 0.5, 0.5])
        p, data = copy.deepcopy(self.protocol), copy.deepcopy(self.data)
        p["estimator"]["C"] = [2.0, 1.0]
        for row in data["observations"]:
            row["values"] = [0.0] * 246
        result = self.fit_last(data=data, protocol=p)
        endpoint = result["endpoints"][0]
        self.assertEqual(endpoint["selected_measure"], "measure-000")
        self.assertEqual(endpoint["selected_C"], 2.0)
        self.assertEqual(endpoint["inner_score"], 0.5)
        self.assertTrue(all(p["predicted_class"] == "face" for p in result["predictions"].values()))

    def test_nonconvergence_is_refused(self):
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.linear_model import LogisticRegression

        def unconverged(*args, **kwargs):
            warnings.warn("independent nonconvergence control", ConvergenceWarning)

        with mock.patch.object(LogisticRegression, "fit", side_effect=unconverged):
            with self.assertRaises(core.Refusal):
                core.fit_model([-2, -1, 1, 2], [0, 0, 1, 1], 10, self.protocol["estimator"])

    def test_exact_work_limits_and_one_under_refusal_precede_every_fit(self):
        # Four outer folds each contain 246 candidates, three inner fits per
        # candidate, and one final fit: 4 * (246 * 3 + 1) = 2956.
        # Records: 984 candidate/model records + 3 partitions + outer model
        # + endpoint + fold + 2 predictions = 992 per fold, hence 3968 total.
        protocol = copy.deepcopy(self.protocol)
        protocol["execution_limits"] = {
            "max_fit_calls": 2956, "max_ledger_records": 3968, "max_observations": 8}
        workload = core.preflight(self.data, protocol)
        self.assertEqual(workload, {"fit_calls": 2956, "ledger_records": 3968,
                                    "observations": 8, "logical_counts_only": True})
        for field in protocol["execution_limits"]:
            changed = copy.deepcopy(protocol)
            changed["execution_limits"][field] -= 1
            with self.subTest(limit=field):
                with mock.patch.object(core, "fit_model", side_effect=AssertionError("fit before refusal")) as fit:
                    with self.assertRaises(core.Refusal):
                        core.run_nested(self.data, self.labels, changed)
                    fit.assert_not_called()
        fold_protocol = copy.deepcopy(self.protocol)
        fold_protocol["execution_limits"] = {
            "max_fit_calls": 739, "max_ledger_records": 992, "max_observations": 8}
        self.assertEqual(core.preflight(self.data, fold_protocol, "outer-p3")["fit_calls"], 739)
        fold_protocol["execution_limits"]["max_fit_calls"] = 738
        with mock.patch.object(core, "fit_model", side_effect=AssertionError("fit before fold refusal")) as fit:
            with self.assertRaises(core.Refusal):
                self.fit_last(protocol=fold_protocol)
            fit.assert_not_called()

    def test_single_training_class_is_refused(self):
        with self.assertRaises(core.Refusal):
            core.fit_model([-1, 1], [0, 0], 10, self.protocol["estimator"])

    def test_scoring_observation_cap_is_enforced_before_metric_work(self):
        protocol = copy.deepcopy(self.protocol)
        protocol["execution_limits"]["max_observations"] = 7
        with mock.patch.object(core, "_summarize", side_effect=AssertionError("scoring before refusal")) as summarize:
            with self.assertRaises(core.Refusal):
                core.score_predictions(self.data, self.labels, self.result["predictions"], protocol)
            summarize.assert_not_called()

    def test_independent_confusions_distinguish_person_and_row_weighting(self):
        p, data, labels = generated_fixture(3)
        for extra_id in ("p0-2", "p0-3"):
            p["expected_observations"]["vision"].append({"id": extra_id, "participant": "p0"})
            data["observations"].append({"id": extra_id, "participant": "p0", "endpoint": "vision",
                                         "values": [0.0] * 246})
            labels[extra_id] = "face"
        predicted = {oid: label for oid, label in labels.items()}
        predicted.update({"p0-3": "object", "p1-0": "object", "p1-1": "face"})
        predictions = {oid: {"predicted_class": label,
                             "probability_class1": 0.9 if label == "object" else 0.1}
                       for oid, label in predicted.items()}
        score = core.score_predictions(data, labels, predictions, p)["endpoints"]["vision"]
        by_person = {row["participant"]: row for row in score["participants"]}
        self.assertEqual(by_person["p0"]["confusion"], [[2, 1], [0, 1]])
        self.assertEqual(by_person["p1"]["confusion"], [[0, 1], [1, 0]])
        self.assertEqual(by_person["p2"]["confusion"], [[1, 0], [0, 1]])
        self.assertAlmostEqual(score["participant_mean_accuracy"], 7 / 12)
        self.assertAlmostEqual(score["participant_mean_balanced_accuracy"], 11 / 18)
        self.assertEqual(score["pooled_accuracy"], 5 / 8)

    def test_undefined_person_balanced_accuracy_is_not_silently_dropped(self):
        labels = dict(self.labels, **{"p3-1": "face"})
        predictions = {oid: {"predicted_class": "face", "probability_class1": 0.5} for oid in labels}
        score = core.score_predictions(self.data, labels, predictions, self.protocol)["endpoints"]["vision"]
        self.assertIsNone(score["participant_mean_balanced_accuracy"])
        self.assertEqual(score["undefined_balanced_accuracy_participants"], ["p3"])
        self.assertEqual(len(score["participants"]), 4)
        self.assertEqual(score["rows"], 8)

    def test_prediction_support_probability_and_class_are_validated(self):
        alterations = []
        missing = copy.deepcopy(self.result["predictions"])
        missing.pop("p0-0")
        alterations.append(missing)
        for probability in (float("nan"), -0.01, 1.01, True):
            changed = copy.deepcopy(self.result["predictions"])
            changed["p0-0"]["probability_class1"] = probability
            alterations.append(changed)
        inconsistent = copy.deepcopy(self.result["predictions"])
        inconsistent["p0-0"]["predicted_class"] = "object"
        alterations.append(inconsistent)
        for predictions in alterations:
            with self.subTest(prediction_count=len(predictions)):
                with self.assertRaises(core.Refusal):
                    core.score_predictions(self.data, self.labels, predictions, self.protocol)

    def test_engineering_result_keeps_scientific_and_execution_holds(self):
        for field in ("scientific_qualification", "whole_task_complete", "held_out_data_globally_unseen",
                      "candidate_process_isolated", "source_time_series_to_features_verified",
                      "corrected_supplement_join_verified", "measure_domain_matches_paper_verified",
                      "complete_authentic_cohort_verified"):
            self.assertIs(self.result[field], False)


class MEGDesignAndIOControls(unittest.TestCase):
    def test_outcome_blind_94_person_plan_covers_every_partition(self):
        people = [f"person-{index:03d}" for index in range(94)]
        result = design.recommended_fold_plan(people)
        self.assertEqual(result, design.recommended_fold_plan(list(reversed(people))))
        folds = result["outer_folds"]
        self.assertEqual(len(folds), 10)
        self.assertEqual([len(f["test_participants"]) for f in folds], [10] * 4 + [9] * 6)
        all_test = set()
        for index, fold in enumerate(folds):
            self.assertEqual(fold["id"], f"outer-{index:02d}")
            test = set(fold["test_participants"])
            self.assertFalse(test & all_test)
            all_test |= test
            train = set(people) - test
            inner = fold["inner_validation_participants"]
            self.assertEqual(len(inner), 5)
            self.assertLessEqual(max(map(len, inner)) - min(map(len, inner)), 1)
            seen_validation = set()
            for group in inner:
                validation = set(group)
                self.assertFalse(validation & test)
                self.assertFalse(validation & seen_validation)
                self.assertTrue(validation < train)
                seen_validation |= validation
            self.assertEqual(seen_validation, train)
        self.assertEqual(all_test, set(people))
        for field in ("construction_uses_outcomes", "authentic_cohort_verified",
                      "scientific_policy_frozen", "scientific_qualification"):
            self.assertIs(result[field], False)

    def test_published_roster_and_saved_proposal_bind_the_same_94_identifiers(self):
        # This is the independently source-checked upstream identifier-body hash,
        # not a digest newly accepted from the file being tested.
        body = (PACKAGE / "published_participants.txt").read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),
                         "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a")
        people = body.decode().splitlines()
        self.assertEqual(len(people), 94)
        self.assertEqual(len(set(people)), 94)
        saved = json.loads((PACKAGE / "PROSPECTIVE_FOLDS.json").read_text())
        self.assertEqual(saved.pop("published_roster_sha256"), hashlib.sha256(body).hexdigest())
        self.assertEqual(saved, design.recommended_fold_plan(people))
        self.assertIs(saved["authentic_cohort_verified"], False)
        self.assertIs(saved["scientific_policy_frozen"], False)

    def test_fold_proposal_refuses_wrong_support_and_invalid_ids(self):
        people = [f"person-{index:03d}" for index in range(94)]
        duplicate = people.copy()
        duplicate[-1] = duplicate[0]
        whitespace = people.copy()
        whitespace[0] = " person-000"
        for invalid in (people[:-1], people + ["extra"], duplicate, whitespace, tuple(people)):
            with self.subTest(kind=type(invalid).__name__, size=len(invalid)):
                with self.assertRaises(ValueError):
                    design.recommended_fold_plan(invalid)

    def test_json_parser_refuses_duplicates_nonfinite_and_huge_integer(self):
        old_limit = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(4300)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "input.json"
                for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}',
                             b'{"a":-Infinity}', b'\xff', b'9' * 4500):
                    with self.subTest(prefix=body[:24]):
                        path.write_bytes(body)
                        with self.assertRaises(runner.core.Refusal):
                            runner.read_json(path, 5000)
        finally:
            sys.set_int_max_str_digits(old_limit)

    def test_input_byte_caps_are_exact_and_validated_before_open(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "one-byte.json"
            path.write_bytes(b"0")
            self.assertEqual(runner.read_json(path, 1), (0, hashlib.sha256(b"0").hexdigest()))
            self.assertEqual(runner.read_json(path, sys.maxsize - 1)[0], 0)
            path.write_bytes(b"null")
            self.assertEqual(runner.read_json(path, 4)[0], None)
            with self.assertRaises(runner.core.Refusal):
                runner.read_json(path, 3)
            for invalid in (0, -1, True, sys.maxsize):
                with self.subTest(limit=invalid):
                    with mock.patch("builtins.open", side_effect=AssertionError("opened before limit check")) as opened:
                        with self.assertRaises(runner.core.Refusal):
                            runner.read_json(path, invalid)
                        opened.assert_not_called()

    def test_nul_paths_are_refused_before_file_operations(self):
        with mock.patch("builtins.open", side_effect=AssertionError("opened NUL path")) as opened:
            with self.assertRaises(runner.core.Refusal):
                runner.read_json("bad\0path", 100)
            opened.assert_not_called()
        with mock.patch.object(runner.tempfile, "NamedTemporaryFile",
                               side_effect=AssertionError("created temporary for NUL path")) as temporary:
            with self.assertRaises(runner.core.Refusal):
                runner.write_new_json("bad\0path", {}, 100)
            temporary.assert_not_called()

    def test_output_byte_cap_is_exact_and_fresh_publication_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            value = {"key": [1, 2]}
            expected = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
            output = root / "result.json"
            runner.write_new_json(output, value, len(expected))
            self.assertEqual(output.read_bytes(), expected)
            refused = root / "too-small.json"
            with self.assertRaises(runner.core.Refusal):
                runner.write_new_json(refused, value, len(expected) - 1)
            self.assertFalse(refused.exists())
            for invalid in (0, -1, True, sys.maxsize):
                with self.subTest(limit=invalid):
                    with self.assertRaises(runner.core.Refusal):
                        runner.write_new_json(refused, value, invalid)
            self.assertEqual(set(root.iterdir()), {output})

    def test_existing_output_and_input_hardlink_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.json"
            source.write_bytes(b'{"protected":"original"}')
            alias = root / "result.json"
            os.link(source, alias)
            with self.assertRaises(FileExistsError):
                runner.write_new_json(alias, {"replacement": True}, 1000)
            self.assertEqual(source.read_bytes(), b'{"protected":"original"}')
            self.assertEqual(alias.read_bytes(), source.read_bytes())
            self.assertEqual(set(root.iterdir()), {source, alias})

    def test_failed_atomic_publication_cleans_only_its_temporary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = root / "keep.txt"
            marker.write_text("keep")
            with mock.patch.object(runner.os, "link", side_effect=OSError("injected publish failure")):
                with self.assertRaises(OSError):
                    runner.write_new_json(root / "result.json", {"ok": True}, 1000)
            self.assertEqual(set(root.iterdir()), {marker})
            self.assertEqual(marker.read_text(), "keep")

    def cli_inputs(self, root):
        protocol, dataset, _ = generated_fixture()
        protocol_path, features_path = root / "protocol input.json", root / "feature input.json"
        protocol_path.write_text(json.dumps(protocol, sort_keys=True))
        features_path.write_text(json.dumps(dataset, sort_keys=True))
        protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        return protocol_path, features_path, protocol_sha

    def cli(self, script, protocol_path, features_path, protocol_sha, output, maximum=10000):
        # -S excludes installed packages: preflight must not need a numerical
        # library, fit any model or read a label operand.
        command = [sys.executable, "-I", "-S", "-B", str(script), "preflight",
                   "--protocol", str(protocol_path), "--protocol-sha256", protocol_sha,
                   "--features", str(features_path), "--max-input-bytes", "200000",
                   "--max-output-bytes", str(maximum), "--output", str(output)]
        return subprocess.run(command, text=True, capture_output=True, timeout=20,
                              cwd=output.parent)

    def test_cli_stdlib_preflight_receipt_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protocol, features, protocol_sha = self.cli_inputs(root)
            output = root / "preflight result.json"
            result = self.cli(PACKAGE / "run.py", protocol, features, protocol_sha, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            body = output.read_bytes()
            receipt = json.loads(body)
            self.assertEqual(receipt["schema"], "meg_preflight_v1")
            self.assertEqual(receipt["workload"], {"fit_calls": 2956, "ledger_records": 3968,
                                                 "observations": 8, "logical_counts_only": True})
            self.assertEqual(receipt["input_file_sha256"], {
                "protocol": protocol_sha, "features": hashlib.sha256(features.read_bytes()).hexdigest()})
            self.assertEqual(receipt["executed_core_sha256"], hashlib.sha256(SOURCE.read_bytes()).hexdigest())
            self.assertIs(receipt["scientific_qualification"], False)
            self.assertIs(receipt["physical_provenance_verified"], False)
            second = self.cli(PACKAGE / "run.py", protocol, features, protocol_sha, output)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), body)
            self.assertEqual(json.loads(second.stderr)["status"], "refused")
            self.assertFalse(list(root.glob(".meg-output-*")))

    def test_cli_pinning_and_output_caps_refuse_without_partial_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protocol, features, protocol_sha = self.cli_inputs(root)
            wrong_hash_output = root / "wrong-hash.json"
            failed = self.cli(PACKAGE / "run.py", protocol, features, "f" * 64, wrong_hash_output)
            self.assertEqual(failed.returncode, 2)
            self.assertFalse(wrong_hash_output.exists())
            self.assertEqual(json.loads(failed.stderr)["status"], "refused")
            baseline = root / "baseline.json"
            self.assertEqual(self.cli(PACKAGE / "run.py", protocol, features, protocol_sha, baseline).returncode, 0)
            exact = len(baseline.read_bytes())
            exact_output = root / "exact.json"
            self.assertEqual(self.cli(PACKAGE / "run.py", protocol, features, protocol_sha, exact_output, exact).returncode, 0)
            self.assertEqual(exact_output.read_bytes(), baseline.read_bytes())
            too_small = root / "too-small.json"
            failed = self.cli(PACKAGE / "run.py", protocol, features, protocol_sha, too_small, exact - 1)
            self.assertEqual(failed.returncode, 2)
            self.assertFalse(too_small.exists())
            self.assertFalse(list(root.glob(".meg-output-*")))

    def test_cli_executes_source_instead_of_valid_stale_bytecode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / "copied-package"
            package.mkdir()
            copied_core = package / "core.py"
            shutil.copyfile(SOURCE, copied_core)
            shutil.copyfile(PACKAGE / "run.py", package / "run.py")
            cache = Path(importlib.util.cache_from_source(str(copied_core)))
            cache.parent.mkdir()
            stat = copied_core.stat()
            sentinel = compile("raise RuntimeError('stale-bytecode-control')", str(copied_core), "exec")
            cache.write_bytes(importlib.util.MAGIC_NUMBER
                              + struct.pack("<III", 0, int(stat.st_mtime) & 0xFFFFFFFF, stat.st_size & 0xFFFFFFFF)
                              + marshal.dumps(sentinel))
            # Prove this is a usable cached-bytecode control, not merely an
            # ignored corrupt cache, using the ordinary CPython source loader.
            probe = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-c",
                 "import importlib.util,sys; s=importlib.util.spec_from_file_location('control',sys.argv[1]); "
                 "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)", str(copied_core)],
                capture_output=True, text=True, timeout=20)
            self.assertNotEqual(probe.returncode, 0)
            self.assertIn("stale-bytecode-control", probe.stderr)
            protocol, features, protocol_sha = self.cli_inputs(root)
            output = root / "verified-source-result.json"
            result = self.cli(package / "run.py", protocol, features, protocol_sha, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt["executed_core_sha256"], hashlib.sha256(copied_core.read_bytes()).hexdigest())
            self.assertEqual(receipt["schema"], "meg_preflight_v1")


if __name__ == "__main__":
    unittest.main()
