"""Synthetic mechanics fixtures only. These are NOT original-source references."""
import csv
import json
from pathlib import Path
import numpy as np
import population_contract as q


def toy_ref(counts=None, labels=None):
    contract = json.loads((Path(__file__).resolve().parents[1]/'environment/method_contract.json').read_text())
    if labels is None: labels = np.array([0]*8+[1]*8,dtype=np.int64)
    if counts is None: counts = [np.array([0,1,0,1,2,0,1,1,7,8,7,6,9,8,7,8]), np.zeros(len(labels),dtype=int)]
    labels = np.asarray(labels,dtype=np.int64); n = len(labels)
    asset = 'synthetic_fixture.nwb'
    sessions = [dict(asset_path=asset,asset_id='fixture-only',source_sha256='0'*64,subject_id='fixture-subject',nwb_identifier='fixture',
        literal_session_id=None,n_source_trials=n,n_learning_trials=0,n_recognition_trials=n,n_new=int(sum(labels == 0)),n_old=int(sum(labels == 1)),
        n_source_units=len(counts),n_mtl_units=len(counts),n_electrodes=len(counts),status='ok')]
    trials = [dict(asset_path=asset,source_trial_row=i,trial_id=2**53+3+i,stim_phase='recog',source_label_token=str(y),source_label=int(y),
        external_image_file='D:\\fixture\\'+str(i),image_in_learning=False,start_time_s=float(i*3),stim_on_time_s=float(i*3),
        stim_off_time_s=float(i*3+1),stop_time_s=float(i*3+2),included=True,status='included_recognition') for i,y in enumerate(labels)]
    units = [dict(asset_path=asset,unit_key=asset+'::unit='+str(9-i),source_unit_row=i,unit_id=9-i,n_electrode_links=1,
        electrode_row=i,electrode_id=101+i,original_channel=41+i,location='RightHippocampus',included=True,region='Hippocampus',exclusion_reason='included_mtl') for i in range(len(counts))]
    arrays = dict(unit_key=np.asarray([r['unit_key'] for r in units],dtype=str),response_unit_index=np.repeat(np.arange(len(units)),n),
        source_trial_row=np.tile(np.arange(n),len(units)),trial_id=np.tile([r['trial_id'] for r in trials],len(units)),
        source_label=np.tile(labels,len(units)),spike_count=np.concatenate(counts).astype(np.int64) if counts else np.array([],dtype=np.int64),repeat_id=np.arange(60))
    arrays['rate_hz'] = arrays['spike_count']/1.5; arrays['train_membership'] = q.generate_masks(arrays)
    metadata = dict(status='complete',task_id='MTLMEMORY-001',dandiset_id='000004',published_version='0.220126.1852',source_manifest_sha256=q.SOURCE_SHA256,
        method_contract_sha256=q.METHOD_SHA256,source_sha256={asset:'0'*64},method_contract=contract,headline_population=q.POPULATIONS[1],
        software_versions={'implementation':'synthetic mechanics only'},source_observed=dict(n_sessions=1,n_patients=1,n_source_trials=n,n_recognition_trials=n,
            n_source_units=len(units),n_mtl_units=len(units),sessions=[dict(asset_path=asset,phase_experiment_ids=dict(learn=1,recog=2),
            clock_mapping_counts=dict(n_trials=n),label_membership_counts=dict(code0_absent_from_learning=int(sum(labels == 0))),unit_electrode_link_counts=dict(one=len(units)))]))
    return dict(**arrays,sessions=sessions,trials=trials,units=units,metadata=metadata)


def write_csv(path, rows, fields):
    with Path(path).open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({k: int(v) if isinstance(v,bool) else v for k,v in row.items() if k in fields})


def emit(output, ref, headline=None):
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    headline = headline or q.POPULATIONS[1]; derived = q.analyze(ref); contract=ref['metadata']['method_contract']
    tables = {name:ref[key] for name,key in [('sessions.csv','sessions'),('trials.csv','trials'),('units.csv','units')]}
    tables.update({'neurons.csv':derived['neurons'],'split_events.csv':derived['split_events']})
    for name,rows in tables.items(): write_csv(output/name,rows,contract['outputs'][name]['columns'])
    np.savez_compressed(output/'trial_counts.npz',**{k:ref[k] for k in q.ARRAY_FIELDS})
    metadata = {**ref['metadata'],'headline_population':headline}
    (output/'results.json').write_text(json.dumps(q.summarize(ref,derived['neurons'],headline),allow_nan=False))
    (output/'run_metadata.json').write_text(json.dumps(metadata,allow_nan=False))
    (output/'findings.md').write_text('A descriptive calculation; no biological conclusion is claimed.\n')
    return output
