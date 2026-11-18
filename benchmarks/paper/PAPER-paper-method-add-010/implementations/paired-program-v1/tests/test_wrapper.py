"""Generated filesystem/subprocess controls, never authentic inputs or Docker."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("meg_candidate_wrapper", HERE / "candidate_wrapper.py")
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


class WrapperTests(unittest.TestCase):
    # Every written fixture is tiny; conservative counters retain overwritten
    # request bytes and subprocess writes independently of final retained size.
    fixture_write_bound = 0

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="meg-wrapper-generated-"))
        self.output = self.root / "output"
        self.input = self.root / "input"
        self.output.mkdir(); self.input.mkdir()
        self.program = self.root / "candidate.py"
        self.request = self.root / "request.json"
        self.binding = {"request": str(self.request), "program": str(self.program),
                        "input": str(self.input), "output": str(self.output),
                        "python": str(Path(sys.executable).resolve())}
        self.document = {"schema": "osl_owned_phase_request_v1", "phase_id": "generated-meg-A-00",
                         "clock": {"origin": time.monotonic() - 1,
                                   "phase_deadline": time.monotonic() + 10},
                         "resources": {"max_file_bytes": 4096, "max_output_bytes": 8192,
                                       "manifest_bytes": 4096, "cleanup_seconds": 2},
                         "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}
        self.store_request()
        self.store_program("out.write_bytes(b'{\"p\":0.5}\\n')")
        # No neural-array file is fabricated or decoded. The candidate fixture
        # intentionally ignores this empty, generated input directory.
        # All hard-coded generated candidate paths below write <=1025 bytes;
        # at most one <1KiB manifest is produced per test.
        type(self).fixture_write_bound += 2048

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, path, body):
        path.write_bytes(body)
        type(self).fixture_write_bound += len(body)

    def store_request(self, raw=None):
        self.put(self.request, raw if raw is not None else wrapper.encoded(self.document))

    def store_program(self, action):
        source = ("import argparse,os,sys,time\nfrom pathlib import Path\n"
                  "p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');"
                  "a=p.parse_args();out=Path(a.output)\n" + action + "\n")
        self.put(self.program, source.encode())

    def run_fixture(self):
        return wrapper.run(_generated=self.binding)

    def test_success_exact_manifest_and_raw_request_digest(self):
        # Whitespace differs from canonical JSON; hash must bind actual bytes.
        raw = json.dumps(self.document, indent=1).encode() + b"\n\n"
        self.store_request(raw)
        result = self.run_fixture()
        self.assertEqual(result, json.loads((self.output / "OUTPUTS.json").read_bytes()))
        self.assertEqual(result["request_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["files"], {"RESULT.json": wrapper.pin(b'{"p":0.5}\n')})
        self.assertEqual(stat.S_IMODE((self.output / "OUTPUTS.json").stat().st_mode), 0o444)

    def test_preexisting_output_refuses_before_candidate(self):
        self.put(self.output / "old", b"x")
        with self.assertRaisesRegex(ValueError, "initially be empty"):
            self.run_fixture()
        self.assertFalse((self.output / "RESULT.json").exists())

    def test_extra_file_and_directory_refused(self):
        for action in ["(out.parent/'extra').write_bytes(b'x')",
                       "(out.parent/'extra').mkdir()"]:
            with self.subTest(action=action):
                self.store_program("out.write_bytes(b'{}')\n" + action)
                with self.assertRaisesRegex(ValueError, "Exactly one"):
                    self.run_fixture()
                for child in self.output.iterdir():
                    child.rmdir() if child.is_dir() else child.unlink()

    def test_symlink_result_refused(self):
        self.store_program("out.symlink_to(Path(a.input).parent/'request.json')")
        with self.assertRaises(OSError):
            self.run_fixture()
        self.assertFalse((self.output / "OUTPUTS.json").exists())

    def test_multilink_result_refused(self):
        self.store_program("os.link(Path(a.input).parent/'request.json',out)")
        with self.assertRaisesRegex(ValueError, "singly linked"):
            self.run_fixture()

    def test_nonregular_result_refused_without_blocking(self):
        self.store_program("os.mkfifo(out)")
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.run_fixture()

    def test_oversized_result_refused(self):
        self.document["resources"].update(max_file_bytes=1024, manifest_bytes=1024)
        self.store_request()
        self.store_program("out.write_bytes(b'x'*1025)")
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.run_fixture()

    def test_failed_candidate_never_publishes_manifest(self):
        self.store_program("out.write_bytes(b'{}')\nsys.exit(3)")
        with self.assertRaisesRegex(ValueError, "exit successfully"):
            self.run_fixture()
        self.assertFalse((self.output / "OUTPUTS.json").exists())

    def test_request_mutation_rejected(self):
        self.store_program("out.write_bytes(b'{}')\n(Path(a.input).parent/'request.json').write_bytes(b'{}')")
        type(self).fixture_write_bound += 2
        with self.assertRaisesRegex(ValueError, "remain unchanged"):
            self.run_fixture()

    def test_expired_clock_refuses_before_launch(self):
        self.document["clock"]["phase_deadline"] = time.monotonic() - 0.1
        self.store_request()
        with self.assertRaisesRegex(ValueError, "Live original"):
            self.run_fixture()
        self.assertFalse((self.output / "RESULT.json").exists())

    def test_timeout_does_not_renew_deadline(self):
        self.store_program("time.sleep(2)\nout.write_bytes(b'{}')")
        self.document["clock"]["phase_deadline"] = time.monotonic() + 0.15
        self.store_request()
        began = time.monotonic()
        real_popen, observed = subprocess.Popen, []
        def retain_child(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            observed.append(child)
            return child
        with mock.patch.object(wrapper.subprocess, "Popen", side_effect=retain_child):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_fixture()
        self.assertEqual(len(observed), 1)
        self.assertIsNotNone(observed[0].returncode, "Exact direct child must have been waited/reaped")
        self.assertLess(time.monotonic() - began, 1)
        self.assertFalse((self.output / "OUTPUTS.json").exists())

    def test_manifest_mode_under_restrictive_umask(self):
        previous = os.umask(0o077)
        try:
            self.run_fixture()
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE((self.output / "OUTPUTS.json").stat().st_mode), 0o444)
        self.assertEqual(set(p.name for p in self.output.iterdir()), {"RESULT.json", "OUTPUTS.json"})

    def test_candidate_stays_in_owned_process_group(self):
        self.store_program("out.write_bytes(str(os.getpgrp()).encode())")
        self.run_fixture()
        self.assertEqual(int((self.output / "RESULT.json").read_bytes()), os.getpgrp())

    def test_bad_request_and_manifest_budget_refused(self):
        for change in [{"phase_id": "bad/name"}, {"output": {"kind": "native_capture", "manifest": "CAPTURE.json"}}]:
            with self.subTest(change=change):
                doc = dict(self.document); doc.update(change)
                self.store_request(wrapper.encoded(doc))
                with self.assertRaises(ValueError): self.run_fixture()
        self.document["resources"]["manifest_bytes"] = 1
        self.store_request()
        with self.assertRaisesRegex(ValueError, "resource ceilings"):
            self.run_fixture()
        self.assertFalse((self.output / "OUTPUTS.json").exists())


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        print("GENERATED_FIXTURE_CONSERVATIVE_WRITE_BOUND", WrapperTests.fixture_write_bound)
