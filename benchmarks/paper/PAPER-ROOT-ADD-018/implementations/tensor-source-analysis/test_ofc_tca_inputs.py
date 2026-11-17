"""Invented source-semantics controls only; no empirical or native execution."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ofc_tca_inputs as t


def fixture(name="invented-000", cohort="Expert", full_axis=False):
    axis = [-4 + i / 20 for i in range(241)] if full_axis else [-2., -1., 0., .8, 1., 2.]
    width = len(axis)
    return {"session_id": name, "animal_id": "invented-animal", "cohort": cohort,
            "S": {"Block": [3, 1, 2, 3, 1, 2], "vios": [0] * 6},
            "SU": [{"cluster_id": i + 10, "xvec": {"COFF": axis.copy()},
                    "hmat": {event: [[float(r * width + c + i * 100) for c in range(width)]
                                     for r in range(6)] for event in t.EVENTS}}
                   for i in range(5)]}


def cohort_fixture(cohort="Expert"):
    # Complete invented identity count; only the first session is source-eligible.
    sessions = []
    for i in range(t.COHORT_SESSION_COUNTS[cohort]):
        sessions.append({"session_id": "invented-%03d" % i, "animal_id": "invented-animal-%d" % (i % 7),
                         "cohort": cohort, "S": {"Block": [1, 2, 1, 2, 1]}, "SU": []})
    sessions[0] = fixture(sessions[0]["session_id"], cohort)
    return sessions, [x["session_id"] for x in sessions]


class SourceArithmetic(unittest.TestCase):
    def test_closed_form_sample_sd_block_order_and_inclusive_windows(self):
        result = t.prepare_session(fixture())
        self.assertEqual(result["report"]["status"], "transformed")
        self.assertEqual([len(result["data"]), len(result["data"][0]), len(result["data"][0][0])], [5, 18, 3])
        # Full event comprises integers0..35. Sample variance is N(N+1)/12=111.
        for unit in result["data"]:
            for segment in result["layout"]:
                for offset, column in enumerate(segment["source_columns_one_based"]):
                    c = column - 1
                    for block, row_center in enumerate((1.5, 2.5, 3.5)):
                        expected = (6 * row_center + c - 17.5) / math.sqrt(111.)
                        self.assertAlmostEqual(unit[segment["output_start"] + offset][block], expected, places=14)
        self.assertEqual(result["report"]["selected_source_rows_one_based"], [[1, 4], [2, 5], [3, 6]])

    def test_source_241_columns_produce_197_positions(self):
        result = t.prepare_session(fixture(full_axis=True))
        self.assertEqual(result["report"]["status"], "transformed")
        self.assertEqual(len(result["data"][0]), 197)
        self.assertEqual([len(x["times_s"]) for x in result["layout"]], [41, 41, 41, 37, 37])

    def test_full_matrix_includes_outside_crop_and_violations_in_normalizer(self):
        original = fixture()
        baseline = t.prepare_session(original)
        altered = copy.deepcopy(original)
        altered["SU"][0]["hmat"]["COFF"][0][0] = 10000.
        changed = t.prepare_session(altered)
        self.assertNotEqual(baseline["data"][0][0][0], changed["data"][0][0][0])
        # Mark both low-block rows violations: they remain in the normalizer.
        altered["S"]["vios"] = [1, 0, 0, 1, 0, 0]
        changed = t.prepare_session(altered)
        values = [v for row in altered["SU"][0]["hmat"]["COFF"] for v in row]
        mu = sum(values) / len(values)
        sd = math.sqrt(sum((x - mu) ** 2 for x in values) / (len(values) - 1))
        expected = (((7 - mu) / sd) + ((25 - mu) / sd)) / 2
        self.assertAlmostEqual(changed["data"][0][0][1], expected)
        self.assertEqual([x[0] for x in changed["data"][0][:4]], [0.] * 4)

    def test_one_missing_mean_zeros_whole_event_block_across_units(self):
        session = fixture()
        for row in (0, 3):
            session["SU"][0]["hmat"]["COFF"][row][1] = math.nan
        result = t.prepare_session(session)
        for unit in result["data"]:
            self.assertEqual([x[0] for x in unit[:4]], [0.] * 4)
        gate = result["report"]["event_block_gates"][0]
        self.assertEqual(gate["missing_mean_entries"], 1)
        self.assertTrue(gate["zero_initialized_retained"])
        self.assertTrue(result["report"]["event_block_gates"][1]["assigned"])
        self.assertTrue(result["report"]["event_block_gates"][3]["assigned"])

    def test_partial_missing_trial_is_omitted_without_zero_gate(self):
        session = fixture()
        session["SU"][0]["hmat"]["COFF"][0][1] = math.nan
        result = t.prepare_session(session)
        self.assertTrue(result["report"]["event_block_gates"][0]["assigned"])
        values = [float(i) for i in range(36) if i != 1]
        mu = sum(values) / 35
        sd = math.sqrt(sum((x - mu) ** 2 for x in values) / 34)
        self.assertAlmostEqual(result["data"][0][0][0], (19 - mu) / sd)

    def test_constant_unit_suppresses_all_blocks_of_that_event(self):
        session = fixture()
        session["SU"][2]["hmat"]["Rew"] = [[7.] * 6 for _ in range(6)]
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "transformed")
        for unit in result["data"]:
            self.assertEqual(unit[12:15], [[0., 0., 0.]] * 3)
        self.assertEqual(sum(not x["assigned"] for x in result["report"]["event_block_gates"]), 3)

    def test_all_nan_event_is_not_imputed_and_is_audited(self):
        session = fixture()
        session["SU"][0]["hmat"]["Opt"] = [[math.nan] * 6 for _ in range(6)]
        result = t.prepare_session(session)
        for unit in result["data"]:
            self.assertEqual(unit[15:], [[0., 0., 0.]] * 3)
        self.assertEqual(result["report"]["event_block_gates"][-1]["normalization"][0]["observed"], 0)

    def test_first_unit_coff_controls_all_five_events(self):
        session = fixture()
        for unit in session["SU"]:
            unit["xvec"]["Rew"] = [999.]
        session["SU"][1]["xvec"]["COFF"] = [999.]
        self.assertEqual(t.prepare_session(session)["data"], t.prepare_session(fixture())["data"])

    def test_eventwise_normalization_does_not_pool_other_events(self):
        session = fixture()
        baseline = t.prepare_session(session)
        session["SU"][0]["hmat"]["SON"][0][0] = 5000.
        result = t.prepare_session(session)
        self.assertEqual(baseline["data"][0][:4], result["data"][0][:4])
        self.assertNotEqual(baseline["data"][0][4:8], result["data"][0][4:8])
        self.assertEqual(baseline["data"][0][8:], result["data"][0][8:])

    def test_four_transitions_does_not_establish_three_blocks(self):
        session = fixture()
        session["S"]["Block"] = [1, 2, 1, 2, 1, 2]
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "transformed")
        self.assertEqual(result["report"]["selected_source_rows_one_based"][0], [])
        self.assertTrue(all(x[0] == 0 for unit in result["data"] for x in unit))


class SourceRefusals(unittest.TestCase):
    def test_five_unit_and_four_transition_boundaries(self):
        session = fixture()
        session["SU"] = session["SU"][:4]
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "excluded_by_source")
        self.assertEqual(result["report"]["cluster_ids"], [10, 11, 12, 13])
        session = fixture()
        session["S"]["Block"] = [1, 1, 2, 2, 3, 3]
        self.assertEqual(t.prepare_session(session)["report"]["status"], "excluded_by_source")

    def test_singleton_branch_preserves_all_identities_and_returns_no_tensor(self):
        session = fixture()
        session["S"]["vios"][0] = 1
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "unsupported")
        self.assertIn("singleton", result["report"]["reason"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["report"]["animal_id"], session["animal_id"])
        self.assertEqual(result["report"]["cluster_ids"], [10, 11, 12, 13, 14])

    def test_missing_opt_is_required_existing_four_event_projection_is_insufficient(self):
        session = fixture()
        del session["SU"][4]["hmat"]["Opt"]
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "unsupported")
        self.assertIn("Opt", result["report"]["reason"])
        self.assertIsNone(result["data"])

    def test_ragged_inf_bool_and_trial_mismatch_refused(self):
        for mutation in (lambda s: s["SU"][0]["hmat"]["COFF"][1].pop(),
                         lambda s: s["SU"][0]["hmat"]["COFF"][0].__setitem__(0, math.inf),
                         lambda s: s["SU"][0]["hmat"]["COFF"][0].__setitem__(0, True),
                         lambda s: s["SU"][0]["hmat"]["COFF"].pop(),
                         lambda s: s["S"]["vios"].pop()):
            session = fixture()
            mutation(session)
            with self.subTest(mutation=mutation):
                result = t.prepare_session(session)
                self.assertEqual(result["report"]["status"], "unsupported")
                self.assertIsNone(result["data"])

    def test_missing_duplicate_and_round_tie_endpoint_refused(self):
        for axis in ([-2., -.9, 0., .8, 1., 2.], [-2., -1., -.9999, .8, 1., 2.],
                     [-2., -1.0005, 0., .8, 1., 2.]):
            session = fixture()
            session["SU"][0]["xvec"]["COFF"] = axis
            self.assertEqual(t.prepare_session(session)["report"]["status"], "unsupported")

    def test_near_grid_rounding_has_unique_source_match(self):
        session = fixture()
        session["SU"][0]["xvec"]["COFF"] = [-2., -1.0001, 0., .8001, 1.0001, 2.]
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "transformed")
        self.assertEqual(result["layout"][0]["source_columns_one_based"], [2, 3, 4, 5])

    def test_duplicate_cluster_is_identity_failure_not_exclusion(self):
        session = fixture()
        session["SU"][1]["cluster_id"] = 10
        with self.assertRaisesRegex(t.Unsupported, "duplicate"):
            t.prepare_session(session)

    def test_nonconstant_underflow_is_not_treated_as_constant_source_zero(self):
        with self.assertRaisesRegex(t.Unsupported, "underflow"):
            t.normalize([[1e-200, 2e-200], [3e-200, 4e-200]], 2, 2)
        session = fixture()
        session["SU"][0]["hmat"]["COFF"] = [
            [float(r * 6 + c + 1) * 1e-200 for c in range(6)] for r in range(6)]
        result = t.prepare_session(session)
        self.assertEqual(result["report"]["status"], "unsupported")
        self.assertIn("underflow", result["report"]["reason"])
        self.assertEqual(result["report"]["cluster_ids"], [10, 11, 12, 13, 14])
        self.assertIsNone(result["data"])


class FullCohortBoundary(unittest.TestCase):
    def test_full_expert_and_naive_counts_preserve_excluded_sessions(self):
        for cohort in ("Expert", "Naive"):
            sessions, ids = cohort_fixture(cohort)
            result = t.prepare_cohort(sessions, cohort=cohort, expected_session_ids=ids)
            self.assertEqual(result["status"], "transformed")
            self.assertEqual(len(result["reports"]), t.COHORT_SESSION_COUNTS[cohort])
            self.assertEqual(result["all_source_session_ids"], ids)
            self.assertEqual(len(result["tensor_info"]), 5)
            self.assertEqual(result["tensor_info"][0]["source_unit_one_based"], 1)
            self.assertFalse(result["whole_task_complete"])
            self.assertFalse(result["native_parity"])

    def test_missing_extra_reordered_and_mixed_sessions_refused(self):
        sessions, ids = cohort_fixture()
        for altered in (sessions[:-1], sessions + [sessions[0]], list(reversed(sessions))):
            with self.assertRaisesRegex(t.Unsupported, "coverage/order"):
                t.prepare_cohort(altered, cohort="Expert", expected_session_ids=ids)
        sessions[0]["cohort"] = "Naive"
        with self.assertRaisesRegex(t.Unsupported, "mixing"):
            t.prepare_cohort(sessions, cohort="Expert", expected_session_ids=ids)

    def test_source_subset_cannot_be_declared_complete(self):
        with self.assertRaisesRegex(t.Unsupported, "complete"):
            t.prepare_cohort([fixture()], cohort="Expert", expected_session_ids=["invented-000"])

    def test_one_unsupported_session_blocks_every_partial_tensor(self):
        sessions, ids = cohort_fixture()
        sessions[1] = fixture(ids[1])
        sessions[1]["S"]["vios"][0] = 1
        result = t.prepare_cohort(sessions, cohort="Expert", expected_session_ids=ids)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(len(result["reports"]), 191)
        self.assertEqual(result["reports"][1]["cluster_ids"], [10, 11, 12, 13, 14])
        self.assertIsNone(result["data"])
        self.assertEqual(result["tensor_info"], [])

    def test_mismatched_grid_preserves_reports_but_refuses_concat(self):
        sessions, ids = cohort_fixture()
        sessions[1] = fixture(ids[1])
        sessions[1]["SU"][0]["xvec"]["COFF"][2] = .01
        result = t.prepare_cohort(sessions, cohort="Expert", expected_session_ids=ids)
        self.assertEqual(result["status"], "unsupported")
        self.assertIn("grids differ", result["reason"])
        self.assertIsNone(result["data"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
