"""Source/authority controls; no observer, candidate or numeric operation invoked."""
import json,types,time,unittest
from pathlib import Path
HERE=Path(__file__).absolute().parent
SERIALIZED=0

def load(name,path,**kw):
 m=types.ModuleType(name);m.__file__=str(path);m.__dict__.update(kw);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
c=load('common',HERE/'program/common.py');policy=load('policy',HERE/'program/policy.py',c=c)
def encoded(v):
 global SERIALIZED
 b=c.encoded(v);SERIALIZED+=len(b)
 if SERIALIZED>1048576:raise ValueError('test serialization allocation')
 return b
class Tests(unittest.TestCase):
 def test_whole_source_closure(self):
  a=load('adapter',HERE/'adapter.py');captures=a.Captures(time.monotonic()+10)
  b=a.own_sources(captures,a.pin((HERE/'SOURCE_MANIFEST.json').read_bytes()));_,_,_,bodies,_=a.target(captures,b)
  self.assertEqual(set(bodies),a.CONTROLLER_NAMES);self.assertEqual(len(bodies),15)
  bad=dict(b);bad['source_dependencies']=list(reversed(b['source_dependencies']))
  with self.assertRaises(ValueError):a.target(captures,bad)
 def test_disabled_templates_and_complete_prerequisites(self):
  source=c.pin((HERE/'program/SOURCE_MANIFEST.json').read_bytes());s=json.loads((HERE/'SELECTION.template.json').read_bytes())
  with self.assertRaises(ValueError):policy.selection(s,source)
  plan=dict(contexts=54,query_count=21600,training_per_context=21200,files=216,public_bytes=18663400000,max_fold_bytes=345620000)
  s.update(execution_selected=True,other_future_bytes=0,plan=plan,limits=policy.limits(plan,900,120))
  policy.selection(s,source)
  docs={k:json.loads((HERE/file).read_bytes()) for k,file in [('input_review','INPUT_REVIEW.template.json'),('method_review','METHOD_REVIEW.template.json'),('runtime_review','CONTROLLER_RUNTIME.template.json'),('preparation','PREPARATION.template.json')]}
  for k,d in docs.items():
   s[k]={**s[k],'path':'/INVENTED_'+k}
   for field,value in list(d.items()):
    if value is False and field not in ('scientific_qualified','numeric_scoring_authorized','pins_alone_prove_original_authenticity','matlab_pipeline_parity_claimed','hashes_prove_chronology'):d[field]=True
  docs['input_review'].update(preparation=s['preparation'],plan=plan)
  docs['runtime_review']['profile']={k:s[k] for k in ('candidate_seconds','reference_seconds','memory_bytes','plan','limits')}
  binding=json.loads((HERE/'program/BINDING.json').read_bytes())
  def read(path,cap,pin):return encoded(docs[next(k for k in docs if path=='/INVENTED_'+k)])
  policy.reviews(s,source,binding,read)
  for key,field in [('method_review','no_target_person_calibration_or_query_batch_fitting'),('input_review','all54_training_and_query_partitions_verified'),('preparation','full_source_authenticity_admitted'),('runtime_review','fixed_reference_source_and_native_arithmetic_qualified')]:
   docs[key][field]=False
   with self.assertRaises(ValueError):policy.reviews(s,source,binding,read)
   docs[key][field]=True
if __name__=='__main__':
 r=unittest.main(exit=False);print(json.dumps(dict(canonical_serialization_bytes=SERIALIZED,fixture_file_writes=0,actual_native_or_scientific_execution=False)));raise SystemExit(not r.result.wasSuccessful())
