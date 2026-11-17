"""Complete invented integrated reference test and real isolated transport cases.

Defined only. The source phase never imports this module into a native runtime.
"""
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from consumer import FEATURES, GROUPS, outer_fold, training_view, ContractError
from checks import cohort
from reference import ContextCounts
from model_artifact import from_model, encode_artifact, decode_artifact
from reference_workflow import fit_all_references, emit
from transport_harness import stage_programme
from journal_controls import run_journal_controls

NEGATIVE = {
    "wrong_token": ("out-of-order/replayed token",),
    "extra_reply": ("multiple replies ahead of commitment", "out-of-order/replayed token", "unsolicited output before"),
    "nan": ("nonfinite JSON",),
    "duplicate_key": ("duplicate JSON key",),
    "zero_probability": ("four strictly positive finite probabilities",),
    "oversized": ("participant reply record bound", "unterminated oversized reply"),
    "unterminated": ("unterminated oversized reply",),
    "early_exit": ("EOF before complete trial", "Broken pipe"),
    "timeout": ("whole trial/response deadline",),
}
POSITIVE = ("normal", "isolation", "lookahead", "orphan_child")
TRANSPORT_CONTROLS = (*POSITIVE, *NEGATIVE, "trial_reset", "future_perturbation")
EXPECTED_EPISODES = len(POSITIVE) + len(NEGATIVE) + 4


def run_controls(source, output, family, deadline):
    source = Path(source); output = Path(output); output.mkdir(mode=0o700)
    # The complete production journal integration precedes even tiny fits,
    # real episode dispatch and all authentic parsing/fitting.
    rows = run_journal_controls(source, output / "production-journal-controls", family.plan)
    ds = cohort()
    synthetic = fit_all_references(ds, output / "complete-synthetic-references", deadline,
                                   expected_decisions=640, expected_trials=80)
    if synthetic["complete_outer_folds"] != 80 or synthetic["inner_ridge_fits"] != 720 or synthetic["final_ridge_fits"] != 80:
        raise ContractError("complete invented integrated reference control")
    rows.append({"name": "complete80fold_reference_artifact_score", "pass": True, "tiny_fits": 800})
    checked = 0
    for subject, held in sorted(GROUPS):
        train, _ = outer_fold(ds, subject, held)
        altered = []
        for d in ds:
            if d.subject == subject and d.session == held:
                x = d.observation(); x["nB"] = 11
                d = replace(d, values=tuple(x[k] for k in FEATURES), action=4 if d.action != 4 else 3)
            altered.append(d)
        changed_train, _ = outer_fold(altered, subject, held)
        if training_view(train) != training_view(changed_train):
            raise ContractError("held states/labels entered training projection")
        checked += 1
    if checked != 80: raise ContractError("all80 leakage projections")
    rows.append({"name": "all80_held_state_label_projection_invariance", "pass": True, "folds": checked})
    for b in (b'{"schema":"bad"}', b'{"schema":"x","schema":"y"}', b'{"x":NaN}'):
        try: decode_artifact(b)
        except (ValueError, TypeError): pass
        else: raise ContractError("invalid artifact was accepted")
    rows.append({"name": "artifact_unknown_duplicate_nonfinite_refusal", "pass": True})
    train, test = outer_fold(ds, "1", 1); trial = tuple(test)
    model = encode_artifact(from_model(ContextCounts(train)))
    model_path = output / (os.urandom(16).hex() + ".json")
    with model_path.open("xb") as f: f.write(model)
    model_path.chmod(0o400); model_pin = {"bytes": len(model), "sha256": hashlib.sha256(model).hexdigest()}
    canary = output / "private-host-canary"; canary.write_bytes(os.urandom(32)); canary.chmod(0o600)
    constants = ("HOST_CANARY = " + repr(str(canary)) + "\n").encode()
    attack_source = (source / "hostile_program.py").read_bytes()
    start_count = family.count
    def execute(mode, seq=trial, secret=None):
        programme = output / ("programme-%03d" % family.count)
        entry = "participant_entry.py" if mode == "normal" else "attack_" + mode + ".py"
        extra = {} if mode == "normal" else {entry: attack_source, "control_constants.py": constants}
        pins = stage_programme(source, programme, extra)
        return family.run(seq, programme, model_path, entry, pins, model_pin, secret=secret)
    for name in POSITIVE:
        result, predictions, directory = execute(name)
        if not result["complete"] or len(predictions) != len(trial):
            raise ContractError("positive real transport control failed: " + name)
        rows.append({"name": name, "pass": True, "episode": str(directory)})
    for name, expected in NEGATIVE.items():
        result, predictions, directory = execute(name)
        attach = result["attach"]
        if result["complete"] or predictions is not None or not result["cid"] or attach is None or attach["issue"] is None:
            raise ContractError("negative transport did not reach its real admitted boundary: " + name)
        reason = attach["issue"]["reason"]
        if not any(x in reason for x in expected):
            raise ContractError("negative transport failed at an unrelated stage: " + name + ": " + reason)
        # A correctly committed first reply may legally release query2 before
        # a separately arriving duplicate is observed; the whole run still fails.
        if not (1 <= attach["counts"]["queries"] <= (2 if name == "extra_reply" else 1)):
            raise ContractError("rejected reply exposed a later state")
        rows.append({"name": name, "pass": True, "observed_refusal": reason, "episode": str(directory)})
    one, _, dir_one = execute("trial_reset"); two, _, dir_two = execute("trial_reset")
    if not one["complete"] or not two["complete"] or one["cid"] == two["cid"]:
        raise ContractError("trial isolation did not use fresh real containers")
    rows.append({"name": "trial_reset", "pass": True, "episodes": [str(dir_one), str(dir_two)]})
    secret = b"explicit-invented-future-perturbation-key"
    altered = list(trial); x = altered[-1].observation(); x["nL"] += 1; x["muL"] = (x["rL"] + 1) / (x["nL"] + 2)
    altered[-1] = replace(altered[-1], action=4 if altered[-1].action == 3 else 3, values=tuple(x[k] for k in FEATURES))
    one, values_one, dir_one = execute("normal", secret=secret)
    two, values_two, dir_two = execute("normal", seq=tuple(altered), secret=secret)
    if not one["complete"] or not two["complete"] or values_one[0][1] != values_two[0][1]:
        raise ContractError("future perturbation altered first real committed prediction")
    # These are tiny invented transcripts, read in full; no scientific payload.
    q_one = (dir_one / "queries.jsonl").read_bytes().splitlines()
    q_two = (dir_two / "queries.jsonl").read_bytes().splitlines()
    if len(q_one) != len(trial) or len(q_two) != len(trial) or q_one[0] != q_two[0] or q_one[-1] == q_two[-1]:
        raise ContractError("actual current/future query separation")
    rows.append({"name": "future_perturbation", "pass": True, "episodes": [str(dir_one), str(dir_two)]})
    if family.count - start_count != EXPECTED_EPISODES or len(rows) != 7 + len(TRANSPORT_CONTROLS):
        raise ContractError("complete integrated control roster")
    result = {"schema": "hybrid-participant-integrated-controls-v1", "controls": rows, "all_passed": True,
              "control_count": len(rows), "real_container_episodes": EXPECTED_EPISODES,
              "tiny_invented_ridge_fits": 800, "authentic_data": False, "count_delta": 0,
              "earlier31_controls": "accepted unchanged prerequisite evidence; not rerun or counted as new outcomes"}
    emit(output / "CONTROLS.json", result)
    return result
