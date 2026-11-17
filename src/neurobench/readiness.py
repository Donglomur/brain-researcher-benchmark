#!/usr/bin/env python3
"""Report explicit task acceptance separately from components and study completion.

Reads metadata only. It does not run candidates, open scientific arrays, grant
execution, or infer acceptance from the presence of three implementation pieces.
The older neurobench CLI stays byte-identical for its frozen consumers.
"""
import json
from pathlib import Path

from neurobench import ROOT, digest, read, specifications, summary, within


def pinned_json(root, descriptor):
    if set(descriptor) != {"path", "bytes", "sha256"}:
        raise ValueError("Expected an exact acceptance-evidence descriptor")
    path = within(root, descriptor["path"])
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_size != descriptor["bytes"]
            or not 0 < descriptor["bytes"] <= 128_000
            or digest(path) != descriptor["sha256"]):
        raise ValueError("Missing or changed acceptance evidence")
    return read(path)


def accepted_tasks(root=ROOT):
    _, canonical = specifications(root)
    ledger = read(root / "docs/neuroscience-benchmarks/build/implementation_status.json")
    admissions = ledger.get("bounded_task_admissions", {"schema_version": 1,
                                                       "records": {}, "accepted_ids": []})
    records = admissions["records"]
    if admissions["schema_version"] != 1 or set(records) - set(canonical):
        raise ValueError("Unknown acceptance schema or canonical task")
    accepted, ready, rows = [], [], []
    for task_id, record in sorted(records.items()):
        if record.get("root_accepted") is not True:
            continue
        decision = pinned_json(root, record["decision_evidence"])
        for key in ("candidate_id", "finite_contract_id", "decision", "scientific_scope",
                    "root_accepted", "current_dispatch", "original_full_contract_complete",
                    "research_qualified", "submission_ready"):
            if record.get(key) != decision.get(key):
                raise ValueError("Acceptance record/evidence disagreement: " + task_id + "/" + key)
        if (record["candidate_id"] != task_id
                or record["decision"] != "accept_local_bounded_executable_task"
                or decision.get("reviewer") != "root"
                or decision.get("execution_authority") is not False):
            raise ValueError("Acceptance is not an exact root decision")
        current = record["current_dispatch"]
        if current["status"] not in ("ready_under_fresh_grant", "needs_capacity_successor"):
            raise ValueError("Unknown current dispatch status")
        if (current.get("execution_authority") is not False
                or current.get("ready_to_run_unchanged") is not
                (current["status"] == "ready_under_fresh_grant")):
            raise ValueError("Dispatch readiness is not execution authority")
        accepted.append(task_id)
        if current["ready_to_run_unchanged"]:
            ready.append(task_id)
        rows.append({"id": task_id, "finite_contract_id": record["finite_contract_id"],
                     "scope": record["scientific_scope"],
                     "current_dispatch_status": current["status"],
                     "decision_evidence": record["decision_evidence"]})
    if sorted(admissions["accepted_ids"]) != accepted:
        raise ValueError("Accepted-ID inventory disagrees with explicit decisions")
    return {"accepted_local_bounded_tasks": len(accepted),
            "accepted_local_bounded_task_ids": accepted,
            "currently_dispatch_ready_bounded_tasks": len(ready),
            "currently_dispatch_ready_bounded_task_ids": ready,
            "task_acceptance_basis": "Pinned root decisions for finite scientific scopes; "
                                     "separate from original full studies and release qualification.",
            "current_dispatch_note": "Every run still needs a fresh allocation and actual "
                                     "capacity gate; this report grants no execution.",
            "accepted_task_scopes": rows}


if __name__ == "__main__":
    print(json.dumps({**summary(), **accepted_tasks()}, indent=2))
