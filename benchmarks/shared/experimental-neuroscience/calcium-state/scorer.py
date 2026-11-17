"""Prospective calcium-state endpoint. No authentic dataset is admitted here.

The evaluator supplies a digest-bound, private manifest produced after full
source admission. Candidate JSON cannot supply labels, cohort or exclusions.
Only standard-library code is used; no upstream implementation is copied.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
from collections import defaultdict
from pathlib import Path

TASK = "sleep-anesthesia-calcium-2026"
STATES = {
    "sleep": ("awake", "quiet_wake", "nrem", "rem"),
    "anesthesia": ("awake", "anesthesia"),
}
RAW_STATES = {
    "sleep": {0.0: "awake", 0.5: "quiet_wake", 1.0: "nrem", 2.0: "rem"},
    "anesthesia": {0.0: "awake", 1.0: "anesthesia"},
}
GATES = (
    "complete_cohort", "animal_identity", "label_and_boundary_semantics",
    "preprocessing_context", "processed_release_equivalence", "data_rights",
)
MAX_JSON_BYTES = 16 * 1024 * 1024


class Invalid(ValueError):
    pass


def require(condition, why):
    if not condition:
        raise Invalid(why)


def keys(obj, expected, why):
    require(type(obj) is dict and set(obj) == set(expected), why)


def token(x):
    return type(x) is str and 0 < len(x) <= 128 and all(
        c.isascii() and (c.isalnum() or c in "_.-") for c in x
    )


def integer(x, minimum=0):
    return type(x) is int and x >= minimum


def sha256(x):
    return type(x) is str and len(x) == 64 and all(c in "0123456789abcdef" for c in x)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "duplicate JSON key")
        result[k] = v
    return result


def load_json(path, expected_sha256=None):
    with Path(path).open("rb") as f:
        raw = f.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "JSON byte limit")
    if expected_sha256 is not None:
        require(sha256(expected_sha256), "manifest digest syntax")
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "manifest digest mismatch")
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Invalid("invalid JSON encoding") from exc


def state_label(regime, raw):
    require(regime in RAW_STATES and finite(raw), "unknown regime or state value")
    require(raw in RAW_STATES[regime], "unsupported state code")
    return RAW_STATES[regime][raw]


def derive_cases(recordings, window_frames, guard_frames, case_salt_hex):
    """Enumerate every eligible window, never crossing state or acquisition cuts.

    Each epoch is half-open and the complete epoch sequence must cover [0,T).
    Acquisition boundaries are also half-open cuts. Guard each resulting
    segment at both ends; retain exact guarded/remainder exclusion counts.
    Frame indexing is zero-based only after authenticated MATLAB conversion.
    """
    require(type(recordings) is list and recordings, "empty recordings")
    require(integer(window_frames, 1) and integer(guard_frames), "window/guard configuration")
    require(sha256(case_salt_hex), "private256bit case salt required")
    cases, coverage, seen = [], [], set()
    for rec in recordings:
        keys(rec, ("recording_id", "animal_id", "regime", "n_frames", "source_sha256",
                   "boundaries", "epochs"), "recording schema")
        rid, animal, regime, n = (rec[k] for k in ("recording_id", "animal_id", "regime", "n_frames"))
        require(token(rid) and rid not in seen and token(animal), "recording/animal identity")
        seen.add(rid)
        require(regime in STATES and integer(n, 1) and sha256(rec["source_sha256"]), "recording provenance")
        bounds = rec["boundaries"]
        require(type(bounds) is list and all(integer(x, 1) and x < n for x in bounds), "boundary range")
        require(bounds == sorted(set(bounds)), "boundary order/uniqueness")
        epochs = rec["epochs"]
        require(type(epochs) is list and epochs, "missing state epochs")
        previous, local = 0, []
        for epoch in epochs:
            keys(epoch, ("start", "stop", "raw_state"), "epoch schema")
            a, b = epoch["start"], epoch["stop"]
            require(integer(a) and integer(b, 1) and a == previous and a < b <= n, "epoch gap/overlap/range")
            label = state_label(regime, epoch["raw_state"])
            cuts = [a] + [c for c in bounds if a < c < b] + [b]
            for lo, hi in zip(cuts, cuts[1:]):
                available = max(0, hi - lo - 2 * guard_frames)
                count = available // window_frames
                for j in range(count):
                    start = lo + guard_frames + j * window_frames
                    private_identity = json.dumps(
                        [TASK, rid, animal, rec["source_sha256"], start, start + window_frames],
                        separators=(",", ":"), ensure_ascii=True).encode()
                    ident = hmac.new(bytes.fromhex(case_salt_hex), private_identity,
                                     hashlib.sha256).hexdigest()
                    cases.append({"case_id": ident, "recording_id": rid, "animal_id": animal,
                                  "regime": regime, "state": label, "start": start,
                                  "stop": start + window_frames})
                local.append({"start": lo, "stop": hi, "state": label,
                              "scored_frames": count * window_frames,
                              "guarded_frames": min(hi - lo, 2 * guard_frames),
                              "remainder_frames": available % window_frames,
                              "case_count": count})
            previous = b
        require(previous == n, "incomplete recording state coverage")
        require(sum(x["scored_frames"] + x["guarded_frames"] + x["remainder_frames"] for x in local) == n,
                "frame conservation")
        coverage.append({"recording_id": rid, "n_frames": n, "segments": local})
    require(cases, "no eligible complete windows")
    return cases, coverage


def validate_manifest(manifest):
    keys(manifest, ("schema", "task_id", "admission", "window_frames", "guard_frames", "case_salt_hex",
                    "recordings", "folds"), "manifest schema")
    require(manifest["schema"] == "calcium-state-private-manifest-v1" and manifest["task_id"] == TASK,
            "manifest identity")
    keys(manifest["admission"], GATES, "admission gate schema")
    for name, evidence in manifest["admission"].items():
        keys(evidence, ("accepted", "evidence_sha256"), "admission evidence schema")
        require(evidence["accepted"] is True and sha256(evidence["evidence_sha256"]), "unresolved admission: " + name)
    cases, coverage = derive_cases(manifest["recordings"], manifest["window_frames"], manifest["guard_frames"],
                                   manifest["case_salt_hex"])
    animals = {r["animal_id"] for r in manifest["recordings"]}
    require(len(animals) >= 3, "at least three authenticated animals required")
    case_animals = {c["animal_id"] for c in cases}
    require(case_animals == animals, "animal lost to window exclusions")
    folds = manifest["folds"]
    require(type(folds) is list and len(folds) == len(animals), "complete outer fold census")
    evaluated, fold_ids = set(), set()
    for fold in folds:
        keys(fold, ("fold_id", "train_animals", "validation_animals", "test_animals"), "fold schema")
        require(token(fold["fold_id"]) and fold["fold_id"] not in fold_ids, "fold identity")
        fold_ids.add(fold["fold_id"])
        groups = []
        for role in ("train_animals", "validation_animals", "test_animals"):
            ids = fold[role]
            require(type(ids) is list and ids and all(token(x) for x in ids) and len(ids) == len(set(ids)), "fold group census")
            groups.append(set(ids))
        train, val, test = groups
        require(len(test) == 1 and not (train & val or train & test or val & test), "animal leakage or multi-animal test")
        require(train | val | test == animals, "fold does not partition all animals")
        require(not test & evaluated, "animal evaluated more than once")
        evaluated |= test
        # Both training and tuning must contain every source-defined regime/state.
        expected = {(r, s) for r, states in STATES.items() for s in states}
        for role in (train, val):
            observed = {(c["regime"], c["state"]) for c in cases if c["animal_id"] in role}
            require(observed == expected, "incomplete train/validation regime-state support")
    require(evaluated == animals, "animal evaluation coverage")
    return cases, coverage


def candidate_index(manifest):
    """Project only allowed case metadata; array provisioning is a separate gate.

    Sort by opaque token so index order cannot expose acquisition chronology.
    No private recording/animal identity, salt, labels, offsets or source digest
    is copied. The future packet builder must use this whitelist, not cases.
    """
    cases, _ = validate_manifest(manifest)
    return [{"case_id": c["case_id"], "regime": c["regime"],
             "n_frames": c["stop"] - c["start"]}
            for c in sorted(cases, key=lambda c: c["case_id"])]


def validate_prediction(submission, cases):
    keys(submission, ("schema", "task_id", "predictions"), "submission schema")
    require(submission["schema"] == "calcium-state-predictions-v1" and submission["task_id"] == TASK,
            "submission identity")
    rows = submission["predictions"]
    require(type(rows) is list and len(rows) == len(cases), "prediction count")
    expected = {c["case_id"]: c for c in cases}
    result = {}
    for row in rows:
        keys(row, ("case_id", "probabilities"), "prediction row schema")
        ident = row["case_id"]
        require(type(ident) is str and ident in expected and ident not in result, "unknown/duplicate case")
        p = row["probabilities"]
        states = STATES[expected[ident]["regime"]]
        keys(p, states, "regime-specific probability schema")
        require(all(finite(v) and 0 <= v <= 1 for v in p.values()), "invalid probability")
        require(abs(math.fsum(p.values()) - 1.0) <= 1e-10, "probabilities do not sum to one")
        result[ident] = p
    require(set(result) == set(expected), "missing prediction")
    return result


def metrics(cases, predictions):
    grouped = defaultdict(list)
    for c in cases:
        p, states = predictions[c["case_id"]], STATES[c["regime"]]
        chosen = max(states, key=lambda s: p[s])  # ties use declared state order
        grouped[(c["animal_id"], c["regime"], c["state"])].append(
            (float(chosen == c["state"]), -math.log2(max(p[c["state"]], 1e-12))))
    state_rows, regime_rows, animal_rows = [], [], []
    by_regime = defaultdict(list)
    for (animal, regime, state), observations in sorted(grouped.items()):
        row = {"animal_id": animal, "regime": regime, "state": state,
               "cases": len(observations),
               "recall": math.fsum(x[0] for x in observations) / len(observations),
               "log_loss_bits": math.fsum(x[1] for x in observations) / len(observations)}
        state_rows.append(row)
        by_regime[(animal, regime)].append(row)
    by_animal = defaultdict(list)
    for (animal, regime), rows in sorted(by_regime.items()):
        row = {"animal_id": animal, "regime": regime,
               "states_present": [r["state"] for r in rows],
               "balanced_accuracy": math.fsum(r["recall"] for r in rows) / len(rows),
               "balanced_log_loss_bits": math.fsum(r["log_loss_bits"] for r in rows) / len(rows)}
        regime_rows.append(row)
        by_animal[animal].append(row)
    for animal, rows in sorted(by_animal.items()):
        animal_rows.append({"animal_id": animal,
                            "regimes_present": [r["regime"] for r in rows],
                            "balanced_accuracy": math.fsum(r["balanced_accuracy"] for r in rows) / len(rows),
                            "balanced_log_loss_bits": math.fsum(r["balanced_log_loss_bits"] for r in rows) / len(rows)})
    return {"animal_macro_balanced_accuracy": math.fsum(r["balanced_accuracy"] for r in animal_rows) / len(animal_rows),
            "animal_macro_balanced_log_loss_bits": math.fsum(r["balanced_log_loss_bits"] for r in animal_rows) / len(animal_rows),
            "animal_metrics": animal_rows, "regime_metrics": regime_rows, "state_metrics": state_rows}


def score(manifest, submission, rate_reference):
    cases, coverage = validate_manifest(manifest)
    predicted = validate_prediction(submission, cases)
    reference = validate_prediction(rate_reference, cases)
    result, baseline = metrics(cases, predicted), metrics(cases, reference)
    paired = []
    for a, b in zip(result["animal_metrics"], baseline["animal_metrics"]):
        require(a["animal_id"] == b["animal_id"], "paired animal join")
        paired.append({"animal_id": a["animal_id"],
                       "balanced_accuracy_gain": a["balanced_accuracy"] - b["balanced_accuracy"],
                       "log_loss_bits_reduction": b["balanced_log_loss_bits"] - a["balanced_log_loss_bits"]})
    return {"schema": "calcium-state-score-v1", "task_id": TASK,
            "candidate": result, "rate_reference": baseline, "paired_animal_differences": paired,
            "primary_gain": result["animal_macro_balanced_accuracy"] - baseline["animal_macro_balanced_accuracy"],
            "coverage": coverage, "cases": len(cases), "animals": len(paired),
            "inference": "Descriptive paired estimates only; no significance, causal, consciousness or qualification claim."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--predictions", required=True)
    p.add_argument("--rate-reference", required=True)
    args = p.parse_args()
    result = score(load_json(args.manifest, args.manifest_sha256),
                   load_json(args.predictions), load_json(args.rate_reference))
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
