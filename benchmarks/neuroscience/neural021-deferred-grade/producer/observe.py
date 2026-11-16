"""Original-clock full92 external observer; no scientific qualification."""
import time
ORIGIN=time.monotonic()
import argparse,hashlib,json,math,os,re,shutil,signal,stat,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
BOOT={'bytes': 1613, 'sha256': '4dcfda207b80696918afd539804ab666c384e2cccf2d17ea767c446a0ae2d5c0'}
def boot():
    p=HERE/'bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT['bytes']+1)
    if len(raw)!=BOOT['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT['sha256']:raise ValueError('bootstrap pin')
    m=types.ModuleType('neural021_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

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
        if type(row['observed_retained_bytes'])is not int or not 0<=row['observed_retained_bytes']<=24000000:raise ValueError('bounded CLI retained bytes')
        seconds=row['seconds']
        try:finite=type(seconds)in(int,float) and seconds>=0 and math.isfinite(seconds)
        except OverflowError:finite=False
        if not finite:raise ValueError('finite nonnegative CLI duration')

def admit(c,root,terminal,source,binding,selection,deadline,read):
    tick=lambda:c.before(deadline)
    scope=binding['scope'];program=c.only_pin(selection['program'])
    c.need(terminal.get('schema')=='neural021_full92_worker_v1' and terminal.get('status')=='complete_unqualified' and terminal.get('source')==source and terminal.get('scope')==scope,'exact complete-panel worker terminal')
    c.need(not any(os.path.lexists(root/name) for name in ('FAILURE.json','current','support')),'no failed or retained public view')
    v=c.parse(c.capture(root/'COMPLETE.json',32768,terminal['complete'],tick,read))
    c.need(v['schema']=='neural021_full92_complete_v1' and v['source']==source and v['program']==program and v['status']=='complete_unqualified' and v['scope']==scope,'same complete source/program/scope')
    for key in ('all_public_views_retired','complete_public_format_validated','external_natural_zero_required'):
        c.need(v[key] is True,'complete public-format and retirement proof')
    for key in ('numerical_grading_performed','semantic_training_compliance_proven','runtime_qualified','scientific_qualified'):
        c.need(v[key] is False,'unqualified public admission; no semantic/numerical inference')
    c.need(set(v['views'])=={'fit','infer','support'} and set(v['native'])=={'fit','infer','admission'},'all three ordered phases represented')
    public={r['target']:c.only_pin(r) for r in binding['files'] if r['visibility']=='public'}
    for phase in ('fit','infer','support'):
        expected_names=binding['phase_public_members'][phase] if phase!='support' else ['public/interface.py','public/cases.json']
        expected={Path(name).relative_to('public').as_posix():public[name] for name in expected_names}
        prepared=c.parse(c.capture(root/('VIEW_'+phase+'_PREPARED.json'),32768,v['views'][phase]['prepared'],tick,read))
        c.need(prepared['schema']=='neural021_phase_view_v1' and prepared['phase']==phase and prepared['files']==expected and type(prepared['member_count'])is int and prepared['member_count']==len(expected) and prepared['decoded'] is False,'exact phase-specific public view')
        retired=c.parse(c.capture(root/('VIEW_'+phase+'_RETIRED.json'),8192,v['views'][phase]['retired'],tick,read))
        expected_retired=dict(schema='neural021_phase_retired_v1',phase=phase,member_count=len(expected),absent=True,parent_fsynced=True)
        c.need(c.encoded(retired)==c.encoded(expected_retired),'complete phase view retirement')
    commitment=c.parse(c.capture(root/'commitment/COMMITMENT.json',8192,v['commitment'],tick,read))
    c.need(commitment['source']==source and commitment['program']==program and commitment['scope']==scope and commitment['method_review']==c.only_pin(selection['method_review']) and commitment['before_any_public_signal_view'] is True,'same globally committed candidate and method review')
    c.capture(root/'commitment/program.py',1048576,program,tick,read)
    state=c.exact_pin(v['state']);c.need(state['bytes']<=16777216,'opaque state cap')
    seal=c.parse(c.capture(root/'STATE_COMMITTED.json',8192,v['state_commitment'],tick,read))
    c.need(seal['schema']=='neural021_state_seal_v1' and seal['source']==source and seal['program']==program and seal['state']==state and seal['fit_native']==v['native']['fit'] and seal['fit_retirement']==v['views']['fit']['retired'],'fit-state native/retirement seal chain')
    c.need(seal['before_any_query_view'] is True and seal['readonly_owned_state'] is True and seal['semantic_training_only_compliance_proven'] is False and seal['training_only_lazy_computation_permitted'] is True,'custody timing distinct from semantic compliance')
    outputs=v['outputs'];c.need(type(outputs)is dict and set(outputs)=={'submission.json'},'complete prediction artifact')
    c.need(c.exact_pin(outputs['submission.json'])['bytes']<=4194304,'unchanged4MiB submission domain')
    sealed=c.parse(c.capture(root/'SUBMISSION_COMMITTED.json',8192,v['outputs_commitment'],tick,read))
    c.need(sealed['source']==source and sealed['program']==program and sealed['state_commitment']==v['state_commitment'] and sealed['outputs']==outputs and sealed['infer_native']==v['native']['infer'] and sealed['infer_retirement']==v['views']['infer']['retired'] and sealed['public_format_not_yet_validated'] is True and sealed['numerically_validated'] is False,'whole batch sealed after inference closure before public admission')
    for phase,expected_outputs in [('fit',{'state.bin':state}),('infer',outputs),('admission',{'support.json':v['admission_output']})]:
        record=c.parse(c.capture(root/phase/'NATIVE.json',262144,v['native'][phase],tick,read))
        c.need(record['schema']=='neural021_owned_phase_v1' and record['phase']==phase and record['source']==source and record['status']=='captured' and record['outputs']==expected_outputs,'same source/phase complete artifact')
        c.need(record['all_native_resources_closed'] is True and record['cli_reaped'] is True and record['producer_closed_before_capture'] is True and record['recovery_may_be_required'] is False and record['numerical_grading_called'] is False and record['error_type'] is None,'error-free producer/native/CLI closure')
        prefix=record['attempt_prefix'];c.need(type(prefix)is str and re.fullmatch('neural021-[0-9a-f]{24}',prefix),'exact phase-owned prefix')
        expected_resources={(prefix+'-'+phase,'container'),(prefix+'-holder','container'),(prefix+'-volume','volume')}
        closures=record['closures'];c.need(type(closures)is list and len(closures)==3 and {(x['name'],x['kind']) for x in closures}==expected_resources,'exact three distinct owned resources')
        for x in closures:
            c.need(set(x)=={'kind','name','removed','absence_observed','creation_outcome_unknown','closed'} and x['closed'] is True and x['removed'] is True and x['absence_observed'] is True and x['creation_outcome_unknown'] is False,'fully acknowledged removed native resource')
        c.natural_zero(record['natural_exit']);validate_cli_commands(record['command_metadata'])
        for name,pin in expected_outputs.items():
            cap={'state.bin':16777216,'submission.json':4194304,'support.json':262144}[name]
            raw=c.capture(root/phase/name,cap,pin,tick,read)
            if name=='support.json':
                expected=dict(task_id='NEURAL-021',status='public_format_admitted_ungraded',query_trials=92,active_queries=52,perturbation_queries=40,time_bins=30,velocity_axes=2,cases_sha256=binding['cases']['sha256'],private_target_calls=0,numerical_values_verified=False,scientific_qualification_added=False,operator_entrypoint='neural021_full92_public_support_v1',requires_observed_cli_exit_zero=True)
                c.need(c.encoded(c.parse(raw))==c.encoded(expected),'public format-only result')
    h=c.parse(c.capture(root/'GRADE_HANDOFF.json',8192,v['grade_handoff'],tick,read))
    c.need(h['task_id']=='NEURAL-021' and h['submission']==dict(path=str(root/'infer/submission.json'),**outputs['submission.json']) and h['export_descriptor']==binding['export_descriptor'] and h['scope']==scope,'separate complete-panel grade operand')
    for key in ('execution_authorized','baselines_executed','semantic_training_compliance_proven','scientific_reasoning_or_causality_or_SOTA_established'):
        c.need(h[key] is False,'no numerical/scientific outcome from public admission')
    c.need(h['new_budget_and_external_observer_required'] is True and h['private_target_calls_this_run']==0 and h['condition_R2_negative_null_and_loss_preserved'] is True and h['time_template_comparison_required_for_interpretation'] is True,'unchanged separately selected grading boundary')
    c.need(c.inventory(root,c.RETAIN,2000)[2]<=c.RETAIN-16384,'whole retained output and external slot')
    return outputs,terminal['complete']

def main():
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','external-output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();deadline=ORIGIN+120;exitcode=2
    def stop(*_):raise TimeoutError('original observer deadline or stop')
    old={}
    try:
        for number in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):old[number]=signal.signal(number,stop)
        signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
        source=json.loads(a.source_pin);c,manifest,bodies,source_reads=boot().load(HERE,source,deadline)
        c.need(bodies['observe.py']==c.capture(Path(__file__),100000,manifest['files']['observe.py'],lambda:c.before(deadline)),'selected observer')
        policy=c.module(bodies,'policy.py',HERE,c=c);selection_pin=json.loads(a.selection_pin)
        s=policy.selection(c.parse(c.capture(a.selection,32768,selection_pin,lambda:c.before(deadline))),source)
        whole=ORIGIN+policy.whole(s['fit_seconds'],s['infer_seconds']);worker_end=whole-20;outer=whole+60
        output=c.path(a.external_output);root=c.path(s['output'])
        c.need(not os.path.lexists(output) and not os.path.lexists(root) and output!=root and not output.is_relative_to(root) and not root.is_relative_to(output),'fresh separate receipt/attempt')
        c.need(root.parent.stat().st_dev==output.parent.stat().st_dev and os.statvfs(output.parent).f_frsize<=4096,'same bounded filesystem')
        c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+c.RETAIN,'full phase custody before output creation')
        initial=slot(output,c.encoded(dict(schema='neural021_full92_external_v1',status='started',source=source)),deadline,create=True)
        proc=c.module(bodies,'process.py',HERE);cache=Path(str(output)+'.UNUSED-PYCACHE')
        c.need(not os.path.lexists(cache),'fresh unused child cache')
        argv=[str(Path(sys.executable).resolve()),'-I','-S','-B','-X','pycache_prefix='+str(cache),str(HERE/'worker.py'),'--source-pin',a.source_pin,'--selection',a.selection,'--selection-pin',a.selection_pin,'--origin',repr(ORIGIN),'--worker-end',repr(worker_end)]
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')};env['PYTHONDONTWRITEBYTECODE']='1'
        reads=source_reads+131072;record=None;error=None;bundle=None;complete=None;success=False
        def read(n):
            nonlocal reads
            c.need(reads+n<=64000000,'observer whole read ceiling');reads+=n;c.before(whole)
        signal.setitimer(signal.ITIMER_REAL,max(.001,worker_end-time.monotonic()))
        try:
            raw,record=proc.run(argv,worker_end,whole+40,env)
            c.need(time.monotonic()<worker_end,'natural process closure before original worker endpoint')
            c.need(record['natural_exit'] is True and record['exit_code']==0 and record['process_reaped'] and record['process_group_absent'] and record['streams_closed'],'natural worker closure')
            c.need(not os.path.lexists(cache),'disabled child cache absent')
            signal.setitimer(signal.ITIMER_REAL,max(.001,whole-time.monotonic()))
            bundle,complete=admit(c,root,c.parse(raw),source,c.parse(bodies['BINDINGS.json']),s,whole,read);success=True
        except BaseException as exc:
            error=type(exc).__name__
            if isinstance(exc,proc.ChildFailure):record=exc.record
        deadline=whole if success else outer
        signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()));c.before(deadline)
        used=c.inventory(root,c.RETAIN,2000)[2] if root.exists() else 0
        c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+max(0,c.RETAIN-used-8192),'terminal retained-capacity guard')
        receipt=dict(schema='neural021_full92_external_v1',status='complete_unqualified' if success else 'failed',source=source,selection=selection_pin,attempt=str(root),argv=argv,child=record,error_type=error,outputs=bundle,complete=complete,origin_monotonic=ORIGIN,whole_deadline=whole,outer_deadline=outer,elapsed_before_publication=time.monotonic()-ORIGIN,observer_read_reservations=reads,observer_write_reservations=16384,full92_source_scope=True,scientific_qualified=False,runtime_qualified=False,numerical_grading_performed=False,nested_cli_and_native_recovery_may_be_required=not success,host_group_scope='exact worker PGID only; independent Docker CLI groups and native resources require all three phase closures; forced outer failure leaves them unresolved',automatic_retry=False)
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
