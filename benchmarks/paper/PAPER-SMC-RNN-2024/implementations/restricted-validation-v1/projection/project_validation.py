#!/usr/bin/env python3
"""Project the original SMC VALID input into a physically restricted packet.

This trusted preparation process may stream complete raw HDF5 bytes to authenticate
them. It never numerically indexes VALID held-out spikes or TRAIN behavior. The
worker receives only the fresh packet, not this request, receipt, or raw parents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

REQUEST_SCHEMA = "smc_restricted_validation_projection_request_v1"
PACKET_SCHEMA = "smc_restricted_validation_packet_v1"
RECEIPT_SCHEMA = "smc_restricted_validation_projection_receipt_v1"
MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_METADATA_BYTES = 128 * 1024
MAX_PACKET_BYTES = 160 * 1024 * 1024
ROWS_PER_CHUNK = 16
SOURCE_PINS = {
    "train": {"sha256": "49d202bb01fe724ed0c57b4444394a9bd6efe76b67a1d22c912d51d97de922f8"},
    "eval": {"sha256": "c6b86a268862cb812f0ae1d9e8629cf0ce3d1a760e03b7d16cf5cb32ce8d7fb9"},
    "panel": {"bytes": 5047, "sha256": "773a54ed1cfd1083b6d08fee17c7bcb416088a35b5e65a01d9485a3c7c58158a"},
    "identity": {"bytes": 39804, "sha256": "2a48e686daa737c6a3bbfae7fa0e4b409fed156f82a1d49c216fedc7c3beec87"},
}
ORDER_PINS = {
    "trial_indices_sha256": "e2261c95ca4a46b3ca4c14b74bfbf222486f5f39c0c77fd22ffe12d8a97af8ce",
    "neuron_indices_sha256": "1c70f09e86c025e6236367ae6837bd07224bb73e548916e264b9a54dd66baf88",
    "conditions_sha256": "2b21b6d389fdc0ad8d751a9f996c1568d7b1dafbd510b5685354d5602939152e",
    "tensor_trial_indices_sha256": "1180bcd7082f6eec884944481a90e983dc832421bb00cf94f3227b6b99007738",
}
GEOMETRY = {"train_trials": 1721, "eval_trials": 574, "observed_bins": 35,
            "train_forward_bins": 10, "heldin_units": 137, "heldout_units": 45,
            "bin_size_ms": 20}
RELATIVE_FILES = {
    "train": "mc_maze/val/train_input_20ms.h5",
    "eval": "mc_maze/val/eval_input_20ms.h5",
}
SHAPES = {
    "train": {"train_spikes_heldin": (1721, 35, 137),
              "train_spikes_heldin_forward": (1721, 10, 137),
              "train_spikes_heldout": (1721, 35, 45),
              "train_spikes_heldout_forward": (1721, 10, 45)},
    "eval": {"eval_spikes_heldin": (574, 35, 137)},
}
EXCLUDED_SOURCE_SHAPES = {"train": {"train_behavior": (1721, 35, 2)},
                          "eval": {"eval_spikes_heldout": (574, 35, 45)}}
CONTENT_PINS = {
    "train_spikes_heldin": "a810f84a5063dbf02fc95292266ee577f3b11e6ee33592ba3f29f5e52d47f9fd",
    "train_spikes_heldin_forward": "8e688930a0409c9f303a23696c03463e834eed2adc914a4d79529250790f922f",
    "train_spikes_heldout": "c43d9fb5722cb6d7a9b759b53cf421baad4d9866fb727a77d70a1982e5ee12a3",
    "train_spikes_heldout_forward": "fa741dcdbdcf7b70674cb24b93c0637f79d6c450a7a172708188aa3fd168afc9",
    "eval_spikes_heldin": "5f1ca725d1fd49ae1a318a453a99ac2e6864eabd9acb6ceb1cf518e2a829bb34",
}
ROLES = {"train": "original_train_only_metric_decoder_inference_inputs",
         "eval": "restricted_validation_observations_only"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def exact(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), label + " fields")


def hexhash(value):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "SHA256 syntax")
    return value


def canonical(value, *, exists=True):
    require(isinstance(value, (str, Path)), "Path type")
    p = Path(value)
    require(p.is_absolute() and p == p.resolve(strict=exists), "Canonical absolute unlinked path")
    return p


def signature(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def checked_file(path):
    p = canonical(path)
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "Ordinary singly linked file required")
    return p, s


def descriptor(value, *, cap=MAX_SOURCE_BYTES):
    exact(value, {"path", "bytes", "sha256"}, "Descriptor")
    require(type(value["bytes"]) is int and 0 < value["bytes"] <= cap, "Descriptor byte bound")
    hexhash(value["sha256"])
    canonical(value["path"])
    return value


def authenticate(value, *, cap=MAX_SOURCE_BYTES, capture=False):
    descriptor(value, cap=cap)
    p, before = checked_file(value["path"])
    require(before.st_size == value["bytes"], "File size drift")
    h = hashlib.sha256()
    chunks = []
    count = 0
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        require(signature(os.fstat(stream.fileno())) == signature(before), "File open identity drift")
        while True:
            block = stream.read(min(1024 * 1024, value["bytes"] - count + 1))
            if not block:
                break
            count += len(block)
            require(count <= value["bytes"], "File exceeded declared size")
            h.update(block)
            if capture:
                chunks.append(block)
        require(signature(os.fstat(stream.fileno())) == signature(before), "File read identity drift")
    require(signature(p.lstat()) == signature(before), "Named file identity drift")
    require(count == value["bytes"] and h.hexdigest() == value["sha256"], "File content drift")
    return b"".join(chunks) if capture else value


def file_descriptor(path, cap=MAX_SOURCE_BYTES):
    p, before = checked_file(path)
    require(0 < before.st_size <= cap, "Output byte bound")
    h = hashlib.sha256()
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        require(signature(os.fstat(stream.fileno())) == signature(before), "Output open drift")
        count = 0
        while True:
            block = stream.read(min(1024 * 1024, before.st_size - count + 1))
            if not block:
                break
            count += len(block)
            require(count <= before.st_size, "Output size drift")
            h.update(block)
        require(signature(os.fstat(stream.fileno())) == signature(before), "Output read drift")
    require(count == before.st_size and signature(p.lstat()) == signature(before), "Output named drift")
    return {"path": str(p), "bytes": count, "sha256": h.hexdigest()}


def source_identity():
    d = file_descriptor(Path(__file__).resolve(), MAX_METADATA_BYTES)
    return {"bytes": d["bytes"], "sha256": d["sha256"]}


def nongit(path):
    require(not any((p / ".git").exists() for p in (path, *path.parents)), "Private non-Git output required")


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def fresh_outputs(root, receipt, inputs):
    root = canonical(root, exists=False)
    receipt = canonical(receipt, exists=False)
    require(not root.exists() and not receipt.exists(), "Fresh output paths required")
    require(root.parent.is_dir() and receipt.parent.is_dir(), "Existing output parents required")
    nongit(root)
    nongit(receipt)
    require(disjoint(root, receipt), "Private receipt must be outside packet")
    for p in inputs:
        require(disjoint(root, p) and disjoint(root, p.parent), "Packet overlaps input parent")
        require(disjoint(receipt, p) and disjoint(receipt, p.parent), "Receipt overlaps input parent")
    return root, receipt


def write_json(path, value):
    body = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    require(len(body) <= MAX_METADATA_BYTES, "Metadata byte bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return file_descriptor(path, MAX_METADATA_BYTES)


def validate_identity(identity):
    exact(identity, {"conditions", "neurons", "ordered_trials"}, "Source identity")
    trials = identity["ordered_trials"]
    exact(trials, {"train", "val", "test"}, "Trial splits")
    seen = set()
    for name, length in (("train", 1721), ("val", 574), ("test", 574)):
        values = trials[name]
        require(isinstance(values, list) and len(values) == length and
                all(type(x) is int for x in values), "Trial split length/type")
        require(len(set(values)) == length and not seen.intersection(values), "Trial overlap")
        seen.update(values)
    neurons = identity["neurons"]
    exact(neurons, {"spikes", "heldout_spikes"}, "Neuron order")
    seen = set()
    for name, length in (("spikes", 137), ("heldout_spikes", 45)):
        values = neurons[name]
        require(isinstance(values, list) and len(values) == length and
                all(isinstance(x, str) for x in values), "Neuron count/type")
        require(len(set(values)) == length and not seen.intersection(values), "Neuron overlap")
        seen.update(values)
    require(isinstance(identity["conditions"], list) and len(identity["conditions"]) == 108,
            "Condition count")
    actual = {"trial_indices_sha256": digest(trials), "neuron_indices_sha256": digest(neurons),
              "conditions_sha256": digest(identity["conditions"]),
              "tensor_trial_indices_sha256": digest({"train": trials["train"], "eval": trials["val"]})}
    require(actual == ORDER_PINS, "Source split/neuron/condition order drift")
    return actual


def scientific_modules():
    import h5py
    import numpy as np
    return h5py, np


def validate_h5(handle, role, *, raw, h5py):
    shapes = dict(SHAPES[role])
    if raw:
        shapes.update(EXCLUDED_SOURCE_SHAPES[role])
    require(set(handle.keys()) == set(shapes), "HDF5 fields outside exact allowlist")
    require(len(handle.attrs) == 0, "HDF5 root attributes unsupported")
    for name, shape in shapes.items():
        require(isinstance(handle.get(name, getlink=True), h5py.HardLink), "HDF5 links unsupported")
        item = handle[name]
        require(isinstance(item, h5py.Dataset), "Only ordinary datasets supported")
        require(tuple(item.shape) == shape, "HDF5 shape/phase mismatch: " + name)
        require(item.dtype.kind in "iuf" and item.dtype.itemsize in (1, 2, 4, 8) and
                item.dtype.fields is None and item.dtype.subdtype is None and
                h5py.check_dtype(vlen=item.dtype) is None, "Numeric fixed-width dtype required")
        require(not item.is_virtual and not item.external and len(item.attrs) == 0,
                "External/virtual/attributed dataset unsupported")


def scan_dataset(item, expected, np, destination=None):
    """Same f8 C-order tensor digest as original prepare.py, streamed by rows."""
    h = hashlib.sha256(json.dumps(list(item.shape), separators=(",", ":")).encode())
    for start in range(0, item.shape[0], ROWS_PER_CHUNK):
        stop = min(start + ROWS_PER_CHUNK, item.shape[0])
        values = item[start:stop, :, :]
        require(tuple(values.shape) == (stop - start, *item.shape[1:]) and values.dtype == item.dtype,
                "Dataset read shape/dtype drift")
        require(bool(np.isfinite(values).all()) and bool((values >= 0).all()), "Invalid spike counts")
        canonical_values = np.asarray(values, dtype="<f8", order="C")
        h.update(canonical_values.tobytes(order="C"))
        if destination is not None:
            destination[start:stop, :, :] = values
    require(h.hexdigest() == expected, "Tensor content/order drift")
    return {"shape": list(item.shape), "dtype": item.dtype.str, "content_sha256": h.hexdigest()}


def project_file(source, output, role, h5py, np):
    before = checked_file(source["path"])[1]
    fd = os.open(source["path"], os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        require(signature(os.fstat(stream.fileno())) == signature(before), "Raw source open drift")
        with h5py.File(stream, "r") as original:
            validate_h5(original, role, raw=True, h5py=h5py)
            with h5py.File(output, "x") as projected:
                datasets = {}
                for name, shape in SHAPES[role].items():
                    item = original[name]
                    target = projected.create_dataset(name, shape=shape, dtype=item.dtype,
                        chunks=(min(ROWS_PER_CHUNK, shape[0]), shape[1], shape[2]),
                        compression="gzip", compression_opts=4, shuffle=False, track_times=False)
                    datasets[name] = scan_dataset(item, CONTENT_PINS[name], np, target)
                projected.flush()
        require(signature(os.fstat(stream.fileno())) == signature(before), "Raw source changed during projection")
    require(signature(Path(source["path"]).lstat()) == signature(before), "Raw source named drift")
    os.chmod(output, 0o444)
    d = file_descriptor(output, MAX_PACKET_BYTES)
    return {"bytes": d["bytes"], "sha256": d["sha256"], "datasets": datasets}


def expected_packet_fields():
    return {"schema", "dataset", "phase", "units", "geometry", "roles", "order", "projector", "files"}


def inspect_packet(manifest_path, manifest_sha256):
    """Authenticate a portable packet without opening any original source path."""
    manifest, s = checked_file(manifest_path)
    require(manifest.name == "PACKET.json", "Packet manifest name")
    body = authenticate({"path": str(manifest), "bytes": s.st_size,
                         "sha256": hexhash(manifest_sha256)}, cap=MAX_METADATA_BYTES, capture=True)
    packet = json.loads(body)
    exact(packet, expected_packet_fields(), "Packet")
    require(packet["schema"] == PACKET_SCHEMA and packet["dataset"] == "mc_maze" and
            packet["phase"] == "val" and packet["units"] == "spike_counts_per_20ms_bin", "Packet condition")
    require(packet["geometry"] == GEOMETRY and packet["roles"] == ROLES and
            packet["order"] == ORDER_PINS and packet["projector"] == source_identity(), "Packet identities")
    exact(packet["files"], set(RELATIVE_FILES.values()), "Packet files")
    root = manifest.parent
    expected_leaves = {"PACKET.json", *RELATIVE_FILES.values()}
    expected_directories = {"mc_maze", "mc_maze/val"}
    leaves, directories = set(), set()
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(base) / name
            require(not p.is_symlink(), "Packet symlink")
            rel = p.relative_to(root).as_posix()
            if name in dirs:
                directories.add(rel)
            else:
                checked_file(p)
                leaves.add(rel)
        require(leaves <= expected_leaves and directories <= expected_directories, "Packet extra path")
    require(leaves == expected_leaves and directories == expected_directories, "Packet path roster")
    h5py, np = scientific_modules()
    total = s.st_size
    for role, relative in RELATIVE_FILES.items():
        record = packet["files"][relative]
        exact(record, {"bytes", "sha256", "datasets"}, "Projected file")
        exact(record["datasets"], set(SHAPES[role]), "Projected datasets")
        d = {"path": str(root / relative), "bytes": record["bytes"], "sha256": record["sha256"]}
        authenticate(d, cap=MAX_PACKET_BYTES)
        total += d["bytes"]
        require(total <= MAX_PACKET_BYTES, "Whole packet byte bound")
        before = checked_file(d["path"])[1]
        fd = os.open(d["path"], os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            require(signature(os.fstat(stream.fileno())) == signature(before), "Projected open drift")
            with h5py.File(stream, "r") as handle:
                validate_h5(handle, role, raw=False, h5py=h5py)
                for name in SHAPES[role]:
                    require(scan_dataset(handle[name], CONTENT_PINS[name], np) == record["datasets"][name],
                            "Projected dataset metadata/content drift")
            require(signature(os.fstat(stream.fileno())) == signature(before), "Projected read drift")
        require(signature(Path(d["path"]).lstat()) == signature(before), "Projected named drift")
    return packet


def project(request_path, request_sha256):
    """Trusted operator preparation only; never launch a worker or scorer."""
    request_path, s = checked_file(request_path)
    request = json.loads(authenticate({"path": str(request_path), "bytes": s.st_size,
        "sha256": hexhash(request_sha256)}, cap=MAX_METADATA_BYTES, capture=True))
    exact(request, {"schema", "source", "output_root", "receipt"}, "Projection request")
    require(request["schema"] == REQUEST_SCHEMA, "Projection request schema")
    exact(request["source"], set(SOURCE_PINS), "Selected original sources")
    inputs = [request_path, Path(__file__).resolve()]
    for role, pin in SOURCE_PINS.items():
        d = descriptor(request["source"][role], cap=MAX_METADATA_BYTES if role in ("panel", "identity") else MAX_SOURCE_BYTES)
        require(all(d[k] == v for k, v in pin.items()), "Original source selection mismatch: " + role)
        inputs.append(Path(d["path"]))
    require(len(set(inputs)) == len(inputs), "Input path alias")
    root, receipt = fresh_outputs(request["output_root"], request["receipt"], inputs)
    identity = json.loads(authenticate(request["source"]["identity"], cap=MAX_METADATA_BYTES, capture=True))
    validate_identity(identity)
    authenticate(request["source"]["panel"], cap=MAX_METADATA_BYTES)
    # Whole raw-container authentication is privileged byte I/O, not restricted worker access.
    for role in ("train", "eval"):
        authenticate(request["source"][role])
    h5py, np = scientific_modules()
    root.mkdir(mode=0o755)
    (root / "mc_maze").mkdir(mode=0o755)
    (root / "mc_maze/val").mkdir(mode=0o755)
    files = {}
    for role, relative in RELATIVE_FILES.items():
        files[relative] = project_file(request["source"][role], root / relative, role, h5py, np)
    # Neither a failed second projection nor a drifting source can yield a ready manifest.
    for role in ("train", "eval"):
        authenticate(request["source"][role])
    packet = {"schema": PACKET_SCHEMA, "dataset": "mc_maze", "phase": "val",
              "units": "spike_counts_per_20ms_bin", "geometry": GEOMETRY, "roles": ROLES,
              "order": ORDER_PINS, "projector": source_identity(), "files": files}
    require(sum(x["bytes"] for x in files.values()) + MAX_METADATA_BYTES <= MAX_PACKET_BYTES,
            "Whole packet byte bound")
    manifest = write_json(root / "PACKET.json", packet)
    inspect_packet(manifest["path"], manifest["sha256"])
    report = {"schema": RECEIPT_SCHEMA, "status": "projected_and_authenticated",
              "request": {"path": str(request_path), "bytes": s.st_size, "sha256": request_sha256},
              "source": request["source"], "packet": manifest,
              "projector": packet["projector"],
              "numeric_source_fields_read": {k: list(v) for k, v in SHAPES.items()},
              "raw_container_bytes_authenticated": True,
              "excluded_source_numeric_fields_read": False,
              "worker_raw_access_authorized": False,
              "runtime_qualified": False}
    return {"packet": manifest, "receipt": write_json(receipt, report)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("project")
    p.add_argument("--request", required=True)
    p.add_argument("--sha256", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("--packet", required=True)
    p.add_argument("--sha256", required=True)
    args = parser.parse_args()
    result = project(args.request, args.sha256) if args.command == "project" else inspect_packet(args.packet, args.sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
