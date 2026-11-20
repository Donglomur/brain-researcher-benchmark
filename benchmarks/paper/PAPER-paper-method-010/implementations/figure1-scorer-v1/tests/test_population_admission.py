"""Generated fixed-population regression; no original data or model fits."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("figure1_population_guard", ROOT / "scorer.py")
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)
PANEL_SPEC = importlib.util.spec_from_file_location(
    "figure1_population_panel", ROOT.parent / "figure1-reference-panel-v1" / "reference_panel.py")
panel = importlib.util.module_from_spec(PANEL_SPEC)
PANEL_SPEC.loader.exec_module(panel)


class PopulationAdmissionTests(unittest.TestCase):
    def test_domain_refusal_precedes_allocation_and_preserves_valid_score(self):
        truth = np.concatenate([
            module + np.linspace(.01, .99, count)
            for module, count in enumerate(scorer.MODULE_COUNTS)
        ])
        invalid = [np.full(6000, 1e9 + .25), np.full(6000, -1.),
                   np.full(6000, 5.), truth[:-1], np.array([])]
        for target in invalid:
            with self.subTest(shape=target.shape):
                with mock.patch.object(scorer.np, "bincount",
                                       side_effect=AssertionError("allocation reached")) as allocate:
                    with self.assertRaises(ValueError):
                        scorer.validate_original_population(target)
                    allocate.assert_not_called()
        validated = scorer.validate_original_population(truth)
        np.testing.assert_array_equal(validated, truth)
        np.testing.assert_array_equal(
            scorer.triplet_order(validated, validated, np.random.RandomState(41)),
            np.ones(5))
        # The source pin used by the existing reference-panel consumer must move
        # with this narrow current-source fix. Its aggregation remains unchanged.
        summary = panel._summarizer(ROOT / "scorer.py")(
            np.full((10, 2, 2, 5), .25), range(10))
        np.testing.assert_array_equal(summary["mean_percent"], np.full((2, 2, 5), 25.))
        np.testing.assert_array_equal(summary["sem_percent"], np.zeros((2, 2, 5)))


if __name__ == "__main__":
    unittest.main()
