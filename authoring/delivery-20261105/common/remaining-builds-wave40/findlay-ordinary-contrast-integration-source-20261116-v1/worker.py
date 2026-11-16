"""One selected no-download Findlay census continuation; no fit or model run."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import sys
import time
import types

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[4]
PREFIX = ROOT.relative_to(REPOSITORY).as_posix()
OLD = PREFIX.rsplit("/", 1)[0] + "/findlay-complete-intake-census-source-20261115-v1"
DOSSIER = PREFIX.rsplit("/", 1)[0] + "/findlay-sleep-complete-contract-source-20261115-v1"


def need(ok, why):
    if not ok:
        raise ValueError(why)


def captured(name, relative, admission):
    module = types.ModuleType(name)
    module.__file__ = str(REPOSITORY / relative)
    sys.modules[name] = module
    exec(compile(admission["source_capture"][relative], module.__file__, "exec"), module.__dict__)
    return module


def ledger(task, key, filename, admission):
    pin = task[key]
    need(Path(pin["path"]).is_absolute(), "External complete metadata path")
    body = admission["source_capture"][pin["path"]]
    need(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
         "Exact original complete ledger bytes")
    return json.loads(body)


def pinned_body(pin, budget, intake, cap):
    need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "Exact complete input pin")
    need(type(pin["bytes"]) is int and 0 < pin["bytes"] <= cap, "Bounded complete original input")
    body = intake.read_all(Path(pin["path"]), budget, pin["bytes"])
    need(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
         "Exact retained input body")
    return body


def admit_prior(pin, new_output, ledger_value, budget, intake):
    manifest = json.loads(pinned_body(pin, budget, intake, 262144))
    need(type(manifest) is dict and set(manifest) == {
        "schema", "root", "files", "independent_review", "previous_request", "previous_source_lock",
        "prior_status", "prior_cost_completeness"}
        and manifest["schema"] == "findlay-census-continuation-inputs/v1"
        and manifest["prior_status"] == "REFUSED"
        and manifest["prior_cost_completeness"] == "known lower bound; incomplete worker costs",
        "Exact failed-whole continuation input schema")
    prior = Path(manifest["root"])
    need(prior.is_absolute() and prior == prior.resolve(strict=True)
         and not prior.is_relative_to(REPOSITORY)
         and not (new_output.is_relative_to(prior) or prior.is_relative_to(new_output)),
         "Disjoint canonical original artifact root")
    review = pinned_body(manifest["independent_review"], budget, intake, 262144)
    previous_request = json.loads(pinned_body(manifest["previous_request"], budget, intake, 131072))
    previous_lock = pinned_body(manifest["previous_source_lock"], budget, intake, 262144)
    need(previous_request["execution"]["output_root"] == str(prior)
         and previous_request["execution"]["source_lock"] == manifest["previous_source_lock"]
         and previous_request["schema"] == "findlay-complete-intake-census-request/v1",
         "Original failed request/source/output binding")
    need(type(manifest["files"]) is dict and 17 < len(manifest["files"]) <= 128,
         "Finite exact retained-input roster")
    consumed = set()

    def read(relative, cap=2097152):
        pure = PurePosixPath(relative)
        need(not pure.is_absolute() and pure.as_posix() == relative
             and all(part not in ("", ".", "..") for part in pure.parts), "Literal retained relative path")
        value = manifest["files"][relative]
        need(type(value) is dict and set(value) == {"bytes", "sha256"}, "Exact relative stored-byte pin")
        full = {"path": str(prior / relative), **value}
        body = pinned_body(full, budget, intake, cap)
        consumed.add(relative)
        return body, full

    outer = json.loads(read("outer_result.json")[0])
    need(outer["status"] == "REFUSED" and outer["scientific_qualification"] is False
         and outer["observed"]["completion"]["returncode"] == 1
         and outer["observed"]["cleanup"]["absence_verified"] is True
         and outer["request_sha256"] == manifest["previous_request"]["sha256"]
         and outer["source_lock_sha256"] == manifest["previous_source_lock"]["sha256"],
         "Original failed whole and independently reviewed cleanup joins")
    http = json.loads(read("worker/HTTP.private.json")[0])
    integrity = json.loads(read("worker/INTEGRITY.private.json")[0])
    archive, archive_pin = read("worker/release.zip", 3015691)
    need(http["complete"] is True and http["attempts"] == 1 and integrity["complete"] is True
         and len(archive) == ledger_value["archive_bytes"] == http["retained_body_bytes"]
         and archive_pin["sha256"] == http["retained_body_sha256"] == integrity["archive"]["sha256"],
         "Entire original download/archive remains unchanged")
    measured = {row["name"]: row for row in integrity["members"]}
    need(len(measured) == 17 and set(measured) == {row["path"] for row in ledger_value["members"]},
         "All seventeen original release members")
    for member in ledger_value["members"]:
        body, member_pin = read("worker/members/" + member["path"], 3015691)
        row = measured[member["path"]]
        need(len(body) == member["bytes"] == row["bytes"] and row["stored_byte_recheck"] is True
             and member_pin["sha256"] == row["sha256"], "All original member bodies unchanged")
        member["sha256"] = row["sha256"]
        member["sha256_status"] = "Complete prior authentic intake, independent byte review and continuation recheck"
    tables = {}
    for member in ledger_value["members"]:
        name = member["path"]
        if not name.endswith(".pqt"):
            continue
        report_body, report_pin = read("worker/table-" + name + ".private.json")
        report = json.loads(report_body)
        need(report["authentication"]["sha256"] == member["sha256"]
             and report["authentication"]["bytes"] == member["bytes"]
             and report["authentication"]["footer_sha256"] == member["footer_sha256"],
             "Complete retained census is bound to original input")
        groups = []
        for index, part_pin in enumerate(report["group_parts"]):
            relative = "worker/groups-" + name + f"-{index:03d}.private.json"
            data, checked_pin = read(relative)
            need(checked_pin == part_pin, "Literal original group-part pin")
            part = json.loads(data)
            need(part["table"] == name and part["first_group"] == len(groups)
                 and 0 < len(part["groups"]) <= 2048, "Complete consecutive original group parts")
            groups.extend(part["groups"])
        need(len(groups) == report["group_count"] and sum(row[1] for row in groups) == report["rows"],
             "All group keys and row counts retained")
        report["groups"] = groups
        tables[name] = {"pin": report_pin, "report": report}
    need(consumed == set(manifest["files"]), "No unused or unverified retained-input pins")
    return prior / "worker/members", tables, measured, {
        "manifest": pin, "review": manifest["independent_review"],
        "previous_request": manifest["previous_request"], "previous_source_lock": manifest["previous_source_lock"],
        "prior_whole_status": "REFUSED", "prior_cost_completeness": manifest["prior_cost_completeness"],
        "prior_elapsed_seconds": outer["elapsed_seconds"],
        "prior_managed_runtime_read_bytes": outer["managed_runtime_read_bytes"],
        "prior_managed_source_read_bytes": outer["managed_source_read_bytes"],
        "prior_outer_receipt_read_bytes": outer["outer_receipt_read_bytes"],
        "original_family_serialized_extent": None,
        "original_family_serialized_extent_upper_bound": 2097152,
        "original_missing_worker_costs_not_reconstructed": True,
        "verified_input_files": len(consumed), "new_downloads": 0}


def operate(admission, intake, census, rules, tail, native_ready, ordinary_module, ordinary_policy):
    task = admission["request"]["task"]
    need(set(task) == {"input_ledger", "published_families", "data_read_cap", "worker_output_cap", "prior_attempt", "private_policy"}
         and task["data_read_cap"] == 33554432 and task["worker_output_cap"] == 33554432,
         "Exact complete continuation task and adequate output ceiling")
    for field in ("source_read_bytes", "runtime_join_read_bytes", "receipt_read_bytes"):
        need(type(admission[field]) is int and admission[field] >= 0, "Complete measured worker admission costs")
    inputs = ledger(task, "input_ledger", "INPUT_LEDGER.json", admission)
    families = ledger(task, "published_families", "PUBLISHED_98_LEDGER.json", admission)
    need((inputs["member_count"], inputs["parquet_member_count"], inputs["static_subjects"], inputs["static_sessions"])
         == (17, 13, 16, 29), "Entire source cohort and release")
    output = Path(admission["output_root"]) / "worker"
    output.mkdir(mode=0o700)
    budget = intake.Budget(output, admission["work_deadline"], read_limit=24*1024**2,
                           write_limit=task["worker_output_cap"])
    budget.check()
    budget.write_json("NATIVE_RUNTIME.private.json", native_ready())
    members, tables, measured, reuse = admit_prior(task["prior_attempt"], output, inputs, budget, intake)
    result_census = tail.resume_tail(members, inputs, families, budget, tables,
                                    census_module=census, rules_module=rules,
                                    ordinary_module=ordinary_module, ordinary_policy=ordinary_policy)
    need(result_census["status"] == "COMPLETE_INTAKE_CENSUS_WITH_GATES"
         and result_census["table_count"] == 13 and result_census["family_count"] == 98
         and result_census["all_tables_and_families_accounted"] is True
         and result_census["scientific_ready"] is False and result_census["models_fitted"] == 0,
         "Complete original table and family scope without scientific promotion")
    post = []
    for name, value in sorted(measured.items()):
        body = intake.read_all(members / name, budget, value["bytes"])
        need(hashlib.sha256(body).hexdigest() == value["sha256"], "Complete post-tail original member parity")
        post.append({"name": name, "bytes": len(body), "sha256": value["sha256"]})
    post_pin = budget.write_json("POST_CENSUS_INTEGRITY.private.json", {"members": post})
    result = {"schema": "findlay-worker-result/v1", "status": "COMPLETE_INTAKE_CENSUS_WITH_GATES",
              "all_tables": 13, "all_families": 98, "scientific_qualification": False, "models_fitted": 0,
              "original_work_deadline": admission["work_deadline"], "continuation_inputs": reuse,
              "source_ledger_pins": {k: task[k] for k in ("input_ledger", "published_families")},
              "post_census_integrity": post_pin, "census": result_census,
              "application_read_bytes": budget.read_bytes, "worker_write_bytes_before_result": budget.write_bytes,
              "worker_receipts_before_result": budget.outputs,
              "worker_source_read_bytes": admission["source_read_bytes"],
              "worker_runtime_join_read_bytes": admission["runtime_join_read_bytes"],
              "worker_admission_receipt_read_bytes": admission["receipt_read_bytes"],
              "reads_exclude_runtime_source_and_os_implicit_io": True, "candidate_visible_outputs": False}
    budget.write_json("result.json", result)
    budget.check()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (160, 165))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4*1024**2, 4*1024**2))
    sys.dont_write_bytecode = True
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "ARROW_IO_THREADS"):
        os.environ[name] = "1"
    sys.path.insert(0, str(REPOSITORY / "authoring/delivery-20261105/common/remaining-builds-wave40/findlay-complete-census-continuation-source-20261115-v1/owner"))
    import run as owner
    admission = owner.worker_admission(args.request, args.request_sha256)
    need(Path(admission["request"]["execution"]["repository_root"]) == REPOSITORY, "Exact worker repository")
    intake = captured("findlay_tail_intake", OLD + "/intake.py", admission)
    census = captured("findlay_tail_original_census", "authoring/delivery-20261105/common/remaining-builds-wave40/findlay-identity-contrast-semantics-source-20261115-v1/identity/census.py", admission)
    rules = captured("findlay_tail_original_rules", "authoring/delivery-20261105/common/remaining-builds-wave40/findlay-identity-contrast-semantics-source-20261115-v1/identity/family_rules.py", admission)
    tail = captured("findlay_tail_census", PREFIX + "/census_tail.py", admission)
    ordinary = captured("findlay_ordinary_reconciliation", PREFIX + "/ordinary_reconciliation.py", admission)
    policy = captured("findlay_ordinary_policy", "authoring/delivery-20261105/common/remaining-builds-wave40/findlay-identity-contrast-semantics-source-20261115-v1/contrast/ordinary_contrast_policy.py", admission)
    contract = captured("findlay_private_contract", PREFIX + "/external_contract.py", admission)
    private = contract.authenticate("private_policy", admission["source_capture"][
        admission["request"]["task"]["private_policy"]["path"]])
    rules.configure_private_policy(private)
    policy.configure_private_policy(private)
    runtime = admission["runtime_module"]
    runtime.install_import_guard(admission["runtime_manifest"],
        allowed_source_files=[str(REPOSITORY / relative) for relative in admission["source_capture"] if not Path(relative).is_absolute()])

    def native_ready():
        import pyarrow
        import pyarrow.parquet
        pyarrow.set_cpu_count(1)
        pyarrow.set_io_thread_count(1)
        return runtime.verify_imported_runtime(admission["runtime_manifest"])

    result = operate(admission, intake, census, rules, tail, native_ready, ordinary, policy)
    print(json.dumps({"status": result["status"], "all_tables": 13, "all_families": 98,
                      "models_fitted": 0, "new_GETs": 0}), flush=True)
    need(time.monotonic() < admission["work_deadline"], "Original final worker deadline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
