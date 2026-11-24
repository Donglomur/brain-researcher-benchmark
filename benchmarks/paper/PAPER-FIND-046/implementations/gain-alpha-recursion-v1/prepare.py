#!/usr/bin/env python3
"""Prepare the original Figure 3 ratTrial inputs without inferring percentiles."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location("find046_gain_alpha_model", Path(__file__).with_name("model.py"))
model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(model)
ContractError = model.ContractError
require, keys, finite = model.require, model.keys, model.finite


def validate_raw(payload):
    keys(payload, ("schema_version", "input_kind", "preprocessing", "rat_trial"), "input")
    require(type(payload["schema_version"]) is int and payload["schema_version"] == 1,
            "schema_version must be integer1")
    require(payload["input_kind"] in model.INPUT_KINDS, "explicit input_kind required")
    require(payload["preprocessing"] == "author_figure3_raw_ratTrial",
            "raw author Figure3 ratTrial required; already prepared input must not be processed twice")
    rows = payload["rat_trial"]
    keys(rows, ("trial_ids", "reward", "iti", "ntrials"), "rat_trial")
    ids, rewards, iti, counts = (rows[k] for k in ("trial_ids", "reward", "iti", "ntrials"))
    require(isinstance(ids, list) and ids and all(type(x) is str and x for x in ids),
            "trial_ids must retain explicit original identities")
    require(len(set(ids)) == len(ids), "duplicate trial identities")
    require(isinstance(rewards, list) and isinstance(iti, list) and
            len(rewards) == len(iti) == len(ids), "full reward/ITI/identity row alignment required")
    require(isinstance(counts, list) and counts and
            all(type(n) is int and n >= 0 for n in counts) and sum(counts) == len(ids),
            "ntrials must partition every row exactly")
    reward = [finite(x, f"reward[{i}]", nullable=True) for i, x in enumerate(rewards)]
    raw_iti = [finite(x, f"iti[{i}]", nullable=True) for i, x in enumerate(iti)]
    masked_iti, first_rows, offset = list(raw_iti), [], 0
    for session, count in enumerate(counts):
        # MATLAB assigns ITI(ctr) for every ntrials entry, including zero counts.
        require(offset < len(ids),
                f"session{session}: source first-ITI assignment would extend ITI beyond original rows")
        masked_iti[offset] = None
        first_rows.append(offset)
        offset += count
    require(any(x is not None for x in masked_iti),
            "no finite ITI operand remains for the external native percentile")
    return reward, raw_iti, masked_iti, first_rows


def statistic_request(payload):
    _, _, masked_iti, first_rows = validate_raw(payload)
    return {"schema_version": 1, "task_id": model.TASK_ID,
            "source_revision": model.REVISION, "input_kind": payload["input_kind"],
            "input_sha256": model.canonical_hash(payload),
            "source_first_iti_assignment_rows_zero_based": first_rows,
            "statistic_operands": [{"key": "iti_p99", "function": "prctile",
                                    "percentile": 99, "values": masked_iti}],
            "missing_value_encoding": "Restore every null to MATLAB NaN without row deletion",
            "qualification": "requests_only_not_native_statistical_validation"}


def standard_reward(value):
    """Both assignments in convertreward.m, including its unchanged values."""
    if value is None:
        return None
    converted = {4: 1, 5: 1, 8: 2, 10: 2, 16: 3, 20: 3,
                 32: 4, 40: 4, 64: 5, 80: 5}.get(value, value)
    return {1: 5, 2: 10, 3: 20, 4: 40, 5: 80}.get(converted, converted)


def prepare(payload, receipt):
    reward, raw_iti, masked_iti, first_rows = validate_raw(payload)
    request = statistic_request(payload)
    threshold = model.validate_receipt(request, receipt)["iti_p99"]
    outlier = [i for i, value in enumerate(masked_iti)
               if value is not None and value > threshold]
    outlier_set, first_set = set(outlier), set(first_rows)
    prepared_iti = [None if i in outlier_set else value for i, value in enumerate(masked_iti)]
    prepared = {"schema_version": 1, "input_kind": payload["input_kind"],
                "preprocessing": "author_figure3_preprocessed_ratTrial",
                "rat_trial": {"trial_ids": list(payload["rat_trial"]["trial_ids"]),
                              "reward": [standard_reward(x) for x in reward],
                              "iti": prepared_iti,
                              "ntrials": list(payload["rat_trial"]["ntrials"])}}
    # Do not emit something the existing recurrence cannot consume. In
    # particular, insufficient retained rows and retained missing rewards fail.
    model.validate(prepared)
    ledger = [{"trial_id": identity, "row_zero_based": i,
               "raw_reward": reward[i], "standard_reward": prepared["rat_trial"]["reward"][i],
               "raw_iti": raw_iti[i], "prepared_iti": prepared_iti[i],
               "source_first_iti_assignment": i in first_set,
               "source_p99_outlier": i in outlier_set,
               "retained_by_recurrence_iti_mask": prepared_iti[i] is not None}
              for i, identity in enumerate(prepared["rat_trial"]["trial_ids"])]
    audit = {"schema_version": 1, "task_id": model.TASK_ID, "source_revision": model.REVISION,
             "input_kind": payload["input_kind"], "status": "conditional_source_preparation_only",
             "input_sha256": model.canonical_hash(payload),
             "request_sha256": model.canonical_hash(request),
             "receipt_sha256": model.canonical_hash(receipt),
             "prepared_sha256": model.canonical_hash(prepared),
             "native_iti_p99": threshold,
             "source_first_iti_assignment_rows_zero_based": first_rows,
             "outlier_rows_zero_based": outlier, "row_ledger": ledger,
             "reproduction_qualified": False, "improvement_eligible": False,
             "limits": ["Native input completeness, export authenticity and percentile execution are unverified.",
                        "All declared original rows and ntrials entries are retained; no original population is inferred.",
                        "This prepares recurrence inputs only, not fits, full-panel reproduction or scientific performance."]}
    return prepared, audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("requests", "prepare"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = model.read_json(args.input)
        if args.mode == "requests":
            require(args.receipt is None and args.audit_output is None,
                    "requests mode accepts neither receipt nor audit output")
            outputs = [(args.output, statistic_request(payload))]
        else:
            require(args.receipt is not None and args.audit_output is not None,
                    "prepare requires --receipt and --audit-output")
            require(args.output.resolve() != args.audit_output.resolve(), "distinct output paths required")
            prepared, audit = prepare(payload, model.read_json(args.receipt))
            outputs = [(args.output, prepared), (args.audit_output, audit)]
        require(all(not path.exists() for path, _ in outputs), "output already exists")
        for path, value in outputs:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    except (ContractError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"input rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
