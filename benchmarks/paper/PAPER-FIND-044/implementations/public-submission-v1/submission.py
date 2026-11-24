#!/usr/bin/env python3
"""Prepare and preflight the public Figure 1 e/g/h/k submission, without answers."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

PUBLIC_PINS = {
    "PUBLIC_CONTRACT.json": "e52eb549321064a838d3186ec75efcae179f9b1bf4800c0673af60e0ac391950",
    "SUBMISSION_SCHEMA.json": "6f6b67281b8094feff0bb938e4fb93a89090b59ef68ed746553bb332ccf0f282",
}
ENDPOINTS = ("g", "h", "k")
ENDPOINT_STATUS = {
    "defined", "not_source_learner", "no_consumption_or_no_trials",
    "no_window_observations", "source_fallback_failed",
    "undefined_source_calculation", "change_point_undefined", "unresolved",
}
STATUSES = {
    "session_audit": {"status": {"defined", "unresolved"}},
    "trials": {"state": {"retained", "prefix_removed", "recording_cutoff_removed", "unresolved"}},
    "daily": {"status": {"defined", "no_retained_observations", "unresolved"}},
    "mice": {
        "mouse_status": {"defined", "no_consumption_or_no_trials", "unresolved"},
        "learner_status": {"defined", "no_consumption_or_no_trials", "no_day_le8_observations", "unresolved"},
        "g_status": ENDPOINT_STATUS, "h_status": ENDPOINT_STATUS, "k_status": ENDPOINT_STATUS,
    },
    "group_e": {"status": {"defined", "mean_only_n1", "no_defined_observations", "unresolved"}},
    "group_endpoints": {"status": {"defined", "mean_only_n1", "no_defined_observations", "unresolved"}},
    "comparisons": {
        "welch_status": {"defined", "insufficient_n", "zero_standard_error_undefined", "unresolved"},
        "F_status": {"defined", "source_equal_variances_branch", "zero_denominator_variance_undefined",
                     "insufficient_n", "source_formula_outside_probability_range", "unresolved"},
    },
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _string(value):
    if type(value) is not str:
        return False
    try:
        return 1 <= len(value.encode("utf-8")) <= 128
    except UnicodeEncodeError:
        return False


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def parse_submission(payload, cap_bytes):
    """Apply the public JSON parser limits before semantic format checks."""
    require(len(payload) <= cap_bytes, "submission exceeds public payload cap")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def number(token, convert, limit):
        require(len(token) <= limit, "numeric token exceeds public length limit")
        value = convert(token)
        require(_finite(value), "nonfinite number")
        return value

    def constant(token):
        raise ValueError("nonfinite literal: " + token)

    try:
        result = json.loads(payload.decode("utf-8", errors="strict"), object_pairs_hook=pairs,
                            parse_int=lambda token: number(token, int, 32),
                            parse_float=lambda token: number(token, float, 128),
                            parse_constant=constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid UTF-8 or excessive JSON nesting") from error

    def walk(value, depth):
        require(depth <= 12, "JSON nesting depth exceeds 12")
        if type(value) is str:
            try:
                value.encode("utf-8", errors="strict")
            except UnicodeEncodeError as error:
                raise ValueError("invalid Unicode string") from error
        elif type(value) is dict:
            for key, item in value.items():
                walk(key, depth + 1)
                walk(item, depth + 1)
        elif type(value) is list:
            for item in value:
                walk(item, depth + 1)

    walk(result, 1)
    return result


def load_public(directory):
    documents = {}
    for name, digest in PUBLIC_PINS.items():
        payload = (Path(directory) / name).read_bytes()
        require(hashlib.sha256(payload).hexdigest() == digest, "public source pin mismatch: " + name)
        documents[name] = json.loads(payload)
    return documents["PUBLIC_CONTRACT.json"], documents["SUBMISSION_SCHEMA.json"]


def identities(contract):
    """Every pre-cutoff source cue remains present, even when unresolved/removed."""
    sessions = contract["sessions"]
    conditions = list(contract["caps"])
    return {
        "session_audit": [(row["asset_id"],) for row in sessions],
        "trials": [(row["asset_id"], ordinal) for row in sessions
                   for ordinal in range(1, row["source_cue_count_before"] + 1)],
        "daily": sorted({(row["mouse_id"], row["day"]) for row in sessions if row["day"] <= 8}),
        "mice": [(row["mouse_id"],) for row in contract["mice"]],
        "group_e": [(condition, trial) for condition in conditions
                    for trial in range(1, contract["caps"][condition] + 1)],
        "group_endpoints": [(panel, condition) for panel in ENDPOINTS for condition in conditions],
        "comparisons": [(panel,) for panel in ENDPOINTS],
    }


def scaffold(contract, schema):
    """All scientific observations are explicitly unresolved; zeros are placeholders."""
    document = dict(schema["header_values"])
    rosters = {condition: [row["mouse_id"] for row in contract["mice"]
                           if row["condition"] == condition] for condition in contract["caps"]}
    source_counts = {row["asset_id"]: row["source_cue_count_before"] for row in contract["sessions"]}
    for table, keys in identities(contract).items():
        spec = schema["tables"][table]
        rows = []
        for key in keys:
            record = dict.fromkeys(spec["columns"])
            record.update(zip(spec["identity_columns"], key))
            for field in schema["field_type_rules"][table].get("unsigned_integer", []):
                record.setdefault(field, 0)
                if field not in spec["identity_columns"]:
                    record[field] = 0
            for field in STATUSES[table]:
                record[field] = "unresolved"
            if table == "session_audit":
                record.update(cutoff_applied=False, source_cue_count_before=source_counts[key[0]])
            elif table == "trials":
                for field in spec["columns"][3:]:
                    record[field] = None
            elif table == "mice":
                record.update(learned_trial=None, h_selected_rows=None)
            elif table == "group_endpoints":
                record.update(included_mouse_ids=[], undefined_or_ineligible_mouse_statuses={
                    mouse: "unresolved" for mouse in rosters[key[1]]})
            elif table == "comparisons":
                record.update(sign_order="60s_minus_600s", F_df1=None, F_df2=None)
            rows.append([record[column] for column in spec["columns"]])
        document[table] = {"columns": list(spec["columns"]), "rows": rows}
    validate(document, contract, schema)
    return document


def null_fields(table, row, columns):
    if table == "trials":
        if row["state"] in {"recording_cutoff_removed", "unresolved"}:
            return set(columns[3:])
        if row["state"] == "prefix_removed":
            return {"retained_index", "cumulative_normalized_count"}
    elif table == "daily" and row["status"] != "defined":
        return {"mean_rate_hz", "meets_threshold"}
    elif table == "mice":
        result = set()
        if row["learner_status"] != "defined":
            result.add("is_learner")
        if row["g_status"] != "defined":
            result.add("learned_trial")
        if row["h_status"] != "defined":
            result.update({"time_to_learn_s", "h_selected_rows", "h_next_trial_present"})
        if row["k_status"] != "defined":
            result.add("k_mean_rate_hz")
        return result
    elif table in {"group_e", "group_endpoints"}:
        fields = ({"mean_rate_hz", "sample_sd_hz", "sem_hz"} if table == "group_e"
                  else {"mean", "sample_sd", "sem"})
        if row["status"] == "mean_only_n1":
            return fields - {"mean_rate_hz", "mean"}
        if row["status"] != "defined":
            return fields
    elif table == "comparisons":
        result = set()
        if row["welch_status"] == "zero_standard_error_undefined":
            result.update({"t", "welch_df", "p_two_sided"})
        elif row["welch_status"] != "defined":
            result.update({"difference", "standard_error", "t", "welch_df", "p_two_sided"})
        if row["F_status"] == "source_equal_variances_branch":
            result.update({"F_numerator_condition", "F_df1", "F_df2"})
        elif row["F_status"] not in {"defined", "source_formula_outside_probability_range"}:
            result.update({"F", "F_source_p", "F_numerator_condition", "F_df1", "F_df2"})
        return result
    return set()


def validate(document, contract, schema):
    """Public format/identity checks only. Finite inaccurate answers remain valid."""
    headers = schema["header_values"]
    require(type(document) is dict and set(document) == set(headers) | set(schema["tables"]),
            "root must contain exactly the four headers and seven tables")
    for field, expected in headers.items():
        require(type(document[field]) is type(expected) and document[field] == expected,
                "wrong header: " + field)
    expected_identities = identities(contract)
    counts = {}
    rosters = {condition: {row["mouse_id"] for row in contract["mice"] if row["condition"] == condition}
               for condition in contract["caps"]}
    for table, spec in schema["tables"].items():
        value = document[table]
        require(type(value) is dict and set(value) == {"columns", "rows"}, table + ": invalid container")
        require(value["columns"] == spec["columns"], table + ": incorrect ordered columns")
        rows = value["rows"]
        require(type(rows) is list, table + ": rows must be an array")
        require(len(rows) == len(expected_identities[table]), table + ": incomplete identity coverage")
        expected = set(expected_identities[table])
        seen = set()
        types = schema["field_type_rules"][table]
        for ordinal, values in enumerate(rows):
            prefix = f"{table} row {ordinal + 1}: "
            require(type(values) is list and len(values) == len(spec["columns"]), prefix + "wrong row width")
            row = dict(zip(spec["columns"], values))
            key = tuple(row[field] for field in spec["identity_columns"])
            for item, example in zip(key, expected_identities[table][0]):
                require(type(item) is type(example) and (type(item) is int or _string(item)),
                        prefix + "invalid identity type")
            require(key in expected and key not in seen, prefix + "unexpected or duplicate identity")
            seen.add(key)
            for field, allowed in STATUSES[table].items():
                require(_string(row[field]) and row[field] in allowed, prefix + "invalid " + field)
            nullable = null_fields(table, row, spec["columns"])
            for field in nullable:
                require(row[field] is None, prefix + field + " must be null for this status")
            for field in types.get("unsigned_integer_or_null", []):
                require(row[field] is None or (type(row[field]) is int and 0 <= row[field] <= 10**9),
                        prefix + "invalid " + field)
            for kind, check in (
                ("Boolean", lambda value: type(value) is bool),
                ("unsigned_integer", lambda value: type(value) is int and 0 <= value <= 10**9),
                ("signed_integer", lambda value: type(value) is int and -10**9 <= value <= 10**9),
                ("finite_numeric", _finite),
            ):
                for field in types.get(kind, []):
                    if field not in nullable:
                        require(check(row[field]), prefix + "invalid " + field)
            if table == "group_endpoints":
                included = row["included_mouse_ids"]
                excluded = row["undefined_or_ineligible_mouse_statuses"]
                require(type(included) is list and all(_string(mouse) for mouse in included),
                        prefix + "invalid included mouse list")
                require(len(included) == len(set(included)), prefix + "duplicate included mouse")
                require(type(excluded) is dict and all(_string(mouse) and _string(status)
                        and status in ENDPOINT_STATUS for mouse, status in excluded.items()),
                        prefix + "invalid endpoint status map")
                require(not set(included) & set(excluded)
                        and set(included) | set(excluded) == rosters[row["condition"]],
                        prefix + "endpoint inventory must partition the complete condition roster")
            elif table == "comparisons":
                require(row["sign_order"] == "60s_minus_600s", prefix + "wrong sign order")
                if "F_numerator_condition" not in nullable:
                    require(type(row["F_numerator_condition"]) is str
                            and row["F_numerator_condition"] in {"60s", "600s"},
                            prefix + "invalid F numerator condition")
        require(seen == expected, table + ": incomplete identity coverage")
        counts[table] = len(rows)
    return {"status": "public_format_valid", "row_counts": counts,
            "scope": "public_identity_type_and_status_checks_only", "scientific_score": None,
            "numerical_correctness_checked": False, "paper_improvement_claim": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "registered-runtime",
                        help="directory of the two exact checksum-pinned public contracts")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("scaffold", help="write all source identities with unresolved observations")
    prepare.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("validate", help="check format and complete public identity coverage")
    check.add_argument("--submission", type=Path, required=True)
    check.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        contract, schema = load_public(args.public_dir)
        if args.command == "scaffold":
            result = scaffold(contract, schema)
            encoded = (json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
            require(len(encoded) <= schema["payload_cap_bytes"], "scaffold exceeds public payload cap")
            with args.output.open("xb") as handle:
                handle.write(encoded)
            print(json.dumps({"status": "unresolved_scaffold_written", "bytes": len(encoded),
                              "sha256": hashlib.sha256(encoded).hexdigest(),
                              "all_scientific_observations_unresolved": True,
                              "scientific_score": None}))
        else:
            with args.submission.open("rb") as handle:
                payload = handle.read(schema["payload_cap_bytes"] + 1)
            result = validate(parse_submission(payload, schema["payload_cap_bytes"]), contract, schema)
            result["submission_sha256"] = hashlib.sha256(payload).hexdigest()
            encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
            if args.output:
                with args.output.open("x", encoding="utf-8") as handle:
                    handle.write(encoded)
            else:
                print(encoded, end="")
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "public_preflight_failed", "error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
