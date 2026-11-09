"""Complete deterministic scientific identities and source-derived resource algebra."""
import math
import common as c
import protocol as p

def grid():
    rows=[]
    for family in ('BP_LDA','TM_LDA'):
        for i,value in enumerate((.01,.1,.5,'AUTO')):rows.append({'id':family+'_'+str(i),'family':family,'shrinkage':value,'alpha':None,'gamma':None})
    for i,alpha in enumerate((.01,.1,1.,10.)):
        for j,gamma in enumerate((1/1280,1/320,4/320)):rows.append({'id':'RBF_KRR_'+str(3*i+j),'family':'RBF_KRR','shrinkage':None,'alpha':alpha,'gamma':gamma})
    return rows

def reference_jobs(index):
    p.validate_index(index)
    for view in c.VIEWS:
        for outer in c.PEOPLE:
            prefix=view+'/'+outer
            for setting in grid():
                for inner in (x for x in c.PEOPLE if x!=outer):
                    base=prefix+'/inner/'+setting['id']+'/'+inner
                    yield {'id':base+'/fit','operation':'fit','view':view,'outer':outer,'inner':inner,'configuration':setting}
                    yield {'id':base+'/infer','operation':'inner_infer','view':view,'outer':outer,'inner':inner,'configuration':setting}
            yield {'id':prefix+'/select','operation':'select','view':view,'outer':outer}
            for family in p.HANDLES:
                yield {'id':prefix+'/final/'+family+'/fit','operation':'historical'if family=='HISTORICAL_BP_LDA'else'fit','view':view,'outer':outer,'family':family,'inner':'FINAL'}
                yield {'id':prefix+'/final/'+family+'/infer','operation':'infer','view':view,'outer':outer,'family':family,'inner':'FINAL'}

def cases(index):
    p.validate_index(index)
    for view in c.VIEWS:
        for outer in c.PEOPLE:
            for mode in c.MODES:
                for replication in c.REPS:
                    for row in (r for r in index['rows']if r['person']==outer):
                        yield {'id':'case/'+mode+'/'+replication+'/'+view+'/'+row['canonical_id'],'mode':mode,'replication':replication,'view':view,'outer':outer,'canonical_id':row['canonical_id']}

def panels():
    for view in c.VIEWS:
        for person in c.PEOPLE:
            for mode in c.MODES:
                for rep in c.REPS:yield {'id':'candidate/'+mode+'/'+rep+'/'+view+'/'+person,'role':'candidate','mode':mode,'replication':rep,'view':view,'person':person}
            for handle in p.HANDLES:yield {'id':'reference/'+handle+'/'+view+'/'+person,'role':'reference','handle':handle,'view':view,'person':person}
            for handle in ('UNIFORM','LAPLACE'):yield {'id':'analytic/'+handle+'/'+view+'/'+person,'role':'analytic','handle':handle,'view':view,'person':person}

def memory(operation,n,d,q=0,family=None):
    for v in (n,d):c.integer(v,1)
    c.integer(q)
    if operation in ('fit','historical'):
        raw=512*2**20+64*n*d+256*d*d+(48*n*n if family=='RBF_KRR'else 0)
    elif operation in ('infer','inner_infer'):raw=512*2**20+32*n*d+64*q*d+32*q*12
    elif operation=='select':return 4*2**30
    else:c.need(False,'declared scientific operation')
    return math.ceil(raw/2**30)*2**30

def numerical_limits(operation,n,d,q=0,family=None):
    bound=memory(operation,n,d,q,family)
    # Logical planned allocations remain below the actual selected resident cap;
    # native library/runtime overhead is separately qualified, not equated here.
    return {'max_array_bytes':bound//2,'max_workspace_bytes':bound-128*2**20,'max_output_bytes':bound//2}

def whole_seconds(index):
    n=p.counts(index)['N'];scientific=10*3600+3680*7200+3680*900+20*300+12*n*480+3600
    provider=120*(54*n+27);author=24*60;host=86400+60*(7391+54*n+24)
    return {'scientific_native':scientific,'provider':provider,'source_author_native':author,'host_including_one_persistent_issuer':host,'normal_seconds':scientific+provider+author+host,'failure_closeout_seconds':120,'persistent_host_processes':3,'statistical_semantic_review_seconds':0}

def exact_roster(actual,expected,key='id'):
    c.need(type(actual)is list,'complete ordered roster');a=[]
    for row in actual:c.need(type(row)is dict and type(row.get(key))is str,'typed roster identity');a.append(row[key])
    wanted=[r[key]for r in expected];c.need(a==wanted and len(set(a))==len(a),'complete exact ordered roster, no subset or duplicate')
