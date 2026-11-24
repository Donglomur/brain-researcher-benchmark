"""Generated engineering controls; no authentic neuroscience data or claims."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import beta_evaluator as b


def piecewise(fs=1200):
    a = np.ones((2, int(3.5 * fs)))
    a[1] *= 3
    active = b.window_indices(fs, a.shape[1], (.3, .8))
    rebound = b.window_indices(fs, a.shape[1], (1, 1.5))
    a[:, active] = np.array([.5, 3])[:, None]
    a[:, rebound] = np.array([1.5, 4.5])[:, None]
    return a


def fixture():
    records, arrays = [], {}
    rng = np.random.default_rng(100)
    for i, pid in enumerate(b.CHILDREN + b.ADULTS):
        group = "children" if pid in b.CHILDREN else "adults"
        row = {"participant_id": pid, "group": group, "included": pid not in b.AUTHOR_EXCLUSIONS}
        if row["included"]:
            age = 2 + i * .35 if group == "children" else 20 + (i - 27) * .6
            row.update(age_years=age, head_size_cm=float(46 + rng.normal()), motion_mm=float(abs(rng.normal())))
            n = 2 + i % 4
            amplitude = np.ones((n, 4200))
            amplitude[:, 359:960] = .85 - .004 * age
            amplitude[:, 1199:1800] = 1 + .006 * age + .01 * row["motion_mm"]
            arrays[pid] = {"index": amplitude, "pinky": amplitude * 3.7}
            row.update(retained_index_trials=n, retained_pinky_trials=n)
        records.append(row)
    manifest = {"schema_version": 1, "task_id": b.TASK_ID, "source_revision": b.SOURCE_REVISION,
        "band_hz": [13, 30], "quantity": "hilbert_amplitude", "sampling_frequency_hz": 1200,
        "seed": 42, "event_shift_repeats": 2, "bootstrap_repeats": 10, "matched_trial_count": 2,
        "participants": records}
    for key in ("preprocessing_provenance", "artifact_policy_provenance", "source_peak_provenance", "envelope_extraction_provenance", "metadata_provenance"):
        manifest[key] = "generated engineering control; no native preprocessing or empirical evidence"
    return manifest, arrays


class EnvelopeTests(unittest.TestCase):
    def test_normalization_discrepancy_is_observable(self):
        # Hand calculation: trial active fractions(-.5,0), rebound(.5,.5).
        primary = b.summarize_envelopes(piecewise(), 1200)
        paper = b.summarize_envelopes(piecewise(), 1200, normalization="paper_ratio_of_means")
        self.assertAlmostEqual(primary["active_fraction"], -.25)
        self.assertAlmostEqual(primary["rebound_fraction"], .5)
        self.assertAlmostEqual(primary["modulation_fraction"], .75)
        self.assertAlmostEqual(paper["active_fraction"], -.125)
        self.assertAlmostEqual(paper["modulation_fraction"], .625)

    def test_independently_derived_reference_fixture(self):
        a = np.ones((2, 4200)); a[1] *= 9
        a[0, 1199:1800] = 2
        self.assertAlmostEqual(b.summarize_envelopes(a, 1200)["modulation_fraction"], .5)
        self.assertAlmostEqual(b.summarize_envelopes(a, 1200, normalization="paper_ratio_of_means")["modulation_fraction"], .1)

    def test_matlab_index_endpoints_not_plot_times(self):
        sl = b.window_indices(1200, 4200, (.3, .8))
        self.assertEqual((sl.start, sl.stop), (359, 960))
        a = np.ones((2, 4200))
        a[:, 359] = 2
        self.assertAlmostEqual(b.summarize_envelopes(a, 1200)["active_fraction"], 1 / 601)

    def test_amplitude_scale_invariance(self):
        a = piecewise()
        scaled = a * np.array([10, .1])[:, None]
        self.assertAlmostEqual(b.summarize_envelopes(a, 1200)["modulation_fraction"], b.summarize_envelopes(scaled, 1200)["modulation_fraction"])

    def test_bad_amplitude_or_single_zero_baseline_rejected(self):
        for bad in (np.zeros((2, 4200)), np.full((2, 4200), np.nan), np.full((2, 4200), -1), np.ones((2, 4199))):
            with self.assertRaises(b.ContractError):
                b.summarize_envelopes(bad, 1200)
        a = piecewise()
        a[0, 2999:3600] = 0
        with self.assertRaises(b.ContractError):
            b.summarize_envelopes(a, 1200)

    def test_complex_analytic_signal_cannot_silently_change_endpoint(self):
        analytic = np.ones((2, 4200), dtype=complex)
        analytic[:, 1199:1800] += np.sqrt(3) * 1j
        # |1 + sqrt(3)i| = 2 during rebound, versus magnitude 1 at rest.
        # Dropping imaginary values would instead report zero modulation.
        self.assertAlmostEqual(b.summarize_envelopes(np.abs(analytic), 1200)["modulation_fraction"], 1)
        with self.assertRaisesRegex(b.ContractError, "real numeric"):
            b.summarize_envelopes(analytic, 1200)
        with self.assertRaises(b.ContractError):
            b.summarize_envelopes(np.ones((2, 4200), dtype=complex), 1200)

    def test_nonnumeric_and_boolean_arrays_are_not_amplitudes(self):
        for values in (np.full((2, 4200), "1"), np.ones((2, 4200), dtype=bool),
                       np.ones((2, 4200), dtype=object)):
            with self.subTest(dtype=str(values.dtype)):
                with self.assertRaisesRegex(b.ContractError, "real numeric"):
                    b.validate_envelopes(values, 1200)

    def test_matching_is_condition_independent_and_amplitude_blind(self):
        a = np.tile(np.arange(10)[:, None], (1, 4200))
        first = b.matched_trials(a, a + 100, 4, 5, "sub-001")
        again = b.matched_trials(a * 5, a - 99, 4, 5, "sub-001")
        for c in b.CONDITIONS:
            self.assertEqual(first[c][1], again[c][1])
            self.assertEqual(len(set(first[c][1])), 4)
        with self.assertRaises(b.ContractError):
            b.matched_trials(a, a[:3], 4, 5, "sub-001")

    def test_shift_null_constant_signal_and_reproducibility(self):
        kwargs = dict(repeats=9, seed=1, participant_id="sub-001", condition="index")
        result = b.event_shift_control(np.ones((3, 4200)), 1200, **kwargs)
        self.assertEqual(result["null_modulation_fraction"], [0] * 9)
        self.assertEqual(result["absolute_surrogate_exceedance_fraction_plus_one"], 1)
        self.assertEqual(b.event_shift_control(piecewise(), 1200, **kwargs), b.event_shift_control(piecewise(), 1200, **kwargs))


class StatisticalTests(unittest.TestCase):
    def test_ols_known_slope_and_rank_failure(self):
        x = np.arange(10, dtype=float)
        fitted = b.ols(3 + 2 * x, x, ["age_years"])
        np.testing.assert_allclose(fitted["coefficients"], [3, 2], atol=1e-12)
        self.assertAlmostEqual(fitted["r_squared"], 1)
        with self.assertRaises(b.ContractError):
            b.ols(x, np.ones((10, 2)), ["a", "b"])

    def test_subject_level_models_and_constant_count_matched_design(self):
        manifest, arrays = fixture()
        result = b.evaluate(manifest, arrays)
        primary = result["all_retained"]["age_models"]["pooled"]["index"]["modulation_fraction"]
        self.assertEqual(primary["unadjusted"]["n_participants"], 51)
        self.assertAlmostEqual(primary["unadjusted"]["r_squared"], primary["pearson"]["r"] ** 2)
        matched = result["matched_trials"]["age_models"]["pooled"]["index"]["modulation_fraction"]["adjusted"]
        self.assertEqual(matched["status"], "computed")
        self.assertEqual(matched["terms"], ["intercept", "age_years", "head_size_cm", "motion_mm"])
        self.assertEqual(result["population"]["original"], 53)
        self.assertEqual(len(result["population"]["ledger"]), 53)
        self.assertEqual(len(result["prospective_participant_folds"]), 51)
        self.assertFalse(result["native_reproduction"])
        boot = result["all_retained"]["pooled_age_bootstrap"]["endpoints"]["index"]["modulation_fraction"]
        self.assertEqual(boot["valid_slope_replicates"], 10)
        self.assertLessEqual(boot["age_slope_percentile_95"][0], boot["age_slope_percentile_95"][1])

    def test_folds_ignore_outcomes_and_keep_subject_once(self):
        manifest, _ = fixture()
        rows = [r for r in manifest["participants"] if r["included"]]
        folds = b.age_stratified_folds(rows)
        reversed_rows = list(reversed(rows))
        self.assertEqual(folds, b.age_stratified_folds(reversed_rows))
        for group in ("children", "adults"):
            counts = [sum(folds[r["participant_id"]] == f for r in rows if r["group"] == group) for f in range(5)]
            self.assertLessEqual(max(counts) - min(counts), 1)

    def test_missing_subject_covariate_wrong_quantity_and_count_rejected(self):
        manifest, arrays = fixture()
        variants = []
        m = copy.deepcopy(manifest); m["participants"].pop(); variants.append(m)
        m = copy.deepcopy(manifest); del m["participants"][0]["motion_mm"]; variants.append(m)
        m = copy.deepcopy(manifest); m["quantity"] = "power"; variants.append(m)
        m = copy.deepcopy(manifest); m["participants"][0]["retained_index_trials"] += 1; variants.append(m)
        m = copy.deepcopy(manifest); m["participants"][0]["included"] = False; variants.append(m)
        for m in variants:
            with self.assertRaises(b.ContractError):
                b.evaluate(m, arrays)

    def test_cli_full53_pins_and_digest_rejection(self):
        manifest, arrays = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for row in manifest["participants"]:
                if not row["included"]:
                    continue
                name = row["participant_id"] + ".npz"
                np.savez(path / name, **arrays[row["participant_id"]])
                row.update(envelopes_npz=name, envelopes_sha256=hashlib.sha256((path / name).read_bytes()).hexdigest())
            (path / "manifest.json").write_text(json.dumps(manifest))
            command = [sys.executable, str(ROOT / "beta_evaluator.py"), str(path / "manifest.json"), str(path / "result.json")]
            subprocess.run(command, check=True, capture_output=True, text=True)
            result = json.loads((path / "result.json").read_text())
            self.assertEqual(len(result["input_pins"]), 51)
            self.assertEqual(result["scientific_qualification"], "unknown")
            manifest["participants"][0]["envelopes_sha256"] = "0" * 64
            (path / "manifest.json").write_text(json.dumps(manifest))
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("digest mismatch", failed.stderr)


if __name__ == "__main__":
    unittest.main()
