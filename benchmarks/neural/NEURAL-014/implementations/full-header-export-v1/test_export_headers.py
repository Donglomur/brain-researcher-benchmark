"""Generated ZIP/HDF5 controls for the new exporter, not original-data validation."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib


def _bounded_entry():
    """Contain Python/native diagnostics before importing scientific libraries."""
    child = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--generated-control-child"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    total = retained = 0
    try:
        while True:
            body = child.stdout.read(4096)
            if not body:
                break
            total += len(body)
            keep = body[:max(0, 16384 - retained)]
            if keep:
                sys.stdout.buffer.write(keep)
                sys.stdout.buffer.flush()
                retained += len(keep)
        status = child.wait()
        return 78 if total > 16384 else (128 - status if status < 0 else status)
    finally:
        child.stdout.close()
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__" and sys.argv[1:] != ["--generated-control-child"]:
    # No setsid: the pool retains ownership of both supervisor and test child.
    raise SystemExit(_bounded_entry())

os.environ["HDF5_PLUGIN_PATH"] = ""
import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural014_new_header_export", HERE / "export_headers.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(os.environ["NEURAL014_HEADER_TEST_TMPDIR"])
        if not cls.scratch.is_absolute() or not cls.scratch.is_dir():
            raise ValueError("preallocated absolute generated scratch required")
        cls.writes = 0
        cls.fixture_material = 0
        cls.stage_charge = 0
        cls.consumer = e._consumer()
        task_path = Path(os.environ.get("NEURAL014_HEADER_TEST_TASK", str(HERE.parents[1] / "task.json")))
        cls.task = task_path.read_bytes()
        cls.original = e._contract(cls.task, cls.consumer)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.scratch)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @classmethod
    def charge(cls, n, field):
        if n < 0 or cls.writes + cls.fixture_material + cls.stage_charge + n > 500000:
            raise ValueError("cumulative generated fixture/staging500000B ceiling")
        setattr(cls, field, getattr(cls, field) + n)

    def hdf(self, *, session="t15.2023.08.11", block=1, trial=1, mode=None):
        out = io.BytesIO()
        with h5py.File(out, "w") as f:
            if mode == "empty":
                pass
            elif mode == "root_dataset":
                f.create_dataset("trial_0001", shape=(1,), dtype="u1")
            elif mode in ("soft", "external"):
                f["trial_0001"] = h5py.SoftLink("/nowhere") if mode == "soft" else h5py.ExternalLink("not-opened.h5", "/x")
            else:
                g = f.create_group("trial_0001")
                g.attrs["session"] = session
                g.attrs["block_num"] = block
                g.attrs["trial_num"] = trial
                # A genuine dataset exists; successful export must never decode it.
                g.create_dataset("input_features", shape=(1,), dtype="f4")
                g.create_dataset("transcription", shape=(1,), dtype="i4")
                g.create_dataset("seq_class_ids", shape=(1,), dtype="i4")
                if mode == "missing":
                    del g.attrs["trial_num"]
                elif mode == "alias":
                    f["trial_0002"] = g
                elif mode == "foreign_group":
                    f.move("trial_0001", "unrecognized")
        body = out.getvalue()
        self.charge(len(body), "fixture_material")
        return body

    def archive(self, rows, *, suffix="archive.zip", extras=()):
        # rows: [(member_name, real generated HDF5 bytes, native session)]
        path = self.root / suffix
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, body, _ in rows:
                z.writestr(name, body)
            for name, body in extras:
                z.writestr(name, body)
        archive_body = buffer.getvalue()
        self.charge(len(archive_body), "writes")
        path.write_bytes(archive_body)
        with zipfile.ZipFile(io.BytesIO(archive_body)) as z:
            members = {name: {"bytes": len(body), "compressed_size": z.getinfo(name).compress_size,
                              "session": session, "date": session[4:].replace(".", "-"),
                              "split": name.rsplit("/", 1)[1][5:-5]}
                       for name, body, session in rows}
        return path, {"archive": e.pin(archive_body), "members": members}

    def collect(self, path, contract):
        # Charge full possible stage writes before every attempt, including refusals.
        self.charge(sum(row["bytes"] for row in contract["members"].values()), "stage_charge")
        return e._collect(path, contract, self.root, h5py)

    def one(self, body=None):
        return self.archive([("hdf5_data_final/t15.2023.08.11/data_train.hdf5",
                              self.hdf() if body is None else body, "t15.2023.08.11")])

    def test_full127_empty_members_are_preserved_not_invented_trials(self):
        body = self.hdf(mode="empty")
        rows = [(name, body, row["session"]) for name, row in self.original["members"].items()]
        path, contract = self.archive(rows)
        result, costs = self.collect(path, contract)
        self.assertEqual(set(x["name"] for x in result["members"]), set(self.original["members"]))
        self.assertEqual(len(result["members"]), 127)
        self.assertEqual(len({x["session"] for x in contract["members"].values()}), 45)
        self.assertTrue(all(x["trials"] == [] for x in result["members"]))
        self.assertEqual(costs["member_opaque_bytes_staged"], 127 * len(body))

    def test_native_three_split_headers_and_unchanged_comparison_bridge(self):
        rows = [(f"hdf5_data_final/t15.2023.08.11/data_{split}.hdf5",
                 self.hdf(block=1 if split == "train" else 2, trial=i + 1), "t15.2023.08.11")
                for i, split in enumerate(("train", "val", "test"))]
        path, contract = self.archive(rows)
        with patch.object(h5py.Dataset, "__getitem__", side_effect=AssertionError("dataset decoded")), \
             patch.object(h5py.Dataset, "read_direct", side_effect=AssertionError("dataset decoded")):
            result, _ = self.collect(path, contract)
        self.assertEqual(set(result), {"schema", "coverage", "archive_sha256", "members"})
        self.assertEqual(result["coverage"], "all_source_members")
        self.assertEqual([x["trials"][0]["trial_num"] for x in result["members"]], [3, 1, 2])
        csv = b"Date,Post-implant day,Block number,Number of sentences,Corpus,Split\n2023-08-11,1,1,1,generated,Train\n2023-08-11,1,2,3,generated,Val/Test\n"
        # Only the production source-authentication boundary is replaced for tiny
        # generated containers. The existing comparison body itself is unchanged.
        with patch.object(self.consumer, "source_members", return_value=contract["members"]), \
             patch.object(self.consumer, "ARCHIVE_SHA256", contract["archive"]["sha256"]):
            comparison = self.consumer.reconcile(b"generated", csv, e.canonical(result))
        self.assertEqual(comparison["blocks"][0]["comparison"], "exact")
        self.assertEqual(comparison["blocks"][1]["observed_by_split"], {"train": 0, "val": 1, "test": 1})
        self.assertEqual(comparison["blocks"][1]["observed_minus_declared"], -1)
        self.assertFalse(comparison["all_source_blocks_match"])
        self.assertFalse(comparison["source_payload_authentication_established"])

    def test_original_gate_has_no_generated_source_override(self):
        path, _ = self.one()
        self.assertEqual(self.original["archive"]["bytes"], 11051034483)
        self.assertEqual(self.original["archive"]["sha256"], self.consumer.ARCHIVE_SHA256)
        with patch.object(e, "_headers", side_effect=AssertionError("opened before archive authentication")):
            with self.assertRaisesRegex(ValueError, "extent"):
                # No staging can occur: the original11GB extent gate precedes ZIP.
                e._collect(path, self.original, self.root, h5py)
        incomplete = b'{"id":"NEURAL-014","input_assets":{"readiness_records":[]}}'
        with patch.object(e, "_collect", side_effect=AssertionError("original I/O before full contract")):
            with self.assertRaisesRegex(ValueError, "exact T15 source record"):
                e.export_headers(incomplete, b"not yet read", path, self.root)

    def test_archive_hash_and_extent_fail_before_hdf5(self):
        path, c = self.one()
        for change in ({"bytes": c["archive"]["bytes"] + 1}, {"sha256": "0" * 64}):
            bad = copy.deepcopy(c); bad["archive"].update(change)
            with patch.object(e, "_headers", side_effect=AssertionError("premature HDF5 open")):
                with self.assertRaises(ValueError):
                    self.collect(path, bad)

    def test_incomplete_extra_and_wrong_extent_rosters_refuse(self):
        body = self.hdf(mode="empty")
        path, c = self.one(body)
        bad = copy.deepcopy(c); bad["members"][next(iter(bad["members"]))]["compressed_size"] += 1
        with self.assertRaisesRegex(ValueError, "extent"):
            self.collect(path, bad)
        bad = copy.deepcopy(c); bad["members"]["hdf5_data_final/t15.2023.08.11/data_test.hdf5"] = dict(next(iter(c["members"].values())))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.collect(path, bad)
        path, c = self.archive([(next(iter(c["members"])), body, "t15.2023.08.11")],
                               suffix="extra.zip", extras=[("../outside", b"x")])
        with self.assertRaises(ValueError):
            self.collect(path, c)

    def test_zip_duplicates_links_encryption_and_foreign_files_refuse(self):
        body = self.hdf(mode="empty")
        path, c = self.one(body)
        info = zipfile.ZipInfo(next(iter(c["members"])))
        info.file_size = len(body); info.compress_size = next(iter(c["members"].values()))["compressed_size"]
        class FakeDirectory:
            def __init__(self, infos): self.infos = infos
            def infolist(self): return self.infos
        for mode in ("duplicate", "symlink", "encrypted", "foreign"):
            item = copy.copy(info)
            if mode == "symlink": item.external_attr = (stat.S_IFLNK | 0o777) << 16
            if mode == "encrypted": item.flag_bits |= 1
            if mode == "foreign": item.filename = item.orig_filename = "unexpected.txt"
            rows = [item, item] if mode == "duplicate" else [item]
            with self.assertRaises(ValueError): e._zip_roster(FakeDirectory(rows), c["members"])

    def test_corrupted_member_crc_or_compression_refuses(self):
        path, c = self.one()
        original = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(original)) as z:
            info = z.infolist()[0]
        # Change compressed member bytes but retain the old CRC. The generated
        # archive contract is intentionally resealed; member parsing must refuse.
        offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        damaged = bytearray(original); damaged[offset + info.compress_size // 2] ^= 0x40
        self.charge(len(damaged), "writes"); path.write_bytes(damaged)
        c["archive"] = e.pin(damaged)
        with self.assertRaises((ValueError, zipfile.BadZipFile, zlib.error, OSError)):
            self.collect(path, c)

    def test_symlink_archive_is_not_followed(self):
        path, c = self.one()
        link = self.root / "link.zip"
        self.charge(len(str(path).encode()), "writes")
        link.symlink_to(path)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.collect(link, c)

    def test_nonordinary_hdf5_roots_refuse_without_following_links(self):
        for i, mode in enumerate(("soft", "external", "alias", "root_dataset", "foreign_group")):
            path, c = self.archive([("hdf5_data_final/t15.2023.08.11/data_train.hdf5", self.hdf(mode=mode), "t15.2023.08.11")], suffix=f"badroot{i}.zip")
            with self.assertRaises(ValueError): self.collect(path, c)

    def test_malformed_native_identity_attributes_refuse(self):
        variants = [dict(mode="missing"), dict(block=np.array([1, 2], dtype="i4")),
                    dict(block=True), dict(block=1.5), dict(trial=-1),
                    dict(trial=50001), dict(session="t15.2023.08.12")]
        for i, args in enumerate(variants):
            path, c = self.archive([("hdf5_data_final/t15.2023.08.11/data_train.hdf5", self.hdf(**args), "t15.2023.08.11")], suffix=f"badattr{i}.zip")
            with self.assertRaises(ValueError): self.collect(path, c)

    def test_duplicate_native_identity_across_splits_refuses(self):
        body = self.hdf()
        path, c = self.archive([(f"hdf5_data_final/t15.2023.08.11/data_{s}.hdf5", body, "t15.2023.08.11") for s in ("train", "val")])
        with self.assertRaisesRegex(ValueError, "duplicate native"):
            self.collect(path, c)

    def test_same_open_archive_path_replacement_is_detected(self):
        path, c = self.one()
        real = e._headers
        def replace(stream, member, library):
            result = real(stream, member, library)
            moved = self.root / "retained-source.zip"
            path.rename(moved)
            replacement = moved.read_bytes()
            self.charge(len(replacement), "writes")
            path.write_bytes(replacement)
            return result
        with patch.object(e, "_headers", side_effect=replace):
            with self.assertRaisesRegex(ValueError, "custody changed"):
                self.collect(path, c)

    def test_staged_member_mutation_is_detected(self):
        path, c = self.one()
        real = e._headers
        def mutate(stream, member, library):
            result = real(stream, member, library)
            self.charge(1, "writes")
            stream.stream.seek(0); stream.stream.write(b"X"); stream.stream.flush()
            return result
        with patch.object(e, "_headers", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "member changed"):
                self.collect(path, c)

    def test_read_and_group_bounds_refuse_without_truncating(self):
        reader = e._Reads(io.BytesIO(b"abc"), 2)
        with self.assertRaisesRegex(ValueError, "budget"):
            reader.read(3)
        path, c = self.one()
        with patch.object(e, "MAX_GROUPS", 0):
            with self.assertRaisesRegex(ValueError, "limit"):
                self.collect(path, c)

    def test_cli_failure_never_publishes_success_and_refuses_reuse(self):
        task = self.root / "task.json"; self.charge(2, "writes"); task.write_bytes(b"{}")
        csv = self.root / "source.csv"; self.charge(1, "writes"); csv.write_bytes(b"x")
        target = self.root / "fresh"
        argv = ["export_headers.py", "--task", str(task), "--author-csv", str(csv),
                "--archive", str(self.root / "absent.zip"), "--scratch", str(self.root), "--out", str(target)]
        self.charge(len(e.canonical({"status": "failed", "complete_export": False})), "writes")
        with patch.object(sys, "argv", argv), patch.object(e, "export_headers", side_effect=ValueError("generated failure")):
            with self.assertRaises(ValueError): e.main()
        self.assertEqual([p.name for p in target.iterdir()], ["FAILED.json"])
        self.assertFalse(json.loads((target / "FAILED.json").read_bytes())["complete_export"])
        with patch.object(sys, "argv", argv):
            with self.assertRaises(FileExistsError): e.main()


if __name__ == "__main__":
    # The outer entry enforces16KiB on all child bytes, including import errors
    # and native stderr. This formatting only keeps ordinary summaries compact.
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    print(log.getvalue()[:12000], end="")
    print(json.dumps({"h5py": h5py.__version__, "numpy": np.__version__,
                      "fixture_material_bytes": Controls.fixture_material,
                      "archive_and_output_bytes": Controls.writes,
                      "conservative_stage_write_bytes": Controls.stage_charge,
                      "generated_only": True, "original_runtime_qualified": False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
