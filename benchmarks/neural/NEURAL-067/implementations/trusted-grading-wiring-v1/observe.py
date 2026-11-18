"""Independent absolute-clock parent; forced host stops remain unresolved failures."""
import time
ORIGIN=time.monotonic()
import argparse,base64,hashlib,json,os,re,signal,stat,sys,types
from pathlib import Path
HERE=Path(__file__).absolute().parent
PROCESS={'bytes':6710,'sha256':'791ea3b0bab72ef4487b3c3fdd47a828f8effaa27ebf7a6872e3b4ed324e074d'}
BOOT='import base64,sys;b=base64.b64decode(sys.argv.pop(1));p=sys.argv.pop(1);sys.argv[0]=p;exec(compile(b,p,"exec"),{"__name__":"__main__","__file__":p})'

def bootstrap_capture(path,pin):
    p=Path(path).absolute()
    if any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('linked bootstrap')
    fd=os.open(p,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd)
        if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=200000 and a.st_size==pin['bytes']):raise ValueError('bootstrap extent')
        with os.fdopen(fd,'rb',closefd=False) as f:b=f.read(200001)
        sig=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(b)!=a.st_size or hashlib.sha256(b).hexdigest()!=pin['sha256'] or sig(a)!=sig(os.fstat(fd)) or sig(a)!=sig(p.lstat()):raise ValueError('bootstrap pin')
        return b
    finally:os.close(fd)

def role(io,path,pin,policy=None):
    v=io.parse(io.capture(path,200000,pin));state=v.get('natural_state');clean=v.get('cleanup')
    io.need(v.get('error_type') is None and v.get('role_deadline_met') is True and state
        and state['ExitCode']==0 and state['OOMKilled'] is False and state['Running'] is False
        and clean and clean['owned_absence_confirmed'] is True and not clean.get('forced_stop')
        and not clean.get('creation_outcome_unknown',False),'natural zero and exact owned-resource absence')
    if 'attach' in v:
        a=v['attach']
        io.need(v.get('status')=='complete' and v.get('all_owned_absent') is True and a
            and a.get('attach_reaped') is True and a.get('attach_group_absent') is True
            and a.get('selector_closed') is True and a.get('finished') is True
            and a.get('natural_returncode')==0 and a.get('error_type') is None
            and not a.get('forced_attach_stop') and a.get('deadline_met') is True
            and a.get('streams_closed')=={'stdin':True,'stdout':True,'stderr':True},'independently joined causal attach closure')
    if policy is not None:
        mappings=(list(v['mount_admissions'].values()) if 'mount_admissions' in v else
                  [v.get('created_mount_admission'),v.get('finished_mount_admission')])
        io.need(len(mappings)==2 and all(type(x)is dict and x.get('mount_source_policy')==policy for x in mappings),'root-selected mount policy in both role inspections')
    return v

def admit(io,attempt,raw,record,source_pin,bodies,selection):
    io.need(record['natural_exit'] is True and record['exit_code']==0 and record['process_reaped'] is True
        and record['process_group_absent'] is True and record['streams_closed'] is True
        and not record['timed_out'] and not record['kill_sent'] and record['error_type'] is None,'natural complete controller')
    cp=io.capture(attempt/'COMPLETION.json',100000);v=io.parse(cp);lock=io.parse(bodies['LOCK.json'])
    io.need(v['success'] is True and v['source_manifest']==source_pin and v['scope']==lock['scope']
        and v['query_blocks']==56 and v['committed_arm_rows']==137960
        and v['runtime_qualified'] is False and v['scientific_qualification'] is False
        and v['mechanism_adherence_proven'] is False,'complete full original task')
    seal=io.parse(io.capture(attempt/'PROGRAM_COMMIT.json',200000,v['program_commit']))
    daemon=io.parse(io.capture(attempt/'DAEMON.json',20000))
    io.need(daemon['mount_source_policy']==selection['mount_source_policy'] and daemon['observed']==v['daemon_observed']
        and daemon['docker_socket']==selection['docker_socket'] and daemon['docker_socket_identity']==selection['docker_socket_identity'],'selected local daemon and alias policy')
    from mount_policy import gate
    gate(selection['mount_source_policy'],daemon['observed'])
    io.need(seal['no_training_release_before_commit'] is True and seal['program']=={k:selection['program'][k] for k in ('bytes','sha256')}
        and seal['method']=={k:selection['method'][k] for k in ('bytes','sha256')},'genuine sealed program')
    states=io.parse(io.capture(attempt/'STATES_SEALED.json',100000,v['states_sealed']))
    io.need(states['states']==v['training'] and states['program_commit']==v['program_commit']
        and [r['arm'] for r in v['training']]==lock['design']['arms'],'four independently trained states before queries')
    for t in v['training']:
        arm=t['arm'];role(io,attempt/('fit-'+arm)/'HOST.json',t['producer_host'],selection['mount_source_policy'])
        io.capture(attempt/'states'/(arm+'.bin'),33554432,t['state'])
        retired=io.parse(io.capture(attempt/('train-'+arm)/'RETIRED.json',100000,t['retired']))
        closed=io.parse(io.capture(attempt/('train-'+arm)/'CLOSED.json',100000,retired['closed']))
        io.need(closed['admission']==t['admission'] and closed['link']['state']==t['state']
            and retired['output_absent'] is True and not os.path.lexists(attempt/('train-'+arm)/'output'),'closed then retired masked training view')
        admission=io.parse(io.capture(attempt/('train-'+arm)/'ADMISSION.json',100000,t['admission']))
        role(io,attempt/('train-'+arm)/'HOST.json',admission['host'],selection['mount_source_policy'])
    expected=[(r,a) for r in lock['design']['query'] for a in lock['design']['arms']]
    io.need(len(v['queries'])==56,'all query blocks')
    for index,(q,(r,a)) in enumerate(zip(v['queries'],expected)):
        io.need((q['run'],q['arm'])==(r['run'],a),'fixed full ordered query roster')
        phase=attempt/'queries'/f'{index:02d}';role(io,phase/'HOST.json',q['host'],selection['mount_source_policy'])
        closed=io.parse(io.capture(phase/'CLOSED.json',100000,q['closed']))
        io.need(closed['journal']==q['journal'] and closed['states_sealed']==v['states_sealed']
            and closed['program_commit']==v['program_commit'] and closed['committed_rows']==r['n_rows']
            and closed['all_owned_absent'] is True,'causal full-support journal closure')
        j=q['journal'];io.need(j['file']==r['run']+'__'+a+'.bin' and j['bytes']==4096+r['n_rows']*160,'exact journal extent/name')
        io.capture(attempt/'journals'/j['file'],j['bytes'],j)
    retired=io.parse(io.capture(attempt/'cache/RETIRED.json',100000,v['cache_retired']))
    closed=io.parse(io.capture(attempt/'cache/CLOSED.json',100000,retired['closed']))
    io.need(closed['admission']==v['cache_admission'] and retired['output_absent'] is True
        and not os.path.lexists(attempt/'cache/output'),'query cache removed only after complete streams')
    ca=io.parse(io.capture(attempt/'cache/ADMISSION.json',100000,v['cache_admission']));role(io,attempt/'cache/HOST.json',ca['host'],selection['mount_source_policy'])
    admit_grade(io,attempt,v,lock,bodies,selection)
    io.need(v['controlled_read_reservations']<=io.READ and v['write_reservations_before_final']<=io.WRITE,'shared resource caps')
    io.need(io.parse(raw)=={'success':True,'query_blocks':56,'committed_arm_rows':137960,'scientific_qualification':False},'exact successful host terminal')
    return io.identity(cp)

def admit_grade(io,attempt,v,lock,bodies,selection):
    """Join the new grade receipts without changing participant/cleanup policy."""
    entries=[q['journal'] for q in v['queries']]
    expected=[(r['run'],a,4096+r['n_rows']*160) for r in lock['design']['query'] for a in lock['design']['arms']]
    io.need(len(entries)==56 and [(x['run'],x['arm'],x['bytes']) for x in entries]==expected,
            'complete ordered original journal grading support')
    joined=io.parse(io.capture(attempt/'GRADING_INPUT.json',100000,v['grading_input']))
    io.need(joined=={'schema':'neural067_closed_journal_grading_input_v1','journals':entries,
        'all_query_producers_absent':True,'program_commit':v['program_commit'],'states_sealed':v['states_sealed'],
        'contract_sha256':lock['trusted_grading']['contract_sha256']},'closed journal source/contract link')
    ga=io.parse(io.capture(attempt/'grade/ADMISSION.json',100000,v['grade']['admission']))
    io.need(ga['host']==v['grade']['host'] and ga['worker']==v['grade']['worker'],'exact grade receipt binding')
    invraw=io.capture(attempt/'grade/INVOCATION.json',100000,ga['invocation']);inv=io.parse(invraw)
    io.need(inv['schema']=='neural067_worker_invocation_v1' and inv['mode']=='grade' and inv['journals']==entries
        and inv['grading_evidence']==lock['grading_evidence'] and inv['worker_source']==io.identity(bodies['worker/worker.py'])
        and inv['design']==lock['design_pin'],'exact current grading invocation')
    worker=io.parse(io.capture(attempt/'grade/output/WORKER.json',100000,ga['worker']))
    io.need(worker['mode']=='grade' and worker['invocation']==io.identity(invraw) and worker['worker_source']==inv['worker_source']
        and worker['package_files']==inv['files'] and worker['requires_external_natural_exit'] is True
        and worker['runtime_qualified'] is False and worker['scientific_qualification'] is False
        and worker['result']=={'status':'scored_current_session_contract','scientific_score_computed':True,
            'scientific_qualification':False,'causal_program_execution_verified':False,
            'contract_sha256':lock['trusted_grading']['contract_sha256'],'journal_blocks':56},'current worker grade admission')
    io.need(ga['files']=={**worker['files'],'WORKER.json':ga['worker']}
        and worker['files']=={'data/score.json':v['grade']['score']},'only bounded current score output')
    role(io,attempt/'grade/HOST.json',ga['host'],selection['mount_source_policy'])
    score=io.parse(io.capture(attempt/'grade/output/data/score.json',1000000,v['grade']['score']))
    io.need(score['schema']=='neural067_session_grade_v1' and score['contract_sha256']==lock['trusted_grading']['contract_sha256']
        and score['query_runs']==14 and score['query_sessions']==7 and score['full_rows_per_arm']==34490
        and set(score['arms'])==set(lock['design']['arms']) and score['causal_program_execution_verified'] is False,
        'current session score identity; negative and undefined values preserved')


def unresolved(io,attempt):
    paths=['cache','assemble','grade']+['train-'+a for a in ('neural','clock','neural_clock','shifted_neural_clock')]
    paths+=['fit-'+a for a in ('neural','clock','neural_clock','shifted_neural_clock')]+['queries/'+f'{i:02d}' for i in range(56)]
    rows=[]
    for p in paths:
        row={'phase':p,'owned_absence_verified':False,'state':'missing_or_unreadable'}
        try:
            b=io.capture(attempt/p/'INTENT.json',65536);v=io.parse(b)
            name,owner=v.get('name'),v.get('owner')
            io.need(type(name)is str and re.fullmatch(r'neural067-(trusted|train|query)-[a-f0-9]{32}',name)
                and type(owner)is str and re.fullmatch('[a-f0-9]{32}',owner),'safe exact owned selectors')
            row.update(state='captured_unadmitted',intent=io.identity(b),name=name,owner=owner)
            source=v.get('program_sha256')
            if source is not None:
                io.need(type(source)is str and re.fullmatch('[a-f0-9]{64}',source),'safe exact program source selector')
                row['program_sha256']=source
            try:
                b=io.capture(attempt/p/'CREATED.json',32768);created=io.parse(b)
                identifier=created.get('container_id',created.get('identifier'))
                io.need(type(identifier)is str and re.fullmatch('[a-f0-9]{64}',identifier)
                    and created.get('name')==name and created.get('owner')==owner,'matching exact created identity')
                if source is not None:io.need(created.get('program_sha256')==source,'matching created source selector')
                row.update(created=io.identity(b),identifier=identifier)
            except BaseException as e:row['created_error_type']=type(e).__name__
        except BaseException as e:row['error_type']=type(e).__name__
        rows.append(row)
    return {'automatic_daemon_recovery':False,'operator_recovery_required_before_retry':True,'phases':rows}

def main(argv=None):
    end=ORIGIN+10860;code=2;io=budget=attempt=root=None;result={'success':False,'scientific_qualification':False}
    try:
        p=argparse.ArgumentParser(add_help=False)
        for n in ('source-bytes','selection-bytes'):p.add_argument('--'+n,type=int,required=True)
        for n in ('source-sha256','selection-sha256'):p.add_argument('--'+n,required=True)
        p.add_argument('--selection',type=Path,required=True);a=p.parse_args(argv)
        if not(sys.flags.isolated and sys.dont_write_bytecode and sys.pycache_prefix and not os.path.lexists(sys.pycache_prefix)):raise ValueError('fresh cache before imports')
        sp={'bytes':a.source_bytes,'sha256':a.source_sha256}
        manifest=json.loads(bootstrap_capture(HERE/'SOURCE_MANIFEST.json',sp))
        entries=[r for r in manifest['files'] if r['path']=='run_program.py']
        if len(entries)!=1:raise ValueError('unique exact entry pin')
        bootstrap=bootstrap_capture(HERE/'run_program.py',entries[0])
        m=types.ModuleType('_neural067_bootstrap');m.__file__=str(HERE/'run_program.py');exec(compile(bootstrap,m.__file__,'exec'),m.__dict__)
        rows,bodies=m.source(sp)
        if bootstrap!=bodies['run_program.py']:raise ValueError('bootstrap must join selected source')
        import runtime_io as io
        original_capture=io.capture
        read_reserve=[10000000] # Captured bootstrap/source and post-source closure allowance.
        def counted_capture(path,limit,expected=None):
            charge=expected['bytes'] if expected is not None else limit
            if read_reserve[0]+charge>400000000:raise ValueError('shared parent read reservation')
            read_reserve[0]+=charge
            return original_capture(path,limit,expected)
        io.capture=counted_capture
        selection_pin={'bytes':a.selection_bytes,'sha256':a.selection_sha256}
        selection=m.selected(io.parse(m.cap(a.selection,selection_pin)),sp)
        attempt=io.ordinary(selection['attempt']);root=attempt.with_name(attempt.name+'.observer')
        io.need(sys.flags.isolated and sys.dont_write_bytecode and sys.pycache_prefix==str(root/'.disabled-pycache')
            and not os.path.lexists(sys.pycache_prefix) and not os.path.lexists(root) and not os.path.lexists(attempt),'fresh exact isolated namespace')
        io.need(root.parent.stat().st_dev==Path(selection['repository']).stat().st_dev,'same physical volume')
        s=os.statvfs(root.parent);io.need(s.f_bavail*s.f_frsize>=io.FLOOR+selection['other_bytes']+io.OWN,'full phase reservation')
        budget=io.Budget(root,selection['other_bytes'],end,(root,attempt),write_limit=131072,meta_limit=131072);budget.mkdir(root)
        command=[sys.executable,'-I','-B','-X','pycache_prefix='+str(attempt/'.disabled-pycache'),'-c',BOOT,
            base64.b64encode(bodies['run_program.py']).decode(),str(HERE/'run_program.py'),
            '--source-bytes',str(a.source_bytes),'--source-sha256',a.source_sha256,'--selection',str(a.selection),
            '--selection-bytes',str(a.selection_bytes),'--selection-sha256',a.selection_sha256,'--normal-deadline',repr(ORIGIN+10800)]
        budget.save(root/'START.json',{'source_manifest':sp,'selection':selection_pin,
            'argv_shape':command[:6]+['captured_bootstrap','captured_entry_bytes']+command[8:],
            'normal_seconds':10800,'host_cleanup_seconds':20,'outer_seconds':10860})
        io.need({k:rows['process.py'][k] for k in ('bytes','sha256')}==PROCESS,'unchanged parent process helper')
        helper=io.module(bodies['process.py'],'_neural067_child',HERE/'process.py')
        try:raw,record=helper.run(command,ORIGIN+10800,ORIGIN+10820,{'PATH':'/usr/bin:/bin','HOME':os.environ.get('HOME','/tmp'),'PYTHONDONTWRITEBYTECODE':'1'})
        except helper.ChildFailure as e:raw=b'';record=e.record
        result['child']=record;io.need(type(record.get('pid'))is int and record['pid']>1,'known host process')
        result['independent_host_group_absent']=helper.group_absent(record['pid'])
        io.need(result['independent_host_group_absent'] is True,'independent host group absence')
        completion=admit(io,attempt,raw,record,sp,bodies,selection)
        for n,r in rows.items():m.cap(HERE/n,r)
        m.cap(HERE/'SOURCE_MANIFEST.json',sp)
        io.need(not os.path.lexists(sys.pycache_prefix) and not os.path.lexists(attempt/'.disabled-pycache'),'no cache writes')
        result.update(success=True,completion=completion,source_manifest=sp,selection=selection_pin,
            runtime_qualified=False,mechanism_adherence_proven=False,parent_controlled_read_reservations=read_reserve[0])
    except BaseException as e:
        result.update(success=False,error_type=type(e).__name__)
        if io is not None and attempt is not None:result['unresolved_resource_obligations']=unresolved(io,attempt)
    try:
        if budget is not None:
            budget.save(root/'OBSERVATION.json',result,cap=120000);budget.tick()
            print(json.dumps({'success':result['success'],'scientific_qualification':False}),flush=True)
            code=0 if result['success'] and time.monotonic()<end else 2
    except BaseException:code=2
    return code if time.monotonic()<end else 2

if __name__=='__main__':
    def stop(*_):raise TimeoutError('outer deadline or controlled interruption')
    for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(s,stop)
    signal.setitimer(signal.ITIMER_REAL,max(.001,ORIGIN+10860-time.monotonic()))
    try:raise SystemExit(main())
    finally:signal.setitimer(signal.ITIMER_REAL,0)
