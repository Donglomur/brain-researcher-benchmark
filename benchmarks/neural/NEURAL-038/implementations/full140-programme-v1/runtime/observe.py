"""Original-clock full140 external observer; no scientific qualification."""
import time
ORIGIN=time.monotonic()
import argparse,hashlib,json,math,os,shutil,signal,stat,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
BOOT={'bytes': 1613, 'sha256': 'da3efeb07fe97a3916f1e01df6916b00fe61a55f1bef0ad68fd4f2b174f80977'}
def boot():
    p=HERE/'bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT['bytes']+1)
    if len(raw)!=BOOT['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT['sha256']:raise ValueError('bootstrap pin')
    m=types.ModuleType('neural038_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

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

def validate_cli_commands(rows):
    """Admit only complete, timely, source-compatible command closure evidence."""
    fields={'phase','returncode','error_type','observed_retained_bytes','seconds',
            'client_reaped','cleanup_complete','cleanup_before_original_cutoff',
            'owned_group_absence_observed','leader_exited_with_group_alive',
            'group_probe_or_cleanup_error'}
    if type(rows)is not list or not 1<=len(rows)<=64:raise ValueError('bounded complete CLI evidence')
    for row in rows:
        if type(row)is not dict or set(row)!=fields:raise ValueError('exact CLI evidence fields')
        if type(row['returncode'])is not int or row['returncode']!=0:raise ValueError('natural CLI zero')
        if row['error_type'] is not None or row['group_probe_or_cleanup_error'] is not None:raise ValueError('error-free CLI closure')
        for name in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed'):
            if row[name] is not True:raise ValueError('strict complete timely CLI closure')
        if row['leader_exited_with_group_alive'] is not False:raise ValueError('no surviving CLI descendants')
        if type(row['phase'])is not str or not 1<=len(row['phase'].encode('utf-8'))<=128:raise ValueError('bounded CLI phase')
        if type(row['observed_retained_bytes'])is not int or not 0<=row['observed_retained_bytes']<=21400000:raise ValueError('bounded CLI retained bytes')
        seconds=row['seconds']
        try:finite=type(seconds)in(int,float) and seconds>=0 and math.isfinite(seconds)
        except OverflowError:finite=False
        if not finite:raise ValueError('finite nonnegative CLI duration')

def admit(c,root,terminal,source,binding,deadline,read):
    tick=lambda:c.before(deadline)
    scope=binding['scope']
    c.need(terminal.get('schema')=='neural038_full140_worker_v1' and terminal.get('status')=='complete_unqualified' and terminal.get('source')==source and terminal.get('scope')==scope,'exact complete-panel worker terminal')
    c.need(not os.path.lexists(root/'FAILURE.json') and not os.path.lexists(root/'current'),'no failed or retained view')
    v=c.parse(c.capture(root/'COMPLETE.json',32768,terminal['complete'],tick,read))
    c.need(v['source']==source and v['status']=='complete_unqualified' and v['scope']==scope and v['all_public_views_retired'] is True and v['complete_report_schema_support_validated'] is True,'full140 support output, no scope reduction')
    c.need(v['numerical_grading_performed'] is False and v['runtime_qualified'] is False and v['scientific_qualified'] is False,'unqualified auxiliary admission only')
    prepared=c.parse(c.capture(root/'VIEW_PREPARED.json',32768,v['view_prepared'],tick,read))
    expected={Path(r['target']).relative_to('public').as_posix():c.only_pin(r) for r in binding['files'] if r['visibility']=='public'}
    c.need(prepared['files']==expected and prepared['member_count']==25 and prepared['primitive_files']==18 and prepared['decoded'] is False,'original full public view')
    retired=c.parse(c.capture(root/'VIEW_RETIRED.json',8192,v['view_retirement'],tick,read))
    c.need(retired==dict(schema='neural038_full140_public_retired_v1',member_count=25,primitive_files=18,absent=True,parent_fsynced=True),'complete public retirement')
    commitment=c.parse(c.capture(root/'commitment/COMMITMENT.json',8192,v['commitment'],tick,read))
    c.need(commitment['source']==source and commitment['program']==v['program'] and commitment['scope']==scope and commitment['before_any_public_signal_view'] is True,'global program commitment')
    c.capture(root/'commitment/program.py',131072,v['program'],tick,read)
    for phase,key,cap in [('candidate','report',16000000),('admission','admission_output',65536)]:
        record=c.parse(c.capture(root/phase/'NATIVE.json',262144,v[phase+'_native'],tick,read))
        c.need(record['phase']==phase and record['source']==source and record['status']=='captured' and record['output']==v[key],'same phase/source output')
        c.need(record['all_native_resources_closed'] is True and record['cli_reaped'] is True and record['producer_closed_before_capture'] is True and record['recovery_may_be_required'] is False,'producer/native/CLI closure')
        c.need(len(record['closures'])==3 and all(x['closed'] is True for x in record['closures']) and sorted(x['kind'] for x in record['closures'])==['container','container','volume'],'all three resource closures')
        c.need(len({x['name'] for x in record['closures']})==3 and all(x['name'].startswith(record['attempt_prefix']+'-') for x in record['closures']),'exact distinct phase-owned names')
        c.validate_natural_exit(record['natural_exit'])
        validate_cli_commands(record['command_metadata'])
        raw=c.capture(root/phase/'report.json',cap,v[key],tick,read)
        if phase=='admission':
            expected=dict(task_id='NEURAL-038',status='public_structure_consistent_artifact_only',memberships=140,blocks=4,declared_numeric_operands=866,private_reference_calls=0,numeric_comparison_performed=False,scientific_qualification_added=False,operator_entrypoint='neural038_exact_scorer_core_admit_v1',export_manifest_sha256=binding['export_descriptor']['sha256'],requires_observed_cli_exit_zero=True)
            c.need(c.encoded(c.parse(raw))==c.encoded(expected),'auxiliary support result only')
    h=c.parse(c.capture(root/'GRADE_HANDOFF.json',8192,v['grade_handoff'],tick,read))
    c.need(h['report']==dict(path=str(root/'candidate/report.json'),**v['report']) and h['export_descriptor']==binding['export_descriptor'] and h['scope']==scope and h['execution_authorized'] is False and h['scientific_reasoning_or_causality_or_SOTA_established'] is False,'separate unauthorized numerical grade')
    c.need(c.inventory(root,c.RETAIN,2000)[2]<=c.RETAIN-16384,'whole retained output and external slot')
    return v['report'],terminal['complete']

def main():
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','external-output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();deadline=ORIGIN+120;exitcode=2
    def stop(*_):raise TimeoutError('original observer deadline or stop')
    old={s:signal.signal(s,stop) for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    try:
        source=json.loads(a.source_pin);c,manifest,bodies,source_reads=boot().load(HERE,source,deadline)
        c.need(bodies['observe.py']==c.capture(Path(__file__),100000,manifest['files']['observe.py'],lambda:c.before(deadline)),'selected observer')
        policy=c.module(bodies,'policy.py',HERE,c=c);selection_pin=json.loads(a.selection_pin)
        s=policy.selection(c.parse(c.capture(a.selection,32768,selection_pin,lambda:c.before(deadline))),source)
        whole=ORIGIN+policy.whole(s['candidate_seconds']);worker_end=whole-20;outer=whole+60
        output=c.path(a.external_output);root=c.path(s['output'])
        c.need(not os.path.lexists(output) and not os.path.lexists(root) and output!=root and not output.is_relative_to(root) and not root.is_relative_to(output),'fresh separate receipt/attempt')
        c.need(root.parent.stat().st_dev==output.parent.stat().st_dev and os.statvfs(output.parent).f_frsize<=4096,'same bounded filesystem')
        c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+c.RETAIN,'full phase custody before output creation')
        initial=slot(output,c.encoded(dict(schema='neural038_full140_external_v1',status='started',source=source)),deadline,create=True)
        proc=c.module(bodies,'process.py',HERE);cache=Path(str(output)+'.UNUSED-PYCACHE')
        c.need(not os.path.lexists(cache),'fresh unused child cache')
        argv=[str(Path(sys.executable).resolve()),'-I','-S','-B','-X','pycache_prefix='+str(cache),str(HERE/'worker.py'),'--source-pin',a.source_pin,'--selection',a.selection,'--selection-pin',a.selection_pin,'--origin',repr(ORIGIN),'--worker-end',repr(worker_end)]
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')};env['PYTHONDONTWRITEBYTECODE']='1'
        reads=source_reads+65536;record=None;error=None;bundle=None;complete=None;success=False
        def read(n):
            nonlocal reads
            c.need(reads+n<=20000000,'observer whole read ceiling');reads+=n;c.before(whole)
        signal.setitimer(signal.ITIMER_REAL,max(.001,worker_end-time.monotonic()))
        try:
            raw,record=proc.run(argv,worker_end,whole+40,env)
            c.need(time.monotonic()<worker_end,'natural process closure before original worker endpoint')
            c.need(record['natural_exit'] is True and record['exit_code']==0 and record['process_reaped'] and record['process_group_absent'] and record['streams_closed'] and record.get('timer_disable_error','missing') is None and record.get('timer_restore_error','missing') is None,'natural worker closure')
            c.need(not os.path.lexists(cache),'disabled child cache absent')
            signal.setitimer(signal.ITIMER_REAL,max(.001,whole-time.monotonic()))
            bundle,complete=admit(c,root,c.parse(raw),source,c.parse(bodies['BINDINGS.json']),whole,read);success=True
        except BaseException as exc:
            error=type(exc).__name__
            if isinstance(exc,proc.ChildFailure):record=exc.record
        deadline=whole if success else outer
        signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()));c.before(deadline)
        used=c.inventory(root,c.RETAIN,2000)[2] if root.exists() else 0
        c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+max(0,c.RETAIN-used-8192),'terminal retained-capacity guard')
        receipt=dict(schema='neural038_full140_external_v1',status='complete_unqualified' if success else 'failed',source=source,selection=selection_pin,attempt=str(root),argv=argv,child=record,error_type=error,report=bundle,complete=complete,origin_monotonic=ORIGIN,whole_deadline=whole,outer_deadline=outer,elapsed_before_publication=time.monotonic()-ORIGIN,observer_read_reservations=reads,observer_write_reservations=16384,full140_source_scope=True,scientific_qualified=False,runtime_qualified=False,numerical_grading_performed=False,nested_cli_and_native_recovery_may_be_required=not success,host_group_scope='exact worker PGID only; independent Docker CLI groups and native resources require both phase closures; forced outer failure leaves them unresolved',automatic_retry=False)
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
