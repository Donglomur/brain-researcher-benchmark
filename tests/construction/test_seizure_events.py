"""Independent generated controls for NEURAL-009's conditional evaluator.

Expected event counts and rational macro values were frozen before reading the
implementation. The complete 686-name fixture uses invented one-hour recordings,
labels and scores. It verifies source behavior, never authentic EEG agreement.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE = (REPOSITORY / "benchmarks/neural/NEURAL-009/implementations"
           / "seizure-events-v1")
SPEC = importlib.util.spec_from_file_location("neural009_test_core", PACKAGE / "core.py")
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def score_runs(intervals, ticks=36000, positive=1.0):
    """Encode hand-selected intervals as complete scores, independent of scorer."""
    rows, end = [], 0
    for start, stop in intervals:
        if start > end:
            rows.append([end, start, 0.0])
        rows.append([start, stop, positive])
        end = stop
    if end < ticks:
        rows.append([end, ticks, 0.0])
    return rows


def complete_fixture():
    index, actual_people, source_sha = core.source_index()
    people = [f"chb{i:02d}" for i in range(1, 25) if i != 21]
    assert actual_people == people
    assert len(index) == 686
    policy = core.recommended_policy()
    policy_sha = core.canonical_sha256(policy)
    admissions, predictions, first_by_person, first_chb21 = [], [], {}, False
    for path in sorted(index):
        folder = path.split("/", 1)[0]
        person = "chb01" if folder == "chb21" else folder
        assert index[path]["biological_person"] == person
        references, hypotheses = [], []
        if person not in first_by_person:
            first_by_person[person] = path
            references = [[10000, 11000]]
            hypotheses = [[10000, 11000]]
            if person == "chb01":
                hypotheses += [[20000, 20100], [30000, 30100]]
        if folder == "chb21" and not first_chb21:
            first_chb21 = True
            references = [[10000, 11000]]
            hypotheses = []
        admissions.append({
            "recording_id": path, "biological_person": person,
            "edf_sha256": index[path]["publisher_sha256"],
            "edf_header_sha256": digest("invented-header:" + path),
            "annotation_sha256": digest("invented-labels:" + path),
            "annotation_status": "explicit_events" if references else "explicit_zero_events",
            "native_sample_rate_hz": 256, "native_sample_count": 921600,
            "observed_ticks": 36000,
            # Repeated bipolar labels are valid declarations; channel identity
            # uses indices and must not silently collapse them.
            "channels": [{"label": "T8-P8", "role": "eeg"},
                         {"label": "T8-P8", "role": "eeg"},
                         {"label": "EDF Annotations", "role": "annotation"}],
            "predictor_channels": [0, 1], "reference_intervals": references,
        })
        predictions.append({
            "recording_id": path, "biological_person": person, "fold_id": person,
            "score_runs": score_runs(hypotheses), "predicted_intervals": hypotheses,
        })
    admission = {
        "schema": "neural009_admission_v1", "task_id": "NEURAL-009",
        "source_index_sha256": source_sha, "public_development_only": True,
        "normalization_recipe_sha256": digest("invented-normalization"),
        "clock_review_sha256": digest("invented-clock-review"),
        "rights_review_sha256": digest("invented-rights-review"),
        "folds": [{"id": p, "train_people": [q for q in people if q != p],
                   "test_people": [p]} for p in people],
        "records": admissions,
    }
    candidate = {
        "schema": "neural009_candidate_v1", "task_id": "NEURAL-009",
        "source_index_sha256": source_sha, "policy_sha256": policy_sha,
        "support_sha256": core.canonical_sha256(core.public_support(admission)),
        "recipe_sha256": digest("invented-frozen-predictor"), "records": predictions,
    }
    limits = {"max_record_ticks": 36000, "max_total_ticks": 686 * 36000,
              "max_prediction_segments": sum(len(r["score_runs"]) for r in predictions)}
    return admission, policy, candidate, limits


def evaluate(admission, policy, candidate, limits):
    return core.evaluate(admission, policy, candidate,
                         expected_policy_sha256=core.canonical_sha256(policy), limits=limits)


class RecordEventSemantics(unittest.TestCase):
    def setUp(self):
        self.policy = core.recommended_policy()
        self.policy.update(tolerance_start_seconds=0, tolerance_end_seconds=0,
                           minimum_overlap=0, merge_gap_seconds=0, maximum_event_seconds=300)

    def check_counts(self, references, predictions, expected, *, ticks=600, policy=None):
        result = core.evaluate_record(references, predictions, ticks, policy or self.policy)
        actual = (result["processed_reference_events"], result["true_positives"],
                  result["false_positives"])
        self.assertEqual(actual, expected)
        return result

    def test_one_hypothesis_can_detect_two_references(self):
        r = self.check_counts([[100, 200], [300, 400]], [[150, 350]], (2, 2, 0))
        self.assertEqual(r["event_metrics"]["f1"], 1)

    def test_two_hypotheses_hitting_one_reference_are_not_duplicate_false_alarms(self):
        self.check_counts([[100, 300]], [[110, 150], [200, 250]], (1, 1, 0))

    def test_touching_endpoint_is_not_overlap(self):
        self.check_counts([[100, 200]], [[200, 300]], (1, 0, 1))

    def test_last_observed_bin_is_scored(self):
        self.check_counts([[599, 600]], [[599, 600]], (1, 1, 0))

    def test_merge_gap_is_strict(self):
        self.policy["merge_gap_seconds"] = 10
        r = self.check_counts([[100, 200], [300, 400]], [[100, 200]], (2, 1, 0))
        self.assertAlmostEqual(r["event_metrics"]["f1"], 2 / 3)
        self.check_counts([[100, 200], [299, 400]], [[100, 200]], (1, 1, 0))

    def test_duration_split_changes_reference_count(self):
        self.policy["maximum_event_seconds"] = 20
        r = self.check_counts([[0, 600]], [[0, 200]], (3, 1, 0))
        self.assertEqual(r["event_metrics"]["f1"], 0.5)

    def test_tolerance_is_clipped_to_each_record(self):
        self.policy.update(tolerance_start_seconds=100, tolerance_end_seconds=100)
        left = self.check_counts([[500, 600]], [], (1, 0, 0))
        right = self.check_counts([], [[0, 100]], (0, 0, 1))
        self.assertEqual(left["observed_ticks"] + right["observed_ticks"], 1200)
        # Two minute-long files contribute 120 seconds even if their wall clocks
        # are separated by hours. Their tolerance masks never cross the boundary.
        self.assertEqual(Fraction(864000, 1200), 720)

    def test_extended_reference_duration_is_overlap_denominator(self):
        self.policy.update(tolerance_start_seconds=10, tolerance_end_seconds=10,
                           minimum_overlap=0.5)
        self.check_counts([[100, 200]], [[100, 200]], (1, 0, 1))

    def test_overlap_fraction_must_exceed_threshold_plus_epsilon(self):
        self.policy["minimum_overlap"] = 0.5
        self.check_counts([[100, 200]], [[100, 150]], (1, 0, 1))
        self.check_counts([[100, 200]], [[100, 151]], (1, 1, 0))

    def test_no_event_metrics_are_explicitly_undefined(self):
        r = self.check_counts([], [], (0, 0, 0))
        for metric in ("f1", "sensitivity", "precision"):
            self.assertIsNone(r["event_metrics"][metric])
        self.assertEqual(r["event_metrics"]["false_alarms_per_24_observed_hours"], 0)

    def test_low_level_policy_refuses_undefined_or_off_grid_parameters(self):
        mutations = [("maximum_event_seconds", 0), ("merge_gap_seconds", -1),
                     ("tolerance_start_seconds", 0.05), ("minimum_overlap", 1.01),
                     ("minimum_overlap", float("nan")), ("tolerance_end_seconds", True)]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                policy = dict(self.policy)
                policy[key] = value
                with mock.patch.object(core, "_upstream", side_effect=AssertionError("scoring reached")):
                    with self.assertRaises(core.PolicyError):
                        core.evaluate_record([[100, 200]], [[100, 200]], 600, policy)

    def test_sample_diagnostics_expose_per_record_constant_positive_weakness(self):
        r = self.check_counts([[100, 200]], [[0, 600]], (1, 1, 0))
        self.assertEqual(r["event_metrics"]["f1"], 1)
        self.assertEqual(r["sample_true_positive_ticks"], 100)
        self.assertEqual(r["sample_false_positive_ticks"], 500)


class CompleteCohortControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admission, cls.policy, cls.candidate, cls.limits = complete_fixture()
        cls.result = evaluate(cls.admission, cls.policy, cls.candidate, cls.limits)

    def copies(self):
        return copy.deepcopy((self.admission, self.policy, self.candidate, self.limits))

    def test_complete_patient_macro_result_matches_independent_fractions(self):
        r = self.result
        self.assertEqual(r["counts"]["recordings"], 686)
        self.assertEqual(r["counts"]["biological_people"], 23)
        self.assertEqual(r["counts"]["folds"], 23)
        self.assertEqual(r["counts"]["observed_ticks"], 24696000)
        self.assertEqual(len(r["record_results"]), 686)
        self.assertAlmostEqual(r["primary"]["value"], 112 / 115)
        macro = r["candidate"]["patient_macro_event_metrics"]
        self.assertAlmostEqual(macro["sensitivity"], 45 / 46)
        self.assertAlmostEqual(macro["false_alarms_per_24_observed_hours"], 16 / 575)
        pooled = r["candidate"]["pooled_diagnostic"]
        self.assertEqual((pooled["processed_reference_events"], pooled["true_positives"],
                          pooled["false_positives"]), (24, 23, 2))
        self.assertAlmostEqual(pooled["event_metrics"]["f1"], 46 / 49)
        self.assertAlmostEqual(pooled["event_metrics"]["false_alarms_per_24_observed_hours"], 24 / 343)
        self.assertEqual(pooled["sample_reference_positive_ticks"], 24000)
        self.assertEqual(pooled["sample_true_positive_ticks"], 23000)
        self.assertEqual(pooled["sample_false_positive_ticks"], 200)

    def test_alias_is_pooled_before_macro_aggregation(self):
        people = {r["biological_person"]: r for r in self.result["candidate"]["patients"]}
        self.assertNotIn("chb21", people)
        alias = people["chb01"]
        self.assertEqual(alias["observed_ticks"], 75 * 36000)
        self.assertEqual((alias["processed_reference_events"], alias["true_positives"],
                          alias["false_positives"]), (2, 1, 2))
        self.assertEqual(alias["event_metrics"]["f1"], 0.4)

    def test_complete_background_counts_against_constant_positive_control(self):
        control = self.result["constant_controls"]["all_positive_control"]["pooled_diagnostic"]
        self.assertEqual(control["processed_predicted_events"], 8232)
        self.assertEqual((control["processed_reference_events"], control["true_positives"],
                          control["false_positives"]), (24, 24, 8208))
        self.assertAlmostEqual(control["event_metrics"]["f1"], 1 / 172)
        self.assertAlmostEqual(control["sample_diagnostics"]["precision"], 1 / 1029)
        self.assertAlmostEqual(control["sample_diagnostics"]["f1"], 1 / 515)
        negative = self.result["constant_controls"]["all_negative_control"]
        self.assertEqual(negative["patient_macro_event_metrics"]["f1"], 0)
        self.assertEqual(negative["patient_macro_event_metrics"]["sensitivity"], 0)

    def test_generated_source_result_never_promotes_scientific_qualification(self):
        verification = self.result["verification"]
        for key in ("authentic_signal_payloads_verified", "normalization_independently_verified",
                    "physical_target_privacy_verified", "training_or_causal_context_verified",
                    "signal_derived_reference_competence_verified", "native_runtime_qualified",
                    "scientific_qualification"):
            self.assertIs(verification[key], False)
        json.dumps(self.result, allow_nan=False)

    def test_reference_only_changes_do_not_change_candidate_binding(self):
        admission, policy, candidate, limits = self.copies()
        before = core.public_support(admission)
        row = next(r for r in admission["records"]
                   if r["biological_person"] == "chb02" and r["reference_intervals"])
        row["reference_intervals"] = []
        row["annotation_status"] = "explicit_zero_events"
        row["annotation_sha256"] = digest("changed invented operator labels")
        admission["clock_review_sha256"] = digest("changed operator clock evidence")
        self.assertEqual(core.public_support(admission), before)
        self.assertEqual(candidate["support_sha256"], core.canonical_sha256(before))
        # All labels for this person are now empty. A valid all-negative response
        # makes that person's event F1 undefined; do not drop the person silently.
        for prediction in candidate["records"]:
            if prediction["biological_person"] == "chb02":
                prediction["score_runs"] = [[0, 36000, 0.0]]
                prediction["predicted_intervals"] = []
        result = evaluate(admission, policy, candidate, limits)
        self.assertIsNone(result["primary"]["value"])
        self.assertEqual(result["candidate"]["undefined_patient_metrics"]["f1"], ["chb02"])
        self.assertEqual(result["counts"]["biological_people"], 23)

    def test_threshold_equality_and_adjacent_positive_runs_are_merged(self):
        admission, policy, candidate, limits = self.copies()
        row = next(r for r in candidate["records"]
                   if r["biological_person"] == "chb02" and r["predicted_intervals"])
        row["score_runs"] = [[0, 10000, 0.49], [10000, 10500, 0.5],
                             [10500, 11000, 0.51], [11000, 36000, 0.49]]
        limits["max_prediction_segments"] += 1
        result = evaluate(admission, policy, candidate, limits)
        self.assertAlmostEqual(result["primary"]["value"], 112 / 115)
        scored = next(r for r in result["record_results"] if r["recording_id"] == row["recording_id"])
        self.assertEqual(scored["raw_predicted_events"], 1)

    def test_candidate_missing_duplicate_unknown_alias_and_fold_are_rejected(self):
        changes = {
            "missing": lambda c: c["records"].pop(),
            "duplicate": lambda c: c["records"].__setitem__(-1, copy.deepcopy(c["records"][0])),
            "unknown": lambda c: c["records"][0].__setitem__("recording_id", "chb99/unknown.edf"),
            "alias": lambda c: next(r for r in c["records"] if r["recording_id"].startswith("chb21/"))
                .__setitem__("biological_person", "chb21"),
            "wrong_fold": lambda c: c["records"][0].__setitem__("fold_id", "chb24"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.candidate)
                change(candidate)
                with self.assertRaises(core.CandidateError):
                    core.validate_candidate(candidate)

    def test_public_malformed_runs_fail_without_operator_source_work(self):
        cases = [
            [[1, 36000, 0]], [[0, 100, 0], [101, 36000, 0]],
            [[0, 100, 0], [99, 36000, 0]], [[0, 0, 0], [0, 36000, 0]],
            [[False, 36000, 0]], [[0, 36000, True]], [[0, 36000, float("nan")]],
            [[0, 36000, float("inf")]], [[0, 36000, -0.1]], [[0, 36000, 1.1]],
        ]
        for runs in cases:
            with self.subTest(runs=runs):
                candidate = copy.deepcopy(self.candidate)
                candidate["records"][0]["score_runs"] = runs
                with mock.patch.object(core, "_admit", side_effect=AssertionError("operator reference reached")):
                    with self.assertRaises(core.CandidateError):
                        evaluate(None, self.policy, candidate, self.limits)

    def test_declared_intervals_and_complete_sample_coverage_are_checked(self):
        for name in ("truncated", "wrong_intervals"):
            with self.subTest(name=name):
                admission, policy, candidate, limits = self.copies()
                row = next(r for r in candidate["records"] if not r["predicted_intervals"])
                if name == "truncated":
                    row["score_runs"][-1][1] -= 1
                else:
                    row["predicted_intervals"] = [[10, 20]]
                with mock.patch.object(core, "_upstream", side_effect=AssertionError("scoring reached")):
                    with self.assertRaises(core.CandidateError):
                        evaluate(admission, policy, candidate, limits)

    def test_no_private_annotation_or_unknown_fields_are_accepted_from_candidate(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["records"][0]["reference_intervals"] = [[10000, 11000]]
        with self.assertRaises(core.CandidateError):
            core.validate_candidate(candidate)

    def test_operator_identity_clock_annotation_and_channel_gates(self):
        changes = {
            "missing": lambda a: a["records"].pop(),
            "publisher": lambda a: a["records"][0].__setitem__("edf_sha256", "0" * 64),
            "noninteger_rate": lambda a: a["records"][0].__setitem__("native_sample_rate_hz", True),
            "inconsistent_clock": lambda a: a["records"][0].__setitem__("native_sample_count", 921601),
            "absent_labels": lambda a: a["records"][0].__setitem__("annotation_status", "unknown"),
            "out_of_bounds_label": lambda a: a["records"][0].__setitem__("reference_intervals", [[35999, 36001]]),
            "label_predictor": lambda a: a["records"][0].__setitem__("predictor_channels", [2]),
            "split_leakage": lambda a: a["folds"][0]["train_people"].append(a["folds"][0]["id"]),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                admission, policy, candidate, limits = self.copies()
                change(admission)
                candidate["support_sha256"] = core.canonical_sha256(core.public_support(admission))
                with mock.patch.object(core, "_upstream", side_effect=AssertionError("scoring reached")):
                    with self.assertRaises(core.AdmissionError):
                        evaluate(admission, policy, candidate, limits)

    def test_policy_change_or_binding_mismatch_is_refused(self):
        admission, policy, candidate, limits = self.copies()
        policy["threshold"] = 0.25
        with self.assertRaises(core.PolicyError):
            evaluate(admission, policy, candidate, limits)
        with self.assertRaises(core.PolicyError):
            core.evaluate(self.admission, self.policy, self.candidate,
                          expected_policy_sha256="0" * 64, limits=self.limits)

    def test_resource_limits_refuse_before_upstream_allocation(self):
        for field in ("max_record_ticks", "max_total_ticks", "max_prediction_segments"):
            with self.subTest(field=field):
                limits = dict(self.limits)
                limits[field] -= 1
                with mock.patch.object(core, "_upstream", side_effect=AssertionError("scoring reached")):
                    with self.assertRaises((core.AdmissionError, core.CandidateError)):
                        evaluate(self.admission, self.policy, self.candidate, limits)


class SourceIdentityControls(unittest.TestCase):
    def test_modified_upstream_source_is_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            vendor = root / "vendor/timescoring"
            vendor.mkdir(parents=True)
            for filename in ("annotations.py", "scoring.py"):
                body = (PACKAGE / "vendor/timescoring" / filename).read_bytes()
                if filename == "scoring.py":
                    body += b"\n# altered evaluator source\n"
                (vendor / filename).write_bytes(body)
            with mock.patch.object(core, "ROOT", root):
                with self.assertRaises(core.SourceError):
                    core.evaluate_record([[100, 200]], [[100, 200]], 600,
                                         {"tolerance_start_seconds": 0,
                                          "tolerance_end_seconds": 0,
                                          "minimum_overlap": 0,
                                          "maximum_event_seconds": 300,
                                          "merge_gap_seconds": 0})

    def test_modified_identity_index_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            data = json.loads((PACKAGE / "record_index.json").read_text())
            data["recordings"][0]["publisher_sha256"] = "0" * 64
            (root / "record_index.json").write_text(json.dumps(data))
            with mock.patch.object(core, "ROOT", root):
                with self.assertRaises(core.SourceError):
                    core.source_index()

    def test_modified_recommended_policy_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            data = json.loads((PACKAGE / "recommended_policy.json").read_text())
            data["threshold"] = 0.25
            (root / "recommended_policy.json").write_text(json.dumps(data))
            with mock.patch.object(core, "ROOT", root):
                with self.assertRaises(core.SourceError):
                    core.recommended_policy()


class CommandLineControls(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        admission, policy, candidate, limits = complete_fixture()
        self.policy_sha = core.canonical_sha256(policy)
        self.manifest_sha = hashlib.sha256((PACKAGE / "source_manifest.json").read_bytes()).hexdigest()
        values = {"admission": admission, "policy": policy, "candidate": candidate,
                  "limits": limits, "support": core.public_support(admission)}
        self.paths = {name: self.root / (name + ".json") for name in values}
        for name, value in values.items():
            self.paths[name].write_text(json.dumps(value, allow_nan=False))
        self.output = self.root / "result.json"

    def command(self, *, package=PACKAGE, manifest_sha=None):
        # Use this suite's selected dependency environment. Some supported local
        # interpreters provide NumPy in their user site; isolation would hide that
        # already-installed dependency rather than test the CLI's behavior.
        args = [sys.executable, "-B", str(package / "cli.py"), "evaluate",
                "--expected-manifest-sha256", manifest_sha or self.manifest_sha,
                "--expected-policy-sha256", self.policy_sha,
                "--max-input-bytes", "2000000", "--max-output-bytes", "3000000",
                "--output", str(self.output)]
        for name, path in self.paths.items():
            args.extend(["--" + name, str(path)])
        return args

    def invoke(self, **kwargs):
        return subprocess.run(self.command(**kwargs), capture_output=True, text=True,
                              timeout=10, check=False)

    def test_valid_cli_evaluates_complete_fixture(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.output.read_text())
        self.assertAlmostEqual(report["primary"]["value"], 112 / 115)
        self.assertEqual(report["counts"]["recordings"], 686)
        self.assertIs(report["verification"]["scientific_qualification"], False)

    def test_invalid_candidate_is_rejected_before_missing_private_reference(self):
        self.paths["candidate"].write_text("{}")
        self.paths["admission"].unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr)
        self.assertEqual(error["error_type"], "CandidateError")
        self.assertIn("Candidate", error["reason"])
        self.assertFalse(self.output.exists())

    def test_wrong_candidate_policy_is_rejected_before_private_fifo_open(self):
        candidate = json.loads(self.paths["candidate"].read_text())
        candidate["policy_sha256"] = "0" * 64
        self.paths["candidate"].write_text(json.dumps(candidate))
        self.paths["admission"].unlink()
        os.mkfifo(self.paths["admission"])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr)
        self.assertEqual(error["error_type"], "CandidateError")
        self.assertIn("frozen policy", error["reason"])
        self.assertFalse(self.output.exists())

    def test_public_support_failure_precedes_private_reference_open(self):
        candidate = json.loads(self.paths["candidate"].read_text())
        row = next(r for r in candidate["records"] if not r["predicted_intervals"])
        row["score_runs"][-1][1] -= 1
        self.paths["candidate"].write_text(json.dumps(candidate))
        self.paths["admission"].unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr)
        self.assertEqual(error["error_type"], "CandidateError")
        self.assertNotIn("No such file", error["reason"])
        self.assertFalse(self.output.exists())

    def test_public_candidate_fifo_is_refused_without_blocking(self):
        self.paths["candidate"].unlink()
        os.mkfifo(self.paths["candidate"])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("regular file", json.loads(result.stderr)["reason"])
        self.assertFalse(self.output.exists())

    def test_json_duplicate_key_is_refused_before_private_reference_open(self):
        self.paths["candidate"].write_text('{"schema": 1, "schema": 2}')
        self.paths["admission"].unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Duplicate JSON", json.loads(result.stderr)["reason"])
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        original = b"existing operator evidence\n"
        self.output.write_bytes(original)
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("new path", json.loads(result.stderr)["reason"])
        self.assertEqual(self.output.read_bytes(), original)

    def test_candidate_byte_budget_refuses_before_private_reference_open(self):
        self.paths["admission"].unlink()
        args = self.command()
        args[args.index("--max-input-bytes") + 1] = "100"
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("byte budget", json.loads(result.stderr)["reason"])
        self.assertFalse(self.output.exists())

    def test_huge_positive_input_cap_does_not_request_a_huge_allocation(self):
        args = self.command()
        args[args.index("--max-input-bytes") + 1] = str(10 ** 100)
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["counts"]["recordings"], 686)
        self.assertEqual(report["counts"]["biological_people"], 23)
        self.assertAlmostEqual(report["primary"]["value"], 112 / 115)
        self.assertIs(report["verification"]["scientific_qualification"], False)

    def test_result_byte_budget_does_not_publish_an_incomplete_artifact(self):
        args = self.command()
        args[args.index("--max-output-bytes") + 1] = "1"
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("output byte budget", json.loads(result.stderr)["reason"])
        self.assertFalse(self.output.exists())

    def test_wrong_manifest_or_changed_source_refuses_execution(self):
        result = self.invoke(manifest_sha="0" * 64)
        self.assertEqual(result.returncode, 2)
        self.assertIn("manifest identity", json.loads(result.stderr)["reason"])
        copied = self.root / "copied-package"
        shutil.copytree(PACKAGE, copied, ignore=shutil.ignore_patterns("__pycache__"))
        path = copied / "core.py"
        original = path.read_bytes()
        changed = original.replace(b"Complete-cohort", b"complete-cohort", 1)
        self.assertNotEqual(changed, original)
        self.assertEqual(len(changed), len(original))
        path.write_bytes(changed)
        result = self.invoke(package=copied)
        self.assertEqual(result.returncode, 2)
        self.assertIn("source member", json.loads(result.stderr)["reason"])
        self.assertFalse(self.output.exists())


# Original-event alarm diagnostics: hand-computed invented intervals. These are
# scoring controls, not EEG agreement, measured online latency or model results.
def event(index, duration, state, first_new_offset, overlap, no_overlap):
    """Spell the expected diagnostic result shape; no interval calculation occurs."""
    return {
        "reference_event_index": index,
        "reference_duration_ticks": duration,
        "onset_alarm_state": state,
        "first_new_alarm_offset_ticks": first_new_offset,
        "positive_overlap_ticks": overlap,
        "no_raw_event_overlap": no_overlap,
    }


def diagnostics(*events):
    return {
        "schema": "raw-event-alarm-diagnostics-v1",
        "tick_rate_hz": 10,
        "events": list(events),
    }


class OriginalEventIntervalControls(unittest.TestCase):
    def check(self, references, predictions, expected):
        before = copy.deepcopy((references, predictions))
        actual = core._original_event_alarm_diagnostics(references, predictions)
        self.assertEqual(actual, expected)
        self.assertEqual((references, predictions), before)
        self.assertIs(type(actual["tick_rate_hz"]), int)
        for row in actual["events"]:
            for key in ("reference_event_index", "reference_duration_ticks",
                        "positive_overlap_ticks"):
                self.assertIs(type(row[key]), int)
            offset = row["first_new_alarm_offset_ticks"]
            if offset is not None:
                self.assertIs(type(offset), int)
            self.assertIs(type(row["no_raw_event_overlap"]), bool)
        return actual

    def test_hand_computed_onset_states_and_later_edges(self):
        cases = [
            ([[100, 200]], [], event(0, 100, "negative", None, 0, True)),
            ([[100, 200]], [[100, 200]], event(0, 100, "new_alarm", 0, 100, False)),
            ([[100, 200]], [[50, 250]], event(0, 100, "continuing_alarm", None, 100, False)),
            ([[100, 200]], [[130, 170]], event(0, 100, "negative", 30, 40, False)),
            ([[100, 200]], [[50, 100]], event(0, 100, "negative", None, 0, True)),
            ([[100, 200]], [[200, 250]], event(0, 100, "negative", None, 0, True)),
            ([[100, 200]], [[80, 120], [150, 180]],
             event(0, 100, "continuing_alarm", 50, 50, False)),
            ([[0, 100]], [[0, 100]],
             event(0, 100, "positive_at_record_start", None, 100, False)),
            ([[0, 100]], [[20, 30]],
             event(0, 100, "negative_at_record_start", 20, 10, False)),
            ([[0, 100]], [[0, 20], [50, 60]],
             event(0, 100, "positive_at_record_start", 50, 30, False)),
            ([[0, 100]], [],
             event(0, 100, "negative_at_record_start", None, 0, True)),
        ]
        for references, predictions, expected in cases:
            with self.subTest(references=references, predictions=predictions):
                self.check(references, predictions, diagnostics(expected))

    def test_touching_predictions_do_not_create_new_alarm_edges(self):
        expected = diagnostics(event(0, 100, "continuing_alarm", None, 100, False))
        self.check([[100, 200]], [[50, 220]], expected)
        self.check([[100, 200]], [[50, 120], [120, 150], [150, 220]], expected)

    def test_one_alarm_bridges_two_distinct_raw_events(self):
        self.check([[100, 130], [150, 200]], [[110, 190]], diagnostics(
            event(0, 30, "negative", 10, 20, False),
            event(1, 50, "continuing_alarm", None, 40, False),
        ))

    def test_touching_reference_events_are_not_merged(self):
        self.check([[100, 150], [150, 200]], [[100, 200]], diagnostics(
            event(0, 50, "new_alarm", 0, 50, False),
            event(1, 50, "continuing_alarm", None, 50, False),
        ))

    def test_first_of_multiple_in_event_alarm_edges_is_retained(self):
        self.check([[100, 200]], [[110, 130], [160, 170]], diagnostics(
            event(0, 100, "negative", 10, 30, False),
        ))

    def test_record_start_alarm_has_known_continuity_at_a_later_onset(self):
        self.check([[100, 200]], [[0, 120]], diagnostics(
            event(0, 100, "continuing_alarm", None, 20, False),
        ))

    def test_no_annotations_remains_empty_even_with_positive_predictions(self):
        self.check([], [], diagnostics())
        self.check([], [[0, 600]], diagnostics())

    def test_separate_records_do_not_supply_antecedent_alarm_state(self):
        self.check([[500, 600]], [[550, 600]], diagnostics(
            event(0, 100, "negative", 50, 50, False),
        ))
        self.check([[0, 100]], [[0, 50]], diagnostics(
            event(0, 100, "positive_at_record_start", None, 50, False),
        ))

    def test_sparse_large_integer_coordinates_preserve_exact_offsets(self):
        # All coordinates remain below the existing 2**53-1 admission limit.
        # Exercise only the interval helper, never the upstream dense scorer.
        shift = 2**53 - 1000
        self.check([[shift + 100, shift + 200]],
                   [[shift + 130, shift + 170]], diagnostics(
                       event(0, 100, "negative", 30, 40, False),
                   ))


class OriginalEventScorerIntegration(unittest.TestCase):
    def test_tolerant_credit_is_not_raw_overlap_or_an_onset_detection(self):
        policy = core.recommended_policy()
        result = core.evaluate_record([[100, 200]], [[200, 250]], 1000, policy)
        self.assertEqual(result["raw_event_alarm_diagnostics"], diagnostics(
            event(0, 100, "negative", None, 0, True),
        ))
        # Default tolerance can credit the processed event despite zero overlap
        # with the original annotation. Preserve both answers, with clear names.
        self.assertEqual((result["processed_reference_events"], result["true_positives"],
                          result["false_positives"]), (1, 1, 0))
        self.assertEqual(result["event_metrics"]["f1"], 1)
        self.assertEqual(result["sample_true_positive_ticks"], 0)
        self.assertEqual(result["sample_false_positive_ticks"], 50)
        self.assertEqual(result["sample_predicted_positive_ticks"], 50)

    def test_existing_record_fields_and_policy_remain_unchanged(self):
        self.assertEqual(hashlib.sha256((PACKAGE / "recommended_policy.json").read_bytes()).hexdigest(),
                         "b05ea7b363f4969fd5f1d1230686e6dea391393637028701f9f9f7785469588e")
        policy = core.recommended_policy()
        result = core.evaluate_record([[100, 200]], [[0, 600]], 600, policy)
        result.pop("raw_event_alarm_diagnostics")
        self.assertEqual(result, {
            "raw_reference_events": 1, "raw_predicted_events": 1,
            "processed_reference_events": 1, "processed_predicted_events": 1,
            "true_positives": 1, "false_positives": 0, "observed_ticks": 600,
            "event_metrics": {"sensitivity": 1, "precision": 1, "f1": 1,
                              "false_alarms_per_24_observed_hours": 0},
            "sample_reference_positive_ticks": 100,
            "sample_true_positive_ticks": 100,
            "sample_false_positive_ticks": 500,
            "sample_predicted_positive_ticks": 600,
        })
        self.assertEqual(core._COUNT_FIELDS, (
            "raw_reference_events", "raw_predicted_events", "processed_reference_events",
            "processed_predicted_events", "true_positives", "false_positives", "observed_ticks",
            "sample_reference_positive_ticks", "sample_true_positive_ticks",
            "sample_false_positive_ticks", "sample_predicted_positive_ticks",
        ))


class OriginalEventCompleteCohortControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admission, cls.policy, cls.candidate, cls.limits = complete_fixture()
        cls.result = core.evaluate(
            cls.admission, cls.policy, cls.candidate,
            expected_policy_sha256=core.canonical_sha256(cls.policy), limits=cls.limits,
        )

    def test_existing_complete_metrics_occupancy_and_alias_are_preserved(self):
        result = self.result
        self.assertEqual(result["counts"]["recordings"], 686)
        self.assertEqual(result["counts"]["biological_people"], 23)
        self.assertEqual(result["counts"]["folds"], 23)
        self.assertEqual(result["counts"]["observed_ticks"], 24696000)
        self.assertAlmostEqual(result["primary"]["value"], 112 / 115)
        pooled = result["candidate"]["pooled_diagnostic"]
        self.assertEqual((pooled["raw_reference_events"], pooled["processed_reference_events"],
                          pooled["true_positives"], pooled["false_positives"]), (24, 24, 23, 2))
        self.assertEqual(pooled["sample_predicted_positive_ticks"], 23200)
        self.assertAlmostEqual(pooled["sample_diagnostics"]["predicted_positive_time_fraction"],
                               23200 / 24696000)
        patients = {row["biological_person"]: row for row in result["candidate"]["patients"]}
        self.assertNotIn("chb21", patients)
        self.assertEqual(patients["chb01"]["observed_ticks"], 75 * 36000)
        self.assertEqual(patients["chb01"]["event_metrics"]["f1"], 0.4)
        positive = result["constant_controls"]["all_positive_control"]["pooled_diagnostic"]
        self.assertEqual(positive["sample_diagnostics"]["predicted_positive_time_fraction"], 1)
        self.assertAlmostEqual(positive["event_metrics"]["f1"], 1 / 172)
        self.assertIs(result["verification"]["training_or_causal_context_verified"], False)
        self.assertIs(result["verification"]["scientific_qualification"], False)

    def test_all_records_retain_original_event_diagnostics(self):
        rows = self.result["record_results"]
        self.assertEqual(len(rows), 686)
        positive_events = missing_events = total_events = 0
        for row in rows:
            observed = row["raw_event_alarm_diagnostics"]
            self.assertEqual(observed["schema"], "raw-event-alarm-diagnostics-v1")
            self.assertEqual(observed["tick_rate_hz"], 10)
            self.assertEqual(len(observed["events"]), row["raw_reference_events"])
            for original in observed["events"]:
                total_events += 1
                if row["recording_id"].startswith("chb21/"):
                    self.assertEqual(row["biological_person"], "chb01")
                    self.assertEqual(original, event(0, 1000, "negative", None, 0, True))
                    missing_events += 1
                else:
                    self.assertEqual(original, event(0, 1000, "new_alarm", 0, 1000, False))
                    positive_events += 1
        self.assertEqual((total_events, positive_events, missing_events), (24, 23, 1))

    def test_diagnostics_do_not_enter_candidate_or_public_support(self):
        support = core.public_support(self.admission)
        changed = copy.deepcopy(self.admission)
        row = next(row for row in changed["records"] if row["reference_intervals"])
        row["reference_intervals"] = []
        row["annotation_status"] = "explicit_zero_events"
        row["annotation_sha256"] = "0" * 64
        self.assertEqual(core.public_support(changed), support)
        self.assertEqual(core.canonical_sha256(support), self.candidate["support_sha256"])
        for public in (support, self.candidate):
            self.assertNotIn("raw_event_alarm_diagnostics", public)
            for record in public["records"]:
                self.assertNotIn("raw_event_alarm_diagnostics", record)
                self.assertNotIn("reference_intervals", record)



if __name__ == "__main__":
    unittest.main()
