"""Complete native reference campaign and dispatch; no scientific execution during BUILD."""
from pathlib import Path
import os
from .guard import need,capture,capture_created,strict,encoded,bare,Publisher,Unscorable,ordinary
from .source import source_bytes
from .scope import compile_jobs
from .controller import run_owned,Journal
from .array_io import verify_file

def organize(plan,completed,root,budget):
    out={key:{} for key in ('brain','features','rdm','rsa','null')}
    byid={x['id']:x for x in plan['jobs']}
    for jobid,desc in completed.items():
        row=strict(capture(root,desc,budget));job=byid[jobid];kind=job['kind']
        if kind=='brain':key=(job['panel'],job['subject'],job['roi'])
        elif kind=='features':key=(job['panel'],job['model'])
        elif kind=='rdm':key=jobid.removeprefix('rdm:')
        elif kind=='rsa':key=(job['condition'],job['roi'])
        elif kind=='null':key=(job['model'],job['roi'])
        else:continue
        need(row['job']==jobid and row['plan']==bare(encoded(plan)),'actual receipt bound to full plan')
        out[kind][key]=row['result']
    return out

def dispatch(package,inputs_root,scope,inputs,authority,plan,job,completed,budget,output):
    """One selected job. Real native producers, never an injectable callback."""
    from . import native,consumer_production
    need(job in plan['jobs'],'selected full-plan job')
    need(set(job['dependencies'])<=set(completed),'all original dependencies completed')
    publisher=Publisher(output,budget);session=None
    try:
        receipts=organize(plan,completed,inputs_root,budget)
        session=native.NativeSession(inputs_root,inputs,authority,budget)
        panel=job.get('panel');model=job.get('model');kind=job['kind']
        if kind=='brain':
            row=next(x for x in inputs['panels'][panel]['brain'] if x['subject']==job['subject'] and x['roi']==job['roi']);result=native.brain(session,panel,row,publisher)
        elif kind=='features':
            protocol=strict(source_bytes(package,'source-donors/metadata/PROTOCOL.json',budget))
            config=next((x['config'] for x in protocol['models'] if x['id']==model),None)
            if config is None:config=strict(capture(inputs_root,inputs['auxiliary_configuration'],budget))
            result=native.features(session,panel,model,config,publisher)
        elif kind=='rdm':
            condition={k:job[k] for k in ('panel','method','model','role')};condition['id']=job['id'].removeprefix('rdm:')
            result=native.model_rdms(session,condition,receipts['features'][(panel,model)],publisher)
        elif kind in ('rsa','null'):
            condition=job['condition'] if kind=='rsa' else 'test:pca:'+model
            rdms=receipts['rdm'][condition];brains=[receipts['brain'][(panel,s,job['roi'])] for s in scope['subjects']]
            if kind=='rsa':result=native.rsa(session,rdms,brains,publisher)
            else:
                schedule=strict(capture(inputs_root,inputs['permutation_schedule'],budget));result=native.nulls(session,rdms,brains,schedule,publisher)
        elif kind=='consume':
            schedule=strict(capture(inputs_root,inputs['permutation_schedule'],budget));result=consumer_production.production(session,package,scope,receipts,schedule,publisher)
        elif kind=='report':
            previous=strict(capture(inputs_root,completed['consume'],budget))
            need(previous['job']=='consume' and previous['plan']==bare(encoded(plan)),'original collection identity')
            result={'schema':'hundred_models_scientific_report_v1','scope':bare(encoded(scope)),'consumer':previous['result'],'all_figures_required':list(range(1,23)),'tables_required':[1,2],'scientific_qualification':False,'historical_parity':False,'improvement':'requires independent panel and explicit G17/G18 population/uncertainty selection','source_execution_only_claim':'A completed source campaign does not itself qualify scientific conclusions.'}
        else:raise ValueError('closed native job dispatch')
        session.close();budget.check()
        receipt={'schema':'hundred_models_original_job_receipt_v1','job':job['id'],'plan':bare(encoded(plan)),'result':result,'source_scope':bare(encoded(scope)),'inputs':bare(encoded(inputs)),'budget':budget.snapshot(),'output_custody':publisher.state()}
        return publisher.write('RECEIPT.json',encoded(receipt))
    except BaseException as error:
        error.known_output_prefix=publisher.state();error.add_note('Original owned job failure; no completed receipt or scientific result inferred.')
        raise

def execute_reference(package,root,scope,inputs,authority,budget,output,source_pin):
    plan=compile_jobs(scope,inputs);need(authority['plan']==bare(encoded(plan)),'selected whole immutable reference plan')
    need(authority['source']==source_pin,'selected full runtime source closure')
    publisher=Publisher(output,budget);journal=Journal(publisher,plan);completed={}
    # All job files are rooted beneath the externally mounted input/output workspace.
    root=Path(root).absolute();package=Path(package).absolute();output=Path(output).absolute()
    need(output.is_relative_to(root) and package.is_relative_to(root),'source/output roots in declared isolated workspace')
    binary=verify_file(root,authority['python_binary'],budget)
    for ordinal,job in enumerate(plan['jobs']):
        journal.admit_job(job);jobdir=output/f'work_{ordinal:05}'
        request={'schema':'hundred_models_job_request_v1','job':job,'plan':plan,'scope':scope,'inputs':inputs,'authority':authority,'completed':completed,'output':str(jobdir.relative_to(root)),'limits':inputs['job_limits']}
        request_desc=publisher.write(f'request_{ordinal:05}.json',encoded(request));request_desc['path']=str((output/request_desc['path']).relative_to(root))
        argv=[str(binary),'-I','-S','-B',str(package/'entry.py'),'worker','--root',str(root),'--source-bytes',str(source_pin['bytes']),'--source-sha256',source_pin['sha256'],'--request',request_desc['path'],'--request-bytes',str(request_desc['bytes']),'--request-sha256',request_desc['sha256'],'--deadline-ns',str(budget.deadline_ns),'--bootstrap-read-bytes',str(inputs['job_limits']['read_bytes'])]
        env={'PATH':inputs['native_PATH'],'LC_ALL':'C','PYTHONHASHSEED':str(inputs['hash_seed']),'MPLBACKEND':'Agg'}
        try:
            observation=run_owned(argv,str(package),env,budget,stream_limit=inputs['stream_limit_bytes'],limits=inputs['process_limits'])
            receipt_path=jobdir/'RECEIPT.json';body,receipt=capture_created(root,str(receipt_path.relative_to(root)),budget,cap=16*1024*1024)
            parsed=strict(body);need(parsed['job']==job['id'] and parsed['plan']==bare(encoded(plan)),'independent actual child receipt identity')
            journal.complete(job,receipt,observation);completed[job['id']]=receipt
        except BaseException as error:
            journal.failed=True;error.campaign_prefix={'completed':dict(completed),'failed_job':job['id'],'output':publisher.state()};raise
    return journal.final()
