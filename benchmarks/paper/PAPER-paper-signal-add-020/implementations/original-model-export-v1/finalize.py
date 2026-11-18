#!/usr/bin/env python3
"""Bind an existing native-model export to prepared inputs; emit the public ABI.

No fitting, reference estimates, numerical scoring, or network access.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

TASK = "PAPER-paper-signal-add-020"
REVISION = "4f5767df1516e0ec3c234d51ba36e4b741eb60e8"
CONTRACT_SHA = "fb6e8af8127f39bc6b8ad617f24feeae2dc51a58cc19fcdf03afe6de5e3b601a"
INPUT_SHA = "713ff6401f861bb96e965efef70f26d3c207f3644654bc75df21d58bf258c206"
RANDOM = {
    "FRN": ["(Intercept)", "abs_epe_arousal_s", "P2_offer_s", "P2_base_offer_s"],
    "P3a": ["(Intercept)", "abs_rpe_s", "abs_epe_arousal_s", "P3a_base_offer_s"],
    "P3b": ["(Intercept)", "abs_rpe_s", "P3b_base_offer_s"],
}
OUTCOMES = {"FRN": "FRN_N2_offer_s", "P3a": "P3a_offer_s", "P3b": "P3b_offer_s"}


class ExportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ExportError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), "Expected a finite JSON number")
    return float(value)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ExportError("Nonfinite JSON number")
    value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    # Also reject finite-token exponent overflow, e.g. 1e999.
    canonical(value)
    return value


def bounded(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, f"Oversized input: {path.name}")
    return data


def check_covariance(matrix, size):
    require(type(matrix) is list and len(matrix) == size and
            all(type(row) is list and len(row) == size for row in matrix), "Covariance shape differs")
    values = [[number(value) for value in row] for row in matrix]
    scale = max(abs(value) for row in values for value in row)
    tolerance = 1e-12 + 1e-10 * scale
    require(all(abs(values[i][j] - values[j][i]) <= tolerance
                for i in range(size) for j in range(size)), "Asymmetric fixed-effect covariance")
    lower = [[0.] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1):
            residual = (values[i][j] + values[j][i]) / 2 - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                require(math.isfinite(residual) and residual > 0, "Covariance is not positive definite")
                lower[i][j] = math.sqrt(residual)
            else:
                lower[i][j] = residual / lower[j][j]
    return values


def contrast(model):
    terms, beta, cov = model["terms"], model["coefficients"], model["covariance"]
    v, r = terms.index("abs_epe_valence_s"), terms.index("abs_rpe_s")
    estimate = beta[v] - beta[r]
    independent_var = cov[v][v] + cov[r][r]
    full_var = independent_var - cov[v][r] - cov[r][v]
    require(full_var > 0 and independent_var > 0, "Contrast variance is not positive")
    full_se, independent_se = math.sqrt(full_var), math.sqrt(independent_var)
    full_z, independent_z = estimate / full_se, estimate / independent_se
    return {
        "estimate": estimate, "full_covariance_se": full_se,
        "full_covariance_z": full_z,
        "full_covariance_two_sided_normal_p": math.erfc(abs(full_z) / math.sqrt(2)),
        "historical_independence_se": independent_se,
        "historical_independence_z": independent_z,
        "historical_single_normal_tail_p": .5 * math.erfc(abs(independent_z) / math.sqrt(2)),
    }


def validate_export(export, prepared, contract):
    """Pure interchange validation. Production pins contract bytes in finalize()."""
    require(set(export) == {"schema", "source_revision", "binding_basis", "export_runtime", "models"}, "Export root fields differ")
    require(export["schema"] == "erp-original-model-export/v1" and export["source_revision"] == REVISION,
            "Export schema or source revision differs")
    require(export["binding_basis"] == "operator_supplied_original_source_rows", "Explicit source-row binding required")
    require(set(export["models"]) == set(RANDOM) == set(prepared), "Conditional model panel differs")
    runtime = export["export_runtime"]
    require(type(runtime) is dict and type(runtime.get("R")) is str and runtime["R"] and
            type(runtime.get("packages")) is dict and runtime["packages"].get("lme4") and
            runtime["packages"].get("jsonlite"), "Export runtime information missing")
    summaries, provenance = {}, {}
    model_fields = {"formula", "REML", "weights", "offset", "fixed_design_verified", "random_design_verified",
                    "random_group", "random_terms", "group_levels", "frame", "native_frame_row_names",
                    "operator_bound_source_rows", "terms", "coefficients", "covariance", "diagnostics"}
    source_count = contract["public_input_files"][0]["rows"]
    warning_fields = ("optimizer", "optimizer_control", "convergence_code", "convergence_messages", "optimizer_warnings", "singular")
    for name, spec in contract["models"].items():
        model, rows = export["models"][name], prepared[name]
        require(set(model) == model_fields, f"Model fields differ: {name}")
        require("".join(model["formula"].split()) == "".join(spec["formula"].split()), f"Source formula differs: {name}")
        require(model["REML"] is True and model["weights"] is None and model["offset"] is None,
                f"Unsupported estimation, weighting or offset: {name}")
        require(model["fixed_design_verified"] is True and model["random_design_verified"] is True and
                model["random_group"] == "sub" and model["random_terms"] == RANDOM[name], f"Actual design differs: {name}")
        require(len(rows) == spec["required_rows"], f"Retained support differs: {name}")
        ids = [int(row["source_row"]) for row in rows]
        require(len(set(ids)) == len(ids) and all(1 <= row <= source_count for row in ids), f"Invalid source IDs: {name}")
        require(ids == sorted(ids), f"Prepared source order differs: {name}")
        actual_ids = model["operator_bound_source_rows"]
        require(type(actual_ids) is list and all(type(x) is int for x in actual_ids) and actual_ids == ids,
                f"Original-row binding/order differs: {name}")
        groups = [row["sub"] for row in rows]
        levels = model["group_levels"]
        require(type(levels) is list and all(type(x) is str and x for x in levels) and
                len(set(levels)) == len(levels) == spec["required_participants"] and set(levels) == set(groups),
                f"Participant support differs: {name}")
        require(len(set((row["sub"], row["trialGlobal"]) for row in rows)) == len(rows), f"Duplicate trial identity: {name}")
        fields = [OUTCOMES[name]] + spec["terms"][1:] + ["sub"]
        frame = model["frame"]
        require(set(frame) == set(fields), f"Model-frame columns differ: {name}")
        for field in fields:
            values = frame[field]
            require(type(values) is list and len(values) == len(rows), f"Model-frame support differs: {name}/{field}")
            if field == "sub":
                require(values == groups, f"Participant order differs: {name}")
            else:
                require([number(value) for value in values] == [number(float(row[field])) for row in rows],
                        f"Fitted-frame value/order differs: {name}/{field}")
        native_names = model["native_frame_row_names"]
        require(type(native_names) is list and len(native_names) == len(rows) and
                all(type(x) is str and x for x in native_names) and len(set(native_names)) == len(rows),
                f"Native frame row names invalid: {name}")
        terms = model["terms"]
        require(type(terms) is list and all(type(x) is str for x in terms) and
                len(set(terms)) == len(terms) == len(spec["terms"]) and set(terms) == set(spec["terms"]),
                f"Fixed terms differ: {name}")
        require(type(model["coefficients"]) is list and len(model["coefficients"]) == len(terms), "Coefficient shape differs")
        beta = [number(x) for x in model["coefficients"]]
        covariance = check_covariance(model["covariance"], len(terms))
        require(type(model["diagnostics"]) is dict and set(warning_fields).issubset(model["diagnostics"]),
                "Native optimizer/convergence diagnostics missing")
        summaries[name] = {"terms": terms, "coefficients": beta, "covariance": covariance, "retained_source_rows": ids}
        provenance[name] = {
            "retained_rows": len(rows), "participants": len(levels), "group_levels": levels,
            "ordered_identity_sha256": digest(canonical([[int(r["source_row"]), r["sub"], r["trialGlobal"]] for r in rows])),
            "native_frame_row_names_sha256": digest(canonical(native_names)),
            "native_diagnostics": model["diagnostics"],
        }
    warnings = {name: {field: model["diagnostics"][field] for field in warning_fields}
                for name, model in export["models"].items()}
    method = ("Already-fitted original conditional Gaussian REML models; native exporter checked fixed/random design and unweighted/no-offset structure. "
              "Export runtime (not original fit-time provenance): " + canonical(runtime).decode() +
              "; native optimizer/convergence diagnostics: " + canonical(warnings).decode())
    require(len(method.encode()) <= 16384, "Method text exceeds public ABI")
    summary = {"schema_version": 1, "candidate_id": TASK, "input_manifest_sha256": INPUT_SHA,
               "analysis_family": "specified_conditional_REML_v1", "method": method,
               "models": summaries, "P3b_report": contrast(summaries["P3b"])}
    require(len(canonical(summary)) + 1 <= 200000, "Summary exceeds public ABI size including final newline")
    return summary, provenance


def load_prepared(directory, contract, contract_sha):
    receipt_bytes = bounded(directory / "receipt.json", 65536)
    receipt = strict_json(receipt_bytes)
    require(receipt["component"] == TASK + "/processed-inputs-v1" and receipt["source_revision"] == REVISION and
            receipt["contract_sha256"] == contract_sha, "Prepared input receipt identity differs")
    expected_sources = [{"name": Path(s["path"]).name, "bytes": s["bytes"], "sha256": s["sha256"], "rows": s["rows"]}
                        for s in contract["public_input_files"]]
    require(receipt["sources"] == expected_sources, "Prepared source pins differ")
    require(set(receipt["models"]) == set(RANDOM), "Prepared model panel differs")
    frames, pins = {}, {}
    for name, spec in contract["models"].items():
        record = receipt["models"][name]
        raw = bounded(directory / (name + ".csv"), 2 * 1024**2)
        require(record["output"] == {"name": name + ".csv", "bytes": len(raw), "sha256": digest(raw)}, "Prepared CSV identity differs")
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
        expected_columns = ["source_row", "sub", "trialGlobal", OUTCOMES[name]] + spec["terms"][1:]
        require(reader.fieldnames == expected_columns == record["columns"], "Prepared CSV columns differ")
        rows = list(reader)
        require(all(None not in row and all(v is not None for v in row.values()) for row in rows), "Ragged prepared CSV")
        identities = [[int(r["source_row"]), r["sub"], r["trialGlobal"]] for r in rows]
        require(digest(canonical(identities)) == record["ordered_identity_sha256"] and
                record["retained_rows"] == len(rows) == spec["required_rows"] and
                record["participants"] == len({r["sub"] for r in rows}) == spec["required_participants"] and
                record["formula"] == spec["formula"], "Prepared support/identity receipt differs")
        frames[name], pins[name] = rows, record["output"]
    return frames, {"receipt_sha256": digest(receipt_bytes), "prepared_files": pins}


def finalize(export_path, prepared_dir, contract_path, output_dir):
    contract_bytes = bounded(contract_path, 32768)
    require(digest(contract_bytes) == CONTRACT_SHA, "Unreviewed public contract bytes")
    contract = strict_json(contract_bytes)
    export_bytes = bounded(export_path, 16 * 1024**2)
    export = strict_json(export_bytes)
    frames, prepared_pins = load_prepared(prepared_dir, contract, CONTRACT_SHA)
    summary, model_provenance = validate_export(export, frames, contract)
    provenance = {
        "schema": "erp-original-model-export-provenance/v1", "candidate_id": TASK,
        "qualification": "generated_interchange_bridge_not_authentic_fit_or_scientific_result",
        "public_contract_sha256": CONTRACT_SHA, "export_sha256": digest(export_bytes),
        "export_bytes": len(export_bytes), "export_runtime": export["export_runtime"],
        **prepared_pins, "models": model_provenance,
        "limitations": [
            "Retain the original export: it preserves actual frame values and native row names; native row names are not original source IDs.",
            "Explicit operator binding plus ordered frame equality does not authenticate an original fit, its chronology, or independent ERP/behavior correspondence.",
            "Prepared-table source pins rely on the existing preparer's receipt; this bridge does not reread or reconstruct the eight original tables.",
            "Export-runtime versions do not establish original author or fit-time versions.",
            "No companion/choice-model export, whole-paper reproduction, improvement eligibility, or native R parity is established.",
        ],
    }
    require(not output_dir.exists() and not output_dir.is_symlink(), "Output directory must be fresh")
    output_dir.mkdir()
    emitted_summary = canonical(summary) + b"\n"
    require(len(emitted_summary) <= 200000, "Emitted summary exceeds public ABI size")
    (output_dir / "summary.json").write_bytes(emitted_summary)
    (output_dir / "provenance.json").write_bytes(canonical(provenance) + b"\n")
    return {"summary_bytes": len(emitted_summary), "models": list(summary["models"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=Path(__file__).resolve().parent.parent / "registered-runtime/public_contract.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--accept-ordered-operator-binding", action="store_true", required=True,
                        help="Acknowledge that equality checks do not establish fit chronology or independent ERP linkage")
    args = parser.parse_args()
    try:
        print(json.dumps(finalize(args.export, args.prepared_dir, args.contract, args.output_dir)))
    except (ExportError, OSError, KeyError, TypeError, ValueError, OverflowError) as exc:
        parser.exit(2, f"Export refused: {exc}\n")


if __name__ == "__main__":
    main()
