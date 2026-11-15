"""Standalone stdlib tests. All scientific values and runtime observations are invented."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import shutil
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import common
import configuration as cfg
import docker_owner as docker
import runner
from numeric import envelope,scalar
from fixtures import fixture,abstention
spec=importlib.util.spec_from_file_location("bridge_for_controls",ROOT/"task/bridge.py")
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class ScoringControls(unittest.TestCase):
    def setUp(self):
        self.public,self.reference,self.submitted=fixture();self.calls=0
    def grade(self,value):
        def load():
            self.calls+=1
            return self.reference
        return envelope.grade(common.encode(value),self.public,load,scalar)
    def test_complete_report_and_independent_signed_endpoint(self):
        result=self.grade(self.submitted)
        self.assertEqual(result["status"],"scored");self.assertEqual(self.calls,1)
        self.assertEqual(result["membership"]["misassigned_rows"],0)
        self.assertEqual(result["scalar_score"]["primary_interval_correct_trial_slope_error"]["absolute_error"],0)
        self.submitted["model_artifact"]["models"][2]["fit"]["coefficients"]["trial"]+=0.5
        result=self.grade(self.submitted)
        error=result["scalar_score"]["primary_interval_correct_trial_slope_error"]
        # Independently retain binary64 rounding in each derived slope.
        expected=(0.8+0.4)-(0.3+0.4)
        self.assertEqual(error["signed_candidate_minus_reference"],expected)
        self.assertEqual(error["absolute_error"],abs(expected))
        self.assertIsNone(result["scientific_success"])
    def test_covariance_axis_permutation_keeps_named_values(self):
        fit=self.submitted["model_artifact"]["models"][0]["fit"]
        order=[3,1,0,2];old=copy.deepcopy(fit["covariance"])
        fit["covariance"]={"axes":[old["axes"][i] for i in order],
                           "values":[[old["values"][i][j] for j in order] for i in order]}
        result=self.grade(self.submitted)
        self.assertTrue(all(x["absolute_error"]==0 for x in
            result["scalar_score"]["phases"][0]["numerical_errors"]["covariance"]["entries"].values()))
    def test_missing_and_duplicate_rows_reject_before_private_read(self):
        for mode in ("missing","duplicate"):
            s=copy.deepcopy(self.submitted)
            ids=s["preprocessing"]["phase_source_row_ids"]["stimulus"]
            ids.pop() if mode=="missing" else ids.append(ids[0])
            self.assertEqual(self.grade(s)["status"],"invalid_submission")
        self.assertEqual(self.calls,0)
    def test_complete_wrong_membership_remains_visible(self):
        p=self.submitted["preprocessing"]["phase_source_row_ids"]
        p["stimulus"][0],p["feedback"][0]=p["feedback"][0],p["stimulus"][0]
        result=self.grade(self.submitted)
        self.assertEqual(result["status"],"scored")
        self.assertEqual(result["membership"]["misassigned_rows"],2)
        self.assertEqual(result["membership"]["expected_raw_rows"],7)
    def test_partial_keeps_fixed_denominators(self):
        self.submitted["submission_status"]="partial"
        model=self.submitted["model_artifact"];model["submission_status"]="partial"
        model["models"][0].update(status="abstained",reason="Invented",fit=None)
        result=self.grade(self.submitted)
        self.assertEqual(result["expected_scalar_denominators"],
                         {"coefficients":12,"covariance_entries":48,"variance_components":9})
        self.assertFalse(result["scalar_score"]["complete_numerical_coverage"])
    def test_abstention_never_reads_reference(self):
        result=self.grade(abstention(self.submitted))
        self.assertEqual(result["status"],"abstained");self.assertEqual(self.calls,0)
    def test_stale_identity_and_numeric_underflow_refuse_without_reference(self):
        self.submitted["input_raw_sha256"]="d"*64
        self.assertEqual(self.grade(self.submitted)["status"],"invalid_submission")
        self.assertEqual(self.calls,0)
        for body in (b'{"a":1,"a":2}',b'{"a":1e-99999}',b'{"a":NaN}'):
            with self.assertRaises(envelope.AdmissionError):envelope.decode(body)

class FileAndAdmissionControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="human-ripple-invented-")
        self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def test_bridge_exact_bytes_and_no_extra_payload(self):
        out=self.root/"out";out.mkdir();p=out/"submission.json";p.write_bytes(b'{"invented":1}\n')
        self.assertEqual(bridge.capture_output(out),p.read_bytes())
        (out/"unclaimed").write_bytes(b"x")
        with self.assertRaisesRegex(ValueError,"exactly one"):bridge.capture_output(out)
    def test_bridge_symlink_hardlink_and_oversize_refuse(self):
        out=self.root/"out";out.mkdir();source=self.root/"source";source.write_bytes(b"{}")
        p=out/"submission.json";p.symlink_to(source)
        with self.assertRaises(OSError):bridge.capture_output(out)
        p.unlink();os.link(source,p)
        with self.assertRaisesRegex(ValueError,"single-link"):bridge.capture_output(out)
        p.unlink();p.write_bytes(b"x"*(262144+1))
        with self.assertRaisesRegex(ValueError,"bounded"):bridge.capture_output(out)
    def test_forged_closure_cannot_open_private_reference(self):
        budget=common.Budget(time.monotonic()+5,1048576,1048576)
        pub,_,_=fixture()
        with self.assertRaisesRegex(common.Refusal,"owned_closed_failed"):
            runner.grade_closed({"submission":{}},pub,{},self.root,budget)
    def test_source_manifest_detects_added_file_in_relocated_tree(self):
        # Real source set verification on this standalone export; no repo imports.
        body=(ROOT/"SOURCE_MANIFEST.json").read_bytes()
        runner.source_admission(common.pin(body)["sha256"],
                                common.Budget(time.monotonic()+10,8*1024**2,1024))
        clone=self.root/"relocated"
        shutil.copytree(ROOT,clone)
        with patch.object(runner,"ROOT",clone):
            runner.source_admission(common.pin(body)["sha256"],
                                    common.Budget(time.monotonic()+10,8*1024**2,1024))
            (clone/"unlisted.py").write_text("raise RuntimeError('not admitted')")
            with self.assertRaisesRegex(common.Refusal,"exact source set"):
                runner.source_admission(common.pin(body)["sha256"],
                                        common.Budget(time.monotonic()+10,8*1024**2,1024))
    def test_whole_operator_selection_and_preparation_binding(self):
        files={n:{"bytes":10,"sha256":"a"*64} for n in cfg.PUBLIC_NAMES}
        descriptor=lambda name:{"path":str(self.root/name),"bytes":10,"sha256":"a"*64}
        request={"schema":"human-ripple-program-request/v1","task_id":cfg.TASK_ID,
            "selected":True,"output_root":str(self.root/"fresh"),"program":descriptor("program.py"),
            "input_root":str(self.root/"input"),"preparation":descriptor("prep.json"),
            "runtime":descriptor("runtime.json"),"capacity":descriptor("capacity.json"),
            "source_manifest_sha256":"b"*64,"prior_known_seconds":1290,"operator_ceiling_seconds":1365}
        prep={"schema":"human-ripple-prepared-inputs/v1","task_id":cfg.TASK_ID,
            "condition":"original_long_table_and_protocol","public_files":files,
            "private_bundle":descriptor("reference.json"),"accepted_review_sha256":"c"*64}
        runtime={"schema":"human-ripple-runtime-admission/v1","image":cfg.IMAGE,
            "docker":str(self.root/"docker"),"docker_physical":[0]*7,
            "daemon_socket":str(self.root/"socket"),"daemon_guard":dict.fromkeys(
                ("dev","inode","mode","uid","gid","nlink"),0),"qualification_review_sha256":"d"*64}
        cap={"observed_epoch":time.time(),"observed_monotonic":time.monotonic(),
            "available_bytes":8*1024**3,"other_reserved_bytes":0,"memory_pressure":1,
            "pageout_growth":0,"swapout_growth":0,"swap_used_growth":0,"logical_cpus":8,
            "observed_cpu_cores":0.0,"other_selected_cpu_cores":0.0,"roster_confirmed":True}
        contract={"public_files":copy.deepcopy(files)}
        cfg.admit(request,prep,runtime,cap,contract)
        for key,value in (("selected",False),("prior_known_seconds",True),
                          ("operator_ceiling_seconds",1290)):
            with self.assertRaises(common.Refusal):
                cfg.admit({**request,key:value},prep,runtime,cap,contract)
        wrong=copy.deepcopy(prep);wrong["public_files"]["TASK.md"]["bytes"]=10.0
        with self.assertRaisesRegex(common.Refusal,"pin_extent"):
            cfg.admit(request,wrong,runtime,cap,contract)
        wrong=copy.deepcopy(prep);wrong["public_files"]["TASK.md"]["sha256"]="f"*64
        with self.assertRaisesRegex(common.Refusal,"five-file"):
            cfg.admit(request,wrong,runtime,cap,contract)
    def test_source_second_read_and_directory_limit(self):
        original=b"invented initial source";changed=b"invented altered source"
        source=self.root/"bridge.py";source.write_bytes(original)
        manifest={"files":{"bridge.py":common.pin(original)}}
        with patch.object(runner,"ROOT",self.root):
            b=common.Budget(time.monotonic()+10,1048576,1024)
            self.assertEqual(runner.source_member("bridge.py",manifest,b,32768),original)
            source.write_bytes(changed)
            with self.assertRaises(common.Refusal):
                runner.source_member("bridge.py",manifest,b,32768)
            for i in range(257):(self.root/str(i)).mkdir()
            with self.assertRaisesRegex(common.Refusal,"including directories"):
                runner.tree_names(self.root,b)
    def test_capacity_freshness_pressure_and_typed_reserve(self):
        c={"observed_epoch":100.0,"observed_monotonic":50.0,"available_bytes":8*1024**3,
            "other_reserved_bytes":0,"memory_pressure":1,"pageout_growth":0,
            "swapout_growth":0,"swap_used_growth":0,"logical_cpus":8,
            "observed_cpu_cores":1.0,"other_selected_cpu_cores":0.0,"roster_confirmed":True}
        self.assertIs(cfg.capacity(c,wall=101,monotonic=51),c)
        for key,value in (("other_reserved_bytes",0.0),("memory_pressure",2),
                          ("pageout_growth",1),("swap_used_growth",1),
                          ("available_bytes",1),("roster_confirmed",False)):
            q={**c,key:value}
            with self.assertRaises(common.Refusal):cfg.capacity(q,wall=101,monotonic=51)
        with self.assertRaisesRegex(common.Refusal,"fresh"):
            cfg.capacity(c,wall=161,monotonic=111)
    def test_private_and_public_path_overlap_refused(self):
        with self.assertRaisesRegex(common.Refusal,"nonnested"):
            cfg.independent_paths(str(self.root/"inputs"),str(self.root/"inputs/reference.json"))

def inspection(name,cid,mounts,final):
    return [{"Id":cid,"Image":docker.IMAGE,"Name":"/"+name,"RestartCount":0,
        "Config":{"Labels":{docker.LABEL:name},"Entrypoint":["python"],
            "Cmd":["-I","-B","/task/bridge.py"],"User":"65534:65534",
            "WorkingDir":"/output","Env":list(docker.THREAD_ENV)},
        "HostConfig":{"Memory":3221225472,"MemorySwap":3221225472,
            "NanoCpus":1750000000,"PidsLimit":64,"NetworkMode":"none",
            "ReadonlyRootfs":True,"CapDrop":["ALL"],"SecurityOpt":["no-new-privileges"],
            "LogConfig":{"Type":"none"},"Privileged":False,"CapAdd":None,"Devices":None,
            "PidMode":"","IpcMode":"private",
            "Tmpfs":{"/work":"rw,nosuid,nodev,size=134217728,mode=1777",
                     "/tmp":"rw,noexec,nosuid,nodev,size=67108864,mode=1777",
                     "/output":"rw,noexec,nosuid,nodev,size=8388608,nr_inodes=32,uid=65534,gid=65534,mode=0700"},
            "Ulimits":[{"Name":k,"Soft":a,"Hard":b} for k,a,b in
                       (("cpu",20,22),("nofile",1024,1024),("core",0,0),("fsize",2000000,2000000))]},
        "Mounts":[{"Type":"bind","Source":s,"Destination":d,"RW":rw} for s,d,rw in mounts],
        "State":{"Running":False,"Paused":False,"Restarting":False,"OOMKilled":False,
                 "Error":"","Status":"exited" if final else "created","ExitCode":0,
                 "StartedAt":"invented-start"}}]

class IsolationControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="human-ripple-boundary-")
        self.root=Path(self.temp.name).resolve()
        self.mounts={(str(self.root/"input"),"/input",False),
                     (str(self.root/"task"),"/task",False),
                     (str(self.root/"program.py"),"/program/program.py",False)}
    def tearDown(self):self.temp.cleanup()
    def test_profile_exact_R_image_CPU_memory_and_readonly_mounts(self):
        argv=docker.create_argv("invented",self.root/"input",self.root/"task",self.root/"program.py")
        self.assertIn("--cpus=1.75",argv);self.assertIn("--memory=3g",argv)
        self.assertIn("--user=65534:65534",argv)
        self.assertEqual(argv[-5:],["--entrypoint=python",docker.IMAGE,"-I","-B","/task/bridge.py"])
        destinations=[a.split(",dst=",1)[1].split(",",1)[0] for a in argv if a.startswith("type=bind,")]
        self.assertEqual(set(destinations),{"/input","/task","/program/program.py"})
        info=inspection("invented","a"*64,self.mounts,False)
        docker.validate_inspection(info,"a"*64,"invented",self.mounts,final=False)
        for field,value in (("NetworkMode","host"),("Memory",3221225472.0),
                            ("NanoCpus",1000000000),("ReadonlyRootfs",False)):
            bad=copy.deepcopy(info);bad[0]["HostConfig"][field]=value
            with self.assertRaises(common.Refusal):
                docker.validate_inspection(bad,"a"*64,"invented",self.mounts,final=False)
    def invoke(self,remove_failure=False):
        public,reference,submitted=fixture()
        body=common.encode(submitted)
        name="human-ripple-candidate-"+__import__("hashlib").sha256(str(self.root/"candidate").encode()).hexdigest()[:24]
        calls=[];started=False
        def fake(argv,**kw):
            nonlocal started
            args=argv[5:];calls.append(args);out=b"";code=0
            if args[0]=="create":out=("a"*64).encode()
            elif args[0]=="inspect":out=common.encode(inspection(name,"a"*64,self.mounts,started))
            elif args[:2]==["start","-a"]:started=True;out=body
            elif args[:2]==["rm","-f"] and remove_failure:code=1
            record={"argv":argv,"dispatched":True,"complete":True,"exit_code":code,
                    "EOF":["stderr","stdout"],"reaped":True,"group_absent":True,
                    "cleanup_errors":[],"evidence_errors":[],"signals":[]}
            kw["observed"]("finished",record)
            return record,out,b""
        budget=common.Budget(time.monotonic()+20,8*1024**2,8*1024**2)
        with patch.object(docker,"_CLI_CONFIG",self.root/"config"),patch.object(docker,"_CLI_ENV",{}),patch.object(docker,"command",fake):
            episode=docker.run_candidate(root=self.root/"candidate",input_dir=self.root/"input",
                task_dir=self.root/"task",program=self.root/"program.py",budget=budget,
                active_deadline=time.monotonic()+10)
        return episode,calls,budget,public,reference
    def test_full_mock_lifecycle_closes_before_reference_grading(self):
        episode,calls,budget,public,reference=self.invoke()
        self.assertIs(type(episode),docker.ClosedRun)
        self.assertEqual(calls[-3][0],"rm");self.assertEqual(calls[-2][0],"ps");self.assertEqual(calls[-1][0],"ps")
        private=self.root/"reference.json";raw=common.encode(reference);private.write_bytes(raw)
        observed=[]
        original=cfg.load
        def guarded(desc,*a,**kw):
            if desc["path"]==str(private):
                self.assertTrue((self.root/"OUTCOME_COMMIT.private.json").exists())
                observed.append("reference")
            return original(desc,*a,**kw)
        with patch.object(cfg,"load",guarded):
            result,_=runner.grade_closed(episode,public,{"path":str(private),**common.pin(raw)},self.root,budget)
        self.assertEqual(result["status"],"scored");self.assertEqual(observed,["reference"])
    def test_uncertain_removal_never_publishes_successful_artifact(self):
        with self.assertRaisesRegex(common.Refusal,"candidate_not_completely_closed"):
            self.invoke(remove_failure=True)
        self.assertFalse((self.root/"candidate/SUBMISSION.private.bin").exists())

if __name__=="__main__":
    unittest.main(verbosity=2)

