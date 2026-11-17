"""Original-clock full14 observer; two full-public outputs, no scientific grading."""
import time,signal
ORIGIN=globals().get('ADAPTER_ORIGIN',time.monotonic())
FINAL_END=ORIGIN+120
INITIAL={}
def expired(*_):raise TimeoutError('original observer deadline or stop')
def restore_handlers(old):
    errors=[]
    try:signal.setitimer(signal.ITIMER_REAL,0)
    except BaseException as e:errors.append(e)
    for sig,h in old.items():
        try:signal.signal(sig,h)
        except BaseException as e:errors.append(e)
    return errors
def enter_startup():
    if 'ADAPTER_ORIGIN' in globals():
        guard=globals().get('ADAPTER_STARTUP_GUARD')
        if not callable(guard):raise ValueError('explicit original adapter owner')
        guard(ORIGIN)
    elif signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise ValueError('fresh standalone observer')
    old={sig:signal.getsignal(sig) for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    try:
        for sig in old:signal.signal(sig,expired)
        left=ORIGIN+120-time.monotonic()
        if left<=0:raise TimeoutError('original startup expired')
        signal.setitimer(signal.ITIMER_REAL,left)
    except BaseException as primary:
        for e in restore_handlers(old):primary.add_note('startup cleanup: '+type(e).__name__)
        raise
    return old
BOOT={'bytes': 1613, 'sha256': '0bc4e945d93eb34a3ea7bc635042eef48f1f6ec6264c1af3731ee2da592a4143'}
CAPTURED_WORKER='import time,signal,sys\nend=float(sys.argv[3])\ndef expired(*_):raise TimeoutError("captured worker original startup deadline")\nif time.monotonic()>=end:raise TimeoutError("captured worker startup expired")\nfor sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,expired)\nsignal.setitimer(signal.ITIMER_REAL,end-time.monotonic())\nimport base64\npath=sys.argv[1];raw=base64.b64decode(sys.argv[2],validate=True)\nsys.argv=[path,*sys.argv[4:]]\nexec(compile(raw,path,"exec"),{"__name__":"__main__","__file__":path})\n'
def boot():
    p=HERE/'bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT['bytes']+1)
    if len(raw)!=BOOT['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT['sha256']:raise ValueError('bootstrap pin')
    m=types.ModuleType('neural035_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

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

def admit(c,root,terminal,source,deadline,read,program_pin):
    tick=lambda:c.before(deadline)
    c.need(terminal.get('schema')=='neural035_full14_worker_v1' and terminal.get('status')=='complete_unqualified' and terminal.get('source')==source and terminal.get('outputs')==2,'whole worker terminal')
    c.need(not os.path.lexists(root/'FAILURE.json') and not os.path.lexists(root/'current'),'no failure or live view')
    value=c.parse(c.capture(root/'COMPLETE.json',32768,terminal['complete'],tick,read))
    c.need(value['source']==source and value['status']=='complete_unqualified' and value['outputs']==2 and value['sessions']==14 and value['biological_mice']==7 and value['cells']==1012 and value['query_blocks_per_output']==28 and value['all_views_retired']is True,'original full14 scope')
    for key in ('private_grading_performed','target_bodies_opened','runtime_qualified','scientific_qualified'):c.need(value[key]is False,'unqualified target-free collection')
    c.need(type(value['contexts'])is list and [r['case'] for r in value['contexts']]==[0,1],'complete two roles')
    commitment=c.parse(c.capture(root/'commitment/COMMITMENT.json',8192,value['commitment'],tick,read))
    c.need(commitment['source']==source and commitment['programs']==value['programs'] and commitment['before_any_public_view']is True,'original common commitment')
    c.need(value['programs']==dict(candidate=program_pin,operator=c.pin(BODIES['baseline_program.py'])),'exact selected candidate and fixed independent operator')
    for role,pin in value['programs'].items():c.capture(root/'commitment'/(role+'.py'),131072,pin,tick,read)
    retired=c.parse(c.capture(root/'journal/RETIRED.json',16384,value['retirement'],tick,read))
    prepared=c.parse(c.capture(root/'journal/PREPARED.json',16384,tick=tick,charge=read))
    c.need(retired==dict(absent=True,parent_fsynced=True,files=prepared['files']),'exact closed public view')
    expected={Path(row['target']).name:c.only_pin(row) for row in c.parse(BODIES['BINDINGS.json'])['public_files']}
    c.need(prepared['files']==expected and prepared['public_bytes']==11648181 and prepared['numeric_arrays_decoded_by_host']is False,'source-bound complete21 public view')
    documents=[]
    for case,row in enumerate(value['contexts']):
        c.need(row['role']==('candidate','operator')[case] and row['native_closed']is True,'role identity')
        record=c.parse(c.capture(root/'cases'/f'{case:02d}'/'NATIVE.json',262144,row['native_receipt'],tick,read))
        c.need(record['case']==case and record['role']==row['role'] and record['source']==source and record['status']=='captured' and record['prediction']==row['prediction'],'same native/captured output')
        c.need(record['all_native_resources_closed']is True and record['cli_reaped']is True and record['candidate_closed_before_capture']is True,'native closure')
        c.need(len(record['closures'])==3 and all(x['closed']is True for x in record['closures']) and sorted(x['kind'] for x in record['closures'])==['container','container','volume'],'all three native resources')
        c.validate_natural_exit(record['natural_exit']);c.validate_cli_commands(record['command_metadata'])
        documents.append(c.parse(c.capture(root/'cases'/f'{case:02d}'/'predictions.json',2000000,row['prediction'],tick,read)))
    public=c.parse(c.capture(root/'PUBLIC_MANIFEST.json',2000000,value['public_manifest'],tick,read))
    for row in public['sessions']:c.need(c.only_pin(row)==expected[row['file']],'canonical manifest exact public asset pins')
    core=c.module(BODIES,'order_core.py',HERE);contract=c.module(BODIES,'output_contract.py',HERE,c=c)
    contract.admit_pair(*documents,public,core)
    c.need(c.inventory(root,c.RETAIN,2000)[2]<=c.RETAIN-16384,'full retention plus observer slot')
    return {r['role']:r['prediction'] for r in value['contexts']},terminal['complete']

def main():
    global FINAL_END,HERE,BODIES,argparse,base64,hashlib,json,os,shutil,stat,sys,types,Path
    # All imports and argparse remain inside the entry's independent cleanup.
    import argparse,base64,hashlib,json,os,shutil,stat,sys,types
    from pathlib import Path
    HERE=Path(__file__).resolve().parent
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','external-output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();deadline=ORIGIN+120
    source=json.loads(a.source_pin);c,manifest,bodies,source_reads=boot().load(HERE,source,deadline);BODIES=bodies
    c.need(bodies['observe.py']==c.capture(Path(__file__),100000,manifest['files']['observe.py'],lambda:c.before(deadline)),'selected observer')
    policy=c.module(bodies,'policy.py',HERE,c=c);selection_pin=json.loads(a.selection_pin)
    s=policy.selection(c.parse(c.capture(a.selection,32768,selection_pin,lambda:c.before(deadline))),source)
    whole=ORIGIN+policy.whole(s['candidate_seconds']);worker_end=whole-20;outer=whole+60;FINAL_END=outer
    output=c.path(a.external_output);root=c.path(s['output'])
    c.need(not os.path.lexists(output) and not os.path.lexists(root) and output!=root and not output.is_relative_to(root) and not root.is_relative_to(output),'fresh separate receipt/attempt')
    c.need(root.parent.stat().st_dev==output.parent.stat().st_dev and os.statvfs(output.parent).f_frsize<=4096,'same bounded filesystem')
    c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+c.RETAIN,'full custody before creation')
    initial=slot(output,c.encoded(dict(schema='neural035_full14_external_v1',status='started',source=source)),deadline,create=True)
    proc=c.module(bodies,'process.py',HERE);cache=Path(str(output)+'.UNUSED-PYCACHE');c.need(not os.path.lexists(cache),'fresh disabled child cache')
    argv=[str(Path(sys.executable).resolve()),'-I','-S','-B','-X','pycache_prefix='+str(cache),'-c',CAPTURED_WORKER,str(HERE/'worker.py'),base64.b64encode(bodies['worker.py']).decode('ascii'),repr(ORIGIN+120),'--source-pin',a.source_pin,'--selection',a.selection,'--selection-pin',a.selection_pin,'--origin',repr(ORIGIN),'--worker-end',repr(worker_end)]
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')};env['PYTHONDONTWRITEBYTECODE']='1'
    reads=source_reads+65536;record=None;error=None;outputs=None;complete=None;success=False
    def read(n):
        nonlocal reads
        c.need(reads+n<=16777216,'observer whole read ceiling');reads+=n;c.before(whole)
    c.before(worker_end);signal.setitimer(signal.ITIMER_REAL,worker_end-time.monotonic())
    try:
        raw,record=proc.run(argv,worker_end,whole+40,env);c.before(worker_end)
        c.need(record['natural_exit']is True and type(record['exit_code'])is int and record['exit_code']==0 and record['process_reaped']is True and record['process_group_absent']is True and record['streams_closed']is True,'natural worker closure')
        c.need(all(record[k]is False for k in ('timed_out','kill_sent')) and all(record[k]is None for k in ('error_type','timer_disable_error','timer_restore_error')),'unforced error-free child')
        c.need(not os.path.lexists(cache),'disabled cache absent');c.before(whole)
        signal.setitimer(signal.ITIMER_REAL,whole-time.monotonic())
        outputs,complete=admit(c,root,c.parse(raw),source,whole,read,c.only_pin(s['program']));success=True
    except BaseException as exc:
        error=type(exc).__name__
        if isinstance(exc,proc.ChildFailure):record=exc.record
    deadline=whole if success else outer;FINAL_END=deadline;c.before(deadline)
    signal.setitimer(signal.ITIMER_REAL,deadline-time.monotonic())
    used=c.inventory(root,c.RETAIN,2000)[2] if root.exists() else 0
    c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+max(0,c.RETAIN-used-8192),'terminal capacity')
    receipt=dict(schema='neural035_full14_external_v1',status='complete_unqualified' if success else 'failed',source=source,selection=selection_pin,attempt=str(root),captured_worker_source=c.pin(bodies['worker.py']),child=record,error_type=error,outputs=outputs,complete=complete,origin_monotonic=ORIGIN,whole_deadline=whole,outer_deadline=outer,elapsed_before_publication=time.monotonic()-ORIGIN,observer_read_reservations=reads,observer_write_reservations=16384,full14_source_scope=True,scientific_qualified=False,runtime_qualified=False,grading_performed=False,nested_native_recovery_may_be_required=not success,host_group_scope='exact worker group; independent CLI/native resources need each successful closure',automatic_retry=False)
    slot(output,c.encoded(receipt),deadline,create=False,stamp=initial);c.before(deadline)
    return 0 if success else 2

def entry():
    old=enter_startup();result=2
    try:result=main()
    except BaseException:result=2
    finally:
        if restore_handlers(old):result=2
    return result if time.monotonic()<FINAL_END else 2

if __name__=='__main__':
    result=entry()
    if time.monotonic()>=FINAL_END:result=2
    raise SystemExit(result)

