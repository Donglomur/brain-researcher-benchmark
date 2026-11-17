"""Independent full-population plumbing control; Poisson fitting alone is stubbed.

All files and observations are generated engineering controls. This exercises
the complete 64-file/128-region path without asserting an empirical result.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("panel_review_evaluator", MODULE_PATH)
ev = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ev
spec.loader.exec_module(ev)


class IndependentPanelIntegration(unittest.TestCase):
    def test_complete_hashed_panel_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = {"source_revision": ev.SOURCE_REVISION,
                        "dandiset_version": "0.240511.0307", "sessions": []}
            for animal_index, animal in enumerate(ev.ANIMALS):
                for session in range(8):
                    z = np.array([[p + 100 * session, p / 2, 5,
                                   6 + animal_index, 2, 1, t]
                                  for p, t in zip([0, 10, 20, 30], [0, 1, 0, 1])], dtype=float)
                    x = np.tile(np.arange(1, 5)[:, None], (1, 41))
                    locations = np.array(["CA1"] * 20 + ["PFC"] * 20 + ["OTHER"])
                    path = root / f"{animal}-{session}.npz"
                    np.savez(path, latents=z, counts=x, locations=locations)
                    raw = path.read_bytes()
                    manifest["sessions"].append({"animal": animal, "session_index": session,
                        "epoch_id": f"epoch-{session}", "path": path.name,
                        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

            pools = []

            def stub_only_fitting(z, counts, pooled, parameters):
                # The actual driver must select the region and pool all 8 sessions
                # of one animal, centering each session before concatenation.
                self.assertEqual(counts.shape, (4, 20))
                self.assertEqual(pooled.shape, (32, 7))
                np.testing.assert_allclose(pooled[:, :2].reshape(8, 4, 2).mean(1), 0)
                self.assertEqual(len(np.unique(pooled[:, 3])), 1)
                self.assertEqual(parameters, ev.BasisParameters(10, 3, 100, 40))
                pools.append(float(pooled[0, 3]))
                return {"counts": counts, "predictions": counts.astype(float) + 0.25,
                        "cv_scores": np.full((20, 10, 10), 0.5),
                        "selected_alpha_indices": np.zeros(20, dtype=int),
                        "alphas": np.logspace(-0.5, 2, 10)}

            with patch.object(ev, "source_glm_fit", side_effect=stub_only_fitting) as fitting:
                result = ev.run_source_glm_panel(manifest, root, seed=752)
            self.assertEqual(fitting.call_count, 128)
            self.assertEqual(len(result["rows"]), 128)
            self.assertEqual(pools, [float(6 + a) for a in range(8) for _ in range(16)])
            self.assertEqual(result["neuron_subset"], 19)
            self.assertEqual(result["subset_repetitions"], 500)
            self.assertFalse(result["original_basis_search_reexecuted"])
            expected = {(a, s, r) for a in ev.ANIMALS for s in range(8) for r in ev.REGIONS}
            observed = {(r["animal"], r["session_index"], r["region"]) for r in result["rows"]}
            self.assertEqual(observed, expected)
            for row in result["rows"]:
                pairs = np.asarray(row["unit_subsets"])
                self.assertEqual(pairs.shape, (500, 2, 19))
                self.assertTrue(np.all((pairs >= 0) & (pairs < 20)))
                self.assertTrue(all(len(set(indices)) == 19 for indices in pairs.reshape(-1, 19)))
                self.assertTrue(np.any(pairs[:, 0] != pairs[:, 1]))
                self.assertAlmostEqual(row["raw_pr"], 1.)
                self.assertAlmostEqual(row["fitted_pr"], 1.)
                self.assertAlmostEqual(row["mean_selected_cv_d2"], 0.5)
            for contrast in result["prospective_descriptive_contrasts"]:
                self.assertEqual((contrast["animals"], contrast["sessions"]), (8, 64))
                self.assertAlmostEqual(contrast["mean_contrast"], 0.)

            first = root / manifest["sessions"][0]["path"]
            first.write_bytes(first.read_bytes() + b"tamper")
            with patch.object(ev, "source_glm_fit") as fitting:
                with self.assertRaisesRegex(ev.ContractError, "content pin mismatch"):
                    ev.run_source_glm_panel(manifest, root, seed=752)
                fitting.assert_not_called()


if __name__ == "__main__":
    unittest.main()
