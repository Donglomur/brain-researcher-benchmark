"""Generated engineering controls, including independently derived scalar oracles."""
import copy
import csv
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import ncc_evaluator as ncc


def scalar_r(a, b):
    am, bm = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - am) * (y - bm) for x, y in zip(a, b))
    denominator = (sum((x - am) ** 2 for x in a) * sum((y - bm) ** 2 for y in b)) ** .5
    return numerator / denominator if denominator else None


def scalar_cross(a, b):
    values = [scalar_r(x, y) for x in a for y in b]
    return sum(values) / len(values) if None not in values else None


def pin(path):
    return {"path": path.name, "sha256": ncc.sha256(path)}


def build_control(directory):
    """Bounded generated arrays; deliberately not a substitute for empirical data."""
    rng = np.random.RandomState(814)
    manifest = {"schema_version": 1, "task_id": ncc.TASK_ID, "source_commit": ncc.SOURCE_COMMIT,
                "population": "generated_engineering_control", "training_regime": "shared_stimulus_fig2",
                "stimulus_ids": [10, 20, 30], "repeat_count": 2, "subjects": [], "models": []}
    for subject in ncc.SUBJECTS:
        path = directory / f"{subject}.npz"
        data = {"x": rng.randn(6, 8), "labels": np.repeat([10, 20, 30], 2),
                "trial_ids": np.array([f"row-{i}" for i in range(6)]),
                "voxel_ids": np.array([f"{subject}:voxel-{i}" for i in range(8)])}
        data.update({f"roi_{roi}": np.arange(8) if roi == "VC" else np.array([i, i + 1, i + 2]) for i, roi in enumerate(ncc.ROIS)})
        np.savez(path, **data)
        manifest["subjects"].append({"id": subject, "file": pin(path), "training_stimulus_ids": [1, 2, 3, 4]})
    for (source, target), method in itertools.product(itertools.permutations(ncc.SUBJECTS, 2), ncc.METHODS):
        path = directory / f"{source}-{target}-{method}.npz"
        data = {"x_mean": rng.randn(8), "x_norm": np.exp(rng.randn(8)), "y_mean": rng.randn(8), "y_norm": np.exp(rng.randn(8)),
                "source_voxel_ids": np.array([f"{source}:voxel-{i}" for i in range(8)]),
                "target_voxel_ids": np.array([f"{target}:voxel-{i}" for i in range(8)])}
        if method == "brain_loss":
            data["M"] = rng.randn(9, 8)
        else:
            for i, (n_in, n_out) in enumerate(((8, 4), (4, 4), (4, 8))):
                data[f"W{i}"] = rng.randn(n_out, n_in)
                data[f"b{i}"] = rng.randn(n_out)
        np.savez(path, **data)
        manifest["models"].append({"source": source, "target": target, "method": method, "file": pin(path),
                                   "source_fit_stimulus_ids": [1, 2, 3, 4], "target_fit_stimulus_ids": [1, 2, 3, 4]})
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


class MetricControls(unittest.TestCase):
    def test_cross_repeat_is_not_repeat_mean(self):
        repeats = np.array([[1., 0, -1], [0, 1, -1]])
        self.assertAlmostEqual(ncc.cross_repeat_correlation(repeats, repeats), .75)
        self.assertAlmostEqual(scalar_r(repeats.mean(0), repeats.mean(0)), 1.)

    def test_scalar_pearson_oracle(self):
        rng = np.random.RandomState(43)
        a, b = rng.randn(3, 7), rng.randn(4, 7)
        self.assertAlmostEqual(ncc.cross_repeat_correlation(a, b), scalar_cross(a.tolist(), b.tolist()), places=14)

    def test_undefined_is_not_zero(self):
        self.assertIsNone(ncc.cross_repeat_correlation([[1, 1], [0, 1]], [[0, 1]]))

    def test_pattern_profile_axes_and_order(self):
        labels = np.array([20, 10, 20, 10, 30, 30])
        x = np.array([[3, 2, 1], [1, 4, 2], [8, 5, 2], [2, 6, 3], [4, 5, 2], [5, 3, 9]], float)
        y = x * np.array([2., 3, 4]) + [10, 20, 30]
        pred = x[:, ::-1].copy()
        subject = {"x": x, "labels": labels, "voxel_ids": ["a", "b", "c"], "rois": {"VC": np.arange(3)}}
        target = dict(subject, x=y)
        norms = {"y_mean": np.array([10., 20, 30]), "y_norm": np.array([2., 3, 4])}
        rows = ncc.score_pair(pred, subject, target, norms, [10, 20, 30], "sub01", "sub02", "brain_loss")
        patterns, profiles = rows[:3], rows[3:]
        for row, label in zip(patterns, [10, 20, 30]):
            self.assertAlmostEqual(row["raw_r"], scalar_cross(x[labels == label].tolist(), pred[labels == label].tolist()))
        for voxel, row in enumerate(profiles):
            a = [[x[labels == label][repeat, voxel] for label in [10, 20, 30]] for repeat in range(2)]
            b = [[pred[labels == label][repeat, voxel] for label in [10, 20, 30]] for repeat in range(2)]
            self.assertAlmostEqual(row["raw_r"], scalar_cross(a, b))

    def test_ceiling_threshold_clipping_and_missing(self):
        rows = [{"target": "sub01", "roi": "VC", "axis": "pattern", "feature": i, "raw_r": r} for i, r in enumerate([.9, -.9, .7, None])]
        ceilings = {("sub01", "VC", "pattern", i): (.5, .5 if i == 2 else .1) for i in range(4)}
        ncc.apply_ceilings(rows, ceilings)
        self.assertEqual([r["normalized_r"] for r in rows], [1., -1., None, None])
        self.assertFalse(rows[2]["eligible"])
        self.assertTrue(rows[3]["eligible"])
        with self.assertRaises(ncc.ContractError):
            ncc.apply_ceilings(rows, dict(list(ceilings.items())[:-1]))

    def test_source_bootstrap_matches_author_first_occurrence_orders(self):
        # Author plot_figure.py first sorts the Source/Target groupby. Within
        # each ROI/method, unique() sees sub02 first in Target, then sub01 only
        # in the next Source block. Seed equality alone cannot recover this.
        values = {pair: i / 20 for i, pair in enumerate(itertools.permutations(ncc.SUBJECTS, 2))}
        source_order = ["sub01", "sub02", "sub03", "sub04", "sub05"]
        target_order = ["sub02", "sub03", "sub04", "sub05", "sub01"]
        rng = np.random.RandomState(42)
        means = []
        for _ in range(1000):
            # Literal accepted-pair sampling from the author loop, independent
            # of the evaluator's roster construction and accumulation.
            sources, targets = [], []
            while len(sources) < 20:
                source = rng.choice(source_order, 1, replace=True)[0]
                target = rng.choice(target_order, 1, replace=True)[0]
                if source != target:
                    sources.append(source)
                    targets.append(target)
            means.append(np.mean([values[pair] for pair in zip(sources, targets)]))
        actual = ncc.source_pair_bootstrap(values)
        self.assertEqual(actual["bootstrap_mean"], float(np.mean(means)))
        self.assertEqual(actual["percentile_2_5"], float(np.percentile(means, 2.5)))
        self.assertEqual(actual["percentile_97_5"], float(np.percentile(means, 97.5)))
        self.assertEqual(actual["replicates"], 1000)
        self.assertEqual(actual["seed"], 42)

    def test_source_bootstrap_ignores_input_mapping_insertion_order(self):
        values = {pair: i / 20 for i, pair in enumerate(itertools.permutations(ncc.SUBJECTS, 2))}
        reversed_values = dict(reversed(list(values.items())))
        self.assertEqual(ncc.source_pair_bootstrap(values, 20),
                         ncc.source_pair_bootstrap(reversed_values, 20))

    def test_source_bootstrap_rejects_incomplete_or_self_pair_panel(self):
        values = {pair: i / 20 for i, pair in enumerate(itertools.permutations(ncc.SUBJECTS, 2))}
        del values[("sub01", "sub02")]
        with self.assertRaisesRegex(ncc.ContractError, "all 20 nonself"):
            ncc.source_pair_bootstrap(values)
        values[("sub01", "sub01")] = .5
        with self.assertRaisesRegex(ncc.ContractError, "all 20 nonself"):
            ncc.source_pair_bootstrap(values)

    def test_source_bootstrap_deterministic_and_not_subject_claim(self):
        values = {pair: i / 20 for i, pair in enumerate(itertools.permutations(ncc.SUBJECTS, 2))}
        a = ncc.source_pair_bootstrap(values, 20)
        self.assertEqual(a, ncc.source_pair_bootstrap(values, 20))
        self.assertIn("not_independent_subject", a["unit"])


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.path, self.manifest = build_control(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def save_manifest(self):
        self.path.write_text(json.dumps(self.manifest))

    def test_complete_pair_inference_and_cli(self):
        result = ncc.evaluate(self.path)
        self.assertEqual(result["source_pairs"], 20)
        self.assertEqual(result["raw"]["summaries"][0]["complete_pairs"], 20)
        self.assertEqual(len(result["raw"]["pair_rows"]), 20 * 2 * 6 * 2)
        self.assertIsNone(result["normalized"])
        self.assertEqual(result["scientific_qualification"], "unknown")
        output = self.directory / "result.json"
        completed = subprocess.run([sys.executable, str(PACKAGE / "ncc_evaluator.py"), "evaluate", str(self.path), "--output", str(output)], text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text())["population"], "generated_engineering_control")

    def test_numpy_content_scalar_topology_oracle(self):
        record = next(x for x in self.manifest["models"] if x["method"] == "content_loss")
        model = ncc.read_npz(self.directory, record["file"])
        row = list(range(8))
        output, norms = ncc.predict(model, [row], "content_loss", model["source_voxel_ids"], model["target_voxel_ids"])
        state = [(v - m) / s for v, m, s in zip(row, model["x_mean"], model["x_norm"])]
        for layer in range(3):
            state = [sum(a * b for a, b in zip(weights, state)) + bias for weights, bias in zip(model[f"W{layer}"], model[f"b{layer}"])]
            if layer < 2:
                mean = sum(state) / len(state)
                variance = sum((v - mean) ** 2 for v in state) / len(state)
                state = [(v - mean) / (variance + 1e-5) ** .5 for v in state]
                state = [v if v >= 0 else .2 * v for v in state]
        np.testing.assert_allclose(output[0], state, atol=1e-13)

    def test_numpy_brain_affine_oracle(self):
        record = next(x for x in self.manifest["models"] if x["method"] == "brain_loss")
        model = ncc.read_npz(self.directory, record["file"])
        x = np.arange(8.)[None]
        output, _ = ncc.predict(model, x, "brain_loss", model["source_voxel_ids"], model["target_voxel_ids"])
        expected = [sum((v - mu) / norm * weight for v, mu, norm, weight in zip(x[0], model["x_mean"], model["x_norm"], model["M"][:-1, j])) + model["M"][-1, j] for j in range(8)]
        np.testing.assert_allclose(output[0], expected)

    def test_missing_pair_rejected(self):
        self.manifest["models"].pop()
        self.save_manifest()
        with self.assertRaisesRegex(ncc.ContractError, "20 directed"):
            ncc.evaluate(self.path)

    def test_training_test_leak_rejected(self):
        self.manifest["subjects"][0]["training_stimulus_ids"].append(10)
        self.save_manifest()
        with self.assertRaisesRegex(ncc.ContractError, "leakage"):
            ncc.evaluate(self.path)

    def test_shared_training_cannot_be_nonshared(self):
        self.manifest["subjects"][0]["training_stimulus_ids"] = [1, 2, 3, 5]
        self.save_manifest()
        with self.assertRaisesRegex(ncc.ContractError, "shared Fig2"):
            ncc.evaluate(self.path)

    def test_model_voxel_reorder_rejected(self):
        record = self.manifest["models"][0]
        model = ncc.read_npz(self.directory, record["file"])
        model["target_voxel_ids"] = model["target_voxel_ids"][::-1]
        path = self.directory / record["file"]["path"]
        np.savez(path, **model)
        record["file"] = pin(path)
        self.save_manifest()
        with self.assertRaisesRegex(ncc.ContractError, "voxel identity/order"):
            ncc.evaluate(self.path)

    def test_artifact_tampering_rejected(self):
        with (self.directory / self.manifest["models"][0]["file"]["path"]).open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaisesRegex(ncc.ContractError, "SHA256 mismatch"):
            ncc.evaluate(self.path)

    def test_generated_shape_cannot_claim_public_population(self):
        self.manifest["population"] = "public_deeprecon"
        self.save_manifest()
        with self.assertRaisesRegex(ncc.ContractError, "50 images"):
            ncc.evaluate(self.path)

    def test_duplicate_trial_id_and_missing_repeat_rejected(self):
        record = self.manifest["subjects"][0]
        data = ncc.read_npz(self.directory, record["file"])
        data["trial_ids"][1] = data["trial_ids"][0]
        with self.assertRaisesRegex(ncc.ContractError, "duplicate"):
            ncc.validate_subject(data, [1, 2], [10, 20, 30], 2)
        data["trial_ids"][1] = "repaired"
        data["labels"][0] = 20
        with self.assertRaisesRegex(ncc.ContractError, "repeat count"):
            ncc.validate_subject(data, [1, 2], [10, 20, 30], 2)

    def test_pinned_ceiling_csv_end_to_end(self):
        result = ncc.evaluate(self.path)
        keys = sorted({(r["target"], r["roi"], r["axis"], r["feature"]) for r in result["rows"]})
        definitions = []
        for axis in ("pattern", "profile"):
            definition = {"axis": axis}
            feature = "Image index" if axis == "pattern" else "Vox_idx"
            for kind, field, value in (("ceiling_file", "Correlation", .5), ("threshold_file", "Threshold 1", .1)):
                path = self.directory / f"{axis}-{kind}.csv"
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=["Subject", "ROI", feature, field]); writer.writeheader()
                    for subject, roi, ax, index in keys:
                        if ax == axis:
                            writer.writerow({"Subject": subject, "ROI": roi, feature: index, field: value})
                definition[kind] = pin(path)
            definitions.append(definition)
        self.manifest["noise_ceilings"] = definitions
        self.save_manifest()
        result = ncc.evaluate(self.path)
        self.assertIsNotNone(result["normalized"])
        self.assertIn("unqualified", result["normalized_stage"])
        self.assertTrue(all(r["normalized_r"] is None or -1 <= r["normalized_r"] <= 1 for r in result["rows"]))


if __name__ == "__main__":
    unittest.main()
