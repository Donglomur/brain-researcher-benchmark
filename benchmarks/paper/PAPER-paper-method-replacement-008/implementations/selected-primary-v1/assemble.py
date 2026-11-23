"""Assemble complete BaRISTA selected-panel predictions without loading gold.

Inputs are per-run class-one probabilities with the actual ordered query IDs.
This does not collect native model outputs or authenticate their execution.
"""
import argparse
import importlib.util
from pathlib import Path

# Explicit sibling loading also works under the documented isolated interpreter.
_spec = importlib.util.spec_from_file_location(
    "barista_selected_assembler_score", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)
from protocol import canonical, digest
from io_contract import capture, fresh, ordinary, parse, put

RECEIPT_CAP = 8_000_000
RECEIPT_TOTAL_CAP = 128_000_000
IDENTITY_KEYS = ("id", "arm", "model")


def _basename(name, suffix):
    if (not isinstance(name, str) or not name.endswith(suffix)
            or "\\" in name or Path(name).name != name
            or any(ord(c) < 32 for c in name)):
        raise ValueError("Single ordinary relative basename required")
    return name


def compile_submission(public, receipts, base):
    """Order complete per-run receipts and validate their unchanged NPY files.

    Receipts may arrive in any order. Probabilities are never reordered, averaged,
    rounded, complemented, or inferred from an AUC. All IDs must already match
    the frozen public query order; zero/dropped rows are not repaired here.
    """
    public = score.validate_public(public)
    expected = list(score.outputs(public))
    if not isinstance(receipts, list) or len(receipts) != len(expected):
        raise ValueError("All 5,880 per-run receipts required")
    expected_by_key = {tuple(row[k] for k in IDENTITY_KEYS): row for row in expected}
    admitted = {}
    for receipt in receipts:
        if (not isinstance(receipt, dict) or set(receipt) != {
                "schema", "panel_id", "id", "arm", "model", "query_ids", "values"}
                or receipt["schema"] != "barista_selected_primary_run_v1"
                or receipt["panel_id"] != public["panel_id"]
                or any(type(receipt[k]) is not str for k in IDENTITY_KEYS)):
            raise ValueError("Exact per-run generation and identity required")
        key = tuple(receipt[k] for k in IDENTITY_KEYS)
        if key not in expected_by_key or key in admitted:
            raise ValueError("Unknown or duplicate selected run")
        exp = expected_by_key[key]
        ids = receipt["query_ids"]
        if (not isinstance(ids, list) or len(ids) != exp["query_count"]
                or any(type(q) is not str or not q or len(q) > 4096 for q in ids)
                or len(set(ids)) != len(ids)
                or digest(ids) != exp["query_ids_sha256"]):
            raise ValueError("Complete unique query IDs in frozen order required")
        admitted[key] = {k: exp[k] for k in (*IDENTITY_KEYS, "query_ids_sha256")}
        admitted[key]["values"] = receipt["values"]
    submission = {
        "schema": "barista_selected_primary_submission_v1", "task_id": score.TASK_ID,
        "panel_id": public["panel_id"],
        "predictions": [admitted[tuple(row[k] for k in IDENTITY_KEYS)] for row in expected],
    }
    body = canonical(submission)
    if len(body) + 1 > score.JSON_CAP:
        raise ValueError("Submission JSON byte bound")
    # Reuse the scorer's complete finite-probability, shape, hash and budget rules.
    # This path has no gold supplier and does not compute any performance metric.
    score.admit(public, body, base)
    return submission


def _read_receipts(index, base, public):
    if (not isinstance(index, dict) or set(index) != {"schema", "panel_id", "runs"}
            or index["schema"] != "barista_selected_primary_run_index_v1"
            or index["panel_id"] != public["panel_id"]
            or not isinstance(index["runs"], list)
            or len(index["runs"]) != len(list(score.outputs(public)))):
        raise ValueError("Complete selected-panel run index required")
    names = [_basename(name, ".json") for name in index["runs"]]
    if len(set(names)) != len(names):
        raise ValueError("Repeated run receipt path")
    receipts, total = [], 0
    for name in names:
        # The remaining cap is applied before the read, including the last file.
        remaining = RECEIPT_TOTAL_CAP - total
        if remaining <= 0:
            raise ValueError("Aggregate run-receipt byte bound")
        body = capture(base / name, cap=min(RECEIPT_CAP, remaining))
        total += len(body)
        receipts.append(parse(body))
    return receipts


def write_submission(public, receipts, base, out_path, *, max_output_bytes):
    """Validate and write one manifest; array paths stay relative to its parent."""
    if type(max_output_bytes) is not int or not 0 < max_output_bytes <= score.JSON_CAP:
        raise ValueError("Explicit positive bounded output allowance required")
    base = ordinary(base)
    out_path = fresh(out_path)
    if out_path.parent.resolve() != base.resolve():
        raise ValueError("Output must share the index and NPY directory")
    submission = compile_submission(public, receipts, base)
    if len(canonical(submission)) + 1 > max_output_bytes:
        raise ValueError("Submission exceeds explicit output allowance")
    put(out_path, submission)
    return submission


def assemble(public_path, index_path, out_path, *, max_output_bytes):
    """Load the per-run index, then write beside its existing NPY files."""
    public_path, index_path = ordinary(public_path), ordinary(index_path)
    public = score.validate_public(parse(capture(public_path, cap=score.JSON_CAP)))
    index = parse(capture(index_path, cap=score.JSON_CAP))
    receipts = _read_receipts(index, index_path.parent, public)
    return write_submission(public, receipts, index_path.parent, out_path,
                            max_output_bytes=max_output_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("public", "index", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--max-output-bytes", required=True, type=int)
    args = parser.parse_args()
    assemble(args.public, args.index, args.out, max_output_bytes=args.max_output_bytes)


if __name__ == "__main__":
    main()
