"""Bounded operator-only admission of the source Figure 1 reference panel.

Byte identity and a valid native layout do not prove publication provenance,
source execution, candidate data use, reproduction or improvement.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

import numpy as np


SCHEMA = "rastermap-figure1-reference-panel/v1"
METHODS = ("rastermap", "t-SNE", "UMAP", "isomap", "laplacian eigenmaps",
           "hierarchical clustering", "PCA")
MODULES = ("tuning", "sustained", "sequence 1", "sequence 2", "power-law")
METRICS = ("contamination", "correct_triplets")
SHAPES = {"scores_all.npy": (10, 2, 8, 5), "embs_all.npy": (10, 7, 6000, 1)}
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_HEADER_BYTES = 4096
SCORER_SHA256 = "392a4ff40fa8764d994d42d978fe3735a983f707552957ade8423a0acf70d4d9"
SCORER_PATH = Path(__file__).resolve().parents[1] / "figure1-scorer-v1" / "scorer.py"


class InvalidPanel(ValueError):
    """An artifact does not satisfy the narrow original producer layout."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pin(value):
    if (not isinstance(value, str) or len(value) != 64 or
            any(c not in "0123456789abcdef" for c in value)):
        raise InvalidPanel("expected_sha256 must be 64 lowercase hexadecimal characters")
    return value


def _primitive_npy(payload, expected_shape):
    """Validate geometry and primitive type before constructing an array view."""
    if payload[:6] != b"\x93NUMPY" or len(payload) < 10:
        raise InvalidPanel("member is not an NPY file")
    version = tuple(payload[6:8])
    if version == (1, 0):
        width, code = 2, "<H"
    elif version == (2, 0):
        width, code = 4, "<I"
    else:
        raise InvalidPanel("only primitive NPY versions 1.0 and 2.0 are admitted")
    if len(payload) < 8 + width:
        raise InvalidPanel("truncated NPY header length")
    size = struct.unpack(code, payload[8:8 + width])[0]
    offset = 8 + width + size
    if not 0 < size <= MAX_HEADER_BYTES or offset > len(payload):
        raise InvalidPanel("invalid or oversized NPY header")
    header = payload[8 + width:offset]
    if not header.endswith(b"\n"):
        raise InvalidPanel("NPY header must end with newline")
    try:
        tree = ast.parse(header.decode("latin1").strip(), mode="eval")
        if not isinstance(tree.body, ast.Dict):
            raise InvalidPanel("NPY header must be a dictionary")
        keys = [ast.literal_eval(k) for k in tree.body.keys]
        if len(keys) != 3 or set(keys) != {"descr", "fortran_order", "shape"}:
            raise InvalidPanel("NPY header contains duplicate or unexpected fields")
        meta = ast.literal_eval(tree)
    except (SyntaxError, UnicodeError, ValueError, TypeError) as exc:
        raise InvalidPanel("invalid NPY header") from exc
    shape = meta["shape"]
    if (type(shape) is not tuple or any(type(n) is not int for n in shape)
            or shape != expected_shape):
        raise InvalidPanel("array does not retain the complete original axes")
    if meta["fortran_order"] is not False:
        raise InvalidPanel("the original producer stores C-order arrays")
    if not isinstance(meta["descr"], str):
        raise InvalidPanel("structured and object dtypes are not admitted")
    try:
        dtype = np.dtype(meta["descr"])
    except TypeError as exc:
        raise InvalidPanel("invalid primitive dtype") from exc
    if dtype.kind != "f" or dtype.itemsize != 8 or dtype.hasobject:
        raise InvalidPanel("the original producer stores float64 arrays")
    count = 1
    for n in expected_shape:
        count *= n
    if len(payload) != offset + 8 * count:
        raise InvalidPanel("NPY extent differs from its complete fixed geometry")
    array = np.frombuffer(payload, dtype=dtype, count=count, offset=offset).reshape(shape)
    if not np.isfinite(array).all():
        raise InvalidPanel("all original coordinates and scores must be finite")
    return array


def load_panel(payload, expected_sha256):
    """Admit bytes once; never unpickle, extract files or execute author code."""
    if not isinstance(payload, bytes) or len(payload) > MAX_ARCHIVE_BYTES:
        raise InvalidPanel("reference archive must be bytes within 5 MiB")
    if _sha(payload) != _pin(expected_sha256):
        raise InvalidPanel("reference archive SHA-256 mismatch")
    arrays, members = {}, {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != 2 or set(names) != set(SHAPES):
                raise InvalidPanel("archive must contain exactly scores_all.npy and embs_all.npy")
            for info in entries:
                if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise InvalidPanel("encrypted or unsupported compressed member")
                expected_shape = SHAPES[info.filename]
                count = 1
                for n in expected_shape:
                    count *= n
                bound = count * 8 + MAX_HEADER_BYTES + 12
                if not 0 < info.file_size <= bound:
                    raise InvalidPanel("declared member extent exceeds its fixed geometry")
                with archive.open(info) as stream:
                    body = stream.read(bound + 1)
                if len(body) > bound or len(body) != info.file_size:
                    raise InvalidPanel("expanded member exceeds the admitted bound")
                arrays[info.filename] = _primitive_npy(body, expected_shape)
                members[info.filename] = {"bytes": len(body), "sha256": _sha(body)}
    except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise InvalidPanel("invalid reference archive") from exc
    scores = arrays["scores_all.npy"]
    if ((scores < 0) | (scores > 1)).any():
        raise InvalidPanel("source score arrays must contain fractions in [0, 1]")
    return arrays, members


def _summarizer(scorer_path):
    """Use the existing verified aggregation; hash and execute the same bytes."""
    path = Path(scorer_path)
    with path.open("rb") as handle:
        body = handle.read(16385)
    if len(body) > 16384 or _sha(body) != SCORER_SHA256:
        raise InvalidPanel("existing Figure 1 scorer source pin does not match")
    namespace = {"__name__": "_rastermap_source_summary", "__file__": str(path)}
    exec(compile(body, str(path), "exec"), namespace)
    return namespace["summarize_panel"]


def report_panel(payload, expected_sha256, *, scorer_path=None):
    """Return the complete source-shaped panel with explicit provenance limits."""
    arrays, members = load_panel(payload, expected_sha256)
    summary = _summarizer(SCORER_PATH if scorer_path is None else scorer_path)(
        arrays["scores_all.npy"], list(range(10)))
    embeddings = arrays["embs_all.npy"]
    return {
        "schema": SCHEMA,
        "artifact": {"bytes": len(payload), "sha256": expected_sha256},
        "source_member_identities": members,
        "axes": {"realizations": list(range(10)), "metrics": list(METRICS),
                 "scored_methods": list(METHODS) + ["sampled_random_control"],
                 "plotted_methods": list(METHODS), "modules": list(MODULES)},
        "panel": summary,
        "coordinate_sha256": [[_sha(embeddings[r, m].astype("<f8", copy=False).tobytes(order="C"))
                               for m in range(7)] for r in range(10)],
        "analytical_guides_percent": {
            "contamination": [100 * 5 / 6] * 4 + [100 * 2 / 3],
            "correct_triplets": [100 / 3] * 5,
            "role": "source plotted reference lines; distinct from sampled random scores",
        },
        "runtime": {"numpy": np.__version__, "scorer_sha256": SCORER_SHA256},
        "qualification": {
            "operator_supplied_byte_identity_and_layout_only": True,
            "published_artifact_authenticated": False,
            "source_execution_verified": False,
            "original_post_fit_rng_recovered": False,
            "reproduction_established": False,
            "improvement_established": False,
            "paper_win": None,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.artifact.is_absolute() or not args.output.is_absolute():
        parser.error("operator input and output paths must be absolute")
    with args.artifact.open("rb") as handle:
        payload = handle.read(MAX_ARCHIVE_BYTES + 1)
    result = report_panel(payload, args.expected_sha256)
    with args.output.open("x", encoding="utf8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
