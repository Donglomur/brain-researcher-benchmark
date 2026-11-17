"""Full-cohort deterministic projection only; no fitted response model or scoring."""
import argparse,hashlib,io,json,os
from pathlib import Path
import numpy as np
from io_contract import capture,decode,frozen_roster,ROSTER_SHA256
from packet_io import write_json,describe,FILE_CAP
import nwb_input as native
from projection import FAMILIES,prediction_rows,state_rows,assign_states
TASK='NEURAL-092'

def same_identity(f,sid):
 obj=f['identifier'][()]
 if isinstance(obj,bytes):obj=obj.decode()
 if str(obj)!=sid:raise ValueError('NWB identifier differs from exact frozen session')

def build_one(path,record,row,task):
 desc={k:record[k] for k in ('bytes','sha256')}
 with native.opened(path,desc) as f:
  same_identity(f,row['session_id'])
  selected=native.select_units(f)
  units=selected['units']
  if not units:raise ValueError('required session has no eligible units; no replacement')
  invalid=native.invalid_intervals(f)
  families=FAMILIES if task=='NEURAL-091' else ('drifting_gratings',)
  stimuli={family:native.intervals(f,family) for family in families}
  rows,dis=(prediction_rows(stimuli,invalid['intervals']) if task=='NEURAL-091' else state_rows(stimuli,invalid['intervals']))
  # Metadata-only trial selection is final before any neural values are read.
  cov=native.state_covariates(f,[(r['onset']-.5,r['onset']) for r in rows])
  rows,state=assign_states(rows,cov['running'],cov['pupil'])
  all_counts=native.count_windows(f,units,[r['window'] for r in rows])
 exposure=.2 if task=='NEURAL-091' else 1.9
 fit=np.array([r['split']=='FIT' for r in rows]);nfit=int(fit.sum())
 # Python integer sums avoid overflow; strictly FIT counts and exposure only.
 baseline=[(sum(int(x) for x in all_counts[fit,j])+.5)/(nfit*exposure) for j in range(len(units))]
 if not np.isfinite(baseline).all() or min(baseline)<=0:raise ValueError('FIT baseline unsupported numeric range')
 unit_metadata=[{'unit_id':str(u['id']),'area':u['area'],'FITbaseline':baseline[j],'presence_ratio':u['presence_ratio'],'isi_violations':u['isi_violations'],'amplitude_cutoff':u['amplitude_cutoff']} for j,u in enumerate(units)]
 meta={'schema':'neuropixels_session_v1','task_id':task,'session_id':row['session_id'],'mouse_id':row['donor_id'],'unit_ids':[str(u['id']) for u in units],'areas':[u['area'] for u in units],'unit_metadata':unit_metadata,'rows':rows,'baseline_rates':baseline,'exposure_seconds':exposure,'state_policy':state,'support':{'unit_dispositions':selected['dispositions'],'all_unit_records':[{k:u[k] for k in ('id','area','quality','peak_channel_id','valid_data','presence_ratio','isi_violations','amplitude_cutoff') if k in u} for u in selected['all_units']],'trial_dispositions':dis,'invalid_time_status':invalid['status'],'invalid_rows':invalid['rows'],'behavior':cov['support'],'observation_coverage':'No authenticated per-unit observation intervals; rates condition on full unit observation over every retained window. Zero released counts are not verified silence.','source_preprocessing':'Published full-recording spike sorting and QC are transductive.'}}
 return meta,{name:np.asarray(all_counts[[r['split']==name for r in rows]],dtype=np.int64) for name in ('FIT','VALIDATION','QUERY')}

def main():
 p=argparse.ArgumentParser();p.add_argument('--roster',required=True);p.add_argument('--raw-binding',required=True);p.add_argument('--raw-binding-sha256',required=True);p.add_argument('--raw-root',required=True);p.add_argument('--output',required=True);p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
 roster,_=frozen_roster(a.roster);raw=capture(a.raw_binding,1000000)
 if hashlib.sha256(raw).hexdigest()!=a.raw_binding_sha256:raise ValueError('operator-selected complete raw binding pin')
 binding=decode(raw)
 if binding['schema']!='allen32_raw_binding_v1' or binding['roster_sha256']!=ROSTER_SHA256 or binding['complete'] is not True:raise ValueError('incomplete source generation')
 records={x['session_id']:x for x in binding['files']}
 if len(records)!=len(binding['files']) or set(records)!={x['session_id'] for x in roster['sessions']}:raise ValueError('exact full32 source cohort required')
 for row in roster['sessions']:
  rec=records[row['session_id']]
  if rec['bytes']!=row['source']['bytes'] or rec['url']!=row['source']['url'] or rec['etag']!=row['source']['etag'] or rec['path']!=row['session_id']+'.nwb':raise ValueError('frozen source identity mismatch')
 dest=Path(a.output)
 if dest.exists() or dest.is_symlink():raise ValueError('fresh output only')
 if not 0<a.max_output_bytes<=16000000000:raise ValueError('positive cap at most16GB')
 dest.mkdir(parents=True);(dest/'public').mkdir();(dest/'private').mkdir();used=0;sessions=[]
 def put(path,body):
  nonlocal used
  if used+len(body)>a.max_output_bytes:raise ValueError('selected total retained output cap')
  with path.open('xb') as f:f.write(body)
  path.chmod(0o444);used+=len(body)
 def js(path,value):put(path,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
 for row in roster['sessions']:
  sid=row['session_id'];m,parts=build_one(Path(a.raw_root)/records[sid]['path'],records[sid],row,TASK)
  qpath=dest/'public'/(sid+'.json');js(qpath,m);entry={'session_id':sid,'mouse_id':row['donor_id'],'metadata':describe(qpath,dest),'counts':{}}
  for phase,arr in parts.items():
   store='private' if TASK=='NEURAL-091' and phase=='QUERY' else 'public';path=dest/store/(sid+'-'+phase+'.npz');buf=io.BytesIO();np.savez_compressed(buf,counts=arr);body=buf.getvalue()
   if len(body)>FILE_CAP or arr.nbytes>FILE_CAP:raise ValueError('per-session packet cap; no trimming')
   put(path,body);entry['counts'][phase]=describe(path,dest)
  sessions.append(entry)
 limits=['No scientific/model execution or runtime qualification implied by data projection.','Complete-window unit observation is an unverified source assumption.','Published sorting/QC/pupil filtering may use future/full-recording information.']
 index={'schema':'neuropixels_task_packet_v1','task_id':TASK,'roster_sha256':ROSTER_SHA256,'sessions':sessions,'limitations':limits};js(dest/'private'/'INDEX.json',index)
 public_sessions=[]
 for x in sessions:
  y=dict(x);y['counts']={k:v for k,v in x['counts'].items() if TASK=='NEURAL-092' or k!='QUERY'};public_sessions.append(y)
 js(dest/'public'/'INDEX.json',{**index,'sessions':public_sessions})
 receipt={'task_id':TASK,'complete':True,'sessions':32,'mice':32,'raw_binding_sha256':a.raw_binding_sha256,'packet_files_bytes_before_receipt':used,'models_fitted':0,'scores_computed':0}
 js(dest/'PREPARATION_RECEIPT.json',receipt)
 print(json.dumps({'complete':True,'retained_bytes':used,'sessions':32}))
if __name__=='__main__':main()
