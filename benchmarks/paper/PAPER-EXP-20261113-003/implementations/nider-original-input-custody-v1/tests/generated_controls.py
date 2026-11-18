"""Generated-only custody/preparation controls; no original input, network, R or fit."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("new_original_custody", HERE / "prepare_original_inputs.py")
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)
IMPLEMENTATIONS = None


def raw_pin(path):
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class OriginalCustodyControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="exp003-generated-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)
        self.c = op.load_custody(str(IMPLEMENTATIONS))
        self.material = {"workbook": b"GENERATED\\x00workbook",
                         "script": b"GENERATED text, never evaluated",
                         "lock": b'{"generated":true}'}
        self.assets = {}
        self.locations = {"schema": "nider_original_input_locations_v1", "inputs": {}}
        for key, content in self.material.items():
            path = self.root / ("source-" + key)
            path.write_bytes(content)
            path.chmod(0o600)
            fixed = copy.deepcopy(op.ASSETS[key])
            fixed.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
            self.assets[key] = fixed
            self.locations["inputs"][key] = str(path)
        # Internal generated-fixture policy only. CLI has no pin-override field.
        patcher = mock.patch.object(op, "ASSETS", self.assets)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.stage_root = self.root / "staged"
        self.executables = {}
        for key in ("python", "rscript"):
            path = self.root / ("generated-" + key)
            path.write_bytes(("GENERATED opaque identity " + key).encode())
            path.chmod(0o700)
            self.executables[key] = raw_pin(path)
        self.native = self.root / "native-source"
        self.native.mkdir(mode=0o700)
        native_pins = {}
        for name in op.NATIVE_COMPONENT:
            path = self.native / name
            path.write_bytes(("GENERATED source marker " + name).encode())
            row = raw_pin(path)
            native_pins[name] = {"bytes": row["bytes"], "sha256": row["sha256"]}
        patcher = mock.patch.object(op, "NATIVE_COMPONENT", native_pins)
        patcher.start()
        self.addCleanup(patcher.stop)

    def staged(self):
        result = op.stage(self.locations, str(IMPLEMENTATIONS), str(self.stage_root))
        return result["custody"]

    def request(self, custody, operation="producer"):
        out = {"schema": "nider_original_command_binding_request_v1", "operation": operation,
            "custody": custody, **copy.deepcopy(self.executables), "owner_runtime_identity": "generated-only",
            "arm": "A", "artifact_byte_limit": 134217728}
        if operation == "producer":
            out.update(bundle_output=str(self.root / "future-bundle"), producer_timeout_seconds=1800)
        else:
            view = self.root / "view"
            view.mkdir(mode=0o700)
            for name in op.PAYLOADS:
                path = view / name
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                path.write_bytes(b"x")  # Deliberately not a native/scientific object.
            out.update(payload_view=str(view), native_component_root=str(self.native),
                       native_receipt=str(self.root / "native-receipt.json"), verification_wall_seconds=180)
        return out

    def test_fixed_policy_cannot_be_overridden_in_location_request(self):
        value = copy.deepcopy(self.locations)
        value["expected_pins"] = self.assets
        with self.assertRaisesRegex(ValueError, "exact_three_original_locations"):
            op.stage(value, str(IMPLEMENTATIONS), str(self.stage_root))
        self.assertFalse(self.stage_root.exists())

    def test_bootstrap_fifo_is_rejected_before_body_read(self):
        root = self.root / "fifo-implementations"
        path = root / op.CUSTODY_RELATIVE
        path.parent.mkdir(parents=True)
        os.mkfifo(path, 0o600)
        actual_open, actual_fdopen = os.open, os.fdopen

        def guarded_open(path, flags):
            self.assertTrue(flags & os.O_NONBLOCK)
            self.assertTrue(flags & os.O_NOFOLLOW)
            return actual_open(path, flags)

        class NoBodyRead:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.file.close()

            def fileno(self):
                return self.file.fileno()

            def read(self, *args):
                raise AssertionError("FIFO body must not be read")

        with mock.patch.object(op.os, "open", side_effect=guarded_open), mock.patch.object(
                op.os, "fdopen", side_effect=lambda *args: NoBodyRead(actual_fdopen(*args))):
            with self.assertRaisesRegex(ValueError, "bootstrap_regular_unique_source"):
                op.load_custody(str(root))

    def test_bootstrap_symlink_and_noncanonical_paths_reject_before_open(self):
        root = self.root / "link-implementations"
        path = root / op.CUSTODY_RELATIVE
        path.parent.mkdir(parents=True)
        path.symlink_to(IMPLEMENTATIONS / op.CUSTODY_RELATIVE)
        with mock.patch.object(op.os, "open", side_effect=AssertionError("unexpected open")):
            with self.assertRaisesRegex(ValueError, "bootstrap_symlink_path"):
                op.load_custody(str(root))
            for value in ("relative-implementations", str(root) + "/../elsewhere"):
                with self.assertRaisesRegex(ValueError, "bootstrap_canonical_path_required"):
                    op.load_custody(value)

    def test_runtime_label_rejects_blank_whitespace_and_nul(self):
        request = {"operation": "producer", "arm": "A", "artifact_byte_limit": 1,
                   "producer_timeout_seconds": 1}
        for label in ("", "   ", "\t\n", "owner\x00runtime"):
            request["owner_runtime_identity"] = label
            with self.assertRaisesRegex(ValueError, "owner_runtime_identity"):
                op.limits(request)

    def test_stage_makes_independent_verified_copies_without_running_inputs(self):
        custody = self.staged()
        record = json.loads(Path(custody["path"]).read_text())
        self.assertTrue(record["complete"])
        self.assertFalse(record["runtime_admitted"])
        self.assertFalse((self.stage_root / "INCOMPLETE.json").exists())
        for key, entry in record["staged_inputs"].items():
            target = Path(entry["path"])
            source = Path(self.locations["inputs"][key])
            self.assertEqual(target.read_bytes(), self.material[key])
            self.assertNotEqual(target.stat().st_ino, source.stat().st_ino)
            self.assertEqual(target.stat().st_nlink, 1)
            self.assertEqual(target.stat().st_mode & 0o777, 0o400)
        # Origin paths are historical; frozen copies remain usable after source movement/change.
        Path(self.locations["inputs"]["script"]).write_bytes(b"changed generated origin")
        op.recheck_stage(self.c, custody["path"], custody["sha256"], str(IMPLEMENTATIONS))

    def test_bad_original_identity_creates_no_stage(self):
        Path(self.locations["inputs"]["workbook"]).write_bytes(b"wrong")
        with self.assertRaises(ValueError):
            op.stage(self.locations, str(IMPLEMENTATIONS), str(self.stage_root))
        self.assertFalse(self.stage_root.exists())

    def test_original_symlink_and_hardlink_are_rejected(self):
        original = Path(self.locations["inputs"]["lock"])
        link = self.root / "link"
        link.symlink_to(original)
        locations = copy.deepcopy(self.locations)
        locations["inputs"]["lock"] = str(link)
        with self.assertRaises(ValueError):
            op.stage(locations, str(IMPLEMENTATIONS), str(self.stage_root))
        link.unlink()
        os.link(original, link)
        with self.assertRaises(ValueError):
            op.stage(self.locations, str(IMPLEMENTATIONS), str(self.stage_root))
        self.assertFalse(self.stage_root.exists())

    def test_preexisting_stage_and_binding_are_not_overwritten(self):
        self.stage_root.mkdir(mode=0o700)
        sentinel = self.stage_root / "sentinel"
        sentinel.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "new_path_required"):
            op.stage(self.locations, str(IMPLEMENTATIONS), str(self.stage_root))
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_consumer_pin_drift_rejects_before_any_original_copy(self):
        wrong = copy.deepcopy(op.CONSUMERS)
        wrong["nider-primary-companions-v1/replay_companions.py"]["sha256"] = "0" * 64
        with mock.patch.object(op, "CONSUMERS", wrong):
            with self.assertRaises(ValueError):
                op.stage(self.locations, str(IMPLEMENTATIONS), str(self.stage_root))
        self.assertFalse(self.stage_root.exists())

    def test_publication_failure_preserves_incomplete_unusable_stage(self):
        original_write = self.c.write_new

        def write_then_fail(path, raw):
            result = original_write(path, raw)
            if Path(path).name == "CUSTODY.json":
                raise OSError("generated failure after bytes")
            return result

        with mock.patch.object(op, "load_custody", return_value=self.c), mock.patch.object(
                self.c, "write_new", side_effect=write_then_fail):
            with self.assertRaises(OSError):
                op.stage(self.locations, str(IMPLEMENTATIONS), str(self.stage_root))
        self.assertTrue((self.stage_root / "INCOMPLETE.json").exists())
        self.assertTrue((self.stage_root / "FAILURE.json").exists())
        failed = raw_pin(self.stage_root / "CUSTODY.json")
        with self.assertRaisesRegex(ValueError, "incomplete_or_failed_stage"):
            op.recheck_stage(self.c, failed["path"], failed["sha256"], str(IMPLEMENTATIONS))

    def test_staged_byte_changes_fail_before_command_binding(self):
        custody = self.staged()
        target = self.stage_root / "inputs" / self.assets["script"]["name"]
        target.chmod(0o600)
        target.write_bytes(b"changed")
        destination = self.root / "binding.json"
        with self.assertRaises(ValueError):
            op.bind(self.request(custody), str(IMPLEMENTATIONS), str(destination))
        self.assertFalse(destination.exists())

    def test_modified_receipt_and_forged_runtime_claim_are_rejected(self):
        custody = self.staged()
        path = Path(custody["path"])
        row = json.loads(path.read_text())
        row["runtime_admitted"] = True
        path.write_text(json.dumps(row))
        with self.assertRaises(ValueError):
            op.recheck_stage(self.c, custody["path"], custody["sha256"], str(IMPLEMENTATIONS))
        changed = raw_pin(path)
        with self.assertRaisesRegex(ValueError, "custody_cannot_admit_execution"):
            op.recheck_stage(self.c, changed["path"], changed["sha256"], str(IMPLEMENTATIONS))

    def test_producer_binding_uses_frozen_three_inputs_and_never_certifies_runtime(self):
        custody = self.staged()
        output = self.root / "binding.json"
        result = op.bind(self.request(custody), str(IMPLEMENTATIONS), str(output))
        row = json.loads(output.read_text())
        self.assertEqual(len(row["commands"]), 1)
        argv = row["commands"][0]["argv"]
        for flag, key in [("--original-workbook", "workbook"), ("--official-script", "script"), ("--renv-lock", "lock")]:
            self.assertEqual(argv[argv.index(flag) + 1], str(self.stage_root / "inputs" / self.assets[key]["name"]))
        self.assertEqual(row["commands"][0]["role"], "new_original57_expression_producer")
        self.assertFalse(row["runtime_versions_observed"])
        self.assertFalse(result["runtime_admitted"])
        self.assertFalse(row["execution_selected"])
        self.assertIsNone(row["native_component"])
        self.assertFalse((self.root / "future-bundle").exists())

    def test_runtime_byte_identity_and_executable_mode_are_required(self):
        custody = self.staged()
        request = self.request(custody)
        path = Path(request["rscript"]["path"])
        original = path.read_bytes()
        path.write_bytes(b"changed generated executable")
        with self.assertRaises(ValueError):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "binding.json"))
        path.write_bytes(original)
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "executable_mode_required"):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "binding.json"))

    def test_producer_destination_cannot_reuse_existing_or_stage_tree(self):
        custody = self.staged()
        request = self.request(custody)
        request["bundle_output"] = str(self.stage_root / "future-bundle")
        with self.assertRaisesRegex(ValueError, "distinct_producer_output"):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "binding.json"))
        request["bundle_output"] = str(self.root / "exists")
        Path(request["bundle_output"]).mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "new_path_required"):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "binding.json"))

    def test_qualification_binds_only_existing_closure_verifier_and_bridge(self):
        custody = self.staged()
        request = self.request(custody, "qualification")
        output = self.root / "binding.json"
        op.bind(request, str(IMPLEMENTATIONS), str(output))
        row = json.loads(output.read_text())
        self.assertEqual([x["role"] for x in row["commands"]],
            ["existing26_payload_closure", "existing17_native_consistency", "existing_receipt_bridge"])
        self.assertEqual(row["native_component_status"], "reviewed_private_requires_root_selection")
        self.assertFalse(row["native_verifier_executed"])
        self.assertFalse(row["runtime_admitted"])
        self.assertFalse(Path(request["native_receipt"]).exists())
        self.assertIn("metadata only", row["preconditions"][0])
        (Path(request["payload_view"]) / "MANIFEST.json").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "exact26_payload_view"):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "second-binding.json"))

    def test_qualification_native_source_changes_block_binding(self):
        custody = self.staged()
        request = self.request(custody, "qualification")
        (self.native / "native_verifier.R").write_bytes(b"changed source")
        with self.assertRaises(ValueError):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "binding.json"))
        self.assertFalse((self.root / "binding.json").exists())

    def test_qualification_receipt_cannot_enter_payload_view(self):
        custody = self.staged()
        request = self.request(custody, "qualification")
        request["native_receipt"] = str(Path(request["payload_view"]) / "receipt.json")
        with self.assertRaisesRegex(ValueError, "qualification_outputs_outside_view"):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "binding.json"))

    def test_rewritten_consumer_membership_in_custody_is_rejected(self):
        custody = self.staged()
        path = Path(custody["path"])
        row = json.loads(path.read_text())
        row["consumers"].pop("nider-primary-producer-v2/source_selection.R")
        path.write_text(json.dumps(row))
        changed = raw_pin(path)
        with self.assertRaisesRegex(ValueError, "consumer_binding_changed"):
            op.recheck_stage(self.c, changed["path"], changed["sha256"], str(IMPLEMENTATIONS))

    def test_existing_binding_and_placeholder_pin_cannot_be_used(self):
        custody = self.staged()
        request = self.request(custody)
        output = self.root / "binding.json"
        output.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "new_path_required"):
            op.bind(request, str(IMPLEMENTATIONS), str(output))
        self.assertEqual(output.read_bytes(), b"preserve")
        request["rscript"]["sha256"] = "OWNER_MUST_FILL"
        with self.assertRaises(ValueError):
            op.bind(request, str(IMPLEMENTATIONS), str(self.root / "different.json"))

    def test_cli_request_digest_and_duplicate_keys_fail_closed(self):
        request = self.root / "request.json"
        request.write_bytes(b'{"schema":"x","schema":"y"}')
        argv = ["prepare_original_inputs.py", "stage", "--implementation-root", str(IMPLEMENTATIONS),
                "--request", str(request), "--request-sha256", raw_pin(request)["sha256"],
                "--output", str(self.stage_root)]
        with mock.patch.object(sys, "argv", argv), self.assertRaisesRegex(ValueError, "duplicate_json_key"):
            op.main()
        argv[argv.index("--request-sha256") + 1] = "0" * 64
        with mock.patch.object(sys, "argv", argv), self.assertRaises(ValueError):
            op.main()
        self.assertFalse(self.stage_root.exists())


class LimitedOutput:
    def __init__(self, stream):
        self.stream = stream
        self.remaining = 15360

    def write(self, value):
        raw = value.encode()
        keep = raw[:self.remaining].decode(errors="ignore")
        self.remaining -= len(keep.encode())
        self.stream.write(keep)
        return len(value)

    def flush(self):
        self.stream.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementations", required=True)
    args = parser.parse_args()
    IMPLEMENTATIONS = Path(args.implementations).resolve()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OriginalCustodyControls)
    result = unittest.TextTestRunner(stream=LimitedOutput(sys.stdout), verbosity=2).run(suite)
    print(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "skips": len(result.skipped),
                      "scope": "generated_only_no_native_execution"}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
