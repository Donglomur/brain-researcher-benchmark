"""One shared create-method export; all other lifecycle methods are inherited."""
from qualified_core import BaseEngine
from contract_profile import IMAGE,THREADS,LIMITS,TMPFS,VOLUME_OPTIONS,canonical,command,verify,require

class ProfileEngine(BaseEngine):
    def __init__(self,end,out,budget,profile):
        super().__init__(end,out,budget);self.profile=profile
    def create(self,name,role,mounts):
        canonical(role,mounts,self.profile);lim=LIMITS[role]
        argv=['create','--pull','never','--name',name,'--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory',str(lim['memory']),'--memory-swap',str(lim['memory']),'--cpus',str(lim['cpus']/1e9),'--pids-limit',str(lim['pids']),'--restart','no','--log-driver','local','--log-opt','max-size=64k','--log-opt','max-file=1','--log-opt','compress=false','--ulimit','cpu=20:22','--ulimit','nofile=1024:1024','--ulimit','core=0:0','--ulimit','fsize=33554432:33554432','--workdir','/'if role=='holder'else'/output']
        for dest,row in mounts.items():argv+=['--mount',f"type={row['type']},src={row['source']},dst={dest}"+(',volume-nocopy'if row['type']=='volume'else'')+(''if row['rw']else',readonly')]
        if role=='candidate':
            for dest,opts in TMPFS.items():argv+=['--tmpfs',dest+':'+opts]
        for key in THREADS:argv+=['--env',key+'=2']
        argv+=['--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python',IMAGE,*command(role,self.profile)]
        self.own('container',name,argv);p=self.run(argv);require(p.returncode==0,'Container creation')
        v=self.inspect('container',name);boundary=verify(v,name,role,mounts,self.profile);return v,boundary

    def volume(self,name):
        # Base lifecycle remains inherited; only the exact reviewed volume size differs.
        argv=['volume','create','--driver','local','--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+VOLUME_OPTIONS,name]
        self.own('volume',name,argv);p=self.run(argv);require(p.returncode==0,'Volume creation')
        value=self.inspect('volume',name)
        require(value['Driver']=='local'and value.get('Options')=={'type':'tmpfs','device':'tmpfs','o':VOLUME_OPTIONS},'Exact reviewed memory-backed volume')
        return value
