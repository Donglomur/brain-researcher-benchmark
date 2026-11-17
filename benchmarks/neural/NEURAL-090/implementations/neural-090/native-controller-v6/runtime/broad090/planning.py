"""Deterministic source-only fitting/calibration masks and shared-event audit."""
import hashlib,math
from collections import defaultdict
from programme.contracts import need
from .protocol import Case

def event_id(row):return '/'.join((*row['run_key'],row['source_idx']))
def rank(row):return (hashlib.sha256(('N090-BROAD-v1:'+event_id(row)).encode()).hexdigest(),event_id(row))
def sorted_rows(rows):return tuple(sorted(rows,key=rank))
def quota(rows,n):
    rows=sorted_rows(rows);need(len(rows)>=n,'full fixed label quota unavailable; no partial case')
    return rows[:n]

def source_inner_split(rows,index):
    people=sorted({r['person'] for r in rows},key=lambda p:(hashlib.sha256(('N090-TUNE:'+p).encode()).hexdigest(),p))
    if len(people)>1:
        count=max(1,math.ceil(len(people)/5));tune_people=set(people[-count:])
        train=tuple(r for r in rows if r['person'] not in tune_people)
        tune=tuple(r for r in rows if r['person'] in tune_people)
        guard=()
    else:
        train=[];tune=[];guard=[]
        for r in rows:
            run=index[tuple(r['run_key'])];cut=(run.clock.sample_count*4)//5;start=r['start_sample']
            if start+125<=cut-250:train.append(r)
            elif start>=cut+250:tune.append(r)
            else:guard.append(r)
        train,tune,guard=tuple(train),tuple(tune),tuple(guard)
    need(train and tune,'nonempty independent inner source roles')
    return train,tune,guard

def case_plan(case,events_by_run,index):
    need(type(case) is Case,'selected full-scope case')
    allrows=tuple(r for rows in events_by_run.values() for r in rows)
    ids=[event_id(r) for r in allrows];need(len(ids)==len(set(ids)),'complete unique original row identities')
    # Match source-subject via run key, keeping biological person separately.
    query=tuple(r for r in allrows if r['run_key'][0]==case.person and r['chapter']==case.query_chapter)
    opposite=tuple(r for r in allrows if r['run_key'][0]==case.person and r['chapter']==case.source_chapter)
    need(query and opposite,'full two-chapter target-person support')
    if case.axis=='held_chapter':source=opposite
    elif case.axis=='joint_person_held_chapter':source=tuple(r for r in allrows if r['run_key'][0]!=case.person and r['chapter']==case.source_chapter)
    else:source=tuple(r for r in allrows if r['run_key'][0]!=case.person)
    inner_train,inner_tune,guard=source_inner_split(source,index)
    if case.axis=='held_chapter' and case.budget=='1024':
        inner_train,inner_tune=quota(inner_train,819),quota(inner_tune,205)
        final_source=(*inner_train,*inner_tune)
    else:final_source=source
    calibration=quota(opposite,case.calibration_count) if case.calibration_count else ()
    roles={'inner_train':sorted_rows(inner_train),'inner_tune':sorted_rows(inner_tune),
           'source_refit':sorted_rows(final_source),'calibration':sorted_rows(calibration),'query':sorted_rows(query)}
    qevents={r['canonical_event'] for r in query};qwords={r['canonical_word'] for r in query}
    overlap={name:sorted(qevents&{r['canonical_event'] for r in rows}) for name,rows in roles.items() if name!='query'}
    if case.primary_eligible:
        need(not any(overlap.values()),'global original event closure before target exposure')
        need(all(r['chapter']!=case.query_chapter for name,rows in roles.items() if name!='query' for r in rows),'held chapter absent in every source/CAL role')
    # CAL is disjoint from query for every axis, even the exposed person route.
    need(not overlap['calibration'],'calibration never reveals a remaining query-event label through duplicates')
    need({event_id(r) for r in inner_train}.isdisjoint(event_id(r) for r in inner_tune),'inner TRAIN/TUNE identity disjoint')
    need({event_id(r) for r in final_source}.isdisjoint(event_id(r) for r in calibration),'source/CAL identity disjoint')
    source_groups=defaultdict(list)
    for r in source:source_groups[r['canonical_event']].append(event_id(r))
    oracle={event_id(q):source_groups.get(q['canonical_event'],[]) for q in query}
    exposed_words={event_id(q):q['canonical_word'] for q in query}
    role_ids={name:{event_id(x) for x in rows} for name,rows in roles.items()}
    disposition={event_id(r):[name for name,chosen in role_ids.items() if event_id(r) in chosen] for r in allrows}
    return {'schema':'n090-case-plan-v1','case':case.key,'axis':case.axis,'budget':case.budget,
            'roles':{k:[event_id(r) for r in v] for k,v in roles.items()},
            'counts':{k:len(v) for k,v in roles.items()},'all_row_disposition':disposition,
            'inner_guard':[event_id(r) for r in guard],'shared_query_event_overlap':overlap,
            'same_event_donor_label_audit':oracle,'query_word_identity_private':exposed_words,
            'primary_eligible':case.primary_eligible,'person_condition':'exposed_within_narrative' if not case.primary_eligible else 'held_chapter',
            'calibration_unique_labels':len(calibration),'source_unique_labels':len(final_source),
            'source_refit_restores_inner_guard':case.budget=='full' and case.axis=='held_chapter',
            'context_exposure':'audio and transcript are stimulus-exposed diagnostics; protected captures seal first',
            'scientific_execution':False}

def interval_union(rows):
    """Exact admitted TRAIN sample union; overlaps charged once per recording."""
    byrun=defaultdict(list)
    for r in rows:byrun[tuple(r['run_key'])].append((r['start_sample'],r['start_sample']+125))
    result={}
    for key,intervals in byrun.items():
        merged=[]
        for a,b in sorted(intervals):
            need(type(a) is int and type(b) is int and 0<=a<b,'source sample intervals')
            if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
            else:merged.append((a,b))
        result[key]=tuple(merged)
    return result

def shifted_donors(rows):
    """Nearest >=5s-separated selected window in same recording and role.

    No circular wrapping, label use, cross-role fallback or independence claim.
    Donor reuse is explicit. The entire case refuses if any row has no donor.
    """
    groups=defaultdict(list)
    for row in rows:groups[tuple(row['run_key'])].append(row)
    from bisect import bisect_left,bisect_right
    result={}
    for group in groups.values():
        bystart={}
        for row in group:
            start=row['start_sample']
            if start not in bystart or rank(row)<rank(bystart[start]):bystart[start]=row
        starts=sorted(bystart)
        for row in group:
            start=row['start_sample'];left=bisect_right(starts,start-1250)-1;right=bisect_left(starts,start+1250)
            options=[]
            if left>=0:options.append(bystart[starts[left]])
            if right<len(starts):options.append(bystart[starts[right]])
            need(options,'fixed time-shift donor unavailable; preserve whole-case unsupported')
            donor=min(options,key=lambda r:(abs(r['start_sample']-start),rank(r)))
            result[event_id(row)]=event_id(donor)
    return result
