"""Full32 observed-data contrast scorer; private binding follows complete public admission."""
import argparse,json,math
from fractions import Fraction
from pathlib import Path
from io_contract import capture,decode,frozen_roster
from packet_io import index,get_json,get_npz,validate_public
from state_core import AREAS,mean_absolute_error,aggregate_session_errors,_scalar
from analysis import PAIR_KEYS,reconstruct

def admit_candidate(path,session_ids):
 d=decode(capture(path,1000000))
 if set(d)!={'schema','task_id','sessions'} or d['schema']!='neuropixels_state_submission_v1' or d['task_id']!='NEURAL-092' or not isinstance(d['sessions'],dict) or set(d['sessions'])!=set(session_ids):raise ValueError('exact complete32 state submission')
 for sid,value in d['sessions'].items():
  if not isinstance(value,dict) or set(value)!={'running','pupil'}:raise ValueError('both separate state modes required')
  for mode,v in value.items():
   if not isinstance(v,dict) or set(v)!={'areas','matched'} or not isinstance(v['areas'],dict) or set(v['areas'])!=set(AREAS) or not isinstance(v['matched'],dict) or set(v['matched'])!=set(PAIR_KEYS):raise ValueError('full area and pairwise sensitivity axes required')
   for x in list(v['areas'].values())+list(v['matched'].values()):
    if x is not None and (type(x) not in (float,int) or not math.isfinite(float(x))):raise ValueError('finite signed effects or explicit null')
 return d['sessions']

def evaluate(candidate,metadata,gold_loader):
 errors={'running':{},'pupil':{}};sessions={}
 for sid,m in metadata.items():
  truth=reconstruct(m,gold_loader(sid));result={}
  for mode,v in truth.items():
   error=mean_absolute_error(candidate[sid][mode]['areas'],v['areas']);errors[mode][sid]=error;matched_errors={}
   for key,expected in v['matched'].items():
    x=candidate[sid][mode]['matched'][key]
    if expected is None:
     if x is not None:raise ValueError('unsupported matched comparison requires null')
     matched_errors[key]=_scalar(None,'undefined_matched_support')
    else:
     if x is None:raise ValueError('defined matched comparison missing')
     matched_errors[key]=_scalar(abs(Fraction.from_float(float(x))-expected))
   result[mode]={'area_error':error.report(),'area_support':v['areas'].report(),'pairing':v['pairing'].report(),'matched_error':matched_errors,'matched_support':v['matched_support']}
  sessions[sid]=result
 aggregate={mode:aggregate_session_errors(err,{sid:m['mouse_id'] for sid,m in metadata.items()}) for mode,err in errors.items()}
 return {'admitted':True,'task_id':'NEURAL-092','primary_running_reconstruction_error':aggregate['running'],'separate_pupil_reconstruction_error':aggregate['pupil'],'sessions':sessions,'explanatory_gain':None,'explanatory_gain_qualified':False,'causal_effect_identified':False,'scientific_or_runtime_qualification':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--roster',required=True);p.add_argument('--index',required=True);p.add_argument('--index-sha256',required=True);p.add_argument('--packet-root',required=True);p.add_argument('--submission',required=True);a=p.parse_args()
 try:
  roster,_=frozen_roster(a.roster);idx=index(a.index,a.index_sha256,'NEURAL-092');entries={x['session_id']:x for x in idx['sessions']}
  if len(entries)!=len(idx['sessions']) or set(entries)!={x['session_id'] for x in roster['sessions']}:raise ValueError('frozen full32 panel')
  root=Path(a.packet_root);meta={r['session_id']:validate_public(get_json(root,entries[r['session_id']]['metadata']),r['session_id'],r['donor_id']) for r in roster['sessions']}
  if any(m['task_id']!='NEURAL-092' for m in meta.values()):raise ValueError('session task mismatch')
  candidate=admit_candidate(a.submission,meta)
  result=evaluate(candidate,meta,lambda sid:get_npz(root,entries[sid]['counts']['QUERY'],{'counts'})['counts'])
 except (ValueError,TypeError,KeyError,OSError,OverflowError,RuntimeError) as e:result={'admitted':False,'error':type(e).__name__+': '+str(e)}
 print(json.dumps(result,allow_nan=False))
 if not result['admitted']:raise SystemExit(1)
if __name__=='__main__':main()
