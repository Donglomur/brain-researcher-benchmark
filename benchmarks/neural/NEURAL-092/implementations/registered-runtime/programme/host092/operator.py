"""Stable Linux supervisor with original errors through every owned suffix."""
import argparse,ctypes,os,resource,signal,time,traceback
from pathlib import Path
from .admission import load_selection,selected_profile,full_plan,root_owned
from .storage import Store,Ledger,ErrorOwner,encode,digest
from .linux import acquire_group,Runtime,write,metrics,delete_owned_runtimes

def verify_image(profile,ledger,errors):
    from .storage import parts
    import stat
    start=len(errors.events);selection=root=None;manifest=None
    def body():
        nonlocal selection,root,manifest
        row=profile['rootfs_manifest'];path=root_owned(row['path'])
        selection=Store(str(path.parent),ledger,errors=errors)
        manifest=selection.json(path.name,{k:row[k]for k in ('bytes','sha256')},1048576)
        if set(manifest)!={'schema','members'}or manifest['schema']!='neural092_selected_clean_image_v1'or type(manifest['members'])is not dict:raise ValueError('complete selected image inverse')
        members=manifest['members'];seen=set();image=Path(profile['rootfs']);root=Store(str(image),ledger,errors=errors)
        for base,dirs,files in os.walk(image,followlinks=False):
            root_owned(base,True)
            for name in dirs+files:
                p=Path(base)/name;st=p.lstat()
                if stat.S_ISDIR(st.st_mode):continue
                key=str(p.relative_to(image));parts(key)
                if key not in members:raise ValueError('unselected image member')
                seen.add(key);desc=members[key]
                if stat.S_ISLNK(st.st_mode):
                    if desc!={'kind':'symlink','target':os.readlink(p)}:raise ValueError('image link identity')
                elif stat.S_ISREG(st.st_mode):
                    root_owned(p)
                    if set(desc)!={'kind','bytes','sha256'}or desc['kind']!='regular':raise ValueError('image regular descriptor')
                    root.read(key,{k:desc[k]for k in ('bytes','sha256')},desc['bytes'])
                else:raise ValueError('no special image members')
        if seen!=set(members):raise ValueError('missing image member')
    try:errors.call('verify_image',body)
    except BaseException:pass
    finally:
        if root is not None:errors.cleanup('image_store_close',root.close)
        if selection is not None:errors.cleanup('image_selection_close',selection.close)
    errors.finish(start)

def mount_output(path,bytes_limit,inodes):
    path.mkdir(mode=0o700);libc=ctypes.CDLL(None,use_errno=True)
    options=('size='+str(bytes_limit)+',nr_inodes='+str(inodes)+',mode=0700,uid=65534,gid=65534').encode()
    if libc.mount(b'tmpfs',os.fsencode(path),b'tmpfs',2|4|8,options)!=0:raise OSError(ctypes.get_errno(),'bounded output mount')
def unmount(path):
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.umount2(os.fsencode(path),0)!=0:raise OSError(ctypes.get_errno(),'owned output unmount')

def verify_source(profile,ledger,errors):
    start=len(errors.events);root=None
    def body():
        nonlocal root
        root=Store(profile['source_root'],ledger,errors=errors)
        for name,pin in profile['source_files'].items():
            root_owned(Path(profile['source_root'])/name);root.read(name,pin,pin['bytes'])
        if profile['binding_pins']['source_snapshot']!=digest(encode(profile['source_files'])):raise ValueError('original selected complete source inverse')
    try:errors.call('verify_source',body)
    except BaseException:pass
    finally:
        if root is not None:errors.cleanup('source_store_close',root.close)
    errors.finish(start)

def publish_final(work,ledger,name,value,errors):
    """One actual Store owner; its constructor, encode, write and close all join."""
    start=len(errors.events);store=None;pin=None
    def body():
        nonlocal store,pin
        store=Store(str(work),ledger,True,errors)
        pin=store.put(name,encode(value()))
    try:errors.call(name+'_publication',body)
    except BaseException:pass
    finally:
        if store is not None:errors.cleanup(name+'_store_close',store.close)
    errors.finish(start);return pin

def retire_gate(gate,index):
    fd=gate[index];gate[index]=None
    if fd is not None:os.close(fd)

def wait_owned_child(pid,seconds,poll):
    deadline=time.monotonic()+seconds
    while True:
        got,status=os.waitpid(pid,os.WNOHANG)
        if got:return status
        if time.monotonic()>=deadline:raise TimeoutError('owned coordinator wait remains unobserved')
        time.sleep(poll)

def coordinator(profile,work,group,supervisor_pid,selection):
    from gain.cost import Attempt
    from gain.programme import run_programme
    from .host import Host
    from .frozen import plain
    # This original caller owns both journals before Runtime/Host acquisition.
    # Scientific Attempt is unchanged. Its events are scientific/boundary
    # summaries; host_errors are the ordered ordinary nested occurrences.
    attempt=Attempt();attempt.host_errors=ErrorOwner();errors=attempt.host_errors
    ledger=Ledger(profile['io_limits']['coordinator']);host=runtime=None;result=None
    try:
        runtime=errors.call('runtime_acquire',lambda:Runtime(profile,work,group,ledger,errors))
        host=Host.__new__(Host)
        errors.call('host_acquire',lambda:Host.__init__(host,profile,work,group,runtime,ledger,supervisor_pid,selection,errors))
        result=run_programme(host,attempt)
    except BaseException as error:
        if attempt.first is not error:attempt.fail('coordinator',error)
    finally:
        if host is not None:attempt.cleanup('host_close',host.close)
    # A later ordinary failure must not replace an earlier scientific first.
    try:
        publish_final(work,ledger,'COORDINATOR_FINAL.json',lambda:plain({
            'result':result,'first':attempt.first,'events':attempt.events,
            'host_errors':errors.events,'calls':attempt.calls.counts,
            'ledger':ledger.used,'runtime':[]if runtime is None else runtime.records,
            'qualified':False}),errors)
    except BaseException as error:
        attempt.fail('coordinator_final_publication',error)
    attempt.finish()

def execute(selection,bootstrap=None):
    errors=ErrorOwner()
    start,before=bootstrap if bootstrap is not None else(time.monotonic_ns(),resource.getrusage(resource.RUSAGE_SELF))
    profile=errors.call('selection',lambda:selected_profile(selection))
    plans,admission=errors.call('full_resource_plan',lambda:full_plan(profile))
    ledger=Ledger(profile['io_limits']['supervisor'])
    verify_source(profile,ledger,errors);verify_image(profile,ledger,errors)
    work=Path(profile['work_parent'])/profile['run_id']
    errors.call('work_acquire',lambda:work.mkdir(mode=0o700))
    owned=[];mounted=[];gate=[None,None];pid=status=group=None;observations={};snapshot=None
    body_start=len(errors.events)
    try:
        group=acquire_group(profile['cgroup_parent'],profile['run_id'],profile['limits'],owned,errors)
        group.leaf('coordinator');group.leaf('control')
        for name in ('prediction','observed'):
            group.leaf(name);path=work/(name+'-output')
            mount_output(path,profile['runtime_output_bytes'],profile['io_limits']['coordinator']['files']);mounted.append(path)
        gate[:]=os.pipe() # both endpoints retained BEFORE a possible failed fork
        pid=os.fork()
        if pid==0:
            try:
                retire_gate(gate,1)
                if os.read(gate[0],1)!=b'G':raise RuntimeError('parent placement gate absent')
                retire_gate(gate,0)
                coordinator(profile,work,group,os.getppid(),selection)
            except BaseException:
                # Child termination retires its remaining descriptors. Only the
                # original parent wait conveys status, not a reconstructed error.
                os._exit(1)
            os._exit(0)
        retire_gate(gate,0)
        write(group.path/'coordinator/cgroup.procs',pid,errors)
        os.write(gate[1],b'G')
        retire_gate(gate,1)
        deadline=time.monotonic()+profile['wall_seconds']
        while True:
            got,status_now=os.waitpid(pid,os.WNOHANG)
            if got:status=status_now # retain original reap BEFORE fallible metrics
            observations['latest']=metrics(group.path,errors)
            if got:break
            if time.monotonic()>=deadline:raise TimeoutError('entire evaluator/candidate wall limit')
            time.sleep(profile['poll_seconds'])
        if status!=0:raise RuntimeError('coordinator failed with original wait status '+str(status))
    except BaseException as error:
        if not any(row['error']is error for row in errors.events[body_start:]):errors.fail('supervisor_body',error)
    finally:
        for i in (0,1):
            if gate[i]is not None:errors.cleanup('gate_'+str(i)+'_close',lambda i=i:retire_gate(gate,i))
        for g in reversed(owned):
            if g.owned:
                def drain(g=g):observations['post_stop']=g.drain(profile['control_seconds'])
                errors.cleanup('group_drain',drain)
        if pid is not None and status is None:
            # Kill and wait are independent attempts. A failed kill never skips
            # wait. ESRCH is an absent signal target, never proof of wait status.
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as error:errors.fail('coordinator_kill',error)
            def wait():
                nonlocal status
                status=wait_owned_child(pid,profile['control_seconds'],profile['poll_seconds'])
            errors.cleanup('wait_after_stop',wait)
        if 'post_stop'in observations:
            parent=None;capture_start=len(errors.events)
            try:
                parent=Store(str(work),ledger,True,errors)
                b=parent.capture_untrusted('COORDINATOR_FINAL.json',profile['runtime_output_bytes'])
                snapshot=parent.put('PARENT_CAPTURED_COORDINATOR.json',b)
            except BaseException as error:
                if not any(row['error']is error for row in errors.events[capture_start:]):errors.fail('parent_partial_output_capture',error)
            finally:
                if parent is not None:errors.cleanup('parent_capture_close',parent.close)
            errors.cleanup('runtime_deletion',lambda:delete_owned_runtimes(profile,work,('prediction','observed'),errors,owned[-1].path/'control',ledger))
        for path in reversed(mounted):errors.cleanup('output_unmount',lambda path=path:unmount(path))
        for g in reversed(owned):
            if g.owned and 'post_stop'in observations:
                def final_drain(g=g):
                    observations['after_runtime_delete']=g.drain(profile['control_seconds'])
                    g.remove_empty()
                errors.cleanup('group_remove',final_drain)
    terminal=None
    def terminal_snapshot():
        nonlocal terminal
        after=resource.getrusage(resource.RUSAGE_SELF)
        terminal={'schema':'neural092_original_supervisor_v1','original_child_pid':pid,'original_wait_status':status,
          'observations':observations,'captured_coordinator':snapshot,'resource_admission':admission,
          'supervisor_elapsed_ns':time.monotonic_ns()-start,'supervisor_user_seconds':after.ru_utime-before.ru_utime,
          'supervisor_system_seconds':after.ru_stime-before.ru_stime,'supervisor_peak_rss_absolute':after.ru_maxrss,
          'supervisor_io_reservations':dict(ledger.used),
          'failures':[{'where':row['where'],'type':type(row['error']).__name__}for row in errors.events],
          'raw_errors_remain_in_original_supervisor':True,'qualified':False}
        return terminal
    # Construct the final observations under the same owner; a failed snapshot
    # cannot masquerade as a complete final record.
    try:
        errors.call('supervisor_final_observation',terminal_snapshot)
        publish_final(work,ledger,'SUPERVISOR_FINAL.json',lambda:terminal,errors)
    except BaseException:pass # already retained by the original owner
    def after_tail():
        if terminal is None:return
        usage=resource.getrusage(resource.RUSAGE_SELF)
        terminal['after_owned_retirement']={'elapsed_ns':time.monotonic_ns()-start,
          'user_seconds':usage.ru_utime-before.ru_utime,'system_seconds':usage.ru_stime-before.ru_stime,
          'peak_rss_absolute':usage.ru_maxrss,'io_reservations':dict(ledger.used),
          'durable_snapshot_precedes_its_own_publication_tail':True}
    errors.cleanup('supervisor_after_publication_observation',after_tail)
    errors.finish()
    return terminal

def main():
    bootstrap=(time.monotonic_ns(),resource.getrusage(resource.RUSAGE_SELF))
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True);a=p.parse_args()
    terminal=execute(load_selection(a.selection,a.selection_sha256),bootstrap)
    print(encode(terminal).decode('utf8'),end='')
if __name__=='__main__':main()
