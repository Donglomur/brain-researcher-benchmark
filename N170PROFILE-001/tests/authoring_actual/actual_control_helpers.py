"""Authoring-only mutations, not production scoring or new scientific analyses.

Negative bundles isolate a deliberately incoherent component while retaining
other receipts. Classify effects before invoking the normal full validator.
"""
import csv
import io
import json
import math
import os
from pathlib import Path
import numpy as np

MODES={'baseline':'positive','coherent_axes_rows':'positive','six_decimal_receipts':'positive',
       'wrong_source_hash':'binding','missing_participant':'binding','missing_trial':'binding',
       'condition_sign_flip':'numerical','ptp_plus_one':'numerical',
       'participant_amplitude_plus_one':'numerical','headline_mean_plus_one':'numerical'}
FRAGMENTS={'wrong_source_hash':'source_manifest_sha256','missing_participant':'complete participant membership',
           'missing_trial':'trials: complete source membership','condition_sign_flip':'source waveform fidelity',
           'ptp_plus_one':'numeric_tolerance','participant_amplitude_plus_one':'amp_po8_uv: measurement replay',
           'headline_mean_plus_one':'amp_po8_uv: numerical mismatch'}


class NotConstructed(ValueError):pass


def snapshot(root,reader):
    root=reader.safe_path(root);files=reader.output_files(root)
    captured={name:reader.read_bytes(path) for name,path in files.items()}
    reader.need(set(reader.output_files(root))==set(captured),'baseline_inventory_changed')
    return captured


def clone(destination,captured,reader,protected):
    out=reader.safe_path(destination)
    reader.need(not os.path.lexists(out) and out.parent.is_dir(),'fresh_control_destination')
    for value in protected:
        p=reader.safe_path(value)
        reader.need(out!=p and p not in out.parents and out not in p.parents,'control_source_overlap')
    reader.need(len(captured)<=reader.MAX_OUTPUT_FILES and sum(map(len,captured.values()))<=reader.AGGREGATE_LIMIT,'control_snapshot_bound')
    for name,raw in captured.items():
        reader.need(type(name) is str and Path(name).name==name and name not in ('.','..') and '\\' not in name and '\0' not in name,'control_name')
        reader.need(isinstance(raw,bytes) and len(raw)<=reader.LIMIT,'control_member_bound')
    out.mkdir(mode=0o700)
    for name,raw in captured.items():
        with os.fdopen(os.open(out/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
    return out


def replace(out,name,raw,reader):
    files=reader.output_files(out);reader.need(name in files,'unknown_control_file')
    if len(raw)>reader.LIMIT or sum(p.stat().st_size for k,p in files.items() if k!=name)+len(raw)>reader.AGGREGATE_LIMIT:
        raise NotConstructed('serialization exceeds public cap; no headroom requirement imposed')
    p=reader.safe_path(files[name]);reader.read_bytes(p)
    with os.fdopen(os.open(p,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW),'wb') as f:f.write(raw)


def read_csv(path,reader):
    text=reader.read_bytes(path).decode('utf-8-sig');prior=csv.field_size_limit(reader.MAX_CSV_FIELD)
    try:rows=list(csv.reader(io.StringIO(text,newline=''),strict=True))
    finally:csv.field_size_limit(prior)
    reader.need(rows and len(set(rows[0]))==len(rows[0]) and all(len(r)==len(rows[0]) for r in rows),'control_csv_shape')
    return rows[0],[dict(zip(rows[0],r)) for r in rows[1:]]


def csv_bytes(fields,rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode()


def json_bytes(value):return (json.dumps(value,indent=2,allow_nan=False,ensure_ascii=False)+'\n').encode()


def npz_bytes(arrays):
    buffer=io.BytesIO();np.savez(buffer,**arrays);return buffer.getvalue()


def baseline_replay(out,reference,modules):
    proof=modules['proof_of_work'];reader=modules['io_contract']
    waves,flags=proof.canonical_primitives(reader.npz_read(Path(out)/'erp_evidence.npz'),reference)
    people=proof.participant_replay(waves,flags,reference)
    return dict(people={r['subject_id']:r for r in people},groups=proof.group_replay(people))


def receipt(mode):
    return dict(mode=mode,category=MODES[mode],classification='constructed',numeric_effect_count=0,
                binding_effect_count=0,status_effect_count=0,effect_count=0,effect_max_absolute_gap=None,
                expected_rejection_fragment=FRAGMENTS.get(mode),
                description='positive serialization equivalence' if MODES[mode]=='positive' else
                'isolated deliberately incoherent diagnostic; other primitive and metadata receipts unchanged')


def classify(info,gaps,violations):
    values=np.asarray(gaps,dtype=float);bad=np.asarray(violations,dtype=bool)
    info['numeric_effect_count']=int(np.count_nonzero(bad));info['effect_count']=info['numeric_effect_count']
    info['effect_max_absolute_gap']=float(np.max(values)) if values.size else None
    info['classification']='effective' if info['effect_count'] else 'nondiscriminating'
    return info


def mutate(out,mode,reference,modules,replayed):
    reader=modules['io_contract'];proof=modules['proof_of_work'];out=Path(out);info=receipt(mode)
    if mode=='baseline':return info
    if mode=='coherent_axes_rows':
        a=reader.npz_read(out/'erp_evidence.npz')
        s=np.arange(len(a['subject_ids']))[::-1];c=np.array([1,0]);k=np.arange(len(a['sample_offsets']))[::-1]
        h=np.arange(len(a['rejection_channel_labels']))[::-1];e=np.arange(len(a['epoch_subject_ids']))[::-1]
        for name,index in [('subject_ids',s),('condition_labels',c),('sample_offsets',k),('rejection_channel_labels',h),
                           ('epoch_subject_ids',e),('epoch_source_event_index',e),('epoch_po8_baseline_uv',e)]:a[name]=a[name][index]
        a['condition_defined']=a['condition_defined'][np.ix_(s,c)];a['evoked_po8_uv']=a['evoked_po8_uv'][np.ix_(s,c,k)]
        a['epoch_peak_to_peak_uv']=a['epoch_peak_to_peak_uv'][np.ix_(e,h)]
        replace(out,'erp_evidence.npz',npz_bytes(a),reader)
        for name in ('annotations.csv','trials.csv','per_subject.csv'):
            fields,rows=read_csv(out/name,reader);replace(out,name,csv_bytes(fields[::-1],rows[::-1]),reader)
        meta=reader.json_bytes(reader.read_bytes(out/'run_metadata.json'))
        for name in ('cohort','source_files'):meta[name].reverse()
        for name in ('source_observed','analysis_observed'):meta[name]['persons'].reverse()
        replace(out,'run_metadata.json',json_bytes(meta),reader);return info
    if mode=='six_decimal_receipts':
        fields,rows=read_csv(out/'per_subject.csv',reader)
        continuous=('amp_po8_uv','onset_ms','measurement_baseline_uv','peak_time_ms','peak_uv','half_height_uv')
        for row in rows:
            for name in continuous:
                if row[name]!='':row[name]=format(reader.number(row[name]),'.6f')
        replace(out,'per_subject.csv',csv_bytes(fields,rows),reader)
        def rounded(value):
            if type(value) is float:return round(value,6)
            if isinstance(value,list):return [rounded(x) for x in value]
            if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
            return value
        group=reader.json_bytes(reader.read_bytes(out/'n170.json'));replace(out,'n170.json',json_bytes(rounded(group)),reader)
        return info
    if mode=='wrong_source_hash':
        meta=reader.json_bytes(reader.read_bytes(out/'run_metadata.json'));old=meta['source_manifest_sha256']
        meta['source_manifest_sha256']='0'*64 if old!='0'*64 else '1'*64
        replace(out,'run_metadata.json',json_bytes(meta),reader)
    elif mode in ('missing_participant','missing_trial'):
        name='per_subject.csv' if mode=='missing_participant' else 'trials.csv';fields,rows=read_csv(out/name,reader)
        if not rows:info['classification']='nondiscriminating';return info
        replace(out,name,csv_bytes(fields,rows[1:]),reader)
    elif mode=='condition_sign_flip':
        a=reader.npz_read(out/'erp_evidence.npz');a['evoked_po8_uv']=-np.asarray(a['evoked_po8_uv'],dtype=np.float64)
        waves,flags=proof.canonical_primitives(a,reference);gaps=[];bad=[];wc=modules['wave_contract']
        for i in range(37):
            for j in range(2):
                if flags[i,j]:
                    diff=np.abs(waves[i,j]-reference['evoked_po8_uv'][i,j]);bound=wc.waveform_budget(reference['evoked_po8_uv'][i,j])
                    gaps.extend(diff.tolist());bad.extend((diff>bound).tolist())
            if flags[i].all():
                source=np.array(reference['evoked_po8_uv'][i,0]-reference['evoked_po8_uv'][i,1],dtype=float,order='C')
                changed=np.array(waves[i,0]-waves[i,1],dtype=float,order='C')
                source-=source[:52].mean();changed-=changed[:52].mean();diff=np.abs(changed-source)
                gaps.extend(diff.tolist());bad.extend((diff>wc.waveform_budget(source)).tolist())
        replace(out,'erp_evidence.npz',npz_bytes(a),reader);return classify(info,gaps,bad)
    elif mode=='ptp_plus_one':
        a=reader.npz_read(out/'erp_evidence.npz');a['epoch_peak_to_peak_uv']=a['epoch_peak_to_peak_uv']+1.0
        keys=list(zip(a['epoch_subject_ids'].tolist(),[reader.integer(v) for v in a['epoch_source_event_index']]))
        order={tuple(key):i for i,key in enumerate(reference['epoch_keys'])};channels={v:i for i,v in enumerate(reference['rejection_channel_labels'])}
        canonical=reference['epoch_peak_to_peak_uv'][np.ix_([order[k] for k in keys],[channels[v] for v in a['rejection_channel_labels']])]
        diff=np.abs(a['epoch_peak_to_peak_uv']-canonical);bad=diff>1e-6+1e-6*np.abs(canonical)
        replace(out,'erp_evidence.npz',npz_bytes(a),reader);return classify(info,diff,bad)
    elif mode=='participant_amplitude_plus_one':
        fields,rows=read_csv(out/'per_subject.csv',reader)
        chosen=next((r for r in rows if replayed['people'][r['subject_id']]['amp_po8_uv'] is not None),None)
        if chosen is None:info['classification']='nondiscriminating';return info
        expected=replayed['people'][chosen['subject_id']]['amp_po8_uv'];changed=reader.number(chosen['amp_po8_uv'])+1.
        if not math.isfinite(changed):raise NotConstructed('additive amplitude not representable')
        chosen['amp_po8_uv']=repr(changed);replace(out,'per_subject.csv',csv_bytes(fields,rows),reader)
        gap=abs(changed-expected);return classify(info,[gap],[gap>1e-6+1e-6*abs(expected)])
    elif mode=='headline_mean_plus_one':
        group=reader.json_bytes(reader.read_bytes(out/'n170.json'));expected=replayed['groups']['amp_po8_uv']
        if expected is None:info['classification']='nondiscriminating';return info
        changed=reader.number(group['amp_po8_uv'])+1.
        if not math.isfinite(changed):raise NotConstructed('additive headline not representable')
        group['amp_po8_uv']=changed;replace(out,'n170.json',json_bytes(group),reader)
        gap=abs(changed-expected);return classify(info,[gap],[gap>1e-6+1e-6*abs(expected)])
    else:raise ValueError('unknown_control_mode')
    info.update(classification='effective',binding_effect_count=1,effect_count=1)
    return info
