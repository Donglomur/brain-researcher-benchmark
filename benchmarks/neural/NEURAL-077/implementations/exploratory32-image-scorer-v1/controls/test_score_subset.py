"""Generated-only controls; no actual protocol, images, gold or data opened."""
import json, math, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import types
HERE=Path(__file__).resolve().parents[1]
body=(HERE/"score_subset.py").read_bytes()
s=types.ModuleType("synthetic_subset");s.__file__=str(HERE/"score_subset.py")
exec(compile(body,s.__file__,"exec"),s.__dict__)
WRITTEN=0

def put(path,value,raw=False):
    global WRITTEN
    b=value if raw else s.encode(value);WRITTEN+=len(b)
    assert WRITTEN<=2*1024**2,"cumulative generated write ceiling"
    path.write_bytes(b);return s.pin(b)

class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="subset-generated-",dir=HERE/"controls")
        self.root=Path(self.tmp.name);self.pred=self.root/"predictions";self.pred.mkdir()
        self.protocol=self.root/"protocol.json"
        self.pp=put(self.protocol,{"schema":"erp-exploratory-image-pilot-protocol/v1","cases":[{"trial_id":x} for x in s.IDS]})
        self.source=self.root/"classify.py";self.sp=put(self.source,b"# generated fixed programme\n",True)
        self.files={}
        for arm in s.ARMS:
            rows=[{"trial_id":i,"status":"ok","target_probability":.5,"first_response":json.dumps({"trial_id":i,"target_probability":.5})} for i in s.IDS]
            self.files[arm]={"schema":"erp-exploratory-predictions/v1","arm":arm,"protocol_sha256":self.pp["sha256"],"records":rows}
        self.commit=self.root/"commit.json";self.freeze()
        self.labels={i:int(k>=16) for k,i in enumerate(s.IDS)}
    def tearDown(self): self.tmp.cleanup()
    def freeze(self):
        pins={a:put(self.pred/(a+".json"),self.files[a]) for a in s.ARMS}
        self.cp=put(self.commit,{"schema":"erp-exploratory-prediction-commit/v1","protocol":self.pp,
            "prediction_directory":str(self.pred),"arms":pins,"programme_source":{"path":str(self.source),**self.sp}})
    def args(self):return (self.protocol,self.pp["sha256"],self.commit,self.cp["sha256"])
    def run_score(self): return s.evaluate(*self.args(),gold_loader=lambda _:self.labels)
    def reject_without_gold(self):
        calls=[]
        with self.assertRaises(ValueError):s.evaluate(*self.args(),gold_loader=lambda _:(calls.append(True) or self.labels))
        self.assertEqual(calls,[])
    def set_prob(self,arm,alias,p,status="ok"):
        row=self.files[arm]["records"][s.IDS.index(alias)];row.update(status=status,target_probability=p,
          first_response=json.dumps({"trial_id":alias,"target_probability":p}) if status=="ok" else status)
    def test_01_complete_pair_gate_then_score(self):
        calls=[]
        result=s.evaluate(*self.args(),gold_loader=lambda p:(calls.append(p) or self.labels))
        self.assertEqual(len(calls),1);self.assertEqual(result["arms"]["direct"]["balanced_accuracy"],.5)
        self.assertTrue(result["gold_opened_after_both_admitted"])
        self.assertEqual(result["uncertainty"]["primary_direct_minus_programme_BA"],[0.,0.])
    def test_02_missing_extra_duplicate_ids_no_gold(self):
        for kind in ("missing","extra","duplicate"):
            original=list(self.files["direct"]["records"])
            if kind=="missing":self.files["direct"]["records"]=original[:-1]
            elif kind=="extra":self.files["direct"]["records"]=original+[dict(original[0],trial_id="case-33")]
            else:self.files["direct"]["records"]=original[:-1]+[original[0]]
            self.freeze();self.reject_without_gold();self.files["direct"]["records"]=original
    def test_03_exact_two_files_no_gold(self):
        put(self.pred/"extra.json",{});self.reject_without_gold();(self.pred/"extra.json").unlink()
        (self.pred/"direct.json").unlink()
        self.reject_without_gold()
    def test_04_hash_mutation_no_gold(self):
        with (self.pred/"programme.json").open("ab") as f:f.write(b" ")
        self.reject_without_gold()
    def test_05_duplicate_json_fields_and_nonfinite(self):
        with self.assertRaises(ValueError):s.decode(b'{"a":1,"a":2}')
        for value in (float("nan"),float("inf"),True,-.01,1.01):
            self.assertFalse(s.finite_probability(value))
        for raw in (b'{"x":NaN}',b'{"x":Infinity}'):
            with self.assertRaises(ValueError):s.decode(raw)
    def test_06_response_identity_probability_must_match(self):
        for raw in ('{"trial_id":"case-02","target_probability":0.5}',
                    '{"trial_id":"case-01","target_probability":0.2}',
                    '{"trial_id":"case-01","target_probability":true}',
                    '{"trial_id":"case-01","target_probability":0.5,"why":"x"}'):
            self.files["direct"]["records"][0]["first_response"]=raw
            self.freeze();self.reject_without_gold()
    def test_07_failure_counts_incorrect_not_omitted(self):
        for a in s.ARMS:
            for i in s.IDS:self.set_prob(a,i,float(self.labels[i]))
        for status,i in zip(s.STATUSES[1:],s.IDS[:4]):self.set_prob("direct",i,None,status)
        self.freeze();r=self.run_score()
        self.assertEqual(r["arms"]["direct"]["coverage"],28/32)
        self.assertEqual(r["arms"]["direct"]["balanced_accuracy"],.875)
        self.assertEqual(r["primary_direct_minus_programme_BA"],-.125)
        self.assertEqual(len(r["arms"]["direct"]["failure_aliases"]),4)
    def test_08_class_weighting_not_accuracy(self):
        self.labels={i:int(k>=28) for k,i in enumerate(s.IDS)}
        for a in s.ARMS:
            for i in s.IDS:self.set_prob(a,i,0.)
        self.freeze();r=self.run_score();self.assertEqual(r["class_support"],{"standard":28,"target":4})
        self.assertEqual(r["arms"]["direct"]["balanced_accuracy"],.5)
    def test_09_paired_draw_reuse(self):
        for a in s.ARMS:
            for k,i in enumerate(s.IDS):self.set_prob(a,i,float(k%3==0))
        self.freeze();r=self.run_score()
        self.assertEqual(r["uncertainty"]["primary_direct_minus_programme_BA"],[0.,0.])
        self.assertEqual(r["uncertainty"]["secondary_unadjusted_absolute_arm_BA"]["direct"],r["uncertainty"]["secondary_unadjusted_absolute_arm_BA"]["programme"])
    def test_10_orientation_threshold_and_stratification(self):
        for i in s.IDS:
            self.set_prob("direct",i,.5 if self.labels[i] else .499999)
            self.set_prob("programme",i,.499999 if self.labels[i] else .5)
        self.freeze();r=self.run_score();self.assertEqual(r["primary_direct_minus_programme_BA"],1.)
        self.assertEqual(r["uncertainty"]["primary_direct_minus_programme_BA"],[1.,1.])
    def test_11_seed_quantile_count_and_determinism(self):
        import numpy as np
        for k,i in enumerate(s.IDS):self.set_prob("direct",i,float(k%5==0))
        self.freeze();seen=[];real=np.quantile
        def observe(values,q,method):
            seen.append((len(values),q,method));return real(values,q,method=method)
        with patch.object(np,"quantile",side_effect=observe):r=self.run_score()
        self.assertEqual(seen,[(10000,[.025,.975],"linear")]*3)
        self.assertEqual(r,self.run_score());self.assertEqual(r["uncertainty"]["seed"],20261122)
    def test_12_one_class_and_invalid_gold_visible(self):
        self.labels={i:0 for i in s.IDS};r=self.run_score()
        self.assertIsNone(r["primary_direct_minus_programme_BA"]);self.assertIsNone(r["uncertainty"])
        self.assertEqual(r["status"],"one_class_balanced_accuracy_unavailable")
        self.labels[s.IDS[0]]=True
        with self.assertRaises(ValueError):self.run_score()
    def test_13_protocol_commit_and_source_auth_before_gold(self):
        self.cp["sha256"]="0"*64;self.reject_without_gold();self.freeze()
        put(self.source,b"# changed\n",True);self.reject_without_gold()
    def test_14_no_private_rows_or_id_joins_in_result(self):
        r=self.run_score();text=json.dumps(r)
        for forbidden in ("PARTICIPANT_JOIN","source_person","sub-","source_event_code","source_anchor","private/people"):
            self.assertNotIn(forbidden,text)
        self.assertNotIn("labels",r)
    def test_15_symlink_and_changed_read_close_fd(self):
        p=self.root/"link";p.symlink_to(self.protocol)
        with self.assertRaises(ValueError):s.read(p)
        opened=[];real=os.fdopen
        def tracking(*a,**kw):f=real(*a,**kw);opened.append(f);return f
        with patch.object(os,"fdopen",side_effect=tracking):
            with self.assertRaises(ValueError):s.read(self.protocol,{"bytes":1,"sha256":"0"*64})
        self.assertTrue(all(f.closed for f in opened))
    def test_16_output_create_only_and_interrupted_fsync(self):
        p=self.root/"out.json";s.write_new(p,{"a":1})
        with self.assertRaises(FileExistsError):s.write_new(p,{"a":2})
        self.assertEqual(json.loads(p.read_bytes()),{"a":1})
        opened=[];real=os.fdopen
        def tracking(*a,**kw):f=real(*a,**kw);opened.append(f);return f
        with patch.object(os,"fdopen",side_effect=tracking),patch.object(os,"fsync",side_effect=OSError("generated interruption")):
            with self.assertRaises(OSError):s.write_new(self.root/"interrupted.json",{"a":1})
        self.assertTrue(all(f.closed for f in opened))

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"generated_only":True,"methods":result.testsRun,"fixture_cumulative_written_bytes":WRITTEN,
      "extra_direct_fixture_write_upper":4096,"limit":2*1024**2,"original_gold_opened":False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
