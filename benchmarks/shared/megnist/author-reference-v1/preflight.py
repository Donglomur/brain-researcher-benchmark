"""Task-local MegNIST identity and header checks, never an isolation claim.

Manifest validation defaults to metadata only. ``inspect_files=True`` hashes
the named files and checks HDF5 headers; callers must separately authorize
such reads. Construction tests use generated fixtures exclusively. This module
does not download, import author code, fit models, inspect feature values, or
establish filesystem/process/network/provider isolation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

AUTHOR_SHA256 = "f377af312dd066691e5f046b5ead51c5f77745ffbd908850cc49a5d95061ab18"
REFERENCE_MANIFEST_SHA256 = "ec53db9a60779e01ee05496833418355151781afff7b02f9db20a879029ace02"
REFERENCE_ROWS = {"train": 10000, "val": 1000, "test": 1000}
REFERENCE_FEATURE_SHAPE = (306, 250)
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA256")
    return value


def _positive(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _read_json(path: Path, cap: int = 1024 * 1024) -> tuple[dict, bytes]:
    if not path.is_file() or path.stat().st_size > cap:
        raise ValueError("Required local JSON is absent or exceeds the bounded metadata size")
    raw = path.read_bytes()
    document = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if not isinstance(document, dict):
        raise ValueError("Expected a JSON object")
    return document, raw


def _file_identity(path: Path, expected_sha256: str, expected_size: int | None = None) -> dict:
    _digest(expected_sha256, "expected_sha256")
    if not path.is_file():
        raise ValueError("Required local file is missing; downloads are not permitted")
    size = path.stat().st_size
    if expected_size is not None and size != expected_size:
        raise ValueError("Local file size does not match the accepted manifest")
    with path.open("rb") as handle:
        observed = hashlib.file_digest(handle, "sha256").hexdigest()
    if observed != expected_sha256:
        raise ValueError("Local file SHA256 does not match its accepted identity")
    return {"path": str(path), "size": size, "sha256": observed}


def _inside(root: Path, filename: object) -> Path:
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        raise ValueError("Manifest paths must be plain local filenames")
    path = (root / filename).resolve()
    if path.parent != root:
        raise ValueError("Manifest file or symlink escapes the selected input directory")
    return path


def _limits() -> dict:
    return {
        "scientific_qualification": False,
        "actual_isolation_qualified": False,
        "runtime_isolation_qualified": False,
        "reproduction_status": "unknown",
        "improvement_status": "unknown",
        "downloads_performed": False,
        "limit": "Identity, shape and path checks do not establish process/filesystem/network/provider isolation.",
    }


def verify_source_identity(source_path, expected_sha256: str = AUTHOR_SHA256) -> dict:
    """Hash at most 256 KiB of a named source file; do not import it."""
    path = Path(source_path).resolve()
    if not path.is_file() or path.stat().st_size > 262144:
        raise ValueError("Named source is missing or exceeds the source-file cap")
    return {"source": _file_identity(path, expected_sha256), **_limits()}


def check_path_separation(candidate_root, private_root) -> dict:
    """Reject overlapping declared roots, without claiming access enforcement."""
    candidate = Path(candidate_root).resolve()
    private = Path(private_root).resolve()
    if candidate == private or candidate in private.parents or private in candidate.parents:
        raise ValueError("Candidate and evaluator-private roots must be disjoint")
    return {"declared_roots_disjoint": True, **_limits()}


def inspect_candidate_h5(path, *, split: str, expected_rows: int, feature_shape) -> dict:
    """Check headers/links only, with no feature, ID or label-array reads."""
    import h5py

    if split not in REFERENCE_ROWS:
        raise ValueError("Unknown split")
    count = _positive(expected_rows, "expected_rows")
    shape = tuple(_positive(v, "feature_shape") for v in feature_shape)
    if not shape:
        raise ValueError("feature_shape cannot be empty")
    required = {"data", "case_ids"} | ({"labels"} if split != "test" else set())
    with h5py.File(Path(path), "r") as handle:
        if set(handle.keys()) != required or len(handle.attrs):
            raise ValueError("Unexpected datasets or attributes in candidate input")
        for name in required:
            if not isinstance(handle.get(name, getlink=True), h5py.HardLink):
                raise ValueError("External/soft HDF5 links are not candidate input")
            dataset = handle[name]
            if not isinstance(dataset, h5py.Dataset) or len(dataset.attrs):
                raise ValueError("Candidate inputs require plain datasets without attributes")
            if dataset.is_virtual or dataset.external is not None:
                raise ValueError("Virtual/external HDF5 storage is not candidate input")
        data, ids = handle["data"], handle["case_ids"]
        if tuple(data.shape) != (count, *shape) or data.dtype.kind != "f" or data.dtype.itemsize != 4:
            raise ValueError("Feature shape or float32 dtype mismatch")
        if tuple(ids.shape) != (count, 16) or ids.dtype.kind != "u" or ids.dtype.itemsize != 1:
            raise ValueError("case_ids must preserve the prepared (rows,16) raw uint8 identifiers")
        if split != "test":
            labels = handle["labels"]
            if tuple(labels.shape) != (count,) or labels.dtype.kind != "i" or labels.dtype.itemsize != 4:
                raise ValueError("Training/validation labels must preserve signed int32 representation")
    return {
        "split": split,
        "rows": count,
        "feature_shape": list(shape),
        "datasets": sorted(required),
        "header_shapes_verified": True,
        "array_values_read": False,
        "case_id_uniqueness_verified": False,
        **_limits(),
    }


def validate_input_manifest(manifest_path, *, profile="reference", expected_sha256=None,
                            root=None, inspect_files=False, feature_shape=None) -> dict:
    """Validate a pinned original manifest or an explicit generated fixture.

    The reference profile always requires the accepted raw manifest identity.
    A generated profile must declare ``generated_fixture: true`` and never
    changes reference support. File bytes/headers are read only on explicit opt-in.
    """
    path = Path(manifest_path).resolve()
    document, raw = _read_json(path)
    observed = hashlib.sha256(raw).hexdigest()
    if profile not in {"reference", "generated"}:
        raise ValueError("profile must be reference or generated")
    if expected_sha256 is not None and observed != _digest(expected_sha256, "expected_sha256"):
        raise ValueError("Manifest identity mismatch")
    if profile == "reference":
        if observed != REFERENCE_MANIFEST_SHA256:
            raise ValueError("Reference profile requires the exact accepted original input manifest")
        shape = REFERENCE_FEATURE_SHAPE
        if feature_shape is not None and tuple(feature_shape) != shape:
            raise ValueError("Reference feature support cannot be changed")
    else:
        if document.get("generated_fixture") is not True:
            raise ValueError("Generated profile requires explicit generated_fixture=true")
        dimensions = feature_shape if feature_shape is not None else document.get("feature_shape", [])
        shape = tuple(_positive(v, "feature_shape") for v in dimensions)
        if not shape:
            raise ValueError("Generated fixtures must specify feature_shape")
    if document.get("schema") != "standalone_features_static_axes_v2":
        raise ValueError("Unexpected prepared-input schema")
    splits = document.get("splits")
    if not isinstance(splits, dict) or set(splits) != set(REFERENCE_ROWS):
        raise ValueError("Exactly train, val and test split declarations are required")
    base = Path(root).resolve() if root is not None else path.parent
    checked = {}
    for split in ("train", "val", "test"):
        record = splits[split]
        if not isinstance(record, dict):
            raise ValueError("Each split declaration must be a mapping")
        count = _positive(record.get("rows"), "rows")
        if profile == "reference" and count != REFERENCE_ROWS[split]:
            raise ValueError("Reference split support cannot be changed")
        required = {"data", "case_ids"} | ({"labels"} if split != "test" else set())
        datasets = record.get("datasets")
        if not isinstance(datasets, list) or len(datasets) != len(required) or set(datasets) != required:
            raise ValueError("Incorrect split dataset declaration; test must not contain labels")
        if record.get("file") != f"{split}.h5":
            raise ValueError("Unexpected split filename")
        file_path = _inside(base, record["file"])
        digest = _digest(record.get("sha256"), "split.sha256")
        size = _positive(record.get("size"), "split.size")
        checked[split] = {"path": str(file_path), "rows": count, "size": size, "sha256": digest}
        if inspect_files:
            _file_identity(file_path, digest, size)
            checked[split]["header_check"] = inspect_candidate_h5(
                file_path, split=split, expected_rows=count, feature_shape=shape)
    axes = document.get("axes")
    if profile == "reference" and not isinstance(axes, dict):
        raise ValueError("Reference manifest requires the original static axes")
    if axes is not None:
        if not isinstance(axes, dict):
            raise ValueError("axes must be a mapping")
        axes_path = _inside(base, axes.get("file"))
        axes_digest = _digest(axes.get("sha256"), "axes.sha256")
        axes_size = _positive(axes.get("size"), "axes.size")
        if inspect_files:
            _file_identity(axes_path, axes_digest, axes_size)
    return {
        "profile": profile,
        "manifest_sha256": observed,
        "manifest_identity_verified": profile == "reference" or expected_sha256 is not None,
        "feature_shape": list(shape),
        "splits": checked,
        "file_identities_verified": bool(inspect_files),
        "header_shapes_verified": bool(inspect_files),
        "authentic_reference_data_read": profile == "reference" and bool(inspect_files),
        "source_download_fallback_invoked": False,
        **_limits(),
    }


def validate_normalization_cache(cache_path, *, expected_provenance_sha256,
                                 expected_train_sha256, expected_source_sha256=AUTHOR_SHA256) -> dict:
    """Verify pinned sidecar/cache bytes and train/source/method binding.

    This does not recompute normalization or read training arrays. Numeric
    vector/finite checks remain the fitting adapter's responsibility.
    """
    path = Path(cache_path).resolve()
    sidecar = Path(str(path) + ".json")
    _file_identity(sidecar, _digest(expected_provenance_sha256, "expected_provenance_sha256"))
    document, _ = _read_json(sidecar)
    if document.get("schema") != "megnist-normalization-cache/v1":
        raise ValueError("Unexpected normalization cache schema")
    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Missing normalization provenance")
    expected = {
        "schema": "megnist-training-normalization/v1",
        "train_sha256": _digest(expected_train_sha256, "expected_train_sha256"),
        "source_sha256": _digest(expected_source_sha256, "expected_source_sha256"),
        "method": "author-sequential-welford-population-v1",
        "statistics_batch_size": 1000,
    }
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError("Normalization provenance does not match training/source/method identity")
    count = _positive(provenance.get("training_rows"), "training_rows")
    shape = provenance.get("sample_shape")
    if not isinstance(shape, list) or not shape:
        raise ValueError("Missing normalization sample_shape")
    features = math.prod(_positive(v, "sample_shape") for v in shape)
    if provenance.get("flattened_features") != features:
        raise ValueError("Normalization feature count mismatch")
    for name in ("mean", "std"):
        spec = provenance.get(name)
        if not isinstance(spec, dict) or spec.get("dtype") != "<f8" or spec.get("shape") != [features]:
            raise ValueError("Normalization array identity/shape mismatch")
        _digest(spec.get("sha256"), f"{name}.sha256")
    cache = _file_identity(path, _digest(document.get("cache_sha256"), "cache_sha256"))
    return {
        "cache": cache,
        "provenance_sha256": expected_provenance_sha256,
        "training_rows": count,
        "sample_shape": shape,
        "cache_bytes_and_binding_verified": True,
        "numeric_vectors_verified": False,
        "training_arrays_read": False,
        **_limits(),
    }
