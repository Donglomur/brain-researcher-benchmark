#!/usr/bin/env python3
"""Prepare operator Movie10 panel metadata from the four pinned original HDF5s.

No acquisition, response-array read, fitting, candidate execution or readiness claim.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
from pathlib import Path
import re

import evaluate as ev

# Browser-visible pointer text at the exact source commit. Reconstructed bytes
# independently match the Git blob IDs already pinned in NEURAL-039/task.json.
# These are pointer identities, not newly acquired HDF5 SHA256 observations.
POINTERS = {
    "sub-01": ("v2/g2", 92248907, "679e60674df5d669e09467c3a84fbba1", "40047fdf418dfea06a7435eb2690d750ec99f3eb"),
    "sub-02": ("V0/G6", 92262363, "5fc31c031b40e5c032c145816dedeb3d", "480814bec3bbfdf7a05d62fdeecb6137b16b248f"),
    "sub-03": ("KV/QJ", 92197356, "3748698c8261e92bf3be29944829543b", "cc42fbfc511d72512605886d4455679da19c0602"),
    "sub-05": ("F5/6w", 92241379, "1b16eaea10be5a58052b891806cf10e6", "634e57160c2482ba706e1233fab185f3caf8d99f"),
}


def source_records():
    """Fixed original payload expectations; no filesystem or network access."""
    records = {}
    for subject in ev.SUBJECTS:
        directory, size, md5, blob = POINTERS[subject]
        key = f"MD5E-s{size}--{md5}.h5"
        pointer = f"../../../.git/annex/objects/{directory}/{key}/{key}".encode("ascii")
        git_id = hashlib.sha1(b"blob " + str(len(pointer)).encode("ascii") + b"\0" + pointer).hexdigest()
        if git_id != blob:
            raise ValueError("Pinned source pointer identity differs")
        source_path = (f"fmri/{subject}/func/{subject}_task-movie10_space-MNI152NLin2009cAsym_"
                       "atlas-Schaefer18_parcel-1000Par7Net_bold.h5")
        records[subject] = {
            "file": f"{subject}_movie10.h5", "bytes": size, "md5": md5,
            "pointer_bytes": len(pointer), "pointer_git_sha1": git_id,
            "pointer_sha256": hashlib.sha256(pointer).hexdigest(),
            "source_path": source_path,
            "source_url": ("https://raw.githubusercontent.com/courtois-neuromod/"
                           f"algonauts_2025.competitors/{ev.SOURCE_COMMIT}/{source_path}"),
        }
    return records


def _prepare(source_root, expected, h5py):
    """Internal dependency seam for generated controls; CLI fixes expected sources."""
    ev.fields(expected, ev.SUBJECTS)
    paths = ev.exact_directory(source_root, (f"{s}_movie10.h5" for s in ev.SUBJECTS))
    panel = {"schema": "neural039_movie10_panel_v1", "source_commit": ev.SOURCE_COMMIT,
             "subjects": {}}
    with ExitStack() as stack:
        opened = {}
        # Hash all four originals before parsing any HDF5 container. The same
        # open descriptors are retained through metadata inspection; ev.open_file
        # checks inode/stat identity again before the function can return.
        for subject in ev.SUBJECTS:
            item = expected[subject]
            if (item["file"] != f"{subject}_movie10.h5" or type(item["bytes"]) is not int
                    or item["bytes"] <= 0 or not re.fullmatch(r"[0-9a-f]{32}", item["md5"])):
                raise ValueError("Exact positive subject-specific payload identity required")
            stream = stack.enter_context(ev.open_file(paths / item["file"], item["bytes"]))
            md5, sha256, extent = hashlib.md5(), hashlib.sha256(), 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                extent += len(block)
                md5.update(block)
                sha256.update(block)
            if extent != item["bytes"] or md5.hexdigest() != item["md5"]:
                raise ValueError(f"Original payload identity differs for {subject}")
            stream.seek(0)
            opened[subject] = stream
            panel["subjects"][subject] = {"file": item["file"], "bytes": extent,
                                           "sha256": sha256.hexdigest(), "datasets": {}}
        for subject in ev.SUBJECTS:
            with h5py.File(opened[subject], "r") as handle:
                inventory = panel["subjects"][subject]["datasets"]
                for key in handle.keys():
                    if not isinstance(handle.get(key, getlink=True), h5py.HardLink):
                        raise ValueError("Only local hard-linked HDF5 datasets are admitted")
                    dataset = handle[key]
                    if (not isinstance(dataset, h5py.Dataset) or dataset.dtype.str != "<f4"
                            or dataset.is_virtual or dataset.external):
                        raise ValueError("Original local float32 dataset schema required")
                    # Shape/dtype/storage metadata only; do not index dataset data.
                    inventory[key] = list(dataset.shape)
        ev.validate_panel(panel)
    return panel


def prepare(source_root, h5py):
    return _prepare(source_root, source_records(), h5py)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("sources", help="Emit fixed pointer-derived source metadata only")
    build = sub.add_parser("prepare", help="Authenticate local originals and inspect HDF5 metadata")
    build.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "sources":
        result = {"schema": "neural039_movie10_original_source_expectations_v1",
                  "source_commit": ev.SOURCE_COMMIT, "subjects": source_records(),
                  "payload_bytes": sum(x["bytes"] for x in source_records().values()),
                  "payloads_acquired": False, "payload_schema_verified": False,
                  "pointer_evidence": "browser-visible text reconstructed to previously pinned Git blob IDs"}
    else:
        import h5py
        result = prepare(args.source_root, h5py)
    body = ev.canonical(result)
    with ev.ordinary(args.output).open("xb") as output:
        output.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
