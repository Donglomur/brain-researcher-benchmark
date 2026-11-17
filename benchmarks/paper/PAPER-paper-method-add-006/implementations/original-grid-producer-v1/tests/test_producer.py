"""Generated implementation controls, never authentic benchmark results."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import glm_search as G
import native_inputs as I
import producer as P


def packet(animal="KL8", session=0, region="CA1", n=40):
    aid = I.SOURCE_ORDER[animal][int(animal == "ZT2" and session >= 4)]
    trial = np.arange(n) // 4 + 100
    z = np.column_stack([np.arange(n) % 7, np.arange(n) % 5, np.full(n, 5.),
                         np.full(n, 6.), np.arange(n) % 3, trial % 2, np.arange(n) % 2]).astype(float)
    x = np.column_stack([np.arange(n) % 3 + 1, np.arange(n) % 4 + 1])
    arrays = {"x": x, "z": z, "t": 1000. + np.arange(n) * .5, "trial": trial,
              "unit_ids": np.arange(2) + (10 if region == "CA1" else 20),
              "strict_columns": np.array([0])}
    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    raw = stream.getvalue()
    cid = f"{animal}-s{session + 1:02d}-{region}"
    case = {"id": cid, "rat": animal, "session": session + 1, "area": region,
            "source_asset_id": aid, "source_epoch": session, "rows": n,
            "units": 1, "unit_ids": [int(arrays["unit_ids"][0])],
            "native": {"path": cid + ".npz", "bytes": len(raw), "sha256": I.sha256(raw)}}
    return case, raw


class FakePanel:
    """Generated source-shaped panel; deliberately carries no authentic claim."""
    design_sha256 = "0" * 64

    def __init__(self):
        self.by_key = {}
        self.raw = {}
        for a in G.K.ANIMALS:
            for s in range(8):
                for r in G.K.REGIONS:
                    c, raw = packet(a, s, r)
                    self.by_key[(a, s, r)] = c
                    self.raw[(a, s, r)] = raw

    def load_session(self, a, s, r):
        return I.load_packet(self.raw[(a, s, r)], self.by_key[(a, s, r)])

    paired = I.PreparedPanel.paired


class ProducerControls(unittest.TestCase):
    def test_actual_tiny_grid_matches_independent_sklearn_and_oof(self):
        from sklearn.linear_model import PoissonRegressor
        from sklearn.model_selection import GridSearchCV, KFold
        t = np.arange(40)
        design = np.column_stack([np.sin(t / 5), np.cos(t / 7)])
        counts = ((t * 7) % 5 + 1).astype(float)[:, None]
        result = G.fit_search(design, counts)
        def independent_refit(cv):
            values = np.asarray([cv[f"split{j}_test_score"] for j in range(10)])
            return np.argmax(np.nanmean(values, axis=0))
        direct = GridSearchCV(PoissonRegressor(), {"alpha": np.logspace(-.5, 2, 10)},
                              cv=10, n_jobs=1, error_score="raise", refit=independent_refit)
        direct.fit(design, counts[:, 0])
        expected_scores = np.asarray([direct.cv_results_[f"split{j}_test_score"] for j in range(10)]).T
        np.testing.assert_allclose(result["cv_scores"][0], expected_scores, rtol=0, atol=0)
        self.assertEqual(result["selected_alpha_indices"].tolist(), [direct.best_index_])
        np.testing.assert_allclose(result["predictions"][:, 0], direct.predict(design), rtol=0, atol=0)
        self.assertEqual(result["fit_count"], 111)
        for fold, (train, test) in enumerate(KFold(10).split(design)):
            model = PoissonRegressor(alpha=direct.best_estimator_.alpha).fit(design[train], counts[train, 0])
            np.testing.assert_allclose(result["oof_predictions"][test, 0], model.predict(design[test]), rtol=0, atol=0)
            self.assertTrue((result["fold_ids"][test] == fold).all())
        self.assertFalse(np.allclose(result["oof_predictions"], result["predictions"]))

    def test_fit_failure_does_not_become_dropped_unit(self):
        with patch("sklearn.model_selection.GridSearchCV.fit", side_effect=RuntimeError("fit failed")):
            with self.assertRaisesRegex(RuntimeError, "fit failed"):
                G.fit_search(np.ones((20, 2)), np.ones((20, 1)))

    def test_native_packet_through_actual_basis_search_preserves_eligible_ids(self):
        case, raw = packet()
        p = I.load_packet(raw, case)
        n = len(p["z"])
        p["z"][:, 3] = 6 + .6 * np.sin(np.arange(n))
        p["z"][:, 4] = .8 * np.cos(np.arange(n))
        p["z"][0, 2] = 4  # Strict recorded-speed boundary excludes this row.
        p["x"][:, 1] = 0   # Native session rate filter excludes this unit.
        centered, _, rows, units = G.K.prepare_glm_session(p["z"], p["x"])
        pooled = np.concatenate([centered.copy() for _ in range(8)])
        result = G.fit_session(p, pooled, G.GRID.index(G.FIGURE_BASIS))
        self.assertEqual(result["predictions"].shape, (n - 1, 1))
        self.assertEqual(result["fit_count"], 111)
        np.testing.assert_array_equal(result["row_ids"], p["row_ids"][rows])
        np.testing.assert_array_equal(result["unit_ids"], p["unit_ids"][units])
        pos = np.exp(-((centered[:, None, :2] - result["basis_position"]) ** 2).sum(2) / 200) / (200 * np.pi)
        vx = np.exp(-(centered[:, 3, None] - result["basis_vx"]) ** 2 / 80) / np.sqrt(80 * np.pi)
        vy = np.exp(-(centered[:, 4, None] - result["basis_vy"]) ** 2 / 80) / np.sqrt(80 * np.pi)
        raw_design = np.column_stack([pos * (centered[:, 6, None] == 0),
                                      pos * (centered[:, 6, None] == 1), vx, vy])
        np.testing.assert_allclose(result["covariates"],
                                   (raw_design - raw_design.mean(0)) / raw_design.std(0),
                                   rtol=1e-13, atol=1e-13)

    def test_warning_preserved_not_changed_to_error(self):
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.model_selection import GridSearchCV
        original = GridSearchCV.fit
        def warn_fit(search, *args, **kwargs):
            warnings.warn("generated retained convergence warning", ConvergenceWarning)
            return original(search, *args, **kwargs)
        with patch.object(GridSearchCV, "fit", warn_fit):
            result = G.fit_search(np.linspace(-1, 1, 20)[:, None], (np.arange(20) % 3 + 1)[:, None])
        self.assertTrue(any(w["category"] == "ConvergenceWarning" and w["count"] == 1 for w in result["warnings"]))

    def test_complete_grid_and_contiguous_fold_plan(self):
        jobs = list(G.job_plan())
        self.assertEqual(len(jobs), 13824)
        self.assertEqual(len({j["id"] for j in jobs}), 13824)
        self.assertEqual(len(G.GRID), 108)
        self.assertEqual(G.GRID[0], (5, 3, 10, 10))
        self.assertEqual(G.GRID[-1], (15, 12, 150, 80))
        self.assertEqual(len([j for j in jobs if tuple(j["basis"]) == G.FIGURE_BASIS]), 128)
        self.assertEqual(np.bincount(G.source_fold_ids(23)).tolist(), [3, 3, 3, 2, 2, 2, 2, 2, 2, 2])
        with self.assertRaises(G.ContractError):
            G.source_fold_ids(9)

    def test_native_all_units_not_strict_training_list_and_equal_trial(self):
        case, raw = packet()
        result = I.load_packet(raw, case)
        self.assertEqual(result["x"].shape[1], 2)
        self.assertEqual(case["units"], 1)
        self.assertEqual(len(result["unit_ids"]), 2)
        self.assertIn("|epoch=0|t=", result["row_ids"][0])
        self.assertEqual(result["represented_trial_ids"].tolist(), list(range(100, 110)))

    def test_complete_manifest_and_missing_epoch_refusals(self):
        panel = FakePanel()
        cases = list(panel.by_key.values())
        I.validate_design({"schema": "population_geometry_operator_design_v1", "cases": cases})
        for mutation in (cases[:-1], [*cases[:1], cases[0], *cases[2:]]):
            with self.assertRaises(G.ContractError):
                I.validate_design({"schema": "population_geometry_operator_design_v1", "cases": mutation})
        altered = copy.deepcopy(cases)
        altered[1]["source_epoch"] = 999
        with self.assertRaisesRegex(G.ContractError, "paired regions"):
            I.validate_design({"schema": "population_geometry_operator_design_v1", "cases": altered})

    def test_pool_centers_each_of_eight_sessions_and_uses_recorded_speed(self):
        calls = []
        def load(a, s, r):
            p = FakePanel().load_session(a, s, r)
            p["z"][:, :2] += s * 100
            p["z"][0, 2] = 4
            p["z"][:, 3:5] = 0  # geometry mask must not influence GLM pool.
            calls.append((a, s, r))
            return p
        pooled = G.pooled_latents(load, "KL8")
        self.assertEqual(calls, [("KL8", s, "CA1") for s in range(8)])
        self.assertEqual(pooled.shape, (8 * 39, 7))
        for chunk in np.split(pooled, 8):
            np.testing.assert_allclose(chunk[:, :2].mean(0), 0, atol=1e-13)

    def test_checkpoint_roundtrip_nonfinite_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result"
            value = {"values": np.array([np.nan, np.inf, -np.inf, 3.]), "x": np.nan,
                     "ids": np.array(["native|1", "native|2"])}
            binding = {"design": "generated"}
            P.save_result(path, value, binding, max_bytes=100000)
            restored = P.load_result(path, binding, max_bytes=100000)
            np.testing.assert_array_equal(restored["values"], value["values"])
            self.assertTrue(np.isnan(restored["x"]))
            with self.assertRaisesRegex(G.ContractError, "binding differs"):
                P.load_result(path, {"design": "different"}, max_bytes=100000)
            with self.assertRaises(FileExistsError):
                P.save_result(path, value, binding, max_bytes=100000)
            with (path / "arrays.npz").open("ab") as f:
                f.write(b"changed")
            with self.assertRaises(G.ContractError):
                P.load_result(path, binding, max_bytes=100000)

    def test_checkpoint_ceiling_precedes_directory_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result"
            with self.assertRaises(G.ContractError):
                P.save_result(path, {"x": np.ones(100)}, {}, max_bytes=1)
            self.assertFalse(path.exists())

    def test_checkpoint_expansion_cap_and_fortran_canonicalization(self):
        with tempfile.TemporaryDirectory() as temp:
            too_big = Path(temp) / "compressed"
            with self.assertRaisesRegex(G.ContractError, "expanded result"):
                P.save_result(too_big, {"zeros": np.zeros(10000)}, {}, max_bytes=4000)
            self.assertFalse(too_big.exists())
            matrix = np.asfortranarray(np.arange(12.).reshape(3, 4))
            path = Path(temp) / "fortran"
            P.save_result(path, {"matrix": matrix}, {}, max_bytes=4000)
            np.testing.assert_array_equal(P.load_result(path, {}, max_bytes=4000)["matrix"], matrix)

    def test_complete_grid_finalizer_rejects_missing_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                P.validate_complete_grid(temp, {}, max_result_bytes=100000)

    def test_rng_restore_continues_exact_stream(self):
        import geometry_results as R
        a, b = np.random.RandomState(8), np.random.RandomState(999)
        a.randn(7)
        P.restore_rng(b, R.state(a))
        np.testing.assert_array_equal(a.randn(100), b.randn(100))

    def test_trend_runtime_accepts_only_named_current_backend(self):
        values = {"numpy": "2.2.6", "scipy": "1.15.3", "scikit-learn": "1.6.1",
                  "statsmodels": "0.14.5", "pandas": "2.2.3", "patsy": "1.0.1"}
        with patch("importlib.metadata.version", side_effect=values.__getitem__):
            result = P.require_trend_runtime()
            self.assertEqual({k: result[k] for k in values}, values)
            values["statsmodels"] = "0.99.0"
            with self.assertRaisesRegex(G.ContractError, "current statsmodels"):
                P.require_trend_runtime()

    def test_all64_oof_export_consumed_by_existing_panel_scorer(self):
        panel = FakePanel()
        binding = P.execution_binding(panel)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            saved = base / "saved"
            saved.mkdir()
            for a in G.K.ANIMALS:
                for s in range(8):
                    for r in G.K.REGIONS:
                        p = panel.load_session(a, s, r)
                        job = next(j for j in G.job_plan() if j["animal"] == a and j["session_index"] == s
                                   and j["region"] == r and j["basis_index"] == 0)
                        result = {"job": job, "oof_predictions": p["x"] + .25,
                                  "row_ids": p["row_ids"], "unit_ids": p["unit_ids"],
                                  "fold_ids": G.source_fold_ids(len(p["z"]))}
                        P.save_result(saved / job["id"], result, binding, max_bytes=100000)
            out = base / "oof"
            P.export_oof_panel(panel, saved, out, basis_index=0, max_result_bytes=100000)
            reference = json.loads((out / "REFERENCE.json").read_text())
            author = json.loads((out / "AUTHOR.json").read_text())
            scored = P.replay_module().replay_panel(reference, author, author, [out, out, out])
            self.assertEqual(len(scored["sessions"]), 64)
            self.assertIsNone(scored["population_d2"])
            self.assertEqual(sum(r["regions"]["CA1"]["eligible_unit_count"] for r in scored["sessions"]), 128)


if __name__ == "__main__":
    unittest.main()
