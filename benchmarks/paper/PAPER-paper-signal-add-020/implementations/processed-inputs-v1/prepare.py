#!/usr/bin/env python3
"""Prepare the registered conditional ERP models from pinned public source CSVs.

This is input preparation, not fitting, scoring, or independent ERP linkage
verification. The command has no network or private-reference dependency.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "registered-runtime/public_contract.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
SOURCE_REVISION = "4f5767df1516e0ec3c234d51ba36e4b741eb60e8"
MODEL_COLUMNS = {
    "FRN": ["FRN_N2_offer_s", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s",
            "P2_offer_s", "P2_base_offer_s", "sub"],
    "P3a": ["P3a_offer_s", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s",
            "P3a_base_offer_s", "sub"],
    "P3b": ["P3b_offer_s", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s",
            "P3b_base_offer_s", "sub"],
}
IDENTITY_COLUMNS = ["source_row", "sub", "trialGlobal"]
MISSING = {"", "NA", "NaN"}


class PreparationError(ValueError):
    """Source bytes or rows do not satisfy the registered input contract."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _missing(value: str) -> bool:
    return value.strip() in MISSING


def _finite(value: str, column: str, source_row: int) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise PreparationError(f"Nonnumeric {column} at source row {source_row}") from exc
    if not math.isfinite(number):
        raise PreparationError(f"Nonfinite {column} at source row {source_row}")
    return number


def _read_pinned_table(path: Path, spec: dict) -> tuple[list[dict[str, str]], dict]:
    # Authenticate the same bytes we subsequently parse; no hash/parse reopen.
    data = path.read_bytes()
    if len(data) != spec["bytes"] or digest(data) != spec["sha256"]:
        raise PreparationError(f"Source identity mismatch: {path.name}")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
        if reader.fieldnames != spec["columns"] or len(set(reader.fieldnames or [])) != len(reader.fieldnames or []):
            raise PreparationError(f"Source column mismatch: {path.name}")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise PreparationError(f"Invalid source CSV: {path.name}") from exc
    if len(rows) != spec["rows"]:
        raise PreparationError(f"Source row-count mismatch: {path.name}")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise PreparationError(f"Ragged source CSV: {path.name}")
    return rows, {"name": path.name, "bytes": len(data), "sha256": digest(data), "rows": len(rows)}


def _validate_contract(contract: dict) -> None:
    if contract["analysis_family"] != "specified_conditional_REML_v1":
        raise PreparationError("Unsupported analysis family")
    if set(contract["models"]) != set(MODEL_COLUMNS):
        raise PreparationError("Unexpected model panel")
    for name, columns in MODEL_COLUMNS.items():
        # Every random-effect variable is also included. A future formula change
        # must not silently keep this preparer's old complete-case rule.
        variables = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", contract["models"][name]["formula"]))
        if variables != set(columns):
            raise PreparationError(f"Formula variables changed: {name}")
    specs = contract["public_input_files"]
    names = [Path(spec["path"]).name for spec in specs]
    if len(names) != 8 or len(set(names)) != 8 or names[0] != "BEH_ug.csv":
        raise PreparationError("Expected the eight registered tables, behavior first")
    if len({spec["rows"] for spec in specs}) != 1:
        raise PreparationError("Source tables have different declared row counts")


def _join_rows(tables: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    """Positional author join, with no sort, deduplication, or inferred ERP keys."""
    if len({len(table) for table in tables}) != 1:
        raise PreparationError("Source tables have different row counts")
    columns: set[str] = set()
    for table in tables:
        if not table:
            raise PreparationError("Empty source table")
        new_columns = set(table[0])
        if columns.intersection(new_columns) or "source_row" in new_columns:
            raise PreparationError("Ambiguous duplicate source columns")
        columns.update(new_columns)
    joined = []
    seen_keys = set()
    for index, values in enumerate(zip(*tables), 1):
        row = {key: value for item in values for key, value in item.items()}
        if _missing(row["sub"]) or _missing(row["trialGlobal"]):
            raise PreparationError(f"Missing trial identity at source row {index}")
        trial = _finite(row["trialGlobal"], "trialGlobal", index)
        if not trial.is_integer() or trial < 1:
            raise PreparationError(f"Invalid trialGlobal at source row {index}")
        key = (row["sub"].strip(), int(trial))
        if key in seen_keys:
            raise PreparationError(f"Duplicate behavior trial identity at source row {index}")
        seen_keys.add(key)
        row["source_row"] = str(index)
        joined.append(row)
    return joined


def _select_rows(rows: list[dict[str, str]], columns: list[str]) -> tuple[list[dict[str, str]], dict]:
    first_filter = [row for row in rows if not _missing(row["epe_valence_s"])]
    retained = [row for row in first_filter if all(not _missing(row[column]) for column in columns)]
    for row in retained:
        for column in columns:
            if column != "sub":
                _finite(row[column], column, int(row["source_row"]))
    identities = [[int(row["source_row"]), row["sub"], row["trialGlobal"]] for row in retained]
    return retained, {
        "source_rows": len(rows),
        "excluded_missing_valence_pe": len(rows) - len(first_filter),
        "excluded_model_complete_cases": len(first_filter) - len(retained),
        "retained_rows": len(retained),
        "participants": len({row["sub"] for row in retained}),
        "ordered_identity_sha256": digest(json.dumps(identities, separators=(",", ":")).encode()),
    }


def prepare(source_dir: Path, output_dir: Path) -> dict:
    source_dir = source_dir.resolve(strict=True)
    output_dir = output_dir.absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise PreparationError("Output directory must be fresh")
    resolved_output = output_dir.resolve()
    if resolved_output.is_relative_to(REPOSITORY_ROOT) or resolved_output.is_relative_to(source_dir):
        raise PreparationError("Output must be outside the repository and source directory")
    contract_bytes = CONTRACT_PATH.read_bytes()
    contract = json.loads(contract_bytes)
    _validate_contract(contract)
    tables, source_receipts = [], []
    for spec in contract["public_input_files"]:
        table, receipt = _read_pinned_table(source_dir / Path(spec["path"]).name, spec)
        tables.append(table)
        source_receipts.append(receipt)
    rows = _join_rows(tables)
    required_participants = {model["required_participants"] for model in contract["models"].values()}
    counts = Counter(row["sub"] for row in rows)
    if len(required_participants) != 1 or len(counts) not in required_participants or len(set(counts.values())) != 1:
        raise PreparationError("Source participant panel differs from the registered complete cohort")
    model_rows, model_receipts = {}, {}
    for name, columns in MODEL_COLUMNS.items():
        selected, receipt = _select_rows(rows, columns)
        spec = contract["models"][name]
        if receipt["retained_rows"] != spec["required_rows"] or receipt["participants"] != spec["required_participants"]:
            raise PreparationError(f"Registered retained cohort mismatch: {name}")
        model_rows[name] = selected
        model_receipts[name] = {**receipt, "formula": spec["formula"], "columns": IDENTITY_COLUMNS + [column for column in columns if column != "sub"]}
    report = {
        "schema_version": 1,
        "component": "PAPER-paper-signal-add-020/processed-inputs-v1",
        "qualification": "source_tables_prepared_no_fit_or_score",
        "source_revision": SOURCE_REVISION,
        "contract_sha256": digest(contract_bytes),
        "sources": source_receipts,
        "models": model_receipts,
        "alignment": "Author positional join; ERP exports have no independently verified trial keys",
        "scaled_columns": "Copied unchanged from authenticated author CSVs",
        "split": "Original complete-cohort mixed-effects analysis; no predictive split introduced",
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".erp-prepare-", dir=output_dir.parent))
    try:
        for name, selected in model_rows.items():
            destination = temporary / f"{name}.csv"
            with destination.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=model_receipts[name]["columns"], extrasaction="ignore", lineterminator="\n")
                writer.writeheader()
                writer.writerows(selected)
            payload = destination.read_bytes()
            model_receipts[name]["output"] = {"name": destination.name, "bytes": len(payload), "sha256": digest(payload)}
        (temporary / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        # Reserve the destination without overwriting an existing directory.
        output_dir.mkdir()
        try:
            for child in temporary.iterdir():
                child.rename(output_dir / child.name)
        except BaseException:
            shutil.rmtree(output_dir)
            raise
    finally:
        shutil.rmtree(temporary)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory containing all eight exact author CSVs")
    parser.add_argument("--output-dir", type=Path, required=True, help="Fresh directory outside the repository and inputs")
    args = parser.parse_args()
    try:
        report = prepare(args.source_dir, args.output_dir)
    except (PreparationError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Preparation failed: {exc}\n")
    print(json.dumps({"qualification": report["qualification"], "models": {name: {key: model[key] for key in ("retained_rows", "participants", "ordered_identity_sha256")} for name, model in report["models"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
