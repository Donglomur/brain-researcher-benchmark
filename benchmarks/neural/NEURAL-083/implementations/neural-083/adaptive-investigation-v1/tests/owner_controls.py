"""Finite Linux owner controls; scope and custody are specified in README.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types

NAMES = (
    'adaptive_owner.py', 'admission.py', 'entry.py', 'inherited/integration.py',
    'inherited/process_owner.py', 'inherited/program/admission.py',
    'inherited/program/common.py', 'inherited/program/native.py',
    'inherited/program/observe.py', 'inherited/program/process.py')
SOURCE_CAP = 262144
TOTAL_CAP = 6291456
CI_PROC_GRANT = 262144


def failure_payload(error, stage, cases):
    record=getattr(error,'record',None)
    raw=json.dumps(record,sort_keys=True).encode()
    owner=getattr(error,'actual_owner',None)
    secondaries=list(getattr(owner,'errors',()))
    restoration=list(getattr(error,'engineering_diagnostic_errors',()))
    def describe(value):
        return None if value is None else dict(type=type(value).__name__,message=str(value)[:1024])
    available=record is not None
    value=dict(schema='neural083_harness_first_failure_v1',status='failed',
        case=stage,completed_cases=list(cases),exception=describe(error),ci_proc_grant=CI_PROC_GRANT,
        original_error=describe(getattr(error,'original_error',None)),
        record_bytes=len(raw) if available else None,
        record_sha256=hashlib.sha256(raw).hexdigest() if available else None,
        record=record if available and len(raw)<=24576 else None,
        record_available=available,record_complete=available and len(raw)<=24576,
        owner_secondary_errors=[describe(x) for x in secondaries[:4]],
        owner_secondary_count=len(secondaries),
        diagnostic_secondary_errors=[describe(x) for x in restoration[:4]],
        diagnostic_secondary_count=len(restoration),qualification_issued=False)
    encoded=(json.dumps(value,sort_keys=True)+'\n').encode()
    if len(encoded)>32768:raise ValueError('failure diagnostic output cap')
    return encoded


def emit_failure(error, raw, write):
    try:
        position=0
        while position<len(raw):
            n=write(2,raw[position:])
            if type(n)is not int or not 0<n<=len(raw)-position:
                raise RuntimeError('short failure diagnostic output')
            position+=n
    except BaseException as secondary:
        error.engineering_diagnostic_errors=tuple(getattr(error,'engineering_diagnostic_errors',()))+(secondary,)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection', required=True)
    parser.add_argument('--selection-bytes', required=True, type=int)
    parser.add_argument('--selection-sha256', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or sys.version_info < (3, 11):
        raise ValueError('selected Linux CPython >=3.11 engineering environment only')
    started = time.monotonic()
    def expiry(*_):
        raise TimeoutError('one selected 15-second engineering interval')
    old = signal.signal(signal.SIGALRM, expiry)
    signal.setitimer(signal.ITIMER_REAL, 15)
    used = 0
    def debit(n):
        nonlocal used
        if type(n) is not int or n < 0 or used+n > TOTAL_CAP:
            raise ValueError('selected total managed source and proc transfer cap')
        used += n
    def capture(path, n, digest):
        path = Path(path).absolute()
        if type(n) is not int or not 0 < n <= SOURCE_CAP:
            raise ValueError('ordinary bounded source extent')
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('source path aliases')
        debit(n+1)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != n:
                raise ValueError('exact ordinary selected source')
            raw = bytearray()
            while len(raw) < n+1:
                part = os.read(fd, n+1-len(raw))
                if not part:
                    break
                raw.extend(part)
            after = os.fstat(fd)
            keys = ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            if any(getattr(before,k) != getattr(after,k) for k in keys):
                raise ValueError('source changed during capture')
        finally:
            os.close(fd)
        if len(raw) != n or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('selected source digest')
        return bytes(raw)
    modules = {}
    cases = []
    stage = 'source_admission'
    first_failure = None
    try:
        selected = json.loads(capture(args.selection,args.selection_bytes,args.selection_sha256))
        if set(selected) != {'root','files'} or set(selected['files']) != set(NAMES):
            raise ValueError('closed ten-body candidate source selection')
        root = Path(selected['root']).absolute()
        bodies = {}
        for name in NAMES:
            descriptor = selected['files'][name]
            if set(descriptor) != {'bytes','sha256'}:
                raise ValueError('exact source pin')
            bodies[name] = capture(root/name,descriptor['bytes'],descriptor['sha256'])
        if sum(map(len,bodies.values())) > SOURCE_CAP:
            raise ValueError('whole selected source cap')
        for name in NAMES:
            module = types.ModuleType('selected_owner_'+str(len(modules)))
            module.__file__ = str(root/name)
            exec(compile(bodies[name],module.__file__,'exec'),module.__dict__)
            modules[name] = module
        grant_names=('adaptive_owner.py','inherited/process_owner.py',
            'inherited/program/process.py','inherited/program/native.py','inherited/program/common.py')
        if any(type(modules[n].PROC_READ_CAP)is not int or modules[n].PROC_READ_CAP!=65536
               for n in grant_names):raise ValueError('exact original production proc grant')
        for n in grant_names:modules[n].PROC_READ_CAP=CI_PROC_GRANT
        env = {'PATH':'/usr/bin:/bin','LANG':'C','PYTHONDONTWRITEBYTECODE':'1'}
        python = str(Path(sys.executable).resolve())
        normal_command = [python,'-I','-S','-B','-c','import os;os.write(1,b"out");os.write(2,b"err")']
        def normal(name):
            nonlocal stage
            stage='real_natural_'+name
            module=modules[name];grants=[]
            def read(n):grants.append(n);debit(n)
            now=time.monotonic()
            if name.endswith('program/process.py'):
                raw,record=module.run(normal_command,now+2,now+3,env,metadata_read=read)
                assert raw==b'out' and record['streams_closed'] is True
            else:
                record=module.run(normal_command,normal_end=now+2,cleanup_end=now+3,
                                  env=env,metadata_read=read,stream_cap=64)
                assert base64.b64decode(record['stdout_base64'])==b'out'
                assert base64.b64decode(record['stderr_base64'])==b'err'
            assert grants==[CI_PROC_GRANT]
            assert record['natural_exit'] is True and record['exit_code']==0
            assert record['process_reaped'] is True and record['process_group_absent'] is True
            value=record['process_ownership']
            assert value['signals_retired_before_reap'] is True
            assert value['final_read_only_probe_after_reap'] is True
            assert value['proc_snapshot_is_absence_proof'] is False
            assert value['proc_metadata_reserved_bytes']==CI_PROC_GRANT
            cases.append('real_natural_'+name)
        for name in ('adaptive_owner.py','inherited/process_owner.py','inherited/program/process.py'):
            normal(name)
        stage='real_native_owner_tiny_cli_prefix_no_Docker'
        native=modules['inherited/program/native.py'];common=modules['inherited/program/common.py']
        docker=native.Docker(python,'/selected-inert-socket',metadata_read=debit)
        docker.prefix=normal_command;docker.env=env
        raw=docker([],time.monotonic()+3,'invented_tiny_cli',64)
        assert raw==b'out' and docker.last_original['stderr']==b'err'
        common.validate_cli_commands(docker.records,64)
        common.validate_process_ownership(docker.ownership_records,docker.records)
        cases.append('real_native_owner_tiny_cli_prefix_no_Docker')
        adaptive=modules['adaptive_owner.py']
        for label,code,cap,duration in (
            ('combined_cap_plus_probe','import os;os.write(1,b"123456789")',8,2),
            ('original_timeout','import time;time.sleep(5)',64,.15)):
            stage='real_'+label
            now=time.monotonic()
            try:
                adaptive.run([python,'-I','-S','-B','-c',code],normal_end=now+duration,
                             cleanup_end=now+duration+1,env=env,metadata_read=debit,stream_cap=cap)
            except adaptive.ChildFailure as error:
                record=error.record
                assert record['process_reaped'] is True and record['process_group_absent'] is True
                assert record['cleanup_errors']==[] and error.actual_owner.errors==[]
                assert record['parent_alarm_expired_during_cleanup'] is False
                if label=='combined_cap_plus_probe':
                    assert type(error.original_error) is ValueError
                    assert str(error.original_error)=='consumed combined stream cap exceeded'
                    assert record['primary_error']=={'type':'ValueError','message':'consumed combined stream cap exceeded'}
                    assert record['consumed_bytes']['stdout']==9
                    assert base64.b64decode(record['stdout_base64'])==b'123456789'
                else:
                    assert type(error.original_error) is TimeoutError
                    assert str(error.original_error)=='original child work deadline'
                    assert record['primary_error']=={'type':'TimeoutError','message':'original child work deadline'}
                cases.append('real_'+label)
            else:
                raise AssertionError('selected negative control unexpectedly accepted')
        stage='real_legacy_combined_cap_plus_probe'
        legacy=modules['inherited/program/process.py'];now=time.monotonic()
        code='import os;os.write(1,b"a"*32768);os.write(2,b"b"*32769)'
        try:
            legacy.run([python,'-I','-S','-B','-c',code],now+2,now+3,env,metadata_read=debit)
        except legacy.ChildFailure as error:
            assert type(error.original_error) is ValueError
            assert str(error.original_error)=='consumed combined stream cap exceeded'
            assert error.record['primary_error']=={'type':'ValueError','message':'consumed combined stream cap exceeded'}
            assert error.record['cleanup_errors']==[] and error.actual_owner.errors==[]
            assert error.record['parent_alarm_expired_during_cleanup'] is False
            assert error.record['combined_stream_bytes']==65537
            assert error.record['process_reaped'] is True
            assert error.record['process_group_absent'] is True
            prefixes=error.actual_consumed_prefixes
            assert sum(len(base64.b64decode(x,validate=True)) for x in prefixes.values())==65537
            assert base64.b64decode(prefixes['stdout'])==b'a'*32768
            assert base64.b64decode(prefixes['stderr'])==b'b'*32769
            cases.append('real_legacy_combined_cap_plus_probe')
        else:raise AssertionError('fourth owner admitted combined-cap overflow')
        stage='inert_actual_native_late_failure_no_recapture'
        saved={key:getattr(native,key,None) for key in ('c','BoundedDocker','path','call','time')}
        reads=[];clock=[100.0];first=OSError('invented native dispatch failure')
        secondary=TimeoutError('invented expired publication deadline')
        transport=types.SimpleNamespace(records=[],ownership_records=[],reaped=True)
        def phase_capture(*args):
            reads.append(args[0])
            if len(reads)>1:raise AssertionError('late source recapture masks first failure')
            return b'invented-source'
        def phase_save(*args):raise secondary
        def phase_call(*args):clock[0]=1000.0;raise first
        native.c=types.SimpleNamespace(capture=phase_capture,pin=common.pin,
            encoded=common.encoded,save=phase_save,validate_cli_commands=lambda *a:None,
            validate_process_ownership=lambda *a:None)
        native.BoundedDocker=lambda *a,**k:transport
        native.path=lambda *a:types.SimpleNamespace(stat=lambda:types.SimpleNamespace(st_mode=stat.S_IFSOCK))
        native.call=phase_call;native.time=types.SimpleNamespace(monotonic=lambda:clock[0])
        budget=types.SimpleNamespace(read=lambda *a:None,write=lambda *a:None,tick=lambda:None)
        try:
            try:native.phase({'fit_seconds':1,'docker_binary':'inert','docker_socket':'inert',
                'memory_bytes':1},root,root,root/'invented_program.py',None,root,'fit',1,{},budget,200.0)
            except OSError as error:
                assert error is first and error.actual_native_transport is transport
                assert error.native_secondary_errors==[secondary]
                assert error.actual_native_record['error_type']=='OSError'
                assert error.actual_native_record['status']=='failed'
                assert error.actual_native_record['all_native_resources_closed'] is False
                assert len(reads)==1
                cases.append('inert_actual_native_late_failure_no_recapture')
            else:raise AssertionError('late native failure unexpectedly accepted')
        finally:
            for key,value in saved.items():setattr(native,key,value)
        stage='inert_post_reap_reuse_no_signal'
        original_os=adaptive.os;events=[]
        terminal=types.SimpleNamespace(si_pid=707,si_code=os.CLD_EXITED,si_status=0)
        proxy=types.SimpleNamespace(**{name:getattr(os,name) for name in dir(os)})
        proxy.waitid=lambda *args: terminal
        proxy.waitpid=lambda *args:(events.append(('reap',707)) or (707,0))
        proxy.getpgid=lambda pid:pid;proxy.getsid=lambda pid:pid
        proxy.killpg=lambda pid,sig:events.append(('group',pid,sig))
        adaptive.os=proxy
        try:
            group=adaptive._PinnedGroup(types.SimpleNamespace(pid=707,returncode=None))
            group.observe(time.monotonic()+1)
            group.send(signal.SIGTERM,time.monotonic()+1)
            group.reap(time.monotonic()+1)
            assert group.absent_after_reap() is False
            try:group.send(signal.SIGKILL,time.monotonic()+1)
            except RuntimeError as error:
                assert type(error) is RuntimeError and str(error)=='group signaling permanently retired'
            else:raise AssertionError('post-reap mutation admitted')
            assert events==[('group',707,signal.SIGTERM),('reap',707),('group',707,0)]
            events.clear()
            stage='inert_lost_wait_ownership_no_signal'
            ownership_error=ChildProcessError('invented external reap')
            def lost(*_):raise ownership_error
            proxy.waitid=lost
            group=adaptive._PinnedGroup(types.SimpleNamespace(pid=707,returncode=None))
            try:group.send(signal.SIGTERM,time.monotonic()+1)
            except ChildProcessError as error:
                assert error is ownership_error and str(error)=='invented external reap'
            else:raise AssertionError('lost ownership admitted')
            assert events==[] and group.wait_ownership_lost is True
            cases.extend(('inert_post_reap_reuse_no_signal','inert_lost_wait_ownership_no_signal'))
        finally:
            adaptive.os=original_os
        stage='inert_actual_entry_metadata_callback'
        entry=modules['entry.py'];charged=[];published=[];sentinel={}
        def fake_run(argv,**kw):kw['metadata_read'](65536);return sentinel
        bridge=types.SimpleNamespace(child_argv=lambda *a:[],environment=lambda:env,
            publish_child=lambda output,record,budget:published.append(record),
            natural=lambda record:None)
        ctx={'owner':types.SimpleNamespace(run=fake_run,ChildFailure=RuntimeError),
             'bridge':bridge,'metadata_budget':types.SimpleNamespace(read=lambda n:charged.append(n))}
        assert entry.launch(ctx,root/'entry.py',bodies['entry.py'],[],0,1,2,None) is sentinel
        assert charged==[65536] and published==[sentinel]
        fault=adaptive.ChildFailure({'primary_error':{'type':'ValueError','message':'invented'},
            'stdout_base64':'b3V0','stderr_base64':'ZXJy'},ValueError('invented'),
            types.SimpleNamespace(errors=[OSError('invented close')]))
        wire=failure_payload(fault,stage,cases)
        decoded=json.loads(wire)
        assert decoded['record']==fault.record and decoded['record_complete'] is True
        assert decoded['original_error']=={'type':'ValueError','message':'invented'}
        assert decoded['owner_secondary_errors']==[{'type':'OSError','message':'invented close'}]
        write_error=OSError('invented diagnostic publication failure')
        def no_write(*args):raise write_error
        emit_failure(fault,wire,no_write)
        assert fault.engineering_diagnostic_errors==(write_error,)
        assert fault.original_error.args==('invented',) and fault.record is not None
        decoded=json.loads(failure_payload(fault,stage,cases))
        assert decoded['diagnostic_secondary_count']==1
        assert decoded['diagnostic_secondary_errors'][0]['message']==str(write_error)
        absent=json.loads(failure_payload(ValueError('invented missing record'),stage,cases))
        assert absent['record_available'] is False and absent['record_complete'] is False
        cases.append('inert_actual_entry_metadata_callback')
        def proc_disappearance(name, variant):
            nonlocal stage
            stage='inert_proc_'+name+'_'+variant
            module=modules[name]
            saved={key:getattr(module,key) for key in
                   ('os','subprocess','selectors','signal','time','sys')}
            saved_path=getattr(module,'path',None)
            vanished=(ProcessLookupError if variant=='lookup_close_failure' else FileNotFoundError)(
                'invented vanished proc stat')
            close_error=OSError('invented proc directory close failure')
            failing=variant!='vanished_known_closure'
            events=[];grants=[];reads={};selector_instances=[];processes=[]
            stat_body=b'707 (inert) '+b' '.join([b'Z',b'1',b'707',b'707']+[b'0']*15+[b'1'])
            payloads={401:b'out',402:b'err',103:stat_body}
            def event(*values):
                if len(events)>=128:raise AssertionError('inert leaf call envelope')
                events.append(values)
            class Pipe:
                def __init__(self,fd):self.fd=fd;self.closed=False
                def fileno(self):return self.fd
                def close(self):event('pipe-close',self.fd);self.closed=True
            class Process:
                pid=707;returncode=None
                def __init__(self):self.stdout=Pipe(401);self.stderr=Pipe(402)
            class Selector:
                def __init__(self):self.keys={};self.calls=0;self.closed=False;selector_instances.append(self)
                def register(self,stream,event_mask,data):
                    assert event_mask==1
                    self.keys[stream.fileno()]=types.SimpleNamespace(fileobj=stream,data=data)
                def get_map(self):return self.keys
                def select(self,timeout):
                    self.calls+=1;assert self.calls<=4 and 0<=timeout<=.1
                    return [(key,1) for key in list(self.keys.values())]
                def unregister(self,stream):del self.keys[stream.fileno()]
                def close(self):event('selector-close');self.closed=True
            class ProcNames:
                def __iter__(self):return iter([types.SimpleNamespace(name='999'),types.SimpleNamespace(name='707')])
                def close(self):event('scandir-close')
            def popen(argv,**kw):
                event('popen');assert not processes and argv==['inert-child']
                assert kw==dict(stdin=-3,stdout=-1,stderr=-1,env={'INERT':'1'},
                               start_new_session=True,bufsize=0)
                process=Process();processes.append(process);return process
            def opened(path,flags,*,dir_fd=None):
                event('open',path,dir_fd)
                if path=='/proc' and dir_fd is None:return 100
                if path=='999' and dir_fd==100:return 101
                if path=='707' and dir_fd==100:return 102
                if path=='stat' and dir_fd==101:raise vanished
                if path=='stat' and dir_fd==102:return 103
                raise AssertionError('unexpected inert proc operand')
            def read(fd,wanted):
                event('read',fd,wanted);assert fd in payloads and type(wanted)is int and wanted>0
                offset=reads.get(fd,0);part=payloads[fd][offset:offset+wanted]
                reads[fd]=offset+len(part);return part
            def close(fd):
                event('close',fd);assert fd in (100,101,102,103)
                if fd==101 and failing:raise close_error
            def scandir(fd):assert fd==100;event('scandir');return ProcNames()
            def fstat(fd):assert fd==103;return types.SimpleNamespace(st_mode=stat.S_IFREG|0o444)
            def waitid(*args):
                assert args==(os.P_PID,707,os.WEXITED|os.WNOHANG|os.WNOWAIT)
                event('waitid');return types.SimpleNamespace(si_pid=707,si_code=os.CLD_EXITED,si_status=0)
            def waitpid(pid,options):
                assert pid==707 and options==os.WNOHANG
                event('reap');return 707,0
            def killpg(pid,sig):
                assert pid==707;event('group',sig)
                if sig==0:raise ProcessLookupError('inert final absence')
                assert sig in (signal.SIGTERM,signal.SIGKILL)
            def charge(n):grants.append(n);debit(n)
            constants=('O_RDONLY','O_DIRECTORY','O_NOFOLLOW','O_NONBLOCK','P_PID',
                       'WEXITED','WNOHANG','WNOWAIT','CLD_EXITED','CLD_KILLED','CLD_DUMPED')
            proxy=types.SimpleNamespace(**{key:getattr(os,key) for key in constants},
                open=opened,read=read,close=close,scandir=scandir,fstat=fstat,
                waitid=waitid,waitpid=waitpid,waitstatus_to_exitcode=lambda value:0,
                getpgid=lambda pid:pid,getsid=lambda pid:pid,killpg=killpg,
                set_blocking=lambda fd,flag:event('set-blocking',fd,flag),environ={})
            module.os=proxy
            module.subprocess=types.SimpleNamespace(Popen=popen,DEVNULL=-3,PIPE=-1)
            module.selectors=types.SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1)
            module.signal=types.SimpleNamespace(SIGCHLD=signal.SIGCHLD,SIG_DFL=signal.SIG_DFL,
                SIGTERM=signal.SIGTERM,SIGKILL=signal.SIGKILL,ITIMER_REAL=signal.ITIMER_REAL,
                getsignal=lambda sig:signal.SIG_DFL,setitimer=lambda *args:(0.0,0.0))
            module.time=types.SimpleNamespace(monotonic=lambda:100.0,
                sleep=lambda duration:(_ for _ in ()).throw(AssertionError('unexpected inert sleep')))
            module.sys=types.SimpleNamespace(platform='linux')
            native_case=name.endswith('/native.py');legacy_case=name.endswith('/process.py')
            caller=None;caught=None;record=None;prefixes=None;owner=None
            try:
                if native_case:
                    module.path=lambda value:value
                    caller=module.Docker('inert-child','inert-socket',metadata_read=charge)
                    caller.prefix=['inert-child'];caller.env={'INERT':'1'}
                try:
                    if native_case:
                        assert caller([],104.0,'inert_proc_disappearance',64)==b'out'
                        record=caller.records[0]
                        owner=caller.last_original['owner']
                    elif legacy_case:
                        raw,record=module.run(['inert-child'],102.0,103.0,{'INERT':'1'},metadata_read=charge)
                        assert raw==b'out'
                    else:
                        record=module.run(['inert-child'],normal_end=102.0,cleanup_end=103.0,
                                          env={'INERT':'1'},metadata_read=charge,stream_cap=64)
                except BaseException as error:
                    caught=error
                    if not failing:raise
                    if native_case:
                        assert error is vanished and caller.last_original['first'] is vanished
                        assert error.actual_cli_original is caller.last_original
                        owner=caller.last_original['owner'];record=caller.records[0]
                        assert caller.last_original['cleanup_errors']==[close_error]
                        assert caller.original_failures==[caller.last_original]
                        assert caller.reaped is False and record['cleanup_complete'] is False
                        assert caller.ownership_records[0]['cleanup_error_types']==['OSError']
                    else:
                        assert type(error)is module.ChildFailure and error.original_error is vanished
                        owner=error.actual_owner;record=error.record
                        assert record['primary_error']==dict(type=type(vanished).__name__,message=str(vanished))
                        assert record['cleanup_errors']==['proc-close:OSError']
                        prefixes=error.actual_consumed_prefixes if legacy_case else dict(
                            stdout=record['stdout_base64'],stderr=record['stderr_base64'])
                    assert owner.errors==[close_error] and owner.errors[0] is close_error
                    assert owner.proc_prefixes==[bytearray()]
                    value=owner.evidence()
                    assert value['proc_descriptor_closure_known'] is False
                    assert value['proc_cleanup_error_types']==['OSError']
                if failing:
                    assert caught is not None
                else:
                    assert caught is None
                    value=owner.evidence() if native_case else record['process_ownership']
                    assert value['proc_descriptor_closure_known'] is True
                    assert value['proc_cleanup_error_types']==[]
                    assert value['proc_directory_entries']==2 and value['proc_metadata_actual_bytes']==len(stat_body)
                    assert value['other_group_members_observed']==[]
                    if native_case:
                        assert owner.errors==[] and owner.proc_prefixes==[bytearray(),bytearray(stat_body)]
                        assert caller.reaped is True and record['cleanup_complete'] is True
                        assert caller.last_original['first'] is None and caller.last_original['cleanup_errors']==[]
                        common.validate_cli_commands(caller.records,64)
                        common.validate_process_ownership(caller.ownership_records,caller.records)
                        for key,replacement in (('proc_descriptor_closure_known',False),
                                                ('proc_cleanup_error_types',['OSError'])):
                            bad=dict(caller.ownership_records[0])
                            bad['ownership']=dict(bad['ownership']);bad['ownership'][key]=replacement
                            try:common.validate_process_ownership([bad],caller.records)
                            except ValueError as error:
                                assert str(error)=='known error-free proc descriptor closure'
                            else:raise AssertionError('consumer admitted failed proc closure')
                    else:
                        assert record['primary_error'] is None and record['cleanup_errors']==[]
                        assert record['natural_exit'] is True and record['exit_code']==0
                        assert record['process_reaped'] is True and record['process_group_absent'] is True
                        if not legacy_case:
                            prefixes=dict(stdout=record['stdout_base64'],stderr=record['stderr_base64'])
                if native_case:
                    assert bytes(caller.last_original['stdout'])==b'out'
                    assert bytes(caller.last_original['stderr'])==b'err'
                    assert caller.ownership_records[0]['stdout_eof'] is True
                    assert caller.ownership_records[0]['stderr_eof'] is True
                elif prefixes is not None:
                    assert base64.b64decode(prefixes['stdout'],validate=True)==b'out'
                    assert base64.b64decode(prefixes['stderr'],validate=True)==b'err'
                if not native_case:
                    assert record['consumed_bytes']=={'stdout':3,'stderr':3}
                    assert record['stdout_eof'] is True and record['stderr_eof'] is True
                assert grants==[CI_PROC_GRANT] and len(processes)==1
                assert all((processes[0].stdout.closed,processes[0].stderr.closed,selector_instances[0].closed))
                assert ('open','stat',101) in events and ('close',101) in events
                assert ('scandir-close',) in events and ('close',100) in events
                assert events.count(('reap',))==1
                reaped_at=events.index(('reap',))
                assert [event for event in events[reaped_at+1:] if event[0]=='group']==[('group',0)]
                if failing:assert ('open','707',100) not in events
                else:assert ('open','stat',102) in events and ('close',103) in events and ('close',102) in events
                if not failing:
                    probe=module._PinnedGroup(processes[0]);probe.proc_read_reserved=CI_PROC_GRANT
                    before_reads=dict(reads)
                    try:probe._stat_body(100,'707',103.0)
                    except ValueError as error:
                        assert type(error)is ValueError and str(error)=='complete proc snapshot exceeds precharged metadata grant'
                    else:raise AssertionError('exhausted selected proc grant admitted')
                    assert reads==before_reads and probe.proc_read_reserved==CI_PROC_GRANT and probe.errors==[]
                    if native_case:
                        common.PROC_READ_CAP=65536
                        try:
                            try:common.validate_process_ownership(caller.ownership_records,caller.records)
                            except ValueError as error:
                                assert str(error)=='complete bounded prepaid proc snapshot'
                            else:raise AssertionError('default validator admitted CI-sized receipt')
                        finally:common.PROC_READ_CAP=CI_PROC_GRANT
                cases.append('inert_proc_'+name+'_'+variant)
            finally:
                for key,value in saved.items():setattr(module,key,value)
                if native_case:module.path=saved_path
        for owner_name in ('adaptive_owner.py','inherited/process_owner.py',
                           'inherited/program/process.py','inherited/program/native.py'):
            for variant in ('not_found_close_failure','lookup_close_failure','vanished_known_closure'):
                proc_disappearance(owner_name,variant)
        stage='final_result_publication'
        result=dict(schema='neural083_prospective_owner_engineering_v1',status='passed',
            cases=cases,ci_proc_grant=CI_PROC_GRANT,managed_reserved_bytes=used,elapsed_seconds=time.monotonic()-started,
            real_kernel_cases=7,inert_logic_cases=16,Docker_executed=False,
            model_science_or_data_executed=False,qualification_issued=False)
        assert len(cases)==23 and len(set(cases))==23
        if time.monotonic()-started>=15:raise TimeoutError('original final publication cutoff')
        encoded=(json.dumps(result,sort_keys=True)+'\n').encode()
        if len(encoded)>16384:raise ValueError('selected result output cap')
        if os.write(1,encoded)!=len(encoded):raise RuntimeError('short engineering output')
        if time.monotonic()-started>=15:raise TimeoutError('original postpublication cutoff')
    except BaseException as error:
        first_failure=error
    finally:
        for restore in (lambda:signal.setitimer(signal.ITIMER_REAL,0),
                        lambda:signal.signal(signal.SIGALRM,old)):
            try:restore()
            except BaseException as secondary:
                if first_failure is None:first_failure=secondary
                else:
                    first_failure.engineering_diagnostic_errors=tuple(getattr(
                        first_failure,'engineering_diagnostic_errors',()))+(secondary,)
    if first_failure is not None:
        try:
            if time.monotonic()-started>=15:raise TimeoutError('original failure publication cutoff')
            raw=failure_payload(first_failure,stage,cases)
            emit_failure(first_failure,raw,os.write)
            if time.monotonic()-started>=15:raise TimeoutError('original failure postpublication cutoff')
        except BaseException as secondary:
            first_failure.engineering_diagnostic_errors=tuple(getattr(
                first_failure,'engineering_diagnostic_errors',()))+(secondary,)
        raise first_failure


if __name__=='__main__':
    main()
