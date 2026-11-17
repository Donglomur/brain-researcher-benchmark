"""Concrete Linux cgroup-v2/bubblewrap caller; qualified deployment is required.

Qualification must establish immutable source/input mounts, an exclusive
quota-backed workspace, and this exact native backend. A metadata receipt is
not proof of those physical properties. No subprocess runs on import.
"""
import os,selectors,signal,stat,subprocess,time,uuid,hashlib
from pathlib import Path
from .core import need,absolute,capture,descriptor,save,canonical,byte_pin
from .terminal import TerminalCustody,resource_verdict

def tree(root,cap,count_cap,budget=None):
    root=absolute(str(Path(root).absolute()));need(root.is_dir(),'directory required')
    rows=[];total=0
    for p in sorted(root.rglob('*')):
        if budget:budget.tick()
        need(not p.is_symlink(),'tree symlink')
        if p.is_dir():continue
        need(p.is_file() and len(rows)<count_cap,'regular finite member count')
        row=descriptor(p,cap-total,budget);total+=row['bytes'];need(total<=cap,'whole tree capacity')
        rows.append({'relative':str(p.relative_to(root)),**row})
    return {'root':str(root),'members':rows,'bytes':total}
def check_tree(record,budget=None):
    need(tree(record['root'],record['bytes'],len(record['members'])+1,budget)==record,'immutable tree changed')
def cpu_ns(cgroup):
    fields=dict(line.split() for line in (cgroup/'cpu.stat').read_text().splitlines())
    return int(fields['usage_usec'])*1000

class Dispatcher:
    def __init__(self,profile,budget):
        self.profile=profile;self.budget=budget;self.operations=[]
        need(os.name=='posix' and Path('/sys/fs/cgroup/cgroup.controllers').exists(),'qualified Linux cgroup-v2 only')
        for k in ('memory_bytes','pids','wall_ns','cleanup_ns','cpu_ns','stream_bytes','input_bytes','output_bytes','output_members','poll_ns','terminal_bytes','terminal_ns'):
            need(type(profile.get(k))is int and profile[k]>0,'finite complete runtime limits')
        need(profile['poll_ns']<=100000000,'watchdog at most100ms')
        capture(profile['bwrap']['path'],profile['bwrap']['bytes'],profile['bwrap'],budget)
        check_tree(profile['rootfs'],budget)
        self.parent=absolute(profile['cgroup_parent'])
        need(self.parent.is_dir(),'qualified delegated parent')
        # External source-bound qualification authenticates both quota and immutability.
        for key in ('quota_evidence','mount_evidence'):
            row=profile[key];capture(row['path'],row['bytes'],row,budget)

    def run(self,argv,inputs,source,output,stage,model=None,environment=None):
        cfg=self.profile;b=self.budget;t0=time.monotonic_ns()
        run_end=min(b.deadline,t0+cfg['wall_ns']);cleanup_end=min(b.deadline,t0+cfg['wall_ns']+cfg['cleanup_ns'])
        b.reserve(process_starts=1,cpu_ns=cfg['cpu_ns'],read=2*(cfg['stream_bytes']+1),
                  written=2*cfg['stream_bytes']+cfg['output_bytes'],hashed=2*cfg['stream_bytes'])
        need(stage in ('prepare','feature','train','query','provider'),'fixed operation kind')
        need(type(argv)is list and argv and all(type(x)is str and '\0' not in x for x in argv),'literal argv')
        out=absolute(str(Path(output).absolute()));out.mkdir(mode=0o700)
        captures=out/'capture';captures.mkdir(mode=0o700);product=out/'product';product.mkdir(mode=0o700)
        terminal=TerminalCustody(captures,{'OUTCOME.json':cfg['terminal_bytes']},b,
            min(b.evidence_deadline,t0+cfg['wall_ns']+cfg['cleanup_ns']+cfg['terminal_ns']))
        source_rec=tree(source,cfg['input_bytes'],10000,b)
        input_recs=[tree(x,cfg['input_bytes'],10000,b) for x in inputs]
        model_rec=tree(model,cfg['input_bytes'],10000,b) if model else None
        cg=self.parent/('n056-'+uuid.uuid4().hex);cg.mkdir();inode=cg.stat().st_ino
        for name,value in [('memory.max',cfg['memory_bytes']),('memory.swap.max',0),
                           ('pids.max',cfg['pids']),('cpu.max',cfg['cpu_max'])]:
            (cg/name).write_text(str(value))
        cmd=[cfg['bwrap']['path'],'--unshare-all','--die-with-parent','--new-session','--clearenv',
             '--ro-bind',cfg['rootfs']['root'],'/','--proc','/proc','--dev','/dev',
             '--tmpfs','/tmp','--dir','/input','--ro-bind',str(Path(source).absolute()),'/source',
             '--bind',str(product),'/output','--chdir','/output']
        for i,p in enumerate(inputs):cmd+=['--ro-bind',str(Path(p).absolute()),'/input/'+str(i)]
        if model:cmd+=['--ro-bind',str(Path(model).absolute()),'/model']
        env={'PATH':'/usr/bin:/bin','HOME':'/tmp','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1',
             'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
        need(environment is None or set(environment)=={'NEURAL056_STAGE'},'fixed benign environment only')
        env.update(environment or {})
        for k,v in sorted(env.items()):cmd+=['--setenv',k,v]
        cmd+=['--',*argv]
        launch=save(captures/'LAUNCH.json',{'argv':cmd,'stage':stage,'started_ns':t0,
          'run_deadline_ns':run_end,'cleanup_deadline_ns':cleanup_end,
          'source':source_rec,'inputs':input_recs,'model':model_rec,
          'ownership':{'path':str(cg),'inode':inode}},b)
        process=None;failure=None;forced=False;returncode=None
        eof={'stdout':False,'stderr':False};counts={'stdout':0,'stderr':0}
        hashes={name:hashlib.sha256() for name in eof}
        fds={};streams={};selector=selectors.DefaultSelector();persistence={}
        def own():return cg.exists() and cg.stat().st_ino==inode
        def kill():
            nonlocal forced
            need(own(),'cgroup ownership lost; never kill a reused identity')
            (cg/'cgroup.kill').write_text('1');forced=True
        def join(): (cg/'cgroup.procs').write_text(str(os.getpid()))
        try:
            need(time.monotonic_ns()<run_end,'startup consumed original run interval')
            for name in eof:fds[name]=os.open(captures/(name+'.txt'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                close_fds=True,start_new_session=True,preexec_fn=join,env={})
            b.observe(process_starts=1)
            for name,s in [('stdout',process.stdout),('stderr',process.stderr)]:
                streams[name]=s;os.set_blocking(s.fileno(),False);selector.register(s,selectors.EVENT_READ,name)
            while selector.get_map() or process.poll() is None:
                now=time.monotonic_ns()
                if not forced and (now>=run_end or cpu_ns(cg)>cfg['cpu_ns']):
                    failure='process deadline/CPU limit';kill()
                if now>=cleanup_end:
                    failure='original cleanup deadline';break
                for key,_ in selector.select(min(cfg['poll_ns']/1e9,max(0,(cleanup_end-now)/1e9))):
                    name=key.data;room=cfg['stream_bytes']-counts[name]
                    chunk=os.read(key.fileobj.fileno(),min(65536,room+1))
                    b.observe(read=len(chunk))
                    if not chunk:eof[name]=True;selector.unregister(key.fileobj);key.fileobj.close();continue
                    accepted=chunk[:room];off=0
                    while off<len(accepted):
                        need(time.monotonic_ns()<cleanup_end,'original stream-persistence deadline')
                        n=os.write(fds[name],accepted[off:]);need(n>0,'stream short write')
                        hashes[name].update(accepted[off:off+n]);off+=n;counts[name]+=n
                        b.record_known(written=n,hashed=n)
                    if len(chunk)>room:
                        if not forced:failure='stream cap; exact prefix retained';kill()
                        selector.unregister(key.fileobj);key.fileobj.close()
                # The externally qualified quota is the physical bound.
                # This source check separately rejects malformed/oversized products.
                if not forced:
                    rows=list(product.rglob('*'))
                    if (len(rows)>cfg['output_members'] or any(p.is_symlink() for p in rows)
                        or sum(p.stat().st_size for p in rows if p.is_file())>cfg['output_bytes']):
                        failure='product extent';kill()
            if process.poll() is None and own():kill()
            left=(cleanup_end-time.monotonic_ns())/1e9
            if process.poll() is None and left>0:
                try:returncode=process.wait(timeout=left)
                except subprocess.TimeoutExpired:failure='unobserved root completion'
            else:returncode=process.poll()
        except Exception as exc:
            failure=type(exc).__name__+': '+str(exc)
            if process is not None and own():
                try:kill()
                except Exception as cleanup_exc:persistence['kill']=type(cleanup_exc).__name__
        finally:
            # Attempt each stream independently; one failure never suppresses the other.
            for name,fd in fds.items():
                try:
                    need(time.monotonic_ns()<cleanup_end,'late stream flush')
                    os.fsync(fd);persistence[name]='flushed'
                except Exception as exc:persistence[name]='failed:'+type(exc).__name__;failure=failure or 'stream flush failed'
                finally:os.close(fd)
            selector.close()
            for s in streams.values():
                if not s.closed:s.close()
        empty=False;resources={};cleanup_failure=None
        try:
            need(own(),'owned hierarchy lost')
            if 'populated 1' in (cg/'cgroup.events').read_text():kill()
            while 'populated 1' in (cg/'cgroup.events').read_text() and time.monotonic_ns()<cleanup_end:
                time.sleep(min(cfg['poll_ns']/1e9,max(0,(cleanup_end-time.monotonic_ns())/1e9)))
            empty='populated 0' in (cg/'cgroup.events').read_text()
            resources={name:(cg/name).read_text() for name in ('cpu.stat','memory.peak','memory.events','pids.events','io.stat')}
            if process is not None and process.poll() is None and empty:
                left=(cleanup_end-time.monotonic_ns())/1e9
                if left>0:returncode=process.wait(timeout=left)
            if empty:cg.rmdir()
        except Exception as exc:cleanup_failure=type(exc).__name__+': '+str(exc)
        verdict=resource_verdict(resources,cfg)
        if not verdict['complete']:failure=failure or '; '.join(verdict['failures'])
        cpu=verdict['observed'].get('cpu_ns')
        try:
            if cpu is not None:b.observe(cpu_ns=cpu)
        except Exception as exc:failure=failure or str(exc)
        record={'launch':launch,'started_ns':t0,'run_deadline_ns':run_end,'cleanup_deadline_ns':cleanup_end,
          'completed_ns':time.monotonic_ns(),'launched':process is not None,'exit_code':returncode,
          'forced':forced,'failure':failure,'cleanup_failure':cleanup_failure,'cleanup_empty':empty,
          'stream_eof':eof,'stream_counts':counts,'stream_persistence':persistence,'resources':resources,
          'leaf_resource_verdict':verdict,'known_stream_prefix_pins':{n:{'bytes':counts[n],'sha256':hashes[n].hexdigest()} for n in eof},
          'source':source_rec,'inputs':input_recs,'model':model_rec,'complete':False}
        try:
            need(time.monotonic_ns()<cleanup_end,'no late success')
            need(returncode==0 and not forced and failure is None and cleanup_failure is None and empty
                 and all(eof.values()) and all(persistence.get(n)=='flushed' for n in eof),'incomplete original process')
            check_tree(source_rec,b)
            for r in input_recs:check_tree(r,b)
            if model_rec:check_tree(model_rec,b)
            record['outputs']=tree(product,cfg['output_bytes'],cfg['output_members'],b)
            b.observe(written=record['outputs']['bytes'])
            record['streams']={n:descriptor(captures/(n+'.txt'),cfg['stream_bytes'],b) for n in eof}
            b.tick();need(time.monotonic_ns()<cleanup_end,'output reconciliation exceeded original deadline')
            record['complete']=True
        except Exception as exc:
            record['complete']=False;record['finalization_error']=type(exc).__name__+': '+str(exc)
        # Reserved evidence has its own cutoff inside the adopted operation
        # envelope. It cannot turn late/failed work into a successful operation.
        record['terminal_created_ns']=time.monotonic_ns()
        if record['terminal_created_ns']>=cleanup_end:record['complete']=False
        record['known_cost_before_terminal']=b.compact()
        try:record_pin=terminal.emit('OUTCOME.json',record)
        finally:terminal.close()
        self.operations.append(record_pin)
        return {**record,'terminal':record_pin}
