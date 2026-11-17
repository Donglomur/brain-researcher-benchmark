"""Source-only NEURAL081 preparation and unchanged-constructor controls.

The complete fixtures contain public source and invented, unresolved operator
metadata. No EEG, model, private target, qualification or scientific run is used.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("benchmarks/neural/NEURAL-081/implementations/neural-081/portable-v1")
RESOLUTION = PACKAGE / "source-resolution"
PREPARER = RESOLUTION / "prepare_sources.py"
SOURCE_MAP = RESOLUTION / "SOURCE_MAP.json"
RELEASE = PACKAGE / "release/PORTABLE_RELEASE.json"
CONSTRUCTOR = PACKAGE / "release/neural081_instance.py"
CAP = 32 * 1024 * 1024
HISTORICAL_PINS = {
    "SOURCE_MANIFEST.json": (1621, "c53215694945eaed25b5f62864b44e4fd73b8161d96db2263d85ca4f97053d4f"),
    "PUBLIC_RELEASE_MANIFEST.json": (7985, "c1bd08b248f696aea83467a37a01d69aae5dfccb3053f90cd09bb98134c4731c"),
    "release/PORTABLE_RELEASE.json": (54631, "d6d3406ba2e0fce136fbe7d71bf76fd311915324eb031493a2d963184f2ae2ca"),
    "release/neural081_instance.py": (153697, "ef339b63f9a817a6ed8feb620451c8cf3b73389345a3d80bcdb376609416c1d9"),
    "release/SOURCE_FRAGMENT_MANIFEST.json": (994, "ccca25858bbe18d4e1f4b63a8671902d1a8eb377aeac9a976098e7789d2f4845"),
}


def fingerprint(path):
    raw = path.read_bytes()
    return len(raw), hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


class Neural081Relocation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="neural081-relocation-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        self.checkout = self.workspace / "public checkout with spaces"
        self.checkout.mkdir()
        # The copy has only this public package and the explicit public source
        # rows. It neither follows runtime operands nor relies on Git history.
        shutil.copytree(ROOT / PACKAGE, self.checkout / PACKAGE,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.mapping = read_json(self.checkout / SOURCE_MAP)
        self.release = read_json(self.checkout / RELEASE)
        for row in self.mapping["rows"]:
            source = ROOT / row["source"]
            target = self.checkout / row["source"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        self.destination = self.workspace / "exact prerequisite sources"

    def prepare(self, *, public_root=None, destination=None, **limits):
        values = {"read-cap": CAP, "write-cap": CAP, "live-cap": CAP,
                  "deadline": time.monotonic() + 20}
        values.update(limits)
        argv = [sys.executable, "-I", "-S", "-B", str(self.checkout / PREPARER),
                "--public-root", str(public_root or self.checkout),
                "--destination", str(destination or self.destination)]
        for key, value in values.items():
            argv.extend(["--" + key, str(value)])
        return subprocess.run(argv, capture_output=True, timeout=25,
                              cwd=self.workspace)

    def assert_pin(self, path, descriptor):
        self.assertEqual(fingerprint(path),
                         (descriptor["bytes"], descriptor["sha256"]), str(path))

    def assert_preflight_refusal(self, **kwargs):
        result = self.prepare(**kwargs)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.destination.exists(), result.stderr)
        return result

    def test_historical_release_and_assembly_are_unchanged(self):
        for relative, expected in HISTORICAL_PINS.items():
            with self.subTest(relative=relative):
                self.assertEqual(fingerprint(ROOT / PACKAGE / relative), expected)
        frozen = read_json(ROOT / PACKAGE / "SOURCE_MANIFEST.json")
        self.assertEqual(len(frozen["files"]), 9)
        for relative, descriptor in frozen["files"].items():
            self.assert_pin(ROOT / PACKAGE / relative, descriptor)
        assembly = read_json(ROOT / PACKAGE / "release/SOURCE_FRAGMENT_MANIFEST.json")
        fragments = []
        for row in assembly["fragments"]:
            self.assert_pin(ROOT / PACKAGE / row["path"], row)
            fragments.append((ROOT / PACKAGE / row["path"]).read_bytes())
        separator = bytes.fromhex(assembly["separator_hex"])
        self.assertEqual(separator.join(fragments), (ROOT / CONSTRUCTOR).read_bytes())

    def test_complete_preparation_builds_unchanged_independent_instance(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        prepared = json.loads(result.stdout)
        self.assertEqual(prepared["status"], "prepared_not_qualified")
        self.assertEqual(prepared["prerequisites"], 105)
        self.assertFalse(prepared["scientific_execution"])
        self.assertFalse(prepared["runtime_authorization"])
        self.assertFalse(prepared["qualification_created"])
        self.assert_pin(Path(prepared["receipt"]["path"]), prepared["receipt"])
        receipt = read_json(Path(prepared["receipt"]["path"]))
        self.assertEqual(receipt["prerequisites"], 105)
        self.assertEqual(len(receipt["files"]), 105)
        for descriptor in receipt["files"]:
            self.assert_pin(Path(descriptor["path"]), descriptor)
        for key in ("runtime_authorization", "qualification_created", "scientific_execution"):
            self.assertFalse(receipt[key])
        expected = {row["path"]: row for row in self.release["public_files"]}
        mapped = {row["path"]: row for row in self.mapping["rows"]}
        self.assertEqual(len(expected), 105)
        self.assertEqual(set(mapped), set(expected))
        source_bytes = sum(row["bytes"] for row in expected.values())
        budget = prepared["budget"]
        self.assertFalse(budget["physical_IO_RSS_measured"])
        self.assertGreaterEqual(budget["used"]["read_bytes"], 2 * source_bytes)
        self.assertGreaterEqual(budget["used"]["write_bytes"], source_bytes
                                + prepared["receipt"]["bytes"]
                                + prepared["terminal_report_reservation_bytes"])
        for key in ("read_bytes", "write_bytes"):
            self.assertEqual(budget["limits"][key], CAP)
            self.assertLessEqual(budget["used"][key], CAP)
        self.assertLessEqual(budget["managed_peak_bytes"], CAP)
        for relative, descriptor in expected.items():
            self.assert_pin(self.destination / relative, descriptor)
            self.assertEqual((mapped[relative]["bytes"], mapped[relative]["sha256"]),
                             (descriptor["bytes"], descriptor["sha256"]))
        self.assertEqual(len(self.mapping["historical_helpers"]), 3)

        instance = self.workspace / "fresh instance"
        for role in ("operator", "raw", "secret", "protected", "output"):
            (self.workspace / role).mkdir()
        profile = {
            "schema": "neural081_portable_profile_v1", "task_id": "NEURAL-081",
            "root_roles": {"source": str(instance),
                           **{role: [str(self.workspace / role)]
                              for role in ("operator", "raw", "secret", "protected")},
                           "output": str(self.workspace / "output")},
            **{role: {"disposition": "not_supplied"} for role in
               ("input_records", "environment_records", "execution_selection")},
        }
        profile_path = self.workspace / "operator/profile.json"
        profile_path.write_text(json.dumps(profile, sort_keys=True))
        release_bytes, release_sha = fingerprint(self.checkout / RELEASE)
        profile_bytes, profile_sha = fingerprint(profile_path)
        argv = [sys.executable, "-I", "-S", "-B", str(self.checkout / CONSTRUCTOR),
                "build", "--release", str(self.checkout / RELEASE),
                "--release-bytes", str(release_bytes), "--release-sha256", release_sha,
                "--public-root", str(self.destination), "--root", str(instance),
                "--profile", str(profile_path), "--profile-bytes", str(profile_bytes),
                "--profile-sha256", profile_sha, "--read-cap", str(CAP),
                "--write-cap", str(CAP), "--live-cap", str(CAP),
                "--deadline", str(time.monotonic() + 20)]
        built = subprocess.run(argv, capture_output=True, timeout=25, cwd=self.workspace)
        self.assertEqual(built.returncode, 0, built.stderr)
        report = json.loads(built.stdout)
        self.assertEqual(report["status"], "constructed_not_qualified")
        for key in ("runtime_authorization", "qualification_created", "scientific_execution"):
            self.assertFalse(report[key])
        build_result = read_json(Path(report["instance"]["path"]))
        self.assertEqual(len(self.release["active_sources"]), 66)
        for relative, descriptor in self.release["active_sources"].items():
            self.assert_pin(instance / relative, descriptor)
        for relative, descriptor in expected.items():
            self.assert_pin(instance / "origin" / relative, descriptor)
        freeze = read_json(Path(build_result["source_freeze"]["path"]))
        self.assertEqual(len(freeze["files"]), 72)
        registry = read_json(Path(build_result["registry_initial"]["path"]))
        self.assertEqual(registry["admission"], {"runnable": False, "research_qualified": False})
        self.assertEqual(registry["program_execution"]["verification"]["status"], "not_run")
        requirements = read_json(Path(build_result["requirements"]["path"]))
        self.assertTrue(requirements["unmet"])
        self.assertFalse(requirements["qualification_created"])

        # Remove both the new staging tree and source checkout: the installed
        # source graph must close on its own copies, with external operands held.
        shutil.rmtree(self.destination)
        shutil.rmtree(self.checkout)
        for relative, descriptor in freeze["files"].items():
            self.assert_pin(instance / relative, descriptor)
        stage_input = self.workspace / "operator/select-run.json"
        stage_input.write_text(json.dumps({
            "schema": "neural081_portable_stage_input_v1", "stage": "select-run",
            "instance": report["instance"], "run": None,
            "payload": {"input": None, "selection": None},
        }, sort_keys=True))
        size, digest = fingerprint(stage_input)
        held = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(instance / "tools/neural081_instance.py"),
             "select-run", "--input", str(stage_input), "--input-bytes", str(size),
             "--input-sha256", digest, "--read-cap", str(CAP), "--write-cap", str(CAP),
             "--live-cap", str(CAP), "--deadline", str(time.monotonic() + 20)],
            capture_output=True, timeout=25, cwd=self.workspace,
        )
        self.assertNotEqual(held.returncode, 0)
        self.assertIn(b"unresolved operand requires an explicit selected stage input", held.stderr)
        for role in ("raw", "secret", "protected", "output"):
            self.assertEqual(list((self.workspace / role).iterdir()), [])
        self.assertEqual(read_json(Path(build_result["registry_initial"]["path"])), registry)

    def test_missing_source_refuses_before_destination_creation(self):
        (self.checkout / self.mapping["rows"][0]["source"]).unlink()
        self.assert_preflight_refusal()

    def test_changed_source_refuses_before_destination_creation(self):
        path = self.checkout / self.mapping["rows"][0]["source"]
        original = path.read_bytes()
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        self.assert_preflight_refusal()

    def test_symlinked_source_refuses_before_destination_creation(self):
        path = self.checkout / self.mapping["rows"][0]["source"]
        held = self.workspace / "same-source-body"
        path.rename(held)
        path.symlink_to(held)
        self.assert_preflight_refusal()

    def test_hardlinked_source_refuses_before_destination_creation(self):
        path = self.checkout / self.mapping["rows"][0]["source"]
        os.link(path, self.workspace / "hardlinked-source-body")
        self.assert_preflight_refusal()

    def test_source_map_tampering_is_refused(self):
        path = self.checkout / SOURCE_MAP
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_preflight_refusal()

    def test_original_constructor_tampering_is_refused(self):
        path = self.checkout / CONSTRUCTOR
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_preflight_refusal()

    def test_existing_destination_is_preserved(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep.txt"
        sentinel.write_bytes(b"preexisting output must survive")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.destination.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"preexisting output must survive")

    def test_expired_deadline_and_exhausted_read_budget_refuse(self):
        for limits in ({"deadline": time.monotonic() - 1}, {"read-cap": 1}):
            with self.subTest(limits=limits):
                self.assert_preflight_refusal(**limits)

    def test_small_write_and_live_budgets_never_report_success(self):
        for index, limits in enumerate(({"write-cap": 1}, {"live-cap": 65536})):
            with self.subTest(limits=limits):
                result = self.prepare(destination=self.workspace / ("bounded-" + str(index)), **limits)
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_destination_inside_public_checkout_is_refused(self):
        destination = self.checkout / "in-place-stage"
        result = self.prepare(destination=destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(destination.exists())

    def test_terminal_flush_deadline_is_part_of_success(self):
        # Exercise main's real serialization/write/flush sequence without sleeps
        # or source copies. Only preparation and the terminal clock/sink are fake.
        for flush_time in (9.5, 11.0):
            with self.subTest(flush_time=flush_time):
                module = types.ModuleType("neural081_preparer_deadline_test")
                source = self.checkout / PREPARER
                module.__file__ = str(source)
                exec(compile(source.read_bytes(), str(source), "exec"), module.__dict__)
                clock = [9.0]
                received = []
                calls = []

                class TerminalSink:
                    def write(self, raw):
                        received.append(raw)
                        return len(raw)

                    def flush(self):
                        clock[0] = flush_time

                def prepared(*args, **kwargs):
                    calls.append((args, kwargs))
                    return {"status": "prepared_not_qualified"}

                module.prepare = prepared
                module.time = types.SimpleNamespace(monotonic=lambda: clock[0])
                module.sys = types.SimpleNamespace(
                    stdout=types.SimpleNamespace(buffer=TerminalSink()))
                argv = ["--public-root", "/unread-public-source",
                        "--destination", "/uncreated-destination",
                        "--read-cap", str(CAP), "--write-cap", str(CAP),
                        "--live-cap", str(CAP), "--deadline", "10"]
                if flush_time < 10:
                    self.assertEqual(module.main(argv), 0)
                else:
                    with self.assertRaisesRegex(ValueError, "deadline after terminal report"):
                        module.main(argv)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][1]["deadline"], 10.0)
                self.assertEqual(json.loads(b"".join(received)),
                                 {"status": "prepared_not_qualified"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
