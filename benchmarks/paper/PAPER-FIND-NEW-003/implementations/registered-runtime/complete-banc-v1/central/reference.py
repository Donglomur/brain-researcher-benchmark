"""All-family native producer orchestration and exact output provenance."""
from dataclasses import asdict
from pathlib import Path
from banc_runtime.codec import need,encode,pin,relative,parse
from banc_runtime.construct import manifest
from .io import exact_fields,read,read_json,write_json,write_diagnostic,fresh_directory,digest,metadata
from .clock import guard
from .failures import FailureEnvelope
from .storage import copy,census,checked_binding
from .method import validate_reference_plan,validate_requests
from .authority import verify_envelope
from .process import bounded_process,sandbox_argv
from .projection import project

def attempt_receipt(value):
    fields=('id','exit_code','wall_seconds','peak_rss_bytes','output_bytes','failure')
    need(value.get('observer_complete') is True and not value.get('cleanup_errors') and value.get('peak_rss_bytes') is not None and type(value.get('output_bytes')) is int and type(value.get('exit_code')) is int,'unknown process costs cannot be zero-imputed into accepted output')
    return {k:value[k] for k in fields}

def persist_process(root,name,receipt,meter):
    failure=None
    if receipt.get('observer_complete') is not True:
        failure=FailureEnvelope(ValueError('process observer/custody incomplete; native producer success suppressed'),'process_admission').attach('process_receipt',receipt)
    try:write_diagnostic(root,name,receipt,meter)
    except BaseException as exc:
        if failure is None:failure=FailureEnvelope(exc,'process_receipt_publication').attach('process_receipt',receipt)
        else:failure.add(exc,'process_receipt_publication')
    if failure is not None:raise failure
    try:guard(meter,'after_process_receipt_publication')
    except BaseException as exc:raise FailureEnvelope(exc).attach('process_receipt',receipt)

def allocate(l,meter):
    need(hasattr(meter,'cpu_seconds_limit'),'whole-attempt CPU reservation policy required')
    need(l['address_space_bytes']<=meter.address_space_ceiling and l['file_bytes']<=meter.file_bytes_ceiling,'subordinate memory/file ceiling within whole deployment')
    meter._reserve('cpu_seconds_reserved',l['cpu_seconds'],meter.cpu_seconds_limit)
    meter.reserve_read(l['read_bytes']);meter.reserve_output(l['output_bytes'])
    meter.admit_rows(l['row_count']);meter.admit_pairs(l['pair_work'])
    meter._reserve('jobs',l['jobs'],meter.limits.jobs)

def process_limits(l,meter):
    import time
    guard(meter,'before_subordinate_clock_selection')
    remaining=(meter.limits.deadline_ns-time.monotonic_ns())//10**9
    need(remaining>=1,'whole-attempt deadline leaves no process budget')
    return {**l,'wall_seconds':min(l['wall_seconds'],remaining)}

def run_reference(ctx,prepared,root,meter):
    source=ctx['source'];method=ctx['method'];input_root=ctx['roots']['input_root'];cap=ctx['deployment']['limits']['read_bytes']
    plan=validate_reference_plan(read_json(input_root,method['reference_plan'],meter),source)
    requests={j['id']:read_json(input_root,j['request'],meter) for j in plan['jobs']}
    validate_requests(plan,requests,source)
    signed=parse(metadata(input_root/relative(plan['qualification_evidence']),meter,1048576))
    q=verify_envelope(signed,ctx['keys'],ctx['deployment']['issuers']['reference'],'reference_execution')
    exact_fields(q,('source_sha256','method_sha256','reference_plan_sha256','projection_sha256','jobs'),'independent producer qualification')
    need(q['source_sha256']==source['manifest_identity']['sha256'] and q['method_sha256']==ctx['authority'].method_identity and
      q['reference_plan_sha256']==method['reference_plan']['sha256'] and q['projection_sha256']==plan['projection']['sha256'],'exact independently qualified producer/projection closure')
    need(set(q['jobs'])==set(requests),'every producer separately admitted')
    jobs={};attempts=[];jobs_root=fresh_directory(root,'jobs');logs=fresh_directory(root,'logs')
    for j in plan['jobs']:
        guard(meter,'before_reference_'+j['id']);req=requests[j['id']]
        need(all(c.isascii() and (c.isalnum() or c in '._-') for c in j['id']),'ordinary native job id')
        evidence=q['jobs'][j['id']]
        exact_fields(evidence,('request_sha256','context_qualification_sha256','original_figure','wrapper'),'job execution authority')
        need(evidence['request_sha256']==j['request']['sha256'],'exact producer request independently admitted')
        digest(evidence['context_qualification_sha256'])
        work=fresh_directory(jobs_root,j['id']);initial={};bindings={}
        failed=[dep for dep in j['dependencies'] if jobs[dep]['state']!='completed']
        if failed:
            jobs[j['id']]={'state':'required_unscorable','root':str(work),'files':{},
              'receipt':{'reason':'actual upstream producer failed','dependencies':failed,'job_not_launched':True}}
            continue
        for name,binding in req['inputs'].items():
            relative(name)
            if set(binding)=={'role','descriptor'}:
                checked_binding(name,binding,method)
                raw=read(input_root,binding['descriptor'],meter,cap);bindings[name]=binding
            else:
                exact_fields(binding,('job','file'),'upstream actual producer input')
                need(binding['job'] in j['dependencies'] and jobs[binding['job']]['state']=='completed','actual completed declared dependency')
                upstream=jobs[binding['job']];need(binding['file'] in upstream['files'],'actual upstream file')
                raw=read(upstream['root'],upstream['files'][binding['file']],meter,cap)
                bindings[name]={'role':'upstream_producer','descriptor':{'path':name,**pin(raw)}}
            initial[name]=copy(work,name,raw,meter)
        for row in req['source_context']:
            exact_fields(row,('source_member','destination'),'original source context staging')
            need(row['source_member'] in source['runtime_captured'],'only authenticated accepted source context')
            need(row['destination'] not in initial,'no context/input collision')
            initial[row['destination']]=copy(work,row['destination'],source['runtime_captured'][row['source_member']],meter)
        # Subordinate explicit jobs never silently receive a whole new budget.
        if j['kind'] in ('admission','evaluation_pending'):
            need(req['parameters']=={} and not req['inputs'] and not req['source_context'] and req['execution_authority'] is None,'controller-only stage request')
            value={'support':[j['family']], 'content': {'kind':j['kind'],'prepared_input_identity':prepared['identity'],
              'scientific_qualification':False,'protected_evaluation_pending':j['kind']=='evaluation_pending'}}
            d=write_json(work,'result.json',value,meter)
            jobs[j['id']]={'state':'completed','root':str(work),'files':{'result.json':d},'receipt':{'kind':'controller_admission','sha256':d['sha256']}}
            continue
        if req['execution_authority'] is not None:
            need(evidence['wrapper'] is not None and req['execution_authority']==evidence['wrapper']['capability'],'independently selected wrapper capability')
            d=req['execution_authority'];raw=read(input_root,d,meter,cap)
            need(d['path'] not in initial,'capability cannot replace native input/source')
            initial[d['path']]=copy(work,d['path'],raw,meter)
        else:need(evidence['wrapper'] is None,'no undeclared wrapper capability')
        if j['kind']=='original_figure':
            e=evidence['original_figure'];exact_fields(e,('program_identity','script','runtime_context_qualified','qualification_evidence_sha256','script_member'),'qualified original script context')
            member='source/primary-source/R/figures/'+req['parameters']['script']
            need(e['program_identity']==ctx['program'].selection_identity and e['script']==req['parameters']['script'] and e['runtime_context_qualified'] is True and
              e['script_member']==source['members'][member] and e['qualification_evidence_sha256']==evidence['context_qualification_sha256'],'source-owned original figure/context authority join')
        else:need(evidence['original_figure'] is None,'original context cannot qualify another producer')
        l=j['limits'];allocate(l,meter);effective=process_limits(l,meter)
        control={'schema':'banc_complete_native_worker_v1','request':req,'program':manifest(ctx['program']),
          'input_bindings':bindings,'native_authority':{'wrapper':evidence['wrapper'],'original_figure':evidence['original_figure']},
          'limits':effective,'Rscript':ctx['deployment']['sandbox']['Rscript']}
        initial['worker-control.json']=write_json(work,'worker-control.json',control,meter)
        command=[ctx['deployment']['sandbox']['python'],'-B','/programme/native_worker.py','/output/worker-control.json']
        argv=sandbox_argv(ctx['deployment']['sandbox'],role='reference',input_root=work,output_root=work,
          source_root=source['root'],command=command,meter=meter)
        meter.reserve_output(65536)
        receipt=bounded_process(argv,cwd=work,log_root=logs,name=j['id'],limits=process_limits(l,meter),meter=meter)
        persist_process(root,'receipt-'+j['id']+'.json',receipt,meter)
        # All source/data copies must survive with exact bytes. Output inventory
        # excludes immutable inputs, so an input file cannot serve as a result.
        for name,d in initial.items():read(work,d,meter,cap)
        files,total=census(work,meter,cap=l['file_bytes'],total_cap=l['output_bytes']+sum(d['bytes'] for d in initial.values()),exclude=initial)
        meter.complete_output(sum(d['bytes'] for d in files.values()))
        receipt={**receipt,'process_log_bytes':receipt['output_bytes'],
          'output_bytes':receipt['output_bytes']+sum(d['bytes'] for d in files.values())}
        write_json(root,'complete-receipt-'+j['id']+'.json',receipt,meter)
        attempts.append(attempt_receipt(receipt))
        state='completed' if receipt['exit_code']==0 else 'failed'
        if state=='completed':
            need('worker-costs.json' in files and 'result.json' in files,'actual producer completion and subordinate accounting')
            cost=read_json(work,files['worker-costs.json'],meter)
            need(cost['read_reserved']<=l['read_bytes'] and cost['output_reserved']<=l['output_bytes'],'worker stayed within original reservation')
            meter.complete_read(cost['read_completed'])
        jobs[j['id']]={'state':state,'root':str(work),'files':files,'receipt':receipt,
          'subordinate_accounting':'observed' if state=='completed' else 'unknown_after_failure_full_reservation_retained'}
    need(attempts,'reference includes actual measured producer attempts')
    projection=read_json(input_root,plan['projection'],meter)
    bundle_root=fresh_directory(root,'bundle')
    descriptor,seal=project(projection,jobs,source['contracts'],ctx['program'].selection_identity,bundle_root,attempts,
      source['manifest_identity']['sha256'],prepared['identity'],meter)
    return {'bundle_root':str(bundle_root),'bundle':descriptor,'seal_identity':seal.identity,'jobs':jobs,'attempts':attempts,
      'projection':plan['projection'],'execution_evidence':plan['qualification_evidence'],'scientific_qualification':False}
