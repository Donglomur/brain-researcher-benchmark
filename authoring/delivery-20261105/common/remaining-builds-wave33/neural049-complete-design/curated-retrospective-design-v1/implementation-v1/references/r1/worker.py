"""Actual source-owned numerical worker; parent owns independent execution authority."""
from pathlib import Path
from .budget import Budget,Failure
from .contract import environment,numpy_checked,canonical,config_admit
from .storage import Store,path_admit,pin_admit
from .features import feature_transform
from .model import fit,predict

COMMON={'schema','operation','qualified_execution','source_identity','origin','deadline',
        'input_roots','environment','batch','assigned_days','assigned_ids'}
EXTRA={'fit':{'scope','configuration','labels'},'predict':{'state'},
       'features':{'view','training_scope','statistics','temporal'}}


def request_admit(req,source_identity,origin,deadline):
    if type(req) is not dict or req.get('schema')!='neural049_r1_request_v1' or req.get('qualified_execution') is not True:
        raise ValueError('independently admitted execution absent')
    if req.get('source_identity')!=source_identity or type(source_identity) is not dict or not source_identity:
        raise ValueError('captured source identity mismatch')
    if type(req.get('origin')) not in (int,float) or type(req.get('deadline')) not in (int,float) or req['origin']!=origin or req['deadline']!=deadline:
        raise ValueError('original clock authority mismatch')
    op=req.get('operation')
    if op not in EXTRA: raise ValueError('unknown operation')
    expected=COMMON|EXTRA[op]
    parts=type(req.get('batch')) is dict and req['batch'].get('schema')=='neural049_numeric_parts_v1'
    if op=='fit' and parts: expected=expected-{'labels'}
    if set(req)!=expected: raise ValueError('exact operation fields required')
    environment(req['environment'])
    if type(req['input_roots']) is not list or not req['input_roots'] or any(type(x) is not str for x in req['input_roots']): raise ValueError('input roots')
    days,ids=req['assigned_days'],req['assigned_ids']
    if type(days) is not list or not days or any(type(x) is not int or x<=0 for x in days) or days!=sorted(set(days)): raise ValueError('assigned complete ordered days')
    if type(ids) is not list or len(ids)!=len(set(ids)) or any(type(x) is not str or not x for x in ids): raise ValueError('assigned complete rows')
    if op=='fit':
        config_admit(req['configuration']); scope=req['scope']
        if type(scope) is not dict or scope.get('training_days')!=days or scope.get('training_ids')!=ids or scope.get('environment')!=req['environment'] or scope.get('source_identity')!=source_identity:
            raise ValueError('fit scope authority differs')
        view=scope['view']
    elif op=='features':
        if type(req['training_scope']) is not bool or type(req['temporal']) is not bool or req['training_scope']!=(req['statistics'] is None): raise ValueError('features fit/query authority')
        view=req['view']
    else: view=None
    if view is not None and view not in ('C','N','NC','NC_D'): raise ValueError('view')
    return op,view


def descriptor_admit(d,shape,dtype,store):
    if type(d) is not dict or set(d)!={'path','pin','shape','dtype'} or d['shape']!=list(shape) or d['dtype']!=dtype: raise ValueError('input descriptor shape/dtype')
    pin_admit(d['pin']); path_admit(d['path'],store.roots)


def load_batch(req,view,store,np):
    spec=req['batch']; is_fit=req['operation']=='fit'
    if type(spec) is not dict: raise ValueError('batch descriptor')
    if spec.get('schema')=='neural049_numeric_parts_v1':
        if set(spec)!={'schema','parts'} or type(spec['parts']) is not list or not spec['parts']: raise ValueError('ordered complete parts')
        parts=spec['parts']
        if [x.get('day') for x in parts]!=req['assigned_days']: raise ValueError('part/day membership')
        if 'labels' in req: raise ValueError('parts forbid top-level labels')
    elif spec.get('schema')=='neural049_numeric_batch_v1':
        if set(spec)!={'schema','ids','axis','x','mask','offsets','context'}: raise ValueError('single batch descriptor fields')
        arrays={k:spec[k] for k in ('mask','offsets')}
        if view!='C': arrays['x']=spec['x']
        elif spec['x'] is not None: raise ValueError('C waveform descriptor forbidden')
        if view!='N': arrays['context']=spec['context']
        elif spec['context'] is not None: raise ValueError('N context descriptor forbidden')
        part={'day':req['assigned_days'][0],'ids':spec['ids'],'axis':spec['axis'],'arrays':arrays}
        if is_fit: part['labels']=req['labels']
        # Single aggregate's complete days are independently bound in the request.
        parts=[part]
    else: raise ValueError('unrecognized batch representation')
    all_ids=[]; axis=None; full_payload=0
    keys={'mask','offsets'}|({'x'} if view!='C' else set())|({'context'} if view!='N' else set())
    # Complete membership, label/view policy and primitive shapes BEFORE first NPY.
    for part in parts:
        if type(part) is not dict or set(part)!=({'day','ids','axis','arrays'}|({'labels'} if is_fit else set())): raise ValueError('part fields/forbidden labels')
        if type(part['day']) is not int or part['day'] not in req['assigned_days']: raise ValueError('unknown part day')
        if type(part['ids']) is not list or any(type(x) is not str or not x for x in part['ids']): raise ValueError('part row identity')
        if type(part['axis']) is not list or not part['axis'] or any(type(x) is not str or not x for x in part['axis']) or len(set(part['axis']))!=len(part['axis']): raise ValueError('channel axis')
        if axis is None: axis=part['axis']
        elif axis!=part['axis']: raise ValueError('part axis mismatch')
        all_ids.extend(part['ids']); n,c=len(part['ids']),len(axis)
        if type(part['arrays']) is not dict or set(part['arrays'])!=keys: raise ValueError('input view fields')
        expected={'mask':((n,c,5000),'bool'),'offsets':((n,),'float64'),'x':((n,c,5000),'float64'),'context':((n,6),'float64')}
        for name,d in part['arrays'].items():
            descriptor_admit(d,*expected[name],store); full_payload+=d['pin']['bytes']
        if is_fit:
            descriptor_admit(part['labels'],(n,),'float64',store); full_payload+=part['labels']['pin']['bytes']
    if all_ids!=req['assigned_ids'] or len(set(all_ids))!=len(all_ids): raise ValueError('complete assigned support mismatch')
    if is_fit and axis!=req['scope']['axis']: raise ValueError('fit full axis mismatch')
    store.budget.reserve('all-parts-retention-concatenation',allocation_bytes=full_payload*3,
                         live_bytes=full_payload*4,elements=full_payload*3,work=max(1,full_payload*4))
    blocks={k:[] for k in keys}; labels=[]
    for part in parts:
        for k in sorted(keys): blocks[k].append(store.array(part['arrays'][k],np))
        if is_fit: labels.append(store.array(part['labels'],np))
    batch={'schema':'neural049_numeric_batch_v1','ids':all_ids,'axis':axis,'x':None,'context':None}
    for k,items in blocks.items(): batch[k]=np.ascontiguousarray(np.concatenate(items,axis=0))
    target=np.ascontiguousarray(np.concatenate(labels,axis=0)) if is_fit else None
    store.budget.tick(); return batch,target


def worker_run(request_path,expected_request_pin,source_identity,origin,deadline,limits,output_root):
    budget=Budget(origin,deadline,limits)
    store=None; root_created=False; primary=None; later=[]
    try:
        # Bootstrap only opens the independently pinned request, before any
        # candidate/input/output operand. No bool alone authenticates a run.
        boot=Store(budget,[str(path_admit(request_path).parent)])
        req=boot.json({'path':request_path,'pin':expected_request_pin},request=True)
        op,view=request_admit(req,source_identity,origin,deadline)
        store=Store(budget,req['input_roots'])
        np=numpy_checked(req['environment'])
        state=None
        if op=='predict':
            state=store.load_tree(req['state'],np)
            if state['meta']['scope']['environment']!=req['environment'] or state['meta']['scope']['source_identity']!=source_identity: raise ValueError('state environment/source differs')
            view=state['meta']['scope']['view']
        batch,labels=load_batch(req,view,store,np)
        if op=='fit':
            result=fit(req['scope'],batch,labels,req['configuration'],budget)
            result['meta']['worker_input_lineage']={'request':expected_request_pin,'batch':req['batch'],
                'labels':req.get('labels'),'assigned_days':req['assigned_days'],'assigned_ids':req['assigned_ids'],
                'source_identity':source_identity,'environment':req['environment']}
        elif op=='predict': result=predict(state,batch,budget)
        else:
            statistics=None if req['statistics'] is None else store.load_tree(req['statistics'],np)
            values,stats=feature_transform(batch,view,budget,req['environment'],statistics,req['temporal'])
            result={'features':values,'statistics':stats,'ids':batch['ids'],'view':view,'training_scope':req['training_scope']}
        store.fresh_root(output_root); root_created=True
        output=store.save_tree(result,np,'STATE.json' if op!='predict' else 'RESULT.json')
        work=store.write_json('WORK.json',{'status':'numerical_operation_and_artifacts_completed',
                             'operation':op,'request':expected_request_pin,'source_identity':source_identity,
                             'budget_pre_work_publication':budget.snapshot()})
        receipt=store.write_json('RECEIPT.json',{'schema':'neural049_r1_receipt_v1','operation':op,
                                'request':expected_request_pin,'source_identity':source_identity,
                                'assigned_days':req['assigned_days'],'assigned_ids':req['assigned_ids'],
                                'batch':req['batch'],'input_state':req.get('state'),
                                'root':str(store.root),'result':output,'work':work,
                                'artifacts_before_receipt':list(store.outputs),
                                'budget_pre_receipt_publication':budget.snapshot(),
                                'independent_process_closure_required':True})
        budget.tick()
        return {'receipt':receipt,'artifacts':list(store.outputs),'budget':budget.snapshot()}
    except BaseException as e:
        primary=e
        # No automatic retry or overwritten artifacts. Failure publication is
        # optional and cannot hide primary errors or the final attempted costs.
        if root_created:
            try:
                store.write_json('FAILURE.json',{'status':'failed','error_type':type(e).__name__,
                                  'error':str(e),'prior_later':getattr(e,'later',[]),
                                  'budget_pre_failure_publication':budget.snapshot()})
            except BaseException as close: later.append(repr(close))
        raise Failure(str(primary),budget.snapshot(),getattr(primary,'later',[])+later) from primary
