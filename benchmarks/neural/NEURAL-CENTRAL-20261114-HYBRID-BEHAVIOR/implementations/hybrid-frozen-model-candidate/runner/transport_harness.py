"""Finite Hybrid episode orchestration, including independent outer recovery."""
import hashlib
import json
import os
import re
import time
from pathlib import Path
import donor_checked_source as custody
import donor_create_lifecycle as lifecycle
import donor_process_closure as closer
from episode_owner_base import Owner
from trial_transport import TrialOwner
from reference_workflow import emit, group_complete_trials
from consumer import ContractError, GROUPS, validate_decisions
from scoring import score_complete, paired_comparison

PROGRAMME_FILES = ("participant_entry.py", "model_artifact.py", "reference.py", "consumer.py")


def stage_programme(source, destination, extra=None):
    destination.mkdir(mode=0o700); pins = {}
    for name in PROGRAMME_FILES:
        b = (source / name).read_bytes(); custody.write_new(destination / name, b, 1048576)
        pins[name] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    for name, b in (extra or {}).items():
        custody.need(Path(name).name == name and name.endswith(".py") and name not in pins, "flat control programme")
        custody.write_new(destination / name, b, 1048576); pins[name] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    custody.need(sum(x["bytes"] for x in pins.values()) <= 1048576, "whole programme bound")
    return pins


class EpisodeFamily:
    def __init__(self, plan, source, output, deadline, signals):
        self.plan = plan; self.source = source; self.output = output; self.deadline = deadline; self.signals = signals
        self.root = output / "episodes"; self.root.mkdir(mode=0o700); self.count = 0; self.rows = []
        self.reserved_output = 0

    def run(self, trial, programme, artifact, entry, programme_pins, artifact_pin, secret=None):
        index = self.count; self.count += 1
        custody.need(self.count <= self.plan["maximum_episodes"], "entire predeclared episode count")
        # Admission is conservative and complete: all possible current queries,
        # valid-size replies, and a finite lifecycle receipt allowance per trial.
        self.reserved_output += len(trial) * 8192 + 4 * 1024**2 + 65536 + 4097
        custody.need(self.reserved_output <= self.plan["episode_output_reservation_bytes"], "complete episode-family output reservation")
        root = self.root / ("episode-%05d" % index); root.mkdir(mode=0o700)
        token = self.plan["operation_token"] + "-e%05d" % index
        owner = TrialOwner(custody, closer, root, self.source, self.plan, self.plan["source_lock_sha256"],
                           self.deadline, self.signals, token, lifecycle=lifecycle, cli_group_mode="controller")
        result, predictions = owner.run_trial(trial, programme, artifact, entry, programme_pins, artifact_pin, secret=secret)
        # Never continue to another control or trial after uncertain containment.
        custody.need(result["cleanup"]["absent"] and not result["cleanup"]["errors"], "complete previous episode containment")
        self.rows.append({"episode": index, "name": result["name"], "complete": result["complete"],
                          "decision_count": len(trial), "result": str(root / "TRIAL_RESULT.json")})
        return result, predictions, root


def run_complete_participant(decisions, references, programme, programme_pins, family):
    """Full fixed-reference participant replay; no hidden-case subset or selection."""
    validate_decisions(decisions, expected_eligible=163135, expected_trials=4884)
    folds = {(x["subject_private"], x["held_session_private"]): x for x in references["artifact_manifest_private"]}
    if len(folds) != 80 or set(folds) != GROUPS:
        raise ContractError("complete participant fold-to-training-artifact map")
    trials = group_complete_trials(decisions)
    if len(trials) != 4884:
        raise ContractError("all4884 fresh participant episodes required")
    predictions = []; ledger = []
    for trial in trials:
        first = trial[0]; key = (first.subject, first.session)
        # Only this fold's training-selected frozen model enters this container.
        model = folds[key]["artifacts"]["family_train_selected"]
        result, values, directory = family.run(trial, programme, Path(model["path"]), "participant_entry.py", programme_pins, model)
        if not result["complete"]:
            raise ContractError("whole participant incomplete; no successful-trial score")
        predictions.extend((d.source_row, p) for d, p in values)
        ledger.append({"trial_private": [first.subject, first.session, first.trial],
                       "model_sha256": model["sha256"], "episode": str(directory)})
    if len(predictions) != 163135 or len(ledger) != 4884:
        raise ContractError("complete participant commitments")
    score = score_complete(decisions, predictions)
    comparison = paired_comparison(score, references["scores"]["family_train_selected"])
    return {"schema": "hybrid-complete-isolated-reference-participant-v1", "score": score,
            "against_same_host_reference": comparison, "whole_trial_artifact_mapping_private": ledger,
            "participant_type": "fixed reference replay; no LLM or frontier claim", "count_delta": 0}


def recover_operation(plan, source, output, capture, deadline, controller_closed):
    """Independent post-worker recovery using the donor lifecycle and owner.

    Worker-group closure must precede this call. An unresolved create journal is
    never settled by a merely empty namespace observation.
    """
    root = capture / "episode-recovery"; root.mkdir(mode=0o700)
    errors = []; journal_rows = []; owners = {}; seen_indices = set()
    ep_root = output / "episodes"
    try:
        paths = sorted(ep_root.iterdir()) if ep_root.exists() else []
        custody.need(len(paths) <= plan["maximum_episodes"], "complete finite owned episode directory set")
        for directory in paths:
            custody.ordinary_path(directory)
            custody.need(directory.is_dir() and re.fullmatch(r"episode-[0-9]{5}", directory.name), "owned episode directory")
            index = int(directory.name.removeprefix("episode-")); custody.need(index < plan["maximum_episodes"] and index not in seen_indices, "owned episode index")
            seen_indices.add(index); token = plan["operation_token"] + "-e%05d" % index
            one = lifecycle.inspect_journals(custody, directory, token, 1, plan["image"], plan["docker_prefix"])
            journal_rows.append({"episode": index, "all_dispatch_completions_known": one["all_dispatch_completions_known"],
                                 "errors": one["errors"], "rows": one["rows"]})
            recovery_dir = root / directory.name; recovery_dir.mkdir(mode=0o700)
            owner = Owner(custody, closer, recovery_dir, source, plan, plan["source_lock_sha256"], deadline, [], token,
                          lifecycle=lifecycle, cli_group_mode="separate")
            owner.creations = {r["name"]: r for r in one["rows"]}; owners[token] = owner
    except BaseException as exc:
        errors.append({"stage": "complete_journals", "type": type(exc).__name__, "reason": str(exc)[:1024]})
    probe_dir = root / "namespace"; probe_dir.mkdir(mode=0o700)
    probe = Owner(custody, closer, probe_dir, source, plan, plan["source_lock_sha256"], deadline, [], plan["operation_token"],
                  lifecycle=lifecycle, cli_group_mode="separate")
    absent = False
    try:
        _, raw, _, _ = probe.call(["ps", "--all", "--quiet", "--no-trunc", "--filter", "label=hybrid.operation=" + plan["operation_token"]], cleanup=True)
        ids = raw.decode().splitlines(); custody.need(len(ids) <= 1, "one live owned episode maximum")
        for cid in ids:
            info = probe.inspect(cid, cleanup=True); token = info["owner"]
            custody.need(token in owners and info["name"] == "/" + token + "-00", "exact journaled owned recovery")
            owner = owners[token]; owner.owned(info, token + "-00", cid)
            clean = owner.cleanup(token + "-00", cid); owner.write("OUTER_CLEANUP.json", clean)
            custody.need(clean["observed_absent_at_probe"] and not clean["errors"], "outer owned episode removal")
    except BaseException as exc:
        errors.append({"stage": "native_recovery", "type": type(exc).__name__, "reason": str(exc)[:1024]})
    try:
        _, raw, _, _ = probe.call(["ps", "--all", "--quiet", "--no-trunc", "--filter", "label=hybrid.operation=" + plan["operation_token"]], cleanup=True)
        custody.need(raw == b"", "complete owned namespace final absence"); absent = True
    except BaseException as exc:
        errors.append({"stage": "independent_final_probe", "type": type(exc).__name__, "reason": str(exc)[:1024]})
    all_owners = [probe, *owners.values()]
    cli_closed = all(len(o.cli_closures) == o.calls and all(x["closure"] and x["closure"]["reaped"] and
        x["closure"]["process_group_absent"] and not x["closure"]["errors"] for x in o.cli_closures) for o in all_owners)
    settled = not errors and all(x["all_dispatch_completions_known"] for x in journal_rows)
    result = {"schema": "hybrid-participant-independent-outer-recovery-v1", "episode_journals": journal_rows,
              "namespace_absent_at_final_probe": absent, "all_create_completions_known": settled,
              "all_recovery_cli_groups_closed": cli_closed, "errors": errors,
              "controller_group_closed": controller_closed,
              "complete": absent and settled and cli_closed and controller_closed,
              "quarantine_required": not settled or not controller_closed}
    emit(capture / "EPISODE_RECOVERY.json", result, 16 * 1024**2)
    return result
