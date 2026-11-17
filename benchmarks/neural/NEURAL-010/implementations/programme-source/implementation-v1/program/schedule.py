"""Exact full scientific job identities; ordering is an access barrier."""
import itertools
import common as c

STRONG=('candidate','matched_no_eeg')
FIT_COUNTS={'candidate':4577,'matched_no_eeg':4577,'montage_only':529,'signal_reference':23}

def support(rows):
    c.need(type(rows)is list and len(rows)==c.RECORDS,'complete686-record metadata')
    seen=set();people=set()
    for row in rows:
        c.ident(row['recording_id']);c.ident(row['patient_id']);c.integer(row['duration_seconds'],1,86400)
        c.need(row['recording_id']not in seen,'unique record identity');seen.add(row['recording_id']);people.add(row['patient_id'])
    c.need(len(people)==c.PEOPLE,'complete23 biological people');return sorted(people)

def job_id(outer,arm,kind,inner=None,grid=None):
    c.ident(outer);c.need(arm in c.ARMS,'selected stream');c.need(kind in('fit','infer','validate','select'),'selected job kind')
    if inner is not None:c.ident(inner);c.need(inner!=outer,'outer labels cannot enter an inner query')
    if grid is not None:c.integer(grid,0,8)
    return '/'.join([outer,arm,'final'if inner is None else inner,'none'if grid is None else str(grid),kind])

def reference_jobs(rows):
    """Every fit is followed by sealed inference, then authorized validation.

    This is a generator to avoid materializing numerical arrays or a large work
    graph. The iterator contains no targets and never calls a producer.
    """
    people=support(rows)
    for row in sorted(rows,key=lambda r:r['recording_id']):
        yield {'id':'features/'+row['recording_id'],'kind':'features','recording_id':row['recording_id']}
    for outer in people:
        inner_people=[p for p in people if p!=outer]
        for arm in c.ARMS:
            grids=range(9)if arm in STRONG else(None,)
            if arm!='signal_reference':
                for inner in inner_people:
                    for grid in grids:
                        fit=job_id(outer,arm,'fit',inner,grid);infer=job_id(outer,arm,'infer',inner,grid)
                        context={'outer':outer,'inner':inner,'arm':arm,'grid':grid,'training_people':[p for p in people if p not in(outer,inner)],'query_people':[inner]}
                        yield {**context,'id':fit,'kind':'fit','dependencies':[]}
                        yield {**context,'id':infer,'kind':'infer','dependencies':[fit]}
                        yield {**context,'id':job_id(outer,arm,'validate',inner,grid),'kind':'validate','dependencies':[fit,infer]}
                selection=job_id(outer,arm,'select')
                validations=[job_id(outer,arm,'validate',inner,grid)for inner in inner_people for grid in grids]
                yield {'id':selection,'kind':'select','outer':outer,'arm':arm,'inner':None,'grid':None,'training_people':inner_people,'query_people':[],'dependencies':validations}
            else:selection=None
            fit=job_id(outer,arm,'fit');context={'outer':outer,'inner':None,'arm':arm,'grid':None,'training_people':inner_people,'query_people':[outer]}
            yield {**context,'id':fit,'kind':'fit','dependencies':[]if selection is None else[selection]}
            yield {**context,'id':job_id(outer,arm,'infer'),'kind':'infer','dependencies':[fit]}

def expected_counts():return {'features':686,'fit':9706,'infer':9706,'validate':9614,'select':69,'fixed_reference_native_processes':29781,'final_fold_streams':92,'merged_streams':4,'fixed_authors':3,'adaptive_authors':6,'analyst_executions':12}
def analyst_contexts():
    for mode,replication,view in itertools.product(c.MODES,range(3),c.VIEWS):
        yield {'id':mode+'/'+str(replication)+'/'+view,'mode':mode,'replication':replication,'view':view,'fixed_author':'fixed-author/'+str(replication)if mode=='frozen_program'else None}

def dispositions(expected,entered,completed,failed):
    expected=list(expected);c.need(len(expected)==len(set(expected)),'unique exact phase roster')
    en=set(entered);co=set(completed);fa=set(failed)
    c.need(len(en)==len(entered)and len(co)==len(completed)and len(fa)==len(failed)and en<=set(expected)and co<=en and fa<=en and not(co&fa),'disjoint typed phase disposition')
    return {'completed':sorted(co),'failed':sorted(fa),'entered_incomplete':sorted(en-co-fa),'unentered':sorted(set(expected)-en)}

def complete_reference_admission(rows,operations):
    """Exact ordered job graph, complete bodies are admitted separately."""
    c.need(type(operations)is list,'complete observed operations')
    iterator=iter(operations);counts={k:0 for k in('features','fit','infer','validate','select')};fits={k:0 for k in c.ARMS};last=None
    for expected in reference_jobs(rows):
        actual=next(iterator,None);c.need(type(actual)is dict and c.typed_equal(actual.get('job'),expected),'exact complete ordered producer identity/role/dependencies')
        c.need(actual.get('status')=='completed'and type(actual.get('returncode'))is int and actual['returncode']==0 and actual.get('natural_completion')is True and actual.get('unknown_survivors')is False,'genuine natural complete producer')
        c.need(actual.get('previous')==last,'exact operation chain');c.descriptor(actual['record']);last=actual['record'];counts[expected['kind']]+=1
        if expected['kind']=='fit':fits[expected['arm']]+=1
    c.need(next(iterator,None)is None,'no extra producer')
    c.need(c.typed_equal(fits,FIT_COUNTS)and all(counts[k]==expected_counts()[k]for k in counts),'complete exact reference scientific graph')
    return {'counts':counts,'fit_counts':fits,'last':last,'full_support':True}
