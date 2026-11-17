"""Portable source checks for MC_Maze; no scientific or native campaign.

The selected source is trusted ordinary code. Numerical/provider/native leaves
are never invoked. Source consistency is not scientific or deployment authority.
"""
import argparse
import ast
import collections
import hashlib
import importlib
import importlib.abc
import itertools
import json
import os
from pathlib import Path
import resource
import selectors
import stat
import subprocess
import sys
import tempfile
import time


CURRENT = {}

def run_checks(task_root, work_parent=None):
    started = time.monotonic()
    checks = []
    children = []
    root = Path(task_root).absolute()
    component = root / "complete-operator"
    parent = Path(work_parent).resolve() if work_parent else Path(tempfile.gettempdir()).resolve()
    work = Path(tempfile.mkdtemp(prefix="nlb017-source-", dir=parent))
    os.chmod(work, 0o700)
    transfer = {"source_read_bytes": 0, "fixture_write_bytes": 0, "child_source_charge": 0, "captured_stream_bytes": 0}
    CURRENT.update(checks=checks, children=children, source_transfer=transfer, work_directory=str(work), started=started)

    def check(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)

    def read(path, cap=2**20):
        path = Path(path)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= cap:
            raise AssertionError("bounded ordinary source")
        with path.open("rb") as source:
            raw = source.read(cap + 1)
        transfer["source_read_bytes"] += len(raw)
        if len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() == "":
            raise AssertionError("source extent changed")
        return raw

    def create(path, raw):
        with Path(path).open("xb") as out:
            out.write(raw)
        os.chmod(path, 0o644)
        transfer["fixture_write_bytes"] += len(raw)

    def child(argv, expected, source_charge):
        deadline = min(started + 60, time.monotonic() + 10)
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work)
        streams = {"stdout": bytearray(), "stderr": bytearray()}
        selected = selectors.DefaultSelector()
        selected.register(process.stdout, selectors.EVENT_READ, "stdout")
        selected.register(process.stderr, selectors.EVENT_READ, "stderr")
        try:
            while selected.get_map():
                if time.monotonic() >= deadline:
                    process.kill()
                    raise AssertionError("source child deadline")
                for key, _ in selected.select(.1):
                    output = streams[key.data]
                    body = os.read(key.fileobj.fileno(), min(16384, 65537 - len(output)))
                    if not body:
                        selected.unregister(key.fileobj)
                        continue
                    output.extend(body)
                    if len(output) > 65536:
                        process.kill()
                        raise AssertionError("source child stream cap")
            code = process.wait(timeout=1)
        finally:
            selected.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=1)
            process.stdout.close()
            process.stderr.close()
        row = {"argv": argv, "returncode": code, **{k: bytes(v).decode("utf-8") for k, v in streams.items()}}
        children.append(row)
        transfer["child_source_charge"] += source_charge
        transfer["captured_stream_bytes"] += sum(len(v) for v in streams.values())
        check((code == 0) if expected else (code != 0), "child_expected_exit_" + str(len(children)))
        return row

    check(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode, "actual_isolated_no_site_no_bytecode_checker")
    manifest_raw = read(component / "SOURCE_MANIFEST.json")
    manifest = json.loads(manifest_raw)
    entry_raw = read(component / "nlb_entry.py")
    capture_extent = len(manifest_raw) + sum(row["bytes"] for row in manifest["files"])
    check(capture_extent < 2**20 and len(manifest["files"]) == 73, "complete_bounded_payload")
    sidecar = json.loads(read(root / "SOURCE_COMPONENTS.json", 65536))
    check(set(sidecar) == {"schema_version", "task_id", "components"} and sidecar["schema_version"] == 1 and sidecar["task_id"] == "NEURAL-017", "existing_discovery_schema")
    declaration = sidecar["components"][0]
    check(len(sidecar["components"]) == 1 and set(declaration) == {"id", "title", "root", "source_manifest", "readme", "inspection", "scope", "status", "holds"}, "closed_source_component_declaration")
    check(declaration["inspection"] == {"argv": ["{python}", "complete-operator/source_inspection.py", "--inspect"]}, "real_existing_discovery_argv_shape")
    check(declaration["source_manifest"] == {"path": "complete-operator/SOURCE_MANIFEST.json", "bytes": len(manifest_raw), "sha256": hashlib.sha256(manifest_raw).hexdigest()}, "sidecar_actual_manifest_pin")
    inspector = child([sys.executable, "-I", "-S", "-B", str(component / "source_inspection.py"), "--inspect"], True, capture_extent + len(entry_raw) + 65536)
    observed = json.loads(inspector["stdout"])
    check(observed["source_bodies"] == 75 and observed["python_bodies"] == 55 and observed["groups"] == 100 and observed["query_cases"] == 574 and observed["scientific_roles"] == 28844, "actual_complete_source_inspector_scope")
    check(observed["local_module_execution"] is False and observed["self_authentication_claim"] is False and observed["scientific_qualified"] is False, "inspection_is_not_execution_or_authority")
    for route in ("prepare", "campaign"):
        prefix = work / (route + "-cache")
        result = child([sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + str(prefix), str(component / "nlb_entry.py"), route, "--help"], True, capture_extent + len(entry_raw))
        check("usage:" in result["stdout"] and not result["stderr"], "actual_" + route + "_help")
        check(prefix.is_dir() and stat.S_IMODE(prefix.stat().st_mode) == 0o700 and not list(prefix.iterdir()), route + "_owned_empty_prefix")
    prefix = work / "describe-cache"
    described = child([sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + str(prefix), str(component / "nlb_entry.py"), "campaign", "describe"], True, capture_extent + len(entry_raw))
    description = json.loads(described["stdout"])
    check(description["groups"] == 100 and description["F_programmes"] == 50 and description["I_cases"] == 28700 and description["references"] == ["R" + str(i) for i in range(9)] and description["open_scientific_gates"] == 24, "actual_full_campaign_description")
    check(description["authentic_execution_performed"] is False and description["default_deployment_enabled"] is False, "actual_description_keeps_holds")

    # Reuse only the actual trusted entry definitions, without executing main.
    # Actual direct startup is exercised above. This separate step reaches the
    # real finite programme constructor, not a reconstructed roster algorithm.
    marker = b'if __name__ != "__main__":'
    check(entry_raw.count(marker) == 1, "exact_entry_definition_boundary")
    namespace = {"__name__": "selected_source_definitions", "__file__": str(component / "nlb_entry.py")}
    exec(compile(entry_raw.split(marker)[0], str(component / "nlb_entry.py"), "exec", dont_inherit=True), namespace)
    captured, charged = namespace["capture_source"](str(component))
    transfer["source_read_bytes"] += charged
    check(charged == capture_extent and len(captured) == 53, "actual_complete_captured_nlb_source")

    class NoScientificImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            forbidden = ("numpy", "scipy", "sklearn", "pandas", "h5py", "neo", "quantities", "elephant", "openai", "nlb.scientific", "nlb.raw_prepare", "nlb.raw_counts")
            if any(fullname == name or fullname.startswith(name + ".") for name in forbidden):
                raise AssertionError("unselected numerical/native import: " + fullname)
            return None

    blocker = NoScientificImports()
    loader = namespace["install_captured"](captured)
    sys.meta_path.insert(0, blocker)
    try:
        programme = importlib.import_module("nlb.programme")
        groups = programme.expected_groups()
        expected = set(itertools.product(programme.CONDITIONS, ("F", "I"), ("A", "B"), range(1, 6)))
        check(len(groups) == 100 and {(g["condition"], g["mode"], g["code_view"], g["agent_seed"]) for g in groups} == expected and all(g["cases"] == 574 for g in groups), "actual_complete100_group_cross_product")
        jobs = programme.expected_jobs(None)
        check(len(jobs) == 28844, "actual_full28844_role_constructor")
        case_rows = collections.defaultdict(set)
        for name, row in jobs.items():
            if row["role"] == "participant_I_case":
                case_rows[name.rsplit("/", 1)[0]].add(row["case_index"])
        check(len(case_rows) == 50 and all(values == set(range(574)) for values in case_rows.values()), "every_I_group_has_all574_cases")
        check(sum(row["role"] == "participant_F" for row in jobs.values()) == 50 and sum(row["role"] == "reference_predict" for row in jobs.values()) == 31, "all_F_groups_and_reference_bank")
        del jobs, case_rows
        refused = False
        try:
            importlib.import_module("nlb.unlisted_public_fixture")
        except ModuleNotFoundError:
            refused = True
        check(refused, "actual_captured_loader_refuses_unlisted_local_module")
    finally:
        sys.meta_path.remove(loader)
        sys.meta_path.remove(blocker)
        for name in list(sys.modules):
            if name == "nlb" or name.startswith("nlb."):
                del sys.modules[name]

    occupied = work / "occupied-cache"
    create(occupied, b"inert occupied prefix\n")
    before = occupied.stat()
    result = child([sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + str(occupied), str(component / "nlb_entry.py"), "prepare", "--help"], False, len(entry_raw))
    check("FileExistsError" in result["stderr"] and occupied.stat().st_ino == before.st_ino and occupied.read_bytes() == b"inert occupied prefix\n", "existing_prefix_refused_without_overwrite")
    fixture = work / "wrong-manifest"
    fixture.mkdir(mode=0o700)
    create(fixture / "nlb_entry.py", entry_raw)
    wrong = bytearray(manifest_raw)
    wrong[0] = ord("[") if wrong[0] != ord("[") else ord("{")
    create(fixture / "SOURCE_MANIFEST.json", wrong)
    result = child([sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + str(work / "wrong-cache"), str(fixture / "nlb_entry.py"), "prepare", "--help"], False, len(entry_raw) + len(manifest_raw))
    check("selected source SHA-256 mismatch" in result["stderr"], "wrong_manifest_refused_before_payload_import")
    missing = work / "missing-payload"
    missing.mkdir(mode=0o700)
    create(missing / "nlb_entry.py", entry_raw)
    create(missing / "SOURCE_MANIFEST.json", manifest_raw)
    result = child([sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + str(work / "missing-cache"), str(missing / "nlb_entry.py"), "campaign", "--help"], False, len(entry_raw) + len(manifest_raw))
    check("FileNotFoundError" in result["stderr"], "missing_payload_refused_before_import")

    freeze_raw = read(root / "SOURCE_FREEZE.json", 65536)
    freeze = json.loads(freeze_raw)
    for name in ("README.md", "score.py"):
        raw = read(root / name)
        check(freeze["files"][name] == {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, "legacy_freeze_current_" + name)
    public = json.loads(read(root / "manifest.json", 65536))
    check(public["source_freeze_sha256"] == hashlib.sha256(freeze_raw).hexdigest() and public["admission"]["runnable"] is False and public["admission"]["research_qualified"] is False and public["admission"]["submission_ready"] is False, "public_manifest_freeze_and_false_admission")
    score_pin = freeze["files"]["score.py"]["sha256"]
    check(all(public["entrypoints"][name]["sha256"] == score_pin for name in ("score", "validate")), "both_legacy_entrypoint_source_pins")
    legacy = check_legacy_socket(root / "score.py")
    transfer["source_read_bytes"] += legacy["selected_source_bytes"]
    checks.extend("legacy:" + name for name in legacy["checks"])
    scale = 1 if sys.platform == "darwin" else 1024
    parent_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
    child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * scale
    check(parent_peak + child_peak <= 128 * 2**20, "parent_plus_max_sequential_child_peak_below128MiB")
    virtual_role_reservation = 512 * (28844 + 100)
    check(sum(transfer.values()) < 8 * 2**20, "source_logical_transfer_below8MiB")
    check(sum(transfer.values()) + virtual_role_reservation < 24 * 2**20, "source_plus_full_role_transfer_reservation_below24MiB")
    check(time.monotonic() - started < 60, "source_check_below60seconds")
    return {"schema": "NLB017_public_source_check_v1", "status": "PASS", "check_count": len(checks), "checks": checks,
            "children": children, "source_transfer": transfer, "virtual_full_role_transfer_reservation": virtual_role_reservation, "elapsed_seconds": time.monotonic() - started,
            "parent_peak_rss_bytes": parent_peak, "max_sequential_child_peak_rss_bytes": child_peak,
            "peak_sum_is_conservative_upper_bound": True, "work_directory": str(work), "legacy_socket_check": legacy,
            "scientific_or_native_execution": False, "model_or_data_used": False, "qualifications_promoted": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-parent")
    parser.add_argument("--result")
    args = parser.parse_args(argv)
    failure = None
    try:
        result = run_checks(Path(__file__).absolute().parent, args.work_parent)
    except BaseException as error:
        failure = error
        result = {**CURRENT, "status": "FAIL", "check_count": len(CURRENT.get("checks", [])),
                  "error": {"type": type(error).__name__, "message": str(error)[:2048]},
                  "elapsed_seconds": time.monotonic() - CURRENT.get("started", time.monotonic()),
                  "scientific_or_native_execution": False}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if len(raw) > 65536:
        raise AssertionError("bounded source-control result")
    if args.result:
        with Path(args.result).open("xb") as out:
            out.write(raw)
    print(json.dumps({"status": result["status"], "check_count": result["check_count"], "groups": 100,
                      "cases_per_group": 574, "scientific_roles": 28844, "scientific_execution": False,
                      "logical_source_transfer": sum(result["source_transfer"].values()), "elapsed_seconds": result["elapsed_seconds"],
                      "work_directory": result["work_directory"]}, sort_keys=True))
    if failure is not None:
        raise failure
    return 0


# Exact separately authored inert legacy dispatcher check.
"""Inert test of the exact public legacy Docker configuration/dispatcher.

No import of score.py, no call to main(), no real subprocess, filesystem
mutation, Docker, credential discovery, numerical module or data input.
The parent must freeze/admit this source and its finite plan before calling it.
This helper may be integrated into the one public source checker; it does not
require another public package path.
"""
import ast
import hashlib
from pathlib import Path, PurePosixPath
import stat
import time
from types import SimpleNamespace

SCORE_BYTES = 13349
SCORE_SHA256 = "c3f76f241ffe8c5780fb671545520033b1944d4bf6db8f7ccb9f8c19d7cb3631"
SELECTORS = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")


def check_legacy_socket(score_path):
    """Exercise the actual selected statements under explicitly inert leaves."""
    started = time.monotonic()
    path = Path(score_path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != SCORE_BYTES:
        raise AssertionError("exact ordinary single-link selected score source")
    with path.open("rb") as source:
        raw = source.read(SCORE_BYTES + 1)
    after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise AssertionError("source changed during static capture")
    if len(raw) != SCORE_BYTES or hashlib.sha256(raw).hexdigest() != SCORE_SHA256:
        raise AssertionError("selected public score source mismatch")
    checks = ["exact_current_source_identity"]
    tree = ast.parse(raw.decode("utf-8"), filename="selected:score.py")
    main_nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    if len(main_nodes) != 1:
        raise AssertionError("one actual main source definition")
    main = main_nodes[0]
    setup = []
    for node in main.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "env" or
            isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "env"
            for t in node.targets
        ):
            setup.append(node)
    runs = [n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == "run"]
    if len(setup) != 2 or len(runs) != 1:
        raise AssertionError("exact environment setup and one actual nested dispatcher")
    run = runs[0]
    calls = [n for n in ast.walk(run) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "subprocess" and n.func.attr == "run"]
    if len(calls) != 1:
        raise AssertionError("sole subprocess dispatcher")
    checks.append("actual_configuration_and_dispatch_source_selected")

    original_environment = {key: "inert-unselected-" + key for key in SELECTORS}
    original_environment.update({"DOCKER_CONFIG": "/inert-unselected-config", "PATH": "/inert/bin", "LANG": "C"})
    preserved_environment = dict(original_environment)
    fake_clock = SimpleNamespace(value=100.0)
    fake_clock.monotonic = lambda: fake_clock.value
    invocation_log = []
    response = SimpleNamespace(returncode=0, stdout="inert", stderr="")

    def inert_subprocess_run(argv, **kwargs):
        invocation_log.append({"argv": list(argv), "kwargs": dict(kwargs)})
        return response

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    namespace = {
        "__builtins__": {"str": str, "min": min, "len": len},
        "os": SimpleNamespace(environ=original_environment),
        "ROOT": PurePosixPath("/inert-selected-root"),
        "time": fake_clock,
        "subprocess": SimpleNamespace(run=inert_subprocess_run),
        "require": require,
        "docker": "/usr/local/bin/docker",
        "commands": [],
        "work_deadline": 148.0,
        "final_deadline": 159.0,
    }
    # Compile only the exact selected setup and existing dispatcher. No module
    # import, global initialization, main lifecycle or other scientific leaf runs.
    selected = ast.fix_missing_locations(ast.Module(body=[*setup, run], type_ignores=[]))
    exec(compile(selected, "inert:selected-score-statements", "exec", dont_inherit=True), namespace)
    actual_env = namespace["env"]
    if any(key in actual_env for key in SELECTORS):
        raise AssertionError("ambient Docker endpoint/context/TLS selector survived")
    checks.append("all_five_ambient_selectors_removed")
    if actual_env.get("DOCKER_CONFIG") != "/inert-selected-root/.cache-build/docker-config":
        raise AssertionError("explicit task-local Docker config changed")
    checks.append("explicit_task_local_config_preserved")
    if actual_env.get("PATH") != "/inert/bin" or actual_env.get("LANG") != "C":
        raise AssertionError("unrelated execution environment changed")
    checks.append("unrelated_environment_preserved")
    if original_environment != preserved_environment or actual_env is original_environment:
        raise AssertionError("caller environment mutated instead of copied")
    checks.append("caller_environment_unchanged")

    operations = [
        ["inspect", "--type", "container", "inert-container"],
        ["create", "--name", "inert-container"],
        ["start", "inert-container"],
        ["wait", "inert-container"],
        ["logs", "inert-container"],
        ["rm", "--force", "inert-container"],
    ]
    for operation in operations:
        cleanup = operation[0] == "rm"
        result = namespace["run"](operation, cleanup=cleanup)
        observed = invocation_log[-1]
        if result is not response or observed["argv"] != ["/usr/local/bin/docker", "--host", "unix:///var/run/docker.sock", *operation]:
            raise AssertionError("actual operation did not use fixed local host")
        if observed["kwargs"] != {"env": actual_env, "capture_output": True, "text": True, "timeout": 5 if cleanup else 40}:
            raise AssertionError("original execution arguments or deadline behavior changed")
        checks.append("fixed_dispatch_" + operation[0])
    if namespace["commands"] != operations or len(invocation_log) != len(operations):
        raise AssertionError("original command ledger changed")
    checks.append("original_command_ledger_preserved")
    fake_clock.value = 200.0
    refused = False
    try:
        namespace["run"](["inspect", "late-inert-container"])
    except ValueError as error:
        refused = str(error) == "Whole-stage deadline"
    if not refused or len(invocation_log) != len(operations) or namespace["commands"] != operations:
        raise AssertionError("late operation reached inert subprocess or modified ledger")
    checks.append("original_deadline_refuses_before_dispatch")
    if time.monotonic() - started > 3.0:
        raise AssertionError("selected three-second inert-check bound exceeded")
    return {
        "schema": "neural017_legacy_socket_inert_check_v1",
        "checks": checks,
        "check_count": len(checks),
        "fixed_endpoint": "unix:///var/run/docker.sock",
        "inert_dispatch_count": len(invocation_log),
        "selected_source_bytes": len(raw),
        "actual_subprocess_invoked": False,
        "candidate_main_imported_or_called": False,
        "native_or_scientific_execution": False,
        "qualification_claim": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
