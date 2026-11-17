"""Complete 96-job/192-phase plan. Host provenance is never a public case."""
import hashlib
import io_contract as io
from analysis import panel,ARMS
from scientific_contract import profile_sha256
from prepare_case import make_cases

def job_plan(panel_raw):
 p=io.strict(panel_raw);records=panel(p)
 people=sorted({r['patient_id']for r in records.values()if r['cohort']=='CHB'})
 jobs=[]
 for arm in ARMS:
  for held in people+[None]:
   ids=sorted(rid for rid,r in records.items()if(r['cohort']=='Siena'if held is None else r['cohort']=='CHB'and r['patient_id']==held))
   jobs.append({'job_id':arm+':'+(held if held is not None else'full-target'),'arm':arm,'held_source_patient':held,'training_people':23 if held is None else 22,'query_recording_ids':ids})
 io.need(len(jobs)==96 and len({r['job_id']for r in jobs})==96,'all four arms and 24 logical jobs per arm')
 return {'schema':'neural012_job_plan_v3','panel_sha256':hashlib.sha256(panel_raw).hexdigest(),'scientific_profile_sha256':profile_sha256(p['scientific_profile']),'phases':['fit','predict'],'planned_invocations':192,'jobs':jobs,'execution_verified':False}

def prepare_job(panel_raw,source_targets_raw,plan,job_id):
 io.need(plan==job_plan(panel_raw),'same original complete panel/plan')
 matches=[x for x in plan['jobs']if x['job_id']==job_id];io.need(len(matches)==1,'one original logical job')
 job=matches[0];fit,predict=make_cases(panel_raw,source_targets_raw,job['arm'],job['held_source_patient'])
 io.need(sorted(r['recording_id']for r in predict['query'])==job['query_recording_ids'],'complete query inverse')
 raws={'fit':io.encoded(fit),'predict':io.encoded(predict)}
 # This combined provenance is host-only. Fit sees no query identities or fields.
 return raws,{'schema':'neural012_case_origin_v3','job':job,'panel_sha256':plan['panel_sha256'],'scientific_profile_sha256':plan['scientific_profile_sha256'],
 'source_targets_sha256':hashlib.sha256(source_targets_raw).hexdigest(),'fit_case_sha256':hashlib.sha256(raws['fit']).hexdigest(),
 'predict_case_sha256':hashlib.sha256(raws['predict']).hexdigest(),'fit_use_verified':False}
