"""Full-geometry generated delivery controls; no native programme execution."""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); import verify
sys.path.insert(0, str(HERE.parent / "paired-program-v1"))
import contract
import prepare
from storage import decoded, encoded, pin


class Delivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="generated-delivery-", dir=HERE / "tests")
        cls.root = Path(cls.temp.name); cls.root.chmod(0o700)
        cls.prepared = cls.root / "prepared"
        source = cls.root / "never_execute.py"
        source.write_text("raise AssertionError('submission must never execute during verification')\n")
        paper = cls.root / "generated-paper"; paper.write_bytes(b"GENERATED PAPER ONLY")
        cls.paper_pin = pin(paper.read_bytes())
        author = cls.root / "generated-author"; author.mkdir()
        cls.author_hashes = {}
        for relative in prepare.AUTHOR_FILES:
            body = ("GENERATED AUTHOR SOURCE ONLY " + relative).encode()
            leaf = author / relative; leaf.parent.mkdir(parents=True, exist_ok=True); leaf.write_bytes(body)
            cls.author_hashes[relative] = pin(body)["sha256"]
        folds = cls.root / "folds.json"
        folds.write_bytes(encoded({"folds": {p: i % 10 for i, p in enumerate(contract.published_participants())},
                                   "evidence": "Generated fixture grouping; no historical claim"}))
        records, matrices = [], {}
        base = np.arange(4000, dtype="<f8").reshape(4, 1000)
        for person in contract.published_participants():
            for category in contract.CATEGORIES:
                rid = contract.source_observation_id(person, category); matrix = base + len(records)
                records.append({"source_id": rid, "participant": person, "category": category,
                                "tensor_sha256": hashlib.sha256(matrix.tobytes()).hexdigest()})
                matrices[rid] = matrix
        with mock.patch.object(prepare, "AUTHOR_FILES", cls.author_hashes), \
             mock.patch.object(prepare, "load_original_windows", return_value=(records, matrices, prepare.PREPARED_BINDING)):
            prepare.prepare("/generated-never-opened", folds, source, source, paper, cls.paper_pin, author, cls.prepared)
        cls.original = (cls.prepared / "PREPARED.json").read_bytes()
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        for path in cls.root.rglob("*"):
            if path.is_dir(): path.chmod(0o700)
        cls.temp.cleanup()

    def output(self):
        type(self).counter += 1
        return self.root / ("report-%03d.json" % self.counter)

    def check(self, *, output=None, **kwargs):
        args = {"read_limit": 64 * 1024**2, "write_limit": 65536, "seconds": 60,
                "paired_source_manifest": pin((verify.PAIRED / "SOURCE_MANIFEST.json").read_bytes()),
                "_generated_author_hashes": self.author_hashes, **kwargs}
        return verify.verify(self.prepared, pin((self.prepared / "PREPARED.json").read_bytes()),
                             self.paper_pin, output or self.output(), **args)

    @contextlib.contextmanager
    def changed(self, relative, raw, update):
        path = self.prepared / relative; before = path.read_bytes(); mode = path.stat().st_mode & 0o777
        try:
            path.chmod(0o600); path.write_bytes(raw); path.chmod(mode)
            document = decoded(self.original); update(document, pin(raw))
            (self.prepared / "PREPARED.json").write_bytes(encoded(document))
            yield
        finally:
            path.chmod(0o600); path.write_bytes(before); path.chmod(mode)
            (self.prepared / "PREPARED.json").write_bytes(self.original)

    def test_complete_generated_delivery_never_executes_candidate_and_never_qualifies(self):
        output = self.output(); result = self.check(output=output)
        self.assertEqual((result["participants"], result["windows"], result["predictions_per_condition"]), (94, 376, 188))
        self.assertEqual(len(result["contexts"]), 10)
        self.assertEqual(result["scope"], "generated_delivery_control")
        self.assertEqual(result["status"], "provisional_structural_check")
        self.assertFalse(result["preparation_history_independently_observed"])
        self.assertFalse(result["source_array_numerical_rederivation"])
        self.assertFalse(result["native_runtime_qualification"])
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_production_rejects_fictional_author_sources(self):
        with self.assertRaisesRegex(ValueError, "official source"):
            self.check(_generated_author_hashes=None)

    def test_context_held_query_and_training_label_swaps_are_rejected_after_rehash(self):
        relative = "contexts/fold-00/CONTEXT.json"
        original = decoded((self.prepared / relative).read_bytes())
        for field in ("queries", "training"):
            changed = decoded(encoded(original))
            if field == "queries": changed[field][0] = changed["training"][0]["id"]
            else: changed[field][0]["label"] = "face" if changed[field][0]["label"] == "object" else "object"
            changed["context_sha256"] = contract.digest({k: v for k, v in changed.items() if k != "context_sha256"})
            def update(document, value):
                row = document["contexts"]["0"]; row["mount"]["files"]["CONTEXT.json"] = value
                row["context_sha256"] = changed["context_sha256"]
            with self.subTest(field=field), self.changed(relative, encoded(changed), update), self.assertRaisesRegex(ValueError, "context labels"):
                self.check()

    def test_extra_author_payload_and_symlink_are_rejected(self):
        root = self.prepared / "author"; extra = root / "TARGETS.json"
        for link in (False, True):
            root.chmod(0o700)
            if link: extra.symlink_to(self.prepared / "PRIVATE_PANEL.json")
            else: extra.write_bytes(b"unexpected")
            root.chmod(0o555)
            try:
                with self.subTest(symlink=link), self.assertRaises(ValueError): self.check()
            finally:
                root.chmod(0o700); extra.unlink(); root.chmod(0o555)

    def test_bank_tensor_swap_rejected_even_when_file_pin_is_updated(self):
        path = self.prepared / "data/WINDOWS.npy"; raw = path.read_bytes()
        start = 10 + struct.unpack("<H", raw[8:10])[0]; width = 32000
        first, second = raw[start:start + width], raw[start + width:start + 2 * width]
        try:
            path.chmod(0o600)
            with path.open("r+b") as handle: handle.seek(start); handle.write(second + first)
            path.chmod(0o444)
            doc = decoded(self.original); doc["data"]["files"]["WINDOWS.npy"] = pin(path.read_bytes())
            (self.prepared / "PREPARED.json").write_bytes(encoded(doc))
            with self.assertRaisesRegex(ValueError, "anonymous row/source value mismatch"): self.check()
        finally:
            path.chmod(0o600)
            with path.open("r+b") as handle: handle.seek(start); handle.write(first + second)
            path.chmod(0o444); (self.prepared / "PREPARED.json").write_bytes(self.original)

    def test_nonfinite_tensor_is_rejected_even_with_matching_tensor_hash(self):
        raw = bytearray((self.prepared / "data/WINDOWS.npy").read_bytes())
        start = 10 + struct.unpack("<H", raw[8:10])[0]; struct.pack_into("<d", raw, start, float("nan"))
        panel = decoded((self.prepared / "PRIVATE_PANEL.json").read_bytes())
        windows = contract.ordered_public_windows(panel)
        windows[0]["tensor_sha256"] = hashlib.sha256(raw[start:start + 32000]).hexdigest()
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            verify.bank_rows(bytes(raw), windows, verify.Budget(1, 1, 60))

    def test_bank_byte_order_and_trailing_payload_are_not_silently_accepted(self):
        original = (self.prepared / "data/WINDOWS.npy").read_bytes()
        panel = decoded((self.prepared / "PRIVATE_PANEL.json").read_bytes())
        windows = contract.ordered_public_windows(panel)
        for raw in (original.replace(b"'<f8'", b"'>f8'", 1), original + b"x"):
            with self.assertRaises(ValueError): verify.bank_rows(raw, windows, verify.Budget(1, 1, 60))

    def test_private_modes_and_qualification_flags_fail_closed(self):
        private = self.prepared / "PRIVATE_PANEL.json"; private.chmod(0o644)
        try:
            with self.assertRaisesRegex(ValueError, "permissions"): self.check()
        finally: private.chmod(0o600)
        changed = decoded(self.original); changed["historical_folds_authenticated"] = True
        (self.prepared / "PREPARED.json").write_bytes(encoded(changed))
        try:
            with self.assertRaisesRegex(ValueError, "promotion"): self.check()
        finally: (self.prepared / "PREPARED.json").write_bytes(self.original)

    def test_source_and_whole_read_grants_cannot_be_skipped(self):
        with self.assertRaisesRegex(ValueError, "read ceiling"): self.check(read_limit=4096)
        wrong_hash = dict(pin((verify.PAIRED / "SOURCE_MANIFEST.json").read_bytes()), sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "immutable bytes"):
            self.check(paired_source_manifest=wrong_hash)

    def test_wrong_expected_extent_fails_without_payload_read(self):
        budget = verify.Budget(100, 1, 30)
        with mock.patch.object(verify.os, "fdopen") as reader, self.assertRaisesRegex(ValueError, "extent"):
            budget.read(self.prepared / "PREPARED.json", pin(b"x"), 8192)
        reader.assert_not_called(); self.assertEqual(budget.read_reserved, 2)

    def test_final_write_past_deadline_keeps_only_provisional_receipt(self):
        clock = mock.Mock(return_value=0.0); actual = verify.os.fsync
        def delayed(fd): actual(fd); clock.return_value = 61.0
        output = self.output()
        with mock.patch.object(verify.os, "fsync", side_effect=delayed), self.assertRaisesRegex(ValueError, "deadline"):
            self.check(output=output, clock=clock)
        report = decoded(output.read_bytes())
        self.assertEqual(report["status"], "provisional_structural_check")
        self.assertTrue(report["external_successful_exit_deadline_and_final_report_pin_required"])

    def test_post_read_permissions_link_or_programme_changes_are_rejected(self):
        actual = verify.bank_rows
        for change in ("permissions", "link", "programme"):
            private = self.prepared / "PRIVATE_PANEL.json"
            programme = self.prepared / "program-A/submission.py"; before = programme.read_bytes()
            link = self.root / "late-hardlink"
            def mutate(raw, windows, budget, *, generic=False):
                actual(raw, windows, budget, generic=generic)
                if change == "permissions": private.chmod(0o644)
                elif change == "link": os.link(private, link)
                else:
                    programme.chmod(0o600); programme.write_bytes(before + b"# mutation\n"); programme.chmod(0o444)
            try:
                with self.subTest(change=change), mock.patch.object(verify, "bank_rows", side_effect=mutate), \
                     self.assertRaisesRegex(ValueError, "captured delivery leaf changed"):
                    self.check()
            finally:
                private.chmod(0o600)
                if link.exists(): link.unlink()
                programme.chmod(0o600); programme.write_bytes(before); programme.chmod(0o444)

    def test_bootstrap_rejects_fifo_and_hardlink_without_payload_read(self):
        fifo = self.root / "bootstrap-fifo"; os.mkfifo(fifo)
        try:
            with mock.patch.object(verify.os, "fdopen") as payload, self.assertRaisesRegex(ValueError, "bootstrap"):
                verify.bootstrap_pin(fifo)
            payload.assert_not_called()
        finally: fifo.unlink()
        original = self.root / "bootstrap-regular"; original.write_bytes(encoded(pin(b"generated")))
        link = self.root / "bootstrap-link"; os.link(original, link)
        try:
            with self.assertRaisesRegex(ValueError, "single-link"): verify.bootstrap_pin(original)
        finally: link.unlink()
        self.assertEqual(verify.bootstrap_pin(original), pin(b"generated"))


class HeaderTypes(unittest.TestCase):
    def test_shape_requires_integer_tuple_and_finite_geometry_without_disk_fixture(self):
        payload = bytes(376 * 32000)
        windows = [{"tensor_sha256": hashlib.sha256(bytes(32000)).hexdigest()}] * 376
        for shape in ((376, 4, 1000), (376.0, 4, 1000), [376, 4, 1000]):
            header = (repr({"descr": "<f8", "fortran_order": False, "shape": shape}).ljust(117) + "\n").encode()
            raw = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + payload
            if type(shape) is tuple and type(shape[0]) is int:
                verify.bank_rows(raw, windows, verify.Budget(1, 1, 60))
            else:
                with self.subTest(shape=shape), self.assertRaisesRegex(ValueError, "geometry"):
                    verify.bank_rows(raw, windows, verify.Budget(1, 1, 60))


if __name__ == "__main__":
    unittest.main()
