"""Concrete future Linux OCI mount/process/cgroup policy and write observer.

This source is not deployment qualification. The selected runc/rootfs/bpftrace
and cgroup permissions do not exist in this packet and must pass G09/G18/G22.
The observer charges requested write bytes conservatively. Unsupported write
mechanisms and shared writable mappings are denied rather than unmetered.
"""
import os
from pathlib import Path
import signal
import subprocess
import time
from .io import need, read, load, dump, identity, tree, canonical
from .resources import limits, eligible
from .process import command, validate_command

DENIED_WRITE = ['writev','pwritev','pwritev2','sendfile','sendfile64','copy_file_range','splice','vmsplice','tee',
                'truncate','ftruncate','fallocate','io_setup','io_submit','io_uring_setup','io_uring_enter',
                'io_uring_register','shmget','shmat','memfd_create','process_vm_writev','ptrace','bpf','perf_event_open','openat2']


def config(profile,source,inputs,state,writable,argv,cap,cgroup,build_state=None,products=None):
    limits(cap)
    need(profile['rootfs_readonly']is True and profile['network']=='none',"Qualified immutable tool image/no network")
    mounts=[]
    for dest,path in [('/source',source),('/inputs',inputs),('/state_ro',state),('/build_ro',build_state),('/products_ro',products)]:
        if path is not None:mounts.append({'destination':dest,'type':'bind','source':str(Path(path).absolute()),'options':['rbind','ro','nosuid','nodev']})
    for name in ('scratch','tmp','home','output','build'):
        p=Path(writable)/name;p.mkdir(parents=True,exist_ok=False)
        mounts.append({'destination':'/'+name,'type':'bind','source':str(p.absolute()),'options':['rbind','rw','nosuid','nodev']})
    mounts += [{'destination':'/proc','type':'proc','source':'proc','options':['nosuid','nodev','noexec']},
               {'destination':'/dev/null','type':'bind','source':'/dev/null','options':['bind','rw','nosuid','noexec']}]
    return {'ociVersion':'1.0.2','root':{'path':profile['rootfs'],'readonly':True},
            'hostname':'participant','process':{'terminal':False,'user':{'uid':0,'gid':0},'args':argv,
            'env':['HOME=/home','TMPDIR=/tmp','PATH='+profile['image_path'],'PYTHONDONTWRITEBYTECODE=1'],
            'cwd':'/scratch','noNewPrivileges':True,'capabilities':{'bounding':[],'effective':[],'inheritable':[],'permitted':[],'ambient':[]},
            'rlimits':[{'type':'RLIMIT_FSIZE','hard':cap['member_bytes'],'soft':cap['member_bytes']},
                       {'type':'RLIMIT_NOFILE','hard':256,'soft':256}]},'mounts':mounts,
            'linux':{'namespaces':[{'type':t}for t in ('pid','network','mount','ipc','uts','user','cgroup')],
            'uidMappings':profile['uid_mappings'],'gidMappings':profile['gid_mappings'],'cgroupsPath':cgroup,
            'resources':{'memory':{'limit':cap['memory_bytes']},'pids':{'limit':cap['processes']}},
            'seccomp':{'defaultAction':'SCMP_ACT_ALLOW','architectures':profile['seccomp_architectures'],
                       'syscalls':[{'names':DENIED_WRITE+['mount','umount2','unshare','setns','open_by_handle_at','name_to_handle_at','reboot','kexec_load','socket'],'action':'SCMP_ACT_ERRNO','errnoRet':1},
                                   {'names':['mmap','mmap2'],'action':'SCMP_ACT_ERRNO','errnoRet':1,
                                    'args':[{'index':3,'value':1,'valueTwo':1,'op':'SCMP_CMP_MASKED_EQ'}]}]}}}


def counters(cgroup):
    p=Path(cgroup)
    cpu=dict(line.split()for line in(p/'cpu.stat').read_text().splitlines())
    events=dict(line.split()for line in(p/'cgroup.events').read_text().splitlines())
    return {'cpu_usec':int(cpu['usage_usec']),'memory_bytes':int((p/'memory.peak').read_text()),
            'processes':int((p/'pids.peak').read_text()),'populated':int(events['populated'])}


def observer_source(cgroup):
    need('"'not in str(cgroup)and '\n'not in str(cgroup),"Selected cgroup path")
    predicate='/cgroup == cgroupid("'+str(cgroup)+'")/'
    return ('BEGIN { @bytes = 0; @creates = 0; printf("READY\\n"); }\n'
            'tracepoint:syscalls:sys_enter_write,tracepoint:syscalls:sys_enter_pwrite64 '
            +predicate+' { @bytes = sum(args->count); }\n'
            'tracepoint:syscalls:sys_enter_open,tracepoint:syscalls:sys_enter_openat '
            '/cgroup == cgroupid("'+str(cgroup)+'") && (args->flags & 64)/ { @creates = count(); }\n'
            'tracepoint:syscalls:sys_enter_creat,tracepoint:syscalls:sys_enter_mkdir,tracepoint:syscalls:sys_enter_mkdirat,'
            'tracepoint:syscalls:sys_enter_link,tracepoint:syscalls:sys_enter_linkat,'
            'tracepoint:syscalls:sys_enter_symlink,tracepoint:syscalls:sys_enter_symlinkat,'
            'tracepoint:syscalls:sys_enter_mknod,tracepoint:syscalls:sys_enter_mknodat '
            +predicate+' { @creates = count(); }\n'
            'interval:ms:25 { printf("W %llu\\nC %llu\\n", @bytes, @creates); }\n'
            'END { printf("FINAL %llu\\nFINALC %llu\\n", @bytes, @creates); clear(@bytes); clear(@creates); }\n')


def run(profile,job,request,source,inputs,state,root,cap,build_state=None,products=None,*,observation=None):
    """Full OCI lifetime with explicit original ownership, even without files."""
    from .observation import Observation
    o=Observation('isolated_process') if observation is None else observation
    if o.deadline is None:o.bind_deadline(cap['wall_ms'])
    c=Observation('command');c.bind_deadline(cap['wall_ms'],o);o.children['command']=c
    # These strong originals are installed before qualification/JSON/path work.
    o.record.update(schema='cogm-isolated-process-v1',job=job,profile=profile,
        original_worker_clock={'started':o.started,'deadline':o.deadline,'wall_limit_ms':o.wall_limit_ms},
        selected_limits=cap,original_command=None,returncode=None,natural_completion=False,
        failure=None,initial_cgroup=None,final_cgroup=None,all_descendants_absent=False,
        resources={k:None for k in cap},quota_observer_complete=False,
        final_sample_after_exit=False,output_tree=None,observer_streams={},observer_argv=None,
        observer_returncode=None,image_before=None,image_after=None,config_identity=None,
        request_identity=None,observer_launch_attempted=False,observer_pid=None)
    try:
        return _run(profile,job,request,source,inputs,state,root,cap,build_state,products,o,c)
    except BaseException as exc:
        o.fail(exc,'isolated_terminal');o.raise_failure()


def _run(profile,job,request,source,inputs,state,root,cap,build_state,products,o,c):
    from .contracts import require_qualification
    from .image import verify as verify_image
    from .observation import snapshot
    record=o.record;mon=monout=monerr=None;cgroup=None;writable=None;bundle=None
    cgroup_acquired=False
    initial=final=None;maximum_write=maximum_creates=0;observed_tree=None
    initial_known=False;final_known=False;tree_final=False;complete=False
    started=o.started;deadline=o.deadline
    root=Path(root).absolute();monargv=None

    def sample(last):
        nonlocal maximum_write,maximum_creates,final,observed_tree,final_known,tree_final
        need(mon.poll() is None,'Quota observer remains live')
        raw=read(root/'observer.stdout',cap['log_bytes']+1);o.streams['observer.stdout']=raw
        for line in raw.decode('utf-8','strict').splitlines():
            if line.startswith('W '):maximum_write=max(maximum_write,int(line[2:]))
            if line.startswith('C '):maximum_creates=max(maximum_creates,int(line[2:]))
        final=counters(cgroup);record['final_cgroup']=final;final_known=bool(last)
        observed_tree=tree(writable,total=cap['retained_bytes'],member=cap['member_bytes'],files=cap['files'])
        record['output_tree']=observed_tree;tree_final=bool(last)
        cpu=final['cpu_usec']-initial['cpu_usec']
        need(0<=cpu<=cap['cpu_usec'],'Final CPU resource allowance')
        need(maximum_write<=cap['cumulative_write_bytes'],'Original requested write-byte allowance')
        need(maximum_creates<=cap['files'],'Original cumulative file-creation allowance')
        need(final['memory_bytes']<=cap['memory_bytes'] and final['processes']<=cap['processes'],'Individual memory/process allowance')

    try:
        require_qualification(profile['qualification'],profile['selected_qualification'],
                              'reference_preparation' if job['arm']=='REFERENCE' else 'participant')
        for name in ('runc','bpftrace'):read(profile[name]['path'],profile[name]['bytes'],profile[name])
        record['image_before']=verify_image(profile)
        need(not root.exists(),'Fresh isolated original operation');root.mkdir(parents=True)
        cgroup=Path(profile['cgroup_parent'])/job['public_id'];need(not cgroup.exists(),'Fresh private cgroup');cgroup.mkdir()
        cgroup_acquired=True  # only the successful original mkdir grants cleanup ownership
        writable=root/'writable';writable.mkdir();bundle=root/'bundle';bundle.mkdir()
        need(request['input_bytes']<=cap['input_bytes'],'Complete original mounted input allowance')
        cfg=config(profile,source,inputs,state,writable,request['entrypoint'],cap,str(cgroup),build_state,products)
        record['config_identity']=dump(bundle/'config.json',cfg)
        (root/'writes.bt').write_text(observer_source(cgroup))
        record['request_identity']=identity(canonical(request))
        monout=open(root/'observer.stdout','xb');o.handles['observer.stdout']=monout
        monerr=open(root/'observer.stderr','xb');o.handles['observer.stderr']=monerr
        monargv=[profile['bpftrace']['path'],'-q',str(root/'writes.bt')];record['observer_argv']=monargv
        def observer_limits():
            import resource
            resource.setrlimit(resource.RLIMIT_FSIZE,(cap['log_bytes']+1,cap['log_bytes']+1))
        record['observer_launch_attempted']=True
        mon=subprocess.Popen(monargv,stdout=monout,stderr=monerr,start_new_session=True,preexec_fn=observer_limits)
        o.handles['observer']=mon;record['observer_pid']=mon.pid
        while True:
            raw=read(root/'observer.stdout',cap['log_bytes']+1);o.streams['observer.stdout']=raw
            if b'READY\n' in raw:break
            need(mon.poll() is None and time.monotonic()<deadline,'Original quota observer startup');time.sleep(.01)
        initial=counters(cgroup);record['initial_cgroup']=initial;initial_known=True
        argv=[profile['runc']['path'],'--root',str(root/'runtime-state'),'run','--bundle',str(bundle),job['public_id']]
        remaining=int((deadline-time.monotonic())*1000);need(remaining>0,'Full worker wall includes setup')
        # Join the actual mutable record BEFORE calling the original producer.
        record['original_command']=c.record
        command(argv,root,{'PATH':os.defpath},request,root/'command',wall_ms=remaining,
                stream_bytes=cap['log_bytes'],observer=sample,observation=c)
        need(c.record['natural_completion'] and c.record['failure'] is None,'Original runc natural completion')
        sample(True)
    except BaseException as exc:o.fail(exc,'isolated_execution')

    def close_cgroup():
        nonlocal final,final_known
        final_known=False  # a pre-cleanup sample cannot certify a failed final read
        (cgroup/'cgroup.kill').write_text('1')
        until=time.monotonic()+1
        while time.monotonic()<until:
            final=counters(cgroup);record['final_cgroup']=final
            if final['populated']==0:final_known=True;return
            time.sleep(.01)
        need(False,'Cgroup cleanup unconfirmed')
    if cgroup_acquired:o.attempt('cgroup_cleanup',close_cgroup)
    if mon is not None:
        def stop_observer():
            try:os.killpg(mon.pid,signal.SIGINT)
            except ProcessLookupError:pass
            try:mon.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:os.killpg(mon.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                mon.wait(timeout=1)
            record['observer_returncode']=mon.returncode
        o.attempt('observer_cleanup',stop_observer)
    for name,handle in [('observer.stdout',monout),('observer.stderr',monerr)]:
        if handle is not None:o.attempt(name+'_close',handle.close)
    # Each final sample retains its returned object before parsing/validation.
    for name in ('observer.stdout','observer.stderr'):
        def capture(name=name):
            b=read(root/name,cap['log_bytes']+1);o.streams[name]=b
            record['observer_streams'][name]=identity(b)
        if (root/name).exists():o.attempt('final_'+name,capture)
    def observer_final():
        nonlocal complete,maximum_write,maximum_creates
        text=o.streams.get('observer.stdout',b'').decode('utf-8','strict').splitlines()
        last=[x for x in text if x.startswith('FINAL ')];creates=[x for x in text if x.startswith('FINALC ')]
        need(mon is not None and record['observer_returncode']==0 and len(last)==len(creates)==1,'Original write observer complete')
        w=int(last[0].split()[1]);f=int(creates[0].split()[1]);need(w>=maximum_write and f>=maximum_creates,'Monotonic final quota counters')
        maximum_write=w;maximum_creates=f;complete=True
    o.attempt('observer_final',observer_final)
    if writable is not None:
        def final_tree():
            nonlocal observed_tree,tree_final
            observed_tree=tree(writable,total=cap['retained_bytes'],member=cap['member_bytes'],files=cap['files'])
            record['output_tree']=observed_tree;tree_final=final_known
        o.attempt('final_output_tree',final_tree)
    record['image_after']=o.attempt('image_after',lambda:verify_image(profile))
    record['returncode']=c.record.get('returncode')
    record['all_descendants_absent']=final_known and final is not None and final['populated']==0
    record['quota_observer_complete']=complete
    record['final_sample_after_exit']=final_known and c.record.get('returncode') is not None
    cpu=None if initial is None or final is None else final['cpu_usec']-initial['cpu_usec']
    usage={'wall_ms':int((time.monotonic()-started)*1000),'cpu_usec':cpu,
        'memory_bytes':None if final is None else final['memory_bytes'],
        'processes':None if final is None else final['processes'],
        'cumulative_write_bytes':maximum_write if initial_known else None,
        'retained_bytes':None if observed_tree is None else observed_tree['bytes'],
        'files':None if observed_tree is None else max(maximum_creates,len(observed_tree['files'])),
        'member_bytes':None if observed_tree is None else max([0]+[x['bytes']for x in observed_tree['files']]),
        'input_bytes':request.get('input_bytes'),
        'output_bytes':None if observed_tree is None else sum(x['bytes']for x in observed_tree['files']if x['path'].startswith('output/')),
        'log_bytes':sum(len(v)for v in o.streams.values())+sum(len(v)for v in c.streams.values())}
    record['resources']=usage
    record['resource_completeness']={k:False for k in usage}
    for k in ('cpu_usec','memory_bytes','processes'):record['resource_completeness'][k]=initial_known and final_known
    for k in ('retained_bytes','member_bytes','output_bytes'):record['resource_completeness'][k]=tree_final
    record['resource_completeness'].update(wall_ms=True,input_bytes=usage['input_bytes'] is not None,
        cumulative_write_bytes=complete,files=complete and tree_final,
        log_bytes=complete and len(record['observer_streams'])==2 and all(c.record.get('pipe_eof',{}).values()) and bool(c.record.get('pipe_eof')))
    record['resource_semantics']='null is unavailable; incomplete nonnull values are observed lower bounds, never zero-cost certificates'
    def final_admission():
        violations=[k for k,v in usage.items()if v is not None and (type(v)is not int or v<0 or v>cap[k])]
        record['resource_violations']=violations
        need(not violations,'ResourceLimit: final original counters '+','.join(violations))
        need(all(record['resource_completeness'].values()),'Complete final accounting required')
        need(record['all_descendants_absent'],'Original descendant cleanup required')
        need(record['image_before']==record['image_after'],'Original immutable image after lifetime')
    o.attempt('final_resource_admission',final_admission)
    record['failure']=o.failure();record['secondary_failures']=o.secondary()
    record['natural_completion']=bool(c.record.get('natural_completion') and o.first_error is None)
    record['publication']=o.publication_summary()
    o.completed=record
    o.publish('PROCESS.json',record,lambda:dump(root/'PROCESS.json',record))
    # The publication itself may fail. The carrier remains the authority; a
    # serialized preceding record never retroactively certifies that write.
    o.attempt('process_publication_complete',lambda:o.check_deadline('process_publication_complete'))
    if o.first_error is not None:o.raise_failure()
    eligible(record,cap)
    return record
