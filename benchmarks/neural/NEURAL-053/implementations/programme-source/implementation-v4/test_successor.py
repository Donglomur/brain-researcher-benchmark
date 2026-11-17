"""Narrow I1-I3 invented controls. No authentic arrays, provider or scientific run."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cohort import ARMS, Refusal, Profile
from io_support import Budget, canonical_bytes, object_digest, REQUIRED_RUN_QUALIFICATIONS
from grading import required_case_keys, validate_complete_panels, array_digest, grade_full_run
from selection import ReferenceSelection, derive_reference_selection, admit_reference_selection
from phase_manifest import SOURCE_FILES, budget_snapshot, admit_invocation
from phase_worker import IncrementBudget
from reference.models import setting_grid, select_setting

ROOT = Path(__file__).resolve().parent
FIXTURE_CAP = 2 * 1024 * 1024


def budget():
    now = time.monotonic()
    return Budget({"source_read": 32*1024*1024, "artifact_write": 2*1024*1024}, now, now+300)


def authority(phase, extra):
    bindings = {"phase":phase, "profile":"four_people_1854_classes_96_contexts_3904_fits", **extra}
    q = {name:hashlib.sha256(name.encode()).hexdigest() for name in REQUIRED_RUN_QUALIFICATIONS}
    permit = {"schema":"neural053_full_run_admission_v1", "decision":"accepted_exact_canonical_full_run",
              "bindings":bindings,"qualifications":q,"independent_reviewer":"INVENTED-CONTROL-NOT-AUTHORITY"}
    return permit, frozenset([object_digest(permit),*q.values()])


class Fixture:
    def __init__(self, root, materialize):
        self.root,self.materialize,self.bytes = Path(root),materialize,0
    def put(self, name, value):
        body=canonical_bytes(value); self.bytes+=len(body)
        if self.materialize:
            p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(body)
        return {"path":str(self.root/name),"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}


def reference_fixture(f):
    grid=setting_grid(); public={"ridge":"ridge","shrinkage_lda":"lda","fourier_ridge":"fourier_ridge"}
    records=[{"rank":r,"top1_fraction":[r+1,55620],"balanced_top1":(r+1)/55620,
        "mean_log_loss":float(20-r)+t/100,"temperature":t,"people":3,"classes":1854,
        "validation_rows_per_person_class":10} for r in range(16) for t in (.1,1,10)]
    selected={family:select_setting([r for r in records if grid[r["rank"]]["family"]==family],family) for family in public}
    primary=public[grid[select_setting(records)["rank"]]["family"]]
    sha="a"*64
    fits=[{"phase":"inner","rank":r,"split":s,"state_digest":sha,"fit_support":sha,"validation_support":sha}
          for r in range(16) for s in range(15)]
    fits += [{"phase":"final","family":public[family],"rank":choice["rank"],"temperature":choice["temperature"],
              "state_digest":sha,"fit_support":sha} for family,choice in selected.items()]
    fits += [{"phase":"final","family":"centroid","temperature":1,"state_digest":sha,"fit_support":sha}]
    cases=[]
    for fold in range(4):
        for arm in ARMS:
            case={"fold_ordinal":fold,"arm":arm,"inner_fits":240,"selected_family_refits":3,"centroid_fits":1}
            stem=f"{fold}-{arm}"
            evidence=f.put(stem+"-evidence.json",{"schema":"neural053_reference_case_v1","fold_ordinal":fold,"arm":arm,
                "fits":244,"engineering_profile":False,"selection_records":records,"fit_records":fits,
                "selected":selected,"primary_family":primary})
            # Only artifact descriptors; no plan/model body is created or run.
            plans={name:{"path":str(f.root/(stem+name+"-NEVER-OPEN")),"bytes":0,"sha256":sha} for name in (*public.values(),"centroid")}
            value={"case":case,"fits":244,"plans":plans,"training_selection":evidence,"primary_family":primary,
                   "source_method_or_scientific_admission":False}
            pin=f.put(stem+"-manifest.json",value)
            cases.append({**value,"artifact_manifest_sha256":pin["sha256"],"manifest":pin})
    return f.put("programme.json",{"schema":"neural053_full_reference_program_v1","completed_fits":3904,"cases":cases,
                                   "scientific_qualification_conferred":False})


def source_manifest():
    result=[]
    for name in sorted(SOURCE_FILES):
        p=ROOT/name; size=p.stat().st_size
        body=p.read_bytes(); assert len(body)==size
        result.append({"path":name,"bytes":size,"sha256":hashlib.sha256(body).hexdigest()})
    return result


class SuccessorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="neural053-i123-")
        cls.f=Fixture(cls.temp.name,True)
        cls.program=reference_fixture(cls.f)
        cls.selection=derive_reference_selection(cls.program,budget())
        cls.selection_pin=cls.f.put("selection.json",cls.selection.document)
        cls.sources=source_manifest()
        cls.source_bytes=sum(p["bytes"] for p in cls.sources)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_i2_complete_training_selection_rederived(self):
        result=admit_reference_selection(self.selection_pin,self.program,self.selection.digest,budget())
        self.assertEqual(len(result.families),16)
        self.assertEqual(result.document["source_reference_program"],self.program)

    def test_i2_substitution_refused_before_any_records_or_targets(self):
        bad=copy.deepcopy(self.selection.document);bad["cases"][0]["family"]="ridge"
        self.assertNotEqual(bad,self.selection.document)
        pin=self.f.put("substituted-selection.json",bad)
        permit,approved=authority("grade_all",{"reference_program_output_sha256":self.program["sha256"],
                                             "reference_selection_sha256":self.selection.digest})
        touched=[]
        def forbidden(*args): touched.append(True);raise AssertionError("Answer/record access")
        with self.assertRaises(Refusal):
            grade_full_run(forbidden,{},frozenset(),pin,self.program,frozenset(),forbidden,
                           permit,permit["bindings"],approved,budget())
        self.assertEqual(touched,[])

    def test_i2_training_evidence_tamper_refused(self):
        original=self.program["sha256"]
        pin={**self.program,"sha256":"0"*64}
        with self.assertRaises(Refusal): derive_reference_selection(pin,budget())
        self.assertNotEqual(original,pin["sha256"])

    def panel(self):
        import numpy as np
        # Complete160 routing keys, only4 invented rows/2classes; never canonical execution.
        profile=Profile(people=("p0","p1","p2","p3"),classes=2,engineering=True)
        p=np.array([[.6,.4],[.4,.6],[.6,.4],[.4,.6]],dtype=np.float32)
        records={};descriptors={};executions=set();method="b"*64
        for key in required_case_keys():
            d={"classes":[1,2],"query_ids":["q0","q1","q2","q3"]};descriptors[key]=d
            e={"schema":"neural053_prediction_execution_v1","context_key":list(key),"method_admission_digest":method,
               "query_descriptor_digest":object_digest(d),"reference_selection_digest":self.selection.digest,
               "probabilities_digest":array_digest(p),"natural_exit_code":0,"source_state_unchanged":True}
            executions.add(object_digest(e))
            records[key]={"context_key":list(key),"probabilities":p,"query_ids":d["query_ids"],"classes":d["classes"],
                "query_descriptor_digest":object_digest(d),"reference_selection_digest":self.selection.digest,
                "method_admission_digest":method,"execution_receipt":e}
        return records,descriptors,frozenset([method]),frozenset(executions),profile

    def test_i1_full_panel_exact_int_zero_and_impostors(self):
        records,descriptors,methods,executions,profile=self.panel()
        self.assertTrue(validate_complete_panels(records,descriptors,methods,self.selection,executions,profile))
        key=required_case_keys()[0]
        for invalid in (False,0.0,"0",None):
            records[key]["execution_receipt"]["natural_exit_code"]=invalid
            admitted=frozenset([*executions,object_digest(records[key]["execution_receipt"])])
            with self.assertRaises(Refusal): validate_complete_panels(records,descriptors,methods,self.selection,admitted,profile)

    def phase_fixture(self,suffix,*,bad_operand=False,bad_source=False,bad_exit=False):
        ledger=budget(); before=budget_snapshot(ledger)
        source=copy.deepcopy(self.sources)
        if bad_source: source[0]["sha256"]="0"*64
        prepared=self.f.put(suffix+"-prepared.json",{"schema":"INVENTED-NO-NUMERIC-BODY"})
        output=self.f.put(suffix+"-output.json",{"schema":"neural053_phase_outputs_v2","phase":"prepare_original",
             "invocation_sha256":"a"*64,"runtime_source_sha256":object_digest(source),"artifacts":{"prepared":prepared}})
        completion={"schema":"neural053_phase_observed_completion_v2","phase":"prepare_original","natural_exit_code":False if bad_exit else 0,
            "source_state_unchanged":True,"process_group_absent":True,"streams_closed":True,
            "output_manifest":output,"invocation_sha256":"a"*64,"runtime_source_sha256":object_digest(source),"budget_after":before}
        parent=self.f.put(suffix+"-completion.json",completion)
        actual=prepared if not bad_operand else {**prepared,"path":prepared["path"]+"-UNRELATED"}
        invocation=self.f.put(suffix+"-invocation.json",{"schema":"neural053_phase_invocation_v2","phase":"prepare_views",
            "source_root":str(ROOT),"runtime_sources":source,"artifacts":{"prepared":actual},"parameters":{},
            "upstream":{"prepare_original":parent},"ledger_parent":parent})
        permit,approved=authority("prepare_views",{"budget_before_sha256":object_digest(before),"invocation":invocation,
                                                  "runtime_source_manifest_sha256":object_digest(source)})
        return ledger,invocation,permit,frozenset([*approved,object_digest(completion)])

    def test_i3_actual_source_and_upstream_operand_positive(self):
        b,p,permit,a=self.phase_fixture("positive")
        value=admit_invocation("prepare_views",p,permit,permit["bindings"],a,b)
        self.assertEqual(set(value["artifacts"]),{"prepared"})
        self.assertGreaterEqual(b.used["source_read"],self.source_bytes)

    def test_i3_actual_operand_source_and_upstream_exit_refusal(self):
        for name,option in (("operand","bad_operand"),("source","bad_source"),("exit","bad_exit")):
            b,p,permit,a=self.phase_fixture(name,**{option:True})
            with self.assertRaises(Refusal): admit_invocation("prepare_views",p,permit,permit["bindings"],a,b)

    def test_i3_invocation_and_ledger_substitution_precedes_sources(self):
        b,p,permit,a=self.phase_fixture("substitute")
        with self.assertRaises(Refusal): admit_invocation("prepare_views",{**p,"sha256":"0"*64},permit,permit["bindings"],a,b)
        self.assertEqual(b.used["source_read"],0)
        b.charge("source_read",1)
        with self.assertRaises(Refusal): admit_invocation("prepare_views",p,permit,permit["bindings"],a,b)
        self.assertEqual(b.used["source_read"],1)

    def test_phase_increment_caps_retain_original_ledger(self):
        base=budget_snapshot(budget());base["used"]["source_read"]=17
        child=IncrementBudget(base,{"source_read":3,"artifact_write":2})
        child.charge("source_read",3)
        self.assertEqual(child.used["source_read"],20)
        self.assertEqual(child.origin_monotonic,base["origin_monotonic"])
        with self.assertRaises(Refusal):child.charge("source_read",1)


def preflight():
    # Serialize planned fixture once in memory without writes, data or executions.
    f=Fixture("/tmp/neural053-i123-XXXXXXXX",False);reference_fixture(f)
    # Conservative space for selection+substitution, five source/phase metadata
    # groups, shared4x2 probabilities, records and transient support structures.
    provision=f.bytes+260000
    require=__import__("cohort").require
    require(provision<=FIXTURE_CAP,"Exact parent-only2MiB fixture provision")
    return {"schema":"neural053_i123_control_preflight_v2","reference_fixture_serialized_bytes":f.bytes,
            "cumulative_fixture_provision_bytes":FIXTURE_CAP,"estimated_materialized_ceiling_bytes":provision,
            "retained_provision_bytes":65536,"live_provision_bytes":6*1024*1024,
            "authentic_data_or_scientific_runs":0,"physical_RSS_or_IO_certified":False}


if __name__=="__main__":
    import sys
    if sys.argv[1:]==["--preflight"]:print(json.dumps(preflight(),sort_keys=True))
    else:unittest.main()
