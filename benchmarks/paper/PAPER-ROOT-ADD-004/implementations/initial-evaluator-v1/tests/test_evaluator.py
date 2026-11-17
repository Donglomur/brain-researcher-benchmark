"""Generated mathematical controls; no authentic data or reproduction evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location("respiration_evaluator", Path(__file__).parents[1] / "evaluator.py")
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def participant(pid="P02"):
    rng = np.random.default_rng(41)
    loc_t = np.arange(-40, 601) / 200
    ret_t = np.arange(-400, 601) / 200
    exh_t = np.arange(-1000, 1001) / 200
    loc, ret = [], []
    for session in ("object", "scene"):
        for category in ("object", "scene"):
            for rep in range(3):
                signal = (1 if category == "scene" else -1) * np.exp(-((loc_t - .7) / .8) ** 2)
                loc.append({"trial_id": f"loc/{session}/{category}/{rep}", "session": session,
                            "category": category, "eeg": np.array([signal, -.5 * signal]) + rng.normal(0, .4, (2, len(loc_t)))})
        for test in ("pre", "post"):
            for rep in range(4):
                phase = np.mod(2 * np.pi * .25 * ret_t + rep / 3, 2 * np.pi)
                carrier = (1 + .3 * np.cos(ret_t)) * np.sin(2 * np.pi * 10 * ret_t + rep / 10)
                signal = (1 if session == "scene" else -1) * np.exp(-((ret_t - .8) / .8) ** 2)
                exht_cue = exh_t + 1
                exhcarrier = (1 + .3 * np.cos(exht_cue)) * np.sin(2 * np.pi * 10 * exht_cue + rep / 10)
                exhsignal = (1 if session == "scene" else -1) * np.exp(-((exht_cue - .8) / .8) ** 2)
                ret.append({"trial_id": f"ret/{session}/{test}/{rep}", "session": session, "test": test,
                            "is_old": True, "recognized": rep != 3, "remembered": rep < 2,
                            "eeg": np.array([signal + carrier, -.5 * signal + .7 * carrier]) + rng.normal(0, .1, (2, len(ret_t))),
                            "respiration_phase_radians": phase, "exhalation_trough_seconds": [1.],
                            "exhalation_epoch_trough_seconds": 1.,
                            "exhalation_eeg": np.array([exhsignal + exhcarrier, -.5 * exhsignal + .7 * exhcarrier]) + rng.normal(0, .1, (2, len(exh_t)))})
    return {"participant_id": pid, "channels": ["Fz", "Pz"], "localizer_times": loc_t,
            "retrieval_times": ret_t, "exhalation_times": exh_t, "localizer": loc, "retrieval": ret}


def packet():
    base = participant()
    return {"schema": "respiration-epochs-v1", "expected_participant_ids": e.SOURCE_ROSTER,
            "provenance": {"data_kind": "generated_engineering_control", "sample_rate_hz": 200,
                           "epoch_preprocessing": "generated arrays; no empirical preprocessing",
                           "respiration_phase_convention": "generated radians; inhalation phase zero",
                           "trial_label_source": "generated deterministic control",
                           "cohort_source": "source IDs used only as generated fixture keys"},
            "participants": [{**base, "participant_id": pid} for pid in e.SOURCE_ROSTER]}


class NumericalControls(unittest.TestCase):
    def test_auc_pairwise_oracle_ties_and_reversal(self):
        y, s = np.array([0, 0, 1, 1]), np.array([0., 2., 2., 4.])
        pairs = [(a > b) + .5 * (a == b) for a in s[y == 1] for b in s[y == 0]]
        self.assertAlmostEqual(e.auc(y, s), sum(pairs) / 4)
        self.assertAlmostEqual(e.auc(y, -s), 1 - sum(pairs) / 4)
        self.assertEqual(e.auc([0, 1], [1, 1]), .5)
        self.assertTrue(np.isnan(e.auc([1, 1], [1, 2])))

    def test_signed_average_precedes_modulus(self):
        got = e.decision_confidence(np.array([[[2., 3.], [-2., 1.]]]), [.15, 1.5])
        np.testing.assert_array_equal(got, [[0., 2.]])

    def test_lda_one_feature_closed_form(self):
        x = np.array([[-3.], [-1.], [1.], [3.]])
        m = e.fit_lda(x, [0, 0, 1, 1])
        # Class means -2,+2; pooled within-class variance=2; 10% ridge=>2.2.
        self.assertAlmostEqual(m["weight"][0], 4 / 2.2)
        self.assertAlmostEqual(m["intercept"], 0.)
        self.assertEqual(e.auc([0, 0, 1, 1], (x @ m["weight"])), 1.)

    def test_model_weights_ignore_retrieval_values(self):
        x = np.array([[[-3., -2.]], [[-1., -1.]], [[1., 1.]], [[3., 2.]]])
        _, first = e.temporal_decisions(x, [0, 0, 1, 1], x)
        _, second = e.temporal_decisions(x, [0, 0, 1, 1], x * 1000 + 71)
        for a, b in zip(first, second):
            np.testing.assert_array_equal(a["weight"], b["weight"])
            self.assertEqual(a["intercept"], b["intercept"])

    def test_spearman_ties_undefined_and_negative_coupling(self):
        self.assertAlmostEqual(e.spearman([1, 1, 3, 4], [4, 4, 2, 1]), -1.)
        self.assertTrue(np.isnan(e.spearman([1, 1, 1], [1, 2, 3])))
        confidence = np.arange(4.)[:, None] * np.ones((4, 7))
        power = -confidence[:, None, :]
        np.testing.assert_allclose(e.coupling(confidence, power)["smoothed_250ms"], -1.)

    def test_resultant_cancellation_and_rotation(self):
        self.assertAlmostEqual(e.resultant([0, np.pi])["length"], 0.)
        self.assertAlmostEqual(e.resultant([.4, .4])["length"], 1.)
        self.assertAlmostEqual(e.resultant([0, 1])["length"], e.resultant([2, 3])["length"])

    def test_hann_direct_scalar_oracle_and_padding(self):
        axis = np.arange(-200, 201) / 200
        signal = np.cos(2 * np.pi * 10 * axis)
        got = e.hann_power(signal[None, None, :], axis, [0], frequencies=[10]).item()
        # Independent scalar Fourier sum: 101 samples = nearest odd five cycles.
        n = 101
        taper = [.5 - .5 * np.cos(2 * np.pi * j / (n - 1)) for j in range(n)]
        amplitude = sum(taper[j] * signal[150 + j] * np.exp(-2j * np.pi * 10 * (j - 50) / 200) for j in range(n))
        self.assertAlmostEqual(got, abs(amplitude) ** 2 / sum(w * w for w in taper))
        with self.assertRaisesRegex(ValueError, "padding"):
            e.hann_power(signal[None, None, :], axis, [1], frequencies=[10])
        with self.assertRaisesRegex(ValueError, "sample aligned"):
            e.sample_indices(axis, [.001])

    def test_hann_18hz_uses_actual_nearest_odd_length(self):
        axis = np.arange(-200, 201) / 200
        signal = np.cos(2 * np.pi * 18 * axis)
        got = e.hann_power(signal[None, None, :], axis, [0], frequencies=[18]).item()
        # 5*200/18=55.555..., nearest odd is55, not57.
        n = 55
        taper = [.5 - .5 * np.cos(2 * np.pi * j / (n - 1)) for j in range(n)]
        amplitude = sum(taper[j] * signal[173 + j] * np.exp(-2j * np.pi * 18 * (j - 27) / 200) for j in range(n))
        self.assertAlmostEqual(got, abs(amplitude) ** 2 / sum(w * w for w in taper))

    def test_memory_pools_hit_counts_and_keeps_four_cells(self):
        rows = []
        for session in ("object", "scene"):
            for test in ("pre", "post"):
                for j in range(4 if session == "scene" else 1):
                    rows.append({"session": session, "test": test, "is_old": True,
                                 "recognized": True, "remembered": session == "object"})
        result = e.memory_summary(rows)
        self.assertEqual(result["pooled_hit_accuracy"], .2)
        self.assertEqual(result["mean_four_cell_accuracy_diagnostic"], .5)
        with self.assertRaisesRegex(ValueError, "missing condition"):
            e.memory_summary(rows[1:])

    def test_zero_hit_diagnostic_cell_does_not_delete_valid_pooled_endpoint(self):
        rows = [{"session": session, "test": test, "is_old": True,
                 "recognized": session == "object", "remembered": session == "object"}
                for session in ("object", "scene") for test in ("pre", "post")]
        result = e.memory_summary(rows)
        self.assertEqual(result["pooled_hit_accuracy"], 1.)
        self.assertIsNone(e.json_safe(result)["cells"][2]["accuracy"])
        for row in rows:
            row["recognized"] = False
            row["remembered"] = False
        with self.assertRaisesRegex(ValueError, "zero pooled"):
            e.memory_summary(rows)


class AdmissionAndPipeline(unittest.TestCase):
    def test_participant_full_path_and_trial_reordering(self):
        p = participant()
        result = e.analyze_participant(p)
        self.assertAlmostEqual(result["behavior"]["pooled_hit_accuracy"], 2 / 3)
        self.assertEqual(result["exhalation_groups"]["remembered"]["n_trials"], 8)
        self.assertEqual(result["exhalation_groups"]["not_remembered"]["n_trials"], 8)
        self.assertEqual(result["remembered_minus_not_auc"].shape, (34, 81))
        self.assertTrue(np.isfinite(result["remembered_minus_not_coupling"]).all())
        p["retrieval"].reverse()
        p["localizer"].reverse()
        second = e.analyze_participant(p)
        np.testing.assert_array_equal(result["remembered_minus_not_auc"], second["remembered_minus_not_auc"])
        np.testing.assert_array_equal(result["remembered_minus_not_coupling"], second["remembered_minus_not_coupling"])

    def test_duplicate_trials_and_inconsistent_labels_rejected(self):
        p = participant()
        p["retrieval"][0]["trial_id"] = p["localizer"][0]["trial_id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            e.validate_participant(p)
        p = participant()
        p["retrieval"][0]["recognized"] = False
        with self.assertRaisesRegex(ValueError, "true recognition hit"):
            e.validate_participant(p)

    def test_last_strictly_interior_trough_and_foil_audit(self):
        p = participant()
        p["retrieval"][0]["exhalation_trough_seconds"] = [0., 1., 2., 3.]
        p["retrieval"][0]["exhalation_epoch_trough_seconds"] = 2.
        p["retrieval"][1]["exhalation_trough_seconds"] = [0., 3.]
        p["retrieval"][2]["is_old"] = False
        result = e.analyze_participant(p)
        counts = {r["status"] for r in result["retrieval_admission_audit"]}
        self.assertEqual(counts, {"included", "no_trough_strictly_0_to_3s", "foil"})
        row = next(r for r in result["retrieval_admission_audit"] if r["trial_id"] == p["retrieval"][0]["trial_id"])
        self.assertEqual(row["candidate_trough_count"], 2)
        self.assertEqual(row["selected_trough_seconds"], 2.)
        p["retrieval"][0]["exhalation_epoch_trough_seconds"] = 1.
        with self.assertRaisesRegex(ValueError, "last strictly interior"):
            e.validate_participant(p)

    def test_complete_source_roster_and_channel_order_enforced(self):
        p = packet()
        p["participants"] = p["participants"][:-1]
        with self.assertRaisesRegex(ValueError, "18-person"):
            e.evaluate(p)
        p = packet()
        p["participants"][1] = {**p["participants"][1], "channels": ["Pz", "Fz"]}
        with self.assertRaisesRegex(ValueError, "channel identities"):
            e.evaluate(p)

    def test_complete_generated_cohort_does_not_qualify(self):
        result = e.evaluate(packet())
        self.assertEqual(result["group"]["n_participants"], 18)
        self.assertFalse(result["scientifically_qualified"])
        self.assertIsNone(result["binary_reward"])
        self.assertIsNone(e.json_safe(result)["group"]["peak_resultant_vs_memory_spearman"])
        self.assertGreater(len(result["holds"]), 5)


if __name__ == "__main__":
    unittest.main()
