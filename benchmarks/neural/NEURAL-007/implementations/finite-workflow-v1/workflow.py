"""One finite, provider-neutral sleep programme plus protected pair.

Execution requires separate operator admission, exact external exposures and a
host supervisor. No admission is manufactured here and no retry is performed.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import provenance

COMMAND = C.PROGRAMME_COMMAND
RESOURCES = C.PROGRAMME_RESOURCES
GLOBAL_SECONDS = C.GLOBAL_SECONDS


def freeze(programme, source_freeze, run_root):
    """Freeze all participant code/dependencies before any scientific-input read."""
    C.authenticate_sources(source_freeze)
    raw = C.snapshot(programme, 200000)
    raw.decode("utf-8", errors="strict")
    root = C.path(run_root)
    root.mkdir(mode=0o700)  # Fresh only: never overwrite/reuse a previous attempt.
    frozen = C.write(root / "program.py", raw, 0o444)
    definition = {"schema": "sleep007_finite_programme_v1", "programme": C.plain(frozen), "image": C.IMAGE,
                  "source_freeze": C.plain(source_freeze), "profile": C.original("profile")[1],
                  "information": "six_labeled_training_people_plus_features_clocks_and_YASA"}
    definition = C.write(root / "PROGRAMME.json", C.json_bytes(definition), 0o444)
    return C.write(root / "PREPARED.json", C.json_bytes({"schema": "sleep007_finite_prepared_v1",
                   "programme": frozen, "definition": definition, "source_freeze": source_freeze,
                   "scientific_input_content_reads": 0, "participant_image": C.IMAGE}))


def checked_prepared(descriptor):
    value = json.loads(C.descriptor_read(descriptor, 32768))
    C.need(set(value) == {"schema", "programme", "definition", "source_freeze", "scientific_input_content_reads", "participant_image"}
           and value["schema"] == "sleep007_finite_prepared_v1" and value["scientific_input_content_reads"] == 0
           and value["participant_image"] == C.IMAGE, "exact pre-input programme freeze")
    source = C.authenticate_sources(value["source_freeze"])
    C.descriptor_read(value["programme"], 200000).decode("utf-8", errors="strict")
    definition = json.loads(C.descriptor_read(value["definition"], 32768))
    C.need(definition == {"schema": "sleep007_finite_programme_v1", "programme": C.plain(value["programme"]),
                         "image": C.IMAGE, "source_freeze": C.plain(value["source_freeze"]),
                         "profile": C.original("profile")[1],
                         "information": "six_labeled_training_people_plus_features_clocks_and_YASA"}, "complete dependency freeze")
    return value, source


def locations(descriptor, profile):
    value = json.loads(C.descriptor_read(descriptor, 32768))
    expected = {row["path"] for row in profile["training"] + profile["helpers"]
                + [r for unit in profile["units"] for r in unit["active_inputs"]]}
    C.need(set(value) == {"schema", "files"} and value["schema"] == "sleep007_public_locations_v1"
           and set(value["files"]) == expected, "only original 22 scientific arrays and two public helpers")
    for path in value["files"].values():
        C.need(type(path) is str and Path(path).is_absolute(), "absolute operator location")
    return value["files"]


def file_mount(file, expected, purpose="input"):
    file = C.path(file)
    return {"path": str(file), "kind": "file", "purpose": purpose, "files": {file.name: expected}}


def make_mounts(prepared, source, profile, public_locations, case):
    """Metadata-only exact participant exposure; never reads array contents."""
    unit = next(u for u in profile["units"] if u["unit_id"] == case)
    mounts = {row["mount_destination"]: file_mount(public_locations[row["path"]], C.plain(row))
              for row in profile["training"] + profile["helpers"] + unit["active_inputs"]}
    for target, name in (("/input/case.json", case), ("/input/public_validation.py", "validation")):
        mounts[target] = file_mount(*C.original(name), purpose="contract")
    mounts["/program/program.py"] = file_mount(prepared["programme"]["path"], C.plain(prepared["programme"]), "program")
    mounts["/trusted/PROGRAMME.json"] = file_mount(prepared["definition"]["path"], C.plain(prepared["definition"]), "contract")
    for name in ("common.py", "producer.py"):
        mounts["/trusted/" + name] = file_mount(C.HERE / name, source["files"][name], "program")
    return mounts


def _grader_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (200000, 200000))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 2**30, 4 * 2**30))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))


def dispatch_grade(request_descriptor, root, deadline):
    """Fresh trusted process after producer closure; no candidate imports."""
    C.need(time.monotonic() + 22 < deadline, "complete grading and cleanup allowance remains")
    stdout = root / "grade.stdout.json"
    stderr = root / "grade.stderr"
    process = None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        os.chmod(stdout, 0o600)
        os.chmod(stderr, 0o600)
        try:
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(root), "TMPDIR": str(root),
                   "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                   "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
            process = subprocess.Popen([sys.executable, "-I", "-B", str(C.HERE / "grading.py"),
                         "--request", request_descriptor["path"], "--bytes", str(request_descriptor["bytes"]),
                         "--sha256", request_descriptor["sha256"]], stdin=subprocess.DEVNULL,
                         stdout=out, stderr=err, cwd=root, env=env, start_new_session=True, preexec_fn=_grader_limits)
            process.wait(timeout=20)
        finally:
            if process is not None:
                # A reaped leader's numeric PID can be reused. Signal only the
                # still-owned unreaped child; a later group observation never
                # authorizes a signal to an already released numeric identity.
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=2)
    C.need(process.returncode == 0, "protected grading process exited successfully")
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        pass
    else:
        raise ValueError("grading process group still exists")
    raw = C.snapshot(stdout, 200000)
    report = json.loads(raw)
    C.need(report["status"] == "valid_descriptive_paired_result" and report["private_loader_calls"] == 1,
           "complete protected descriptive pair")
    return {"report": {"path": str(stdout), **C.pin(raw)}, "exit_code": process.returncode, "process_group_closed": True}


def execute(config):
    """Exactly two programme phases and one paired grade; failures never retry."""
    C.need(set(config) == {"schema", "prepared", "public_locations", "viewer_proof", "viewer", "references",
                          "private_locations", "provider", "exposures"}
           and config["schema"] == "sleep007_finite_execution_v1", "complete separately admitted finite execution")
    prepared, source = checked_prepared(config["prepared"])
    profile = json.loads(C.read(*C.original("profile")))
    public = locations(config["public_locations"], profile)
    provenance.admit_viewer(config["viewer_proof"], config["viewer"])
    root = C.path(config["prepared"]["path"]).parent / "attempt"
    root.mkdir(mode=0o700)
    for name in ("control", "quarantine", "journal"):
        (root / name).mkdir(mode=0o700)
    provider_module = C.load_provider()
    provider_config = config["provider"]
    C.need(set(provider_config) == {"docker_binary", "docker_socket"}, "operator-owned Docker interface only")
    C.need(set(config["exposures"]) == {case for case, _ in C.SPEC_CASES}, "two separately reviewed exposures")
    exposures = {}
    for case, descriptor in config["exposures"].items():
        # Descriptor equality is checked against actual mount/source in Provider.
        C.descriptor_read(descriptor, 2**20)
        exposures[descriptor["sha256"]] = descriptor["path"]
    provider = provider_module.Provider(root / "control", root / "quarantine",
                   provider_config["docker_binary"], provider_config["docker_socket"], C.bindings()["provider_manifest"],
                   exposures, 65 * 2**20, 16 * 2**20)
    origin = time.monotonic()
    deadline = origin + GLOBAL_SECONDS
    phases, parts = {}, {}
    journal_bytes = 0
    journal_count = 0

    def journal(event, value):
        nonlocal journal_bytes, journal_count
        raw = C.json_bytes({"event": event, "value": value})
        C.need(journal_count < 512 and journal_bytes + len(raw) <= 8 * 2**20, "bounded parent-owned complete journal")
        C.write(root / "journal" / (str(journal_count).zfill(6) + ".json"), raw)
        journal_count += 1
        journal_bytes += len(raw)

    for index, (case, _) in enumerate(C.SPEC_CASES):
        mounts = make_mounts(prepared, source, profile, public, case)
        request = {"schema": "osl_owned_phase_request_v1", "phase_id": "sleep007_" + case.replace("-", "_"),
                   "action": "held_attempt", "role": "A", "image": C.IMAGE, "command": COMMAND, "workdir": "/work",
                   "source": C.plain(prepared["definition"]), "exposure": C.plain(config["exposures"][case]),
                   "clock": {"origin": origin, "phase_deadline": origin + 110 * (index + 1)},
                   "resources": dict(RESOURCES), "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}
        result = provider.execute_phase(request, mounts, deadline, journal)
        observed = provider.observe(request["phase_id"], result["receipt"]["request_sha256"], result["receipt_pin"], deadline)
        C.need(observed["receipt"] == result["receipt"], "unchanged independent observation")
        receipt = observed["receipt"]
        output = C.path(receipt["quarantine_root"])
        C.need(receipt["status"] == "captured", "programme phase succeeded before output admission")
        request_file = root / "control" / request["phase_id"] / "REQUEST.json"
        request_pin = {"bytes": len(provider_module.encoded(request)), "sha256": receipt["request_sha256"]}
        row = {"request": {"path": str(request_file), **request_pin},
               "receipt": {"path": result["receipt_path"], **result["receipt_pin"]},
               "observer": C.write(root / (case + "-observer.json"), C.json_bytes(observed)),
               "result": {"path": str(output / "RESULT.json"), **receipt["output_inventory"]["files"]["RESULT.json"]},
               "predictions": {"path": str(output / "predictions.npz"), **receipt["output_inventory"]["files"]["predictions.npz"]}}
        # This admission is before the next person's process starts.
        definition = json.loads(C.descriptor_read(prepared["definition"], 32768))
        provenance.check_phase(row, definition, C.plain(prepared["definition"]), source["files"], profile, case)
        phases[case], parts[case] = row, row["predictions"]
    # No programme execution or source mutation is allowed after this commitment.
    checked_prepared(config["prepared"])
    commit = C.write(root / "PROGRAMME_COMMIT.json", C.json_bytes({"schema": "sleep007_finite_programme_commit_v1",
                 "source_freeze": prepared["source_freeze"], "definition": prepared["definition"], "phases": phases,
                 "parts": parts, "original_deadline": deadline, "clock_origin": origin}))
    request = {"schema": "sleep007_finite_grade_v1", "source_freeze": prepared["source_freeze"],
               "programme_commit": commit, "parts": parts,
               **{key: config[key] for key in ("viewer_proof", "viewer", "references", "private_locations")}}
    provenance.admit_grade(request)
    import grading
    # Both complete arms and both original references pass before grade dispatch.
    grading.validate_public(request["viewer"], request["parts"], request["references"])
    grade_request = C.write(root / "GRADE_REQUEST.json", C.json_bytes(request))
    grade = dispatch_grade(grade_request, root, deadline)
    return C.write(root / "COMPLETE.json", C.json_bytes({"schema": "sleep007_finite_workflow_result_v1", "status": "complete",
                   "epochs": 5450, "people": 2, "programme_commit": commit, "grade": grade,
                   "clock_origin": origin, "deadline": deadline, "finished": time.monotonic(),
                   "external_model_provider_calls_initiated_by_coordinator": 0,
                   "participant_model_or_fit_calls": None, "journal_bytes": journal_bytes, "journal_records": journal_count,
                   "provider_read_bytes": provider.read_used, "provider_reserved_write_bytes": provider.write_used,
                   "contrast": "workflow_capability_not_matched_tool_effect", "scientific_qualification": False,
                   "population_inference": False, "automatic_retry": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--bytes", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    config = json.loads(C.read(args.config, {"bytes": args.bytes, "sha256": args.sha256}, 32768))
    try:
        result = execute(config)
    except BaseException as error:
        print(C.json_bytes({"status": "failed", "error_type": type(error).__name__, "automatic_retry": False}).decode(), end="")
        raise
    print(C.json_bytes(result).decode(), end="")


if __name__ == "__main__":
    main()
