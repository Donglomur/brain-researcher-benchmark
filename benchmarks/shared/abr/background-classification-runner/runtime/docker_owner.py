"""Exact owned Docker process lifecycle; candidates never execute on the host.

This create/inspect/start/remove module
owns only uniquely named, labelled CIDs and its own Docker-client process groups.
"""
import errno
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
from common import need, pin, decode, encode, write, read, plain, Refusal
from durable_evidence import Evidence

IMAGE='UNSELECTED_ABR_RUNTIME'
DOCKER='/usr/local/bin/docker'
LABEL='org.neurobench.abr.fold.owner'
THREAD_ENV=('OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1',
            'NUMEXPR_NUM_THREADS=1','PYTHONHASHSEED=0')
MEMORY=2147483648
SUBMISSION_CAP=2*1024*1024
_CLOSED_TOKEN=object()
_FAILED_TOKEN=object()
# Keep exact spawned Popen owners through every exceptional path. A hard owner
# horizon may attempt only these groups, never a discovered/unrelated process.
_CLIENTS={}
_SPAWN_SIGNALS={signal.SIGALRM,signal.SIGTERM,signal.SIGINT,signal.SIGUSR1}
DAEMON_SOCKET=Path('/OWNER/runtime/docker.sock')
DAEMON_GUARD=None
_CLI_CONFIG=None
_CLI_ENV=None
HOST_CAPACITY_ARGV={
    ('/usr/sbin/sysctl','-n','hw.logicalcpu'),
    ('/usr/sbin/sysctl','-n','hw.memsize'),
    ('/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'),
    ('/usr/bin/vm_stat',),
    ('/bin/ps','-A','-o','%cpu='),
}
HOST_CAPACITY_ENV={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LANG':'C','LC_ALL':'C'}

def daemon_guard():
    p=plain(DAEMON_SOCKET);s=p.lstat()
    observed={'dev':s.st_dev,'inode':s.st_ino,'mode':s.st_mode,
              'uid':s.st_uid,'gid':s.st_gid,'nlink':s.st_nlink}
    need(stat.S_ISSOCK(s.st_mode) and observed==DAEMON_GUARD and s.st_uid==os.getuid(),
         'exact_selected_local_daemon_socket')
    return observed

def configure_cli(root,budget):
    global _CLI_CONFIG,_CLI_ENV
    need(_CLI_CONFIG is None and _CLI_ENV is None,'one_private_CLI_configuration')
    observed=daemon_guard()
    root=plain(root);root.mkdir(mode=0o700)
    entry=write(root/'config.json',b'{"auths":{}}\n',budget)
    search=root/'empty-path';search.mkdir(mode=0o500)
    os.chmod(root,0o500)
    _CLI_CONFIG=root
    # No host context, credential helper, TLS option, registry proxy or home
    # configuration is inherited. Docker's own daemon policy is a separate
    # trusted local service, not a proven full OS/daemon binary closure.
    # Docker can auto-discover a platform credential helper even with empty
    # auths. Its executable search path is therefore an empty owned directory;
    # the selected Docker executable itself is always an absolute argv operand.
    _CLI_ENV={'PATH':str(search),'LANG':'C','DOCKER_CONFIG':str(root)}
    return {'socket':str(DAEMON_SOCKET),'guard':observed,'config':entry,
            'environment':dict(_CLI_ENV),'host_config_or_credentials_read':False,
            'full_daemon_binary_closure':False}

def cli_argv(args):
    need(_CLI_CONFIG is not None and _CLI_ENV is not None,'selected_CLI_configured')
    return [DOCKER,'--host','unix://'+str(DAEMON_SOCKET),'--config',str(_CLI_CONFIG),*args]

def require_configured_cli(configuration, budget):
    """Reuse the one owned probe/pair CLI configuration, never reset globals."""
    need(type(configuration) is dict and set(configuration)=={
         'socket','guard','config','environment','host_config_or_credentials_read',
         'full_daemon_binary_closure'},'exact_owned_CLI_binding')
    need(_CLI_CONFIG is not None and _CLI_ENV is not None,'owned_CLI_already_configured')
    expected_env={'PATH':str(_CLI_CONFIG/'empty-path'),'LANG':'C','DOCKER_CONFIG':str(_CLI_CONFIG)}
    need(configuration['socket']==str(DAEMON_SOCKET) and
         configuration['guard']==daemon_guard() and
         configuration['environment']==_CLI_ENV==expected_env and
         configuration['host_config_or_credentials_read'] is False and
         configuration['full_daemon_binary_closure'] is False,'unchanged_owned_CLI_binding')
    entry=configuration['config']
    need(type(entry) is dict and set(entry)=={'path','bytes','sha256'} and
         plain(entry['path'])==_CLI_CONFIG/'config.json','owned_CLI_configuration_path')
    body=read(entry['path'],{k:entry[k] for k in ('bytes','sha256')},budget,cap=65536,mode=0o400)
    need(body==b'{"auths":{}}\n' and stat.S_IMODE(_CLI_CONFIG.lstat().st_mode)==0o500 and
         stat.S_IMODE((_CLI_CONFIG/'empty-path').lstat().st_mode)==0o500 and
         not any((_CLI_CONFIG/'empty-path').iterdir()),'sealed_empty_credential_configuration')
    return True

def registered_clients():
    return tuple(_CLIENTS)

def reap_retire(proc):
    """Only nonblocking reap, atomically retiring numeric signal authority.

    The unreaped child reserves its PID. Once waitpid has reaped it, a surviving
    or recycled numeric group cannot be signalled on that old authority.
    """
    previous=signal.pthread_sigmask(signal.SIG_BLOCK,_SPAWN_SIGNALS)
    try:
        code=proc.poll()
        return code
    finally:
        if proc.returncode is not None:
            _CLIENTS.pop(proc.pid,None)
        signal.pthread_sigmask(signal.SIG_SETMASK,previous)

def bounded_reap(proc,until):
    while True:
        code=reap_retire(proc)
        if code is not None:return code
        remaining=until-time.monotonic()
        if remaining<=0:return None
        time.sleep(min(.01,remaining))

def kill_unreaped_owned(proc):
    previous=signal.pthread_sigmask(signal.SIG_BLOCK,_SPAWN_SIGNALS)
    try:
        if _CLIENTS.get(proc.pid) is not proc or proc.returncode is not None:
            return False
        os.killpg(proc.pid,signal.SIGKILL)
        return True
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK,previous)

def kill_registered_clients():
    """Nonwaiting best effort for a fatal owner horizon; never a closure claim."""
    records=[]
    for pid,proc in tuple(_CLIENTS.items()):
        row={'pid':pid,'kill_attempted':False,'kill_returned':False,'errors':[]}
        try:
            row['kill_attempted']=(_CLIENTS.get(pid) is proc and proc.returncode is None)
            row['kill_returned']=kill_unreaped_owned(proc)
            if not row['kill_attempted']:
                row['signal_authority_retired']=True
        except ProcessLookupError:
            row['group_not_found_at_signal']=True
        except BaseException as error:
            row['errors'].append(type(error).__name__)
        records.append(row)
    return records

def cleanup_registered_clients(until):
    """Failure-only bounded fallback. Reap/absence are observed separately."""
    rows=kill_registered_clients()
    for row in rows:
        pid=row['pid'];proc=_CLIENTS.get(pid)
        row.update({'reaped':False,'group_absent':None,'stream_EOF_observed':False})
        if proc is None:
            row['errors'].append('RegisteredOwnerUnavailable');continue
        try:
            code=bounded_reap(proc,min(until,time.monotonic()+1))
            row['exit_code']=code;row['reaped']=code is not None
        except BaseException as error:
            row['errors'].append(type(error).__name__)
        row['group_absent']=absent_group(pid)
        row['signal_authority_retired']=pid not in _CLIENTS
    return rows

@dataclass(frozen=True)
class ClosedRun:
    submission: dict
    lifecycle: dict
    _token: object

def require_closed(value):
    need(type(value) is ClosedRun and value._token is _CLOSED_TOKEN,'owned_closed_candidate_required')
    return value

@dataclass(frozen=True)
class ClosedFailure:
    lifecycle: dict
    reason: str
    _token: object

def require_closed_episode(value):
    if type(value) is ClosedRun:
        return require_closed(value)
    need(type(value) is ClosedFailure and value._token is _FAILED_TOKEN,
         'owned_closed_failed_candidate_required')
    return value

def classify_closed_candidate_failure(failure, start_record, cleanup, state, calls):
    """Only ordinary candidate failures after proved owned resource cleanup.

    Cancellation, daemon/evidence failures and uncertain client/container cleanup
    never become benchmark zeros. Truncated capture can close a failed episode,
    but it can never become a successful submission.
    """
    if not (failure and failure['phase']=='candidate_work' and failure['preceding'] is None and
            failure['class']=='Refusal' and failure['message']=='docker_client_incomplete' and
            start_record and start_record.get('dispatched') is True and
            start_record.get('reaped') is True and start_record.get('group_absent') is True and
            not start_record.get('cleanup_errors') and not start_record.get('evidence_errors') and
            len(cleanup)==1 and cleanup[0]['ownership_admitted'] is True and
            cleanup[0]['removal_observed'] is True and cleanup[0]['id_absent'] is True and
            cleanup[0]['name_absent'] is True and not cleanup[0]['errors'] and
            type(state) is dict and type(state.get('StartedAt')) is str and
            state['StartedAt'] and not state['StartedAt'].startswith('0001-') and
            state.get('Status') in ('running','exited') and state.get('Error')==''):
        return None
    if any(not c.get('complete') or c.get('exit_code')!=0 for c in calls if c is not start_record):
        return None
    fault=start_record.get('failure')
    if fault is not None:
        if fault.get('class')!='Refusal' or start_record.get('signals') not in ([],['SIGKILL_owned_group']):
            return None
        return {'docker_client_deadline':'candidate_timeout',
                'docker_stream_extent':'candidate_output_limit'}.get(fault.get('message'))
    if (start_record.get('complete') is True and start_record.get('EOF')==['stderr','stdout'] and
        not start_record.get('signals') and type(start_record.get('exit_code')) is int and
        start_record['exit_code']!=0 and type(state) is dict and
        state.get('Running') is False and state.get('Paused') is False and
        state.get('Restarting') is False and state.get('Status')=='exited' and
        state.get('Error')=='' and type(state.get('ExitCode')) is int and
        state['ExitCode']==start_record['exit_code']):
        return 'candidate_oom' if state.get('OOMKilled') is True else 'candidate_nonzero'
    return None

def cid(value):
    need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),'typed_cid')
    return value

def absent_group(pid):
    try:
        os.killpg(pid,0)
    except ProcessLookupError:
        return True
    except BaseException:
        return None
    return False

def command(argv, *, directory, number, budget, until, observed,
            cleanup_call=False, cap=65536, host_capacity=False):
    """Keep all setup after spawn inside owned cleanup; retain exact partials."""
    need(type(argv) is list and argv and all(type(x) is str for x in argv),'command_argv')
    need(type(host_capacity) is bool,'explicit_command_kind')
    if host_capacity:
        need(tuple(argv) in HOST_CAPACITY_ARGV and cap==65536 and not cleanup_call,
             'exact_host_capacity_command')
        selected_environment=HOST_CAPACITY_ENV
    else:
        need(_CLI_CONFIG is not None and _CLI_ENV is not None and argv[:5]==cli_argv([]),
             'explicit_local_Docker_endpoint_and_config')
        selected_environment=_CLI_ENV
    need(type(cap) is int and 0<cap<=SUBMISSION_CAP and time.monotonic()<until<=budget.deadline,'command_deadline')
    root=plain(directory)
    record={'argv':argv,'dispatched':False,'exit_code':None,'EOF':[],
            'reaped':False,'group_absent':None,'failure':None,'cleanup_errors':[],
            'signals':[],'evidence_errors':[],
            'observed_pipe_bytes_at_least':{'stdout':0,'stderr':0}}
    record['command_kind']='host_capacity' if host_capacity else 'owned_Docker_client'
    record['selected_environment']=dict(selected_environment)
    proc=None
    selector=None
    streams={}
    files={}
    output={'stdout':bytearray(),'stderr':bytearray()}
    failure=None
    start=time.monotonic()
    # Reserve both complete stream ceilings before spawn, including partials.
    budget.reserve_write(2*cap)
    try:
        record['daemon_socket_before']=daemon_guard()
        for name in ('stdout','stderr'):
            path=root/(str(number).zfill(3)+'.'+name)
            files[name]=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        need(len(_CLIENTS)<32,'finite_owned_client_registry')
        # Python handles these pending signals only after the exact child is
        # registered. The CLI inherits this blocked mask; all cleanup uses
        # unmaskable SIGKILL and does not rely on the CLI accepting SIGTERM.
        previous_mask=signal.pthread_sigmask(signal.SIG_BLOCK,_SPAWN_SIGNALS)
        try:
            proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,start_new_session=True,env=dict(selected_environment))
            _CLIENTS[proc.pid]=proc
            record['dispatched']=True
            record['pid']=proc.pid
            record['registered_before_signal_unblock']=True
            record['child_inherited_blocked_signals']=['SIGALRM','SIGINT','SIGTERM','SIGUSR1']
            streams={'stdout':proc.stdout,'stderr':proc.stderr}
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK,previous_mask)
        if not observed('spawned',record):
            record['evidence_errors'].append('spawn_evidence_persistence')
            need(cleanup_call,'spawn_evidence_persistence')
        selector=selectors.DefaultSelector()
        for name,stream in streams.items():
            os.set_blocking(stream.fileno(),False)
            selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or reap_retire(proc) is None:
            need(time.monotonic()<until,'docker_client_deadline')
            for key,_ in selector.select(min(.05,max(0,until-time.monotonic()))):
                name=key.data
                request=min(65536,cap-len(output[name])+1)
                budget.charge_read(request)
                block=os.read(key.fileobj.fileno(),request)
                budget.reads-=request-len(block)
                if not block:
                    record['EOF'].append(name)
                    selector.unregister(key.fileobj)
                    continue
                record['observed_pipe_bytes_at_least'][name]+=len(block)
                remaining=cap-len(output[name])
                retained=block[:remaining];at=0
                while at<len(retained):
                    n=os.write(files[name],retained[at:]);need(n>0,'stream_write')
                    output[name].extend(retained[at:at+n]);at+=n
                    budget.successful+=n
                need(len(block)<=remaining,'docker_stream_extent')
        record['exit_code']=bounded_reap(proc,until)
        need(record['exit_code'] is not None,'nonblocking_reap_at_deadline')
        record['reaped']=True
    except BaseException as error:
        failure=error
        record['failure']={'class':type(error).__name__,'message':str(error)}
    finally:
        if proc is not None:
            observation=absent_group(proc.pid)
            if observation is not True:
                try:
                    if kill_unreaped_owned(proc):
                        record['signals'].append('SIGKILL_owned_group')
                    else:
                        record['cleanup_errors'].append({'phase':'retired_signal_authority',
                            'class':'AmbiguousGroupAfterReap'})
                except ProcessLookupError:
                    pass
                except BaseException as error:
                    record['cleanup_errors'].append({'phase':'kill','class':type(error).__name__})
            try:
                record['exit_code']=bounded_reap(proc,min(budget.deadline,time.monotonic()+5))
                need(record['exit_code'] is not None,'owned_reap_deadline_exhausted')
                record['reaped']=True
            except BaseException as error:
                record['cleanup_errors'].append({'phase':'reap','class':type(error).__name__})
            record['group_absent']=absent_group(proc.pid)
            record['signal_authority_retired_at_reap']=proc.pid not in _CLIENTS
        try:
            record['daemon_socket_after']=daemon_guard()
        except BaseException as error:
            record['cleanup_errors'].append({'phase':'daemon_socket_recheck','class':type(error).__name__})
        if selector is not None:
            try:
                selector.close()
            except BaseException as error:
                record['cleanup_errors'].append({'phase':'selector_close','class':type(error).__name__})
        for name,stream in streams.items():
            try:
                stream.close()
            except BaseException as error:
                record['cleanup_errors'].append({'phase':name+'_close','class':type(error).__name__})
        # Raw writes retained each observed prefix while the client was live.
        # Independent fsync/mode/close attempts never skip a later owned handle.
        for name,fd in files.items():
            path=root/(str(number).zfill(3)+'.'+name)
            raw=bytes(output[name])
            try:
                os.fsync(fd)
            except BaseException as error:
                record['cleanup_errors'].append({'phase':name+'_fsync','class':type(error).__name__})
            try:
                os.fchmod(fd,0o400)
            except BaseException as error:
                record['cleanup_errors'].append({'phase':name+'_mode','class':type(error).__name__})
            try:
                os.close(fd)
            except BaseException as error:
                record['cleanup_errors'].append({'phase':name+'_close_fd','class':type(error).__name__})
            record[name]={'path':str(path),**pin(raw)}
        record['elapsed_seconds']=time.monotonic()-start
    record['EOF'].sort()
    record['complete']=(failure is None and record['reaped'] is True and
                        record['group_absent'] is True and record['EOF']==['stderr','stdout'] and
                        not record['signals'] and not record['cleanup_errors'] and
                        not record['evidence_errors'] and
                        time.monotonic()<until)
    if not observed('finished',record):
        record['complete']=False
        record['cleanup_errors'].append({'phase':'final_call_evidence','class':'PersistenceFailure'})
    # Reap retirement happened atomically before all blocking evidence work.
    # Group absence remains an independent success requirement, never renewed
    # kill authority for a reaped/recycled numeric PID.
    # The durable call event precedes return/refusal and later publication.
    return record,bytes(output['stdout']),bytes(output['stderr'])

def create_argv(name, input_dir, task_dir, program, image=IMAGE):
    need(image==IMAGE,'fixed_image')
    mounts=[(input_dir,'/input'),(task_dir,'/task'),(program,'/candidate/solution.py')]
    out=[DOCKER,'create','--pull=never','--name',name,'--label',LABEL+'='+name,
         '--network=none','--read-only','--cpus=1','--memory=2g','--memory-swap=2g',
         '--pids-limit=64','--log-driver=none','--cap-drop=ALL',
         '--security-opt=no-new-privileges','--user=501:20','--workdir=/work',
         '--tmpfs=/work:rw,nosuid,nodev,size=134217728,mode=1777',
         '--tmpfs=/tmp:rw,nosuid,nodev,size=134217728,mode=1777',
         '--ulimit=nofile=1024:1024','--ulimit=fsize=1048576:1048576']
    for value in THREAD_ENV:
        out+=['--env',value]
    for source,dest in mounts:
        out+=['--mount','type=bind,src='+str(plain(source))+',dst='+dest+',readonly']
    return out+['--entrypoint=python3',IMAGE,'-I','-B','/candidate/solution.py']

def owned(obj, expected_cid, name):
    need(type(obj) is list and len(obj)==1,'one_inspection')
    item=obj[0]
    need(item['Id']==cid(expected_cid) and item['Image']==IMAGE and
         item['Name']=='/'+name and item['Config']['Labels'].get(LABEL)==name,'exact_owned_container')
    return item

def validate_inspection(obj, expected_cid, name, mounts, *, final):
    item=owned(obj,expected_cid,name)
    host=item['HostConfig'];config=item['Config'];state=item['State']
    need(type(item['RestartCount']) is int and item['RestartCount']==0,'no_restart')
    need(config['Entrypoint']==['python3'] and config['Cmd']==['-I','-B','/candidate/solution.py'] and
         config['User']=='501:20' and config['WorkingDir']=='/work','candidate_process')
    env=config['Env'];need(type(env) is list and all(type(x) is str for x in env),'container_environment')
    need(all(env.count(x)==1 and sum(y.partition('=')[0]==x.partition('=')[0] for y in env)==1
             for x in THREAD_ENV),'fixed_library_threads')
    for key in ('Memory','MemorySwap','NanoCpus','PidsLimit'):
        need(type(host[key]) is int,'typed_resource_limits')
    need(host['Memory']==host['MemorySwap']==MEMORY and host['NanoCpus']==1000000000 and
         host['PidsLimit']==64 and host['NetworkMode']=='none' and
         host['ReadonlyRootfs'] is True and host['CapDrop']==['ALL'] and
         host['SecurityOpt']==['no-new-privileges'] and host['LogConfig']['Type']=='none','container_limits')
    need(host['Privileged'] is False and not host.get('CapAdd') and not host.get('Devices') and
         host.get('PidMode','')=='' and host.get('IpcMode')=='private','no_host_or_extra_device_privilege')
    need(host['Tmpfs']=={'/work':'rw,nosuid,nodev,size=134217728,mode=1777',
                         '/tmp':'rw,nosuid,nodev,size=134217728,mode=1777'},'exact_tmpfs')
    ul=host['Ulimits']
    need(type(ul) is list and len(ul)==2 and
         all(type(x['Soft']) is type(x['Hard']) is int for x in ul) and
         {(x['Name'],x['Soft'],x['Hard']) for x in ul}==
         {('nofile',1024,1024),('fsize',1048576,1048576)},'exact_ulimits')
    observed=item['Mounts'];binds=[x for x in observed if x['Type']=='bind']
    need(len(binds)==3 and {(x['Source'],x['Destination'],x['RW']) for x in binds}==mounts and
         all(x['RW'] is False for x in binds) and
         all(x['Type'] in ('bind','tmpfs') for x in observed),'exact_readonly_mounts')
    need(state['Running'] is False and state['Paused'] is False and state['Restarting'] is False and
         state['OOMKilled'] is False and state['Error']=='','clean_container_state')
    if final:
        need(state['Status']=='exited' and type(state['ExitCode']) is int and state['ExitCode']==0,'candidate_natural_zero')
    else:
        need(state['Status']=='created','candidate_created')
    return item

def run_candidate(*, root, input_dir, task_dir, program, budget, active_deadline):
    """No reference parameter exists. All returned artifacts remain owner-private."""
    root=plain(root);root.mkdir(mode=0o700);logs=root/'logs';logs.mkdir(mode=0o700)
    need(time.monotonic()<active_deadline<budget.deadline,'active_and_cleanup_deadlines')
    name='abr-fold-'+hashlib.sha256(str(root).encode()).hexdigest()[:24]
    calls=[];cleanup=[];active_cid=None;owned_cid=None
    creation_dispatched=False;failure=None;submission=None;artifact=None;life_entry=None
    start_record=None;cleanup_state=None
    journal=Evidence(root/'LIFECYCLE_JOURNAL.private.bin',budget)
    persistence=[]
    old_handlers={}
    def preserve(phase,value):
        return journal.emit(phase,value)
    def record_failure(phase,error):
        nonlocal failure
        failure={'phase':phase,'class':type(error).__name__,'message':str(error),
                 'preceding':failure}
    def admit_owned(obj,target):
        nonlocal owned_cid
        item=owned(obj,target,name)
        # Ownership is established before later configuration validation and
        # is not revoked by a subsequent failed inspection or journal write.
        owned_cid=target
        preserve('ownership_admitted',{'cid':target,'name':name,'label':LABEL,'image':IMAGE})
        return item
    def cancelled(signum,frame):
        raise Refusal('owner_cancelled')
    def call(args, *, seconds=5, cleanup_call=False, allowed=(0,), cap=65536):
        nonlocal start_record
        deadline=budget.deadline if cleanup_call else active_deadline
        until=min(deadline,time.monotonic()+seconds)
        need(len(calls)<12,'finite_docker_call_count')
        pending={'argv':cli_argv(args),'dispatch_intent':True,'dispatched':False,
                 'outcome_observed':False,'cleanup_call':cleanup_call}
        calls.append(pending)
        number=len(calls)
        persisted=preserve('call_intent',{'number':number,'record':pending})
        # Evidence failures stop new ordinary work. Cleanup of previously
        # owned resources must still be attempted and cannot be skipped.
        need(persisted or cleanup_call,'call_intent_persistence')
        def observed(phase,record):
            pending.update(record)
            if phase=='finished':pending['outcome_observed']=True
            return preserve('call_'+phase,{'number':number,'record':dict(pending)})
        try:
            record,out,err=command(pending['argv'],directory=logs,number=number,
                                   budget=budget,until=until,observed=observed,
                                   cleanup_call=cleanup_call,cap=cap)
        except BaseException as error:
            pending['exception_class']=type(error).__name__
            preserve('call_exception',{'number':number,'record':dict(pending)})
            raise
        pending.update(record);pending['outcome_observed']=True
        if args[:2]==['start','-a']:
            start_record=pending
        need(record['complete'] and record['exit_code'] in allowed,'docker_client_incomplete')
        return out
    def inspect(value, cleanup_call=False):
        return decode(call(['inspect',cid(value)],cleanup_call=cleanup_call),65536)
    try:
        for sig in (signal.SIGTERM,signal.SIGINT):
            old_handlers[sig]=signal.getsignal(sig);signal.signal(sig,cancelled)
        need(not call(['ps','-aq','--no-trunc','--filter','name=^/'+name+'$']).strip(),'fresh_container_name')
        write(root/'CREATE_INTENT.private.json',encode({'name':name,'label':LABEL,'image':IMAGE}),budget)
        creation_dispatched=True
        argv=create_argv(name,input_dir,task_dir,program)
        raw=call(argv[1:])
        active_cid=cid(raw.decode().strip())
        mounts={(str(input_dir),'/input',False),(str(task_dir),'/task',False),
                (str(program),'/candidate/solution.py',False)}
        initial=inspect(active_cid)
        admit_owned(initial,active_cid)
        need(not journal.errors,'ownership_evidence_complete')
        validate_inspection(initial,active_cid,name,mounts,final=False)
        output=call(['start','-a',active_cid],seconds=600,cap=SUBMISSION_CAP)
        validate_inspection(inspect(active_cid),active_cid,name,mounts,final=True)
        need(len(output)<=SUBMISSION_CAP,'closed_submission_capture_limit')
        submission=output
    except BaseException as error:
        record_failure('candidate_work',error)
    finally:
        for sig in old_handlers:
            try:signal.signal(sig,signal.SIG_IGN)
            except BaseException as error:record_failure('ignore_cleanup_signal',error)
        if active_cid is None and creation_dispatched:
            try:
                raw=call(['ps','-aq','--no-trunc','--filter','name=^/'+name+'$',
                          '--filter','label='+LABEL+'='+name],cleanup_call=True).decode().strip()
                if raw:
                    recovered=cid(raw)
                    admit_owned(inspect(recovered,True),recovered)
                    active_cid=recovered
            except BaseException as error:
                record_failure('owned_recovery',error)
        if active_cid is not None:
            target=active_cid
            observation={'cid':target,'name':name,'ownership_admitted':owned_cid==target,
                         'cleanup_inspection':False,'removal_observed':False,
                         'id_absent':None,'name_absent':None,'errors':[]}
            cleanup.append(observation)
            try:
                cleanup_item=admit_owned(inspect(target,True),target)
                cleanup_state=cleanup_item.get('State')
                observation['cleanup_inspection']=True
            except BaseException as error:
                observation['errors'].append({'phase':'inspection','class':type(error).__name__})
                record_failure('cleanup_inspection',error)
            observation['ownership_admitted']=owned_cid==target
            # A failed later inspection does not erase exact earlier ownership.
            # Each action has its own protected observation; rm uncertainty
            # cannot suppress either independent absence check.
            if owned_cid==target:
                try:
                    call(['rm','-f',target],cleanup_call=True)
                    observation['removal_observed']=True
                except BaseException as error:
                    observation['errors'].append({'phase':'removal','class':type(error).__name__})
                    record_failure('owned_removal',error)
            else:
                record_failure('unadmitted_container',Refusal('exact_ownership_not_established'))
            for key,query in (('id_absent','id='+target),('name_absent','name=^/'+name+'$')):
                try:
                    answer=call(['ps','-aq','--no-trunc','--filter',query],cleanup_call=True)
                    observation[key]=not bool(answer.strip())
                    need(observation[key] is True,'exact_owned_absence')
                except BaseException as error:
                    observation['errors'].append({'phase':key,'class':type(error).__name__})
                    record_failure(key,error)
            if observation['id_absent'] is True and observation['name_absent'] is True:
                active_cid=None
            preserve('cleanup_observations',observation)
        for sig,old in old_handlers.items():
            try:signal.signal(sig,old)
            except BaseException as error:record_failure('restore_signal',error)
    closed=(failure is None and active_cid is None and len(cleanup)==1 and
            cleanup[0]['ownership_admitted'] is True and
            cleanup[0]['removal_observed'] is True and
            cleanup[0]['id_absent'] is True and cleanup[0]['name_absent'] is True and
            not cleanup[0]['errors'] and submission is not None and not journal.errors)
    failed_reason=classify_closed_candidate_failure(failure,start_record,cleanup,cleanup_state,calls)
    failed_closed=failed_reason is not None and active_cid is None and not journal.errors
    def snapshot():
        # Full call bodies are already in distinct, indexed durable events.
        return {'schema':'tms_isolated_candidate_lifecycle_v2','call_count':len(calls),
                'cleanup':cleanup,'failure':failure,'remaining_owned_cid':active_cid,
                'admitted_owned_cid':owned_cid,'candidate_closed':closed,
                'episode_closed':closed or failed_closed,'failed_episode_reason':failed_reason,
                'submission':artifact,'reference_access_in_this_module':False,
                'candidate_image_content_qualified':False,'publication_errors':persistence}
    try:
        need(preserve('before_submission_publication',snapshot()),'prepublication_evidence')
        if closed:
            artifact=write(root/'SUBMISSION.private.bin',submission,budget)
        need(preserve('after_submission_publication',snapshot()),'publication_evidence')
        budget.check()
    except BaseException as error:
        closed=False
        failed_closed=False
        persistence.append({'phase':'submission_or_deadline','class':type(error).__name__})
        record_failure('submission_or_deadline',error)
        preserve('publication_failure',snapshot())
    finally:
        journal.close()
    if journal.errors or journal.closed is not True:
        closed=False
        failed_closed=False
        record_failure('journal_closure',Refusal(encode(journal.receipt()['persistence_errors']).decode()))
    life=snapshot();life['calls']=calls;life['journal']=journal.receipt()
    try:
        life_entry=write(root/'LIFECYCLE.private.json',encode(life),budget)
        budget.check()
    except BaseException as error:
        closed=False
        failed_closed=False
        persistence.append({'phase':'final_lifecycle_publication','class':type(error).__name__})
        record_failure('final_lifecycle_publication',error)
    # Main's separately reserved emergency record retains this finite summary
    # if final metadata publication itself fails. The pre-reserved journal
    # already holds argv, actual dispatch, exit/reap/EOF and cleanup evidence.
    need(closed or failed_closed,'candidate_not_completely_closed:'+encode({
        'failure':failure,'publication_errors':persistence,
        'journal_errors':journal.errors,'journal_closed':journal.closed}).decode())
    if failed_closed:
        return ClosedFailure(life_entry,failed_reason,_FAILED_TOKEN)
    return ClosedRun(artifact,life_entry,_CLOSED_TOKEN)

