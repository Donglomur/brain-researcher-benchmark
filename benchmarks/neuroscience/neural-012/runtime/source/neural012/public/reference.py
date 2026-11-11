"""Two-phase fixed reference: source-only fit then frozen-state offline prediction.

The caller, not this program, must establish isolation and original phase lineage.
"""
import hashlib,math
import io_contract as io
import control_recipe as c
from event_protocol import from_scores
from case_contract import validate_case,phase_rows,validate_fit_state,validate_fit_limits
RECIPE='neural012_fixed_reference_v1'

def feature_loader(case,physical_loader):
 arm=case['arm']
 def features(row):
  raw,rate,labels,common_reference_selected=physical_loader(row)
  x,fs=c.transform(raw,rate,labels,row['cohort'],arm,common_reference_selected)
  return c.feature(x,fs)
 return features

def fit(case,physical_loader,fit_state_limits):
 validate_case(case,'fit');validate_fit_limits(fit_state_limits)
 arm=case['arm'];n=case['training_people'];train=case['train']
 if arm=='timing':parameters={'minute_probabilities':[float(x)for x in c.timing_table(train,n)]}
 else:parameters={'threshold':float(c.fit_threshold(train,n,feature_loader(case,physical_loader)))}
 artifact={'schema_version':1,'task_id':io.TASK,'arm':arm,'fit_case_sha256':hashlib.sha256(io.encoded(case)).hexdigest(),
 'training_use_declaration':'fit_attempted','state':{'recipe':RECIPE,'training_people':n,'parameters':parameters}}
 return validate_reference_state(artifact,case['arm'],n,artifact['fit_case_sha256'],fit_state_limits)

def validate_reference_state(artifact,arm,people,fit_case_sha256,fit_state_limits):
 validate_fit_state(artifact,fit_case_sha256,arm,fit_state_limits)
 state=artifact['state'];io.fields(state,['recipe','training_people','parameters'])
 io.need(artifact['training_use_declaration']=='fit_attempted'and state['recipe']==RECIPE and type(state['training_people'])is int and state['training_people']==people,'exact fixed-reference fitted state')
 parameters=state['parameters']
 if arm=='timing':
  io.fields(parameters,['minute_probabilities']);table=parameters['minute_probabilities']
  io.need(type(table)is list and len(table)==60 and all(type(x)in(int,float)and 0<=x<=1 for x in table),'complete finite 60-bin timing table')
 else:
  io.fields(parameters,['threshold']);threshold=parameters['threshold']
  io.need(type(threshold)in(int,float)and math.isfinite(threshold),'finite fitted reference threshold')
 return artifact

def predict(case,artifact,physical_loader,fit_state_limits):
 validate_case(case,'predict');validate_fit_limits(fit_state_limits)
 arm=case['arm'];query=case['query'];n=case['training_people']
 validate_reference_state(artifact,arm,n,case['fit_case_sha256'],fit_state_limits)
 parameters=artifact['state']['parameters'];features=feature_loader(case,physical_loader);rows=[]
 for r in query:
  d=r['duration_seconds']
  scores=(features(r)>=parameters['threshold']).astype(float).tolist()if arm!='timing'else[float(parameters['minute_probabilities'][min(t//60,59)])for t in range(d)]
  c.need(len(scores)==d,'complete query stream')
  rows.append({'recording_id':r['recording_id'],'scores':scores,'events':from_scores(scores,d)})
 return {'schema_version':1,'task_id':io.TASK,'arm':arm,'records':rows}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['case','output']:p.add_argument('--'+k,type=Path,required=True)
 for k in ['signal-root','reference-binding','fit-state']:p.add_argument('--'+k,type=Path)
 p.add_argument('--reference-binding-sha256');p.add_argument('--fit-state-sha256')
 p.add_argument('--fit-state-limits',required=True,help='Closed runtime-selected JSON resource limits')
 a=p.parse_args();limits=validate_fit_limits(io.strict(a.fit_state_limits.encode('utf8')))
 io.need(not a.output.exists()and not a.output.is_symlink(),'fresh output before fit/query reads')
 case=validate_case(io.strict(io.read(a.case,10000000)))
 if case['phase']=='fit':
  io.need(a.fit_state is None and a.fit_state_sha256 is None,'fit cannot consume an earlier fitted state')
  artifact=None
 else:
  io.need(a.fit_state is not None and a.fit_state_sha256 is not None,'prediction requires exact captured fit artifact')
  artifact=validate_fit_state(io.strict(io.read(a.fit_state,limits['bytes'],a.fit_state_sha256)),case['fit_case_sha256'],case['arm'],limits)
 if case['arm']=='timing':
  io.need(a.signal_root is None and a.reference_binding is None and a.reference_binding_sha256 is None,'timing forbids signal/reference inputs')
  def forbidden_loader(row):raise RuntimeError('timing has no physical loader')
  loader=forbidden_loader
 else:
  io.need(a.signal_root is not None and a.reference_binding is not None and a.reference_binding_sha256 is not None,'signal arm requires selected physical inputs')
  from scientific_contract import validate_reference,profile_sha256
  from physical_io import load
  binding=validate_reference(io.strict(io.read(a.reference_binding,io.MAX_JSON,a.reference_binding_sha256)),phase_rows(case))
  io.need(profile_sha256(binding['scientific_profile'])==case['scientific_profile_sha256'],'phase scientific profile/reference binding')
  loader=lambda row:load(row,a.signal_root,binding)
 result=fit(case,loader,limits)if case['phase']=='fit'else predict(case,artifact,loader,limits)
 io.write(a.output,result)
