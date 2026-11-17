"""Invented engineering controls only; no authentic data or model observations."""

import copy
import math
import unittest

from neuralflow_adapter import (ContractError, adapt_rows, choice_feature_view, protected_split_plan,
                               score_choices, validate_roster)


def invented_fixture(repeats=3):
    roster, units, trials, spikes = [], [], [], []
    for subject in (0, 1):
        for session in range(15):
            uids = [100, 400, 900]  # Deliberately sparse, non-package neuron IDs.
            p = {"population_id": f"invented-{subject}-{session}", "subject_id": subject,
                 "session_id": session, "uids": uids}
            roster.append(p)
            units.append({"subject_id": subject, "session_id": session, "uids": uids,
                          "analysis_type": "population", "overfitted": True, "underfitted": False})
            trial_id = 2 ** 53 + 1
            for correct in ("Left", "Right"):
                for difficulty in ("easy", "hard"):
                    for choice in ("Left", "Right"):
                        for repeat in range(repeats):
                            trial_id += 2
                            t = {"subject_id": subject, "session_id": session, "trial_id": trial_id,
                                 "stim_onset": 0.0, "reaction_times": 0.5,
                                 "correct_response": correct, "stim_difficulty": difficulty,
                                 "chosen_side": choice, "recorded_units": uids}
                            trials.append(t)
                            for uid in uids:
                                spikes.append({"subject_id": subject, "session_id": session,
                                               "trial_id": trial_id, "unit_id": uid,
                                               "spike_times": [0.1, 0.12, 0.2, 0.5, 0.7]})
    return roster, units, trials, spikes


def choice_fixture():
    roster, _, _, _ = invented_fixture(1)
    targets, predictions = [], []
    for p in roster:
        for trial_id, side in enumerate(("Left", "Right")):
            row = {k: p[k] for k in ("population_id", "subject_id", "session_id")}
            row.update(trial_id=trial_id, chosen_side=side)
            targets.append(row)
            pred = {k: row[k] for k in ("population_id", "subject_id", "session_id", "trial_id")}
            pred.update(probability_right=0.1 if side == "Left" else 0.9, fit_status="fit")
            predictions.append(pred)
    return roster, targets, predictions


class AdapterControls(unittest.TestCase):
    def setUp(self):
        self.roster, self.units, self.trials, self.spikes = invented_fixture(1)

    def run_adapter(self, **overrides):
        values = dict(units_rows=self.units, trial_rows=self.trials, spike_rows=self.spikes,
                      roster=self.roster, source_clock="stimulus_relative_seconds",
                      endpoint_policy="left_closed_right_open")
        values.update(overrides)
        return adapt_rows(**values)

    def test_full_cohort_and_reversible_sparse_unit_map(self):
        result = self.run_adapter()
        self.assertEqual(result["populations"], 30)
        self.assertEqual(len(result["episodes"]), 30 * 8)
        self.assertFalse(result["scientific_qualification"])
        unit_map = result["population_unit_maps"][0]
        self.assertEqual(unit_map["dense_index_to_source_unit_id"], [100, 400, 900])
        episode = result["episodes"][0]
        self.assertGreater(episode["trial_id"], 2 ** 53)
        self.assertEqual([s["dense_neuron_index"] for s in episode["spikes"]], [0, 1, 2])
        self.assertNotIn("overfitted", json_keys_recursive(result))
        self.assertNotIn("underfitted", json_keys_recursive(result))

    def test_condition_uses_stimulus_not_error_trial_choice(self):
        episodes = self.run_adapter()["episodes"]
        errors = [e for e in episodes if e["stimulus_condition"] == "Left_easy" and e["chosen_side"] == "Right"]
        self.assertEqual(len(errors), 30)

    def test_choice_feature_view_strips_targets_and_unknown_nested_metadata(self):
        projection = self.run_adapter()
        projection["episodes"][0]["secret_reference"] = "not an input"
        projection["episodes"][0]["spikes"][0]["overfitted"] = True
        public = choice_feature_view(projection)
        keys = json_keys_recursive(public)
        self.assertNotIn("chosen_side", keys)
        self.assertNotIn("secret_reference", keys)
        self.assertNotIn("overfitted", keys)
        self.assertFalse(public["lono_safe"])
        public["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"].clear()
        self.assertTrue(projection["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"])

    def test_original_ordered_unit_map_is_preserved_and_disagreement_rejected(self):
        self.roster[0]["uids"] = [900, 100, 400]
        self.units[0]["uids"] = [900, 100, 400]
        result = self.run_adapter()
        self.assertEqual(result["population_unit_maps"][0]["dense_index_to_source_unit_id"], [900, 100, 400])
        self.assertEqual([r["unit_id"] for r in result["episodes"][0]["spikes"]], [900, 100, 400])
        self.units[0]["uids"] = [100, 400, 900]
        with self.assertRaises(ContractError):
            self.run_adapter()

    def test_endpoint_policy_is_explicit_and_changes_only_right_boundary(self):
        opened = self.run_adapter()["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"]
        closed = self.run_adapter(endpoint_policy="closed")["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"]
        self.assertEqual(opened, [0.0, 0.08000000000000002])
        self.assertEqual(closed, opened + [0.38])
        with self.assertRaises(ContractError):
            self.run_adapter(endpoint_policy="guess")

    def test_absolute_and_relative_clock_projection_agree(self):
        # Dyadic interior times avoid hiding a boundary decision behind tolerances.
        interior_spikes = copy.deepcopy(self.spikes)
        for s in interior_spikes:
            s["spike_times"] = [0.125, 0.25, 0.375]
        relative = self.run_adapter(spike_rows=interior_spikes)
        shifted_trials = copy.deepcopy(self.trials)
        shifted_spikes = copy.deepcopy(interior_spikes)
        for t in shifted_trials:
            t["stim_onset"] = 10.0
        for s in shifted_spikes:
            s["spike_times"] = [x + 10 for x in s["spike_times"]]
        absolute = self.run_adapter(trial_rows=shifted_trials, spike_rows=shifted_spikes,
                                    source_clock="absolute_seconds")
        for a, b in zip(relative["episodes"], absolute["episodes"]):
            self.assertEqual(a["trial_id"], b["trial_id"])
            for sa, sb in zip(a["spikes"], b["spikes"]):
                self.assertEqual(sa["unit_id"], sb["unit_id"])
                self.assertEqual(len(sa["spike_seconds_from_window_start"]), len(sb["spike_seconds_from_window_start"]))
                for ta, tb in zip(sa["spike_seconds_from_window_start"], sb["spike_seconds_from_window_start"]):
                    self.assertAlmostEqual(ta, tb, places=12)
        with self.assertRaises(ContractError):
            self.run_adapter(source_clock="auto")

    def test_absolute_exact_source_boundaries_survive_cancellation(self):
        trials = copy.deepcopy(self.trials)
        spikes = copy.deepcopy(self.spikes)
        for t in trials:
            t["stim_onset"] = 10.0
        for s in spikes:
            s["spike_times"] = [10.0 + 0.12, 10.0 + 0.5]
        opened = self.run_adapter(trial_rows=trials, spike_rows=spikes, source_clock="absolute_seconds")
        closed = self.run_adapter(trial_rows=trials, spike_rows=spikes, source_clock="absolute_seconds", endpoint_policy="closed")
        self.assertEqual(opened["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"], [0.0])
        e = closed["episodes"][0]
        self.assertEqual(e["spikes"][0]["spike_seconds_from_window_start"], [0.0, e["duration_seconds"]])

    def test_source_clock_cannot_collapse_window_by_float_precision(self):
        trials = copy.deepcopy(self.trials)
        for t in trials:
            t["stim_onset"] = 1e30
        with self.assertRaises(ContractError):
            self.run_adapter(trial_rows=trials, source_clock="absolute_seconds")

    def test_same_session_and_trial_ids_across_monkeys_never_merge(self):
        result = self.run_adapter()
        cases = {(e["population_id"], e["subject_id"], e["session_id"], e["trial_id"]) for e in result["episodes"]}
        self.assertEqual(len(cases), len(result["episodes"]))

    def test_missing_unit_trial_row_is_not_silence(self):
        with self.assertRaises(ContractError):
            self.run_adapter(spike_rows=self.spikes[1:])
        changed = copy.deepcopy(self.spikes)
        changed[0]["spike_times"] = []
        self.assertEqual(self.run_adapter(spike_rows=changed)["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"], [])

    def test_missing_condition_or_population_is_rejected(self):
        with self.assertRaises(ContractError):
            self.run_adapter(roster=self.roster[:-1])
        kept = [t for t in self.trials if t["stim_difficulty"] != "hard"]
        keys = {(t["subject_id"], t["session_id"], t["trial_id"]) for t in kept}
        spikes = [s for s in self.spikes if (s["subject_id"], s["session_id"], s["trial_id"]) in keys]
        with self.assertRaises(ContractError):
            self.run_adapter(trial_rows=kept, spike_rows=spikes)

    def test_orphan_duplicate_unsorted_and_nonfinite_spikes_rejected(self):
        bad_rows = []
        orphan = copy.deepcopy(self.spikes); orphan[0]["unit_id"] = 999
        bad_rows.append(orphan)
        bad_rows.append(self.spikes + [self.spikes[0]])
        unsorted = copy.deepcopy(self.spikes); unsorted[0]["spike_times"] = [0.4, 0.2]
        bad_rows.append(unsorted)
        nonfinite = copy.deepcopy(self.spikes); nonfinite[0]["spike_times"] = [float("nan")]
        bad_rows.append(nonfinite)
        for rows in bad_rows:
            with self.subTest(rows=rows[0]):
                with self.assertRaises(ContractError):
                    self.run_adapter(spike_rows=rows)

    def test_population_membership_cannot_be_inferred_from_session_alone(self):
        changed = copy.deepcopy(self.units); changed[0]["uids"] = [100, 400, 901]
        with self.assertRaises(ContractError):
            self.run_adapter(units_rows=changed)

    def test_boolean_ids_and_short_windows_rejected(self):
        changed = copy.deepcopy(self.trials); changed[0]["trial_id"] = True
        with self.assertRaises(ContractError):
            self.run_adapter(trial_rows=changed)
        changed = copy.deepcopy(self.trials); changed[0]["reaction_times"] = 0.12
        with self.assertRaises(ContractError):
            self.run_adapter(trial_rows=changed)


def json_keys_recursive(value):
    if isinstance(value, dict):
        return set(value).union(*(json_keys_recursive(x) for x in value.values()))
    if isinstance(value, list):
        return set().union(*(json_keys_recursive(x) for x in value))
    return set()


class SplitControls(unittest.TestCase):
    def test_grouping_determinism_and_no_input_mutation(self):
        _, _, trials, _ = invented_fixture(3)
        before = copy.deepcopy(trials)
        a = protected_split_plan(trials, evaluator_secret=b"invented-test-secret-only-0000000")
        b = protected_split_plan(list(reversed(trials)), evaluator_secret=b"invented-test-secret-only-0000000")
        self.assertEqual(a, b)
        self.assertEqual(trials, before)
        keys = {(r["subject_id"], r["session_id"], r["trial_id"]) for r in a}
        self.assertEqual(len(keys), len(trials))
        self.assertEqual(CounterForTests(r["partition"] for r in a), {"train": 240, "validation": 240, "test": 240})

    def test_too_small_stratum_duplicate_and_short_secret_rejected(self):
        _, _, trials, _ = invented_fixture(1)
        with self.assertRaises(ContractError):
            protected_split_plan(trials, evaluator_secret=b"x" * 32)
        _, _, trials, _ = invented_fixture(3)
        with self.assertRaises(ContractError):
            protected_split_plan(trials + [trials[0]], evaluator_secret=b"x" * 32)
        with self.assertRaises(ContractError):
            protected_split_plan(trials, evaluator_secret=b"short")


def CounterForTests(items):
    result = {}
    for item in items:
        result[item] = result.get(item, 0) + 1
    return result


class ScoringControls(unittest.TestCase):
    def test_known_correct_predictions_and_component_only_status(self):
        roster, targets, predictions = choice_fixture()
        result = score_choices(targets, predictions, roster)
        self.assertEqual(result["animal_balanced_accuracy"], 1.0)
        self.assertAlmostEqual(result["per_population"][0]["log_loss"], -math.log(0.9))
        self.assertAlmostEqual(result["per_population"][0]["brier_score"], 0.01)
        self.assertFalse(result["complete_contract_evaluation"])

    def test_failed_fit_fallback_stays_in_full_denominator(self):
        roster, targets, predictions = choice_fixture()
        for p in predictions[:2]:
            p.update(probability_right=0.5, fit_status="fallback_after_fit_failure")
        result = score_choices(targets, predictions, roster)
        self.assertEqual(result["populations_with_fit_failure"], 1)
        self.assertAlmostEqual(result["animal_balanced_accuracy"], 29.5 / 30)

    def test_trial_count_does_not_reweight_population_or_monkey(self):
        roster, targets, predictions = choice_fixture()
        for p in predictions[:2]:
            p["probability_right"] = 1 - p["probability_right"]
        baseline = score_choices(targets, predictions, roster)["animal_balanced_accuracy"]
        for i in range(2, 102):
            t = dict(targets[0], trial_id=i); p = dict(predictions[0], trial_id=i)
            targets.append(t); predictions.append(p)
        self.assertEqual(score_choices(targets, predictions, roster)["animal_balanced_accuracy"], baseline)

    def test_missing_extra_duplicate_and_nan_predictions_rejected(self):
        roster, targets, predictions = choice_fixture()
        variants = [predictions[:-1], predictions + [dict(predictions[0], trial_id=999)], predictions + [predictions[0]]]
        bad = copy.deepcopy(predictions); bad[0]["probability_right"] = float("nan"); variants.append(bad)
        for p in variants:
            with self.assertRaises(ContractError):
                score_choices(targets, p, roster)

    def test_case_identity_and_single_class_fail_closed(self):
        roster, targets, predictions = choice_fixture()
        swapped = copy.deepcopy(targets); swapped[0]["subject_id"] = 1
        with self.assertRaises(ContractError):
            score_choices(swapped, predictions, roster)
        changed = copy.deepcopy(targets); changed[0]["chosen_side"] = "Right"
        with self.assertRaises(ContractError):
            score_choices(changed, predictions, roster)

    def test_population_roster_cannot_inflate_by_duplicate_composition(self):
        roster, _, _ = choice_fixture()
        roster[1]["session_id"] = roster[0]["session_id"]
        roster[1]["uids"] = list(reversed(roster[0]["uids"]))
        with self.assertRaises(ContractError):
            validate_roster(roster)


if __name__ == "__main__":
    unittest.main()
