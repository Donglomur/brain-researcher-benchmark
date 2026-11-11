"""Authenticate the12 upstream-derived primitive field sets and exact trial join.

This does not read any EEG/eye recording, compute targets or fit a model.
Primitive metadata were produced by the shared trusted079 intake; original
object-NPY noise ceilings/args are not loaded or exported here.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_contract import capture,decode
from protocol import SUBJECTS,SESSIONS,CHANNELS,FIT,VALIDATION,QUERY

RECEIPT_SHA='d528066efe9742685eba77a6de3cbf5f81de05898b1847ba5aae76fadbfdd84c'


def need(ok,msg):
    if not ok:raise ValueError(msg)


def clock(times):
    need(type(times) is list and len(times)==1800,'Exact released1800-sample metadata clock')
    need(all(type(x) in (int,float) and abs(float(x)-(-.1+i/500))<=1e-9 for i,x in enumerate(times)),
         'Exact500Hz stimulus-relative metadata clock−.1..3.498s')
    return list(range(50,1550))


def trial_index(meta,session):
    values=[]
    for name,lo,hi in (('stimulus_id',1,1102),('run_number',1,16),('trial_number',1,66)):
        need(type(meta[name]) is dict and set(meta[name])==set(SESSIONS),'All eight session fields')
        v=meta[name][session]
        need(type(v) is list and v and all(type(x) is int and lo<=x<=hi for x in v),'Authentic integer trial metadata')
        values.append(v)
    need(len({len(v) for v in values})==1,'Trial field lengths')
    out={}
    for i,(vid,run,trial) in enumerate(zip(*values)):
        need((run,trial) not in out,'Duplicate session/run/trial key')
        out[run,trial]={'row':i,'video_id':vid}
    return out


def join(subject,eeg,eye):
    need(subject in SUBJECTS,'Exact designated person')
    clock(eeg['times']);clock(eye['times'])
    ch=eeg['ch_names'];need(type(ch) is list and len(ch)==CHANNELS and len(set(ch))==CHANNELS
                          and all(type(x) is str and x for x in ch),'All127 released channels')
    sessions={};counts=Counter()
    for session in SESSIONS:
        e=trial_index(eeg,session);o=trial_index(eye,session);common=sorted(e.keys()&o.keys())
        need(common,'Every designated session has an EEG/eye intersection')
        joined=[]
        for run,trial in common:
            a,b=e[run,trial],o[run,trial];need(a['video_id']==b['video_id'],'Stimulus identity disagreement at exact trial key')
            vid=a['video_id'];counts[vid]+=1
            joined.append({'run':run,'trial':trial,'video_id':vid,'eeg_row':a['row'],'eye_row':b['row']})
        sessions[session]={'eeg_trials':len(e),'eye_trials':len(o),'joined':joined,
            'eeg_only':[{'run':r,'trial':t,'video_id':e[r,t]['video_id']} for r,t in sorted(e.keys()-o.keys())],
            'eye_only':[{'run':r,'trial':t,'video_id':o[r,t]['video_id']} for r,t in sorted(o.keys()-e.keys())]}
    missing=[v for v in range(1,1103) if not counts[v]]
    need(not missing,'Every1102 video requires at least one exact joined trial; missing:'+str(missing))
    return {'subject':subject,'channel_names':ch,'eeg_times':eeg['times'],'eye_times':eye['times'],
            'sessions':sessions,'counts_per_video':[counts[i] for i in range(1,1103)],
            'support':{'joined_trials':sum(counts.values()),'missing_videos':missing,
                       'fit_min_repeats':min(counts[i] for i in FIT),'validation_min_repeats':min(counts[i] for i in VALIDATION),
                       'query_min_repeats':min(counts[i] for i in QUERY)}}


def build(source,out):
    need(not out.exists() and not out.is_symlink(),'Fresh selected join output')
    raw=capture(source/'SHARED_SELECTED_FIELDS_RECEIPT.json',10000)
    need(hashlib.sha256(raw).hexdigest()==RECEIPT_SHA,'Frozen shared selected-field receipt')
    receipt=decode(raw);need(receipt['complete'] is True and receipt['operator_private_only'] is True
         and {x['file'] for x in receipt['files']}=={s+'_selected_fields.json' for s in SUBJECTS},'Complete six-person selected fields')
    people=[];sources=[];channels=None
    for row in receipt['files']:
        body=capture(source/row['file'],2_000_000)
        need(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],'Authenticated primitive selected fields')
        obj=decode(body);fields=obj['selected_fields']
        need(obj['recording_arrays_or_noise_ceiling_exported'] is False and set(fields)=={'eeg','eye'},'No scientific data/ceiling input')
        record=join(obj['subject'],fields['eeg'],fields['eye'])
        if channels is None:channels=record['channel_names']
        need(channels==record['channel_names'],'Common released channel order across all people')
        people.append(record);sources.append(row)
    need({r['subject'] for r in people}==set(SUBJECTS),'Full six-person panel')
    result={'schema':'neural080_joined_metadata_v1','subjects':people,'selected_field_sources':sources,
            'hardware_alignment_independently_verified':False,'signal_arrays_read':False,'scientific_scores':0}
    body=(json.dumps(result,allow_nan=False,separators=(',',':'))+'\n').encode()
    need(len(body)<=12_000_000,'Bounded metadata join output')
    with out.open('xb') as f:f.write(body)
    return {'path':str(out),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
            'subjects':[{'subject':r['subject'],**r['support']} for r in people],
            'signal_arrays_read':False,'scientific_scores':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.out),indent=2))
