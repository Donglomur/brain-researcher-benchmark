"""Bounded-allocation MindEye2 retrieval scoring; no model or data acquisition.

The numerical engine maps the full original feature population and computes
cosines in row blocks. The source's 30 overlapping 300-image draws then index
the same matrix. This changes allocation, not populations or metric directions.
Native floating-point/device parity remains unqualified.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "mindeye2_initial_evaluator", Path(__file__).parents[1] / "initial-evaluator-v1/evaluator.py")
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)

CONTRACT_SHA256 = "97752be74ac2af84fbd8441f50e2f4e9ba1e2a518d0b90ec553f8d08d19890b0"
FEATURE_SPACE = "openclip:ViT-bigG-14:laion2b_s39b_b160k:256x1664-tokens"
FEATURE_WIDTH = 256 * 1664
MAX_BLOCK_ROWS = 32
MAX_FEATURE_BLOCK = 4096


def _shape(array, name):
    if not isinstance(array, np.ndarray) or array.dtype.kind not in "fiu":
        raise ValueError(f"{name}: real numeric ndarray required")
    if array.ndim < 2 or not array.shape[0] or np.prod(array.shape[1:]) < 2:
        raise ValueError(f"{name}: nonempty row feature vectors required")
    if not array.flags.c_contiguous:
        raise ValueError(f"{name}: C-order storage required; refusing a full-array reshape copy")
    return array.shape[0], int(np.prod(array.shape[1:]))


def _block_rows(value):
    if type(value) is not int or not 1 <= value <= MAX_BLOCK_ROWS:
        raise ValueError(f"block_rows must be an integer in 1..{MAX_BLOCK_ROWS}")
    return value


def _row_normalizers(array, rows):
    """Compute each row's overflow-safe normalization with one bounded row copy."""
    width = _shape(array, "features")[1]
    # Advanced indexing makes a bounded copy, even for an already-float64 map.
    block = np.asarray(array[rows], dtype=np.float64).reshape(len(rows), width)
    if not np.isfinite(block).all():
        raise ValueError("all declared feature rows must be finite")
    scale = np.maximum(block.max(axis=1), -block.min(axis=1))
    if np.any(scale == 0):
        raise ValueError("undefined cosine: zero feature vector")
    block /= scale[:, None]
    # Avoid an additional block-sized square temporary.
    norms = np.sqrt(np.einsum("ij,ij->i", block, block))
    return scale, norms


def _normalizers(array, block_rows):
    n = len(array)
    scale, norm = np.empty(n), np.empty(n)
    for begin in range(0, n, block_rows):
        stop = min(begin + block_rows, n)
        scale[begin:stop], norm[begin:stop] = _row_normalizers(array, np.arange(begin, stop))
    return scale, norm


def _normalized_columns(array, order, begin, stop, scale, norm):
    flat = array.reshape(len(array), -1)  # _shape already forbids copy-producing layout.
    block = np.asarray(flat[order, begin:stop], dtype=np.float64)
    block /= scale[order, None]
    block /= norm[order, None]
    return block


def cosine_matrix(brain, images, brain_order, *, block_rows=8, feature_block=1024):
    """Return brain-query/image-candidate cosines without population-sized copies.

    brain_order maps reference rows to candidate storage rows. The only dense
    population-sized result is N by N, about 8 MB for the original 1,000 images.
    This is an allocation bound, not an OS RSS/file-cache guarantee.
    """
    block_rows = _block_rows(block_rows)
    if type(feature_block) is not int or not 1 <= feature_block <= MAX_FEATURE_BLOCK:
        raise ValueError(f"feature_block must be an integer in 1..{MAX_FEATURE_BLOCK}")
    shape = _shape(brain, "brain")
    if shape != _shape(images, "images"):
        raise ValueError("paired feature geometry differs")
    n, width = shape
    order = np.asarray(brain_order)
    if order.shape != (n,) or order.dtype.kind not in "iu" or not np.array_equal(np.sort(order), np.arange(n)):
        raise ValueError("brain_order must be an exact row permutation")
    bscale, bnorm = _normalizers(brain, block_rows)
    iscale, inorm = _normalizers(images, block_rows)
    result = np.zeros((n, n), dtype=np.float64)
    image_order = np.arange(n)
    # Feature tiling reads each input twice in total instead of rereading the
    # entire image population for every brain row block. Column tiles and the
    # N*N score matrix remain small for the original 1000-image population.
    for begin in range(0, width, feature_block):
        stop = min(begin + feature_block, width)
        b = _normalized_columns(brain, order, begin, stop, bscale, bnorm)
        i = _normalized_columns(images, image_order, begin, stop, iscale, inorm)
        result += b @ i.T
    return result


def retrieval_from_cosines(similarities):
    """Corrected author directions; preserve predecessor's strict tie rejection."""
    sim = np.asarray(similarities)
    if sim.ndim != 2 or sim.shape[0] != sim.shape[1] or len(sim) < 2 or not np.isfinite(sim).all():
        raise ValueError("finite square similarity matrix required")
    result = {}
    for name, matrix in (("image_retrieval", sim), ("brain_retrieval", sim.T)):
        maximum = matrix.max(axis=1, keepdims=True)
        if np.any(np.sum(matrix == maximum, axis=1) != 1):
            raise ValueError(f"{name}: tied maximum; native tie parity is unresolved")
        result[name] = float(np.mean(matrix.argmax(axis=1) == np.arange(len(matrix))))
    return result


def score_aligned_features(ids, pools, brain, images, *, brain_order=None, block_rows=8, feature_block=1024):
    """Low-dimensional generated controls use this same numerical engine."""
    ids = legacy._ids(ids, "image_ids", 300)
    legacy.validate_pools(ids, pools)
    if _shape(brain, "brain")[0] != len(ids) or _shape(images, "images")[0] != len(ids):
        raise ValueError("feature row count differs from identities")
    order = np.arange(len(ids)) if brain_order is None else brain_order
    similarities = cosine_matrix(brain, images, order, block_rows=block_rows, feature_block=feature_block)
    locations = {name: position for position, name in enumerate(ids)}
    values = {"image_retrieval": [], "brain_retrieval": []}
    for pool in pools:
        selected = [locations[name] for name in pool]
        draw = retrieval_from_cosines(similarities[np.ix_(selected, selected)])
        for name, score in draw.items():
            values[name].append(score)
    return {name: legacy._summary(scores) for name, scores in values.items()}


def validate_reference(reference):
    if reference.get("task_id") != legacy.TASK or reference.get("contract_sha256") != CONTRACT_SHA256:
        raise ValueError("reference must bind the current original-task improvement contract")
    if reference.get("code_revision") != legacy.CODE_REVISION or reference.get("dataset_revision") != legacy.DATA_REVISION:
        raise ValueError("source revisions differ from the frozen source")
    if type(reference.get("subject")) is not int or reference["subject"] not in (1, 2, 5, 7):
        raise ValueError("paper cohort is subjects 1, 2, 5, 7")
    ids = legacy._ids(reference.get("image_ids"), "reference image_ids", 1000)
    if len(ids) != 1000:
        raise ValueError("complete original shared1000 population required")
    legacy.validate_pools(ids, reference.get("retrieval_pools"))
    if reference.get("feature_space") != FEATURE_SPACE:
        raise ValueError("original OpenCLIP token feature space required")
    for name in ("image_features_sha256", "population_manifest_sha256", "feature_extraction_receipt_sha256"):
        legacy._sha(reference.get(name), name)
    return ids


def evaluate(reference, candidate, images, brain, *, block_rows=8, feature_block=1024):
    ids = validate_reference(reference)
    if candidate.get("reference_manifest_digest") != legacy.digest(reference):
        raise ValueError("candidate reference commitment differs")
    candidate_ids = legacy._ids(candidate.get("image_ids"), "candidate image_ids", 1000)
    if set(candidate_ids) != set(ids) or type(candidate.get("subject")) is not int or candidate["subject"] != reference["subject"]:
        raise ValueError("candidate population/subject differs")
    if candidate.get("feature_space") != FEATURE_SPACE:
        raise ValueError("candidate feature space differs")
    for name in ("brain_features_sha256", "checkpoint_sha256", "exposure_ledger_sha256"):
        legacy._sha(candidate.get(name), name)
    if _shape(brain, "brain") != (1000, FEATURE_WIDTH) or _shape(images, "images") != (1000, FEATURE_WIDTH):
        raise ValueError("native retrieval requires exactly 1000 rows and 256*1664 coordinates")
    locations = {name: position for position, name in enumerate(candidate_ids)}
    metrics = score_aligned_features(ids, reference["retrieval_pools"], brain, images,
                                    brain_order=np.array([locations[name] for name in ids]),
                                    block_rows=block_rows, feature_block=feature_block)
    return {"task_id": legacy.TASK, "scope": "bounded_original_population_feature_retrieval",
            "reference_manifest_digest": legacy.digest(reference), "candidate_manifest_digest": legacy.digest(candidate),
            "population_manifest_sha256": reference["population_manifest_sha256"],
            "subject": reference["subject"], "n_images": 1000,
            "pool_digest": legacy.digest(reference["retrieval_pools"]), "metrics": metrics,
            "allocation": {"block_rows": block_rows, "feature_block": feature_block,
                           "similarity_matrix_bytes": 1000 * 1000 * 8,
                           "normalized_block_bytes_each": block_rows * FEATURE_WIDTH * 8,
                           "column_tile_bytes_each": 1000 * feature_block * 8,
                           "rss_or_page_cache_bound": False},
            "scientific_qualification": False, "full_contract_complete": False,
            "native_parity_verified": False,
            "limits": ["Feature production, repeated presentations and original exposure require authentication.",
                       "A per-subject feature score does not establish the four-subject paper result.",
                       "Full reconstruction companion panel and native author baseline remain required.",
                       "Float64 blocked arithmetic is not qualified against native GPU/TF32/float16 arithmetic.",
                       "Pool intervals describe Monte Carlo variation, not independent participants."]}


def _hash_stream(stream):
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _identity(stream):
    value = os.fstat(stream.fileno())
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


@contextmanager
def mapped_npy(path, expected_sha256):
    """Hash and map the same open regular file; forbid pickle/trailing payloads."""
    legacy._sha(expected_sha256, "array SHA-256")
    with open(path, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("ordinary NPY file required")
        identity = _identity(stream)
        if _hash_stream(stream) != expected_sha256:
            raise ValueError("array SHA-256 mismatch")
        stream.seek(0)
        version = np.lib.format.read_magic(stream)
        readers = {(1, 0): np.lib.format.read_array_header_1_0,
                   (2, 0): np.lib.format.read_array_header_2_0}
        if version not in readers:
            raise ValueError("NPY version 1.0 or 2.0 required")
        shape, fortran, dtype = readers[version](stream, max_header_size=10000)
        if dtype.kind not in "fiu" or dtype.hasobject or len(shape) < 2 or any(n <= 0 for n in shape):
            raise ValueError("primitive nonempty numeric NPY required")
        if fortran:
            raise ValueError("C-order NPY required")
        offset = stream.tell()
        # Python integer arithmetic prevents adversarial header size overflow.
        size = int(dtype.itemsize)
        for dim in shape:
            size *= dim
        if identity[2] != offset + size:
            raise ValueError("NPY size mismatch or trailing payload")
        mapped = np.memmap(stream, dtype=dtype, mode="r", offset=offset, shape=shape, order="C")
        try:
            yield mapped
            if _identity(stream) != identity:
                raise ValueError("source NPY changed during scoring")
        finally:
            mapped._mmap.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "reference-sha256", "candidate", "image-features", "brain-features"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--block-rows", type=int, default=8)
    parser.add_argument("--feature-block", type=int, default=1024)
    args = parser.parse_args(argv)
    _block_rows(args.block_rows)
    raw = Path(args.reference).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.reference_sha256:
        raise ValueError("trusted reference SHA-256 mismatch")
    reference = json.loads(raw)
    candidate = json.loads(Path(args.candidate).read_text())
    validate_reference(reference)
    with mapped_npy(args.image_features, reference["image_features_sha256"]) as images:
        with mapped_npy(args.brain_features, candidate["brain_features_sha256"]) as brain:
            result = evaluate(reference, candidate, images, brain, block_rows=args.block_rows,
                              feature_block=args.feature_block)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
