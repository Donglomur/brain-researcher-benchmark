"""Stream complete paired-BeRST TIFFs through a single raw-derived soma ROI.

This operator component outputs fluorescence AU, never voltage or a paper score.
It does not select an ROI, fit a denoiser, read EP, or change the source panel.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import tifffile

TASK_ID = "PAPER-paper-method-030"
N_FRAMES = 5000
SAMPLE_RATE_HZ = 500
ROOT = Path(__file__).resolve().parent
POPULATION = ROOT.parent / "initial-evaluator-v1" / "population.json"
MAX_FRAME_BYTES = 64 * 1024 * 1024


class InputError(ValueError):
    """Incomplete, mismatched, or unsupported optical input."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InputError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def read_json(path: Path) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(InputError("nonfinite JSON constant")))


def _path(value: Any, base: Path) -> Path:
    require(isinstance(value, str) and bool(value), "input path required")
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_roi(spec: dict[str, Any], raw_sha256: str, shape: tuple[int, int], base: Path) -> np.ndarray:
    """Read an operator-frozen binary mask; provenance is not an isolation proof."""
    require(set(spec) == {"path", "sha256", "source_raw_sha256", "selection_policy", "evidence_sha256"},
            "ROI requires exact path/hash/raw source/selection/evidence fields")
    require(valid_hash(spec["sha256"]) and valid_hash(spec["evidence_sha256"]), "ROI evidence hashes required")
    require(spec["source_raw_sha256"] == raw_sha256, "ROI is bound to a different raw movie")
    require(spec["selection_policy"] == "raw_only_frozen_before_method_comparison", "raw-only frozen ROI required")
    with _path(spec["path"], base).open("rb") as handle:
        data = handle.read(MAX_FRAME_BYTES + 1)
    require(len(data) <= MAX_FRAME_BYTES, "ROI file exceeds component bound")
    require(sha256_bytes(data) == spec["sha256"], "ROI file hash mismatch")
    # JSON has no executable deserialization or hidden array-axis conventions.
    values = json.loads(data)
    mask = np.asarray(values)
    require(mask.shape == shape and mask.dtype.kind in "biu", "ROI must be a binary y,x matrix with the declared shape")
    require(bool(np.all((mask == 0) | (mask == 1))) and bool(np.any(mask)), "ROI must contain one or more selected pixels and only 0/1")
    return mask.astype(bool)


def stream_roi_mean(path: Path, expected_sha256: str, mask: np.ndarray,
                    expected_frames: int = N_FRAMES, expected_bytes: int | None = None,
                    source_md5_base64: str | None = None) -> tuple[list[float], dict[str, Any]]:
    """Read one grayscale page at a time; never call whole-stack asarray.

    expected_frames is parameterized for generated controls. The public panel
    path always supplies the original manifest's 5000 frames without trimming.
    """
    require(valid_hash(expected_sha256), "movie SHA-256 required")
    require(isinstance(expected_frames, int) and not isinstance(expected_frames, bool) and expected_frames > 0,
            "positive frame count required")
    require(mask.ndim == 2 and mask.dtype == np.bool_ and bool(mask.any()), "nonempty binary ROI required")
    require(mask.size * 8 <= MAX_FRAME_BYTES, "frame exceeds component memory bound")
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if expected_bytes is not None:
            require(before.st_size == expected_bytes, "movie byte count differs from frozen source")
        digest = hashlib.sha256()
        md5 = hashlib.md5(usedforsecurity=False)
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            md5.update(chunk)
        require(digest.hexdigest() == expected_sha256, "movie content hash mismatch")
        md5_base64 = base64.b64encode(md5.digest()).decode("ascii")
        if source_md5_base64 is not None:
            require(md5_base64 == source_md5_base64, "raw movie differs from cached GCS content checksum")
        handle.seek(0)
        trace = []
        with tifffile.TiffFile(handle) as movie:
            require(len(movie.pages) == expected_frames, "complete movie page count required; trimming is forbidden")
            for page in movie.pages:
                require(tuple(page.shape) == mask.shape and page.samplesperpixel == 1,
                        "expected exactly one grayscale y,x image per TIFF page")
                require(page.photometric == tifffile.PHOTOMETRIC.MINISBLACK,
                        "only MINISBLACK numeric grayscale TIFF intensities are supported")
                orientation = page.tags.get("Orientation")
                require(orientation is None or orientation.value == 1,
                        "TIFF orientation must preserve top-left y,x pixel coordinates")
                require(page.dtype.kind in "iuf" and page.dtype.itemsize <= 8, "unsupported pixel dtype")
                require(page.size * page.dtype.itemsize <= MAX_FRAME_BYTES, "TIFF frame exceeds component memory bound")
                # Explicit maxworkers=1 also bounds compressed-page decoding.
                frame = page.asarray(maxworkers=1)
                require(bool(np.all(np.isfinite(frame))), "nonfinite movie pixel")
                with np.errstate(over="raise", invalid="raise"):
                    try:
                        value = float(np.mean(frame[mask], dtype=np.float64))
                    except FloatingPointError as exc:
                        raise InputError("ROI mean exceeds finite numeric range") from exc
                require(np.isfinite(value), "nonfinite ROI mean")
                trace.append(value)
        after = os.fstat(handle.fileno())
        fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(fingerprint(before) == fingerprint(after), "movie changed during extraction")
    return trace, {"sha256": expected_sha256, "bytes": before.st_size,
                   "md5_base64": md5_base64, "cached_gcs_md5_verified": source_md5_base64 is not None,
                   "frame_count": len(trace), "shape_yx": list(mask.shape), "roi_pixels": int(mask.sum())}


def validate_panel(panel: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    require(set(panel) == {"schema_version", "task_id", "population_sha256", "methods", "recordings"}, "unsupported panel fields")
    require(panel["schema_version"] == 1 and panel["task_id"] == TASK_ID, "wrong task or schema")
    require(panel["population_sha256"] == sha256_bytes(POPULATION.read_bytes()), "population hash mismatch")
    catalogue = {row["recording_id"]: row for row in read_json(POPULATION)["recordings"]}
    methods = panel["methods"]
    require(isinstance(methods, list) and all(isinstance(m, str) and m for m in methods), "named methods required")
    require(len(methods) == len(set(methods)) and "raw" in methods and "cellmincer" in methods
            and bool({"pmd", "n2s"} & set(methods)), "raw, CellMincer and PMD or N2S required exactly once")
    rows = panel["recordings"]
    require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), "recording list required")
    require(len(rows) == len(catalogue) and {r.get("recording_id") for r in rows} == set(catalogue),
            "all 22 saved recording identities required exactly once")
    for row in rows:
        require(set(row) == {"recording_id", "cell_id", "shape_yx", "roi", "movies"}, "unsupported recording fields")
        source = catalogue[row["recording_id"]]
        require(row["cell_id"] == source["cell_id"], "cell identity mismatch")
        shape = row["shape_yx"]
        require(isinstance(shape, list) and len(shape) == 2 and all(type(v) is int and v > 0 for v in shape), "positive y,x shape required")
        require(shape[0] * shape[1] * 8 <= MAX_FRAME_BYTES, "frame exceeds component memory bound")
        require(isinstance(row["movies"], dict) and set(row["movies"]) == set(methods), "identical method coverage required")
        for method, movie in row["movies"].items():
            fields = {"path", "sha256", "source_object"} if method == "raw" else {"path", "sha256"}
            require(isinstance(movie, dict) and set(movie) == fields and valid_hash(movie["sha256"]), "movie path and content pin required")
            if method == "raw":
                require(movie["source_object"] == source["raw_tiff"], "raw source object identity mismatch")
    return rows, catalogue


def extract_panel(panel: dict[str, Any], base: Path) -> dict[str, Any]:
    rows, catalogue = validate_panel(panel)
    raw_checksums = read_json(ROOT / "raw-md5.json")
    require(set(raw_checksums) == set(catalogue), "raw checksum coverage differs from catalogue")
    prepared = []
    for row in sorted(rows, key=lambda r: r["recording_id"]):
        raw = row["movies"]["raw"]
        mask = load_roi(row["roi"], raw["sha256"], tuple(row["shape_yx"]), base)
        traces, receipts = {}, {}
        for method in panel["methods"]:
            movie = row["movies"][method]
            trace, receipt = stream_roi_mean(_path(movie["path"], base), movie["sha256"], mask,
                expected_frames=N_FRAMES, expected_bytes=int(raw["source_object"]["bytes"]) if method == "raw" else None,
                source_md5_base64=raw_checksums[row["recording_id"]] if method == "raw" else None)
            traces[method], receipts[method] = trace, receipt
        prepared.append({"recording_id": row["recording_id"], "cell_id": row["cell_id"],
                         "raw_source_object": catalogue[row["recording_id"]]["raw_tiff"],
                         "roi_sha256": row["roi"]["sha256"], "roi_selection_evidence_sha256": row["roi"]["evidence_sha256"],
                         "fluorescence_au": traces, "movie_receipts": receipts})
    return {"task_id": TASK_ID, "schema_version": 1, "scope": "complete_saved_22_optical_roi_extraction",
            "population_sha256": panel["population_sha256"], "units": "fluorescence_arbitrary_units",
            "sampling_rate_hz": SAMPLE_RATE_HZ, "time_origin": "first_optical_frame_no_ep_alignment",
            "axis_order": "tyx", "roi_policy": "one_raw_only_frozen_mask_shared_by_all_methods",
            "frames_per_recording": N_FRAMES, "recordings": prepared,
            "qualification": "optical_extraction_only_not_original_panel_or_paper_score",
            "remaining_gaps": ["Original 26-training/22-evaluation membership is not established by saved inventory.",
                               "ROI declarations and evidence hashes do not authenticate historical masks or prove raw-only selection.",
                               "No EP channel conversion, clock mapping, detrending, affine calibration, or denoiser qualification.",
                               "Original prominence bins, spectral mask and aggregation remain unresolved."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    temporary = None
    try:
        require(not args.output.exists(), "refusing to replace existing extraction output")
        result = extract_panel(read_json(args.panel), args.panel.resolve().parent)
        with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, prefix=".roi-extract-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(result, handle, allow_nan=False, separators=(",", ":"))
            handle.write("\n")
        # Hard-link publication is atomic and fails if a concurrent writer won.
        os.link(temporary, args.output)
    except (InputError, KeyError, TypeError, OSError, ValueError) as exc:
        parser.exit(2, f"invalid optical extraction input: {exc}\n")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
