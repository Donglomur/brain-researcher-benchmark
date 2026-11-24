"""Protected paired evaluation after complete, closed spinal delivery.

The reference argument belongs to the trusted operator. This handoff preserves
the original evaluator; it supplies no missing trained reference or paper claim.
Closed operator artifacts are trusted custody, not a hostile-host boundary.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
CONDITION = "current_source_noise7_eligible_v1"
BANK_SHA = "33085162e9ba9ea64ef9862f681ec6f43c7065256b89430c313e5ac0dab5c726"
IMAGE = "sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156"
ARMS = ("paper_data", "paper_data_author_code")


def need(value, message):
    if not value:
        raise ValueError(message)


def absent(path):
    return not path.exists() and not path.is_symlink()


def _load_source(expected_sha):
    spec = importlib.util.spec_from_file_location("_spinal_completion_grade_source", HERE / "source.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_source(expected_sha)


def _read(loaded, path, expected=None, limit=200_000):
    raw = loaded.contract.capture(path, limit)
    actual = loaded.contract.pin(raw)
    if expected is not None:
        need(actual == expected, "exact immutable handoff artifact")
    value = loaded.collector.strict_json(raw)
    need(type(value) is dict, "handoff JSON object required")
    return value, actual


def _pin(value):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and value["bytes"] > 0
         and type(value["sha256"]) is str
         and re.fullmatch("[0-9a-f]{64}", value["sha256"]), "bounded exact byte/hash pin")
    return value


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _closed_attempt(loaded, root, host_exit_sha256, source_sha256):
    """Only source and saved operator/public metadata; no numerical operands."""
    c = loaded.contract
    need(type(host_exit_sha256) is str and re.fullmatch("[0-9a-f]{64}", host_exit_sha256),
         "operator-frozen host-exit identity")
    host, host_pin = _read(loaded, root / "HOST_EXIT.json")
    need(host_pin["sha256"] == host_exit_sha256, "frozen complete host receipt")
    need(host["schema"] == "spinal_current_completion_host_exit_v1"
         and host["completion_source"] == loaded.source_pin
         and host["completion_source"]["sha256"] == source_sha256
         and host["delivery_source"] == loaded.delivery_source_pin
         and host["campaign_relative_path"] == "campaign"
         and host["folds"] == 88 and host["eligible_recordings_per_arm"] == 116
         and host["engineering_control"] is True
         and host["scientific_scoring"] is False, "selected complete engineering host")
    observation = host["worker_observation"]
    need(observation.get("natural_exit") is True and observation.get("process_reaped") is True
         and observation.get("streams_closed") is True and observation.get("exit_code") == 0
         and observation.get("error_type") is None and observation.get("kill_sent") is False
         and observation.get("owned_host_group_absent") is True
         and not observation.get("cleanup_errors") and not observation.get("output_overflow"),
         "natural zero closed worker")
    plan, _ = _read(loaded, root / "PLAN.json", _pin(host["plan"]))
    loaded.profile.validate(plan)
    need(plan["schema"] == "spinal_current_completion_plan_v1"
         and plan["scope"] == "fixed_one_hz_nonlearning_engineering_pair"
         and plan["image"] == IMAGE
         and plan["bank_manifest_sha256"] == BANK_SHA and plan["output_unit"] == "hz"
         and plan["purpose"] in ("reproduction", "improvement"), "fixed bank, purpose and rate unit")
    streams = {}
    for name in ("stdout", "stderr"):
        body = c.capture(root / ("worker." + name), 65536)
        need(c.pin(body) == host[name] and len(body) == observation[name + "_bytes"],
             "actual bounded worker streams match host observation")
        streams[name] = body
    need(loaded.collector.strict_json(streams["stdout"]) == {
        "complete": True, "completion_source": loaded.source_pin,
        "delivery_source": loaded.delivery_source_pin, "plan": host["plan"],
        "folds": 88, "scientific_scoring": False}, "exact worker completion response")
    intent, _ = _read(loaded, root / "INTENT.json")
    need(intent["schema"] == "spinal_current_completion_intent_v1"
         and intent["completion_source"] == loaded.source_pin
         and intent["delivery_source"] == loaded.delivery_source_pin
         and intent["plan"] == host["plan"] and intent["all_88_contexts_required"] is True
         and intent["automatic_retry"] is False and intent["engineering_control"] is True
         and intent["scientific_scoring"] is False, "original selected whole-campaign intent")
    started, deadline = intent["started_monotonic"], intent["deadline_monotonic"]
    host_elapsed = host["elapsed_seconds"]
    need(_finite(started) and _finite(deadline) and 0 <= started < deadline
         and deadline == started + plan["campaign_seconds"]
         and _finite(host_elapsed) and 0 <= host_elapsed < plan["campaign_seconds"],
         "finite original whole clock and terminal elapsed")
    campaign = root / "campaign"
    need(absent(root / "FAILED.json") and absent(campaign / "FAILED.json"),
         "failure cannot coexist with successful paired handoff")
    done, _ = _read(loaded, campaign / "WORKER_COMPLETE.json", _pin(host["worker_complete"]))
    need(done["schema"] == "spinal_current_transport_complete_v1"
         and done["condition_id"] == CONDITION and done["bank_manifest_sha256"] == BANK_SHA
         and done["source_manifest"] == loaded.delivery_source_pin
         and done["source_recording_census"] == 132 and done["eligible_recordings"] == 116
         and done["noise_exclusions"] == 16 and done["required_neurons"] == 44
         and done["same_data_across_arms"] is True
         and done["scientific_scoring_performed"] is False,
         "complete original current-condition campaign")
    runtime, runtime_pin = _read(loaded, campaign / "RUNTIME.json")
    remaining = runtime["aggregate_observed_remaining_seconds"]
    old = loaded.transport.runtime_selection(plan["candidate_seconds"], plan["memory_bytes"],
                                              plan["other_reserve_bytes"])
    need(runtime["profile"] == "spinal_full_pair_fixed_control_aggregate_v1"
         and runtime["completion_source"] == loaded.source_pin and runtime["plan"] == host["plan"]
         and runtime["selected_campaign_seconds"] == plan["campaign_seconds"]
         and runtime["all_88_contexts_required"] is True and runtime["partial_success_allowed"] is False
         and runtime["aggregate_deadline_monotonic"] == deadline
         and _finite(remaining) and plan["candidate_seconds"] + 540 < remaining <= plan["campaign_seconds"]
         and plan["campaign_seconds"] - remaining <= host_elapsed
         and runtime["outer_wall_seconds"] == remaining
         and runtime["worker_wall_seconds"] == remaining - 60
         and runtime["original_sum_of_all_fold_maxima"] == {
             k: old[k] for k in ("worker_wall_seconds", "outer_wall_seconds")},
         "exact selected aggregate profile, source, plan and unchanged clock")
    need(runtime["candidate_seconds"] == plan["candidate_seconds"]
         and runtime["memory_bytes"] == plan["memory_bytes"] and runtime["cpu"] == 1
         and runtime["folds_per_arm"] == 44 and runtime["arms"] == list(ARMS)
         and runtime["per_fold_wall_seconds"] == plan["candidate_seconds"] + 420
         and runtime["automatic_retry"] is False, "unchanged complete per-fold profile")
    need(done["selected_fold_seconds"] == 88 * runtime["per_fold_wall_seconds"],
         "all 88 selected fold allowances retained")
    elapsed = done["elapsed_seconds"]
    need(type(elapsed) in (int, float) and math.isfinite(elapsed)
         and 0 <= elapsed < runtime["worker_wall_seconds"], "complete campaign within selected clock")
    pair, _ = _read(loaded, campaign / "PAIR_SEAL.json")
    contents = {}
    controls = [row for row in loaded.manifest["files"] if row["path"] == "control/program.py"]
    need(len(controls) == 1, "one source-frozen fixed control")
    control_pin = {k: controls[0][k] for k in ("bytes", "sha256")}
    for arm in ARMS:
        seal = pair["arms"][arm]["seal"]
        need(seal["files"] == [{"path": "program.py", **control_pin}],
             "same exact source-frozen fixed control in both arms")
        pins = {row["path"]: {k: row[k] for k in ("bytes", "sha256")} for row in seal["files"]}
        pins["config.json"] = seal["configuration_pin"]
        directory = campaign / "programs" / arm
        need(loaded.transport.tree_pins(directory, file_limit=129, byte_limit=c.PROGRAM_LIMIT + 4096) == pins,
             "unchanged complete sealed program snapshot")
        contents[arm] = {name: c.capture(directory / name, pin["bytes"]) for name, pin in pins.items()}
        need(seal["configuration"] == c.configuration(arm, plan["purpose"], plan["output_unit"]),
             "matched arm/purpose/unit configuration")
    c.check_pair(pair, contents)
    need(done["pair_pin"] == pair["pair_pin"], "same pre-label paired freeze")
    roster, _ = loaded.current.read_json(loaded.current.HERE / "CASE_ROSTER.json",
                                         expected_sha=loaded.current.ROSTER_SHA256)
    need(roster["bank_manifest_sha256"] == BANK_SHA and len(roster["expected_neurons"]) == 44,
         "source-bound complete 44-neuron roster")
    census, _ = _read(loaded, campaign / "OPERATOR_CENSUS.json")
    need(census == roster, "unchanged source cohort and recording census")
    need(set(done["arms"]) == set(host["candidate_manifests"]) == set(ARMS), "both complete access arms")
    all_contexts = set()
    folds = {}
    for arm in ARMS:
        result = done["arms"][arm]
        need(result["folds"] == 44 and result["eligible_recordings"] == 116
             and result["program_seal"] == pair["arms"][arm]["seal_pin"]
             and result["prediction_manifest"] == host["candidate_manifests"][arm],
             "complete arm manifest bound by host and original worker")
        for held in roster["expected_neurons"]:
            folder = campaign / arm / "folds" / held
            proof, _ = _read(loaded, folder / "FOLD_PROOF.json")
            lifecycle, _ = _read(loaded, folder / "LIFECYCLE.json", _pin(proof["lifecycle"]))
            loaded.collector.closed(lifecycle)
            namespace = lifecycle["namespace"]
            need(type(namespace) is str and namespace and namespace not in all_contexts,
                 "88 distinct closed participant contexts")
            all_contexts.add(namespace)
            need(lifecycle["schema"] == "cascade44_fold_lifecycle_v1"
                 and lifecycle["program_seal"] == pair["arms"][arm]["seal_pin"]
                 and lifecycle["source_manifest"] == loaded.delivery_source_pin
                 and lifecycle["runtime_contract"] == runtime_pin
                 and lifecycle["image"] == IMAGE
                 and lifecycle["candidate_seconds"] == plan["candidate_seconds"]
                 and lifecycle["memory_bytes"] == plan["memory_bytes"]
                 and lifecycle["candidate_started"] is True
                 and lifecycle["private_scoring_called"] is False,
                 "closed context joins selected source/program/runtime")
            expected_ids = [r["recording_id"] for r in roster["records"]
                            if r["neuron_id"] == held and r["status"] == "prepared"]
            excluded_ids = [r["recording_id"] for r in roster["records"] if r["neuron_id"] == held]
            need(proof["held_neuron"] == held and proof["arm"] == arm
                 and proof["program_seal"] == pair["arms"][arm]["seal_pin"]
                 and proof["query_recording_ids"] == expected_ids
                 and proof["held_all_source_records_excluded"] == excluded_ids
                 and proof["fresh_context_namespace"] == namespace
                 and proof["candidate_closed_before_capture"] is True
                 and proof["input_files"] == lifecycle["public_post_pin"],
                 "whole held neuron, original order and actual input identity")
            retired, _ = _read(loaded, folder / "RETIRED.json")
            need(retired == {"input_absent": True, "trusted_absent": True}
                 and absent(folder / "input") and absent(folder / "trusted"),
                 "prior labelled/trusted views retired before scoring")
            folds[(arm, held)] = (folder, proof, lifecycle)
    need(len(all_contexts) == 88, "both complete original 44-fold campaigns")
    return host, plan, pair, roster, folds


def _validate_public_candidates(loaded, root, host, plan, pair, roster, folds, bank):
    c = loaded.contract
    candidates = {}
    common = {}
    for arm in ARMS:
        captured = {}
        for held in roster["expected_neurons"]:
            folder, proof, lifecycle = folds[(arm, held)]
            selected = loaded.materials.select_fold(bank, held)
            manifest = loaded.materials._participant_manifest(selected, arm, plan["purpose"])
            inputs = proof["input_files"]
            need(inputs["FOLD.json"] == c.pin(c.encoded(manifest)), "exact original public fold manifest")
            binding = {
                "schema": "spinal_current_program_binding_v1", "condition_id": CONDITION,
                "held_neuron": held, "arm": arm, "purpose": plan["purpose"],
                "output_unit": plan["output_unit"], "pair_pin": pair["pair_pin"],
                "program_seal": pair["arms"][arm]["seal_pin"],
                "fold_manifest": inputs["FOLD.json"], "input_files": dict(sorted(inputs.items())),
                "query_records": manifest["query_records"],
                "training_policy": "eligible_same_cohort_except_entire_held_neuron",
                "fresh_context_required": True,
            }
            need(proof["binding"] == c.pin(c.encoded(binding)), "exact retired binding reconstructed")
            comparable = {name: value for name, value in inputs.items()
                          if name != "FOLD.json" and not name.startswith("author-code/")}
            comparable["FOLD_COMMON"] = c.pin(c.encoded({k: v for k, v in manifest.items() if k != "arm"}))
            if arm == ARMS[0]:
                common[held] = comparable
            else:
                need(comparable == common[held], "same actual paper/data bytes across both arms")
            values = loaded.collector.collect_fold(binding, lifecycle, folder / "captured", loaded.current)
            need(not set(values).intersection(captured), "one captured held prediction per original recording")
            captured.update(values)
        bundle = loaded.current.load_predictions(root / "campaign" / arm / "candidate", bank,
                     role="candidate", manifest_sha256=_pin(host["candidate_manifests"][arm])["sha256"])
        need(bundle.metadata["methods"] == {"candidate": plan["output_unit"]}, "same selected candidate unit")
        need(set(captured) == set(bundle.by_id) and len(captured) == 116, "all 116 captured candidate recordings")
        for row in bank.eligible:
            # Public candidate payloads are decoded for BOTH arms before any
            # reference payload or electrical source target is read.
            values = loaded.current._prediction_arrays(bundle, row)["candidate"]
            expected = captured[row["recording_id"]]
            need(np.isfinite(values[32:-32]).all()
                 and np.array_equal(values, expected, equal_nan=True),
                 "candidate vectors exactly match complete closed captures")
        candidates[arm] = bundle
    return candidates


def _paired_summary(rows):
    """Descriptive equal-neuron deltas; never subtract unmatched arm means."""
    values = [row["delta"] for row in rows if row["delta"] is not None]
    mean = median = None
    if values:
        scale = max(abs(value) for value in values)
        mean = math.fsum(value / scale for value in values) / len(values) * scale if scale else 0.0
        ordered = sorted(values)
        half = len(ordered) // 2
        median = (ordered[half] if len(ordered) % 2
                  else ordered[half - 1] / 2 + ordered[half] / 2)
    statuses = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    return {"expected_neurons": len(rows), "defined_neurons": len(values),
            "undefined_neurons": len(rows) - len(values), "status_counts": statuses,
            "mean": mean, "median": median}


def paired_access_summary(results, expected_neurons):
    """Join existing candidate metrics by neuron, retaining undefined operands.

    This compares the two information conditions on the adopted current bank.
    It adds no source-paper metric, uncertainty estimate or success criterion.
    """
    need(set(results) == set(ARMS) and expected_neurons, "both complete access results required")
    left, right = (results[arm] for arm in ARMS)
    for key in ("condition_id", "bank_manifest_sha256", "operator_reference_manifest_sha256", "coverage"):
        need(left[key] == right[key], "paired results require identical bank, reference and coverage")
    rows = [result["metrics"]["per_neuron"] for result in (left, right)]
    need(all(set(row) == set(expected_neurons) for row in rows), "exact original neuron pair required")
    directions = {"correlation": "higher_is_better", "normalized_l1": "lower_is_better",
                  "signed_bias": "signed_change_only_not_an_improvement_direction"}
    paired = {}
    for identity, cohort in sorted(expected_neurons.items()):
        a, b = (row[identity] for row in rows)
        need(all(a[key] == b[key] for key in ("total_bins", "scored_bins", "sampling_rate_hz")),
             "paired neuron requires identical scored support")
        values = {}
        for metric in directions:
            operands = {}
            for arm, row in zip(ARMS, (a, b)):
                candidate = row["methods"]["candidate"]
                source = candidate["correlation"] if metric == "correlation" else candidate["rate_diagnostics"]
                value = source["value" if metric == "correlation" else metric]
                status = source["status"]
                need((status == "defined" and _finite(value)) or (status != "defined" and value is None),
                     "paired metric value and definition status must agree")
                operands[arm] = {"value": value, "status": status}
            av, bv = (operands[arm]["value"] for arm in ARMS)
            delta = None
            if av is None or bv is None:
                status = ("both_undefined" if av is None and bv is None else
                          "paper_data_undefined" if av is None else "paper_data_author_code_undefined")
            else:
                delta = bv - av
                status = "defined" if math.isfinite(delta) else "unrepresentable_delta"
                if status != "defined":
                    delta = None
            values[metric] = {"operands": operands, "delta": delta, "status": status}
        paired[identity] = {"cohort": cohort, "scored_bins": a["scored_bins"], "metrics": values}
    cohorts = {}
    for cohort in sorted(set(expected_neurons.values())):
        identities = sorted(identity for identity, group in expected_neurons.items() if group == cohort)
        cohorts[cohort] = {"neuron_ids": identities, "metrics": {
            metric: _paired_summary([paired[identity]["metrics"][metric] for identity in identities])
            for metric in directions}}
    return {"difference": "paper_data_author_code_minus_paper_data",
            "aggregation": "within_neuron_delta_then_equal_neuron_separate_cohort_summary",
            "metric_directions": directions, "per_neuron": paired, "cohorts": cohorts,
            "rate_diagnostics_are_not_qualified_historical_bias_error": True,
            "uncertainty_or_superiority_rule_defined": False,
            "scientific_improvement_established": False}


def grade_pair(attempt_root, *, host_exit_sha256, source_sha256, bank_root,
               reference_root, reference_manifest_sha256, loaded=None):
    """Internal injected module seam is for generated controls, never CLI input."""
    need(type(reference_manifest_sha256) is str
         and re.fullmatch("[0-9a-f]{64}", reference_manifest_sha256),
         "independently frozen operator reference manifest is mandatory")
    loaded = _load_source(source_sha256) if loaded is None else loaded
    root = Path(attempt_root).absolute()
    host, plan, pair, roster, folds = _closed_attempt(loaded, root, host_exit_sha256, source_sha256)
    need(Path(plan["bank"]).absolute() == Path(bank_root).absolute(), "same selected operator bank path")
    # Bank loading reads only authenticated metadata. Actual source arrays are
    # first read by the unchanged evaluator after both public validations below.
    bank = loaded.current.load_bank(bank_root)
    candidates = _validate_public_candidates(loaded, root, host, plan, pair, roster, folds, bank)
    reference = loaded.current.load_predictions(reference_root, bank, role="operator_reference",
                                                manifest_sha256=reference_manifest_sha256)
    results = {arm: loaded.current.evaluate(bank, reference, candidates[arm]) for arm in ARMS}
    return {"schema": "spinal_current_paired_protected_comparison_v1", "condition_id": CONDITION,
            "host_exit_sha256": host_exit_sha256, "completion_source_sha256": source_sha256,
            "bank_manifest_sha256": BANK_SHA, "operator_reference_manifest_sha256": reference_manifest_sha256,
            "closed_contexts": 88, "validated_recording_predictions": 232,
            "both_public_candidates_validated_before_protected_arrays": True,
            "results": results,
            "paired_access_summary": paired_access_summary(results, roster["expected_neurons"]),
            "reference_qualification_established": False,
            "historical_paper_reproduction_established": False,
            "paper_improvement_or_SOTA_established": False,
            "external_outer_exit_independently_validated_by_this_grader": False,
            "full_transport_qualification_requires_separate_external_exit_zero": True,
            "operator_artifact_custody_is_trusted": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("attempt", "bank", "references", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    for field in ("host-exit-sha256", "source-sha256", "reference-manifest-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    need(absent(args.output), "exclusive fresh private comparison output")
    result = grade_pair(args.attempt, host_exit_sha256=args.host_exit_sha256,
                        source_sha256=args.source_sha256, bank_root=args.bank,
                        reference_root=args.references, reference_manifest_sha256=args.reference_manifest_sha256)
    raw = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    need(len(raw) <= 4 * 1024**2, "bounded complete paired score report")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"paired_comparison": True, "closed_contexts": 88,
                      "scientific_success_claimed": False}))


if __name__ == "__main__":
    main()
