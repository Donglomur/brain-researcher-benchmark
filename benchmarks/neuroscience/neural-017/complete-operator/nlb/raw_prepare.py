"""Future privileged raw-to-full-panel conversion; no reference fitting."""
def prepare(raw,planned,organizer_source_path,source_manifest_sha,trace):
 import io,json,hashlib,h5py,numpy as np
 from .contracts import need,canonical
 from . import raw_counts as c
 from .fingerprint import compute_panel_fingerprint
 need(len(raw)==690612247 and hashlib.sha256(raw).hexdigest()=='a27f84f9c31f077011062fd99a6ced199fdf19e656151f056c3c6244a408a3c4','exact selected training NWB')
 with h5py.File(io.BytesIO(raw),'r')as f:
  identity,units,heldout,lo,hi,trials,intervals=c.inspect_metadata(f);selected,selection=c.full_selection(trials,intervals);windows=c.window_plan(selected)
  ti=[i for i,x in enumerate(selected)if x['split']=='train'];ei=[i for i,x in enumerate(selected)if x['split']=='val']
  ids=lambda ix:np.asarray(['train-nwb:trial-'+str(selected[i]['trial_id'])for i in ix])
  cond=lambda ix:np.asarray([json.dumps(selected[i]['condition'],separators=(',',':'))for i in ix])
  axes={'train_trial_ids':ids(ti),'eval_trial_ids':ids(ei),'heldin_unit_ids':np.asarray(['Jenkins-20090925:unit-'+str(u)for u in units[~heldout]]),'heldout_unit_ids':np.asarray(['Jenkins-20090925:unit-'+str(u)for u in units[heldout]]),'train_condition_ids':cond(ti),'eval_condition_ids':cond(ei),'bin_left_edges_ms':np.arange(-250,450,5,dtype=float)}
  for k,v in axes.items():need(np.array_equal(v,planned[k])and canonical(v.tolist())==canonical(planned[k]),'exact canonical pre-activity planned support mismatch: '+k)
  need(planned['chronological_eval_trial_ids']is None or canonical(planned['chronological_eval_trial_ids'])==canonical(axes['eval_trial_ids'].tolist()),'original known chronology matches planned support before activity')
  clock=c.official_alignment_full(trials,selected,organizer_source_path)
  trace({'event':'metadata_and_clock_complete_before_spikes','source_identity':identity,'selection':selection,'clock':clock})
  counts=np.empty((2295,140,182),dtype=np.uint16)
  for unit in range(182):
   counts[:,:,unit],proof=c.sparse_unit_counts(f['/units/spike_times'][lo[unit]:hi[unit]],windows);trace({'event':'original_count_conservation','unit_index':unit,**proof})
 public={**axes,'train_counts_heldin':counts[ti][:,:,~heldout],'train_counts_heldout':counts[ti][:,:,heldout],'eval_counts_heldin':counts[ei][:,:,~heldout],'eval_valid_mask':np.ones((574,140,45),dtype=bool),'source_manifest_sha256':source_manifest_sha}
 public['panel_fingerprint']=compute_panel_fingerprint(public)
 target={'counts_heldout':counts[ei][:,:,heldout],'trial_ids':axes['eval_trial_ids'],'unit_ids':axes['heldout_unit_ids'],'valid_mask':public['eval_valid_mask'],'panel_fingerprint':np.asarray(public['panel_fingerprint'])}
 report={'schema':'NLB017_full_conversion_v1','support':[1721,574,140,137,45],'all_source_trials':True,'clock':clock,'selection':selection,'no_reference_fit':True,'raw_operator_target_access':True,'public_panel_fingerprint':public['panel_fingerprint'],'chronological_eval_trial_ids':axes['eval_trial_ids'].tolist()}
 return public,target,report
