"""Generated assembly controls, not neural scoring or image-fidelity tests.

One shared full48/54x20 invented fixture and one successful117-file export are
used for the complete suite. PNG containers have correct CRC/header structure
but deliberately no decoded pixels. The b'{}\n' engineering answer is unscored.
All fixture writes, output writes and mutation/restoration bytes are charged
before writing, with a512KiB cumulative cap. No authentic data are used.
"""
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
import builtins
import importlib
from importlib.util import resolve_name
import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import attempt
import test_attempt as fixtures


FORBIDDEN_IMPORT_ROOTS = frozenset(("numpy", "PIL", "prepare", "attempt_grade"))


@contextmanager
def reject_scientific_imports():
    """Audit normal import routes, including cached roots and submodules.

    Existing modules are left untouched. This is import-causality measurement,
    not isolation from direct sys.modules access, captured aliases or custom
    loaders. Deliberate negative probes use their own separate record.
    """
    rejected = []
    original_import = builtins.__import__
    original_dynamic = importlib.import_module

    def check(name):
        if name.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
            rejected.append(name)
            raise AssertionError("forbidden scientific import: " + name)

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        resolved = name
        if level and globals and globals.get("__package__"):
            resolved = resolve_name("." * level + name, globals["__package__"])
        check(resolved)
        return original_import(name, globals, locals, fromlist, level)

    def guarded_dynamic(name, package=None):
        resolved = resolve_name(name, package) if name.startswith(".") else name
        check(resolved)
        return original_dynamic(name, package)

    with patch.object(builtins, "__import__", guarded_import), patch.object(
            importlib, "import_module", guarded_dynamic):
        yield rejected


def load_exporter_under_guard():
    # Compile the sibling source into a fresh namespace, even if discovery
    # already cached export_material. This also measures module initialization.
    path = Path(__file__).with_name("export_material.py")
    module = ModuleType("neural096_export_material_under_test")
    module.__file__ = str(path)
    with reject_scientific_imports() as rejected:
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    if rejected:
        raise AssertionError("exporter initialization attempted scientific imports")
    return module, rejected


exporter, EXPORT_INITIALIZATION_REJECTIONS = load_exporter_under_guard()


# Integrated CI uses the sibling implementation. The isolated source-pool
# runner may set this exact path before setUpClass; no source copy is required.
ATTEMPT_SOURCE = Path(__file__).with_name("attempt.py")


class ExportAssemblyControls(unittest.TestCase):
    WRITE_CEILING = 512 * 1024
    PROJECTED_CUMULATIVE_WRITE_BYTES = 465 * 1024

    @classmethod
    def charge(cls, count):
        cls.written_bytes += count
        if cls.written_bytes > cls.WRITE_CEILING:
            raise AssertionError("generated assembly cumulative write budget exceeded")

    @classmethod
    def write(cls, path, body):
        cls.charge(len(body))
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)

    @classmethod
    def file_pin(cls, path, body):
        return {"path": str(path), **exporter.pin(body)}

    @classmethod
    def put(cls, name, body):
        path = cls.inputs / name
        cls.write(path, body)
        return cls.file_pin(path, body)

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="n096-export-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name).resolve()
        cls.inputs = cls.root / "inputs"
        cls.inputs.mkdir(mode=0o700)
        cls.written_bytes = 0
        cls.successful_exports = 0
        cls.success_attempted = False
        cls.success_result = None
        cls.dispatch = []
        cls.captured = {}
        cls.verified_captures = []
        cls.native_copy_calls = 0
        cls.export_import_rejections = []
        cls.guard_probe_rejections = 0
        original_run = exporter.run_export
        def guarded_run(*args, **kwargs):
            with reject_scientific_imports() as rejected:
                try:
                    return original_run(*args, **kwargs)
                finally:
                    cls.export_import_rejections.extend(rejected)
                    if rejected:
                        raise AssertionError("export attempted scientific imports")
        handle = patch.object(exporter, "run_export", guarded_run)
        handle.start()
        cls.addClassCleanup(handle.stop)

        _, _, index, observations, unused_binding = fixtures.generated_inputs()
        cls.index_bytes, cls.observation_bytes = index, observations
        cls.index_pin = cls.put("i.json", index)
        cls.observation_pin = cls.put("o.json", observations)
        # This58B container tests byte custody only. No renderer or pixel
        # decoder is invoked, and no image-fidelity claim follows from it.
        cls.png_bytes = (b"\x89PNG\r\n\x1a\n"
            + fixtures.chunk(b"IHDR", struct.pack(">IIBBBBB", 1360, 1180, 8, 2, 0, 0, 0))
            + fixtures.chunk(b"IDAT", b"x") + fixtures.chunk(b"IEND", b""))
        cls.png_pin = cls.put("image.png", cls.png_bytes)
        plain_index = exporter.pin(index)
        plain_observation = exporter.pin(observations)
        preparation_binding = {
            "preparation_completion_sha256": "b" * 64,
            "preparation_receipt": exporter.pin(b"generated preparation receipt"),
            "observation": plain_observation,
        }
        observation_manifest = {
            "schema": "neural096-observation-delivery-manifest/v1",
            "method": attempt.METHOD, "source_binding": preparation_binding,
            "files": {"viewer/INDEX.json": plain_index,
                      "programme/observations.json": plain_observation},
        }
        observation_body = exporter.encoded(observation_manifest)
        observation_manifest_pin = cls.put("observation-manifest.json", observation_body)
        raster_files = {"INDEX.json": plain_index,
            **{"cells/" + identity + ".png": exporter.pin(cls.png_bytes) for identity in attempt.IDS}}
        raster_manifest = {
            "schema": "neural096-observation-raster-bundle/v1", "files": raster_files,
            "source_observation_manifest": exporter.pin(observation_body),
            "source_index": plain_index, "inherited_preparation_binding": preparation_binding,
        }
        raster_body = exporter.encoded(raster_manifest)
        raster_manifest_pin = cls.put("raster-manifest.json", raster_body)
        cls.binding = {
            "index_sha256": plain_index["sha256"],
            "observation_manifest_sha256": exporter.pin(observation_body)["sha256"],
            "observation_sha256": plain_observation["sha256"],
            "preparation_completion_sha256": "b" * 64,
            "renderer_manifest_sha256": exporter.pin(raster_body)["sha256"],
        }
        postflight = {
            "schema": "neural096-full48-independent-custody-postflight/v1",
            "status": "accepted_saved_full48_raster_custody",
            "images": 48, "supported_cells": 27, "unsupported_cells": 21,
            "native_materialization_source_binding": cls.binding,
            "output_inventory": {"bundle/MANIFEST.json": exporter.pin(raster_body),
                **{"bundle/" + name: value for name, value in raster_files.items()}},
        }
        cls.postflight_pin = cls.put("postflight.json", exporter.encoded(postflight))
        # Public sibling documents contain the real task/answer contract;
        # only observations, PNG containers and source-provenance facts here
        # are generated. No document content is used as a scored answer.
        cls.instruction = Path(__file__).with_name("INSTRUCTION.md").read_bytes()
        cls.contract = Path(__file__).with_name("ANSWER_CONTRACT.json").read_bytes()
        cls.instruction_pin = cls.put("instruction.txt", cls.instruction)
        cls.contract_pin = cls.put("contract.json", cls.contract)
        source = Path(ATTEMPT_SOURCE).resolve()
        source_body = source.read_bytes()
        if exporter.pin(source_body) != exporter.ATTEMPT_PIN:
            raise AssertionError("generated controls require the exact frozen attempt source")
        cls.unused_root = cls.root / "unused0"
        cls.success_root = cls.root / "success"
        cls.partial_root = cls.root / "partial"
        cls.protocol = {
            "schema": exporter.SCHEMA,
            "attempt_source": cls.file_pin(source, source_body),
            "input": {"index": cls.index_pin, "observations": cls.observation_pin,
                "pngs": {identity: cls.png_pin for identity in attempt.IDS},
                "source_binding": cls.binding},
            "documents": {"instruction": cls.instruction_pin, "answer_contract": cls.contract_pin},
            "provenance": {"raster_postflight": cls.postflight_pin,
                "raster_manifest": raster_manifest_pin,
                "observation_manifest": observation_manifest_pin},
            "output_root": str(cls.unused_root),
            "limits": {"output_bytes": 8 * 1024**2, "application_read_bytes": 64 * 1024**2},
            "condition": {"method": attempt.METHOD, "engineering_only": True,
                          "cells": 48, "supported": 27, "unsupported": 21},
        }
        cls.protocol_bytes = exporter.encoded(cls.protocol)
        cls.protocol_path = cls.inputs / "protocol.json"
        cls.write(cls.protocol_path, cls.protocol_bytes)
        cls.protocol_sha = exporter.pin(cls.protocol_bytes)["sha256"]

        original_write = exporter.write_output
        def counted_write(context, relative, body, writer=None):
            cls.charge(len(body))
            return original_write(context, relative, body, writer=writer)
        handle = patch.object(exporter, "write_output", counted_write)
        handle.start()
        cls.addClassCleanup(handle.stop)

        original_load = exporter.load_attempt
        def observed_load(path, expected_pin, budget):
            core = original_load(path, expected_pin, budget)
            request, capture, final = core.request_observation, core.submit_final, core.get_final
            def observed_request(material_root, attempt_root, attempt_sha, selected):
                response = request(material_root, attempt_root, attempt_sha, selected)
                cls.dispatch.append((Path(attempt_root).name, dict(selected)))
                return response
            def observed_capture(attempt_root, attempt_sha, answer):
                if answer != b"{}\n":
                    raise AssertionError("engineering sentinel changed")
                result = capture(attempt_root, attempt_sha, answer)
                cls.captured[str(attempt_root)] = result["receipt_pin"]
                return result
            def observed_final(attempt_root, attempt_sha, final_sha):
                anchor = cls.captured[str(attempt_root)]
                if final_sha != anchor["sha256"]:
                    raise AssertionError("get_final did not receive capture-returned external pin")
                commits = Path(attempt_root).parents[1] / "operator/CAPTURE_COMMITS.json"
                if not commits.is_file():
                    raise AssertionError("external capture commits missing before final readback")
                saved = exporter.decoded(commits.read_bytes())
                if saved["captures"][Path(attempt_root).name]["final_receipt"] != anchor:
                    raise AssertionError("external capture commits differ from capture return")
                result = final(attempt_root, attempt_sha, final_sha)
                cls.verified_captures.append((str(attempt_root), final_sha))
                return result
            core.request_observation, core.submit_final, core.get_final = (
                observed_request, observed_capture, observed_final)
            return core
        handle = patch.object(exporter, "load_attempt", observed_load)
        handle.start()
        cls.addClassCleanup(handle.stop)
        original_native = exporter.materialize_native
        def observed_native(context):
            cls.native_copy_calls += 1
            return original_native(context)
        handle = patch.object(exporter, "materialize_native", observed_native)
        handle.start()
        cls.addClassCleanup(handle.stop)

    @classmethod
    @contextmanager
    def changed_bytes(cls, path, modified):
        """Patch only differing bytes; charge patches and restores separately."""
        original = path.read_bytes()
        if len(original) != len(modified):
            raise AssertionError("generated mutations must preserve file extent")
        differences = [(i, old, new) for i, (old, new) in enumerate(zip(original, modified)) if old != new]
        def apply(which):
            descriptor = os.open(path, os.O_RDWR)
            with os.fdopen(descriptor, "r+b") as handle:
                for offset, old, new in differences:
                    cls.charge(1)
                    handle.seek(offset)
                    handle.write(bytes((new if which else old,)))
        apply(True)
        try:
            yield exporter.pin(modified)["sha256"]
        finally:
            apply(False)

    @classmethod
    @contextmanager
    def destination(cls, path):
        source, target = str(cls.unused_root).encode(), str(path).encode()
        if len(source) != len(target) or cls.protocol_bytes.count(source) != 1:
            raise AssertionError("fixed-width generated destination convention changed")
        modified = cls.protocol_bytes.replace(source, target)
        with cls.changed_bytes(cls.protocol_path, modified) as sha:
            yield sha

    def success(self):
        cls = type(self)
        if cls.success_result is None:
            self.assertFalse(cls.success_attempted, "prior full export failed; automatic retry refused")
            cls.success_attempted = True
            with cls.destination(cls.success_root) as sha:
                cls.success_result = exporter.run_export(cls.protocol_path, sha)
            cls.successful_exports += 1
        self.assertEqual(cls.successful_exports, 1)
        return cls.success_result

    def assert_import_guard_with_preloaded_modules(self):
        original_import, original_dynamic = builtins.__import__, importlib.import_module
        preexisting = {name: sys.modules[name] for name in FORBIDDEN_IMPORT_ROOTS if name in sys.modules}
        added = {name: ModuleType(name) for name in FORBIDDEN_IMPORT_ROOTS if name not in sys.modules}
        sys.modules.update(added)
        try:
            for name in sorted(FORBIDDEN_IMPORT_ROOTS):
                probes = (
                    lambda name=name: builtins.__import__(name),
                    lambda name=name: builtins.__import__(name + ".__guard_probe__"),
                    lambda name=name: importlib.import_module(name),
                    lambda name=name: importlib.import_module(".__guard_probe__", name),
                    lambda name=name: builtins.__import__("__guard_probe__", {"__package__": name}, None, (), 1),
                )
                for probe in probes:
                    with self.assertRaisesRegex(AssertionError, "forbidden scientific import"):
                        with reject_scientific_imports() as rejected:
                            probe()
                    self.assertEqual(len(rejected), 1)
                    type(self).guard_probe_rejections += 1
                    self.assertIs(builtins.__import__, original_import)
                    self.assertIs(importlib.import_module, original_dynamic)
            with reject_scientific_imports() as rejected:
                self.assertIs(builtins.__import__("math"), sys.modules["math"])
            self.assertEqual(rejected, [])
            self.assertIs(builtins.__import__, original_import)
            self.assertIs(importlib.import_module, original_dynamic)
            for name, module in {**preexisting, **added}.items():
                self.assertIs(sys.modules[name], module)
        finally:
            for name, module in added.items():
                if sys.modules.get(name) is module:
                    del sys.modules[name]
        for name, module in preexisting.items():
            self.assertIs(sys.modules[name], module)
        self.assertEqual(type(self).guard_probe_rejections, 20)

    def test_complete_117_files_full_traversal_and_shared_bindings(self):
        self.assert_import_guard_with_preloaded_modules()
        result = self.success()
        self.assertEqual(result["status"], "exported_engineering_only")
        self.assertEqual(result["files"], 117)
        self.assertEqual(set(result["expected_files"]), exporter.allowed_files())
        self.assertEqual(sum(name.startswith("material/") for name in result["expected_files"]), 53)
        self.assertEqual(sum(name.startswith("engineering/") for name in result["expected_files"]), 59)
        self.assertEqual(sum(name.startswith("operator/") for name in result["expected_files"]), 5)
        self.assertEqual(result["bytes"], sum(item["bytes"] for item in result["expected_files"].values()))
        wanted = [("native", {"kind": "index"})]
        wanted += [("native", {"kind": "view", "cell_id": identity}) for identity in attempt.IDS]
        wanted += [("programme", {"kind": "index"}), ("programme", {"kind": "observations"})]
        self.assertEqual(self.dispatch, wanted)
        self.assertEqual(len(self.verified_captures), 2)
        index_paths = [self.success_root / "material" / arm / "INDEX.json" for arm in ("native", "programme")]
        self.assertEqual(index_paths[0].read_bytes(), index_paths[1].read_bytes())
        index = exporter.decoded(index_paths[0].read_bytes())
        self.assertEqual(len(index["cells"]), 48)
        self.assertEqual(sum(cell["supported"] for cell in index["cells"]), 27)
        self.assertEqual(len(index["unit_ids"]), 54)
        self.assertEqual(index["phase_bins"], 20)
        self.assertEqual((self.success_root / "material/programme/observations.json").read_bytes(), self.observation_bytes)
        for arm in ("native", "programme"):
            folder = self.success_root / "engineering" / arm
            manifest = exporter.decoded((folder / "ATTEMPT.json").read_bytes())
            final = exporter.decoded((folder / "FINAL.json").read_bytes())
            for name, body in (("instruction_sha256", self.instruction), ("answer_contract_sha256", self.contract)):
                self.assertEqual(manifest[name], exporter.pin(body)["sha256"])
                self.assertEqual(final[name], manifest[name])
            self.assertEqual(manifest["index_sha256"], self.binding["index_sha256"])
            self.assertEqual((folder / "ANSWER.bin").read_bytes(), b"{}\n")
            self.assertEqual(manifest["config"]["max_final_answer_bytes"], 3)
        receipt = exporter.decoded((self.success_root / "operator/EXPORT_RECEIPT.json").read_bytes())
        self.assertTrue(all(value is False for value in receipt["qualification"].values()))
        self.assertFalse(receipt["qualification"]["engineering_answer_graded"])
        self.assertLessEqual(self.written_bytes, self.WRITE_CEILING)
        self.assertEqual(EXPORT_INITIALIZATION_REJECTIONS, [])
        self.assertEqual(self.export_import_rejections, [])

    def test_input_pin_and_source_preimage_failures_precede_any_copy(self):
        before = self.native_copy_calls
        with self.assertRaisesRegex(exporter.ExportError, "protocol_identity"):
            exporter.run_export(self.protocol_path, "0" * 64)
        source_sha = exporter.ATTEMPT_PIN["sha256"].encode()
        self.assertEqual(self.protocol_bytes.count(source_sha), 1)
        changed_sha = (b"0" if source_sha[:1] != b"0" else b"1") + source_sha[1:]
        with self.changed_bytes(self.protocol_path, self.protocol_bytes.replace(source_sha, changed_sha)) as sha:
            with self.assertRaisesRegex(exporter.ExportError, "metadata_value"):
                exporter.run_export(self.protocol_path, sha)
        # A freshly pinned but inconsistent provenance fact must still fail
        # the cross-record join, not merely a stale-file hash check.
        postflight = Path(self.postflight_pin["path"])
        original_postflight = postflight.read_bytes()
        self.assertEqual(original_postflight.count(b"b" * 64), 1)
        changed_postflight = original_postflight.replace(b"b" * 64, b"c" * 64)
        old_pin = self.postflight_pin["sha256"].encode()
        new_pin = exporter.pin(changed_postflight)["sha256"].encode()
        self.assertEqual(self.protocol_bytes.count(old_pin), 1)
        with self.changed_bytes(postflight, changed_postflight):
            with self.changed_bytes(self.protocol_path, self.protocol_bytes.replace(old_pin, new_pin)) as sha:
                with self.assertRaisesRegex(exporter.ExportError, "metadata_value"):
                    exporter.run_export(self.protocol_path, sha)
        for path in (Path(self.instruction_pin["path"]), Path(self.png_pin["path"])):
            with self.subTest(input=path.name):
                original = path.read_bytes()
                changed = bytes((original[0] ^ 1,)) + original[1:]
                with self.changed_bytes(path, changed):
                    with self.assertRaisesRegex(exporter.ExportError, "metadata_value"):
                        exporter.run_export(self.protocol_path, self.protocol_sha)
        self.assertEqual(self.native_copy_calls, before)
        self.assertFalse(self.unused_root.exists())

    def test_output_collision_and_unlisted_private_entries_are_refused(self):
        result = self.success()
        before = self.native_copy_calls
        with self.destination(self.success_root) as sha:
            with self.assertRaisesRegex(exporter.ExportError, "fresh_export_root_required"):
                exporter.run_export(self.protocol_path, sha)
        self.assertEqual(self.native_copy_calls, before)
        for relative, body in (("unexpected.json", b"{}\n"), ("private/reference.json", b"{}\n")):
            target = self.success_root / relative
            added_directory = target.parent != self.success_root
            if added_directory:
                target.parent.mkdir(mode=0o700)
            try:
                self.write(target, body)
                with self.assertRaisesRegex(exporter.ExportError, "extra_"):
                    exporter.verify_closed_output(self.success_root, result["expected_files"])
            finally:
                target.unlink()
                if added_directory:
                    target.parent.rmdir()
        empty = self.success_root / "private"
        empty.mkdir(mode=0o700)
        try:
            with self.assertRaisesRegex(exporter.ExportError, "extra_or_nonprivate_output_directory"):
                exporter.verify_closed_output(self.success_root, result["expected_files"])
        finally:
            empty.rmdir()
        missing = self.success_root / "material/native/cells" / (attempt.IDS[-1] + ".png")
        parked = self.root / "temporarily-parked-generated.png"
        missing.rename(parked)
        try:
            with self.assertRaisesRegex(exporter.ExportError, "missing_output"):
                exporter.verify_closed_output(self.success_root, result["expected_files"])
        finally:
            parked.rename(missing)
        verified = exporter.verify_closed_output(self.success_root, result["expected_files"])
        self.assertEqual(verified, {"files": 117, "bytes": result["bytes"]})

    def test_nonprivate_output_modes_are_refused_without_payload_rewrites(self):
        result = self.success()
        cases = ((self.success_root, 0o700, 0o755, "private_output_root_mode"),
                 (self.success_root / "material/native", 0o700, 0o755, "extra_or_nonprivate_output_directory"),
                 (self.success_root / "engineering/native/LOCK", 0o600, 0o644, "extra_special_or_nonprivate_output"))
        for path, original, changed, refusal in cases:
            with self.subTest(path=str(path.relative_to(self.success_root))):
                path.chmod(changed)
                try:
                    with self.assertRaisesRegex(exporter.ExportError, refusal):
                        exporter.verify_closed_output(self.success_root, result["expected_files"])
                finally:
                    path.chmod(original)
        self.assertEqual(exporter.verify_closed_output(self.success_root, result["expected_files"]),
                         {"files": 117, "bytes": result["bytes"]})

    def test_partial_failure_is_preserved_and_same_destination_is_not_retried(self):
        def stop_before_copy(context):
            raise RuntimeError("generated interruption before native material copy")
        with self.destination(self.partial_root) as sha:
            with patch.object(exporter, "materialize_native", side_effect=stop_before_copy) as copy:
                with self.assertRaisesRegex(RuntimeError, "generated interruption"):
                    exporter.run_export(self.protocol_path, sha)
                self.assertEqual(copy.call_count, 1)
                names = {str(path.relative_to(self.partial_root)) for path in self.partial_root.rglob("*") if path.is_file()}
                self.assertEqual(names, {"operator/INSTRUCTION.md", "operator/ANSWER_CONTRACT.json", "operator/PROTOCOL.json"})
                before = {name: exporter.pin((self.partial_root / name).read_bytes()) for name in names}
                with self.assertRaisesRegex(exporter.ExportError, "fresh_export_root_required"):
                    exporter.run_export(self.protocol_path, sha)
                self.assertEqual(copy.call_count, 1)
                self.assertEqual(before, {name: exporter.pin((self.partial_root / name).read_bytes()) for name in names})
        self.assertFalse((self.partial_root / "operator/EXPORT_RECEIPT.json").exists())
        self.assertFalse((self.partial_root / "operator/CAPTURE_COMMITS.json").exists())
        self.assertEqual(self.protocol_path.read_bytes(), self.protocol_bytes)
        self.assertLessEqual(self.written_bytes, self.WRITE_CEILING)


if __name__ == "__main__":
    unittest.main()
