"""Protected durable job, request, original process and product authentication.

This is file/operation custody, never proof of arbitrary-program no-query-fit.
All scientific qualification and deployment gates remain separately mandatory.
"""
import math
from pathlib import Path
from .io import need,exact,read,read_json,identity,canonical,write_json,bind_source

RESOURCE_KEYS=('cpu_seconds','wall_seconds','memory_bytes','input_view_bytes','scratch_bytes','trained_state_bytes','outcome_bytes','model_input_tokens','model_output_tokens','tool_calls')

def artifact(path,cap=64_000_000):
    p=Path(path).absolute();return {'path':str(p),**identity(read(p,cap))}

def get(row,cap=64_000_000):
    return read_json(row['path'],cap,row)

def numeric(value):return type(value)in(int,float)and math.isfinite(value)and value>=0

def scientific_process_only(record):
    need(record['engineering_only']is False,'An engineering child cannot qualify a scientific operation')

def validate_outer(root,request,selected,expected_record=None):
    """Validate original real exit and actual captured argv/request/source/streams."""
    root=Path(root).absolute()
    record=read_json(root/'PROCESS_RECORD.json',1_000_000,expected_record)
    need(record['schema']=='n097-original-process-v1'and record['status']=='process_completed'
         and type(record['returncode'])is int and record['returncode']==0,'Original outer must naturally complete successfully')
    need(record['launch_attempted']is True and record['process_creation_outcome']=='process_handle_observed'
         and type(record['pid'])is int and record['pid']>0,'Original dispatched process handle')
    need(not any(x.get('cleanup_unconfirmed')for x in record['cleanup']),'Original cleanup confirmed')
    need(record['request_identity']==identity(canonical(request)),'Original outer request identity')
    need(record['source_pin']==selected,'Exact selected launcher source')
    read(root/'selected_worker.py',1_000_000,selected)
    need(read_json(root/'request.json',1_000_000)==request,'Original written request')
    need(Path(record['interpreter']).is_absolute()and record['argv']==[record['interpreter'],'-I','-B',str(root/'selected_worker.py'),str(root/'request.json'),str(root/'worker_output.json')],'Exact original isolated argv')
    need(record['cwd']==str(root)and record['environment']=={'PATH':__import__('os').defpath,'PYTHONHASHSEED':'0'},'Original launch cwd/environment')
    need(numeric(record['elapsed_seconds'])and numeric(record['deadline_seconds'])and record['elapsed_seconds']<=record['deadline_seconds'],'Original outer complete elapsed allowance')
    for stream in ('stdout','stderr'):
        read(root/(stream+'.bin'),record['stream_cap'],record['streams'][stream])
    return record

def validate_fold(binding,job,contract,source_panel):
    body=get(binding)
    need(body['schema']=='n097-protected-fold-binding-v2'and body['job']==job and body['contract']==contract,'Exact protected planned job descriptor')
    need(body['source_panel_identity']==source_panel,'Same independently selected source panel')
    need(type(body['episode'])is str and body['episode'],'Original opaque episode')
    queries=body['queries'];need(type(queries)is list,'Complete original query list')
    if body['kind']!='interpretation':
        need(queries and len({q['nonce']for q in queries})==len(queries)and len({q['private_id']for q in queries})==len(queries),'Unique full fold query identity set')
    dimension={'SIGNAL':60,'PRE':60,'NUISANCE':8,'SIGNAL_NUISANCE':68,'PRE_NUISANCE':68}.get(job.get('arm'))
    def vector(value):
        need(type(value)is list and len(value)==dimension and all(type(v)in (int,float)and math.isfinite(v)for v in value),'Exact finite single-query feature vector')
    for q in queries:
        need(type(q['nonce'])is str and type(q['private_id'])is str,'Protected query join types')
        if body['kind']=='candidate':
            need(q.get('artifact'),'Every candidate query has its exact view artifact')
            value=get(q['artifact'],100_000);exact(value,['schema','opaque_episode_nonce','opaque_query_nonce','x_numeric_vector'])
            need(value['schema']=='neural097-query-v2'and value['opaque_episode_nonce']==body['episode']and value['opaque_query_nonce']==q['nonce'],'Actual one-query view identity')
            vector(value['x_numeric_vector'])
    inputs=body['inputs'];need(type(inputs)is list,'Typed original inputs')
    if body['kind']=='candidate':need(len(inputs)==1 and 'path'in inputs[0],'One exact candidate training view')
    elif body['kind']=='reference':need(len(inputs)==2 and [x.get('role')for x in inputs]==['training_view','query_views'],'Original reference training and query-batch roles')
    elif body['kind']=='interpretation':need(len(inputs)==1 and inputs[0].get('role')=='aggregate','Only fixed safe aggregate interpretation input')
    else:need(False,'Known protected fold role')
    for inp in inputs:
        item=inp.get('artifact',inp);value=get(item,100_000_000)
        if body['kind']=='interpretation':
            need(value['schema']=='n097-one-pass-interpretation-request-v1'and value['contract']==contract and value['condition']==job['condition']and value['predictions_immutable']is True and value['private_targets_exposed']is False and value['aggregate_identity']==identity(canonical(value['aggregate'])),'Exact fixed aggregate and interpretation context')
        elif inp.get('role')=='query_views':
            need(type(value)is list and len(value)==len(queries)and {x['opaque_query_nonce']for x in value}=={q['nonce']for q in queries},'Exact complete reference query-batch identity')
            for x in value:
                exact(x,['opaque_query_nonce','x_numeric_vector']);vector(x['x_numeric_vector'])
        else:
            need(value['schema']=='neural097-train-view-v2'and value['feature_arm']==job['arm']and value['opaque_episode_nonce']==body['episode']and value['contract_version']==contract and value['access_arm']==job.get('access','REFERENCE'),'Actual training view source/arm/access/episode')
            from .views import feature_columns
            need(value['feature_columns']==feature_columns(job['arm']),'Exact declared feature columns and units')
            from .io import relative
            for member in ('features_member','training_rows_member','inner_validation_plan_member'):
                a=value[member];read(Path(item['path']).parent/relative(a['path']),100_000_000,a)
    return body

def capture_fold(path,kind,job,contract,source_panel,episode,inputs,queries,knowledge_inputs=None,initial_budget=None):
    body={'schema':'n097-protected-fold-binding-v2','kind':kind,'job':job,'contract':contract,'source_panel_identity':source_panel,'episode':episode,'inputs':inputs,'queries':queries,'knowledge_inputs':knowledge_inputs or [],'initial_budget':initial_budget}
    pin=write_json(path,body,64_000_000);return {'path':str(Path(path).absolute()),**pin}

def validate_native(root,request,receipt):
    """Original qualified native observer/commands/products, never inner status alone."""
    root=Path(root)/'native';native=read_json(root/'NATIVE_ATTEMPT.json',16_000_000)
    need(native==receipt['actual_processes']and native['request_identity']==identity(canonical(request)),'Original native attempt joins receipt/request')
    need(native['status']=='physical_process_completed'and native['all_owned_absent']is True and native['monitor']['all_descendants_reaped']is True,'Original native descendants/owned resources closed')
    need(native['monitor']['source_request']==identity(canonical(request)),'Original native monitor request')
    for i,command in enumerate(native['commands'],1):
        need(command['sequence']==i and command['returncode']is not None and not command.get('cleanup_unconfirmed')and not command.get('failure'),'Original complete native command sequence')
        need(read_json(root/'commands'/f'{i:06d}.json',1_000_000)==command,'Original native command body')
        for stream in ('stdout','stderr'):read(root/'commands'/f'{i:06d}-{stream}.bin',8_000_001,command[stream])
    need(native['commands'],'Native evidence cannot be an empty receipt')
    for row in native['artifacts'].values():
        path=Path(row['path']).absolute();need(path.is_relative_to(root.absolute()),'Native product stays in original custody')
        read(path,row['bytes'],row)
    monitor=native['artifacts']['control/MONITOR.json']
    need(get(monitor,1_000_000)==native['monitor'],'Original captured monitor body')
    need(native['bound_products']==receipt['outputs'],'Original native product role binding')
    cpu=(native['monitor']['final_cgroup']['cpu_microseconds']-native['monitor']['initial_cgroup']['cpu_microseconds'])/1e6
    need(numeric(cpu)and receipt['resources']['cpu_seconds']==cpu,'Final original descendant CPU observation')
    need(receipt['resources']['memory_bytes']==native['monitor']['final_cgroup']['memory_peak_bytes'],'Original memory peak')
    return native

def validate_operation(chain,job,fold_pin,operation,query=None):
    doc=get(chain);exact(doc,['schema','root','request','outer','receipt','selection','operator_root','job','fold','operation','query'])
    need(doc['schema']=='n097-original-operation-chain-v2'and doc['job']==job and doc['fold']==fold_pin and doc['operation']==operation and doc['query']==query,'Exact planned operation/role/query chain')
    root=Path(doc['root']).absolute();need(Path(chain['path']).absolute()==root/'OPERATION.json','Original operation namespace')
    for key,name in [('request','request.json'),('outer','PROCESS_RECORD.json'),('receipt','worker_output.json')]:
        need(Path(doc[key]['path']).absolute()==root/name,'Original operation member namespace')
    req=get(doc['request'],1_000_000)
    need(req['protected_binding']==fold_pin and req['protected_job']==job and req['operation']==operation and req['opaque_query_nonce']==query,'Original request planned job and role')
    fold=validate_fold(fold_pin,job,req['contract'],get(fold_pin)['source_panel_identity'])
    need(req['opaque_episode_nonce']==fold['episode'],'Original request episode')
    if query is not None:need(query in {x['nonce']for x in fold['queries']},'Request is one expected query')
    if fold['kind']in ('reference','interpretation'):need(req['budget_remaining']==fold['initial_budget'],'Original selected noncandidate allowance')
    selection=doc['selection']
    from .execution import qualified_runtime
    qualified_runtime(selection,doc['operator_root'])
    profile=selection['runtime_profile']
    need(req['runtime_profile']==read_json(Path(doc['operator_root'])/profile['path'],2_000_000,profile),'Exact original native profile body')
    outer=validate_outer(root,req,selection['launcher'],doc['outer']);scientific_process_only(outer)
    receipt=get(doc['receipt'],16_000_000)
    need(receipt['schema']=='n097-runtime-worker-receipt-v1'and receipt['status']=='complete'and receipt['descendants_closed']is True,'Complete original receipt')
    need(receipt['request_identity']==identity(canonical(req))and receipt['contract']==req['contract'],'Original receipt contract/request')
    need(receipt['source_closure']==req['source_closure']and receipt['inputs']==req['inputs'],'Original executed source/input joins')
    need(receipt['environment']==selection['environment']==req['runtime_environment']and receipt['isolation_qualification']==selection['qualification'],'Original environment/qualification joins')
    source=req['source_closure'];checked=bind_source(source['root'],source['files'])
    need(all(source[k]==checked[k]for k in ('files','closure_sha256','total_bytes')),'Original source closure remains exact')
    for key in RESOURCE_KEYS:
        need(numeric(receipt['resources'][key])and numeric(req['budget_remaining'][key])and receipt['resources'][key]<=req['budget_remaining'][key],'Actual original resource observation within remaining allowance')
    for role,value in receipt['outputs'].items():
        closure=value if role=='training_state'else value.get('actual_source_closure')if role in ('training_program','query_program')else None
        if closure is not None:
            need(Path(closure['root']).absolute().is_relative_to(root),'State/source original output custody')
            checked=bind_source(closure['root'],closure['files']);need(all(closure[k]==checked[k]for k in checked),'Captured complete state/source bytes')
        else:
            need(Path(value['path']).absolute().is_relative_to(root),'Product original output custody');read(value['path'],req['budget_remaining']['outcome_bytes'],value)
    validate_native(root,req,receipt)
    return {'request':req,'driver_process':outer,'runtime_receipt':receipt,'receipt_identity':identity(canonical(receipt)),'chain':chain,'fold':fold}

def capture_operation(root,request,selection,operator_root):
    root=Path(root).absolute()
    body={'schema':'n097-original-operation-chain-v2','root':str(root),'request':artifact(root/'request.json',1_000_000),'outer':artifact(root/'PROCESS_RECORD.json',1_000_000),'receipt':artifact(root/'worker_output.json',16_000_000),'selection':selection,'operator_root':str(Path(operator_root).absolute()),'job':request['protected_job'],'fold':request['protected_binding'],'operation':request['operation'],'query':request['opaque_query_nonce']}
    row={'path':str(root/'OPERATION.json'),**write_json(root/'OPERATION.json',body)}
    return validate_operation(row,body['job'],body['fold'],body['operation'],body['query'])

def verify_candidate(row,job,programme):
    """Whole training->fresh-query sequence and actual prediction product joins."""
    need(row['job']==job and row['job_id']==job['id']and row['arm']==job['arm'],'Exact immutable job/arm/setting/person/half/seed')
    fold=validate_fold(row['fold_binding'],job,programme['contract'],programme['source_panel_identity'])
    need(fold['kind']=='candidate'and row['opaque_episode_nonce']==fold['episode'],'Original candidate fold role')
    joins={q['nonce']:q['private_id']for q in fold['queries']};need(row['private_query_joins']==joins,'Exact selected query universe')
    ops=row['operation_chains'];expected=1+len(joins)*(1 if job['mode']=='F'else 2)
    need(len(ops)==expected and len({x['path']for x in ops})==expected,'Every original training/query operation once')
    first=validate_operation(ops[0],job,row['fold_binding'],'train'if job['mode']=='F'else'investigate')
    need(first['request']['source_closure']==row['source_closure']and first['request']['family_policy']==row['family_policy'],'Original sealed candidate source and policy')
    need(first['request']['inputs']==fold['inputs']+fold.get('knowledge_inputs',[]),'Exact selected training inputs')
    state=first['runtime_receipt']['training_state_identity'];need(state and state['sealed_before_query']is True and state==first['runtime_receipt']['outputs']['training_state'],'Original frozen training state is the actual produced state role')
    product=get(row['prediction_artifact'],16_000_000);actual={x['opaque_query_nonce']:x for x in product['outcomes']};index=1
    need(product['opaque_episode_nonce']==fold['episode']and len(actual)==len(product['outcomes'])and set(actual)==set(joins),'Whole typed prediction query set')
    remaining=fold['initial_budget'];need(type(remaining)is dict and first['request']['budget_remaining']==remaining,'Original selected aggregate fold allowance')
    receipts=[first]
    for q in fold['queries']:
        role='predict'if job['mode']=='F'else'query_analysis';op=validate_operation(ops[index],job,row['fold_binding'],role,q['nonce']);index+=1;receipts.append(op)
        need(op['request']['source_closure']==row['source_closure'],'Original sealed query source')
        expected_inputs=[{'training_state':state},q['artifact']]
        # Knowledge input is deliberately appended by request() to every operation.
        extra=fold.get('knowledge_inputs',[])
        need(op['request']['inputs']==expected_inputs+extra,'One exact selected query plus frozen training state')
        need(op['runtime_receipt']['training_state_identity']==state,'Frozen state unchanged')
        if job['mode']=='I':
            generated=op['runtime_receipt']['outputs']['query_program'];op=validate_operation(ops[index],job,row['fold_binding'],'query_execute',q['nonce']);index+=1;receipts.append(op)
            need(op['request']['source_closure']==generated['actual_source_closure']and op['request']['entrypoints']=={'query_execute':generated['entrypoint']},'Actual captured adaptive query source')
            need(op['request']['inputs']==expected_inputs+extra and op['runtime_receipt']['training_state_identity']==state,'Adaptive execution same one query and frozen state')
        prediction=get(op['runtime_receipt']['outputs']['prediction'],100_000)
        expected_row={'opaque_query_nonce':q['nonce'],'status':prediction['status'],'p_face':prediction['p_face']}
        need(prediction['opaque_episode_nonce']==fold['episode']and prediction['opaque_query_nonce']==q['nonce']and actual[q['nonce']]==expected_row,'Collected value comes from actual original query product')
    from .execution import spend
    for op in receipts:
        need(op['request']['family_policy']==row['family_policy'],'Declared family/search/query policy unchanged throughout actual operations')
        need(op['request']['budget_remaining']==remaining,'No reset of cumulative allowance at a fresh operation')
        remaining=spend(remaining,op['runtime_receipt'])
    need(row['actual_process_receipts']==[x['receipt_identity']for x in receipts]and row['resources']==[x['runtime_receipt']['resources']for x in receipts],'Original full receipt and resource sequence')
    return receipts

def verify_reference_panel(body,programme,reference,source_panel):
    """Reconstruct a complete reference from its original1650-programme custody."""
    from .contract import ARMS
    need(body['reference']==reference and body['seed']==97097 and body['contract']==programme['contract']and body['source_panel_identity']==source_panel,'Exact reference panel source/recipe')
    expected={j['id']:j for j in programme['reference_jobs']if j['reference']==reference}
    rows=body['complete_source_process_closure']
    need(len(rows)==330 and {r['job']['id']for r in rows}==set(expected),'All330 original reference jobs')
    values={a:{}for a in ARMS}
    for row in rows:
        job=row['job'];need(job==expected[job['id']],'Exact expected original reference job')
        fold=validate_fold(row['fold_binding'],job,programme['contract'],source_panel)
        need(fold['kind']=='reference'and row['private_query_joins']=={q['nonce']:q['private_id']for q in fold['queries']},'Complete original reference fold/query universe')
        op=validate_operation(row['operation_chain'],job,row['fold_binding'],'reference_train')
        need(op['request']['inputs']==fold['inputs']and op['request']['reference_recipe']=={'reference':reference,'seed':97097},'Original reference inputs and fixed recipe')
        need(row['runtime_receipt_identity']==op['receipt_identity']and row['bank']==op['runtime_receipt']['outputs']['reference_bank'],'Original bank role and receipt bytes')
        bank=get(row['bank']);need(bank['schema']=='n097-reference-bank-v1'and bank['reference']==reference and bank['seed']==97097 and bank['contract']==programme['contract']and bank['fit']['final_fit_complete']is True and bank['numeric_state'],'Full actual source-produced reference bank')
        seen=set();joins=row['private_query_joins']
        for pred in bank['predictions']:
            nonce=pred['opaque_query_nonce'];value=pred['p_face'];need(nonce in joins and nonce not in seen and numeric(value)and value<=1,'Typed complete reference predictions')
            seen.add(nonce);key=joins[nonce];need(key not in values[job['arm']],'No reference half duplication');values[job['arm']][key]=value
        need(seen==set(joins),'No reference query omission')
    need(values==body['predictions'],'Published reference values exactly original bank products')
    need(set(values)==set(ARMS)and values['SIGNAL']and all(set(values[a])==set(values['SIGNAL'])for a in ARMS),'Full identical reference arm case universe')
    return values

def verify_failed_closure(row):
    """Global target barrier reauthenticates failed actors in every condition."""
    evidence=row['failure_closure_evidence'];need(evidence['job']==row['job'],'Original failed job closure')
    observed={str(p.absolute())for p in Path(evidence['attempt_root']).rglob('PROCESS_RECORD.json')}
    need(observed=={str(Path(x['process']['path']).absolute())for x in evidence['records']},'No original failed-job process record omitted from closure')
    if evidence['kind']=='before_dispatch':
        need(evidence['phase']=='view_preparation'and evidence['process_dispatch_attempted']is False and evidence['records']==[],'Original controller failure before any worker dispatch')
        return
    need(evidence['kind']=='original_process_records'and evidence['records'],'Every attempted original process must be accounted for')
    for item in evidence['records']:
        record=get(item['process'],1_000_000);root=Path(item['process']['path']).parent
        need(record['schema']=='n097-original-process-v1','Original failed process schema')
        for stream in ('stdout','stderr'):read(root/(stream+'.bin'),record['stream_cap']+1,record['streams'][stream])
        if record['process_creation_outcome']=='not_dispatched':
            need(record['launch_attempted']is False and record['protected_job']==row['job']and record['contract']==row['contract'],'Original no-dispatch job/contract evidence');continue
        request=read_json(root/'request.json',1_000_000)
        need(record['request_identity']==identity(canonical(request))and request['protected_job']==row['job']and request['contract']==row['contract'],'Original failed request job/contract identity')
        need(record['returncode']is not None and not any(x.get('cleanup_unconfirmed')for x in record['cleanup']),'Failed outer actually terminated')
        native=get(item['native_attempt'],16_000_000)
        need(Path(item['native_attempt']['path']).absolute()==root.absolute()/'native/NATIVE_ATTEMPT.json'and native['request_identity']==record['request_identity']and native['all_owned_absent']is True,'Failed original native descendants/owned resources closed')
        for command in native['commands']:
            seq=command['sequence'];need(read_json(root/'native/commands'/f'{seq:06d}.json',1_000_000)==command and command['returncode']is not None and not command.get('cleanup_unconfirmed'),'Original failed native command completion')
            for stream in ('stdout','stderr'):read(root/'native/commands'/f'{seq:06d}-{stream}.bin',8_000_001,command[stream])
