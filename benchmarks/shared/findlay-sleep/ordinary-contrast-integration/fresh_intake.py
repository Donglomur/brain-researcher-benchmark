"""Fresh local-original preparation through the existing owner; no acquisition.

Inputs are the exact complete release and fixed external scientific metadata.
Receipts describe this new operation, never a fictitious earlier failed run.
"""
import hashlib
import json
import os
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def provision_original(pin, ledger, budget, intake, contract):
    contract.validate_archive_pin(pin)
    need(pin["bytes"] == ledger["archive_bytes"], "Whole original release extent")
    budget.check()
    body = intake.read_all(Path(pin["path"]), budget, pin["bytes"])
    need(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
         "Complete original archive SHA256; arbitrary replacements are refused")
    intake.directory(body, ledger)
    # Only an authenticated complete original is copied into this fresh output.
    destination = budget.root / "release.zip"
    budget.charge_write(len(body))
    with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                           0o400), "wb") as stream:
        need(stream.write(body) == len(body), "Complete original archive write")
        stream.flush()
        os.fsync(stream.fileno())
    budget.check()
    receipt = budget.write_json("ORIGINAL_INPUT.private.json", {
        "schema": "findlay-local-original-input/v1",
        "source": pin, "copied_archive": {"path": str(destination), "bytes": len(body),
            "sha256": pin["sha256"]}, "new_GETs": 0, "complete": True,
        "digest_origin": "Accepted observed exact release identity, not provider checksum",
        "prior_attempt_required": False, "scientific_qualification": False})
    return destination, receipt


def operate(admission, intake, census, rules, native_ready, ordinary, policy, contract):
    task = admission["request"]["task"]
    need(admission["request"]["schema"] == "findlay-portable-first-intake-request/v1"
         and set(task) == {"input_ledger", "published_families", "private_policy",
             "original_archive", "data_read_cap", "worker_output_cap"}
         and task["data_read_cap"] == task["worker_output_cap"] == 33554432,
         "Exact complete first-intake request and unchanged output allowance")
    for key in ("source_read_bytes", "runtime_join_read_bytes", "receipt_read_bytes"):
        need(type(admission[key]) is int and admission[key] >= 0, "Complete worker admission costs")
    metadata = {key: contract.authenticate(key, admission["source_capture"][task[key]["path"]])
                for key in contract.PINS}
    contract.join(metadata)
    inputs, families = metadata["input_ledger"], metadata["published_families"]
    rules.configure_private_policy(metadata["private_policy"])
    policy.configure_private_policy(metadata["private_policy"])
    output = Path(admission["output_root"]) / "worker"
    output.mkdir(mode=0o700)
    budget = intake.Budget(output, admission["work_deadline"], read_limit=24*1024**2,
                           write_limit=task["worker_output_cap"])
    archive, input_receipt = provision_original(task["original_archive"], inputs, budget, intake, contract)
    members, integrity_pin = intake.extract_verify(archive, inputs, budget)
    integrity = json.loads(intake.read_all(Path(integrity_pin["path"]), budget, 2*1024**2))
    need(integrity["complete"] is True
         and integrity["archive"] == {key: task["original_archive"][key] for key in ("bytes", "sha256")},
         "Extracted archive matches the complete fixed original")
    measured = {row["name"]: row for row in integrity["members"]}
    need(len(measured) == len(integrity["members"]) == 17
         and set(measured) == {row["path"] for row in inputs["members"]}, "All seventeen original members")
    for member in inputs["members"]:
        observed = measured[member["path"]]
        need(observed["bytes"] == member["bytes"] and observed["stored_byte_recheck"] is True,
             "Complete independently reread member pin")
        member["sha256"] = observed["sha256"]
        member["sha256_status"] = "Fresh local original archive and full stored-member verification"
    budget.check()
    budget.write_json("NATIVE_RUNTIME.private.json", native_ready())
    result_census = census.census(members, inputs, families, budget, rules_module=rules,
                                 ordinary_module=ordinary, ordinary_policy=policy)
    need(result_census["status"] == "COMPLETE_INTAKE_CENSUS_WITH_GATES"
         and result_census["table_count"] == 13 and result_census["family_count"] == 98
         and len(result_census["table_reports"]) == 13
         and len(result_census["contrast_reports"]) == 2
         and result_census["all_tables_and_families_accounted"] is True
         and result_census["scientific_ready"] is False and result_census["models_fitted"] == 0,
         "Entire original census and both contrast reports, with scientific holds")
    post = []
    for name, observed in sorted(measured.items()):
        body = intake.read_all(members / name, budget, observed["bytes"])
        need(hashlib.sha256(body).hexdigest() == observed["sha256"], "Post-census member integrity")
        post.append({"name": name, "bytes": len(body), "sha256": observed["sha256"]})
    post_pin = budget.write_json("POST_CENSUS_INTEGRITY.private.json", {"members": post})
    result = {"schema": "findlay-worker-result/v1", "status": "COMPLETE_INTAKE_CENSUS_WITH_GATES",
        "all_tables": 13, "all_families": 98, "scientific_qualification": False, "models_fitted": 0,
        "input_mode": "fresh_local_original", "prior_attempt_required": False, "new_GETs": 0,
        "original_work_deadline": admission["work_deadline"], "original_input": input_receipt,
        "source_ledger_pins": {key: task[key] for key in contract.PINS},
        "integrity": integrity_pin, "post_census_integrity": post_pin, "census": result_census,
        "application_read_bytes": budget.read_bytes, "worker_write_bytes_before_result": budget.write_bytes,
        "worker_receipts_before_result": budget.outputs, "worker_source_read_bytes": admission["source_read_bytes"],
        "worker_runtime_join_read_bytes": admission["runtime_join_read_bytes"],
        "worker_admission_receipt_read_bytes": admission["receipt_read_bytes"],
        "reads_exclude_runtime_source_and_os_implicit_io": True, "candidate_visible_outputs": False}
    budget.write_json("result.json", result)
    budget.check()
    return result

