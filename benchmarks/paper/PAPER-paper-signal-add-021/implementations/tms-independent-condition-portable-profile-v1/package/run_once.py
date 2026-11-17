"""One fresh, operator-selected local run; unchanged full reconstruction/scoring."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import stat
import sys
import time

P=Path(__file__).absolute().parent
EXTERNAL=None
OUT=None
SOURCE_CAP=2097152
READ_CAP=268435456
WRITE_CAP=67108864
ACTIVE=300
TOTAL=360
HOST_RSS_CAP=268435456
MODULES=('common','source_projection','durable_evidence','docker_owner','fixture','packet','runtime','assessment','task_runner','rounding','numerical_controls','bridge')

def portable_bootstrap(source, lock_sha, config_path, config_sha):
    # Only this authenticated owner source is imported; never participant code.
    import importlib.util
    def take(p, cap):
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:
                raise ValueError('bounded portable source')
            parts=[];left=a.st_size
            while left:
                b=os.read(fd,min(left,65536))
                if not b:raise ValueError('short portable source')
                parts.append(b);left-=len(b)
            z=os.fstat(fd);n=Path(p).lstat()
            fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            if any(getattr(a,k)!=getattr(z,k) or getattr(a,k)!=getattr(n,k) for k in fields):
                raise ValueError('unstable portable source')
            return b''.join(parts)
        finally:os.close(fd)
    raw=take(source/'PORTABLE_SOURCE_LOCK.json',65536)
    if hashlib.sha256(raw).hexdigest()!=lock_sha:raise ValueError('portable source lock identity')
    lock=json.loads(raw);entry=lock['members']['portable_config.py']
    body=take(source/'portable_config.py',1048576)
    if (len(body),hashlib.sha256(body).hexdigest())!=(entry['bytes'],entry['sha256']):
        raise ValueError('portable configuration source identity')
    if 'portable_config' in sys.modules:raise ValueError('fresh portable configuration namespace')
    spec=importlib.util.spec_from_file_location('portable_config',source/'portable_config.py')
    mod=importlib.util.module_from_spec(spec);sys.modules['portable_config']=mod
    exec(compile(body,str(source/'portable_config.py'),'exec'),mod.__dict__)
    bodies,total=mod.load_source(str(source),lock_sha)
    cfg=mod.load(config_path,config_sha,source_bodies=bodies)
    mod.state()['source_lock_sha256']=lock_sha
    return mod,cfg,bodies,total+len(raw)+len(body)+mod.state()['config_bytes']


def require(value,message):
    if not value:
        raise ValueError(message)

def ordinary(path,cap,required_mode=None):
    require(path.is_absolute() and '..' not in path.parts and
            not any(x.is_symlink() for x in (path,*path.parents)),'source_path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        require(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<=a.st_size<=cap
                and (required_mode is None or stat.S_IMODE(a.st_mode)==required_mode),'source_file')
        pieces=[];remaining=a.st_size
        while remaining:
            b=os.read(fd,min(65536,remaining));require(bool(b),'complete_source')
            pieces.append(b);remaining-=len(b)
        b=os.fstat(fd);c=path.lstat()
        keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        require(all(getattr(a,k)==getattr(b,k)==getattr(c,k) for k in keys),'source_stable')
        return b''.join(pieces)
    finally:
        os.close(fd)

def checked_attempt(value):
    if type(value) is not str or not (1 <= len(value) <= 64) or value[0] not in 'abcdefghijklmnopqrstuvwxyz0123456789' or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in value):
        raise ValueError('bounded_plain_attempt_id')
    return value

def admit_manifest(raw, expected_sha, attempt):
    checked_attempt(attempt)
    if type(expected_sha) is not str or len(expected_sha) != 64 or any(c not in '0123456789abcdef' for c in expected_sha):
        raise ValueError('manifest_sha256')
    if not (0 < len(raw) <= 65536) or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('root_manifest_identity')
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('duplicate_manifest_key')
            out[key] = value
        return out
    obj = json.loads(raw, object_pairs_hook=pairs)
    if type(obj) is not dict or set(obj) != {'schema', 'attempt_id', 'selection'} or obj['schema'] != 'tms_local_method_reconstruction_run_v1' or obj['attempt_id'] != attempt or type(obj['selection']) is not dict or type(obj['selection'].get('comparator_calibration')) is not bool:
        raise ValueError('closed_root_run_manifest')
    return obj['selection']

def main():
    global OUT,READ_CAP,WRITE_CAP,ACTIVE,TOTAL,EXTERNAL
    start=time.monotonic()
    require(len(sys.argv)==13 and sys.argv[9]=='--config' and sys.argv[11]=='--config-sha256' and sys.argv[1]=='--mode' and sys.argv[2]=='benchmark'
            and sys.argv[7]=='--attempt-id'
            and sys.argv[3]=='--source-lock-sha256' and sys.argv[5]=='--root-selection-sha256'
            and all(len(sys.argv[i])==64 and all(c in '0123456789abcdef' for c in sys.argv[i]) for i in (4,6)),
            'exact_locked_invocation')
    mode=sys.argv[2];lock_sha=sys.argv[4];selection_sha=sys.argv[6]
    attempt=checked_attempt(sys.argv[8])
    if mode=='image':READ_CAP=67108864;WRITE_CAP=33554432;ACTIVE=210;TOTAL=240
    OUT=None  # Set after the same selected configuration is independently authenticated.
    deadline=start+TOTAL;active=start+ACTIVE
    hard=False;loaded={};client_cleanup=[]
    def fatal_exit():
        # A fatal exit cannot qualify. Attempt only registered client groups;
        # no fresh waiting, deadline extension or invented closure observation.
        for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT,signal.SIGUSR1):
            signal.signal(sig,signal.SIG_IGN)
        owner=loaded.get('docker_owner')
        if owner is not None:
            try:owner.kill_registered_clients()
            except BaseException:pass
        os._exit(124)
    def cancelled(signum,frame):
        # Repeated soft signals cannot interrupt the remaining owned cleanup.
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        raise InterruptedError('owner_soft_cancellation')
    def alarm(signum,frame):
        nonlocal hard
        if hard:
            fatal_exit()
        hard=True
        remaining=deadline-time.monotonic()
        if remaining<=0:fatal_exit()
        signal.setitimer(signal.ITIMER_REAL,remaining)
        raise TimeoutError('original_active_window_elapsed')
    signal.signal(signal.SIGALRM,alarm)
    signal.signal(signal.SIGTERM,cancelled)
    signal.signal(signal.SIGINT,cancelled)
    signal.signal(signal.SIGUSR1,lambda signum,frame:fatal_exit())
    remaining=active-time.monotonic();require(remaining>0,'original_active_deadline')
    signal.setitimer(signal.ITIMER_REAL,remaining)
    # The enclosing owner registers this Popen while masking cancellation.
    # Unlike the Docker CLI, this trusted child must process its own original
    # horizon and explicit fatal-cleanup requests after handlers are installed.
    signal.pthread_sigmask(signal.SIG_UNBLOCK,
        {signal.SIGALRM,signal.SIGTERM,signal.SIGINT,signal.SIGUSR1})
    pc,cfg,bodies,read_charge=portable_bootstrap(P,lock_sha,sys.argv[10],sys.argv[12])
    read_charge+=pc.admit_host(cfg);pc.preflight_assets(cfg)
    require(read_charge<READ_CAP,'portable_bootstrap_read_bound')
    EXTERNAL=Path(cfg['workspace']);OUT=EXTERNAL/'attempts'/attempt/(mode+'-01')
    require(set(MODULES).issubset({n[:-3] for n in bodies if n.endswith('.py')}),'complete_portable_owner_modules')
    selected_path=EXTERNAL/'selections'/(attempt+'.json')
    selected_body=ordinary(selected_path,65536,required_mode=0o400);read_charge+=len(selected_body)
    require(hashlib.sha256(selected_body).hexdigest()==selection_sha and read_charge<READ_CAP,'selected_root_operation')
    selected=admit_manifest(selected_body,selection_sha,attempt)
    require(not any(name in sys.modules for name in MODULES),'fresh_owner_modules')
    for name in MODULES:
        spec=importlib.util.spec_from_file_location(name,P/(name+'.py'))
        mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;loaded[name]=mod
        exec(compile(bodies[name+'.py'],str(P/(name+'.py')),'exec'),mod.__dict__)
    loaded['docker_owner'].configure_portable(cfg)
    loaded['packet'].configure_portable(cfg)
    # Refuse the complete root authority before output allocation or Docker CLI work.
    # prepare() repeats this unchanged existing selection check at the input join.
    loaded['bridge'].selection(selected)
    c=loaded['common']
    c.plain(OUT);require(OUT.parent.is_dir(),'prepared_external_parent')
    OUT.mkdir(mode=0o700)
    budget=c.Budget(deadline,READ_CAP,WRITE_CAP);budget.charge_read(read_charge)
    c.write(OUT/'STARTED.private.json',c.encode({'source_lock_sha256':lock_sha,'root_selection_sha256':selection_sha,'mode':mode,
        'maximum_attempts':1,'attempt_id':attempt,'comparator_calibration':selected['comparator_calibration'],
        'original_active_seconds':ACTIVE,'original_total_seconds':TOTAL,
        'source_only_until_selected':True}),budget)
    emergency=OUT/'EMERGENCY_RESERVE.bin'
    c.write(emergency,bytes(65536),budget)
    budget.reserve_write(65536)  # one bounded emergency rewrite, including failure
    def preserve_emergency(error,phase):
        # Reuse reserved space even when the logical write/deadline admission
        # refuses a new file. A changed reserve overrides provisional success.
        body=c.encode({'phase':phase,'class':type(error).__name__,
                       'message_prefix':str(error)[:2048],'partial_outcome':True,
                       'owned_client_fallback_cleanup':client_cleanup})
        require(len(body)<=65536,'bounded_emergency_record')
        os.chmod(emergency,0o600)
        fd=os.open(emergency,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        saved=None
        try:
            at=0
            while at<len(body):
                n=os.write(fd,body[at:]);require(n>0,'emergency_write');at+=n
            os.ftruncate(fd,len(body));os.fsync(fd);os.fchmod(fd,0o400)
        except BaseException as exc:
            saved=exc
        finally:
            try:os.close(fd)
            except BaseException as exc:
                if saved is None:saved=exc
                else:saved.add_note('emergency close: '+type(exc).__name__)
        if saved is not None:raise saved
    result=None;failure=None
    try:
        cli=loaded['docker_owner'].configure_cli(OUT/'private-cli-config',budget)
        c.write(OUT/'CLI_ENDPOINT.private.json',c.encode(cli),budget)
        plan=loaded['bridge'].prepare(selected,root=OUT/'benchmark',source_bodies=bodies,source_root=P,budget=budget)
        documents={'TASK.md':bodies['candidate/TASK.md'],'DATA_SCHEMA.md':bodies['candidate/DATA_SCHEMA.md'],
                   'TASK_CONTRACT.json':bodies['TASK_CONTRACT.json']}
        entry=loaded['task_runner'].execute_authentic(plan,document_bodies=documents,budget=budget,active_deadline=active)
        diagnostic=loaded['bridge'].diagnostics(OUT/'benchmark',budget=budget,calibration=selected['comparator_calibration'])
        result={'schema':'tms_portable_private_reconstruction_owner_result_v1','benchmark_result':entry,
                'secondary_diagnostics':diagnostic,'closed_submissions':2,'model_calls':0,
                'method_specified_reconstruction':True,'paper_only_understanding':False,'native_parity':False,
                'public_redistribution':False,'scientific_qualification':False,
                'portable_config_sha256':pc.state()['sha256']}
        require(not loaded['docker_owner'].registered_clients(),'no_remaining_registered_clients')
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system()=='Linux':peak*=1024
        require(type(peak) is int and peak<=HOST_RSS_CAP,'owner_report_point_rss')
        result.update({'managed_reads':budget.reads,'reserved_write_bytes_before_result':budget.reserved,
                       'successful_write_bytes_before_result':budget.successful,
                       'owner_report_point_rss_bytes':peak,'elapsed_seconds_before_result':time.monotonic()-start})
        c.write(OUT/'RESULT.private.json',c.encode(result),budget)
        members=[];total=0
        for path in sorted(OUT.rglob('*')):
            budget.check()
            st=path.lstat()
            require(stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode),'ordinary_output_tree')
            if not stat.S_ISREG(st.st_mode):continue
            require(st.st_nlink==1 and stat.S_IMODE(st.st_mode)==0o400,'sealed_single_link_output')
            budget.charge_read(st.st_size)
            raw=ordinary(path,st.st_size)
            require(len(raw)==st.st_size,'complete_census_body_extent')
            members.append({'path':str(path.relative_to(OUT)),'bytes':len(raw),
                            'sha256':hashlib.sha256(raw).hexdigest()})
            total+=len(raw)
            require(len(members)<=256,'finite_output_file_census')
        require(total<=WRITE_CAP,'whole_retained_limit')
        c.write(OUT/'CUSTODY.private.json',c.encode({'schema':'tms_p21_complete_private_custody_v1',
            'members':members,'bytes_before_custody':total,'self_excluded':True,
            'managed_reads_before_custody':budget.reads,'original_deadline_admitted':True}),budget)
        for path in sorted((x for x in OUT.rglob('*') if x.is_dir()),key=lambda x:len(x.parts),reverse=True):
            os.chmod(path,0o500)
        os.chmod(OUT,0o500)
        budget.check()
        print(json.dumps({'status':'COMPLETE_PENDING_INDEPENDENT_REVIEW','mode':mode,
                          'containers':1 if mode=='image' else 2,'original_mat_reads':0,
                          'models':0,'scientific_qualification':False,'results_private':True}),flush=True)
        budget.check()
    except BaseException as error:
        # Applies to image clients as well as candidate clients. This fallback
        # cannot turn a failed command into success or assert capture EOF.
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            client_cleanup=loaded['docker_owner'].cleanup_registered_clients(deadline)
        except BaseException as cleanup_error:
            client_cleanup=[{'fallback_error_class':type(cleanup_error).__name__,
                             'closure_unestablished':True}]
        failure={'class':type(error).__name__,'message':str(error)}
        failure['owned_client_fallback_cleanup']=client_cleanup
        try:
            c.write(OUT/'FAILURE.private.json',c.encode(failure),budget)
        except BaseException as secondary:
            failure['preservation_failure_class']=type(secondary).__name__
        try:
            preserve_emergency(error,'complete_owner_or_finalization')
        except BaseException as secondary:
            failure['emergency_preservation_failure_class']=type(secondary).__name__
    if failure is not None:
        print(json.dumps({'status':'FAILED_PRESERVED_OR_PARTIAL','class':failure['class'],
                          'preservation_failure_class':failure.get('preservation_failure_class'),
                          'emergency_preservation_failure_class':failure.get('emergency_preservation_failure_class'),
                          'automatic_retry':False}),flush=True)
        return 1
    return 0

if __name__=='__main__':
    os.umask(0o077)
    raise SystemExit(main())

