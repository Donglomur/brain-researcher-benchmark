"""Concrete caller observation and independent collection readback, no science callback."""
from pathlib import Path
from core import need,parse,encoded,publish,fresh,pin,capture
from caller_observer import run as observe_child
from engine import Engine
from admission import admit
from launch_code import CODE

def command(a,captured):
    cfg={'source_root':a['roots']['source'],'manifest_path':captured['manifest_path'],'manifest':captured['pin'],
         'bootstrap_source':captured['manifest']['files']['program/bootstrap.py'],'entry_source':captured['manifest']['files']['program/entry.py'],
         'origin':a['clock']['origin'],'bootstrap_deadline':a['clock']['production_end'],'launch_source_read_cap':a['resources']['source_bytes'],
         'source_read_cap':a['resources']['source_bytes'],'authority':captured['authority_descriptor'],'role':'worker'}
    return [a['host_python'],'-I','-B','-c',CODE,encoded(cfg).decode()]

def natural(record,argv,a):
    need(record['argv']==argv and record['cwd']==a['roots']['source'],'actual caller command/cwd')
    for key in('successful_observation','spawn_attempted','spawn_returned','natural_exit','process_reaped','process_group_absent','streams_closed','selector_closed','stdout_eof','stderr_eof','mutating_signals_disabled','no_mutating_signals'):
        need(record.get(key)is True,'natural exact caller '+key)
    for key in('cleanup_attempted','timed_out','parent_timer_elapsed','cleanup_ownership_unknown','failed_unknown_child_state','spawn_ownership_unknown','output_overflow','term_attempted','kill_attempted','forced_termination_supported','requires_separate_child_inspection'):
        need(record.get(key)is False,'no uncertain caller '+key)
    need(type(record['exit_code'])is int and record['exit_code']==0 and record['mutating_signal_count']==0,'exact natural zero, no mutators')
    need(record['normal_end']==a['clock']['production_end']and record['cleanup_end']==a['clock']['observation_end']
         and a['clock']['origin']<=record['observed_start']<=record['normal_closed_at']<=record['final_closed_at']<record['normal_end'],'original complete caller clock')
    need(record['error_type']is None and record['cleanup_mode']=='observation_and_bounded_wait_only','selected conservative caller contract')
    return record

def source_recheck(a,captured,b):
    capture(captured['manifest_path'],captured['pin'],a['resources']['source_bytes'],b,retain=False)
    for name,desc in captured['manifest']['files'].items():capture(Path(a['roots']['source'])/name,desc,a['resources']['source_bytes'],b,retain=False)
    b.tick()

def inventory(a,b):
    from urllib.parse import quote
    rows={}
    for role in('public','private'):
        selected=a['native_'+role];e=Engine(selected,b,lambda _:None)
        query=quote(encoded({'label':['neural049.study='+selected['study']]}).decode(),safe='')
        _,raw=e.request('GET','/containers/json?all=1&filters='+query,None,a['clock']['readback_end'],limit=a['resources']['native_inventory_bytes'])
        obj=parse(raw);need(type(obj)is list and not obj,'independent complete-study resource retirement')
        rows[role]={'raw':pin(raw),'empty':True,'study':selected['study'],'observed':b.tick()}
    return rows

def retain_bundle(root,bundle,b):
    """Attempt each original stream and caller record once, independently."""
    retained={};errors=[];attempted=[]
    for name,value in [('stdout',bundle['stdout']),('stderr',bundle['stderr']),('caller',bundle['record'])]:
        attempted.append(name)
        try:
            body=encoded(value)if name=='caller'else value
            need(type(body)is bytes and len(body)<=65536,'bounded original capture artifact')
            retained[name]=publish(root/(name+'.bin'if name!='caller'else'CALLER.json'),body,b,readonly=True)
        except BaseException as error:errors.append({'artifact':name,'error':type(error).__name__,'durability':'unknown'})
    return {'retained':retained,'errors':errors,'attempted':attempted,'complete':not errors,'no_retry':True}


def observe(a,captured,b):
    root=Path(a['roots']['observation']);argv=command(a,captured);bundle=None;written={};retention=None;phase='setup'
    try:
        fresh(root,b);written['intent']=publish(root/'INTENT.json',encoded({'argv':argv,'source':captured['pin'],'authority':captured['authority_pin'],'original_origin':b.origin}),b,readonly=True)
        source_recheck(a,captured,b)
        # Caller retains at most its fixed bounded streams. These logical reservations
        # precede spawning; they do not measure subprocess or OS physical usage.
        b.reserve_read(131072);b.reserve_write(131072);phase='caller'
        bundle=observe_child(argv,a['clock']['production_end'],a['clock']['observation_end'],a['host_environment'],a['roots']['source'])
        retention=retain_bundle(root,bundle,b);written.update(retention['retained'])
        need(retention['complete'],'original capture artifact durability failed')
        natural(bundle['record'],argv,a);need(not bundle['stderr'],'successful worker has no unadmitted stderr')
        result=parse(bundle['stdout']);need(result['status']=='collected','actual complete worker result')
        phase='readback';admitted=admit(a,captured,result['producer'],b);resources=inventory(a,b);source_recheck(a,captured,b)
        record={'schema':'neural049_observation_v1','status':'complete','source':captured['pin'],'authority':captured['authority_pin'],
                'original_origin':b.origin,'producer':result['producer'],'caller':bundle['record'],'streams':{k:written[k]for k in('stdout','stderr')},'caller_artifact':{'path':str(root/'CALLER.json'),'pin':written['caller']},
                'resource_inventory':resources,'schedule':admitted['producer']['disposition'],'closure_counts':{k:admitted['closure'][k]for k in('phase_count','native_count','provider_count')},
                'observed_end':b.tick(),'logical_costs_before_observation_publication':b.record(),
                'own_outer_exit_not_self_certified':True}
        desc=publish(root/'OBSERVATION.json',encoded(record),b,readonly=True);b.tick()
        return {'status':'observed','observation':{'path':str(root/'OBSERVATION.json'),'pin':desc},'source':captured['pin']}
    except BaseException as error:
        if bundle is None:bundle=getattr(error,'bundle',None)
        if bundle is not None and retention is None:
            retention=retain_bundle(root,bundle,b);written.update(retention['retained'])
        from controller import raw_budget
        failure={'status':'failed','phase':phase,'error':type(error).__name__,'bundle':None if bundle is None else {'record':bundle['record'],'stdout':pin(bundle['stdout']),'stderr':pin(bundle['stderr'])},'written':written,'capture_retention':retention,'costs':raw_budget(b),'unknown_surviving_child_or_container':True,'no_retry':True}
        error.failure_record=failure;error.original_caller_bundle=bundle
        try:publish(root/'FAILED.json',encoded(failure),b,readonly=True)
        except BaseException as later:failure['failure_publication_error']=type(later).__name__
        raise
