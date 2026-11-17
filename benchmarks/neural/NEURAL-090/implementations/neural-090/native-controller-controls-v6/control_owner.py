"""Finite source-bound stdlib engineering child; original child wait and EOF only.

Adapted from the retained FIND supervisor. No poll/reap-then-group-signal sequence:
this child cannot fork/exec, no killpg is used, direct-child kill retires before
the final raw wait. ECHILD is an ownership failure, never a zero status.
This does not qualify general process containment or native code.
"""
import argparse, hashlib, json, linecache, os, selectors, signal, stat, subprocess, sys, threading, time, traceback
from pathlib import Path

STREAM_CAP=65536
FINAL_CUSTODY={}

class PublicationFailure(RuntimeError):
    def __init__(self,first,secondary,body):
        self.first=first;self.secondary=tuple(secondary);self.body=body
        super().__init__('owner publication failed; all original raw causes retained')
BOOTSTRAP="""import hashlib,os,stat,sys
p,n,h=sys.argv[1:4];n=int(n)
fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
with os.fdopen(fd,'rb') as f:
 if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError('ordinary selected child')
 raw=f.read(n+1)
if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=h:raise ValueError('selected child source')
sys.argv=[p]+sys.argv[4:]
exec(compile(raw,p,'exec'),{'__name__':'__main__','__file__':p})
"""

def main():
    origin=time.monotonic();work_end=origin+90.;publication_end=origin+105.;end=origin+120.
    parser=argparse.ArgumentParser(allow_abbrev=False)
    for n in ('manifest','manifest-bytes','manifest-sha256','source-root','output'):parser.add_argument('--'+n,required=True)
    args=parser.parse_args()
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize):raise ValueError('actual -I -S -B owner required')
    if os.name!='posix'or signal.getsignal(signal.SIGCHLD)!=signal.SIG_DFL or threading.current_thread()is not threading.main_thread()or threading.active_count()!=1:
        raise ValueError('default SIGCHLD and sole main-thread wait ownership required')
    observations=[];used=[0]
    def charge(n):
        if type(n)is not int or n<0 or used[0]+n>8*1048576:raise RuntimeError('fixed8MiB outer logical allowance')
        used[0]+=n
    def read(path,n,sha):
        p=Path(path);s=p.lstat()
        if n>1048576 or s.st_size!=n or not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or any(q.is_symlink()for q in(p,*p.parents)):raise ValueError('exact ordinary selected source')
        charge(n+1);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);raw=bytearray();first=None;secondary=[]
        stamp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mode,x.st_nlink,x.st_mtime_ns,x.st_ctime_ns)
        try:
            if stamp(s)!=stamp(os.fstat(fd)):raise ValueError('owner source open identity')
            while len(raw)<=n:
                if time.monotonic()>=end:raise TimeoutError('original owner capture deadline')
                b=os.read(fd,min(65536,n+1-len(raw)))
                if not b:break
                raw.extend(b)
            if stamp(s)!=stamp(os.fstat(fd))or stamp(s)!=stamp(p.lstat()):raise ValueError('owner stable source capture')
        except BaseException as e:first=e
        finally:
            try:os.close(fd)
            except BaseException as e:
                if first is None:first=e
                else:secondary.append(e)
        if first is not None:first.source_secondary=tuple(secondary);first.source_prefix=bytes(raw);raise first
        if len(raw)!=n or sha is not None and hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('owner selected body digest')
        return bytes(raw)
    manifest=Path(args.manifest).absolute();source=Path(args.source_root).absolute();raw=read(manifest,int(args.manifest_bytes),args.manifest_sha256);selection=json.loads(raw)
    if selection['schema']!='n090_finite_controller_engineering_selection_v1'or selection['execution_selected']is not False:raise ValueError('exact prospective manifest')
    if selection['case_roster']!=['C'+str(i).zfill(2)for i in range(1,25)]:raise ValueError('exact complete24 roster')
    rows=selection['files'];names=[r['path']for r in rows]
    if len(set(names))!=6 or any('/'in n or n.startswith('.')for n in names):raise ValueError('closed flat harness graph')
    captured={r['path']:read(manifest.parent/r['path'],r['bytes'],r['sha256'])for r in rows}
    for name,body in captured.items():
        path=str(manifest.parent/name);linecache.cache[path]=(len(body),None,body.decode('utf-8').splitlines(True),path)
    mine=captured['control_owner.py']
    if read(__file__,len(mine),hashlib.sha256(mine).hexdigest())!=mine:raise ValueError('actual owner selected source')
    output=Path(args.output).absolute()
    if output.parent!=manifest.parent or output.name!='actual-v1'or any(q.is_symlink()for q in output.parents):raise ValueError('fixed create-only attempt destination')
    output.mkdir(mode=0o700)
    def publish(name,body):
        if len(body)>262144:raise ValueError('bounded owner publication')
        charge(len(body));p=output/name;fd=None;offset=0;original=None;extra=[]
        try:
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            while offset<len(body):
                n=os.write(fd,body[offset:])
                if n<=0:raise OSError('short original owner publication')
                offset+=n
            os.fsync(fd)
        except BaseException as error:original=error
        finally:
            if fd is not None:
                try:os.close(fd)
                except BaseException as error:
                    if original is None:original=error
                    else:extra.append(error)
        if original is not None:raise PublicationFailure(original,extra,body)from original
    child=next(r for r in rows if r['path']=='control_child.py')
    argv=[sys.executable,'-I','-S','-B','-c',BOOTSTRAP,str(manifest.parent/child['path']),str(child['bytes']),child['sha256'],'--manifest',str(manifest),'--manifest-bytes',args.manifest_bytes,'--manifest-sha256',args.manifest_sha256,'--source-root',str(source),'--output',str(output),'--work-end',str(work_end),'--publication-end',str(publication_end)]
    charge(child['bytes']+sum(len(s.encode())+1 for s in argv));publish('OWNER_SELECTION.json',(json.dumps({'argv':argv,'selection_sha256':args.manifest_sha256,'origin':origin,'work_end':work_end,'publication_end':publication_end,'cleanup_end':end},sort_keys=True)+'\n').encode())
    process=None;selector=None;first=None;secondary=[];streams={'stdout':bytearray(),'stderr':bytearray()};eof=set();waits=[];kill_sent=False;kill_retired=False;wait_lost=False;reaped=False;raw_waits=[]
    def record(error):
        nonlocal first
        observations.append(error)
        if first is None:first=error
        else:secondary.append(error)
    def wait_original(deadline):
        nonlocal wait_lost,reaped,kill_retired
        if reaped or wait_lost:raise RuntimeError('original child wait ownership unavailable')
        while True:
            if time.monotonic()>=deadline:raise TimeoutError('original raw child wait cutoff')
            # Retire destructive actions BEFORE the syscall can reap. An async
            # exception after the syscall but before Python bookkeeping is safe.
            kill_retired=True
            try:pid,status=os.waitpid(process.pid,os.WNOHANG)
            except ChildProcessError:
                wait_lost=True;kill_retired=True;raise
            if pid==0:
                # An actual zero return proves this original child was not reaped.
                kill_retired=False
                time.sleep(min(.01,max(0.,deadline-time.monotonic())));continue
            if pid!=process.pid:
                wait_lost=True;kill_retired=True;raise RuntimeError('raw wait returned another child identity')
            # This is the only successful reap; no signal can follow it.
            reaped=True;kill_retired=True;raw_waits.append({'pid':pid,'status':status})
            value=os.waitstatus_to_exitcode(status);process.returncode=value
            return value
    try:
        selector=selectors.DefaultSelector()
        if time.monotonic()>=work_end:raise TimeoutError('original owner bootstrap work cutoff')
        process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=output,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},close_fds=True,start_new_session=True,bufsize=0)
        for name in streams:
            f=getattr(process,name);os.set_blocking(f.fileno(),False);selector.register(f,selectors.EVENT_READ,name)
        while selector.get_map():
            left=publication_end-time.monotonic()
            if left<=0:raise TimeoutError('original finite child publication cutoff')
            for key,_ in selector.select(min(.02,left)):
                b=os.read(key.fd,min(8192,STREAM_CAP+1-len(streams[key.data])));charge(len(b))
                if b:
                    streams[key.data].extend(b)
                    if len(streams[key.data])>STREAM_CAP:raise ValueError('exact per-stream cap plus refused probe')
                else:eof.add(key.data);selector.unregister(key.fileobj)
        left=publication_end-time.monotonic()
        if left<=0:raise TimeoutError('original child wait cutoff')
        # Raw waitpid cannot map a missing original status to Popen's synthetic0.
        waits.append(wait_original(publication_end))
        if waits[-1]!=0:raise RuntimeError('actual engineering child nonzero')
    except BaseException as e:record(e)
    finally:
        if process is not None:
            if not kill_retired:
                # Default SIGCHLD and the sole waiter keep an unreaped PID pinned.
                # No Popen poll/kill/wait may implicitly reap or synthesize a status.
                try:
                    if signal.getsignal(signal.SIGCHLD)!=signal.SIG_DFL or threading.active_count()!=1:raise RuntimeError('exclusive original wait ownership changed')
                    os.kill(process.pid,signal.SIGKILL);kill_sent=True
                except ProcessLookupError:pass
                except BaseException as e:record(e)
                kill_retired=True
            # Unknown/retired signaling does not prohibit a nonmutating wait.
            # If a prior syscall reaped but was interrupted before bookkeeping,
            # this reports ECHILD as lost ownership and never signals that PID.
            if not reaped and not wait_lost:
                try:
                    left=end-time.monotonic()
                    if left<=0:raise TimeoutError('original child retirement cutoff')
                    waits.append(wait_original(end))
                except BaseException as e:record(e)
            for name in streams:
                f=getattr(process,name,None)
                if f is not None:
                    try:f.close()
                    except BaseException as e:record(e)
        if selector is not None:
            try:selector.close()
            except BaseException as e:record(e)
    result=None
    try:
        path=output/'CHILD_RESULT.json'
        if path.exists():result=json.loads(read(path,path.stat().st_size,None))
        if result is None or result['status']!='PASS'or [x['case']for x in result['cases']]!=selection['case_roster']or result['attempted']!=24:raise RuntimeError('missing or incomplete actual24 result')
        if eof!={'stdout','stderr'}or waits!=[0]or not reaped or wait_lost or len(raw_waits)!=1:raise RuntimeError('actual original child wait and both EOF required')
    except BaseException as e:record(e)
    # Bounded ordinary inventory, no recursive cleanup; failed fixtures remain.
    retained=0;entries=0;pending=[output]
    try:
        while pending:
            folder=pending.pop()
            with os.scandir(folder)as it:
                for entry in it:
                    entries+=1
                    if entries>4096:raise RuntimeError('finite retained fixture entry count')
                    s=entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(s.st_mode):pending.append(Path(entry.path))
                    elif stat.S_ISREG(s.st_mode):retained+=s.st_size
                    else:raise RuntimeError('nonordinary retained fixture')
        if retained+2*(STREAM_CAP+1)+262144>4*1048576:raise RuntimeError('whole4MiB retained envelope')
    except BaseException as e:record(e)
    for name,b in streams.items():
        try:publish(name+'.txt',bytes(b))
        except BaseException as e:record(e)
    def projected(e):
        try:return {'type':type(e).__name__,'reason':str(e)[:4096],'traceback':''.join(traceback.format_exception(e,limit=24))[:24576]}
        except BaseException as projection:
            record(projection);return {'type':type(e).__name__,'projection_unavailable':True,'projection_error':type(projection).__name__}
    if time.monotonic()>=end:record(TimeoutError('original120second final publication cutoff'))
    outcome={'schema':'n090_original_engineering_owner_v1','status':'PASS'if first is None else'FAIL','argv':argv,'first':None if first is None else projected(first),'secondary':[projected(e)for e in tuple(secondary)],'wait_returns':waits,'raw_wait_observations':raw_waits,'original_reaped':reaped,'wait_ownership_lost':wait_lost,'stream_eof':sorted(eof),'kill_sent':kill_sent,'kill_actions_retired':kill_retired,'child_pid':None if process is None else process.pid,'group_absence_measured':False,'descendant_policy':'captured trusted child denies actual fork/exec/subprocess; no general containment qualification','streams':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'complete':n in eof}for n,b in streams.items()},'child_result':result,'retained_bytes_before_final':retained,'owner_managed_transfer':used[0],'whole_attempt_charge_bytes':selection['whole_attempt_transfer_bytes'],'origin':origin,'seconds_before_final':time.monotonic()-origin,'native_scientific_provider_runs':0,'automatic_retry':False}
    FINAL_CUSTODY.update(outcome=outcome,first=first,secondary=secondary,original_errors=observations)
    durable=False;body=None
    try:
        outcome['status']='PASS'if first is None and not secondary else'FAIL'
        body=(json.dumps(outcome,sort_keys=True,allow_nan=False)+'\n').encode()
        publish('ORIGINAL_OWNER.json',body);durable=True
    except BaseException as error:record(error)
    if time.monotonic()>=end:record(TimeoutError('original final owner publication endpoint'))
    try:print(json.dumps({'status':'PASS'if first is None else'FAIL','output':str(output),'waits':waits,'passed':0 if result is None else len(result['cases']),'durable_owner_record':durable}),flush=True)
    except BaseException as error:record(error)
    if first is not None:
        fallback={'status':'FAIL','durable_owner_record':durable,'first_type':type(first).__name__,'first_reason':str(first)[:2048],'secondary_types':[type(e).__name__ for e in secondary[:32]],'original_outcome_retained_in_process':True}
        try:sys.stderr.write(json.dumps(fallback,sort_keys=True)+'\n');sys.stderr.flush()
        except BaseException as error:record(error)
    FINAL_CUSTODY.update(first=first,secondary=tuple(secondary),intended_body=body,durable=durable)
    return 0 if first is None and not secondary and time.monotonic()<end else 1

if __name__=='__main__':raise SystemExit(main())
