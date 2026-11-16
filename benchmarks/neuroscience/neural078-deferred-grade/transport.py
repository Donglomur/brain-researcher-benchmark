"""Bounded local grade transport; exact retained CLI capture function."""
import json,os,re,selectors,signal,subprocess,time
from types import SimpleNamespace
from bound_io import need,parse
from absence import absence

def bind(binary,socket,config,image,budget,call= None):
    call=call or bounded_call
    env={k:v for k,v in os.environ.items() if not k.startswith(('DOCKER_','PYTHON','LD_','DYLD_'))}
    env.update(DOCKER_HOST='unix://'+str(socket),DOCKER_CONFIG=str(config))
    engines=[]
    class Engine:
        def __init__(self,end,out,budget):
            self.end=end;self.out=out;self.budget=budget;self.commands=[];self.owned=[];self.identities={};engines.append(self)
        def run(self,args,timeout=5,cap=200000):
            need(len(self.commands)<96 and type(cap)is int and 0<cap<=262144,'Bounded grade CLI inventory')
            p=call(str(binary),env,args,min(self.end,time.monotonic()+timeout),cap)
            self.commands.append(dict(argv=args,returncode=p.returncode,stdout_bytes=len(p.stdout),stderr_bytes=len(p.stderr)));return p
        def own(self,kind,name,args):
            need(kind=='container','One trusted container only')
            p=self.run(['inspect','--type','container',name],timeout=2,cap=65536)
            need(absence(p.returncode,p.stdout.decode(),p.stderr.decode(),kind,name),'Fresh trusted grade name')
            self.owned.append(dict(kind=kind,name=name,attempted_before_dispatch=True,argv=args))
            self.budget.save(self.out/'resource_ownership.json',dict(owned=self.owned),65536)
        def inspect(self,kind,name):
            need(kind=='container','Container identity only');p=self.run(['inspect','--type','container',name])
            need(type(p.returncode)is int and p.returncode==0,'Successful trusted inspect');rows=parse(p.stdout)
            need(type(rows)is list and len(rows)==1 and rows[0]['Name']=='/'+name,'Exact inspected trusted container')
            v=rows[0];ident=v['Id'];need(type(ident)is str and re.fullmatch('[a-f0-9]{64}',ident),'Immutable trusted container ID')
            need(name not in self.identities or self.identities[name]==ident,'Stable trusted container identity');self.identities[name]=ident;return v
        def cleanup(self,kind,name):
            row=dict(kind=kind,name=name,absence_verified=False)
            try:
                need(kind=='container' and len([x for x in self.owned if x['name']==name])==1,'Only exact owned grade resource')
                ident=self.identities.get(name);need(ident is not None,'Known inspected identity required before cleanup')
                p=self.run(['inspect','--type','container',name],timeout=2,cap=65536)
                if not absence(p.returncode,p.stdout.decode(),p.stderr.decode(),kind,name):
                    need(p.returncode==0,'Live inspect or exact absence');v=parse(p.stdout)
                    need(type(v)is list and len(v)==1 and v[0]['Name']=='/'+name and v[0]['Id']==ident,'Same owned native identity before removal')
                    p=self.run(['rm','--force',ident],timeout=2,cap=65536);row['remove_returncode']=p.returncode
                checks=[]
                for target in (name,ident):
                    p=self.run(['inspect','--type','container',target],timeout=2,cap=65536);checks.append(absence(p.returncode,p.stdout.decode(),p.stderr.decode(),kind,target))
                row.update(required_absence_targets=[name,ident],absence_verified=all(checks))
            except BaseException as error:row['error_type']=type(error).__name__
            return row
    return dict(engine_class=Engine,engines=engines,contract=SimpleNamespace(IMAGE=image),call=call,binary=str(binary),env=env)

def previous_absence(rows,lib,end):
    evidence=[]
    for row in rows:
        kind,name=row['kind'],row['name'];need(kind in ('container','volume') and type(name)is str and re.fullmatch('neural078-[a-f0-9]{24}-(candidate|admission|holder|volume)',name),'Original owned phase resource name')
        need(row.get('closed') is True and row.get('absence_observed') is True and row.get('creation_outcome_unknown') is False and type(row.get('removed'))is bool,'Complete original native resource closure')
        argv=['volume','inspect',name] if kind=='volume' else ['inspect','--type','container',name]
        p=lib['call'](lib['binary'],lib['env'],argv,min(end,time.monotonic()+2),65536)
        need(absence(p.returncode,p.stdout.decode(),p.stderr.decode(),kind,name),'Former resource remains absent before private release')
        evidence.append(dict(kind=kind,name=name,absent=True))
    need(len(evidence)==6 and len({x['name'] for x in evidence})==6,'All six distinct former resources')
    return evidence

def bounded_call(binary,env,args,deadline,cap):
    """Adapted NEURAL068 bounded CLI capture; nonzero exits remain explicit operands."""
    need(deadline-time.monotonic()>0,'Docker client deadline')
    p=subprocess.Popen([binary,*args],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
    sel=None
    try:
        sel=selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()}
        for key,f in [('stdout',p.stdout),('stderr',p.stderr)]:
            os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,key)
        while sel.get_map():
            left=deadline-time.monotonic();need(left>0,'Bounded Docker client time')
            for key,_ in sel.select(min(.05,left)):
                try:b=os.read(key.fileobj.fileno(),min(32768,cap-len(buffers[key.data])+1))
                except BlockingIOError:continue
                if not b:sel.unregister(key.fileobj);continue
                need(len(buffers[key.data])+len(b)<=cap,'Preventive Docker stream cap');buffers[key.data].extend(b)
        rc=p.wait(timeout=max(.001,deadline-time.monotonic()))
        need(time.monotonic()<deadline,'Original Docker client deadline after wait')
        return subprocess.CompletedProcess(args,rc,bytes(buffers['stdout']),bytes(buffers['stderr']))
    finally:
        # All work after a successful Popen, including selector setup, is covered.
        cleanup_end=time.monotonic()+2
        def group_exists():
            try:os.killpg(p.pid,0);return True
            except ProcessLookupError:return False
        closed=False
        try:
            if p.poll() is None or group_exists():
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                try:
                    left=cleanup_end-time.monotonic()
                    if left>0:p.wait(timeout=min(1,left))
                except subprocess.TimeoutExpired:pass
            finish=min(cleanup_end,time.monotonic()+1)
            while group_exists() and time.monotonic()<finish:time.sleep(.01)
            closed=p.poll() is not None and not group_exists()
        finally:
            close_errors=[]
            for handle in (sel,p.stdout,p.stderr):
                if handle is not None:
                    try:handle.close()
                    except BaseException as error:close_errors.append(type(error).__name__)
        need(closed and not close_errors,'Docker client reaped/group absent/handles closed')
        need(time.monotonic()<cleanup_end,'Fixed Docker client cleanup acceptance deadline')
        need(time.monotonic()<deadline,'Original Docker client deadline includes closure')
