"""MindBridge Table 1 CLIP two-way scores from operator-extracted features.

This distinct adapter does not change the Table 2 benchmark. It runs no CLIP or
diffusion model. The source extraction and eight-candidate oracle selection must
already have run; this module validates their declared pairing and selection.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np

SUBJECTS = ("1", "2", "5", "7")
GALLERY_SIZE = 982
CLIP_DIM = 768
CANDIDATES = 8
SCHEMA = "mindbridge-table1-clip-features/v1"
SOURCE_REVISION = "2a3943ff5b619db6f85f16a5e7ff1331d25def55"
SOURCE_EVAL_SHA256 = "bde3c051c6f1c3be47c7075986ba2854a16561ff8702b3cbbf412edfcdf5c180"


class MetricError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise MetricError(message)


def two_way_from_features(reals, preds):
    """Literal source numerical rule, with explicit invalid-input refusal.

    Inputs are the source model's .float().flatten(1).cpu().numpy() outputs.
    Columns are predicted images. Equal correlations lose; there is no half-tie,
    cosine replacement, cross-subject gallery, or feature normalization here.
    This small mathematical helper is not itself a qualified paper endpoint.
    """
    need(isinstance(reals, np.ndarray) and isinstance(preds, np.ndarray),
         "feature inputs must be NumPy arrays")
    need(reals.dtype == preds.dtype == np.dtype("float32"),
         "source final features must be float32")
    need(reals.ndim == preds.ndim == 2 and reals.shape == preds.shape
         and reals.shape[0] >= 2 and reals.shape[1] >= 2,
         "paired image-by-feature matrices required")
    need(np.isfinite(reals).all() and np.isfinite(preds).all(),
         "features must be finite")
    need(np.all(np.ptp(reals, axis=1) > 0) and np.all(np.ptp(preds, axis=1) > 0),
         "every feature vector must have defined Pearson correlation")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        r = np.corrcoef(reals, preds)
        r = r[:len(reals), len(reals):]
    need(np.isfinite(r).all(), "all Pearson comparisons must be finite")
    congruents = np.diag(r)
    success = r < congruents
    success_cnt = np.sum(success, 0)
    # Preserve the author's mean(integer counts) THEN division, rather than
    # averaging per-image quotients, whose last floating-point bits can differ.
    perf = np.mean(success_cnt) / (len(reals) - 1)
    return success_cnt, float(perf)


def source_selected_indices(cosines, selected_indices):
    """Check source-computed hidden-token cosines and first-maximum choice.

    These eight scalars must come from the original hidden-state Clipper path,
    including its normalization, target dtype cast and second cosine norm.
    They are NOT similarities of the pooled features scored above. Recomputing
    hidden-token similarities with a different numerical library is out of scope.
    """
    need(isinstance(cosines, np.ndarray) and cosines.ndim == 2
         and cosines.shape[1] == CANDIDATES
         and cosines.dtype in (np.dtype("float32"), np.dtype("float64"))
         and np.isfinite(cosines).all(), "eight finite source cosines per image")
    need(isinstance(selected_indices, np.ndarray)
         and selected_indices.shape == (len(cosines),)
         and selected_indices.dtype.kind in "iu",
         "one integer selected index per image")
    # Exact original finite-input selection rule. Refuse NaN rather than silently
    # skip invalid candidates as the author's np.nanargmax otherwise permits.
    expected = np.nanargmax(cosines, axis=1)
    need(np.array_equal(selected_indices, expected),
         "selected image must be the first maximum among the eight source cosines")
    return expected


def subject_mean(subject_scores):
    need(isinstance(subject_scores, dict) and set(subject_scores) == set(SUBJECTS),
         "Table 1 requires all four subjects 1, 2, 5, 7")
    values = [subject_scores[s] for s in SUBJECTS]
    need(all(type(x) in (float, int) and np.isfinite(x) and 0 <= x <= 1 for x in values),
         "finite subject scores in [0, 1] required")
    return float(np.mean(values))


def _identities(value):
    need(type(value) is list and len(value) == GALLERY_SIZE
         and all(type(x) is str and x and x.strip() == x for x in value)
         and len(set(value)) == GALLERY_SIZE, "982 unique nonempty image identities required")
    return value


def validate_rows(rows):
    need(type(rows) is list and len(rows) == len(SUBJECTS), "all four subject rows required")
    need(all(type(row) is dict for row in rows), "subject rows must be objects")
    need([row.get("subject") for row in rows].count("1") == 1
         and {row.get("subject") for row in rows} == set(SUBJECTS),
         "subjects 1, 2, 5, 7 exactly once")
    common = None
    for row in rows:
        need(set(row) == {"subject", "target_ids", "reconstruction_ids", "selection_ids",
                          "target_features", "selected_features", "selection_cosines",
                          "selected_candidate_indices"}, "exact subject row fields required")
        ids = _identities(row["target_ids"])
        need(ids == row["reconstruction_ids"] == row["selection_ids"],
             "target, selected reconstruction and selection rows must have identical pairing")
        if common is None:
            common = set(ids)
        need(set(ids) == common, "four subjects must declare the same 982-image stimulus set")
    return {row["subject"]: row for row in rows}


def evaluate(rows, load_array, *, max_working_bytes):
    """Score four complete declared galleries; caller owns/authenticates input I/O.

    The bound is a conservative numerical workspace admission, not a hard OS RSS
    limit. No small-gallery fallback is exposed by this endpoint adapter.
    """
    by_subject = validate_rows(rows)
    need(type(max_working_bytes) is int
         and max_working_bytes >= 128 * 1024**2, "at least 128 MiB numerical workspace required")
    scores, details = {}, []
    for subject in SUBJECTS:
        row = by_subject[subject]
        reals = load_array(row["target_features"])
        preds = load_array(row["selected_features"])
        need(isinstance(reals, np.ndarray) and isinstance(preds, np.ndarray)
             and reals.shape == preds.shape == (GALLERY_SIZE, CLIP_DIM),
             "complete 982-by-768 final CLIP feature matrices required")
        cosines = load_array(row["selection_cosines"])
        chosen = load_array(row["selected_candidate_indices"])
        need(isinstance(cosines, np.ndarray) and len(cosines) == GALLERY_SIZE,
             "selection covers the complete gallery")
        source_selected_indices(cosines, chosen)
        counts, score = two_way_from_features(reals, preds)
        scores[subject] = score
        details.append({"subject": subject, "images": GALLERY_SIZE,
                        "comparisons_per_image": GALLERY_SIZE - 1,
                        "successful_comparisons": int(np.sum(counts)),
                        "clip_two_way": score})
        del reals, preds, cosines, chosen, counts
    return {
        "schema": "mindbridge-table1-clip-result/v1",
        "endpoint": "table1.mindbridge.joint-subjects-1257.clip",
        "feature_only": True,
        "subjects": details,
        "clip_two_way": subject_mean(scores),
        "paper_reference_percent": 94.7,
        "target_aware_best_of_eight": True,
        "source_selection_arithmetic_reexecuted": False,
        "native_CLIP_extraction_qualified": False,
        "historical_checkpoint_qualified": False,
        "original_membership_qualified": False,
        "scientific_qualification": False,
        "reproduction": "unknown",
        "improvement": "unknown",
        "table2_full48_qualified": False,
    }


class FileArrays:
    """Bounded hashed NPY input under an operator-controlled static parent.

    This is not an adversarial-filesystem sandbox. No pickle or object arrays.
    All payload bytes pass a full SHA check before NumPy parses captured bytes.
    """
    def __init__(self, root, max_read_bytes):
        self.root = Path(root).resolve()
        need(type(max_read_bytes) is int and max_read_bytes > 0, "positive read limit required")
        self.limit = max_read_bytes
        self.read_bytes = 0

    def __call__(self, desc):
        need(type(desc) is dict and set(desc) == {"path", "bytes", "sha256"},
             "exact NPY descriptor required")
        p, size, digest = desc["path"], desc["bytes"], desc["sha256"]
        need(type(p) is str and p and "\\" not in p and "\x00" not in p,
             "ordinary relative NPY path required")
        rel = Path(p)
        need(not rel.is_absolute() and ".." not in rel.parts and rel.as_posix() == p,
             "ordinary relative NPY path required")
        need(type(size) is int and 0 < size <= 8 * 1024**2,
             "NPY extent must be positive and at most 8 MiB")
        need(type(digest) is str and len(digest) == 64
             and all(c in "0123456789abcdef" for c in digest), "canonical SHA256 required")
        path = self.root / rel
        need(not any(x.is_symlink() for x in (path, *path.parents)),
             "symlink payload path refused")
        need(path.is_file() and path.stat().st_size == size, "regular payload extent mismatch")
        need(self.read_bytes + size + 1 <= self.limit, "cumulative payload read limit exceeded")
        with path.open("rb") as stream:
            raw = stream.read(size + 1)
        self.read_bytes += len(raw)
        need(len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
             "complete payload SHA256 mismatch")
        # Reuse the existing original-panel reader's bounded header/frombuffer
        # pattern: validate exact body extent BEFORE constructing any array.
        buffer = io.BytesIO(raw)
        try:
            version = np.lib.format.read_magic(buffer)
            need(version in ((1, 0), (2, 0)), "plain NPY v1/v2 required")
            reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                      else np.lib.format.read_array_header_2_0)
            shape, fortran, dtype = reader(buffer, max_header_size=10000)
        except (ValueError, OSError, EOFError) as exc:
            raise MetricError("invalid bounded NPY header") from exc
        need(not fortran and dtype.kind in "fiu" and dtype.itemsize in (4, 8)
             and 1 <= len(shape) <= 2 and all(type(x) is int and x > 0 for x in shape),
             "bounded C-order float/integer feature NPY required")
        need(buffer.tell() + math.prod(shape) * dtype.itemsize == len(raw),
             "exact NPY header/body extent required")
        value = np.frombuffer(raw, dtype=dtype, offset=buffer.tell()).reshape(shape)
        need(np.isfinite(value).all(), "finite NPY payload required")
        return value


def _object(pairs):
    obj = {}
    for key, value in pairs:
        need(key not in obj, "duplicate JSON key")
        obj[key] = value
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--max-read-bytes", type=int, required=True)
    parser.add_argument("--max-working-bytes", type=int, required=True)
    args = parser.parse_args()
    path = Path(args.manifest)
    need(path.stat().st_size <= 2 * 1024**2, "bounded manifest required")
    packet = json.loads(path.read_text(), object_pairs_hook=_object,
                        parse_constant=lambda _: (_ for _ in ()).throw(MetricError("nonfinite JSON")))
    need(type(packet) is dict and set(packet) == {"schema", "rows"}
         and packet["schema"] == SCHEMA, "exact Table 1 feature manifest required")
    arrays = FileArrays(path.parent, args.max_read_bytes)
    result = evaluate(packet["rows"], arrays, max_working_bytes=args.max_working_bytes)
    result["payload_read_bytes"] = arrays.read_bytes
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
