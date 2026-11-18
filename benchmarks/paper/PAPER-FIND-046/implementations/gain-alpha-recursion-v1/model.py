#!/usr/bin/env python3
"""Figure 3 deterministic recurrences; no fitting or inferred MATLAB percentiles.

The source-preprocessed input and external statistic receipt are declarations,
not authenticated native exports. This module never promotes scientific status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

TASK_ID = "PAPER-FIND-046"
REVISION = "b7b68ca8c107d8ce4a061e16da214307f175c3e5"
INPUT_KINDS = ("generated_engineering_control", "authorized_native_export")
MAX_JSON_BYTES = 32 * 1024 * 1024
CONDITIONS = (
    ("figure3a", 0.6, 1.0, False),
    ("gain_proestrus", 0.6, 1.75, True),
    ("alpha_proestrus", 0.8, 1.0, False),
    ("gain_diestrus", 0.6, 1.0, True),
    ("alpha_diestrus", 0.6, 1.0, False),
)


class ContractError(ValueError):
    """Cannot preserve the explicitly scoped source computation."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def keys(value, expected, where):
    require(isinstance(value, dict) and set(value) == set(expected),
            f"{where}: exact fields required: {','.join(expected)}")


def finite(value, where, nullable=False):
    if value is None and nullable:
        return None
    require(type(value) in (int, float), f"{where}: finite real number required")
    try:
        out = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContractError(f"{where}: finite real number required") from exc
    require(math.isfinite(out), f"{where}: use null for missing values")
    return out


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate(payload):
    keys(payload, ("schema_version", "input_kind", "preprocessing", "rat_trial"), "input")
    require(type(payload["schema_version"]) is int and payload["schema_version"] == 1,
            "schema_version must be integer1")
    require(payload["input_kind"] in INPUT_KINDS, "explicit input_kind required")
    require(payload["preprocessing"] == "author_figure3_preprocessed_ratTrial",
            "only the original caller's preprocessed ratTrial interface is supported")
    rows = payload["rat_trial"]
    keys(rows, ("trial_ids", "reward", "iti", "ntrials"), "rat_trial")
    ids, rewards, iti, counts = (rows[k] for k in ("trial_ids", "reward", "iti", "ntrials"))
    require(isinstance(ids, list) and ids and all(type(x) is str and x for x in ids),
            "trial_ids must be a nonempty array of explicit identities")
    require(len(set(ids)) == len(ids), "duplicate trial identities")
    require(isinstance(rewards, list) and isinstance(iti, list) and
            len(rewards) == len(iti) == len(ids), "full reward/ITI/identity row alignment required")
    require(isinstance(counts, list) and counts and
            all(type(n) is int and n >= 0 for n in counts) and sum(counts) == len(ids),
            "ntrials must partition every row exactly; zero-length sessions are retained")
    # MATLAB masks solely on nonmissing ITI. An ignored reward may be missing.
    checked_rewards = [finite(x, f"reward[{i}]", nullable=True) for i, x in enumerate(rewards)]
    checked_iti = [finite(x, f"iti[{i}]", nullable=True) for i, x in enumerate(iti)]
    sessions, offset = [], 0
    for session, n in enumerate(counts):
        if n:
            require(checked_iti[offset] is None,
                    f"session{session}: source Figure3 caller must set first ITI to missing")
        sessions.extend([session] * n)
        offset += n
    good = [i for i, x in enumerate(checked_iti) if x is not None]
    require(len(good) >= 2,
            "fewer than two retained ITI rows: source first-pass initialization is undefined")
    require(all(checked_rewards[i] is not None for i in good),
            "retained ITI row has missing reward; native missingness semantics unresolved")
    starts = {j for j, index in enumerate(good)
              if j == 0 or sessions[index] != sessions[good[j - 1]]}
    return {"ids": ids, "reward": checked_rewards, "iti": checked_iti,
            "ntrials": counts, "sessions": sessions, "good": good, "starts": starts}


def pass_states(rewards, starts, alpha, initial, gain=1.0, gain_enabled=False, threshold=0.0):
    """Preserve the original n-1 loop, including its final-row asymmetry."""
    kappa, rpe = [None] * len(rewards), [None] * len(rewards)
    for i in range(len(rewards) - 1):
        if i in starts:
            kappa[i] = initial
        delta = finite(rewards[i] - kappa[i], f"rpe[{i}]")
        if gain_enabled and delta > threshold:
            delta = finite(delta * gain, f"gained_rpe[{i}]")
        rpe[i] = delta
        kappa[i + 1] = finite(kappa[i] + alpha * delta, f"kappa[{i + 1}]")
    return kappa, rpe


def first_passes(state):
    rewards = [state["reward"][i] for i in state["good"]]
    answer = {}
    for alpha in (0.6, 0.8):
        kappa, rpe = pass_states(rewards, state["starts"], alpha, 1.0)
        ordered = sorted(kappa)
        middle = len(ordered) // 2
        initial = (ordered[middle] if len(ordered) % 2 else
                   finite((ordered[middle - 1] + ordered[middle]) / 2.0, "median"))
        answer[alpha] = {"kappa": kappa, "rpe": rpe, "median_kappa": initial}
    return answer


def statistic_requests(payload):
    state = validate(payload)
    passes = first_passes(state)
    operands = [{"key": "iti_p90", "function": "prctile", "percentile": 90,
                 "values": state["iti"]}]
    for alpha in (0.6, 0.8):
        operands.append({"key": f"first_rpe_alpha_{alpha}_p90", "function": "prctile",
                         "percentile": 90, "values": passes[alpha]["rpe"]})
    return {"schema_version": 1, "task_id": TASK_ID, "source_revision": REVISION,
            "input_kind": payload["input_kind"], "input_sha256": canonical_hash(payload),
            "statistic_operands": operands,
            "missing_value_encoding": "JSON null must be restored to MATLAB NaN without row deletion",
            "qualification": "requests_only_not_native_statistical_validation"}


def validate_receipt(request, receipt):
    keys(receipt, ("schema_version", "input_kind", "request_sha256", "producer", "values"),
         "statistic receipt")
    require(type(receipt["schema_version"]) is int and receipt["schema_version"] == 1,
            "receipt schema_version must be integer1")
    require(receipt["input_kind"] == request["input_kind"], "receipt/input kind mismatch")
    require(receipt["request_sha256"] == canonical_hash(request),
            "statistic receipt does not bind these exact operands")
    require(type(receipt["producer"]) is str and receipt["producer"].strip(),
            "explicit statistic producer/release declaration required")
    operands = request["statistic_operands"]
    keys(receipt["values"], tuple(x["key"] for x in operands), "receipt values")
    values = {}
    for operand in operands:
        key = operand["key"]
        value = finite(receipt["values"][key], key)
        support = [x for x in operand["values"] if x is not None]
        require(min(support) <= value <= max(support), f"{key}: result outside operand support")
        values[key] = value
    return values


def reconstruct(payload, receipt):
    state = validate(payload)
    request = statistic_requests(payload)
    stats = validate_receipt(request, receipt)
    passes = first_passes(state)
    rewards = [state["reward"][i] for i in state["good"]]
    outputs = []
    for name, alpha, gain, gain_enabled in CONDITIONS:
        initial = passes[alpha]["median_kappa"]
        threshold = stats[f"first_rpe_alpha_{alpha}_p90"]
        kappa, rpe = pass_states(rewards, state["starts"], alpha, initial,
                                gain, gain_enabled, threshold)
        latency = [finite(stats["iti_p90"] - 0.1 * x, "latency") for x in kappa]
        def expand(values):
            full = [None] * len(state["ids"])
            for index, value in zip(state["good"], values):
                full[index] = value
            return full
        outputs.append({"condition": name, "alpha": alpha, "gain": gain,
                        "gain_enabled": gain_enabled, "opto_arg": 0, "figure": 3,
                        "initial_kappa": initial, "large_rpe_threshold": threshold,
                        "LatOpt": expand(latency), "RPE": expand(rpe),
                        "Kappa": expand(kappa), "Rewards": expand(rewards)})
    return {"schema_version": 1, "task_id": TASK_ID, "source_revision": REVISION,
            "status": "conditional_recurrence_component_only", "input_kind": payload["input_kind"],
            "input_sha256": canonical_hash(payload), "request_sha256": canonical_hash(request),
            "receipt_sha256": canonical_hash(receipt), "trial_ids": list(state["ids"]),
            "ntrials": list(state["ntrials"]), "retained_indices_zero_based": state["good"],
            "retained_session_start_positions_zero_based": sorted(state["starts"]),
            "last_retained_rpe_is_missing": True,
            "last_retained_row_starts_session": len(rewards) - 1 in state["starts"],
            "final_session_start_reset_executed": False if len(rewards) - 1 in state["starts"] else None,
            "conditions": outputs, "native_statistic_authentication": "not_established",
            "native_preprocessing_and_matlab_parity": "not_established",
            "reproduction_qualified": False, "improvement_eligible": False,
            "limits": [
                "Input must retain the author's reward conversion, first-ITI removal and 99th-percentile outlier handling; this module does not perform or authenticate them.",
                "Native percentile outputs are required externally. Hash binding is operand identity, not proof that MATLAB produced the values.",
                "Only deterministic opto_arg0/fig3 calls are implemented. No fits, random intervention, Figure4 behavior or supplied BestFits verification.",
                "No downstream block dynamics/regressions, Figure2 or Figure3 full-panel reproduction, scientific improvement or task readiness is established.",
            ]}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    with path.open("rb") as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "input exceeds32MiB explicit JSON envelope; no subset is selected")
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ContractError(f"invalid JSON constant:{x}")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("requests", "reconstruct"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = read_json(args.input)
        if args.mode == "requests":
            require(args.receipt is None, "requests mode does not consume a receipt")
            result = statistic_requests(payload)
        else:
            require(args.receipt is not None, "reconstruct requires a statistic receipt")
            result = reconstruct(payload, read_json(args.receipt))
        encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
    except (ContractError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"input rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
