"""Generated relocation/admission controls; no data, candidate, runtime or scorer run."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    raw = (root / "SOURCE_MANIFEST.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.manifest_sha256:
        raise ValueError("reviewed manifest required before helper execution")
    manifest = json.loads(raw)
    body = (root / "portable.py").read_bytes()
    if {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()} != manifest["files"]["portable.py"]:
        raise ValueError("helper identity before execution")
    module = types.ModuleType("purkinje_portable_tested")
    module.__file__ = str(root / "portable.py")
    exec(compile(body, module.__file__, "exec"), module.__dict__)

    class Controls(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory(prefix="purkinje-relocation-invented-")
            self.base = Path(self.temp.name).resolve()
            self.copy = self.base / "different root with spaces"
            shutil.copytree(root, self.copy)
            self.old_popen = subprocess.Popen
            subprocess.Popen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("native dispatch forbidden"))
        def tearDown(self):
            subprocess.Popen = self.old_popen
            self.temp.cleanup()
        def load(self):
            return module.load_executor(self.copy, args.manifest_sha256)
        def test_complete_dependency_relocation_and_module_isolation(self):
            before = {n:sys.modules.get(n) for n in ("common","schema","numeric_score","paired_packet")}
            old = Path.cwd()
            try:
                os.chdir(self.base)
                executor = self.load()
            finally:
                os.chdir(old)
            self.assertEqual(before, {n:sys.modules.get(n) for n in before})
            self.assertEqual([len(executor.paired.inventory(c)) for c in ("A","B")], [16,18])
            self.assertEqual(executor.modules["numeric_score"].__file__,
                             str(self.copy / module.PRODUCER / "numeric_score.py"))
            self.assertEqual(executor.paired.contract["scope"]["trees"],10)
            self.assertEqual(executor.paired.contract["scope"]["components"],13)
            self.assertEqual(executor.paired.contract["scope"]["table_numerical_fields"],31)
            self.assertEqual(executor.paired.contract["scope"]["summary_errors"],58)
            self.assertFalse(executor.used)
        def test_changed_adapter_rejected_without_execution(self):
            marker = self.base / "never-created"
            p = self.copy / module.ADAPTER
            p.write_text("from pathlib import Path\nPath("+repr(str(marker))+").write_text('bad')\n")
            with self.assertRaises(ValueError): self.load()
            self.assertFalse(marker.exists())
        def test_stale_scorer_or_reference_descriptor_rejected(self):
            for name in ("numeric_score.py","REFERENCE_PINS.json"):
                p = self.copy / module.PRODUCER / name
                original = p.read_bytes()
                p.write_bytes(original[:-1]+b" ")
                with self.assertRaises(ValueError): self.load()
                p.write_bytes(original)
        def test_unknown_member_and_symlink_root_refused(self):
            p=self.copy/"unexpected.py";p.write_text("raise RuntimeError('not imported')\n")
            with self.assertRaises(ValueError):self.load()
            p.unlink()
            alias=self.base/"alias";alias.symlink_to(self.copy,target_is_directory=True)
            with self.assertRaises(ValueError):module.load_executor(alias,args.manifest_sha256)
        def test_fifo_and_hardlink_refused_before_open(self):
            p=self.copy/module.ADAPTER;original=p.read_bytes();p.unlink();os.mkfifo(p)
            with self.assertRaises(ValueError):self.load()
            p.unlink();p.write_bytes(original)
            extra=self.base/"hardlink";os.link(p,extra)
            with self.assertRaises(ValueError):self.load()
        def test_disabled_templates_and_invalid_closed_pair_never_read_targets(self):
            executor=self.load()
            requests={c:json.loads((self.copy/module.PAIRED/("RUN_REQUEST_"+c+".template.json")).read_bytes())
                      for c in ("A","B")}
            pins={c:executor.paired_module.pin(executor.paired_module.encode(requests[c])) for c in ("A","B")}
            with self.assertRaises(ValueError):
                executor.execute_pair(requests=requests,request_pins=pins,programs={},packet_roots={},
                    packet_receipts={},runtime={},owner_authorization={},owner_authorization_pin={},
                    root=self.base/"unused",budget=None,active_deadline=0)
            self.assertFalse((self.base/"unused").exists())
            reads=[]
            with self.assertRaises(ValueError):
                executor.grade_closed_pair(None,authority={},authority_pin={},
                    reference_reader=lambda:reads.append("forbidden"),budget=None)
            self.assertEqual(reads,[])
        def test_operator_map_covers_complete_external_operands(self):
            value=json.loads((self.copy/"OPERATOR_PATHS.template.json").read_bytes())
            executor=self.load()
            provider={n:{k:r[k] for k in ("bytes","sha256")} for n,r in executor.paired.inventory("B").items()
                      if r["source"].startswith("provider/")}
            refs={n:{k:r[k] for k in ("bytes","sha256")} for n,r in executor.paired.references["references"].items()}
            self.assertEqual(value["provider_files"],provider)
            self.assertEqual(value["private_reference_files"],refs)
            self.assertEqual((len(provider),len(refs)),(15,5))
            self.assertFalse(value["execution_selected"])
            self.assertTrue(value["template_only"])

    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    print(json.dumps({"relocation_controls":result.testsRun,"authentic_data_reads":0,
                      "candidate_executions":0,"native_runs":0,"scorer_runs":0,"count_delta":0},sort_keys=True))
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    raise SystemExit(main())

