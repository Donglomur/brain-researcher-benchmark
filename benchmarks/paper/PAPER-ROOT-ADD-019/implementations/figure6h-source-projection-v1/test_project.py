"""Generated software controls; no biological source arrays or source fits."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ach_projection", HERE / "project.py")
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


def fixture(index=1):
    trials = ["invented_t1", "invented_t2", "invented_t3"]
    return {"schema": "ach_fig6h_projection_input_v1", "task": project.TASK,
            "source_code_sha256": project.SOURCE_SHA256, "source_export_sha256": "a" * 64,
            "session_id": "invented_session_%02d" % index,
            "rat_id": "invented_rat_%d" % ((index - 1) % 8),
            "source_session_index_one_based": index, "trial_ids": trials,
            "units": [{"unit_id": "invented_unit_%d" % u, "trial_ids": trials[:],
                       "son_time_s": [-.1, .1, .3, .5, .7],
                       "son_values": [[100 * t + 10 * u + k for k in range(5)]
                                      for t in range(3)]} for u in range(5)],
            "selection": {"is_fast": [True, False, False], "is_slow": [False, False, True],
                          "trial_indices_one_based": [1, 3], "literal_labels": [1, 0]}}


def panel():
    return {"schema": "ach_fig6h_projection_panel_input_v1", "task": project.TASK,
            "source_cohort_manifest_sha256": "b" * 64,
            "sessions": [fixture(i + 1) for i in range(18)]}


class ProjectionControls(unittest.TestCase):
    def test_matlab_column_major_order_and_source_nearest_tie(self):
        got = project.project_session(fixture())
        self.assertEqual(got["window_indices_one_based_inclusive"], [1, 4])
        self.assertEqual(got["window_endpoint_seconds"], [-.1, .5])
        expected = [0, 10, 20, 30, 40, 1, 11, 21, 31, 41,
                    2, 12, 22, 32, 42, 3, 13, 23, 33, 43]
        self.assertEqual(got["trial_by_predictor_matrix"], [expected, [x + 200 for x in expected]])
        self.assertEqual([c["native_time_index_one_based"] for c in got["feature_columns"]],
                         [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5)
        self.assertEqual(got["trial_ids"], ["invented_t1", "invented_t3"])

    def test_unselected_trials_and_times_do_not_enter_predictors(self):
        row = fixture()
        before = project.project_session(row)["trial_by_predictor_matrix"]
        for unit in row["units"]:
            unit["son_values"][1] = [float("nan")] * 5
            unit["son_values"][0][4] = float("inf")
            unit["son_values"][2][4] = -999
        self.assertEqual(project.project_session(row)["trial_by_predictor_matrix"], before)

    def test_same_shape_but_different_unit_clock_refused(self):
        row = fixture()
        row["units"][1]["son_time_s"][1] = .15
        with self.assertRaisesRegex(ValueError, "unequal unit time grids"):
            project.project_session(row)

    def test_permuted_trial_identity_refused_without_reordering(self):
        row = fixture()
        row["units"][2]["trial_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "trial identity/order"):
            project.project_session(row)

    def test_source_label_collision_is_retained_and_flagged_not_repaired(self):
        row = fixture()
        row["selection"] = {"is_fast": [False, True, True], "is_slow": [True, False, False],
                            "trial_indices_one_based": [1, 2, 3], "literal_labels": [0, 0, 0]}
        got = project.project_session(row)
        self.assertEqual(got["source_label_audit"]["mismatched_trial_indices_one_based"], [2, 3])
        self.assertFalse(got["two_literal_classes_present"])
        row["selection"]["literal_labels"] = [0, 1, 1]
        with self.assertRaisesRegex(ValueError, "corrected branches"):
            project.project_session(row)

    def test_inclusive_quartile_overlap_remains_visible(self):
        row = fixture()
        row["selection"] = {"is_fast": [True, True, False], "is_slow": [True, False, True],
                            "trial_indices_one_based": [1, 2, 3], "literal_labels": [0, 0, 0]}
        got = project.project_session(row)
        self.assertEqual(got["source_label_audit"]["overlapping_quartile_trial_indices_one_based"], [1])
        self.assertEqual(got["trial_ids"], row["trial_ids"])

    def test_shape_missing_value_boolean_and_support_fail_closed(self):
        mutations = [
            lambda x: x["units"].pop(),
            lambda x: x["units"][1]["son_values"].pop(),
            lambda x: x["units"][1]["son_values"][0].pop(),
            lambda x: x["units"][1]["son_values"][0].__setitem__(0, float("nan")),
            lambda x: x["units"][1]["son_values"][0].__setitem__(0, True),
            lambda x: x["units"][1].update(unit_id=x["units"][0]["unit_id"]),
            lambda x: x["units"][1]["son_time_s"].reverse(),
            lambda x: x["selection"]["trial_indices_one_based"].reverse(),
            lambda x: x["selection"]["is_fast"].__setitem__(0, 1),
            lambda x: x["selection"]["literal_labels"].__setitem__(0, True),
            lambda x: x.update(source_code_sha256="0" * 64),
            lambda x: x.update(source_session_index_one_based=True),
            lambda x: x.update(unknown_field="not allowed"),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                row = fixture()
                mutate(row)
                with self.assertRaises(ValueError):
                    project.project_session(row)

    def test_complete_panel_counts_are_only_consistency_not_admission(self):
        got = project.project_complete_panel(panel())
        self.assertEqual(len(got["sessions"]), 18)
        self.assertFalse(got["source_admission_established"])
        self.assertFalse(got["readiness_promoted"])
        for mutate in (
            lambda x: x["sessions"].pop(),
            lambda x: x["sessions"][0].update(rat_id="ninth_invented_rat"),
            lambda x: x["sessions"].reverse(),
            lambda x: x["sessions"][1].update(source_session_index_one_based=1),
            lambda x: x["sessions"][1].update(session_id=x["sessions"][0]["session_id"]),
        ):
            row = panel()
            mutate(row)
            with self.assertRaises(ValueError):
                project.project_complete_panel(row)

    def test_projection_does_not_mutate_original_export(self):
        row = fixture()
        before = copy.deepcopy(row)
        project.project_session(row)
        self.assertEqual(row, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
