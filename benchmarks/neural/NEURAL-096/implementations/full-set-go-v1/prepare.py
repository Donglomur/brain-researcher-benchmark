#!/usr/bin/env python3
"""Prepare every nominal-800-ms source train/validation Set–Go interval.

This is source preparation, not an estimator, scientific scorer, or model run.
No test-file, outcome/outlier, behavioral-tp or prior-solver result is read.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time

import h5py
import numpy as np

from core import (ContractError, require, observed_union, containing_segment,
                  phase_edges, count_phase_spikes, matched_support)

SOURCE_BYTES = 14119912
SOURCE_SHA256 = '6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198'
SOURCE_URL = 'https://api.dandiarchive.org/api/assets/c90cbccc-31a5-4815-88e6-822d8c5ca68c/download/'
FIELDS = ('id','split','ts','is_short','is_eye','theta','start_time','stop_time',
          'ready_time','set_time','go_time')
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
READS = []


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def dataset(handle, path, *, shape=None, max_bytes=32*1024*1024):
    group = handle
    for component in path.strip('/').split('/'):
        require(isinstance(group, h5py.Group), 'non-group in source path')
        require(isinstance(group.get(component, getlink=True), h5py.HardLink),
                'indirect HDF5 link refused')
        group = group[component]
    require(isinstance(group, h5py.Dataset) and not group.is_virtual and not group.external,
            'indirect HDF5 dataset refused')
    require(group.size * max(group.dtype.itemsize, 64 if group.dtype.kind == 'O' else 0) <= max_bytes,
            'source dataset exceeds read bound')
    if shape is not None:
        require(tuple(group.shape) == tuple(shape), 'unexpected source shape: '+path)
    return group


def read(handle, path, **kwargs):
    item = dataset(handle, path, **kwargs)
    value = item[...]
    READS.append({'path':path,'shape':list(item.shape),'dtype':str(item.dtype)})
    return value


def source_metadata(handle):
    data = {name:read(handle,'/intervals/trials/'+name,shape=(1160,)) for name in FIELDS}
    require(data['id'].dtype.kind in 'iu' and len(set(map(int,data['id']))) == 1160,
            'source trial IDs must be unique integers')
    data['split'] = [value.decode('utf8') if isinstance(value,bytes) else str(value)
                     for value in data['split']]
    require(Counter(data['split']) == {'train':748,'val':258,'none':154}, 'source split census changed')
    for name in ('is_eye','is_short'):
        require(data[name].dtype.kind == 'b', 'cue flag must be boolean')
    unit_ids = read(handle,'/units/id',shape=(54,))
    heldout = read(handle,'/units/heldout',shape=(54,))
    require(unit_ids.dtype.kind in 'iu' and len(set(map(int,unit_ids))) == 54, 'invalid unit IDs')
    require(heldout.dtype.kind == 'b' and int(heldout.sum()) == 14, 'source unit roles changed')
    obs = read(handle,'/units/obs_intervals',shape=(324,2))
    index = read(handle,'/units/obs_intervals_index',shape=(54,))
    require(index.dtype.kind in 'iu' and bool((index[1:] > index[:-1]).all())
            and int(index[0]) > 0 and int(index[-1]) == len(obs), 'invalid observation offsets')
    unions=[]
    first=0
    for last in index:
        unions.append(observed_union(obs[first:int(last)])); first=int(last)
    require(all(x == unions[0] for x in unions), 'units do not share the complete observation support')
    segments=unions[0]
    require(len(segments) == 6, 'source observation segment count changed')
    selected, census, failures = [], [], []
    for i, trial_id in enumerate(data['id']):
        eligible = data['split'][i] in ('train','val') and data['ts'][i] == 800.0
        census.append({'source_row':i,'trial_id':int(trial_id),'source_split':data['split'][i],
                       'nominal_selected':bool(eligible),
                       'selection_reason':'nominal_800_train_val' if eligible else
                       ('outside_source_train_val' if data['split'][i] == 'none' else 'nominal_interval_not_800')})
        if not eligible:
            continue
        row={'source_row':i,'trial_id':int(trial_id),'source_split':data['split'][i],
             'is_eye':bool(data['is_eye'][i]),'is_short':bool(data['is_short'][i]),
             'theta':float(data['theta'][i]),'nominal_sample_interval_ms':float(data['ts'][i])}
        for key in ('start_time','stop_time','ready_time','set_time','go_time'):
            row[key] = float(data[key][i])
        try:
            require(all(math.isfinite(row[k]) for k in ('start_time','stop_time','ready_time','set_time','go_time')),
                    'nonfinite required event')
            require(row['theta'] in (0.0,180.0), 'unknown response direction')
            require(row['start_time'] <= row['ready_time'] < row['set_time'] < row['go_time'] <= row['stop_time'],
                    'native Set–Go is outside its ordered trial events')
            row['observation_segment'] = containing_segment(row['set_time'],row['go_time'],segments)
            row['actual_sample_interval_seconds'] = row['set_time']-row['ready_time']
            row['observed_production_interval_seconds'] = row['go_time']-row['set_time']
            phase_edges(row['set_time'],row['go_time'])
        except ContractError as exc:
            failures.append({'trial_id':int(trial_id),'reason':str(exc)})
        selected.append(row)
    require(len(selected) == 204 and Counter(r['source_split'] for r in selected) == {'train':150,'val':54},
            'complete nominal-800 source census changed')
    if failures:
        return {'status':'unsupported_source_coverage','failures':failures,'census':census}, None
    selected.sort(key=lambda row:row['set_time'])
    require(all(a['go_time'] <= b['set_time'] for a,b in zip(selected,selected[1:])),
            'selected complete production intervals overlap')
    metadata = {'schema':'neural096_full_set_go_observations_v1','status':'source_metadata_supported',
        'task_id':'NEURAL-096','source':{'sha256':SOURCE_SHA256,'bytes':SOURCE_BYTES,
            'url':SOURCE_URL,'dandiset':'000130','version':'0.241017.1448','license':'CC-BY-4.0',
            'animal':'Haydn','session':'20161211'},
        'parent_source_split_counts':{'train':748,'val':258,'none':154},
        'selected_split_counts':{'train':150,'val':54},'selected_trial_count':204,
        'unit_ids':list(map(int,unit_ids)), 'nlb_heldout_unit_flags':list(map(bool,heldout)),
        'unit_scope':'All54released source-training units:40NLBheld-in+14NLBheld-out. This is observed-data analysis, not NLBheld-out-unit prediction.',
        'observation_segments_seconds':segments,'support':matched_support(selected,len(segments)),
        'trial_order':'Ascending native Set time, all204 nominal800ms source train/validation rows.',
        'census':census,'trials':selected,
        'representation':{'phase_bins':20,'interval':'[native set_time, native go_time)',
            'phase_edges':'Exact rational affine interpolation of supplied binary64 endpoints, rounded once to binary64; stored edges define bin membership.',
            'count_units':'spikes per source unit per phase bin','exposure_units':'seconds per phase bin',
            'raw_spike_units':'native absolute recording seconds, stored without time normalization',
            'ragged_order':'trial-major then unit-major; offsets[t*54+u:t*54+u+2]',
            'scope':'Allspikes in the complete observed interval retained. Phase normalization changes speed information; raw times, actual edges and exposures are supplied.',
            'no_fitted_basis':True,'no_smoothing':True},
        'interpretation_limits':[
            'Retrospective response-conditioned observations, not prospective prediction or causal attribution.',
            'One already exposed animal/session; trials, bins and neurons are not independent animals.',
            'Observation segments are not verified randomized prior/effector assignment blocks.',
            'No behavioral tp, outcome/is_outlier, testasset, prior answer, model fit or contrast is accessed/computed.',
            'Full task reference contrast, defensible blocked uncertainty and scientific qualification remain unestablished.'
        ]}
    return metadata, (unit_ids,heldout)


def extract(handle, metadata, unit_info):
    unit_ids, heldout = unit_info
    index=read(handle,'/units/spike_times_index',shape=(54,))
    values=dataset(handle,'/units/spike_times')
    require(index.dtype.kind in 'iu' and bool((index[1:] >= index[:-1]).all())
            and int(index[0]) >= 0 and int(index[-1]) == values.size, 'invalid spike offsets')
    require(values.ndim == 1 and values.dtype == np.dtype('float64'), 'source spike time dtype changed')
    rows=metadata['trials']; edges=np.stack([phase_edges(r['set_time'],r['go_time']) for r in rows])
    counts=np.zeros((len(rows),54,20),dtype='<u4')
    chunks=[[None]*54 for _ in rows]
    first=0; observed=metadata['observation_segments_seconds']
    for u,last in enumerate(index):
        vector=values[first:int(last)]; first=int(last)
        require(bool(np.isfinite(vector).all()) and bool((vector[1:] >= vector[:-1]).all()),
                'source unit spikes must be finite and sorted')
        for t,row in enumerate(rows):
            left,right=np.searchsorted(vector,[row['set_time'],row['go_time']],side='left')
            part=vector[left:right].copy()
            counts[t,u]=count_phase_spikes(part,edges[t])
            require(int(counts[t,u].sum()) == len(part),'full-interval spike conservation failed')
            chunks[t][u]=part
    READS.append({'path':'/units/spike_times','shape':list(values.shape),'dtype':str(values.dtype),
                  'read_pattern':'one complete source unit vector at a time; retain selected full intervals only'})
    flattened=[chunk for trial in chunks for chunk in trial]
    offsets=np.concatenate((np.asarray([0],dtype='<i8'),np.cumsum([len(c) for c in flattened],dtype=np.int64)))
    spikes=np.concatenate(flattened).astype('<f8',copy=False)
    require(int(offsets[-1]) == len(spikes) == int(counts.sum(dtype=np.uint64)), 'ragged spike conservation failed')
    return {'counts':counts,'phase_edges_seconds':edges,'exposure_seconds':np.diff(edges,axis=1),
            'spike_times_seconds':spikes,'spike_offsets':offsets,
            'trial_ids':np.asarray([r['trial_id'] for r in rows],dtype='<i8'),
            'unit_ids':unit_ids.astype('<i8'),'nlb_heldout_unit_flags':heldout.astype('u1')}


def prepare(source, output, *, reserve_bytes):
    started=time.monotonic(); cpu=time.process_time(); READS.clear()
    source,output=Path(source),Path(output).resolve()
    require(type(reserve_bytes) is int and reserve_bytes >= 0, 'invalid free disk reserve')
    require(source.is_file() and not source.is_symlink() and source.stat().st_size == SOURCE_BYTES
            and sha(source) == SOURCE_SHA256,'exact authenticated training NWB required')
    require(not output.exists(), 'output already exists')
    require(not any((p/'.git').exists() for p in (output,*output.parents)), 'authentic output must remain outside Git worktrees')
    output.parent.mkdir(parents=True,exist_ok=True)
    require(shutil.disk_usage(output.parent).free >= reserve_bytes+MAX_OUTPUT_BYTES,'insufficient disk reserve')
    source_files={name:{'bytes':(Path(__file__).parent/name).stat().st_size,
                        'sha256':sha(Path(__file__).parent/name)} for name in ('core.py','prepare.py','PROTOCOL.json')}
    with h5py.File(source,'r') as handle:
        metadata,unit_info=source_metadata(handle)
        arrays=extract(handle,metadata,unit_info) if unit_info is not None else None
    require(sha(source) == SOURCE_SHA256,'source changed during preparation')
    require(all(sha(Path(__file__).parent/name)==pin['sha256'] for name,pin in source_files.items()),
            'implementation changed during preparation')
    with tempfile.TemporaryDirectory(prefix='.neural096-set-go-',dir=output.parent) as temp:
        staging=Path(temp)/'packet'; staging.mkdir()
        write_json(staging/'observations.json',metadata)
        if arrays is not None:
            np.savez_compressed(staging/'observations.npz',**arrays)
        inventory=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(staging.iterdir())]
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        receipt={'schema':'neural096_source_preparation_receipt_v1',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'status':'complete_source_observations_prepared' if arrays is not None else 'unsupported_source_coverage',
            'source_sha256':SOURCE_SHA256,'implementation':source_files,'files':inventory,
            'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'h5py':h5py.__version__},
            'value_reads':READS.copy(),'spike_values_read':arrays is not None,'test_asset_read':False,
            'new_download_bytes':0,'new_model_trials':0,'fits':0,'reference_contrasts':0,
            'scientific_qualified':False,'full_task_completed':False,
            'selected_trials':len(metadata.get('trials',[])), 'units':54 if arrays is not None else None,
            'total_retained_spikes':int(arrays['counts'].sum(dtype=np.uint64)) if arrays is not None else None,
            'cpu_seconds_before_receipt':time.process_time()-cpu,'wall_seconds_before_receipt':time.monotonic()-started,
            'peak_rss_bytes':rss if sys.platform=='darwin' else rss*1024,
            'output_cap_bytes':MAX_OUTPUT_BYTES,'operator_disk_reserve_bytes':reserve_bytes}
        write_json(staging/'receipt.json',receipt)
        require(sum(p.stat().st_size for p in staging.iterdir()) <= MAX_OUTPUT_BYTES,'complete output exceeds byte limit')
        require(shutil.disk_usage(output.parent).free >= reserve_bytes,'free disk reserve exhausted')
        staging.rename(output)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reserve-bytes',type=int,default=0)
    args=parser.parse_args()
    result=prepare(args.source,args.output,reserve_bytes=args.reserve_bytes)
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='complete_source_observations_prepared' else 2


if __name__=='__main__':
    raise SystemExit(main())
