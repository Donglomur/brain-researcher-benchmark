"""Generated software controls only: no source recordings or historical answers."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packet


def fixture():
    n = packet.TRAIN + packet.QUERY
    source = {
        "counts": np.zeros((n, 180, 182), dtype=np.uint8),
        "trial_ids": np.asarray([f"generated-trial-{i}" for i in range(n)]),
        "split": np.asarray(["val" if i % 4 == 0 else "train" for i in range(n)]),
        "unit_ids": np.asarray([f"generated-unit-{i}" for i in range(182)]),
        # Interleave unit groups so a positional first-137 projection is wrong.
        "unit_is_heldout": np.asarray([i % 4 == 0 and i < 180 for i in range(182)]),
        "bin_left_edges_ms": np.arange(-250, 650, 5),
        "trial_type": np.arange(n, dtype=np.int64) % 7,
        "trial_version": np.arange(n, dtype=np.int64) % 3,
    }
    return source


class PacketTests(unittest.TestCase):
    def test_projection_joins_exact_identities_and_boundaries(self):
        source = fixture()
        # Trial 1 trains; trial 0 queries. Unit 0 is held-out, unit 1 held-in.
        source["counts"][0, 139, 1] = 11   # +445 ms: permitted
        source["counts"][0, 140, 1] = 23   # +450 ms: future target
        source["counts"][0, 139, 0] = 37   # query held-out past: never public
        source["counts"][0, 179, 0] = 41   # +645 ms held-out target
        source["counts"][1, 139, 0] = 43   # training held-out past: permitted
        source["counts"][1, 140, 0] = 47   # training future: permitted
        public, gold = packet.project(source)
        self.assertEqual(set(public), packet.PUBLIC_FIELDS)
        self.assertEqual(set(gold), packet.TARGET_FIELDS)
        self.assertEqual(public["eval_spikes_heldin"].shape, (574, 140, 137))
        self.assertEqual(public["train_future_counts"].shape, (1721, 40, 182))
        self.assertEqual(gold["target_counts"].shape, (574, 40, 182))
        self.assertEqual(public["eval_spikes_heldin"][0, 139, 0], 11)
        self.assertEqual(gold["target_counts"][0, 0, 0], 23)
        self.assertEqual(gold["target_counts"][0, 39, 137], 41)
        self.assertEqual(public["train_spikes_heldout"][0, 139, 0], 43)
        self.assertEqual(public["train_future_counts"][0, 0, 137], 47)
        self.assertTrue(gold["valid_mask"].all())
        self.assertEqual(public["eval_trial_ids"][0], "generated-trial-0")
        self.assertEqual(public["train_trial_ids"][0], "generated-trial-1")
        self.assertEqual(public["forecast_unit_ids"][137], "generated-unit-0")
        np.testing.assert_array_equal(public["eval_trial_type"], source["trial_type"][::4])
        np.testing.assert_array_equal(gold["unit_ids"], public["forecast_unit_ids"])
        for value in public.values():
            self.assertFalse(np.shares_memory(value, source["counts"]))
            for target in gold.values():
                self.assertFalse(np.shares_memory(value, target))
        source["counts"].fill(0)
        self.assertEqual(public["eval_spikes_heldin"][0, 139, 0], 11)

    def test_forbidden_values_cannot_affect_public_packet_or_fingerprint(self):
        source = fixture()
        public_before, gold_before = packet.project(source)
        query_rows = np.flatnonzero(source["split"] == "val")
        hidden_units = np.flatnonzero(source["unit_is_heldout"])
        source["counts"][np.ix_(query_rows, np.arange(140, 180), np.arange(182))] = 17
        source["counts"][np.ix_(query_rows, np.arange(140), hidden_units)] = 31
        public_after, gold_after = packet.project(source)
        for name in packet.PUBLIC_FIELDS:
            np.testing.assert_array_equal(public_before[name], public_after[name], err_msg=name)
        self.assertFalse(np.array_equal(gold_before["target_counts"], gold_after["target_counts"]))
        self.assertTrue((gold_after["target_counts"] == 17).all())
        # A permitted observation must change the public commitment.
        source["counts"][0, 0, 1] = 1
        changed, _ = packet.project(source)
        self.assertNotEqual(str(changed["panel_fingerprint"]), str(public_before["panel_fingerprint"]))

    def test_reject_partial_panel_fractional_counts_wrong_clock_and_extra_fields(self):
        source = fixture()
        cases = []
        cases.append({**source, "counts": source["counts"][:-1]})
        cases.append({**source, "bin_left_edges_ms": np.arange(-250, 650, 5) + 1})
        cases.append({**source, "behavior": np.zeros(1)})
        cases.append({**source, "counts": np.broadcast_to(np.asarray(0.5), source["counts"].shape)})
        cases.append({**source, "counts": np.broadcast_to(np.asarray(np.nan), source["counts"].shape)})
        cases.append({**source, "counts": np.broadcast_to(np.asarray(-1), source["counts"].shape)})
        cases.append({**source, "counts": np.broadcast_to(np.asarray(True), source["counts"].shape)})
        for bad in cases:
            with self.subTest(keys=set(bad), dtype=bad["counts"].dtype):
                with self.assertRaises(ValueError):
                    packet.project(bad)

    def test_reject_duplicated_ids_and_changed_split_or_unit_membership(self):
        source = fixture()
        for name, index, value in (("trial_ids", 1, source["trial_ids"][0]),
                                   ("unit_ids", 1, source["unit_ids"][0]),
                                   ("split", 0, "train"),
                                   ("unit_is_heldout", 0, False)):
            bad = dict(source)
            bad[name] = source[name].copy()
            bad[name][index] = value
            with self.subTest(field=name), self.assertRaises(ValueError):
                packet.project(bad)

    def test_serialized_inventory_and_existing_scorer_accept_same_panel(self):
        source = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            participant, operator = root / "participant", root / "operator"
            participant.mkdir()
            operator.mkdir()
            receipt = packet.write_packets(source, participant, operator)
            self.assertEqual({p.name for p in participant.iterdir()}, {"public_input.npz"})
            self.assertEqual({p.name for p in operator.iterdir()}, {"operator_future_targets.npz"})
            with np.load(participant / "public_input.npz", allow_pickle=False) as archive:
                self.assertEqual(set(archive.files), packet.PUBLIC_FIELDS)
                public = {name: archive[name] for name in archive.files}
            with np.load(operator / "operator_future_targets.npz", allow_pickle=False) as archive:
                self.assertEqual(set(archive.files), packet.TARGET_FIELDS)
                gold = {name: archive[name] for name in archive.files}
            core_path = Path(__file__).resolve().parents[1] / "registered-runtime" / "scoring-v2" / "scoring_core.py"
            spec = importlib.util.spec_from_file_location("forecast_scoring_v2", core_path)
            core = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(core)
            identities = packet.scorer_public(public)
            candidate = {**identities, "expected_counts": np.full((574, 40, 182), 0.1, dtype=np.float32)}
            core.validate_candidate(candidate, identities)
            self.assertEqual(str(gold["panel_fingerprint"]), receipt["panel_fingerprint"])
            np.testing.assert_array_equal(gold["trial_ids"], identities["trial_ids"])
            np.testing.assert_array_equal(gold["unit_ids"], identities["forecast_unit_ids"])
            with self.assertRaises(ValueError):
                packet.write_packets(source, participant, operator)

    def test_nested_roots_rejected_before_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "private"
            child.mkdir()
            # Invalid empty source demonstrates path rejection precedes preparation.
            for left, right in ((root, root), (root, child), (child, root)):
                with self.assertRaisesRegex(ValueError, "disjoint"):
                    packet.write_packets({}, left, right)


if __name__ == "__main__":
    unittest.main()
