"""NEURAL051 six-case supervised source capability; actual dispatch unselected."""
import argparse,ast,base64,hashlib,io,json,math,os,re,shutil,signal,stat,sys,time,types,uuid
from pathlib import Path

HERE=Path(__file__).resolve().parent
LOCK_PIN={'bytes':2594,'sha256':'56401428e14ffe4ef779c1f14ddb86b9881d9ed3a757ec8bf054706912f625c3'}
CASES=tuple('sub-'+p+'_'+r for p in ('01','02','03') for r in ('V1','IT'))
FUTURE=3_000_000_000
RETAINED=500_000_000
SCORE_CAP=50_000_000
CHUNK=4*1024**2
RUNTIME_FILES={'dispatch.py','entry.py','holder.py','LOCK.json'}

def need(v):
    if not v:raise ValueError('NEURAL051 dispatch boundary')
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def capture(path,expected,cap):
    p=Path(path).absolute();need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)))
    need(type(expected['bytes']) is int and 0<expected['bytes']<=cap)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==expected['bytes'])
        b=f.read(a.st_size+1);z=os.fstat(f.fileno());n=p.lstat()
    fields=('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
    need(all(getattr(a,k)==getattr(z,k)==getattr(n,k) for k in fields) and pin(b)=={k:expected[k]for k in ('bytes','sha256')});return b
def module(raw,name,filename):
    m=types.ModuleType(name);m.__file__=str(filename);exec(compile(raw,str(filename),'exec'),m.__dict__);return m

def dependencies(repo):
    """Join reviewed source; only explicit namespace/extent constants adapt."""
    repo=Path(repo).absolute();lock=json.loads(capture(HERE/'LOCK.json',LOCK_PIN,10000))
    need(lock['cases']==list(CASES) and lock['condition']=='JPEG-RGB-1' and lock['task_id']=='NEURAL-051')
    def get(name,cap=100000):
        p=lock['pins'][name];return capture(repo/p['path'],p,cap)
    raw=get('transport');tree=ast.parse(raw)
    class Extent(ast.NodeTransformer):
        def visit_Constant(self,n):
            if n.value==524288:return ast.copy_location(ast.Constant(50_000_000),n)
            if n.value=='fsize=524288:524288':return ast.copy_location(ast.Constant('fsize=50000000:50000000'),n)
            if n.value=='neural069-[a-f0-9]{24}-volume':return ast.copy_location(ast.Constant('neural051-[a-f0-9]{24}-volume'),n)
            return n
    t=Extent().visit(tree);ast.fix_missing_locations(t)
    r=types.ModuleType('reviewed_transport');exec(compile(t,'<pinned NEURAL069 transport:051 constants>','exec'),r.__dict__)
    r.LABEL='org.neurobench.neural051-program-owner';r.VOLUME_BYTES=64*1024**2
    r.VOLUME_OPTIONS='size=67108864,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
    ch=module(get('child'),'reviewed_child',repo/lock['pins']['child']['path'])
    return types.SimpleNamespace(repo=repo,lock=lock,get=get,r=r,ch=ch)

def sources(expected):
    manifest=json.loads(capture(HERE/'SOURCE_MANIFEST.json',expected,100000))
    need(manifest['schema']=='neural051_jpeg_rgb1_dispatch_source_v1' and set(manifest['runtime_files'])==RUNTIME_FILES)
    bodies={n:capture(HERE/n,p,200000) for n,p in manifest['runtime_files'].items()}
    need(pin(bodies['LOCK.json'])==LOCK_PIN);return bodies

def footprint(root):
    total=0;count=0;todo=[Path(root)] if os.path.lexists(root) else []
    while todo:
        p=todo.pop();s=p.lstat();count+=1;need(count<=60000)
        need(stat.S_ISDIR(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_nlink==1))
        total+=max(s.st_size,s.st_blocks*512);need(total<=FUTURE)
        if stat.S_ISDIR(s.st_mode):
            with os.scandir(p) as it:
                for x in it:need(count+len(todo)<60000);todo.append(p/x.name)
    return total

class Writer:
    def __init__(self,root,other,cap=FUTURE):self.root=Path(root);self.other=other;self.cap=cap;self.written=0
    def guard(self,extra=0):
        need(type(self.other) is int and self.other>=0 and extra>=0)
        used=footprint(self.root);need(used+extra+65536<=self.cap and self.written+extra<=min(RETAINED,self.cap))
        need(shutil.disk_usage(self.root.parent).free>=21474836480+self.other+max(0,self.cap-used))
    def child_other(self,reservation):
        self.guard();used=footprint(self.root);need(used+reservation<=self.cap)
        return self.other+max(0,self.cap-used-reservation)
    def mkdir(self,p,mode=0o700):
        self.guard(65536);Path(p).mkdir(mode=mode);syncdir(Path(p).parent)
    def bytes(self,p,raw,cap=100000):
        need(type(raw) is bytes and len(raw)<=cap);self.guard(len(raw));p=Path(p)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        self.written+=len(raw);return pin(raw)
    def json(self,p,value,cap=100000):
        """Exclusive pending/link publication; no marker-only success claim."""
        p=Path(p);raw=encoded(value);need(len(raw)<=cap and not os.path.lexists(p));tmp=p.with_name('.'+p.name+'.pending')
        result=self.bytes(tmp,raw,cap);os.link(tmp,p);tmp.unlink();syncdir(p.parent);return result
def syncdir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def commit_read(e,directory,expected,source_pin):
    r=e.r;raw=r.capture(Path(directory)/'COMMIT.json',10000,expected);c=r.parse(raw)
    need(set(c)=={'schema','task_id','condition','program','source_manifest','lock','image','cases','candidate_seconds','memory_bytes','exposure_declaration'})
    need(c['schema']=='neural051_program_commit_v1' and c['task_id']=='NEURAL-051' and c['condition']=='JPEG-RGB-1'
         and c['source_manifest']==source_pin and c['lock']==LOCK_PIN and c['image']==r.IMAGE and c['cases']==list(CASES))
    need(type(c['candidate_seconds']) is int and 1<=c['candidate_seconds']<=7200
         and type(c['memory_bytes']) is int and 536870912<=c['memory_bytes']<=4294967296
         and type(c['exposure_declaration']) is str and 1<=len(c['exposure_declaration'])<=4096)
    program=r.capture(Path(directory)/'program.py',131072,c['program']);program.decode('utf-8')
    return c,program

def freeze(repo,program,dest,seconds,memory,exposure,source_pin,other):
    e=dependencies(repo);sources(source_pin);raw=e.r.capture(program,131072);raw.decode('utf-8')
    need(type(seconds) is int and 1<=seconds<=7200 and type(memory) is int and 536870912<=memory<=4294967296)
    need(type(exposure) is str and 1<=len(exposure)<=4096)
    d=e.r.path(dest);need(not os.path.lexists(d));w=Writer(d,other,500000);w.mkdir(d)
    c={'schema':'neural051_program_commit_v1','task_id':'NEURAL-051','condition':'JPEG-RGB-1','program':pin(raw),
       'source_manifest':source_pin,'lock':LOCK_PIN,'image':e.r.IMAGE,'cases':list(CASES),
       'candidate_seconds':seconds,'memory_bytes':memory,'exposure_declaration':exposure}
    w.bytes(d/'program.py',raw,131072);cp=w.json(d/'COMMIT.json',c,10000);syncdir(d)
    return {'status':'committed','commit':cp,'program':pin(raw)}

def score_functions(e):
    """Exact frozen admission functions only, never grade_arrays or design."""
    import numpy as np
    need(np.__version__=='2.2.6')
    tree=ast.parse(e.get('scorer_source'));names={'load_array','validate_roster','roster_digest'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];need(len(nodes)==3)
    ns={'np':np,'io':io,'math':math,'json':json,'hashlib':hashlib,'CASES':CASES,'SUBJECTS':('01','02','03')}
    exec(compile(ast.Module(nodes,[]),'<unchanged NEURAL051 output admission>','exec'),ns)
    return types.SimpleNamespace(**{n:ns[n]for n in names})

def capture_output(e,d,keeper,work,destination,writer):
    """Chunk transport only after actual producer removal; no raw Docker logs."""
    r=e.r;idx=r.parse(r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','index'],work,'score_index',4096))
    need(set(idx)=={'schema','bytes','sha256'} and idx['schema']=='neural051_score_index_v1'
         and type(idx['bytes']) is int and 0<idx['bytes']<=SCORE_CAP and re.fullmatch('[a-f0-9]{64}',idx['sha256']))
    writer.guard(idx['bytes']);tmp=Path(destination).with_suffix('.pending');need(not os.path.lexists(destination))
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);h=hashlib.sha256();total=0
    with os.fdopen(fd,'wb') as f:
        for offset in range(0,idx['bytes'],CHUNK):
            reply=r.parse(r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','chunk','--offset',str(offset)],work,'score_chunk',6_000_000,15))
            need(set(reply)=={'schema','offset','total_bytes','bytes','sha256','base64'} and reply['schema']=='neural051_score_chunk_v1'
                 and reply['offset']==offset and reply['total_bytes']==idx['bytes'])
            raw=base64.b64decode(reply['base64'],validate=True)
            need(len(raw)==min(CHUNK,idx['bytes']-offset) and pin(raw)=={k:reply[k]for k in ('bytes','sha256')})
            writer.guard(len(raw));f.write(raw);h.update(raw);total+=len(raw);writer.written+=len(raw)
        f.flush();os.fsync(f.fileno())
    result={'bytes':total,'sha256':h.hexdigest()};need(result=={k:idx[k]for k in ('bytes','sha256')})
    os.link(tmp,destination);tmp.unlink();syncdir(Path(destination).parent);return result

def case_lifecycle(e,d,snapshot,c,view,attempt,destination,writer,end):
    """Task adaptation of reviewed069/CASCADE ordering; exact ownership only."""
    r=e.r;start=time.monotonic();command_start=len(d.records);work=end-60;items=[];closures=[];failure=None;natural=None;score=None;candidate_closed=False
    prefix='neural051-'+uuid.uuid4().hex[:24]
    def item(role,kind):
        x={'kind':kind,'name':prefix+'-'+role,'owner':prefix+'/'+role,'attempted':False,'acknowledged':False};items.append(x)
        writer.json(attempt/('INTENT-'+role+'.json'),x,4096);return x
    def before(x):need(r.resource_inventory(d,x,x['owner'],work,'before_'+x['kind'])==[])
    def create(x,role,mounts,memory):
        before(x);x['attempted']=True
        ident=r.call(d,r.create_args(x,role,mounts,memory),work,'create_'+role,4096,12).decode('ascii').strip()
        need(re.fullmatch('[a-f0-9]{64}',ident));x.update(id=ident,acknowledged=True)
        r.admission(r.inspect(d,'container',ident,work,'admit_'+role),x,role,mounts,memory)
    try:
        need(time.monotonic()<work-30)
        image=r.parse(r.call(d,['image','inspect',r.IMAGE,'--format','{{json .}}'],work,'image',131072))
        need(image['Id']==r.IMAGE and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']))
        volume=item('volume','volume');before(volume);volume['attempted']=True
        result=r.call(d,['volume','create','--driver','local','--label',r.LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+r.VOLUME_OPTIONS,volume['name']],work,'create_volume',4096).decode().strip()
        need(result==volume['name']);volume['acknowledged']=True
        v=r.inspect(d,'volume',volume['name'],work,'volume_admit');r.owned(v,volume,volume['owner'])
        need(v['Driver']=='local' and v['Options']=={'type':'tmpfs','device':'tmpfs','o':r.VOLUME_OPTIONS})
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',snapshot/'holder.py',False),'/capture':('volume',volume['name'],False)}
        create(holder,'holder',hm,268435456);r.call(d,['container','start',holder['id']],work,'holder_start',4096)
        need(r.parse(r.call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','ready'],work,'holder_ready',4096))=={'ready':True})
        producer=item('candidate','container');cm={'/entry.py':('bind',snapshot/'entry.py',False),'/submission/program.py':('bind',snapshot/'program.py',False),'/case':('bind',view,False),'/output':('volume',volume['name'],True)}
        create(producer,'candidate',cm,c['memory_bytes']);begin=time.monotonic()
        r.call(d,['container','start',producer['id']],work,'candidate_start',4096)
        reply=d(['container','wait',producer['id']],min(work,begin+c['candidate_seconds']),'candidate_wait',4096)
        state=r.inspect(d,'container',producer['id'],work,'candidate_exit');r.owned(state,producer,producer['owner'])
        natural={k:state['State'][k]for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
        need(reply.strip()==b'0' and natural=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False} and time.monotonic()-begin<=c['candidate_seconds'])
        close=r.retire(d,producer,work);closures.append(close);need(close['closed'] and close['removed']);items.remove(producer);candidate_closed=True
        score=capture_output(e,d,holder,work,destination,writer)
    except BaseException as exc:failure=type(exc).__name__
    finally:
        for x in reversed(items):
            try:closures.append(r.retire(d,x,end))
            except BaseException as exc:closures.append({'kind':x['kind'],'name':x['name'],'closed':False,'error_type':type(exc).__name__})
    closed=len(closures)==3 and all(x.get('closed') and x.get('removed') and x.get('absence_observed') and x.get('creation_outcome_unknown') is False for x in closures)
    return {'schema':'neural051_case_lifecycle_v1','status':'captured' if failure is None and score is not None and closed and d.reaped else 'failed',
            'program':c['program'],'condition':c['condition'],'image':r.IMAGE,'score':score,'natural_exit':natural,
            'candidate_closed_before_capture':candidate_closed,'closures':closures,'all_resources_closed':closed,'cli_reaped':d.reaped,
            'error_type':failure,'elapsed_seconds':time.monotonic()-start,'limit_seconds':c['candidate_seconds']+420,
            'command_metadata':[dict(x) for x in d.records[command_start:]],'private_scoring_called':False}

def lifecycle_closed(x):
    need(x['status']=='captured' and x['all_resources_closed'] is True and x['candidate_closed_before_capture'] is True
         and x['cli_reaped'] is True and x['error_type'] is None and x['private_scoring_called'] is False
         and x['natural_exit']=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}
         and 0<=x['elapsed_seconds']<=x['limit_seconds'])
    need(len(x['closures'])==3 and all(z.get('closed') and z.get('removed') and z.get('absence_observed') and z.get('creation_outcome_unknown') is False for z in x['closures']))
    return True

def retire_child(e,workspace,admission,execution,execution_pin,other,snapshot):
    x=e.r.parse(e.r.capture(execution,100000,execution_pin));lifecycle_closed(x)
    need(x['input_admission']==admission and x['condition']=='JPEG-RGB-1' and x['case'] in CASES)
    raw=capture(snapshot/'invocation.py',e.lock['pins']['invocation'],100000)
    inv=module(raw,'retire_inputs',snapshot/'invocation.py')
    return inv.retire_after_runner_closed(e.repo,workspace,admission,other,lambda:lifecycle_closed(x))

def worker(repo,commit,commit_pin,source_pin,output,other,socket):
    start=time.monotonic();e=dependencies(repo);bodies=sources(source_pin);c,program=commit_read(e,commit,commit_pin,source_pin)
    end=start+6*(2000+c['candidate_seconds']+420+300+100)+120
    old=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('whole worker bound')))
    need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0));signal.setitimer(signal.ITIMER_REAL,max(.001,end-start-60))
    output=e.r.path(output);need(not os.path.lexists(output));w=Writer(output,other,FUTURE-2_000_000);rows=[]
    try:
        w.mkdir(output);snapshot=output/'snapshot';w.mkdir(snapshot,0o755)
        for n,b in {**bodies,'program.py':program,'invocation.py':e.get('invocation'),'BINDINGS.json':e.get('invocation_bindings')}.items():w.bytes(snapshot/n,b,200000)
        w.bytes(snapshot/'SOURCE_MANIFEST.json',capture(HERE/'SOURCE_MANIFEST.json',source_pin,100000),100000)
        snapshot.chmod(0o555);syncdir(snapshot)
        out=output/'captured';w.mkdir(out);records=output/'records';w.mkdir(records);workspaces=output/'workspaces';w.mkdir(workspaces)
        intent={'schema':'neural051_dispatch_intent_v1','commit':commit_pin,'source_manifest':source_pin,'program':c['program'],
                'condition':'JPEG-RGB-1','cases':list(CASES),'image':e.r.IMAGE,'whole_seconds':end-start,'other_reserved_bytes':other,'future_bytes':FUTURE-2_000_000,
                'controlled_read_allowance_bytes':52_000_000_000,'cumulative_write_allowance_bytes':15_000_000_000,'failed_costs_preserved':True}
        intent_pin=w.json(output/'INTENT.json',intent,10000)
        funcs=score_functions(e);roster=e.r.parse(e.get('roster',3_000_000));funcs.validate_roster(roster);need(funcs.roster_digest(roster)==e.lock['roster_sha256'])
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
        d=e.r.Docker(shutil.which('docker') or '/usr/local/bin/docker',e.r.path(socket))
        for case in CASES:
            need(time.monotonic()<end-100);case_dir=records/case;w.mkdir(case_dir);workspace=workspaces/case;w.mkdir(workspace)
            prep_other=w.child_other(2_383_554_432)
            argv=[str(Path(sys.executable).resolve()),'-I','-B',str(snapshot/'invocation.py'),'--repo',str(e.repo),'--workspace',str(workspace),'--case',case,'--condition','JPEG-RGB-1','--invocation',case,'--other-reserved-bytes',str(prep_other)]
            raw,prep_exit=e.ch.child(argv,min(end-80,time.monotonic()+2060),env);terminal=e.r.parse(raw)
            need(terminal['status']=='input_prepared' and terminal['case']==case and terminal['condition']=='JPEG-RGB-1' and terminal['invocation']==case)
            admission=terminal['admission'];a=e.r.parse(e.r.capture(workspace/'ADMISSION.json',65536,admission))
            need(a['case']==case and a['condition']=='JPEG-RGB-1' and a['source_sha256']==e.r.parse(e.get('invocation_bindings'))['pins']['SOURCE_MANIFEST.json']['sha256']
                 and a['mount']==terminal['mount']=={'source':str(workspace/'current'),'destination':'/case','read_only':True}
                 and not (workspace/'FAILED.json').exists())
            w.json(case_dir/'PREPARE_EXIT.json',{'child':prep_exit,'terminal':terminal},20000)
            x=case_lifecycle(e,d,snapshot,c,workspace/'current',case_dir,out/(case+'.npy'),w,min(end-80,time.monotonic()+c['candidate_seconds']+420))
            x.update(case=case,input_admission=admission);xp=w.json(case_dir/'EXECUTION.json',x,100000);lifecycle_closed(x)
            score=e.r.capture(out/(case+'.npy'),SCORE_CAP,x['score']);funcs.load_array(score,(1540,3700));del score
            retire_other=w.child_other(32*1024**2)
            cmd=[str(Path(sys.executable).resolve()),'-I','-B',str(snapshot/'dispatch.py'),'retire-child','--repo',str(e.repo),'--workspace',str(workspace),'--execution',str(case_dir/'EXECUTION.json'),'--execution-pin',json.dumps(xp),'--admission-pin',json.dumps(admission),'--other-reserved-bytes',str(retire_other),'--snapshot',str(snapshot),'--source-pin',json.dumps(source_pin)]
            raw,retired=e.ch.child(cmd,min(end-80,time.monotonic()+360),env);ret=e.r.parse(raw)
            need(ret['status']=='retired' and not os.path.lexists(workspace/'current'))
            e.r.capture(workspace/'RETIREMENT.json',65536,ret['retirement'])
            row={'case':case,'program':c['program'],'condition':'JPEG-RGB-1','score':x['score'],'execution':xp,'input_admission':admission,'retirement':ret['retirement'],'retirement_child':retired}
            rp=w.json(case_dir/'CLOSED.json',row,20000);rows.append({'case':case,'record':rp})
        need(len(rows)==6)
        files={}
        for case in CASES:
            raw=e.r.capture(out/(case+'.npy'),SCORE_CAP);funcs.load_array(raw,(1540,3700));files[case]={'file':case+'.npy','sha256':pin(raw)['sha256']};del raw
        need({p.name for p in out.iterdir()}=={c+'.npy' for c in CASES})
        manifest={'schema':'neural051-scores-v1','roster_sha256':funcs.roster_digest(roster),'files':files};mp=w.json(out/'submission.json',manifest,10000)
        need(time.monotonic()<end and footprint(output)<=RETAINED)
        result={'schema':'neural051_dispatch_complete_v1','status':'closed','condition':'JPEG-RGB-1','program':c['program'],'commit':commit_pin,'source_manifest':source_pin,'intent':intent_pin,'cases':rows,'submission':mp,'private_scoring_called':False,'runtime_qualified':False,'seconds':time.monotonic()-start,'whole_seconds':end-start}
        done=w.json(output/'COMPLETE.json',result,20000);need(time.monotonic()<end)
        return {'status':'closed','completion':done,'outputs':7}
    except BaseException as exc:
        if output.is_dir():
            try:w.json(output/'FAILURE.json',{'status':'failed','error_type':type(exc).__name__,'completed_cases':rows,'resource_recovery_may_be_required':True,'automatic_retry':False},20000)
            except BaseException:pass
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)


def closed_panel(e,attempt,c,commit_pin,source_pin,completion_pin):
    """No candidate declaration substitutes for trusted execution evidence."""
    r=e.r;attempt=Path(attempt);need(not os.path.lexists(attempt/'FAILURE.json'))
    done=r.parse(r.capture(attempt/'COMPLETE.json',20000,completion_pin))
    need(done['schema']=='neural051_dispatch_complete_v1' and done['status']=='closed' and done['condition']=='JPEG-RGB-1'
         and done['program']==c['program'] and done['commit']==commit_pin and done['source_manifest']==source_pin
         and done['private_scoring_called'] is False and done['runtime_qualified'] is False
         and [x['case'] for x in done['cases']]==list(CASES) and 0<=done['seconds']<=done['whole_seconds'])
    intent=r.parse(r.capture(attempt/'INTENT.json',10000,done['intent']))
    need(intent['commit']==commit_pin and intent['source_manifest']==source_pin and intent['program']==c['program']
         and intent['cases']==list(CASES) and intent['condition']=='JPEG-RGB-1' and intent['image']==r.IMAGE
         and intent['whole_seconds']==done['whole_seconds']==6*(2000+c['candidate_seconds']+420+300+100)+120)
    funcs=score_functions(e);roster=r.parse(e.get('roster',3_000_000));funcs.validate_roster(roster)
    bodies=sources(source_pin)
    snapshots={**{n:pin(b)for n,b in bodies.items()},'SOURCE_MANIFEST.json':source_pin,'program.py':c['program'],
               'invocation.py':{k:e.lock['pins']['invocation'][k]for k in ('bytes','sha256')},
               'BINDINGS.json':{k:e.lock['pins']['invocation_bindings'][k]for k in ('bytes','sha256')}}
    for n,p in snapshots.items():r.capture(attempt/'snapshot'/n,200000,p)
    source_binding=r.parse(e.get('invocation_bindings'))
    expected_files={'INTENT.json','COMPLETE.json',*('snapshot/'+n for n in snapshots),'captured/submission.json',*('captured/'+k+'.npy'for k in CASES)}
    expected_dirs={'snapshot','captured','records','workspaces'}
    outputs={};closures=[]
    for row in done['cases']:
        case=row['case'];directory=attempt/'records'/case;workspace=attempt/'workspaces'/case
        closed=r.parse(r.capture(directory/'CLOSED.json',20000,row['record']))
        need(closed['case']==case and closed['condition']=='JPEG-RGB-1' and closed['program']==c['program']
             and not os.path.lexists(workspace/'current') and not os.path.lexists(workspace/'FAILED.json'))
        x=r.parse(r.capture(directory/'EXECUTION.json',100000,closed['execution']));lifecycle_closed(x)
        need(x['case']==case and x['program']==c['program'] and x['condition']=='JPEG-RGB-1'
             and x['image']==r.IMAGE and x['score']==closed['score'] and x['input_admission']==closed['input_admission']
             and x['limit_seconds']==c['candidate_seconds']+420)
        names=set();prefixes=set()
        for role,kind in (('volume','volume'),('holder','container'),('candidate','container')):
            initial=r.parse(r.capture(directory/('INTENT-'+role+'.json'),4096))
            need(initial['kind']==kind and initial['attempted'] is False and initial['acknowledged'] is False
                 and re.fullmatch('neural051-[a-f0-9]{24}-'+role,initial['name']))
            need(initial['owner']==initial['name'].removesuffix('-'+role)+'/'+role)
            prefixes.add(initial['name'].removesuffix('-'+role))
            actual=[z for z in x['closures'] if z['name']==initial['name'] and z['kind']==kind];need(len(actual)==1);names.add(initial['name'])
        need(len(names)==3 and len(prefixes)==1)
        prep=r.parse(r.capture(directory/'PREPARE_EXIT.json',20000));observed_child(prep['child'])
        need(prep['terminal']['admission']==closed['input_admission'] and prep['terminal']['case']==case
             and prep['terminal']['condition']=='JPEG-RGB-1')
        a=r.parse(r.capture(workspace/'ADMISSION.json',65536,closed['input_admission']))
        nimages=8020 if case.startswith('sub-01_') else 7300
        need(a['case']==case and a['condition']=='JPEG-RGB-1' and a['status']=='input_prepared'
             and a['source_sha256']==source_binding['pins']['SOURCE_MANIFEST.json']['sha256']
             and a['binding']==snapshots['BINDINGS.json'] and a['images']==nimages and a['full_case_file_count']==nimages+10
             and a['array_files']==6 and a['candidate_executions']==0 and a['scientific_fits_or_scores']==0
             and a['mount']=={'source':str(workspace/'current'),'destination':'/case','read_only':True})
        retired=r.parse(r.capture(workspace/'RETIREMENT.json',65536,closed['retirement']));observed_child(closed['retirement_child'])
        need(retired['admission']==closed['input_admission'] and retired['case']==case and retired['current_absent'] is True)
        raw=r.capture(attempt/'captured'/(case+'.npy'),SCORE_CAP,closed['score']);funcs.load_array(raw,(1540,3700));outputs[case]={'file':case+'.npy','sha256':pin(raw)['sha256']};del raw
        closures.append(row)
        expected_dirs.update({'records/'+case,'workspaces/'+case})
        expected_files.update('records/'+case+'/'+n for n in ('INTENT-volume.json','INTENT-holder.json','INTENT-candidate.json','PREPARE_EXIT.json','EXECUTION.json','CLOSED.json'))
        expected_files.update('workspaces/'+case+'/'+n for n in ('LEASE.json','ENVELOPE.json','RESERVATION.json','PROCESS.json','HOST.json','WORKER.json','INVENTORY.json','ADMISSION.json','RETIREMENT.json'))
    need({p.name for p in (attempt/'captured').iterdir()}=={'submission.json',*(x+'.npy' for x in CASES)})
    submission=r.parse(r.capture(attempt/'captured/submission.json',10000,done['submission']))
    need(submission=={'schema':'neural051-scores-v1','roster_sha256':funcs.roster_digest(roster),'files':outputs})
    actual_files=set();actual_dirs=set();need(footprint(attempt)<=RETAINED)
    for parent,dirs,files in os.walk(attempt,followlinks=False):
        for name in dirs:actual_dirs.add(str((Path(parent)/name).relative_to(attempt)))
        for name in files:actual_files.add(str((Path(parent)/name).relative_to(attempt)))
    need(actual_files==expected_files and actual_dirs==expected_dirs)
    return {'completion':completion_pin,'submission':done['submission'],'cases':closures,'program':c['program'],'condition':'JPEG-RGB-1','outputs':7}

def observed_child(v):
    need(v['natural_exit'] is True and v['process_reaped'] is True and v['streams_closed'] is True
         and v['timed_out'] is False and type(v['exit_code']) is int and v['exit_code']==0 and v['error_type'] is None)

def supervise(repo,commit,commit_pin,source_pin,output,other,socket):
    start=time.monotonic();e=dependencies(repo);bodies=sources(source_pin);c,program=commit_read(e,commit,commit_pin,source_pin)
    limit=6*(2000+c['candidate_seconds']+420+300+100)+240;end=start+limit
    need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0));old=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('whole supervisor')))
    signal.setitimer(signal.ITIMER_REAL,limit);output=e.r.path(output);need(not os.path.lexists(output));w=Writer(output,other);owned=False
    try:
        need(output!=e.repo and e.repo not in output.parents and output not in e.repo.parents)
        w.mkdir(output);owned=True;source=output/'source';w.mkdir(source,0o755)
        for n,b in bodies.items():w.bytes(source/n,b,200000)
        w.bytes(source/'SOURCE_MANIFEST.json',capture(HERE/'SOURCE_MANIFEST.json',source_pin,100000),100000);source.chmod(0o555)
        w.json(output/'INTENT.json',{'schema':'neural051_supervisor_intent_v1','source_manifest':source_pin,'commit':commit_pin,
            'program':c['program'],'condition':'JPEG-RGB-1','cases':list(CASES),'whole_seconds':limit,'future_bytes':FUTURE,
            'other_reserved_bytes':other,'private_scoring_called':False},10000)
        need(footprint(output)<=2_000_000)
        argv=[str(Path(sys.executable).resolve()),'-I','-B',str(source/'dispatch.py'),'worker','--repo',str(e.repo),
              '--source-pin',json.dumps(source_pin),'--commit',str(e.r.path(commit)),'--commit-pin',json.dumps(commit_pin),
              '--output',str(output/'attempt'),'--other-reserved-bytes',str(other+2_000_000),'--docker-socket',str(e.r.path(socket))]
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
        raw,child=e.ch.child(argv,end-10,env);terminal=e.r.parse(raw);observed_child(child)
        need(set(terminal)=={'status','completion','outputs'} and terminal['status']=='closed' and terminal['outputs']==7)
        joined=closed_panel(e,output/'attempt',c,commit_pin,source_pin,terminal['completion'])
        need(time.monotonic()<end and footprint(output)<=RETAINED+2_000_000)
        receipt={'schema':'neural051_dispatch_host_exit_v1','status':'closed','source_manifest':source_pin,'commit':commit_pin,
                 'child':child,'whole_seconds':limit,'seconds_before_publication':time.monotonic()-start,
                 'private_scoring_called':False,'runtime_qualified':False,**joined}
        hp=w.json(output/'HOST_EXIT.json',receipt,30000);need(time.monotonic()<end)
        return {'status':'closed','host_exit':hp,'submission':str(output/'attempt/captured/submission.json'),'condition':'JPEG-RGB-1','outputs':7}
    except BaseException as exc:
        if owned:
            value={'status':'failed','error_type':type(exc).__name__,'resource_recovery_may_be_required':True,'automatic_retry':False}
            if isinstance(exc,e.ch.ChildFailure):value['child']=exc.record
            try:w.json(output/'FAILURE.json',value,20000)
            except BaseException:pass
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def admit(repo,commit,commit_pin,source_pin,output,host_pin):
    """Trusted operator supplies pin only after natural enclosing CLI zero."""
    e=dependencies(repo);bodies=sources(source_pin);c,_=commit_read(e,commit,commit_pin,source_pin)
    output=e.r.path(output);need(not os.path.lexists(output/'FAILURE.json'))
    host=e.r.parse(e.r.capture(output/'HOST_EXIT.json',30000,host_pin));observed_child(host['child'])
    need(host['schema']=='neural051_dispatch_host_exit_v1' and host['status']=='closed'
         and host['source_manifest']==source_pin and host['commit']==commit_pin and host['program']==c['program']
         and host['condition']=='JPEG-RGB-1' and host['private_scoring_called'] is False
         and host['runtime_qualified'] is False and host['outputs']==7
         and host['whole_seconds']==6*(2000+c['candidate_seconds']+420+300+100)+240
         and 0<=host['seconds_before_publication']<=host['whole_seconds'])
    joined=closed_panel(e,output/'attempt',c,commit_pin,source_pin,host['completion'])
    for name,value in joined.items():need(host[name]==value)
    intent=e.r.parse(e.r.capture(output/'INTENT.json',10000))
    need(intent['schema']=='neural051_supervisor_intent_v1' and intent['source_manifest']==source_pin
         and intent['commit']==commit_pin and intent['program']==c['program'] and intent['condition']=='JPEG-RGB-1'
         and intent['cases']==list(CASES) and intent['whole_seconds']==host['whole_seconds'] and intent['private_scoring_called'] is False)
    for name,body in bodies.items():e.r.capture(output/'source'/name,200000,pin(body))
    e.r.capture(output/'source/SOURCE_MANIFEST.json',100000,source_pin)
    need({p.name for p in output.iterdir()}=={'source','attempt','INTENT.json','HOST_EXIT.json'})
    return {'status':'admitted_for_separate_grading','submission':str(output/'attempt/captured/submission.json'),
            'condition':'JPEG-RGB-1','runtime_qualified':False,'grading_performed':False}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    for name in ('freeze','run','worker','retire-child','admit'):
        a=sub.add_parser(name);a.add_argument('--repo',required=True);a.add_argument('--source-pin',required=True)
        if name!='admit':a.add_argument('--other-reserved-bytes',required=True,type=int)
        if name=='freeze':
            a.add_argument('--program',required=True);a.add_argument('--destination',required=True);a.add_argument('--candidate-seconds',required=True,type=int);a.add_argument('--memory-bytes',required=True,type=int);a.add_argument('--exposure-declaration',required=True)
        elif name in ('run','worker','admit'):
            a.add_argument('--commit',required=True);a.add_argument('--commit-pin',required=True);a.add_argument('--output',required=True)
            if name!='admit':a.add_argument('--docker-socket',required=True)
            if name=='admit':a.add_argument('--host-pin',required=True)
        else:
            for k in ('workspace','execution','execution-pin','admission-pin','snapshot'):a.add_argument('--'+k,required=True)
    a=p.parse_args();sp=json.loads(a.source_pin)
    try:
        if a.action=='freeze':value=freeze(a.repo,a.program,a.destination,a.candidate_seconds,a.memory_bytes,a.exposure_declaration,sp,a.other_reserved_bytes)
        elif a.action=='worker':value=worker(a.repo,a.commit,json.loads(a.commit_pin),sp,a.output,a.other_reserved_bytes,a.docker_socket)
        elif a.action=='run':value=supervise(a.repo,a.commit,json.loads(a.commit_pin),sp,a.output,a.other_reserved_bytes,a.docker_socket)
        elif a.action=='admit':value=admit(a.repo,a.commit,json.loads(a.commit_pin),sp,a.output,json.loads(a.host_pin))
        else:
            e=dependencies(a.repo);sources(sp)
            value={'status':'retired','retirement':retire_child(e,Path(a.workspace),json.loads(a.admission_pin),Path(a.execution),json.loads(a.execution_pin),a.other_reserved_bytes,Path(a.snapshot))}
        print(json.dumps(value,separators=(',',':')));return 0
    except BaseException as exc:print(json.dumps({'status':'failed','error_type':type(exc).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())
