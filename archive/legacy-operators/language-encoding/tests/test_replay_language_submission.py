"""Adversarial gate tests; no candidate execution and no Docker needed here."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
import zipfile

import numpy as np

spec = importlib.util.spec_from_file_location("replay_gate", Path(__file__).resolve().parents[1] / "replay_language_submission.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def inventory(self):
        return [{"name": n, "mode": stat.S_IFREG | 0o600, "nlink": 1, "size": 20} for n in sorted(g.REQUIRED)]

    def test_complete_inventory(self):
        self.assertEqual(set(g.validate_inventory(self.inventory())), g.REQUIRED)

    def test_empty_or_unexpected_inventory(self):
        for entries in ([], self.inventory() + [{"name": "secret"}], self.inventory() + self.inventory()[:1]):
            with self.subTest(entries=entries), self.assertRaises(g.GateError): g.validate_inventory(entries)

    def test_links_directories_and_special_files_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFSOCK):
            entries = self.inventory(); entries[0]["mode"] = mode
            with self.subTest(mode=mode), self.assertRaises(g.GateError): g.validate_inventory(entries)
        entries = self.inventory(); entries[0]["nlink"] = 2
        with self.assertRaises(g.GateError): g.validate_inventory(entries)

    def test_output_size_and_type_rejected(self):
        for size in (0, -1, True, 10**9):
            entries = self.inventory(); entries[0]["size"] = size
            with self.subTest(size=size), self.assertRaises(g.GateError): g.validate_inventory(entries)

    def test_tar_never_extracts_link_or_traversal(self):
        for name, kind in (("../report.json", tarfile.REGTYPE), ("report.json", tarfile.SYMTYPE), ("report.json", tarfile.LNKTYPE)):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w") as t:
                info = tarfile.TarInfo(name); info.type = kind; info.size = 2 if kind == tarfile.REGTYPE else 0
                if kind != tarfile.REGTYPE: info.linkname = "/etc/passwd"
                t.addfile(info, io.BytesIO(b"{}") if info.size else None)
            with self.subTest(name=name, kind=kind), self.assertRaises(g.GateError): g.unpack_one(data.getvalue(), "report.json", 2)

    def test_regular_tar_bytes_only(self):
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w") as t:
            info = tarfile.TarInfo("report.json"); info.size = 2; t.addfile(info, io.BytesIO(b"{}"))
        self.assertEqual(g.unpack_one(raw.getvalue(), "report.json", 2), b"{}")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_source_symlink_hardlink_and_hash_mismatch(self):
        original = self.root / "original.py"; original.write_text("print('test')")
        link = self.root / "link.py"; link.symlink_to(original)
        with self.assertRaises(g.GateError): g.copy_regular(link, self.root / "copy.py", 100)
        link.unlink(); os.link(original, link)
        with self.assertRaises(g.GateError): g.copy_regular(original, self.root / "copy.py", 100)
        link.unlink()
        with self.assertRaises(g.GateError): g.copy_regular(original, self.root / "copy.py", 100, "0" * 64)

    def test_input_inventory_and_lock_hash_enforced(self):
        data = self.root / "data"; data.mkdir()
        source = self.root / "source.py"; source.write_text("print('hello')")
        records = []
        for name in g.INPUTS:
            (data/name).write_text(name)
            records.append({"role": "public_input", "local_path": "environment/data/" + name, "bytes": len(name), "sha256": g.sha(data/name)})
        lock = self.root / "lock.json"; lock.write_text(json.dumps({"schema_version": 1, "inputs": records}))
        stage = self.root / "stage"; stage.mkdir()
        (data / "query_truth.npz").write_text("secret")
        with self.assertRaises(g.GateError): g.stage_inputs(source, data, lock, stage)
        (data / "query_truth.npz").unlink()
        (data / "train_items.csv").write_text("tampered")
        with self.assertRaises(g.GateError): g.stage_inputs(source, data, lock, stage)
        for directory in stage.iterdir(): directory.chmod(0o700)

    def test_safe_npz_headers(self):
        path = self.root / "model.npz"
        np.savez(path, coef=np.zeros(1600), intercept=np.array(1.), alpha=np.array(10000.))
        g.validate_model_headers(path)

    def test_npz_object_wrong_shape_or_extra_member_rejected(self):
        for coef, extra in ((np.array([object()]), {}), (np.zeros(1601), {}), (np.zeros(1600), {"hidden": [1]})):
            path = self.root / "model.npz"; np.savez(path, coef=coef, intercept=np.array(1.), alpha=np.array(1.), **extra)
            with self.assertRaises(g.GateError): g.validate_model_headers(path)

    def test_npz_allocation_bomb_rejected_before_numpy_load(self):
        buf = io.BytesIO(); np.lib.format.write_array_header_1_0(buf, {"descr": "<f8", "fortran_order": False, "shape": (10**12,)})
        path = self.root / "model.npz"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("coef.npy", buf.getvalue()); z.writestr("intercept.npy", b"bad"); z.writestr("alpha.npy", b"bad")
        with self.assertRaises(g.GateError): g.validate_model_headers(path)

    def test_candidate_command_has_only_public_source_and_volume(self):
        cmd = g.candidate_command("candidate", g.IMAGE, "output-volume", self.root, 4*1024**3, 2, 128, 120)
        mounts = [cmd[i+1] for i, value in enumerate(cmd) if value == "--mount"]
        self.assertEqual(len(mounts), 3)
        self.assertIn("readonly", mounts[0]); self.assertIn("readonly", mounts[1])
        self.assertIn("type=volume", mounts[2]); self.assertIn("volume-nocopy", mounts[2])
        for forbidden in ("docker.sock", "tests/private", str(g.REPO)):
            self.assertFalse(any(forbidden in m for m in mounts))
        self.assertIn("--read-only", cmd); self.assertIn("none", cmd); self.assertIn("65534:65534", cmd)
        self.assertIn("--pids-limit", cmd); self.assertIn("--memory-swap", cmd)
        self.assertEqual(cmd[cmd.index("--entrypoint") + 1], "python")

    def test_unvetted_image_or_excessive_budget_rejected_before_creation(self):
        with self.assertRaises(g.GateError): g.replay(self.root/'missing.py', self.root/'new', image="python:latest")
        with self.assertRaises(g.GateError): g.replay(self.root/'missing.py', self.root/'new', wall=10000)
        self.assertFalse((self.root/'new').exists())

    def test_private_reference_must_match_pin(self):
        private = self.root / "private"; private.mkdir()
        (private/'expected.npz').write_bytes(b"trusted bytes")
        lock = self.root / "lock.json"
        pin = {"role": "verifier_reference", "local_path": "tests/private/expected.npz", "bytes": 13, "sha256": g.sha(private/'expected.npz')}
        lock.write_text(json.dumps({"inputs": [pin]}))
        g.verify_private_reference(private, lock)
        (private/'expected.npz').write_bytes(b"changed bytes")
        with self.assertRaises(g.GateError): g.verify_private_reference(private, lock)
        lock.write_text(json.dumps({"inputs": [pin, pin]}))
        with self.assertRaises(g.GateError): g.verify_private_reference(private, lock)

    def test_collector_mount_and_network_policy(self):
        value = {"Mounts": [{"Type": "volume", "Name": "v", "Destination": "/capture", "RW": False}], "Config": {"User": "65534:65534"}, "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"]}}
        g.verify_collector(value, "v")
        value["Mounts"][0]["RW"] = True
        with self.assertRaises(g.GateError): g.verify_collector(value, "v")

    def test_contract_policy_allows_bounded_regular_diagnostics_only(self):
        extra = {"name": "any-diagnostic.txt", "mode": stat.S_IFREG | 0o600, "nlink": 1, "size": 20}
        entries = self.inventory() + [extra]
        with self.assertRaises(g.GateError): g.validate_inventory(entries)
        self.assertIn(extra["name"], g.validate_inventory(entries, "artifact-contract"))
        for key, value in (("mode", stat.S_IFLNK), ("mode", stat.S_IFDIR), ("nlink", 2), ("size", 1_000_001)):
            changed = {**extra, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(g.GateError): g.validate_inventory(self.inventory()+[changed], "artifact-contract")

    def test_contract_policy_still_requires_artifacts(self):
        with self.assertRaises(g.GateError): g.validate_inventory([], "artifact-contract")


if __name__ == "__main__": unittest.main()
