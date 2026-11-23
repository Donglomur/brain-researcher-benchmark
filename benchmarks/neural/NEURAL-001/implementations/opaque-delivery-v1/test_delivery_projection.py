"""Generated software controls only; no authentic MEG or source target access."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

import delivery_projection as d

PREDECESSOR = Path(__file__).resolve().parent.parent / "programme-source/implementation-v1/correction-v3/package"
sys.path.insert(0, str(PREDECESSOR))
from support import packets

spec = importlib.util.spec_from_file_location("projection_control_packet_store", PREDECESSOR / "support/store-v1/packet_store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)

SECRET = bytes(range(32))  # Public GENERATED-control key, never use for real delivery.
LABELS = [f"MEG{i:03d}{suffix}" for i in range(102) for suffix in (1, 2, 3)]


def inputs(person):
    runs = list(d.RUNS[:2] if person == "sub-01" else d.RUNS)
    n = 4 * len(runs)
    training = {"meg": np.arange(n * 306, dtype="<f8").reshape(n, 306),
                "envelope": np.arange(n, dtype="<f8"), "offsets": np.arange(0, n + 1, 4, dtype="<i8"),
                "source_run_ids": runs, "source_epoch_numbers": [1] * len(runs),
                "channel_labels": LABELS.copy(), "fs_hz": 64}
    lengths = [4 + i % 3 for i in range(120)]
    offsets = np.asarray([0] + list(np.cumsum(lengths)), dtype="<i8")
    queries = {"meg": np.arange(int(offsets[-1]) * 306, dtype="<f8").reshape(int(offsets[-1]), 306),
               "offsets": offsets, "source_trial_indices": list(range(1, 121)),
               "channel_labels": LABELS.copy(), "fs_hz": 64}
    return training, queries


class ProjectionControls(unittest.TestCase):
    def test_complete_24_person_packet_store_interoperation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            packet_root, custody_root = base / "packets", base / "custody"
            packet_root.mkdir()
            custody_root.mkdir()
            records = {}
            for person in d.PEOPLE:
                training, queries = inputs(person)
                projected = d.project_person(person, training, queries, secret=SECRET)
                records[person] = d.write_projection(projected, packet_root, custody_root)
                private = json.loads((custody_root / projected.person_alias / "identity.json").read_text())
                self.assertEqual(private["prepared_file_pins"]["queries"], records[person]["queries"]["pin"])
                self.assertEqual(len(list((packet_root / projected.person_alias).iterdir())), 2)
            budget = store.IOBudget(source_read_limit=20_000_000, expanded_limit=20_000_000,
                                    materialized_limit=20_000_000, serialized_limit=20_000_000)
            admitted = store.PacketStore(str(packet_root), records, budget)
            self.assertEqual(len(records), 24)
            self.assertEqual(sum(len(r["training"]["run_ids"]) for r in records.values()), 94)
            for person in ("sub-01", "sub-02"):
                actual = admitted.load_training(person)
                training, queries = inputs(person)
                np.testing.assert_array_equal(actual["meg"], training["meg"])
                self.assertEqual(len(set(actual["run_ids"].tolist())), 2 if person == "sub-01" else 4)
                projected = d.project_person(person, training, queries, secret=SECRET)
                for index in (0, 59, 119):
                    query = admitted.load_query(person, records[person]["subject"]["query_ids"][index])
                    source = projected.private_mapping["projected_to_source_zero_based"][index]
                    a, b = queries["offsets"][source:source + 2]
                    np.testing.assert_array_equal(query["meg"], queries["meg"][a:b])
                    self.assertNotIn("source_trial_one_based", query)
                prior = admitted.load_query(person, records[person]["subject"]["query_ids"][0], "no_neural")
                self.assertEqual(set(prior), {"id", "length", "arm", "fs_hz"})

    def test_target_independent_mapping_and_exact_prediction_reassembly(self):
        training, queries = inputs("sub-02")
        projected = d.project_person("sub-02", training, queries, secret=SECRET)
        order = projected.private_mapping["projected_to_source_zero_based"]
        self.assertNotEqual(order, list(range(120)))
        source_target = np.arange(len(queries["meg"]), dtype="<f8")  # Generated values only.
        target, offsets = d.reorder_intervals(source_target, queries["offsets"], order)
        predictions = {ident: target[a:b].copy() for ident, a, b in
                       zip(projected.record["subject"]["query_ids"], offsets, offsets[1:])}
        body = packets.assemble_person(predictions, projected.record["subject"])
        actual = packets.validate_person_submission(body, projected.record["subject"])
        np.testing.assert_array_equal(actual, target)
        # Independent inverse: each projected segment must recover its original segment.
        recovered = np.empty_like(source_target)
        for index, source in enumerate(order):
            a, b = queries["offsets"][source:source + 2]
            recovered[a:b] = actual[offsets[index]:offsets[index + 1]]
        np.testing.assert_array_equal(recovered, source_target)
        changed = copy.deepcopy(queries)
        changed["meg"][:] = -77
        again = d.project_person("sub-02", training, changed, secret=SECRET)
        self.assertEqual(projected.private_mapping, again.private_mapping)
        training["envelope"][:] = 9
        changed_training = d.project_person("sub-02", training, queries, secret=SECRET)
        self.assertEqual(projected.private_mapping, changed_training.private_mapping)

    def test_public_schema_and_owned_arrays(self):
        training, queries = inputs("sub-02")
        projected = d.project_person("sub-02", training, queries, secret=SECRET)
        self.assertEqual(set(projected.queries), {"meg", "offsets", "interval_ids", "channel_labels"})
        self.assertEqual(set(projected.training), {"meg", "envelope", "offsets", "interval_ids", "run_ids", "channel_labels"})
        for array in (projected.training["interval_ids"], projected.training["run_ids"], projected.queries["interval_ids"]):
            for value in array:
                packets.opaque_id(str(value))
                self.assertNotIn("audiobook", value)
                self.assertNotIn("sub-", value)
        before = projected.training["meg"].copy()
        training["meg"][:] = -100
        np.testing.assert_array_equal(projected.training["meg"], before)
        other = d.project_person("sub-03", *inputs("sub-03"), secret=SECRET)
        self.assertTrue(set(other.queries["interval_ids"]).isdisjoint(projected.queries["interval_ids"]))

    def test_rejects_incomplete_runs_and_trials(self):
        for defect in ("wrong_run", "duplicate_epoch", "missing_trial", "reordered_trials", "target_field", "channel_order", "nonfinite"):
            with self.subTest(defect=defect):
                training, queries = inputs("sub-02")
                if defect == "wrong_run": training["source_run_ids"][3] = d.RUNS[0]
                if defect == "duplicate_epoch": training["source_run_ids"][1] = d.RUNS[0]
                if defect == "missing_trial": queries["source_trial_indices"].pop()
                if defect == "reordered_trials": queries["source_trial_indices"].reverse()
                if defect == "target_field": queries["target"] = np.zeros(len(queries["meg"]))
                if defect == "channel_order": queries["channel_labels"].reverse()
                if defect == "nonfinite": queries["meg"][0, 0] = np.nan
                with self.assertRaises(ValueError): d.project_person("sub-02", training, queries, secret=SECRET)
        with self.assertRaises(ValueError):
            d.reorder_intervals(np.arange(8), np.array([0, 4, 8], dtype="<i8"), [0, 0])

    def test_rejects_wrapped_offsets_before_interval_slicing(self):
        values = np.arange(12, dtype="<f8")
        malformed = np.array([0, np.iinfo(np.int64).max, -5, 12], dtype="<i8")
        # These signed differences wrap positive; neither the giant index nor
        # the negative slice is a permissible native interval boundary.
        self.assertTrue(np.all(np.diff(malformed) >= 4))
        for supplied in (values, np.column_stack((values, -values))):
            with self.subTest(dimensions=supplied.ndim):
                with self.assertRaisesRegex(ValueError, "Complete interval support"):
                    d.reorder_intervals(supplied, malformed, [0, 1, 2])
        valid = np.array([0, 4, 12], dtype="<i8")
        actual, offsets = d.reorder_intervals(values, valid, [1, 0])
        np.testing.assert_array_equal(actual, np.r_[values[4:], values[:4]])
        np.testing.assert_array_equal(offsets, [0, 8, 12])

    def test_rejects_wrapped_native_training_offsets(self):
        training, queries = inputs("sub-02")
        training["offsets"] = np.array(
            [0, np.iinfo(np.int64).max, -9, -5, len(training["meg"])], dtype="<i8")
        self.assertTrue(np.all(np.diff(training["offsets"]) >= 4))
        with self.assertRaisesRegex(ValueError, "Complete interval support"):
            d.project_person("sub-02", training, queries, secret=SECRET)

    def test_deterministic_files_and_no_overwrite_or_nested_custody(self):
        projected = d.project_person("sub-01", *inputs("sub-01"), secret=SECRET)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            roots = [base / name for name in ("packet_a", "custody_a", "packet_b", "custody_b")]
            for root in roots: root.mkdir()
            a = d.write_projection(projected, roots[0], roots[1])
            b = d.write_projection(projected, roots[2], roots[3])
            self.assertEqual(a, b)
            with self.assertRaises(ValueError): d.write_projection(projected, roots[0], roots[1])
            nested = roots[2] / "nested"
            nested.mkdir()
            with self.assertRaises(ValueError): d.write_projection(projected, roots[2], nested)


if __name__ == "__main__":
    unittest.main(verbosity=2)
