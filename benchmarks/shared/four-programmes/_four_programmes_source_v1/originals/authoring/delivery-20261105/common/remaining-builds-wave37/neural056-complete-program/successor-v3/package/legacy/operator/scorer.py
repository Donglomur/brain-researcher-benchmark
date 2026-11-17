"""Continuous full-panel encoding scorer; never fits or executes candidate code."""
import argparse,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,ARMS,SHAPE,need,digest,canonical,validate_design
from array_io import capture,metadata,identity,arrays,fresh_output

def correlation(y,p):
 y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
 need(y.shape==p.shape==SHAPE and np.isfinite(y).all() and np.isfinite(p).all(),'Finite full image/channel/time support')
 # Scale before centering to prevent avoidable float64 overflow; Pearson invariant.
 ys=np.max(np.abs(y),axis=0);ps=np.max(np.abs(p),axis=0);ys[ys==0]=1;ps[ps==0]=1
 a=y/ys;b=p/ps;a-=a.mean(axis=0);b-=b.mean(axis=0)
 sy=np.sum(a*a,axis=0);sp=np.sum(b*b,axis=0);valid=sy>0;vary=sp>0;r=np.zeros((17,100))
 both=valid&vary;r[both]=np.sum(a*b,axis=0)[both]/np.sqrt(sy[both]*sp[both]);r=np.clip(r,-1,1)
 need(np.isfinite(r).all(),'Representable correlation')
 raw=[[None if not valid[c,t] or not vary[c,t] else float(r[c,t]) for t in range(100)] for c in range(17)]
 score=[[None if not valid[c,t] else float(r[c,t]) for t in range(100)] for c in range(17)]
 return {'pearson':raw,'scoring_correlation':score,'constant_target_cells':int((~valid).sum()),'constant_prediction_cells':int((~vary).sum()),'mean_all1700':float(r.mean()) if valid.all() else None}

def split_half(odd,even):
 r=correlation(odd,even)
 return {'pearson':r['pearson'],'constant_odd_cells':r['constant_target_cells'],'constant_even_cells':r['constant_prediction_cells'],'mean_all1700':None if r['constant_target_cells'] or r['constant_prediction_cells'] else r['mean_all1700']}

def admit(submission,d):
 validate_design(d);s=Path(submission);need(s.is_dir() and not s.is_symlink(),'Ordinary submission directory');m=metadata(s/'predictions.json');need(set(m)=={'schema','design_sha256','query_image_ids','entries'} and m['schema']=='neural056_predictions_v1' and m['design_sha256']==digest(d) and m['query_image_ids']==d['query_image_ids'],'Exact bound ordered submission')
 need(type(m['entries'])is list and len(m['entries'])==30,'All30 person-arm blocks');out={};names={'predictions.json'}
 for row in m['entries']:
  need(type(row)is dict and set(row)=={'person','arm','file','bytes','sha256'},'Exact block keys');key=(row['person'],row['arm']);need(key[0]in PEOPLE and key[1]in ARMS and key not in out,'Distinct prescribed block')
  name=key[0]+'__'+key[1]+'.npz';need(row['file']==name and type(row['bytes'])is int,'Canonical path and bytes');b=capture(s/name,4_000_000);need(identity(b)=={'bytes':row['bytes'],'sha256':row['sha256']},'Captured identity')
  p=arrays(b,('prediction',),4_000_000)['prediction'];need(p.shape==SHAPE and p.dtype.kind=='f' and p.dtype.itemsize in(4,8) and np.isfinite(p).all(),'All200images/17channels/100times finite');out[key]=p.astype(np.float64);names.add(name)
 need({x.name for x in s.iterdir()}==names,'No extra output');return out

def grade(submission,d,target):
 pred=admit(submission,d);results={a:{} for a in ARMS};reliability={}
 for person in PEOPLE:
  v=target(person);need(set(v)=={'mean','half_odd','half_even'},'Complete private mean and descriptive reliability arrays')
  for name in v:need(np.asarray(v[name]).shape==SHAPE and np.isfinite(v[name]).all(),'Private full support')
  for a in ARMS:results[a][person]=correlation(v['mean'],pred[(person,a)])
  reliability[person]=split_half(v['half_odd'],v['half_even'])
 def avg(vals):return float(np.mean(vals)) if all(x is not None for x in vals) else None
 means={a:avg([results[a][p]['mean_all1700'] for p in PEOPLE]) for a in ARMS}
 effects={}
 for baseline in ['low_level','response_permuted']:
  vals=[None if results['representation'][p]['mean_all1700'] is None or results[baseline][p]['mean_all1700'] is None else results['representation'][p]['mean_all1700']-results[baseline][p]['mean_all1700'] for p in PEOPLE]
  effects['representation_minus_'+baseline]={'by_person':dict(zip(PEOPLE,vals)),'mean':avg(vals)}
 return {'schema':'neural056_grade_v1','design_sha256':digest(d),'per_person':results,'primary_equal_person_mean':means,'paired_effects':effects,'split_half_reliability':reliability,'reliability_correction_applied':False,'binary_success':None,'population_scope':'ten public people conditional on200shared testimages','method_execution_verified':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--operator',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();fresh_output(a.output);d=metadata(a.operator/'design.json');bindings=metadata(a.operator/'TARGETS.json');need(bindings['design_sha256']==digest(d),'Private design join')
 def target(person):
  r=bindings['targets'][person];b=capture(a.operator/'targets'/f'{person}.npz',10_000_000);need(identity(b)==r,'Exact private target');return arrays(b,('mean','half_odd','half_even'),10_000_000)
 a.output.write_bytes(canonical(grade(a.submission,d,target)))
if __name__=='__main__':main()
