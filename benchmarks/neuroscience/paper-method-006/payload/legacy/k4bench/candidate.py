"""Matched candidate authoring, tool protocol and sealed I program lifecycle."""
from .protocol import require, identifier, unique, validate_pin, digest, write_new, relative
from .admission import packet_members, CELLS
from .identity import manifest_digest

TRANSITIONS = {
    "created": {"authoring", "failed"},
    "authoring": {"sealed", "failed"},
    "sealed": {"running", "failed"},
    "running": {"submitted", "failed"},
    "submitted": {"protected-validation", "failed"},
    "protected-validation": {"reported", "failed"},
    "reported": set(), "failed": set(),
}


def authoring_request(cell, manifest, provider_profile, token_budget, tool_budget):
    require(cell in CELLS, "invalid-cell", cell)
    require(provider_profile["transport"] == "isolated-local-jsonl-v1",
            "provider-unimplemented", "no network provider adapter selected or represented as implemented")
    require(provider_profile["executable_pin"] and provider_profile["environment_pin"],
            "provider-unbound", "exact provider/version/environment")
    validate_pin(provider_profile["executable_pin"])
    validate_pin(provider_profile["environment_pin"])
    require(token_budget > 0 and tool_budget > 0, "unbounded-provider-budget", cell)
    packet = packet_members(manifest["members"], cell)
    return {"schema": "kilosort4_candidate_authoring_request_v1", "cell": cell,
            "manifest_digest": manifest_digest(manifest), "packet": packet,
            "provider_profile": provider_profile,
            "token_budget": token_budget, "tool_call_budget": tool_budget,
            "tool_protocol": "kilosort4-tools-jsonl-v1",
            "tools": ["read_text", "write_text", "list_files", "run_python"],
            "network": "none", "protected_truth_feedback": False,
            "required_output": "program.py plus submission.json and method explanation",
            "fixed_query_contract": "one fresh full-recording process per query; no provider calls after seal",
            "author_code_available": cell.startswith("B"),
            "replication_or_improvement": cell[-1],
            "query_data_is_public_and_exposure_unverified": True}


def seal_submission(cell, submission, packet_digest, provider_receipt_pin):
    require(cell in CELLS, "invalid-cell", cell)
    require(submission["schema"] == "kilosort4_candidate_submission_v1", "submission-schema", cell)
    files = unique(submission["files"], "path")
    require("program.py" in files and "method.md" in files, "missing-submission-file", cell)
    require(submission["entrypoint"] == ["python", "-I", "/candidate/program.py", "/run/request.json", "/output"],
            "candidate-entrypoint", "fixed standalone program protocol")
    for file in files.values():
        relative(file["path"])
        validate_pin(file)
    require(submission["purpose"] == cell[-1] and submission["cell"] == cell,
            "submission-cell-mismatch", cell)
    require(submission["external_models"] == [] or submission["common_model_admission_pins"],
            "unadmitted-candidate-model", cell)
    for pin in submission["common_model_admission_pins"]:
        validate_pin(pin)
    validate_pin(provider_receipt_pin)
    return {"schema": "kilosort4_program_seal_v1", "cell": cell,
            "submission_digest": digest(submission), "files": submission["files"],
            "packet_digest": packet_digest, "provider_receipt_pin": provider_receipt_pin,
            "state": "sealed", "no_query_feedback_before_seal": True,
            "external_fit_state": submission["external_models"]}


class Lifecycle:
    """Host append-only state with simultaneous A/B I commitment barrier."""
    def __init__(self, run_directory, meter, manifest_digest_value):
        self.run_directory = run_directory
        self.meter, self.manifest_digest_value = meter, manifest_digest_value
        self.states = {cell: "created" for cell in CELLS}
        self.seals, self.sequence, self.query_attempts = {}, 0, set()
        self.previous_digest = None

    def transition(self, cell, state, payload):
        require(state in TRANSITIONS[self.states[cell]], "invalid-lifecycle-transition", cell)
        require(state != "sealed" or payload["state"] == "sealed", "missing-seal", cell)
        record = {"schema": "kilosort4_lifecycle_event_v1", "sequence": self.sequence,
                  "manifest_digest": self.manifest_digest_value, "cell": cell,
                  "from": self.states[cell], "to": state, "payload": payload,
                  "previous_event_digest": self.previous_digest}
        pin = write_new(self.run_directory / f"event-{self.sequence:06}.json", record, self.meter)
        self.sequence += 1
        self.previous_digest = digest(record)
        self.states[cell] = state
        if state == "sealed":
            self.seals[cell] = payload
        return pin

    def permit_query(self, cell, query_id, fresh_workspace_receipt_pin):
        require(cell in {"A-I", "B-I"}, "wrong-query-purpose", cell)
        require(set(self.seals) >= {"A-I", "B-I"}, "paired-seal-barrier", "both I programs first")
        require(self.states[cell] in {"sealed", "running"}, "query-lifecycle-state", cell)
        require((cell, query_id) not in self.query_attempts, "query-retry-not-selected", query_id)
        validate_pin(fresh_workspace_receipt_pin)
        self.query_attempts.add((cell, query_id))
        return {"cell": cell, "query_id": query_id, "program_seal": self.seals[cell],
                "fresh_workspace_receipt_pin": fresh_workspace_receipt_pin,
                "provider_access": False, "persistent_state": False, "truth_access": False,
                "R_output_access": False, "transductive_fit_on_current_full_recording": True}

    def protected_evaluation_barrier(self, required_query_ids, submission_receipts):
        expected = {(cell, query) for cell in ("A-I", "B-I") for query in required_query_ids}
        actual = {(r["cell"], r["query_id"]) for r in submission_receipts}
        require(len(submission_receipts) == len(actual) and actual == expected,
                "incomplete-protected-barrier", "all I query outputs before protected score access")
        require(set(self.seals) >= {"A-I", "B-I"}, "paired-seal-barrier", "sealed programs")
        for row in submission_receipts:
            require(row["seal_digest"] == digest(self.seals[row["cell"]]),
                    "candidate-mutated-after-seal", row["query_id"])
            validate_pin(row["output_pin"])
            validate_pin(row["attempt_receipt_pin"])
        return {"status": "barrier-satisfied", "manifest_digest": self.manifest_digest_value,
                "submission_receipts_digest": digest(submission_receipts),
                "submission_receipts": submission_receipts,
                "program_seals": self.seals,
                "no_feedback_return_path": True}
