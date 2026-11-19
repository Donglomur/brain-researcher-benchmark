"""Focused generated controls for the changed preparation/audit/runner path."""
import copy
import hashlib
import os
from pathlib import Path
import struct
import unittest
from unittest import mock

import contract as raw_contract
import generic_contract as contract
import generic_prepare as prepare
import run
import storage
import transport
from generic_fixture import fixture
from storage import decoded, encoded, pin


class GeneratedTransport:
    calls = []
    data_pin_by_role = {}
    selected = None
    closed = False

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).calls = []
        type(self).data_pin_by_role = {}
        type(self).closed = False

    def execute_fold(self, role, fold, mounts, exposure_pin, resources, phase_deadline, journal):
        assert ("/author" in mounts) == (role == "B")
        assert "/input/FEATURES.npy" in mounts and "/input/WINDOWS.npy" not in mounts
        assert not any(any(token in desc["path"] for token in ("PRIVATE", "REFERENCE", "FROZEN_FOLDS", "SOURCE_QC")) for desc in mounts.values())
        assert phase_deadline == self.kwargs["original_deadline"]
        context = decoded(Path(mounts["/input/CONTEXT.json"]["path"]).read_bytes())
        panel = type(self).selected["panel"]
        source = {r["id"]: r["source_id"] for r in panel["private_records"]}
        probabilities = type(self).selected["arms"][role]["probabilities_object"]
        body = encoded({"schema": contract.RESPONSE_SCHEMA, "input_mode": contract.MODE,
            "context_sha256": context["context_sha256"],
            "probabilities": {i: probabilities[source[i]] for i in context["queries"]}})
        phase = transport.phase_id(self.kwargs["campaign_id"], role, fold)
        journal("OWNERSHIP", {"generated": True, "phase_id": phase})
        type(self).calls.append((role, fold, context["context_sha256"]))
        type(self).data_pin_by_role[role] = mounts["/input/FEATURES.npy"]["files"]
        return {"phase_id": phase, "result_bytes": body, "result_pin": pin(body),
                "request_pin": pin(phase.encode()), "receipt_pin": pin((phase + "generated").encode())}

    def complete_for_grading(self):
        assert len(type(self).calls) == 20
        type(self).closed = True
        return {"scope": "generated_only", "accepted_phases": 20}


class GenericIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixture()
        cls.root = Path(os.environ["MEG_CONTROL_OUTPUT"])
        cls.root.mkdir(mode=0o700)
        inputs = cls.root / "inputs"; inputs.mkdir(mode=0o700)
        programmes = []
        for role in ("A", "B"):
            path = inputs / (role + ".py"); path.write_text("# generated programme; not executed\n"); programmes.append(path)
        paper = inputs / "paper.bin"; paper.write_bytes(b"GENERATED PAPER ONLY\n")
        cls.paper_pin = pin(paper.read_bytes())
        authors = inputs / "author"; authors.mkdir(mode=0o700)
        cls.author_hashes = {}
        for relative in prepare.raw_prepare.AUTHOR_FILES:
            path = authors / relative; path.parent.mkdir(parents=True, exist_ok=True)
            body = ("# GENERATED AUTHOR ONLY: " + relative).encode(); path.write_bytes(body)
            cls.author_hashes[relative] = pin(body)["sha256"]
        cls.prepared = cls.root / "prepared"
        def generated_sources(*paths):
            frozen = decoded((cls.prepared / "PROGRAMMES_FROZEN.json").read_bytes())
            assert set(frozen) == {"A", "B"}
            return (cls.f["records"], cls.f["folds"], cls.f["binding"], encoded(cls.f["reference"]),
                    encoded(cls.f["ledger"]), {"schema": "generated-source-qc", "other_category_values": False})
        # Only source acquisition is replaced. Actual scalar packing, opaque
        # context construction, programme freezing, capsule writing and sealing run.
        with mock.patch.object(prepare, "load_sources", side_effect=generated_sources), \
             mock.patch.object(prepare.raw_prepare, "AUTHOR_FILES", cls.author_hashes):
            cls.document = prepare.prepare("GENERATED", "GENERATED", "GENERATED", "GENERATED",
                *programmes, paper, cls.paper_pin, authors, cls.prepared)
        cls.prepared_pin = pin((cls.prepared / "PREPARED.json").read_bytes())
        cls.f["panel"] = decoded((cls.prepared / "PRIVATE_PANEL.json").read_bytes())
        GeneratedTransport.selected = cls.f

    def profile(self):
        return {"schema": "meg-runtime-campaign/v2", "input_mode": contract.MODE,
            "campaign_id": "generated-generic-mode", "outcome": "reproduction",
            "image": "sha256:" + "1" * 64, "docker_binary": "/generated/docker",
            "docker_socket": "/generated/docker.sock", "image_inventory_sha256": "2" * 64,
            "boundary_audit": {"bytes": 1, "sha256": "3" * 64}, "role_boundary_verified": True,
            "phase_resources": {"setup_seconds": 1, "producer_seconds": 1, "capture_seconds": 1,
                "cleanup_seconds": 1, "memory_bytes": 134217728, "cpu_nanos": 1000000000,
                "pids": 64, "scratch_bytes": 4096, "max_files": 2, "max_directories": 1,
                "max_file_bytes": 1048576, "max_output_bytes": 2097152, "manifest_bytes": 4096,
                "max_cli_calls": 96, "max_cli_bytes": 2097152, "inventory_bytes": 65536,
                "source_read_bytes": 1048576, "host_write_bytes": 1048576},
            "total_seconds": 120, "transport_read_bytes": 33554432, "transport_write_bytes": 33554432,
            "coordinator_read_bytes": 8388608, "coordinator_write_bytes": 1048576,
            "delivery_read_bytes": 4194304, "delivery_write_bytes": 16384, "delivery_seconds": 10,
            "paper_pin": self.paper_pin, "paired_source_manifest": pin((Path(run.__file__).parent / "SOURCE_MANIFEST.json").read_bytes()),
            "reference_result": self.document["reference_result"], "reference_folds": self.document["reference_folds"]}

    def test_twenty_phases_and_private_reference_barrier(self):
        opened = []
        real_read = run.read
        def observed(path, cap, expected=None):
            if Path(path).name in ("PRIVATE_PANEL.json", "REFERENCE_RESULT.json", "FROZEN_FOLDS.json", "REFERENCE_BINDING.json"):
                opened.append((Path(path).name, len(GeneratedTransport.calls), GeneratedTransport.closed))
            return real_read(path, cap, expected)
        with mock.patch.object(run, "read", side_effect=observed):
            receipt = run.execute(self.prepared, self.prepared_pin, self.profile(), self.root / "campaign",
                _generated=True, _transport_factory=GeneratedTransport, _generated_author_hashes=self.author_hashes)
        self.assertEqual(len(receipt["phases"]), 20)
        self.assertEqual({x[0] for x in opened}, {"PRIVATE_PANEL.json", "REFERENCE_RESULT.json", "FROZEN_FOLDS.json", "REFERENCE_BINDING.json"})
        self.assertTrue(all(count == 20 and closed for _, count, closed in opened))
        self.assertEqual(GeneratedTransport.data_pin_by_role["A"], GeneratedTransport.data_pin_by_role["B"])
        self.assertTrue(all(GeneratedTransport.calls[2*f][2] == GeneratedTransport.calls[2*f+1][2] for f in range(10)))
        self.assertEqual(receipt["scope"], "generated_coordinator_simulation")
        self.assertFalse(receipt["scientific_qualification"])
        score = decoded((self.root / "campaign/SCORE.json").read_bytes())
        self.assertEqual(score["input_mode"], contract.MODE)
        audit = decoded((self.root / "campaign/admission/DELIVERY.json").read_bytes())
        self.assertEqual(audit["reference_body_reads"], 0)
        self.assertTrue(audit["reference_authentication_deferred_until_grading"])

    def test_scalar_geometry_and_private_identity_mapping(self):
        body = (self.prepared / "data/FEATURES.npy").read_bytes()
        header = struct.unpack("<H", body[8:10])[0]
        values = [x[0] for x in struct.iter_unpack("<d", body[10+header:])]
        self.assertEqual(len(values), 188)
        panel = self.f["panel"]
        rows = contract.ordered_public_rows(panel)
        self.assertEqual([hashlib.sha256(struct.pack("<d", v)).hexdigest() for v in values], [r["scalar_sha256"] for r in rows])
        context = contract.public_context(panel, 0)
        text = encoded(context).decode()
        self.assertFalse(any(r["source_id"] in text or r["row_key"] in text or r["participant"] in text for r in panel["private_records"]))
        for record in panel["private_records"]:
            if panel["participant_folds"][record["participant"]] == 0:
                self.assertNotIn(record["id"], {r["id"] for r in context["training"]})

    def test_raw_mode_schema_and_cross_mode_rejection(self):
        raw = self.profile()
        for key in ("input_mode", "reference_result", "reference_folds"): raw.pop(key)
        raw["schema"] = "meg-runtime-campaign/v1"
        self.assertIs(run.validate_runtime(raw), raw)
        wrong = self.profile(); wrong["input_mode"] = "raw_windows_v1"
        with self.assertRaises(ValueError): run.validate_runtime(wrong)
        with self.assertRaises(ValueError): raw_contract._checked_context(contract.public_context(self.f["panel"], 0))
        context = contract.public_context(self.f["panel"], 0)
        response = {"schema": contract.RESPONSE_SCHEMA, "input_mode": contract.MODE,
                    "context_sha256": context["context_sha256"], "probabilities": {i: 0.5 for i in context["queries"]}}
        response["source_feature_values"] = None
        with self.assertRaises(ValueError): contract.validate_prediction(response, context, "reproduction")

    def test_frozen_plan_and_reference_mapping_reject_mismatches(self):
        contract.validate_frozen_folds(self.f["ledger"], self.f["panel"])
        changed = copy.deepcopy(self.f["ledger"])
        changed["plans"][0]["folds"][0]["test_row_keys"][0] = "wrong"
        with self.assertRaises(ValueError): contract.validate_frozen_folds(changed, self.f["panel"])
        changed = copy.deepcopy(self.f["reference"])
        changed["results"][0]["predictions"][0]["fold"] = 9
        with self.assertRaises(ValueError): prepare.validate_reference(self.f["records"], changed, self.f["ledger"])
