"""Generated software controls only; no authentic labels, EEG or model trial."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural009_diagnostics_test", ROOT / "diagnostics.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
core, _ = d.load_predecessor()


def complete_fixture():
    index, people, digest = core.source_index()
    policy = core.recommended_policy()
    admission = {"schema": "neural009_admission_v1", "task_id": "NEURAL-009",
                 "source_index_sha256": digest, "public_development_only": True,
                 "normalization_recipe_sha256": "1" * 64, "clock_review_sha256": "2" * 64,
                 "rights_review_sha256": "3" * 64, "folds": core._folds(people), "records": []}
    candidate = {"schema": "neural009_candidate_v1", "task_id": "NEURAL-009",
                 "source_index_sha256": digest, "policy_sha256": core.canonical_sha256(policy),
                 "support_sha256": "0" * 64, "recipe_sha256": "4" * 64, "records": []}
    seen = set()
    for identifier, source in sorted(index.items()):
        person = source["biological_person"]
        folder = identifier.split("/")[0]
        first = folder not in seen
        seen.add(folder)
        reference = [[1000, 1100]] if first else []
        # One missed event in the alias folder, whose person is still chb01.
        prediction = [[1020, 1030]] if first and folder != "chb21" else []
        runs = [[0, 1020, 0.0], [1020, 1030, 1.0], [1030, 2000, 0.0]] if prediction else [[0, 2000, 0.0]]
        admission["records"].append({
            "recording_id": identifier, "biological_person": person,
            "edf_sha256": source["publisher_sha256"], "edf_header_sha256": "5" * 64,
            "annotation_sha256": "6" * 64,
            "annotation_status": "explicit_events" if reference else "explicit_zero_events",
            "native_sample_rate_hz": 256, "native_sample_count": 51200, "observed_ticks": 2000,
            "channels": [{"label": "invented EEG", "role": "eeg"}], "predictor_channels": [0],
            "reference_intervals": reference})
        candidate["records"].append({"recording_id": identifier, "biological_person": person,
                                    "fold_id": person, "score_runs": runs, "predicted_intervals": prediction})
    candidate["support_sha256"] = core.canonical_sha256(core.public_support(admission))
    limits = {"max_record_ticks": 2000, "max_total_ticks": 686 * 2000, "max_prediction_segments": 2000}
    return admission, policy, candidate, limits


class RawAndProcessedControls(unittest.TestCase):
    def diagnose(self, ref, hyp, ticks=3000):
        return d.diagnose_record(ref, hyp, ticks, _core=core)

    def test_early_only_credit_is_a_raw_miss(self):
        result = self.diagnose([[1000, 1100]], [[800, 810]])
        self.assertEqual(result["summary"]["raw_event_misses"], 1)
        self.assertIsNone(result["raw_events"][0]["decision_delay_seconds"])
        self.assertEqual(result["processed_events"][0]["credit_location"], "early_only")

    def test_late_only_credit_and_half_open_boundary(self):
        result = self.diagnose([[1000, 1100]], [[1100, 1110]])
        self.assertEqual(result["summary"]["raw_event_misses"], 1)
        self.assertEqual(result["processed_events"][0]["credit_location"], "late_only")

    def test_disjoint_early_and_late_credit_strict_merge_gap(self):
        result = self.diagnose([[1000, 1100]], [[700, 701], [1601, 1602]])
        self.assertEqual(result["processed_events"][0]["credit_location"], "early_and_late_only")
        merged = self.diagnose([[1000, 1100]], [[700, 701], [1600, 1601]])
        row = merged["processed_events"][0]
        self.assertEqual(row["credit_location"], "within_processed_reference")
        self.assertTrue(row["credited_without_raw_seizure_overlap"])
        self.assertEqual(merged["summary"]["raw_event_misses"], 1)

    def test_reference_merge_gap_is_not_an_actual_seizure(self):
        result = self.diagnose([[1000, 1010], [1500, 1510]], [[1300, 1310]])
        self.assertEqual(result["summary"]["raw_event_misses"], 2)
        self.assertEqual(result["summary"]["processed_event_count"], 1)
        self.assertTrue(result["processed_events"][0]["credited_without_raw_seizure_overlap"])

    def test_decision_delay_is_bin_endpoint_not_start(self):
        event = self.diagnose([[1000, 1100]], [[1020, 1030]])["raw_events"][0]
        self.assertEqual(event["first_positive_decision_tick"], 1021)
        self.assertEqual(event["decision_delay_seconds"], 2.1)
        self.assertEqual(event["positive_run_start_offset_seconds"], 2)
        self.assertFalse(event["alarm_already_active_before_onset"])

    def test_all_positive_does_not_become_a_new_onset_alarm(self):
        result = self.diagnose([[1000, 1100]], [[0, 3000]])
        event = result["raw_events"][0]
        self.assertEqual(event["decision_delay_seconds"], 0.1)
        self.assertEqual(event["positive_run_start_offset_seconds"], -100)
        self.assertTrue(event["alarm_already_active_before_onset"])
        self.assertEqual(result["summary"]["already_active_alarm_count"], 1)

    def test_adjacent_positive_segments_have_one_alarm_transition(self):
        event = self.diagnose([[1000, 1100]], [[900, 1000], [1000, 1020]])["raw_events"][0]
        self.assertEqual(event["positive_run_start_offset_seconds"], -10)
        self.assertTrue(event["alarm_already_active_before_onset"])

    def test_final_bin_and_record_boundary(self):
        final = self.diagnose([[2999, 3000]], [[2999, 3000]])
        self.assertEqual(final["raw_events"][0]["first_positive_decision_tick"], 3000)
        self.assertEqual(final["raw_events"][0]["decision_delay_seconds"], 0.1)
        left = self.diagnose([[2999, 3000]], [])
        right = self.diagnose([], [[0, 1]])
        self.assertEqual(left["summary"]["raw_event_misses"], 1)
        self.assertEqual(right["summary"]["raw_event_count"], 0)
        self.assertEqual(left["summary"]["processed_event_credit_counts"]["not_credited"], 1)

    def test_undefined_and_miss_denominators_remain_visible(self):
        empty = self.diagnose([], [])
        self.assertIsNone(empty["summary"]["raw_event_overlap_fraction"])
        self.assertIsNone(empty["summary"]["conditional_decision_delay_seconds"]["mean"])
        result = self.diagnose([[100, 200], [1500, 1600]], [[120, 130]])
        summary = result["summary"]
        self.assertEqual(summary["raw_event_overlap_fraction"], 0.5)
        self.assertEqual(summary["raw_event_misses"], 1)
        self.assertEqual(summary["conditional_decision_delay_seconds"]["denominator_detected_raw_events"], 1)
        self.assertEqual(summary["conditional_decision_delay_seconds"]["mean"], 2.1)

    def test_split_processed_events_do_not_duplicate_raw_event_delays(self):
        result = self.diagnose([[0, 6000]], [[0, 1]], ticks=6000)
        self.assertEqual(len(result["raw_events"]), 1)
        self.assertEqual(len(result["processed_events"]), 2)
        self.assertEqual(result["summary"]["raw_events_with_in_event_positive_bin"], 1)

    def test_invalid_intervals_rejected(self):
        for ref, hyp in (([[1.1, 2]], []), ([[1, 4], [3, 5]], []), ([], [[3, 2]]), ([], [[0, 3001]])):
            with self.subTest(ref=ref, hyp=hyp), self.assertRaises(ValueError):
                self.diagnose(ref, hyp)

    def test_interval_queries_against_independent_binary_mask(self):
        rng = random.Random(901)
        for _ in range(20):
            mask = [rng.randrange(2) for _ in range(40)]
            intervals, start = [], None
            for i, bit in enumerate(mask + [0]):
                if bit and start is None:
                    start = i
                elif not bit and start is not None:
                    intervals.append([start, i])
                    start = None
            union = d.IntervalUnion(intervals)
            for a in range(41):
                for b in range(a, 41):
                    self.assertEqual(union.overlap(a, b), sum(mask[a:b]))
                    first = next((i for i in range(a, b) if mask[i]), None)
                    hit = union.first(a, b)
                    self.assertEqual(hit[0] if hit else None, first)


class CompleteCohortControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admission, cls.policy, cls.candidate, cls.limits = complete_fixture()
        cls.result = d.evaluate(cls.admission, cls.policy, cls.candidate,
                               expected_policy_sha256=core.canonical_sha256(cls.policy), limits=cls.limits)

    def test_primary_result_exactly_preserved(self):
        expected = core.evaluate(self.admission, self.policy, self.candidate,
                                 expected_policy_sha256=core.canonical_sha256(self.policy), limits=self.limits)
        self.assertEqual(self.result["primary_evaluation"], expected)
        self.assertEqual(len(self.result["record_diagnostics"]), 686)

    def test_person_alias_and_macro_denominator(self):
        arm = self.result["arm_diagnostics"]["candidate"]
        patients = {r["biological_person"]: r for r in arm["patients"]}
        self.assertEqual(len(patients), 23)
        self.assertNotIn("chb21", patients)
        self.assertEqual(patients["chb01"]["raw_event_count"], 2)
        self.assertEqual(patients["chb01"]["raw_event_misses"], 1)
        self.assertAlmostEqual(arm["patient_macro_raw_event_overlap_fraction"], 45 / 46)
        self.assertEqual(arm["pooled_diagnostic"]["raw_event_overlap_fraction"], 23 / 24)

    def test_constant_controls_same_support(self):
        negative = self.result["arm_diagnostics"]["all_negative_control"]["pooled_diagnostic"]
        positive = self.result["arm_diagnostics"]["all_positive_control"]["pooled_diagnostic"]
        self.assertEqual(negative["raw_event_misses"], 24)
        self.assertEqual(positive["raw_event_misses"], 0)
        self.assertEqual(positive["already_active_alarm_count"], 24)
        self.assertEqual(positive["observed_ticks"], 686 * 2000)

    def test_partial_population_refused(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["records"].pop()
        with self.assertRaises(ValueError):
            d.evaluate(self.admission, self.policy, candidate,
                       expected_policy_sha256=core.canonical_sha256(self.policy), limits=self.limits)

    def test_cli_preflight_precedes_private_open_and_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {"admission": self.admission, "candidate": self.candidate,
                      "policy": self.policy, "limits": self.limits,
                      "support": core.public_support(self.admission)}
            for name, value in values.items():
                (root / (name + ".json")).write_text(json.dumps(value))
            def command(output):
                return [sys.executable, "-B", str(ROOT / "diagnostics.py"),
                        *[part for name in values for part in ("--" + name, str(root / (name + ".json")))],
                        "--output", str(root / output), "--expected-policy-sha256", core.canonical_sha256(self.policy),
                        "--max-input-bytes", "2000000", "--max-output-bytes", "10000000"]
            good = subprocess.run(command("result.json"), capture_output=True, text=True, timeout=30)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads((root / "result.json").read_text()), self.result)
            invalid = copy.deepcopy(self.candidate)
            invalid["support_sha256"] = "0" * 64
            (root / "candidate.json").write_text(json.dumps(invalid))
            (root / "admission.json").unlink()
            bad = subprocess.run(command("refused.json"), capture_output=True, text=True, timeout=30)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("public observation support", bad.stderr)
            self.assertNotIn("FileNotFoundError", bad.stderr)
            self.assertFalse((root / "refused.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
