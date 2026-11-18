"""Generated controls: real storage on a mocked tiny grid, full metadata census separately."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collection as C

GENERATED_WRITE_UPPER = 0


def tiny_plan():
    return ([{"family": "glm", "id": j["id"], "job": j}
             for j in itertools.islice(C.G.job_plan(), 2)] +
            [{"family": "geometry", "id": C.P.geometry_id(j), "job": j}
             for j in itertools.islice(C.R.geometry_plan(), 2)])


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="collection-generated-", dir=Path(__file__).parent)
        self.base = Path(self.temp.name).resolve()
        self.removed_or_overwritten = 0
        self.plan = tiny_plan()

    def tearDown(self):
        global GENERATED_WRITE_UPPER
        # A conservative logical-byte charge, including copies later deleted or
        # overwritten. Hard-link aliases conservatively count twice here.
        current = sum(p.stat().st_size for p in self.base.rglob("*") if p.is_file() and not p.is_symlink())
        GENERATED_WRITE_UPPER += current + self.removed_or_overwritten
        self.temp.cleanup()

    @contextmanager
    def mocked_grid(self):
        with mock.patch.object(C, "full_plan", side_effect=lambda: iter(self.plan)), \
             mock.patch.object(C, "EXPECTED_COUNTS", {"glm": 2, "geometry": 2}):
            yield

    def binding(self):
        return C.make_binding(method_sha256="1" * 64, operator_input_sha256="2" * 64,
                              information_condition="paper_data")

    def records(self):
        return [{"family": c["family"], "id": c["id"],
                 "candidate": {"job_id": c["id"], "method_sha256": "1" * 64,
                               "values": np.arange(6, dtype=float).reshape(2, 3)}} for c in self.plan]

    def freeze(self, records=None, name="submission", **kw):
        root = self.base / name
        binding = self.binding()
        result = C.freeze_submission(root, self.records() if records is None else records, binding,
                                     max_result_bytes=kw.get("max_result_bytes", 8192),
                                     max_total_bytes=kw.get("max_total_bytes", 131072))
        return root, binding, result

    def verify(self, root, binding, result, **kw):
        return C.verify_submission(root, binding, expected_complete_sha256=result["complete_sha256"],
                                   max_result_bytes=kw.get("max_result_bytes", 8192),
                                   max_total_bytes=kw.get("max_total_bytes", 131072))

    def evaluate(self, root, binding, result, calls):
        def loader(family, job):
            calls.append((family, job))
            return {"trusted": True}
        def evaluator(reference, candidate):
            self.assertEqual(reference, {"trusted": True})
            return candidate["values"].sum()
        return list(C.evaluate_submission(root, binding, loader,
                         {"glm": evaluator, "geometry": evaluator},
                         expected_complete_sha256=result["complete_sha256"],
                         max_result_bytes=8192, max_total_bytes=131072))

    def overwrite(self, path, content):
        self.removed_or_overwritten += path.stat().st_size
        path.write_bytes(content)

    def remove(self, path):
        self.removed_or_overwritten += sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        shutil.rmtree(path)

    def mutate_manifest_with_new_external_seal(self, root, result, mutate):
        """Craft a consistently rehashed malicious packet to test structural checks."""
        path = root / "RECORDS.jsonl"
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        mutate(rows)
        stream = b"".join(C.canonical(row) + b"\n" for row in rows)
        self.overwrite(path, stream)
        complete_path = root / "COMPLETE.json"
        complete = json.loads(complete_path.read_bytes())
        complete["record_stream"] = {"path": "RECORDS.jsonl", "bytes": len(stream),
                                     "sha256": hashlib.sha256(stream).hexdigest()}
        actual_artifacts = sum(p.stat().st_size for p in (root / "records").rglob("*") if p.is_file())
        while True:
            raw = C.canonical(complete) + b"\n"
            total = actual_artifacts + len(stream) + len(raw)
            if complete["cumulative_logical_write_bytes"] == total:
                break
            complete["cumulative_logical_write_bytes"] = total
        self.overwrite(complete_path, raw)
        result["complete_sha256"] = hashlib.sha256(raw).hexdigest()

    def test_full_original_metadata_census_and_order(self):
        census = C.plan_fingerprint()
        self.assertEqual(census["counts"], {"glm": 13824, "geometry": 64000})
        seen = {"glm": set(), "geometry": set()}
        first = last = None
        for row in C.full_plan():
            if first is None:
                first = row
            self.assertNotIn(row["id"], seen[row["family"]])
            seen[row["family"]].add(row["id"])
            last = row
        self.assertEqual(first["id"], "CA1-b000-KL8-s01")
        self.assertEqual(last["id"], "PFC-r499-ZT2-s08-PFC")
        self.assertEqual({k: len(v) for k, v in seen.items()}, census["counts"])

    def test_real_numeric_storage_roundtrip_and_evaluator_binding(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            seal = self.verify(root, binding, result)
            self.assertEqual(seal["records"], 4)
            self.assertEqual(result["cumulative_logical_write_bytes"],
                             sum(p.stat().st_size for p in root.rglob("*") if p.is_file()))
            calls = []
            outputs = self.evaluate(root, binding, result, calls)
            self.assertEqual(len(calls), 4)
            self.assertEqual([r["id"] for r in outputs], [r["id"] for r in self.plan])
            self.assertTrue(all(r["result"] == 15 for r in outputs))
            self.assertFalse(seal["phase_isolation_attested"])

    def test_every_payload_is_loaded_before_first_reference_callback(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            original = C.P.load_result
            loads = []
            def counted(*args, **kwargs):
                loads.append(str(args[0]))
                return original(*args, **kwargs)
            def reference(family, job):
                self.assertGreaterEqual(len(loads), 5)
                return {}
            with mock.patch.object(C.P, "load_result", side_effect=counted):
                outputs = list(C.evaluate_submission(root, binding, reference,
                    {"glm": lambda r, c: {}, "geometry": lambda r, c: {}},
                    expected_complete_sha256=result["complete_sha256"],
                    max_result_bytes=8192, max_total_bytes=131072))
            self.assertEqual(len(outputs), 4)

    def test_incomplete_grid_remains_partial_and_refuses_evaluation(self):
        with self.mocked_grid():
            with self.assertRaisesRegex(ValueError, "incomplete candidate grid"):
                self.freeze(self.records()[:-1])
            root = self.base / "submission"
            self.assertFalse((root / "COMPLETE.json").exists())
            self.assertTrue((root / "FAILURE.json").exists())
            self.assertEqual(len(list((root / "records").iterdir())), 3)
            calls = []
            with self.assertRaises(ValueError):
                self.evaluate(root, self.binding(), {"complete_sha256": "0" * 64}, calls)
            self.assertEqual(calls, [])

    def test_duplicate_reordered_and_extra_records_are_not_complete(self):
        with self.mocked_grid():
            values = self.records()
            variants = [values[:1] + values[:1] + values[2:],
                        [values[1], values[0], *values[2:]], values + values[:1]]
            for index, rows in enumerate(variants):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    self.freeze(rows, name=f"bad{index}")
                self.assertFalse((self.base / f"bad{index}" / "COMPLETE.json").exists())

    def test_candidate_method_or_job_change_refused_before_numeric_write(self):
        with self.mocked_grid():
            for index, key in enumerate(("method_sha256", "job_id")):
                rows = self.records()
                rows[0]["candidate"][key] = "3" * 64
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    self.freeze(rows, name=f"bad{index}")
                self.assertEqual(list((self.base / f"bad{index}" / "records").iterdir()), [])

    def test_altered_operator_input_binding_fails_before_target_access(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            binding = dict(binding, operator_input_sha256="7" * 64)
            calls = []
            with self.assertRaisesRegex(ValueError, "identity/counts differ"):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_external_freeze_hash_is_required(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            for changed in ("", "a" * 64):
                with self.assertRaises(ValueError):
                    self.verify(root, binding, dict(result, complete_sha256=changed))

    def test_late_array_tamper_blocks_every_reference_callback(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            path = root / "records/000003/arrays.npz"
            data = bytearray(path.read_bytes()); data[-1] ^= 1
            self.overwrite(path, data)
            calls = []
            with self.assertRaisesRegex(ValueError, "numeric artifact differs"):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_late_json_tamper_blocks_every_reference_callback(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            path = root / "records/000003/record.json"
            self.overwrite(path, path.read_bytes().replace(b'"method_sha256":"1111', b'"method_sha256":"9999'))
            calls = []
            with self.assertRaisesRegex(ValueError, "numeric artifact differs"):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_missing_late_payload_directory_blocks_every_reference(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            self.remove(root / "records/000003")
            calls = []
            with self.assertRaises((OSError, ValueError)):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_extra_coordinate_and_root_files_refused(self):
        with self.mocked_grid():
            for index, extra in enumerate(("records/000004", "unexpected")):
                root, binding, result = self.freeze(name=f"extra{index}")
                (root / extra).mkdir()
                calls = []
                with self.assertRaises(ValueError):
                    self.evaluate(root, binding, result, calls)
                self.assertEqual(calls, [])

    def test_manifest_path_traversal_refused_even_with_new_consistent_seal(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            self.mutate_manifest_with_new_external_seal(root, result,
                lambda rows: rows[-1].update(path="../outside"))
            calls = []
            with self.assertRaisesRegex(ValueError, "manifest coordinate/order differs"):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_duplicate_manifest_coordinate_refused_with_new_consistent_seal(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            self.mutate_manifest_with_new_external_seal(root, result,
                lambda rows: rows.__setitem__(-1, dict(rows[-2])))
            calls = []
            with self.assertRaisesRegex(ValueError, "manifest coordinate/order differs"):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_torn_manifest_line_rejected_before_reference(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            path = root / "RECORDS.jsonl"
            self.overwrite(path, path.read_bytes()[:-1])
            calls = []
            with self.assertRaises(ValueError):
                self.evaluate(root, binding, result, calls)
            self.assertEqual(calls, [])

    def test_symlink_and_hardlink_payload_refused(self):
        with self.mocked_grid():
            for index, linkkind in enumerate(("symlink", "hardlink")):
                root, binding, result = self.freeze(name=f"links{index}")
                target = root / "records/000003/arrays.npz"
                outside = self.base / f"outside{index}.npz"
                if linkkind == "symlink":
                    target.rename(outside)
                    target.symlink_to(outside)
                else:
                    outside.hardlink_to(target)
                calls = []
                with self.assertRaisesRegex(ValueError, "ordinary bounded single-link"):
                    self.evaluate(root, binding, result, calls)
                self.assertEqual(calls, [])

    def test_fresh_output_required_and_earlier_complete_not_overwritten(self):
        with self.mocked_grid():
            root, binding, result = self.freeze()
            original = (root / "COMPLETE.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "fresh ordinary"):
                self.freeze()
            self.assertEqual((root / "COMPLETE.json").read_bytes(), original)

    def test_result_and_total_byte_limits_refuse_before_completion(self):
        with self.mocked_grid():
            with self.assertRaises(ValueError):
                self.freeze(max_result_bytes=64)
            root = self.base / "submission"
            self.assertFalse((root / "COMPLETE.json").exists())
            failure = json.loads((root / "FAILURE.json").read_bytes())
            self.assertEqual(failure["charged_before_failure_receipt"], 64)
            with self.assertRaises(ValueError):
                self.freeze(name="smalltotal", max_result_bytes=8192, max_total_bytes=13000)
            self.assertFalse((self.base / "smalltotal/COMPLETE.json").exists())

    def test_object_array_is_refused_and_unknown_writer_allowance_preserved(self):
        with self.mocked_grid():
            rows = self.records(); rows[0]["candidate"]["values"] = np.array([object()], dtype=object)
            with self.assertRaises(ValueError):
                self.freeze(rows)
            failure = json.loads((self.base / "submission/FAILURE.json").read_bytes())
            self.assertEqual(failure["charged_before_failure_receipt"], 8192)
            self.assertFalse((self.base / "submission/COMPLETE.json").exists())

    def test_partial_completion_write_is_precharged_before_failure_receipt(self):
        with self.mocked_grid():
            original = C._write_exclusive
            attempts = []
            def fail_completion(path, raw):
                if path.name == "COMPLETE.json":
                    attempts.append(len(raw))
                    original(path, raw[:100])
                    raise OSError("generated partial completion write")
                return original(path, raw)
            with mock.patch.object(C, "_write_exclusive", side_effect=fail_completion):
                with self.assertRaisesRegex(OSError, "generated partial completion"):
                    self.freeze()
            root = self.base / "submission"
            failure = json.loads((root / "FAILURE.json").read_bytes())
            artifacts = sum(p.stat().st_size for p in (root / "records").rglob("*") if p.is_file())
            stream = (root / "RECORDS.jsonl").stat().st_size
            self.assertEqual(failure["charged_before_failure_receipt"], artifacts + stream + attempts[0])
            self.assertLessEqual(failure["charged_before_failure_receipt"] +
                                 (root / "FAILURE.json").stat().st_size, 131072)
            self.assertEqual((root / "COMPLETE.json").stat().st_size, 100)

    def test_partial_numeric_write_retains_full_inherited_writer_allowance(self):
        with self.mocked_grid():
            def fail_save(path, *args, **kwargs):
                path.mkdir()
                (path / "arrays.npz").write_bytes(b"partial")
                raise OSError("generated partial numeric write")
            with mock.patch.object(C.P, "save_result", side_effect=fail_save):
                with self.assertRaisesRegex(OSError, "partial numeric"):
                    self.freeze()
            failure = json.loads((self.base / "submission/FAILURE.json").read_bytes())
            self.assertEqual(failure["charged_before_failure_receipt"], 8192)
            self.assertEqual((self.base / "submission/records/000000/arrays.npz").read_bytes(), b"partial")

    def test_bad_limit_types_and_unknown_information_condition_refused(self):
        with self.mocked_grid():
            for value in (True, 0, -1, 2.5):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    C.freeze_submission(self.base / "nooutput", [], self.binding(),
                                        max_result_bytes=value, max_total_bytes=131072)
            with self.assertRaisesRegex(ValueError, "information condition"):
                C.make_binding(method_sha256="1" * 64, operator_input_sha256="2" * 64,
                               information_condition="paper_and_answers")
            self.assertFalse((self.base / "nooutput").exists())


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = (unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:], module=sys.modules[__name__])
             if len(sys.argv) > 1 else unittest.defaultTestLoader.loadTestsFromTestCase(CollectionTests))
    def method_names(items):
        for item in items:
            if isinstance(item, unittest.TestSuite):
                yield from method_names(item)
            else:
                yield item.id()
    selected = list(method_names(suite))
    result = runner.run(suite)
    print(json.dumps({"generated_logical_write_upper_bytes": GENERATED_WRITE_UPPER,
                      "scope": "real tiny numeric storage with explicitly mocked 2+2 grid; original metadata census only when its named method executes",
                      "selected_methods": selected,
                      "full_metadata_census_executed": any(n.endswith(".test_full_original_metadata_census_and_order") for n in selected),
                      "authentic_input_reads": 0}, sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
