"""New generated custody controls; no original source/data or old suite.

One real generated HDF5/NPZ fixture exercises production readers and file
capture. Full14 source orchestration uses an authenticated in-memory file
facade with real HDF5/NPZ decoding, followed by one real private export. This
does not qualify full14 production filesystem custody or authentic inputs.
"""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import h5py
import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural068_export_layout", HERE / "export_layout.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
WRITTEN, WRITE_CAP = 0, 225280
N = 576


def charge(count):
    global WRITTEN
    WRITTEN += count
    if WRITTEN > WRITE_CAP:
        raise AssertionError("Generated output allocation exceeded")


def put(path, raw):
    charge(len(raw))
    path.write_bytes(raw)


@contextmanager
def output_tree(root):
    """Charge all production-created files, including failed partial trees."""
    try:
        yield root
    finally:
        if root.exists():
            charge(sum(p.lstat().st_size for p in root.rglob("*") if p.is_file() or p.is_symlink()))


def nwb_bytes(*, mask_kind="bool", rate=.02, bad_trial=False, linked=False):
    stream = io.BytesIO()
    with h5py.File(stream, "w") as f:
        for name in ("OpenLoopKinematics", "OpenLoopKinematicsVelocity"):
            group = f.create_group("acquisition/" + name)
            group.attrs["description"] = ",".join(e.LABELS)
            data = group.create_dataset("data", shape=(N, 7), dtype="f8", fillvalue=float("nan"))
            data.attrs.update(unit="arbitrary", offset=0., conversion=1.)
            clock = group.create_dataset("starting_time", data=0.)
            clock.attrs["rate"] = rate
        trials = np.array([1.] * 500 + [2.] * 74 + [3.] * 2, dtype="f8")
        if bad_trial:
            trials[0] = float("nan")
        f.create_dataset("acquisition/TrialNum/data", data=trials, compression="gzip")
        masks = np.ones(N, dtype=mask_kind)
        masks[0] = 0
        f.create_dataset("acquisition/eval_mask/data", data=masks, compression="gzip")
        if linked:
            del f["acquisition/eval_mask/data"]
            f["acquisition/eval_mask/data"] = h5py.ExternalLink("must-not-open.h5", "/mask")
    raw = stream.getvalue()
    assert len(raw) <= 24576
    return raw


def npz_bytes(kind, *, clock_change=False, trial_change=False, mask_swap=False, nonbinary=False):
    stream = io.BytesIO()
    if kind == "input":
        time = np.arange(N) * .02
        trial = np.array([1] * 500 + [2] * 74 + [3] * 2, dtype="int64")
        if clock_change:
            time[1] += .001
        if trial_change:
            trial[1] = 2
        np.savez_compressed(stream, time_s=time, trial=trial, spikes=np.zeros((N, 176), dtype="uint16"))
        cap = 8192
    else:
        mask = np.ones(N, dtype="uint8"); mask[0] = 0
        if mask_swap:
            mask[0], mask[1] = 1, 0
        if nonbinary:
            mask[1] = 2
        np.savez_compressed(stream, eval_mask=mask, velocity=np.full((N, 7), np.nan))
        cap = 4096
    raw = stream.getvalue()
    assert len(raw) <= cap
    return raw


class MemoryFiles:
    def __init__(self, files):
        self.files, self.opened = files, []

    @contextmanager
    def authenticated(self, path, expected, budget):
        path = Path(path)
        raw = self.files[path]
        e.pin(expected)
        e.need(e.identity(raw) == expected, "Generated file facade pin mismatch")
        self.opened.append(path)
        stream = e.TrackedStream(io.BytesIO(raw), budget)
        yield stream
        e.need(self.files[path] == raw, "Generated file facade mutation")


def fixture(mutate=None, input_raw=None, target_raw=None):
    root = Path("/generated-neural068-export")
    raw_nwb = nwb_bytes()
    raw_input = npz_bytes("input") if input_raw is None else input_raw
    raw_target = npz_bytes("target") if target_raw is None else target_raw
    files = {HERE / name: (HERE / name).read_bytes() for name in ("export_layout.py", "scorer.py")}
    # Execute only the already pinned scorer inside this admitted generated test.
    scorer = e.scorer_module(HERE / "scorer.py", e.ReadBudget(100000))
    rows, shared = [], []
    runs = list(e.TRAIN) + [run for run, _ in scorer.RUNS]
    for index, run in enumerate(runs):
        role, group = ("train", "held-in-calib") if index < 13 else ("query", "held-out-calib")
        aid = f"00000000-0000-0000-0000-{index+1:012x}"
        source = {"asset_id": aid, "path": f"sub-HumanPitt-{group}/sub-HumanPitt-{group}_ses-{run}.nwb",
                  "url": "https://generated.invalid/never-requested", **e.identity(raw_nwb)}
        row = {"run": run, "role": role, "n_rows": N, "source": source,
               "input": e.identity(raw_input), "target": e.identity(raw_target)}
        if role == "query":
            row["split"] = {"segments": [[0, 500], [500, 574], [574, N]], "query_start": 574,
                            "query_stop": N, "query_rows": 2, "query_scored_rows": 2,
                            "prefixes": {str(b): {"elapsed_seconds": b, "rows": b*50,
                                                    "labeled_rows": b*50-1 if b else 0} for b in (0, 5, 10)}}
            files[root / "original" / (aid + ".nwb")] = raw_nwb
            files[root / "prepared" / run / "input.npz"] = raw_input
            files[root / "prepared" / run / "target.npz"] = raw_target
        rows.append(row)
        shared.append({**source, "run": run, "role": role, "n_rows": N,
                       "prepared": {"input.npz": row["input"], "target.npz": row["target"]}})
    preparation = {"schema": "falcon_h1_shared_preparation_v1", "rows": shared
                   + [{"role": "duplicate_minival_not_projected"} for _ in range(13)],
                   "full_raw_files": 40, "distinct_calibration_runs": 27, "minival_duplicates": 13}
    pool = {"schema": "neural068-prefix-5-10-third-segment-v1", "packet_id": "pending", "labels": e.LABELS,
            "runs": rows, "scope": "generated", "shared_preparation": {},
            "performance_inspected": False, "scientific_computation": False}
    if mutate:
        mutate(pool, preparation)
    prep_raw = e.canonical(preparation); pool["shared_preparation"] = e.identity(prep_raw)
    pool["packet_id"] = hashlib.sha256(e.canonical({k: v for k, v in pool.items() if k != "packet_id"})).hexdigest()
    files[root / "PREPARATION.json"] = prep_raw
    files[root / "POOL.json"] = e.canonical(pool)
    files[root / "external.json"] = e.canonical({"generated": True, "source_admission": False})
    def desc(path):
        return {"path": str(path), **e.identity(files[path])}
    selection = {"schema": "neural068-protected-layout-export-selection-v1",
                 "pool": desc(root / "POOL.json"), "preparation": desc(root / "PREPARATION.json"),
                 "external_metadata_receipt": desc(root / "external.json"),
                 "exporter": desc(HERE / "export_layout.py"), "original_root": str(root / "original"),
                 "prepared_root": str(root / "prepared"), "read_ceiling_bytes": 100000000,
                 "output_ceiling_bytes": 180000}
    return selection, MemoryFiles(files)


class ExportControls(unittest.TestCase):
    def export(self, bundle, out, *, allow_publication=False):
        selection, files = bundle
        with mock.patch.object(e, "authenticated", files.authenticated):
            if not allow_publication:
                with mock.patch.object(e, "publish", side_effect=AssertionError("rejected export reached publication")):
                    return e.export_layout(selection, out)
            return e.export_layout(selection, out)

    def test_real_generated_readers_do_not_decode_velocity_or_spikes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            bodies = {"source.nwb": nwb_bytes(), "input.npz": npz_bytes("input"), "target.npz": npz_bytes("target")}
            for name, raw in bodies.items():
                put(root / name, raw)
            old_get = h5py.Dataset.__getitem__
            old_open = zipfile.ZipFile.open
            def h5_get(data, key):
                self.assertNotIn(data.name, ("/acquisition/OpenLoopKinematics/data", "/acquisition/OpenLoopKinematicsVelocity/data", "/units/spike_times"))
                return old_get(data, key)
            def zip_open(archive, member, *args, **kwargs):
                self.assertNotIn(getattr(member, "filename", member), ("velocity.npy", "spikes.npy"))
                return old_open(archive, member, *args, **kwargs)
            budget = e.ReadBudget(1000000)
            with mock.patch.object(h5py.Dataset, "__getitem__", h5_get), mock.patch.object(zipfile.ZipFile, "open", zip_open):
                with e.authenticated(root / "source.nwb", e.identity(bodies["source.nwb"]), budget) as stream:
                    original = e.nwb_metadata(stream)
                for kind in ("input", "target"):
                    with e.authenticated(root / (kind + ".npz"), e.identity(bodies[kind + ".npz"]), budget) as stream:
                        values = e.npz_metadata(stream, kind, N)
                    self.assertEqual(values["time_s"] if kind == "input" else [bool(v) for v in values["eval_mask"]],
                                     original["time_s"] if kind == "input" else original["eval_mask"])
            self.assertGreater(budget.used, sum(map(len, bodies.values())) * 2)

    def test_original_reader_rejects_clock_trial_nonboolean_and_links(self):
        for kwargs, message in [({"rate": 50.}, "legacy zero-origin"), ({"bad_trial": True}, "TrialNum"),
                                ({"mask_kind": "uint8"}, "Genuinely Boolean"), ({"linked": True}, "No linked")]:
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(e.CustodyError, message):
                e.nwb_metadata(io.BytesIO(nwb_bytes(**kwargs)))

    def test_prepared_reader_rejects_duplicate_object_shape_and_noncanonical_members(self):
        base = npz_bytes("input")
        with zipfile.ZipFile(io.BytesIO(base)) as z:
            members = {n: z.read(n) for n in z.namelist()}
        cases = []
        for bad_dtype, bad_shape in [("|O", (N,)), ("<f8", (N - 1,))]:
            header = repr({"descr": bad_dtype, "fortran_order": False, "shape": bad_shape}).encode()
            header += b" " * ((-10-len(header)-1) % 64) + b"\n"
            cases.append({**members, "time_s.npy": b"\x93NUMPY\x01\x00" + len(header).to_bytes(2,"little") + header + b"\0" * (N*8)})
        cases.append({**members, "../outside.npy": b"x"})
        for changed in cases:
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as z:
                for n, raw in changed.items(): z.writestr(n, raw)
            with self.assertRaises(e.CustodyError): e.npz_metadata(io.BytesIO(out.getvalue()), "input", N)
        out = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(out, "w") as z:
                for n, raw in members.items(): z.writestr(n, raw)
                z.writestr("trial.npy", members["trial.npy"])
        with self.assertRaisesRegex(e.CustodyError, "unique NPZ"):
            e.npz_metadata(io.BytesIO(out.getvalue()), "input", N)

    def test_full14_export_preserves_layout_and_records_explicit_limits(self):
        bundle = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp).resolve() / "export"
            with output_tree(out):
                receipt = self.export(bundle, out, allow_publication=True)
                metadata = json.loads((out / "source_metadata.json").read_bytes())
                layout = json.loads((out / "layout.json").read_bytes())
                self.assertEqual(len(metadata), 14)
                self.assertEqual(len(layout["runs"]), 14)
                self.assertEqual(receipt["context_count"], 84)
                self.assertEqual(receipt["artifacts"]["layout.json"], e.identity((out / "layout.json").read_bytes()))
                scorer = e.scorer_module(HERE / "scorer.py", e.ReadBudget(100000))
                self.assertEqual(layout, scorer.make_layout(metadata))
                self.assertEqual(len({scorer.context_id(r["run"], a, b) for r in layout["runs"] for a in scorer.ARMS for b in scorer.BUDGETS}), 84)
                self.assertTrue(receipt["protected_container_bytes_read"])
                for field in ("velocity_and_spike_values_decoded", "dataset_identity_qualified", "producer_execution_verified",
                              "velocity_target_equality_verified", "runtime_qualified", "scientific_qualification", "readiness_promoted"):
                    self.assertIs(receipt[field], False)
                self.assertEqual({p.name for p in out.iterdir()}, {"layout.json", "source_metadata.json", "EXPORT_CUSTODY.json"})
                self.assertEqual(out.stat().st_mode & 0o777, 0o700)

    def test_rowwise_mismatches_fail_despite_rebound_file_pins(self):
        cases = [("input", {"clock_change": True}, "clock rows"), ("input", {"trial_change": True}, "TrialNum rows"),
                 ("target", {"mask_swap": True}, "mask bits"), ("target", {"nonbinary": True}, "mask bits")]
        for kind, kwargs, message in cases:
            bundle = fixture(**{kind + "_raw": npz_bytes(kind, **kwargs)})
            with tempfile.TemporaryDirectory() as tmp, self.subTest(kwargs=kwargs):
                out = Path(tmp).resolve() / "must-not-publish"
                with self.assertRaisesRegex(e.CustodyError, message): self.export(bundle, out)
                self.assertFalse(out.exists())

    def test_missing_reordered_minival_and_short_support_are_rejected(self):
        def minival(pool, prep):
            pool["runs"][13]["source"]["path"] = "sub-HumanPitt-held-out-minival/bad.nwb"
            prep["rows"][13]["path"] = pool["runs"][13]["source"]["path"]
        cases = [(lambda p,s: p["runs"].pop(), "27-run order"),
                 (lambda p,s: p["runs"].reverse(), "27-run order"), (minival, "no minival substitution"),
                 (lambda p,s: p["runs"][-1]["split"].update(query_stop=N-1), "complete query support")]
        for mutate, message in cases:
            with tempfile.TemporaryDirectory() as tmp, self.subTest(message=message):
                out = Path(tmp).resolve() / "must-not-publish"
                with self.assertRaisesRegex(e.CustodyError, message): self.export(fixture(mutate), out)
                self.assertFalse(out.exists())

    def test_wrong_pins_source_mutation_and_read_budget_fail_before_overread(self):
        bundle = fixture()
        bundle[0]["exporter"]["sha256"] = "f"*64
        with mock.patch.object(e, "publish", side_effect=AssertionError("pin failure reached publication")), \
                self.assertRaisesRegex(e.CustodyError, "facade pin mismatch"):
            self.export(bundle, HERE / "_never_created")
        for key in [p for p in fixture()[1].files if p.suffix in (".nwb", ".npz")][:3]:
            bundle = fixture(); bundle[1].files[key] += b"changed"
            with mock.patch.object(e, "publish", side_effect=AssertionError("pin failure reached publication")), \
                    self.assertRaisesRegex(e.CustodyError, "facade pin mismatch"):
                self.export(bundle, HERE / "_never_created")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / "tiny.bin"; put(path, b"abc")
            with self.assertRaisesRegex(e.CustodyError, "container bytes"):
                with e.authenticated(path, e.identity(b"xyz"), e.ReadBudget(100)): pass
            with self.assertRaises(e.CustodyError):
                with e.authenticated(path, e.identity(b"abc"), e.ReadBudget(100)):
                    put(path, b"def")
            link = path.with_name("linked.bin"); link.symlink_to(path); charge(len(str(path).encode()))
            with self.assertRaisesRegex(e.CustodyError, "Unlinked"):
                with e.authenticated(link, e.identity(b"def"), e.ReadBudget(100)): pass
        for method in ("read", "readinto"):
            inner = io.BytesIO(b"abcd"); stream = e.TrackedStream(inner, e.ReadBudget(2))
            with self.assertRaisesRegex(e.CustodyError, "ceiling"):
                stream.read(4) if method == "read" else stream.readinto(bytearray(4))
            self.assertEqual(inner.tell(), 0)

    def test_receipt_fsync_and_directory_fsync_failures_leave_no_completion(self):
        for fail_call in (3, 4):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp).resolve() / "partial"; calls = []
                real_fsync = os.fsync
                def fsync(fd):
                    calls.append(fd)
                    if len(calls) == fail_call: raise OSError("generated fsync failure")
                    return real_fsync(fd)
                # The pending receipt can have been fully written before the
                # injected failure. Charge those deleted receipt bytes as well.
                minimal = {"artifacts": {"layout.json": e.identity(e.canonical({})), "source_metadata.json": e.identity(e.canonical([]))}}
                charge(len(e.canonical(minimal)))
                with output_tree(out), mock.patch.object(e.os, "fsync", fsync), self.assertRaisesRegex(OSError, "generated fsync"):
                    e.publish(out, [], {}, {}, 4096)
                self.assertFalse((out / "EXPORT_CUSTODY.json").exists())
                self.assertFalse((out / ".EXPORT_CUSTODY.pending").exists())


if __name__ == "__main__":
    try:
        print(f"GENERATED_RUNTIME Python3; h5py={h5py.__version__}; numpy={np.__version__}")
        unittest.main(verbosity=2)
    finally:
        print(f"GENERATED_FILES_CUMULATIVE_BYTES={WRITTEN}; CAP={WRITE_CAP}; AUTHENTIC_INPUT_READS=0")
