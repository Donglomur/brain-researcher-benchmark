"""One shared create-method export; all other lifecycle methods are inherited."""
from common import BaseEngine
import re
import os
from files import json_read, need
from contract_profile import IMAGE,THREADS,LIMITS,TMPFS,canonical,command,verify,require

class ProfileEngine(BaseEngine):
    def __init__(self,end,out,budget,profile):
        super().__init__(end,out,budget);self.profile=profile
    def sync_directory(self):
        fd=os.open(self.out,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    def journal(self):
        super().journal()
        self.sync_directory()
    def create(self,name,role,mounts):
        canonical(role,mounts,self.profile);lim=LIMITS[role]
        argv=['create','--pull','never','--name',name,'--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory',str(lim['memory']),'--memory-swap',str(lim['memory']),'--cpus',str(lim['cpus']/1e9),'--pids-limit',str(lim['pids']),'--restart','no','--log-driver','local','--log-opt','max-size=64k','--log-opt','max-file=1','--log-opt','compress=false','--ulimit','cpu=1050:1051','--ulimit','nofile=1024:1024','--ulimit','core=0:0','--ulimit','fsize=4000000:4000000','--workdir','/'if role=='holder'else'/output']
        for dest,row in mounts.items():argv+=['--mount',f"type={row['type']},src={row['source']},dst={dest}"+(',volume-nocopy'if row['type']=='volume'else'')+(''if row['rw']else',readonly')]
        if role=='candidate':
            for dest,opts in TMPFS.items():argv+=['--tmpfs',dest+':'+opts]
        for key in THREADS:argv+=['--env',key+'=1']
        argv+=['--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python',IMAGE,*command(role,self.profile)]
        self.own('container',name,argv);p=self.run(argv);self.record_create_result(name,p);require(p.returncode==0,'Container creation')
        v=self.inspect('container',name);need(v.get('Id')==json_read(self.out/('create-result-'+name+'.json'))['created_id'],'Returned and inspected immutable IDs agree');boundary=verify(v,name,role,mounts,self.profile);return v,boundary

    def record_create_result(self,name,created):
        out=created.stdout.decode('ascii',errors='replace');err=created.stderr.decode(errors='replace')
        identity=out.strip() if created.returncode==0 else None
        record=self.write('create-result-'+name+'.json',{'kind':'container','name':name,'returncode':created.returncode,'stdout':out,'stderr':err,'created_id':identity},cap=16384)
        fd=os.open(record,os.O_RDONLY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.sync_directory()
        need(created.returncode==0 and re.fullmatch('[a-f0-9]{64}',identity or '') is not None,'Exact successful create stdout identity')
        return identity

    def cleanup(self,kind,name):
        from panel_recovery import recover
        item=next(row for row in self.owned if row['kind']==kind and row['name']==name)
        try:return recover(self.out.parent,self.out,item,self,self.budget)
        except BaseException as error:return {'kind':kind,'name':name,'absence_verified':False,'error':repr(error)[:2000]}
