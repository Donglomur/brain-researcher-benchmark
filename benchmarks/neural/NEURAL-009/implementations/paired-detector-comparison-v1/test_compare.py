"""Generated complete-roster controls; no authentic EEG, annotations or results."""
from __future__ import annotations

import argparse
import contextlib
import copy
from fractions import Fraction
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("neural009_comparison_test", ROOT / "compare.py")
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def score_runs(intervals, ticks):
    rows, previous = [], 0
    for start, stop in intervals:
        if start != previous:
            rows.append([previous, start, 0])
        rows.append([start, stop, 1])
        previous = stop
    if previous != ticks:
        rows.append([previous, ticks, 0])
    return rows


def generated_fixture(core):
    index, people, source_sha = core.source_index()
    assert len(index) == 686 and len(people) == 23 and "chb21" not in people
    ticks, seen, seen_alias = 2000, set(), False
    admission_rows, reference_rows, candidate_rows = [], [], []
    for identifier, source in sorted(index.items()):
        person = source["biological_person"]
        target = []
        if person not in seen:
            seen.add(person)
            target = [[300, 400]]
        if identifier.startswith("chb21/") and not seen_alias:
            seen_alias = True
            target = [[300, 400]]
        admission_rows.append({
            "recording_id": identifier, "biological_person": person,
            "edf_sha256": source["publisher_sha256"],
            "edf_header_sha256": digest("generated header " + identifier),
            "annotation_sha256": digest("generated annotations " + identifier),
            "annotation_status": "explicit_events" if target else "explicit_zero_events",
            "native_sample_rate_hz": 256, "native_sample_count": ticks * 256 // 10,
            "observed_ticks": ticks,
            "channels": [{"label": "GENERATED-EEG", "role": "eeg"}],
            "predictor_channels": [0], "reference_intervals": target,
        })
        ref_prediction, cand_prediction = copy.deepcopy(target), copy.deepcopy(target)
        if person == "chb01" and not identifier.startswith("chb21/") and target:
            ref_prediction = []
            cand_prediction += [[1600, 1610]]
        for rows, prediction in ((reference_rows, ref_prediction), (candidate_rows, cand_prediction)):
            rows.append({"recording_id": identifier, "biological_person": person, "fold_id": person,
                         "score_runs": score_runs(prediction, ticks), "predicted_intervals": prediction})
    policy = core.recommended_policy()
    admission = {"schema": "neural009_admission_v1", "task_id": "NEURAL-009",
                 "source_index_sha256": source_sha, "public_development_only": True,
                 "normalization_recipe_sha256": digest("generated normalization"),
                 "clock_review_sha256": digest("generated clock"),
                 "rights_review_sha256": digest("generated rights"),
                 "folds": [{"id": p, "train_people": [q for q in people if q != p],
                            "test_people": [p]} for p in people], "records": admission_rows}
    support = core.public_support(admission)
    common = {"schema": "neural009_candidate_v1", "task_id": "NEURAL-009",
              "source_index_sha256": source_sha, "support_sha256": core.canonical_sha256(support),
              "policy_sha256": core.canonical_sha256(policy)}
    reference = {**common, "recipe_sha256": digest("generated reference"), "records": reference_rows}
    candidate = {**common, "recipe_sha256": digest("generated candidate"), "records": candidate_rows}
    limits = {"max_record_ticks": ticks, "max_total_ticks": ticks * 686,
              "max_prediction_segments": 1000}
    bindings = {"expected_policy_sha256": common["policy_sha256"],
                "expected_reference_recipe_sha256": reference["recipe_sha256"],
                "expected_candidate_recipe_sha256": candidate["recipe_sha256"], "limits": limits}
    return admission, policy, support, reference, candidate, bindings


class CompletePairedComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core, cls.cli = comparison.load_predecessor(PREDECESSOR)
        cls.fixture = generated_fixture(cls.core)
        cls.result = cls.run_comparison(cls.fixture)

    @classmethod
    def run_comparison(cls, fixture):
        admission, policy, support, reference, candidate, bindings = fixture
        return comparison.compare(admission, policy, support, reference, candidate,
                                  _core=cls.core, **bindings)

    def test_hand_calculated_person_macro_and_tradeoff(self):
        result = self.result
        self.assertAlmostEqual(result["primary"]["reference"], float(Fraction(68, 69)))
        self.assertAlmostEqual(result["primary"]["candidate"], float(Fraction(114, 115)))
        self.assertAlmostEqual(result["primary"]["candidate_minus_reference"], float(Fraction(2, 345)))
        delta = result["patient_macro_event_metric_differences"]
        self.assertAlmostEqual(delta["sensitivity"]["candidate_minus_reference"], 1 / 46)
        self.assertAlmostEqual(delta["precision"]["candidate_minus_reference"], -1 / 69)
        self.assertGreater(delta["false_alarms_per_24_observed_hours"]["candidate_minus_reference"], 0)
        self.assertEqual(delta["false_alarms_per_24_observed_hours"]["direction"], "lower")

    def test_alias_and_full_background_exposure_are_preserved(self):
        rows = self.result["paired_people"]
        self.assertEqual(len(rows), 23)
        self.assertNotIn("chb21", {r["biological_person"] for r in rows})
        person = next(r for r in rows if r["biological_person"] == "chb01")
        record_count = sum(r["biological_person"] == "chb01" for r in self.fixture[0]["records"])
        self.assertEqual(person["observed_ticks"], record_count * 2000)
        self.assertAlmostEqual(person["event_metric_differences"]["f1"]["reference"], 2 / 3)
        self.assertAlmostEqual(person["event_metric_differences"]["f1"]["candidate"], 4 / 5)
        false_alarm_delta = person["event_metric_differences"]["false_alarms_per_24_observed_hours"]
        self.assertEqual(false_alarm_delta["candidate_minus_reference"], 864000 / (record_count * 2000))
        self.assertEqual(self.result["counts"]["observed_ticks"], 686 * 2000)

    def test_reference_scorer_outputs_remain_intact(self):
        admission, policy, _, reference, _, bindings = self.fixture
        expected = self.core.evaluate(admission, policy, reference,
            expected_policy_sha256=bindings["expected_policy_sha256"], limits=bindings["limits"])
        self.assertEqual(self.result["evaluations"]["reference"], expected)
        for arm in self.result["evaluations"].values():
            self.assertEqual(len(arm["record_results"]), 686)
            self.assertFalse(arm["verification"]["scientific_qualification"])
            self.assertIn("all_positive_control", arm["constant_controls"])

    def test_zero_difference_for_identical_submissions(self):
        fixture = copy.deepcopy(self.fixture)
        fixture = (*fixture[:4], fixture[3], {**fixture[5],
            "expected_candidate_recipe_sha256": fixture[3]["recipe_sha256"]})
        result = self.run_comparison(fixture)
        self.assertEqual(result["primary"]["candidate_minus_reference"], 0)
        for metric in result["patient_macro_event_metric_differences"].values():
            self.assertEqual(metric["candidate_minus_reference"], 0)

    def test_undefined_person_is_not_dropped(self):
        admission, policy, support, reference, candidate, bindings = copy.deepcopy(self.fixture)
        for row in admission["records"]:
            if row["biological_person"] == "chb02":
                row["reference_intervals"] = []
                row["annotation_status"] = "explicit_zero_events"
        for arm in (reference, candidate):
            for row in arm["records"]:
                if row["biological_person"] == "chb02":
                    row["score_runs"] = [[0, 2000, 0]]
                    row["predicted_intervals"] = []
        result = self.run_comparison((admission, policy, support, reference, candidate, bindings))
        self.assertIsNone(result["primary"]["candidate_minus_reference"])
        self.assertEqual(result["undefined_paired_people"]["f1"], ["chb02"])
        self.assertEqual(len(result["paired_people"]), 23)

    def test_both_arm_coverage_recipe_and_fold_checks_precede_private_admission(self):
        mutations = (
            lambda arm: arm["records"].pop(),
            lambda arm: arm["records"][0].update(fold_id="chb21"),
            lambda arm: arm.update(recipe_sha256="0" * 64),
            lambda arm: arm["records"][0]["score_runs"].__setitem__(-1, [400, 1999, 0]),
            lambda arm: arm.update(support_sha256="0" * 64),
        )
        for position in (3, 4):
            for mutate in mutations:
                with self.subTest(arm=position, mutation=mutate):
                    fixture = list(copy.deepcopy(self.fixture))
                    mutate(fixture[position])
                    fixture[0] = object()  # Cannot be inspected as private admission.
                    with mock.patch.object(self.core, "evaluate", side_effect=AssertionError("private scoring")):
                        with self.assertRaises(self.core.CandidateError):
                            self.run_comparison(fixture)

    def test_public_support_change_cannot_change_private_denominator(self):
        fixture = list(copy.deepcopy(self.fixture))
        fixture[0]["records"][0]["observed_ticks"] += 1
        with mock.patch.object(self.core, "evaluate", side_effect=AssertionError("private scoring")):
            with self.assertRaisesRegex(self.core.AdmissionError, "Private admission and public support differ"):
                self.run_comparison(fixture)

    def test_inputs_unchanged_and_no_superiority_claim(self):
        before = self.core.canonical_sha256(self.fixture)
        self.run_comparison(self.fixture)
        self.assertEqual(self.core.canonical_sha256(self.fixture), before)
        self.assertIsNone(self.result["statistical_superiority"])
        self.assertFalse(self.result["scientific_qualification"])

    def command(self):
        args = []
        for name in ("admission", "reference", "candidate", "policy", "support", "limits", "output"):
            args += ["--" + name, str(ROOT / ("generated-not-created-" + name + ".json"))]
        bindings = self.fixture[5]
        for name in ("expected_policy_sha256", "expected_reference_recipe_sha256", "expected_candidate_recipe_sha256"):
            args += ["--" + name.replace("_", "-"), bindings[name]]
        return args + ["--max-input-bytes", "2000000", "--max-output-bytes", "4000000"]

    def test_cli_bad_either_arm_never_opens_private_reference(self):
        for bad_arm in ("reference", "candidate"):
            with self.subTest(arm=bad_arm):
                admission, policy, support, reference, candidate, bindings = copy.deepcopy(self.fixture)
                values = dict(admission=admission, policy=policy, support=support,
                              reference=reference, candidate=candidate, limits=bindings["limits"])
                values[bad_arm]["recipe_sha256"] = "0" * 64
                opened = []
                def read(path, cap):
                    role = Path(path).stem.removeprefix("generated-not-created-")
                    opened.append(role)
                    if role == "admission":
                        raise AssertionError("Private reference opened")
                    return values[role]
                with mock.patch.object(comparison, "load_predecessor", return_value=(self.core, self.cli)), \
                     mock.patch.object(self.cli, "read_json", side_effect=read), \
                     mock.patch.object(self.cli, "write_output") as output, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(comparison.main(self.command()), 2)
                    self.assertNotIn("admission", opened)
                    output.assert_not_called()

    def test_cli_real_compare_and_result_dispatch(self):
        admission, policy, support, reference, candidate, bindings = self.fixture
        values = dict(admission=admission, policy=policy, support=support,
                      reference=reference, candidate=candidate, limits=bindings["limits"])
        opened = []
        def read(path, cap):
            role = Path(path).stem.removeprefix("generated-not-created-")
            opened.append(role)
            return values[role]
        with mock.patch.object(comparison, "load_predecessor", return_value=(self.core, self.cli)), \
             mock.patch.object(self.cli, "read_json", side_effect=read), \
             mock.patch.object(self.cli, "write_output") as output, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(comparison.main(self.command()), 0)
            self.assertEqual(opened[-1], "admission")
            self.assertEqual(output.call_args.args[1], self.result)

    def test_changed_predecessor_refuses_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "cli.py").write_bytes(b"raise RuntimeError('not executed')\n")
            with self.assertRaisesRegex(ValueError, "Predecessor loader identity mismatch"):
                comparison.load_predecessor(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predecessor", type=Path, default=ROOT.parent / "seizure-events-v1")
    args, remaining = parser.parse_known_args()
    PREDECESSOR = args.predecessor
    unittest.main(argv=[__file__, *remaining])
else:
    PREDECESSOR = ROOT.parent / "seizure-events-v1"
