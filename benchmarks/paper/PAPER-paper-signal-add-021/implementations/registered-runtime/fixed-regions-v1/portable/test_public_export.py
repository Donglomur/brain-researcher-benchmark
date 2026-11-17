"""Public-tree composition controls. No private checkout or research payload."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import shutil
import unittest

HERE=Path(__file__).absolute().parent
ROOT=HERE.parent
spec=importlib.util.spec_from_file_location("public_provision",HERE/"provision.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
spec=importlib.util.spec_from_file_location("public_fixtures",HERE/"test_provision.py")
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)


class PublicExport(unittest.TestCase):
    def test_complete_relocated_sixteen_member_graph(self):
        cat=p.catalog();bodies,reads=p.capture_owner(ROOT,cat)
        self.assertEqual(len(bodies),16)
        self.assertLess(reads,2*1024*1024)
        self.assertEqual({n:p.pin(b) for n,b in bodies.items()},cat["source_members"])
        expected={"TASK.md":"TASK.md","METHOD.json":"METHOD.json",
                  "SUBMISSION_SCHEMA.json":"SUBMISSION_SCHEMA.json","owner/scorer.py":"scorer.py"}
        self.assertEqual({k:cat["source_locations"][k] for k in expected},expected)
        self.assertEqual(len(set(cat["source_locations"].values())),16)

    def test_default_cli_needs_no_private_source_checkout(self):
        fixture=fixtures.Provisioning("test_full_graph_exact_four_changes_and_source_syntax")
        fixture.setUpClass();fixture.setUp()
        try:
            request=fixture.tmp/"request.json";request.write_bytes(p.encode(fixture.request))
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                p.main(["plan","--request",str(request)])
            value=json.loads(output.getvalue())
            self.assertEqual(value["schema"],"tms_portable_plan_v1")
            self.assertFalse(value["execution_selected"])
            self.assertFalse(value["owner_grant_template"]["owner_selected_execution"])
            self.assertEqual(value["asset_body_reads"],0)
        finally:fixture.tearDown()

    def test_escape_map_refused_before_outside_read(self):
        cat=p.catalog();first=next(iter(cat["source_locations"]))
        cat["source_locations"][first]="../outside.py"
        with self.assertRaisesRegex(ValueError,"in-tree source"):
            p.capture_owner(ROOT,cat)

    def test_missing_shared_method_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            copyroot=Path(temp).resolve()/"task"
            shutil.copytree(ROOT,copyroot)
            (copyroot/"METHOD.json").unlink()
            with self.assertRaises(FileNotFoundError):
                p.capture_owner(copyroot,p.catalog())

    def test_unbound_request_and_template_host_identity(self):
        request=json.loads((HERE/"REQUEST.template.json").read_bytes())
        self.assertIs(request["owner_use"]["authorized_local_use"],False)
        self.assertTrue(all(v is None for v in request["runtime"]["daemon_guard"].values()))
        config=json.loads((HERE/"owner-template"/"CONFIG.json").read_bytes())
        self.assertIsNone(config["daemon_guard"]);self.assertEqual(config["daemon_socket"],"")
        tree=ast.parse((HERE/"owner-template"/"owner"/"docker_owner.py").read_bytes())
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and
                  any(isinstance(t,ast.Name) and t.id=="DAEMON_GUARD" for t in n.targets))
        self.assertIsNone(ast.literal_eval(node.value))
        with self.assertRaisesRegex(ValueError,"local-use"):
            p.bind_config(request,p.catalog())

    def test_scientific_contract_and_count_unchanged(self):
        pins={"TASK.md":"dc4c933535debdf6e26cbc527665fedf5ecf0dcbed7ad29a843fff2673102d98",
              "METHOD.json":"d0868b617aa4e936319767603c2d34b10275133c21b80250d48fe5302bb709aa",
              "SUBMISSION_SCHEMA.json":"1167b43d7b352254b5e04d6f230c9a76b03b5829e461835cbee92edec04f0aac",
              "scorer.py":"0211d01f059378f09c665df7c7b825c4bd1812e33671b420c49da9ce6504fd3e"}
        for name,sha in pins.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha)
        profile=json.loads((ROOT/"PROFILE.json").read_bytes())
        self.assertEqual((profile["regions"],profile["effects"],profile["leave_one_out_summaries"]),(12,36,540))
        self.assertEqual(profile["additional_registered_tasks"],0)
        self.assertFalse(profile["public_submission_ready"])
        self.assertFalse(profile["new_portable_actual_execution"])
        self.assertFalse(profile["legacy_behavioral_248_profile_replaced"])

    def test_full_public_lock_and_no_body_or_host_path_leak(self):
        lock=json.loads((ROOT/"SOURCE_LOCK.json").read_bytes())
        files={x["path"]:x for x in lock["files"]}
        actual={x.relative_to(ROOT).as_posix() for x in ROOT.rglob("*") if x.is_file()}
        self.assertEqual(actual,set(files)|{"SOURCE_LOCK.json"})
        import re
        private_path=re.compile("/"+"Users"+"/[^/\\s\"']+/")
        self.assertIsNotNone(private_path.search("/"+"Users"+"/"+"synthetic-owner"+"/x"))
        total=0
        for name,entry in files.items():
            raw=(ROOT/name).read_bytes();self.assertEqual(p.pin(raw),{k:entry[k] for k in ("bytes","sha256")})
            total+=len(raw);text=raw.decode()
            self.assertIsNone(private_path.search(text),name)
            self.assertNotIn(0,raw)
            self.assertNotIn(Path(name).suffix.lower(),(".pdf",".f64",".u8",".mat",".npz",".bin"))
            self.assertNotIn(".private.",name)
        self.assertEqual(total,lock["total_bytes"])

    def test_relocated_dependency_symlink_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()/"task";shutil.copytree(ROOT,root)
            entry=root/"scorer.py";body=entry.read_bytes();entry.unlink()
            target=Path(temp).resolve()/"external.py";target.write_bytes(body)
            entry.symlink_to(target)
            with self.assertRaisesRegex(ValueError,"symlink"):
                p.capture_owner(root,p.catalog())


if __name__=="__main__":unittest.main()
