"""Local artifact grader. Does not execute candidate code or provide isolation.

Candidate report admission is complete before numeric packet loading/reference
analysis. Reference computation happens only when an operator later invokes it.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
from interface import Invalid,capture_regular,decode_json,write_json_fresh
ROOT=Path(__file__).resolve().parents[1]
DESIGN_SHA='3e4e7fec421ab57c61e19b66859f0434b314357de5c44dcf2957f6a5057108ec'
METHODS=('macro_primary','unweighted_pooled','reliability_weighted_pooled','reliability_adjustment')
METRICS=('animacy_given_size','size_given_animacy','joint')
def mean_finite(values):
 if not values:return None
 largest=max(values)
 if not math.isfinite(largest):return None
 return largest*(math.fsum(x/largest for x in values)/len(values))if largest else 0.0
def compare(candidate,expected):
 """Continuous errors plus exact support; never a biological effect threshold."""
 mismatches=[];numeric_errors=[];numeric_bad=0;exact_bad=0;numeric_slots=0
 def note(path,kind,a,b):
  if len(mismatches)<100:mismatches.append({'path':path,'kind':kind,'submitted':a,'expected':b})
 def walk(a,b,path):
  nonlocal numeric_bad,exact_bad,numeric_slots
  if type(b)is dict:
   if type(a)is not dict or set(a)!=set(b):exact_bad+=1;note(path,'keys',list(a)if isinstance(a,dict)else type(a).__name__,list(b));return
   for k in b:walk(a[k],b[k],path+'/'+k)
  elif type(b)is list:
   if type(a)is not list or len(a)!=len(b):exact_bad+=1;note(path,'length',len(a)if isinstance(a,list)else None,len(b));return
   for i,(x,y)in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
  elif type(b)is float:
   numeric_slots+=1
   if type(a)not in(int,float)or not math.isfinite(a):exact_bad+=1;note(path,'availability_or_type',a,b);return
   err=abs(a-b);numeric_errors.append(err)
   if not math.isclose(a,b,abs_tol=1e-8,rel_tol=1e-6):numeric_bad+=1;note(path,'numeric',a,b)
  elif type(a)is not type(b)or a!=b:exact_bad+=1;note(path,'support_identity_or_status',a,b)
 walk(candidate,expected,'/analysis')
 primary=[];primary_available=True;primary_support_matches=True
 try:
  for a,b in zip(candidate['participants'],expected['participants']):
   if any(a.get(k)!=b.get(k)for k in('subject_id','rows','voxel_support','roi_overlap_voxels')):primary_support_matches=False
   for roi in('V1','IT'):
    for metric in METRICS:
     x=a['roi_metrics']['macro_primary'][roi][metric];y=b['roi_metrics']['macro_primary'][roi][metric]
     if x['status']!='defined' or y['status']!='defined' or type(x['value'])not in(int,float)or type(y['value'])not in(int,float)or not math.isfinite(x['value'])or not math.isfinite(y['value']):primary_available=False
     else:primary.append(abs(x['value']-y['value']))
 except(KeyError,TypeError,IndexError):primary_available=False
 # The primary requires its own cohort/voxel/status support. Secondary
 # discrepancies remain visible and prevent full reconstruction, not this MAE.
 primary_ok=primary_available and len(primary)==18 and primary_support_matches
 primary_error=mean_finite(primary)if primary_ok else None
 return {'status':'scored','primary_metric':'equal_weight_18_participant_roi_endpoint_absolute_error','primary_error':primary_error,'primary_defined':primary_error is not None,'primary_support_matches':primary_support_matches,'primary_unavailable_reason':None if primary_error is not None else 'required_support_undefined_or_mismatched_or_unrepresentable','numeric_report_fields':numeric_slots,'numeric_fields_outside_tolerance':numeric_bad,'exact_disposition_mismatches':exact_bad,'all_numeric_mean_absolute_error':mean_finite(numeric_errors),'full_reconstruction':numeric_bad==0 and exact_bad==0,'tolerance':{'absolute':1e-8,'relative':1e-6,'purpose':'numerical reproduction, not scientific effect criterion'},'discrepancies_first100':mismatches,'scientific_claim':'protocol-defined reconstruction only; no SOTA, causal or full-paper claim'}
def grade_submission(submission,root=ROOT):
 # DESIGN contains source IDs/independent labels only, no neural observations.
 design_body=capture_regular(root/'private/DESIGN.json',cap=1000000)
 if hashlib.sha256(design_body).hexdigest()!=DESIGN_SHA:raise RuntimeError('operator DESIGN pin changed')
 design=decode_json(design_body,cap=1000000)
 from report_contract import validate_report
 try:
  body=capture_regular(submission,cap=4000000);submitted=decode_json(body,cap=4000000);validate_report(submitted,design)
 except Invalid as e:return {'status':'invalid_submission','reason':str(e),'primary_error':None,'full_reconstruction':False}
 # Nothing below runs for a malformed, incomplete or wrong scientific schema.
 from data_io import load_packet
 try:subjects,features,manifest_sha=load_packet(root,submitted_manifest_sha256=submitted['input_manifest_sha256'])
 except Invalid as e:return {'status':'invalid_submission','reason':str(e),'primary_error':None,'full_reconstruction':False}
 from encoding_core import analyze
 expected=analyze(subjects,features,draws=1000,strict=True)
 result=compare(submitted['analysis'],expected)
 result.update(task_id='NEURAL-052',input_manifest_sha256=manifest_sha,submission_sha256=hashlib.sha256(body).hexdigest())
 return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--submission',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 if args.output.exists()or args.output.is_symlink():raise SystemExit('fresh output required')
 try:r=grade_submission(args.submission)
 except Exception as e:r={'status':'operator_error','reason':type(e).__name__+': '+str(e),'primary_error':None,'full_reconstruction':False}
 write_json_fresh(args.output,r,cap=262144)
 print(json.dumps({'status':r['status'],'output':str(args.output)}));return 0 if r['status']=='scored'else 2
if __name__=='__main__':sys.exit(main())
