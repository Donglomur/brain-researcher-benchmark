"""Concrete local operator phase launcher and external natural-exit observation.

Native input preparation, reference fitting and the protected grader run only in
an independently qualified operator namespace. Candidate tools/query inference
use the separately qualified Docker adapters. This module does not assert that
the local machine is qualified, or turn its own output into an approval.
"""
from pathlib import Path
import json
import os
from cohort import require
from io_support import admit_full_run, canonical_bytes, object_digest, authenticate_file
from storage import write_json_fresh
from phase_manifest import metadata, source_closure, budget_snapshot
from adapters.process import ProcessObserver


def _receipt_write(path, record, budget):
    # Include this receipt's own logical write in its exact cumulative snapshot.
    size = 0
    for _ in range(16):
        after = budget_snapshot(budget)
        after["used"]["artifact_write"] += size
        value = {**record, "budget_after": after}
        n = len(canonical_bytes(value))
        if n == size:
            pin = write_json_fresh(path, value, budget)
            require(budget_snapshot(budget) == after, "Receipt includes its own charge")
            budget.check_clock()
            return pin
        size = n
    raise ValueError("Receipt-size accounting failed to converge")


def launch_phase(phase, invocation_pin, permit_pin, approvals_pin, launcher_config_pin, budget):
    """Operator-owned API; every operand is an exact independently approved pin.

    The child inherits the pre-launch ledger. Parent reserves its complete
    incremental allowance BEFORE Popen and retains it on all failures. Actual
    child use is evidence, never refunded or charged twice. Host metadata,
    staging and observer costs are additional charges to the same parent ledger.
    """
    before = budget_snapshot(budget)
    permit = metadata(permit_pin, budget)
    approvals = metadata(approvals_pin, budget)
    require(approvals.get("schema") == "neural053_phase_approval_registry_v2" and
            type(approvals.get("approved_receipts")) is list, "Protected operator phase registry")
    # approvals_pin is a protected operator-channel trust anchor, like the
    # method registry pin. It cannot be embedded in the receipt it approves
    # without a circular content hash; candidate namespaces never supply it.
    approved = frozenset(approvals["approved_receipts"])
    bindings = permit["bindings"]
    admit_full_run(permit, bindings, approved, phase)
    require(bindings.get("budget_before_sha256") == object_digest(before) and bindings.get("invocation") == invocation_pin and
            bindings.get("phase_launcher_config") == launcher_config_pin,
            "Exact actual launch operands and original ledger")
    config = metadata(launcher_config_pin, budget)
    require(set(config) == {"schema", "python", "working_directory", "control_directory", "increment_caps", "seconds", "cleanup_seconds", "stream_cap_bytes"} and
            config["schema"] == "neural053_phase_launcher_v2", "Closed concrete local launch configuration")
    invocation = metadata(invocation_pin, budget)
    require(object_digest(invocation["runtime_sources"]) == bindings.get("runtime_source_manifest_sha256"), "Reviewed current runtime list")
    source_closure(invocation["source_root"], invocation["runtime_sources"], budget)
    authenticate_file(config["python"]["path"], config["python"], budget)
    control = Path(config["control_directory"])
    require(control.is_absolute() and control.parent.is_dir() and not control.parent.is_symlink() and not control.exists(), "Fresh private operator control directory")
    control.mkdir(mode=0o700)
    caps = config["increment_caps"]
    require(set(caps) == set(before["limits"]) and all(type(v) is int and v >= 0 for v in caps.values()), "Every child counter has a finite reserved cap")
    envelope = {"schema": "neural053_phase_child_envelope_v2", "phase": phase, "invocation": invocation_pin,
                "permit": permit, "approved_receipts": sorted(approved), "budget_before": before, "increment_caps": caps}
    envelope_pin = write_json_fresh(control / "child_envelope.json", envelope, budget)
    for name, amount in caps.items(): budget.charge(name, amount)
    script = str(Path(invocation["source_root"]) / "phase_worker.py")
    argv = [config["python"]["path"], "-I", "-B", script, "--envelope", envelope_pin["path"],
            "--bytes", str(envelope_pin["bytes"]), "--sha256", envelope_pin["sha256"]]
    # No inherited PYTHONPATH/provider credentials/context variables. A future
    # provider credential must be deliberately supplied through its env-name
    # contract by the protected operator; only that named secret is inherited.
    env = {"PATH": os.defpath, "LANG": "C.UTF-8"}
    if phase == "author_candidates":
        adapter = metadata(invocation["artifacts"]["adapter_config"], budget)
        name = adapter["provider"]["api_key_env"]
        require(type(name) is str and name and name in os.environ, "Explicit configured provider credential environment")
        env[name] = os.environ[name]
    try:
        observed = ProcessObserver().run(argv, cwd=config["working_directory"], env=env, budget=budget,
            seconds=config["seconds"], cleanup_seconds=config["cleanup_seconds"], stream_cap=config["stream_cap_bytes"])
        result = json.loads(observed["stdout"])
        require(result.get("schema") == "neural053_phase_child_return_v2" and result.get("phase") == phase, "Exact observed phase output framing")
        require(set(result["increment_used"]) == set(caps) and all(type(v) is int and 0 <= v <= caps[k] for k,v in result["increment_used"].items()), "Strict bounded child debit evidence")
        child_after = result["budget_after"]
        require(all(child_after[k] == before[k] for k in ("origin_monotonic", "deadline_monotonic", "limits")) and
                child_after["used"] == {k:before["used"][k] + result["increment_used"][k] for k in caps}, "No child reset or unreported charge")
        output = metadata(result["output_manifest"], budget)
        require(output["schema"] == "neural053_phase_outputs_v2" and output["phase"] == phase and
                output["invocation_sha256"] == invocation_pin["sha256"] and output["runtime_source_sha256"] == bindings["runtime_source_manifest_sha256"], "Observed phase output exact source/operand join")
        source_closure(invocation["source_root"], invocation["runtime_sources"], budget)
        authenticate_file(config["python"]["path"], config["python"], budget)
        observation = observed["observation"]
        receipt = {"schema": "neural053_phase_observed_completion_v2", "phase": phase,
                   "invocation_sha256": invocation_pin["sha256"], "runtime_source_sha256": bindings["runtime_source_manifest_sha256"],
                   "output_manifest": result["output_manifest"], "natural_exit_code": observation["natural_exit_code"],
                   "source_state_unchanged": True, "process_group_absent": observation["process_group_absent"], "streams_closed": observation["streams_closed"],
                   "observer": observation, "child_increment_reserved": caps, "child_increment_used": result["increment_used"],
                   "unused_reservation_refunded": False, "approval": "independent_operator_review_still_required",
                   "scientific_qualification_conferred": False}
        return _receipt_write(control / "observed_completion.json", receipt, budget)
    except BaseException as exc:
        # Failed child reservation is retained in the in-memory parent ledger;
        # serialize when remaining write budget permits, never pretend success.
        failure = {"schema": "neural053_phase_failed_attempt_v2", "phase": phase, "error_type": type(exc).__name__,
                   "budget_after": budget_snapshot(budget), "child_increment_reserved": caps, "observation": getattr(exc, "evidence", {}),
                   "scientific_qualification_conferred": False}
        data = canonical_bytes(failure)
        if budget.used["artifact_write"] + len(data) <= budget.limits["artifact_write"]:
            write_json_fresh(control / "failed_attempt.json", failure, budget)
        raise
