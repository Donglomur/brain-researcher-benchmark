"""New generated portable transport/receipt/forwarding controls; no dataset HTTP."""
import copy,hashlib,importlib.util,json,os,shutil,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("movie10_input",HERE/"acquire.py")
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
PREPARER=Path(os.environ.get("N039_TEST_PREPARER",str(HERE.parent/"movie10-evaluator-v1/prepare_panel.py")))

class PortableInputControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get("N039_TEST_TMPDIR"))
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
    def fixture_manifest(self):
        m=copy.deepcopy(api.load_manifest())
        for i,row in enumerate(m["files"]):
            body=("tiny"+str(i)).encode()
            row.update(bytes=len(body),md5=hashlib.md5(body).hexdigest(),
              url="https://example.invalid/"+row["subject"])
        m["total_bytes"]=20
        return m
    def fake_success(self,argv,out,log,cap,logcap,end):
        subject=argv[-1].rsplit("/",1)[-1]
        order=["sub-01","sub-02","sub-03","sub-05"]
        body=("tiny"+str(order.index(subject))).encode();Path(out).write_bytes(body)
        status=("N039_STATUS\nhttp_code=200\nexitcode=0\nnum_redirects=0\nsize_download=5\n"
          "url_effective="+argv[-1]+"\nssl_verify_result=0\nN039_END\n").encode()
        Path(log).write_bytes(status)
        return {"argv":argv,"stdout_written":5,"stdout_received":5,
          "stderr_written":len(status),"stderr_received":len(status),"closed":True,
          "write_accounting_exact":True,"exit_code":0}
    def captured_fixture(self):
        m=self.fixture_manifest();data=self.root/"data";evidence=self.root/"evidence"
        result=api._fetch(m,data,evidence,Path("/generated/curl"),self.fake_success,False)
        self.assertEqual(result["status"],"verified_original_inputs")
        receipt=evidence/"receipt.json";sha=api.digest(receipt.read_bytes())
        return m,data,receipt,sha

    def test_transport_body_limit_preserves_exact_prefix_and_closes(self):
        out=self.root/"out";log=self.root/"log"
        event=api.bounded_client([sys.executable,"-I","-B","-c","import os;os.write(1,b'abcdefgh')"],
          out,log,4,32,time.monotonic()+3)
        self.assertEqual(out.read_bytes(),b"abcd")
        self.assertIn("output limit",event["failure"]);self.assertTrue(event["closed"])
        self.assertEqual(event["stdout_written"],4)

    def test_transport_stderr_limit_preserves_prefix_and_closes(self):
        out=self.root/"out";log=self.root/"log"
        event=api.bounded_client([sys.executable,"-I","-B","-c","import os;os.write(2,b'abcdefgh')"],
          out,log,32,4,time.monotonic()+3)
        self.assertEqual(log.read_bytes(),b"abcd")
        self.assertIn("output limit",event["failure"]);self.assertTrue(event["closed"])

    def test_transport_deadline_closes_live_generated_child(self):
        event=api.bounded_client([sys.executable,"-I","-B","-c","import time;time.sleep(5)"],
          self.root/"out",self.root/"log",32,32,time.monotonic()+.15)
        self.assertIn("deadline",event["failure"]);self.assertTrue(event["closed"])
        self.assertTrue(api.group_absent(event["pid"]))

    def test_exited_leader_open_pipe_reports_uncertainty_without_unsafe_kill(self):
        class FakeSelector:
            def register(self,*args):pass
            def get_map(self):return {1:1}
            def select(self,*args):return []
            def close(self):pass
        streams=[]
        for _ in range(2):
            read_fd,write_fd=os.pipe();os.close(write_fd);streams.append(os.fdopen(read_fd,"rb"))
        proc=SimpleNamespace(pid=987654321,stdout=streams[0],stderr=streams[1],
          poll=lambda:0,wait=lambda **kw:0,returncode=0)
        ticks=iter([.1,.2,.3,.4,.5])
        with patch.object(api.subprocess,"Popen",return_value=proc), \
             patch.object(api.selectors,"DefaultSelector",return_value=FakeSelector()), \
             patch.object(api.time,"monotonic",side_effect=lambda:next(ticks)), \
             patch.object(api,"group_absent",return_value=False),patch.object(api.os,"killpg") as kill:
            event=api.bounded_client(["generated"],self.root/"out",self.root/"log",8,8,.25)
        kill.assert_not_called();self.assertTrue(event["cleanup_uncertain"])
        self.assertTrue(event["no_retry"]);self.assertFalse(event["closed"])

    def test_client_exception_retains_uncertain_attempt_and_full_charge(self):
        m=self.fixture_manifest();calls=[]
        def fail(*args):calls.append(args);raise OSError("generated client exception")
        r=api._fetch(m,self.root/"data",self.root/"evidence",Path("/generated/curl"),fail,False)
        self.assertEqual(len(calls),1);self.assertEqual(len(r["requests"]),1)
        self.assertFalse(r["raw_accounting_exact"]);self.assertTrue(r["cleanup_uncertain"])
        self.assertEqual(r["raw_cumulative_charge"],536870912)
        self.assertEqual(r["not_attempted"],["sub-02","sub-03","sub-05"])

    def test_changed_operator_client_is_rejected_before_object_request(self):
        m=self.fixture_manifest();curl=self.root/"curl";curl.write_bytes(b"client")
        pin=api.digest(curl.read_bytes());calls=[]
        def version(argv,out,log,cap,logcap,end):
            calls.append(argv);Path(out).write_bytes(b"curl 8.7.1 generated\n");Path(log).write_bytes(b"")
            curl.write_bytes(b"changed")
            return {"closed":True,"exit_code":0}
        r=api._fetch(m,self.root/"data",self.root/"evidence",curl,version,True,pin)
        self.assertEqual(len(calls),1);self.assertEqual(r["requests"],[])
        self.assertEqual(r["not_attempted"],["sub-01","sub-02","sub-03","sub-05"])
        self.assertIn("client identity changed",r["failure"])

    def test_fetch_transport_failure_emits_receipt_and_no_next_object(self):
        m=self.fixture_manifest();calls=[]
        def fail(argv,out,log,cap,logcap,end):
            calls.append(argv);Path(out).write_bytes(b"x");Path(log).write_bytes(b"failed")
            return {"stdout_written":1,"closed":True,"write_accounting_exact":True,
              "exit_code":28,"failure":"generated transport failure"}
        r=api._fetch(m,self.root/"data",self.root/"evidence",Path("/generated/curl"),fail,False)
        self.assertEqual(len(calls),1);self.assertEqual(r["raw_written_bytes"],1)
        self.assertEqual(r["not_attempted"],["sub-02","sub-03","sub-05"])
        self.assertFalse(r["all_four_custody_verified"])
        self.assertEqual((self.root/"data/sub-01_movie10.h5.partial").read_bytes(),b"x")
        self.assertTrue((self.root/"evidence/receipt.json").is_file())

    def test_fixed_manifest_tampering_is_rejected(self):
        changed=api.read(HERE/"original-sources.v1.json",16384)+b"\n"
        (self.root/"original-sources.v1.json").write_bytes(changed)
        with patch.object(api,"HERE",self.root):
            with self.assertRaisesRegex(ValueError,"manifest changed"):api.load_manifest()

    def test_fixed_manifest_matches_existing_preparer_metadata(self):
        manifest=api.load_manifest();bodies=api.converter_sources(manifest,PREPARER)
        module=api.types.ModuleType("evaluate");module.__file__=str(PREPARER.parent/"evaluate.py")
        exec(compile(bodies["evaluate.py"],module.__file__,"exec"),module.__dict__)
        namespace={"__name__":"metadata_only_import","__file__":str(PREPARER)}
        with patch.dict(sys.modules,{"evaluate":module}):
            exec(compile(bodies["prepare_panel.py"],str(PREPARER),"exec"),namespace)
        expected=namespace["source_records"]()
        self.assertEqual(set(expected),{row["subject"] for row in manifest["files"]})
        for row in manifest["files"]:
            self.assertEqual({k:row[k] for k in ("bytes","md5")},
              {k:expected[row["subject"]][k] for k in ("bytes","md5")})
            self.assertEqual(row["filename"],expected[row["subject"]]["file"])

    def test_receipt_path_and_hash_must_match_generated_capture(self):
        m,data,receipt,sha=self.captured_fixture()
        with self.assertRaisesRegex(ValueError,"receipt digest"):
            api.verified_receipt(m,data,receipt,"0"*64)
        r=json.loads(receipt.read_bytes());r["data_dir"]=str(self.root/"other")
        bad=self.root/"bad.json";bad.write_bytes(api.canonical(r))
        with self.assertRaisesRegex(ValueError,"receipt required"):
            api.verified_receipt(m,data,bad,api.digest(bad.read_bytes()))
        self.assertTrue(api.verified_receipt(m,data,receipt,sha)["all_four_custody_verified"])

    def test_prepare_command_forwards_exact_existing_converter_contract(self):
        m,data,receipt,sha=self.captured_fixture();panel=self.root/"panel.json"
        argv=api.preparation_command(m,data,receipt,sha,PREPARER,panel)
        self.assertEqual(argv[:5],[sys.executable,"-I","-B",str(HERE/"acquire.py"),"prepare"])
        self.assertEqual(argv[argv.index("--data-dir")+1],str(data))
        self.assertEqual(argv[argv.index("--receipt-sha256")+1],sha)
        self.assertEqual(argv[argv.index("--preparer")+1],str(PREPARER.absolute()))
        self.assertEqual(argv[argv.index("--panel")+1],str(panel))
        self.assertFalse(panel.exists())
        with self.assertRaisesRegex(ValueError,"outside"):
            api.preparation_command(m,data,receipt,sha,PREPARER,data/"panel.json")

    def test_preparer_change_between_emission_and_execution_is_rejected(self):
        m,data,receipt,sha=self.captured_fixture()
        folder=self.root/"converter";folder.mkdir()
        for name in ("prepare_panel.py","evaluate.py"):shutil.copyfile(PREPARER.parent/name,folder/name)
        preparer=folder/"prepare_panel.py";panel=self.root/"panel.json"
        argv=api.preparation_command(m,data,receipt,sha,preparer,panel)
        with preparer.open("ab") as f:f.write(b"\n")
        args=SimpleNamespace(runner_sha256=argv[6],data_dir=data,receipt=receipt,
          receipt_sha256=sha,preparer=preparer,panel=panel)
        with self.assertRaisesRegex(ValueError,"Bounded ordinary|source changed"):
            api.execute_preparer(m,args,lambda *_:self.fail("converter must not execute"))

    def test_explicit_prepare_revalidates_and_forwards_unchanged_bytes(self):
        m,data,receipt,sha=self.captured_fixture();panel=self.root/"panel.json"
        argv=api.preparation_command(m,data,receipt,sha,PREPARER,panel)
        args=SimpleNamespace(runner_sha256=argv[6],data_dir=data,receipt=receipt,
          receipt_sha256=sha,preparer=PREPARER,panel=panel)
        calls=[]
        def observe(code,namespace):calls.append((code.co_filename,namespace.get("__name__")))
        with patch.object(sys,"argv",list(sys.argv)),patch.object(sys,"path",list(sys.path)),patch.dict(sys.modules):
            api.execute_preparer(m,args,observe)
            self.assertEqual(sys.argv,[str(PREPARER.absolute()),"--output",str(panel),"prepare","--source-root",str(data)])
            self.assertEqual(sys.path[0],str(PREPARER.absolute().parent))
        self.assertEqual(calls,[(str(PREPARER.absolute().parent/"evaluate.py"),"evaluate"),
          (str(PREPARER.absolute()),"__main__")])
        self.assertFalse(panel.exists())

if __name__=="__main__":unittest.main(verbosity=2)
