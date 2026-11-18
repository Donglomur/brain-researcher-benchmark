"""Focused generated paired-intake controls; no authentic/protected references."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.io import savemat
from suns2_benchmark import paired_submission as m, candidate_io as cio
from suns2_benchmark.constants import VIDEO_IDS, ASSISTANCE_CONDITIONS

class PairedControls(unittest.TestCase):
    written=0
    @classmethod
    def write(cls,path,data):
        cls.written+=len(data)
        if cls.written>24576: raise AssertionError("generated fixture write cap")
        path.write_bytes(data)
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="suns2-paired-generated-",dir=os.environ.get("TMPDIR") or None)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name).resolve()
        cls.bindings=[]; cls.receipts=[]; cls.submissions=[]
        for arm,condition in enumerate(ASSISTANCE_CONDITIONS):
            procedure=("a" if arm==0 else "b")*64
            receipts=[]
            for i,video in enumerate(VIDEO_IDS):
                binding=dict(extension_id="suns2-paired-outcomes/v1",campaign_id="generated-trial",
                    common_protocol_digest="c"*64,condition=condition,procedure_digest=procedure,
                    fold_index=i,held_video=video,fresh_state_id=f"state-{arm}-{i}")
                cls.bindings.append(binding)
                row=dict(binding=deepcopy(binding),outputs={})
                receipts.append(row); cls.receipts.append(row)
            for oi,outcome in enumerate(m.OUTCOME_KINDS):
                directory=cls.root/f"{arm}-{outcome}"; (directory/"masks").mkdir(parents=True)
                cases=[]
                for i,video in enumerate(VIDEO_IDS):
                    array=np.zeros((50,50,1),dtype=np.uint8); array[arm*10+i,7+oi,0]=1
                    buffer=io.BytesIO(); savemat(buffer,{"Masks":array},do_compression=True)
                    raw=buffer.getvalue(); digest=hashlib.sha256(raw).hexdigest()
                    cls.write(directory/"masks"/f"{video}.mat",raw)
                    cases.append(dict(video_id=video,path=f"masks/{video}.mat",sha256=digest,bytes=len(raw)))
                    receipts[i]["outputs"][outcome]=dict(sha256=digest,bytes=len(raw))
                manifest=dict(schema="suns2-candidate-submission/v1",condition=condition,
                              procedure_digest=procedure,cases=cases)
                cls.write(directory/"submission.json",json.dumps(manifest).encode())
                cls.submissions.append(dict(condition=condition,outcome_kind=outcome,directory=str(directory)))
        cls.frozen=m.freeze_paired_submissions(cls.submissions,cls.bindings,cls.receipts)
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        if cls.root.exists(): raise AssertionError("generated fixture cleanup failed")
    def call(self,submissions=None,bindings=None,receipts=None,digest=None,reference_failure_root=None):
        self.checked_roots=[]
        def validate(path,digest,root):
            self.checked_roots.append(root)
            if root==reference_failure_root: raise ValueError("generated cross-panel reference refusal")
        with mock.patch.object(m,"validate_reference_spec",side_effect=validate):
            return m.grade_paired_submissions("/generated/private/spec.json","d"*64,
            self.submissions if submissions is None else submissions,
            self.bindings if bindings is None else bindings,
            self.receipts if receipts is None else receipts,
            self.frozen["freeze_sha256"] if digest is None else digest)
    def fake_grade(self,path,digest,directory,condition,procedure):
        _,metadata=cio.load_candidate_submission(directory,condition,procedure)
        return dict(condition=condition,procedure_digest=procedure,reference_spec_sha256=digest,
            submission=metadata,status="scored_with_undefined_original",scores={"original":None,
            "descriptive_outcome":{"same_panel_geometry_improvement":False}})
    def test_all36_admitted_before_grade_and_four_distinct_reports_preserved(self):
        admissions=[]; reports=[]
        def load(*args):
            admissions.append(args[0]); return cio.load_candidate_submission(*args)
        def grade(*args):
            self.assertEqual(len(admissions),4)
            self.assertEqual(self.checked_roots,[r["directory"] for r in self.submissions])
            report=self.fake_grade(*args); reports.append(report); return report
        with mock.patch.object(m,"load_candidate_submission",side_effect=load),mock.patch.object(m,"grade_submission",side_effect=grade):
            result=self.call()
        self.assertEqual(len(result["reports"]),4)
        self.assertEqual([r["outcome_kind"] for r in result["reports"]],list(m.OUTCOME_KINDS)*2)
        self.assertEqual([r["grading"] for r in result["reports"]],reports)
        self.assertFalse(result["recreation_label_proves_historical_reproduction"])
        self.assertEqual(result["new_benchmark_count"],0)
    def test_receipt_coverage_swaps_crossarm_aliases_and_changed_commitment(self):
        variants=[]
        variants.append(dict(receipts=self.receipts[:-1]))
        bad=deepcopy(self.receipts); bad[-1]=deepcopy(bad[0]); variants.append(dict(receipts=bad))
        bad=deepcopy(self.receipts); bad[0]["binding"]["held_video"]=VIDEO_IDS[1]; variants.append(dict(receipts=bad))
        bad=deepcopy(self.receipts); bad[0]["binding"]["procedure_digest"]="b"*64; variants.append(dict(receipts=bad))
        bad=deepcopy(self.receipts); a,b=m.OUTCOME_KINDS; bad[0]["outputs"][a],bad[0]["outputs"][b]=bad[0]["outputs"][b],bad[0]["outputs"][a]; variants.append(dict(receipts=bad))
        bad=deepcopy(self.submissions); bad[-1]["directory"]=bad[0]["directory"]; variants.append(dict(submissions=bad))
        variants.append(dict(digest="0"*64))
        before=json.dumps(self.frozen,sort_keys=True)
        changed=deepcopy(self.bindings); changed[0]["fresh_state_id"]="other-state"
        variants.append(dict(bindings=changed))
        with mock.patch.object(m,"grade_submission",side_effect=AssertionError("grading before fullfreeze")) as grader:
            for kwargs in variants:
                with self.subTest(keys=list(kwargs)),self.assertRaises(m.PairedSubmissionError): self.call(**kwargs)
            self.assertEqual(grader.call_count,0)
        self.assertEqual(json.dumps(self.frozen,sort_keys=True),before)
    def test_fourth_returned_pin_mismatch_releases_no_partial_report(self):
        count=0
        def grade(*args):
            nonlocal count
            count+=1; report=self.fake_grade(*args)
            if count==4: report["submission"]["cases"][0]["sha256"]="f"*64
            return report
        with mock.patch.object(m,"grade_submission",side_effect=grade),self.assertRaises(m.PairedSubmissionError) as caught:
            self.call()
        self.assertEqual(count,4)
        self.assertEqual(str(caught.exception),"Paired grading refused; no partial reports released")
        self.assertFalse(hasattr(caught.exception,"reports"))
    def test_reference_custody_refusal_on_fourth_root_precedes_any_grade(self):
        with mock.patch.object(m,"grade_submission") as grader,self.assertRaises(m.PairedSubmissionError):
            self.call(reference_failure_root=self.submissions[-1]["directory"])
        self.assertEqual(self.checked_roots,[r["directory"] for r in self.submissions])
        self.assertEqual(grader.call_count,0)
    def test_directory_replacement_after_load_and_at_final_barrier(self):
        root=Path(self.submissions[0]["directory"])
        backup=root.with_name(root.name+"-held")
        for trigger in (1,4):
            count=0
            def load(*args):
                nonlocal count
                result=cio.load_candidate_submission(*args); count+=1
                if count==trigger:
                    root.rename(backup); root.mkdir()
                return result
            try:
                with mock.patch.object(m,"load_candidate_submission",side_effect=load),self.assertRaisesRegex(m.PairedSubmissionError,"directory identity changed"):
                    m.freeze_paired_submissions(self.submissions,self.bindings,self.receipts)
                self.assertEqual(count,trigger)
            finally:
                if backup.exists(): root.rmdir(); backup.rename(root)
    def test_real_generated_file_changes_before_and_during_private_grading(self):
        path=Path(self.submissions[-1]["directory"])/"masks"/f"{VIDEO_IDS[0]}.mat"
        original=path.read_bytes()
        try:
            self.write(path,original+b"x")
            with mock.patch.object(m,"grade_submission") as grader,self.assertRaises(m.PairedSubmissionError): self.call()
            self.assertEqual(grader.call_count,0)
        finally: self.write(path,original)
        count=0
        def grade(*args):
            nonlocal count
            count+=1
            if count==1: self.write(path,original+b"x")
            return self.fake_grade(*args)
        try:
            with mock.patch.object(m,"grade_submission",side_effect=grade),self.assertRaises(m.PairedSubmissionError) as caught: self.call()
            self.assertEqual(count,4)
            self.assertEqual(str(caught.exception),"Paired grading refused; no partial reports released")
        finally: self.write(path,original)

if __name__=="__main__":
    buffer=io.StringIO()
    result=unittest.TextTestRunner(stream=buffer,verbosity=1,failfast=True).run(unittest.defaultTestLoader.loadTestsFromTestCase(PairedControls))
    print(buffer.getvalue()[:2048],end="")
    print("generated_fixture_bytes_written="+str(PairedControls.written)+"; authentic_reads=0; protected_grades=0")
    sys.exit(0 if result.wasSuccessful() else 1)
