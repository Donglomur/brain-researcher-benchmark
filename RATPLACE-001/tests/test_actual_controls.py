"""Authoring-only actual-output controls; excluded by production test.sh."""
import copy
import csv
import json
import os
import numpy as np
import pytest

pytestmark=pytest.mark.skipif(os.environ.get('REPAIR_RUN_ACTUAL_CONTROLS')!='1',reason='explicit actual-output QA required')

MODES=('baseline','axis_permutation','six_decimal_receipts','descriptive_extras',
       'raw_count','null_count','offset','defined_mask','headline','p_domain',
       'source_hash','missing_unit','missing_ledger','failure_marker')

def persist(actual,path,reader):
    path.mkdir()
    with (path/'spatial_evidence.npz').open('xb') as f:np.savez_compressed(f,**actual['arrays'])
    with (path/'spatial_information.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=reader.COLUMNS);w.writeheader();w.writerows(actual['rows'])
    for name,key in [('results.json','results'),('run_metadata.json','metadata')]:
        (path/name).write_text(json.dumps(actual[key],indent=2,allow_nan=False)+'\n')
    (path/'findings.md').write_text(actual['findings'])

@pytest.mark.parametrize('mode',MODES)
def test_actual_control(mode,actual_context,tmp_path,record_property):
    modules,reference,baseline=actual_context
    # Never share nested receipt dictionaries or arrays with the genuine baseline.
    actual=copy.deepcopy(baseline);a=actual['arrays'];n=len(a['unit_ids'])
    positive=mode in MODES[:4]
    record_property('control_mode',mode)
    record_property('control_category','positive' if positive else 'negative')
    if n==0 and mode in ('raw_count','null_count','offset','defined_mask','headline','p_domain','missing_unit'):
        record_property('control_outcome','unavailable');record_property('effect_count',0)
        return
    if mode=='axis_permutation':
        ui=np.arange(n)[::-1];bi=np.arange(20)[::-1];di=np.arange(300)[::-1]
        a['unit_ids']=a['unit_ids'][ui];a['bin_ids']=a['bin_ids'][bi];a['draw_ids']=a['draw_ids'][di]
        a['occupancy_seconds']=a['occupancy_seconds'][bi]
        a['raw_counts']=a['raw_counts'][np.ix_(ui,bi)]
        a['shifted_counts']=a['shifted_counts'][np.ix_(ui,di,bi)]
        for key in ('shift_offsets_seconds','shift_defined'):a[key]=a[key][np.ix_(ui,di)]
        actual['rows'].reverse();actual['metadata']['all_units'].reverse()
    elif mode=='six_decimal_receipts':
        numeric=[]
        for row in actual['rows']:
            own=dict(row);own['n_spikes']=int(row['n_spikes'])
            for k in modules['proof_v2'].FLOAT_FIELDS:
                row[k]=format(float(row[k]),'.6f') if row[k] else ''
                own[k]=float(row[k]) if row[k] else None
            numeric.append(own)
        actual['results']=modules['information_kernel'].summarize(numeric)
    elif mode=='descriptive_extras':
        actual['metadata']['software_note']='An independently serialized version description.'
        actual['findings']='Single-session normalized-position method control; no physical calibration claim.\n'
    elif mode=='raw_count':a['raw_counts'][0,0]+=1
    elif mode=='null_count':a['shifted_counts'][0,0,0]+=1
    elif mode=='offset':a['shift_offsets_seconds'][0,0]+=1.
    elif mode=='defined_mask':a['shift_defined'][0,0]=not a['shift_defined'][0,0]
    elif mode=='headline':actual['results']['mean_raw_bits_per_spike']+=1.
    elif mode=='p_domain':
        selected=next((row for row in actual['rows'] if row['status']=='ok'),None)
        if selected is None:
            record_property('control_outcome','unavailable');record_property('effect_count',0);return
        selected['p_upper']='1.0000005'
    elif mode=='source_hash':actual['metadata']['pins']['source_manifest_sha256']='0'*64
    elif mode=='missing_unit':actual['rows'].pop()
    elif mode=='missing_ledger':actual['metadata']['all_units'].pop()
    path=tmp_path/'candidate';persist(actual,path,modules['artifact_reader'])
    if mode=='descriptive_extras':(path/'additional_notes.txt').write_text('Permitted regular extra.')
    if mode=='failure_marker':(path/'failure_report.json').write_text('{}')
    record_property('effect_count',0 if positive else 1)
    if positive:
        assert modules['proof_v2'].validate_output_directory(path,reference)['status']=='verified'
        record_property('control_outcome','accepted_positive')
    else:
        with pytest.raises(ValueError):modules['proof_v2'].validate_output_directory(path,reference)
        record_property('control_outcome','effective_rejection')
    # tmp_path candidates remain under the explicitly retained QA basetemp.
