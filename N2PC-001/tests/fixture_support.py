"""Authoring emitter and manufactured basis; not a production source substitute."""
from copy import deepcopy
import csv
import json
import os
import numpy as np
import io_contract as io
import n2pc_math as core
import source_reference as source


def manufactured(empty_subject=None, zero=False):
    method,manifest=source.authority();annotations=[];trials=[];observed=[];processing=[]
    by={(r['subject'],r['role']):r for r in manifest['files']}
    for s in core.SUBJECTS:
        events=[dict(type=111,latency=1001,urevent=1),dict(type=121 if s!=empty_subject else 201,latency=2201,urevent=2),
                dict(type=112,latency=51,urevent=3),dict(type=-99,latency=1600.5,duration={'source_nonfinite':'nan'},urevent=None),
                dict(type=122,latency=1601,duration=0,urevent=5)]
        a,t,segments=core.annotate(s,events,4096);annotations.extend(a);trials.extend(t)
        labels=method['source']['channel_labels']
        observed.append(dict(subject=s,set_path=by[s,'set']['path'],fdt_path=by[s,'fdt']['path'],literal_fdt_pointer=by[s,'fdt']['path'],
            sfreq_hz=1024,n_samples=4096,n_channels=33,channel_labels=labels,source_reference_json='common',source_units_json=None,
            source_bad_channels=None,n_source_events=len(a),event_type_counts={str(k):sum(int(r['event_description'])==k for r in a) for k in {int(r['event_description']) for r in a}},
            n_target_left=sum(r['target_field']=='left' for r in t),n_target_right=sum(r['target_field']=='right' for r in t),
            n_boundary_events=1,n_bad_annotations=0,history_sha256='a'*64))
        processing.append(dict(subject=s,eeg_reference_channels=labels[:30],excluded_eog_channels=labels[30:],filter_segments=segments,
            fir_length=33793,epoch_offsets=[-205,461],baseline_offsets=[-204,0],measurement_offsets=[205,307],
            n_left_retained=sum(r['retained'] and r['target_field']=='left' for r in t),
            n_right_retained=sum(r['retained'] and r['target_field']=='right' for r in t),
            drop_reason_counts={k:sum(r['drop_reason']==k for r in t) for k in ('out_of_data','boundary_crossing','bad_annotation')}))
    keys=[(r['subject'],r['source_event_index']) for r in trials if r['retained']]
    x=np.zeros((len(keys),2,667),dtype=np.float64)
    if not zero:
        for j in range(len(x)):
            x[j,0]=(j+1)*.1+np.sin(np.arange(667)/50)
            x[j,1]=(j+1)*.2+np.cos(np.arange(667)/30)
    fields=('subject','role','path','object_id','version','size_bytes','sha256','md5')
    metadata=dict(status='ok',dataset_id='erp-core-n2pc-fixed12',source_manifest_sha256=source.SOURCE_SHA,method_contract_sha256=source.METHOD_SHA,
        subjects=list(core.SUBJECTS),source_files=[{k:r[k] for k in fields} for r in manifest['files']],source_observed=observed,processing_observed=processing)
    return dict(method=method,manifest=manifest,subjects=list(core.SUBJECTS),annotations=annotations,trials=trials,epochs_uv=x,keys=keys,metadata=metadata)


def write_output(path,reference,epochs=None):
    path=io.safe_path(path);io.need(not os.path.lexists(path) and path.parent.is_dir(),'fresh_output')
    path.mkdir()
    x=reference['epochs_uv'] if epochs is None else np.asarray(epochs)
    own=core.derive(reference['trials'],x,reference['subjects'])
    schema=reference['method']['output_schema']
    for name,rows in [('annotations.csv',reference['annotations']),('trials.csv',own['trials']),('per_subject.csv',own['per_subject']),('waveforms.csv',own['waveforms'])]:
        with (path/name).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(schema[name]['required_columns']));writer.writeheader();writer.writerows(rows)
    with (path/'response_epochs.npz').open('xb') as f:
        np.savez_compressed(f,subject=np.array([k[0] for k in reference['keys']],dtype=np.int64),
            source_event_index=np.array([k[1] for k in reference['keys']],dtype=np.int64),channel_labels=np.array(['PO7','PO8']),
            sample_offsets=core.OFFSETS,epochs_uv=x)
    metadata=deepcopy(reference['metadata']);metadata.update(software_versions={'numpy':np.__version__},
        implementation='Independent direct FDT analytic FIR and accepted primitive replay; no solution imports.',warnings=[])
    for name,value in [('n2pc.json',own['result']),('run_metadata.json',metadata)]:
        with (path/name).open('x') as f:json.dump(value,f,allow_nan=False,indent=2)
    with (path/'findings.md').open('x') as f:f.write('Signed fixed-cohort method control; no expected direction or population inference.\n')
    return own
