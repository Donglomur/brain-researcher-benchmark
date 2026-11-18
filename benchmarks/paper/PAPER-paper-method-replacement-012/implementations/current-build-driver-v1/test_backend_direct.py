"""Generated controls for the build driver; no real backend or wheel build.

All backend artifacts are explicitly invented plain bytes bearing a .whl name,
not installable wheels. Requirement doubles do not qualify the real parser.
"""
from __future__ import annotations
import argparse
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nuclr_backend_under_test", HERE / "backend_direct.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
FIXTURES = None
WRITTEN = 0
CASE = 0
FIXTURE_CUMULATIVE_LIMIT = 32768

def put(path, body):
    global WRITTEN
    if isinstance(body, str):
        body = body.encode()
    if WRITTEN + len(body) > FIXTURE_CUMULATIVE_LIMIT:
        raise RuntimeError("Generated fixture cumulative bound exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    WRITTEN += len(body)
    return path

def fresh_case():
    global CASE
    CASE += 1
    root = FIXTURES / f"case-{CASE:03d}"
    root.mkdir()
    source = root / "source"
    source.mkdir()
    out = root / "out"
    out.mkdir()
    member = put(source / "setup.py", b"# Invented source fixture, never executed.\n")
    pin = {"path": "setup.py", **driver.descriptor(member), "mode": stat.S_IMODE(member.stat().st_mode)}
    profile = {
        "schema": "nuclr-backend-profile/v1",
        "driver": driver.descriptor(HERE / "backend_direct.py"),
        "interpreter": {"path": str(member), "resolved_path": str(member), **driver.descriptor(member)},
        "condition": driver.CONDITION,
        "project": "temporaldata",
        "source_identity": driver.SOURCES["temporaldata"],
        "backend": "setuptools.build_meta",
        "backend_config_settings": None,
        "build_distributions": {"setuptools": "80.9.0"},
        "python": {"implementation": "CPython", "version": "3.11.18", "system": "Linux", "machine": "x86_64"},
        "max_seconds": 120,
        "max_log_bytes": driver.MAX_LOG,
        "max_wheel_bytes": driver.MAX_WHEEL,
        "hook_requirement_pins": {"setuptools>=80": {"name": "setuptools", "version": "80.9.0", "extras": []}},
        "source_root": str(source),
        "source_files": [pin],
        "environment_root": str(root / "invented-environment-never-imported"),
        "backend_module": {"path": "invented-backend-not-imported.py"},
        "requirement_parser_module": {"path": "invented-parser-not-imported.py"},
    }
    return root, out, member, profile

class RequirementDouble:
    """Minimal fixed generated semantic oracle, not a packaging parser."""
    def __init__(self, literal):
        if literal not in ("setuptools>=80", "setuptools>=81", "setuptools @ https://invalid.invalid/example"):
            raise ValueError("Unrecognized generated requirement")
        self.name = "setuptools"
        self.extras = set()
        self.url = "https://invalid.invalid/example" if " @ " in literal else None
        self.marker = None
        minimum = 81 if ">=81" in literal else 80
        class SpecifierDouble:
            def contains(self, version, prereleases):
                if prereleases is not True:
                    raise AssertionError("Driver omitted explicit prerelease policy")
                return int(version.split(".")[0]) >= minimum
        self.specifier = SpecifierDouble()

class BackendDouble:
    def __init__(self, member, *, requirements=None, mutation=None, output="normal"):
        self.member = member
        self.requirements = ["setuptools>=80"] if requirements is None else requirements
        self.mutation = mutation
        self.output = output
        self.calls = []
    def get_requires_for_build_wheel(self, config_settings):
        self.calls.append(("requires", config_settings))
        if self.mutation == "requires":
            put(self.member, b"# Invented changed source at requirement hook.\n")
        return self.requirements
    def build_wheel(self, destination, config_settings, metadata_directory):
        self.calls.append(("build", config_settings, metadata_directory))
        if self.mutation == "build":
            put(self.member, b"# Invented changed source at build hook.\n")
        path = Path(destination)
        if self.output == "unsafe":
            return "../escape.whl"
        if self.output == "symlink":
            (path / "generated.whl").symlink_to(self.member)
        else:
            put(path / "generated.whl", b"INVENTED; NOT AN INSTALLABLE WHEEL.\n")
        if self.output == "multiple":
            put(path / "extra.whl", b"INVENTED SECOND OUTPUT\n")
        return "generated.whl"

class BackendControls(unittest.TestCase):
    def call_core(self, profile, out, backend):
        stage = {"original_runtime_qualified": False, "scientific_result": False}
        result = driver.build_core(backend, RequirementDouble, profile, dict(driver.BUILD_BASE), out, stage)
        return result

    def test_hook_order_literal_requirements_and_unqualified_artifact(self):
        _, out, member, profile = fresh_case()
        backend = BackendDouble(member)
        result = self.call_core(profile, out, backend)
        self.assertEqual(backend.calls, [("requires", None), ("build", None, None)])
        self.assertEqual(result["literal_hook_requires"], ["setuptools>=80"])
        self.assertEqual(result["requirement_decisions"], [{"literal": "setuptools>=80", "active": True, "name": "setuptools", "version": "80.9.0", "extras": []}])
        self.assertEqual(result["source_pre"], result["source_after_requirements"])
        self.assertEqual(result["source_pre"], result["source_post"])
        self.assertEqual(result["wheel"], {"name": "generated.whl", **driver.descriptor(out / "wheels" / "generated.whl")})
        self.assertEqual(result["status"], "backend_completed_uninstalled_unqualified")
        self.assertIs(result["original_runtime_qualified"], False)
        self.assertIs(result["scientific_result"], False)

    def test_unknown_or_malformed_requirement_stops_before_build(self):
        for value in (["never-admitted>=1"], "setuptools>=80", [3]):
            with self.subTest(value=value):
                _, out, member, profile = fresh_case()
                backend = BackendDouble(member, requirements=value)
                with self.assertRaises(driver.Refusal):
                    self.call_core(profile, out, backend)
                self.assertEqual(backend.calls, [("requires", None)])
                self.assertFalse((out / "wheels").exists())

    def test_unsatisfied_or_direct_url_requirement_stops_before_build(self):
        for literal in ("setuptools>=81", "setuptools @ https://invalid.invalid/example"):
            with self.subTest(literal=literal):
                _, out, member, profile = fresh_case()
                profile["hook_requirement_pins"] = {literal: {"name": "setuptools", "version": "80.9.0", "extras": []}}
                backend = BackendDouble(member, requirements=[literal])
                with self.assertRaises(driver.Refusal):
                    self.call_core(profile, out, backend)
                self.assertEqual(backend.calls, [("requires", None)])
                self.assertFalse((out / "wheels").exists())

    def test_missing_or_wrong_installed_requirement_is_refused(self):
        _, _, _, profile = fresh_case()
        for installed in ({}, {"setuptools": "80.8.0"}):
            with self.subTest(installed=installed):
                with self.assertRaises(driver.Refusal):
                    driver.admit_requirements(["setuptools>=80"], profile["hook_requirement_pins"], installed, RequirementDouble)

    def test_original_source_mutation_at_either_hook_is_refused(self):
        for mutation in ("requires", "build"):
            with self.subTest(mutation=mutation):
                _, out, member, profile = fresh_case()
                backend = BackendDouble(member, mutation=mutation)
                with self.assertRaisesRegex(driver.Refusal, "Source changed"):
                    self.call_core(profile, out, backend)
                self.assertEqual(len(backend.calls), 1 if mutation == "requires" else 2)

    def test_unsafe_multiple_symlink_and_oversized_outputs_are_refused(self):
        for output in ("unsafe", "multiple", "symlink", "oversized"):
            with self.subTest(output=output):
                _, out, member, profile = fresh_case()
                if output == "oversized":
                    profile["max_wheel_bytes"] = 1
                backend = BackendDouble(member, output=output)
                with self.assertRaises(driver.Refusal):
                    self.call_core(profile, out, backend)
                self.assertEqual(len(backend.calls), 2)

    def test_existing_output_directory_is_not_overwritten(self):
        _, out, member, profile = fresh_case()
        wheels = out / "wheels"
        wheels.mkdir()
        sentinel = put(wheels / "already-owned.txt", b"KEEP\n")
        backend = BackendDouble(member)
        with self.assertRaises(FileExistsError):
            self.call_core(profile, out, backend)
        self.assertEqual(sentinel.read_bytes(), b"KEEP\n")
        self.assertEqual(backend.calls, [("requires", None)])

    def test_source_roster_duplicate_mode_path_and_symlink_rejected(self):
        root, _, member, profile = fresh_case()
        rows = profile["source_files"]
        with self.assertRaisesRegex(driver.Refusal, "Duplicate"):
            driver.verify_members(profile["source_root"], rows * 2)
        wrong = copy.deepcopy(rows); wrong[0]["mode"] ^= stat.S_IXUSR
        with self.assertRaisesRegex(driver.Refusal, "mode"):
            driver.verify_members(profile["source_root"], wrong)
        for relative in ("../setup.py", "/absolute", "a//b", "a\\b"):
            with self.subTest(relative=relative):
                with self.assertRaises(driver.Refusal):
                    driver.safe_child(root, relative)
        (root / "alias").symlink_to(member)
        with self.assertRaisesRegex(driver.Refusal, "Symlink"):
            driver.safe_child(root, "alias")

    def test_profile_rejects_unselected_versions_backend_and_incomplete_git_context(self):
        _, _, _, profile = fresh_case()
        self.assertIs(driver.validate_profile(profile), profile)
        for key, value in (("project", "other"), ("source_identity", "0" * 40), ("backend", "different.backend"), ("build_distributions", {"setuptools": "68.2.2"}), ("max_seconds", 121)):
            with self.subTest(key=key):
                wrong = copy.deepcopy(profile); wrong[key] = value
                with self.assertRaises(driver.Refusal):
                    driver.validate_profile(wrong)
        wrong = copy.deepcopy(profile); wrong["python"]["version"] = "3.11.6"
        with self.assertRaisesRegex(driver.Refusal, "CPU runtime"):
            driver.validate_profile(wrong)
        wrong = copy.deepcopy(profile)
        wrong.update(project="brainsets", source_identity=driver.SOURCES["brainsets"], build_distributions={**driver.BUILD_BASE, **driver.BRAINSETS_EXTRA})
        with self.assertRaisesRegex(driver.Refusal, "brainsets context"):
            driver.validate_profile(wrong)
        wrong["brainsets_context"] = {"commit": driver.SOURCES["brainsets"], "root_tree": "2ded1667f32794d5fc83ec93d75c558272bc9a10", "tracked_blobs": 98}
        with self.assertRaisesRegex(driver.Refusal, "source roster"):
            driver.validate_profile(wrong)

    def test_admission_requires_selection_matching_profile_and_unchanged_evidence(self):
        root, _, _, profile = fresh_case()
        evidence = put(root / "invented-evidence.json", '{"scope":"generated only"}\n')
        row = {"path": str(evidence), **driver.descriptor(evidence)}
        pin = {"bytes": 10, "sha256": "1" * 64}
        admission = {"schema": "nuclr-build-sandbox-admission/v1", "condition": driver.CONDITION, "project": "temporaldata", "profile": pin, "selected_execution": True, "source_materialization_verified": True, "installed_build_environment_verified": True, "source_evidence": row, "environment_evidence": row, "os_isolation_evidence": row}
        self.assertIs(driver.authenticate_admission(profile, pin, admission), admission)
        for key in ("selected_execution", "source_materialization_verified", "installed_build_environment_verified"):
            wrong = copy.deepcopy(admission); wrong[key] = False
            with self.subTest(key=key), self.assertRaises(driver.Refusal):
                driver.authenticate_admission(profile, pin, wrong)
        wrong = copy.deepcopy(admission); wrong["profile"]["sha256"] = "2" * 64
        with self.assertRaisesRegex(driver.Refusal, "profile mismatch"):
            driver.authenticate_admission(profile, pin, wrong)
        put(evidence, '{"scope":"changed generated evidence"}\n')
        with self.assertRaisesRegex(driver.Refusal, "evidence changed"):
            driver.authenticate_admission(profile, pin, admission)

    def run_child(self, code, seconds=7, limit=1024, *, allow_empty_log=False):
        global WRITTEN
        root, _, _, _ = fresh_case()
        log = root / "owned-child.log"
        result = driver.run_owned([sys.executable, "-I", "-S", "-B", "-c", code], str(root), {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, log, seconds, limit)
        WRITTEN += result["output_bytes"]
        self.assertLessEqual(WRITTEN, FIXTURE_CUMULATIVE_LIMIT)
        text = log.read_text()
        pid = result["pid"]
        if text:
            self.assertEqual(int(text.splitlines()[0]), pid)
        else:
            self.assertTrue(allow_empty_log, "Only cancellation may interrupt before pipe drain")
        self.assertIs(result["leader_reaped"], True)
        self.assertIsNone(result["cleanup_error"])
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        with self.assertRaises(ProcessLookupError):
            os.killpg(pid, 0)
        self.assertEqual(result["log"], driver.descriptor(log, limit + 1))
        return result, text

    def test_owned_child_nonzero_exit_is_preserved_and_reaped(self):
        result, _ = self.run_child("import os; print(os.getpid(), flush=True); os._exit(7)")
        self.assertEqual(result["exit_code"], 7)
        self.assertIsNone(result["error"])

    def test_owned_child_timeout_is_recorded_and_reaped(self):
        result, _ = self.run_child("import os,time; print(os.getpid(), flush=True); time.sleep(10)", seconds=5.25)
        self.assertIsNotNone(result["error"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertLess(result["wall_seconds"], 5)

    def test_owned_child_output_cap_records_partial_and_reaps(self):
        result, _ = self.run_child("import os; print(os.getpid(), flush=True); os.write(1,b'x'*128)", limit=32)
        self.assertIn("extent", result["error"])
        self.assertEqual(result["output_bytes"], 33)


    def test_owned_parent_term_cancels_and_reaps_only_owned_child(self):
        # Parent handlers are installed before Popen; the owned child cannot
        # signal this test outside run_owned's guarded cancellation window.
        result, _ = self.run_child(
            "import os,signal,time; print(os.getpid(), flush=True); os.kill(os.getppid(), signal.SIGTERM); time.sleep(10)",
            allow_empty_log=True,
        )
        self.assertIn("signal", result["error"])
        self.assertNotEqual(result["exit_code"], 0)

    def test_final_group_signal_precedes_first_reap(self):
        events = []
        root, _, _, _ = fresh_case()
        class StreamDouble:
            def close(self):
                events.append("close")
        class ProcessDouble:
            pid = 424242
            returncode = 0
            stdout = StreamDouble()
            def wait(self, timeout):
                events.append("wait")
                return 0
        class SelectorDouble:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def register(self, *args):
                pass
            def get_map(self):
                return {}
        def kill_group(pid, sig):
            self.assertEqual(pid, 424242)
            events.append("term" if sig == signal.SIGTERM else "kill")
        with mock.patch.object(driver.subprocess, "Popen", return_value=ProcessDouble()), mock.patch.object(driver.selectors, "DefaultSelector", return_value=SelectorDouble()), mock.patch.object(driver.os, "killpg", side_effect=kill_group), mock.patch.object(driver.time, "sleep"):
            result = driver.run_owned(["never-executed-generated-double"], str(root), {}, root / "empty-owned-log", 7, 64)
        self.assertEqual(events, ["term", "kill", "wait", "close"])
        self.assertIs(result["leader_reaped"], True)
        self.assertIsNone(result["cleanup_error"])


def main():
    global FIXTURES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    FIXTURES = args.fixtures
    if not FIXTURES.is_absolute() or FIXTURES.exists() or FIXTURES.is_symlink():
        raise ValueError("Use an absolute new fixture root; prior runs stay immutable")
    FIXTURES.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BackendControls)
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    retained = sum(p.stat().st_size for p in FIXTURES.rglob("*") if p.is_file() and not p.is_symlink())
    print("GENERATED_CONTROL_ACCOUNTING=" + json.dumps({"methods": count, "fixture_cumulative_bytes": WRITTEN, "retained_regular_fixture_bytes": retained, "fixture_write_limit": FIXTURE_CUMULATIVE_LIMIT, "scope": "invented source/output fixtures and harmless subprocesses; no actual package build or qualification"}, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1

if __name__ == "__main__":
    raise SystemExit(main())
