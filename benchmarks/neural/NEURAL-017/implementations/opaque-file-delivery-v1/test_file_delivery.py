"""Generated complete-panel controls; never load an authentic task operand."""
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("file_delivery_controls", HERE / "file_delivery.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
WRITTEN = 0


def count_write(path, body, cap=None):
    global WRITTEN
    assert WRITTEN + len(body) <= 32 * 1024**2, "Cumulative generated fixture payload cap"
    if cap is None:
        Path(path).write_bytes(body)
        value = a.pin(body)
    else:
        value = ORIGINAL_WRITE(path, body, cap)
    WRITTEN += len(body)
    return value


ORIGINAL_WRITE = a.write_new
a.write_new = count_write


def npz(arrays):
    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    return stream.getvalue()


class FullPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        # macOS /var is a symlink; use the actual temporary directory identity.
        cls.root = Path(cls.temp.name).resolve()
        cls.sources = a.load_sources()
        cls.sources.assets = copy.deepcopy(cls.sources.assets)
        d = cls.sources.delivery
        clock = np.arange(-250, 450, 5, dtype=float)
        source = {
            "train_counts_heldin": np.broadcast_to((np.arange(140)[:, None] + np.arange(137)[None, :]).astype("u1") % 5, (1721, 140, 137)),
            "train_counts_heldout": np.broadcast_to((np.arange(140)[:, None] + np.arange(45)[None, :]).astype("u1") % 7, (1721, 140, 45)),
            "eval_counts_heldin": np.broadcast_to((np.arange(140)[:, None] + np.arange(137)[None, :]).astype("u1") % 3, (574, 140, 137)),
            "train_trial_ids": np.asarray([f"source-train-{i}" for i in range(1721)]),
            "eval_trial_ids": np.asarray([f"source-query-{i}" for i in range(574)]),
            "heldin_unit_ids": np.asarray([f"source-observed-{i}" for i in range(137)]),
            "heldout_unit_ids": np.asarray([f"source-withheld-{i}" for i in range(45)]),
            "train_condition_ids": np.asarray([f"condition-{i % 3}" for i in range(1721)]),
            "eval_condition_ids": np.asarray([f"condition-{i % 3}" for i in range(574)]),
            "bin_left_edges_ms": clock,
            "eval_valid_mask": np.ones((574, 140, 45), dtype=bool),
            "source_manifest_sha256": np.asarray("a" * 64),
        }
        source["panel_fingerprint"] = np.asarray(d.fingerprint(source))
        cls.source_pin = count_write(cls.root / "source.npz", npz(source))
        cls.sources.assets["public"]["packet"].update(cls.source_pin)
        cls.sources.assets["panel_fingerprint"] = str(source["panel_fingerprint"])
        count_write(cls.root / "key", bytes(range(32)))
        cls.export = a.export_packet(cls.root / "source.npz", cls.root / "key",
            cls.root / "public", cls.root / "operator", cls.sources)
        cls.receipt_path = cls.root / "operator/EXPORT.json"
        cls.binding_path = cls.root / "operator/binding.json"
        cls.binding = json.loads(cls.binding_path.read_bytes())
        cls.original = (1.0 + (np.arange(574) % 3)[:, None, None]
                        + (np.arange(140) % 2)[None, :, None] / 4
                        + (np.arange(45) % 5)[None, None, :] / 8)
        axes = cls.binding["core"]["axes"]
        # Deliberately use noncanonical participant row and unit ordering.
        cls.query_order = np.arange(574)[::-1]
        cls.unit_order = np.roll(np.arange(45), 7)
        cls.candidate = {
            "expected_counts": cls.original[np.ix_(cls.query_order, np.arange(140), cls.unit_order)],
            "trial_ids": np.asarray(axes["eval_trial_ids"]["opaque_in_source_order"])[cls.query_order],
            "heldout_unit_ids": np.asarray(axes["heldout_unit_ids"]["opaque_in_source_order"])[cls.unit_order],
            "bin_left_edges_ms": clock,
            "prediction_units": np.asarray("expected_spikes_per_bin"),
            "panel_fingerprint": np.asarray(cls.binding["public_panel_fingerprint"]),
        }
        cls.target_calls = 0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(dir=self.root))
        self.calls = []

    def protected(self, zero=False):
        self.calls.append("protected")
        shape = (574, 140, 45)
        axes = self.binding["core"]["axes"]
        gold = {"counts_heldout": np.zeros(shape, dtype="u1") if zero else np.ones(shape, dtype="u1"),
            "trial_ids": np.asarray(axes["eval_trial_ids"]["source"]),
            "unit_ids": np.asarray(axes["heldout_unit_ids"]["source"]),
            "valid_mask": np.ones(shape, dtype=bool),
            "panel_fingerprint": self.sources.assets["panel_fingerprint"]}
        fixed = {"expected_counts": np.full(shape, 1.25),
            "trial_ids": gold["trial_ids"], "heldout_unit_ids": gold["unit_ids"],
            "bin_left_edges_ms": self.sources.delivery.GRID,
            "prediction_units": "expected_spikes_per_bin", "panel_fingerprint": gold["panel_fingerprint"]}
        return gold, fixed

    def run_candidate(self, candidate=None, *, zero=False, receipt_path=None, receipt_pin=None, binding_path=None):
        body = npz(self.candidate if candidate is None else candidate)
        submission_pin = count_write(self.case / "submitted.npz", body)
        return a.collect_and_grade(receipt_path or self.receipt_path,
            receipt_pin or self.export["export_receipt"], binding_path or self.binding_path,
            self.case / "submitted.npz", submission_pin, self.case / "grade", self.sources,
            lambda: self.protected(zero))

    def test_full_export_every_cell_and_private_custody(self):
        self.assertEqual({p.name for p in (self.root / "public").iterdir()}, {"public.npz"})
        with np.load(self.root / "public/public.npz", allow_pickle=False) as public:
            self.assertEqual(set(public.files), self.sources.delivery.PUBLIC_KEYS)
            axes = self.binding["core"]["axes"]
            for count_key, trial_axis, unit_axis, modulus in (
                ("train_counts_heldin", "train_trial_ids", "heldin_unit_ids", 5),
                ("train_counts_heldout", "train_trial_ids", "heldout_unit_ids", 7),
                ("eval_counts_heldin", "eval_trial_ids", "heldin_unit_ids", 3),
            ):
                perm = np.argsort(axes[unit_axis]["opaque_in_source_order"])
                raw = (np.arange(140)[:, None] + np.arange(len(perm))[None, :]).astype("u1") % modulus
                got = public[count_key]
                self.assertEqual(got.shape, self.sources.delivery.COUNT_SHAPES[count_key])
                self.assertTrue(np.array_equal(got, np.broadcast_to(raw[:, perm], got.shape)))
                self.assertTrue(all(str(x).startswith("tr-") for x in public[trial_axis]))
            for split, n in (("train", 1721), ("eval", 574)):
                order = np.argsort(axes[split + "_trial_ids"]["opaque_in_source_order"])
                self.assertEqual(public[split + "_condition_ids"].tolist(), [f"condition-{i % 3}" for i in order])
                self.assertEqual(len(order), n)
            self.assertTrue(np.array_equal(public["bin_left_edges_ms"], self.sources.delivery.GRID))
            self.assertTrue(public["eval_valid_mask"].all())
        receipt = json.loads(self.receipt_path.read_bytes())
        self.assertEqual(receipt["support"], a.SUPPORT)
        self.assertFalse(receipt["old_campaign_commitments_valid_for_this_export"])
        self.assertEqual((self.root / "operator").stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.binding_path.stat().st_mode & 0o777, 0o400)

    def test_full_reordered_prediction_original_metric_and_source_axes(self):
        result = self.run_candidate()
        self.assertEqual(self.calls, ["protected"])
        self.assertEqual(result["protected_callback_invocations"], 1)
        with np.load(self.case / "grade/restored_predictions.npz", allow_pickle=False) as restored:
            self.assertTrue(np.array_equal(restored["expected_counts"], self.original))
            self.assertEqual(restored["trial_ids"].tolist(), self.binding["core"]["axes"]["eval_trial_ids"]["source"])
        score = json.loads((self.case / "grade/score.json").read_bytes())
        # Independent finite 30-term oracle for all 3,616,200 cells.
        total = 0.0
        for t in range(3):
            trials = sum(i % 3 == t for i in range(574))
            for b in range(2):
                for u in range(5):
                    lam = 1 + t + b / 4 + u / 8
                    total += trials * 70 * 9 * (math.log(lam) + 1 - lam)
        expected = total / (574 * 140 * 45 * math.log(2))
        self.assertAlmostEqual(score["candidate"]["co_bps"], expected, places=12)
        self.assertAlmostEqual(score["fixed_condition_time"]["co_bps"], (math.log(1.25) - .25) / math.log(2), places=12)
        self.assertLess(score["candidate_minus_condition_co_bps"], 0)
        self.assertEqual(score["candidate"]["valid_cells"], 3616200)
        self.assertFalse(score["scientific_admission"])

    def test_zero_target_total_is_undefined_not_perfect(self):
        self.run_candidate(zero=True)
        score = json.loads((self.case / "grade/score.json").read_bytes())
        self.assertEqual(score["status"], "undefined_zero_target_spikes")
        self.assertIsNone(score["candidate"]["co_bps"])

    def test_missing_query_rejected_before_protected_callback(self):
        changed = dict(self.candidate, trial_ids=self.candidate["trial_ids"][:-1])
        with self.assertRaisesRegex(ValueError, "shape"):
            self.run_candidate(changed)
        self.assertFalse(self.calls)
        receipt = json.loads((self.case / "grade/RECEIPT.json").read_bytes())
        self.assertEqual(receipt["protected_callback_invocations"], 0)
        self.assertEqual(receipt["status"], "operator_error")

    def test_duplicate_axis_wrong_clock_units_and_panel_refuse(self):
        changes = {
            "trial_ids": np.repeat(self.candidate["trial_ids"][:1], 574),
            "heldout_unit_ids": np.repeat(self.candidate["heldout_unit_ids"][:1], 45),
            "bin_left_edges_ms": self.sources.delivery.GRID + 1,
            "prediction_units": np.asarray("Hz"),
            "panel_fingerprint": np.asarray("f" * 64),
        }
        for name, value in changes.items():
            with self.subTest(name=name):
                self.case = Path(tempfile.mkdtemp(dir=self.root))
                with self.assertRaises(ValueError):
                    self.run_candidate(dict(self.candidate, **{name: value}))
                self.assertFalse(self.calls)

    def test_zero_and_nonfinite_prediction_refuse(self):
        for value in (0.0, float("nan"), float("inf")):
            self.case = Path(tempfile.mkdtemp(dir=self.root))
            changed = dict(self.candidate, expected_counts=np.full((574, 140, 45), value))
            with self.assertRaises(ValueError):
                self.run_candidate(changed)
            self.assertFalse(self.calls)

    def test_extra_npz_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.run_candidate(dict(self.candidate, targets=np.asarray([1])))
        self.assertFalse(self.calls)

    def test_source_pin_failure_precedes_array_decode(self):
        path = self.case / "changed.npz"
        body = bytearray((self.root / "source.npz").read_bytes())
        body[0] ^= 1
        count_write(path, bytes(body))
        with patch.object(self.sources.arrays, "load_arrays", side_effect=AssertionError("decoder reached")):
            with self.assertRaisesRegex(ValueError, "pin"):
                a.export_packet(path, self.root / "key", self.case / "public", self.case / "operator", self.sources)
        self.assertFalse((self.case / "public").exists())

    def test_changed_mapping_and_receipt_refuse_before_candidate_parser(self):
        bad = self.case / "binding.json"
        binding = copy.deepcopy(self.binding)
        binding["core"]["axes"]["eval_trial_ids"]["source"].reverse()
        count_write(bad, a.encoded(binding))
        with patch.object(self.sources.grader, "candidate_npz", side_effect=AssertionError("parser reached")):
            with self.assertRaises(ValueError):
                self.run_candidate(binding_path=bad)
        self.assertFalse(self.calls)

    def test_export_scope_cannot_be_reduced(self):
        receipt = json.loads(self.receipt_path.read_bytes())
        receipt["support"]["query_trials"] = 573
        path = self.case / "EXPORT.json"
        wanted = count_write(path, a.encoded(receipt))
        with self.assertRaisesRegex(ValueError, "support"):
            self.run_candidate(receipt_path=path, receipt_pin=wanted)
        self.assertFalse(self.calls)

    def test_captured_file_mutation_is_detected_before_targets(self):
        original = self.sources.grader.candidate_npz
        def mutate_after_parse(path, *args):
            result = original(path, *args)
            path.chmod(0o600)
            count_write(path, b"invalid")
            return result
        with patch.object(self.sources.grader, "candidate_npz", mutate_after_parse):
            with self.assertRaises(ValueError):
                self.run_candidate()
        self.assertFalse(self.calls)

    def test_wrong_private_pin_refuses_without_score(self):
        path = self.case / "private.npz"
        count_write(path, b"generated invalid source")
        loader = a.protected_loader(path, self.case / "absent.npz", self.sources)
        with self.assertRaisesRegex(ValueError, "extent"):
            loader()

    def test_complete_generated_private_files_are_loaded_only_after_restoration(self):
        gold, fixed = self.protected()
        self.calls.clear()
        reference = dict(fixed)
        reference["rates_condition_psth"] = reference.pop("expected_counts")
        # A trusted archive can contain unselected members. The file loader
        # must decode only the original selected operands, with pickle disabled.
        reference["unused_object_member"] = np.asarray([{"never": "decode"}], dtype=object)
        target = self.case / "target.npz"
        comparator = self.case / "reference.npz"
        target_pin = count_write(target, npz(gold))
        comparator_pin = count_write(comparator, npz(reference))
        submission = self.case / "submitted.npz"
        submitted_pin = count_write(submission, npz(self.candidate))
        with patch.dict(self.sources.assets["private"]["targets"], target_pin), \
             patch.dict(self.sources.assets["private"]["comparator"], comparator_pin):
            loader = a.protected_loader(target, comparator, self.sources,
                other_roles=(self.case / "grade", submission, self.receipt_path, self.binding_path))
            def late():
                self.assertTrue((self.case / "grade/restored_predictions.npz").exists())
                self.calls.append("file-loader")
                return loader()
            result = a.collect_and_grade(self.receipt_path, self.export["export_receipt"],
                self.binding_path, submission, submitted_pin, self.case / "grade", self.sources, late)
        self.assertEqual(result["status"], "scored_development_candidate")
        self.assertEqual(self.calls, ["file-loader"])

    def test_role_alias_symlink_extent_duplicate_json_and_no_overwrite(self):
        with self.assertRaisesRegex(ValueError, "Disjoint"):
            a.separate(self.case, self.case / "nested")
        link = self.case / "link"
        link.symlink_to(self.root / "key")
        with self.assertRaisesRegex(ValueError, "Unlinked"):
            a.snapshot(link, a.pin(bytes(range(32))), 32)
        with self.assertRaises(ValueError):
            a.decode(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            a.decode(b'{"a":1e999}')
        with self.assertRaises(ValueError):
            a.export_packet(self.root / "source.npz", self.root / "key", self.root / "public", self.root / "operator", self.sources)
        self.assertEqual(a.pin(self.receipt_path.read_bytes()), self.export["export_receipt"])


if __name__ == "__main__":
    import sys
    suite = (unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:], module=sys.modules[__name__])
             if len(sys.argv) > 1 else unittest.defaultTestLoader.loadTestsFromTestCase(FullPanel))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"generated_fixture_payload_write_bytes": WRITTEN,
        "scope": "Successful explicit fixture and adapter file body writes only; not filesystem metadata or physical I/O.",
        "runtime": a.runtime(), "authentic_payload_reads": 0, "model_or_native_runs": 0}, sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
