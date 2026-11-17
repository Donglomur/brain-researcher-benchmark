"""Invented analytic controls; no native arithmetic or authentic values."""
import dataclasses as dc
import hashlib
import json
from pathlib import Path
import sys
import tracemalloc
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from hundred_models_dimensions import consumers as c

CANONICAL_BYTES = 0
CANONICAL_CALLS = 0


def meter(value):
    global CANONICAL_BYTES, CANONICAL_CALLS
    if dc.is_dataclass(value):
        value = dc.asdict(value)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    CANONICAL_BYTES += len(raw)
    CANONICAL_CALLS += 1
    return value


FOLDERS = ("models_pca_rerun", "models_no_dimred", "models")


def fixture(branch):
    folders = FOLDERS if branch == "figure16" else ("explicit_training_run",)
    models = c.membership(branch)
    layers = tuple((name, ("feature_0", "feature_1")) for name, _ in models)
    records = []
    for model, kind in models:
        for folder in folders:
            values = (-.9, -.1) if model == "AlexNet" else (.5, .5)
            records.append(c.ModelCondition(model, folder, tuple(c.LayerScore(n, x) for n, x in zip(("feature_0", "feature_1"), values))))
    frame = c.ROIFrame("V2", tuple(records), c.NoiseCeiling(.1, .8))
    meter({"layers": layers, "frame": dc.asdict(frame), "branch": branch, "folders": folders})
    return folders, layers, frame


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f16 = fixture("figure16")
        cls.f17 = fixture("figure17")

    def test_01_literal_membership_and_branch_axis(self):
        # Parse only quoted literal model names/types; do not import author YAML.
        import re
        root = BASE.parents[2]
        config = (root / "hundred-models-paper/public/author-code/configs/calc_alignment.yaml").read_text()
        expected = []
        for block in re.split(r"^  - name: ", config, flags=re.M)[1:]:
            lines = block.split("\n")
            name = re.match(r"'([^']+)'", lines[0]).group(1)
            kind = next(re.search(r"'([^']+)'", line).group(1) for line in lines[1:] if line.startswith("    type:"))
            expected.append((name, kind))
        self.assertEqual(tuple(expected), c.membership("figure16"))
        self.assertEqual(tuple(x for x in expected if x[1].startswith("image-")), c.membership("figure17"))
        self.assertEqual((len(expected), len(c.membership("figure17"))), (92, 51))

    def test_02_signed_first_tie_box_rows_and_group_statistics(self):
        folders, layers, frame = self.f16
        result = c.consume_roi("figure16", folders, layers, "V2", frame)
        meter(result)
        self.assertEqual(len(result.best_layers), 276)
        self.assertEqual(len(result.depth_rows), 552)
        self.assertEqual([(x.folder, x.layer, x.R) for x in result.best_layers[:3]], [(f, "feature_1", -.1) for f in folders])
        self.assertEqual(result.best_layers[3].layer, "feature_0")
        self.assertEqual(tuple(x.group for x in result.summaries[:3]), tuple("image-in1k-" + f for f in folders))
        for summary in result.summaries[:3]:
            self.assertEqual(summary.median_best_R, .5)
            self.assertAlmostEqual(summary.mean_best_R, 19.9 / 41)
            self.assertEqual(summary.noise_ceiling, frame.noise_ceiling)
        self.assertEqual({x.normalized_depth for x in result.depth_rows}, {0., 1.})
        self.assertFalse(result.whole_branch_complete)
        self.assertFalse(result.historical_execution_proven)
        self.assertFalse(result.renderer_qualified)

    def test_03_train_fifty_one_not_ninety_nine(self):
        folders, layers, frame = self.f17
        result = c.consume_roi("figure17", folders, layers, "V2", frame)
        meter(result)
        self.assertEqual((len(result.best_layers), len(result.depth_rows), len(result.summaries)), (51, 102, 2))
        self.assertEqual(tuple(x.group for x in result.summaries), ("image-in1k", "image-k400"))
        self.assertTrue(result.is_displayed_depth_roi)
        self.assertEqual({x.folder for x in result.depth_rows}, set(folders))

    def test_04_order_support_nonfinite_and_wrong_axis_refused(self):
        folders, layers, frame = self.f16
        candidates = [
            dc.replace(frame, records=frame.records[:-1]),
            dc.replace(frame, records=(frame.records[1], frame.records[0]) + frame.records[2:]),
            dc.replace(frame, roi="V1"),
            dc.replace(frame, noise_ceiling=c.NoiseCeiling(float("nan"), .8)),
            dc.replace(frame, records=(dc.replace(frame.records[0], layers=(c.LayerScore("feature_0", float("inf")), c.LayerScore("feature_1", -.1))),) + frame.records[1:]),
            dc.replace(frame, records=(dc.replace(frame.records[0], model="unselected_auxiliary"),) + frame.records[1:]),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate.roi, count=len(candidate.records)):
                with self.assertRaises(ValueError):
                    c.consume_roi("figure16", folders, layers, "V2", candidate)
        with self.assertRaises(ValueError):
            c.consume_roi("figure16", tuple(reversed(folders)), layers, "V2", frame)
        with self.assertRaises(ValueError):
            c.validate_folders("figure16", (folders[0],) * 3)

    def test_05_combined_normalization_discriminator(self):
        # Composition-only seam: manufacture different adjusted endpoint scales.
        # This does not claim the source transformation produces this geometry
        # under the wrapper's common layer-axis invariant.
        folders, layers, frame = self.f16
        original = c.depth.adjust_layers
        def altered(table, **kw):
            result = original(table, **kw)
            scale = 2 if table.rows[0][5] == "models" else 1
            rows = tuple(row[:1] + (row[1] * scale,) + row[2:] for row in result.table.rows)
            return dc.replace(result, table=dc.replace(result.table, rows=rows))
        with patch.object(c.depth, "adjust_layers", altered):
            result = c.consume_roi("figure16", folders, layers, "V2", frame)
        meter(result)
        alex = [x for x in result.depth_rows if x.model == "AlexNet"]
        self.assertEqual({x.max_layer_across_conditions for x in alex}, {2})
        self.assertEqual({x.normalized_depth for x in alex if x.folder != "models"}, {0., .5})
        self.assertEqual({x.normalized_depth for x in alex if x.folder == "models"}, {0., 1.})

    def test_06_source_modal_one_refuses(self):
        folders, layers, frame = self.f17
        one = tuple((model, ("feature_0",)) for model, _ in layers)
        records = tuple(dc.replace(record, layers=record.layers[:1]) for record in frame.records)
        with self.assertRaises(c.depth.DepthDomainError):
            c.consume_roi("figure17", folders, one, "V2", dc.replace(frame, records=records))


if __name__ == "__main__":
    pins = {}
    for name in ("consumers.py", "_scope.py", "_depth.py", "_catalog_gate.py"):
        raw = (BASE / "hundred_models_dimensions" / name).read_bytes()
        pins[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    tracemalloc.start()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    live, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    for name, descriptor in pins.items():
        raw = (BASE / "hundred_models_dimensions" / name).read_bytes()
        assert {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == descriptor
    print(json.dumps({"groups": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "runtime_pins": pins, "canonical_fixture_bytes": CANONICAL_BYTES, "canonical_calls": CANONICAL_CALLS, "traced_live_bytes_after_runtime_imports": live, "traced_peak_bytes_after_runtime_imports": peak, "physical_fixture_file_bytes": 0}, sort_keys=True))
    sys.exit(not result.wasSuccessful())
