"""Ordinary-source checks only; no data, numerical dependency or scientific run."""
import argparse
import builtins
import hashlib
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

ENTRY_PIN = {'bytes': 29760, 'sha256': 'af966c48ee2c84de0ed9b410d3ebe7d88856bfc9ede072a6724c543aa587e7f1'}
MANIFEST_PIN = {'bytes': 2439, 'sha256': '6188e5b0becb3140ac48f0510855e9487c18fb2d20804fe52330ed2a3ce59dc3'}
STATE = {}


def digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def run(task_root, work_parent=None):
    started = time.monotonic()
    root = Path(task_root).absolute()
    source = root / "preparation/source"
    parent = Path(work_parent or tempfile.gettempdir()).resolve()
    work = Path(tempfile.mkdtemp(prefix="neural083-source-", dir=parent))
    os.chmod(work, 0o700)
    checks, children = [], []
    charge = {"source": 0, "child_source_reservation": 0, "fixture_write": 0, "streams": 0}
    STATE.update(checks=checks, children=children, charge=charge, work_directory=str(work))

    def check(ok, name):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    def read(path, cap=100000):
        s = path.lstat()
        check(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and 0 < s.st_size <= cap, "ordinary_source:" + path.name)
        with path.open("rb") as handle:
            raw = handle.read(cap + 1)
        charge["source"] += len(raw)
        check(len(raw) == s.st_size, "complete_source:" + path.name)
        return raw

    def write(path, raw):
        with path.open("xb") as handle:
            handle.write(raw)
        os.chmod(path, 0o644)
        charge["fixture_write"] += len(raw)

    def child(entry, prefix, arguments, success):
        argv = [sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + str(prefix), str(entry), *arguments]
        # The fixed source reader admits at most100,000 captured bytes, plus
        # the externally trusted entry (at most65,536). No data is selected.
        charge["child_source_reservation"] += 165536
        deadline = min(started + 20, time.monotonic() + 5)
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work)
        selector = selectors.DefaultSelector()
        streams = {"stdout": bytearray(), "stderr": bytearray()}
        error = None
        for key in streams:
            selector.register(getattr(p, key), selectors.EVENT_READ, key)
        try:
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise AssertionError("bounded ordinary child deadline")
                for key, _ in selector.select(.1):
                    left = 8192 - len(streams[key.data])
                    if left <= 0:
                        raise AssertionError("bounded ordinary child stream")
                    body = os.read(key.fileobj.fileno(), min(left, 4096))
                    if body:
                        streams[key.data].extend(body)
                    else:
                        selector.unregister(key.fileobj)
            code = p.wait(timeout=1)
        except BaseException as exc:
            error = exc
            p.kill()
            code = p.wait(timeout=1)
        finally:
            selector.close()
            p.stdout.close()
            p.stderr.close()
        charge["streams"] += sum(map(len, streams.values()))
        observation = {"argv": argv, "returncode": code, **{k: bytes(v).decode() for k, v in streams.items()}, "error": None if error is None else repr(error)}
        children.append(observation)
        if error is not None:
            raise error
        check((code == 0) if success else (code != 0), "actual_child_exit:" + str(len(children)))
        return observation

    check(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode, "isolated_no_site_no_bytecode")
    entry = read(source / "prepare_entry.py")
    manifest = read(source / "SOURCES.json")
    check(digest(entry) == ENTRY_PIN and digest(manifest) == MANIFEST_PIN, "externally_selected_source_identities")
    table = json.loads(manifest)
    check(table["schema"] == "neural083_preparation_sources_v1" and len(table["files"]) == 10, "complete_ten_source_manifest")
    for name, expected in table["files"].items():
        raw = read(source / name)
        check(digest(raw) == {k: expected[k] for k in ("bytes", "sha256")}, "exact_dependency:" + name)
        check("authoring/" not in expected["origin"], "public_origin:" + name)

    inspected = child(source / "prepare_entry.py", work / "inspect-cache", ["inspect"], True)
    observed = json.loads(inspected["stdout"])
    check(observed["original_source_members"] == 10 and observed["records"] == 108 and observed["people"] == 54 and observed["sessions"] == 2 and observed["combined_conditions"] == 2592, "actual_inspect_full_scope")
    check(observed["scientific_execution"] is False and observed["source_identity"] == {"original_manifest": MANIFEST_PIN, "entry": ENTRY_PIN}, "actual_inspect_identity_and_no_science")
    check(not inspected["stderr"] and not (work / "inspect-cache").exists(), "inspect_prefix_remains_absent")
    help_result = child(source / "prepare_entry.py", work / "help-cache", ["--help"], True)
    check("plan-project" in help_result["stdout"] and "plan-finalize" in help_result["stdout"] and not (work / "help-cache").exists(), "actual_direct_help_and_absent_cache")

    real_import = builtins.__import__
    forbidden = {"numpy", "scipy", "torch", "pandas", "h5py", "openai", "sklearn", "mne"}

    def source_only_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".")[0] in forbidden:
            raise AssertionError("Unselected scientific dependency: " + name)
        return real_import(name, globals, locals, fromlist, level)

    check(not forbidden.intersection(sys.modules), "no_preloaded_scientific_dependency")
    namespace = {"__name__": "selected_neural083_source", "__file__": str(source / "prepare_entry.py")}
    builtins.__import__ = source_only_import
    try:
        exec(compile(entry, str(source / "prepare_entry.py"), "exec", dont_inherit=True), namespace)
        check(namespace["ROSTER"] == tuple((p, s) for p in range(1, 55) for s in (1, 2)), "actual_complete108_source_roster")
        bodies, captured, identity = namespace["source_capture"](source)
        charge["source"] += captured
        budget = namespace["Budget"]({"read_bytes": 1048576, "write_bytes": 1048576, "retained_bytes": 1048576}, time.monotonic_ns() + 10_000_000_000)
        libraries = namespace["Libraries"](source, bodies, budget, identity)
        check(libraries.modules["array_io"].loaded is None, "actual_captured_graph_keeps_array_module_lazy")
        check(libraries.index.c is libraries.common and libraries.store.c is libraries.common and libraries.index.contracts is libraries.contracts and libraries.store.contracts is libraries.contracts, "actual_common_contracts_injections")
        check(libraries.index.scientific is libraries.modules["protocol"] and libraries.store.scientific is libraries.modules["protocol"], "actual_protocol_injections")
        cases = [{"case": "case_" + format(i, "024x")} for i in range(108)]
        rows = list(libraries.contracts.schedule({"cases": cases}))
        expected = {(panel, case["case"], setting, arm) for panel in ("candidate", "reference") for case in cases for setting in ("target20", "transfer0", "target100", "other_session20") for arm in ("EEG", "CONTEXT", "PERMUTED_EEG")}
        check(len(rows) == 2592 and {(v["panel"], v["case"], v["setting"], v["arm"]) for v in rows} == expected and [v["ordinal"] for v in rows] == list(range(2592)), "actual_full2592_schedule_on_invented_case_names")
        check(libraries.modules["array_io"].loaded is None and not forbidden.intersection(sys.modules), "no_scientific_leaf_for_source_graph_or_schedule")
        del rows, expected, cases, libraries, bodies
    finally:
        builtins.__import__ = real_import

    occupied = work / "occupied-cache"
    write(occupied, b"inert occupied cache prefix\n")
    before = occupied.stat()
    refused = child(source / "prepare_entry.py", occupied, ["inspect"], False)
    check("Fresh absent cache prefix" in refused["stderr"] and occupied.stat().st_ino == before.st_ino, "actual_existing_prefix_refused_without_overwrite")
    wrong = work / "wrong-source"
    wrong.mkdir(mode=0o700)
    write(wrong / "prepare_entry.py", entry)
    changed = bytearray(manifest)
    changed[0] = ord("[")
    write(wrong / "SOURCES.json", changed)
    refused = child(wrong / "prepare_entry.py", work / "wrong-cache", ["inspect"], False)
    check("Stable exact complete body" in refused["stderr"] and not (work / "wrong-cache").exists(), "actual_manifest_pin_refusal_before_local_interpretation")
    missing = work / "missing-source"
    missing.mkdir(mode=0o700)
    write(missing / "prepare_entry.py", entry)
    write(missing / "SOURCES.json", manifest)
    refused = child(missing / "prepare_entry.py", work / "missing-cache", ["inspect"], False)
    check("FileNotFoundError" in refused["stderr"] and not (work / "missing-cache").exists(), "actual_missing_dependency_refusal")
    refused = child(source / "prepare_entry.py", work / "request-cache", ["plan-project"], False)
    check("Pinned explicit operation request" in refused["stderr"] and not (work / "request-cache").exists(), "actual_operation_refuses_without_explicit_external_request")
    scale = 1 if sys.platform == "darwin" else 1024
    parent_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
    child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * scale
    virtual = 512 * (2592 + 108)
    check(sum(charge.values()) + virtual <= 4 * 2**20, "logical_source_and_virtual_metadata_below4MiB")
    check(parent_peak + child_peak <= 96 * 2**20, "parent_plus_max_child_upper_bound_below96MiB")
    check(time.monotonic() - started < 20, "source_checks_below20seconds")
    return {**STATE, "status": "PASS", "check_count": len(checks), "virtual_metadata_reservation": virtual, "elapsed_seconds": time.monotonic() - started, "parent_peak_bytes": parent_peak, "max_sequential_child_peak_bytes": child_peak, "peak_sum_is_upper_bound": True, "authentic_data_or_headers_opened": False, "scientific_native_model_execution": False, "qualification_delta": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-parent")
    parser.add_argument("--result")
    args = parser.parse_args()
    failure = None
    try:
        result = run(Path(__file__).absolute().parent, args.work_parent)
    except BaseException as error:
        failure = error
        result = {**STATE, "status": "FAIL", "check_count": len(STATE.get("checks", [])), "error": {"type": type(error).__name__, "message": str(error)}, "scientific_native_model_execution": False}
    body = (json.dumps(result, indent=2) + "\n").encode()
    if len(body) > 65536:
        raise AssertionError("bounded source-check record")
    if args.result:
        with Path(args.result).open("xb") as handle:
            handle.write(body)
    print(json.dumps({k: result[k] for k in ("status", "check_count", "work_directory")}))
    if failure is not None:
        raise failure


if __name__ == "__main__":
    main()
