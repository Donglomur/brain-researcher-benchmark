"""Prepare disjoint phase views from one full host-only logical job."""
import argparse,hashlib
from pathlib import Path
import io_contract as io
from analysis import panel,interval_list,ARMS
from scientific_contract import profile_sha256
from case_contract import project_row,validate_case,validate_phase_pair

def make_cases(panel_raw,source_targets_raw,arm,held_source_patient=None):
 p=io.strict(panel_raw);records=panel(p);profile=profile_sha256(p['scientific_profile'])
 gold=io.strict(source_targets_raw);io.fields(gold,['panel_sha256','scientific_profile_sha256','records'])
 io.need(gold['panel_sha256']==hashlib.sha256(panel_raw).hexdigest()and gold['scientific_profile_sha256']==profile,'source target/panel/profile binding')
 source={rid:r for rid,r in records.items()if r['cohort']=='CHB'};labels={}
 io.need(type(gold['records'])is list and len(gold['records'])==686,'CHB labels only')
 for row in gold['records']:
  io.fields(row,['recording_id','events']);rid=row['recording_id']
  io.need(type(rid)is str and rid in source and rid not in labels,'no Siena labels in training source')
  labels[rid]=interval_list(row['events'],source[rid]['duration_seconds'])
 io.need(arm in ARMS and(held_source_patient is None or held_source_patient in{x['patient_id']for x in source.values()}),'known arm/source held person')
 train=[project_row(r,arm,labels[rid])for rid,r in sorted(source.items())if r['patient_id']!=held_source_patient]
 query=[project_row(r,arm)for rid,r in sorted(records.items())if(r['cohort']=='Siena'if held_source_patient is None else r['cohort']=='CHB'and r['patient_id']==held_source_patient)]
 common={'schema_version':3,'task_id':io.TASK,'arm':arm,'training_people':23 if held_source_patient is None else 22,'scientific_profile_sha256':profile,'supervisor_verified':False}
 fit=validate_case(dict(common,phase='fit',train=train),'fit')
 predict=validate_case(dict(common,phase='predict',query=query,fit_case_sha256=hashlib.sha256(io.encoded(fit)).hexdigest()),'predict')
 return validate_phase_pair(fit,predict)

def make_case(panel_raw,source_targets_raw,arm,phase,held_source_patient=None):
 io.need(phase in('fit','predict'),'explicit phase required')
 fit,predict=make_cases(panel_raw,source_targets_raw,arm,held_source_patient)
 return fit if phase=='fit'else predict

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['panel','source-targets','output']:p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--source-targets-sha256',required=True);p.add_argument('--arm',choices=ARMS,required=True)
 p.add_argument('--phase',choices=('fit','predict'),required=True);p.add_argument('--held-source-patient');a=p.parse_args()
 io.need(not a.output.exists()and not a.output.is_symlink(),'fresh output before private access')
 io.write(a.output,make_case(io.read(a.panel,3000000),io.read(a.source_targets,3000000,a.source_targets_sha256),a.arm,a.phase,a.held_source_patient))
