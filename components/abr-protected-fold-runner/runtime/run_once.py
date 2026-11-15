"""One selected ABR ten-fold campaign using the existing owned lifecycle and cleanup."""
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
PACKAGE=P.parent
EXTERNAL=Path('/OWNER/operation')
OUT=None
SOURCE_CAP=2097152
READ_CAP=21474836480
WRITE_CAP=8589934592
ACTIVE=7200
TOTAL=7320
HOST_RSS_CAP=1073741824
MODULES=('common', 'durable_evidence', 'docker_owner', 'split', 'packet', 'builder', 'score', 'fold_context', 'prepared_manifest', 'fold_runner', 'runner_config')
MODULE_PATHS={'common': 'runtime/common.py', 'durable_evidence': 'runtime/durable_evidence.py', 'docker_owner': 'runtime/docker_owner.py', 'split': 'runtime/split.py', 'packet': 'runtime/packet.py', 'builder': 'runtime/builder.py', 'score': 'runtime/score.py', 'fold_context': 'runtime/fold_context.py', 'prepared_manifest': 'runtime/prepared_manifest.py', 'fold_runner': 'runtime/fold_runner.py', 'runner_config': 'runtime/runner_config.py'}
LOCK_MEMBERS={'CONFIG.json','SUBMISSION_SCHEMA.json','TASK.md','runtime/builder.py','runtime/common.py','runtime/docker_owner.py','runtime/durable_evidence.py','runtime/fold_context.py','runtime/fold_runner.py','runtime/outer_once.py','runtime/packet.py','runtime/prepared_manifest.py','runtime/run_once.py','runtime/runner_config.py','runtime/score.py','runtime/split.py'}
EXECUTABLE_PIN=(52640,'4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1')

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

def execute_stages(wrapper, modules, bodies, *, root, budget, active_deadline):
    c=modules['common'];owner=modules['docker_owner']
    plan=modules['runner_config'].prepare(wrapper,modules,bodies,budget)
    c.write(root/'ADMISSION.private.json',c.encode(plan['admission']),budget)
    result=modules['fold_runner'].execute(plan['selection'],plan['documents'],
        root=root/'benchmark',budget=budget,active_deadline=active_deadline)
    c.need(not owner.registered_clients(),'all ten episodes closed')
    return result

def main():
    global OUT,READ_CAP,WRITE_CAP,ACTIVE,TOTAL
    start=time.monotonic()
    require(len(sys.argv)==11 and sys.argv[1]=='--mode' and sys.argv[2]=='whole'
            and sys.argv[7]=='--attempt-id' and sys.argv[9]=='--outer-deadline'
            and sys.argv[3]=='--source-lock-sha256' and sys.argv[5]=='--root-selection-sha256'
            and all(len(sys.argv[i])==64 and all(c in '0123456789abcdef' for c in sys.argv[i]) for i in (4,6)),
            'exact_locked_invocation')
    mode=sys.argv[2];lock_sha=sys.argv[4];selection_sha=sys.argv[6]
    attempt=checked_attempt(sys.argv[8])
    outer_deadline=float(sys.argv[10])
    require(math.isfinite(outer_deadline) and start+TOTAL+5<outer_deadline<=start+7350,
            'full_original_inner_horizon_within_caller')
    OUT=EXTERNAL/'attempts'/attempt/(mode+'-01')
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
    require(sys.version_info[:3]==(3,11,6) and platform.system()=='Darwin' and
            sys.flags.isolated==1 and sys.flags.no_site==1 and sys.dont_write_bytecode,
            'selected_owner_runtime')
    exe=Path(os.path.realpath(sys.executable));eb=ordinary(exe,EXECUTABLE_PIN[0])
    require((len(eb),hashlib.sha256(eb).hexdigest())==EXECUTABLE_PIN,'selected_owner_executable')
    lock_raw=ordinary(PACKAGE/'EXECUTION_LOCK.json',65536)
    require(hashlib.sha256(lock_raw).hexdigest()==lock_sha,'selected_execution_lock')
    lock=json.loads(lock_raw)
    require(set(lock)=={'schema','members'} and lock['schema']=='abr_fold_whole_owner_lock_v1'
            and set(lock['members'])==LOCK_MEMBERS,'complete_execution_closure')
    bodies={};read_charge=len(lock_raw)+len(eb)
    for name,entry in lock['members'].items():
        require(type(entry) is dict and set(entry)=={'bytes','sha256'} and
                type(entry['bytes']) is int and 0<=entry['bytes']<=1048576,'source_pin')
        body=ordinary(PACKAGE/name,entry['bytes']);read_charge+=len(body)
        require(read_charge<=SOURCE_CAP and len(body)==entry['bytes'] and
                hashlib.sha256(body).hexdigest()==entry['sha256'],'source_body_identity')
        bodies[name]=body
    selected_path=EXTERNAL/'selections'/(attempt+'.json')
    selected_body=ordinary(selected_path,65536,required_mode=0o400);read_charge+=len(selected_body)
    require(hashlib.sha256(selected_body).hexdigest()==selection_sha and read_charge<=SOURCE_CAP,'selected_root_operation')
    require(not any(name in sys.modules for name in MODULES),'fresh_owner_modules')
    for name in MODULES:
        spec=importlib.util.spec_from_file_location(name,PACKAGE/MODULE_PATHS[name])
        mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;loaded[name]=mod
        exec(compile(bodies[MODULE_PATHS[name]],str(PACKAGE/MODULE_PATHS[name]),'exec'),mod.__dict__)
    wrapper=loaded['runner_config'].admit_manifest(selected_body,selection_sha,attempt)
    c=loaded['common']
    c.plain(OUT);require(OUT.parent.is_dir(),'prepared_external_parent')
    OUT.mkdir(mode=0o700)
    budget=c.Budget(deadline,READ_CAP,WRITE_CAP);budget.charge_read(read_charge)
    c.write(OUT/'STARTED.private.json',c.encode({'source_lock_sha256':lock_sha,'root_selection_sha256':selection_sha,'mode':mode,
        'maximum_attempts':1,'attempt_id':attempt,'outer_deadline':outer_deadline,
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
        result=execute_stages(wrapper,loaded,bodies,root=OUT,budget=budget,active_deadline=active)
        require(not loaded['docker_owner'].registered_clients(),'no_remaining_registered_clients')
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
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
            require(len(members)<=4096,'finite_output_file_census')
        require(total<=WRITE_CAP,'whole_retained_limit')
        c.write(OUT/'CUSTODY.private.json',c.encode({'schema':'abr_fold_whole_private_custody_v1',
            'members':members,'bytes_before_custody':total,'self_excluded':True,
            'managed_reads_before_custody':budget.reads,'original_deadline_admitted':True}),budget)
        for path in sorted((x for x in OUT.rglob('*') if x.is_dir()),key=lambda x:len(x.parts),reverse=True):
            os.chmod(path,0o500)
        os.chmod(OUT,0o500)
        budget.check()
        print(json.dumps({'status':'COMPLETE_PENDING_INDEPENDENT_REVIEW','mode':mode,
                          'containers':10,'authentic_input_conversion_rerun':False,
                          'model_api_calls':0,'scientific_qualification':False,'results_private':True}),flush=True)
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

