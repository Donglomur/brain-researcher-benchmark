"""Invented provisioning controls; accepted source bytes only, no asset bodies."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location("portable_provision", HERE / "provision.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Provisioning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = p.catalog()
        cls.old = Path(os.environ.get("TMS_SOURCE_ROOT", str(HERE.parent)))
        cls.bodies, cls.charged = p.capture_owner(cls.old, cls.cat)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.assets = self.tmp / "locators"
        self.assets.mkdir()
        cfg = self.cat["config_template"]
        def loc(name, value):
            return {"path": str(self.assets / name),
                    "bytes": value["bytes"], "sha256": value["sha256"]}
        evidence = {n: loc(n+".json", cfg[n]) for n in p.READ_FIELDS}
        evidence.update({n: loc(n+".json", v) for n,v in cfg["image_evidence"].items()})
        evidence["source_independent_review"] = loc("fresh-source.json", p.pin(b"pending"))
        self.request = {"schema": "tms_portable_provision_request_v1", "attempt_id": "invented-001",
            "package_root": str(self.tmp/"package"), "operation_root": str(self.tmp/"operation"),
            "assets": {"input_files": {n: loc(n,v) for n,v in cfg["input_files"].items()},
                       "paper": loc("paper.pdf",cfg["paper"]),
                       "reference": loc("protected.json",cfg["reference_selection"]),
                       "official_code": {x["relative"]:loc(x["relative"],x["file"]) for x in cfg["official_code"]}},
            "evidence": evidence,
            "programs": {a:loc(a+".py", p.pin(b"print('{}')\n")) for a in ("A","B")},
            "runtime": {"python": str(self.tmp/"runtime"/"python3.11"),
                        "daemon_socket": str(self.tmp/"runtime"/"docker.sock"),
                        "daemon_guard": {"dev":1,"inode":2,"mode":stat.S_IFSOCK|0o600,"uid":501,"gid":20,"nlink":1},
                        "admission":loc("fresh-runtime.json",p.pin(b"pending"))},
            "owner_use": {"authority_reference":"invented-owner-control",
                          "authorized_local_use":True,"redistribution_granted":False}}

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp):
            os.chmod(root,0o700)
            for f in files:
                path=Path(root)/f
                if not path.is_symlink(): os.chmod(path,0o600)
        shutil.rmtree(self.tmp)

    def admitted_fixture(self):
        plan = p.plan(p.encode(self.request), self.old)
        sr=plan["source_review_template"];sr["whole_source_accepted"]=True
        rt=plan["runtime_admission_template"];rt["selected_runtime_accepted"]=True
        for key,obj in (("source_independent_review",sr),("admission",rt)):
            entry=(self.request["evidence"] if key=="source_independent_review" else self.request["runtime"])[key]
            raw=p.encode(obj);Path(entry["path"]).write_bytes(raw);entry.update(p.pin(raw))
        return p.build(p.encode(self.request),self.old)

    def grant(self):
        root=Path(self.request["package_root"])
        reqraw=(root/"PROVISION_REQUEST.private.json").read_bytes()
        lock=(root/"EXECUTION_LOCK.json").read_bytes()
        wrapper=p.decode((root/"UNSELECTED_RUN.private.json").read_bytes())
        wrapper["selection"]["root_execution_selected"]=True
        return {"schema":"tms_portable_owner_grant_v1",
                "owner_authority_reference":self.request["owner_use"]["authority_reference"],
                "request":p.pin(reqraw),"generated_lock":p.pin(lock),"selected_manifest":p.pin(p.encode(wrapper)),
                "attempt_id":self.request["attempt_id"],"source_review":self.request["evidence"]["source_independent_review"],
                "runtime_admission":self.request["runtime"]["admission"],
                "daemon_socket":self.request["runtime"]["daemon_socket"],
                "daemon_guard":self.request["runtime"]["daemon_guard"],"python":self.request["runtime"]["python"],
                "complete_scope":{"regions":12,"effects":36,"omissions":540},"owner_selected_execution":True}

    def test_full_graph_exact_four_changes_and_source_syntax(self):
        rendered, lock, wrapper, changed=p.render(self.request,self.cat,self.bodies)
        self.assertEqual(set(changed),{"CONFIG.json","owner/run_once.py","owner/outer_once.py","owner/docker_owner.py"})
        self.assertEqual(len(rendered),16)
        self.assertEqual(p.decode(lock)["members"],{n:p.pin(b) for n,b in rendered.items()})
        for n,b in rendered.items():
            if n.endswith(".py"):ast.parse(b)
        for n in ("METHOD.json","TASK.md","SUBMISSION_SCHEMA.json","owner/delivery.py","owner/scorer.py","capacity.py"):
            self.assertEqual(rendered[n],self.bodies[n])
        self.assertFalse(p.decode(wrapper)["selection"]["root_execution_selected"])
        self.assertIn(repr(self.request["runtime"]["python"]).encode(),rendered["owner/outer_once.py"])
        self.assertNotIn(b"/Users/",rendered["CONFIG.json"])

    def test_plan_grant_template_is_unselected_and_complete(self):
        planned=p.plan(p.encode(self.request),self.old)
        self.assertFalse(planned["owner_grant_template"]["owner_selected_execution"])
        self.assertFalse((self.tmp/"package").exists())
        self.admitted_fixture()
        # After the two reviewed evidence descriptors are filled, the final plan
        # must be obtained before build; reconstruct its pure rendering here.
        raw=p.encode(self.request)
        with patch.object(Path,"exists",return_value=False):
            final=p.plan(raw,self.old)
        grant=final["owner_grant_template"]
        grant["owner_selected_execution"]=True
        self.assertEqual(grant,self.grant())

    def test_actual_manifest_and_delivery_abi(self):
        rendered,lock,raw,_=p.render(self.request,self.cat,self.bodies)
        wrapper=p.decode(raw);wrapper["selection"]["root_execution_selected"]=True;raw=p.encode(wrapper)
        names=("common","durable_evidence","docker_owner","delivery","route_config")
        saved={n:sys.modules.get(n) for n in names}
        try:
            modules={}
            for n in names:
                name=("owner/" if n!="route_config" else "")+n+".py"
                m=types.ModuleType(n);m.__file__=str(self.tmp/name);sys.modules[n]=m
                exec(compile(rendered[name],m.__file__,"exec"),m.__dict__);modules[n]=m
            admitted=modules["route_config"].admit_manifest(raw,p.pin(raw)["sha256"],"invented-001")
            docs={n:rendered[n] for n in modules["delivery"].DOCS}
            modules["delivery"].validate_selection(admitted["selection"]["delivery_selection"],docs)
            self.assertEqual(modules["docker_owner"].DAEMON_GUARD,self.request["runtime"]["daemon_guard"])
            self.assertEqual(len(admitted["selection"]["delivery_selection"]["official_code"]),12)
        finally:
            for n,m in saved.items():
                if m is None:sys.modules.pop(n,None)
                else:sys.modules[n]=m

    def test_plan_and_build_never_open_assets_or_execute(self):
        real=p.read_source; seen=[]
        def checked(path,*a,**kw):
            text=str(path);seen.append(text)
            self.assertFalse(text.startswith(str(self.assets)))
            return real(path,*a,**kw)
        with patch.object(p,"read_source",side_effect=checked):
            result=p.build(p.encode(self.request),self.old)
        self.assertFalse(result["execution_selected"]);self.assertEqual(result["asset_body_reads"],0)
        self.assertFalse(any(self.assets.iterdir()))
        self.assertFalse(any((self.tmp/"operation"/"selections").iterdir()))
        self.assertFalse(any((self.tmp/"operation"/"attempts").iterdir()))

    def test_exact_owner_grant_then_no_retry(self):
        self.admitted_fixture();result=p.select(self.tmp/"package",p.encode(self.grant()))
        self.assertFalse(result["launch_performed"])
        chosen=p.decode(Path(result["selection"]["path"]).read_bytes())
        self.assertTrue(chosen["selection"]["root_execution_selected"])
        self.assertEqual(stat.S_IMODE(Path(result["selection"]["path"]).stat().st_mode),0o400)
        with self.assertRaisesRegex(ValueError,"one selected manifest"):
            p.select(self.tmp/"package",p.encode(self.grant()))

    def test_changed_program_refused_by_grant(self):
        self.admitted_fixture();g=self.grant();g["selected_manifest"]["sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"exact owner grant"):p.select(self.tmp/"package",p.encode(g))

    def test_boolean_grant_not_integer(self):
        self.admitted_fixture();g=self.grant();g["owner_selected_execution"]=1
        with self.assertRaisesRegex(ValueError,"exact owner grant"):p.select(self.tmp/"package",p.encode(g))

    def test_missing_projection_member(self):
        del self.request["assets"]["input_files"]["pair_counts.u8"]
        with self.assertRaisesRegex(ValueError,"four projection"):p.render(self.request,self.cat,self.bodies)

    def test_subset_official_code_refused(self):
        self.request["assets"]["official_code"].pop(next(iter(self.request["assets"]["official_code"])))
        with self.assertRaisesRegex(ValueError,"twelve"):p.render(self.request,self.cat,self.bodies)

    def test_replaced_reference_and_tensor_refused(self):
        for entry in (self.request["assets"]["reference"],self.request["assets"]["input_files"]["values.f64"]):
            previous=entry["sha256"];entry["sha256"]="0"*64
            with self.assertRaisesRegex(ValueError,"asset identity"):p.render(self.request,self.cat,self.bodies)
            entry["sha256"]=previous

    def test_protected_locator_alias_refused(self):
        self.request["programs"]["A"]["path"]=self.request["assets"]["reference"]["path"]
        with self.assertRaisesRegex(ValueError,"distinct asset"):p.render(self.request,self.cat,self.bodies)

    def test_output_inside_asset_tree_refused(self):
        self.request["package_root"]=str(self.assets/"paper.pdf")
        with self.assertRaisesRegex(ValueError,"outside generated"):p.render(self.request,self.cat,self.bodies)

    def test_inherited_source_mutation_refused(self):
        bodies=dict(self.bodies);bodies["owner/scorer.py"]+=b"\n"
        with self.assertRaisesRegex(ValueError,"captured predecessor"):p.render(self.request,self.cat,bodies)

    def test_symlink_source_refused(self):
        path=self.tmp/"alias";path.symlink_to(self.old/"TASK.md")
        with self.assertRaisesRegex(ValueError,"symlink"):p.read_source(path)

    def test_duplicate_and_overflow_json_refused(self):
        for raw in (b'{"a":1,"a":2}',b'{"x":1e999}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):p.decode(raw)

    def test_forged_socket_kind_and_bool_refused(self):
        for value in (True,stat.S_IFREG|0o600):
            self.request["runtime"]["daemon_guard"]["mode"]=value
            with self.assertRaises(ValueError):p.render(self.request,self.cat,self.bodies)

    def test_undeclared_rights_and_runtime_refused(self):
        self.request["owner_use"]["authorized_local_use"]=False
        with self.assertRaisesRegex(ValueError,"local-use"):p.render(self.request,self.cat,self.bodies)

    def test_generated_source_mutation_refused_before_selection(self):
        self.admitted_fixture();f=self.tmp/"package"/"owner"/"scorer.py"
        os.chmod(f,0o600);f.write_bytes(f.read_bytes()+b"\n")
        with self.assertRaises(ValueError):p.select(self.tmp/"package",p.encode(self.grant()))

    def test_wrong_runtime_admission_refused(self):
        plan=p.plan(p.encode(self.request),self.old)
        rt=plan["runtime_admission_template"];rt["selected_runtime_accepted"]=True;rt["daemon_guard"]["inode"]=999
        sr=plan["source_review_template"];sr["whole_source_accepted"]=True
        for entry,obj in ((self.request["runtime"]["admission"],rt),(self.request["evidence"]["source_independent_review"],sr)):
            raw=p.encode(obj);Path(entry["path"]).write_bytes(raw);entry.update(p.pin(raw))
        p.build(p.encode(self.request),self.old)
        with self.assertRaisesRegex(ValueError,"runtime admission"):p.select(self.tmp/"package",p.encode(self.grant()))


if __name__=="__main__":unittest.main()
