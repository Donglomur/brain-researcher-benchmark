"""MegNIST feature-only prediction transport; no fitting or private labels.

The adapter preserves the author's C-order flattening, float64 train-statistic
normalization followed by FloatTensor conversion, unshuffled DataLoader, eval
mode and argmax rule. It intentionally does not use the author's label-reading
test Dataset or print test scores. Calling inference requires separate runtime
authorization; importing this module performs no input read or model execution.

File-shape checks and a stable numeric model-state fingerprint do not enforce
process, filesystem, network or conversation isolation.
"""
from __future__ import annotations

import re
from pathlib import Path

import h5py
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from author_route import model_state_sha256

NUM_CLASSES = 10
PREDICTION_SCHEMA = "megnist-per-case-predictions/v1"
_HEX256 = re.compile(r"[0-9a-f]{64}\Z")


def normalize_case_ids(case_ids) -> np.ndarray:
    """Validate the prepared format: unique opaque (N,16) uint8 tokens.

    Every raw byte, including leading/trailing/interior zeros, is significant.
    Tokens are never decoded, stripped, treated as numbers, or used as labels.
    """
    ids = np.asarray(case_ids)
    if ids.ndim != 2 or ids.shape[1:] != (16,) or len(ids) == 0 or ids.dtype != np.dtype("uint8"):
        raise ValueError("case_ids must be a nonempty (N,16) uint8 array")
    ids = ids.copy()
    if len(set(case_id_keys(ids))) != len(ids):
        raise ValueError("duplicate case IDs")
    return ids


def case_id_keys(case_ids) -> list[bytes]:
    """Produce all-16-byte exact join keys for prepared opaque IDs."""
    ids = np.asarray(case_ids)
    if ids.ndim != 2 or ids.shape[1:] != (16,) or ids.dtype != np.dtype("uint8"):
        raise ValueError("case_ids must use the prepared (N,16) uint8 format")
    return [row.tobytes() for row in ids]


def _local_dataset(handle: h5py.File, name: str) -> h5py.Dataset:
    if not isinstance(handle.get(name, getlink=True), h5py.HardLink):
        raise ValueError(f"{name} must be a local HDF5 dataset")
    value = handle[name]
    if not isinstance(value, h5py.Dataset) or value.is_virtual or value.external:
        raise ValueError(f"{name} must be a local non-virtual dataset")
    if value.attrs:
        raise ValueError(f"unexpected attributes on {name}")
    dcpl = value.id.get_create_plist()
    if dcpl.get_nfilters() or value.chunks is not None or dcpl.get_layout() != h5py.h5d.CONTIGUOUS:
        raise ValueError(f"{name} must be contiguous and unfiltered")
    if h5py.h5o.get_info(value.id).rc != 1:
        raise ValueError(f"hard-link aliases are forbidden for {name}")
    if value.dtype.hasobject or value.dtype.fields is not None or value.dtype.subdtype is not None:
        raise ValueError(f"non-numeric/object dataset forbidden for {name}")
    return value


def _validate_rows(count: int, expected_rows: int | None) -> None:
    if count <= 0:
        raise ValueError("empty prediction support")
    if expected_rows is not None:
        if isinstance(expected_rows, bool) or not isinstance(expected_rows, int) or expected_rows <= 0:
            raise ValueError("expected_rows must be a positive integer")
        if count != expected_rows:
            raise ValueError("incomplete or excess case support")


def _require_file_rows(expected_rows) -> None:
    # The genuine test split has1000 cases. Smaller counts are solely for
    # explicit generated controls; preflight still owns full reference scope.
    if isinstance(expected_rows, bool) or not isinstance(expected_rows, int) or not 0 < expected_rows <= 1000:
        raise ValueError("file transport requires explicit expected_rows in1..1000")


def validate_logits(case_ids, logits, *, expected_rows: int | None = None):
    ids = normalize_case_ids(case_ids)
    _validate_rows(len(ids), expected_rows)
    scores = np.asarray(logits)
    if scores.shape != (len(ids), NUM_CLASSES):
        raise ValueError("logits must have shape (number of cases, 10)")
    if scores.dtype.kind != "f" or scores.dtype.itemsize not in (2, 4, 8):
        raise ValueError("logits must use a fixed-width floating dtype")
    if not np.isfinite(scores).all():
        raise ValueError("non-finite logits")
    # Both NumPy and source torch.argmax select the first equal maximum.
    predictions = scores.argmax(axis=1).astype(np.int64, copy=False)
    return ids, scores, predictions


class FeatureOnlyDataset(Dataset):
    """Read data/case_ids only, preserving source per-row normalization."""

    def __init__(self, path, mean, std, *, expected_rows=1000, expected_shape=(306, 250)):
        _require_file_rows(expected_rows)
        if expected_shape is None or not expected_shape or any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in expected_shape):
            raise ValueError("an explicit positive feature shape is required")
        self.path = Path(path)
        with h5py.File(self.path, "r") as handle:
            if set(handle.keys()) != {"data", "case_ids"} or handle.attrs or handle.userblock_size:
                raise ValueError("candidate features must contain only data and case_ids without attributes")
            data = _local_dataset(handle, "data")
            ids = _local_dataset(handle, "case_ids")
            if data.ndim < 2 or data.dtype.kind != "f" or data.dtype.itemsize != 4:
                raise ValueError("data must be a source-compatible float32 case-by-feature array")
            self.length = data.shape[0]
            self.data_shape = tuple(data.shape[1:])
            _validate_rows(self.length, expected_rows)
            if self.data_shape != tuple(expected_shape):
                raise ValueError("feature shape differs from declared support")
            if ids.shape != (self.length, 16) or ids.dtype != np.dtype("uint8"):
                raise ValueError("case ID metadata differs from the prepared format")
            self.case_ids = normalize_case_ids(ids[...])
            if len(self.case_ids) != self.length:
                raise ValueError("case ID length differs from data")
        self.mean = np.asarray(mean)
        self.std = np.asarray(std)
        expected = (int(np.prod(self.data_shape)),)
        if self.mean.shape != expected or self.std.shape != expected:
            raise ValueError("normalization shape differs from flattened source features")
        if self.mean.dtype != np.dtype("float64") or self.std.dtype != np.dtype("float64"):
            raise ValueError("source normalization arrays must retain float64 dtype")
        if not np.isfinite(self.mean).all() or not np.isfinite(self.std).all() or np.any(self.std <= 0):
            raise ValueError("normalization must be finite with positive source-adjusted std")

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        with h5py.File(self.path, "r") as handle:
            # Schema is checked at construction. Runtime file custody/isolation
            # remains the operator's separate responsibility.
            value = handle["data"][index]
        if not np.isfinite(value).all():
            raise ValueError("non-finite feature input")
        value = value.flatten()  # Source uses C-order ndarray.flatten().
        value = (value - self.mean) / self.std
        return torch.FloatTensor(value), index


def predict_h5(model, feature_path, mean, std, *, expected_model_state_sha256=None, batch_size=32, device="cpu", expected_rows=1000, expected_shape=(306, 250)):
    """Return all ordered per-case outputs without labels or accuracy.

    This callable performs model inference when explicitly invoked. It must not
    be used on authentic inputs under source/construction-only authorization.
    The caller owns process/network/filesystem isolation and input provenance.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if not isinstance(model, torch.nn.Module):
        raise ValueError("model must be a torch Module supplied by the trusted runtime")
    if not isinstance(expected_model_state_sha256, str) or not _HEX256.fullmatch(expected_model_state_sha256):
        raise ValueError("an explicit prior model-state freeze hash is required")
    target_device = torch.device(device)
    model.to(target_device)
    model.eval()
    before = model_state_sha256(model)
    if before != expected_model_state_sha256:
        raise ValueError("model state differs from the declared prior freeze")
    dataset = FeatureOnlyDataset(feature_path, mean, std, expected_rows=expected_rows, expected_shape=expected_shape)
    # Match the original test loader: no shuffle, no new generator or seed
    # reset, num_workers=0, and the author's CUDA-dependent pin_memory flag.
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=torch.cuda.is_available())
    chunks = []
    seen_indices = []
    native_predictions = []
    output_dtype = None
    with torch.no_grad():
        for inputs, indices in loader:
            output = model(inputs.to(target_device))
            if not isinstance(output, torch.Tensor) or output.ndim != 2 or output.shape != (len(indices), NUM_CLASSES):
                raise ValueError("model output must be a (batch, 10) tensor")
            if not output.is_floating_point() or not torch.isfinite(output).all().item():
                raise ValueError("model output must be finite floating logits")
            if output_dtype is None:
                output_dtype = output.dtype
            elif output.dtype != output_dtype:
                raise ValueError("model output dtype changed between batches")
            native_predictions.append(output.argmax(dim=1).detach().cpu().numpy())
            # bfloat16 values are exactly representable in float32. Other
            # supported numeric dtypes retain their original values/dtype.
            stored = output.float() if output.dtype == torch.bfloat16 else output
            try:
                chunks.append(stored.detach().cpu().numpy().copy())
            except (TypeError, RuntimeError) as exc:
                raise ValueError("unsupported numeric logits dtype") from exc
            seen_indices.extend(indices.tolist())
    after = model_state_sha256(model)
    if before != after:
        raise ValueError("model numeric state changed during prediction")
    if seen_indices != list(range(len(dataset))):
        raise ValueError("prediction order or support differs from original case order")
    ids, logits, predictions = validate_logits(dataset.case_ids, np.concatenate(chunks), expected_rows=expected_rows)
    if not np.array_equal(predictions, np.concatenate(native_predictions)):
        raise ValueError("stored logits do not preserve native argmax predictions")
    return {"case_ids": ids, "logits": logits, "predictions": predictions, "model_state_sha256": before}


def write_predictions(path, payload) -> None:
    """Write a fresh, numeric HDF5 artifact containing no target field."""
    if set(payload) != {"case_ids", "logits", "predictions", "model_state_sha256"}:
        raise ValueError("unexpected prediction payload fields")
    ids, logits, predictions = validate_logits(payload["case_ids"], payload["logits"])
    _require_file_rows(len(ids))
    supplied = np.asarray(payload["predictions"])
    if supplied.dtype.kind not in "iu" or not np.array_equal(supplied, predictions):
        raise ValueError("supplied predictions disagree with logits")
    state_hash = payload.get("model_state_sha256")
    if not isinstance(state_hash, str) or not _HEX256.fullmatch(state_hash):
        raise ValueError("missing numeric model-state fingerprint")
    destination = Path(path)
    if destination.exists():
        raise FileExistsError(destination)
    with h5py.File(destination, "x") as handle:
        handle.attrs.create("schema", np.bytes_(PREDICTION_SCHEMA))
        handle.attrs.create("model_state_sha256", np.bytes_(state_hash))
        handle.create_dataset("case_ids", data=ids)
        handle.create_dataset("logits", data=logits)
        handle.create_dataset("predictions", data=predictions)


def read_predictions(path, *, expected_rows=1000):
    """Read only the bounded numeric prediction format, never pickle/objects."""
    _require_file_rows(expected_rows)
    with h5py.File(path, "r") as handle:
        if set(handle.keys()) != {"case_ids", "logits", "predictions"} or handle.userblock_size:
            raise ValueError("unexpected prediction fields")
        if set(handle.attrs.keys()) != {"schema", "model_state_sha256"}:
            raise ValueError("unexpected prediction metadata")
        for name, length in (("schema", len(PREDICTION_SCHEMA)), ("model_state_sha256", 64)):
            attr = handle.attrs.get_id(name)
            if attr.shape != () or attr.dtype.kind != "S" or attr.dtype.itemsize != length:
                raise ValueError("prediction metadata must use bounded fixed-width text")
        if bytes(handle.attrs["schema"]) != PREDICTION_SCHEMA.encode("ascii"):
            raise ValueError("unexpected prediction schema")
        ids_ds = _local_dataset(handle, "case_ids")
        logits_ds = _local_dataset(handle, "logits")
        predictions_ds = _local_dataset(handle, "predictions")
        if ids_ds.ndim != 2 or ids_ds.shape[1:] != (16,) or ids_ds.dtype != np.dtype("uint8"):
            raise ValueError("case ID metadata differs from the prepared format")
        rows = ids_ds.shape[0]
        _validate_rows(rows, expected_rows)
        if logits_ds.shape != (rows, NUM_CLASSES) or logits_ds.dtype.kind != "f" or logits_ds.dtype.itemsize not in (2, 4, 8):
            raise ValueError("invalid logits metadata")
        if predictions_ds.shape != (rows,) or predictions_ds.dtype.kind not in "iu":
            raise ValueError("invalid prediction metadata")
        case_ids = ids_ds[...]
        logits = logits_ds[...]
        supplied = predictions_ds[...]
        try:
            state_hash = bytes(handle.attrs["model_state_sha256"]).decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid model-state fingerprint encoding") from exc
    ids, scores, predictions = validate_logits(case_ids, logits, expected_rows=expected_rows)
    if supplied.dtype.kind not in "iu" or not np.array_equal(supplied, predictions):
        raise ValueError("stored predictions disagree with logits")
    if not isinstance(state_hash, str) or not _HEX256.fullmatch(state_hash):
        raise ValueError("invalid model-state fingerprint")
    return {"case_ids": ids, "logits": scores, "predictions": predictions, "model_state_sha256": state_hash}

