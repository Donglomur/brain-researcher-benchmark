"""Deterministic full-panel projection, never fitting/scoring/normalization.

The production entry point requires a root-selected closed source-manifest pin
and the frozen DESIGN pin. It authenticates every metadata join before decoding
source NPYs, then selects all 1,200 design columns and transposes primitive f32.
The full three-person independently selected ROI union is mandatory. No partial
panel switch exists. A failed build leaves incomplete owned files without a
binding; it cannot become a gradeable packet by accident.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np

from interface import capture_regular, write_json_fresh
from data_io import (COLUMN_PROOF_PIN, COUNTS, DESIGN_PIN, FEATURE_NAMES, InputError,
                     NATIVE_COLUMNS, PACKET_CAP, SUBJECTS, checked_bytes, checked_json,
                     pin, read_primitive_npy, safe_path, validate_features, validate_rows,
                     validate_voxels)

IT_COLUMNS = ("glasser-TE1p", "glasser-TE2p", "glasser-FFC", "glasser-VVC", "glasser-VMV2",
              "glasser-VMV3", "glasser-PHA1", "glasser-PHA2", "glasser-PHA3")
ROI_COLUMNS = ("row_index", "voxel_id", "subject_id", "V1", *IT_COLUMNS)
STIMULUS_COLUMNS = ("trial_type", "session", "run", "subject_id", "trial_id", "stimulus", "concept")


def _csv(body, fields):
    try:
        reader = csv.DictReader(io.StringIO(body.decode("utf-8"), newline=""))
        if tuple(reader.fieldnames or ()) != fields:
            raise InputError("source CSV columns differ")
        for row in reader:
            if set(row) != set(fields) or any(value is None for value in row.values()):
                raise InputError("malformed source CSV row")
            yield row
    except (UnicodeError, csv.Error, TypeError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("source CSV decode") from exc


def roi_projection_from_csv(body, sid):
    """Reconstruct complete independent union membership, not response selection."""
    if sid not in SUBJECTS:
        raise InputError("source participant")
    union, voxel_ids, row_count = [], set(), 0
    for i, row in enumerate(_csv(body, ROI_COLUMNS)):
        try:
            native, voxel, subject = int(row["row_index"]), int(row["voxel_id"]), int(row["subject_id"])
        except ValueError as exc:
            raise InputError("source ROI identity integer") from exc
        if native != i or voxel < 0 or voxel in voxel_ids or subject != int(sid):
            raise InputError("complete native ROI identity/row order")
        voxel_ids.add(voxel)
        if any(row[k] not in ("0", "1") for k in ("V1", *IT_COLUMNS)):
            raise InputError("binary independent ROI membership required")
        v1, it = row["V1"] == "1", any(row[k] == "1" for k in IT_COLUMNS)
        if v1 or it:
            union.append({"projection_row": len(union), "native_row_index": native,
                          "voxel_id": voxel, "subject_id": sid, "V1": v1, "IT": it})
        row_count += 1
    if row_count != COUNTS[sid]["native"]:
        raise InputError("full native source ROI table required")
    validate_voxels(union, sid)
    return union


def verify_stimulus_join(body, sid, selected_rows, concepts):
    positions, selected = {}, []
    total = 0
    for i, row in enumerate(_csv(body, STIMULUS_COLUMNS)):
        try:
            session, run = int(row["session"]), int(row["run"])
            trial, subject = int(row["trial_id"]), int(row["subject_id"])
        except ValueError as exc:
            raise InputError("stimulus integer identifiers") from exc
        if (trial != i or subject != int(sid) or not 1 <= session <= 12 or not 1 <= run <= 10
                or row["trial_type"] not in ("train", "test")):
            raise InputError("complete native stimulus sequence identity")
        key = (session, run)
        position = positions.get(key, 0)
        positions[key] = position + 1
        if row["trial_type"] == "test":
            selected.append({"concept": row["concept"], "image": row["stimulus"],
                             "session": session, "run": run, "trial_id": trial,
                             "within_run_position": position})
        total += 1
    if total != NATIVE_COLUMNS or selected != selected_rows:
        raise InputError("frozen design/full-sequence stimulus join")
    validate_rows(selected, concepts)


def project_columns_for_generated_checks(array, trial_ids):
    """Generic primitive copy also tested with tiny invented arrays.

    The production caller separately enforces all 3 fixed native geometries and
    all 1,200 frozen selected columns; this function does not admit a task.
    Values, including nonfinite bit patterns, are preserved without arithmetic.
    """
    if not isinstance(array, np.ndarray) or array.ndim != 2 or array.dtype.str != "<f4":
        raise InputError("primitive little-endian float32 source required")
    if (not isinstance(trial_ids, list) or not trial_ids
            or any(type(i) is not int or not 0 <= i < array.shape[1] for i in trial_ids)
            or len(set(trial_ids)) != len(trial_ids)):
        raise InputError("unique in-range selected column identities")
    return np.array(array[:, trial_ids].T, dtype="<f4", order="C", copy=True)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


class _Budget:
    def __init__(self):
        self.used = 0

    def reserve(self, size):
        if type(size) is not int or size < 0 or self.used + size > PACKET_CAP:
            raise InputError("90 MB total new packet cap")
        self.used += size


def _write_json(path, value, budget):
    body = _json_bytes(value)
    budget.reserve(len(body))
    write_json_fresh(path, value, cap=max(1, len(body)))
    captured = capture_regular(path, cap=max(1, len(body)))
    if captured != body:
        raise InputError("fresh JSON serialization mismatch")
    return {"file": Path(path).name, "bytes": len(captured), "sha256": hashlib.sha256(captured).hexdigest()}


class _BoundedNPYWriter:
    def __init__(self, stream, budget):
        self.stream, self.budget = stream, budget
        self.bytes = 0
        self.digest = hashlib.sha256()

    def write(self, body):
        self.budget.reserve(len(body))
        n = self.stream.write(body)
        if n != len(body):
            raise InputError("incomplete prepared NPY write")
        self.bytes += n
        self.digest.update(body)
        return n

    def flush(self):
        self.stream.flush()


def _write_npy(path, array, budget):
    # O_EXCL plus O_NOFOLLOW prevents reused/dangling output paths. NumPy sees
    # only the bounded writer, so every output byte is charged before writing.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        writer = _BoundedNPYWriter(stream, budget)
        np.save(writer, array, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
        state = os.fstat(stream.fileno())
        named = os.lstat(path)
        if state.st_size != writer.bytes or (state.st_dev, state.st_ino) != (named.st_dev, named.st_ino):
            raise InputError("prepared NPY named identity")
    return {"file": Path(path).name, "bytes": writer.bytes, "sha256": writer.digest.hexdigest(),
            "shape": list(array.shape), "dtype": "<f4"}


def _source_metadata(package_root, shared_root, shared_manifest_pin, design_pin, repository_root):
    root, source_root, repository = Path(package_root), Path(shared_root), Path(repository_root)
    if pin(design_pin) != DESIGN_PIN:
        raise InputError("production frozen DESIGN pin required")
    design = checked_json(safe_path(root, "private/DESIGN.json"), design_pin)
    if (not isinstance(design, dict) or design.get("schema") != "neural052_design_v1"
            or design.get("all_image_features_exact15") is not True or design.get("neural_response_values_read") is not False):
        raise InputError("frozen design identity")
    feature_record = {"feature_names": design["feature_names"], "concept_features": design["concept_features"]}
    concepts = validate_features(feature_record)
    source_pins = design.get("source_pins")
    if not isinstance(source_pins, list) or len(source_pins) != 7:
        raise InputError("complete independent design provenance required")
    for d in source_pins:
        checked_bytes(safe_path(repository, d["path"]), d)
    ds = design.get("subjects")
    if not isinstance(ds, list) or [s.get("subject_id") for s in ds] != list(SUBJECTS):
        raise InputError("frozen complete design participants")
    manifest = checked_json(safe_path(source_root, "SHARED_MANIFEST.json"), shared_manifest_pin)
    if (not isinstance(manifest, dict) or manifest.get("schema") != "things_fmri_full_roi_source_v1"
            or manifest.get("response_values_interpreted") is not False):
        raise InputError("closed complete shared source identity")
    ss = manifest.get("subjects")
    if not isinstance(ss, list) or [s.get("subject_id") for s in ss] != list(SUBJECTS):
        raise InputError("full source participants required")
    proof_desc = manifest.get("column_identity_proof")
    if pin(proof_desc) != COLUMN_PROOF_PIN:
        raise InputError("frozen native column proof pin")
    proof = checked_json(safe_path(repository, proof_desc["path"]), proof_desc)
    if (proof.get("schema") != "things_native_columns_v1" or proof.get("status") != "complete"
            or proof.get("serialized_globals_executed") is not False
            or not isinstance(proof.get("subjects"), list)
            or [s.get("subject_id") for s in proof["subjects"]] != list(SUBJECTS)):
        raise InputError("complete native-column evidence required")
    # The pinned acquisition receipt and plan are metadata provenance, not a
    # substitute for the full byte/hash and geometry checks below.
    for key in ("intake_receipt", "plan"):
        d = manifest.get(key)
        checked_bytes(safe_path(repository, d["path"]), d)
    prepared_metadata = []
    for source, planned, axis in zip(ss, ds, proof["subjects"]):
        sid = source["subject_id"]
        if (source.get("column_identity_proof") != proof_desc
                or axis.get("native_trial_columns_exact") is not True
                or axis.get("column_order") != "integer trial IDs 0 through 9839 in ascending order"
                or axis.get("axis0_leading_metadata_column") != "voxel_id"
                or pin(axis.get("stimuli")) != pin(source.get("source_stimulus_pin"))
                or pin(planned.get("source_stimuli")) != pin(source.get("source_stimulus_pin"))):
            raise InputError("native column/stimulus identity join")
        roi_pin, stimulus_pin = source["source_roi_pin"], source["source_stimulus_pin"]
        roi_body = checked_bytes(safe_path(repository, roi_pin["path"]), roi_pin)
        expected_voxels = roi_projection_from_csv(roi_body, sid)
        voxels_desc = source["voxels"]
        voxels = checked_json(safe_path(source_root, voxels_desc["file"]), voxels_desc)
        if voxels != expected_voxels:
            raise InputError("source projection does not equal full independent native ROI union")
        stimulus = checked_bytes(safe_path(repository, stimulus_pin["path"]), stimulus_pin)
        copy_desc = source["stimuli"]
        copied = checked_bytes(safe_path(source_root, copy_desc["file"]), copy_desc)
        if copied != stimulus or pin(copy_desc) != pin(stimulus_pin):
            raise InputError("copied/original stimulus bytes differ")
        verify_stimulus_join(stimulus, sid, planned["rows"], concepts)
        response = source["responses"]
        if response.get("shape") != [COUNTS[sid]["union"], 9840] or response.get("dtype") != "<f4":
            raise InputError("full native source response geometry required")
        pin(response)
        safe_path(source_root, response["file"])
        prepared_metadata.append({"subject_id": sid, "rows": planned["rows"], "voxels": voxels})
    return design, manifest, feature_record, prepared_metadata


def prepare_packet(package_root, shared_root, shared_manifest_pin, design_pin, repository_root):
    """Build exactly public/input plus private/PACKET_BINDING.json, fresh only."""
    root, source_root = Path(package_root), Path(shared_root)
    output = safe_path(root, "public/input")
    binding_path = safe_path(root, "private/PACKET_BINDING.json")
    if output.exists() or output.is_symlink() or binding_path.exists() or binding_path.is_symlink():
        raise InputError("preparation destinations must be fresh")
    if not output.parent.is_dir() or not binding_path.parent.is_dir():
        raise InputError("existing package public/private directories required")
    design, source, features, metadata = _source_metadata(
        root, source_root, shared_manifest_pin, design_pin, repository_root)
    budget = _Budget()
    minimum = sum(1200 * COUNTS[s]["union"] * 4 + 256 for s in SUBJECTS)
    minimum += len(_json_bytes(features)) + sum(len(_json_bytes(m)) for m in metadata)
    if minimum + 1_000_000 > PACKET_CAP:
        raise InputError("complete projected packet cannot fit fixed bound")
    output.mkdir(exist_ok=False)
    feature_desc = _write_json(output / "features.json", features, budget)
    subjects, files = [], [dict(feature_desc, file="public/input/" + feature_desc["file"])]
    for original, meta in zip(source["subjects"], metadata):
        sid = original["subject_id"]
        d = original["responses"]
        source_array = read_primitive_npy(safe_path(source_root, d["file"]), d,
                                           [COUNTS[sid]["union"], 9840], 250_000_000)
        projected = project_columns_for_generated_checks(source_array, [r["trial_id"] for r in meta["rows"]])
        del source_array
        if projected.shape != (1200, COUNTS[sid]["union"]):
            raise InputError("complete projected panel geometry")
        # Preserve every value unchanged. Finiteness is checked by the future
        # loader; no missing-value repair, summary or statistical test occurs.
        responses = _write_npy(output / f"sub-{sid}_responses.npy", projected, budget)
        del projected
        md = _write_json(output / f"sub-{sid}_metadata.json", meta, budget)
        subjects.append({"subject_id": sid, "responses": responses, "metadata": md})
        files.extend(dict(d, file="public/input/" + d["file"]) for d in (md, responses))
    provenance = {"shared_manifest": pin(shared_manifest_pin), "column_identity_proof": source["column_identity_proof"],
                  "intake_receipt": source["intake_receipt"], "plan": source["plan"],
                  "design_source_pins": design["source_pins"],
                  "source_subjects": source["subjects"],
                  "operation": "complete 1200 design trial columns; transpose native little-f4; no value arithmetic",
                  "scientific_analysis_performed": False}
    manifest = {"schema": "neural052_inputs_v1", "task_id": "NEURAL-052", "design": pin(design_pin),
                "feature_names": FEATURE_NAMES, "features": feature_desc, "subjects": subjects,
                "source_provenance": provenance}
    manifest_desc = _write_json(output / "INPUTS.json", manifest, budget)
    binding = {"schema": "neural052_packet_binding_v1", "task_id": "NEURAL-052", "design": pin(design_pin),
               "inputs": dict(manifest_desc, file="public/input/INPUTS.json"), "files": files,
               "shared_manifest": pin(shared_manifest_pin), "preparation_scientific_analysis": False}
    _write_json(binding_path, binding, budget)
    for child in output.iterdir():
        os.chmod(child, 0o444)
    return {"status": "built_deterministic_packet", "inputs": binding["inputs"],
            "retained_new_bytes": budget.used, "retained_cap_bytes": PACKET_CAP,
            "participants": list(SUBJECTS), "rows_per_participant": 1200,
            "response_values_changed": False, "scientific_analysis_performed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package-root", required=True, type=Path)
    p.add_argument("--shared-root", required=True, type=Path)
    p.add_argument("--repository-root", required=True, type=Path)
    p.add_argument("--shared-manifest-bytes", required=True, type=int)
    p.add_argument("--shared-manifest-sha256", required=True)
    p.add_argument("--design-bytes", required=True, type=int)
    p.add_argument("--design-sha256", required=True)
    args = p.parse_args()
    result = prepare_packet(args.package_root, args.shared_root,
                            {"bytes": args.shared_manifest_bytes, "sha256": args.shared_manifest_sha256},
                            {"bytes": args.design_bytes, "sha256": args.design_sha256}, args.repository_root)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
