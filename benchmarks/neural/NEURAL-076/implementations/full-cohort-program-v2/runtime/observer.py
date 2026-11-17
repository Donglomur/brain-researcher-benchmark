"""Whole-command owner: only observed natural exit can close the full collection."""
import os,sys,time,signal
from pathlib import Path
from common import need,before,path,capture,decode,encode,short,write,inventory,syncdir,FLOOR,RETAIN,MIB

def main(args,loader,bodies,manifest,source,origin,startup_handler):
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--source-sha256',required=True);a.add_argument('--selection',required=True);a.add_argument('--selection-sha256',required=True);v=a.parse_args(args)
    raw,pin=capture(v.selection,131072);need(pin['sha256']==v.selection_sha256,'exact external selection');s=decode(raw)
    need(type(s.get('whole_seconds'))is int and 0<s['whole_seconds']<=650*(7200+840)+7320,'bounded whole selection duration')
    end=origin+s['whole_seconds'];before(end);remaining,interval=signal.getitimer(signal.ITIMER_REAL);need(signal.getsignal(signal.SIGALRM)is startup_handler and 0<remaining<=60 and interval==0 and time.monotonic()<origin+60,'same active original startup enclosure');old=startup_handler
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in()).throw(TimeoutError('original whole observer deadline')));signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
    try:
        loader('coordinator').validate_selection(s,source,bodies)
        result=owned(v,s,pin,loader,source,origin,end)
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        finally:signal.signal(signal.SIGALRM,old)
    before(end);return result,end

def owned(v,s,pin,loader,source,origin,end):
    root=path(s['output']);out=root.with_name(root.name+'.observer');need(not os.path.lexists(root)and not os.path.lexists(out)and out.parent.is_dir(),'fresh owned whole-command paths')
    fs=os.statvfs(out.parent);need(fs.f_bavail*fs.f_frsize>=FLOOR+s['other_future_bytes']+RETAIN+MIB,'whole remaining allowance before start')
    out.mkdir(mode=0o700);syncdir(out.parent);here=Path(__file__).absolute().parent
    argv=[str(Path(sys.executable).resolve()),'-I','-S','-B',str(here/'run.py'),'--source-sha256',source['sha256'],'--selection',str(path(v.selection)),'--selection-sha256',pin['sha256'],'--outer-end',str(end)]
    write(out/'INTENT.json',encode({'schema':'neural076_whole_command_intent_v1','source':source,'selection':pin,'argv':argv,'origin':origin,'end':end,'automatic_retry':False}),131072)
    process=loader('process');streams=record=None;error=None;complete=None
    try:
        streams,record=process.run(argv,end-10,end,{'PATH':'/usr/bin:/bin:/usr/local/bin','LANG':'C','LC_ALL':'C','PYTHONNOUSERSITE':'1'},cwd=str(here),cap=8192,accepted=(0,))
        loader('coordinator').child_closed(record);before(end-10);terminal=decode(streams['stdout']);need(set(terminal)=={'complete','runtime_qualified','scientific_scoring'}and terminal['runtime_qualified']is False and terminal['scientific_scoring']is False,'exact full terminal')
        raw,complete=capture(root/'COMPLETE.json',2*MIB,terminal['complete'],tick=lambda:before(end-10));d=decode(raw)
        need(d['schema']=='neural076_full650_collection_v1'and d['status']=='complete_pending_external_natural_exit'and d['source']==source and d['context_count']==650 and d['private_gold_opened']is False and d['scientific_scoring']is False and d['runtime_qualified']is False and d['scientific_qualified']is False,'same complete public collection')
        need([r['key']for r in d['contexts']]==list(loader('common').KEYS),'ordered full650 closure')
        need(inventory(out,8)[2]+65536<=MIB,'bounded whole observer receipt')
    except process.ChildFailure as exc:record=exc.record;error='ChildFailure'
    except BaseException as exc:error=type(exc).__name__
    # A failed helper alarm handoff leaves no authority for another blocking write.
    need(type(record)is dict and record.get('timer_disable_error','missing')is None and record.get('timer_restore_error','missing')is None,'whole timer custody before any observation publication')
    observation={'schema':'neural076_whole_command_observation_v1','source':source,'selection':pin,'lifecycle':record,'complete':complete,'error':error,'completed':error is None,'runtime_qualified':False,'scientific_scoring':False,'scientific_qualified':False,'observed':time.monotonic(),'deadline':end,'no_cleanup_beyond_owned_child':True,'requires_observed_observer_exit_zero':True}
    before(end);receipt=write(out/'OBSERVATION.json',encode(observation),131072);before(end);need(error is None,'whole-command observation failed; partial evidence retained')
    print(encode({'observation':receipt,'complete':complete,'full_contexts':650,'runtime_qualified':False,'scientific_qualified':False}).decode(),end='',flush=True);before(end);return 0
