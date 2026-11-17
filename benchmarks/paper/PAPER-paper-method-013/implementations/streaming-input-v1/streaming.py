"""Stream source-sized DeepCaImX tiles and decode released full-model outputs.

This implements source-derived arithmetic, not scientific admission. The caller
must supply the unresolved raw-movie frame/crop mapping explicitly. No threshold,
cross-tile merger, model loader, training, or reproduction decision is supplied.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Iterator

import numpy as np

TASK_ID = "PAPER-paper-method-013"
AUTHOR_REVISION = "305a4827929b2c6e82e44c5c69b2ea9d410e20a4"
RECORDINGS = (
    "501271265", "501704220", "524691284", "531006860", "603516552",
    "604145810", "607040613", "669233895", "671162628", "679353932",
)
MAPPING_SCHEMA = "deepcaimx-explicit-movie-mapping/v1"
TILE_COUNT = 9 * 9 * 13
MODEL_INPUT_SHAPE = (1, 400, 64, 64, 1)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def integer(value: Any, name: str, low: int, high: int) -> int:
    require(type(value) is int and low <= value <= high,
            f"{name} must be an integer in [{low}, {high}]")
    return value


def tile_geometry(index: int) -> dict[str, Any]:
    """MATLAB order: row fastest, column next, temporal block last.

    The source tailor's nt=100 default is explicitly replaced by the paper's
    nt=400 setting. The 488-pixel field fits nine step-53 spatial tiles exactly;
    the final 400-frame tile contains 200 observations followed by 200 zeros.
    """
    index = integer(index, "tile index", 0, TILE_COUNT - 1)
    row, column, time = index % 9, (index // 9) % 9, index // 81
    start = [time * 400, row * 53, column * 53]
    return {
        "tile_index": index,
        "axes": ["time", "row", "column"],
        "start_zero_based": start,
        "stop_exclusive": [start[0] + 400, start[1] + 64, start[2] + 64],
        "valid_stop_exclusive": [min(start[0] + 400, 5000), start[1] + 64, start[2] + 64],
        "valid_frames": min(400, 5000 - start[0]),
    }


def validate_mapping(mapping: Any, shape: Any) -> dict[str, Any]:
    """Validate an operator declaration; do not certify its historical truth."""
    require(isinstance(mapping, dict), "mapping must be an object")
    keys = {"schema", "task_id", "recording_id", "source_shape",
            "frame_start_zero_based", "crop_row_start", "crop_column_start",
            "mapping_evidence"}
    require(set(mapping) == keys, "mapping has missing or unknown fields")
    require(mapping["schema"] == MAPPING_SCHEMA, "wrong mapping schema")
    require(mapping["task_id"] == TASK_ID, "wrong task")
    require(mapping["recording_id"] in RECORDINGS, "recording is outside original panel")
    require(isinstance(mapping["source_shape"], list) and len(mapping["source_shape"]) == 3,
            "source_shape must name time,row,column")
    declared = mapping["source_shape"]
    for value in declared:
        integer(value, "source dimension", 1, 2**31 - 1)
    require(declared[1:] == [512, 512], "official movie must have 512x512 source frames")
    require(tuple(declared) == tuple(shape), "declared and actual movie shapes differ")
    require(declared[0] >= 5000, "source movie cannot contain the complete interval")
    integer(mapping["frame_start_zero_based"], "frame start", 0, declared[0] - 5000)
    integer(mapping["crop_row_start"], "crop row start", 0, 24)
    integer(mapping["crop_column_start"], "crop column start", 0, 24)
    evidence = mapping["mapping_evidence"]
    require(isinstance(evidence, str) and 0 < len(evidence.strip()) <= 4096,
            "explicit mapping evidence or unresolved-declaration description required")
    # Copy scalar/list values so caller mutation cannot alter an iterator's plan.
    return {**mapping, "source_shape": list(declared)}


def model_input(dataset: Any, mapping: dict[str, Any], index: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Read exactly one bounded slab, zero-pad, then apply MATLAB single min/max.

    ``dataset`` exposes shape, dtype and slicing (e.g. an h5py data dataset).
    It must contain original uint16 samples in time,row,column order. A constant
    padded tile raises: the source formula would divide by zero, and replacing
    it with an invented zero-valued input would change the source procedure.
    """
    plan = validate_mapping(mapping, dataset.shape)
    dtype = np.dtype(dataset.dtype)
    require(dtype.kind == "u" and dtype.itemsize == 2, "source samples must be uint16")
    geometry = tile_geometry(index)
    t, r, c = geometry["start_zero_based"]
    n = geometry["valid_frames"]
    fs, rs, cs = plan["frame_start_zero_based"], plan["crop_row_start"], plan["crop_column_start"]
    bounds = (slice(fs + t, fs + t + n), slice(rs + r, rs + r + 64),
              slice(cs + c, cs + c + 64))
    block = np.asarray(dataset[bounds])
    require(block.shape == (n, 64, 64), "reader returned an incomplete source slab")
    require(block.dtype.kind == "u" and block.dtype.itemsize == 2,
            "reader changed the source dtype")
    # uint16 values are represented exactly in binary32. Padding participates in
    # min/max, exactly as in tailor.m; do not normalize real samples first.
    tile = np.zeros((400, 64, 64), dtype=np.float32)
    tile[:n] = block
    minimum, maximum = tile.min(), tile.max()
    span = np.float32(maximum - minimum)
    require(bool(np.isfinite(span)) and span > 0, "source normalization has zero or invalid span")
    np.subtract(tile, minimum, out=tile)
    np.divide(tile, span, out=tile)
    require(bool(np.isfinite(tile).all()), "normalization produced nonfinite input")
    metadata = {
        **geometry, "recording_id": plan["recording_id"],
        "source_slice_start": [bounds[0].start, bounds[1].start, bounds[2].start],
        "source_slice_stop": [bounds[0].stop, bounds[1].stop, bounds[2].stop],
        "normalization": "single_precision_minmax_after_zero_padding",
        "padded_minimum": float(minimum), "padded_maximum": float(maximum),
        "mapping_authentication": "unestablished_by_this_component",
    }
    return tile[None, ..., None], metadata


def iter_model_inputs(dataset: Any, mapping: dict[str, Any]) -> Iterator[tuple[np.ndarray, dict[str, Any]]]:
    """Yield every tile once without retaining a whole movie or tile bank."""
    plan = validate_mapping(mapping, dataset.shape)
    for index in range(TILE_COUNT):
        yield model_input(dataset, plan, index)


def iter_panel_inputs(open_recording: Any, mappings: dict[str, Any]) -> Iterator[tuple[np.ndarray, dict[str, Any]]]:
    """Stream all 10,530 tiles in the fixed original ten-recording panel order.

    ``open_recording(recording_id)`` supplies a context manager yielding the
    operator's dataset. Mapping declarations are checked before opening the
    first movie. Only one source handle and the current input tile are needed;
    normal generator close/error unwinds the active source context.
    """
    require(isinstance(mappings, dict) and set(mappings) == set(RECORDINGS),
            "exact original ten-recording mapping panel required")
    plans = {}
    for rid in RECORDINGS:
        row = mappings[rid]
        require(isinstance(row, dict), "each recording mapping must be an object")
        plan = validate_mapping(row, row.get("source_shape", ()))
        require(plan["recording_id"] == rid, "mapping panel recording identity mismatch")
        plans[rid] = plan
    for rid in RECORDINGS:
        with open_recording(rid) as dataset:
            yield from iter_model_inputs(dataset, plans[rid])


def decode_outputs(segmentation: Any, traces: Any, tile_index: int) -> dict[str, np.ndarray]:
    """Expose released eight-channel fields and exact trace support, unassembled.

    The final eight segmentation slices are morphological *fields*, not known
    binary masks. Raw values are retained. No threshold/ROI merging is inferred.
    The display-normalized trace follows the demo's joint maximum over all eight
    channels; it is separate from the unmodified scientific model output.
    """
    geometry = tile_geometry(tile_index)
    seg, trace = np.asarray(segmentation), np.asarray(traces)
    require(seg.shape == (1, 416, 64, 64, 1), "released segmentation shape must be 1x416x64x64x1")
    require(trace.shape == (1, 396, 8), "released trace shape must be 1x396x8")
    require(seg.dtype == np.float32 and trace.dtype == np.float32,
            "released model outputs must retain float32 dtype")
    require(bool(np.isfinite(seg).all()) and bool(np.isfinite(trace).all()), "nonfinite model output")
    require(bool((seg >= 0).all()), "released segmentation fields cannot be negative")
    require(bool((trace >= 0).all()), "released ReLU traces cannot be negative")
    raw = seg[0, 400:408, :, :, 0].copy()
    morphological = seg[0, 408:416, :, :, 0].copy()
    native_trace = trace[0].copy()
    denominator = np.max(native_trace) + 1e-3
    display_trace = native_trace / denominator
    # For the validated nonnegative fields, the demo's sum==0 is exactly the
    # all-zero predicate. Avoid a potentially overflowing sum; add no threshold.
    display_trace[:, ~np.any(morphological != 0, axis=(1, 2))] = 0
    require(bool(np.isfinite(display_trace).all()), "display normalization produced nonfinite output")
    frames = geometry["start_zero_based"][0] + np.arange(2, 398, dtype=np.int64)
    return {
        "raw_footprint_fields": raw,
        "morphological_footprint_fields": morphological,
        "raw_traces_time_roi": native_trace,
        "demo_display_traces_time_roi": display_trace,
        "trace_frame_indices_zero_based": frames,
        "trace_within_observed_interval": frames < 5000,
    }


def _identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


@contextmanager
def ordinary_input(path: str | Path):
    """Stable ordinary-file handle; this is not source-content authentication."""
    # Nonblocking open lets the ordinary-file check reject a FIFO immediately,
    # rather than waiting indefinitely for a writer before fstat can run.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "ordinary source file required")
        yield stream, before
        require(_identity(before) == _identity(os.fstat(stream.fileno())), "input changed during operation")


def read_mapping(path: str | Path) -> tuple[dict[str, Any], str]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate mapping key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    with ordinary_input(path) as (stream, info):
        require(0 < info.st_size <= 65536, "mapping must be at most 64 KiB")
        body = stream.read(65537)
        require(len(body) == info.st_size, "mapping size changed")
    mapping = json.loads(body, object_pairs_hook=unique, parse_constant=constant)
    return mapping, hashlib.sha256(body).hexdigest()


def export_tile(movie_path: str | Path, mapping_path: str | Path, index: int,
                output_path: str | Path) -> dict[str, Any]:
    """Export one declared tile from a local official-layout HDF5 `data` dataset.

    The output is a numeric NPZ containing the model input and UTF-8 JSON receipt.
    It makes no network/model calls. Whole-panel execution uses iter_model_inputs
    inside a separately admitted operator; this CLI is not a study supervisor.
    """
    import h5py

    index = integer(index, "tile index", 0, TILE_COUNT - 1)
    output = Path(output_path)
    require(not output.exists() and not output.is_symlink(), "output already exists")
    mapping, mapping_hash = read_mapping(mapping_path)
    with ordinary_input(movie_path) as (stream, info):
        with h5py.File(stream, "r") as source:
            # Refuse HDF external/soft links, virtual datasets and external raw
            # storage: one declared file must not open undeclared source paths.
            require(isinstance(source.get("data", getlink=True), h5py.HardLink),
                    "data must be a local hard-linked dataset")
            dataset = source["data"]
            require(isinstance(dataset, h5py.Dataset), "data must be a dataset")
            require(not dataset.is_virtual and dataset.external is None,
                    "virtual or external dataset storage is not supported")
            require(dataset.chunks == (1, 512, 512)
                    and dataset.id.get_create_plist().get_nfilters() == 0,
                    "official unfiltered one-frame HDF chunk layout required")
            array, receipt = model_input(dataset, mapping, index)
        receipt.update({
            "schema": "deepcaimx-streamed-tile/v1", "task_id": TASK_ID,
            "author_revision": AUTHOR_REVISION,
            "source_file_bytes": info.st_size,
            "source_file_content_authentication": "not_established",
            "mapping_sha256": mapping_hash,
            "mapping_declaration": mapping,
            "input_shape": list(array.shape), "input_dtype": str(array.dtype),
            "scientific_qualification": "unestablished",
        })
    encoded = json.dumps(receipt, sort_keys=True, allow_nan=False).encode("utf-8")
    # Exclusive creation happens only after all input checks. Incomplete output
    # is removed on failure; successfully written files are never overwritten.
    created = False
    try:
        with output.open("xb") as target:
            created = True
            np.savez(target, model_input=array, receipt_utf8=np.frombuffer(encoded, dtype=np.uint8))
            target.flush()
            os.fsync(target.fileno())
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--movie-hdf5", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--tile-index", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = export_tile(args.movie_hdf5, args.mapping, args.tile_index, args.output)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
