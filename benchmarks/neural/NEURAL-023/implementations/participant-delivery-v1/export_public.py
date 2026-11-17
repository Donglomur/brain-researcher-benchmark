#!/usr/bin/env python3
"""Copy the exact NEURAL-023 public packet and recovered participant sources.

This trusted-operator utility performs opaque byte authentication and copying.
It does not parse numerical values, open private files, or execute a method.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
SOURCE_PINS_SHA256 = "2bf28a88429234542a35205aeff565ec6e04072791c9ee1104134992362dac9d"
ASSET_PINS = {
    "source.npz": {"bytes": 7705272, "sha256": "839f7bf5b5bde7feed560f0e2f5a6fe9b0fb3b75d8f92f1bbff9c78a789a2bb2"},
    "calibration.npz": {"bytes": 1236872, "sha256": "05f7e4535606d4057b48a00b74eb919078875ab7dbcb0f06639174a7216ccac3"},
    "assessment.npz": {"bytes": 8752360, "sha256": "af0cb2d84945917009d059c2393ebb36e675ce6602f371507251a6f00347a1bb"},
    "manifest.json": {"bytes": 1375, "sha256": "3f39ed1105f95ec98dff9afa68bfaccc437de6bd8bbeb111d51ec0eb31a1cd04"},
}
PARTICIPANT_GUIDE = """# NEURAL-023 participant packet

Use source.npz, calibration.npz, assessment.npz and manifest.json under TASK.md.
The packet has all 22,091 assessment endpoints, 96 channels and the original
20 ms trailing x/y velocity target in m/s. It covers one exposed Indy day pair.

packet_io.observed_packet(path, pin, kind) validates and loads each input using
the pin in PUBLIC_ASSETS.json and kind source, calibration, or assessment.
Its endpoint_bin values become case_id in a completed predictions.npz. The
assessment packet has no velocity labels. Preserve channel order and the
packet coordinate convention; endpoint_bin is an edge ID, not a count-row ID.

reference_core.py and REFERENCE_PROTOCOL.json preserve all seven historical
reference recipes. The full panel fits 51 ridge coefficients; export never
executes it. Scientific baseline execution needs its own bounded protocol.
The numerical environment in ENVIRONMENT.json is historical/proposed and has
not been installed or qualified by this export.

The ORIGINAL_* documents and TASK.md describe historical services as lineage.
There is no program execution service or private grader in this public packet.
The separate external-artifact-v1 scorer accepts completed prediction files;
only the operator supplies its private assessment and saved reference assets.

This packet supports numerical investigation/program input. It does not supply
a direct-observation controller, typed viewer, frozen-program isolation or
training-provenance verification. A file score establishes none of those modes.

Exposure: assessment counts reveal NEURAL-024 future-neural targets. Never
combine the two participant mounts or claim NEURAL-024 hidden after this access.
One animal/day pair is not a population or later-session evaluation.
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def literal(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts,
            "Use an absolute path without parent traversal")
    require(not any(p.is_symlink() for p in (path, *path.parents)),
            "Symlink paths and ancestors are not accepted")
    return path


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def snapshot(path, expected=None, cap=10_000_000):
    """Hold only a bounded ordinary file, then verify the frozen byte identity."""
    path = literal(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= cap, "Bounded ordinary single-link file required")
        if expected is not None:
            require(before.st_size == expected["bytes"], "Pinned file length mismatch")
        pieces, remaining = [], before.st_size
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            require(bool(chunk), "File truncated during snapshot")
            pieces.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "File grew during snapshot")
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        require(all(getattr(before, f) == getattr(after, f) for f in fields),
                "File changed during snapshot")
    finally:
        os.close(fd)
    body = b"".join(pieces)
    if expected is not None:
        require(pin(body) == expected, "Pinned file digest mismatch")
    return body


def participant_sources():
    metadata = snapshot(HERE / "SOURCE_PINS.json", cap=20000)
    require(pin(metadata)["sha256"] == SOURCE_PINS_SHA256, "Recovery manifest changed")
    files = json.loads(metadata)["files"]
    # These are code-bundled immutable source pins, never operator-supplied pins.
    return {name: snapshot(HERE / "participant" / name, expected, cap=20000)
            for name, expected in files.items()}


def write_new(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def export_public(inputs, output):
    """Validate all inputs before creating output; only a final receipt completes it."""
    inputs, output = literal(inputs), literal(output)
    require(inputs.is_dir() and output.parent.is_dir(), "Existing input and output-parent directories required")
    require(not output.exists(), "Output must be new; existing output is never overwritten")
    # No listing, recursive search, private pathname construction or target access.
    assets = {name: snapshot(inputs / name, expected) for name, expected in ASSET_PINS.items()}
    sources = participant_sources()
    files = assets | sources | {"README.md": PARTICIPANT_GUIDE.encode("utf-8")}
    output.mkdir(mode=0o700)
    public = output / "public"
    public.mkdir(mode=0o700)
    for name, body in files.items():
        write_new(public / name, body)
        snapshot(public / name, pin(body))
    receipt = {
        "schema_version": 1, "candidate_id": "NEURAL-023",
        "status": "exact_public_packet_exported", "files": {name: pin(body) for name, body in files.items()},
        "source_pins_sha256": SOURCE_PINS_SHA256,
        "scope": {"animals": 1, "day_pairs": 1, "assessment_rows": 22091,
                  "channels": 96, "bin_seconds": 0.02, "exposed_development": True},
        "private_files_opened": 0, "numerical_arrays_loaded": 0,
        "scientific_fits": 0, "candidate_programs_executed": 0,
        "export_is_execution_isolation": False, "scientific_qualification": False,
        "cross_task_exposure": "NEURAL-023 assessment counts expose NEURAL-024 future-neural targets",
    }
    public.chmod(0o555)
    write_new(output / "receipt.json", (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path, help="Exact public input directory")
    parser.add_argument("--output", required=True, type=Path, help="New external delivery directory")
    args = parser.parse_args()
    result = export_public(args.inputs, args.output)
    print(json.dumps({"status": result["status"], "files": len(result["files"]),
                      "bytes": sum(p["bytes"] for p in result["files"].values())}))


if __name__ == "__main__":
    main()
