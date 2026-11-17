"""Exact role-view materialization and full ragged session admission."""
from pathlib import Path
from core import need, relative
from arrays import read_json, read_array

COMMON={'times','time_offsets','locations','location_missing'}
NEURAL={'spike_times','spike_units','spike_offsets','neural_domain','domain_offsets'}


def projected_document(original,role,training):
    need(role in ('C','J') and type(training) is bool,'explicit role projection')
    need(original.get('schema')=='neural058_session_view_v1' and original.get('task')=='NEURAL-058','prepared session schema')
    need(set(original['common'])==COMMON and set(original['neural'])==NEURAL,'complete original split members')
    need(training == (original['role']=='source'),'source labels only')
    return {'schema':'neural058_role_session_v1','task':'NEURAL-058','access':role,
            'corpus_role':original['role'],'session':original['session'],'animal':original['animal'],
            'windows':original['windows'],'regions':original['regions'],'fold':original['fold'],
            'arrays':dict(original['common']) | (dict(original['neural']) if role=='J' else {})
                     | ({'labels':original['labels']} if training else {})}


def offsets(value,total,windows):
    import numpy as np
    need(value.dtype.kind in 'iu' and value.shape==(windows+1,) and value[0]==0 and value[-1]==total,
         'complete ragged offsets')
    need(bool(np.all(np.diff(value)>=0)), 'monotonic full offsets')


def load_session(root,item,role,training,budget,limits):
    import numpy as np
    doc=read_json(root,item,budget,limits['metadata_bytes'])
    need(doc.get('schema')=='neural058_role_session_v1' and doc.get('task')=='NEURAL-058'
         and doc.get('access')==role,'exact assigned projection')
    need((doc['corpus_role']=='source')==training,'training/held-label role')
    expected=COMMON | (NEURAL if role=='J' else set()) | ({'labels'} if training else set())
    need(set(doc['arrays'])==expected,'no undeclared role or target arrays')
    session_root=Path(root)/relative(item['path']).parent
    arrays={k:read_array(session_root,d,budget,limits['array_bytes'],limits['expanded_bytes'])[0] for k,d in doc['arrays'].items()}
    windows=doc['windows']; need(windows and len(windows)<=limits['windows'],'full positive window roster')
    ids=[w['query'] for w in windows]; need(len(set(ids))==len(ids),'unique opaque occurrences, no duplicate removal')
    offsets(arrays['time_offsets'],len(arrays['times']),len(windows))
    need(bool(np.all(np.diff(arrays['time_offsets'])>0)), 'no empty original emitted target')
    U=len(doc['regions']); need(U>0 and arrays['locations'].shape==(U,3)
                             and arrays['location_missing'].shape==(U,3),'full anatomical axes')
    if training: need(arrays['labels'].shape==(len(arrays['times']),2),'complete source heads')
    if role=='J':
        offsets(arrays['spike_offsets'],len(arrays['spike_times']),len(windows))
        offsets(arrays['domain_offsets'],len(arrays['neural_domain']),len(windows))
        need(arrays['spike_units'].shape==arrays['spike_times'].shape and arrays['neural_domain'].shape[1:]==(2,), 'complete neural axes')
    result={'session':doc['session'],'animal':doc['animal'],'fold':doc['fold'],'regions':doc['regions'],
            'locations':arrays['locations'],'location_missing':arrays['location_missing'],'windows':[],
            'source_view':item,'role':role}
    for i,w in enumerate(windows):
        budget.tick(); t0,t1=arrays['time_offsets'][i:i+2]
        row=dict(w); row.update(locations=arrays['locations'],location_missing=arrays['location_missing'],regions=doc['regions'])
        row['times']=arrays['times'][t0:t1]
        need(bool(np.isfinite(row['times']).all()) and bool(np.all(np.diff(row['times'])>0)), 'original ordered timestamps')
        if training: row['labels']=arrays['labels'][t0:t1]
        if role=='J':
            s0,s1=arrays['spike_offsets'][i:i+2]; d0,d1=arrays['domain_offsets'][i:i+2]
            row.update(spike_times=arrays['spike_times'][s0:s1],spike_units=arrays['spike_units'][s0:s1],
                       neural_domain=arrays['neural_domain'][d0:d1])
        result['windows'].append(row)
    budget.tick(); return result


def weights_and_membership(sessions,expected_sessions,expected_animals):
    need([s['session'] for s in sessions]==expected_sessions,'full ordered session membership')
    need(sorted({s['animal'] for s in sessions})==expected_animals,'full animal membership')
    need(all(s['windows'] for s in sessions),'no empty session')
    return sum(len(s['windows']) for s in sessions)
