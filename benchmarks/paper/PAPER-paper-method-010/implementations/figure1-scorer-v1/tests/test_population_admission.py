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


def original_geometry():
    return np.concatenate([
        module + np.linspace(.01, .99, count)
        for module, count in enumerate(scorer.MODULE_COUNTS)
    ])


class PopulationAdmissionTests(unittest.TestCase):
    def test_source_sustained_upper_endpoint_preserves_metric_membership(self):
        truth = original_geometry()
        # Source sustained tpref==0 gives xi=1, then xi_all=2. Its metric
        # label remains 2 even though the generator group was sustained.
        truth[1000:1010] = 2.
        before = truth.copy()
        validated = scorer.validate_original_population(truth)
        np.testing.assert_array_equal(validated, before)
        _, _, labels, counts = scorer._inputs(validated, validated)
        np.testing.assert_array_equal(counts, [1000, 990, 1010, 1000, 2000])
        np.testing.assert_array_equal(labels[1000:1010], np.full(10, 2))
        self.assertTrue(np.shares_memory(validated, truth))

    def test_only_exact_shared_boundaries_can_explain_count_shifts(self):
        truth = original_geometry()
        truth[[1000, 2000, 3000]] = [2., 3., 4.]
        np.testing.assert_array_equal(scorer.validate_original_population(truth), truth)
        for row, boundary in ((1000, 2.), (2000, 3.), (3000, 4.)):
            changed = original_geometry()
            changed[row] = np.nextafter(boundary, float("inf"))
            with self.subTest(row=row), self.assertRaises(ValueError):
                scorer.validate_original_population(changed)
        truth = original_geometry()
        truth[1000] = 1.
        with self.assertRaises(ValueError):
            scorer.validate_original_population(truth)

    def test_report_retains_actual_metric_counts(self):
        truth = original_geometry()
        truth[1000:1010] = 2.
        artifact = {"path": "/operator/unused.npz", "sha256": "a" * 64}
        request = {
            "schema": "rastermap-figure1-score/v1",
            "method_names": ["source_rastermap", "candidate"],
            "realizations": [{"id": i, "metric_seed": i,
                "activity_sha256": "b" * 64, "target": artifact,
                "embeddings": {"source_rastermap": artifact, "candidate": artifact}}
                for i in range(10)]}
        # This is report plumbing only; source numerical parity is tested on
        # small real metric calls in source_parity.py, including endpoints.
        def generated_packet(record, keys):
            return {"xi_all": truth} if "xi_all" in keys else {"embedding": truth}
        with mock.patch.object(scorer, "_load_artifact", side_effect=generated_packet), \
             mock.patch.object(scorer, "source_benchmarks", return_value=(
                 np.full((2, 2, 5), .5), np.full((2, 5), 12))):
            report = scorer.evaluate_request(request)
        self.assertEqual(len(report["realizations"]), 10)
        for row in report["realizations"]:
            self.assertEqual(row["metric_module_counts"], [1000, 990, 1010, 1000, 2000])
        self.assertFalse(report["published_score_reproduced"])
        self.assertFalse(report["paper_improvement_established"])

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
