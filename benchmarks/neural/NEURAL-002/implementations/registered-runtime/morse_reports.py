"""Trusted, private paired reporting and canonical-value reference adapter.

This module never goes into a candidate mount. Its artifacts contain protected
targets, cross-fold predictions and execution metadata. Hashes bind selected
bytes; they do not establish authentic intake, competence or native containment.
All scientific qualification remains false in this source construction.
"""
from dataclasses import dataclass
import hashlib
import json
import math

from contract import PEOPLE, CELLS, require
from morse_selection import (MODES, REFERENCE_NAMES, REPRESENTATION,
                             canonical_bytes, digest, read_member, sha)
from scorer import _targets, score, paired_interval

HOLD_IDS = (
    "authentic_exact_source_intake", "all32_identity_and_complete_class_coverage",
    "raw_marker_and_channel_schema", "known_bad_channel_policy",
    "source_target_privacy_and_contamination", "matched_resource_budget",
    "native_reference_and_null_controls", "independent_scoring_replication",
    "qualified_process_isolation", "scientific_interpretation_review",
    "prefix_identifiability_and_order_controls", "behavioral_diagnostics",
    "historical_software_terms",
)


def _json(body):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def finite_float(text):
        result = float(text)
        require(math.isfinite(result), "finite JSON number required")
        return result
    def reject(text):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=reject)


@dataclass(frozen=True)
class Artifact:
    """Immutable trusted byte snapshot, including its selected pin and binding."""
    body: bytes
    pin_json: bytes
    binding_json: bytes

    @property
    def pin(self):
        return _json(self.pin_json)

    @property
    def binding(self):
        return _json(self.binding_json)


def _snapshot(body, pin, binding):
    require(type(body) is bytes, "immutable artifact bytes required")
    require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "artifact pin schema")
    require(type(pin["bytes"]) is int and pin["bytes"] == len(body), "artifact extent differs")
    require(hashlib.sha256(body).hexdigest() == sha(pin["sha256"]), "artifact bytes differ")
    require(type(binding) is dict, "artifact binding required")
    return Artifact(body, canonical_bytes(pin), canonical_bytes(binding))


def read_artifact(root, pin, binding, *, max_bytes):
    """Capture a bounded ordinary host file; never follow a worker-selected path."""
    return _snapshot(read_member(root, pin, max_bytes), pin, binding)


def _validate_artifact(artifact):
    require(type(artifact) is Artifact, "captured Artifact required")
    return _snapshot(artifact.body, artifact.pin, artifact.binding)


def _spec(plan):
    require(type(plan) is dict and type(plan.get("spec")) is dict, "compiled paired plan required")
    spec = plan["spec"]
    require(plan.get("sha256") == digest(spec), "compiled plan mutated")
    require(spec.get("policy") == "P0-training-only-before-query" and
            spec.get("representation") == REPRESENTATION, "selected numeric/P0 policy")
    require(spec.get("people") == list(PEOPLE) and spec.get("cells") == list(CELLS)
            and spec.get("modes") == list(MODES), "full paired cohort required")
    require(set(spec.get("reference_selection", {})) == set(REFERENCE_NAMES), "all five references selected")
    holds = spec.get("scientific_holds")
    require(type(holds) is list and len(holds) == 13 and
            {h["id"] for h in holds} == set(HOLD_IDS), "all13 scientific holds required")
    return spec


def target_binding(plan):
    spec = _spec(plan)
    return {"schema": "morse-private-targets-v1", "plan_sha256": plan["sha256"],
            "source_receipt_sha256": sha(spec["source_receipt_sha256"]),
            "canonical_sha256": sha(spec["canonical_sha256"])}


def arm_binding(plan, targets_sha256, primary_windows_sha256, arm, *,
                input_windows_sha256, provenance_sha256):
    spec = _spec(plan)
    require(arm in MODES + REFERENCE_NAMES, "unknown report arm")
    return {"schema": "morse-private-predictions-v1", "arm": arm,
            "plan_sha256": plan["sha256"],
            "source_receipt_sha256": sha(spec["source_receipt_sha256"]),
            "canonical_sha256": sha(spec["canonical_sha256"]),
            "targets_sha256": sha(targets_sha256),
            "primary_windows_sha256": sha(primary_windows_sha256),
            "input_windows_sha256": sha(input_windows_sha256),
            "representation": REPRESENTATION, "policy": spec["policy"],
            "provenance_sha256": sha(provenance_sha256)}


def _reference_bindings(spec, bindings, primary_windows_sha256):
    require(type(bindings) is dict and set(bindings) == set(REFERENCE_NAMES), "five exact reference bindings")
    for arm, binding in bindings.items():
        require(type(binding) is dict and set(binding) == {"input_windows_sha256", "provenance_sha256"},
                "reference input/provenance binding schema")
        for value in binding.values():
            sha(value)
        require(spec["reference_selection"][arm] == digest(binding), "reference differs from frozen selection")
        if arm != "premarker":
            require(binding["input_windows_sha256"] == primary_windows_sha256,
                    "non-premarker reference must share canonical candidate values")


def _execution(plan, artifact, predictions, targets, primary_windows_sha256):
    _validate_artifact(artifact)
    require(artifact.binding == {"schema": "morse-private-execution-v1", "plan_sha256": plan["sha256"],
            "source_receipt_sha256": plan["spec"]["source_receipt_sha256"],
            "canonical_sha256": plan["spec"]["canonical_sha256"]},
            "execution capture plan binding")
    evidence = _json(artifact.body)
    require(type(evidence) is dict and evidence.get("schema") == "morse-paired-execution-v1"
            and evidence.get("plan_sha256") == plan["sha256"], "execution identity")
    require(evidence.get("source_receipt_sha256") == plan["spec"]["source_receipt_sha256"]
            and evidence.get("canonical_sha256") == plan["spec"]["canonical_sha256"]
            and evidence.get("primary_windows_sha256") == primary_windows_sha256,
            "execution source/canonical/value binding")
    require(evidence.get("complete") is True and evidence.get("logical_contexts") == 64
            and evidence.get("stage_launches") == 128 and evidence.get("actual_stage_launches") == 128,
            "complete64-context/128-stage execution required")
    require(type(evidence.get("engineering_only")) is bool and
            evidence["engineering_only"] == plan["spec"]["engineering_only"], "engineering path disclosure differs")
    contexts = evidence.get("contexts")
    require(type(contexts) is list and len(contexts) == 64, "all64 execution contexts required")
    people = {row["id"]: row["participant"] for row in targets}
    by_context = {(mode, person): [] for mode in MODES for person in PEOPLE}
    for mode in MODES:
        for row in predictions[mode]:
            by_context[mode, people[row["id"]]].append(row)
    seen = set()
    for row in contexts:
        require(type(row) is dict, "execution context object")
        key = (row.get("mode"), row.get("participant"))
        require(key in by_context and key not in seen, "duplicate/unknown execution context")
        seen.add(key)
        context_id = hashlib.sha256((plan["sha256"] + key[1] + key[0]).encode()).hexdigest()[:32]
        require(row.get("context_id") == context_id, "deterministic context identity differs")
        for phase in ("train", "query"):
            stage = row.get(phase)
            require(type(stage) is dict and stage.get("success") is True
                    and stage.get("terminal_observed") is True and stage.get("cleanup_complete") is True
                    and stage.get("broker_thread_terminal") is True
                    and type(stage.get("container_exit_code")) is int and stage["container_exit_code"] == 0
                    and type(stage.get("attach_exit_code")) is int and stage["attach_exit_code"] == 0,
                    "unclosed or failed stage cannot support complete report")
            require(stage.get("context_id") == context_id and stage.get("mode") == key[0]
                    and stage.get("phase") == phase, "stage context/mode/phase differs")
        sha(row["fit_seal_sha256"])
        rows = sorted(by_context[key], key=lambda r: r["id"])
        require(len(rows) == 312 and row.get("predictions_sha256") == digest(rows),
                "captured predictions differ from the executed context")
    require(seen == set(by_context), "missing execution context")
    return artifact.pin


def compose_report(plan, targets, arms, *, primary_windows_sha256,
                   reference_bindings, execution_receipt=None,
                   bootstrap_seed=2002, repetitions=10000):
    """Recompute every metric from authenticated private prediction bytes.

    Missing arms/receipt produce an explicit incomplete diagnostic report, never
    a reduced-cohort or reference-free primary claim. Malformed present artifacts
    fail closed. No score or receipt is returned to candidate workers.
    """
    spec = _spec(plan)
    sha(primary_windows_sha256)
    _reference_bindings(spec, reference_bindings, primary_windows_sha256)
    _validate_artifact(targets)
    require(targets.binding == target_binding(plan), "target source/plan binding differs")
    target_rows = _json(targets.body)
    _targets(target_rows)
    require(type(arms) is dict and set(arms) <= set(MODES + REFERENCE_NAMES), "unknown prediction arm")
    metrics, parsed, artifacts = {}, {}, {}
    for arm, artifact in arms.items():
        _validate_artifact(artifact)
        binding = ({"input_windows_sha256": primary_windows_sha256,
                    "provenance_sha256": digest(spec["capsules"][arm])}
                   if arm in MODES else reference_bindings[arm])
        expected = arm_binding(plan, targets.pin["sha256"], primary_windows_sha256, arm, **binding)
        require(artifact.binding == expected, "prediction plan/target/window/provenance binding differs")
        predictions = _json(artifact.body)
        metrics[arm] = score(target_rows, predictions)
        parsed[arm] = predictions
        artifacts[arm] = {"pin": artifact.pin, "binding": artifact.binding}
    missing = sorted(set(MODES + REFERENCE_NAMES) - set(arms))
    execution_pin = None
    if execution_receipt is not None:
        require(all(mode in parsed for mode in MODES), "execution receipt needs both candidate captures")
        execution_pin = _execution(plan, execution_receipt, parsed, target_rows, primary_windows_sha256)
    complete = not missing and execution_pin is not None
    paired = {}
    if complete:
        for mode in MODES:
            for reference in REFERENCE_NAMES:
                paired[mode + " minus " + reference] = paired_interval(
                    metrics[mode]["participant_scores"], metrics[reference]["participant_scores"],
                    seed=bootstrap_seed, repetitions=repetitions)
        paired["case_adaptive minus frozen_program"] = paired_interval(
            metrics["case_adaptive"]["participant_scores"], metrics["frozen_program"]["participant_scores"],
            seed=bootstrap_seed, repetitions=repetitions)
    return {"schema": "morse-private-paired-report-v1", "plan_sha256": plan["sha256"],
            "status": "complete-diagnostic-unqualified" if complete else "incomplete-diagnostic",
            "missing_arms": missing, "missing_execution_receipt": execution_pin is None,
            "report_composition_complete": complete, "headline_results": None,
            "scientific_qualification": False, "submission_ready": False,
            "engineering_only": spec["engineering_only"], "benchmark_count": 1,
            "logical_contexts": 64, "stage_launches": 128,
            "nominal_source_counts_only": True,
            "endpoint": "early software-marker-window stimulus-ID information in an unseen participant",
            "targets": {"pin": targets.pin, "binding": targets.binding},
            "primary_windows_sha256": primary_windows_sha256,
            "artifacts": artifacts, "execution_receipt": execution_pin,
            "diagnostic_metrics": metrics, "paired_participant_gains": paired,
            "scientific_holds": [{"id": name, "qualified": False} for name in HOLD_IDS],
            "limitations": [
                "Native containment, physical quotas, authenticated intake and numerical parity remain unqualified.",
                "Source bindings and terminal receipts do not prove absence of covert query fitting; source/trace review remains required.",
                "All five reference bindings are required, but their hashes do not establish matched nuisance joins or EEG competence.",
                "The incumbent ERP shrinkage reference is not automatically a validated competent EEG reference.",
                "No full-character, comprehension, acoustic-onset or pre-response interpretation is authorized.",
                "If all relevant delivered prefixes are identical, primary scientific use must be reconsidered or treated as a negative control.",
            ]}


def run_bound_reference(export_receipt, private_inverse, arm, *, seed=2002,
                        nuisance=None, premarker_receipt=None, premarker_inverse=None):
    """Future authorized reference path: always decode exact serialized inputs.

    This function is intentionally not invoked by source engineering controls.
    It performs full reference computation when called. A real run requires a
    separately authorized intake/execution decision; this module grants none.
    """
    from morse_views import reconstruct_reference_records
    from reference_pipeline import run_reference
    require(arm in REFERENCE_NAMES, "required reference arm only")
    records = reconstruct_reference_records(export_receipt, private_inverse)
    primary = digest(export_receipt["canonical_window_pins"])
    input_pins = primary
    if arm == "premarker":
        require(premarker_receipt is not None and premarker_inverse is not None,
                "separate fixed premarker serialization required")
        before = reconstruct_reference_records(premarker_receipt, premarker_inverse)
        def metadata(rows):
            return sorted(({k: r[k] for k in ("id", "participant", "cell", "label")} for r in rows),
                          key=lambda r: r["id"])
        require(metadata(records) == metadata(before), "premarker source-target identity mismatch")
        input_pins = digest(premarker_receipt["canonical_window_pins"])
        records = {"window": "sample-302 through sample-2 inclusive", "records": before}
    else:
        require(premarker_receipt is None and premarker_inverse is None, "unused premarker input")
    core_arm = "erp_shrinkage" if arm == "validated_competent_EEG_reference" else arm
    result = run_reference(records, core_arm, seed=seed, nuisance=nuisance)
    return {"requested_arm": arm, "actual_implementation": core_arm,
            "representation": REPRESENTATION, "primary_windows_sha256": primary,
            "input_windows_sha256": input_pins, "predictions": result["predictions"],
            "fits": result["fits"], "competence_validated": False,
            "matched_nuisance_join_validated_by_this_adapter": False,
            "scientific_qualification": False}
