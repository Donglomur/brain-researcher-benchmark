"""Explicit original NWB to neutral event export; no discovery or data access on import.

The layout is read from captured load_preprocess.py lines152–165 and234–246.
An adjudicated per-session event pairing table is mandatory. We do not invent
cue/outcome matching for crashes, pseudo-outcomes or background milk.
"""
from pathlib import Path
import hashlib
from reward_common import need, finite_number, integer, unique_records
from observations import CONDITIONS


def decode_events(events, bindings, condition):
    need(condition in CONDITIONS,'Known condition')
    by_id=unique_records(events,['event_id']);used=set();trials=[]
    for row in unique_records(bindings,['trial_id']).values():
        kind=row['kind'];need(kind in ('CS_plus','CS_minus','milk','shock'),'Typed pairing')
        out=by_id[(row['outcome_event_id'],)] if row.get('outcome_event_id') is not None else None
        cue=by_id[(row['cue_event_id'],)] if row.get('cue_event_id') is not None else None
        if kind in ('CS_plus','shock'):
            need(cue is not None and out is not None,'Explicit cue/outcome pairing')
            need(cue['event_code']==15 and out['event_code']==10,'Source cue/outcome codes')
            need(out['event_flag'] in (0,1) and type(out['event_flag']) is int,'Outcome flag')
            delivered=out['event_flag']==0
        elif kind=='CS_minus':
            need(condition=='60s-CSminus' and cue is not None and cue['event_code']==7 and out is None,'Real CS minus')
            delivered=False
        else:
            need(condition=='600s-bgdmilk' and cue is None and out is not None and out['event_code']==7,'Uncued milk')
            delivered=True
        for e in (cue,out):
            if e is not None:
                need(e['event_id'] not in used,'Event cannot belong to two trials');used.add(e['event_id'])
        tcue=None if cue is None else finite_number(cue['timestamp'])
        tout=finite_number(out['timestamp']) if out is not None else tcue
        trials.append({'trial_id':row['trial_id'],'kind':kind,'cue_on':tcue,'outcome_time':tout,
                       'delivered':delivered,'cue_duration':row.get('cue_duration',15),
                       'missing':row.get('missing',[]),'pairing_status':'custodian_adjudicated'})
    expected={e['event_id'] for e in events if e['event_code'] in (15,10) or
              (e['event_code']==7 and condition in ('60s-CSminus','600s-bgdmilk'))}
    need(used==expected,'Complete trial-event support; no dropped hard events')
    return trials


def source_digest(path,limit):
    path=Path(path);need(path.is_file() and not path.is_symlink(),'Regular source file')
    size=path.stat().st_size;need(0<size<=limit,'Registered source byte bound')
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return {'bytes':size,'sha256':h.hexdigest()}


def export_nwb_session(path,entry,authority):
    """Future authorized source operation. Never called by engineering checks.

    Authority is a trusted controller input, not candidate-controlled JSON.
    It must establish authenticated asset/identity/clock/pairing adjudication.
    This source interface is not evidence that those gates have been met.
    """
    need(authority['authentic_data_access_authorized'] is True,'Explicit authentic-data authority required')
    for field in ('identity_verified','event_pairing_adjudicated','clock_units_seconds_verified'):
        need(entry[field] is True,'Unresolved export source gate: '+field)
    need(not entry['condition'].startswith('FC-'),'Aversive photometry/video clock join requires its dedicated source recipe')
    need(source_digest(path,entry['asset_pin']['bytes'])==entry['asset_pin'],'Immutable original asset')
    # Optional scientific dependency is deliberately lazy and never installed here.
    from pynwb import NWBHDF5IO
    with NWBHDF5IO(str(path),mode='r') as io:
        nwb=io.read();log=nwb.acquisition['eventLog']
        code=log.get('event_code').data[:].tolist();time=log.get('timestamp').data[:].tolist();flag=log.get('event_flag').data[:].tolist()
        need(len(code)==len(time)==len(flag),'Event arrays')
        def source_integer(v):
            v=finite_number(v);need(v.is_integer(),'Integral source event code or flag');return int(v)
        events=[{'event_id':i,'event_code':source_integer(c),'timestamp':finite_number(t),'event_flag':source_integer(f)}
                for i,(c,t,f) in enumerate(zip(code,time,flag))]
        need(all(a['timestamp']<=b['timestamp'] for a,b in zip(events,events[1:])),'Native event chronology')
        trials=decode_events(events,entry['trial_bindings'],entry['condition'])
        out={'session_number':entry['session_number'],'start_time':entry['start_time'],'end_time':entry['end_time'],
             'clock_origin':entry['clock_origin'],'trials':trials,'source':entry['asset_pin'],
             'lick_on':[e['timestamp'] for e in events if e['event_code']==5],
             'lick_off':[e['timestamp'] for e in events if e['event_code']==6]}
        if entry['photometry_designated']:
            photo=nwb.processing['photometry']['photometry_dff']
            out['photometry']={'times':[finite_number(x) for x in photo.timestamps[:].tolist()],
                               'values':[finite_number(x) for x in photo.data[:].tolist()],
                               'max_gap':entry['photometry_max_gap'],'fit_scope':'retrospective_full_session',
                               'raw_reconstruction_qualified':False}
        return out


def export_corpus(asset_root,registry,authority):
    need(registry['schema']=='reward_verified_registry_v1','Verified registry schema')
    need(registry['alias_collapse_verified'] is True,'Biological identity before folds')
    animals=[];assets=set()
    for row in unique_records(registry['animals'],['animal_id']).values():
        sessions=[]
        for entry in row['sessions']:
            rel=Path(entry['path']);need(not rel.is_absolute() and '..' not in rel.parts,'Relative asset path')
            need(entry['asset_pin']['sha256'] not in assets,'No duplicate source session')
            assets.add(entry['asset_pin']['sha256'])
            sessions.append(export_nwb_session(Path(asset_root)/rel,dict(entry,condition=row['condition']),authority))
        animals.append({'animal_id':row['animal_id'],'condition':row['condition'],'identity_status':'verified',
                        'sessions':sessions,'histology':row.get('histology'),'source_exclusions':row.get('source_exclusions',[])})
    return {'schema':'reward_neutral_corpus_v1','corpus_identity':registry['corpus_identity'],'animals':animals,
            'source_registry_sha256':registry['registry_sha256'],'raw_physiology_qualified':False}
