"""Generated engineering controls; tiny mocked storage roster, original row shapes.

No authentic arrays, fits, provider invocation or isolation qualification. The
separate census test traverses all original metadata. Storage tests explicitly
mock the shared collector's plan to two GLM plus two geometry coordinates.
STAGED_FIXTURE_ROOT can constrain every disposable fixture to an evidence lane.
GENERATED_WRITE_BYTES counts retained plus overwritten/deleted logical bytes;
this is not allocated disk blocks, interpreter caches or external pool logs.
"""
from __future__ import annotations

import atexit
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import staged_delivery as S
from dependency_loader import G, C, GB, GLB, P, R, V

GENERATED_WRITE_BYTES = 0
FREEZE_INVOCATIONS = 0
CAPS = {"max_result_bytes": 65536, "max_total_bytes": 262144}
SHA = "1" * 64


def reference(job):
    rows = np.arange(500, dtype=np.uint16)
    return {"schema": "population_geometry_operator_reference_v1", "job": copy.deepcopy(job),
            "points": np.arange(9500, dtype=np.float32).reshape(500, 19) / 9500,
            "row_ids": rows, "unit_ids": np.arange(19, dtype=np.uint8),
            "training_positions": np.arange(299, -1, -1, dtype=np.int16),
            "test_positions": np.arange(300, 500, dtype=np.int16),
            "valid_teacher_indices": np.arange(101, dtype=np.int16),
            "labels": np.where(np.arange(500)[:, None] % 2, 1, -1).astype(np.int8) * np.ones((1, 101), dtype=np.int8),
            "latents": np.full((500, 4), 77, dtype=np.float32),
            "source_svc_predictions": np.ones((200, 101), dtype=np.int8),
            "source_checkpoint_sha256": SHA, "private_glm_inputs": "never delivered"}


class FakeRuntime(S.FreshCoordinateRuntime):
    """Deliberately same-process adapter; all successful artifacts stay ineligible."""
    def __init__(self, duplicate=False, corrupt_close=False):
        self.requests, self.observations, self.closed = [], [], []
        self.duplicate, self.corrupt_close = duplicate, corrupt_close
        self.shared = None

    def provision_fresh_context(self, request):
        self.requests.append(copy.deepcopy(request))
        context = "ctx-1" if self.duplicate else "ctx-" + str(len(self.requests))
        request["method_sha256"] = "9" * 64  # Must not mutate retained operator request.
        return S.ContextLease(context, object(), "2" * 64)

    def run_fixed_programme(self, lease, observation):
        self.observations.append(copy.deepcopy(observation))
        observation["row_ids"][:] = 0
        observation["training_labels"][:] = 0
        self.shared = np.ones((200, len(observation["valid_teacher_indices"])), dtype=np.int8)
        return S.RuntimeOutput(self.shared, "3" * 64)

    def close_context(self, lease):
        self.closed.append(lease.context_id)
        if self.shared is not None:
            self.shared[:] = 0  # Frozen output must already be a defensive copy.
        return "not-a-hash" if self.corrupt_close else "4" * 64


class FullMetadataCensus(unittest.TestCase):
    def test_original_full_grid_has_13824_and_64000_coordinates(self):
        seen, counts = set(), {"glm": 0, "geometry": 0}
        for item in C.full_plan():
            identity = (item["family"], item["id"])
            self.assertNotIn(identity, seen)
            seen.add(identity)
            counts[item["family"]] += 1
        self.assertEqual(counts, {"glm": 13824, "geometry": 64000})
        self.assertEqual(len(seen), 77824)


class StagedControls(unittest.TestCase):
    def setUp(self):
        self.plan = [{"family": "glm", "id": job["id"], "job": job}
                     for job in list(G.job_plan())[:2]]
        geometry = R.geometry_plan()
        for _ in range(2):
            job = next(geometry)
            self.plan.append({"family": "geometry", "id": P.geometry_id(job), "job": job})
        self.stack = []
        for patch in (mock.patch.object(C, "full_plan", lambda: iter(copy.deepcopy(self.plan))),
                      mock.patch.object(C, "EXPECTED_COUNTS", {"glm": 2, "geometry": 2})):
            patch.start()
            self.stack.append(patch)
        base = os.environ.get("STAGED_FIXTURE_ROOT")
        if base:
            Path(base).mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="generated-staged-", dir=base)
        self.root = Path(self.tmp.name).resolve()
        self.retired = 0
        self.serial = 0
        self.protocol = S.make_protocol(method_sha256=SHA, operator_input_sha256="5" * 64,
                                        information_condition="paper_data", runtime_contract_sha256="6" * 64)
        self.phash = S._hash(self.protocol)
        self.common = {"expected_protocol_sha256": self.phash, **CAPS}
        self.original_freeze = C.freeze_submission
        def counted(*args, **kwargs):
            global FREEZE_INVOCATIONS
            FREEZE_INVOCATIONS += 1
            return self.original_freeze(*args, **kwargs)
        patch = mock.patch.object(C, "freeze_submission", counted)
        patch.start()
        self.stack.append(patch)

    def tearDown(self):
        global GENERATED_WRITE_BYTES
        GENERATED_WRITE_BYTES += self.retired + sum(p.stat().st_size for p in self.root.rglob("*")
                                                     if p.is_file() and not p.is_symlink())
        self.tmp.cleanup()
        for patch in reversed(self.stack):
            patch.stop()

    def path(self, label):
        self.serial += 1
        return self.root / (label + str(self.serial))

    def mutate(self, path, raw=None):
        self.retired += path.stat().st_size
        if raw is None:
            path.unlink()
        else:
            path.write_bytes(raw)

    def a(self, runtime=None):
        root = self.path("a")
        runtime = runtime or FakeRuntime()
        calls = []
        def loader(job):
            calls.append(job)
            return reference(job)
        seal = S.collect_stage_a(root, loader, runtime, self.protocol, **self.common)
        return root, seal, runtime, calls

    def gate(self, root, seal):
        path = self.path("gate.json")
        pin = S.create_stage_b_gate(path, root, self.protocol,
                                   expected_stage_a_sha256=seal["complete_sha256"], **self.common)
        return path, pin

    def a_records(self, root, seal):
        verified = C.verify_submission(root, seal["binding"], expected_complete_sha256=seal["complete_sha256"], **CAPS)
        return [{"family": co["family"], "id": co["id"], "candidate": candidate}
                for co, candidate in S._read_candidates(root, seal["binding"], verified, **CAPS)]

    def b_records(self):
        records = []
        for co in self.plan:
            if co["family"] == "glm":
                candidate = {"schema": "population_glm_candidate_v1", "job_id": co["id"], "method_sha256": SHA,
                             "row_ids": np.arange(10, dtype=np.uint8), "unit_ids": np.array([0], dtype=np.uint8),
                             "fold_ids": V.source_fold_ids(10).astype(np.uint8),
                             "alpha_oof_predictions": np.ones((10, 1, 10), dtype=np.float32),
                             "full_predictions": np.ones((10, 1), dtype=np.float32),
                             "selected_alpha_indices": np.array([0], dtype=np.uint8)}
            else:
                public = S.project_stage_a(reference(co["job"]), self.protocol, expected_protocol_sha256=self.phash)
                candidate = {"schema": S.B_SCHEMA, "job_id": co["id"], "method_sha256": SHA,
                             **{k: public[k] for k in S.IDENTITIES}, "joint_covariance": np.eye(23, dtype=np.float32)}
            records.append({"family": co["family"], "id": co["id"], "candidate": candidate})
        return records

    def b(self, gate, pin, records=None):
        root = self.path("b")
        seal = S.freeze_stage_b(root, self.b_records() if records is None else records, gate, self.protocol,
                                expected_gate_sha256=pin["sha256"], **self.common)
        return root, seal

    def test_projection_exact_training_labels_and_defensive_copies(self):
        original = reference(self.plan[-1]["job"])
        public = S.project_stage_a(original, self.protocol, expected_protocol_sha256=self.phash)
        self.assertEqual(set(public), {"schema", "job_id", "method_sha256", "protocol_sha256", "neural_points",
                         *S.IDENTITIES, "training_positions", "test_positions", "training_labels", "balanced_teacher_policy"})
        self.assertEqual(public["training_labels"].shape, (300, 101))
        np.testing.assert_array_equal(public["training_labels"], original["labels"][original["training_positions"]])
        self.assertEqual(public["neural_points"].shape, (500, 19))
        self.assertIn("all_500_labels", public["balanced_teacher_policy"])
        public["neural_points"][:] = 88
        public["training_labels"][:] = 0
        public["row_ids"][:] = 0
        self.assertFalse((original["points"] == 88).any())
        self.assertTrue(np.isin(original["labels"], (-1, 1)).all())
        self.assertEqual(len(np.unique(original["row_ids"])), 500)

    def test_projection_rejects_wrong_label_partition_and_teacher_support(self):
        mutations = (lambda r: r.update(training_positions=np.arange(299)),
                     lambda r: r.update(test_positions=np.arange(200)),
                     lambda r: r.update(valid_teacher_indices=np.arange(100)),
                     lambda r: r.update(points=np.zeros((499, 19))))
        for mutation in mutations:
            ref = reference(self.plan[-1]["job"])
            mutation(ref)
            with self.assertRaises(ValueError):
                S.project_stage_a(ref, self.protocol, expected_protocol_sha256=self.phash)

    def test_unavailable_runtime_refuses_before_loader_or_output(self):
        path = self.path("never")
        loader = mock.Mock()
        with self.assertRaises(ValueError):
            S.collect_stage_a(path, loader, None, self.protocol, **self.common)
        self.assertFalse(path.exists())
        loader.assert_not_called()
        with self.assertRaisesRegex(ValueError, "no independently qualified"):
            S.require_production_qualification({"eligible": True})

    def test_stage_a_preserves_outputs_closes_contexts_and_only_calls_geometry(self):
        root, seal, runtime, calls = self.a()
        self.assertEqual(calls, [co["job"] for co in self.plan if co["family"] == "geometry"])
        self.assertEqual(runtime.closed, ["ctx-1", "ctx-2"])
        self.assertEqual(seal["readout_records"], 2)
        self.assertEqual(seal["glm_nonresults"], 2)
        self.assertEqual(seal["evaluated_scientific_results"], 0)
        self.assertIs(seal["eligible"], False)
        for item in self.a_records(root, seal):
            c = item["candidate"]
            if item["family"] == "glm":
                self.assertEqual(c["schema"], S.NONRESULT_SCHEMA)
                self.assertNotIn("full_predictions", c)
            else:
                self.assertTrue((c["readout_predictions"] == 1).all())
                self.assertEqual(c["runtime_receipt"]["request"]["method_sha256"], SHA)
                self.assertIs(c["isolation_qualified"], False)
        for observation in runtime.observations:
            self.assertNotIn("latents", observation)
            self.assertNotIn("source_svc_predictions", observation)
            self.assertNotIn("labels", observation)
            self.assertEqual(observation["training_labels"].shape[0], 300)

    def test_duplicate_context_and_bad_teardown_retain_incomplete_artifacts(self):
        for runtime in (FakeRuntime(duplicate=True), FakeRuntime(corrupt_close=True)):
            path = self.path("failure")
            with self.assertRaises(ValueError):
                S.collect_stage_a(path, reference, runtime, self.protocol, **self.common)
            self.assertTrue((path / "FAILURE.json").is_file())
            self.assertFalse((path / "COMPLETE.json").exists())
            self.assertGreater(len(runtime.closed), 0)

    def test_wrong_protocol_method_input_condition_or_runtime_pin_refuses(self):
        for key, value in (("method_sha256", "8" * 64), ("operator_input_sha256", "8" * 64),
                           ("information_condition", "paper_data_author_code")):
            changed = copy.deepcopy(self.protocol)
            changed["base_binding"][key] = value
            with self.assertRaises(ValueError):
                S.project_stage_a(reference(self.plan[-1]["job"]), changed, expected_protocol_sha256=self.phash)
        changed = copy.deepcopy(self.protocol)
        changed["eligible"] = True
        with self.assertRaises(ValueError):
            S.project_stage_a(reference(self.plan[-1]["job"]), changed, expected_protocol_sha256=S._hash(changed))

    def test_changed_staged_source_or_loader_invalidates_original_protocol(self):
        for name in ("staged_delivery.py", "dependency_loader.py"):
            pins = S._source_pins()
            pins[name]["sha256"] = "0" * 64
            with mock.patch.object(S, "_source_pins", return_value=pins):
                with self.assertRaises(ValueError):
                    S.project_stage_a(reference(self.plan[-1]["job"]), self.protocol,
                                      expected_protocol_sha256=self.phash)

    def test_gate_requires_external_a_pin_and_is_create_only(self):
        root, seal, _, _ = self.a()
        path = self.path("gate")
        with self.assertRaises(ValueError):
            S.create_stage_b_gate(path, root, self.protocol, expected_stage_a_sha256="0" * 64, **self.common)
        self.assertFalse(path.exists())
        gate, pin = self.gate(root, seal)
        with self.assertRaises(ValueError):
            S.create_stage_b_gate(gate, root, self.protocol, expected_stage_a_sha256=seal["complete_sha256"], **self.common)
        self.assertIs(pin["eligible"], False)

    def test_gate_symlink_and_later_corruption_block_every_b_loader(self):
        root, seal, _, _ = self.a()
        gate, pin = self.gate(root, seal)
        link = self.path("symlink")
        link.symlink_to(gate)
        loader = mock.Mock()
        with self.assertRaises(ValueError):
            next(S.iter_stage_b_inputs(link, self.protocol, loader, expected_gate_sha256=pin["sha256"], **self.common))
        rawpath = root / "records" / "000003" / "arrays.npz"
        raw = rawpath.read_bytes()
        self.mutate(rawpath, raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaises(ValueError):
            next(S.iter_stage_b_inputs(gate, self.protocol, loader, expected_gate_sha256=pin["sha256"], **self.common))
        loader.assert_not_called()

    def test_missing_late_payload_and_wrong_gate_pin_block_b_loader(self):
        root, seal, _, _ = self.a()
        gate, pin = self.gate(root, seal)
        loader = mock.Mock()
        with self.assertRaises(ValueError):
            next(S.iter_stage_b_inputs(gate, self.protocol, loader, expected_gate_sha256="0" * 64, **self.common))
        self.mutate(root / "records" / "000003" / "arrays.npz")
        with self.assertRaises((ValueError, FileNotFoundError)):
            next(S.iter_stage_b_inputs(gate, self.protocol, loader, expected_gate_sha256=pin["sha256"], **self.common))
        loader.assert_not_called()

    def test_b_loader_only_after_full_a_verification_and_original_order(self):
        root, seal, _, _ = self.a()
        gate, pin = self.gate(root, seal)
        calls = []
        def loader(family, job):
            calls.append((family, job))
            return {"full_targets_allowed_only_now": True}
        outputs = list(S.iter_stage_b_inputs(gate, self.protocol, loader, expected_gate_sha256=pin["sha256"], **self.common))
        self.assertEqual(calls, [(co["family"], co["job"]) for co in self.plan])
        self.assertTrue(all(out["eligible"] is False for out in outputs))

    def test_semantic_receipt_forgery_duplicate_context_or_nonresult_rejected(self):
        root, seal, _, _ = self.a()
        mutations = (
            lambda records: records[-1]["candidate"]["runtime_receipt"].update(eligible=True),
            lambda records: records[-1]["candidate"]["runtime_receipt"].update(context_id="ctx-1"),
            lambda records: records[-1]["candidate"]["runtime_receipt"]["request"].update(method_sha256="9" * 64),
            lambda records: records[-1]["candidate"]["runtime_receipt"].update(unrecognized=True),
            lambda records: records[0]["candidate"].update(full_predictions=np.ones((1, 1))),
        )
        for mutation in mutations:
            records = self.a_records(root, seal)
            mutation(records)
            forged = self.path("forged")
            pin = C.freeze_submission(forged, records, seal["binding"], **CAPS)
            gate = self.path("never-gate")
            with self.assertRaises(ValueError):
                S.create_stage_b_gate(gate, forged, self.protocol, expected_stage_a_sha256=pin["complete_sha256"], **self.common)
            self.assertFalse(gate.exists())

    def test_b_readout_replacement_placeholder_and_wrong_order_rejected(self):
        root, seal, _, _ = self.a()
        gate, pin = self.gate(root, seal)
        cases = []
        records = self.b_records()
        records[-1]["candidate"]["readout_predictions"] = np.zeros((200, 101), dtype=np.int8)
        cases.append(records)
        records = self.b_records()
        records[0]["candidate"] = S._nonresult(self.plan[0], self.protocol)
        cases.append(records)
        cases.append(list(reversed(self.b_records())))
        for records in cases:
            with self.assertRaises(ValueError):
                self.b(gate, pin, records)

    def test_b_missing_extra_duplicate_coordinates_rejected(self):
        root, seal, _, _ = self.a()
        gate, pin = self.gate(root, seal)
        records = self.b_records()
        for changed in (records[:-1], records + records[-1:], records[:2] + [records[2], records[2]]):
            with self.assertRaises(ValueError):
                self.b(gate, pin, changed)

    def test_join_original_candidate_schemas_and_exact_pinned_a_readouts(self):
        aroot, aseal, _, _ = self.a()
        gate, pin = self.gate(aroot, aseal)
        broot, bseal = self.b(gate, pin)
        root = self.path("joined")
        joined = S.join_stages(root, broot, gate, self.protocol,
                               expected_gate_sha256=pin["sha256"], expected_stage_b_sha256=bseal["complete_sha256"], **self.common)
        final = C.verify_submission(joined["submission_root"], joined["binding"],
                                    expected_complete_sha256=joined["complete_sha256"], **CAPS)
        for co, candidate in S._read_candidates(joined["submission_root"], joined["binding"], final, **CAPS):
            self.assertEqual(set(candidate), GB.FIELDS if co["family"] == "geometry" else GLB.CANDIDATE_KEYS)
            if co["family"] == "geometry":
                self.assertEqual(candidate["schema"], GB.SCHEMA)
                self.assertTrue((candidate["readout_predictions"] == 1).all())
        self.assertIs(joined["eligible"], False)
        receipt = C._json((root / "JOIN.json").read_bytes())
        self.assertEqual(receipt["stage_a_sha256"], aseal["complete_sha256"])
        self.assertEqual(receipt["stage_b_sha256"], bseal["complete_sha256"])
        self.assertIs(receipt["isolation_qualified"], False)
        with self.assertRaises(ValueError):
            S.join_stages(root, broot, gate, self.protocol, expected_gate_sha256=pin["sha256"],
                          expected_stage_b_sha256=bseal["complete_sha256"], **self.common)

    def test_join_rejects_different_stage_a_identity_and_late_b_corruption(self):
        aroot, aseal, _, _ = self.a()
        gate, pin = self.gate(aroot, aseal)
        records = self.b_records()
        records[-1]["candidate"]["training_row_ids"] = records[-1]["candidate"]["training_row_ids"][::-1].copy()
        broot, bseal = self.b(gate, pin, records)
        joined = self.path("mismatch")
        with self.assertRaises(ValueError):
            S.join_stages(joined, broot, gate, self.protocol, expected_gate_sha256=pin["sha256"],
                          expected_stage_b_sha256=bseal["complete_sha256"], **self.common)
        self.assertTrue((joined / "submission" / "FAILURE.json").exists())
        rawpath = broot / "records" / "000003" / "arrays.npz"
        raw = rawpath.read_bytes()
        self.mutate(rawpath, raw + b"tampered")
        untouched = self.path("untouched")
        with self.assertRaises(ValueError):
            S.join_stages(untouched, broot, gate, self.protocol, expected_gate_sha256=pin["sha256"],
                          expected_stage_b_sha256=bseal["complete_sha256"], **self.common)
        self.assertFalse(untouched.exists())


@atexit.register
def print_write_accounting():
    print("STAGED_GENERATED_WRITE_BYTES=" + str(GENERATED_WRITE_BYTES))
    print("STAGED_FREEZE_INVOCATIONS=" + str(FREEZE_INVOCATIONS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
