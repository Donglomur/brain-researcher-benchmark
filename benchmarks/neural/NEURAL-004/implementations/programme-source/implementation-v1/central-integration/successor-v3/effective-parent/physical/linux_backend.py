"""Undeployed Linux fixed-mount backend, never exercised by source controls.

The selected runtime root, binaries, original materials, delegated cgroup and
quota-backed output parent need independent deployment admission. cgroup facts
do not certify total logical I/O or historical authoring. Those remain unknown.
"""
import hashlib
import os
import selectors
import stat
import subprocess
import time
from pathlib import Path
from .wire import need, integer, token, relative, check_pin, body_pin, pin, encode, decode, Cleanup
from .store import read_exact, NOFOLLOW, DIRECTORY

class MaterialRepository:
    def __init__(self, root, catalog, ledger):
        self.root=Path(root);self.catalog=catalog;self.ledger=ledger
        self.fd=os.open(root,os.O_RDONLY|DIRECTORY|NOFOLLOW)

    def open(self, descriptor):
        name=relative(descriptor['path']);expected={k:descriptor[k] for k in ('bytes','sha256')};check_pin(expected)
        record=self.catalog[name]
        need(set(record)=={'relative_path','pin','immutable_admission'} and record['pin']==expected,'admitted complete material identity')
        check_pin(record['immutable_admission']);parts=relative(record['relative_path']).split('/')
        with Cleanup(self.ledger) as cleanup:
            directory=os.dup(self.fd)
            owner=cleanup.defer('close material directory',lambda fd=directory:os.close(fd))
            for part in parts[:-1]:
                child=os.open(part,os.O_RDONLY|DIRECTORY|NOFOLLOW,dir_fd=directory)
                child_owner=cleanup.defer('close material child directory',lambda fd=child:os.close(fd))
                cleanup.close_now(owner);directory=child;owner=child_owner
            self.ledger.reserve({'read_bytes':expected['bytes']+1},'full material identity')
            fd=os.open(parts[-1],os.O_RDONLY|NOFOLLOW,dir_fd=directory)
            file_owner=cleanup.defer('close untransferred material',lambda:os.close(fd))
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'ordinary material extent')
            digest=hashlib.sha256();total=0
            with self.ledger.live(65536,'material hash chunk'):
                while True:
                    self.ledger.tick();block=os.read(fd,65536)
                    if not block:break
                    total+=len(block);need(total<=expected['bytes'],'material growth');digest.update(block)
            after=os.fstat(fd)
            need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                 (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'material stable during hash')
            need(total==expected['bytes'] and digest.hexdigest()==expected['sha256'],'full material digest')
            os.lseek(fd,0,os.SEEK_SET)
            # Do not transfer the file if the directory close fails; it remains
            # owned and receives its own cleanup attempt on that failure.
            cleanup.close_now(owner);cleanup.forget(file_owner);return fd

def native_material_mounts(view):
    required={'common','original_inputs','native_compatibility','original_native_target_names','processed_epochs',
              'author_code','oracle_capture_visible','other_context_history_visible','query_targets_visible'}
    need(type(view) is dict and set(view)==required,'exact native view schema')
    need(all(view[k] is False for k in ('oracle_capture_visible','other_context_history_visible','query_targets_visible')),
         'native view excludes protected cross-context material')
    mounts={}
    def add(target,descriptor):
        need(target.startswith('/') and '..' not in target.replace('\\','/').split('/') and '\n' not in target and '\r' not in target,'fixed safe mount target')
        old=mounts.setdefault(target,descriptor)
        need({k:old[k] for k in ('path','bytes','sha256')}=={k:descriptor[k] for k in ('path','bytes','sha256')},'no contradictory mount')
    for descriptor in view['common']:add('/common/'+relative(descriptor['path']),descriptor)
    by_target={}
    need(set(view['original_inputs'])==set(view['original_native_target_names']),'complete original target mapping')
    for key,descriptor in view['original_inputs'].items():
        target=relative(view['original_native_target_names'][key]);add('/data/'+target,descriptor);by_target[target]=descriptor
    if view['processed_epochs'] is not None:
        for descriptor in view['processed_epochs']['members']:
            target=relative(descriptor['path']);add('/data/'+target,descriptor);by_target[target]=descriptor
    for descriptor in view['author_code']:
        add('/source/author/'+relative(descriptor['author_relative_path']),descriptor)
    for alias in view['native_compatibility']['aliases']:
        canonical=relative(alias['canonical_target']);need(canonical in by_target,'alias original target admitted')
        literal=alias['literal'];need(type(literal) is str and literal and not literal.startswith('/'),'exact original literal alias')
        add('/data/'+literal,by_target[canonical])
    return mounts

class LinuxBackend:
    """Real namespace/cgroup source implementation with explicit unknowns.

    Only a separately admitted supervisor constructs this class. The helper
    does not claim that an arbitrary supplied manifest authenticates itself.
    """
    def __init__(self, store, ledger, admitted_backend):
        need(os.name=='posix' and Path('/proc/self').is_dir(),'Linux backend unavailable')
        required={'schema','runtime_root','runtime_admission','bubblewrap','bubblewrap_pin','python','python_pin',
            'gate_source','gate_pin','cgroup_parent','cgroup_admission','output_parent','output_quota_admission',
            'material_root','material_catalog','memory_max','pids_max','cpu_max','max_output_bytes',
            'max_output_files','stdout_cap','stderr_cap','environment'}
        need(set(admitted_backend)==required and admitted_backend['schema']=='ach_linux_fixed_mount_backend_v1','full named backend profile')
        self.store=store;self.ledger=ledger;self.cfg=admitted_backend;self.jobs={}
        for key in ('runtime_admission','cgroup_admission','output_quota_admission'):check_pin(admitted_backend[key])
        for key in ('memory_max','pids_max','max_output_bytes','max_output_files','stdout_cap','stderr_cap'):integer(admitted_backend[key],1)
        for name,pinkey in (('bubblewrap','bubblewrap_pin'),('python','python_pin'),('gate_source','gate_pin')):
            read_exact(admitted_backend[name],admitted_backend[pinkey],ledger,admitted_backend[pinkey]['bytes'])
        need(type(admitted_backend['environment']) is dict and all(type(k) is str and type(v) is str for k,v in admitted_backend['environment'].items()),'fixed environment')
        need(type(admitted_backend['cpu_max']) is str and len(admitted_backend['cpu_max'].split())==2,'fixed cpu quota/period')
        self.materials=MaterialRepository(admitted_backend['material_root'],admitted_backend['material_catalog'],ledger)

    def read_committed_program(self, descriptor):
        with Cleanup(self.ledger) as cleanup:
            fd=self.materials.open(descriptor)
            cleanup.defer('close committed program',lambda:os.close(fd))
            size=descriptor['bytes'];self.ledger.reserve({'read_bytes':size+1},'committed program read')
            with self.ledger.live(2*(size+1),'committed source copies'):
                out=bytearray()
                while len(out)<=size:
                    block=os.read(fd,min(65536,size+1-len(out)))
                    if not block:break
                    out.extend(block)
                raw=bytes(out);need(body_pin(raw)=={k:descriptor[k] for k in ('bytes','sha256')},'committed program unchanged');return raw

    def stage_exact(self, context, files, view, binding, origin, deadline):
        token(context);need(not context.startswith('_observation_') and context not in self.jobs,'fresh Linux job');need(origin==self.ledger.origin and deadline==self.ledger.scientific,'original job clock')
        staged={}
        for name,raw in files.items():
            need(type(name) is str and name.startswith(('/request/','/source/','/program/')),'fixed source mount root')
            staged[relative(name[1:])]=raw
        material=native_material_mounts(view) if 'original_inputs' in view else self._improvement_mounts(view)
        self.jobs[context]={'context':context,'binding':binding,'phase':'staging','launched':False,
                           'observer_closed':False,'result':None,'unknown':[]}
        self.store.stage(context,staged);self.store.seal(context)
        output=Path(self.cfg['output_parent'])/context;cg=Path(self.cfg['cgroup_parent'])/context
        self.ledger.reserve({'write_bytes':12288,'retained_bytes':12288},'owned output/cgroup/observation metadata')
        output.mkdir(mode=0o700,parents=False,exist_ok=False);cg.mkdir(mode=0o700,parents=False,exist_ok=False)
        observation=self.store.root/('_observation_'+context);observation.mkdir(mode=0o700,parents=False,exist_ok=False)
        cgstat=cg.stat();outputstat=output.stat()
        self.jobs[context]={'context':context,'binding':binding,'material_mounts':material,'view_pin':pin(view),
            'source_files':self.store.contexts[context],'output':str(output),'cgroup':str(cg),
            'observation':str(observation),
            'index_name':'CAPTURE_INDEX.json' if 'original_inputs' in view else 'RESULT_INDEX.json',
            'cgroup_identity':[cgstat.st_dev,cgstat.st_ino],'output_identity':[outputstat.st_dev,outputstat.st_ino],
            'launched':False,'observer_closed':False,'result':None,'unknown':[]}
        self.jobs[context]['phase']='staged'
        stage_token=pin({'context':context,'binding':binding,'view':view,'sources':self.store.contexts[context]})
        self.jobs[context]['token']=stage_token;self.ledger.tick();return stage_token

    def _improvement_mounts(self, view):
        need(type(view) is dict and set(view)=={'schema','materials','exposure_admission','forbidden_feedback'} and
             view['schema']=='ach_minimized_process_view_v1','explicit improvement view')
        check_pin(view['exposure_admission'])
        need(view['forbidden_feedback']==['native','reference_results','outer_labels','other_contexts'], 'protected feedback exclusions')
        result={}
        for target,descriptor in view['materials'].items():
            need(target.startswith(('/training/','/query/','/sealed/','/common/','/source/author/')),'fixed minimal material roots')
            relative(target[1:]);result[target]=descriptor
        return result

    def _owned_cgroup(self, job):
        p=Path(job['cgroup']);s=p.stat();need([s.st_dev,s.st_ino]==job['cgroup_identity'],'same owned cgroup inode');return p

    def _write_control(self, path, text, *, cutoff='scientific'):
        raw=text.encode('ascii');self.ledger.reserve({'write_bytes':len(raw)},'cgroup control',cutoff=cutoff)
        with Cleanup(self.ledger) as cleanup:
            fd=os.open(path,os.O_WRONLY|NOFOLLOW)
            cleanup.defer('close cgroup control',lambda:os.close(fd))
            need(os.write(fd,raw)==len(raw),'complete cgroup control write')

    def launch_exact(self, stage_token, argv, binding, origin, deadline):
        matches=[j for j in self.jobs.values() if j['token']==stage_token]
        need(len(matches)==1,'owned unique stage token');job=matches[0]
        need(not job['launched'] and job['binding']==binding and origin==self.ledger.origin and deadline==self.ledger.scientific,'fresh bound job launch')
        need(type(argv) is list and argv and all(type(x) is str and x and '\0' not in x for x in argv),'concrete worker command')
        self.store.seal(job['context']);self.ledger.tick();cg=self._owned_cgroup(job)
        for name,text in (('memory.max',str(self.cfg['memory_max'])),('pids.max',str(self.cfg['pids_max'])),('cpu.max',self.cfg['cpu_max'])):
            self._write_control(cg/name,text)
        command=[self.cfg['bubblewrap'],'--unshare-all','--die-with-parent','--new-session','--clearenv',
                 '--ro-bind',self.cfg['runtime_root'],'/','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
        for k,v in sorted(self.cfg['environment'].items()):command+=['--setenv',k,v]
        source_root=self.store.context_path(job['context'])
        for top in sorted({name.split('/')[0] for name in job['source_files']}):command+=['--ro-bind',str(source_root/top),'/'+top]
        descriptors=[];fds=[]
        closing=Cleanup(self.ledger,job);primary=None
        try:
            for target,descriptor in sorted(job['material_mounts'].items()):
                fd=self.materials.open(descriptor);fds.append(fd);closing.defer('close launch material',lambda fd=fd:os.close(fd));command+=['--ro-bind','/proc/self/fd/'+str(fd),target]
                descriptors.append({'target':target,'source':descriptor})
            command+=['--bind',job['output'],'/output','--chdir','/output','--']+argv
            gate=[self.cfg['python'],'-I','-S','-B',self.cfg['gate_source']]+command
            self.ledger.reserve({'processes':1},'Linux process launch');self.ledger.tick()
            process=subprocess.Popen(gate,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env={},start_new_session=True,close_fds=True,pass_fds=tuple(fds))
            for name in ('stdin','stdout','stderr'):
                stream=getattr(process,name)
                if stream is not None:
                    closing.defer('close launch '+name,lambda name=name:self._close_stream(job,name))
            job['launched']=True;job['process']=process;job['argv']=argv;job['command_pin']=pin(gate);job['attached']=False
            job['phase']='launched'
            # Only the tiny gate is running. It cannot exec the namespace worker
            # before this owned PID is attached to the delegated cgroup.
            self._write_control(cg/'cgroup.procs',str(process.pid));job['attached']=True;self.ledger.tick()
            process.stdin.write(b'G');process.stdin.flush();self._close_stream(job,'stdin')
            result=self._capture(job,origin,deadline);job['result']=result
            job['phase']='producer_returned'
            need(result['exit_code']==0 and result['natural_exit'] and result['stream_eof'],'complete natural-zero Linux producer')
            while self.cgroup_population(job):self.ledger.tick();time.sleep(.02)
            inventory=self.inventory(job);index=next((x for x in inventory if x['path']==job['index_name']),None)
            need(index is not None,'declared native or improvement result index')
            job['index']=index
            return {'index':index}
        except BaseException as error:
            primary=error
            job['phase']='failed';job['failure_type']=type(error).__name__
            self.ledger.fail('Linux launch',error)
            process=job.get('process')
            if process is not None:
                # cgroup.kill targets the still-owned group, not a potentially
                # reused reaped process-group ID. Forced termination is failure.
                try:
                    if job.get('attached') and self.cgroup_facts(job)['populated']:
                        self._write_control(self._owned_cgroup(job)/'cgroup.kill','1',cutoff='closeout');job['forced_stop']=True
                    elif process.poll() is None:
                        process.kill();job['forced_stop']=True
                    while process.poll() is None:
                        self.ledger.tick('closeout');time.sleep(.005)
                except BaseException as stop_error:
                    def failed_stop(error=stop_error):raise error
                    failed=Cleanup(self.ledger,job);failed.defer('owned cgroup stop',failed_stop);failed.run(error)
            if job.get('result') is not None:
                job['result']['forced_stop']=job.get('forced_stop',False)
                job['result']['natural_exit']=process is not None and process.returncode is not None and not job.get('forced_stop',False)
                job['result']['exit_code']=None if process is None else process.returncode
            elif process is not None:
                job['unknown'].append('raw startup/capture streams unavailable before capture initialization')
            raise
        finally:
            closing.run(primary)

    def cgroup_facts(self, job):
        root=self._owned_cgroup(job);values={}
        for name in ('cgroup.events','memory.peak','cpu.stat','io.stat','pids.current'):
            self.ledger.reserve({'read_bytes':65537},'bounded cgroup evidence',cutoff='closeout')
            with Cleanup(self.ledger,job) as cleanup:
                fd=os.open(root/name,os.O_RDONLY|NOFOLLOW)
                cleanup.defer('close cgroup evidence',lambda:os.close(fd))
                raw=os.read(fd,65537);need(len(raw)<=65536,'cgroup evidence cap');values[name]=raw.decode('ascii')
        events=dict(line.split() for line in values['cgroup.events'].splitlines())
        need(events.get('populated') in ('0','1'),'actual cgroup population')
        return {'populated':events['populated']=='1','raw':values,'physical_accounting_complete':False}

    def cgroup_population(self, job):
        self.ledger.reserve({'read_bytes':1025},'cgroup population observation',cutoff='closeout')
        with Cleanup(self.ledger,job) as cleanup:
            fd=os.open(self._owned_cgroup(job)/'cgroup.events',os.O_RDONLY|NOFOLLOW)
            cleanup.defer('close cgroup population',lambda:os.close(fd))
            raw=os.read(fd,1025);need(len(raw)<=1024,'bounded cgroup events')
        fields=dict(line.split() for line in raw.decode('ascii').splitlines())
        need(fields.get('populated') in ('0','1'),'real cgroup population');return fields['populated']=='1'

    def _close_stream(self, job, name):
        attempts=job.setdefault('stream_close_attempts',[])
        if name in attempts:return
        attempts.append(name)  # Never retry an uncertain close against a reused FD.
        stream=getattr(job['process'],name)
        if stream is not None and not stream.closed:stream.close()

    def _capture(self, job, origin, deadline):
        process=job['process'];caps={'stdout':self.cfg['stdout_cap'],'stderr':self.cfg['stderr_cap']};buffers={k:bytearray() for k in caps}
        eof=set()
        with Cleanup(self.ledger,job) as cleanup:
            # LIFO order: selector, both streams, raw retention. A failing close
            # cannot suppress the other stream or durable retention attempts.
            cleanup.defer('retain both raw streams',lambda:self._retain_streams(job))
            for name in reversed(tuple(caps)):
                cleanup.defer('close captured '+name,lambda name=name:self._close_stream(job,name))
            try:
                selector=selectors.DefaultSelector()
                cleanup.defer('close capture selector',selector.close)
                with self.ledger.live(2*(sum(caps.values())+2),'Linux stream copies'):
                    for name in caps:
                        stream=getattr(process,name);os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
                    while selector.get_map() or process.poll() is None:
                        self.ledger.tick()
                        for key,_ in selector.select(.02):
                            name=key.data;left=caps[name]-len(buffers[name]);extent=min(65536,left+1)
                            self.ledger.reserve({'read_bytes':extent,'retained_bytes':extent},'attempted Linux stream read')
                            block=os.read(key.fileobj.fileno(),extent)
                            if not block:selector.unregister(key.fileobj);eof.add(name);continue
                            buffers[name].extend(block);need(len(block)<=left,'Linux stream cap')
                    code=process.wait();self.ledger.tick()
                    result={'exit_code':code,'natural_exit':True,'stream_eof':eof==set(caps),'finished_ns':self.ledger.clock(),
                            'stdout':bytes(buffers['stdout']),'stderr':bytes(buffers['stderr']),'forced_stop':False}
                    job['result']=result;return result
            except BaseException as error:
                job['result']={'exit_code':process.poll(),'natural_exit':False,'stream_eof':eof==set(caps),
                    'finished_ns':self.ledger.clock(),'stdout':bytes(buffers['stdout']),'stderr':bytes(buffers['stderr']),
                    'forced_stop':job.get('forced_stop',False),'capture_failure':type(error).__name__}
                raise

    def _retain_streams(self, job):
        result=job['result'];need(result is not None,'actual stream record')
        inventory=[];root=Path(job['observation']);job['stream_inventory']=inventory
        def retain(name):
            raw=result[name];self.ledger.reserve({'write_bytes':len(raw)+4096,'retained_bytes':len(raw)+4096},
                'durable actual '+name,cutoff='closeout')
            with Cleanup(self.ledger,job) as cleanup:
                path=root/(name+'.log');fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|NOFOLLOW,0o400)
                cleanup.defer('close retained '+name,lambda:os.close(fd))
                view=memoryview(raw)
                while view:
                    n=os.write(fd,view);need(n>0,'complete raw stream write');view=view[n:]
                os.fsync(fd)
            inventory.append({'path':name+'.log',**body_pin(raw)})
        def sync_directory():
            with Cleanup(self.ledger,job) as cleanup:
                fd=os.open(root,os.O_RDONLY|DIRECTORY|NOFOLLOW)
                cleanup.defer('close retained-stream directory',lambda:os.close(fd));os.fsync(fd)
        try:
            with Cleanup(self.ledger,job) as cleanup:
                cleanup.defer('sync retained-stream directory',sync_directory)
                cleanup.defer('retain stderr',lambda:retain('stderr'))
                cleanup.defer('retain stdout',lambda:retain('stdout'))
        except BaseException:
            job['unknown'].append('durable raw stream retention failed');raise

    def inventory(self, job):
        root=Path(job['output']);s=root.stat();need([s.st_dev,s.st_ino]==job['output_identity'],'owned output directory')
        result=[];total=0
        for directory,dirs,files in os.walk(root,followlinks=False):
            need(all(not (Path(directory)/name).is_symlink() for name in dirs),'no output directory symlinks')
            for name in sorted(files):
                path=Path(directory)/name;s=path.lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary single-link output')
                total+=s.st_size;need(total<=self.cfg['max_output_bytes'] and len(result)<self.cfg['max_output_files'],'complete output extents')
                self.ledger.reserve({'read_bytes':s.st_size+1},'full output inventory hash',cutoff='closeout')
                with Cleanup(self.ledger,job) as cleanup:
                    fd=os.open(path,os.O_RDONLY|NOFOLLOW);digest=hashlib.sha256();n=0
                    cleanup.defer('close inventory file',lambda:os.close(fd))
                    while True:
                        self.ledger.tick('closeout');block=os.read(fd,65536)
                        if not block:break
                        n+=len(block);need(n<=s.st_size,'closed output grew');digest.update(block)
                    after=os.fstat(fd);need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
                        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'output unchanged while hashing')
                need(n==s.st_size,'complete closed output');result.append({'path':path.relative_to(root).as_posix(),'bytes':n,'sha256':digest.hexdigest()})
        return sorted(result,key=lambda x:x['path'])

    def read_closed_output(self, context, name, offset, count):
        job=self.jobs[context];need(job['observer_closed'],'independent observer closure required before output read')
        relative(name);integer(offset);integer(count);matches=[d for d in job['inventory'] if d['path']==name]
        need(len(matches)==1,'closed exact inventory member');descriptor=matches[0]
        need(offset<=descriptor['bytes'] and count<=descriptor['bytes']-offset+1,'output interval with one EOF sentinel')
        available=min(count,descriptor['bytes']-offset)
        self.ledger.reserve({'read_bytes':descriptor['bytes']+count+1},'closed output full identity and bounded interval')
        with Cleanup(self.ledger,job) as cleanup:
            parent=os.open(job['output'],os.O_RDONLY|DIRECTORY|NOFOLLOW)
            owner=cleanup.defer('close output parent',lambda fd=parent:os.close(fd))
            rootstat=os.fstat(parent);need([rootstat.st_dev,rootstat.st_ino]==job['output_identity'],'same closed output root')
            parts=name.split('/')
            for component in parts[:-1]:
                child=os.open(component,os.O_RDONLY|DIRECTORY|NOFOLLOW,dir_fd=parent)
                child_owner=cleanup.defer('close output child directory',lambda fd=child:os.close(fd))
                cleanup.close_now(owner);parent=child;owner=child_owner
            fd=os.open(parts[-1],os.O_RDONLY|NOFOLLOW,dir_fd=parent)
            cleanup.defer('close output file',lambda:os.close(fd));before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==descriptor['bytes'],'closed output ordinary extent')
            with self.ledger.live(65536+2*count,'closed output internal chunk and interval'):
                digest=hashlib.sha256();total=0
                while True:
                    self.ledger.tick();block=os.read(fd,65536)
                    if not block:break
                    total+=len(block);need(total<=descriptor['bytes'],'closed output growth');digest.update(block)
                need(total==descriptor['bytes'] and digest.hexdigest()==descriptor['sha256'],'full immutable output identity')
                os.lseek(fd,offset,os.SEEK_SET);chunks=[];left=available
                while left:
                    block=os.read(fd,min(left,65536));need(block,'complete bounded output interval');chunks.append(block);left-=len(block)
                after=os.fstat(fd);need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'closed output stable through read')
                return b''.join(chunks)
