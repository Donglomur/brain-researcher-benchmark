"""Read the complete published Figure 2 panel and compare normalized pair means.

This is publication-source inspection and arithmetic comparison, not author-model
execution, scientific reproduction admission, or a superiority decision.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
from pathlib import Path

TASK_ID = "PAPER-paper-method-029"
SOURCE_COMMIT = "c264167c2b5a0fa71709a58ae5b50a042f6d7a79"
SOURCE_URL = "https://static-content.springer.com/esm/art%3A10.1038%2Fs43588-025-00826-5/MediaObjects/43588_2025_826_MOESM4_ESM.csv"
SOURCE_SHA256 = "f6beffbcad700f3e24208016daabe18d802805404f32a0585e2f9333fd4968fb"
SOURCE_BYTES = 15637
SUBJECTS = tuple(f"sub{i:02d}" for i in range(1, 6))
ROIS = ("VC", "V1", "V2", "V3", "V4", "HVC")
METHODS = ("brain_loss", "content_loss")
AXES = ("pattern", "profile")
HEADER = ("Source", "Target", "ROI", "Method", "pattern_mean", "profile_mean")
EXPECTED_KEYS = frozenset((s, t, r, m, a) for s, t in itertools.permutations(SUBJECTS, 2)
                          for r, m, a in itertools.product(ROIS, METHODS, AXES))


class ReferenceError(ValueError):
    """A reference or replay does not identify the complete declared panel."""


def require(condition, message):
    if not condition:
        raise ReferenceError(message)


def finite_correlation(value, context):
    require(not isinstance(value, bool), f"{context}: Boolean correlation")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ReferenceError(f"{context}: numeric correlation required") from error
    require(math.isfinite(value) and -1 <= value <= 1,
            f"{context}: finite correlation in [-1,1] required")
    return value


def read_bounded(path, maximum_bytes):
    with Path(path).open("rb") as stream:
        payload = stream.read(maximum_bytes + 1)
    require(len(payload) <= maximum_bytes, "input exceeds size bound")
    return payload


def parse_source_csv(payload):
    """Parse source-shaped bytes; public authentication is in load_reference.

    Exposed separately for generated software controls. Parsing alone does not
    establish that bytes came from the publisher.
    """
    require(isinstance(payload, bytes) and len(payload) <= 65536, "bounded CSV bytes required")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8"), newline=""), strict=True)
        require(tuple(next(reader, ())) == HEADER, "exact Figure 2 column schema required")
        values = {}
        row_count = 0
        for row in reader:
            row_count += 1
            require(row_count <= 240 and len(row) == 6, "exact 240 six-column rows required")
            source, target, roi, method = row[:4]
            for axis, cell in zip(AXES, row[4:]):
                key = (source, target, roi, method, axis)
                require(key in EXPECTED_KEYS, "unknown subject, self-pair, ROI, method or axis")
                require(key not in values, "duplicate source panel key")
                values[key] = finite_correlation(cell, f"row {row_count} {axis}")
        require(set(values) == EXPECTED_KEYS, "complete five-subject/20-pair/six-ROI/two-method/two-axis panel required")
        return values
    except (UnicodeDecodeError, csv.Error) as error:
        raise ReferenceError("malformed UTF-8 CSV") from error


def load_reference(path):
    payload = read_bounded(path, 65536)
    require(len(payload) == SOURCE_BYTES and hashlib.sha256(payload).hexdigest() == SOURCE_SHA256,
            "published Figure 2 CSV byte identity mismatch")
    return parse_source_csv(payload)


def source_summary(values):
    require(set(values) == EXPECTED_KEYS, "complete reference panel required")
    summaries = []
    for roi, method, axis in itertools.product(ROIS, METHODS, AXES):
        pair_values = [values[(s, t, roi, method, axis)]
                       for s, t in itertools.permutations(SUBJECTS, 2)]
        summaries.append({"roi": roi, "method": method, "axis": axis,
                          "observed_pair_mean": math.fsum(pair_values) / 20,
                          "pairs": 20})
    return {"task_id": TASK_ID, "csv_rows": 240, "pair_axis_values": 480,
            "subjects": list(SUBJECTS), "directed_pairs": 20,
            "rois": list(ROIS), "methods": list(METHODS), "axes": list(AXES),
            "metric": "noise-ceiling-normalized within-pair mean correlation",
            "summary_statistic": "observed_equal_pair_mean_not_figure_bootstrap_mean",
            "summaries": summaries,
            "qualification": "pair_table_summary_only",
            "limits": ["The table contains aggregated pair means, not per-feature ceilings or masks.",
                       "Source bootstrap confidence intervals are not independent-subject uncertainty.",
                       "Native data, training condition, model lineage and source replay remain unqualified."]}


def replay_values(result):
    """Read the initial evaluator's normalized aggregate, never its raw score."""
    require(isinstance(result, dict) and result.get("task_id") == TASK_ID, "wrong replay task")
    require(result.get("source_commit") == SOURCE_COMMIT, "wrong replay source revision")
    require(result.get("population") == "public_deeprecon", "public Deeprecon replay required; generated results are not publication reproduction")
    require(result.get("images") == 50 and result.get("repeats") == 24 and result.get("source_pairs") == 20,
            "original 50-image/24-repeat/20-pair replay required")
    require(result.get("methods") == list(METHODS) and result.get("rois") == list(ROIS), "complete source methods and ROI order required")
    normalized = result.get("normalized")
    require(isinstance(normalized, dict), "normalized replay required; raw correlation is a different endpoint")
    rows = normalized.get("pair_rows")
    require(isinstance(rows, list) and len(rows) == 480, "complete 480 normalized pair-axis rows required")
    values = {}
    for row in rows:
        require(isinstance(row, dict), "pair row must be an object")
        key = tuple(row.get(k) for k in ("source", "target", "roi", "method", "axis"))
        require(all(isinstance(v, str) for v in key) and key in EXPECTED_KEYS, "unknown replay panel key")
        require(key not in values, "duplicate replay panel key")
        eligible, total, undefined = (row.get(k) for k in ("eligible_count", "total_count", "undefined_count"))
        require(all(type(v) is int for v in (eligible, total, undefined)), "integer feature counts required")
        require(0 < eligible <= total and undefined == 0, "nonempty complete eligible feature support required")
        require(total == 50 if key[-1] == "pattern" else total >= 2, "original pattern count or nonempty profile required")
        values[key] = finite_correlation(row.get("mean_r"), "replay mean")
    require(set(values) == EXPECTED_KEYS, "complete replay panel required")
    return values


def compare(reference, replay, absolute_tolerance, tolerance_reason):
    """Arithmetic diagnostics, with caller-supplied tolerance, not admission."""
    require(set(reference) == EXPECTED_KEYS, "complete reference panel required")
    require(type(absolute_tolerance) in (int, float) and math.isfinite(absolute_tolerance)
            and 0 <= absolute_tolerance <= 2, "finite absolute tolerance in [0,2] required")
    require(isinstance(tolerance_reason, str) and tolerance_reason.strip(), "tolerance reason required")
    actual = replay_values(replay)
    rows = []
    for key in sorted(EXPECTED_KEYS):
        error = actual[key] - reference[key]
        rows.append(dict(zip(("source", "target", "roi", "method", "axis"), key),
                         published_mean=reference[key], replay_mean=actual[key],
                         signed_error=error, absolute_error=abs(error),
                         within_tolerance=abs(error) <= absolute_tolerance))
    summaries = []
    for roi, method, axis in itertools.product(ROIS, METHODS, AXES):
        group = [r for r in rows if (r["roi"], r["method"], r["axis"]) == (roi, method, axis)]
        summaries.append({"roi": roi, "method": method, "axis": axis, "pairs": 20,
                          "published_pair_mean": math.fsum(r["published_mean"] for r in group) / 20,
                          "replay_pair_mean": math.fsum(r["replay_mean"] for r in group) / 20,
                          "mean_signed_error": math.fsum(r["signed_error"] for r in group) / 20,
                          "maximum_absolute_pair_error": max(r["absolute_error"] for r in group),
                          "root_mean_square_pair_error": math.sqrt(math.fsum(r["signed_error"] ** 2 for r in group) / 20),
                          "pairs_within_tolerance": sum(r["within_tolerance"] for r in group)})
    return {"task_id": TASK_ID,
            "comparison_scope": "arithmetic_published_pair_means_only",
            "supplied_absolute_tolerance": absolute_tolerance, "tolerance_reason": tolerance_reason,
            "tolerance_policy_status": "caller_supplied_not_independently_qualified",
            "pair_axis_values": 480, "all_values_within_tolerance": all(r["within_tolerance"] for r in rows),
            "summaries": summaries, "rows": rows,
            "scientific_reproduction": "not_established_by_arithmetic_comparison",
            "scientific_improvement": "not_evaluated",
            "limits": ["Hashes and replay declarations do not authenticate native execution or fitting provenance.",
                       "A source-conformant predeclared tolerance and independent native replay are still required.",
                       "Separate paper+data and paper+data+author-code attempts need matched access and budgets.",
                       "No candidate method, meaningful improvement effect or dependence-aware uncertainty is evaluated."]}


def export_replay_summary(result, output_path):
    """Export only 480 pair means from an already-computed evaluator result.

    This avoids parsing its potentially large per-voxel JSON report again. Call
    after an independently authorized evaluator run; this function runs no model.
    The exported declarations still require native provenance qualification.
    """
    replay_values(result)
    compact = {key: result[key] for key in ("task_id", "source_commit", "population", "images",
                                           "repeats", "source_pairs", "methods", "rois")}
    fields = ("source", "target", "roi", "method", "axis", "mean_r",
              "eligible_count", "total_count", "undefined_count")
    compact["normalized"] = {"pair_rows": [{key: row[key] for key in fields}
                                              for row in result["normalized"]["pair_rows"]]}
    compact["export_scope"] = "normalized_pair_means_only_native_provenance_not_authenticated"
    with Path(output_path).open("x") as stream:
        stream.write(json.dumps(compact, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", help="exact publisher Figure 2 CSV, kept outside Git")
    parser.add_argument("--output", required=True, help="external JSON report destination")
    parser.add_argument("--replay", help="initial evaluator JSON with normalized pair means")
    parser.add_argument("--absolute-tolerance", type=float)
    parser.add_argument("--tolerance-reason")
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists(), "refusing to overwrite an existing output")
    reference = load_reference(args.source_csv)
    if args.replay:
        payload = read_bounded(args.replay, 64 * 1024 * 1024)
        result = compare(reference, json.loads(payload), args.absolute_tolerance, args.tolerance_reason)
        result["replay_sha256"] = hashlib.sha256(payload).hexdigest()
    else:
        require(args.absolute_tolerance is None and args.tolerance_reason is None, "tolerance requires a replay")
        result = source_summary(reference)
    result["reference_artifact"] = {"url": SOURCE_URL, "sha256": SOURCE_SHA256,
                                    "bytes": SOURCE_BYTES, "byte_identity_verified": True}
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
