"""Concrete selected Linux/Docker isolation, bounded storage and original closure.

Docker CLI process ownership is the adapted held-leader owner; Docker daemon
objects are separately admitted/retired and never inferred from CLI exit alone.
"""
import base64,hashlib,os,re,sys,time
from pathlib import Path
from .common import *
from .cgroup import Cgroup
from .broker import Broker
from . import process

class Isolation:
    def __init__(self,owner,job,track,program,limits,ordinal):
        self.owner=owner;self.job=dict(job);self.track=track;self.program=program;self.limits=dict(limits);self.ordinal=ordinal
        self.invocation=owner.invocation(job,track);self.token=hashlib.sha256((owner.campaign+'|'+self.invocation).encode()).hexdigest();self.uid=owner.cfg['uid_base']+ordinal
        self.root=owner.root/self.token;self.root.mkdir(mode=0o700);self.work=self.root/'work';self.work.mkdir(mode=0o700)
        self.normal_end=min(time.monotonic()+limits['wall_seconds'],owner.work_end);self.cleanup_end=min(self.normal_end+owner.cfg['cleanup_seconds'],owner.end)
        need(self.normal_end<self.cleanup_end,'original actor deadline leaves selected cleanup reserve')
        self.budget=Budget(owner.cfg['isolation_read_bytes'],owner.cfg['isolation_write_bytes'],self.cleanup_end)
        self.normal_budget=self.budget
        self.cleanup_budget=Budget(owner.cfg['isolation_cleanup_read_bytes'],owner.cfg['isolation_cleanup_write_bytes'],self.cleanup_end)
        self.actor=Budget(limits['read_bytes'],limits['write_bytes'],self.normal_end)
        self.errors=Ledger();self.commands=[];self.containers=[];self.mounted=False;self.closed=False;self.returned=None;self.view=None;self.cgroup=None;self.broker=Broker(self);self.round=0;self.receipt=None
        save(self.root/'INTENT.json',encoded({'schema':'n090-native-intent-v1','token':self.token,'uid':self.uid,'work':str(self.work),'cgroup':str(Path(owner.cfg['cgroup_root'])/('n090-'+self.token))}),self.budget)
        try:
            self.cgroup=Cgroup(owner.cfg['cgroup_root'],'n090-'+self.token,self.budget,limits).create()
            options='size='+str(owner.cfg['work_bytes'])+',nr_inodes='+str(owner.cfg['work_inodes'])+',mode=0700,uid='+str(self.uid)+',gid='+str(self.uid)
            self.owner.command([owner.cfg['mount']['path'],'-t','tmpfs','-o',options,'n090-'+self.token,str(self.work)],self.normal_end,self.cleanup_end,self.budget)
            self.mounted=True;self.work_identity=(self.work.stat().st_dev,self.work.stat().st_ino);self.admit_mount()
        except BaseException as e:
            self.errors.record('isolation-create',e);self.close();self.errors.raise_first()
    def admit_mount(self):
        # Exact /proc mount row and actual finite capacity; no caller Boolean.
        raw=kernel_body('/proc/self/mountinfo',self.budget,2**20)
        rows=[line.split()for line in raw.decode().splitlines()if len(line.split())>6 and line.split()[4]==str(self.work)]
        need(len(rows)==1,'one exact kernel output mount');row=rows[0];sep=row.index('-');need(row[sep+1]=='tmpfs'and row[sep+2]=='n090-'+self.token,'actual selected fresh tmpfs')
        s=os.statvfs(self.work);need(s.f_frsize*s.f_blocks<=self.owner.cfg['work_bytes']+s.f_frsize and s.f_files<=self.owner.cfg['work_inodes'],'actual bounded tmpfs capacity/inodes')
    def publish(self,view_root,manifest):
        need(self.view is None,'one fresh arm-only view');asset=manifest
        raw=capture(Path(view_root)/asset['path'],self.actor,asset['bytes'],{'bytes':asset['bytes'],'sha256':asset['sha256']});v=parse(raw)
        need(v['arm']==self.job['arm'],'same selected arm manifest')
        # Existing Compiler created a private flat tree. Stage every declared file,
        # with no host/private sibling mounts; actual ArmViews later checks fields.
        names=[]
        for p in Path(view_root).iterdir():
            need(p.is_file()and not p.is_symlink(),'flat ordinary arm view');names.append(p.name)
        need(len(names)<=32 and asset['path']in names,'finite complete view tree')
        from broad090.views import ArmViews
        ArmViews(view_root,v,None,None) # constructor validates metadata and exact names; no array read
        expected={asset['path']:{'bytes':asset['bytes'],'sha256':asset['sha256']}}
        for role in v['roles'].values():
            for key in('values','timing'):
                row=role[key];need(row['path']not in expected,'unique whole view member');expected[row['path']]={'bytes':row['bytes'],'sha256':row['sha256']}
        target=self.root/'view';target.mkdir(mode=0o700);rows=[]
        for name in sorted(names):
            body=capture(Path(view_root)/name,self.actor,self.limits['read_bytes'],expected[name]);save(target/name,body,self.actor,0o444);rows.append({'path':name,**pin(body)})
        os.chmod(target,0o555);self.view=(target,asset,rows);self.published_root=Path(view_root)
    def inspect_container(self,name,expected_mounts):
        rec=self.owner.docker(['inspect',name],self.normal_end,self.cleanup_end,self.budget);obj=parse(base64.b64decode(rec['stdout_base64']))
        need(type(obj)is list and len(obj)==1,'one owned container');x=obj[0];h=x['HostConfig'];c=x['Config'];s=x['State']
        need(c['Labels'].get('n090.invocation')==self.token and c['Labels'].get('n090.campaign')==self.owner.campaign and x['Image']==self.owner.cfg['image_id'],'exact image and resource ownership')
        need(c['Entrypoint']==[self.owner.cfg['image_python']]and c['Cmd']==['-I','-S','-B','/launcher/boot.py','/request/LAUNCH.json'],'actual fixed preactivation command')
        actual_env={}
        for item in c['Env']:
            key,value=item.split('=',1);need(key not in actual_env,'unique actual actor environment');actual_env[key]=value
        expected_env={**self.owner.image_env,'HOME':'/work','OMP_NUM_THREADS':str(self.limits['threads']),'OPENBLAS_NUM_THREADS':str(self.limits['threads'])}
        need(actual_env==expected_env,'exact selected image plus actor environment')
        need(h['Memory']==self.limits['rss_bytes']and h['MemorySwap']==self.limits['rss_bytes']and h['CgroupnsMode']=='private','actual memory/swap/cgroup namespace')
        need(h.get('CapAdd')in(None,[])and h.get('Devices')in(None,[])and h.get('DeviceRequests')in(None,[]),'no extra capabilities or device exposure')
        need(c['User']==str(self.uid)+':'+str(self.uid)and h['NetworkMode']=='none'and h['ReadonlyRootfs']is True and h['Privileged']is False,'actual isolated UID/rootfs/network')
        need(h['LogConfig']['Type']=='none','no unbounded Docker log sink')
        need(h['CapDrop']==['ALL']and any('no-new-privileges'in q for q in h['SecurityOpt'])and h['PidMode']==''and h['IpcMode']=='private','capabilities and namespace policy')
        need(h['CgroupParent']==str(self.cgroup.path.relative_to('/sys/fs/cgroup'))and h['PidsLimit']==min(self.limits['pids'],self.limits['threads']),'same actual cumulative cgroup/task limit')
        need(all(m['Type']=='bind'and m['Propagation']=='rprivate'for m in x['Mounts']),'fixed private bind propagation')
        got={(m['Source'],m['Destination'],m['RW'])for m in x['Mounts']}
        need(got==set(expected_mounts),'closed exact source/view/work mount set')
        return x
    def container_step(self,argv,tool=False,reference=False,config=None):
        need(self.view is not None and not self.closed and time.monotonic()<self.normal_end,'live current isolation')
        name='n090-'+self.token+'-'+str(len(self.containers));state={'name':name,'created':False,'removed':False,'inspect':None};self.containers.append(state)
        save(self.root/('CONTAINER-'+str(len(self.containers)-1)+'.json'),encoded({'name':name,'token':self.token}),self.budget)
        mounts=[(str(self.work),'/work',True),(str(self.view[0]),'/view',False),(str(self.owner.launcher),'/launcher',False)]
        if reference:mounts.append((str(self.owner.runtime),'/source',False))
        elif self.program is not None:mounts.append((str(self.owner.program_paths[self.job['mode']]),'/candidate',False))
        request_dir=config.parent if config is not None else self.root/('tool-request-'+str(len(self.containers)))
        if config is None:request_dir.mkdir(mode=0o755)
        launch={'argv':argv,'deadline':self.normal_end,'go':'GO','nonce':self.token+'-'+str(len(self.containers))}
        save(request_dir/'LAUNCH.json',encoded(launch),self.budget,0o444)
        mounts.append((str(request_dir),'/request',False))
        cmd=['create','--name',name,'--label','n090.invocation='+self.token,'--label','n090.campaign='+self.owner.campaign,'--pull=never','--log-driver=none','--network=none','--ipc=private','--cgroupns=private','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user',str(self.uid)+':'+str(self.uid),'--pids-limit',str(min(self.limits['pids'],self.limits['threads'])),'--memory',str(self.limits['rss_bytes']),'--memory-swap',str(self.limits['rss_bytes']),'--cgroup-parent',str(self.cgroup.path.relative_to('/sys/fs/cgroup')),'--workdir','/work','--env','HOME=/work','--env','OMP_NUM_THREADS='+str(self.limits['threads']),'--env','OPENBLAS_NUM_THREADS='+str(self.limits['threads'])]
        for src,dst,rw in mounts:
            need(','not in src,'Docker mount delimiter absent');cmd+=['--mount','type=bind,src='+src+',dst='+dst+(''if rw else',readonly')]
        cmd +=['--entrypoint',self.owner.cfg['image_python'],self.owner.cfg['image_id'],'-I','-S','-B','/launcher/boot.py','/request/LAUNCH.json']
        try:
            self.owner.docker(cmd,self.normal_end,self.cleanup_end,self.budget);state['created']=True
            x=self.inspect_container(name,mounts);need(x['State']['Status']=='created'and x['State']['Pid']==0,'inspected before activation');state['inspect']=x
            released=False
            def admission_monitor():
                nonlocal released
                self.cgroup.monitor()
                if released:return
                state=self.inspect_container(name,mounts)['State']
                if state['Status']=='created':return
                need(state['Status']=='running'and type(state['Pid'])is int and state['Pid']>0,'fixed boot waiting for admission')
                pid=state['Pid'];proc=Path('/proc')/str(pid)
                body=kernel_body(proc/'cgroup',self.budget,8192).decode().strip()
                need(body.startswith('0::/')and '\n'not in body,'actual unified actor cgroup')
                actual=Path('/sys/fs/cgroup'+body[3:]);need(actual.is_relative_to(self.cgroup.path)and actual!=self.cgroup.path,'actual actor is in this bounded descendant cgroup')
                rows={line.split(':',1)[0]:line.split(':',1)[1].strip()for line in kernel_body(proc/'status',self.budget,16384).decode().splitlines()if ':'in line}
                need(rows['Uid'].split()==[str(self.uid)]*4 and rows['Gid'].split()==[str(self.uid)]*4 and rows['NoNewPrivs']=='1'and int(rows['CapEff'],16)==0,'actual unprivileged actor identity')
                for ns in('pid','mnt','net','ipc'):
                    need((proc/'ns'/ns).stat().st_ino!=(Path('/proc/self/ns')/ns).stat().st_ino,'actual private '+ns+' namespace')
                need(time.monotonic()<self.normal_end,'original activation deadline')
                save(request_dir/'GO',launch['nonce'].encode(),self.budget,0o444);released=True
                state_record={'pid':pid,'cgroup':body,'uid':self.uid,'no_new_privileges':True,'cap_eff':0}
                self.containers[-1]['activation']=state_record
            rec=self.owner.docker(['start','--attach',name],self.normal_end,self.cleanup_end,self.budget,monitor=admission_monitor);self.commands.append(rec)
            need(released,'actual preactivation barrier released before completion')
            x=self.inspect_container(name,mounts);s=x['State']
            need(s['Status']=='exited'and s['Running']is False and s['Dead']is False and s['OOMKilled']is False and type(s['ExitCode'])is int and s['ExitCode']==0 and s['Pid']==0,'actual natural container zero and non-OOM')
            self.cgroup.monitor();self.owner.docker(['rm',name],self.normal_end,self.cleanup_end,self.budget);state['removed']=True
            return rec
        except BaseException as e:
            self.errors.record('container:'+name,e);raise
    def execute(self,reference=False):
        need(self.returned is None,'no retry or second prediction');response=None;cfg=self.owner.cfg
        maximum=1+self.limits['tool_calls']+self.limits['model_tokens']//(cfg['provider']['input_tokens']+cfg['provider']['output_tokens'])
        for round_number in range(maximum):
            self.round=round_number;request_dir=self.root/('request-'+str(round_number));request_dir.mkdir(mode=0o755)
            request={'kind':'reference'if reference else'candidate','seed':self.job['seed'],'limits':self.limits,'device':cfg['device'],'view':self.view[1],'runtime':self.owner.runtime_pin,'candidate':None if reference else self.program.pin.json(),'round':round_number,'response':response}
            path=request_dir/'request.json';save(path,encoded(request),self.budget,0o444)
            self.container_step([cfg['image_python'],'-I','-B','/launcher/actor_entry.py','/request/request.json'],reference=reference,config=path)
            action_path=self.work/('action-'+str(round_number)+'.json');action=parse(capture(action_path,self.actor,65536))
            if action.get('kind')=='finish':
                fields(action,('kind','prediction'));return self.capture_output(action['prediction'])
            need(not reference,'reference may not request broker actions');response=self.broker.dispatch(action)
        raise ValueError('finite action roster exhausted without complete prediction')
    def run_reference(self,entry,source_root,runtime_manifest,view_root,manifest_asset,seed,limits):
        need(entry=='broad090.worker:reference'and Path(source_root)==self.owner.runtime and runtime_manifest.pin.json()==self.owner.runtime_pin and Path(view_root)==self.published_root and {'path':manifest_asset.path,**manifest_asset.pin.json()}==self.view[1] and seed==self.job['seed']and limits==self.limits,'exact existing reference call');return self.execute(True)
    def run_candidate(self,view_root,manifest_asset,seed,limits):
        need(Path(view_root)==self.published_root and {'path':manifest_asset.path,**manifest_asset.pin.json()}==self.view[1] and seed==self.job['seed']and limits==self.limits,'exact current candidate call');return self.execute(False)
    def capture_output(self,asset):
        from programme.contracts import Asset
        a=Asset.parse(asset);need(a.path=='prediction.json','fixed final prediction filename');source=self.work/'final'
        body=capture(source/a.path,self.actor,a.pin.bytes,a.pin.json());value=parse(body)
        expected={'prediction.json':a.pin.json(),'source.pt':value['source_checkpoint'],'final.pt':value['final_checkpoint'],'logical-resource.json':value['resource_receipt']}
        target=self.owner.captured/self.token;target.mkdir(mode=0o700);rows=[]
        for name,p in expected.items():
            raw=body if name=='prediction.json'else capture(source/name,self.actor,p['bytes'],p)
            self.actor.write(len(raw));save(target/name,raw,self.budget,0o400);rows.append({'path':name,**pin(raw)})
        self.returned=(target,a);self.output_rows=rows;return self.returned
    def close(self):
        if self.closed:return
        self.budget=self.cleanup_budget
        if self.cgroup is not None:self.cgroup.budget=self.cleanup_budget
        # Stop every actual owned daemon object independently, even unknown create acknowledgments.
        for state in self.containers:
            if state['removed']:continue
            def remove(state=state):
                rec=self.owner.docker(['inspect',state['name']],self.cleanup_end-.02,self.cleanup_end,self.budget)
                obj=parse(base64.b64decode(rec['stdout_base64']))[0]
                need(obj['Config']['Labels'].get('n090.invocation')==self.token and obj['Config']['Labels'].get('n090.campaign')==self.owner.campaign,'never remove a foreign daemon object')
                self.owner.docker(['rm','-f',state['name']],self.cleanup_end-.02,self.cleanup_end,self.budget);state['removed']=True
            self.errors.attempt('container-recovery:'+state['name'],remove)
        if self.cgroup is not None:
            self.errors.attempt('cgroup-kill',self.cgroup.kill)
            self.counters=self.errors.attempt('cgroup-finish',self.cgroup.finish)
        if self.mounted:
            def unmount():
                need((self.work.stat().st_dev,self.work.stat().st_ino)==self.work_identity,'same owned tmpfs before unmount')
                self.owner.command([self.owner.cfg['umount']['path'],str(self.work)],self.cleanup_end-.02,self.cleanup_end,self.budget)
                self.mounted=False
            self.errors.attempt('tmpfs-unmount',unmount)
        if not self.errors.events:save(self.root/'CLOSED.json',encoded({'token':self.token,'cgroup_empty_removed':self.cgroup is not None and self.cgroup.closed,'tmpfs_unmounted':not self.mounted,'containers_removed':all(x['removed']for x in self.containers)}),self.budget)
        self.closed=True
        # No nominal receipt may survive any unknown native/descriptor closure.
        if self.errors.events:self.errors.raise_first({'invocation':self.invocation,'commands':self.commands,'containers':self.containers})
    def drain_close_errors(self):return () # close surfaced the strong carrier containing every occurrence.
