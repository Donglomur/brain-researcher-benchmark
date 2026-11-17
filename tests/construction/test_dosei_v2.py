"""Independent generated controls for the conditional DOSEI secondary metrics.

Small exact expectations were frozen before reading the new implementation.
The full source census is invented, with six evaluable assessments; no authentic
clinical data, model performance or scientific qualification is established.
"""
from pathlib import Path
from fractions import Fraction as F
import copy
import hashlib
import json
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/clinical-dosei-responsiveness/implementations/ordinal-metrics-v2"
PRIMARY_SOURCE = ROOT / "benchmarks/neural/clinical-dosei-responsiveness/implementations/ordinal-and-paired/dosei_score.py"
TASK = "clinical-dosei-responsiveness"
PROVENANCE = ("person_join", "assessment_census", "transition_census", "missingness", "group_split", "packet_causality")
CASES = [
    ("A", 1, ["0.5", "0", "0", "0", "0.5"]),
    ("A", 1, ["1", "0", "0", "0", "0"]),
    ("A", 3, ["0", "0.3", "0.4", "0.3", "0"]),
    ("A", 5, ["0.4", "0.35", "0", "0", "0.25"]),
    ("B", 5, ["0", "0", "0", "0", "1"]),
    ("C", 1, ["0", "1", "0", "0", "0"]),
]
EXPECTED_DRAWS = ((0, 1, 1), (2, 2, 2), (2, 2, 0), (0, 1, 1),
                  (2, 2, 1), (1, 0, 1), (1, 0, 1), (1, 1, 2))


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def rational(value):
    return None if value is None else F(int(value["numerator"]), int(value["denominator"]))


def load_source(path, name):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def fixture():
    people = ["A", "B", "C"]
    policy = {
        "schema": "dosei_complete_policy_v1", "task": TASK,
        "categories": [1, 2, 3, 4, 5],
        "label_source": "original_EVENT_MOAAS_assessment",
        "provenance": {role: "0" * 64 for role in PROVENANCE},
        "people": people,
        "folds": [{"fold_id": "fold" + p,
                   "training_people": [q for q in people if q != p],
                   "heldout_people": [p]} for p in people],
        "recordings": [{"recording_id": "rec" + str(i), "person_id": people[i % 3]}
                       for i in range(171)],
        "assessments": [], "transitions": [],
    }
    candidate = {"schema": "dosei_predictions_v1", "task": TASK, "assessments": []}
    reference = {"schema": "dosei_predictions_v1", "task": TASK, "assessments": []}
    targets = {"schema": "dosei_targets_v1", "task": TASK, "assessments": []}
    for i in range(7328):
        ok = i < len(CASES)
        person, category, probabilities = CASES[i] if ok else (people[i % 3], None, None)
        policy["assessments"].append({
            "assessment_id": "a" + str(i), "recording_id": "rec" + str(people.index(person)),
            "source_event_id": "event" + str(i), "label_status": "valid" if ok else "missing",
            "window_status": "complete", "timing_status": "verified", "artifact_status": "included",
        })
        common = {"assessment_id": "a" + str(i), "outer_fold": "fold" + person,
                  "status": "ok" if ok else "not_evaluable"}
        candidate["assessments"].append({**common, "probabilities": copy.deepcopy(probabilities)})
        reference["assessments"].append({**common, "probabilities":
            [str(int(j == category)) for j in range(1, 6)] if ok else None})
        targets["assessments"].append({"assessment_id": "a" + str(i), "category": category})
    for i in range(1129):
        policy["transitions"].append({"transition_id": "t" + str(i),
            "recording_id": "rec" + str(i % 171), "source_event_id": "transition" + str(i)})
    secondary = {
        "schema": "dosei_secondary_policy_v2", "task": TASK,
        "primary_policy_sha256": pin(encode(policy)), "original_packet_set_sha256": "1" * 64,
        "arms": ["candidate", "reference"],
        "contrasts": [{"contrast_id": "candidate_minus_reference",
                       "comparison_arm": "candidate", "reference_arm": "reference"}],
        "hard_category": "lowest_probability_mode", "mae_aggregation": "equal_person_equal_within_person",
        "recall_aggregation": "equal_supported_person_per_category",
        "calibration": {"method": "classwise_reliability_ece",
                        "weighting": "equal_person_equal_within_person", "bin_edges": ["0", "0.5", "1"],
                        "boundary": "left_closed_right_open_last_closed"},
        "bootstrap": {"method": "iid_biological_person_percentile", "seed_sha256": "0" * 64,
                      "replicates": 8, "confidence": "0.5", "quantile": "linear_type7",
                      "metrics": ["normalized_rps", "ordinal_mae"], "difference": "comparison_minus_reference"},
        "freeze_receipts": {k: "2" * 64 for k in ("metric_policy", "before_outcomes", "same_inputs_and_training")},
    }
    bundle = {"schema": "dosei_secondary_predictions_v2", "task": TASK,
              "original_packet_set_sha256": "1" * 64,
              "arms": [{"arm_id": "candidate", "predictions": candidate},
                       {"arm_id": "reference", "predictions": reference}]}
    return policy, bundle, targets, secondary


def score(module, policy, bundle, targets, secondary):
    raw = [encode(x) for x in (policy, bundle, targets, secondary)]
    return module.score_artifacts(*raw, primary_source=PRIMARY_SOURCE,
        **{"expected_" + name + "_sha256": pin(value)
           for name, value in zip(("policy", "predictions", "targets", "secondary"), raw)})


class IndependentDoseiSecondary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = PRIMARY_SOURCE.read_bytes()
        assert len(original) == 15749 and pin(original) == "09560538d472f0b99c65532bf371c8e9af56635e1ec437f68dd2f83b5f7bde77"
        cls.module = load_source(PACKAGE / "dosei_metrics.py", "dosei_metrics_independent_test")

    def test_declared_mode_median_and_ties(self):
        ambiguous = tuple(map(F, CASES[3][2]))
        self.assertEqual(self.module.hard_category(ambiguous, "lowest_probability_mode"), 1)
        self.assertEqual(self.module.hard_category(ambiguous, "lower_probability_median"), 2)
        tied = tuple(map(F, CASES[0][2]))
        self.assertEqual(self.module.hard_category(tied, "lowest_probability_mode"), 1)
        self.assertEqual(self.module.hard_category(tied, "lower_probability_median"), 1)
        with self.assertRaises(ValueError):
            self.module.hard_category(ambiguous, "unspecified")

    def test_percentile_interpolation_uses_declared_type_seven(self):
        values = [F(1, 4), F(0), F(1211, 6400), F(937, 6400)]
        before = list(values)
        self.assertEqual(self.module.linear_quantile(values, F(1, 4)), F(2811, 25600))
        self.assertEqual(self.module.linear_quantile(values, F(3, 4)), F(5233, 25600))
        self.assertEqual(values, before)

    def test_frozen_counter_hash_cluster_draws(self):
        self.assertEqual(self.module.bootstrap_indices(["A", "B", "C"], "0" * 64, 8), EXPECTED_DRAWS)
        self.assertEqual(self.module.bootstrap_indices(["A", "B", "C"], "0" * 64, 8), EXPECTED_DRAWS)

    def test_complete_primary_preserved_and_participant_metrics_exact(self):
        p, b, t, c = fixture()
        before = pin(encode([p, b, t, c]))
        report = score(self.module, p, b, t, c)
        primary = load_source(PRIMARY_SOURCE, "original_dosei_for_comparison")
        for arm in b["arms"]:
            # The prior evaluator body is preserved exactly. Standalone-artifact
            # receipts do not describe the new multi-arm prediction bundle.
            admitted = primary.admit_policy(p)
            probabilities = primary.admit_predictions(arm["predictions"], admitted)
            prior = primary.score_admitted(t, admitted, probabilities)
            self.assertEqual(report["complete_original_scores"][arm["arm_id"]], prior)
        self.assertEqual(rational(report["complete_original_scores"]["candidate"]["primary_normalized_rps"]), F(937, 6400))
        secondary = report["secondary_scores"]["candidate"]
        self.assertEqual(rational(secondary["ordinal_mae"]), F(2, 3))
        self.assertNotEqual(rational(secondary["ordinal_mae"]), F(5, 6))
        self.assertEqual([rational(row["ordinal_mae"]) for row in secondary["people"]], [F(1), F(0), F(1)])
        recall = {row["category"]: row for row in secondary["per_category_recall"]}
        self.assertEqual(rational(recall[1]["supported_person_macro_recall"]), F(1, 2))
        self.assertNotEqual(rational(recall[1]["supported_person_macro_recall"]), F(2, 3))
        self.assertEqual(recall[1]["people_without_category_support"], ["B"])
        for category in (2, 4):
            self.assertIsNone(recall[category]["supported_person_macro_recall"])
            self.assertEqual(recall[category]["people_without_category_support"], ["A", "B", "C"])
            self.assertEqual(recall[category]["support_assessments"], 0)
        self.assertEqual(pin(encode([p, b, t, c])), before)
        for flag in ("physical_input_parity_verified", "authentic_census_verified", "scientifically_qualified"):
            self.assertIs(report[flag], False)
        self.assertEqual(report["new_benchmark_count"], 0)

    def test_classwise_calibration_uses_person_weights_and_declared_edges(self):
        p, b, t, c = fixture()
        report = score(self.module, p, b, t, c)
        calibration = report["secondary_scores"]["candidate"]["calibration"]
        row = next(row for row in calibration["per_category"] if row["category"] == 1)
        self.assertEqual(rational(row["ece"]), F(41, 120))
        low, high = row["bins"]
        self.assertEqual((low["assessment_count"], high["assessment_count"]), (4, 2))
        self.assertEqual((rational(low["weight_mass"]), rational(high["weight_mass"])), (F(5, 6), F(1, 6)))
        self.assertEqual((rational(low["mean_probability"]), rational(low["observed_frequency"])), (F(1, 25), F(2, 5)))
        self.assertEqual((rational(high["mean_probability"]), rational(high["observed_frequency"])), (F(3, 4), F(1)))
        self.assertFalse(low["upper_inclusive"])
        self.assertTrue(high["upper_inclusive"])
        # Both exact0.5 and exact1 lie in the upper bin; no clipping or ad hoc tie move.
        self.assertEqual(rational(high["lower"]), F(1, 2))

    def test_explicit_median_changes_only_secondary_decision_metrics(self):
        p, b, t, c = fixture()
        mode = score(self.module, p, b, t, c)
        c["hard_category"] = "lower_probability_median"
        median = score(self.module, p, b, t, c)
        self.assertEqual(rational(median["secondary_scores"]["candidate"]["ordinal_mae"]), F(7, 12))
        self.assertEqual(mode["complete_original_scores"], median["complete_original_scores"])
        self.assertEqual(mode["secondary_scores"]["candidate"]["calibration"], median["secondary_scores"]["candidate"]["calibration"])

    def test_paired_cluster_interval_exact_and_reverse_contrast(self):
        p, b, t, c = fixture()
        c["contrasts"].append({"contrast_id": "reference_minus_candidate",
                               "comparison_arm": "reference", "reference_arm": "candidate"})
        report = score(self.module, p, b, t, c)
        forward, reverse = report["paired_uncertainty"]
        metrics = forward["bootstrap"]["metrics"]
        self.assertEqual([rational(metrics["normalized_rps"][k]) for k in ("estimate", "lower", "upper")],
                         [F(937, 6400), F(1211, 19200), F(14011, 76800)])
        self.assertEqual([rational(metrics["ordinal_mae"][k]) for k in ("estimate", "lower", "upper")],
                         [F(2, 3), F(1, 3), F(3, 4)])
        reverse_metric = reverse["bootstrap"]["metrics"]["normalized_rps"]
        self.assertEqual([rational(reverse_metric[k]) for k in ("estimate", "lower", "upper")],
                         [-F(937, 6400), -F(14011, 76800), -F(1211, 19200)])
        self.assertEqual(forward["bootstrap"]["draws_sha256"], pin(json.dumps(EXPECTED_DRAWS, separators=(",", ":")).encode("ascii")))
        self.assertEqual(forward["bootstrap"]["draws_sha256"], reverse["bootstrap"]["draws_sha256"])
        self.assertIs(forward["bootstrap"]["draws_shared_across_arms_metrics_and_contrasts"], True)
        self.assertIs(forward["interval_coverage_verified"], False)
        self.assertIs(forward["pre_outcome_freezing_verified"], False)

    def test_unsupported_person_is_retained_and_full_macro_is_undefined(self):
        p, b, t, c = fixture()
        p["assessments"][5]["window_status"] = "incomplete"
        for arm in b["arms"]:
            arm["predictions"]["assessments"][5].update(status="not_evaluable", probabilities=None)
        c["primary_policy_sha256"] = pin(encode(p))
        report = score(self.module, p, b, t, c)
        self.assertEqual(len(report["complete_original_scores"]["candidate"]["assessments"]), 7328)
        self.assertIsNone(report["complete_original_scores"]["candidate"]["primary_normalized_rps"])
        secondary = report["secondary_scores"]["candidate"]
        self.assertEqual([row["person_id"] for row in secondary["people"]], ["A", "B", "C"])
        self.assertIsNone(secondary["ordinal_mae"])
        self.assertEqual(secondary["people"][-1]["evaluable_assessments"], 0)
        self.assertIsNone(secondary["calibration"]["macro_ece"])
        for category in secondary["calibration"]["per_category"]:
            self.assertEqual(sum(row["assessment_count"] for row in category["bins"]), 5)
            self.assertIsNone(category["ece"])
            for row in category["bins"]:
                for key in ("weight_mass", "mean_probability", "observed_frequency", "absolute_gap"):
                    self.assertIsNone(row[key])
        paired = report["paired_uncertainty"][0]
        self.assertEqual(paired["people_without_evaluable_assessments"], ["C"])
        for result in paired["bootstrap"]["metrics"].values():
            self.assertEqual(result, {"estimate": None, "lower": None, "upper": None})

    def test_empty_calibration_bin_is_explicitly_undefined(self):
        p, b, t, c = fixture()
        c["calibration"]["bin_edges"] = ["0", "0.8", "0.9", "1"]
        report = score(self.module, p, b, t, c)
        for category in report["secondary_scores"]["candidate"]["calibration"]["per_category"]:
            empty = category["bins"][1]
            self.assertEqual(empty["assessment_count"], 0)
            self.assertEqual(empty["person_count"], 0)
            self.assertEqual(rational(empty["weight_mass"]), 0)
            for key in ("mean_probability", "observed_frequency", "absolute_gap"):
                self.assertIsNone(empty[key])

    def test_policy_semantics_are_required_and_invalid_choices_refuse(self):
        p, b, t, c = fixture()
        variants = []
        for key in ("hard_category", "calibration", "bootstrap", "freeze_receipts"):
            bad = copy.deepcopy(c)
            del bad[key]
            variants.append(bad)
        for field, value in (("replicates", 1), ("replicates", 4097),
                             ("confidence", "0"), ("confidence", "1"),
                             ("quantile", "nearest_unspecified")):
            bad = copy.deepcopy(c)
            bad["bootstrap"][field] = value
            variants.append(bad)
        for edges in (["0", "0.5", "0.5", "1"], ["0", "0.5", "0.9"], ["0", "NaN", "1"]):
            bad = copy.deepcopy(c)
            bad["calibration"]["bin_edges"] = edges
            variants.append(bad)
        for bad in variants:
            with self.subTest(policy=bad), self.assertRaises(ValueError):
                score(self.module, p, b, t, bad)

    def test_complete_census_and_all_candidate_arms_required(self):
        p, b, t, c = fixture()
        p["assessments"].pop()
        c["primary_policy_sha256"] = pin(encode(p))
        with self.assertRaisesRegex(ValueError, "7328"):
            score(self.module, p, b, t, c)
        p, b, t, c = fixture()
        b["arms"][1]["predictions"]["assessments"].pop()
        with self.assertRaises(ValueError):
            score(self.module, p, b, t, c)
        p, b, t, c = fixture()
        b["arms"][1]["predictions"]["assessments"][0]["outer_fold"] = "foldC"
        with self.assertRaises(ValueError):
            score(self.module, p, b, t, c)

    def test_cli_rejects_second_arm_before_any_protected_target_read(self):
        p, b, t, c = fixture()
        b["arms"][1]["predictions"]["assessments"][0]["probabilities"] = ["0.1"] * 5
        payloads = {k: encode(v) for k, v in zip(("policy", "predictions", "targets", "secondary"), (p, b, t, c))}
        original = load_source(PRIMARY_SOURCE, "original_dosei_for_read_order")
        seen = []
        def read(path, cap):
            seen.append(path)
            if path == "targets":
                raise AssertionError("protected target was opened before every arm was admitted")
            return payloads[path]
        original.read_regular = read
        old_loader = self.module.primary_module
        self.module.primary_module = lambda path: original
        args = ["--primary-source", str(PRIMARY_SOURCE)]
        for kind in ("policy", "predictions", "targets", "secondary"):
            args += ["--" + kind, kind, "--expected-" + kind + "-sha256", pin(payloads[kind])]
        args += ["--output", "UNREACHED_GENERATED_OUTPUT"]
        try:
            with self.assertRaisesRegex(ValueError, "probability sum"):
                self.module.main(args)
        finally:
            self.module.primary_module = old_loader
        self.assertEqual(seen, ["policy", "secondary", "predictions"])

    def test_current_policy_and_original_source_identity_are_bound(self):
        p, b, t, c = fixture()
        c["primary_policy_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            score(self.module, p, b, t, c)
        with tempfile.TemporaryDirectory(prefix="dosei-independent-source-") as temp:
            path = Path(temp) / "dosei_score.py"
            path.write_bytes(PRIMARY_SOURCE.read_bytes() + b"\n# changed identity\n")
            with self.assertRaises(ValueError):
                self.module.primary_module(path)


if __name__ == "__main__":
    unittest.main()
