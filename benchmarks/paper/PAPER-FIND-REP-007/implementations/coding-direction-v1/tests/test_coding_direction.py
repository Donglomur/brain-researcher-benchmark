"""Generated mathematical and failure controls; no original data or source run."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

FILE = Path(__file__).resolve().parents[1] / "coding_direction.py"
SPEC = importlib.util.spec_from_file_location("rep007_coding_direction_tested", FILE)
cd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cd)


def session(novel_first=False):
    order = (["leaf2", "leaf2", "circle1", "circle1", "leaf1", "leaf1"]
             if novel_first else ["leaf1", "leaf1", "circle1", "circle1", "leaf2", "leaf2"])
    walls = np.array(order * 2)
    trial = np.repeat(np.arange(len(walls)), 3)
    frames = walls[trial]
    raw = np.zeros((4, len(frames)))
    for number, stimulus in enumerate(walls):
        first = [2., 4.] if stimulus == "leaf1" else [0., 2.]
        second = [2., 4.] if stimulus == "circle1" else [0., 2.]
        raw[:, number * 3:number * 3 + 2] = [first, second, [1., 3.], [1., 3.]]
    # Population SD of 0..39 is sqrt((40^2-1)/12). Scaling a cell's complete
    # trace leaves its normalized response unchanged, giving an analytic oracle.
    interp = np.arange(60.)[None, None, :] * np.arange(1., 5.)[:, None, None]
    interp = np.repeat(interp, len(walls), axis=1)
    return {
        "spks": raw, "area_ids": np.array([8, 8, 8, -1]),
        "frame_wall": frames, "frame_move": np.ones(len(frames)),
        "frame_corridor": np.tile([1, 1, 0], len(walls)),
        "frame_gray": np.tile([0, 0, 1], len(walls)), "frame_trial": trial,
        "trial_wall": walls, "stimulus_names": np.array(["circle1", "leaf1", "leaf2"]),
        "stimulus_ids": np.array([0, 2, 3]), "interp_spks": interp,
    }


class CodingDirectionControls(unittest.TestCase):
    def test_closed_form_trace_both_populations_and_all_source_slots(self):
        report = cd.coding_direction(session())
        area = report["areas"]["V1"]
        self.assertEqual(area["source_cell_count"], 3)
        self.assertEqual(report["source_cell_count"], 4)  # Outside-area cell preserved.
        self.assertEqual(area["populations"]["first_reference"]["selected_cell_indices"], [0])
        self.assertEqual(area["populations"]["second_reference"]["selected_cell_indices"], [1])
        expected = (np.r_[np.arange(50., 60.), np.arange(60.)] - 46.5) / np.sqrt(133.25)
        for population in area["populations"].values():
            self.assertEqual(list(population["stimuli"]), list(map(str, range(7))))
            np.testing.assert_allclose(population["stimuli"]["2"]["values"], [expected, expected])
            self.assertEqual(population["stimuli"]["1"]["status"], "not_present")
        self.assertEqual(report["areas"]["aHV"]["selection_status"], "no_eligible_cells")
        self.assertFalse(report["full_contract_complete"])
        self.assertFalse(report["scientific_improvement_assessed"])
        json.dumps(report, allow_nan=False)

    def test_reference_odd_trials_novel_complete_and_statistics_all_reference(self):
        result = cd.coding_direction(session())
        traces = result["areas"]["V1"]["populations"]["first_reference"]["stimuli"]
        self.assertEqual(traces["2"]["trial_indices"], [1, 7])
        self.assertEqual(traces["0"]["trial_indices"], [3, 9])
        self.assertEqual(traces["3"]["trial_indices"], [4, 5, 10, 11])
        self.assertEqual(result["normalization_reference_trial_indices"], [[0, 1, 6, 7], [2, 3, 8, 9]])
        self.assertFalse(result["normalization"]["prospective_train_only"])

    def test_odd_raw_frames_cannot_change_selection_or_projected_values(self):
        first = session()
        second = session()
        second["spks"][:, second["frame_trial"] % 2 == 1] = 1e9
        self.assertEqual(cd.coding_direction(first), cd.coding_direction(second))

    def test_interpolated_odd_reference_values_do_change_source_normalizer(self):
        first = cd.coding_direction(session())
        second_input = session()
        second_input["interp_spks"][0, 1, :40] += 50
        second = cd.coding_direction(second_input)
        a = first["areas"]["V1"]["populations"]["first_reference"]
        b = second["areas"]["V1"]["populations"]["first_reference"]
        self.assertEqual(a["selected_cell_indices"], b["selected_cell_indices"])
        self.assertNotEqual(a["normalization_diagnostics"], b["normalization_diagnostics"])
        self.assertNotEqual(a["stimuli"]["3"]["values"], b["stimuli"]["3"]["values"])

    def test_percentile_boundary_ties_retain_all_tied_cells_in_both_populations(self):
        data = session()
        data["spks"][1:3] = data["spks"][0]
        area = cd.coding_direction(data)["areas"]["V1"]
        self.assertEqual(area["upper_lower_percentile_thresholds"], [2., 2.])
        for population in area["populations"].values():
            self.assertEqual(population["selected_cell_indices"], [0, 1, 2])

    def test_first_trial_missing_tail_is_explicit_not_zero_filled(self):
        data = session(novel_first=True)
        result = cd.coding_direction(data)
        out = result["areas"]["V1"]["populations"]["first_reference"]["stimuli"]["3"]
        self.assertEqual(out["trial_indices"], [0, 1, 6, 7])
        self.assertEqual(out["previous_trial_unavailable"], [True, False, False, False])
        self.assertEqual(out["values"][0][:10], [None] * 10)
        np.testing.assert_allclose(out["values"][1][:10], out["values"][0][-10:])

    def test_zero_scale_cells_are_retained_with_undefined_output(self):
        data = session()
        data["interp_spks"][0] = 1
        population = cd.coding_direction(data)["areas"]["V1"]["populations"]["first_reference"]
        self.assertEqual(population["selected_cell_indices"], [0])
        self.assertEqual(population["status"], "undefined_normalization")
        self.assertEqual(population["normalization_diagnostics"]["zero_scale_cells"], 1)
        self.assertEqual(population["stimuli"]["2"]["values"], [[None] * 70] * 2)

    def test_nonfinite_gray_center_is_not_reported_as_valid_normalization(self):
        for gray_value in (np.nan, 1e308):
            with self.subTest(gray_value=gray_value):
                data = session()
                data["interp_spks"][0, :, 42:52] = gray_value
                population = cd.coding_direction(data)["areas"]["V1"]["populations"]["first_reference"]
                self.assertEqual(population["selected_cell_indices"], [0])
                self.assertEqual(population["normalization_diagnostics"]["nonfinite_scale_cells"], 0)
                self.assertEqual(population["normalization_diagnostics"]["nonfinite_center_cells"], 1)
                self.assertGreater(population["normalization_diagnostics"]["nonfinite_normalized_values"], 0)
                self.assertEqual(population["status"], "undefined_normalization")
                self.assertEqual(population["stimuli"]["2"]["values"], [[None] * 70] * 2)

    def test_history_uses_previous_original_trial_before_stimulus_filtering(self):
        data = session()
        data["interp_spks"] += 10 * np.arange(12)[None, :, None]
        stimuli = cd.coding_direction(data)["areas"]["V1"]["populations"]["first_reference"]["stimuli"]
        novel = stimuli["3"]
        self.assertEqual(novel["trial_indices"], [4, 5, 10, 11])
        # For selected cell0, center=46.5+55 and each reference variance is
        # spatial133.25 plus trial-offset925. Trial10 follows ORIGINAL trial9,
        # which is circle1, not the previously retained novel trial5.
        expected = (np.arange(50., 60.) + 90 - 101.5) / np.sqrt(1058.25)
        actual = novel["values"][2][:10]
        np.testing.assert_allclose(actual, expected)
        np.testing.assert_allclose(actual, stimuli["0"]["values"][1][-10:])
        self.assertFalse(np.allclose(actual, novel["values"][2][-10:]))
        self.assertFalse(np.allclose(actual, novel["values"][1][-10:]))

    def test_nonfinite_dprime_never_becomes_arbitrary_percentile_selection(self):
        data = session()
        raw = data["spks"]
        raw[0, (data["frame_wall"] == "leaf1") & (data["frame_corridor"] == 1)] = 2
        raw[0, (data["frame_wall"] == "circle1") & (data["frame_corridor"] == 1)] = 1
        area = cd.coding_direction(data)["areas"]["V1"]
        self.assertEqual(area["selection_status"], "undefined_selection_nonfinite_dprime")
        self.assertEqual(area["eligible_dprime_diagnostics"]["positive_infinity"], 1)
        self.assertIsNone(area["upper_lower_percentile_thresholds"])
        self.assertEqual(area["populations"]["first_reference"]["stimuli"]["3"]["trial_count"], 4)

    def test_malformed_source_axes_and_missing_selection_groups_fail(self):
        cases = []
        data = session(); data["frame_trial"][0] = -1; cases.append(data)
        data = session(); data["frame_gray"][0] = 2; cases.append(data)
        data = session(); data["frame_trial"][0] = 2; cases.append(data)
        data = session(); data["frame_gray"][:] = 0; cases.append(data)
        data = session(); data["frame_move"][(data["frame_wall"] == "circle1")] = 0; cases.append(data)
        data = session(); del data["interp_spks"]; cases.append(data)
        for data in cases:
            with self.subTest(keys=tuple(data)), self.assertRaises(ValueError):
                cd.coding_direction(data)

    def test_invalid_reference_and_unrepresented_source_identity_fail(self):
        for pair in [(2, 2), (True, 0), (2, 9), (2,), "20"]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                cd.coding_direction(session(), pair)
        with self.assertRaises(ValueError):
            cd.coding_direction(session(), (2, 6))
        data = session(); data["stimulus_ids"][2] = 7
        with self.assertRaises(ValueError):
            cd.coding_direction(data)

    def test_dependency_tampering_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evaluator.py"
            path.write_text("raise RuntimeError('must not execute')\n")
            with self.assertRaisesRegex(ValueError, "dependency identity changed"):
                cd._load_initial(path)

    def test_input_arrays_unchanged(self):
        data = session()
        before = {key: value.copy() for key, value in data.items()}
        cd.coding_direction(data)
        for key in data:
            np.testing.assert_array_equal(data[key], before[key])


if __name__ == "__main__":
    unittest.main()
