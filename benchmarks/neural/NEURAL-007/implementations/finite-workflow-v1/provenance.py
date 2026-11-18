"""Trusted operator commitments, not participant-asserted completion flags."""
import json
import math
from pathlib import Path
import common as C

VIEWER_COMPLETE = {"bytes": 6551, "sha256": "fc4b99d1860903e06976e33ae13202253d75d1569b2985af486c0da62290559e"}
VIEWER_REVIEW = {"bytes": 4558, "sha256": "356ae6bb2203d7dc65dc7e8a9f578088b630906df9c70591837d76e222868839"}
VIEWER_SUBMISSION = {"bytes": 677264, "sha256": "1efcb3620776d4042d1050e456e867992a7c6a9c13942c9e68afa9f1a03839d3"}


def admit_viewer(proof, submission):
    if type(proof) is dict and set(proof) == {"fresh_provider"}:
        verifier = C._module("sleep007_fresh_viewer_admission", *C.original("fresh_viewer"))
        return verifier.admit(proof, submission)
    C.need(type(proof) is dict and set(proof) == {"complete", "review"}, "accepted old viewer proof")
    C.need(C.plain(proof["complete"]) == VIEWER_COMPLETE and C.plain(proof["review"]) == VIEWER_REVIEW,
           "exact accepted complete proof and independent review")
    value = json.loads(C.descriptor_read(proof["complete"], 16384))
    C.descriptor_read(proof["review"], 16384)
    C.need(value["status"] == "pass" and value["epochs"] == 5450 and value["new_model_calls"] == 0
           and value["private_target_reads"] == 0 and value["source_commit"] == "f1dea1ee4fa779ea3ee56bc6b5a906186488506b",
           "accepted historical scripted control only")
    C.need(value["submission"] == C.plain(submission) == VIEWER_SUBMISSION, "original collector submission identity")
    C.need(len(value["cases"]) == 2, "both original producer closures")
    for row, (case, epochs) in zip(value["cases"], C.SPEC_CASES):
        C.need(row["case_id"] == case and row["images"] == epochs and row["status"] == "complete_unscored"
               and row["client_exit_code"] == 0 and row["forced_stop"] is False
               and row["process_group_cleanup"] == "absent", "old participant process group closed")
    return value


def scientific_inputs(profile, case):
    unit = next(u for u in profile["units"] if u["unit_id"] == case)
    result = {row["mount_destination"]: C.plain(row) for row in profile["training"] + profile["helpers"] + unit["active_inputs"]}
    result["/input/case.json"] = C.original(case)[1]
    result["/input/public_validation.py"] = C.original("validation")[1]
    return result


def check_phase(record, definition, definition_pin, source_files, profile, case):
    C.need(set(record) == {"request", "receipt", "observer", "result", "predictions"}, "complete trusted phase commitment")
    request = json.loads(C.descriptor_read(record["request"], 32768))
    receipt = json.loads(C.descriptor_read(record["receipt"], 2**20))
    observer = json.loads(C.descriptor_read(record["observer"], 2**20))
    C.need(observer["receipt_pin"] == C.plain(record["receipt"]) and observer["receipt"] == receipt
           and observer["independent_candidate_channel"] is True, "independently observed parent receipt")
    C.need(set(request) == {"schema", "phase_id", "action", "role", "image", "command", "workdir", "source", "exposure", "clock", "resources", "output"}
           and request["schema"] == "osl_owned_phase_request_v1"
           and request["phase_id"] == "sleep007_" + case.replace("-", "_")
           and request["action"] == "held_attempt" and request["role"] == "A" and request["image"] == C.IMAGE
           and request["source"] == definition_pin and request["output"] == {"kind": "generic", "manifest": "OUTPUTS.json"}
           and request["command"] == C.PROGRAMME_COMMAND and request["resources"] == C.PROGRAMME_RESOURCES and request["workdir"] == "/work",
           "exact original-programme producer request")
    C.need(receipt["schema"] == "osl_owned_phase_receipt_v1" and receipt["request_sha256"] == record["request"]["sha256"]
           and receipt["phase_id"] == request["phase_id"] and receipt["source"] == request["source"]
           and receipt["image"] == request["image"] and receipt["action"] == request["action"] and receipt["role"] == request["role"]
           and receipt["exposure"] == request["exposure"] and receipt["status"] == "captured"
           and receipt["all_native_resources_closed"] is True and receipt["producer_closed_before_capture"] is True
           and receipt["cli_reaped"] is True and receipt["error"] is None
           and receipt["enforced_resource_limits"] == C.PROGRAMME_RESOURCES
           and receipt["deadline_exceeded"] is False, "actual closed canonical producer receipt")
    clock, timing = request["clock"], receipt["timing"]
    C.need(set(clock) == {"origin", "phase_deadline"}
           and set(timing) == {"origin", "original_deadline", "phase_deadline", "started", "finished"}
           and all(type(v) in (int, float) and math.isfinite(v) for v in (*clock.values(), *timing.values())), "finite exact clock fields")
    index = [name for name, _ in C.SPEC_CASES].index(case)
    C.need(clock["origin"] == timing["origin"] and timing["original_deadline"] == clock["origin"] + C.GLOBAL_SECONDS
           and clock["phase_deadline"] == clock["origin"] + 110 * (index + 1)
           and timing["phase_deadline"] == timing["started"] + 100
           and clock["origin"] <= timing["started"] < timing["finished"] <= timing["phase_deadline"]
           <= clock["phase_deadline"] <= timing["original_deadline"], "original fixed complete phase allowance")
    exit_state = receipt["natural_exit"]
    C.need(type(exit_state["ExitCode"]) is int and exit_state["ExitCode"] == 0 and exit_state["Running"] is False
           and exit_state["Status"] == "exited" and exit_state["Dead"] is False and exit_state["Pid"] == 0
           and exit_state["OOMKilled"] is False,
           "normal successful participant exit")
    rows = receipt["retired_resources"]
    C.need(len(rows) == 3 and all(row["closed"] is True for row in rows)
           and len({row["name"] for row in rows}) == 3
           and all(row.get("creation_outcome_unknown") is False and row.get("absence_observed") is True for row in rows)
           and sorted(row["kind"] for row in rows) == ["container", "container", "volume"], "all three owned resources closed")
    expected = scientific_inputs(profile, case)
    expected.update({"/program/program.py": definition["programme"], "/trusted/PROGRAMME.json": definition_pin,
                     "/trusted/producer.py": source_files["producer.py"], "/trusted/common.py": source_files["common.py"]})
    before = receipt["input_before"]
    C.need(before == receipt["input_after"] and set(before) == set(expected), "exact unchanged participant-visible input set")
    for target, want in expected.items():
        row = before[target]
        C.need(row["kind"] == "file" and len(row["files"]) == 1 and list(row["files"].values()) == [want], "original input/dependency pin")
    inventory = receipt["output_inventory"]
    C.need(inventory["complete"] is True and set(inventory["files"]) == {"predictions.npz", "RESULT.json", "OUTPUTS.json"},
           "complete captured original output plus envelope")
    for name, key in (("predictions.npz", "predictions"), ("RESULT.json", "result")):
        C.need(inventory["files"][name] == C.plain(record[key])
               and C.path(record[key]["path"]) == C.path(Path(receipt["quarantine_root"]) / name), "captured output custody")
    result = json.loads(C.descriptor_read(record["result"], 4096))
    C.need(result == {"schema": "sleep007_finite_producer_v1", "case_id": case, "epochs": dict(C.SPEC_CASES)[case],
                      "programme": definition["programme"], "predictions": C.plain(record["predictions"]), "participant_exit": 0},
           "exact original per-person producer envelope")
    return request, receipt


def admit_programme(commit_descriptor, source_freeze, parts):
    commit = json.loads(C.descriptor_read(commit_descriptor, 32768))
    C.need(set(commit) == {"schema", "source_freeze", "definition", "phases", "parts", "original_deadline", "clock_origin"}
           and commit["schema"] == "sleep007_finite_programme_commit_v1"
           and commit["source_freeze"] == source_freeze and commit["parts"] == parts
           and set(parts) == {c for c, _ in C.SPEC_CASES}, "exact frozen complete programme commitment")
    source = C.authenticate_sources(source_freeze)
    definition = json.loads(C.descriptor_read(commit["definition"], 32768))
    C.need(set(definition) == {"schema", "programme", "image", "source_freeze", "profile", "information"}
           and definition["schema"] == "sleep007_finite_programme_v1" and definition["image"] == C.IMAGE
           and definition["source_freeze"] == C.plain(source_freeze) and definition["profile"] == C.original("profile")[1]
           and definition["information"] == "six_labeled_training_people_plus_features_clocks_and_YASA",
           "complete programme/dependency freeze before release")
    C.checked_pin(definition["programme"], 200000)
    profile = json.loads(C.read(*C.original("profile")))
    C.need(set(commit["phases"]) == set(parts), "exact complete two-person phase set")
    last_finish = commit["clock_origin"]
    for case, _ in C.SPEC_CASES:
        row = commit["phases"][case]
        C.need(row["predictions"] == parts[case], "programme part from owned capture")
        request, receipt = check_phase(row, definition, C.plain(commit["definition"]), source["files"], profile, case)
        C.need(request["clock"]["origin"] == commit["clock_origin"]
               and receipt["timing"]["original_deadline"] == commit["original_deadline"]
               and last_finish <= receipt["timing"]["started"] < receipt["timing"]["finished"] <= commit["original_deadline"],
               "same finite clock; next person after previous complete closure")
        last_finish = receipt["timing"]["finished"]
    return commit


def admit_grade(request):
    C.need(set(request) == {"schema", "source_freeze", "viewer_proof", "programme_commit", "viewer", "parts", "references", "private_locations"}
           and request["schema"] == "sleep007_finite_grade_v1", "exact trusted grading request")
    admit_viewer(request["viewer_proof"], request["viewer"])
    admit_programme(request["programme_commit"], request["source_freeze"], request["parts"])
    assets = json.loads(C.read(*C.original("assets")))
    C.need(set(request["references"]) == {"YASA", "RF"}, "unchanged comparator roster")
    for name, value in request["references"].items():
        C.need(C.plain(value) == C.plain(assets["comparators"][name]), "original comparator identity")
