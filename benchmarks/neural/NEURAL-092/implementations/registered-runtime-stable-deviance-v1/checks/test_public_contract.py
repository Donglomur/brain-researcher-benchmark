"""Portable POSIX checks of the inactive NEURAL-092 public boundary.

Run with -I -S -B. This suite opens source metadata and one generated Python
package only. It issues no Selection and imports no scientific-data libraries.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

NAMESPACES = ("gain", "host092", "prospective", "source")
CONTROL_IDS = (
    "inert_import", "cli_inspection", "cli_no_selection",
    "cli_exclusive_modes", "unissued_selection_shadow_precedence",
    "unselected_import_cleanup",
)
FIXTURE_BODY = b'raise AssertionError("unselected shadow package executed")\n'
MAX_REPORT_BYTES = 8192
CHILD_OUTPUT_ACCEPTANCE_BYTES = 8192


def require(value, message):
    if not value:
        raise AssertionError(message)


def programme_modules():
    return {name for name in sys.modules
            if any(name == prefix or name.startswith(prefix + ".")
                   for prefix in NAMESPACES)}


def refuses(callback, exception_type, message):
    try:
        callback()
    except exception_type as error:
        require(message in str(error), "different refusal: " + str(error)[:256])
        return
    raise AssertionError("expected " + exception_type.__name__ + ": " + message)


@contextmanager
def observe_calls(functions):
    """Observe real functions without replacing their bodies or dependencies."""
    names = {function.__code__: name for name, function in functions.items()}
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "call" and frame.f_code in names:
            calls.append(names[frame.f_code])

    require(previous is None, "isolated suite requires no existing profiler")
    sys.setprofile(profile)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def run_controls(runtime, work, results):
    require(os.name == "posix", "POSIX source-reader contract required")
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "launch with -I -S -B")
    require(not programme_modules(), "isolated programme namespace required")
    require(not work.exists(), "fresh generated work directory required")
    work.mkdir()
    fixture = work / "shadow" / "prospective" / "__init__.py"
    fixture.parent.mkdir(parents=True)
    with fixture.open("xb") as stream:
        stream.write(FIXTURE_BODY)

    entry = runtime / "operator.py"
    spec = importlib.util.spec_from_file_location("_neural092_public_operator", entry)
    require(spec is not None and spec.loader is not None, "real operator import")
    central = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(central)
    require(not programme_modules(), "central import executed programme imports")
    require(not any(name in sys.modules for name in ("numpy", "h5py")),
            "scientific dependency imported")
    results.append({"id": CONTROL_IDS[0], "status": "passed"})

    def cli(*args):
        # Each real CLI has one finite metadata/error response in the pinned
        # source. Captures stay in memory; only this suite's bounded report is
        # logged. The threshold is checked after collection, not a capture/RSS
        # limit. The enclosing CI runner owns the overall process deadline.
        child = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(entry), *args],
            cwd=work, capture_output=True, timeout=20, check=False,
        )
        require(len(child.stdout) + len(child.stderr) <= CHILD_OUTPUT_ACCEPTANCE_BYTES,
                "CLI output exceeds selected response bound")
        return child

    inspected = cli("--inspect")
    require(inspected.returncode == 0 and not inspected.stderr, "inspect CLI failed")
    definition = json.loads(inspected.stdout)
    require(definition["id"] == "NEURAL-092" and
            definition["source_roles"] == 50 and
            definition["source_bytes"] == 254609 and
            definition["api_modules"] == 39 and definition["contracts"] == 4,
            "complete selected public source graph")
    require(all(definition[key] is False for key in (
        "source_complete", "runnable", "research_qualified", "scientific_execution")),
        "inactive flags changed")
    require(definition["run"] is None and definition["score"] is None,
            "generic entrypoint was activated")
    results.append({"id": CONTROL_IDS[1], "status": "passed"})

    unselected = cli("--run")
    require(unselected.returncode != 0 and not unselected.stdout and
            b"InactiveSource: No genuine original live Selection supplied." in unselected.stderr,
            "CLI run did not preserve explicit inactive refusal")
    results.append({"id": CONTROL_IDS[2], "status": "passed"})

    conflicting = cli("--inspect", "--run")
    require(conflicting.returncode == 2 and not conflicting.stdout and
            b"not allowed with argument" in conflicting.stderr,
            "CLI mutually exclusive modes were accepted")
    results.append({"id": CONTROL_IDS[3], "status": "passed"})

    # This real regular package is deliberately earlier on sys.path. The actual
    # selected finder must bind the initializer-free prospective namespace
    # before Python could execute this package's raising initializer.
    before_path = list(sys.path)
    before_meta = list(sys.meta_path)
    sys.path.insert(0, str(work / "shadow"))
    shadow_path = list(sys.path)
    try:
        with central._source_graph(definition) as (admission, operator, unused):
            prospective = importlib.import_module("prospective")
            require(prospective.__spec__.origin is None and
                    list(prospective.__path__) == [str(runtime / "programme/prospective")],
                    "unselected shadow package won source resolution")
            require(len(admission._SELECTIONS) == 0, "unexpected issued selection")
            selection = admission.Selection()  # Real class, deliberately unissued.
            path_inside = list(sys.path)
            meta_inside = list(sys.meta_path)
            with observe_calls({"issuer": admission.load_selection,
                                "native_operator": operator.execute}) as calls:
                refuses(lambda: central.main(["--run"], selection=selection),
                        RuntimeError, "original root selection capture required")
            require(calls == [], "refused object reached issuer or native operator")
            require(len(admission._SELECTIONS) == 0, "refusal issued registry authority")
            require(sys.path == path_inside and sys.meta_path == meta_inside,
                    "nested public failure did not restore import context")
        require(sys.path == shadow_path and sys.meta_path == before_meta,
                "source context did not restore caller search policy")
    finally:
        sys.path[:] = before_path
        sys.meta_path[:] = before_meta
    require(not any(name in sys.modules for name in ("numpy", "h5py")),
            "refusal imported scientific dependencies")
    results.append({"id": CONTROL_IDS[4], "status": "passed"})

    prior_path = list(sys.path)
    prior_meta = list(sys.meta_path)

    def missing_import():
        with central._source_graph(definition):
            importlib.import_module("prospective.unselected_public_control")

    refuses(missing_import, ModuleNotFoundError,
            "unselected programme module: prospective.unselected_public_control")
    require(sys.path == prior_path and sys.meta_path == prior_meta,
            "failed selected import did not restore caller context")
    require("prospective.unselected_public_control" not in sys.modules,
            "failed import published an unselected module")
    require(len(admission._SELECTIONS) == 0, "failed import issued authority")
    require(not list(work.rglob("__pycache__")), "generated bytecode write")
    require(fixture.read_bytes() == FIXTURE_BODY, "generated fixture changed")
    results.append({"id": CONTROL_IDS[5], "status": "passed"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--work-root", type=Path, required=True,
                        help="Fresh owned generated-fixture directory")
    parser.add_argument("--report", type=Path,
                        help="Optional fresh bounded JSON report")
    args = parser.parse_args()
    results = []
    report = {
        "schema": "neural092_public_boundary_controls_v1",
        "interpreter": sys.executable, "python_version": sys.version,
        "platform": sys.platform,
        "scope": "POSIX stdlib source/import/CLI refusals only",
        "controls": results, "scientific_execution": False,
        "selection_issued": False, "authentic_data": False,
        "readiness_promoted": False, "numerical_calls": 0,
        "fixture_bytes": len(FIXTURE_BODY),
        "fixture_sha256": hashlib.sha256(FIXTURE_BODY).hexdigest(),
    }
    try:
        run_controls(args.runtime_root.resolve(), args.work_root.resolve(), results)
        require(tuple(row["id"] for row in results) == CONTROL_IDS,
                "all six selected public boundaries required")
        report["status"] = "passed"
    except BaseException as error:
        report["status"] = "failed"
        report["failure"] = {"type": type(error).__name__, "message": str(error)[:1024]}
    body = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    require(len(body) <= MAX_REPORT_BYTES, "bounded public report")
    if args.report is not None:
        with args.report.open("xb") as stream:
            stream.write(body)
    sys.stdout.buffer.write(body)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

