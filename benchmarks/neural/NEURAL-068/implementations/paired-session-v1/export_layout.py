"""Protected original/prepared metadata custody for the selected N068 layout.

Whole-container authentication reads protected bytes. Only clock, trial, mask
and header fields are decoded; velocity/spike values remain undecoded. Matching
files/metadata does not authenticate a dataset release or producer execution.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import types
import zipfile


SCORER_PIN = {"bytes": 13947, "sha256": "14c4b87dccbc863419c01b9968cd873c1d0be2eeca9f33c95eb375dfae2b7a76"}
LABELS = ["tx", "ty", "tz", "rx", "g1", "g2", "g3"]
TRAIN = ("19250101T111740", "19250101T112404", "19250108T110520", "19250108T111022",
         "19250108T111455", "19250113T120811", "19250113T121303", "19250115T110633",
         "19250115T111328", "19250119T113543", "19250119T114045", "19250120T115044",
         "19250120T115537")


class CustodyError(ValueError):
    pass


def need(value, message):
    if not value:
        raise CustodyError(message)


def exact(value, keys, message):
    need(type(value) is dict and set(value) == set(keys), message)


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def pin(value):
    exact(value, ("bytes", "sha256"), "Exact file descriptor")
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= 268435456, "Bounded file descriptor")
    need(type(value["sha256"]) is str and len(value["sha256"]) == 64
         and all(c in "0123456789abcdef" for c in value["sha256"]), "SHA256 descriptor")
    return value


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("ascii")


def parse(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    def bad(_):
        raise CustodyError("Nonfinite JSON constant")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts, "Absolute operand path")
    need(not any(p.is_symlink() for p in (path, *path.parents)), "Unlinked operand")
    return path


def stamp(value):
    return (value.st_dev, value.st_ino, value.st_nlink, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


class ReadBudget:
    def __init__(self, limit):
        need(type(limit) is int and 0 < limit <= 2147483648, "Declared read ceiling")
        self.limit, self.used = limit, 0

    def charge(self, count):
        self.used += count
        need(self.used <= self.limit, "Protected read ceiling exceeded")


class TrackedStream:
    """Reserve bounded Python file-object reads before h5py/zip I/O."""
    def __init__(self, stream, budget):
        self.stream, self.budget = stream, budget

    def allowance(self, count):
        position = self.stream.tell()
        end = self.stream.seek(0, os.SEEK_END)
        self.stream.seek(position)
        available = max(0, end - position)
        count = available if count < 0 else min(count, available)
        self.budget.charge(count)  # reserve even if I/O later fails or short-reads
        return count

    def read(self, count=-1):
        return self.stream.read(self.allowance(count))

    def readinto(self, buffer):
        count = self.allowance(len(buffer))
        return self.stream.readinto(memoryview(buffer)[:count])

    def seek(self, offset, whence=0):
        return self.stream.seek(offset, whence)

    def tell(self):
        return self.stream.tell()

    def seekable(self):
        return True

    def readable(self):
        return True

    def writable(self):
        return False

    def flush(self):
        return self.stream.flush()


@contextmanager
def authenticated(path, expected, budget):
    """One pinned file descriptor; hash before and after decoding, never copy."""
    path, expected = ordinary(path), pin(expected)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as file:
        before = os.fstat(file.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected["bytes"], "Exact ordinary source extent")
        stream = TrackedStream(file, budget)
        def check():
            stream.seek(0)
            digest = hashlib.sha256()
            count = 0
            while True:
                block = stream.read(1048576)
                if not block:
                    break
                count += len(block)
                digest.update(block)
            need({"bytes": count, "sha256": digest.hexdigest()} == expected, "Authenticated container bytes")
            need(stamp(before) == stamp(os.fstat(file.fileno())) == stamp(path.lstat()), "Source remained unchanged")
            stream.seek(0)
        check()
        yield stream
        check()


def capture_json(descriptor, budget, cap):
    exact(descriptor, ("path", "bytes", "sha256"), "Exact located metadata descriptor")
    expected = {k: descriptor[k] for k in ("bytes", "sha256")}
    need(expected["bytes"] <= cap, "Metadata extent ceiling")
    with authenticated(descriptor["path"], expected, budget) as stream:
        return parse(stream.read(cap + 1))


def scorer_module(path, budget):
    with authenticated(path, SCORER_PIN, budget) as stream:
        raw = stream.read(SCORER_PIN["bytes"] + 1)
    module = types.ModuleType("_neural068_layout_custody_scorer")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def _npy_header(member):
    need(member.read(6) == b"\x93NUMPY", "Primitive NPY member")
    version = member.read(2)
    need(version in (b"\x01\x00", b"\x02\x00"), "Supported primitive NPY version")
    width = 2 if version[0] == 1 else 4
    length = int.from_bytes(member.read(width), "little")
    need(0 < length <= 4096, "Bounded NPY header")
    raw = member.read(length)
    need(len(raw) == length, "Complete NPY header")
    header = ast.literal_eval(raw.decode("latin1"))
    exact(header, ("descr", "fortran_order", "shape"), "Exact NPY header fields")
    need(header["fortran_order"] is False and type(header["shape"]) is tuple, "C-order primitive array")
    return header, 8 + width + length


def npz_metadata(stream, kind, n):
    """Decode only needed metadata members; never open spikes/velocity members."""
    wanted = {"input": {"time_s": ("<f8", "d"), "trial": ("<i8", "q")},
              "target": {"eval_mask": ("|u1", "B")}}[kind]
    names = {"input": {"spikes.npy", "time_s.npy", "trial.npy"},
             "target": {"velocity.npy", "eval_mask.npy"}}[kind]
    out = {}
    with zipfile.ZipFile(stream) as archive:
        rows = archive.infolist()
        need(len(rows) == len(names) and {r.filename for r in rows} == names, "Exact unique NPZ members")
        need(all(not (r.flag_bits & 1) and r.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                 and r.file_size <= 16000000 for r in rows), "Bounded ordinary NPZ members")
        for name, (dtype, code) in wanted.items():
            info = archive.getinfo(name + ".npy")
            with archive.open(info) as member:
                header, offset = _npy_header(member)
                need(header["descr"] == dtype and header["shape"] == (n,), "Exact prepared metadata dtype/shape")
                size = struct.calcsize("<" + code)
                need(info.file_size == offset + n * size, "Exact prepared metadata extent")
                raw = member.read(n * size + 1)
                need(len(raw) == n * size, "Complete prepared metadata values")
                out[name] = [v[0] for v in struct.iter_unpack("<" + code, raw)]
    return out


def nwb_metadata(stream):
    """Read the declared shared-preparer metadata ABI; require existing h5py."""
    try:
        import h5py
    except ImportError as error:
        raise CustodyError("Existing h5py runtime required; installation is not implicit") from error
    with h5py.File(stream, "r") as file:
        def obj(path):
            current = file
            for part in path.split("/"):
                need(isinstance(current.get(part, getlink=True), h5py.HardLink), "No linked NWB metadata")
                current = current[part]
            return current
        def dataset(path, shape=None):
            data = obj(path)
            need(isinstance(data, h5py.Dataset) and not data.is_virtual
                 and not data.external and data.compression in (None, "gzip"), "Ordinary NWB dataset")
            need(data.dtype.kind in "biuf" and data.dtype.itemsize <= 8, "Primitive NWB metadata dtype")
            if shape is not None:
                need(data.shape == shape, "Exact NWB metadata shape")
            return data
        kin, vel = obj("acquisition/OpenLoopKinematics"), obj("acquisition/OpenLoopKinematicsVelocity")
        kd = dataset("acquisition/OpenLoopKinematics/data")
        vd = dataset("acquisition/OpenLoopKinematicsVelocity/data")
        need(len(vd.shape) == 2 and vd.shape[1] == 7 and 2 <= vd.shape[0] <= 100000,
             "Complete bounded seven-channel source")
        n = vd.shape[0]
        need(kd.shape == (n, 7) and kin.attrs["description"].split(",") == LABELS
             and vel.attrs["description"].split(",") == LABELS, "Exact source channel order")
        need(kd.attrs["unit"] == vd.attrs["unit"] == "arbitrary"
             and float(kd.attrs["offset"]) == float(vd.attrs["offset"]) == 0.
             and float(vd.attrs["conversion"]) == 1., "Unchanged declared source units")
        for name in ("OpenLoopKinematics", "OpenLoopKinematicsVelocity"):
            clock = dataset("acquisition/" + name + "/starting_time", ())
            need(float(clock[()]) == 0. and float(clock.attrs["rate"]) == .02, "Explicit legacy zero-origin 20ms clock")
        trial = dataset("acquisition/TrialNum/data", (n,))
        mask = dataset("acquisition/eval_mask/data", (n,))
        need(mask.dtype.kind == "b" and mask.dtype.itemsize == 1, "Genuinely Boolean original mask")
        trials, masks = trial[()].tolist(), mask[()].tolist()
        need(all(type(t) in (int, float) and math.isfinite(t) and t == math.floor(t) for t in trials)
             and all(b >= a for a, b in zip(trials, trials[1:])), "Monotonic integral original TrialNum")
        need(all(type(m) is bool for m in masks), "Boolean source mask values")
        return {"time_s": [i * .02 for i in range(n)], "trial": [int(t) for t in trials], "eval_mask": masks}


def roster(pool, preparation, scorer):
    exact(pool, ("schema", "packet_id", "labels", "runs", "scope", "shared_preparation",
                 "performance_inspected", "scientific_computation"), "Exact legacy pool fields")
    need(pool["schema"] == "neural068-prefix-5-10-third-segment-v1" and pool["labels"] == LABELS,
         "Unchanged pool/channel generation")
    need(hashlib.sha256(canonical({k: v for k, v in pool.items() if k != "packet_id"})).hexdigest()
         == pool["packet_id"], "Legacy canonical pool generation")
    expected = list(TRAIN) + [run for run, _ in scorer.RUNS]
    need([row["run"] for row in pool["runs"]] == expected, "Exact original 27-run order")
    need(preparation["schema"] == "falcon_h1_shared_preparation_v1"
         and preparation["full_raw_files"] == 40 and preparation["distinct_calibration_runs"] == 27
         and preparation["minival_duplicates"] == 13 and len(preparation["rows"]) == 40,
         "Complete declared shared metadata roster")
    projected = [r for r in preparation["rows"] if r["role"] in ("train", "query")]
    need([r["run"] for r in projected] == expected, "Same shared train/query order")
    need(sum(r["role"] == "duplicate_minival_not_projected" for r in preparation["rows"]) == 13,
         "Minival metadata remains outside selected support")
    for index, (row, prior) in enumerate(zip(pool["runs"], projected)):
        role = "train" if index < 13 else "query"
        group = "held-in-calib" if index < 13 else "held-out-calib"
        source = row["source"]
        need(row["role"] == prior["role"] == role and row["n_rows"] == prior["n_rows"]
             and type(row["n_rows"]) is int and 2 <= row["n_rows"] <= 100000,
             "Same full source role/extent")
        need(source == {key: prior[key] for key in ("asset_id", "path", "bytes", "sha256", "url")},
             "Original source/preparation identity join")
        need(type(source["asset_id"]) is str and len(source["asset_id"]) == 36
             and all(c in "0123456789abcdef-" for c in source["asset_id"]), "Original asset identifier")
        expected_path = f"sub-HumanPitt-{group}/sub-HumanPitt-{group}_ses-{row['run']}.nwb"
        need(source["path"] == expected_path, "Exact calibration asset path; no minival substitution")
        need(row["input"] == prior["prepared"]["input.npz"]
             and row["target"] == prior["prepared"]["target.npz"], "Prepared container pin join")
        pin({k: source[k] for k in ("bytes", "sha256")}); pin(row["input"]); pin(row["target"])
    ids = [r["source"]["asset_id"] for r in pool["runs"]]
    need(len(ids) == len(set(ids)), "Distinct selected asset identifiers")
    return pool["runs"][13:]


def collect_metadata(rows, original_root, prepared_root, budget):
    result, custody = [], []
    for row in rows:
        source = row["source"]
        original = original_root / (source["asset_id"] + ".nwb")
        with authenticated(original, {k: source[k] for k in ("bytes", "sha256")}, budget) as stream:
            actual = nwb_metadata(stream)
        n = row["n_rows"]
        with authenticated(prepared_root / row["run"] / "input.npz", row["input"], budget) as stream:
            prepared = npz_metadata(stream, "input", n)
        with authenticated(prepared_root / row["run"] / "target.npz", row["target"], budget) as stream:
            masks = npz_metadata(stream, "target", n)["eval_mask"]
        need(len(actual["time_s"]) == len(actual["trial"]) == len(actual["eval_mask"]) == n,
             "Full original/prepared metadata extent")
        need(prepared["time_s"] == actual["time_s"], "Exact original/prepared clock rows")
        need(prepared["trial"] == actual["trial"], "Exact original/prepared TrialNum rows")
        need(all(type(v) is int and v in (0, 1) for v in masks)
             and [bool(v) for v in masks] == actual["eval_mask"], "Exact original/prepared mask bits")
        result.append({"run": row["run"], "source_sha256": source["sha256"], **actual})
        custody.append({"run": row["run"], "original": source,
                        "input": row["input"], "target": row["target"], "n_rows": n})
    return result, custody


def same_legacy_support(layout, rows, metadata):
    for current, row, original in zip(layout["runs"], rows, metadata):
        split = row["split"]
        trials = original["trial"]
        starts = [0] + [i for i in range(1, len(trials)) if trials[i] != trials[i - 1]]
        need(split["segments"] == [list(pair) for pair in zip(starts, starts[1:] + [len(trials)])],
             "Exact original legacy trial segments")
        need(current["run"] == row["run"] and current["query_start_bin"] == split["query_start"]
             and current["query_stop_bin"] == split["query_stop"] == row["n_rows"]
             and len(current["row_ids"]) == split["query_rows"]
             and sum(current["eval_mask"]) == split["query_scored_rows"], "Exact legacy complete query support")
        for budget in (0, 5, 10):
            prefix = split["prefixes"][str(budget)]
            need(all(type(v) is int for v in prefix.values())
                 and prefix == {"elapsed_seconds": budget, "rows": budget * 50,
                            "labeled_rows": current["calibration_labeled_rows"][str(budget)]},
                 "Exact legacy calibration support")


def publish(output, metadata, layout, receipt, ceiling):
    """Fresh private artifacts; receipt last. Failed partial trees stay unqualified."""
    need(type(ceiling) is int and 0 < ceiling <= 16777216, "Declared output ceiling")
    bodies = {"layout.json": canonical(layout), "source_metadata.json": canonical(metadata)}
    receipt = {**receipt, "artifacts": {name: identity(raw) for name, raw in bodies.items()}}
    bodies["EXPORT_CUSTODY.json"] = canonical(receipt)
    need(sum(map(len, bodies.values())) <= ceiling, "Full export output ceiling; no truncation")
    output = ordinary(output)
    need(not output.exists(), "Fresh private output directory")
    output.mkdir(mode=0o700)
    owned_receipt_inode = None
    pending, final = output / ".EXPORT_CUSTODY.pending", output / "EXPORT_CUSTODY.json"
    try:
        for name, raw in bodies.items():
            path = pending if name == "EXPORT_CUSTODY.json" else output / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
            with os.fdopen(fd, "wb") as stream:
                if path == pending:
                    info = os.fstat(stream.fileno())
                    owned_receipt_inode = (info.st_dev, info.st_ino)
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.link(pending, final)  # no replacement of an existing final receipt
        pending.unlink()
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except BaseException:
        # Delete only this invocation's receipt inode. Earlier private artifacts
        # remain inspectable, but neither receipt-write nor directory-fsync
        # failure may leave our valid-looking completion record.
        for path in (pending, final):
            try:
                info = path.lstat()
                if (info.st_dev, info.st_ino) == owned_receipt_inode:
                    path.unlink()
            except FileNotFoundError:
                pass
        raise
    return receipt


def export_layout(selection, output_directory, *, scorer_path=None):
    """Trusted API; selection itself must be externally frozen before invocation."""
    exact(selection, ("schema", "pool", "preparation", "external_metadata_receipt", "exporter", "original_root",
                      "prepared_root", "read_ceiling_bytes", "output_ceiling_bytes"), "Exact protected export selection")
    need(selection["schema"] == "neural068-protected-layout-export-selection-v1", "Export selection schema")
    budget = ReadBudget(selection["read_ceiling_bytes"])
    code = selection["exporter"]
    exact(code, ("path", "bytes", "sha256"), "Exact exporter source descriptor")
    need(Path(code["path"]) == Path(__file__).absolute() and code["bytes"] <= 65536,
         "Selected exporter source location/extent")
    with authenticated(code["path"], {k: code[k] for k in ("bytes", "sha256")}, budget):
        pass
    scorer_path = Path(__file__).with_name("scorer.py") if scorer_path is None else Path(scorer_path)
    scorer = scorer_module(ordinary(scorer_path), budget)
    pool = capture_json(selection["pool"], budget, 100000)
    preparation = capture_json(selection["preparation"], budget, 100000)
    need(pool["shared_preparation"] == {k: selection["preparation"][k] for k in ("bytes", "sha256")},
         "Pool binds shared preparation bytes")
    # This external document is pinned and retained, not treated as execution or
    # dataset-authenticity permission. Its issuer/schema remains external.
    capture_json(selection["external_metadata_receipt"], budget, 131072)
    rows = roster(pool, preparation, scorer)
    original_root, prepared_root = ordinary(selection["original_root"]), ordinary(selection["prepared_root"])
    metadata, custody = collect_metadata(rows, original_root, prepared_root, budget)
    layout = scorer.make_layout(metadata)
    same_legacy_support(layout, rows, metadata)
    receipt = {"schema": "neural068-protected-layout-custody-v1", "task_id": "NEURAL-068",
               "source_metadata_compared": True, "selected_runs": 14, "context_count": 84,
               "labels": LABELS, "pool_generation": pool["packet_id"], "layout_packet_id": layout["packet_id"],
               "selection_canonical_pin": identity(canonical(selection)), "selection": selection,
               "exporter_source_pin": {k: code[k] for k in ("bytes", "sha256")},
               "scorer": SCORER_PIN, "sources": custody,
               "external_metadata_receipt": selection["external_metadata_receipt"],
               "protected_container_bytes_read": True, "velocity_and_spike_values_decoded": False,
               "python_file_object_read_reservation_bytes": budget.used,
               "whole_files_hashed_before_and_after_metadata_reads": True,
               "dataset_identity_qualified": False, "producer_execution_verified": False,
               "velocity_target_equality_verified": False, "runtime_qualified": False,
               "scientific_qualification": False, "native_understanding_qualified": False,
               "retrospective_prior_target_access_unexcluded": True, "readiness_promoted": False}
    return publish(output_directory, metadata, layout, receipt, selection["output_ceiling_bytes"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--selection-bytes", required=True, type=int)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    descriptor = {"path": str(args.selection), "bytes": args.selection_bytes, "sha256": args.selection_sha256}
    selection = capture_json(descriptor, ReadBudget(1048576), 65536)
    receipt = export_layout(selection, args.output)
    print(json.dumps({"layout": receipt["artifacts"]["layout.json"], "readiness_promoted": False}))


if __name__ == "__main__":
    main()
