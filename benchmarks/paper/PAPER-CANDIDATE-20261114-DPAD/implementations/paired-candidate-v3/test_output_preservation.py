"""Generated CLI artifact-preservation controls; no authentic data/model activity."""
import copy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import paired as p
from test_stable_pearson import full_fixture

COMMAND_INPUTS = {
    "freeze-author": ("training", "targets", "predictions"),
    "select-candidate": ("training",),
    "preflight": ("plan", "predictions"),
    "compare": ("targets", "reference", "plan", "predictions"),
}
FUNCTIONS = {"freeze-author": "freeze_reference", "select-candidate": "select_candidate",
             "preflight": "preflight", "compare": "compare"}


class OutputPreservation(unittest.TestCase):
    def setUp(self):
        root = os.environ.get("DPAD_CONTROL_ROOT")
        if root:
            Path(root).mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=root))
        else:
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            self.root = Path(directory.name)
        self.inputs = {name: self.root / (name + ".json") for name in
                       ("training", "targets", "predictions", "reference", "plan")}
        for name, path in self.inputs.items():
            path.write_text(json.dumps({"generated_input_role": name}) + "\n")
        self.output = self.root / "result.json"

    def argv(self, command, output=None):
        argv = ["paired.py", command]
        for name in COMMAND_INPUTS[command]:
            argv.extend(["--" + name, str(self.inputs[name])])
        if command in ("preflight", "compare"):
            argv.extend(["--plan-sha256", "a" * 64])
        if command == "compare":
            argv.extend(["--reference-sha256", "b" * 64])
        return argv + ["--output", str(self.output if output is None else output)]

    def rejected_before_read(self, command, output):
        before = {name: path.read_bytes() for name, path in self.inputs.items()}
        stdout, stderr = StringIO(), StringIO()
        with patch("sys.argv", self.argv(command, output)), redirect_stdout(stdout), redirect_stderr(stderr), \
                patch.object(p.e, "read_json", side_effect=AssertionError("input payload read")) as read, \
                patch.object(p, FUNCTIONS[command], side_effect=AssertionError("computation started")) as compute:
            with self.assertRaises(SystemExit) as failure:
                p.main()
        self.assertEqual(failure.exception.code, 2)
        read.assert_not_called()
        compute.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("DPAD paired input rejected", stderr.getvalue())
        self.assertEqual(before, {name: path.read_bytes() for name, path in self.inputs.items()})

    def test_all_four_commands_preserve_direct_and_normalized_input_aliases(self):
        (self.root / "subdir").mkdir()
        for command, names in COMMAND_INPUTS.items():
            for name in names:
                for alias in (self.inputs[name], self.root / "subdir" / ".." / self.inputs[name].name):
                    with self.subTest(command=command, name=name, alias=str(alias)):
                        self.rejected_before_read(command, alias)

    def test_all_four_commands_preserve_symlink_and_hardlink_input_aliases(self):
        for command, names in COMMAND_INPUTS.items():
            for name in names:
                for link_kind in ("symlink", "hardlink"):
                    with self.subTest(command=command, name=name, link_kind=link_kind):
                        alias = self.root / f"{command}-{name}-{link_kind}"
                        if link_kind == "symlink":
                            alias.symlink_to(self.inputs[name])
                        else:
                            os.link(self.inputs[name], alias)
                        self.rejected_before_read(command, alias)
                        self.assertEqual(alias.read_bytes(), self.inputs[name].read_bytes())

    def test_existing_output_dangling_link_directory_and_fifo_refused(self):
        prior = self.root / "prior.json"
        prior.write_bytes(b"retained prior experiment")
        dangling = self.root / "dangling.json"
        dangling.symlink_to(self.root / "absent")
        directory = self.root / "destination-directory"
        directory.mkdir()
        fifo = self.root / "destination-fifo"
        os.mkfifo(fifo)
        try:
            for command in COMMAND_INPUTS:
                for destination in (prior, dangling, directory, fifo):
                    with self.subTest(command=command, destination=str(destination)):
                        self.rejected_before_read(command, destination)
            self.assertEqual(prior.read_bytes(), b"retained prior experiment")
            self.assertTrue(dangling.is_symlink())
        finally:
            fifo.unlink()

    def test_missing_output_parent_rejects_before_payload_read(self):
        for command in COMMAND_INPUTS:
            self.rejected_before_read(command, self.root / "missing" / "result.json")

    def test_all_four_fresh_cli_results_publish_before_success_receipt(self):
        for command in COMMAND_INPUTS:
            result = {"schema": "generated-" + command, "value": [1, 2, 3]}
            output = self.root / (command + ".result.json")
            stdout, stderr = StringIO(), StringIO()
            original_publish = p._publish_output
            def publish(path, body):
                self.assertEqual(stdout.getvalue(), "")
                original_publish(path, body)
                self.assertEqual(json.loads(path.read_bytes()), result)
            with patch("sys.argv", self.argv(command, output)), redirect_stdout(stdout), redirect_stderr(stderr), \
                    patch.object(p.e, "read_json", return_value={}) as read, \
                    patch.object(p, FUNCTIONS[command], return_value=result), \
                    patch.object(p, "_publish_output", side_effect=publish):
                p.main()
            self.assertEqual(read.call_count, len(COMMAND_INPUTS[command]))
            self.assertEqual(output.read_bytes(), (json.dumps(result, indent=2, allow_nan=False) + "\n").encode())
            self.assertEqual(json.loads(stdout.getvalue()), {"schema": result["schema"], "canonical_sha256": p.e.digest(result)})
            self.assertEqual(stderr.getvalue(), "")

    def test_serialization_failure_creates_no_output_or_pending(self):
        stdout, stderr = StringIO(), StringIO()
        with patch("sys.argv", self.argv("preflight")), redirect_stdout(stdout), redirect_stderr(stderr), \
                patch.object(p.e, "read_json", return_value={}), \
                patch.object(p, "preflight", return_value={"schema": "generated", "bad": float("nan")}), \
                patch.object(p.tempfile, "mkstemp", side_effect=AssertionError("publication started")) as temp:
            with self.assertRaises(SystemExit) as failure:
                p.main()
        self.assertEqual(failure.exception.code, 2)
        temp.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual(stdout.getvalue(), "")

    def test_write_short_write_flush_fsync_and_link_failures_have_no_final(self):
        original_fdopen = os.fdopen
        for operation in ("write", "short-write", "flush", "fsync", "link"):
            with self.subTest(operation=operation):
                class Stream:
                    def __init__(self, fd, mode): self.real = original_fdopen(fd, mode)
                    def __enter__(self): self.real.__enter__(); return self
                    def __exit__(self, *args): return self.real.__exit__(*args)
                    def write(self, body):
                        if operation in ("write", "short-write"):
                            self.real.write(body[:2])
                            if operation == "write": raise OSError("generated write failure")
                            return 2
                        return self.real.write(body)
                    def flush(self):
                        if operation == "flush": raise OSError("generated flush failure")
                        return self.real.flush()
                    def fileno(self): return self.real.fileno()
                with patch.object(p.os, "fdopen", side_effect=Stream):
                    if operation in ("fsync", "link"):
                        with patch.object(p.os, operation, side_effect=OSError("generated publication failure")):
                            with self.assertRaises(OSError): p._publish_output(self.output, b'{"complete":true}\n')
                    else:
                        with self.assertRaises(OSError): p._publish_output(self.output, b'{"complete":true}\n')
                self.assertFalse(self.output.exists())
                self.assertFalse(list(self.root.glob(".dpad-result-*.pending")))

    def test_existing_destination_created_after_preflight_is_preserved(self):
        output = p._new_output_path(self.output)
        output.write_bytes(b"competing result")
        with self.assertRaises(FileExistsError): p._publish_output(output, b"new result")
        self.assertEqual(output.read_bytes(), b"competing result")
        self.assertFalse(list(self.root.glob(".dpad-result-*.pending")))

    def test_dangling_destination_created_after_preflight_is_preserved(self):
        output = p._new_output_path(self.output)
        output.symlink_to(self.root / "absent")
        with self.assertRaises(FileExistsError): p._publish_output(output, b"new result")
        self.assertTrue(output.is_symlink())
        self.assertFalse((self.root / "absent").exists())

    def test_publication_failure_prints_no_success_and_keeps_competing_file(self):
        stdout, stderr = StringIO(), StringIO()
        original_publish = p._publish_output
        def race(path, body):
            path.write_bytes(b"other operation")
            original_publish(path, body)
        with patch("sys.argv", self.argv("preflight")), redirect_stdout(stdout), redirect_stderr(stderr), \
                patch.object(p.e, "read_json", return_value={}), \
                patch.object(p, "preflight", return_value={"schema": "generated"}), \
                patch.object(p, "_publish_output", side_effect=race):
            with self.assertRaises(SystemExit) as failure: p.main()
        self.assertEqual(failure.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(self.output.read_bytes(), b"other operation")

    def test_cleanup_failure_keeps_publication_outcome_truthful(self):
        with patch.object(p.Path, "unlink", side_effect=OSError("generated cleanup failure")):
            p._publish_output(self.output, b'{"schema":"generated"}\n')
        self.assertEqual(json.loads(self.output.read_bytes()), {"schema": "generated"})
        self.assertEqual(len(list(self.root.glob(".dpad-result-*.pending"))), 1)
        failed = self.root / "failed.json"
        with patch.object(p.Path, "unlink", side_effect=OSError("generated cleanup failure")), \
                patch.object(p.os, "link", side_effect=OSError("original publication failure")):
            with self.assertRaisesRegex(OSError, "original publication failure"):
                p._publish_output(failed, b"unpublished")
        self.assertFalse(failed.exists())


class FullComparisonPreservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training, cls.targets, cls.author, cls.plan, cls.predictions = full_fixture()
        cls.reference = p.freeze_reference(cls.training, cls.targets, cls.author)
        cls.rh, cls.ph = p.e.digest(cls.reference), p.e.digest(cls.plan)

    def score(self, **changes):
        values = dict(targets=self.targets, reference=self.reference, plan=self.plan,
                      predictions=self.predictions, reference_sha256=self.rh, plan_sha256=self.ph)
        values.update(changes)
        return p.compare(**values)

    def test_complete_generated_grid_and_real_compare_cli(self):
        result = self.score()
        self.assertEqual(len(self.reference["source_grid_results"]["all_grid_scores"]), 1960)
        self.assertEqual(len(result["candidate_grid_scores"]), 280)
        self.assertEqual(len(result["candidate_selected_scores"]), 35)
        self.assertEqual(len(result["paired_fold_deltas"]), 245)
        for row in result["paired_fold_deltas"]:
            self.assertAlmostEqual(row["neural_cc_delta"], -2.0)
            self.assertAlmostEqual(row["behavior_cc_delta"], -2.0)
        root = os.environ.get("DPAD_CONTROL_ROOT")
        temp = tempfile.TemporaryDirectory(dir=root) if not root else None
        directory = Path(temp.name) if temp else Path(tempfile.mkdtemp(prefix="full-comparison-", dir=root))
        if temp: self.addCleanup(temp.cleanup)
        arguments = ["paired.py", "compare"]
        for key, value in (("targets", self.targets), ("reference", self.reference), ("plan", self.plan), ("predictions", self.predictions)):
            path = directory / (key + ".json")
            path.write_text(json.dumps(value) + "\n")
            arguments.extend(["--" + key, str(path)])
        output = directory / "result.json"
        arguments += ["--reference-sha256", self.rh, "--plan-sha256", self.ph, "--output", str(output)]
        stdout = StringIO()
        with patch("sys.argv", arguments), redirect_stdout(stdout): p.main()
        actual = json.loads(output.read_bytes())
        self.assertEqual(actual, result)
        self.assertEqual(p.e.digest(actual), p.e.digest(result))
        self.assertEqual(json.loads(stdout.getvalue())["canonical_sha256"], p.e.digest(result))

    def test_wrong_frozen_hashes_and_incomplete_grid_still_reject(self):
        for changes in ({"reference_sha256": "0" * 64}, {"plan_sha256": "0" * 64},
                        {"predictions": {**self.predictions, "cases": self.predictions["cases"][:-1]}}):
            with self.assertRaises(p.e.ContractError): self.score(**changes)

    def test_undefined_and_nonfinite_candidates_still_reject(self):
        for value in (0.0, float("inf")):
            predictions = copy.deepcopy(self.predictions)
            row = predictions["cases"][0]
            row["neural"] = [[value] * 77 for _ in row["neural"]]
            with self.assertRaises(p.e.ContractError): self.score(predictions=predictions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
