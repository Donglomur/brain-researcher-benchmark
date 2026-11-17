"""Actual full-Broad NativeOwner; all release decisions bind physical observations."""
import base64,hashlib,os,re,stat,sys,time
from pathlib import Path
from .common import *
from . import process
from .native import Isolation

class NativeOwner:
    def __init__(self,cfg,package,original_root,program_root,output_root,selection,timing):
        need(sys.platform=='linux'and os.geteuid()==0,'selected rootful Linux controller only')
        self.cfg=cfg;self.package=Path(package);self.original_root=regular_path(original_root);self.program_root=private_directory(program_root);self.output_root=regular_path(output_root)
        self.started,self.work_end,self.end=timing;need(time.monotonic()<self.work_end<self.end,'original enclosing campaign endpoints')
        self.budget=Budget(cfg['controller_read_bytes'],cfg['controller_write_bytes'],self.end);self.errors=Ledger();self.pending=[];self.isolations=[];self.keys={};self.sealed={};self.completed=False;self.protected=False;self.closed=False
        self.root=Path(cfg['custody_root']);need(not self.root.exists(),'fresh root-owned campaign custody');self.root.mkdir(mode=0o700)
        self.campaign=os.urandom(32).hex();save(self.root/'CAMPAIGN.json',encoded({'schema':'n090-owned-campaign-v1','campaign':self.campaign,'timing':timing}),self.budget)
        self.captured=self.root/'captured';self.captured.mkdir(mode=0o700)
        (self.root/'commands').mkdir(mode=0o700)
        self.command_records=[];self.command_count=0;self.program_paths={};self.runtime=None;self.selection=selection
        from broad090.protocol import jobs,PROTECTED
        from broad090.capture import invocation_key
        self.invocation=invocation_key;self.expected={invocation_key(j,t):j for j in jobs()for t in('candidate','reference')}
        need(len(self.expected)==76800,'complete selected Broad inventory');self.protected_expected={k for k,j in self.expected.items()if j['arm']in PROTECTED}
        for entry in ('docker','mount','umount'):
            row=cfg[entry];capture(row['path'],self.budget,row['bytes'],{'bytes':row['bytes'],'sha256':row['sha256']})
            s=Path(row['path']).stat();need(s.st_uid==0 and not s.st_mode&0o022 and s.st_mode&0o111,'fixed privileged executable custody')
        need(re.fullmatch('sha256:[0-9a-f]{64}',cfg['image_id'])is not None,'immutable local image ID; no pull/alias')
        integer(cfg['proc_metadata_bytes'],65536);need(cfg['proc_metadata_bytes']<=8*2**20,'finite selected proc grant');process.PROC_READ_CAP=cfg['proc_metadata_bytes']
        info=self.docker(['info','--format','{{json .}}'],self.work_end,self.end,self.budget)
        value=parse(base64.b64decode(info['stdout_base64']));need(value['CgroupDriver']=='cgroupfs'and value['CgroupVersion']=='2'and value['OSType']=='linux','actual local cgroupfs/v2 daemon')
        need(not any('rootless'in str(x)or'userns'in str(x)for x in value.get('SecurityOptions',[])),'qualified rootful daemon without UID remapping')
        image=parse(base64.b64decode(self.docker(['image','inspect',cfg['image_id']],self.work_end,self.end,self.budget)['stdout_base64']))
        need(type(image)is list and len(image)==1 and image[0]['Id']==cfg['image_id'],'actual immutable selected image')
        self.image_env={}
        for item in image[0]['Config'].get('Env')or[]:
            key,value=item.split('=',1);need(key not in self.image_env,'unique selected image environment');self.image_env[key]=value
        # Captured fixed launcher contains no evaluator/candidate result or original labels.
        self.launcher=self.root/'launcher';self.launcher.mkdir(mode=0o755);locks={}
        for name in('actor_entry.py','boot.py','common.py','source_loader.py'):
            row=selection[name];raw=capture(self.package/name,self.budget,row['bytes'],row);save(self.launcher/name,raw,self.budget,0o444);locks[name]=row
        for original,destination in(('provider_entry.py','trusted-provider.py'),('place_entry.py','trusted-place.py')):
            provider=self.selection[original];body=capture(self.package/original,self.budget,provider['bytes'],provider);save(self.root/destination,body,self.budget,0o400)
        save(self.launcher/'SOURCE.json',encoded(locks),self.budget,0o444);os.chmod(self.launcher,0o555)
    def command(self,argv,normal_end,cleanup_end,budget,monitor=None):
        need(time.monotonic()<normal_end<cleanup_end<=self.end,'original command/cleanup endpoints')
        budget.read(262145);budget.write(2*262145)
        record={'argv':list(argv),'normal_end':normal_end,'cleanup_end':cleanup_end,'result':None};self.command_count+=1;number=self.command_count
        original=None
        try:
            result=process._run_owned(argv,normal_end=normal_end,cleanup_end=normal_end+(cleanup_end-normal_end)/3,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':str(self.root),'LC_ALL':'C','DOCKER_HOST':'unix:///var/run/docker.sock'},metadata_read=budget.read,stream_cap=262144,monitor=monitor)
            record['result']=result
        except BaseException as error:
            original=error
            if isinstance(error,process.ChildFailure):record['result']=error.record
        # Strong custody precedes serialization, deadline/transfer checks and fsync.
        if original is not None:self.command_records.append((record,original))
        try:
            save(self.root/'commands'/('command-'+str(number)+'.json'),encoded(record),budget)
        except BaseException as publication:
            self.command_records.append((record,publication))
            if original is None:raise Failure(publication,[('command-publication',publication)],record) from publication
            raise Failure(original,[('command',original),('command-publication',publication)],record) from original
        if original is not None:raise original
        return result
    def docker(self,args,normal_end,cleanup_end,budget,monitor=None):
        return self.command([self.cfg['docker']['path'],*args],normal_end,cleanup_end,budget,monitor)
    def admit_runtime(self,runtime_root,runtime_manifest):
        self.runtime=regular_path(runtime_root);self.runtime_pin=runtime_manifest.pin.json()
        manifest=parse(capture(self.runtime/runtime_manifest.path,self.budget,runtime_manifest.pin.bytes,self.runtime_pin))
        need(len(manifest['members'])==24,'unchanged complete selected reference capsule')
        for row in manifest['members']:
            capture(self.runtime/row['path'],self.budget,row['bytes'],{'bytes':row['bytes'],'sha256':row['sha256']});os.chmod(self.runtime/row['path'],0o444)
        for base,dirs,files in os.walk(self.runtime,topdown=False):os.chmod(base,0o555)
        os.chmod(self.runtime/runtime_manifest.path,0o444)
    def admit_originals(self,source_operands,limits):
        need(set(source_operands)=={'catalogue_asset','supplement_asset','classes_asset','channels_asset'},'exact original source operands')
        roots=[self.original_root,self.program_root,self.root,self.output_root,self.runtime]
        for i,a in enumerate(roots):
            for b in roots[i+1:]:
                # Runtime is the fresh code child created by the existing host.
                if {a,b}=={self.output_root,self.runtime}:continue
                need(a!=b and not a.is_relative_to(b)and not b.is_relative_to(a),'disjoint originals/programs/native/output roots')
        need(limits['actor']['toolset']==self.selection['TOOLSET.json'],'selected actual broker/tool source contract')
        self.limits=limits
        self.original_operands={k:{'path':a.path,**a.pin.json()}for k,a in source_operands.items()}
    def admit_programs(self,programs,modes,arms):
        need(tuple(modes)==('frozen_program','case_adaptive_equal_inputs_tools_compute')and len(arms)==5,'unchanged modes/arms')
        for mode,a in programs.items():
            raw=capture(self.program_root/a.path,self.budget,a.pin.bytes,a.pin.json())
            target=self.root/('candidate-'+mode);target.mkdir(mode=0o755);save(target/'program.py',raw,self.budget,0o444);os.chmod(target,0o555);self.program_paths[mode]=target
        self.programs=dict(programs)
    def new_isolation(self,job,track,program,limits):
        key=self.invocation(job,track);need(key in self.expected and job==self.expected[key]and key not in self.keys,'one exact attempted full-scope invocation')
        need(limits==self.limits['actor']and(track=='reference'and program is None or track=='candidate'and program==self.programs[job['mode']]),'actual selected source/profile')
        if job['arm']in('acoustic','transcript'):need(self.protected,'protected global set sealed before diagnostic actor creation')
        ordinal=len(self.isolations);need(ordinal<76800,'finite exact invocation census')
        iso=Isolation(self,job,track,program,limits,ordinal);self.isolations.append(iso);return iso
    def independent_projection_key(self,invocation):
        need(invocation not in self.keys,'one independent projection key');secret=os.urandom(32);need(secret not in self.keys.values(),'no projection-key reuse');self.keys[invocation]=secret;return secret
    def publish_arm_view(self,isolation,view_root,manifest):need(isolation in self.isolations,'owned invocation');return isolation.publish(view_root,manifest)
    def resource_receipt(self,isolation):
        from programme.contracts import Asset,Pin
        need(isolation.closed and not isolation.errors.events and isolation.returned is not None and isolation.cgroup.closed and not isolation.mounted and all(x['removed']for x in isolation.containers),'actual complete native retirement before receipt')
        value={'schema':'n090-native-retired-v1','invocation':isolation.invocation,'uid':isolation.uid,'image_id':self.cfg['image_id'],'source_runtime':self.runtime_pin,'view':isolation.view[1],'outputs':isolation.output_rows,'counters':isolation.counters,'managed_actor':isolation.actor.report(),'managed_owner':isolation.normal_budget.report(),'managed_cleanup':isolation.cleanup_budget.report(),'broker':isolation.broker.receipt(),'normal_end':isolation.normal_end,'cleanup_end':isolation.cleanup_end,'observed_retired':time.monotonic(),'container_ids':[x['name']for x in isolation.containers]}
        need(value['observed_retired']<isolation.cleanup_end,'native retirement within original reserve')
        path='native-'+isolation.token+'.json';raw=encoded(value);p=save(self.root/path,raw,self.budget)
        need(parse(capture(self.root/path,self.budget,len(raw),p))==value,'actual durable native receipt readback')
        isolation.receipt=Asset(path,Pin.parse(p))
        # Broad retains every object identity; discard raw large arrays/transcripts
        # only after their durable source-bound receipt has been authenticated.
        isolation.commands.clear();isolation.broker.calls.clear();isolation.counters=None;isolation.cgroup.events.clear()
        isolation.containers[:]=[{'name':x['name'],'removed':True}for x in isolation.containers]
        isolation.view=(isolation.view[0],isolation.view[1],())
        return isolation.receipt
    def seal_prediction(self,path,pin_value,invocation):
        need(invocation in self.keys and invocation not in self.sealed,'one actual prediction seal');p=regular_path(path)
        capture(p,self.budget,pin_value.bytes,pin_value.json());os.chmod(p,0o400);self.sealed[invocation]={'path':str(p),'pin':pin_value.json()}
    def seal_set(self,path,pin_value,expected,schema):
        value=parse(capture(path,self.budget,pin_value.bytes,pin_value.json()));need(value['schema']==schema and set(value['captures'])==expected,'full exact capture set')
        for key,roles in value['captures'].items():
            need(key in self.sealed,'known raw prediction seal');base=Path(self.sealed[key]['path']);name=base.name
            for role,prefix in(('asset',''),('mapped','mapped-'),('private_audit','audit-')):
                p=base.parent/(prefix+name);content=capture(p,self.budget,roles[role]['bytes'],roles[role]);os.chmod(p,0o400)
                if role=='private_audit':
                    audit=parse(content)['native_resources'];capture(self.root/audit['path'],self.budget,audit['bytes'],{'bytes':audit['bytes'],'sha256':audit['sha256']})
        os.chmod(path,0o400)
    def seal_protected_set(self,path,pin_value,invocations):
        need(not self.protected and set(invocations)==self.protected_expected and set(self.sealed)==self.protected_expected,'all46080 protected outputs before exposure')
        self.seal_set(path,pin_value,self.protected_expected,'n090-protected-capture-set-v1');self.protected=True
    def seal_complete_set(self,path,pin_value):
        need(self.protected and not self.completed and set(self.sealed)==set(self.expected),'all76800 complete outputs before targets')
        self.seal_set(path,pin_value,set(self.expected),'n090-full-capture-set-v1');self.completed=True
    def close(self):
        if self.closed:return
        for iso in self.isolations:
            if not iso.closed:self.errors.attempt('isolation-final-retirement',iso.close)
        self.closed=True;self.errors.raise_first()
    def drain_close_errors(self):return ()
