"""Explicit independently selected entry; shipped deployment is disabled.

This entry never obtains credentials from key files or environment discovery.
A future authorized launcher may pass one already-authorized HTTP header on an
inherited pipe. The header is not hashed, logged or persisted. No API is invoked
in source construction. Independent outer launch/exit observation is required.
"""
import argparse
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import selectors
import time
import types

def close_owned(operations,primary=None):
    first=primary
    for phase,operation in operations:
        try:operation()
        except BaseException as error:
            if first is None:first=error
            else:
                try:
                    records=list(getattr(first,'ach_secondary_errors',[]));records.append({'phase':phase,'type':type(error).__name__})
                    first.ach_secondary_errors=records
                except BaseException:pass
    if primary is None and first is not None:raise first

def checked(path,size,sha,cap):
    if type(size) is not int or not 0<=size<=cap:raise ValueError('bounded independently selected source extent')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);primary=None
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=size:raise ValueError('ordinary exact source')
        parts=[];left=size+1
        while left:
            block=os.read(fd,min(left,65536))
            if not block:break
            parts.append(block);left-=len(block)
        body=b''.join(parts)
        after=os.fstat(fd)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('changed source')
        if len(body)!=size or hashlib.sha256(body).hexdigest()!=sha:raise ValueError('source pin mismatch')
        return body
    except BaseException as error:primary=error;raise
    finally:close_owned([('bootstrap source descriptor close',lambda:os.close(fd))],primary)

def bootstrap(root,manifest_path,manifest_bytes,manifest_sha256):
    raw=checked(manifest_path,manifest_bytes,manifest_sha256,65536)
    manifest=json.loads(raw);bodies={};reads=len(raw)
    if manifest.get('schema')!='ach_investigation_runtime_source_v1':raise ValueError('runtime manifest schema')
    for item in manifest['files']:
        name=item['path']
        if not isinstance(name,str) or name.startswith('/') or any(x in ('','..','.') for x in name.split('/')):raise ValueError('source path')
        if name in bodies:raise ValueError('duplicate runtime source')
        body=checked(root/name,item['bytes'],item['sha256'],262144);bodies[name]=body;reads+=len(body)
    modules={};loading=set();original_import=builtins.__import__
    def get(name):
        if name in modules:return modules[name]
        path=name+'.py'
        if path not in bodies or not name.startswith('ach_') or name=='ach_entry':raise ValueError('fixed owner module')
        if name in loading:raise ValueError('owner import cycle')
        loading.add(name);m=types.ModuleType(name);m.__file__=str(root/path);m.__package__=''
        def frozen_import(module_name,globals=None,locals=None,fromlist=(),level=0):
            if level:raise ValueError('no relative owner imports')
            if module_name.startswith('ach_'):return get(module_name)
            return original_import(module_name,globals,locals,fromlist,level)
        m.__dict__['__builtins__']={**vars(builtins),'__import__':frozen_import}
        try:exec(compile(bodies[path],m.__file__,'exec'),m.__dict__);modules[name]=m;return m
        finally:loading.remove(name)
    return get,bodies,reads,{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def read_authorization_pipe(fd,origin,deadline):
    """Owned inherited pipe, bounded EOF under the original clock; no log/hash."""
    if type(fd) is not int or fd<3 or type(origin) is not int or type(deadline) is not int:
        raise ValueError('invalid opaque credential transport')
    if not origin<=time.monotonic_ns()<deadline:raise ValueError('credential transport original cutoff')
    if not stat.S_ISFIFO(os.fstat(fd).st_mode):raise ValueError('credential transport must be an inherited pipe')
    selector=None;primary=None;parts=[];total=0
    try:
        os.set_blocking(fd,False);selector=selectors.DefaultSelector();selector.register(fd,selectors.EVENT_READ)
        while True:
            now=time.monotonic_ns()
            if not origin<=now<deadline:raise ValueError('credential transport original cutoff')
            ready=selector.select(min(.1,(deadline-now)/1e9))
            if not ready:continue
            block=os.read(fd,min(4096,8193-total))
            if not block:break
            total+=len(block)
            if total>8192:raise ValueError('opaque credential transport extent')
            parts.append(block)
        if not origin<=time.monotonic_ns()<deadline or not total:raise ValueError('opaque credential transport incomplete')
        raw=b''.join(parts)
        if any(x<32 or x>126 for x in raw):raise ValueError('opaque credential encoding refused')
        return raw.decode('ascii')
    except BaseException as error:primary=error;raise
    finally:
        cleanup=[]
        if selector is not None:cleanup.append(('credential selector close',selector.close))
        cleanup.append(('owned credential pipe close',lambda:os.close(fd)))
        close_owned(cleanup,primary)

def launch(options,authorization_header=None):
    root=Path(__file__).absolute().parent
    get,bodies,bootstrap_reads,source_pin=bootstrap(root,options.manifest,options.manifest_bytes,options.manifest_sha256)
    u=get('ach_util');selection_pin={'bytes':options.selection_bytes,'sha256':options.selection_sha256}
    selection=u.decode(u.read_exact(options.selection,selection_pin,1048576),1048576)
    u.need(selection.get('execution_enabled') is True,'production remains disabled before original inputs, keys, sockets or provider')
    helpers=get('ach_helpers').Helpers();wire=helpers.get('wire')
    ledger=get('ach_ledger').OperationLedger(wire.Ledger(selection['logical_limits'],selection['origin_ns'],selection['scientific_ns'],
                       selection['closeout_ns'],selection['outer_ns']),selection['closeout_reserve'])
    ledger.reserve({'read_bytes':bootstrap_reads+2*selection_pin['bytes']+sum(map(len,helpers.bodies.values()))+get('ach_helpers').BINDING['bytes']+8193},
                   'entry/bootstrap source and conservative bounded credential-pipe read reservation')
    acquired=[];primary=None;result=None;journal=None;secondary=[]
    try:
        authority=get('ach_authority').Authority(options.selection,selection_pin,source_pin,ledger,helpers)
        d=selection['inputs_descriptor'];inputs=u.decode(u.read_exact(d['path'],{k:d[k] for k in ('bytes','sha256')},
            selection['input_metadata_bytes'],ledger),selection['input_metadata_bytes']);authority.validate_inputs(inputs)
        deployment=inputs['deployment'];transport=helpers.get('transport')
        provider=transport.ProviderClient(deployment['provider_endpoint'],deployment['path'],deployment['pin'],ledger)
        acquired.append(('provider transport finish',provider.finish_transport))
        raw_observer=transport.ObserverClient(deployment['observer_endpoint'],deployment['path'],deployment['pin'],ledger)
        acquired.append(('observer transport finish',raw_observer.finish_transport))
        authority.validate_clients(provider,raw_observer)
        observer=get('ach_authority').JoinedObserver(raw_observer,authority)
        journal=get('ach_journal').Journal(selection['private_journal_path'],ledger,inputs['profile']['journal_record_bytes'])
        # Closure order is provider, observer, then journal, so every earlier
        # cleanup failure can still be recorded in the owned private journal.
        acquired.append(('private journal close',journal.close));authority.bind_journal(journal)
        job_transport=get('ach_transport').JobTransport(provider,observer,ledger,source_pin,inputs['profile']['job_transport'])
        jobs=get('ach_jobs').Jobs(job_transport,ledger,journal,bodies['ach_generated_worker.py'],inputs['profile']['generated_job'],
            selection['python_path'],inputs['study_admission']['authoring_commitment_pin'])
        libraries=get('ach_bindings').Libraries(ledger)
        if authorization_header is None and getattr(options,'authorization_fd',None) is not None:
            authorization_header=read_authorization_pipe(options.authorization_fd,ledger.origin,ledger.scientific)
        u.need(type(authorization_header) is str and 0<len(authorization_header)<=8192 and
               all(32<=ord(c)<=126 for c in authorization_header),'separately authorized opaque ASCII provider credential required')
        result=get('ach_controller').Controller(libraries,helpers,authority,provider,observer,jobs,ledger,journal,
                                               source_pin,authorization_header).run(inputs)
    except BaseException as error:
        primary=error
        u.finish_owned([('entry failure accounting',lambda:ledger.fail('entry setup or programme',error))],error)
        if journal is not None:u.finish_owned([('entry initiating failure journal',lambda:journal.failure('entry setup or programme',error))],error)
    finally:
        for phase,operation in acquired:
            try:operation()
            except BaseException as error:
                if primary is None:primary=error
                else:u.retain_secondary(primary,error,phase)
                secondary.append({'phase':phase,'type':type(error).__name__})
                u.finish_owned([('entry cleanup failure accounting',lambda:ledger.fail(phase,error))],primary)
                if journal is not None and not journal.closed:
                    u.finish_owned([('entry cleanup failure journal',lambda:journal.failure(phase,error))],primary)
    if primary is not None:
        failure={'schema':'ach_controller_entry_failure_v1','primary':type(primary).__name__,
            'secondary':list(getattr(primary,'ach_secondary_errors',[])),'cleanup_attempt_failures':secondary,
            'logical_accounting':ledger.report(),'source_pin':source_pin,
            'job_failure_descriptor':getattr(primary,'ach_controller_failure',None),
            'pending_authenticated_exchange':getattr(primary,'ach_measurement_exchange',None),
            'native_failure_descriptor':getattr(primary,'ach_failure_descriptor',None),
            'scientific_qualified':False,'independent_outer_failure_capture_required':True}
        def emit_failure():
            body=u.encode(failure);u.need(len(body)<=selection['entry_output_bytes'],'complete bounded failure evidence')
            ledger.reserve({'write_bytes':len(body)+1},'entry failure serialization',cutoff='closeout')
            view=memoryview(body+b'\n')
            while view:
                ledger.tick('closeout');n=os.write(2,view);u.need(n>0,'complete failure evidence write');view=view[n:]
        u.finish_owned([('external entry failure stream',emit_failure)],primary)
        raise primary
    ledger.tick('closeout');result['entry_logical_accounting']=ledger.report()
    result['external_final_natural_zero_required']=True
    return result,ledger,selection

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest_sha256','selection','selection_sha256'):parser.add_argument('--'+name.replace('_','-'),required=True)
    for name in ('manifest_bytes','selection_bytes'):parser.add_argument('--'+name.replace('_','-'),required=True,type=int)
    parser.add_argument('--authorization-fd',type=int)
    options=parser.parse_args();header=None
    # The source default is disabled. Check that gate before reading even an
    # inherited credential pipe. No key-file discovery is implemented.
    selected=json.loads(checked(options.selection,options.selection_bytes,options.selection_sha256,1048576))
    if selected.get('execution_enabled') is not True:raise ValueError('production execution disabled')
    result,ledger,selection=launch(options,header);raw=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>selection['entry_output_bytes']:raise ValueError('complete result serialization extent')
    ledger.reserve({'write_bytes':len(raw)+1},'entry final result',cutoff='closeout')
    view=memoryview(raw+b'\n')
    while view:
        ledger.tick('closeout');n=os.write(1,view)
        if n<=0:raise ValueError('complete final output write')
        view=view[n:]
    ledger.tick('closeout');return 0

if __name__=='__main__':raise SystemExit(main())
