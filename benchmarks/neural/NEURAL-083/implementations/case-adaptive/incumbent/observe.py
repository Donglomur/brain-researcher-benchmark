"""Original-clock full54 external observer; no scientific qualification."""
import time
ORIGIN=globals().get("ADAPTER_ORIGIN",time.monotonic())
import argparse,base64,hashlib,json,os,shutil,signal,stat,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
BOOT={'bytes': 1613, 'sha256': '7854891fba8402ac945edc6ad9d792be1b974521349dcc190a71f308798ab027'}
CAPTURED_WORKER='import time,signal,sys\nend=float(sys.argv[3])\ndef expired(*_):raise TimeoutError("captured worker original startup deadline")\nif time.monotonic()>=end:raise TimeoutError("captured worker startup expired")\nfor sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,expired)\nsignal.setitimer(signal.ITIMER_REAL,end-time.monotonic())\nimport base64\npath=sys.argv[1];raw=base64.b64decode(sys.argv[2],validate=True)\nsys.argv=[path,*sys.argv[4:]]\nexec(compile(raw,path,"exec"),{"__name__":"__main__","__file__":path})\n'
def boot():
    p=HERE/'bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT['bytes']+1)
    if len(raw)!=BOOT['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT['sha256']:raise ValueError('bootstrap pin')
    m=types.ModuleType('neural083_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

def slot(path,raw,deadline,*,create,stamp=None):
    if time.monotonic()>=deadline or len(raw)>8192:raise ValueError('receipt deadline/extent')
    raw+=b' '*(8192-len(raw));flags=os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK
    if create:flags|=os.O_CREAT|os.O_EXCL
    fd=os.open(path,flags,0o600)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1:raise ValueError('ordinary receipt')
        if stamp is not None and (a.st_dev,a.st_ino,a.st_size,a.st_mode)!=(stamp.st_dev,stamp.st_ino,8192,stamp.st_mode):raise ValueError('same reserved receipt inode')
        off=0
        while off<len(raw):
            if time.monotonic()>=deadline:raise TimeoutError('receipt write deadline')
            n=os.pwrite(fd,raw[off:],off)
            if n<=0:raise ValueError('receipt progress')
            off+=n
        if time.monotonic()>=deadline:raise TimeoutError('receipt fsync deadline')
        os.fsync(fd);z=os.fstat(fd);named=Path(path).lstat()
        if z.st_size!=8192 or any(getattr(z,k)!=getattr(named,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError('receipt stable durable inode')
    finally:os.close(fd)
    d=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(d)
    finally:os.close(d)
    if time.monotonic()>=deadline:raise TimeoutError('receipt durability deadline')
    return z


def main():
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','external-output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();deadline=ORIGIN+120;exitcode=2
    def stop(*_):raise TimeoutError('original observer deadline or stop')
    old={};installed=[]
    try:
        for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):
            old[sig]=signal.getsignal(sig)
            signal.signal(sig,stop);installed.append(sig)
        signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
        source=json.loads(a.source_pin);c,manifest,bodies,source_reads=boot().load(HERE,source,deadline)
        c.need(bodies['observe.py']==c.capture(Path(__file__),100000,manifest['files']['observe.py'],lambda:c.before(deadline)),'selected observer')
        contracts=c.module(bodies,'contracts.py',HERE,c=c);policy=c.module(bodies,'policy.py',HERE,c=c,contracts=contracts);selection_pin=json.loads(a.selection_pin)
        s=policy.selection(c.parse(c.capture(a.selection,32768,selection_pin,lambda:c.before(deadline))),source)
        whole=ORIGIN+s['limits']['whole_seconds'];worker_end=whole-s['limits']['observer_seconds'];outer=whole+60
        output=c.path(a.external_output);root=c.path(s['output'])
        c.need(not os.path.lexists(output) and not os.path.lexists(root) and output!=root and not output.is_relative_to(root) and not root.is_relative_to(output),'fresh separate receipt/attempt')
        c.need(root.parent.stat().st_dev==output.parent.stat().st_dev and os.statvfs(output.parent).f_frsize<=4096,'same bounded filesystem')
        c.need(shutil.disk_usage(output.parent).free>=s['limits']['free_floor_bytes']+s['other_future_bytes']+s['limits']['retained'],'full phase custody before output creation')
        initial=slot(output,c.encoded(dict(schema='neural083_sequential_external_v2',status='started',source=source)),deadline,create=True)
        proc=c.module(bodies,'process.py',HERE);cache=Path(str(output)+'.UNUSED-PYCACHE')
        c.need(not os.path.lexists(cache),'fresh unused child cache')
        argv=[str(Path(sys.executable).resolve()),'-I','-S','-B','-X','pycache_prefix='+str(cache),'-c',CAPTURED_WORKER,str(HERE/'worker.py'),base64.b64encode(bodies['worker.py']).decode('ascii'),repr(ORIGIN+120),'--source-pin',a.source_pin,'--selection',a.selection,'--selection-pin',a.selection_pin,'--origin',repr(ORIGIN),'--worker-end',repr(worker_end)]
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')};env['PYTHONDONTWRITEBYTECODE']='1'
        reads=source_reads+65536;record=None;error=None;bundle=None;complete=None;success=False
        def read(n):
            nonlocal reads
            c.need(reads+n<=s['limits']['observer_reads'],'observer whole read ceiling');reads+=n;c.before(whole)
        signal.setitimer(signal.ITIMER_REAL,max(.001,worker_end-time.monotonic()))
        try:
            raw,record=proc.run(argv,worker_end,whole+40,env)
            c.need(time.monotonic()<worker_end,'natural process closure before original worker endpoint')
            c.need(record['natural_exit'] is True and record['exit_code']==0 and record['process_reaped'] and record['process_group_absent'] and record['streams_closed'],'natural worker closure')
            c.need(not os.path.lexists(cache),'disabled child cache absent')
            signal.setitimer(signal.ITIMER_REAL,max(.001,whole-time.monotonic()))
            admission=c.module(bodies,'admission.py',HERE)
            bundle,complete=admission.admit(c,contracts,c.pin(bodies['reference_program.py']),root,c.parse(raw),source,s,whole,read);success=True
        except BaseException as exc:
            error=type(exc).__name__
            if isinstance(exc,proc.ChildFailure):record=exc.record
        deadline=whole if success else outer
        signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()));c.before(deadline)
        used=c.inventory(root,s['limits']['retained'],400200)[2] if root.exists() else 0
        c.need(shutil.disk_usage(output.parent).free>=s['limits']['free_floor_bytes']+s['other_future_bytes']+max(0,s['limits']['retained']-used-8192),'terminal retained-capacity guard')
        receipt=dict(schema='neural083_sequential_external_v2',status='complete_unqualified' if success else 'failed',source=source,selection=selection_pin,attempt=str(root),argv=argv[:9]+['<captured-worker-bytes>']+argv[10:],captured_worker_source=c.pin(bodies['worker.py']),worker_terminal=c.parse(raw) if success else None,child=record,error_type=error,submission=bundle,complete=complete,origin_monotonic=ORIGIN,whole_deadline=whole,outer_deadline=outer,elapsed_before_publication=time.monotonic()-ORIGIN,observer_read_reservations=reads,observer_write_reservations=16384,full54x2x4x3_both_panels=True,prediction_values=259200,limits=s['limits'],scientific_qualified=False,runtime_qualified=False,grading_performed=False,worker_accounting_status='complete_prepublication_snapshot_plus_admitted_terminal_delta' if success else 'unknown_unless_separately_recovered_from_durable_failure_evidence_never_assume_zero',nested_native_recovery_may_be_required=not success,host_group_scope='exact worker process group; native resources require successful per-case closure',automatic_retry=False)
        slot(output,c.encoded(receipt),deadline,create=False,stamp=initial);c.before(deadline)
        exitcode=0 if success else 2
    except BaseException:exitcode=2
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:exitcode=2
        for number,handler in old.items():
            try:signal.signal(number,handler)
            except BaseException:exitcode=2
    return exitcode if time.monotonic()<deadline else 2
if __name__=='__main__':raise SystemExit(main())
