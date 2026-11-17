"""Trusted bounded local Docker lifecycle; no candidate code executes on host."""
from pathlib import Path
import hashlib,json,os,stat,subprocess,time
from absence import absence
from runtime_contract import IMAGE,THREADS,LIMITS,TMPFS,VOLUME_OPTIONS,canonical,command,verify,require
ROOT=Path(__file__).resolve().parents[3]
ENV=dict({k:v for k,v in os.environ.items() if k not in ('DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')},DOCKER_CONFIG=str(ROOT/'.cache-build/docker-config'),DOCKER_HOST='unix:///var/run/docker.sock')
DOCKER='/usr/local/bin/docker'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def regular(path,cap):
    p=Path(path).absolute();require(all(not x.is_symlink()for x in(p,*p.parents)),'No linked input path');s=p.lstat()
    require(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and 0<s.st_size<=cap,'Bounded single-link regular input');return p

def public_pin(path,pin):
    p=regular(path,1000000);require(p.stat().st_size==pin['bytes']and digest(p)==pin['sha256'],'Exact public input identity');return p

def snapshot(path):
    p=regular(path,65536);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as f:
        before=os.fstat(f.fileno());body=f.read(65537);after=os.fstat(f.fileno())
    require(0<len(body)<=65536 and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)and len(body)==before.st_size,'Unchanged bounded program snapshot')
    return body

class Engine:
    def __init__(self,end,out,budget):self.end=end;self.out=Path(out);self.budget=budget;self.owned=[];self.commands=[];self.sequence=0
    def write(self,name,obj,cap=200000):
        data=(json.dumps(obj,indent=2,allow_nan=False)+'\n').encode();require(len(data)<=cap,'Bounded evidence serialization');self.budget.write(self.out/name,data,receipt=True);return self.out/name
    def journal(self):
        data=(json.dumps({'owned':self.owned},indent=2)+'\n').encode();require(len(data)<=65536,'Ownership journal cap');self.budget.check(len(data),receipt=True)
        tmp=self.out/'resource_ownership.next';require(not tmp.exists(),'Fresh atomic ownership staging')
        with tmp.open('xb')as f:f.write(data);f.flush();os.fsync(f.fileno())
        tmp.replace(self.out/'resource_ownership.json')
    def run(self,argv,timeout=5,cap=200000):
        remaining=self.end-time.monotonic();require(remaining>0,'Whole-stage deadline')
        p=subprocess.run([DOCKER,*argv],env=ENV,capture_output=True,timeout=min(timeout,remaining));require(len(p.stdout)<=cap and len(p.stderr)<=cap,'Bounded Docker result')
        self.sequence+=1;self.commands.append({'sequence':self.sequence,'argv':argv,'returncode':p.returncode,'stdout_bytes':len(p.stdout),'stderr_bytes':len(p.stderr)})
        return p
    def fresh(self,kind,name):
        p=self.run(['volume','inspect',name]if kind=='volume'else['inspect','--type','container',name])
        v={'kind':kind,'name':name,'returncode':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')};self.write('precreate-'+name+'.json',v)
        require(absence(p.returncode,v['stdout'],v['stderr'],kind,name),'Exact resource absent before ownership')
    def own(self,kind,name,argv):
        self.fresh(kind,name);self.owned.append({'kind':kind,'name':name,'attempted_before_dispatch':True,'canonical_create_argv':argv});self.journal()
    def inspect(self,kind,name):
        p=self.run(['volume','inspect',name]if kind=='volume'else['inspect','--type','container',name]);text=p.stdout.decode(errors='replace')
        self.write(f'inspect-{self.sequence}-{name}.json',{'returncode':p.returncode,'stdout':text,'stderr':p.stderr.decode(errors='replace')})
        require(p.returncode==0,'Successful inspect required');rows=json.loads(text);require(type(rows)is list and len(rows)==1,'Exact single inspect row');row=rows[0]
        require(row['Name']==(name if kind=='volume'else'/'+name),'Exact inspected resource name');return row
    def volume(self,name):
        argv=['volume','create','--driver','local','--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+VOLUME_OPTIONS,name]
        self.own('volume',name,argv);p=self.run(argv);require(p.returncode==0,'Volume creation');v=self.inspect('volume',name)
        require(v['Driver']=='local'and v.get('Options')=={'type':'tmpfs','device':'tmpfs','o':VOLUME_OPTIONS},'Exact local memory-backed volume only');return v
    def create(self,name,role,mounts):
        canonical(role,mounts);lim=LIMITS[role]
        argv=['create','--pull','never','--name',name,'--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory',str(lim['memory']),'--memory-swap',str(lim['memory']),'--cpus',str(lim['cpus']/1e9),'--pids-limit',str(lim['pids']),'--restart','no','--log-driver','local','--log-opt','max-size=64k','--log-opt','max-file=1','--log-opt','compress=false','--ulimit','cpu=20:22','--ulimit','nofile=1024:1024','--ulimit','core=0:0','--ulimit','fsize=1048576:1048576','--workdir','/'if role=='holder'else'/output']
        for dest,row in mounts.items():argv+=['--mount',f"type={row['type']},src={row['source']},dst={dest}"+(',volume-nocopy'if row['type']=='volume'else'')+(''if row['rw']else',readonly')]
        if role=='candidate':
            for dest,opts in TMPFS.items():argv+=['--tmpfs',dest+':'+opts]
        for key in THREADS:argv+=['--env',key+'=2']
        argv+=['--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python',IMAGE,*command(role)]
        self.own('container',name,argv);p=self.run(argv);require(p.returncode==0,'Container creation')
        v=self.inspect('container',name);boundary=verify(v,name,role,mounts);return v,boundary
    def logs(self,name):
        p=self.run(['logs',name],timeout=3,cap=150000)
        return {'returncode':p.returncode,'stdout':p.stdout[:65536].decode(errors='replace'),'stderr':p.stderr[:65536].decode(errors='replace'),'captured_stdout_bytes':len(p.stdout),'captured_stderr_bytes':len(p.stderr),'possibly_rotated_by_64KiB_log_driver':True,'capture_truncated':len(p.stdout)>65536 or len(p.stderr)>65536}
    def cleanup(self,kind,name):
        row={'kind':kind,'name':name,'absence_verified':False}
        try:
            p=self.run(['volume','rm',name]if kind=='volume'else['rm','--force',name],timeout=2);row['remove']={'returncode':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}
        except Exception as e:row['remove_error']=repr(e)
        try:
            p=self.run(['volume','inspect',name]if kind=='volume'else['inspect','--type','container',name],timeout=2)
            row['inspect']={'returncode':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')};row['absence_verified']=absence(p.returncode,row['inspect']['stdout'],row['inspect']['stderr'],kind,name)
        except Exception as e:row['inspect_error']=repr(e)
        return row
