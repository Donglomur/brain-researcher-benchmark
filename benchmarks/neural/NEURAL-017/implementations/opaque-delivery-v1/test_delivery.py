"""Generated full-support software controls; no source recordings or fitting."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery as d


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FINGERPRINT = load_source("original_fingerprint", HERE.parent / "registered-runtime" /
                          "complete-operator/nlb/fingerprint.py")
METRIC = load_source("original_metric", HERE.parent / "registered-runtime" /
                     "complete-operator/nlb/metric_core.py")


def generated_source():
    p = {
        "train_trial_ids": np.asarray([f"source-trial-{i}" for i in range(1721)]),
        "eval_trial_ids": np.asarray([f"source-trial-{1721+i}" for i in range(574)]),
        "heldin_unit_ids": np.asarray([f"source-unit-{i}" for i in range(137)]),
        "heldout_unit_ids": np.asarray([f"source-unit-{137+i}" for i in range(45)]),
        "train_condition_ids": np.asarray([f"[{i % 17},{i % 3}]" for i in range(1721)]),
        "eval_condition_ids": np.asarray([f"[{i % 17},{i % 3}]" for i in range(574)]),
        "bin_left_edges_ms": d.GRID.copy(),
        "eval_valid_mask": np.broadcast_to(np.array(True), (574, 140, 45)),
        "source_manifest_sha256": "a" * 64,
    }
    for name, (trials, bins, units) in d.COUNT_SHAPES.items():
        # Distinct variation on all three axes; no real source activity.
        p[name] = ((np.arange(trials, dtype=np.uint16)[:, None, None] % 13
                    + np.arange(bins, dtype=np.uint16)[None, :, None] % 7
                    + np.arange(units, dtype=np.uint16)[None, None, :] % 5) % 4).astype(np.uint8)
        p[name].setflags(write=False)
    # Keep the full scientific panel, but use the production streaming hasher
    # here. The inherited implementation's whole-array int64 + bytes copies
    # are compared independently on a separate bounded multi-chunk packet.
    p["panel_fingerprint"] = d.fingerprint(p)
    return p


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = generated_source()
        cls.public, cls.binding = d.export_public(
            cls.source, secret=bytes(range(32)),
            expected_source_fingerprint=cls.source["panel_fingerprint"])
        cls.binding_sha = d.digest(cls.binding)

    def test_fingerprint_matches_inherited_implementation(self):
        self.assertEqual(d.fingerprint(self.source), self.source["panel_fingerprint"])
        self.assertEqual(d.fingerprint(self.public), self.public["panel_fingerprint"].item())
        # Encoding equivalence is independent of task admission. Nineteen rows
        # span two streaming chunks; use every field family, mixed endian data,
        # noncontiguous arrays and a nonconstant mask without full-array copies.
        for original in (self.source, self.public):
            small = {}
            for key, value in original.items():
                value = np.asarray(value)
                if key in d.COUNT_SHAPES:
                    small[key] = value[:19, :6:2, :5].astype('>i8')
                elif key == 'eval_valid_mask':
                    mask = np.ones((19, 3, 5), dtype=bool)
                    mask[0, 0, 0] = False
                    small[key] = mask
                elif key == 'bin_left_edges_ms':
                    small[key] = value[:6:2]
                elif key in ('heldin_unit_ids', 'heldout_unit_ids'):
                    small[key] = value[:5]
                elif key.endswith('_ids'):
                    small[key] = value[:19]
                else:
                    small[key] = value.item()
            self.assertEqual(d.fingerprint(small), FINGERPRINT.compute_panel_fingerprint(small))
        self.assertNotEqual(self.public["panel_fingerprint"].item(), self.source["panel_fingerprint"])

    def test_every_original_cell_and_condition_survives_invertible_permutation(self):
        axes = self.binding["core"]["axes"]
        order = {}
        for name, n in d.AXIS_SIZES.items():
            source_index = {value: i for i, value in enumerate(axes[name]["opaque_in_source_order"])}
            order[name] = np.asarray([source_index[v] for v in self.public[name]])
            self.assertEqual(sorted(order[name].tolist()), list(range(n)))
            self.assertFalse(np.array_equal(order[name], np.arange(n)))
        for name, trials, units in (("train_counts_heldin", "train_trial_ids", "heldin_unit_ids"),
                                   ("train_counts_heldout", "train_trial_ids", "heldout_unit_ids"),
                                   ("eval_counts_heldin", "eval_trial_ids", "heldin_unit_ids")):
            self.assertEqual(self.public[name].dtype, self.source[name].dtype)
            for row in range(len(order[trials])):
                np.testing.assert_array_equal(self.public[name][row],
                                              self.source[name][order[trials][row]][:, order[units]])
        for split in ("train", "eval"):
            np.testing.assert_array_equal(self.public[split + "_condition_ids"],
                                          self.source[split + "_condition_ids"][order[split + "_trial_ids"]])
            self.assertEqual(self.public[split + "_condition_ids"].dtype,
                             self.source[split + "_condition_ids"].dtype)
        np.testing.assert_array_equal(self.public["bin_left_edges_ms"], d.GRID)
        self.assertTrue(self.public["eval_valid_mask"].all())

    def test_public_has_no_source_labels_or_operator_mapping(self):
        self.assertEqual(set(self.public), d.PUBLIC_KEYS)
        for name, value in self.public.items():
            self.assertFalse(value.flags.writeable)
            if name in d.AXIS_SIZES:
                self.assertTrue(all(str(v).startswith(("tr-", "un-")) for v in value))
                self.assertTrue(all(len(str(v)) == 35 for v in value))
                self.assertFalse(any("source-" in str(v) or "condition-" in str(v) for v in value))
        self.assertNotIn("source-trial-", d.canonical({k: v.tolist() for k, v in self.public.items()
                                                    if v.dtype.kind == "U"}).decode())
        self.assertNotEqual(self.public["source_manifest_sha256"].item(), self.source["source_manifest_sha256"])
        self.assertEqual(d.digest(self.binding["core"]), self.public["source_manifest_sha256"].item())

    def prediction(self):
        shape = (574, 140, 45)
        # Values are defined from source positions, then independently joined
        # to delivered IDs; reverse both submitted axes to exercise ID joins.
        source_values = (0.1 + np.arange(shape[0])[:, None, None] / 10000
                         + np.arange(shape[1])[None, :, None] / 100000
                         + np.arange(shape[2])[None, None, :] / 1000)
        axes = self.binding["core"]["axes"]
        ti = {v: i for i, v in enumerate(axes["eval_trial_ids"]["opaque_in_source_order"])}
        ui = {v: i for i, v in enumerate(axes["heldout_unit_ids"]["opaque_in_source_order"])}
        trials = self.public["eval_trial_ids"][::-1]
        units = self.public["heldout_unit_ids"][::-1]
        values = source_values[np.ix_([ti[x] for x in trials], np.arange(140), [ui[x] for x in units])]
        return {"trial_ids": trials, "heldout_unit_ids": units, "expected_counts": values,
                "bin_left_edges_ms": d.GRID, "prediction_units": "expected_spikes_per_bin",
                "panel_fingerprint": self.public["panel_fingerprint"]}, source_values

    def test_restore_arbitrary_prediction_order_and_existing_metric(self):
        p, source_values = self.prediction()
        restored = d.restore_prediction(p, self.binding, expected_binding_sha256=self.binding_sha)
        np.testing.assert_array_equal(restored["expected_counts"], source_values)
        np.testing.assert_array_equal(restored["trial_ids"], self.source["eval_trial_ids"])
        np.testing.assert_array_equal(restored["heldout_unit_ids"], self.source["heldout_unit_ids"])
        self.assertEqual(restored["panel_fingerprint"], self.source["panel_fingerprint"])
        target = np.broadcast_to((np.arange(574, dtype=np.uint8) % 3)[:, None, None], (574, 140, 45))
        gold = {"target_counts": target, "trial_ids": self.source["eval_trial_ids"],
                "heldout_unit_ids": self.source["heldout_unit_ids"], "bin_left_edges_ms": d.GRID,
                "valid_mask": self.source["eval_valid_mask"], "panel_fingerprint": self.source["panel_fingerprint"]}
        got = METRIC.score_submission(restored, gold)
        expected = METRIC.poisson_bits_per_spike(target, source_values, gold["valid_mask"])
        self.assertEqual(got, expected)

    def test_complete_panel_admission_rejects_missing_rows_targets_and_invalid_counts(self):
        source = self.source
        bad = []
        bad.append(dict(source, eval_counts_heldout=np.ones((1,))))
        bad.append(dict(source, eval_counts_heldin=source["eval_counts_heldin"][:-1]))
        bad.append(dict(source, bin_left_edges_ms=d.GRID + 1))
        bad.append(dict(source, eval_valid_mask=np.broadcast_to(False, (574, 140, 45))))
        bad.append(dict(source, train_trial_ids=np.repeat("duplicate", 1721)))
        bad.append(dict(source, eval_condition_ids=np.repeat("unseen", 574)))
        for value in (np.nan, -1.0, 0.5, np.uint64(2**53 + 1)):
            bad.append(dict(source, train_counts_heldin=np.broadcast_to(value, (1721, 140, 137))))
        for source_with_error in bad:
            with self.subTest(field=list(source_with_error)[-1]):
                with self.assertRaises(ValueError):
                    d.export_public(source_with_error, secret=bytes(32),
                                    expected_source_fingerprint=source["panel_fingerprint"])

    def test_content_and_custody_tampering_rejected(self):
        changed = dict(self.source, train_condition_ids=self.source["train_condition_ids"][::-1])
        with self.assertRaisesRegex(ValueError, "content fingerprint"):
            d.export_public(changed, secret=bytes(32), expected_source_fingerprint=self.source["panel_fingerprint"])
        p, _ = self.prediction()
        changed_binding = copy.deepcopy(self.binding)
        changed_binding["core"]["axes"]["eval_trial_ids"]["source"][0] = "different"
        with self.assertRaisesRegex(ValueError, "operator commitment"):
            d.restore_prediction(p, changed_binding, expected_binding_sha256=self.binding_sha)
        for field, value in (("prediction_units", "Hz"), ("panel_fingerprint", "0" * 64),
                             ("trial_ids", np.repeat("duplicate", 574)),
                             ("heldout_unit_ids", np.repeat("wrong", 45)),
                             ("expected_counts", np.zeros((574, 140, 45), dtype=np.uint8)),
                             ("expected_counts", np.ones((573, 140, 45), dtype=np.uint8))):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    d.restore_prediction(dict(p, **{field: value}), self.binding,
                                         expected_binding_sha256=self.binding_sha)

    def test_alias_reproducibility_key_and_role_separation(self):
        secret = bytes(range(32))
        a = d._alias(secret, "a" * 64, "tr", "example")
        self.assertEqual(a, d._alias(secret, "a" * 64, "tr", "example"))
        self.assertNotEqual(a, d._alias(bytes(reversed(secret)), "a" * 64, "tr", "example"))
        self.assertNotEqual(a, d._alias(secret, "b" * 64, "tr", "example"))
        self.assertNotEqual(a[3:], d._alias(secret, "a" * 64, "un", "example")[3:])
        with self.assertRaisesRegex(ValueError, "32 bytes"):
            d.export_public(self.source, secret=b"short", expected_source_fingerprint=self.source["panel_fingerprint"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
