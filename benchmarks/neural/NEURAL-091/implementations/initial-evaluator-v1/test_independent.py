"""Independent generated controls, not native Allen observations.

Poisson expectations below use independent Decimal probability-mass arithmetic.
"""
import copy
from decimal import Decimal, localcontext
import hashlib
import json
import unittest
import evaluator

CONTRACT = "b42c6803c1aede42efe4f65e422494247b355b2dd2799e5817ef61d759cc2445"
SDK_COMMIT = "a9b5c685396126d9748f1ccecf7c00f440569f69"


def freeze_presentation_metadata(bundle, protocol):
    for session, selected in zip(bundle["sessions"], protocol["sessions"]):
        selected["presentation_ids"] = [p["presentation_id"] for p in session["presentations"]]
        payload = json.dumps(session["presentations"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        selected["presentation_table_sha256"] = hashlib.sha256(payload).hexdigest()


def fixture(mouse_ids=("mouse-a",)):
    """One generated calibrated unit/mouse; 4 train seconds, 2 query seconds."""
    sessions, roster = [], []
    for i, mouse in enumerate(mouse_ids):
        sid, uid, pin = "session-" + str(i), "unit-" + str(i), format(i + 1, "064x")
        sessions.append({
            "session_id": sid, "mouse_id": mouse, "session_type": "brain_observatory_1.1",
            "source_file_sha256": pin, "source_file_bytes": 100 + i,
            "units": [{"unit_id": uid, "probe_id": "probeA", "spike_times":
                       [2.2, 2.6, 3, 3.4, 4, 4.7, 10.1, 10.4, 10.8, 11.3]}],
            "presentations": [
                {"presentation_id": "train-short", "stimulus_name": "drifting_gratings", "stimulus_condition_id": "condition-short", "start_time": 0, "stop_time": 1, "stimulus": {"orientation": 0}},
                {"presentation_id": "train-long", "stimulus_name": "drifting_gratings", "stimulus_condition_id": "condition-long", "start_time": 2, "stop_time": 5, "stimulus": {"orientation": 90}},
                {"presentation_id": "query", "stimulus_name": "natural_movie_one", "stimulus_condition_id": "condition-query", "start_time": 10, "stop_time": 12, "stimulus": {"frame": 0}}],
            "invalid_intervals": [],
            "running_samples": [{"start_time": -1, "stop_time": 0, "velocity": 0}, {"start_time": 1, "stop_time": 2, "velocity": 10}, {"start_time": 9, "stop_time": 10, "velocity": 10}],
            "pupil_samples": [{"time": -1, "pupil_area": 1}, {"time": 1, "pupil_area": 9}, {"time": 9, "pupil_area": 9}]})
        roster.append({"session_id": sid, "mouse_id": mouse, "unit_ids": [uid], "source_file_sha256": pin, "source_file_bytes": 100 + i})
    protocol = {"schema_version": 1, "contract_sha256": CONTRACT, "sdk_commit": SDK_COMMIT,
                "heldout_families": ["natural_movie_one"], "temporal_guard_seconds": 0.2,
                "pupil_max_age_seconds": 3, "state_history_seconds": 1, "state_prior_seconds": 2,
                "quality_selection_policy": "generated-control-roster-no-native-data",
                "session_type": "brain_observatory_1.1", "sessions": roster}
    bundle = {"source": "Allen Visual Coding Neuropixels", "sessions": sessions}
    freeze_presentation_metadata(bundle, protocol)
    return bundle, protocol


def predictions(public, rates):
    return [{"key": row["key"], "rate_hz": rate} for row, rate in zip(public["query"], rates)]


def poisson_bps(count, exposure, prediction, baseline):
    """Independent full log-PMF difference, retaining factorial until subtraction."""
    with localcontext() as context:
        context.prec = 50
        y, e, p, b = (Decimal(str(x)) for x in (count, exposure, prediction, baseline))
        factorial = Decimal(1)
        for integer in range(1, count + 1):
            factorial *= integer
        lp = y * (e * p).ln() - e * p - factorial.ln()
        lb = y * (e * b).ln() - e * b - factorial.ln()
        return float((lp - lb) / (y * Decimal(2).ln()))


class IndependentControls(unittest.TestCase):
    def test_exposure_weighted_baseline_and_decimal_poisson_oracle(self):
        bundle, protocol = fixture()
        public, private = evaluator.prepare(bundle, protocol)
        controls = evaluator.fit_controls(public)
        self.assertEqual([r["count"] for r in public["training"]], [0, 6])
        self.assertEqual([r["exposure_seconds"] for r in public["training"]], [1, 3])
        self.assertEqual(controls["mean_rate"][0]["rate_hz"], 1.5)
        # State-high cell: (6 spikes + 2 sec * 1.5 Hz)/(3 + 2 sec).
        self.assertEqual(controls["running_pupil"][0]["rate_hz"], 9 / 5)
        result = evaluator.score(public, private, predictions(public, [2]), bootstrap_replicates=17)
        actual = result["overall"]["mouse_macro_bits_per_spike"]
        self.assertAlmostEqual(actual, poisson_bps(4, 2, 2, 1.5), places=14)
        self.assertAlmostEqual(actual, 0.0543637390566029667, places=14)

    def test_query_target_changes_cannot_change_public_inputs_or_controls(self):
        bundle, protocol = fixture()
        before, private_before = evaluator.prepare(bundle, protocol)
        changed = copy.deepcopy(bundle)
        changed["sessions"][0]["units"][0]["spike_times"] = [2.2, 2.6, 3, 3.4, 4, 4.7, 10.01, 10.02, 10.03, 10.04, 10.05, 10.06, 10.07]
        changed["sessions"][0]["units"][0]["firing_rate"] = 999999
        changed["sessions"][0]["units"][0]["pref_ori_dg"] = 177
        after, private_after = evaluator.prepare(changed, protocol)
        self.assertEqual(before, after)
        self.assertEqual(evaluator.fit_controls(before), evaluator.fit_controls(after))
        self.assertEqual(private_before["targets"][0]["count"], 4)
        self.assertEqual(private_after["targets"][0]["count"], 7)
        fixed = predictions(before, [2])
        old = evaluator.score(before, private_before, fixed, bootstrap_replicates=17)
        new = evaluator.score(after, private_after, fixed, bootstrap_replicates=17)
        self.assertNotEqual(old["overall"], new["overall"])

    def test_future_state_samples_cannot_change_query_inputs(self):
        bundle, protocol = fixture()
        public_before, private_before = evaluator.prepare(bundle, protocol)
        changed = copy.deepcopy(bundle)
        session = changed["sessions"][0]
        session["running_samples"].append({"start_time": 10, "stop_time": 12, "velocity": 999999})
        session["pupil_samples"].append({"time": 10, "pupil_area": 999999})
        public_after, private_after = evaluator.prepare(changed, protocol)
        self.assertEqual(public_before, public_after)
        self.assertEqual(private_before["targets"], private_after["targets"])
        self.assertEqual(evaluator.fit_controls(public_before), evaluator.fit_controls(public_after))

    def test_query_state_cannot_move_training_state_thresholds(self):
        bundle, protocol = fixture()
        public, _ = evaluator.prepare(bundle, protocol)
        before = evaluator.fit_controls(public)
        added = copy.deepcopy(public)
        for i in range(9):
            row = copy.deepcopy(public["query"][0])
            row["key"][2] = "extra-query-" + str(i)
            row["start_time"] += (i + 1) * 10
            row["stop_time"] += (i + 1) * 10
            row["running_speed"] = row["pupil_area"] = 1000000
            added["query"].append(row)
        after = evaluator.fit_controls(added)
        self.assertEqual(before["mean_rate"][0], after["mean_rate"][0])
        self.assertEqual(before["running_pupil"][0], after["running_pupil"][0])
        self.assertEqual(after["running_pupil"][0]["rate_hz"], 1.8)

    def test_invalid_interval_union_removes_exposure_and_counts_once(self):
        bundle, protocol = fixture()
        s = bundle["sessions"][0]
        s["invalid_intervals"] = [{"start_time": 10.5, "stop_time": 11, "scope": "probeA"}, {"start_time": 10.75, "stop_time": 11.25, "scope": "all_probes"}]
        s["units"][0]["spike_times"] = [2.2, 2.6, 3, 3.4, 4, 4.7, 10, 10.5, 10.75, 11, 11.25, 11.5, 12]
        public, private = evaluator.prepare(bundle, protocol)
        self.assertEqual(public["query"][0]["exposure_seconds"], 1.25)
        self.assertEqual(private["targets"][0]["count"], 3)
        self.assertEqual(public["query"][0]["running_coverage"], 1)
        self.assertEqual(public["query"][0]["pupil_coverage"], 1)
        self.assertEqual(evaluator.fit_controls(public)["mean_rate"][0]["rate_hz"], 1.5)

    def test_half_open_queries_do_not_duplicate_boundary_spikes(self):
        bundle, protocol = fixture()
        s = bundle["sessions"][0]
        s["presentations"][-1]["stop_time"] = 11
        next_query = copy.deepcopy(s["presentations"][-1])
        next_query.update(presentation_id="query-next", start_time=11, stop_time=12)
        s["presentations"].append(next_query)
        s["units"][0]["spike_times"] = [2.2, 2.6, 3, 3.4, 4, 4.7, 10, 11, 12]
        freeze_presentation_metadata(bundle, protocol)
        public, private = evaluator.prepare(bundle, protocol)
        self.assertEqual([r["count"] for r in private["targets"]], [1, 1])
        self.assertEqual([r["exposure_seconds"] for r in public["query"]], [1, 1])

    def test_mouse_macro_is_not_spike_weighted(self):
        bundle, protocol = fixture(("mouse-a", "mouse-b"))
        for index, s in enumerate(bundle["sessions"]):
            s["presentations"][-1]["stop_time"] = 11
            n = 1 if index == 0 else 9
            s["units"][0]["spike_times"] = [0.2, 2.2, 3.2, 4.2] + [10.05 + j * 0.1 for j in range(n)]
        freeze_presentation_metadata(bundle, protocol)
        public, private = evaluator.prepare(bundle, protocol)
        result = evaluator.score(public, private, predictions(public, [2, 9]), bootstrap_seed=19, bootstrap_replicates=101)
        a, b = poisson_bps(1, 1, 2, 1), poisson_bps(9, 1, 9, 1)
        macro = (a + b) / 2
        self.assertAlmostEqual(result["overall"]["mouse_macro_bits_per_spike"], macro, places=14)
        self.assertAlmostEqual(macro, 0.7224171843260240745, places=14)
        self.assertNotAlmostEqual(macro, (a + 9 * b) / 10, places=8)
        self.assertEqual(result["overall"]["mouse_count"], 2)
        self.assertAlmostEqual(result["stimulus_families"]["natural_movie_one"]["mouse_macro_bits_per_spike"], macro, places=14)
        self.assertIsNotNone(result["uncertainty"]["limits"])

    def test_mean_control_is_exact_zero_gain(self):
        bundle, protocol = fixture(("mouse-a", "mouse-b"))
        public, private = evaluator.prepare(bundle, protocol)
        result = evaluator.score(public, private, evaluator.fit_controls(public)["mean_rate"], bootstrap_replicates=17)
        self.assertEqual(result["overall"]["mouse_macro_bits_per_spike"], 0)
        self.assertEqual(result["uncertainty"]["limits"], [0, 0])

    def test_zero_reference_positive_target_is_undefined(self):
        bundle, protocol = fixture()
        bundle["sessions"][0]["units"][0]["spike_times"] = [10.1]
        public, private = evaluator.prepare(bundle, protocol)
        result = evaluator.score(public, private, predictions(public, [1]), bootstrap_replicates=17)
        self.assertEqual(evaluator.fit_controls(public)["mean_rate"][0]["rate_hz"], 0)
        self.assertEqual(result["overall"]["status"], "undefined")
        self.assertIsNone(result["overall"]["mouse_macro_bits_per_spike"])
        self.assertIn("zero_training_rate_positive_target", result["overall"]["mice"][0]["status"])

    def test_zero_spike_mouse_remains_in_complete_roster(self):
        bundle, protocol = fixture(("mouse-a", "mouse-b"))
        bundle["sessions"][0]["units"][0]["spike_times"] = [2.2, 2.6, 3, 3.4, 4, 4.7]
        public, private = evaluator.prepare(bundle, protocol)
        result = evaluator.score(public, private, predictions(public, [2, 2]), bootstrap_replicates=17)
        self.assertEqual(result["overall"]["mouse_count"], 2)
        self.assertEqual([r["mouse_id"] for r in result["overall"]["mice"]], ["mouse-a", "mouse-b"])
        self.assertIn("zero_heldout_spikes", result["overall"]["mice"][0]["status"])
        self.assertEqual(result["overall"]["status"], "undefined")
        self.assertIsNone(result["overall"]["mouse_macro_bits_per_spike"])
        self.assertIsNone(result["uncertainty"]["limits"])

    def test_zero_prediction_positive_target_is_negative_infinity(self):
        bundle, protocol = fixture()
        public, private = evaluator.prepare(bundle, protocol)
        result = evaluator.score(public, private, predictions(public, [0]), bootstrap_replicates=17)
        self.assertEqual(result["overall"]["status"], "negative_infinity")
        self.assertIsNone(result["overall"]["mouse_macro_bits_per_spike"])

    def test_missing_state_preserves_trial_with_train_only_fallback(self):
        bundle, protocol = fixture()
        s = bundle["sessions"][0]
        s["running_samples"], s["pupil_samples"] = s["running_samples"][:2], s["pupil_samples"][:2]
        public, private = evaluator.prepare(bundle, protocol)
        self.assertEqual(len(public["query"]), 1)
        self.assertEqual(private["targets"][0]["count"], 4)
        for value, coverage in (("running_speed", "running_coverage"), ("pupil_area", "pupil_coverage")):
            self.assertIsNone(public["query"][0][value])
            self.assertEqual(public["query"][0][coverage], 0)
        self.assertEqual(evaluator.fit_controls(public)["running_pupil"][0]["rate_hz"], 1.5)

    def test_temporal_guard_removes_training_not_query(self):
        bundle, protocol = fixture()
        s = bundle["sessions"][0]
        s["presentations"].append({"presentation_id": "too-close", "stimulus_name": "drifting_gratings", "stimulus_condition_id": "condition-close", "start_time": 9.6, "stop_time": 9.9})
        s["units"][0]["spike_times"].append(9.7)
        s["units"][0]["spike_times"].sort()
        freeze_presentation_metadata(bundle, protocol)
        public, private = evaluator.prepare(bundle, protocol)
        self.assertEqual(len(public["training"]), 2)
        self.assertEqual(len(public["query"]), 1)
        self.assertEqual(private["targets"][0]["count"], 4)
        self.assertIn({"session_id": "session-0", "presentation_id": "too-close", "reason": "temporal_guard"}, private["exclusions"])
        self.assertEqual(evaluator.fit_controls(public)["mean_rate"][0]["rate_hz"], 1.5)

    def test_repeat_family_crossing_rejected_session_local_collision_allowed(self):
        bundle, protocol = fixture(("mouse-a", "mouse-b"))
        public, _ = evaluator.prepare(bundle, protocol)
        self.assertEqual(len(public["query"]), 2)
        bundle["sessions"][0]["presentations"][0]["stimulus_condition_id"] = "condition-query"
        freeze_presentation_metadata(bundle, protocol)
        with self.assertRaisesRegex(ValueError, "repeat condition crosses"):
            evaluator.prepare(bundle, protocol)

    def test_exact_prediction_population_and_packet_binding(self):
        bundle, protocol = fixture(("mouse-a", "mouse-b"))
        public, private = evaluator.prepare(bundle, protocol)
        full = predictions(public, [2, 2])
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            evaluator.score(public, private, full[:1], bootstrap_replicates=17)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluator.score(public, private, full + full[:1], bootstrap_replicates=17)
        changed = copy.deepcopy(public)
        changed["training"][0]["count"] += 1
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            evaluator.score(changed, private, full, bootstrap_replicates=17)

    def test_arbitrary_neural_features_are_not_allowed_public_inputs(self):
        bundle, protocol = fixture()
        public, _ = evaluator.prepare(bundle, protocol)
        public["query"][0]["whole_session_firing_rate"] = 2
        with self.assertRaisesRegex(ValueError, "unapproved public"):
            evaluator.fit_controls(public)

    def test_dropping_presentation_cannot_silently_change_frozen_population(self):
        bundle, protocol = fixture()
        bundle["sessions"][0]["presentations"].pop(0)
        with self.assertRaisesRegex(ValueError, "presentation roster mismatch"):
            evaluator.prepare(bundle, protocol)


if __name__ == "__main__":
    unittest.main()
