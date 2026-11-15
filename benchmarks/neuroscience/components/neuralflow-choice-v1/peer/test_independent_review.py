"""Independent invented controls; no official data or numerical package required."""

import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from neuralflow_adapter import (ContractError, adapt_rows, choice_feature_view,
                               protected_split_plan, score_choices)


def fixture(repeats=1):
    roster, units, trials, spikes = [], [], [], []
    for subject in (0, 1):
        for session in range(15):
            ids = [2**53 + 9, 17, 400]
            roster.append(dict(population_id=f"peer-{subject}-{session}",
                               subject_id=subject, session_id=session, uids=ids))
            units.append(dict(subject_id=subject, session_id=session, uids=ids,
                              analysis_type="population", overfitted=True))
            trial_id = 2**53 + 1
            for side in ("Left", "Right"):
                for difficulty in ("easy", "hard"):
                    for choice in ("Left", "Right"):
                        for _ in range(repeats):
                            trial_id += 2
                            trials.append(dict(subject_id=subject, session_id=session,
                                               trial_id=trial_id, correct_response=side,
                                               stim_difficulty=difficulty, chosen_side=choice,
                                               stim_onset=10.0, reaction_times=0.5,
                                               recorded_units=ids))
                            for uid in ids:
                                spikes.append(dict(subject_id=subject, session_id=session,
                                                   trial_id=trial_id, unit_id=uid,
                                                   spike_times=[10.0 + 0.12, 10.25, 10.5]))
    return roster, units, trials, spikes


def project(data, endpoint="left_closed_right_open"):
    roster, units, trials, spikes = data
    return adapt_rows(units, trials, spikes, roster, source_clock="absolute_seconds",
                      endpoint_policy=endpoint)


class IndependentControls(unittest.TestCase):
    def test_source_order_and_exact_absolute_boundaries(self):
        data = fixture()
        opened, closed = project(data), project(data, "closed")
        for mapping in opened["population_unit_maps"]:
            self.assertEqual(mapping["dense_index_to_source_unit_id"], [2**53 + 9, 17, 400])
        for a, b in zip(opened["episodes"], closed["episodes"]):
            self.assertEqual(a["spikes"][0]["spike_seconds_from_window_start"][0], 0.0)
            self.assertEqual(len(a["spikes"][0]["spike_seconds_from_window_start"]), 2)
            self.assertEqual(b["spikes"][0]["spike_seconds_from_window_start"][-1],
                             b["duration_seconds"])
            self.assertEqual(a["spikes"][0]["unit_id"], 2**53 + 9)

    def test_unresolvable_absolute_window_fails(self):
        data = fixture()
        for row in data[2]:
            row["stim_onset"] = 2**60
        with self.assertRaises(ContractError):
            project(data)

    def test_independent_imbalanced_proper_score_oracle(self):
        roster, _, _, _ = fixture()
        targets, predictions = [], []
        sides, probabilities = ("Left", "Left", "Left", "Right"), (0.1, 0.8, 0.5, 0.7)
        for population in roster:
            for trial_id, (side, probability) in enumerate(zip(sides, probabilities)):
                identity = {k: population[k] for k in ("population_id", "subject_id", "session_id")}
                targets.append(dict(identity, trial_id=trial_id, chosen_side=side))
                predictions.append(dict(identity, trial_id=trial_id, probability_right=probability,
                                        fit_status="fallback_after_fit_failure"
                                        if population["population_id"] == "peer-0-0" else "fit"))
        result = score_choices(targets, list(reversed(predictions)), roster)
        self.assertAlmostEqual(result["animal_balanced_accuracy"], 2 / 3)
        self.assertEqual(result["populations_with_fit_failure"], 1)
        for row in result["per_population"]:
            self.assertAlmostEqual(row["log_loss"], -math.log(0.9 * 0.2 * 0.5 * 0.7) / 4)
            self.assertAlmostEqual(row["brier_score"], 0.2475)
        self.assertFalse(result["complete_contract_evaluation"])

    def test_private_projection_public_view_and_grouped_assignment_join(self):
        data = fixture(3)
        projection = project(data)
        projection["episodes"][0]["private_answer"] = {"underfitted": True}
        projection["episodes"][0]["spikes"][0]["private_answer"] = {"chosen_side": "Right"}
        before = copy.deepcopy(projection)
        public = choice_feature_view(projection)
        def keys(value):
            if isinstance(value, dict):
                return set(value).union(*(keys(x) for x in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(x) for x in value))
            return set()
        self.assertFalse({"chosen_side", "overfitted", "underfitted", "private_answer"} & keys(public))
        self.assertFalse(public["lono_safe"])
        split = protected_split_plan(data[2], evaluator_secret=b"peer-invented-secret-only-0123456789")
        identity = lambda row: (row["subject_id"], row["session_id"], row["trial_id"])
        assignments = {identity(row): row["partition"] for row in split}
        self.assertEqual(len(assignments), len(split))
        self.assertEqual(set(assignments), {identity(row) for row in public["episodes"]})
        self.assertEqual({row["partition"] for row in split}, {"train", "validation", "test"})
        public["episodes"][0]["spikes"][0]["spike_seconds_from_window_start"].append(99.0)
        self.assertEqual(projection, before)


if __name__ == "__main__":
    unittest.main()
