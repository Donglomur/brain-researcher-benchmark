#!/usr/bin/env python3
"""Pinned MATLAB 7.3 source inspection and pre-ZETA/PCA locked normalization.

Reads only explicitly requested MATLAB fields. Does not reconstruct raw calcium,
pose or inverse kinematics, fit a model, or qualify scientific/native execution.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any

import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
PIPELINE = HERE.parent / "train-only-decoding-v2" / "pipeline.py"
PIPELINE_SHA256 = "084a5562e5b262bf30a6e1a26e1cddd9da066b870ae42f8ffff57c01ea14a2ac"
SHA = re.compile(r"[0-9a-f]{64}\Z")
ASSETS_SHA256 = "7fc7b0f68b3b4805076b6e48aa8aadbcb4fd9cd972e28b3a6b35b11a90ff4c70"
_PIPELINE = None
RAW_FIELDS = {x: None for x in (
    "trialNumber", "animalID", "date", "success", "grabTimeC", "liftRT", "goodDLC",
    "wrongZoneFirst", "movementTime", "timeToContact", "has_radical")}
PROVENANCE = ("source_asset_sha256", "clock_evidence_sha256", "feature_provenance_sha256",
              "normalization_recipe_sha256", "upstream_exposure_sha256",
              "trial_selection_policy_sha256")


class Refusal(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise Refusal(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(value: Any) -> str:
    require(isinstance(value, str) and SHA.fullmatch(value) is not None, "Invalid SHA256")
    return value


def positive(value: Any, label: str) -> int:
    require(type(value) is int and 0 < value <= 2**63-1, "Invalid " + label)
    return value


def pipeline():
    global _PIPELINE
    require(hashlib.sha256(PIPELINE.read_bytes()).hexdigest() == PIPELINE_SHA256,
            "V2 pipeline source mismatch")
    if _PIPELINE is not None:
        return _PIPELINE
    spec = importlib.util.spec_from_file_location("calcium_admission_pipeline_v2", PIPELINE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _PIPELINE = module
    return module


def scalar(value: Any, label: str, *, nan: bool = False) -> float:
    a = np.asarray(value)
    require(a.size == 1 and a.dtype.kind in "iuf" and a.dtype.kind != "b", label + " is not a numeric scalar")
    out = float(a.reshape(-1)[0])
    require(math.isfinite(out) or (nan and math.isnan(out)), label + " is nonfinite")
    if a.dtype.kind in "iu":
        require(abs(int(a.reshape(-1)[0])) <= 2**53, label + " loses integer identity")
    return out


def number(value: Any, label: str) -> int:
    v = scalar(value, label)
    require(v.is_integer() and 0 <= v <= 2**53, label + " is not an exact nonnegative integer")
    return int(v)


def flag(value: Any, label: str) -> bool:
    a = np.asarray(value)
    if a.dtype.kind == "b":
        require(a.size == 1, label + " is not scalar")
        return bool(a.reshape(-1)[0])
    v = scalar(value, label)
    require(v in (0, 1), label + " must be logical zero or one")
    return bool(v)


def text(value: Any, label: str) -> str:
    require(isinstance(value, str) and 0 < len(value) <= 256 and
            not any(ord(c) < 32 for c in value), label + " is not a bounded string")
    return value


def grid(value: Any, label: str) -> list[int]:
    a = np.asarray(value)
    require(a.ndim <= 2 and a.size >= 2 and (a.ndim < 2 or 1 in a.shape), label + " must be a vector")
    out = []
    for x in a.reshape(-1, order="F"):
        v = scalar(np.asarray(x), label)
        require(v.is_integer() and abs(v) <= 2**53, label + " requires exact integer milliseconds")
        out.append(int(v))
    require(all(a < b for a, b in zip(out, out[1:])), label + " must be strictly increasing")
    return out


def trials(value: Any, label: str) -> list[int]:
    require(isinstance(value, list) and value and all(type(x) is int and 0 <= x <= 2**53 for x in value),
            label + " requires original numeric trial identities")
    require(len(set(value)) == len(value), label + " contains duplicate trials")
    return value


def named_rows(value: Any, key: str) -> dict[str, dict]:
    require(isinstance(value, list) and all(isinstance(x, dict) and isinstance(x.get(key), str) for x in value),
            "Malformed records: " + key)
    out = {x[key]: x for x in value}
    require(len(out) == len(value), "Duplicate " + key)
    return out


def unique(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, "Duplicate JSON key")
        out[k] = v
    return out


def read_json(path: Path, expected: str, limit: int) -> dict:
    positive(limit, "JSON byte limit")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                "JSON must be a bounded ordinary single-link file")
        chunks, total = [], 0
        while True:
            chunk = f.read(min(65536, limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            require(total <= limit, "JSON byte limit exceeded")
            chunks.append(chunk)
        after = os.fstat(f.fileno())
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "JSON changed during read")
        body = b"".join(chunks)
    require(len(body) <= limit, "JSON byte limit exceeded")
    require(hashlib.sha256(body).hexdigest() == sha(expected), "JSON pin mismatch")
    try:
        out = json.loads(body, object_pairs_hook=unique,
                         parse_constant=lambda x: (_ for _ in ()).throw(Refusal("Nonfinite JSON")))
        require(isinstance(out, dict), "JSON document is not an object")
        return out
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal("Malformed JSON") from exc


class Mat73:
    """Field-selective, bounded MATLAB 7.3 reader with original axis order.

    References are internal only. Arrays are charged before allocation. This
    is not a native-library sandbox; the caller retains process resource limits.
    """
    def __init__(self, file, *, max_elements: int, max_records: int):
        self.file = file
        self.remaining = positive(max_elements, "MAT element limit")
        self.max_records = positive(max_records, "MAT record limit")
        self.loaded = 0

    def _charge(self, node):
        require(not node.is_virtual and not node.external,
                "Virtual or externally stored HDF5 datasets are forbidden")
        ref_kind = h5py.check_dtype(ref=node.dtype)
        require(ref_kind is None or ref_kind is h5py.Reference, "HDF5 region references are forbidden")
        count = math.prod(node.shape)
        require(count <= self.remaining, "MAT decoded element limit exceeded")
        self.remaining -= count
        self.loaded += count
        require(node.ndim <= 2, "Only MATLAB scalar/vector/matrix fields are supported")

    def _class(self, node):
        value = node.attrs.get("MATLAB_class")
        if isinstance(value, bytes):
            return value.decode("ascii", errors="strict")
        if isinstance(value, str):
            return value
        raise Refusal("Missing MATLAB_class")

    def _child(self, group, name):
        require(name in group and isinstance(group.get(name, getlink=True), h5py.HardLink),
                "Missing field or nonlocal HDF5 link: " + name)
        return group[name]

    def _leaf(self, node, depth=0):
        require(depth <= 8, "MAT nesting exceeds limit")
        require(isinstance(node, h5py.Dataset), "Expected MATLAB dataset")
        self._charge(node)
        cls = self._class(node)
        if cls == "cell":
            require(h5py.check_dtype(ref=node.dtype) is not None, "Cell references required")
            refs = node[()].T.reshape(-1, order="F")
            require(len(refs) <= 1024, "Cell count exceeds supported metadata boundary")
            return [self._leaf(self.file[r], depth + 1) for r in refs if self._nonnull(r)]
        if cls == "char":
            require(node.dtype.kind == "u" and node.dtype.itemsize == 2, "Only UTF16 MATLAB chars supported")
            a = np.asarray(node[()]).T
            require(a.size <= 1024 and (a.ndim < 2 or 1 in a.shape), "Only bounded MATLAB char vectors supported")
            try:
                return a.reshape(-1, order="F").astype("<u2").tobytes().decode("utf-16-le")
            except UnicodeError as exc:
                raise Refusal("Invalid MATLAB text") from exc
        require(cls in {"double", "single", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "logical"},
                "Unsupported MATLAB numeric class")
        require(node.dtype.kind in "iufb" and not node.dtype.fields, "Compound/complex/reference data refused")
        result = np.asarray(node[()]).T
        if cls == "logical":
            require(bool(np.all((result == 0) | (result == 1))), "Invalid logical field")
            result = result.astype(bool)
        return result

    @staticmethod
    def _nonnull(ref):
        require(bool(ref), "Null MATLAB reference")
        return True

    def structs(self, node, fields: dict, depth=0):
        require(depth <= 8 and isinstance(node, h5py.Group) and self._class(node) == "struct",
                "Expected bounded MATLAB struct group")
        children = {k: self._child(node, k) for k in fields}
        ref_fields = {k: x for k, x in children.items()
                      if isinstance(x, h5py.Dataset) and h5py.check_dtype(ref=x.dtype) is not None
                      and "MATLAB_class" not in x.attrs}
        sizes = {math.prod(x.shape) for x in ref_fields.values()}
        require(len(sizes) <= 1, "Struct field lengths differ")
        count = next(iter(sizes), 1)
        require(0 < count <= self.max_records, "Struct count exceeds record limit")
        require(count == 1 or len(ref_fields) == len(children), "Mixed nonscalar struct field representation")
        values = {}
        for key, child in children.items():
            if key in ref_fields:
                self._charge(child)
                require(child.ndim <= 2 and (child.ndim < 2 or 1 in child.shape), "Struct array must be a vector")
                refs = child[()].T.reshape(-1, order="F")
                nodes = [self.file[r] for r in refs if self._nonnull(r)]
            else:
                nodes = [child]
            rows = []
            for item in nodes:
                if fields[key] is None:
                    rows.append(self._leaf(item, depth + 1))
                else:
                    nested = self.structs(item, fields[key], depth + 1)
                    require(len(nested) == 1, "Nested metadata struct must be scalar")
                    rows.append(nested[0])
            values[key] = rows
        return [{k: values[k][i] for k in fields} for i in range(count)]

    def read(self, key: str, fields: dict):
        return self.structs(self._child(self.file, key), fields)


def safe_input_path(root: Path, rel: str) -> Path:
    require(isinstance(rel, str) and rel and not Path(rel).is_absolute() and ".." not in Path(rel).parts,
            "Source path must stay below input root")
    root = root.resolve(strict=True)
    path = root / rel
    for part in [path, *path.parents]:
        if part == root:
            break
        require(not part.is_symlink(), "Symlink source path refused")
    return path


def opened_mat(root: Path, entry: dict, limits: dict, *, published_md5: str | None = None):
    """Return a pinned ordinary open file; caller must close it after HDF5 use."""
    path = safe_input_path(root, entry.get("path"))
    expected_size = positive(entry.get("bytes"), "MAT byte count")
    require(expected_size <= positive(limits["max_file_bytes"], "MAT file limit"), "MAT file size exceeds budget")
    handle = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb")
    try:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected_size,
                "MAT must be an exact-sized ordinary single-link file")
        h = hashlib.sha256()
        md5 = hashlib.md5()
        count = 0
        while True:
            chunk = handle.read(min(1024 * 1024, expected_size - count + 1))
            if not chunk:
                break
            count += len(chunk)
            require(count <= expected_size, "MAT grew while hashing")
            h.update(chunk)
            md5.update(chunk)
        require(count == expected_size and h.hexdigest() == sha(entry.get("sha256")), "MAT source hash mismatch")
        require(published_md5 is None or md5.hexdigest() == published_md5, "Published original MD5 mismatch")
        handle.seek(0)
        header = handle.read(520)
        require(header.startswith(b"MATLAB 7.3 MAT-file") and header[512:520] == b"\x89HDF\r\n\x1a\n",
                "Expected MATLAB7.3 header and HDF5 userblock; no v5 fallback")
        handle.seek(0)
        return handle, (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    except BaseException:
        handle.close()
        raise


def stable(handle, before):
    after = os.fstat(handle.fileno())
    require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) == before,
            "Source changed during MAT inspection")


def raw_census(rows: list[dict], session_id: str, p) -> dict:
    mouse, _ = p.SESSIONS[session_id]
    date = session_id.split("_", 1)[1][:8]
    result = []
    seen = set()
    for row in rows:
        n = number(row["trialNumber"], "Original trialNumber")
        require(n > 0, "Original trialNumber must be positive")
        require(n not in seen, "Duplicate raw trial number")
        seen.add(n)
        require(text(row["animalID"], "animalID") == mouse and text(row["date"], "date").startswith(date),
                "Raw mouse/date mismatch")
        reasons = []
        if not flag(row["success"], "success"):
            reasons.append("unsuccessful")
        if math.isnan(scalar(row["grabTimeC"], "grabTimeC", nan=True)):
            reasons.append("grabTimeC_nan")
        for key, ceiling in (("liftRT", 500), ("movementTime", 500), ("timeToContact", 1000)):
            value = scalar(row[key], key, nan=True)
            if not value < ceiling:
                reasons.append(key + "_not_below_" + str(ceiling))
        if not flag(row["goodDLC"], "goodDLC"):
            reasons.append("goodDLC_false")
        if flag(row["wrongZoneFirst"], "wrongZoneFirst"):
            reasons.append("wrongZoneFirst_true")
        if not flag(row["has_radical"], "has_radical"):
            reasons.append("has_radical_false")
        result.append({"trial_number": n, "eligible_by_loadLock4Decode": not reasons,
                       "exclusion_reasons": reasons})
    require(result, "Raw source has no trials")
    return {"session_id": session_id, "ordered_original_trials": result,
            "selected_trial_numbers": [r["trial_number"] for r in result if r["eligible_by_loadLock4Decode"]],
            "trial_numbers_equal_one_based_positions": [r["trial_number"] for r in result] == list(range(1, len(result) + 1)),
            "date_scope": "mouse_and_first_eight_date_characters_only_full_timestamp_is_external"}


def primary_assets() -> dict:
    doc = read_json(HERE.parent / "locked-mat-admission-v1" / "PRIMARY_ASSETS.json", ASSETS_SHA256, 65536)
    return {r["session_id"]: r for r in doc["assets"]}


def roi_metadata(m: dict) -> tuple[np.ndarray, str]:
    a = np.asarray(m["ROILags"])
    require(a.ndim <= 2 and a.size > 0 and (a.ndim < 2 or 1 in a.shape)
            and a.dtype.kind in "iuf" and bool(np.all(np.isfinite(a))), "Invalid native ROILags")
    if a.dtype.kind in "iu":
        require(bool(np.all(a <= 2**53)) and (a.dtype.kind == "u" or bool(np.all(a >= -(2**53)))),
                "ROI lag integers exceed exact float64 admission")
    return a, digest(a.reshape(-1, order="F").astype(float).tolist())


def inspect_raw(manifest: dict, root: Path) -> dict:
    p = pipeline()
    require(manifest.get("schema") == "calcium_raw_mat73_manifest_v1" and manifest.get("author_commit") == p.AUTHOR_COMMIT,
            "Wrong raw MAT inspection manifest")
    entries = named_rows(manifest["sessions"], "session_id")
    require(set(entries) == set(p.SESSIONS), "All ten original imaging sessions required")
    limits = manifest["limits"]
    assets = primary_assets()
    output = []
    seen = set()
    for sid in p.SESSIONS:
        e = entries[sid]
        require(e["bytes"] == assets[sid]["bytes"] and Path(e["path"]).name == assets[sid]["filename"],
                "Raw original filename/byte count differs from published Figshare inventory")
        f, before = opened_mat(root, e, limits, published_md5=assets[sid]["published_md5"])
        try:
            require(before[:2] not in seen, "Physical source file reused for two sessions")
            seen.add(before[:2])
            with h5py.File(f, "r") as h:
                r = Mat73(h, max_elements=limits["max_decoded_elements_per_file"], max_records=limits["max_trials_per_session"])
                out = raw_census(r.read("R", RAW_FIELDS), sid, p)
                m = r.read("M", {"ROILags": None, "cycleDurMs": None})
                require(len(m) == 1, "Raw M must be scalar")
                lags, lag_hash = roi_metadata(m[0])
                cycle = scalar(m[0]["cycleDurMs"], "cycleDurMs")
                require(cycle > 0, "cycleDurMs must be positive")
                out.update({"source_sha256": e["sha256"], "source_bytes": e["bytes"], "decoded_elements": r.loaded,
                            "published_md5_matched": True, "figshare_file_id": assets[sid]["figshare_file_id"],
                            "roi_columns": int(lags.size), "roilags_sha256": lag_hash, "cycle_duration_ms": cycle})
                output.append(out)
            stable(f, before)
        finally:
            f.close()
    return {"schema": "calcium_raw_eligibility_inspection_v1", "task_id": p.TASK_ID,
            "author_commit": p.AUTHOR_COMMIT, "manifest_sha256": digest(manifest), "sessions": output,
            "scope": "Pinned supplied MATLAB7.3 scalar metadata; does not read neural or kinematic arrays.",
            "published_asset_checksums_matched": True,
            "full_timestamp_authenticated": False, "published_asset_identity_independently_qualified": False,
            "clock_alignment_qualified": False, "scientific_qualification": False}


def locked_session(document: dict, entry: dict, recipe: dict, p) -> tuple[dict, dict, dict]:
    sid = entry["session_id"]
    mouse, region = p.SESSIONS[sid]
    metadata = document["M"]
    require(len(metadata) == 1, "M must be scalar")
    m = metadata[0]
    source_grid = grid(m["config"]["tPts"], "M.config.tPts")
    step = number(m["config"]["tBase"], "M.config.tBase")
    require(step > 0 and all(b-a == step for a,b in zip(source_grid, source_grid[1:])), "Source grid/step mismatch")
    require(source_grid == list(range(-200, 801, 10)), "Expected original loadLockSave101sample grid")
    require(scalar(m["config"]["smoothSD"], "smoothSD") == 35 and
            scalar(m["config"]["preT"], "preT") == -200 and scalar(m["config"]["postT"], "postT") == 800 and
            text(m["config"]["eventName"], "config.eventName") == "liftTimeDLC",
            "Locked export preprocessing differs from original joint-angle loadLockSave")
    info = m["config"]["datasetInfo"]
    require(text(info["mouseName"], "datasetInfo.mouseName") == mouse and
            text(info["sessionDate"], "datasetInfo.sessionDate") == sid.split("_", 1)[1][:8] and
            text(info["filename"], "datasetInfo.filename") == primary_assets()[sid]["filename"][:-4],
            "Locked datasetInfo differs from exact original session asset")
    window = recipe["window_ms"]
    require(window == [-100, 400] and recipe["grid_step_ms"] == 10 and step == 10,
            "This adapter retains the registered51sample window")
    target_grid = list(range(-100, 401, 10))
    require(set(target_grid) <= set(source_grid), "Source grid misses requested samples")
    indices = [source_grid.index(x) for x in target_grid]
    require(m["jointNames"] == list(p.JOINT_NAMES), "Native jointNames differ from source order")
    roi_lags, roi_hash = roi_metadata(m)
    roi_count = int(roi_lags.size)
    require(roi_count <= recipe["limits"]["max_rois_per_session"], "ROI limit exceeded")
    roi_ids = [f"{sid}:source-column-{i}" for i in range(1, roi_count + 1)]
    originals = trials(entry["original_trial_numbers"], "Original locked census")
    require(all(n > 0 for n in originals), "Original trial numbers must be positive")
    excluded = entry["excluded_unlocked_trial_numbers"]
    require(isinstance(excluded, list) and all(type(x) is int for x in excluded)
            and len(set(excluded)) == len(excluded) and set(excluded) <= set(originals), "Invalid explicit lock exclusions")
    selected = [x for x in originals if x not in excluded]
    require(selected, "No complete locked trials")
    nrows, krows = document["neurons"], document["kinematics"]
    require(len(nrows) == len(krows) == len(originals), "Source locked census length mismatch")
    require([number(x["trialNumber"], "neural trialNumber") for x in nrows] == originals and
            [number(x["trialNumber"], "kinematic trialNumber") for x in krows] == originals,
            "Native neural/kinematic trial identities or ordering disagree")
    target_field = recipe["target_field"]
    neural_field = p.FEATURE_FIELDS[recipe["feature_variant"]]
    data_trials, context_trials, exclusions = [], [], []
    for n, k, original in zip(nrows, krows, originals):
        nl, kl = flag(n["locked"], "neural locked"), flag(k["locked"], "kinematic locked")
        require(nl == kl, "Neural and kinematic lock masks differ")
        require((original in excluded) == (not nl), "Lock exclusion differs from independently frozen census")
        require(text(k["animalID"], "animalID") == mouse and
                text(k["date"], "date").startswith(sid.split("_", 1)[1][:8]), "Locked mouse/date mismatch")
        require(text(k["eventName"], "eventName") == "liftTimeDLC" and
                grid(k["tPts"], "kinematic tPts") == source_grid, "Native event/time grid mismatch")
        direction = number(k["LR"], "Native LR")
        require(direction in (1, 2), "Native LR must be1left or2right")
        if not nl:
            exclusions.append({"original_trial_number": original, "reason": "both_native_lock_flags_false"})
            continue
        x, y = p.matrix(n[neural_field], "Native neural field"), p.matrix(k[target_field], "Native target field")
        require(x.shape == (len(source_grid), roi_count) and y.shape == (len(source_grid), 24),
                "Native matrix axes/ROI/joint dimensions disagree")
        tid = f"{sid}:trial-{original}"
        data_trials.append({"trial_id": tid, "neural_trial_id": tid, "target_trial_id": tid,
                            "neural_time_ms": target_grid, "target_time_ms": target_grid,
                            "neural": x[indices, :].tolist(), "targets": y[indices, :].tolist()})
        context_trials.append({"trial_id": tid, "original_trial_number": original,
                               "reach_target": "left" if direction == 1 else "right"})
    exposure_digest = p.source_condition.validate_source_condition(entry["source_condition"], recipe["feature_variant"])
    require(entry["source_condition"]["locked_output_grid_ms"] == source_grid,
            "Exposure record locked grid differs from actual export")
    provenance = entry["provenance"]
    require(provenance["upstream_exposure_sha256"] == exposure_digest,
            "Upstream exposure digest does not bind the source-condition body")
    binding = {key: sha(provenance[key]) for key in PROVENANCE}
    binding.update({"session_id": sid, "mouse_id": mouse, "region": region,
                    "roi_ids": roi_ids, "native_neural_field": neural_field,
                    "source_condition": entry["source_condition"]})
    data = dict(binding, trials=data_trials)
    context = {"session_id": sid, "source_asset_sha256": binding["source_asset_sha256"],
               "native_target_mapping_sha256": digest({"author_commit": p.AUTHOR_COMMIT, "LR": {"1": "left", "2": "right"}}),
               "trials": context_trials}
    receipt = {"session_id": sid, "locked_asset_sha256": entry["sha256"], "original_trial_numbers": originals,
               "included_trial_numbers": selected, "excluded_trials": exclusions,
               "source_grid_ms": source_grid, "selected_source_rows_zero_based": indices,
               "roi_columns": roi_count, "roi_identity_scope": "supplied_locked_session_column_ordinals_only",
               "roilags_sha256": roi_hash}
    return data, context, receipt


def normalize_locked(manifest: dict, root: Path) -> dict:
    p = pipeline()
    require(manifest.get("schema") == "calcium_locked_mat73_manifest_v2" and manifest.get("author_commit") == p.AUTHOR_COMMIT,
            "Wrong locked MAT manifest")
    p.source_condition.reject_legacy_support(manifest)
    entries = named_rows(manifest["sessions"], "session_id")
    require(set(entries) == set(p.SESSIONS), "Complete ten-session cohort required")
    recipe = manifest["recipe"]
    require(recipe["target_field"] in p.TARGET_UNITS and recipe["feature_variant"] in p.FEATURE_FIELDS,
            "Unsupported separate target or feature track")
    limits = manifest["io_limits"]
    raw_pin = manifest["raw_inspection"]
    raw_relative = raw_pin["path"]
    raw_path = safe_input_path(root, raw_relative)
    raw_report = read_json(raw_path, raw_pin["sha256"], limits["max_raw_report_bytes"])
    require(raw_report.get("schema") == "calcium_raw_eligibility_inspection_v1" and
            raw_report.get("task_id") == p.TASK_ID and raw_report.get("author_commit") == p.AUTHOR_COMMIT and
            raw_report.get("published_asset_checksums_matched") is True, "Raw source inspection identity is unavailable")
    raw_rows = named_rows(raw_report["sessions"], "session_id")
    require(set(raw_rows) == set(p.SESSIONS), "Raw inspection must cover all ten sessions")
    target_field, neural_field = recipe["target_field"], p.FEATURE_FIELDS[recipe["feature_variant"]]
    fields = {"kinematics": {x: None for x in ("trialNumber", "locked", "animalID", "date", "eventName", "tPts", "LR", target_field)},
              "neurons": {x: None for x in ("trialNumber", "locked", neural_field)},
              "M": {"config": {"tPts": None, "tBase": None, "smoothSD": None, "preT": None,
                                "postT": None, "eventName": None,
                                "datasetInfo": {"mouseName": None, "sessionDate": None, "filename": None}},
                    "jointNames": None, "ROILags": None}}
    datasets, contexts, receipts = [], [], []
    seen = set()
    for sid in p.SESSIONS:
        entry = entries[sid]
        require(raw_rows[sid]["source_sha256"] == entry["provenance"]["source_asset_sha256"] and
                raw_rows[sid]["selected_trial_numbers"] == entry["original_trial_numbers"],
                "Locked export does not match complete raw eligible trial census")
        if recipe["feature_variant"] == "radical":
            require(raw_rows[sid]["trial_numbers_equal_one_based_positions"] is True,
                    "RADICaL R(trialNumber) indexing is not supported by raw identities")
        f, before = opened_mat(root, entry, limits)
        try:
            require(before[:2] not in seen, "Same physical MAT reused across sessions")
            seen.add(before[:2])
            with h5py.File(f, "r") as h:
                reader = Mat73(h, max_elements=limits["max_decoded_elements_per_file"],
                               max_records=recipe["limits"]["max_trials_per_session"])
                document = {key: reader.read(key, spec) for key, spec in fields.items()}
                data, context, receipt = locked_session(document, entry, recipe, p)
                require(receipt["roi_columns"] == raw_rows[sid]["roi_columns"] and
                        receipt["roilags_sha256"] == raw_rows[sid]["roilags_sha256"],
                        "Locked ROI count or lag metadata differs from raw inspection")
                receipt["decoded_elements"] = reader.loaded
                datasets.append(data)
                contexts.append(context)
                receipts.append(receipt)
            stable(f, before)
        finally:
            f.close()
    context = {"schema": "calcium_reach_context_v1", "task_id": p.TASK_ID,
               "event_conditioning": "retrospective_public_liftTimeDLC", "sessions": contexts}
    splits = p.freeze_within_mouse_splits(context, expected_context_sha256=p.digest(context), seed=recipe["split_seed"])
    common = {"task_id": p.TASK_ID, "author_commit": p.AUTHOR_COMMIT, "joint_names": list(p.JOINT_NAMES),
              "target_field": target_field, "target_units": p.TARGET_UNITS[target_field],
              "feature_variant": recipe["feature_variant"], "event_conditioning": "retrospective_public_liftTimeDLC",
              "upstream_exposure_policy": p.source_condition.POLICY}
    dataset = dict(common, schema="calcium_normalized_v2", sessions=datasets)
    protocol = dict(common, schema="calcium_protocol_v2", condition="within_mouse",
                    metric_policy=p.METRIC_POLICY, recipe_selection="fixed_before_evaluation_no_data_tuning",
                    new_mouse_cases=[], **{k: recipe[k] for k in ("window_ms", "grid_step_ms", "cell_budget", "pca_components", "ridge_alpha", "limits")})
    protocol["sessions"] = []
    for row in datasets:
        binding = {k: v for k, v in row.items() if k != "trials"}
        binding.update(splits["sessions"][row["session_id"]])
        protocol["sessions"].append(binding)
    admitted = p.admit(dataset, protocol, expected_protocol_sha256=p.digest(protocol))
    return {"schema": "calcium_locked_normalization_result_v2", "dataset": dataset,
            "protocol": protocol, "context": context,
            "protocol_sha256": p.digest(protocol), "context_sha256": p.digest(context),
            "normalized_input_sha256": admitted["normalized_input_sha256"],
            "receipt": {"manifest_sha256": digest(manifest), "raw_inspection_sha256": raw_pin["sha256"], "sessions": receipts,
                        "complete_sessions": 10, "complete_mice": 5,
                        "scoped_operation": "source_locked_matrix_selection_and_normalization_no_fit",
                        "raw_to_locked_extraction_executed": False, "authentic_native_parity_qualified": False,
                        "provenance_body_authentication": "source_condition_body_bound_other_native_pins_external_not_rederived",
                        "source_condition_policy": p.source_condition.POLICY,
                        "upstream_exposure_qualification": False,
                        "scientific_qualification": False}}


def write_new(path: Path, value: dict, limit: int) -> dict:
    positive(limit, "output byte limit")
    require(not path.exists() and not path.is_symlink(), "Output already exists")
    fd, temp = tempfile.mkstemp(prefix=".calcium-admission-", dir=path.parent)
    total, h = 0, hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as f:
            encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            for text_chunk in encoder.iterencode(value):
                body = text_chunk.encode("utf-8")
                total += len(body)
                require(total <= limit, "Output byte limit exceeded")
                h.update(body)
                f.write(body)
            total += 1
            require(total <= limit, "Output byte limit exceeded")
            f.write(b"\n")
            h.update(b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.link(temp, path)
        return {"bytes": total, "sha256": h.hexdigest()}
    finally:
        os.unlink(temp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("inspect-raw", "normalize-locked"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-manifest-bytes", type=int, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = read_json(args.manifest, args.expected_manifest_sha256, args.max_manifest_bytes)
        operation = inspect_raw if args.operation == "inspect-raw" else normalize_locked
        result = operation(manifest, args.input_root)
        written = write_new(args.output, result, args.max_output_bytes)
        print(json.dumps({"status": "complete_source_operation", "operation": args.operation,
                          "output_sha256": written["sha256"], "output_bytes": written["bytes"],
                          "scientific_qualification": False}))
        return 0
    except (Refusal, KeyError, TypeError, ValueError, OverflowError, OSError, RuntimeError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
