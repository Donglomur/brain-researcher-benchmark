#!/usr/bin/env python3
"""Prepare source-defined ERP companion designs; no fit, score or target lookup."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import tempfile

HELPER_SHA256 = "55c2254924495b0f23fccec081e2c81d7b7b34c4296b91fe78d787d10f2de15f"
CONTRACT_SHA256 = "fb6e8af8127f39bc6b8ad617f24feeae2dc51a58cc19fcdf03afe6de5e3b601a"
SOURCE_REVISION = "4f5767df1516e0ec3c234d51ba36e4b741eb60e8"
MAX_ROWS = 7380
MISSING = {"", "NA", "NaN"}
PE_TERMS = ("abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s")
CHOICE_ERPS = ("P3b_offer_s", "P3a_offer_s", "FRN_N2_offer_s", "P2_offer_s")


class PreparationError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def model_specs() -> dict:
    """Eight source PE-specific models, then three choice parameterizations."""
    specs = {}
    for erp, outcome, nuisance in (
        ("FRN", "FRN_N2_offer_s", ("P2_offer_s", "P2_base_offer_s")),
        ("P3a", "P3a_offer_s", ("P3a_base_offer_s",)),
        ("P3b", "P3b_offer_s", ("P3b_base_offer_s",)),
    ):
        terms = PE_TERMS if erp != "P3b" else PE_TERMS[:2]
        for index, pe in enumerate(terms, 1):
            name = f"{erp}_unconditional_{index}"
            specs[name] = {
                "source_model": f"fig3{'abc'[['FRN', 'P3a', 'P3b'].index(erp)]}_model{index}",
                "family": "gaussian", "estimator": "REML, not executed",
                "outcome": outcome, "fixed_terms": ["(Intercept)", pe, *nuisance],
                "random_terms": ["(Intercept)", *nuisance], "group": "sub",
                "required_columns": [outcome, pe, *nuisance, "sub"],
                "round_center": None,
            }
    for name, source_model, center in (
        ("choice_original", "fig2b_model", 0),
        ("choice_round1", "fig2b_model3", 1),
        ("choice_round5", "fig2b_model4", 5),
    ):
        specs[name] = {
            "source_model": source_model, "family": "binomial_logit",
            "estimator": "source GLMM, not executed", "outcome": "choice_num",
            "fixed_terms": ["(Intercept)", "P3b_offer_s", "trialLocal", *CHOICE_ERPS[1:],
                            *[term + ":trialLocal" for term in CHOICE_ERPS]],
            "random_terms": ["(Intercept)", "P3a_offer_s"], "group": "sub",
            "required_columns": ["choice_num", *CHOICE_ERPS, "trialLocal", "sub"],
            "round_center": center,
        }
    return specs


def missing(value: str) -> bool:
    return value.strip() in MISSING


def number(value: str, context: str) -> float:
    try:
        parsed = float(value)
    except (ValueError, OverflowError) as exc:
        raise PreparationError("Nonnumeric value: " + context) from exc
    if not math.isfinite(parsed):
        raise PreparationError("Nonfinite value: " + context)
    return parsed


def validate_joined(rows: list[dict[str, str]]) -> None:
    """Public pure helper: input is the full ordered join, never a filtered table."""
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ROWS:
        raise PreparationError("Expected bounded nonempty full joined rows")
    all_columns = {"source_row", "sub", "trialGlobal", "epe_valence_s"}
    for spec in model_specs().values():
        all_columns.update(spec["required_columns"])
    identities = set()
    for index, row in enumerate(rows, 1):
        if type(row) is not dict or not all_columns.issubset(row):
            raise PreparationError("Incomplete joined schema")
        if any(type(row[column]) is not str for column in all_columns):
            raise PreparationError("Joined values must be original CSV strings")
        if row["source_row"] != str(index) or missing(row["sub"]) or missing(row["trialGlobal"]):
            raise PreparationError("Missing or reordered full-source identity")
        trial = number(row["trialGlobal"], "trialGlobal")
        if trial < 1 or not trial.is_integer():
            raise PreparationError("Invalid trialGlobal")
        identity = (row["sub"].strip(), int(trial))
        if identity in identities:
            raise PreparationError("Duplicate behavioral trial identity")
        identities.add(identity)


def build_designs(rows: list[dict[str, str]]) -> dict:
    """Build finite X and within-participant random blocks, not expanded Z."""
    validate_joined(rows)
    first = [row for row in rows if not missing(row["epe_valence_s"])]
    models = {}
    for name, spec in model_specs().items():
        selected = [row for row in first
                    if all(not missing(row[column]) for column in spec["required_columns"])]
        if not selected:
            raise PreparationError("No complete rows for required companion: " + name)
        designs = []
        for row in selected:
            values = {column: number(row[column], f"{name}/{row['source_row']}/{column}")
                      for column in spec["required_columns"] if column != "sub"}
            if spec["round_center"] is not None:
                if values["choice_num"] not in (0.0, 1.0):
                    raise PreparationError("choice_num must preserve binary source coding")
                round_number = values["trialLocal"]
                if not round_number.is_integer() or not 1 <= round_number <= 5:
                    raise PreparationError("trialLocal must be an original round 1 through 5")
                values["trialLocal"] -= spec["round_center"]
                for erp in CHOICE_ERPS:
                    values[erp + ":trialLocal"] = values[erp] * values["trialLocal"]
            values["(Intercept)"] = 1.0
            x = [values[term] for term in spec["fixed_terms"]]
            z = [values[term] for term in spec["random_terms"]]
            if not all(math.isfinite(value) for value in x + z):
                raise PreparationError("Nonfinite derived design entry")
            raw_columns = list(dict.fromkeys(["source_row", "sub", "trialGlobal", *spec["required_columns"]]))
            designs.append({
                "source": {column: row[column] for column in raw_columns},
                "x": x, "random_block": z, "y": values[spec["outcome"]],
            })
        identities = [[int(row["source_row"]), row["sub"], row["trialGlobal"]] for row in selected]
        # Preserve every original participant, including those with zero retained
        # rows. The three disjoint stages trace all source rows without treating
        # trials as independent people or substituting a common model mask.
        first_ids = {row["source_row"] for row in first}
        selected_ids = {row["source_row"] for row in selected}
        support = {}
        for row in rows:
            participant = support.setdefault(row["sub"], {
                "sub": row["sub"], "source_rows": 0,
                "excluded_missing_valence_pe_source_rows": [],
                "excluded_model_complete_cases_source_rows": [],
                "retained_source_rows": [],
            })
            participant["source_rows"] += 1
            stage = ("excluded_missing_valence_pe_source_rows" if row["source_row"] not in first_ids
                     else "excluded_model_complete_cases_source_rows" if row["source_row"] not in selected_ids
                     else "retained_source_rows")
            participant[stage].append(int(row["source_row"]))
        models[name] = {
            **spec, "source_rows": len(rows),
            "excluded_missing_valence_pe": len(rows) - len(first),
            "excluded_model_complete_cases": len(first) - len(selected),
            "retained_rows": len(selected), "participants": len({row["sub"] for row in selected}),
            "participant_support": list(support.values()),
            "ordered_identity_sha256": sha256(json.dumps(identities, separators=(",", ":")).encode()),
            "rows": designs,
        }
    return models


def _load_inputs(source_dir: Path) -> tuple[list, dict]:
    implementation_root = Path(__file__).resolve().parent.parent
    helper_path = implementation_root / "processed-inputs-v1/prepare.py"
    contract_path = implementation_root / "registered-runtime/public_contract.json"
    helper_bytes = helper_path.read_bytes()
    contract_bytes = contract_path.read_bytes()
    if sha256(helper_bytes) != HELPER_SHA256 or sha256(contract_bytes) != CONTRACT_SHA256:
        raise PreparationError("Changed prerequisite source or input contract; readjudication required")
    # Execute exactly the already authenticated helper bytes, not a second reopen.
    helper = {"__file__": str(helper_path), "__name__": "_authenticated_erp_input_helper"}
    exec(compile(helper_bytes, str(helper_path), "exec"), helper)
    contract = json.loads(contract_bytes)
    helper["_validate_contract"](contract)
    tables, identities = [], []
    for spec in contract["public_input_files"]:
        table, identity = helper["_read_pinned_table"](source_dir / Path(spec["path"]).name, spec)
        tables.append(table)
        identities.append(identity)
    rows = helper["_join_rows"](tables)
    counts = Counter(row["sub"] for row in rows)
    if len(rows) != MAX_ROWS or len(counts) != 41 or set(counts.values()) != {180}:
        raise PreparationError("Original complete 41-person/180-trial panel required")
    return rows, {"sources": identities, "input_contract_sha256": CONTRACT_SHA256,
                  "input_helper_sha256": HELPER_SHA256}


def _csv(columns: list[str], rows: list[list]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def export_designs(models: dict, output_dir: Path, source_identity: dict) -> dict:
    if set(models) != set(model_specs()):
        raise PreparationError("All eleven companion parameterizations are required")
    if output_dir.exists() or output_dir.is_symlink():
        raise PreparationError("Output directory must be fresh")
    report = {
        "schema": "reward-emotion-companion-designs/v1", "source_revision": SOURCE_REVISION,
        "qualification": "input_designs_only_no_fit_or_score", **source_identity,
        "models": {}, "alignment": "Author positional ERP/behavior correspondence remains assumed",
        "random_design": "Per-row within-participant coefficient block; sub is the group key. Not an expanded sparse Z or fitted random effect.",
        "limits": ["No original fits, effects, covariance, likelihood or inference produced",
                   "Source defaults/runtime, complete companions, trial correspondence and scientific criteria remain unresolved",
                   "No improvement metric, readiness promotion or whole-paper claim"],
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".erp-companions-", dir=output_dir.parent))
    try:
        for name, model in models.items():
            records = model["rows"]
            raw_columns = list(records[0]["source"])
            artifacts = {
                f"{name}.rows.csv": _csv(raw_columns, [[row["source"][column] for column in raw_columns] for row in records]),
                f"{name}.fixed.csv": _csv(["source_row", *model["fixed_terms"]], [[row["source"]["source_row"], *row["x"]] for row in records]),
                f"{name}.random-block.csv": _csv(["source_row", "sub", *model["random_terms"]], [[row["source"]["source_row"], row["source"]["sub"], *row["random_block"]] for row in records]),
            }
            metadata = {key: value for key, value in model.items() if key != "rows"}
            metadata["outputs"] = []
            for filename, payload in artifacts.items():
                (temporary / filename).write_bytes(payload)
                metadata["outputs"].append({"name": filename, "bytes": len(payload), "sha256": sha256(payload)})
            report["models"][name] = metadata
        (temporary / "receipt.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
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


def prepare(source_dir: Path, output_dir: Path) -> dict:
    source_dir = source_dir.resolve(strict=True)
    output_dir = output_dir.absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise PreparationError("Output directory must be fresh")
    repository_root = Path(__file__).resolve().parents[5]
    resolved_output = output_dir.resolve()
    if resolved_output.is_relative_to(repository_root) or resolved_output.is_relative_to(source_dir):
        raise PreparationError("Output must be outside the repository and source directory")
    rows, identity = _load_inputs(source_dir)
    models = build_designs(rows)
    return export_designs(models, output_dir, identity)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.source_dir, args.output_dir)
    except (PreparationError, OSError, KeyError, ValueError) as exc:
        parser.exit(2, "Preparation failed: " + str(exc) + "\n")
    print(json.dumps({"qualification": result["qualification"], "models": len(result["models"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
