"""Prepare exactly ONE outer-person candidate context. Collection stays private."""
import argparse,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,need,canonical,digest,validate_design
from array_io import capture,metadata,identity,arrays,fresh_output
from source_bindings import check_staged_people

def training_people(held):
 need(held in PEOPLE,'One held person');return [p for p in PEOPLE if p!=held]
def stage(panel,held,output):
 fresh_output(output);panel=Path(panel);out=Path(output);d=validate_design(metadata(panel/'design.json'));people=check_staged_people(metadata(panel/'PEOPLE.json'));fm=metadata(panel/'FEATURES.json');roster=metadata(panel/'ROSTER.json',4_000_000);need(digest(roster)==d['roster_sha256'] and digest(fm)==d['feature_binding_sha256'] and digest(people)==d['coordinates']['source_binding_sha256'],'Panel joins')
 total=np.zeros((16540,17,100),dtype=np.float64)
 for person in training_people(held):
  b=capture(panel/'people'/person/'train.npz',230_000_000);need(identity(b)==people[person]['arrays']['train'],'Exact otherpersontrainingpin');v=arrays(b,('mean',),230_000_000)['mean'];need(v.shape==total.shape and v.dtype.kind=='f' and np.isfinite(v).all(),'Fulltrainingmean');total+=v/9
 need(np.isfinite(total).all(),'Finite otherpersonmean');out.mkdir();np.savez_compressed(out/'training_response.npz',mean=total);bindings={'training_response':identity((out/'training_response.npz').read_bytes())}
 for part in ['train','test']:
  b=capture(panel/'features'/(part+'.npz'),330_000_000);need(identity(b)==fm['arrays'][part],'Feature identity');(out/(part+'_features.npz')).write_bytes(b);bindings[part+'_features']=identity(b)
 # All development contexts must separately omit held inner-person responses;
 # this final refit view is NEVER an inner validation packet.
 (out/'case.json').write_bytes(canonical({'schema':'neural056_case_v1','held_person':held,'training_people':training_people(held),'design':d,'bindings':bindings,'development':'Final nine-person refit context only; no tuning/validation on this aggregated response','training_concept_ids':[x['concept_id'] for x in roster['train']]}))
 return {'held_person':held,'query_EEG_files':0,'held_person_training_EEG_files':0,'fit_or_score':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--panel',required=True);p.add_argument('--held-person',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(stage(a.panel,a.held_person,a.output))
