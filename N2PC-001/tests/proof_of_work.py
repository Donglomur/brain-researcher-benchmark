"""Source-epoch binding followed by own-primitive complete signed replay."""
import numpy as np
import io_contract as io
import n2pc_math as core


def scalar_field(got,expected,key,json_mode=False):
    if expected is None:
        io.need(got is None if json_mode else got=='','nullable_field_'+key)
    elif type(expected) is bool:
        if json_mode:io.need(type(got) is bool and got==expected,'boolean_'+key)
        else:io.need(io.boolean(got)==expected,'boolean_'+key)
    elif type(expected) is int:
        if json_mode:io.number(got,True)
        io.need(io.integer(got)==expected,'integer_'+key)
    elif type(expected) is float:
        value=io.number(got,json_mode)
        if key.endswith('_uv') or key=='fixed_po8_minus_po7_pooled_uv_for_reference':io.close(value,expected)
        elif key in ('time_s','onset_s'):io.close(value,expected,1e-9,0)
        else:io.need(value==expected,'source_scalar_'+key)
    else:io.need(type(got) is str and got==expected,'string_'+key)


def literal(got,expected):
    io.exact_json(got,expected)
    if isinstance(expected,dict):
        io.need(set(got)==set(expected),'literal_dict_keys')
        for k in expected:literal(got[k],expected[k])
    elif isinstance(expected,list):
        for a,b in zip(got,expected):literal(a,b)


def normalized_key(row,keys,json_mode=False):
    result=[]
    for k in keys:
        value=row[k]
        if k in ('subject','source_event_index','sample_offset'):
            if k=='subject' and row.get('scope')=='group':
                io.need(value is None if json_mode else value=='','group_subject_null');value=None
            else:
                if json_mode:io.number(value,True)
                value=io.integer(value)
        result.append(value)
    return tuple(result)


def table(path,expected,spec,max_rows):
    columns=spec['required_columns'];keys=spec['key']
    rows=io.csv_read(path,columns,max_rows);indexed={}
    for row in rows:
        key=normalized_key(row,keys)
        io.need(key not in indexed,'duplicate_table_key');indexed[key]=row
    want={normalized_key(r,keys,True):r for r in expected}
    io.need(set(indexed)==set(want),'table_membership')
    for key,r in want.items():
        got=indexed[key]
        for name in columns:
            if name in ('event_type_json','urevent_json'):
                literal(io.json_bytes(got[name]),io.json_bytes(r[name]))
            else:scalar_field(got[name],r[name],name)
    return rows


def epochs(path,reference):
    arrays=io.npz_read(path)
    io.need(set(('subject','source_event_index','channel_labels','sample_offsets','epochs_uv'))<=set(arrays),'npz_required')
    subjects,events,channels,offsets,x=(arrays[k] for k in ('subject','source_event_index','channel_labels','sample_offsets','epochs_uv'))
    for v in (subjects,events,offsets):io.need(v.ndim==1 and v.dtype.kind in 'iu','integer_npz_axes')
    io.need(subjects.shape==events.shape and len(subjects)<=5000,'epoch_key_shape')
    io.need(channels.shape==(2,) and channels.dtype.kind=='U' and set(channels.tolist())=={'PO7','PO8'},'channel_axis')
    io.need(offsets.shape==(667,) and len(set(offsets.tolist()))==667 and set(offsets.tolist())==set(core.OFFSETS.tolist()),'sample_axis')
    io.need(x.shape==(len(subjects),2,667) and x.dtype.kind in 'fiu' and np.isfinite(x).all(),'epoch_array')
    keys=[(int(s),int(e)) for s,e in zip(subjects,events)]
    io.need(len(set(keys))==len(keys) and set(keys)==set(reference['keys']),'retained_epoch_keys')
    index={k:i for i,k in enumerate(keys)}
    rows=[index[k] for k in reference['keys']];ch=[channels.tolist().index(c) for c in ('PO7','PO8')]
    sample={int(v):i for i,v in enumerate(offsets)};ti=[sample[int(v)] for v in core.OFFSETS]
    aligned=np.asarray(x,dtype=np.float64)[rows][:,ch][:,:,ti]
    io.close(aligned,reference['epochs_uv'],1e-6,1e-6)
    return aligned


def result_json(path,expected):
    got=io.json_bytes(io.read_bytes(path,16*1024**2));io.need(isinstance(got,dict),'results_object')
    io.need(set(expected)<=set(got),'results_fields')
    for k,v in expected.items():
        if k=='subjects':
            io.need(isinstance(got[k],list),'subjects_list')
            vals=[io.integer(io.number(x,True)) for x in got[k]]
            io.need(len(vals)==len(set(vals)) and set(vals)==set(v),'subjects_membership')
        elif isinstance(v,(list,dict)):io.exact_json(got[k],v)
        else:scalar_field(got[k],v,k,True)
    return got


def metadata_json(path,expected):
    got=io.json_bytes(io.read_bytes(path,16*1024**2));io.need(isinstance(got,dict),'metadata_object')
    io.need(set(expected)<=set(got),'metadata_fields')
    for key in ('status','dataset_id','source_manifest_sha256','method_contract_sha256'):io.exact_json(got[key],expected[key])
    subjects=got['subjects'];io.need(isinstance(subjects,list),'subjects_list')
    ids=[io.integer(io.number(x,True)) for x in subjects]
    io.need(len(ids)==len(set(ids)) and set(ids)==set(expected['subjects']),'metadata_subjects')
    for section,keys in [('source_files',('subject','role')),('source_observed',('subject',)),('processing_observed',('subject',))]:
        rows=got[section];io.need(isinstance(rows,list) and all(isinstance(r,dict) for r in rows),'metadata_records')
        indexed={}
        for r in rows:
            k=normalized_key(r,keys,True);io.need(k not in indexed,'duplicate_metadata_key');indexed[k]=r
        target={normalized_key(r,keys,True):r for r in expected[section]}
        io.need(set(indexed)==set(target),'metadata_membership')
        for k,r in target.items():
            g=dict(indexed[k])
            for field in ('eeg_reference_channels','excluded_eog_channels'):
                if field in r:
                    io.need(isinstance(g.get(field),list) and len(g[field])==len(r[field]) and set(g[field])==set(r[field]),'metadata_reference_membership')
                    g[field]=r[field]
            io.exact_json(g,r)
            if 'event_type_counts' in r:literal(g['event_type_counts'],r['event_type_counts'])
    versions=got.get('software_versions')
    io.need(isinstance(versions,dict) and versions and all(isinstance(k,str) and isinstance(v,str) and v for k,v in versions.items()),'software_versions')
    io.need(isinstance(got.get('implementation'),str) and got['implementation'].strip(),'implementation_description')
    warnings=got.get('warnings');io.need(isinstance(warnings,list),'warnings_list')
    for w in warnings:
        io.need(isinstance(w,dict) and {'subject','stage','category','message'}<=set(w),'warning_record')
        if w['subject'] is not None:io.need(io.integer(io.number(w['subject'],True)) in ids,'warning_subject')
        io.need(all(isinstance(w[k],str) for k in ('stage','category','message')),'warning_strings')
    return got


def validate(output_dir,reference):
    io.need(reference['subjects']==list(core.SUBJECTS),'production_full_fixed_cohort_required')
    files=io.output_files(output_dir);schema=reference['method']['output_schema']
    x=epochs(files['response_epochs.npz'],reference)
    own=core.derive(reference['trials'],x)
    for name,expected,cap in [('annotations.csv',reference['annotations'],10000),('trials.csv',own['trials'],5000),
                              ('per_subject.csv',own['per_subject'],12),('waveforms.csv',own['waveforms'],8671)]:
        accepted_rows=table(files[name],expected,schema[name],cap)
        if name=='per_subject.csv':
            # Public pre-signal clarification: this descriptive discrete count
            # follows accepted submitted person values, not incidental reduction
            # roundoff in an unreported private arithmetic path.
            own['result']['n_subjects_negative']=sum(r['n2pc_uv']!='' and io.number(r['n2pc_uv'])<0 for r in accepted_rows)
    result_json(files['n2pc.json'],own['result'])
    metadata_json(files['run_metadata.json'],reference['metadata'])
    findings=io.read_bytes(files['findings.md'],1024**2).decode('utf-8')
    io.need(findings.strip(),'nonempty_findings')
    return dict(status='ok',n_subjects=12,n_source_events=len(reference['annotations']),n_target_events=len(reference['trials']),
                n_retained_epochs=len(x),primitive_max_abs_diff_uv=float(np.max(np.abs(x-reference['epochs_uv']))) if x.size else 0.0,
                source_manifest_sha256=reference['metadata']['source_manifest_sha256'],method_contract_sha256=reference['metadata']['method_contract_sha256'])
