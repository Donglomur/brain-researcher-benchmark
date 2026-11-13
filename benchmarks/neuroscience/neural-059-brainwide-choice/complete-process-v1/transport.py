"""Concrete dedicated-Docker/cgroup-v2 owner for N059 workers.

The selected daemon and controller already belong to the selected whole cgroup.
That admission is checked from kernel bytes, not a native-success receipt. Only
this process owns the endpoint. Its image/code operands are immutable selections.
"""
import os
from pathlib import Path
import socket
import stat
import struct
import time
from .core import need, keys, literal, read, capture, encode, parse, pin
from .donor.production_process import ProcessRunner, ObservedFailure
from .donor.cgroup import Cgroup
from . import channel_mount


class OCIStudy:
    def __init__(self, selection, budget, journal, carrier):
        self.s = selection; self.d = selection['deployment']; self.b = budget
        self.j = journal; self.carrier = carrier; self.runner = ProcessRunner(budget,journal,carrier)
        self.rows = []; self.counter = 0; self.rpc_counter = 0; self.groups = []
        self.poisoned = False; self.initial_cpu = None; self.last_cpu = None
        self.kernel_events=[]; self.endpoint=None
        self.end = budget.deadline; self.work_end = self.end-selection['closure_reserve_seconds']
        self.env = {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
        self.binary = str(literal(self.d['docker']['path']))
        capture(self.d['docker'],self.b)
        capture(self.d['dockerd'],self.b)
        need(os.access(self.binary,os.X_OK), 'actual selected Docker executable')
        self.config = literal(self.d['docker_config'])
        need(self.config.is_dir() and not list(self.config.iterdir()), 'empty credential-free Docker configuration')
        self.code = literal(self.d['code_root'])
        self.whole = literal(self.d['whole_cgroup'])
        self.controller = literal(self.d['controller_leaf']); self.daemon = literal(self.d['daemon_leaf'])
        need(os.uname().sysname == 'Linux' and os.geteuid() == 0, 'actual privileged Linux owner')
        need(self.whole.is_relative_to('/sys/fs/cgroup') and self.controller.parent == self.whole
             and self.daemon.parent == self.whole and self.controller != self.daemon,
             'dedicated complete controller/daemon whole cgroup')
        need(self.kernel(self.controller/'cgroup.procs').split() == [str(os.getpid())],
             'single admitted controller before producer work')
        need(self.kernel('/proc/self/cgroup') == self.membership(self.controller), 'controller kernel membership')
        need(self.kernel(self.whole/'cgroup.procs') == '', 'empty whole internal node')
        need({'cpu','memory','pids'} <= set(self.kernel(self.whole/'cgroup.subtree_control').split()),
             'actual delegated complete controllers')
        need(self.kernel(self.whole/'memory.max') == str(self.d['whole_memory_bytes']) and
             self.kernel(self.whole/'memory.swap.max') == '0' and
             self.kernel(self.whole/'pids.max') == str(self.d['whole_pids']), 'actual complete whole enforced limits')
        need({p.name for p in self.whole.iterdir() if p.is_dir()} ==
             {self.controller.name,self.daemon.name}, 'no unrelated producers inside selected lifetime')
        daemon_pids = self.kernel(self.daemon/'cgroup.procs').split()
        need(daemon_pids, 'actual selected daemon process membership')
        self.initial_cpu = self.cpu()
        info = parse(self.command(['info','--format','{{json .}}'],131072).stdout)
        need(info['ID'] == self.d['daemon_id'] and info['DockerRootDir'] == self.d['daemon_root'] and
             info['OSType'] == 'linux' and info['CgroupVersion'] == '2' and info['CgroupDriver'] == 'cgroupfs',
             'original dedicated local daemon identity and unified driver')
        need(not self.command(['ps','--all','--quiet','--no-trunc'],65536).stdout.strip(),
             'dedicated daemon has no preexisting containers')
        self.admission = self.j.json('HOST_ADMISSION.json', {'kernel_daemon_pids':daemon_pids,
            'daemon_info':info,'initial_whole_cpu':self.initial_cpu,'qualification':False,
            'scope':'whole CPU from admission; preadmission daemon startup is not measured'})

    @staticmethod
    def membership(path):
        return '0::/' + str(Path(path).relative_to('/sys/fs/cgroup'))

    def kernel(self, path):
        fd=None; body=bytearray(); first=None
        cap=4194304 if str(path)=='/proc/self/mountinfo' else 16384
        record={'path':str(path),'body_hex':'','closed':False,'error':None,'cap':cap}
        self.kernel_events.append(record); index=len(self.kernel_events)
        try:
            self.b.admit_read(cap+1); fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            while len(body)<=cap:
                chunk=os.read(fd,min(65536,cap+1-len(body))); body.extend(chunk)
                record['body_hex']=body.hex(); self.b.read(len(chunk))
                if not chunk: break
            need(len(body)<=cap,'bounded original kernel observation')
            return bytes(body).decode('ascii').strip()
        except BaseException as error:
            first=error; record['error']=type(error).__name__; raise
        finally:
            secondary=None
            if fd is not None:
                try: os.close(fd); record['closed']=True
                except BaseException as error:
                    secondary=error; self.b.uncertain(str(path),'kernel descriptor closure',error)
            try: self.j.json('kernel-%08d.json'%index,record)
            except BaseException as error:
                self.carrier.fail(error,'original kernel publication')
                if secondary is None: secondary=error
            if secondary is not None:
                if first is None: raise secondary
                first.add_note('Original kernel close/publication also failed: '+type(secondary).__name__)

    def endpoint_join(self,deadline):
        self.b.check('before original daemon endpoint join',deadline)
        path=literal(self.d['docker_host'][7:]); before=path.lstat()
        need(stat.S_ISSOCK(before.st_mode),'actual local daemon socket')
        conn=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            conn.settimeout(max(.001,min(.05,deadline-time.monotonic()))); conn.connect(str(path))
            pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            need(uid==0 and self.kernel('/proc/%d/cgroup'%pid)==self.membership(self.daemon)
                 and str(pid) in self.kernel(self.daemon/'cgroup.procs').split(),
                 'actual endpoint peer belongs to selected whole-owned daemon leaf')
            need(os.readlink('/proc/%d/exe'%pid)==self.d['dockerd']['path'],'actual selected daemon executable')
            start=self.kernel('/proc/%d/stat'%pid).rsplit(')',1)[1].split()[19]
            after=path.lstat(); identity=(before.st_dev,before.st_ino,pid,uid,gid,start)
            need((before.st_dev,before.st_ino,before.st_mode)==(after.st_dev,after.st_ino,after.st_mode),
                 'stable actual endpoint inode')
            if self.endpoint is None:
                self.endpoint=identity; self.j.json('DAEMON_ENDPOINT.json',{'path':str(path),'original_peer':identity})
            else: need(identity==self.endpoint,'same original daemon process and endpoint')
        finally: conn.close()
        self.b.check('after original daemon endpoint join',deadline)

    def cpu(self):
        fields = dict(line.split() for line in self.kernel(self.whole/'cpu.stat').splitlines())
        need(fields['usage_usec'].isdigit(), 'actual unified whole CPU')
        return int(fields['usage_usec'])/1000000

    def poll(self, deadline=None):
        self.b.check('complete N059 lifetime', min(deadline or self.end,self.end))
        if self.initial_cpu is not None:
            self.last_cpu = self.cpu()-self.initial_cpu
            need(0 <= self.last_cpu <= self.b.limits['cpu_seconds'], 'complete whole CPU cap')
        for row in self.rows:
            if row['group'] is not None and row['group'].initial_cpu is not None and not row['group'].closed:
                need(row['group'].sample() <= row['role']['cpu_seconds'], 'complete individual role CPU cap')

    def command(self, args, cap, *, deadline=None, missing=False):
        ident = 'cli-%06d' % self.counter; self.counter += 1
        argv = [self.binary,'--config',str(self.config),'--host',self.d['docker_host'],*args]
        end = min(deadline or self.end,self.end)
        self.endpoint_join(end)
        o=self.runner.run(ident,argv,end,cap,env=self.env,poll_service=self.poll,
                          allowed_returncodes=(0,1) if missing else (0,))
        self.endpoint_join(end)
        # Only inspect's precise Docker absence is accepted. Its genuine code1
        # and streams remain published without poisoning the shared carrier.
        if missing and o.returncode==1:
            text=bytes(o.stderr).decode('utf-8','strict').strip()
            need(args[:3]==['inspect','--type','container'] and bytes(o.stdout).strip() in (b'',b'[]') and
                 text in ('Error: No such object: '+args[-1],
                          'Error response from daemon: No such container: '+args[-1]),
                 'exact observed owned-container absence')
            return None
        return o

    def _inspect(self, row, missing=False, *, deadline=None):
        result = self.command(['inspect','--type','container',row.get('id') or row['name']],131072,
                              missing=missing,deadline=row['deadline'] if deadline is None else deadline)
        if result is None: return None
        value = parse(result.stdout); need(type(value) is list and len(value)==1,'one actual container')
        info = value[0]
        need(info['Name'] == '/'+row['name'] and info['Config']['Labels'].get('org.neurobench.neural059') ==
             self.s['study_id'] and info['Config']['Labels'].get('org.neurobench.role') == row['key'],
             'actual named container ownership, never infer unknown create absent')
        need(info['Id'] == (row.get('id') or info['Id']) and len(info['Id'])==64, 'full immutable container ID')
        row['id'] = info['Id']; row['observations'].append(info)
        return info

    def start(self, key, kind, role, boot, *, policy_body=None, checkpoint=False):
        need(not self.poisoned and time.monotonic()<self.work_end and
             key not in {x['key'] for x in self.rows}, 'fresh worker in original work lifetime')
        origin = time.monotonic(); end = min(origin+role['wall_seconds'], self.work_end)
        name = 'n059-'+self.s['study_id']+'-'+str(len(self.rows))
        row = {'key':key,'kind':kind,'name':name,'id':None,'origin':origin,'deadline':end,
               'role':role,'observations':[],'closed':False,'calls':0,'group':None,
               'bootstrap':None,'failure':None,'model_usage':{'calls':0,'input_tokens':0,'output_tokens':0}}
        self.rows.append(row)  # Own unknown-create intent before any effect.
        self.b.reserve(name+'-emergency-kill',256,0)
        self.b.reserve_capacity(name,role['tmpfs_bytes']+role['channel_bytes'],role['channel_files']+role['work_files'])
        base = self.j.root/name; base.mkdir(mode=0o700)
        channel = base/'channel'; channel.mkdir(mode=0o700)
        row['channel'] = str(channel); inp = base/'input'; inp.mkdir(mode=0o700)
        group = Cgroup(self.whole,name,self.b,self.end); row['group']=group; self.groups.append(group)
        try:
            row['channel_mount']={}
            channel_mount.mount(channel,name,role['channel_bytes'],role['channel_files'],self.kernel,row['channel_mount'])
            group.create(role['memory_bytes'],role['pids'])
            group.write('cpu.max','100000 100000')
            b = {'schema':'n059_worker_boot_v1','role':kind,'key':key,'selection_identity':pin(self.s),
                 'origin':origin,'deadline':end,'role_limits':role,'source_sha256':self.s['source_sha256'],
                 'payload':boot}
            row['bootstrap'] = b; raw = encode(b)
            self.j.write(name+'/input/boot.json',raw)
            if policy_body is not None: self.j.write(name+'/input/policy.py',policy_body)
            # Host owner retains private ancestry; only exact selected input and
            # source are mounted. No parent tree, credentials, Docker or targets.
            for p in inp.iterdir(): os.chmod(p,0o444)
            os.chmod(inp,0o555)
            mounts = [f'type=bind,src={self.code},dst=/code,readonly',
                      f'type=bind,src={inp},dst=/input,readonly',
                      f'type=bind,src={channel},dst=/channel']
            if checkpoint:
                mounts.append(f'type=bind,src={literal(self.s["model"]["checkpoint_root"])},dst=/model,readonly')
            work_options='rw,noexec,nosuid,nodev,size='+str(role['tmpfs_bytes'])+',nr_inodes='+str(role['work_files'])+',uid=65534,gid=65534'
            args = ['create','--pull','never','--name',name,'--label','org.neurobench.neural059='+self.s['study_id'],
                    '--label','org.neurobench.role='+key,'--read-only','--network','none',
                    '--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges',
                    '--cgroupns','host','--cgroup-parent','/'+str(group.path.relative_to('/sys/fs/cgroup')),
                    '--memory',str(role['memory_bytes']),'--memory-swap',str(role['memory_bytes']),
                    '--pids-limit',str(role['pids']),'--cpus','1','--ipc','none',
                    '--tmpfs','/work:'+work_options,
                    '--env','PYTHONDONTWRITEBYTECODE=1','--env','OMP_NUM_THREADS=1',
                    '--env','OPENBLAS_NUM_THREADS=1','--env','MKL_NUM_THREADS=1',
                    '--log-driver','none','--workdir','/work','--entrypoint',role['python']]
            for mount in mounts: args.extend(['--mount',mount])
            args += [role['image'],'-I','-B','/code/worker_entry.py','/input/boot.json',pin(raw)['sha256']]
            out = self.command(args,4096,deadline=end)
            cid = bytes(out.stdout).decode('ascii').strip()
            need(len(cid)==64 and all(x in '0123456789abcdef' for x in cid),'exact create acknowledgement')
            row['id']=cid; info=self._inspect(row); hc=info['HostConfig']
            need(info['Image']==role['image'] and hc['ReadonlyRootfs'] and hc['NetworkMode']=='none'
                 and info['Config']['User']=='65534:65534' and hc['Privileged'] is False
                 and hc['CapDrop']==['ALL'] and not hc.get('CapAdd') and
                 any(x in ('no-new-privileges','no-new-privileges=true') for x in hc['SecurityOpt']) and hc['CgroupnsMode']=='host'
                 and hc['PidMode']=='' and hc['IpcMode']=='none' and not hc.get('Devices')
                 and hc['Memory']==role['memory_bytes'] and hc['MemorySwap']==role['memory_bytes']
                 and hc['PidsLimit']==role['pids'] and hc['CgroupParent']=='/'+str(group.path.relative_to('/sys/fs/cgroup')),
                 'actual immutable restricted worker configuration')
            need(hc['LogConfig']['Type']=='none','no unbounded daemon-owned candidate log files')
            need(hc['Tmpfs']=={'/work':work_options},'exact original work tmpfs byte/inode options')
            actual_mounts={(m['Source'],m['Destination'],m['RW']) for m in info['Mounts'] if m['Type']=='bind'}
            expected={(str(self.code),'/code',False),(str(inp),'/input',False),(str(channel),'/channel',True)}
            if checkpoint: expected.add((str(literal(self.s['model']['checkpoint_root'])),'/model',False))
            need(actual_mounts==expected and all(m['Type'] in ('bind','tmpfs') for m in info['Mounts']),
                 'exact worker mount authority')
            self.command(['start',cid],4096,deadline=end)
            while True:
                self.poll(end); info=self._inspect(row)
                need(info['State']['Running'],'worker remains alive before readiness')
                pid=info['State']['Pid']; membership=self.kernel('/proc/%d/cgroup'%pid)
                need(membership.startswith(self.membership(group.path)+'/'), 'actual worker inside owned subtree')
                row['membership']=membership; row['pid']=pid
                if (channel/'rpc.sock').exists(): break
                time.sleep(.005)
            row['started_inspect']=info
            self.poll(end)
            return row
        except BaseException as error:
            row['failure']=type(error).__name__; self.poisoned=True
            raise

    def rpc(self, row, operation, payload, model_handler=None, *, deadline=None):
        need(not self.poisoned and not row['closed'], 'live healthy selected worker')
        end=min(row['deadline'],deadline or row['deadline'],self.end)
        self.poll(end); row['calls']+=1; self.rpc_counter+=1
        req={'sequence':row['calls'],'operation':operation,'payload':payload,'selection_identity':pin(self.s)}
        raw=encode(req); need(len(raw)<=row['role']['request_bytes'],'whole request bound before send')
        record={'worker':row['key'],'request':req,'sent':0,'received':[],'closed':False,'error':None}
        self.carrier.retain(record); conn=None; index=self.rpc_counter; first=None
        try:
            path=Path(row['channel'])/'rpc.sock'; st=path.lstat()
            need(stat.S_ISSOCK(st.st_mode) and st.st_uid==65534,'actual selected worker socket')
            conn=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); conn.settimeout(.05); conn.connect(str(path))
            pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            need((pid,uid,gid)==(row['pid'],65534,65534),'actual original worker peer')
            def send(body):
                wire=struct.pack('!I',len(body))+body; pos=0
                while pos<len(wire):
                    self.poll(end)
                    try: n=conn.send(wire[pos:])
                    except socket.timeout: continue
                    except BaseException:
                        record['send_extent_unknown']=True; raise
                    need(n>0,'actual frame send progress'); pos+=n; record['sent']+=n; self.b.stream(n)
            def receive():
                buf=bytearray(); frame={'body_hex':'','complete':False}; record['received'].append(frame)
                target=4
                while len(buf)<target:
                    self.poll(end)
                    try: chunk=conn.recv(min(65536,target-len(buf)))
                    except socket.timeout: continue
                    buf.extend(chunk); frame['body_hex']=buf.hex(); self.b.stream(len(chunk))
                    need(chunk,'complete original reply, no EOF prefix promotion')
                    if len(buf)==4:
                        n=struct.unpack('!I',buf)[0]
                        need(0<n<=row['role']['response_bytes'],'bounded worker reply'); target=4+n
                frame['complete']=True; return parse(bytes(buf[4:]))
            send(raw)
            while True:
                result=receive()
                need(result.get('sequence')==row['calls'],'exact original RPC sequence')
                if result.get('kind')=='model':
                    need(row['kind'] in ('actor','actor_predict') and callable(model_handler),'model capability only in selected actor')
                    reply=model_handler(row,result['request'])
                    send(encode({'sequence':row['calls'],'kind':'model_result','result':reply}))
                    continue
                need(set(result)=={'sequence','kind','result'} and result['kind']=='result',
                     'complete original worker result, errors remain failure')
                return result['result']
        except BaseException as error:
            first=error; self.poisoned=True; record['error']=type(error).__name__; row['failure']=type(error).__name__; raise
        finally:
            secondary=None
            try:
                if conn is not None: conn.close(); record['closed']=True
            except BaseException as error:
                secondary=error; record['close_error']=type(error).__name__
                self.b.uncertain(row['key'],'RPC descriptor closure',error)
            try: self.j.json('rpc-%08d.json'%index,record)
            except BaseException as error:
                self.carrier.fail(error,'original RPC custody publication')
                if secondary is None: secondary=error
            if secondary is not None:
                self.poisoned=True
                if first is None: raise secondary
                first.add_note('RPC close/publication also failed: '+type(secondary).__name__)

    def close(self, row):
        need(not row['closed'],'one original worker closure')
        result=self.rpc(row,'close',{})
        need(result.get('closed') is True,'worker protocol retirement')
        while True:
            self.poll(row['deadline']); info=self._inspect(row)
            if not info['State']['Running']: break
            time.sleep(.005)
        need(info['State']['ExitCode']==0 and not info['State']['OOMKilled'] and not info['State'].get('Error'),
             'actual natural zero worker exit')
        row['native_stdout_stderr']='discarded by explicit log-driver=none; only bounded RPC is an accepted worker output'
        group=row['group']; group.finish(); row['group_final']=group.final
        need(group.final['cpu_seconds']<=row['role']['cpu_seconds'],'final original whole-role CPU within cap')
        self.command(['rm',row['id']],4096,deadline=row['deadline'])
        need(self._inspect(row,missing=True) is None,'actual container absent after owned retirement')
        channel_mount.unmount(row['channel_mount'],self.kernel)
        row['closed']=True; row['close_result']=result; row['elapsed']=time.monotonic()-row['origin']
        self.b.release_capacity(row['name'])
        self.b.reservations.pop(row['name']+'-emergency-kill')
        self.poll(row['deadline'])
        return self.j.json('closure-'+row['name']+'.json',self.document(row))

    def document(self,row):
        return {k:v for k,v in row.items() if k!='group'}

    def complete(self, rows):
        need(rows and all(x['closed'] and x['failure'] is None for x in rows),
             'every selected producer has original successful closure')
        return {'capture_identity':pin([self.document(x) for x in rows]),
                'all_selected_processes_exited':True,'status':'source_only_unqualified'}

    def contain(self):
        """No retry: independently retire every known/unknown owned constructor."""
        self.poisoned=True; errors=[]
        for row in reversed(self.rows):
            if row['closed']: continue
            def attempt(name,fn):
                try: return fn()
                except BaseException as error:
                    errors.append({'key':row['key'],'phase':name,'error_type':type(error).__name__})
                    self.b.uncertain(row['key'],name,error)
                    return None
            def kill():
                reservation=self.b.reservations.pop(row['name']+'-emergency-kill',None)
                need(reservation is not None,'original one-shot emergency control reservation')
                if row['group'] is not None: row['group'].emergency_kill()
            # Kill is attempted independently BEFORE ordinary CLI/cost admission.
            # Expired read/CPU budgets cannot skip this reserved kernel control.
            attempt('owned_subtree_emergency_kill',kill)
            def container():
                info=self._inspect(row,missing=True,deadline=self.end)
                if info is not None:
                    self.command(['rm','--force',row['id']],4096)
                    need(self._inspect(row,missing=True,deadline=self.end) is None,'failed owned container absent')
                row['container_absence_observed']=True
            attempt('owned_container_retirement',container)
            def finish():
                if row['group'] is not None:
                    row['group'].finish(); row['group_final']=row['group'].final
            attempt('original_failed_group_closure',finish)
            def channel():
                need(row.get('container_absence_observed') is True and
                     (row['group'] is None or row['group'].closed), 'no live producer can retain channel mount')
                if row.get('channel_mount'): channel_mount.unmount(row['channel_mount'],self.kernel)
            attempt('owned_channel_retirement',channel)
            row['forced_retirement']=True  # Never natural/scoring completion.
        return {'errors':errors,'workers':[self.document(r) for r in self.rows],
                'whole_cpu_seconds':self.last_cpu,'qualification':False}
