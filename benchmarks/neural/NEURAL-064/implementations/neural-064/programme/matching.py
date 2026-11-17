"""Actual deterministic categorical matching and complete disposition producer.
No neural amplitude can enter matching. Count/order controls use invented tokens.
"""
from collections import defaultdict
from .design import POLICIES

def match_secondary(rows,policy):
    if policy not in POLICIES:raise ValueError('separate named policy required')
    seen=set();groups=defaultdict(lambda:{'FIRST':[],'REPEAT':[]});dispositions=[]
    required=('mouse','container','image','change','pre_running_bin','pre_pupil_bin','within_session_history')
    for row in rows:
        eid=row['event']
        if eid in seen:raise ValueError('duplicate source event')
        seen.add(eid)
        if row['phase'] not in ('FIRST','REPEAT'):raise ValueError('secondary phase')
        missing=[k for k in required if row.get(k) is None]
        if policy=='outcome_conditioned_sensitivity' and (row.get('outcome_status')!='known' or row.get('outcome_flags') is None):missing.append('poststimulus_outcome')
        if missing:dispositions.append({'event':eid,'status':'unavailable_matching_fields','fields':missing});continue
        key=tuple(row[k] for k in required)
        if policy=='outcome_conditioned_sensitivity':key+=(tuple(row['outcome_flags']),)
        groups[key][row['phase']].append(row)
    pairs=[];coverage=[]
    for key,arms in sorted(groups.items(),key=lambda kv:repr(kv[0])):
        for arm in arms:arms[arm].sort(key=lambda r:(r['date'],r['onset_order'],r['event']))
        n=min(len(arms['FIRST']),len(arms['REPEAT']));supported=0
        for first,repeat in zip(arms['FIRST'][:n],arms['REPEAT'][:n]):
            status='supported' if first['neural_support']=='supported' and repeat['neural_support']=='supported' else 'unavailable_neural_support_no_replacement'
            supported+=status=='supported';pair={'policy':policy,'first':first['event'],'repeat':repeat['event'],'mouse':first['mouse'],'container':first['container'],'image':first['image'],'status':status}
            pairs.append(pair)
        for arm in arms:
            dispositions.extend({'event':r['event'],'status':'no_one_to_one_overlap'} for r in arms[arm][n:])
        coverage.append({'key':list(key),'first_events':len(arms['FIRST']),'repeat_events':len(arms['REPEAT']),'planned_pairs':n,'supported_pairs':supported,'unsupported_pairs':n-supported})
    used=[eid for p in pairs for eid in (p['first'],p['repeat'])]+[d['event'] for d in dispositions]
    if len(used)!=len(set(used)) or set(used)!=seen:raise ValueError('event conservation')
    return {'policy':policy,'pairs':pairs,'coverage':coverage,'dispositions':dispositions,'source_events':len(seen),
            'poststimulus_conditioned':policy=='outcome_conditioned_sensitivity','lifetime_matched':False,'session_order_matched':False,'causal_effect':False}
