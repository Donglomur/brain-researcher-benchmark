"""Invented metadata/relocation checks; no data, fits, scoring or runtime calls."""
import argparse
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
import stat
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).absolute().parent


def bounded_source(path, cap):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ordinary component source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap):
            raise ValueError("bounded ordinary component source")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(before.st_size + 1)
        if len(body) != before.st_size or stamp(before) != stamp(os.fstat(fd)) or stamp(before) != stamp(path.lstat()):
            raise ValueError("stable complete component source")
        return body
    finally:
        os.close(fd)


def admit_component(expected):
    raw = bounded_source(HERE / "SOURCE_MANIFEST.json", 65536)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("component manifest identity")
    manifest = json.loads(raw)
    bodies = {}
    for pin in manifest["files"]:
        name = pin["name"]
        if Path(name).name != name or name in bodies:
            raise ValueError("flat unique source roster")
        path = HERE / name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("ordinary component source")
        body = bounded_source(path, 262144)
        if len(body) > 262144 or len(body) != pin["bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
            raise ValueError("component member identity")
        bodies[name] = body
    if not {"provision.py", "source_binding.py", "test_provision.py"} <= bodies.keys():
        raise ValueError("complete component source")
    module = types.ModuleType("public_hybrid_provision")
    module.__file__ = str(HERE / "provision.py")
    exec(compile(bodies["provision.py"], module.__file__, "exec"), module.__dict__)
    return module


class MetadataControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hybrid-invented-metadata-")
        self.root = Path(self.temp.name).resolve()
        self.records = []
        for person in range(20):
            for session in range(4):
                number = person * 4 + session
                self.records.append({"invented_person": person, "invented_session": session,
                    "training_only": True, "outer_test_available_to_selector": False,
                    "artifacts": {"family_train_selected": {"path": str(self.root / "old" / ("opaque-%03d.json" % number)),
                        "bytes": 7, "sha256": hashlib.sha256(b"FAKE!!!").hexdigest()}}})
        self.reference = {"schema": "hybrid-complete-train-only-reference-v1", "complete_outer_folds": 80,
            "inner_ridge_fits": 720, "final_ridge_fits": 80, "artifact_manifest_private": self.records}
        self.fake_pin = (1, "0" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def test_full80_map_preserves_records_and_never_requires_model_files(self):
        original = deepcopy(self.reference)
        result = provision.locations_from_reference(self.reference, str(self.root / "new"), self.fake_pin)
        self.assertEqual(len(result["folds"]), 80)
        self.assertEqual(len({r["historical_record_sha256"] for r in result["folds"]}), 80)
        for record, row in zip(self.records, result["folds"]):
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(row["historical_record_sha256"], hashlib.sha256(canonical).hexdigest())
            pin = record["artifacts"]["family_train_selected"]
            self.assertEqual((row["location"]["bytes"], row["location"]["sha256"]), (pin["bytes"], pin["sha256"]))
            self.assertEqual(Path(row["location"]["path"]).name, Path(pin["path"]).name)
            self.assertFalse(Path(row["location"]["path"]).exists())
        self.assertEqual(self.reference, original)
        self.assertFalse((self.root / "new").exists())

    def test_incomplete_duplicate_and_boolean_metadata_are_refused(self):
        for kind in ("missing", "duplicate", "boolean", "oversize", "relative"):
            value = deepcopy(self.reference)
            if kind == "missing":
                value["artifact_manifest_private"].pop()
            elif kind == "duplicate":
                value["artifact_manifest_private"][1] = deepcopy(value["artifact_manifest_private"][0])
            else:
                pin = value["artifact_manifest_private"][0]["artifacts"]["family_train_selected"]
                if kind == "boolean": pin["bytes"] = True
                if kind == "oversize": pin["bytes"] = 65537
                if kind == "relative": pin["path"] = "relative.json"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                provision.locations_from_reference(value, str(self.root / "new"), self.fake_pin)

    def test_duplicate_json_and_nonfinite_values_are_refused(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                provision.strict(body)

    def test_fixed_reference_cli_cannot_accept_invented_input(self):
        reference = self.root / "invented-reference.json"
        reference.write_bytes(provision.canonical(self.reference))
        output = self.root / "must-not-exist.json"
        argv = [str(HERE / "provision.py"), "--source-manifest-sha256", SOURCE_SHA, "locations",
            "--reference", str(reference), "--artifact-directory", str(self.root / "models"), "--output", str(output)]
        previous = sys.argv
        try:
            sys.argv = argv
            with self.assertRaises(ValueError):
                provision.main()
        finally:
            sys.argv = previous
        self.assertFalse(output.exists())

    def test_unaccepted_external_source_is_refused_without_execution(self):
        folder = self.root / "external"
        folder.mkdir()
        (folder / "SOURCE_LOCK.json").write_bytes(b'{}')
        for name in provision.REPLACEMENTS:
            (folder / name).write_bytes(b"raise AssertionError('must never execute')\n")
        with self.assertRaises(ValueError): provision.admit_predecessor(str(folder))
        with self.assertRaises(ValueError): provision.admit_adapters(str(folder))

    def invented_admission(self):
        # This is an in-memory construction fixture. It cannot pass the public
        # CLI's immutable external-source admission and is never executable.
        origin = self.root / "invented-origin"
        plan = {"cases": {"path": str(self.root / "old-cases"), "bytes": 3, "sha256": "a" * 64},
            "references": {"path": str(self.root / "old-reference"), "bytes": 4, "sha256": "b" * 64},
            "docker_prefix": ["INVENTED-NOT-DOCKER", "--config", str(self.root / "old-config")],
            "producer_delivery_source_closure": {"historical_reuse_adapter_sha256": "c" * 64, "fixed": "unchanged"},
            "base_entry": {"path": "INVENTED-NOT-AN-EXECUTABLE"}, "image": "INVENTED-NOT-A-RUNTIME",
            "scope": {"people": 20, "folds": 80, "trials": 4884, "decisions": 163135, "new_fits": 0}}
        bounds = {"components": [{"name": "invented_original_allowance", "maximum_bytes": 15083943973}],
                  "sum_maximum_bytes": 15083943973, "selected_proposal_ceiling_bytes": 17179869184}
        old = {str(origin / "PLAN.json"): provision.canonical(plan), str(origin / "READ_BOUNDS.json"): provision.canonical(bounds)}
        adapters = {name: ("# Invented inert source: " + name + "\n").encode() for name in provision.REPLACEMENTS}
        for name in provision.REPLACEMENTS:
            old[str(origin / name)] = b"# Invented predecessor source.\n"
        for i in range(38): old[str(self.root / "external-invented" / ("member-%02d.py" % i))] = b"# Invented external source.\n"
        pins = [{"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()} for path, body in old.items()]
        lock = {"schema": "INVENTED-NOT-AN-ADMISSIBLE-LOCK", "files": pins, "member_count": 43,
                "member_bytes": sum(len(b) for b in old.values())}
        return (lock, old, origin), adapters, plan

    def test_source_composition_preserves_full_scope_identity_and_runtime(self):
        admitted, adapters, original = self.invented_admission()
        mapping = {"path": str(self.root / "private-map.json"), "bytes": 1, "sha256": "f" * 64}
        source = self.root / "new-source"
        output, caller, capacity = [str(self.root / n) for n in ("output", "caller", "capacity.json")]
        result = provision.compose(admitted, adapters, str(source), mapping, output, caller, capacity,
            "nb-hybrid-invented", str(self.root / "provided-cases"), str(self.root / "provided-reference"))
        plan = json.loads((source / "PLAN.json").read_bytes())
        self.assertEqual(plan["scope"], original["scope"])
        self.assertEqual(plan["image"], original["image"])
        for name in ("cases", "references"):
            self.assertEqual({k: v for k, v in plan[name].items() if k != "path"},
                             {k: v for k, v in original[name].items() if k != "path"})
        self.assertEqual(plan["docker_prefix"][:-1], original["docker_prefix"][:-1])
        self.assertEqual(plan["producer_delivery_source_closure"]["fixed"], "unchanged")
        lock = json.loads((source / "SOURCE_LOCK.json").read_bytes())
        self.assertEqual((lock["member_count"], len(lock["files"])), (43, 43))
        self.assertEqual(admitted[0]["schema"], "INVENTED-NOT-AN-ADMISSIBLE-LOCK")
        bounds = json.loads((source / "READ_BOUNDS.json").read_bytes())
        self.assertEqual(bounds["sum_maximum_bytes"], 15084075045)
        self.assertEqual(sum(c["maximum_bytes"] for c in bounds["components"]), bounds["sum_maximum_bytes"])
        self.assertFalse(result["selected_for_execution"])
        self.assertTrue(all(not Path(p).exists() for p in (output, caller, capacity, mapping["path"])))
        with self.assertRaises(ValueError):
            provision.compose(admitted, adapters, str(source), mapping, output, caller, capacity,
                "nb-hybrid-invented", str(self.root / "provided-cases"), str(self.root / "provided-reference"))

    def test_helper_bootstrap_rejects_same_size_changed_code(self):
        source = self.root / "bootstrap"
        source.mkdir()
        shutil.copyfile(HERE / "provision.py", source / "provision.py")
        marker = source / "SIDE_EFFECT"
        evil = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('ran')\n").encode()
        (source / "source_binding.py").write_bytes(evil.ljust(4147, b" "))
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(source / "provision.py"), "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertIn(b"bootstrap stable literal identity", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest-sha256", required=True)
    args, remaining = parser.parse_known_args()
    SOURCE_SHA = args.source_manifest_sha256
    provision = admit_component(SOURCE_SHA)
    unittest.main(argv=[sys.argv[0], *remaining])
