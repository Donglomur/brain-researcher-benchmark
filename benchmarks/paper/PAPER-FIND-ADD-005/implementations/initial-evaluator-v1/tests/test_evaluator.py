"""Bounded engineering controls; never authentic macaque results.

Boundary/likelihood/eye oracles were derived by the independent source worker.
"""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from evaluator import (Config, ContractError, SOURCE_COMMIT, blocked_folds, evaluate,
                       event_design, fit_poisson, log_likelihood, make_design,
                       normalize_cell, poisson_deviance, source_bin_index, temporal_basis)


def raw_trial(nr=1, duration=1600):
    return {"trial_nr": nr, "fixon2fixon": duration, "condition_code": 2,
            "direction_C": 1, "gap_direction": 180 * (nr % 2),
            "fix_on": 0, "cue_start": 100, "cue_stop": 150,
            "c_start": 300, "c_stop": 500, "choice_target": 800,
            "saccade_landmarks": [1000, 1030], "reward_start": 1200,
            "reward_duration": 80, "saccadeAmplitude": 10,
            "event_presentations": [1, 1, 1, 1],
            "SS": [i * 0.05 + 0.005 for i in range(1, 29)] + [0.32] * (nr % 3),
            "n_minus_1": {"condition_code": 2, "direction_C": 1, "gap_direction": 180 * ((nr-1) % 2)},
            "eyeX": [0.] * (3999 + duration), "eyeY": [0.] * (3999 + duration)}


def document(n=12):
    return {"schema": "erasmus-source-trials-json-v1", "source_commit": SOURCE_COMMIT,
            "cells": [{"monkey": "ENGINEERING_FIXTURE", "cell_id": "generated-unit", "trials": [raw_trial(i) for i in range(n)]}]}


def small_cfg():
    return Config(event_bases=2, outer_folds=3, inner_folds=2, lambdas=(0.1,))


class SourceMappingTests(unittest.TestCase):
    def test_independent_spike_boundary_oracle(self):
        times = np.array([0, 25, 25.001, 50, 99.49])
        actual = np.bincount(source_bin_index(times, 25), minlength=4)
        np.testing.assert_array_equal(actual, [2, 2, 0, 1])
        # MATLAB positive round: .0995 sec rounds to duration100 and is excluded.
        clipped = times[np.floor(times + .5) < 100]
        self.assertEqual(len(clipped), 5)
        self.assertFalse(np.floor(99.5 + .5) < 100)

    def test_full_converter_units_clipping_partial_bin_and_eye_origin(self):
        raw = raw_trial(duration=1607)
        raw["SS"] = [0, .025, .025001, .05, 1.6064, 1.6066, -.001]
        raw["eyeX"] = list(range(3999 + 1607))
        trials, audit = normalize_cell({"monkey": "M", "cell_id": "C", "trials": [raw]}, Config())
        self.assertEqual(audit, [])
        design = make_design(trials, Config())
        self.assertEqual(design["y"].sum(), 5)
        np.testing.assert_array_equal(design["y"][:2], [2, 2])
        self.assertEqual(design["y"][-1], 1)
        self.assertAlmostEqual(design["exposure"][-1], .007)
        self.assertAlmostEqual(design["X"][0, 30], 4011.0)
        self.assertEqual(trials[0]["times"]["delay_start"], 600)

    def test_source_exclusions_are_accounted(self):
        cells = document(5)["cells"][0]
        cells["trials"][0]["fixon2fixon"] = 0
        cells["trials"][1]["c_stop"] = -1
        cells["trials"][2]["event_presentations"] = [2]
        cells["trials"][3]["SS"] = []
        trials, audit = normalize_cell(cells, Config())
        self.assertEqual(len(trials), 1)
        self.assertEqual([a["reason"] for a in audit], ["source_duration_below_1ms", "source_invalid_c_stop", "source_repeated_event", "source_empty_SS"])
        self.assertEqual(trials[0]["position"], 4)

    def test_missing_history_omits_whole_cell(self):
        cells = document(2)["cells"][0]
        del cells["trials"][0]["n_minus_1"]
        trials, audit = normalize_cell(cells, Config())
        self.assertEqual(trials, [])
        self.assertEqual(audit[0]["scope"], "cell")
        self.assertEqual(audit[0]["trials"], 2)

    def test_derived_saccade_directions_and_reward_absence(self):
        raw = raw_trial(); raw["condition_code"] = 1; raw["gap_direction"] = 270
        raw["n_minus_1"] = {"condition_code": 1, "gap_direction": 90}
        raw["reward_duration"] = 0
        trials, _ = normalize_cell({"monkey": "M", "cell_id": "C", "trials": [raw]}, Config())
        self.assertEqual(trials[0]["saccade_direction"], 90)
        self.assertEqual(trials[0]["past_saccade"], 270)
        self.assertIsNone(trials[0]["times"]["reward_start"])
        design = make_design(trials, Config())
        self.assertTrue(np.all(design["X"][:, 25:30] == 0))

    def test_missing_eye_in_trial_is_explicit_exclusion_not_imputation(self):
        raw = raw_trial(); raw["eyeX"][4000] = None
        trials, audit = normalize_cell({"monkey": "M", "cell_id": "C", "trials": [raw]}, Config())
        self.assertFalse(trials)
        self.assertEqual(audit[0]["reason"], "prospective_nonfinite_eye_support")
        raw["eyeX"][4000] = 0; raw["eyeX"][10] = None
        trials, audit = normalize_cell({"monkey": "M", "cell_id": "C", "trials": [raw]}, Config())
        self.assertTrue(trials)

    def test_duplicate_trial_and_nonfinite_spike_rejected(self):
        cells = document(2)["cells"][0]; cells["trials"][1]["trial_nr"] = 0
        with self.assertRaises(ContractError): normalize_cell(cells, Config())
        cells = document(1)["cells"][0]; cells["trials"][0]["SS"] = [float("nan")]
        with self.assertRaises(ContractError): normalize_cell(cells, Config())


class DesignAndFitTests(unittest.TestCase):
    def test_source_progressive_basis_has_normalized_columns(self):
        cfg = Config(); basis = temporal_basis(cfg)
        self.assertEqual(basis.shape, (60, 5))
        np.testing.assert_allclose(basis.max(axis=0), np.ones(5))
        self.assertTrue(np.all(basis >= 0))
        # Independent scalar first component from pinned formula.
        sigma = 60 * 3 * 32 / (4 * 243 - 3 * 32)
        values = [(.5 + .5 * math.cos(2*math.pi*(t-(1+.5*sigma))/sigma)) if abs((t-(1+.5*sigma))/sigma)<.5 else 0 for t in range(1,61)]
        np.testing.assert_allclose(basis[:, 0], np.array(values) / max(values), atol=1e-14)

    def test_event_boundary_and_trial_reset(self):
        cfg = Config()
        at25, after25 = event_design(25, 10, cfg), event_design(25.001, 10, cfg)
        np.testing.assert_allclose(at25[1:9], after25[2:10])
        self.assertTrue(np.all(after25[:1] == 0))
        trials, _ = normalize_cell(document(2)["cells"][0], cfg)
        design = make_design(trials, cfg)
        # Reward kernels from the previous trial cannot enter next trial's early bins.
        self.assertTrue(np.all(design["X"][64:104, 25:30] == 0))

    def test_independent_likelihood_deviance_oracle(self):
        y, mu = np.array([0., 1., 2.]), np.ones(3)
        self.assertAlmostEqual(log_likelihood(y, mu), -3 - math.log(2))
        self.assertAlmostEqual(poisson_deviance(y, mu), 4 * math.log(2))
        self.assertAlmostEqual(log_likelihood(y, np.array([1., 1., 2.]))-log_likelihood(y, mu), 2*math.log(2)-1)

    def test_invalid_score_arrays_fail_closed(self):
        for score in (log_likelihood, poisson_deviance):
            with self.assertRaises(ContractError): score(np.array([1.5]), np.array([1.]))
            with self.assertRaises(ContractError): score(np.array([1.]), np.array([0.]))
            with self.assertRaises(ContractError): score(np.array([1.]), np.array([1., 1.]))

    def test_intercept_fit_and_exposure_are_not_mean_counts(self):
        x = np.zeros((3, 2)); y = np.array([1., 2., 3.]); exposure = np.array([.1, .2, .3])
        model = fit_poisson(x, y, exposure, .1, Config())
        np.testing.assert_allclose(model.predict(x, exposure), y, atol=1e-10)
        self.assertAlmostEqual(math.exp(model.coefficients[0]), 10)

    def test_train_only_scaling_and_all_zero_failure(self):
        x = np.array([[0.], [1.], [2.], [3.]])
        model = fit_poisson(x, np.array([1., 2., 2., 3.]), np.ones(4), .1, Config())
        self.assertAlmostEqual(model.mean[0], 1.5)
        before = model.mean.copy(); model.predict(np.array([[1000.]]), np.ones(1))
        np.testing.assert_array_equal(model.mean, before)
        with self.assertRaises(ContractError): fit_poisson(x, np.zeros(4), np.ones(4), .1, Config())
        with self.assertRaises(ContractError): fit_poisson(x, np.array([.1, 1, 1, 1]), np.ones(4), .1, Config())

    def test_whole_trial_purge_and_insufficient_data(self):
        positions = np.arange(12)
        folds = blocked_folds(positions, positions, 3, 1)
        self.assertEqual(sorted(np.concatenate([test for _, test in folds]).tolist()), list(range(12)))
        for train, test in folds:
            self.assertFalse(set(train) & set(test))
            self.assertTrue(np.all(np.abs(train[:, None] - test[None, :]) > 1))
        with self.assertRaises(ContractError): blocked_folds(np.arange(3), np.arange(3), 3, 1)

    def test_nonconvergence_is_not_scored(self):
        with self.assertRaises(ContractError):
            fit_poisson(np.arange(4.)[:, None], np.array([0., 0., 1., 20.]), np.ones(4), .001, Config(max_iterations=1))


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = document()
        cls.result = evaluate(cls.payload, small_cfg())

    def test_complete_nested_pipeline_coverage_and_unknown_qualification(self):
        result = self.result; cell = result["cells"][0]["result"]
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertFalse(result["benchmark_complete"])
        self.assertEqual(cell["trials"], 12)
        self.assertEqual(cell["bins"], 12*64)
        self.assertEqual(sorted(t for f in cell["folds"] for t in f["test_trials"]), list(range(12)))
        self.assertTrue(math.isfinite(cell["delta_log_likelihood_nats_per_spike"]))
        json.dumps(result, allow_nan=False)

    def test_outer_labels_do_not_change_fold_training_or_penalty(self):
        mutated = copy.deepcopy(self.payload)
        # First outer block is0..3, training is5..11; history guard removes4.
        for trial in mutated["cells"][0]["trials"][:4]: trial["SS"] += [.325] * 15
        other = evaluate(mutated, small_cfg())
        original = self.result["cells"][0]["result"]["folds"][0]["models"]
        changed = other["cells"][0]["result"]["folds"][0]["models"]
        for name in ("full", "reduced"):
            self.assertEqual(original[name]["penalty"], changed[name]["penalty"])
            self.assertEqual(original[name]["inner_scores"], changed[name]["inner_scores"])
            np.testing.assert_array_equal(original[name]["standardized_coefficients_including_intercept"], changed[name]["standardized_coefficients_including_intercept"])

    def test_default_configuration_runs_all_source_bases_and_nested_folds(self):
        result = evaluate(document(30))
        cell = result["cells"][0]["result"]
        self.assertEqual(len(cell["feature_names"]), 82)
        self.assertEqual(len(cell["folds"]), 5)
        self.assertEqual(cell["trials"], 30)
        self.assertTrue(all(len(fold["models"]["full"]["inner_scores"]) == 3 for fold in cell["folds"]))

    def test_cli_and_identity_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); inp, out, cfg = root/'input.json', root/'output.json', root/'config.json'
            inp.write_text(json.dumps(self.payload)); cfg.write_text(json.dumps({"event_bases": 2, "outer_folds": 3, "inner_folds": 2, "lambdas": [.1]}))
            run = subprocess.run([sys.executable, str(PACKAGE/'evaluator.py'), '--input', str(inp), '--output', str(out), '--config', str(cfg)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(json.loads(out.read_text())["input_sha256"]), 64)
        invalid = document(); invalid["source_commit"] = 'unverified'
        with self.assertRaises(ContractError): evaluate(invalid, small_cfg())
        invalid = document(); invalid["cells"] *= 2
        with self.assertRaises(ContractError): evaluate(invalid, small_cfg())

if __name__ == '__main__':
    unittest.main()
