"""Generated protected-grade/driver/observer controls; no scientific execution.

Non-prediction scientific phases and external authority/transport are explicit
uncredentialed doubles. The actual protected grader, Programme.grade, captured
driver, Bodies, Ledger and receipt validator run on complete generated support.
"""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
CENTRAL = HERE.parent / "programme-source/implementation-v1/central-integration/successor-v3"
PARENT = CENTRAL / "effective-parent"
EXPECTED_PHASES = ("runtime", "commit", "prepare", "hmp", "references", "prediction_actors", "dispositions",
                   "prediction_closure", "prediction_grade", "reconstruction_actors", "reconstruction_grade",
                   "spatial", "explanations", "reasoning_grade", "study_closeout")
COUNTS = {"fixtures": 0, "generated_write_bytes": 0, "logical_and_observed_read_bytes": 0}


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GeneratedProgramme:
    """Prepare a real Programme.grade without executing any scientific phase."""
    def __init__(self, owner, *, statuses=None, later_failure=False, hmp_complete=True,
                 refusal=None, body_cap=2*1048576):
        self.owner = owner
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("NEURAL004_PAIRED_TMP"))
        self.root = Path(self.tmp.name)
        self.body_root = self.root / "parent-bodies"; self.body_root.mkdir()
        self.receipt_ios = []; self.manual_writes = 0
        common, controller = owner.parent.module("common"), owner.parent.module("controller")
        grading, barrier, actors, references, bundle, actor_slots, reference_slots = owner.identity.fixture(
            owner.parent, statuses=statuses)
        barrier.release = None
        now = time.monotonic_ns()
        self.clock = {"origin_ns": now-1000000, "scientific_ns": now+60_000_000_000,
                      "closeout_ns": now+70_000_000_000, "outer_ns": now+80_000_000_000}
        limits = {k: 64*1048576 for k in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes", "processes", "requests")}
        self.ledger = common.Ledger(limits, *[self.clock[k] for k in ("origin_ns", "scientific_ns", "closeout_ns", "outer_ns")])
        self.io = owner.ci.IO(64*1048576, 64*1048576, 64*1048576, self.clock["origin_ns"]/1e9,
                              self.clock["outer_ns"]/1e9)
        p = controller.Programme.__new__(controller.Programme)
        p.ledger = self.ledger; p.bodies = common.Bodies(self.body_root, self.ledger, body_cap)
        p.contexts = actor_slots; p.reference_contexts = reference_slots
        p.seed = b"generated-N004-identity-only-seed!"
        p.actors = {c: dict(actors[m+"/"+v][person]) for (m,v,person),c in actor_slots.items()}
        p.reference_seals = {c: dict(references[f][person]) for (f,person),c in reference_slots.items()
                             if references[f][person]["status"] == "sealed"}
        p.closed_dispositions = {c: value["disposition"] for c,value in barrier.closed.items()}
        p.private_maps = {c: actors[m+"/"+v][person]["answer_map"] for (m,v,person),c in actor_slots.items()}
        views = owner.parent.module("views")
        p.reference_maps = {person: [{"id": views.opaque(p.seed,"reference-private","trial",[person,i]),
                                     "source_id": a["id"]} for i,a in enumerate(bundle["answers"][person])]
                            for person in common.PEOPLE}
        p.data = {"source_admission": {"generated_only": True}, "private_rows": [
            {"person": person, "epoch": int(a["id"].split("/")[1]), "contrast": a["value"]}
            for person in common.PEOPLE for a in bundle["answers"][person]]}
        p.barrier = barrier; p.transport = types.SimpleNamespace(records=[])
        p.hmp = {"complete": hmp_complete}; p.references = {"full_closure": True}
        p.prediction_grade = None; p.reconstruction_grade = {}; p.spatial_records = None
        target = p.target_bundle()
        subject = {"contexts_pin": common.pin(barrier.closed,8*1048576),
                   "target_bundle_pin": common.pin(target,32*1048576)}
        self.release = barrier.authorities.envelope("operator", "target_release", subject,
            {"prediction_contexts_closed": True, "no_live_actor_feedback_route": True,
             "protected_scorer_identity": common.pin({"generated_only": True}), "release_ns": 400})
        # Expected old grade is made by the actual grader before the driver runs.
        barrier.open(target,self.release)
        self.expected_grade = grading.grade_prediction_panels(barrier, actors, references, target)
        self.expected_grade["supplied_HMP_condition_complete"] = hmp_complete
        self.expected_bytes = common.encode(self.expected_grade,body_cap)
        barrier.release = None
        self.p = p
        self.environment_pin = common.pin({"generated_environment": True})
        p.admit_runtime = lambda _: {"facts": {"environment_pin": self.environment_pin}}
        p.commit = lambda _: None; p.prepare = lambda *_: None
        p.numerical_references = lambda *_: p.bodies.put_json("REFERENCE_INDEX.json", {"generated_only": True})
        def hmp(*_):
            root = self.root / "hmp-private"; root.mkdir()
            raw = owner.ci.encoded({"artifacts_before_index": [], "generated_only": True})
            self.write(root / "index.json",raw)
            p.hmp["index"] = {"name": "index.json", **owner.ci.pin(raw)}
            return p.bodies.put_json("HMP_RESULT_INDEX.json", {"output_root":str(root),"index":p.hmp["index"]})
        p.numerical_hmp = hmp; p.prediction_actors = lambda *_: None; p.dispositions = lambda: p.closed_dispositions
        p.close_predictions = lambda *_: None
        def reconstruction(*_):
            if later_failure: raise ValueError("generated later reconstruction failure")
        p.reconstruction_actors = reconstruction
        def reconstruction_grades(*_):
            p.reconstruction_grade = {m: {"status":"compared"} for m in common.MODES}
            return p.bodies.put_json("RECONSTRUCTION_GRADE.json",p.reconstruction_grade)
        p.reconstruction_grades = reconstruction_grades
        def spatial():
            p.spatial_records = {"generated_only":True}
            return p.bodies.put_json("SPATIAL_INDEX.json",p.spatial_records)
        p.spatial_descriptions = spatial; p.explanation_actors = lambda *_: None
        def reasoning(*_):
            p.reasoning_result = {"generated_only":True}
            return p.bodies.put_json("REASONING_GRADE.json",p.reasoning_result)
        p.reasoning_grade = reasoning
        p.closeout = lambda *_: p.bodies.put_json("STUDY_CLOSEOUT.json",{"generated_only":True,"whole_study_qualified":False})
        if refusal == "barrier": barrier.closed.pop(next(iter(barrier.closed)))
        original_grade = p.grade
        def grade(envelope):
            result = original_grade(envelope)
            if refusal in ("read", "live", "write", "retained"):
                key = {"read":"read_bytes","live":"live_bytes","write":"write_bytes","retained":"retained_bytes"}[refusal]
                self.ledger.limits[key] = self.ledger.used[key] + (1 if refusal != "live" else 1024)
            if refusal == "body": p.bodies.cap = 1
            if refusal == "clock": self.ledger.scientific = self.ledger.clock()
            return result
        if refusal: p.grade = grade
        owner_ref = self
        class Channel:
            def __init__(self,*_):self.audit=[]
            def exchange(self,*args,**kwargs):
                self.audit.append({"generated_only":True})
                return {"seed_base64":base64.b64encode(b"x"*32).decode(),"delivery_pin":common.pin({"generated_only":True})}
            def bind_parent(self,*_):pass
        authority = types.SimpleNamespace(MetadataChannel=Channel,
            IncrementalEnvelope=lambda _: owner_ref.release, ProviderAccess=lambda *_:None)
        self.facade = types.SimpleNamespace(module=lambda name: {
            "entry":types.SimpleNamespace(construct=lambda *_:p), "authority":authority,
            "common":common,"views":views}[name])
        config = {"clock": self.clock, "source_pin":common.pin({"generated_source":True}),"body_cap":body_cap,
                  "job_limits":{"index_bytes":1024}}
        self.bound = {"operation":{"channel":{},"provider_deployments":{},"original_root":"unused",
                       "source_roster":{},"hmp_environment":{},"hmp_limits":{"metadata_bytes":1048576},
                       "reference_budget":{},"request_scientific_qualification":False},
                      "config":config,"output":self.root,"repository":self.root,"environment_pin":self.environment_pin,
                      "profile":{"worker_live_bytes":64*1048576,"max_output_files":128,"artifact_max_bytes":2*1048576,
                                 "worker_return_bytes":2*1048576,"worker_log_bytes":1048576},
                      "max_jobs":1,"operation_pin":common.pin({"operation":"generated"}),
                      "parent_manifest_pin":common.pin({"parent":"generated"}),"original_clock":self.clock,
                      "canonical_config_pin":common.pin(config,16*1048576)}
        self.result = None

    def write(self,path,raw):
        # Explicitly replace only this generated fixture's own files. Real Bodies
        # makes retained outputs read-only; mutation controls must reach the
        # observer identity/linkage checks without weakening that production rule.
        if path.exists(): path.unlink()
        path.write_bytes(raw);self.manual_writes += len(raw)

    def run(self):
        self.result = self.owner.driver.run(self.io,self.bound,self.facade)
        return self.result

    def phase(self,name="prediction_grade"):
        return next(r for r in self.result["phases"] if r["phase"]==name)

    def build_observation(self):
        ci = self.owner.ci; ret = copy.deepcopy(self.result)
        binding = {"origin":self.clock["origin_ns"]/1e9,"cutoff":self.clock["scientific_ns"]/1e9,
                   "deadline":self.clock["outer_ns"]/1e9}
        argv = ["generated-only-no-worker"]
        empty = ci.pin(b"")
        close = {"schema":"neural065_independent_controller_close_v1","exit_code":0,"natural_exit":True,
                 "forced":False,"reaped":True,"process_group_absent":True,"cleanup_errors":[],"error":None,
                 "argv":argv,"caller_custody_claim":False,"origin":binding["origin"],"work_deadline":binding["cutoff"],
                 "global_deadline":binding["deadline"],"finished":binding["origin"]+.001,
                 "logs":{"stdout":empty,"stderr":empty}}
        for name,value in [("WORKER_RETURN.json",ret),("WORKER_CLOSE.json",close)]:self.write(self.root/name,ci.encoded(value))
        for stream in ("stdout","stderr"):self.write(self.root/("worker."+stream+".log"),b"")
        (self.root/"observer-journal").mkdir(exist_ok=True)
        self.observed = {"errors":[],"worker_failure":None,"close":close,"worker_return":ret,"binding":binding,"argv":argv,
                         "worker_return_pin":ci.pin(ci.encoded(ret)),"close_pin":ci.pin(ci.encoded(close)),
                         "logs":close["logs"],"observer_events":[]}
        return self.observed

    def validate(self):
        ci=self.owner.ci
        io=ci.IO(64*1048576,64*1048576,64*1048576,self.clock["origin_ns"]/1e9,self.clock["outer_ns"]/1e9)
        self.receipt_ios.append(io)
        with mock.patch.object(self.owner.central.module("observer"),"argv_for",
                               return_value=(self.observed["binding"],self.observed["argv"])):
            return self.owner.receipt.validate(io,self.bound,{"parent_manifest_pin":self.bound["parent_manifest_pin"]},self.observed)

    def rewrite_member(self,name,value):
        raw=self.owner.ci.encoded(value);self.write(self.body_root/name,raw)
        self.result["parent_body_inventory"][name]={"path":name,**self.owner.ci.pin(raw)}

    def close(self):
        COUNTS["fixtures"]+=1
        COUNTS["generated_write_bytes"]+=self.manual_writes+self.io.writes+self.ledger.used["write_bytes"]
        COUNTS["logical_and_observed_read_bytes"]+=self.io.reads+self.ledger.used["read_bytes"]+sum(x.reads for x in self.receipt_ios)
        self.tmp.cleanup()


class ProgrammeIntegrationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity=load_file("_n004_paired_identity_fixture",HERE.parent/"protected-grading-identity-v1/test_grading_identity.py")
        cls.identity.verify_source_closure()
        cls.previous_io=sys.modules.get("central_io")
        cls.ci=load_file("central_io",CENTRAL/"central_io.py")
        cls.loader=load_file("_n004_paired_loader",CENTRAL/"source_loader.py")
        own=json.loads((CENTRAL/"SOURCE_MANIFEST.json").read_bytes())["files"]
        parent=json.loads((CENTRAL/"EFFECTIVE_PARENT_MANIFEST.json").read_bytes())["files"]
        cls.central=cls.loader.Captured("_n004_paired_central",CENTRAL,{n:(CENTRAL/n).read_bytes() for n in own}).install()
        cls.parent=cls.loader.Captured("_n004_paired_parent",PARENT,{r["path"]:(PARENT/r["path"]).read_bytes() for r in parent}).install()
        cls.driver=cls.central.module("driver");cls.receipt=cls.central.module("receipt_check")
        cls.kernel=cls.central.module("paired_contrasts")

    @classmethod
    def tearDownClass(cls):
        cls.parent.close();cls.central.close()
        for name in ("_n004_paired_identity_fixture","_n004_paired_loader"):sys.modules.pop(name,None)
        if cls.previous_io is None:sys.modules.pop("central_io",None)
        else:sys.modules["central_io"]=cls.previous_io

    def fixture(self,**kw):
        value=GeneratedProgramme(type(self),**kw);self.addCleanup(value.close);return value

    def test_complete_real_grade_driver_and_receipt(self):
        f=self.fixture();f.run()
        self.assertEqual(f.phase()["status"],"completed")
        self.assertTrue(f.result["all_phases_completed"])
        self.assertEqual((f.body_root/"PREDICTION_GRADE.json").read_bytes(),f.expected_bytes)
        report=json.loads((f.body_root/"PAIRED_PREDICTION_CONTRASTS.json").read_bytes())
        self.assertEqual(report,self.kernel.paired_contrasts(f.expected_grade))
        self.assertEqual(len(report["comparisons"]),15)
        self.assertTrue(all(len(r["people"])==26 and r["population_confidence_interval"] is None for r in report["comparisons"]))
        self.assertEqual(f.ledger.used["read_bytes"],len(f.expected_bytes))
        self.assertEqual(f.ledger.used["live_bytes"],4*len(f.expected_bytes)+1048576)
        self.assertEqual(f.ledger.live_current,0)
        f.build_observation();observed=f.validate()
        self.assertTrue(observed["all_phases_completed"])
        self.assertFalse(observed["new_metric_computed"])

    def test_incomplete_partners_preserve_grade_and_unaffected_comparisons(self):
        f=self.fixture(statuses={("actor","P/E","4"):"blocked",("reference","N","8"):"failed"})
        f.run();self.assertEqual(f.phase()["status"],"completed")
        self.assertEqual((f.body_root/"PREDICTION_GRADE.json").read_bytes(),f.expected_bytes)
        report=json.loads((f.body_root/"PAIRED_PREDICTION_CONTRASTS.json").read_bytes())
        comparisons={r["id"]:r for r in report["comparisons"]}
        self.assertEqual(comparisons["P/E_vs_B"]["status"],"incomplete")
        self.assertIsNone(comparisons["P/E_vs_B"]["person_macro_difference"])
        self.assertIsNone(comparisons["reference/N_vs_B"]["descriptive_delete_one_person_macro"])
        self.assertEqual(comparisons["I/H_vs_B"]["status"],"complete")
        self.assertFalse(report["all_comparisons_complete"])
        f.build_observation();f.validate()

    def test_later_failure_still_requires_and_accepts_paired_report(self):
        f=self.fixture(later_failure=True,hmp_complete=False);f.run()
        self.assertFalse(f.result["all_phases_completed"])
        self.assertEqual(f.phase()["status"],"completed")
        self.assertFalse(f.p.prediction_grade["supplied_HMP_condition_complete"])
        self.assertEqual((f.body_root/"PREDICTION_GRADE.json").read_bytes(),f.expected_bytes)
        f.build_observation();self.assertFalse(f.validate()["all_phases_completed"])
        name="PAIRED_PREDICTION_CONTRASTS.json"
        (f.body_root/name).unlink();del f.result["parent_body_inventory"][name];f.build_observation()
        with self.assertRaisesRegex(ValueError,"Completed grading requires"):f.validate()

    def test_receipt_refuses_missing_grade_even_with_derived_report(self):
        f=self.fixture(later_failure=True);f.run();name="PREDICTION_GRADE.json"
        (f.body_root/name).unlink();del f.result["parent_body_inventory"][name];f.build_observation()
        with self.assertRaisesRegex(ValueError,"Completed grading requires"):f.validate()

    def test_receipt_refuses_rehashed_wrong_grade_link_or_schema(self):
        f=self.fixture(later_failure=True);f.run();name="PAIRED_PREDICTION_CONTRASTS.json"
        original=json.loads((f.body_root/name).read_bytes())
        for field,value in [("input_grade_sha256","0"*64),("schema","wrong")]:
            changed=dict(original);changed[field]=value;f.rewrite_member(name,changed);f.build_observation()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"links exact observed"):f.validate()

    def test_receipt_refuses_changed_bytes_and_unindexed_output(self):
        f=self.fixture(later_failure=True);f.run();f.build_observation()
        path=f.body_root/"PAIRED_PREDICTION_CONTRASTS.json";original=path.read_bytes()
        f.write(path,original[:-1]+b" ")
        with self.assertRaisesRegex(ValueError,"artifact identity"):f.validate()
        f.write(path,original);f.write(f.body_root/"unindexed.json",b"{}")
        with self.assertRaisesRegex(ValueError,"source-owned ordinary artifacts"):f.validate()

    def test_barrier_failure_never_invokes_kernel(self):
        f=self.fixture(refusal="barrier")
        with mock.patch.object(self.driver,"paired_contrasts",side_effect=AssertionError("kernel before release")) as kernel:f.run()
        kernel.assert_not_called();self.assertEqual(f.phase()["status"],"failed")
        self.assertNotIn("PREDICTION_GRADE.json",f.p.bodies.records)
        self.assertNotIn("PAIRED_PREDICTION_CONTRASTS.json",f.p.bodies.records)

    def test_read_and_live_refuse_before_kernel_and_keep_original_grade(self):
        for kind in ("read","live"):
            with self.subTest(kind=kind):
                f=self.fixture(refusal=kind)
                with mock.patch.object(self.driver,"paired_contrasts",side_effect=AssertionError("unadmitted traversal")) as kernel:f.run()
                kernel.assert_not_called();self.assertEqual(f.phase()["status"],"failed")
                self.assertEqual((f.body_root/"PREDICTION_GRADE.json").read_bytes(),f.expected_bytes)
                self.assertNotIn("PAIRED_PREDICTION_CONTRASTS.json",f.p.bodies.records)
                self.assertEqual(f.phase("explanations")["status"],"blocked")

    def test_kernel_failure_preserves_grade_and_existing_dependency_behavior(self):
        f=self.fixture()
        with mock.patch.object(self.driver,"paired_contrasts",side_effect=self.kernel.InvalidGrade("generated invalid report operand")):f.run()
        self.assertEqual(f.phase()["status"],"failed")
        self.assertEqual(f.phase("explanations")["status"],"blocked")
        self.assertEqual(f.phase("reconstruction_actors")["status"],"completed")
        self.assertEqual(f.phase("spatial")["status"],"completed")
        self.assertEqual((f.body_root/"PREDICTION_GRADE.json").read_bytes(),f.expected_bytes)
        self.assertEqual(f.ledger.live_current,0)
        f.build_observation();f.validate()

    def test_write_retention_body_and_clock_caps_are_not_relaxed(self):
        for kind in ("write","retained","body","clock"):
            with self.subTest(kind=kind):
                f=self.fixture(refusal=kind);f.run()
                self.assertEqual(f.phase()["status"],"failed")
                self.assertEqual((f.body_root/"PREDICTION_GRADE.json").read_bytes(),f.expected_bytes)
                self.assertNotIn("PAIRED_PREDICTION_CONTRASTS.json",f.p.bodies.records)
                self.assertEqual(f.ledger.live_current,0)

    def test_output_inventory_ceiling_is_unchanged(self):
        f=self.fixture();f.bound["profile"]["max_output_files"]=1
        with self.assertRaisesRegex(ValueError,"retained parent inventory"):f.run()
        self.assertIn("PREDICTION_GRADE.json",f.p.bodies.records)
        self.assertIn("PAIRED_PREDICTION_CONTRASTS.json",f.p.bodies.records)

    def test_exact_captured_kernel_and_current_source_chain(self):
        self.assertEqual((CENTRAL/"paired_contrasts.py").read_bytes(),(HERE/"paired_contrasts.py").read_bytes())
        self.assertEqual(self.driver.PHASES,EXPECTED_PHASES)
        self.identity.verify_source_closure()
        historical=json.loads((HERE/"SOURCE_EVIDENCE.json").read_bytes())
        self.assertFalse(historical["qualification"]["existing_controller_automatically_calls_extension"])
        current=json.loads((HERE/"PROGRAMME_INTEGRATION.json").read_bytes())
        for row in current["current_source_records"]:
            self.assertEqual(self.ci.pin((HERE.parents[4]/row["path"]).read_bytes()),
                             {k:row[k] for k in ("bytes","sha256")})
        self.assertFalse(current["runtime_qualified"])


if __name__ == "__main__":
    unittest.main()
