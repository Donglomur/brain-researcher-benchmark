"""Generated full-roster composition, no real source data, model or transport."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import contract
import prepare
import run
import transport
import storage
from storage import decoded, encoded, pin, read, write, directory, seal_public_directory, StorageError


def profile():
    return {"schema": "meg-runtime-campaign/v1", "campaign_id": "generated-campaign",
        "outcome": "improvement", "image": "sha256:" + "1" * 64,
        "docker_binary": "/generated/docker", "docker_socket": "/generated/docker.sock",
        "image_inventory_sha256": "2" * 64, "boundary_audit": {"bytes": 1, "sha256": "3" * 64},
        "role_boundary_verified": True, "phase_resources": {
            "setup_seconds": 1, "producer_seconds": 1, "capture_seconds": 1, "cleanup_seconds": 1,
            "memory_bytes": 134217728, "cpu_nanos": 1000000000, "pids": 64,
            "scratch_bytes": 4096, "max_files": 2, "max_directories": 1,
            "max_file_bytes": 1048576, "max_output_bytes": 2097152, "manifest_bytes": 4096,
            "max_cli_calls": 96, "max_cli_bytes": 2097152, "inventory_bytes": 65536,
            "source_read_bytes": 33554432, "host_write_bytes": 4194304},
        "total_seconds": 120, "transport_read_bytes": 1024**3,
        "transport_write_bytes": 128 * 1024**2, "coordinator_read_bytes": 32 * 1024**2,
        "coordinator_write_bytes": 8 * 1024**2,
        "delivery_read_bytes": 64 * 1024**2, "delivery_write_bytes": 65536, "delivery_seconds": 10,
        "paper_pin": CampaignTests.paper_pin,
        "paired_source_manifest": pin((HERE / "SOURCE_MANIFEST.json").read_bytes())}


class GeneratedTransport:
    calls = []
    missing_last = False
    constructions = 0

    def __init__(self, **kwargs):
        type(self).constructions += 1
        self.kwargs = kwargs
        self.calls = []
        type(self).calls = self.calls

    def execute_fold(self, role, fold, mounts, exposure_pin, resources, phase_deadline, journal):
        assert ("/author" in mounts) == (role == "B")
        assert "/input/WINDOWS.npy" in mounts and "/input/CONTEXT.json" in mounts
        assert all("PRIVATE_PANEL" not in d["path"] for d in mounts.values())
        assert phase_deadline == self.kwargs["original_deadline"]
        context = decoded(read(mounts["/input/CONTEXT.json"]["path"], 2 * 1024**2))
        probabilities = {i: 0.5 for i in context["queries"]}
        if self.missing_last and role == "B" and fold == 9:
            probabilities.pop(next(iter(probabilities)))
        response = {"schema": contract.RESPONSE_SCHEMA, "context_sha256": context["context_sha256"],
                    "probabilities": probabilities, "source_feature_values": None}
        body = encoded(response)
        phase = transport.phase_id(self.kwargs["campaign_id"], role, fold)
        journal("OWNERSHIP", {"generated": True, "phase_id": phase})
        self.calls.append((role, fold, context["context_sha256"]))
        return {"phase_id": phase, "result_bytes": body, "result_pin": pin(body),
                "request_pin": pin(phase.encode()), "receipt_pin": pin((phase + "generated-only").encode())}

    def complete_for_grading(self):
        assert {(r, f) for r, f, _ in self.calls} == {(r, f) for r in ("A", "B") for f in range(10)}
        return {"scope": "generated_only", "accepted_phases": 20}


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The runner authenticates every paired-source member. Generated data
        # must live outside that immutable source tree.
        cls.temp = tempfile.TemporaryDirectory(prefix="meg-generated-", dir=HERE.parent / "delivery-verifier-v1/tests")
        cls.root = Path(cls.temp.name)
        cls.prepared = directory(cls.root / "prepared")
        cls.programmes = prepare.freeze_programmes({"A": HERE / "fixed_control.py", "B": HERE / "fixed_control.py"}, cls.prepared)
        cls.records, cls.matrices = [], {}
        cls.folds = {person: i % 10 for i, person in enumerate(contract.published_participants())}
        base = np.arange(4000, dtype="<f8").reshape(4, 1000)
        for person in contract.published_participants():
            for category in ("false", "face", "letter", "object"):
                rid = contract.source_observation_id(person, category)
                matrix = base + len(cls.records)
                cls.records.append({"source_id": rid, "participant": person, "category": category,
                    "tensor_sha256": hashlib.sha256(matrix.tobytes()).hexdigest()})
                cls.matrices[rid] = matrix
        old = os.umask(0o077)
        try:
            cls.panel = prepare.write_panel(cls.prepared, cls.records, cls.matrices,
                prepare.PREPARED_BINDING, cls.folds, key=b"generated-private-key-do-not-use!"[:32])
        finally:
            os.umask(old)
        cls.document = {"schema": "meg-prepared-paired-campaign/v1", "task_id": prepare.TASK,
            **cls.panel, "programmes": cls.programmes,
            "fold_evidence": "Generated fixture group map; historical identity unqualified",
            "historical_folds_authenticated": False, "source_revision": prepare.AUTHOR_REVISION,
            "freeze_order": "both programmes frozen before any original windows or fold labels were prepared",
            "preparation_only": True, "native_phases": 0, "scientific_results": False}
        for name, purpose, leaf in (("paper", "paper", "PAPER.bin"), ("contract", "contract", "PARTICIPANT.md")):
            directory_path = directory(cls.prepared / name)
            body = ("GENERATED ONLY " + name).encode() if name == "paper" else (HERE / "PARTICIPANT.md").read_bytes()
            leaf_pin = write(directory_path / leaf, body, 65536, public=True)
            seal_public_directory(directory_path)
            cls.document[name] = prepare.tree_mount(directory_path, purpose, {leaf: leaf_pin})
            if name == "paper": cls.paper_pin = leaf_pin
        authors = directory(cls.root / "fixture-author-source")
        cls.author_hashes = {}
        for relative in prepare.AUTHOR_FILES:
            target = authors / relative; target.parent.mkdir(parents=True, exist_ok=True)
            body = ("GENERATED AUTHOR ONLY " + relative).encode()
            target.write_bytes(body); cls.author_hashes[relative] = pin(body)["sha256"]
        with mock.patch.object(prepare, "AUTHOR_FILES", cls.author_hashes):
            cls.document["author"] = prepare.author_capsule(authors, cls.prepared / "author")
        cls.prepared_pin = write(cls.prepared / "PREPARED.json", encoded(cls.document), 2 * 1024**2)

    @classmethod
    def tearDownClass(cls):
        # readonly public directories need owner traversal/write before fixture
        # removal. Deleted bytes remain charged to the finite generated budget.
        for item in cls.root.rglob("*"):
            if item.is_dir():
                item.chmod(0o700)
        cls.temp.cleanup()

    def setUp(self):
        GeneratedTransport.missing_last = False
        GeneratedTransport.constructions = 0
        GeneratedTransport.calls = []

    def test_complete_twenty_phases_then_original_private_score(self):
        opened = []
        real_read = run.read
        def observed_read(path, cap, expected=None):
            if Path(path).name == "PRIVATE_PANEL.json":
                opened.append(len(GeneratedTransport.calls))
            return real_read(path, cap, expected)
        with mock.patch.object(run, "read", side_effect=observed_read):
            receipt = run.execute(self.prepared, self.prepared_pin, profile(), self.root / "complete",
                _generated=True, _transport_factory=GeneratedTransport, _generated_author_hashes=self.author_hashes)
        self.assertEqual(opened, [20])
        self.assertEqual(len(receipt["phases"]), 20)
        self.assertEqual(receipt["scope"], "generated_coordinator_simulation")
        self.assertFalse(receipt["scientific_qualification"])
        self.assertEqual(GeneratedTransport.constructions, 1)
        self.assertTrue(receipt["delivery_admission"]["fresh_successful_call_observed"])
        self.assertEqual(receipt["delivery_admission"]["audit_private_panel_reads"], 1)
        self.assertEqual(receipt["delivery_admission"]["scope"], "generated_delivery_control")
        score = decoded(read(self.root / "complete/SCORE.json", 2 * 1024**2))
        self.assertEqual(score["scores"]["A"]["accuracy"], 0.5)
        self.assertEqual(score["scores"]["A"]["accuracy_SD"], 0.0)
        self.assertEqual(score["scores"]["A"]["fold_observations"], [20] * 4 + [18] * 6)
        self.assertEqual(score["B_minus_A_accuracy"], 0)
        self.assertIsNone(score["paper_improvement_success"])
        for fold in range(10):
            self.assertEqual(GeneratedTransport.calls[2 * fold][2], GeneratedTransport.calls[2 * fold + 1][2])

    def test_final_public_prediction_failure_never_opens_targets(self):
        GeneratedTransport.missing_last = True
        opened = []
        real_read = run.read
        def observed_read(path, cap, expected=None):
            if Path(path).name == "PRIVATE_PANEL.json":
                opened.append(str(path))
            return real_read(path, cap, expected)
        out = self.root / "late-failure"
        with mock.patch.object(run, "read", side_effect=observed_read), self.assertRaises(ValueError):
            run.execute(self.prepared, self.prepared_pin, profile(), out,
                        _generated=True, _transport_factory=GeneratedTransport, _generated_author_hashes=self.author_hashes)
        self.assertFalse(opened)
        self.assertFalse((out / "SCORE.json").exists())
        self.assertFalse((out / "BATCH.json").exists())
        failure = decoded(read(out / "FAILURE.json", 32768))
        self.assertEqual(failure["accepted_phase_count"], 19)
        self.assertFalse(failure["owned_resource_absence_inferred"])

    def test_bank_preserves_every_original_generated_matrix_and_private_modes(self):
        panel = decoded(read(self.prepared / "PRIVATE_PANEL.json", 2 * 1024**2))
        bank = np.load(self.prepared / "data/WINDOWS.npy", allow_pickle=False)
        join = {r["id"]: sid for sid, r in contract.private_source_join(panel).items()}
        self.assertEqual(bank.shape, (376, 4, 1000))
        for index, row in enumerate(contract.ordered_public_windows(panel)):
            self.assertTrue(np.array_equal(bank[index], self.matrices[join[row["id"]]]))
        self.assertEqual(stat.S_IMODE((self.prepared / "PRIVATE_PANEL.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.prepared / "data/WINDOWS.npy").stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(self.prepared.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.prepared / "program-A").stat().st_mode), 0o555)
        text = (self.prepared / "contexts/fold-00/CONTEXT.json").read_text()
        self.assertFalse(any(r["source_id"] in text or r["participant"] in text for r in self.records))

    def test_existing_output_and_native_mac_are_refused_before_execution(self):
        with self.assertRaises(ValueError):
            run.execute(self.prepared, self.prepared_pin, profile(), self.prepared,
                        _generated=True, _transport_factory=GeneratedTransport, _generated_author_hashes=self.author_hashes)
        with mock.patch.object(run.platform, "system", return_value="Darwin"), self.assertRaises(ValueError):
            run.execute(self.prepared, self.prepared_pin, profile(), self.root / "not-linux")
        self.assertFalse((self.root / "not-linux").exists())

    def test_runtime_and_external_prepared_pin_fail_closed(self):
        for field, value in (("total_seconds", 80), ("transport_read_bytes", 20 * 33554432),
                             ("role_boundary_verified", False), ("coordinator_read_bytes", True)):
            changed = profile(); changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                run.validate_runtime(changed)
        wrong = dict(self.prepared_pin, sha256="0" * 64)
        with self.assertRaises(ValueError):
            run.execute(self.prepared, wrong, profile(), self.root / "wrong-pin",
                        _generated=True, _transport_factory=GeneratedTransport, _generated_author_hashes=self.author_hashes)

    def test_source_programme_freeze_happens_before_window_loader(self):
        root = self.root / "freeze-order"
        paper = self.root / "generated-paper"; write(paper, b"generated paper", 4096)
        authors = directory(self.root / "generated-authors")
        write(authors / "example.py", b"# generated code only\n", 4096)
        folds = self.root / "generated-folds.json"
        write(folds, encoded({"folds": self.folds, "evidence": "fictional generated fold declaration"}), 131072)
        seen = []
        def source_loader(_):
            frozen = decoded(read(root / "PROGRAMMES_FROZEN.json", 32768))
            self.assertEqual(set(frozen), {"A", "B"})
            seen.append("both_programmes_closed_before_input")
            return self.records, self.matrices, {"bytes": 17, "sha256": "4" * 64}
        with mock.patch.object(prepare, "AUTHOR_FILES", {"example.py": pin(b"# generated code only\n")["sha256"]}), \
             mock.patch.object(prepare, "load_original_windows", side_effect=source_loader), \
             mock.patch.object(prepare, "write_panel", return_value={"panel_sha256": "5" * 64, "rows": 376, "query_rows": 188}):
            result = prepare.prepare("/generated-only-not-opened", folds, HERE / "fixed_control.py", HERE / "fixed_control.py",
                paper, pin(b"generated paper"), authors, root)
        self.assertEqual(seen, ["both_programmes_closed_before_input"])
        self.assertTrue(result["preparation_only"])
        self.assertEqual(result["native_phases"], 0)

    def test_final_receipt_crossing_deadline_never_persists_completion_claim(self):
        clock = mock.Mock(return_value=0.0)
        real_write = run.write
        def cross_deadline(path, body, cap):
            result = real_write(path, body, cap)
            if Path(path).name == "BATCH.json":
                clock.return_value = 121.0
            return result
        out = self.root / "publication-deadline"
        with mock.patch.object(run, "write", side_effect=cross_deadline), self.assertRaises(ValueError):
            run.execute(self.prepared, self.prepared_pin, profile(), out, _generated=True,
                        _transport_factory=GeneratedTransport, _generated_author_hashes=self.author_hashes, clock=clock)
        retained = decoded(read(out / "BATCH.json", 2 * 1024**2))
        self.assertEqual(retained["status"], "provisional")
        self.assertTrue(retained["completion_requires_external_successful_exit_and_deadline_observation"])
        self.assertFalse((out / "FAILURE.json").exists())

    def test_wrong_extent_is_rejected_before_payload_read(self):
        leaf = self.root / "wrong-extent"
        write(leaf, b"a" * 128, 4096)
        budget = run.CampaignIO(2, 1, 10, lambda: 0)
        with mock.patch.object(storage.os, "fdopen") as payload_reader, self.assertRaises(ValueError):
            budget.read(leaf, pin(b"a"), 4096)
        payload_reader.assert_not_called()
        self.assertEqual(budget.read_reserved, 2)

    def rejected_before_transport(self, name, *, prepared_pin=None, runtime=None, error_pattern=".", **kwargs):
        out = self.root / name
        with self.assertRaisesRegex(ValueError, error_pattern):
            run.execute(self.prepared, prepared_pin or self.prepared_pin, runtime or profile(), out,
                _generated=True, _transport_factory=GeneratedTransport,
                _generated_author_hashes=self.author_hashes, **kwargs)
        self.assertEqual(GeneratedTransport.constructions, 0)
        self.assertEqual(GeneratedTransport.calls, [])
        self.assertFalse((out / "SCORE.json").exists())
        self.assertFalse((out / "BATCH.json").exists())
        if (out / "FAILURE.json").exists():
            failure = decoded((out / "FAILURE.json").read_bytes())
            self.assertFalse(failure["delivery_admitted"])
            self.assertFalse(failure["transport_construction_attempted"])
            self.assertEqual(failure["private_panel_reads"], 0)

    def test_altered_programme_and_author_capsules_refuse_before_constructor(self):
        for index, relative in enumerate(("program-A/submission.py", "author/requirements.txt")):
            path = self.prepared / relative; before = path.read_bytes()
            path.chmod(0o600); path.write_bytes(before + b"# altered\n"); path.chmod(0o444)
            try:
                with self.subTest(path=relative): self.rejected_before_transport("capsule-reject-" + str(index))
            finally:
                path.chmod(0o600); path.write_bytes(before); path.chmod(0o444)

    def test_rehashed_bank_refuses_before_constructor(self):
        path = self.prepared / "data/WINDOWS.npy"; original = path.read_bytes()
        start = 10 + struct.unpack("<H", original[8:10])[0]
        before_document = (self.prepared / "PREPARED.json").read_bytes()
        try:
            path.chmod(0o600)
            with path.open("r+b") as handle: handle.seek(start); handle.write(struct.pack("<d", 12345.0))
            path.chmod(0o444)
            changed = decoded(before_document); changed["data"]["files"]["WINDOWS.npy"] = pin(path.read_bytes())
            body = encoded(changed); (self.prepared / "PREPARED.json").write_bytes(body)
            self.rejected_before_transport("rehashed-bank", prepared_pin=pin(body), error_pattern="anonymous row/source tensor mismatch")
        finally:
            path.chmod(0o600)
            with path.open("r+b") as handle: handle.seek(start); handle.write(original[start:start + 8])
            path.chmod(0o444); (self.prepared / "PREPARED.json").write_bytes(before_document)

    def test_rehashed_private_semantic_join_refuses_before_constructor(self):
        relatives = ["PREPARED.json", "PRIVATE_PANEL.json", *(f"contexts/fold-{f:02d}/CONTEXT.json" for f in range(10))]
        saved = {name: (self.prepared / name).read_bytes() for name in relatives}
        try:
            panel = decoded(saved["PRIVATE_PANEL.json"])
            person = contract.published_participants()[0]
            selected = [r for r in panel["private_records"] if r["participant"] == person and r["category"] in ("face", "object")]
            selected[0]["category"], selected[1]["category"] = selected[1]["category"], selected[0]["category"]
            for row in selected: row["source_id"] = contract.source_observation_id(person, row["category"])
            panel["panel_sha256"] = contract.digest({k: v for k, v in panel.items() if k != "panel_sha256"})
            contract._checked_panel(panel)  # valid structure; semantic labels now disagree
            panel_body = encoded(panel); (self.prepared / "PRIVATE_PANEL.json").write_bytes(panel_body)
            doc = decoded(saved["PREPARED.json"]); doc["private_panel"] = pin(panel_body); doc["panel_sha256"] = panel["panel_sha256"]
            for fold in range(10):
                relative = f"contexts/fold-{fold:02d}/CONTEXT.json"; context = decoded(saved[relative])
                context["panel_sha256"] = panel["panel_sha256"]
                context["context_sha256"] = contract.digest({k: v for k, v in context.items() if k != "context_sha256"})
                body = encoded(context); path = self.prepared / relative
                path.chmod(0o600); path.write_bytes(body); path.chmod(0o444)
                doc["contexts"][str(fold)]["context_sha256"] = context["context_sha256"]
                doc["contexts"][str(fold)]["mount"]["files"]["CONTEXT.json"] = pin(body)
            body = encoded(doc); (self.prepared / "PREPARED.json").write_bytes(body)
            self.rejected_before_transport("private-semantic-reject", prepared_pin=pin(body), error_pattern="context labels, held queries")
        finally:
            for name, body in saved.items():
                path = self.prepared / name; path.chmod(0o600); path.write_bytes(body)
                if name.startswith("contexts/"): path.chmod(0o444)

    def test_external_selection_and_generated_mode_cannot_skip_admission(self):
        changed = profile(); changed["paper_pin"] = dict(self.paper_pin, sha256="0" * 64)
        self.rejected_before_transport("wrong-independent-paper", runtime=changed)
        changed = profile(); del changed["paired_source_manifest"]
        self.rejected_before_transport("missing-source-selection", runtime=changed)
        with self.assertRaisesRegex(ValueError, "fictional author hashes"):
            run.execute(self.prepared, self.prepared_pin, profile(), self.root / "production-mode-promotion",
                _generated_author_hashes=self.author_hashes)
        self.assertEqual(GeneratedTransport.constructions, 0)
        self.assertFalse((self.root / "production-mode-promotion").exists())

    def test_gate_publication_deadline_prevents_all_participant_actions(self):
        clock = mock.Mock(return_value=0.0)
        original_fsync = os.fsync
        def cross_original_deadline(fd):
            original_fsync(fd); clock.return_value = 121.0
        with mock.patch.object(os, "fsync", side_effect=cross_original_deadline):
            self.rejected_before_transport("gate-publication-expiry", clock=clock)
        report = decoded((self.root / "gate-publication-expiry/admission/DELIVERY.json").read_bytes())
        self.assertEqual(report["status"], "provisional_structural_check")


if __name__ == "__main__":
    unittest.main()
