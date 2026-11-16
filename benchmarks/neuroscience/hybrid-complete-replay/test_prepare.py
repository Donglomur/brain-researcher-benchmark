"""Invented source/admission tests; no authentic asset is opened."""
from copy import deepcopy
import builtins
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
import types
import unittest
from unittest.mock import patch


def invented_binding(base):
    paths = {name: str(base / name) for name in
        ("base_entry", "cases", "references", "runtime_receipt", "operator_home",
         "caller", "capacity_binding", "output", "docker_config")}
    paths["venv"] = str(base / "venv")
    paths["venv_entry"] = str(base / "venv/bin/python3.11")
    observation = {kind: {"path": str(base / kind), "physical_identity":
        [1, 2**53 + 1, 99, 2**60 + 1, 2**60 + 3, 1],
        "mode": mode, "uid": 501, "gid": 20}
        for kind, mode in (("binary", stat.S_IFREG | 0o755), ("socket", stat.S_IFSOCK | 0o600))}
    return {"schema": "hybrid-operator-local-binding-v1", "paths": paths,
        "operation_token": "invented-controls-only-0001",
        "endpoint": {"original_executable_path": str(base / "alias"),
                     "original_symlink_target": "binary", "expected_observation": observation},
        "historical_artifact_locations": None}


def run(prepare, root, manifest_sha, *, whole=True):
    class Admission(unittest.TestCase):
        def setUp(self):
            self.tmp = tempfile.TemporaryDirectory(prefix="hybrid-source-invented-")
            self.base = Path(self.tmp.name).resolve()
            self.value = invented_binding(self.base)
            self.binding = self.base / "operator.json"
            self.dest = self.base / "source"

        def tearDown(self):
            self.tmp.cleanup()

        def materialize(self, value=None, source=root, digest=manifest_sha):
            raw = prepare.encode(self.value if value is None else value)
            self.binding.write_bytes(raw)
            return prepare.materialize(source, digest, self.binding, prepare.pin(raw), self.dest)

        def test_complete43_no_asset_reads_exact_scope_and_pin_cascade(self):
            result = self.materialize()
            self.assertFalse(result["asset_bodies_read"])
            self.assertFalse(result["execution_selected"])
            self.assertEqual((result["scope"]["participants"], result["scope"]["sessions"],
                              result["scope"]["trials"], result["scope"]["decisions"]), (20, 80, 4884, 163135))
            lock = json.loads((self.dest / "SOURCE_LOCK.json").read_bytes())
            self.assertEqual(len(lock["files"]), 43)
            for row in lock["files"]:
                self.assertEqual(prepare.pin(Path(row["path"]).read_bytes()), {k: row[k] for k in ("bytes", "sha256")})
            plan = json.loads((self.dest / "PLAN.json").read_bytes())
            old = json.loads((root / "PLAN.json").read_bytes())
            for name in ("cases", "references", "base_entry", "venv_entry", "runtime_receipt"):
                self.assertEqual({k: plan[name][k] for k in ("bytes", "sha256")}, {k: old[name][k] for k in ("bytes", "sha256")})
            self.assertEqual(plan["image"], old["image"])
            for relative in ("PLAN.json", "runner/PLAN.json"):
                new = json.loads((self.dest / relative).read_bytes())
                template = json.loads((root / relative).read_bytes())
                self.assertEqual(new["operator_home"], self.value["paths"]["operator_home"])
                for field in ("maximum_episodes", "worker_seconds", "outer_seconds", "resources", "private_output_cap_bytes"):
                    self.assertEqual(new[field], template[field])
            self.assertEqual(plan["endpoint_binding"]["expected_observation"]["binary"]["physical_identity"][1], 2**53 + 1)
            self.assertFalse(Path(self.value["paths"]["cases"]).exists())
            self.assertFalse(Path(self.value["paths"]["output"]).exists())

        def test_operator_cannot_override_scope_or_hash_or_add_field(self):
            for key, value in (("participants", 19), ("image", "other"), ("cases_sha256", "0" * 64)):
                bad = deepcopy(self.value); bad[key] = value
                with self.assertRaises(ValueError): self.materialize(bad)
                self.assertFalse(self.dest.exists())

        def test_float_bool_and_bad_types_in_physical_identity_rejected(self):
            for value in (float(2**60), True, -1, 2**64, "123"):
                bad = deepcopy(self.value)
                bad["endpoint"]["expected_observation"]["binary"]["physical_identity"][1] = value
                with self.assertRaises(ValueError): self.materialize(bad)
                self.assertFalse(self.dest.exists())

        def test_namespace_collision_alias_and_runtime_layout_rejected(self):
            for key, value in (("output", str(self.dest)), ("operator_home", "relative"),
                               ("venv_entry", str(self.base / "venv/bin/python"))):
                bad = deepcopy(self.value); bad["paths"][key] = value
                with self.assertRaises(ValueError): self.materialize(bad)
                self.assertFalse(self.dest.exists())
            self.dest.symlink_to(self.base)
            with self.assertRaises(ValueError): self.materialize()
            self.dest.unlink()

        def test_changed_dependency_rejects_before_creating_output(self):
            copy = self.base / "changed-source"
            shutil.copytree(root, copy)
            (copy / "runner/scoring.py").write_bytes(b"raise RuntimeError('must not execute')\n")
            with self.assertRaises(ValueError): self.materialize(source=copy)
            self.assertFalse(self.dest.exists())

        def test_incomplete_core_rejects_even_with_regenerated_manifest(self):
            copy = self.base / "incomplete-source"
            shutil.copytree(root, copy)
            lock = json.loads((copy / "SOURCE_LOCK.json").read_bytes())
            del lock["files"]["runner/consumer.py"]
            (copy / "SOURCE_LOCK.json").write_bytes(prepare.encode(lock))
            m = json.loads((copy / "SOURCE_MANIFEST.json").read_bytes())
            m["files"]["SOURCE_LOCK.json"] = prepare.pin((copy / "SOURCE_LOCK.json").read_bytes())
            raw = prepare.encode(m); (copy / "SOURCE_MANIFEST.json").write_bytes(raw)
            with self.assertRaises(ValueError): self.materialize(source=copy, digest=prepare.pin(raw)["sha256"])
            self.assertFalse(self.dest.exists())

        def test_duplicate_binding_keys_and_wrong_manifest_or_map_refused(self):
            self.binding.write_bytes(b'{"schema":1,"schema":2}')
            with self.assertRaises(ValueError):
                prepare.materialize(root, manifest_sha, self.binding, prepare.pin(self.binding.read_bytes()), self.dest)
            with self.assertRaises(ValueError): self.materialize(digest="0" * 64)
            bad = deepcopy(self.value); bad["historical_artifact_locations"] = {"path": str(self.base / "map"), "bytes": 131073, "sha256": "0" * 64}
            with self.assertRaises(ValueError): self.materialize(bad)
            self.assertFalse(self.dest.exists())

        def test_no_overwrite_existing_prepared_source(self):
            self.materialize()
            before = (self.dest / "SOURCE_LOCK.json").read_bytes()
            with self.assertRaises(ValueError): self.materialize()
            self.assertEqual((self.dest / "SOURCE_LOCK.json").read_bytes(), before)

        def selected_entry(self, name):
            module = types.ModuleType("invented_" + name.replace(".", "_"))
            module.__file__ = str(root / name)
            raw = (root / name).read_bytes()
            exec(compile(raw, module.__file__, "exec"), module.__dict__)
            return module

        def test_both_selected_entries_reject_changed_helper_before_execution(self):
            marker = self.base / "must-not-exist"
            malicious = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n").encode()
            malicious += b"#" * (prepare.HELPER_PIN[0] - len(malicious))
            helper = self.base / "source_binding.py"
            helper.write_bytes(malicious)
            for name in ("operation_outer.py", "operation_worker.py"):
                module = self.selected_entry(name)
                with self.assertRaisesRegex(ValueError, "bootstrap identity"):
                    module._verified_source_binding(self.base)
                self.assertFalse(marker.exists())

        def test_both_selected_entries_execute_authenticated_capture_not_reread(self):
            helper = self.base / "source_binding.py"
            captured = (root / "source_binding.py").read_bytes()
            original_compile = builtins.compile
            for name in ("operation_outer.py", "operation_worker.py"):
                module = self.selected_entry(name)
                helper.write_bytes(captured)
                seen = []
                def swap_after_capture(raw, filename, *args, **kwargs):
                    if filename == str(helper):
                        seen.append(raw)
                        helper.write_bytes(b"raise RuntimeError('changed after authenticated read')\n")
                    return original_compile(raw, filename, *args, **kwargs)
                with patch.object(builtins, "compile", swap_after_capture):
                    loaded = module._verified_source_binding(self.base)
                self.assertEqual(seen, [captured])
                self.assertTrue(callable(loaded.load))
                self.assertEqual(loaded.__file__, str(helper))
                self.assertIs(sys.modules.pop("source_binding"), loaded)

        def test_selected_bootstrap_requires_fresh_namespace_and_cleans_failure(self):
            helper = self.base / "source_binding.py"
            helper.write_bytes((root / "source_binding.py").read_bytes())
            for name in ("operation_outer.py", "operation_worker.py"):
                module = self.selected_entry(name)
                occupied = types.ModuleType("source_binding")
                self.assertNotIn("source_binding", sys.modules)
                sys.modules["source_binding"] = occupied
                try:
                    with self.assertRaisesRegex(ValueError, "fresh source_binding"):
                        module._verified_source_binding(self.base)
                    self.assertIs(sys.modules["source_binding"], occupied)
                finally:
                    sys.modules.pop("source_binding", None)
                with patch.object(builtins, "compile", side_effect=RuntimeError("invented compile refusal")):
                    with self.assertRaisesRegex(RuntimeError, "invented compile refusal"):
                        module._verified_source_binding(self.base)
                self.assertNotIn("source_binding", sys.modules)

        def test_both_actual_bootstraps_load_entire_materialized43_source_graph(self):
            receipt = self.materialize()
            original_import = builtins.__import__
            def guard(name, *args, **kwargs):
                if name.split(".")[0] in {"numpy", "scipy", "torch", "jax", "tensorflow"}:
                    raise AssertionError("scientific runtime import is prohibited")
                return original_import(name, *args, **kwargs)
            for name in ("operation_outer.py", "operation_worker.py"):
                module = self.selected_entry(name)
                before = dict(sys.modules)
                try:
                    with patch.object(builtins, "__import__", guard), \
                         patch.object(subprocess, "Popen", side_effect=AssertionError("native dispatch prohibited")), \
                         patch.object(os, "system", side_effect=AssertionError("native shell prohibited")):
                        helper = module._verified_source_binding(self.dest)
                        plan, lock, bodies, delivery, sources, owner, modules = helper.load(receipt["source_lock"]["sha256"])
                        self.assertEqual(len(lock["files"]), 43)
                        self.assertEqual(plan["producer_delivery_source_closure"], sources.closure)
                        self.assertEqual((plan["scope"]["participants"], plan["scope"]["sessions"], plan["maximum_episodes"]), (20, 80, 4884))
                        self.assertEqual(plan["venv_entry"]["path"], self.value["paths"]["venv"] + "/bin/python3.11")
                        helper.recheck(lock)
                        sources.check()
                        self.assertIs(sys.modules["source_binding"], helper)
                        self.assertFalse(Path(self.value["paths"]["cases"]).exists())
                finally:
                    for key in list(sys.modules):
                        if key not in before:
                            sys.modules.pop(key, None)
                    for key, value in before.items():
                        if sys.modules.get(key) is not value:
                            sys.modules[key] = value

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Admission))
    if not result.wasSuccessful():
        return False
    if not whole:
        print(json.dumps({"invented_only": True, "admission_controls": result.testsRun,
                          "unchanged_whole_operation_controls": 0,
                          "authentic_replay": False}, sort_keys=True))
        return True
    # Run the unchanged complete operation controls at a newly relocated source.
    # No actual owner main(), process spawn, fit, or authentic input is allowed.
    with tempfile.TemporaryDirectory(prefix="hybrid-whole-invented-") as temp:
        base = Path(temp).resolve()
        data = prepare.encode(invented_binding(base)); path = base / "binding.json"; path.write_bytes(data)
        destination = base / "source"
        receipt = prepare.materialize(root, manifest_sha, path, prepare.pin(data), destination)
        binding_body = (destination / "source_binding.py").read_bytes()
        assert prepare.pin(binding_body) == {"bytes": prepare.HELPER_PIN[0], "sha256": prepare.HELPER_PIN[1]}
        binding = types.ModuleType("source_binding"); binding.__file__ = str(destination / "source_binding.py")
        assert "source_binding" not in sys.modules
        sys.modules["source_binding"] = binding
        exec(compile(binding_body, binding.__file__, "exec"), binding.__dict__)
        lock = json.loads((destination / "SOURCE_LOCK.json").read_bytes())
        descriptor = next(x for x in lock["files"] if x["path"] == str(destination / "test_operation.py"))
        test_body = binding.exact(descriptor["path"], descriptor)
        suite_module = types.ModuleType("hybrid_complete_invented_controls")
        suite_module.__file__ = descriptor["path"]
        exec(compile(test_body, descriptor["path"], "exec"), suite_module.__dict__)
        full = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(suite_module))
        print(json.dumps({"invented_only": True, "admission_controls": result.testsRun,
            "unchanged_whole_operation_controls": full.testsRun, "full_scope": receipt["scope"],
            "historical_reference_refits": 0, "authentic_replay": False}, sort_keys=True))
        return full.wasSuccessful()
