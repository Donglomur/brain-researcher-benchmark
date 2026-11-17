"""Generated raw operands only; no model fits or authentic inputs."""
import copy
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geometry_bridge as B
from deps import G, R, P


def fixture():
    generated = np.random.RandomState(91)
    z = generated.normal(size=(503, 4))
    x = z @ generated.normal(size=(4, 21)) + generated.normal(size=(503, 21))
    rows = np.array([f"bin-{i}" for i in range(503)])
    units = np.array([f"unit-{i}" for i in range(21)])
    rng = np.random.RandomState(213423)
    before = R.state(rng)
    rr, uu = rng.choice(503, 500, replace=False), rng.choice(21, 19, replace=False)
    teacher_state = R.state(rng)
    teachers = rng.randn(4, 500)
    labels = np.sign(z[rr] @ teachers)
    valid = np.flatnonzero(np.abs(labels.mean(axis=0)) < 0.25)
    train = rng.choice(500, 300, replace=False)
    test = np.setdiff1d(np.arange(500), train)
    job = {"case_id": "KL8-s01-CA1", "animal": "KL8", "session": 1,
           "region": "CA1", "repetition": 0, "region_seed": 213423}
    checkpoint = {"job": job, "rng_before": before, "rng_after": R.state(rng),
        "row_positions": rr, "unit_positions": uu, "row_ids": rows[rr], "unit_ids": units[uu],
        "training_row_ids": rows[rr][train], "test_row_ids": rows[rr][test],
        "packet_pin": {"sha256": "1" * 64, "bytes": 1, "path": "generated.npz"},
        "behavior": {"accuracy": None, "status": "unavailable_complete_epoch_trial_table"},
        "readout": {"teacher_identity": R.array_identity(teachers),
             "pre_teacher_state_sha256": R.digest(teacher_state), "latent_identity": R.array_identity(z[rr]),
             "valid_teacher_indices": valid, "training_positions": train, "test_positions": test,
             "rng_before": teacher_state, "rng_after": R.state(rng), "svc_policy": R.SVC_POLICY}}
    prepared = {"x": x, "z": z, "row_ids": rows, "unit_ids": units, "case_id": job["case_id"]}
    # Deliberately perfect generated reference predictions; not fitted SVC.
    ref = B.make_reference(prepared, checkpoint, (1 + labels[test][:, valid]) / 2,
                           checkpoint_sha256="2" * 64, source_prediction_sha256="3" * 64, reference_chain=B.ReferenceChain())
    joint = np.column_stack([x[rr][:, uu], z[rr]])
    joint = joint - joint.mean(axis=0)
    cov = joint.T @ joint / 500
    candidate = {"schema": B.SCHEMA, "job_id": P.geometry_id(job), "method_sha256": "4" * 64,
        "row_ids": rows[rr], "unit_ids": units[uu], "training_row_ids": rows[rr][train],
        "test_row_ids": rows[rr][test], "valid_teacher_indices": valid,
        "joint_covariance": cov, "readout_predictions": labels[test][:, valid]}
    return prepared, checkpoint, ref, candidate


class GeometryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.prepared, self.checkpoint, self.ref, self.candidate = fixture()

    def test_independent_covariance_and_error_oracle(self):
        result = B.evaluate_geometry(self.ref, self.candidate)
        # np.cov is an independently composed covariance route and divisor.
        oracle = np.cov(np.column_stack([self.ref["points"], self.ref["latents"]]),
                        rowvar=False, bias=True)
        np.testing.assert_allclose(result["candidate_reconstruction"]["source_joint_covariance"],
                                   oracle, rtol=1e-13, atol=1e-13)
        self.assertEqual(result["candidate_reconstruction"]["max_absolute_covariance_difference"], 0)
        self.assertEqual(result["candidate_readout"]["error"], 0)
        self.assertEqual(result["source_result"]["readout"]["svc_error"], 0)
        self.assertIsNone(result["scientific_improvement"])
        self.assertFalse(result["qualification"])

    def test_candidate_error_uses_classification_not_hebbian_zero_rule(self):
        self.candidate["readout_predictions"] = np.zeros_like(self.candidate["readout_predictions"])
        r = B.evaluate_geometry(self.ref, self.candidate)
        self.assertEqual(r["candidate_readout"]["error"], 1)
        self.assertEqual(r["source_result"]["readout"]["svc_error"], 0)

    def test_covariance_all529_coordinates_and_derived_change(self):
        self.candidate["joint_covariance"] = self.candidate["joint_covariance"].copy()
        self.candidate["joint_covariance"][0, 0] += 0.125
        r = B.evaluate_geometry(self.ref, self.candidate)["candidate_reconstruction"]
        self.assertEqual(r["max_absolute_covariance_difference"], 0.125)
        diff = r["covariance_coordinate_difference"]
        self.assertEqual(np.count_nonzero(diff), 1)
        self.assertEqual(diff.shape, (23, 23))
        self.assertNotEqual(r["geometry_differences"]["dimensionality"]["difference"], 0)

    def test_asymmetric_lower_left_rejected_before_ignored_block(self):
        self.candidate["joint_covariance"] = self.candidate["joint_covariance"].copy()
        self.candidate["joint_covariance"][22, 0] += 1
        with self.assertRaisesRegex(ValueError, "symmetric"):
            B.evaluate_geometry(self.ref, self.candidate)

    def test_nonphysical_covariance_not_repaired(self):
        self.candidate["joint_covariance"] = -np.eye(23)
        with self.assertRaises(ValueError):
            B.evaluate_geometry(self.ref, self.candidate)

    def test_missing_or_self_scored_candidate_fields_refused(self):
        for key in ["joint_covariance", "readout_predictions"]:
            c = dict(self.candidate); del c[key]
            with self.assertRaisesRegex(ValueError, "exact candidate"):
                B.evaluate_geometry(self.ref, c)
        c = dict(self.candidate, svc_error=0.0)
        with self.assertRaisesRegex(ValueError, "exact candidate"):
            B.evaluate_geometry(self.ref, c)

    def test_complete_native_identity_and_teacher_order_required(self):
        for key in ["row_ids", "unit_ids", "training_row_ids", "test_row_ids", "valid_teacher_indices"]:
            c = dict(self.candidate); c[key] = c[key][::-1]
            with self.assertRaisesRegex(ValueError, "identity/order"):
                B.evaluate_geometry(self.ref, c)

    def test_reference_draw_state_tampering_rejected(self):
        for key in ["row_positions", "unit_positions", "row_ids", "unit_ids", "training_row_ids"]:
            cp = copy.deepcopy(self.checkpoint); cp[key] = cp[key][::-1]
            with self.assertRaises(ValueError):
                B.make_reference(self.prepared, cp, self.ref["source_svc_predictions"],
                                 checkpoint_sha256="2" * 64, source_prediction_sha256="3" * 64, reference_chain=B.ReferenceChain())

    def test_reference_teacher_and_rng_tampering_rejected(self):
        for key in ["teacher_identity", "latent_identity", "pre_teacher_state_sha256"]:
            cp = copy.deepcopy(self.checkpoint); cp["readout"][key] = "f" * 64
            with self.assertRaises(ValueError):
                B.make_reference(self.prepared, cp, self.ref["source_svc_predictions"],
                                 checkpoint_sha256="2" * 64, source_prediction_sha256="3" * 64, reference_chain=B.ReferenceChain())

    def test_incomplete_source_predictions_not_filled_from_summary(self):
        with self.assertRaisesRegex(ValueError, "raw source SVC"):
            B.make_reference(self.prepared, self.checkpoint, np.zeros((200, 1)),
                             checkpoint_sha256="2" * 64, source_prediction_sha256="3" * 64, reference_chain=B.ReferenceChain())

    def test_global_reference_chain_rejects_restart_and_partial_completion(self):
        chain = B.ReferenceChain()
        chain.accept(self.checkpoint)
        with self.assertRaisesRegex(ValueError, "complete64000"):
            chain.finish()
        cp = copy.deepcopy(self.checkpoint)
        cp["job"]["case_id"] = "KL8-s02-CA1"
        cp["job"]["session"] = 2
        with self.assertRaisesRegex(ValueError, "RNG chain"):
            chain.accept(cp)
        with self.assertRaisesRegex(ValueError, "global coordinate"):
            chain.accept(self.checkpoint)

    def test_first_draw_must_start_from_fixed_region_seed(self):
        cp = copy.deepcopy(self.checkpoint)
        cp["rng_before"] = R.state(np.random.RandomState(8))
        with self.assertRaisesRegex(ValueError, "RNG chain"):
            B.ReferenceChain().accept(cp)

    def test_method_and_coordinate_identity_required(self):
        for key, value in [("method_sha256", "unknown"), ("job_id", "CA1-r001-KL8-s01-CA1")]:
            c = dict(self.candidate); c[key] = value
            with self.assertRaises(ValueError):
                B.evaluate_geometry(self.ref, c)

    def test_infinite_discrepancy_is_explicit_not_nan_or_finite_win(self):
        self.assertEqual(B._difference(np.inf, np.inf)["status"], "equal_positive_infinity")
        self.assertEqual(B._difference(np.inf, 1)["status"], "unequal_infinite_value")
        self.assertIsNone(B._difference(1, np.inf)["difference"])

    def test_complete_case_reduction_uses_real_existing_finalizer(self):
        result = B.evaluate_geometry(self.ref, self.candidate)
        rows = []
        for rep in range(500):
            row = dict(result, job=dict(result["job"], repetition=rep),
                       source_result=dict(result["source_result"], repetition=rep))
            rows.append(row)
        glm = {"schema": "source_glm_pr_session_v1", "condition": "current_source_code19",
            "case_id": "KL8-s01-CA1", "subset_pr": np.ones((500, 2)), "raw_pr": 1.0,
            "fitted_pr": 1.0, "mean_selected_cv_d2": 0.25, "mean_selected_cv_sem": 0.1,
            "packet_pin": self.ref["packet_pin"], "operand_role": "author_reference"}
        merged = B.reduce_geometry_case(rows, glm, dict(glm, fitted_pr=2.0, operand_role="candidate"), case_id="KL8-s01-CA1")
        self.assertEqual(merged["candidate_geometry"].shape, (500, 8))
        self.assertEqual(merged["source_result"]["geometry"].shape, (500, 8))
        self.assertEqual(merged["candidate_readout_mean_error"], 0)
        self.assertEqual(merged["source_result"]["glm_expected_pr"], 1.0)
        self.assertEqual(merged["candidate_glm_result"]["fitted_pr"], 2.0)
        with self.assertRaisesRegex(ValueError, "complete ordered"):
            B.reduce_geometry_case(rows[:-1], glm, dict(glm, operand_role="candidate"), case_id="KL8-s01-CA1")

    def test_full_panel_metadata_order_and_duplicate_refused(self):
        # Actual full roster, no original arrays or scientific full-grid run.
        ids = [j["case_id"] for j in R.geometry_plan() if j["repetition"] == 0]
        self.assertEqual(len(ids), 128)
        self.assertEqual(len(set(ids)), 128)
        with self.assertRaisesRegex(ValueError, "complete original128"):
            B.reduce_panel([{"case_id": ids[0]}] * 128)

    def test_glm_pr_uses_paired_draws_and_separate_operand_roles(self):
        rng = np.random.RandomState(8)
        counts = rng.randint(1, 15, (20, 21)).astype(float)
        job = next(j for j in G.job_plan() if j["basis_index"] == G.GRID.index(G.FIGURE_BASIS))
        fitted = {"case_id": "KL8-s01-CA1", "job": job, "packet_pin": self.ref["packet_pin"],
                  "counts": counts, "predictions": counts + 0.1,
                  "cv_scores": np.full((21, 10, 10), 0.25),
                  "selected_alpha_indices": np.zeros(21, dtype=int),
                  "row_ids": np.array([f"r{i}" for i in range(20)]),
                  "unit_ids": np.array([f"u{i}" for i in range(21)])}
        candidate = dict(fitted, predictions=counts[:, ::-1] + 0.1)
        a, b = B.paired_glm_pr(fitted, candidate, rng=np.random.RandomState(15))
        np.testing.assert_array_equal(a["subset_unit_positions"], b["subset_unit_positions"])
        self.assertEqual(a["operand_role"], "author_reference")
        self.assertEqual(b["operand_role"], "candidate")
        self.assertEqual(a["packet_pin"], b["packet_pin"])
        bad = dict(candidate, packet_pin={"sha256": "f" * 64})
        with self.assertRaisesRegex(ValueError, "packet or case"):
            B.paired_glm_pr(fitted, bad, rng=np.random.RandomState(15))

    def test_case_reduction_rejects_cross_packet_and_behavior(self):
        result = B.evaluate_geometry(self.ref, self.candidate)
        rows = [dict(result, job=dict(result["job"], repetition=i),
                     source_result=dict(result["source_result"], repetition=i)) for i in range(500)]
        glm = {"schema": "source_glm_pr_session_v1", "condition": "current_source_code19",
               "case_id": "KL8-s01-CA1", "subset_pr": np.ones((500, 2)), "raw_pr": 1.0,
               "fitted_pr": 1.0, "mean_selected_cv_d2": 0.25, "mean_selected_cv_sem": 0.1,
               "packet_pin": self.ref["packet_pin"], "operand_role": "author_reference"}
        candidate_glm = dict(glm, operand_role="candidate", packet_pin={"sha256": "f" * 64})
        with self.assertRaisesRegex(ValueError, "packet identities"):
            B.reduce_geometry_case(rows, glm, candidate_glm, case_id="KL8-s01-CA1")
        candidate_glm["packet_pin"] = self.ref["packet_pin"]
        rows[-1]["source_result"]["behavior"] = {"accuracy": 1.0,
                                                   "status": "declared_complete_epoch_trial_mean"}
        with self.assertRaisesRegex(ValueError, "behavior provenance"):
            B.reduce_geometry_case(rows, glm, candidate_glm, case_id="KL8-s01-CA1")

    def test_complete_panel_reduction_retains_source_candidate_case_join(self):
        # Full source roster and real finalizers, repeated generated numeric
        # operands. This is not 64,000 independent empirical draw executions.
        result = B.evaluate_geometry(self.ref, self.candidate)
        repetitions = [dict(result, job=dict(result["job"], repetition=i),
                            source_result=dict(result["source_result"], repetition=i)) for i in range(500)]
        glm = {"schema": "source_glm_pr_session_v1", "condition": "current_source_code19",
               "case_id": "KL8-s01-CA1", "subset_pr": np.ones((500, 2)), "raw_pr": 1.0,
               "fitted_pr": 1.0, "mean_selected_cv_d2": 0.25, "mean_selected_cv_sem": 0.1,
               "packet_pin": self.ref["packet_pin"], "operand_role": "author_reference"}
        base = B.reduce_geometry_case(repetitions, glm, dict(glm, operand_role="candidate", fitted_pr=2.0),
                                      case_id="KL8-s01-CA1")
        rows = []
        for animal in R.ANIMALS:
            for session in R.SESSIONS:
                for region in R.REGIONS:
                    cid = f"{animal}-s{session:02d}-{region}"
                    rows.append(dict(base, case_id=cid, source_result=dict(base["source_result"], case_id=cid),
                                     candidate_glm_result=dict(base["candidate_glm_result"], case_id=cid)))
        panel = B.reduce_panel(rows)
        self.assertEqual(panel["candidate_geometry"].shape, (128, 500, 8))
        self.assertEqual(panel["candidate_readout_errors"].shape, (128, 500))
        self.assertEqual(panel["source_result"]["regions"]["CA1"]["geometry"].shape, (500, 8, 8, 8))
        self.assertEqual(panel["candidate_glm_results"][0]["fitted_pr"], 2.0)
        self.assertEqual(panel["source_result"]["regions"]["CA1"]["glm_participation_ratios"][0, 0, 1], 1.0)
        first, second = rows[0]["source_result"]["case_id"], rows[1]["source_result"]["case_id"]
        rows[0]["source_result"]["case_id"], rows[1]["source_result"]["case_id"] = second, first
        with self.assertRaisesRegex(ValueError, "source/candidate case identity"):
            B.reduce_panel(rows)


if __name__ == "__main__":
    unittest.main()
