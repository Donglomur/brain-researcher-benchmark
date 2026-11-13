"""Concrete inactive operator. Execution requires a separate root selection."""
import time
ORIGIN=time.monotonic()
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import types

INHERITED_PIN = {'bytes': 6555, 'sha256': '8bde43ff2b45b4af5ce7dee721761a4e2efa3d9dcc659f17ce65575611cf2095'}
EVIDENCE_LIMITS={'read_bytes':16777216,'write_bytes':16777216,'retained_bytes':16777216}
OWNER_PREFLIGHT_READS=33554432
FAILURE_CAP=2097152


def operation_envelope(limits):
    return dict(worker=dict(limits),owner_preflight_read_bytes=OWNER_PREFLIGHT_READS,
        owner_evidence=dict(EVIDENCE_LIMITS),worker_failure_evidence=dict(EVIDENCE_LIMITS),
        read_upper_bound=limits['reads']+OWNER_PREFLIGHT_READS+2*EVIDENCE_LIMITS['read_bytes'],
        write_upper_bound=limits['writes']+2*EVIDENCE_LIMITS['write_bytes'],
        retained_upper_bound=limits['retained']+2*EVIDENCE_LIMITS['retained_bytes'],
        additive_envelopes=True,overlapping_bootstrap_reads_conservatively_reserved_twice=True)


def failure_payload(error,source,operation):
    return dict(schema='neural083_adaptive_actual_worker_failure_v1',source=source,operation=operation,
        first_error={'type':type(error).__name__,'message':str(error)[:2048]},
        additional_notes=[str(note)[:2048] for note in getattr(error,'__notes__',[])[:16]],
        actual_failure=getattr(error,'adaptive_actual_failure',None),
        actual_provider_receipt=getattr(error,'receipt',getattr(error,'provider_actual_receipt',None)),
        automatic_retry=False)


def publish_worker_failure(ctx,error,evidence,source,operation,emit):
    # Uses the already selected outer evidence deadline, never renews work time.
    raw=ctx['io'].encoded(failure_payload(error,source,operation))
    if len(raw)>FAILURE_CAP:
        error.add_note('Actual failure exceeds preselected outer failure cap')
        return None
    try:return ctx['io'].put(evidence/'WORKER_FAILURE.json',raw,ctx['metadata_budget'])
    except BaseException as publication:
        error.add_note('Reserved worker failure publication failed: '+type(publication).__name__)
        try:
            raw=ctx['io'].encoded(failure_payload(error,source,operation))
            if len(raw)>FAILURE_CAP:raise ValueError('bounded exact failure fallback')
            ctx['metadata_budget'].write(len(raw));emit(raw)
        except BaseException as secondary:error.add_note('Owned failure stream also failed: '+type(secondary).__name__)
        return None


def launch(ctx,file,body,args,origin,normal_end,cleanup_end,output):
    owner=ctx['owner'];bridge=ctx['bridge'];budget=ctx['metadata_budget']
    argv=bridge.child_argv(file,body,origin,args)
    try:record=owner.run(argv,normal_end=normal_end,cleanup_end=cleanup_end,
        env=bridge.environment(),metadata_read=budget.read,stream_cap=2621440)
    except owner.ChildFailure as error:
        try:bridge.publish_child(output,error.record,budget)
        except BaseException as publication:error.add_note('Actual child publication failed: '+type(publication).__name__)
        raise
    bridge.publish_child(output,record,budget);bridge.natural(record);return record


def initial(path,expected,cap):
    p=Path(path).absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('unlinked source/configuration path')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:
            raise ValueError('bounded ordinary source')
        chunks=[];left=a.st_size+1
        while left:
            b=os.read(fd,min(left,65536))
            if not b:break
            chunks.append(b);left-=len(b)
        body=b''.join(chunks);z=os.fstat(fd);n=p.lstat()
        fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        if len(body)!=a.st_size or any(getattr(a,k)!=getattr(z,k) or getattr(z,k)!=getattr(n,k) for k in fields):
            raise ValueError('stable source/configuration capture')
        if expected is not None and {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}!=expected:
            raise ValueError('exact selected source/configuration pin')
        return body
    finally:os.close(fd)


def module(body,path,**bindings):
    m=types.ModuleType('neural083_adaptive_'+Path(path).stem);m.__file__=str(path)
    m.__dict__.update(bindings);exec(compile(body,str(path),'exec'),m.__dict__);return m


def load(root,source,end):
    raw=initial(root/'SOURCE.json',source,262144);manifest=json.loads(raw);spent=len(raw)
    if (set(manifest)!= {'schema','files','inherited'}
        or manifest['schema']!='neural083_case_adaptive_source_v1' or manifest['inherited']!=INHERITED_PIN
        or type(manifest['files'])is not dict or len(manifest['files'])>32):
        raise ValueError('complete selected actor source closure')
    bodies={}
    for name,pin in manifest['files'].items():
        if Path(name).name!=name:raise ValueError('local actor source basename')
        body=initial(root/name,pin,1048576);spent+=len(body)
        if spent>4194304:raise ValueError('bounded actor source closure')
        bodies[name]=body
    inherited=root/'inherited'
    raw=initial(inherited/'SOURCE.json',INHERITED_PIN,131072);spent+=len(raw);old=json.loads(raw)
    entry_body=initial(inherited/'entry.py',old['files']['entry.py'],65536);spent+=len(entry_body)
    old_entry=module(entry_body,inherited/'entry.py')
    io,metadata_budget,_,inherited_bodies,owner,bridge=old_entry.load(inherited,INHERITED_PIN,
        dict(EVIDENCE_LIMITS),end)
    metadata_budget.read(spent)
    c,contracts,_policy,programme_bodies=bridge.programme(inherited,inherited_bodies)
    here=inherited/'program'
    scientific=c.module(programme_bodies,'scientific_protocol.py',here)
    store=c.module(programme_bodies,'store.py',here,c=c,contracts=contracts,scientific=scientific)
    native=c.module(programme_bodies,'native.py',here,c=c)
    comparison=c.module(programme_bodies,'comparison.py',here)
    core='scientific-source/reference_core.py'
    ctx=dict(io=io,metadata_budget=metadata_budget,owner=owner,bridge=bridge,c=c,contracts=contracts,bodies=bodies,
        store=store,native=native,comparison=comparison,programme_bodies=programme_bodies,
        reference_core=inherited_bodies[core],inherited_root=inherited,inherited_bodies=inherited_bodies)
    for name in ('actor','native_tools','programme','admission','configuration','budget','query_budget','adaptive_owner'):
        ctx[name]=module(bodies[name+'.py'],root/(name+'.py'))
    ctx['owner']=ctx['adaptive_owner']
    ctx['provider']=module(bodies['local_chat_provider.py'],root/'local_chat_provider.py')
    return ctx,bodies


def authorize(c,authority,source,request,operation):
    if not (type(authority)is dict and set(authority)=={'schema','source','request','operation','execution_authorized'}
        and authority['schema']=='neural083_adaptive_root_authority_v1' and authority['source']==source
        and authority['request']==request and authority['operation']==operation
        and authority['execution_authorized'] is True):
        raise ValueError('separate exact root authority required')


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('operation',choices=('inspect','run','grade'))
    parser.add_argument('--source-pin',required=True);parser.add_argument('--request',required=True)
    parser.add_argument('--authority');parser.add_argument('--whole-seconds',type=int,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--origin',type=float)
    args=parser.parse_args();origin=ORIGIN if args.origin is None else args.origin
    if not (type(origin)is float and 0<=ORIGIN-origin<30 and 30<args.whole_seconds<=604800):
        raise ValueError('original finite operator interval')
    deadline=origin+args.whole_seconds;root=Path(__file__).absolute().parent
    source=json.loads(args.source_pin);request_spec=json.loads(args.request)
    ctx,bodies=load(root,source,deadline);c=ctx['c'];io=ctx['io'];owner=ctx['owner'];bridge=ctx['bridge']
    raw=initial(request_spec['path'],c.only_pin(request_spec),1048576)
    ctx['metadata_budget'].read(len(raw));request=c.parse(raw)
    c.need(set(request)=={'schema','operation','configuration','evidence_output','grade_inputs'}
        and request['schema']=='neural083_adaptive_operator_request_v1'
        and request['operation']==args.operation,'exact source-bound operator request')
    if args.operation=='inspect':
        c.need(args.authority is None and not args.worker,'source inspection only')
        print(json.dumps(dict(source=source,inherited=INHERITED_PIN,operations=['run','grade'],
            full_conditions=2592,candidate_query_actors=129600,execution_selected=False)))
        return 0
    c.need(args.authority is not None,'separate exact root authority required')
    authority_spec=json.loads(args.authority)
    a=initial(authority_spec['path'],c.only_pin(authority_spec),32768)
    ctx['metadata_budget'].read(len(a));authorize(c,c.parse(a),source,c.only_pin(request_spec),args.operation)
    configuration_raw=initial(request['configuration']['path'],c.only_pin(request['configuration']),1048576)
    ctx['metadata_budget'].read(len(configuration_raw));configuration=c.parse(configuration_raw)
    worker_end=deadline-30
    budget_root=configuration['output'] if args.operation=='run' else request['evidence_output']
    active_limits=dict(configuration['limits'])
    if not args.worker:active_limits.update(reads=OWNER_PREFLIGHT_READS,writes=0,retained=16777216)
    budget=ctx['budget'].Budget(c.path(budget_root),
        configuration['other_future_bytes']+2*EVIDENCE_LIMITS['retained_bytes'],worker_end,active_limits)
    ctx['budget']=budget
    selection,provider_config,prompt,frozen,joined=ctx['configuration'].select(ctx,configuration,source,
        ctx['inherited_root'],ctx['inherited_bodies'],budget)
    ctx.update(provider_config=provider_config,prompt=prompt,frozen_program=frozen)
    c.need(selection['limits']['whole_seconds']==args.whole_seconds
        and selection['limits']['observer_seconds']==30,'same original source-selected whole interval')
    budget.read(ctx['metadata_budget'].reads)
    evidence=c.path(request['evidence_output'])
    for protected in (c.path(joined['value']['canonical_root']),c.path(joined['value']['canonical']['path']).parent):
        c.need(evidence!=protected and evidence not in protected.parents and protected not in evidence.parents,
               'outer evidence disjoint from original records and protected products')
    def expire(*_):raise TimeoutError('original adaptive operation deadline')
    previous={n:signal.getsignal(n) for n in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    for n in previous:signal.signal(n,expire)
    signal.setitimer(signal.ITIMER_REAL,max(.001,(worker_end if args.worker else deadline)-time.monotonic()))
    output=None;child=None
    try:
        if not args.worker:
            output=io.fresh_directory(request['evidence_output'])
            target=c.path(selection['output'])
            c.need(target!=output and target not in output.parents and output not in target.parents,
                   'disjoint programme and outer evidence roots')
            extra=sys.argv[1:]+['--worker','--origin',repr(origin)]
            child=launch(ctx,root/'entry.py',bodies['entry.py'],extra,origin,
                deadline-15,deadline-5,output)
            terminal=c.parse(base64.b64decode(child['stdout_base64'],validate=True))
            c.need(terminal['schema']=='neural083_adaptive_worker_terminal_v1'
                and terminal['operation']==args.operation and terminal['source']==source,
                'exact naturally closed complete worker terminal')
            receipt=io.put(output/'OUTER.json',io.encoded(dict(schema='neural083_adaptive_outer_v1',
                source=source,request=c.only_pin(request_spec),configuration=c.only_pin(request['configuration']),
                operation=args.operation,worker_terminal=terminal,child=child,grading_authorized=False,
                scientific_qualified=False,operation_envelope=operation_envelope(configuration['limits']),
                owner_preflight=budget.record(),owner_evidence=dict(reads=ctx['metadata_budget'].reads,
                    writes=ctx['metadata_budget'].writes))),ctx['metadata_budget'])
            print(json.dumps(dict(status='complete_unqualified',receipt=receipt)));return 0
        if args.operation=='run':
            c.need(request['grade_inputs'] is None,'prediction worker never receives target or grade proof')
            value=ctx['programme'].run(ctx,selection,source,bodies,provider_config,prompt,frozen,origin,worker_end)
        else:
            fields=request['grade_inputs'];c.need(type(fields)is dict and set(fields)=={'terminal','outer_proof'},'exact separate grade operands')
            terminal=c.parse(c.capture(fields['terminal']['path'],65536,c.only_pin(fields['terminal']),budget.tick,budget.read))
            c.need(terminal.get('schema')=='neural083_adaptive_worker_terminal_v1'
                and terminal.get('source')==source and terminal.get('operation')=='run',
                'selected actual complete prediction worker terminal')
            proof=c.parse(c.capture(fields['outer_proof']['path'],65536,c.only_pin(fields['outer_proof']),budget.tick,budget.read))
            complete=joined['value'];called=[]
            def targets():
                c.need(not called,'one protected target callback');called.append(True)
                path=Path(complete['canonical']['path']).parent/'targets.json'
                raw=c.capture(path,complete['protected_targets']['bytes'],complete['protected_targets'],budget.tick,budget.read)
                return c.parse(raw)
            result=ctx['admission'].grade(ctx,selection,source,terminal['result'],proof,targets,budget)
            output=c.path(request['evidence_output'])
            value={'grade':c.save(output/'GRADE.json',c.encoded(result),8388608,budget.tick,budget.write)}
        budget.tick();print(json.dumps(dict(schema='neural083_adaptive_worker_terminal_v1',
            source=source,operation=args.operation,result=value)));return 0
    except BaseException as error:
        if args.worker:
            def emit(raw):
                view=memoryview(raw+b'\n')
                while view:
                    ctx['metadata_budget'].tick();n=os.write(sys.stderr.fileno(),view)
                    if n<=0:raise OSError('complete owned failure stream')
                    view=view[n:]
            publish_worker_failure(ctx,error,evidence,source,args.operation,emit)
        if output is not None and not args.worker:
            try:io.put(output/('WORKER_FAILURE.json' if args.worker else 'FAILURE.json'),
                io.encoded(dict(error_type=type(error).__name__,error=str(error)[:2048],
                    child=bridge.child_failure_record(error) or child,automatic_retry=False,
                    operation_envelope=operation_envelope(configuration['limits']),owner_preflight=budget.record(),
                    actual_failure=getattr(error,'adaptive_actual_failure',None))),ctx['metadata_budget'])
            except BaseException as secondary:error.add_note('Outer failure publication failed: '+type(secondary).__name__)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for n,handler in previous.items():signal.signal(n,handler)


if __name__=='__main__':raise SystemExit(main())
