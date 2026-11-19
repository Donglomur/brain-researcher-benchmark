"""Operator-private serialization bridge to the retained retinal target producer.

This restores the already-produced field-local target layout. It performs no
preprocessing, fitting, split generation, prediction adaptation, or scoring.
The enclosing operator must separately authenticate this programme and runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import types

SOURCE_PINS = {
    "input_binding": (10007, "f4bd10b4c40cef74835001937ce3dc5cb4bd16fcc061b4138696b39827a707d9"),
    "scorer": (10745, "b2ac5156fe01d600d32b35e0bbf716bd6dea69f59b6bd3a062a6a6c2b0bb126c"),
}
TARGET_LAYOUT = "observed_site_targets[site,frame0..1023]; site.field determines the15360-row field block; all inactive entries use the source mask"
OUTPUT_CAP = 524288


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_pinned(pin, cap):
    require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "file descriptor keys")
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= cap, "file extent")
    require(type(pin["sha256"]) is str and len(pin["sha256"]) == 64 and set(pin["sha256"]) <= set("0123456789abcdef"), "file digest syntax")
    fd = os.open(pin["path"], os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"], "ordinary exact file")
        chunks, remaining = [], pin["bytes"] + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        body = b"".join(chunks)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(all(getattr(before, key) == getattr(after, key) for key in fields), "file changed during read")
        require(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"], "file identity")
        return body
    finally:
        os.close(fd)


def strict_json(body):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def constant(value):
        raise ValueError("nonfinite JSON constant")

    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def source_module(name, pin):
    require((pin["bytes"], pin["sha256"]) == SOURCE_PINS[name], "retained source identity")
    body = read_pinned(pin, 16384)
    module = types.ModuleType("_retinal_target_binding_" + name)
    module.__file__ = pin["path"]
    exec(compile(body, pin["path"], "exec"), module.__dict__)
    return module


def decode_observed(body):
    import numpy as np
    require(len(body) <= 2 * 1024**2, "target file cap")
    stream = io.BytesIO(body)
    version = np.lib.format.read_magic(stream)
    readers = {(1, 0): np.lib.format.read_array_header_1_0,
               (2, 0): np.lib.format.read_array_header_2_0}
    require(version in readers, "supported ordinary NPY version")
    shape, fortran, dtype = readers[version](stream, max_header_size=4096)
    require(shape == (147, 1024) and fortran is False and dtype.str == "<f8", "bounded NPY target header")
    payload = body[stream.tell():]
    require(len(payload) == 147 * 1024 * 8, "exact NPY target payload extent")
    return np.frombuffer(payload, dtype="<f8").reshape(147, 1024).copy(order="C")


def array_descriptor(array, order=False):
    out = {"shape": list(array.shape), "dtype": array.dtype.str, "bytes": array.nbytes,
           "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}
    if order:
        out["order"] = "C"
    return out


def restore_private_binding(observed, private, participant, expected_identity, scorer):
    """Restore only labels/mask/sites/splits needed by input_binding.operator_packet."""
    import numpy as np
    require(private["schema"] == "jaxley-private-pre-model-inputs-v1" and private["contains_all_private_targets"] is True,
            "private target metadata schema")
    require(participant["schema"] == "jaxley-original-model-operation-input-v1" and participant["test_targets_included"] is False,
            "participant target exclusion")
    require(set(participant["arrays"]) == {"images", "currents", "mask", "train_targets", "val_targets"}, "participant array roster")
    require(private["cell_id"] == participant["cell_id"] == "20161028_1", "cell identity")
    require(private["target_layout"] == TARGET_LAYOUT, "serialized target layout")
    require(private["sites"] == participant["sites"] and private["splits"] == participant["splits"], "private participant identities")
    sites, splits = private["sites"], private["splits"]
    scorer.validate_sites(sites)
    scorer.validate_split(splits)
    require([len(splits[k]) for k in ("train", "val", "test")] == [12185, 3047, 128], "frozen split extents")
    require(digest_json({"sites": sites, "splits": splits}) == private["identity_sha256"] == participant["identity_sha256"] == expected_identity,
            "frozen split and site identity")
    require(type(observed) is np.ndarray and observed.shape == (147, 1024) and observed.dtype.str == "<f8" and observed.flags.c_contiguous,
            "observed target array layout")
    require(bool(np.isfinite(observed).all()), "finite observed targets")
    require(array_descriptor(observed, order=True) == private["arrays"]["observed_site_targets"], "observed target numeric identity")
    labels = np.zeros((15360, 147), dtype=np.float64)
    mask = np.zeros_like(labels)
    for site_index, site in enumerate(sites):
        start = (site["field"] - 1) * 1024
        labels[start:start + 1024, site_index] = observed[site_index]
        mask[start:start + 1024, site_index] = 1.0
    require(array_descriptor(mask) == participant["arrays"]["mask"], "derived mask numeric identity")
    return {"labels": labels, "mask": mask, "sites": sites, "splits": splits}


def load_operator(manifest):
    require(type(manifest) is dict and set(manifest) == {"schema", "identity_sha256", "inputs", "sources"}, "binding manifest keys")
    require(manifest["schema"] == "jaxley-private-target-sidecar-binding-v1", "binding manifest schema")
    require(set(manifest["inputs"]) == {"private_metadata", "participant_metadata", "observed"}, "input roster")
    require(set(manifest["sources"]) == set(SOURCE_PINS), "source roster")
    inputs = manifest["inputs"]
    private = strict_json(read_pinned(inputs["private_metadata"], 262144))
    participant = strict_json(read_pinned(inputs["participant_metadata"], 262144))
    for name, key in (("observed", "observed_site_targets.npy"), ("participant_metadata", "model_metadata.json")):
        require({k: inputs[name][k] for k in ("bytes", "sha256")} == private["files"][key], "serialized file descriptor join")
    binding = source_module("input_binding", manifest["sources"]["input_binding"])
    scorer = source_module("scorer", manifest["sources"]["scorer"])
    observed = decode_observed(read_pinned(inputs["observed"], 2 * 1024**2))
    restored = restore_private_binding(observed, private, participant, manifest["identity_sha256"], scorer)
    return binding.operator_packet(restored)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", required=True, help="fresh evaluator-private target JSON")
    args = parser.parse_args()
    os.umask(0o077)
    size = os.stat(args.manifest, follow_symlinks=False).st_size
    manifest = strict_json(read_pinned({"path": args.manifest, "bytes": size, "sha256": args.manifest_sha256}, 16384))
    operator = load_operator(manifest)
    body = (json.dumps(operator, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    require(len(body) <= OUTPUT_CAP, "private target output cap")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        # Preserve any partial output for the enclosing owner's failure receipt.
        raise
    print(json.dumps({"schema": "jaxley-private-target-serialization-result-v1", "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(), "identity_sha256": manifest["identity_sha256"],
                      "operator_private": True, "score_computed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
