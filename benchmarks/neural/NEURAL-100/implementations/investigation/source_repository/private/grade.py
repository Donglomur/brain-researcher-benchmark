"""Strict artifact admission followed by future independent source recomputation."""
import argparse,hashlib,json,math
from pathlib import Path
from artifact_io import Invalid,capture_regular,decode_json,read_json
from report_contract import admit,project,CONDITIONS,AREAS

def comparable(v):
 return {'recordings':{r['recording_id']:{k:r[k]for k in('participant_id','area','conditions')}for r in v['recordings']},'areas':v['areas']}
def compare(candidate,expected):
 errors=[];mismatches=[];nulls=0;equal_support=0
 def walk(a,b,path):
  nonlocal nulls,equal_support
  if isinstance(b,dict):
   for k in b:walk(a[k],b[k],path+'/'+k)
  elif isinstance(b,list):
   if not isinstance(a,list)or len(a)!=len(b):mismatches.append(path)
   else:
    for i,(x,y)in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
  elif b is None:
   if a is None:nulls+=1
   else:mismatches.append(path)
  elif type(b)in(int,float) and path.split('/')[-1]not in('participants','defined_participants','defined_draws'):
   if type(a)not in(int,float):mismatches.append(path)
   else:errors.append((path,abs(a-b)))
  elif a!=b:mismatches.append(path)
  else:equal_support+=1
 walk(comparable(candidate),comparable(expected),'')
 primary=[];primary_dispositions=True
 for area in AREAS:
  a=candidate['areas']['primary'][area];b=expected['areas']['primary'][area]
  if a['participants']!=b['participants']or a['defined_participants']!=b['defined_participants']:primary_dispositions=False
  if b['full_mean_ms']is None:
   if a['full_mean_ms']is not None:primary_dispositions=False
  elif a['full_mean_ms']is None:primary_dispositions=False
  else:primary.append(abs(a['full_mean_ms']-b['full_mean_ms']))
 return {'status':'compared','primary_mae_ms':math.fsum(primary)/len(primary)if primary and primary_dispositions else None,
         'primary_numeric_reference_fields':sum(expected['areas']['primary'][area]['full_mean_ms']is not None for area in AREAS),'primary_numeric_fields_compared':len(primary),'primary_support_and_null_dispositions_match':primary_dispositions,
         'all_numeric_mae_ms':math.fsum(v for p,v in errors)/len(errors)if errors else None,
         'maximum_numeric_error_ms':max((v for p,v in errors),default=None),'numeric_fields_compared':len(errors),
         'matching_null_fields':nulls,'matching_status_or_support_fields':equal_support,'disposition_or_support_mismatches':mismatches,
         'mismatches_are_not_dropped_from_claim':True,'scientific_success_or_SOTA_claim':False,'empirical_input_use_established':False,
         'note':'Continuous reconstruction errors and exact dispositions only; no pass threshold or claim that a null full-cohort endpoint is a measured zero.'}
def evaluate(value,roster,reference_loader):
 admit(value,roster)
 expected=project(reference_loader());admit(expected,roster)
 return compare(value,expected)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--submission',type=Path,required=True);p.add_argument('--packet',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists()or a.output.is_symlink():p.error('fresh output required')
 here=Path(__file__).resolve().parent
 try:
  try:binding=read_json(here/'PACKET_BINDING.json');roster=binding['roster']
  except (Invalid,KeyError)as e:raise ValueError('operator packet binding')from e
  value=read_json(a.submission)
  def reference():
   from data_adapter import load_manifest,records
   from analysis_core import analyze
   try:
    m=load_manifest(a.packet/'PREPARED.json',binding['manifest_sha256'])
    return analyze(records(a.packet,m),roster)
   except Invalid as e:raise ValueError('operator packet read')from e
  result=evaluate(value,roster,reference);code=0
 except Invalid as e:result={'status':'invalid_submission','score':None,'reason':str(e)};code=2
 except (OSError,ValueError,TypeError,KeyError,OverflowError)as e:result={'status':'operator_error','score':None,'reason':str(e)};code=3
 with a.output.open('x')as f:json.dump(result,f,allow_nan=False,indent=2)
 return code
if __name__=='__main__':raise SystemExit(main())
