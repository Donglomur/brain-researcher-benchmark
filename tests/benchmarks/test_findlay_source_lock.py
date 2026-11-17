"""Generated source-lock controls; no Git, native parsers or original inputs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RUNNER = "benchmarks/shared/findlay-sleep/census-continuation/owner/run.py"
CURRENT = "benchmarks/integrity/current-closures/findlay-sleep/source-manifest.json"
PREVIOUS = "benchmarks/integrity/current-closures/trust-findlay/predecessor-source-manifest.json"
BINDER = "benchmarks/shared/findlay-sleep/preparation/bind_request.py"


def content_pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class FindlaySourceLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.root = self.parent / "repo"
        self.root.mkdir()
        self.module = types.ModuleType("generated_findlay_owner")
        self.module.__file__ = str(self.root / "owner/run.py")
        body = (ROOT / RUNNER).read_bytes()
        exec(compile(body, self.module.__file__, "exec"), self.module.__dict__)
        self.bodies = {
            "owner/run.py": body,
            "worker/worker.py": b"# Generated worker; never executed.\n",
            "worker/helper.py": b"GENERATED_VALUE = 1\n",
            "worker/external_contract.py": (
                b"import json\n"
                b"def authenticate(field, body): return json.loads(body)\n"
                b"def join(values):\n"
                b"    assert set(values) == {'input_ledger', 'published_families', 'private_policy'}\n"
            ),
        }
        # Generated owner bodies test graph identity; no process owner executes.
        self.module.OWNER_PINS = {}
        for name in ("process_owner.py", "group_bootstrap.py", "trusted_controller.py"):
            generated = ("# Generated " + name + "\n").encode()
            self.bodies[self.module.OWNER_ROOT + name] = generated
            self.module.OWNER_PINS[name] = content_pin(generated)
        for relative, value in self.bodies.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        self.lock = {
            "schema": "findlay-intake-source-lock/v1", "repository_root": str(self.root),
            "execution_authority": False,
            "entrypoint": {"path": "owner/run.py", **content_pin(body)},
            "worker": {"path": "worker/worker.py", **content_pin(self.bodies["worker/worker.py"])},
            "files": {name: content_pin(value) for name, value in self.bodies.items()},
        }
        self.request = {"execution": {
            "repository_root": str(self.root),
            "source_adoption": {"commit": "a" * 40, "worker": self.lock["worker"]},
        }, "task": {}}
        for field in ("input_ledger", "published_families", "private_policy"):
            value = json.dumps({"generated": field}).encode()
            path = self.parent / (field + ".json")
            path.write_bytes(value)
            self.request["task"][field] = {"path": str(path), **content_pin(value)}

    def read_lock(self, value=None):
        body = self.module.canonical(self.lock if value is None else value)
        path = self.parent / "source-lock.json"
        path.write_bytes(body)
        self.request["execution"]["source_lock"] = {"path": str(path), **content_pin(body)}
        return self.module.source_lock(self.request)

    def git_response(self, argv, **kwargs):
        self.assertEqual(argv[:4], ["/usr/bin/git", "-C", str(self.root), "cat-file"])
        operation, spec = argv[-2:]
        commit, relative = spec.split(":", 1)
        self.assertEqual(commit, "a" * 40)
        body = self.bodies[relative]
        output = str(len(body)).encode() + b"\n" if operation == "-s" else body
        return types.SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    def test_valid_lock_and_adopted_capture_preserve_exact_graph(self):
        selected = self.read_lock()
        with mock.patch.object(self.module.subprocess, "run", side_effect=self.git_response) as git:
            captured, total = self.module.source_capture(
                self.request, selected, time.monotonic() + 5, adopted=True)
        self.assertEqual(git.call_count, 2 * len(self.bodies))
        for name, body in self.bodies.items():
            self.assertEqual(captured[name], body)
        self.assertEqual(total, 2 * sum(map(len, self.bodies.values()))
                         + sum(pin["bytes"] for pin in self.request["task"].values()))
        self.assertFalse(selected["execution_authority"])

    def test_pin_path_cannot_redirect_working_source_to_an_adopted_copy(self):
        donor = self.parent / "matching-adopted-copy.py"
        donor.write_bytes(self.bodies["worker/helper.py"])
        (self.root / "worker/helper.py").write_bytes(b"GENERATED_VALUE = 2\n")
        altered = copy.deepcopy(self.lock)
        altered["files"]["worker/helper.py"]["path"] = str(donor)
        with self.assertRaisesRegex(ValueError, "Exact source-member content pin"):
            self.read_lock(altered)
        # Direct helper invocation must not bypass the same intake check.
        with mock.patch.object(self.module, "checked", side_effect=AssertionError("No reads")), \
             mock.patch.object(self.module.subprocess, "run", side_effect=AssertionError("No Git")), \
             self.assertRaisesRegex(ValueError, "Exact source-member content pin"):
            self.module.source_capture(self.request, altered, time.monotonic() + 5, adopted=True)

    def test_changed_working_member_cannot_be_replaced_by_adopted_bytes(self):
        selected = self.read_lock()
        (self.root / "worker/helper.py").write_bytes(b"GENERATED_VALUE = 2\n")
        with mock.patch.object(self.module.subprocess, "run", side_effect=self.git_response), \
             self.assertRaisesRegex(ValueError, "Selected file pin mismatch"):
            self.module.source_capture(self.request, selected, time.monotonic() + 5, adopted=True)

    def test_noncanonical_graph_keys_refuse(self):
        for invalid in ("../helper.py", "/tmp/helper.py", "worker//helper.py", "worker/./helper.py",
                        "worker/helper.json", 12):
            altered = copy.deepcopy(self.lock)
            pin = altered["files"].pop("worker/helper.py")
            altered["files"][invalid] = pin
            with self.subTest(key=invalid), self.assertRaises(ValueError):
                # Avoid JSON changing the type of a nonstring graph key.
                self.module.source_members(altered["files"])

    def test_member_pin_shape_and_numeric_types_refuse(self):
        invalid = [None, [], {}, {"bytes": 1}, {"bytes": True, "sha256": "a" * 64},
                   {"bytes": 0, "sha256": "a" * 64}, {"bytes": -1, "sha256": "a" * 64},
                   {"bytes": 262145, "sha256": "a" * 64},
                   {"bytes": 1, "sha256": "not-a-hash"},
                   {"bytes": 1, "sha256": "a" * 64, "unexpected": 0}]
        for pin in invalid:
            altered = copy.deepcopy(self.lock)
            altered["files"]["worker/helper.py"] = pin
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                self.read_lock(altered)

    def test_source_role_descriptors_are_exact(self):
        for role in ("entrypoint", "worker"):
            altered = copy.deepcopy(self.lock)
            altered[role]["unselected_path"] = "/generated/not-used"
            if role == "worker":
                self.request["execution"]["source_adoption"]["worker"] = altered[role]
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "source-role descriptor"):
                self.read_lock(altered)

    def test_source_lock_never_grants_execution_authority(self):
        altered = copy.deepcopy(self.lock)
        altered["execution_authority"] = True
        with self.assertRaisesRegex(ValueError, "nonauthorizing source lock"):
            self.read_lock(altered)

    def test_request_binder_rejects_override_before_remaining_graph_or_private_reads(self):
        binder = types.ModuleType("generated_findlay_binder")
        binder.__file__ = str(ROOT / BINDER)
        exec(compile((ROOT / BINDER).read_bytes(), binder.__file__, "exec"), binder.__dict__)
        binder.ROOT = self.root
        binder.CURRENT_MANIFEST = self.parent / "current-manifest.json"
        manifest = {key: copy.deepcopy(value) for key, value in self.lock.items()
                    if key != "repository_root"}
        manifest["schema"] = "findlay-portable-source-manifest/v1"
        for index in range(14 - len(manifest["files"])):
            manifest["files"]["worker/extra_%d.py" % index] = content_pin(b"# generated\n")
        manifest["files"]["worker/helper.py"]["path"] = str(self.parent / "donor.py")
        binder.CURRENT_MANIFEST.write_bytes(self.module.canonical(manifest))
        write_dir = self.parent / "bindings"
        write_dir.mkdir()
        output = self.root / "artifacts-build" / "new-operation"
        output.parent.mkdir()
        args = types.SimpleNamespace(commit="a" * 40, write_dir=str(write_dir),
                                     operation_output=str(output))
        real_load = binder.load
        loaded = []

        def checked_load(*values):
            # The binder has already authenticated the entrypoint body. No
            # remaining graph member or private metadata may be read afterward.
            owner = real_load(*values)
            owner.capture = mock.Mock(side_effect=AssertionError("No graph or private reads"))
            loaded.append(owner)
            return owner

        with mock.patch.object(binder, "load", side_effect=checked_load), \
             self.assertRaisesRegex(ValueError, "Exact source-member content pin"):
            binder.build(args)
        self.assertEqual(len(loaded), 1)
        loaded[0].capture.assert_not_called()
        self.assertEqual(list(write_dir.iterdir()), [])
        self.assertFalse(output.exists())

    def test_current_closure_changes_only_runner_and_bootstrap(self):
        current = json.loads((ROOT / CURRENT).read_bytes())
        previous = json.loads((ROOT / PREVIOUS).read_bytes())
        self.assertEqual(set(current), set(previous))
        self.assertEqual(set(current["files"]), set(previous["files"]))
        changed = {name for name in current["files"] if current["files"][name] != previous["files"][name]}
        self.assertEqual(changed, {RUNNER, self.module.OWNER_ROOT + "group_bootstrap.py"})
        for relative, pin in current["files"].items():
            self.assertEqual(content_pin((ROOT / relative).read_bytes()), pin)
        self.assertEqual(current["entrypoint"], {"path": RUNNER, **current["files"][RUNNER]})
        self.assertEqual(current["worker"], previous["worker"])
        self.assertFalse(current["execution_authority"])


if __name__ == "__main__":
    unittest.main()
