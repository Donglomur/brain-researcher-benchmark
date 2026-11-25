#!/usr/bin/env python3
"""Prepare explicit CA1.m-shaped MAT arrays; never acquire data or infer animal IDs.

Requires an existing scipy runtime. The named MAT root is deliberately explicit:
source wrapper Hippocampus_data.mat and supplement filenames do not establish that
an uninspected supplementary MAT file has this shape.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from mint_reference import TASK_ID, validate_packet


def _file_state(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _load_bound_mat(data_path, loadmat):
    """Hash and decode one file description, refusing changed source identity."""
    with data_path.open("rb") as stream:
        before = _file_state(os.fstat(stream.fileno()))
        source_hash = hashlib.sha256()
        for block in iter(lambda: stream.read(64 * 1024), b""):
            source_hash.update(block)
        stream.seek(0)
        loaded = loadmat(stream, simplify_cells=True)
        if (_file_state(os.fstat(stream.fileno())) != before or
                _file_state(data_path.stat()) != before):
            raise ValueError("MAT source changed during hashing or decoding")
    return loaded, source_hash.hexdigest()


def prepare(data_path, root_variable, identities):
    import numpy as np
    from scipy.io import loadmat

    if not isinstance(root_variable, str) or not root_variable:
        raise ValueError("An explicit root variable is required")
    data_path = Path(data_path)
    loaded, source_sha256 = _load_bound_mat(data_path, loadmat)
    root = loaded.get(root_variable)
    if not isinstance(root, dict) or not root:
        raise ValueError("Named MAT root must be a nonempty session struct")
    if set(root) != set(identities):
        raise ValueError("Identity map must cover every MAT session field exactly")
    sessions = []
    for sid in sorted(root):
        raw = root[sid]
        if not isinstance(raw, dict) or "Position" not in raw or "R_neuron_binned" not in raw:
            raise ValueError("Every session needs the fields named by CA1.m")
        neural = np.asarray(raw["R_neuron_binned"])
        position = np.asarray(raw["Position"])
        if neural.ndim != 2 or neural.shape[0] < 2:
            raise ValueError("R_neuron_binned must be neurons by samples, with >=2 neurons")
        if position.ndim > 2 or (position.ndim == 2 and 1 not in position.shape):
            raise ValueError("Position must be a vector")
        position = position.reshape(-1)
        if neural.shape[1] != position.size:
            raise ValueError("Position and neural sample counts differ")
        for array in (neural, position):
            if array.dtype.kind not in "iuf" or not np.isfinite(array).all() or (array < 0).any() or not np.equal(array, np.floor(array)).all():
                raise ValueError("Only finite nonnegative integer bin labels are accepted; no rebinning or rounding")
            if (array > 2 ** 53).any():
                raise ValueError("Bin labels exceed exact JSON numeric range")
        identity = identities[sid]
        if set(identity) != {"animal_id", "neuron_ids"} or len(identity["neuron_ids"]) != neural.shape[0]:
            raise ValueError("Explicit animal and complete neuron identities are required")
        sessions.append({"session_id": sid, "animal_id": identity["animal_id"], "neuron_ids": identity["neuron_ids"], "sample_ids": [f"{sid}:column:{i + 1}" for i in range(position.size)], "ordering": "acquisition_order", "stimulus": position.astype(object).tolist(), "neural": neural.T.astype(object).tolist()})
        # Avoid rounding nonintegral values: exactness already checked above.
        sessions[-1]["stimulus"] = [int(x) for x in sessions[-1]["stimulus"]]
        sessions[-1]["neural"] = [[int(x) for x in row] for row in sessions[-1]["neural"]]
    packet = {"schema_version": 1, "task_id": TASK_ID, "data_kind": "operator_prepared_unqualified", "expected_session_ids": sorted(root), "provenance": {"source": str(data_path.resolve()), "file_sha256": source_sha256, "root_variable": root_variable, "binning_status": "fixed_input_labels_native_provenance_unverified", "sample_id_origin": "MAT column indices; not verified trial identities", "identity_status": "operator supplied, not independently authenticated"}, "sessions": sessions}
    validate_packet(packet)
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--root-variable", required=True)
    parser.add_argument("--identities", type=Path, required=True)
    args = parser.parse_args()
    packet = prepare(args.input, args.root_variable, json.loads(args.identities.read_text()))
    args.output.write_text(json.dumps(packet, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
