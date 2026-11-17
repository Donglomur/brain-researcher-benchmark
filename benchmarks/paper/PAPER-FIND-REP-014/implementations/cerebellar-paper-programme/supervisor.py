"""Concrete independent original-clock process/daemon closure for the full study.

Future separately authorized execution only. No Docker/native process executes
at import. Linux pidfds bind signals to observed processes; a missing leader,
reused PID, surviving group or unknown creation acknowledgment stays unresolved.
"""
import time
BOOT=time.monotonic()
import argparse
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
if globals().get('_SOURCE_CONTEXT') is not None:
    from budget import Budget
    from core import TASK, need, encoded, high_level_jobs, descriptor
    from safe_io import capture, strict, pin, child
    from operation import validate_operation
    from planner import validate_plan, valid_slot, summarize_missing
    from transport.engine import BOOTSTRAP, process_identity
    

SOURCE_SCHEMA='paper_i_executable_source_manifest_v1'


def _boot_need(condition,message):
    if not condition:raise ValueError(message)


def _boot_pin(raw):
    import hashlib
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def _boot_json(raw):
    import json
    def pairs(rows):
        result={}
        for key,value in rows:
            _boot_need(key not in result,'Duplicate bootstrap JSON key');result[key]=value
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite bootstrap metadata')))


def _boot_capture(path,expected,cap,deadline=None):
    """Stable bounded stdlib read before any unverified local module import."""
    import stat
    _boot_need(type(expected) is dict and set(expected)=={'bytes','sha256'} and type(expected['bytes']) is int and 0<=expected['bytes']<=cap and re.fullmatch('[a-f0-9]{64}',expected['sha256']),'Exact bounded startup file identity')
    if deadline is not None:_boot_need(time.monotonic()<deadline,'Original deadline includes bootstrap reads')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
    try:
        before=os.fstat(fd);_boot_need(stat.S_ISREG(before.st_mode) and before.st_size==expected['bytes'],'Complete expected regular startup file')
        pieces=[];total=0
        while total<=expected['bytes']:
            if deadline is not None:_boot_need(time.monotonic()<deadline,'Original deadline during bootstrap capture')
            part=os.read(fd,min(65536,expected['bytes']+1-total))
            if not part:break
            total+=len(part);pieces.append(part)
        after=os.fstat(fd);raw=b''.join(pieces)
        fields=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        _boot_need(fields(before)==fields(after) and _boot_pin(raw)==expected,'Exact stable bytes used for execution')
        return raw
    except BaseException as error:primary=error;raise
    finally:
        try:os.close(fd)
        except BaseException as error:
            if primary is None:raise
            primary.cleanup_errors=[*getattr(primary,'cleanup_errors',[]),{'action':'bootstrap.close','type':type(error).__name__}]


def _boot_child(root,name):
    _boot_need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*',name) and all(p not in ('..','.') for p in Path(name).parts),'Exact ordinary manifest path')
    current=Path(root)
    for part in Path(name).parts:
        current=current/part;_boot_need(not current.is_symlink(),'No symlink in executed source closure')
    return current


def _boot_manifest(manifest):
    _boot_need(type(manifest) is dict and manifest.get('schema')==SOURCE_SCHEMA and manifest.get('task')=='PAPER-FIND-REP-014','Exact program I executable manifest schema/task')
    _boot_need(type(manifest.get('files')) is list and manifest['files'],'Complete source member inventory')
    files={}
    for row in manifest['files']:
        _boot_need(type(row) is dict and set(row)=={'path','bytes','sha256'},'Exact source member descriptor')
        name=row['path'];_boot_need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*',name),'Ordinary exact source name')
        _boot_need(name not in files and not any(p in ('.','..','peer-review','review-revisions','supervisor_support','integration-revisions') for p in Path(name).parts),'Unique production source only')
        _boot_need(Path(name).suffix in ('.py','.m','.json') or name=='PUBLIC_CONTRACT.md','Only explicit public contract document, not arbitrary documentation')
        d={k:row[k] for k in ('bytes','sha256')};_boot_need(type(d['bytes']) is int and 0<=d['bytes']<=1048576 and type(d['sha256']) is str and re.fullmatch('[a-f0-9]{64}',d['sha256']),'Bounded exact source member pin')
        files[name]=d
    required={'controller.py','supervisor.py','operation.py','core.py','budget.py','safe_io.py','planner.py','transport/SOURCE_MANIFEST.json','PUBLIC_CONTRACT.md'}
    _boot_need(required<=set(files) and manifest.get('bytes')==sum(d['bytes'] for d in files.values()),'Complete exact host/transport/document source closure')
    return files


def _captured_loader(root,bodies,files):
    """Finder/loader executes exactly authenticated cached bytes, never pyc."""
    import importlib.abc
    import importlib.util
    python={};packages=set()
    for name in files:
        if not name.endswith('.py'):continue
        parts=Path(name).parts
        fullname='.'.join(parts[:-1] if parts[-1]=='__init__.py' else (*parts[:-1],parts[-1][:-3]))
        _boot_need(fullname and all(p.isidentifier() for p in fullname.split('.')),'Exact importable production module name')
        _boot_need(fullname not in python,'One source per module');python[fullname]=name
        if parts[-1]=='__init__.py':packages.add(fullname)
        for i in range(1,len(fullname.split('.'))):packages.add('.'.join(fullname.split('.')[:i]))
    roots={n.split('.')[0] for n in set(python)|packages}
    class CapturedLoader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def __init__(self):self.executed={};self.modules={}
        def find_spec(self,fullname,path=None,target=None):
            if fullname in python or fullname in packages:return importlib.util.spec_from_loader(fullname,self,is_package=fullname in packages)
            if fullname.split('.')[0] in roots:raise ModuleNotFoundError('Undeclared local source import: '+fullname)
            return None
        def create_module(self,spec):return None
        def exec_module(self,module):
            name=module.__name__;module.__loader__=self
            if name in packages:module.__path__=[]
            self.modules[name]=module
            if name not in python:
                self.executed[name]=None;return
            relative=python[name];raw=bodies[relative]
            _boot_need(_boot_pin(raw)==files[relative],'Authenticated bytes immediately before module execution')
            module.__file__=str(Path(root)/relative);module.__cached__=None
            self.executed[name]={'path':relative,**files[relative]}
            exec(compile(raw,module.__file__,'exec',dont_inherit=True),module.__dict__)
        def verify(self):
            for name,module in sys.modules.items():
                if name.split('.')[0] in roots:_boot_need(self.modules.get(name) is module,'No ambient local module may bypass captured execution')
            for name,module in self.modules.items():
                _boot_need(sys.modules.get(name) is module and module.__loader__ is self,'No preloaded/replaced local dependency bypass')
                relative=python.get(name)
                if relative is not None:
                    _boot_need(self.executed[name]=={'path':relative,**files[relative]} and module.__file__==str(Path(root)/relative),'Exact executed local source provenance')
            return dict(self.executed)
    return CapturedLoader(),roots


def authenticated_run(operation_path,operation_pin,output,origin):
    """Same-process authenticated bootstrap; no process/native dispatch here."""
    import importlib.util
    import math
    raw=_boot_capture(operation_path,operation_pin,1048576);op=_boot_json(raw)
    host=op['host'];cap=host['parent_limits']['read_bytes'];wall=op['global_limits']['wall_seconds']
    _boot_need(type(cap) is int and cap>0 and type(wall) in (int,float) and math.isfinite(wall) and wall>0 and type(origin) in (int,float) and math.isfinite(origin),'Explicit original bootstrap allocation/clock')
    _boot_need(sys.platform.startswith('linux'),'Verified startup requires reviewed Linux host')
    import resource
    memory=host['parent_memory_bytes'];_boot_need(type(memory) is int and memory>0,'Explicit parent startup address-space ceiling')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
    deadline=origin+wall;used=len(raw)
    _boot_need(used<=cap and time.monotonic()<deadline-host['cleanup_seconds'],'Bootstrap charged before any further read or dispatch')
    s=op['source_manifest'];expected={k:s[k] for k in ('bytes','sha256')}
    _boot_need(used+expected['bytes']<=cap,'Manifest fits original parent read partition')
    manifest_raw=_boot_capture(s['path'],expected,min(1048576,host['max_metadata_bytes']),deadline);used+=len(manifest_raw)
    manifest=_boot_json(manifest_raw);files=_boot_manifest(manifest)
    _boot_need(used+sum(d['bytes'] for d in files.values())<=cap,'Full executed closure reserved before source reads')
    root=Path(__file__).resolve().parent;bodies={}
    for name,d in sorted(files.items()):
        body=_boot_capture(_boot_child(root,name),d,max(1,d['bytes']),deadline);used+=len(body);bodies[name]=body
    loader,roots=_captured_loader(root,bodies,files)
    existing={name:module for name,module in sys.modules.items() if name.split('.')[0] in roots}
    _boot_need(all(name=='supervisor' and getattr(module,'__file__',None)==__file__ for name,module in existing.items()),'Dedicated bootstrap refuses already executing unauthenticated local dependencies')
    context={'operation_pin':dict(operation_pin),'operation_raw':raw,'manifest_pin':expected,'manifest_raw':manifest_raw,'files':files,'bodies':bodies,'read_bytes':used,'origin':origin,'deadline':deadline,'loader':loader}
    try:
        for name in existing:sys.modules.pop(name)
        sys.meta_path.insert(0,loader)
        spec=loader.find_spec('supervisor');module=importlib.util.module_from_spec(spec);module._SOURCE_CONTEXT=context
        sys.modules['supervisor']=module;loader.exec_module(module);loader.verify()
        return module.run(operation_path,operation_pin,output,origin)
    finally:
        # Original errors remain primary. In-memory importer cleanup never
        # signals processes, deletes source, or resets a budget/clock.
        if loader in sys.meta_path:sys.meta_path.remove(loader)
        for name,module in list(loader.modules.items()):
            if sys.modules.get(name) is module:sys.modules.pop(name)
        sys.modules.update(existing)



def absent(pgid):
    try:os.killpg(pgid,0)
    except ProcessLookupError:return True
    except PermissionError:return False
    return False


def identity_reader(pid,end,budget):
    def reserve(n):
        budget.tick();need(budget.reads+n<=budget.limits['read_bytes'],'Reserve bounded process identity before read')
    return process_identity(pid,end,budget.read,reserve)


def retire_cli(token,end,budget,grace):
    """Signal only an identity-bound leader; never authorize kill from PID alone.

    Group absence is separately observed. No claim to close an unrecorded child
    or surviving descendant follows from killing a leader.
    """
    result={'process_identity':token,'closed':False,'leader_signalled':False,'identity_match':False}
    fd=None
    try:
        budget.tick();pid=token['pid']
        if absent(token['pgid']):result.update(closed=True,group_absent=True);return result
        fd=os.pidfd_open(pid,0)
        fresh=identity_reader(pid,end,budget)
        need(fresh==token,'Exact UID/boot/start/PID/session identity before pidfd signal')
        result['identity_match']=True
        signal.pidfd_send_signal(fd,signal.SIGKILL,None,0);result['leader_signalled']=True
        cutoff=min(end,time.monotonic()+grace)
        while time.monotonic()<cutoff:
            budget.tick()
            if absent(token['pgid']):result.update(closed=True,group_absent=True);break
            time.sleep(min(.01,max(0,cutoff-time.monotonic())))
        result.setdefault('group_absent',False)
    except BaseException as error:
        result.update(error_type=type(error).__name__,group_absent=False)
        # ESRCH can mean the exact process just exited. Only fresh group absence
        # discharges custody; a birth mismatch never authorizes a group signal.
        try:
            if absent(token['pgid']):result.update(closed=True,group_absent=True)
        except BaseException:pass
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:result.update(closed=False,close_error=type(error).__name__)
    budget.tick();return result


def watch(argv,root,work_deadline,budget,grace,log_cap,host_memory):
    """Gated concrete controller child; all post-Popen work is custody-guarded."""
    import resource
    need(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'Identity-bound Linux process signaling')
    def limits():
        os.umask(0o077);resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(host_memory,host_memory))
    end=budget.end;need(budget.tick()<work_deadline<end,'Original work/terminal cutoffs')
    env={'PATH':'/usr/bin:/bin','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','TZ':'UTC','LC_ALL':'C'}
    process=None;selector=None;pidfd=None;token=None;code=None;primary=None;cleanup=[];forced=False
    buffers={'stdout':bytearray(),'stderr':bytearray()};started=budget.tick()
    try:
        process=subprocess.Popen([argv[0],'-I','-S','-B','-c',BOOTSTRAP,*argv],cwd=root,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,preexec_fn=limits)
        pidfd=os.pidfd_open(process.pid,0)
        token=identity_reader(process.pid,end,budget)
        budget.event({'event':'CONTROLLER-CHILD','process_identity':token,'exec_still_gated':True,'argv':argv})
        need(budget.tick()<work_deadline and os.write(process.stdin.fileno(),b'G')==1,'Durable controller ownership before release')
        process.stdin.close()
        selector=selectors.DefaultSelector()
        for name,stream in (('stdout',process.stdout),('stderr',process.stderr)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or process.poll() is None:
            need(budget.tick()<work_deadline,'Original whole-program work deadline')
            for key,_ in selector.select(min(.05,max(0,work_deadline-time.monotonic()))):
                remaining=log_cap-sum(map(len,buffers.values()))
                need(remaining>=0 and budget.reads+min(65536,remaining+1)<=budget.limits['read_bytes'],'Reserve streaming log read')
                data=os.read(key.fileobj.fileno(),min(65536,remaining+1));budget.read(len(data))
                if not data:selector.unregister(key.fileobj);continue
                need(len(data)<=remaining,'Bounded controller metadata logs');buffers[key.data].extend(data)
        code=process.wait(timeout=max(.001,min(grace,end-budget.tick())))
        need(absent(process.pid),'Controller leader exit cannot hide surviving process group')
    except BaseException as error:
        primary=error;forced=True
        # pidfd was opened while this exact Popen child was gated. It remains
        # identity-bound even if the numeric PID is reused; no killpg is sent.
        if pidfd is not None:
            try:signal.pidfd_send_signal(pidfd,signal.SIGKILL,None,0)
            except ProcessLookupError:pass
            except BaseException as secondary:cleanup.append({'action':'pidfd_kill','type':type(secondary).__name__})
        if process is not None:
            try:
                if process.stdin is not None and not process.stdin.closed:process.stdin.close()
                process.wait(timeout=max(.001,min(grace,end-time.monotonic())))
            except BaseException as secondary:cleanup.append({'action':'reap','type':type(secondary).__name__})
            code=process.returncode
    finally:
        actions=[]
        if selector is not None:actions.append(('selector.close',selector.close))
        if process is not None:
            actions.extend((name+'.close',s.close) for name,s in (('stdin',process.stdin),('stdout',process.stdout),('stderr',process.stderr)) if s is not None)
        if pidfd is not None:actions.append(('pidfd.close',lambda:os.close(pidfd)))
        for name,action in actions:
            try:action()
            except BaseException as error:cleanup.append({'action':name,'type':type(error).__name__})
    try:group_absent=process is None or absent(process.pid)
    except BaseException as error:
        group_absent=False;cleanup.append({'action':'final_group_observation','type':type(error).__name__})
    result={'schema':'paper_i_independent_controller_close_v1','argv':argv,'process_identity':token,
        'started':started,'finished':time.monotonic(),'work_deadline':work_deadline,'global_deadline':end,
        'exit_code':code,'natural_exit':not forced and code==0 and group_absent and not cleanup,'forced':forced,
        'reaped':process is None or process.returncode is not None,'process_group_absent':group_absent,
        'error_type':None if primary is None else type(primary).__name__,'cleanup_errors':cleanup,
        'logs':{k:pin(bytes(v)) for k,v in buffers.items()},
        'source_resource_semantics':'Actual process lifetime and enforced address-space ceiling; no exact RSS claim'}
    result['logs_data']={name:bytes(body) for name,body in buffers.items()}
    return result


def source_view(op,here,root,budget):
    """Copy the exact already-authenticated executable byte closure."""
    context=globals().get('_SOURCE_CONTEXT');need(context is not None,'Verified source execution context required')
    source=op['source_manifest'];expected={k:source[k] for k in ('bytes','sha256')}
    need(context['manifest_pin']==expected and pin(context['manifest_raw'])==expected,'Executed and copied source share exact manifest identity')
    files=_boot_manifest(strict(context['manifest_raw']));need(files==context['files'],'Same complete authenticated source inventory')
    context['loader'].verify()
    root=Path(root);need(not root.exists() and not root.is_symlink(),'Fresh private immutable source view')
    root.mkdir(mode=0o700,parents=False);directories={root}
    for name,d in sorted(files.items()):
        raw=context['bodies'][name];need(pin(raw)==d,'Copy actual verified bytes, never ambient module source')
        target=child(root,name);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        current=target.parent
        while current!=root:directories.add(current);current=current.parent
        need(budget.save(target,raw)==d,'Complete exact source publication');os.chmod(target,0o444)
    view_pin=budget.save(root/'VIEW.json',encoded({'schema':'osl_closed_role_view_v1','files':files}));os.chmod(root/'VIEW.json',0o444)
    for directory in sorted(directories,key=lambda p:len(p.parts),reverse=True):os.chmod(directory,0o555)
    return {'root':str(root.absolute()),'manifest':view_pin,'files':files,'bytes':sum(d['bytes'] for d in files.values())+view_pin['bytes']}


def inspect_cli(control,phase,request_pin,budget,limits,grace):
    """Close each independently recorded birth identity; retain every error."""
    names=[];errors=[];records=[];total=0;intents={};children={}
    try:
        for entry in control.iterdir():
            need(len(names)<limits['max_records']+16,'Finite per-phase durable metadata inventory')
            names.append(entry.name)
    except BaseException as error:errors.append({'stage':'inventory','type':type(error).__name__})
    for name in sorted(names):
        if not re.fullmatch('[0-9]{6}-CLI-(?:INTENT|CHILD).json',name):continue
        try:
            size=(control/name).stat(follow_symlinks=False).st_size
            need(0<size<=limits['max_record_bytes'] and total+size<=limits['max_metadata_bytes'],'Bounded durable CLI ownership')
            budget.read(size);raw=capture(control/name,limits['max_record_bytes']);total+=len(raw);row=strict(raw)
            need(row['schema']=='osl_transport_journal_v1' and row['phase_id']==phase and row['request_sha256']==request_pin['sha256']
                 and row['event'] in ('CLI-INTENT','CLI-CHILD') and name==f"{row['index']:06d}-{row['event']}.json",'Source-owned exact phase journal')
            value=row['value'];command=value['index'];need(type(command) is int and command>=0 and type(value['phase']) is str and type(value['original_end']) in (int,float) and 0<value['original_end']<=budget.end,'Exact CLI call identity and original cutoff')
            if row['event']=='CLI-INTENT':
                need(command not in intents,'Unique CLI intent');intents[command]=value;continue
            need(command not in children,'Unique CLI birth record');children[command]=value
            need(value['docker_exec_still_gated'] is True and value['independent_group'] is True
                and type(value['pid']) is int and value['pid']>1 and value['pid']==value['pgid']==value['process_identity']['pid']==value['process_identity']['pgid'],'Gated durable CLI birth identity')
            close=retire_cli(value['process_identity'],budget.end,budget,grace)
            records.append({'record':pin(raw),'closure':close})
        except BaseException as error:errors.append({'record':name,'type':type(error).__name__,'cleanup_errors':getattr(error,'cleanup_errors',[])})
    for index,value in intents.items():
        if index not in children:
            errors.append({'stage':'birth_token_missing','command_index':index,'custody_unknown':True})
        elif any(children[index][k]!=value[k] for k in ('phase','original_end')):
            errors.append({'stage':'intent_birth_mismatch','command_index':index,'custody_unknown':True})
    if set(children)-set(intents):errors.append({'stage':'birth_without_intent','custody_unknown':True})
    return {'records':records,'errors':errors,'unmatched_intents':sorted(set(intents)-set(children)),'all_recorded_cli_groups_absent':not errors and all(r['closure']['closed'] for r in records),
            'unrecorded_bootstrap_cannot_exec_docker':True}


def phase_token(value):
    need(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',value),'Bounded source-owned phase identity')
    return value


def read_metadata(path,budget,cap,expected=None):
    """Charge the observed full extent before bounded stable/no-follow capture."""
    budget.tick();n=path.stat(follow_symlinks=False).st_size
    need(0<n<=cap,'Explicit complete metadata ceiling')
    budget.read(n);raw=capture(path,cap,expected)
    return strict(raw),pin(raw)


def replay_events(events,plan_loader,origin,end,selection_loader=None,max_phases=1000000):
    """Pure metadata state machine; no source, process, daemon or array access."""
    planned={j['job_id']:j for j in high_level_jobs()}
    starts={};done={};phase_starts={};phase_done={};owners={};evidence={};plan=None;plan_pin=None;selections=[];slot_keys=set()
    error=None;count=0;last=origin
    try:
        for row,record_pin in events:
            need(row['index']==count and row['ledger_clock']['origin']==origin and row['ledger_clock']['deadline']==end,'Exact original event clock/index')
            observed=row['ledger_clock']['observed'];need(type(observed) in (int,float) and last<=observed<=end,'Monotonic original journal clock');last=observed;count+=1
            event=row.get('event')
            if event=='plan_admitted':
                need(plan is None and not starts,'Exactly one complete plan before scientific producers')
                entry=row['plan'];need(set(entry)=={'path','bytes','sha256'} and entry['path']=='PLAN.json','Exact admitted plan location')
                candidate_pin={k:entry[k] for k in ('bytes','sha256')};descriptor(candidate_pin);candidate_plan=plan_loader(entry)
                validate_plan(candidate_plan)
                need(candidate_plan['high_level_jobs']==list(planned.values()),'Exact complete 87-producer identity roster')
                plan,plan_pin=candidate_plan,candidate_pin
            elif event=='high_level_start':
                key=row['job_id'];need(plan is not None and planned.get(key)==row['job'] and key not in starts,'One exact planned producer start')
                starts[key]=row;evidence.setdefault(key,[]).append(record_pin)
            elif event=='high_level_disposition':
                key=row['job_id'];need(key in planned and key not in done and row['status'] in ('complete','failed','blocked','not_started','unknown'),'One legal full producer disposition')
                need(row['status'] not in ('complete','failed') or key in starts,'Execution result requires admitted start')
                need(row['status']!='not_started' or key not in starts,'A started producer cannot become not-started')
                done[key]={k:row[k] for k in ('status','reason','artifact_pins')};evidence.setdefault(key,[]).append(record_pin)
            elif event=='nested_start':
                key=phase_token(row['phase_id']);need(key not in phase_starts and len(phase_starts)<max_phases,'Bounded full nested roster, no hidden phase retry')
                need(row['job_id'] is None or row['job_id'] in starts,'Nested phase belongs to a started exact producer')
                descriptor(row['request_pin']);need(row['control_directory']=='control/'+key and row['original_deadline']==end,'Exact private provider root/original deadline')
                need(row['exposure_path']=='exposures/'+key+'.json','Exact immutable exposure path');descriptor(row['exposure_pin'])
                if plan is None:
                    need(row['job_id'] is None and row['role']=='operator' and row['slot']['stage'] in ('prepare_originals','prepare_support') and row['action']=={'prepare_originals':'prepare_originals','prepare_support':'prepare_views'}[row['slot']['stage']] and valid_slot(None,row['slot']),'Only source-bound bootstrap preparation before complete plan')
                else:need(valid_slot(plan,row['slot']),'Exact full-roster logical phase slot')
                need(row['slot']['job_id']==row['job_id'],'Slot and outer job identity')
                slot_key=encoded(row['slot']);need(slot_key not in slot_keys,'No duplicate logical phase or hidden retry');slot_keys.add(slot_key)
                phase_starts[key]=dict(row)
            elif event=='transport_event':
                key=phase_token(row['phase_id']);need(key in phase_starts and row['job_id']==phase_starts[key]['job_id'],'Transport event belongs to observed nested request')
                record=row['record'];need(pin(encoded(record))==row['pin'] and record['schema']=='osl_transport_journal_v1' and record['phase_id']==key and record['request_sha256']==phase_starts[key]['request_pin']['sha256'] and record['event']==row['name'],'Exact provider callback body and pin')
                if row['name']=='OWNERSHIP':
                    need(key not in owners,'Single durable ownership declaration')
                    value=record['value'];descriptor(value['ownership_pin']);need(pin(encoded(value['ownership']))==value['ownership_pin'],'Exact externally journaled ownership body')
                    owners[key]=value['ownership_pin']
            elif event=='selection_admitted':
                need(plan is not None and selection_loader is not None,'Selection requires complete plan and exact captured artifact authentication')
                checked=selection_loader(row,phase_starts,phase_done)
                need(not any(s['job_id']==checked['job_id'] and s['unit_id']==checked['unit_id'] for s in selections),'One admitted training-only selection per producer/unit')
                selections.append(checked)
            elif event=='nested_disposition':
                key=phase_token(row['phase_id']);need(key in phase_starts and key not in phase_done and row['job_id']==phase_starts[key]['job_id'],'One observed nested disposition')
                need(row['status'] in ('captured','failed','unknown') and type(row['resources_closed']) is bool,'Explicit nested disposition and custody')
                if row['receipt_pin'] is not None:descriptor(row['receipt_pin'])
                phase_done[key]={k:row[k] for k in ('status','receipt_pin','resources_closed')}
    except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)[:2000],'history_complete':False}
    rows=[]
    for key,job in planned.items():
        value=done.get(key)
        if value is None:
            value={'status':'unknown' if error or key in starts else 'not_started','reason':'history_incomplete' if error else 'started_without_terminal_disposition' if key in starts else 'no_start_in_complete_durable_history','artifact_pins':None}
        rows.append({'job':job,**value,'evidence':evidence.get(key,[])})
    nested_rows=[{'phase_id':key,'slot':r['slot'],'job_id':r['job_id'],'action':r['action'],'role':r['role'],**phase_done.get(key,{'status':'unknown','receipt_pin':None,'resources_closed':False})} for key,r in phase_starts.items()]
    try:coverage=None if plan is None else summarize_missing(plan,nested_rows,selections)
    except BaseException as exc:
        coverage={'complete':False,'unknown':True,'error_type':type(exc).__name__}
        error=error or {'type':type(exc).__name__,'message':'Full parametric roster reconciliation failed','history_complete':False}
    return {'schema':'paper_i_independent_producer_ledger_v1','high_level_expected':87,'encoding_expected':60,'native_expected':27,
            'high_level':rows,'observed_nested':nested_rows,'plan_summary':None if plan is None else {'schema':plan['schema'],'counts':plan['counts'],'slot_schema':plan['slot_schema']},'nested_coverage':coverage,'plan_pin':plan_pin,'authenticated_selections':selections,'journal_error':error,'journal_events_read':count,
            'nested_workload_unknown_without_admitted_plan':plan is None,
            'all_high_level_complete':error is None and all(r['status']=='complete' for r in rows),
            'all_observed_nested_closed':error is None and all(r['resources_closed'] for r in nested_rows),
            'unknown_cost_is_never_zero':True,'_phase_starts':phase_starts,'_ownership_pins':owners}


def attempt_ledger(work,budget,host):
    names=[];root=work/'journal'
    def events():
        if not root.exists():return
        need(root.is_dir() and not root.is_symlink(),'Exact controller-owned journal directory')
        for entry in root.iterdir():
            need(len(names)<host['max_events'] and re.fullmatch('[0-9]{7}\.json',entry.name),'Bounded whole-program journal')
            names.append(entry.name)
        for index,name in enumerate(sorted(names)):
            need(name==f'{index:07d}.json','Contiguous complete durable event history')
            yield read_metadata(root/name,budget,host['max_metadata_bytes'])
    def load_plan(entry):
        value,_=read_metadata(work/'PLAN.json',budget,host['max_metadata_bytes'],{k:entry[k] for k in ('bytes','sha256')})
        return value
    def load_selection(row,starts,done):
        entry=row['selection'];need(type(entry) is dict and set(entry)=={'path','bytes','sha256'},'Exact selection artifact reference')
        match=re.fullmatch(r'quarantine/([A-Za-z0-9_-]{1,96})/RESULT\.json',entry['path']);need(match is not None,'Exact captured selection location')
        phase=match.group(1);need(phase in starts and phase in done,'Selection has observed request and closure')
        start=starts[phase];finish=done[phase]
        need(start['slot']['stage']=='selection' and start['job_id']==row['job_id'] and start['slot']['unit_id']==row['unit_id'],'Exact training selection logical slot')
        need(finish['status']=='captured' and finish['resources_closed'] is True and finish['receipt_pin'] is not None,'Complete closed selection capture')
        receipt,_=read_metadata(work/'control'/phase/'RECEIPT.json',budget,host['max_metadata_bytes'],finish['receipt_pin'])
        need(receipt['schema']=='osl_owned_phase_receipt_v1' and receipt['phase_id']==phase and receipt['request_sha256']==start['request_pin']['sha256'] and receipt['status']=='captured' and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True,'Independent selection receipt identity/closure')
        expected={k:entry[k] for k in ('bytes','sha256')};descriptor(expected)
        need(receipt['output_inventory']['files']['RESULT.json']==expected,'Selection result in complete admitted output inventory')
        value,_=read_metadata(child(work,entry['path']),budget,host['max_metadata_bytes'],expected)
        need(value['groups']==row['groups'],'Selection journal matches captured source-bound result')
        return {'job_id':row['job_id'],'unit_id':row['unit_id'],'groups':value['groups'],'selection_pin':expected}
    return replay_events(events(),load_plan,budget.origin,budget.end,load_selection,host['max_phases'])

def recover_phases(work,attempts,engine_pin,controller_pin,controller_closed,op,budget,journal):
    """Independent owned-only recovery; failures do not skip other known phases."""
    from transport import Provider
    host=op['host'];controls=work/'control';quarantine=work/'quarantine'
    starts=attempts['_phase_starts'];owners=attempts['_ownership_pins'];keys=set(starts);inventory_error=None
    try:
        if controls.exists():
            need(controls.is_dir() and not controls.is_symlink(),'Source-owned private control root')
            for entry in controls.iterdir():
                need(len(keys)<host['max_phases'] or entry.name in keys,'Bounded full phase inventory')
                phase_token(entry.name);need(entry.is_dir() and not entry.is_symlink(),'Ordinary owned phase directory')
                keys.add(entry.name)
    except BaseException as error:inventory_error={'type':type(error).__name__,'message':str(error)[:2000]}
    results=[]
    for phase in sorted(keys):
        row={'phase_id':phase,'recovery_complete':False}
        try:
            budget.tick()
            need(controller_closed,'Controller custody must close before daemon recovery')
            need(phase in starts,'Unjournaled phase has unknown custody; never invent ownership')
            start=starts[phase];control=child(controls,phase)
            need(control.exists() and control.is_dir(),'Started phase directory must be observed')
            if phase not in owners:
                need(not (control/'OWNERSHIP.json').exists(),'Ownership without parent-journal authentication remains unknown')
                # Source calls the durable parent OWNERSHIP callback before any
                # Docker CLI gate. A completed complete history can establish
                # this no-creation state; a damaged history cannot.
                need(attempts['journal_error'] is None,'Missing ownership in damaged history remains unknown')
                row.update(recovery_complete=True,resource_creation_not_started=True)
                results.append(row);continue
            request,request_pin=read_metadata(control/'REQUEST.json',budget,host['max_metadata_bytes'],start['request_pin'])
            need(request['phase_id']==phase and request['role']==start['role'] and request['action']==start['action'] and request['clock']['origin']==budget.origin and request['clock']['phase_deadline']<=budget.end-host['cleanup_seconds'],'Exact request identity and original clock')
            exposure=child(work,start['exposure_path'])
            _,exposure_pin=read_metadata(exposure,budget,host['max_metadata_bytes'],start['exposure_pin'])
            need(request['exposure']==exposure_pin,'Original immutable exposure approval join')
            read_metadata(control/'OWNERSHIP.json',budget,min(65536,host['max_metadata_bytes']),owners[phase])
            cli=inspect_cli(control,phase,request_pin,budget,host['recovery'],host['controller_grace_seconds'])
            row['prior_cli_custody']=cli
            need(cli['all_recorded_cli_groups_absent'],'All recorded CLI identity groups must close before daemon recovery')
            limits=host['recovery']
            budget.reserve_producer('outer_recovery_'+phase,limits['source_read_bytes'],limits['host_write_bytes'],limits['host_write_bytes'])
            provider=Provider(controls,quarantine,host['docker_binary'],host['docker_socket'],engine_pin,
                {exposure_pin['sha256']:str(exposure)},limits['source_read_bytes'],limits['host_write_bytes'])
            recovered=provider.recover(phase,request_pin,owners[phase],budget.end,journal,limits,controller_pin)
            receipt=recovered['receipt'];row.update(recovered)
            row['recovery_complete']=bool(receipt.get('all_resource_custody_closed') is True and receipt.get('all_namespaces_empty') is True and receipt.get('cli_reaped') is True)
        except BaseException as error:
            row.update(error_type=type(error).__name__,message=str(error)[:2000],actual_cost_unknown=True,cleanup_errors=getattr(error,'cleanup_errors',[]))
            try:journal('RECOVERY-FAILED',row)
            except BaseException as secondary:row['failure_publication_error']=type(secondary).__name__
        results.append(row)
    return {'phases':results,'inventory_error':inventory_error,
        'independent_terminal_absence_complete':controller_closed and inventory_error is None and attempts['journal_error'] is None and all(r['recovery_complete'] for r in results),
        'unknown_creation_outcomes_resolved_by_absence':False}


def run(operation_path,operation_pin,output,origin=BOOT):
    """Concrete future full operation, separately authorized and explicitly bound."""
    context=globals().get('_SOURCE_CONTEXT')
    if context is None:return authenticated_run(operation_path,operation_pin,output,origin)
    context['loader'].verify()
    need(context['operation_pin']==operation_pin and context['origin']==origin,'Authenticated operation and original clock cannot change')
    import resource
    descriptor(operation_pin);raw=context['operation_raw'];op=validate_operation(strict(raw));host=op['host']
    need(sys.platform.startswith('linux'),'Reviewed Linux pidfd/proc custody and address-space limits')
    root=Path(output);need(root.is_absolute() and not root.exists() and not root.is_symlink(),'Fresh absolute outer operation directory')
    root.mkdir(mode=0o700,parents=False);(root/'journal').mkdir(mode=0o700)
    limits={'wall_seconds':op['global_limits']['wall_seconds'],**host['parent_limits']}
    budget=Budget(limits,origin,root/'journal');budget.read(context['read_bytes']);end=budget.end;work_end=end-host['cleanup_seconds']
    need(budget.tick()<work_end,'Operation parse and cleanup reserve are on original global clock')
    # This supervisor is a dedicated future CLI. Its address-space ceiling plus
    # the child ceiling fits the approved host partition; kernel/RSS remains
    # unmeasured. Container/holder caps are separate operation resources.
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(host['parent_memory_bytes'],host['parent_memory_bytes']))
    operation_copy=root/'OPERATION.json';budget.save(operation_copy,raw)
    for item in (host['python'],{'path':host['docker_binary'],**host['docker_binary_pin']}):
        expected={k:item[k] for k in ('bytes','sha256')};budget.read_file(item['path'],expected,expected['bytes'])
    here=Path(__file__).resolve().parent;view=source_view(op,here,root/'host_source',budget)
    engine_pin=view['files']['transport/SOURCE_MANIFEST.json'];work=root/'work'
    loader='import sys,runpy;p=sys.argv.pop(1);sys.path.insert(0,p);runpy.run_path(p+"/controller.py",run_name="__main__")'
    argv=[host['python']['path'],'-I','-B','-c',loader,view['root'],'--operation',str(operation_copy),
          '--operation-pin',encoded(operation_pin).decode().strip(),'--output',str(work),'--origin',repr(origin),
          '--global-deadline',repr(end),'--work-deadline',repr(work_end)]
    budget.event({'event':'outer_launch_plan','origin':origin,'global_deadline':end,'work_deadline':work_end,
        'operation':operation_pin,'source_manifest':op['source_manifest'],'source_view':view['manifest'],
        'parent_limits':host['parent_limits'],'controller_limits':host['controller_limits'],
        'authenticated_bootstrap_read_bytes':context['read_bytes'],'executed_local_modules':context['loader'].verify()})
    result=watch(argv,here,work_end,budget,host['controller_grace_seconds'],host['log_bytes'],host['controller_memory_bytes'])
    logs=result.pop('logs_data');publication_errors=[]
    for name,body in logs.items():
        try:budget.save(root/(name+'.log'),body)
        except BaseException as error:publication_errors.append({'artifact':name+'.log','error_type':type(error).__name__})
    controller_body=encoded(result);controller_pin=pin(controller_body)
    try:budget.save(root/'CONTROLLER_CLOSE.json',controller_body)
    except BaseException as error:publication_errors.append({'artifact':'CONTROLLER_CLOSE.json','error_type':type(error).__name__})
    def recovery_journal(name,value):
        try:budget.event({'event':'outer_recovery','name':name,'value':value})
        except BaseException as error:
            publication_errors.append({'artifact':'outer_recovery_event','name':name,'value_pin':pin(encoded(value)),'error_type':type(error).__name__})
    controller_closed=result['reaped'] and result['process_group_absent']
    attempts=attempt_ledger(work,budget,host)
    recovery=recover_phases(work,attempts,engine_pin,controller_pin,controller_closed,op,budget,recovery_journal)
    inner=None;inner_report=None;inner_error=None
    try:
        if (work/'CONTROLLER_RESULT.json').exists():
            value,p=read_metadata(work/'CONTROLLER_RESULT.json',budget,host['max_metadata_bytes']);inner={'pin':p,'value':value}
        if (work/'report.json').exists():
            value,p=read_metadata(work/'report.json',budget,host['max_metadata_bytes']);inner_report={'pin':p,'value':value}
    except BaseException as error:inner_error={'type':type(error).__name__,'message':str(error)[:2000]}
    # Closure may be established after a failed producer; it never rewrites a
    # failed scientific disposition or treats the unknown census as zero work.
    attempts.pop('_phase_starts');attempts.pop('_ownership_pins')
    report={'schema':'paper_i_complete_program_outer_receipt_v1','task':TASK,'operation':operation_pin,
        'origin':origin,'deadline':end,'work_deadline':work_end,'controller_close':controller_pin,
        'controller_natural_exit':result['natural_exit'],'independent_recovery':recovery,'controller_result':inner,'controller_report':inner_report,
        'inner_result_error':inner_error,'independent_attempt_ledger':attempts,'global_limits':op['global_limits'],
        'parent_partition':budget.snapshot(),'controller_partition_limits':host['controller_limits'],
        'authenticated_bootstrap':{'physical_read_bytes':context['read_bytes'],'source_manifest':context['manifest_pin'],'executed_local_modules':context['loader'].verify(),'cached_bytes_used_for_source_copy':True},
        'whole_logical_charge_semantics':'Disjoint preallocated parent/controller partitions under the same original clock; conservative producer reservations, no kernel native I/O or RSS claim',
        'publication_errors':publication_errors,'controller_close_independently_observed_in_memory':result,
        'source_full_program_complete':bool(not publication_errors and inner_error is None and result['natural_exit'] and recovery['independent_terminal_absence_complete'] and attempts['all_high_level_complete'] and attempts['all_observed_nested_closed'] and attempts['nested_coverage'] and attempts['nested_coverage'].get('complete') is True and inner and inner['value'].get('complete') is True),
        'actual_whole_producer_resources_measured':False,'runtime_qualified':False,'scientific_qualification':False,'whole_paper_reproduced':False}
    receipt=budget.save(root/'OUTER_RECEIPT.json',encoded(report));budget.tick();return receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);p.add_argument('--operation-bytes',type=int,required=True)
    p.add_argument('--operation-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    run(a.operation,{'bytes':a.operation_bytes,'sha256':a.operation_sha256},a.output)


if __name__=='__main__':main()
