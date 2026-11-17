"""Concrete local raw-source adapters and source-owned clock/bin compiler.
All scientific imports occur inside future worker calls. BUILD ONLY never calls them.
No downloads, credential lookup, precomputed answer or callback provider is used.
"""
from pathlib import Path
from .domain import Refusal,MissingDefinition
from .full_plan import need

def ibl_local(definition):
 from one.api import ONE
 from brainbox.io.one import SessionLoader,SpikeSortingLoader
 from iblatlas.regions import BrainRegions
 import numpy as np
 one=ONE(cache_dir=definition['cache'],mode='local',silent=True)
 session=SessionLoader(one=one,eid=definition['session']);session.load_trials();session.load_wheel()
 trials=session.trials;times=[];clusters=[];unit_ids=[];regions=[];offset=0
 for probe in definition['probes']:
  loader=SpikeSortingLoader(one=one,eid=definition['session'],pname=probe['name'],pid=probe['pid'])
  spikes,units,channels=loader.load_spike_sorting()
  merged=loader.merge_clusters(spikes,units,channels).to_df()
  labels=BrainRegions().acronym2acronym(merged['acronym'].to_numpy(),mapping='Beryl')
  # Cumulative probe offsets and exact local cluster IDs; no hemisphere/probe alias.
  local={int(k):offset+i for i,k in enumerate(merged.index)}
  mapped=np.asarray([local[int(k)]for k in spikes['clusters']],dtype=np.int64)
  times.append(spikes['times']);clusters.append(mapped)
  unit_ids.extend([{'probe':probe['pid'],'cluster':int(k)}for k in merged.index]);regions.extend(labels.tolist());offset+=len(merged)
 result={'spike_times':np.concatenate(times),'spike_units':np.concatenate(clusters),'unit_ids':unit_ids,'unit_regions':regions,
 'trials':{k:trials[k].to_numpy()for k in trials.columns},'wheel':{'times':session.wheel['times'].to_numpy(),'values':np.abs(session.wheel['velocity'].to_numpy())},
 'clock':{'unit':'seconds','domain':'IBL synchronized session time','producer':'SpikeSortingLoader+SessionLoader'},'original_trial_ids':list(range(len(trials)))}
 camera=definition['camera']
 if camera is not None:
  session.load_motion_energy(views=[camera]);table=session.motion_energy[camera+'Camera']
  result['motion']={'times':table['times'].to_numpy(),'values':table['whiskerMotionEnergy'].to_numpy()}
 return result

def allen_nwb(definition):
 from pynwb import NWBHDF5IO
 import numpy as np
 # Selected source mappings are literal NWB interfaces, not arbitrary callables.
 with NWBHDF5IO(definition['path'],'r',load_namespaces=True)as handle:
  nwb=handle.read();units=nwb.units.to_dataframe();ids=list(units.index)
  spike_times=np.concatenate([units.loc[k,'spike_times']for k in ids])
  spike_units=np.concatenate([np.full(len(units.loc[k,'spike_times']),i,dtype=np.int64)for i,k in enumerate(ids)])
  table=nwb.intervals[definition['interval_table']].to_dataframe()
  result={'spike_times':spike_times,'spike_units':spike_units,'unit_ids':ids,
   'unit_regions':units[definition['region_column']].tolist(),'intervals':table,
   'clock':{'unit':'seconds','domain':'NWB session timestamps','producer':'NWBHDF5IO'},'original_trial_ids':list(table.index)}
  for key,location in definition['behavior_interfaces'].items():
   module,interface,series=location
   obj=nwb.processing[module][interface][series]
   result[key]={'times':np.asarray(obj.timestamps[:]),'values':np.asarray(obj.data[:])}
 return result

def rtt_hdf5(definition):
 import h5py,numpy as np
 with h5py.File(definition['path'],'r')as f:
  x=np.asarray(f[definition['spikes_key']]);y=np.asarray(f[definition['velocity_key']]);ids=np.asarray(f[definition['trial_id_key']]).tolist()
 need(x.shape==(1351,30,130)and y.shape==(1351,30,2),'original RTT1351/30/130/XY')
 return {'binned':x,'behavior':y,'original_trial_ids':ids,'unit_ids':list(range(130)),
 'unit_regions':['motor']*130,'clock':{'unit':'seconds','bin':.02,'domain':'Pei preprocessed original trial clock'}}

def read_local(definition):
 need(definition['native_source_version']is not None and definition['original_files'],'actual source/file inventory required')
 if definition['dataset']=='ibl':return ibl_local(definition)
 if definition['dataset']=='allen':return allen_nwb(definition)
 if definition['dataset']=='rtt':return rtt_hdf5(definition)
 raise Refusal('unknown native input family')

ALLEN_LICK_REGIONS=('DG','CA1','CA3','VISp','VISa','LP','TH')

def selected_units(raw,case):
 # STAR Methods: combine the recorded subset of seven named IBL-atlas regions.
 # Never include every recorded region or require all seven to be recorded.
 if case['dataset']=='allen'and case['target']=='lick':
  selected=[i for i,r in enumerate(raw['unit_regions'])if r in ALLEN_LICK_REGIONS]
 else:selected=[i for i,r in enumerate(raw['unit_regions'])if case['region']=='all'or r==case['region']]
 need(selected,'original regional units')
 return selected

def window_contract(case):
 # Bin count is method-owned, not inferred from the first observed onset.
 if case['dataset']=='ibl'and case['cohort']!='ibl_unaligned':
  return {'choice':(2.,.05,40),'prior':(.5,.05,10),
   'wheel-speed':(1.,.02,50),'whisker-motion-energy':(1.,.02,50)}[case['target']]
 if case['dataset']=='ibl':return 2.,.02,100
 if case['dataset']=='allen':return (1.,.01,100)if case['target']=='running-speed'else(.2,.01,20)
 raise Refusal('no interval contract for this family')

def intervals(raw,case,definition):
 import numpy as np
 target=case['target']
 if case['dataset']=='rtt':return None
 if case['dataset']=='ibl'and case['cohort']!='ibl_unaligned':
  event='firstMovement_times'if target in('wheel-speed','whisker-motion-energy')else'stimOn_times'
  left,right,binsize=({'choice':(-.5,1.5,.05),'prior':(-.6,-.1,.05),'wheel-speed':(0.,1.,.02),'whisker-motion-energy':(0.,1.,.02)})[target]
  onset=np.asarray(raw['trials'][event]);return np.c_[onset+left,onset+right],binsize
 # Every original external/continuous interval is selected explicitly. This
 # does not guess Allen's ambiguous 'around onset' or recording boundaries.
 clock=definition['intervals']
 need(clock['source']is not None and clock['unit']=='seconds','original interval source/clock')
 windows=np.asarray(clock['windows'],dtype=float);dt=clock['binsize']
 expected=.02 if case['dataset']=='ibl'else .01
 need(dt==expected and windows.ndim==2 and windows.shape[1]==2,'literal external bin clock')
 # Individual nonfinite or wrong-extent windows receive row dispositions below.
 return windows,dt

def window_metadata(windows):
 import math
 values=[];categories=[]
 for row in windows:
  pair=[];status=[]
  for v in row:
   value=float(v)
   if math.isfinite(value):pair.append(value);status.append('finite')
   else:
    pair.append(None);status.append('nan'if math.isnan(value)else'positive_infinity'if value>0 else'negative_infinity')
  values.append(pair);categories.append(status)
 return {'values':values,'endpoint_dispositions':categories}

def compile_case(raw,case,definition,prior=None):
 import numpy as np
 from scipy.interpolate import interp1d
 selected=selected_units(raw,case)
 if case['dataset']=='rtt':
  return {'x':raw['binned'][:,:,selected],'y':raw['behavior'].reshape(1351,60),'row_inverse':list(range(1351)),
   'trial_ids':raw['original_trial_ids'],'unit_ids':[raw['unit_ids'][i]for i in selected],'dispositions':[], 'clock':raw['clock']}
 windows,dt=intervals(raw,case,definition);duration,expected_dt,nb=window_contract(case)
 need(dt==expected_dt and len(windows)==len(raw['original_trial_ids']),'complete original row/clock inverse')
 xs=[];ys=[];kept=[];dispositions=[]
 spike_times=np.asarray(raw['spike_times']);spike_units=np.asarray(raw['spike_units'])
 target=case['target'];trials=raw.get('trials');source=raw.get('wheel'if target=='wheel-speed'else'motion'if target=='whisker-motion-energy'else'running')
 for row,(start,stop)in enumerate(windows):
  reasons=[]
  if not np.isfinite([start,stop]).all():reasons.append('nonfinite_interval')
  elif abs((stop-start)-duration)>1e-10:reasons.append('interval_extent')
  if trials is not None and case['cohort']!='ibl_unaligned':
   fields=('stimOn_times','choice','feedback_times','probabilityLeft','firstMovement_times','feedbackType')
   if any(not np.isfinite(trials[k][row])for k in fields):reasons.append('missing_required_trial_field')
   rt=trials['firstMovement_times'][row]-trials['stimOn_times'][row]
   if rt<.08 or rt>2 or trials['choice'][row]==0:reasons.append('literal_trial_eligibility')
  y=None
  if not reasons:
   if target=='choice':y=[int(trials['choice'][row]==1)]
   elif target=='prior':
    if prior is None:raise MissingDefinition('original fitted prior producer/target recipe unresolved')
    y=[prior[row]]
   elif target in('gabors','static-gratings'):y=[raw['intervals'].iloc[row][definition['target_column']]]
   elif target=='lick':
    lick_times=np.asarray(raw['lick']['times']);y=[int(np.any((lick_times>=start)&(lick_times<stop)))]
   else:
    if source is None:reasons.append('behavior_unavailable')
    else:
     times=np.asarray(source['times']);values=np.asarray(source['values']);mask=(times>start)&(times<stop)
     t=times[mask];v=values[mask]
     if len(t)<2 or not np.isfinite(v).all():reasons.append('behavior_samples_missing_or_nonfinite')
     elif abs(start-t[0])>dt or abs(stop-t[-1])>dt:reasons.append('behavior_clock_coverage')
     else:y=interp1d(t,v,axis=0,kind='linear',fill_value='extrapolate')(np.linspace(start+dt,stop,nb)).reshape(-1)
  if y is not None and not np.isfinite(y).all():reasons.append('target_nonfinite')
  if reasons:dispositions.append({'row':row,'status':'excluded','reasons':reasons});continue
  edges=start+np.arange(nb+1)*dt
  x=np.column_stack([np.histogram(spike_times[spike_units==u],bins=edges)[0]for u in selected])
  # Histogram's last-bin endpoint is right-inclusive; source windows are half-open.
  for col,u in enumerate(selected):x[-1,col]-=np.count_nonzero((spike_units==u)&(spike_times==stop))
  xs.append(x);ys.append(y);kept.append(row);dispositions.append({'row':row,'status':'retained','reasons':[]})
 need(kept,'no supported trials')
 window_record=window_metadata(windows)
 return {'x':np.asarray(xs,dtype=float),'y':np.asarray(ys,dtype=float),'row_inverse':kept,
 'trial_ids':[raw['original_trial_ids'][i]for i in kept],'unit_ids':[raw['unit_ids'][i]for i in selected],
 'dispositions':dispositions,'clock':raw['clock'],'windows':window_record['values'],'window_endpoint_dispositions':window_record['endpoint_dispositions'],'binsize':dt,
 'unit_selection':{'source':'published Allen licking seven-region union'if case['dataset']=='allen'and target=='lick'else'original regional selection',
  'selected_original_indices':selected,'selected_regions':[raw['unit_regions'][i]for i in selected],
  'eligible_region_union':list(ALLEN_LICK_REGIONS)if case['dataset']=='allen'and target=='lick'else None},
 'sequence_segments':[sum(kept[j]!=kept[j-1]+1 for j in range(1,i+1))for i in range(len(kept))]}
