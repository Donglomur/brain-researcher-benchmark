"""Task-specific NEURAL075 program invocation; authentic execution unselected."""
import argparse,ast,base64,hashlib,json,math,os,re,shutil,signal,stat,struct,sys,time,types,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCK_PIN={'bytes': 9275, 'sha256': '43c17afb9c995180292158fadbd8efa4ee4935b13215edadb2b6517b6a0dee07'}
CASES=tuple(['Subject1/neural/imagery', 'Subject1/neural/perception', 'Subject1/no_neural/imagery', 'Subject1/no_neural/perception', 'Subject1/training_permuted/imagery', 'Subject1/training_permuted/perception', 'Subject2/neural/imagery', 'Subject2/neural/perception', 'Subject2/no_neural/imagery', 'Subject2/no_neural/perception', 'Subject2/training_permuted/imagery', 'Subject2/training_permuted/perception', 'Subject3/neural/imagery', 'Subject3/neural/perception', 'Subject3/no_neural/imagery', 'Subject3/no_neural/perception', 'Subject3/training_permuted/imagery', 'Subject3/training_permuted/perception', 'Subject4/neural/imagery', 'Subject4/neural/perception', 'Subject4/no_neural/imagery', 'Subject4/no_neural/perception', 'Subject4/training_permuted/imagery', 'Subject4/training_permuted/perception', 'Subject5/neural/imagery', 'Subject5/neural/perception', 'Subject5/no_neural/imagery', 'Subject5/no_neural/perception', 'Subject5/training_permuted/imagery', 'Subject5/training_permuted/perception'])
CONDITION='full5_native_VC_cnn7_instructed_category_development'
FILES={'invoke.py','entry.py','holder.py','panel.py','stage.py','LOCK.json'}
CHUNK=4*1024**2

def need(ok):
    if not ok:raise ValueError('NEURAL075 invocation boundary')
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def path(p):
    p=Path(p).absolute();need('..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)));return p
def capture(p,expected=None,cap=100000):
    p=path(p);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap)
        b=f.read(a.st_size+1);z=os.fstat(f.fileno());n=p.lstat()
    need(all(getattr(a,k)==getattr(z,k)==getattr(n,k)for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')) and len(b)==a.st_size)
    need(expected is None or pin(b)=={k:expected[k]for k in ('bytes','sha256')});return b

def module(raw,name,filename):
    m=types.ModuleType(name);m.__file__=str(filename);exec(compile(raw,str(filename),'exec'),m.__dict__);return m

def dependencies(repo):
    repo=path(repo);lock=json.loads(capture(HERE/'LOCK.json',LOCK_PIN))
    need(lock['task_id']=='NEURAL-075' and lock['condition']==CONDITION and lock['cases']==list(CASES))
    def get(name):
        p=lock['pins'][name];return capture(repo/p['path'],p,600000)
    tree=ast.parse(get('transport'));docker=ast.parse(get('docker'))
    old=[x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Docker']
    new=[x for x in docker.body if isinstance(x,ast.ClassDef) and x.name=='Docker'];need(len(old)==len(new)==1)
    tree.body[tree.body.index(old[0])]=new[0]
    class Constants(ast.NodeTransformer):
        def visit_Constant(self,n):
            changes={524288:4194304,'fsize=524288:524288':'fsize=4194304:4194304','neural069-[a-f0-9]{24}-volume':'neural075-[a-f0-9]{24}-volume'}
            if type(n.value) in (int,str) and n.value in changes:return ast.copy_location(ast.Constant(changes[n.value]),n)
            return n
    tree=Constants().visit(tree);ast.fix_missing_locations(tree);r=types.ModuleType('pinned075_transport')
    exec(compile(tree,'<039 transport with exact repaired Slice Docker and075 constants>','exec'),r.__dict__)
    r.LABEL='org.neurobench.neural075-program-owner';r.VOLUME_BYTES=16*1024**2;r.VOLUME_OPTIONS='size=16777216,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
    ch=module(get('child'),'pinned075_child',repo/lock['pins']['child']['path'])
    tree=ast.parse(get('lifecycle'));nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'case_lifecycle','lifecycle_closed'}];need(len(nodes)==2)
    class Names(ast.NodeTransformer):
        def visit_Constant(self,n):
            if type(n.value)is str and 'neural051' in n.value:return ast.copy_location(ast.Constant(n.value.replace('neural051','neural075')),n)
            return n
    body=Names().visit(ast.Module(nodes,[]));ast.fix_missing_locations(body)
    ns={'time':time,'uuid':uuid,'re':re,'need':need,'capture_output':capture_output};exec(compile(body,'<051 lifecycle with075 namespace>','exec'),ns)
    return types.SimpleNamespace(repo=repo,lock=lock,get=get,r=r,ch=ch,life=ns['case_lifecycle'],closed=ns['lifecycle_closed'])

def source(expected):
    raw=capture(HERE/'SOURCE_MANIFEST.json',expected);m=json.loads(raw)
    need(m['schema']=='neural075_invocation_source_v1' and set(m['runtime_files'])==FILES)
    bodies={n:capture(HERE/n,p,100000) for n,p in m['runtime_files'].items()};need(pin(bodies['LOCK.json'])==LOCK_PIN)
    return bodies,raw

def tree_names(root,limit=100):
    root=path(root);need(root.is_dir());files=set();dirs=set();todo=[root];used=0;count=0
    while todo:
        p=todo.pop();s=p.lstat();count+=1;need(count<=limit);used+=max(s.st_size,s.st_blocks*512)
        if stat.S_ISDIR(s.st_mode):
            if p!=root:dirs.add(p.relative_to(root).as_posix())
            with os.scandir(p)as scan:
                for x in scan:need(count+len(todo)<limit);todo.append(p/x.name)
        else:need(stat.S_ISREG(s.st_mode)and s.st_nlink==1);files.add(p.relative_to(root).as_posix())
    return files,dirs,used

def syncdir(p):
    fd=os.open(path(p),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def arm_remaining(end):
    left=end-time.monotonic();need(left>0);signal.setitimer(signal.ITIMER_REAL,left)

def timed_call(function,limit,*args):
    start=time.monotonic();need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.))
    old=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()))
    try:
        arm_remaining(start+limit)
        value=function(*args,_start=start)
        need(time.monotonic()<start+limit);return value
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        finally:signal.signal(signal.SIGALRM,old)

class Writer:
    def __init__(self,e,root,other,cap):self.e=e;self.root=path(root);self.other=other;self.cap=cap;self.written=0;need(type(other)is int and other>=0)
    def guard(self,n=0):
        need(type(n)is int and n>=0 and self.written+n<=self.cap)
        need(shutil.disk_usage(self.root.parent).free>=21474836480+self.other+self.cap)
        used=tree_names(self.root,2000)[2]if self.root.exists()else 0;need(used+((n+65535)//65536+1)*65536<=self.cap)
    def mkdir(self,p,mode=0o700):self.guard(65536);p=path(p);need(p==self.root or self.root in p.parents);p.mkdir(mode=mode);self.written+=65536;syncdir(p.parent)
    def bytes(self,p,b,cap=100000):
        p=path(p);need(self.root in p.parents and len(b)<=cap);self.guard(len(b));v=self.e.r.save(p,b,cap);self.written+=len(b);syncdir(p.parent);return v
    def json(self,p,v,cap=100000):return self.bytes(p,encoded(v),cap)

def read_commit(e,directory,expected,sp):
    c=e.r.parse(capture(path(directory)/'COMMIT.json',expected,10000))
    need(set(c)=={'schema','condition','program','source','lock','image','cases','seconds','memory','exposure','access','collection_manifest'})
    need(c['access'] in ('A','B') and c['collection_manifest']==e.lock['collection_manifest']);need(c['schema']=='neural075_program_commit_v1' and c['condition']==CONDITION and c['source']==sp and c['lock']==LOCK_PIN and c['image']==e.r.IMAGE and c['cases']==list(CASES))
    need(type(c['seconds'])is int and 1<=c['seconds']<=7200 and type(c['memory'])is int and 536870912<=c['memory']<=4294967296 and type(c['exposure'])is str and 0<len(c['exposure'])<=4096)
    b=capture(path(directory)/'program.py',c['program'],131072);b.decode('utf-8');return c,b

def freeze(*args):return timed_call(_freeze,30,*args)
def _freeze(repo,sp,program,out,seconds,memory,exposure,other,access,*,_start):
    e=dependencies(repo);source(sp);need(access in ('A','B'));b=capture(program,cap=131072);b.decode('utf-8')
    need(type(seconds)is int and 1<=seconds<=7200 and type(memory)is int and 536870912<=memory<=4294967296 and type(exposure)is str and 0<len(exposure)<=4096)
    out=path(out);need(not os.path.lexists(out));w=Writer(e,out,other,1000000);w.mkdir(out)
    c={'schema':'neural075_program_commit_v1','condition':CONDITION,'program':pin(b),'source':sp,'lock':LOCK_PIN,'image':e.r.IMAGE,'cases':list(CASES),'seconds':seconds,'memory':memory,'exposure':exposure,'access':access,'collection_manifest':e.lock['collection_manifest']}
    w.bytes(out/'program.py',b,131072);cp=w.json(out/'COMMIT.json',c);return {'status':'committed','commit':cp}

def view_admit(e,case,view,identity_pin,readable=False):
    need(case in CASES);view=path(view);files,dirs,used=tree_names(view,40)
    raw=capture(view/'INPUT_IDENTITY.json',identity_pin,30000);i=e.r.parse(raw)
    need(set(i)=={'schema','case_id','access','files','context_pin'} and i['schema']=='neural075_input_identity_v1' and i['case_id']==case and i['access'] in ('A','B'))
    expected={'case.json','inputs.npz',*e.lock['public_files']}
    if i['access']=='B':expected|={'author_code/'+n for n in e.lock['author_files']}
    need(files==expected|{'INPUT_IDENTITY.json'} and dirs==({'public','author_code'} if i['access']=='B' else {'public'}) and used<=210000000 and set(i['files'])==expected)
    if readable:
        need(all((p.stat().st_mode & 0o005)==0o005 for p in [view,*(view/n for n in dirs)]))
        need(all((view/n).stat().st_mode & 0o004 for n in files))
    need(all(i['files'][n]==p for n,p in e.lock['public_files'].items()))
    if i['access']=='B':need(all(i['files']['author_code/'+n]==p for n,p in e.lock['author_files'].items()))
    raw_context=capture(view/'case.json',i['context_pin'],2**20);c=e.r.parse(raw_context)
    need(set(c)=={'protocol','case_id','person','arm','phase','categories','trial_ids','design_sha256','inputs','n_units','access_condition'})
    need(c['protocol']=='neural075-v1' and c['case_id']==case and '/'.join(c[k]for k in ('person','arm','phase'))==case and c['access_condition']==i['access'] and c['design_sha256']==e.lock['design']['sha256'] and c['n_units']==1000)
    need(type(c['categories'])is list and len(c['categories'])==len(set(c['categories']))==50 and all(type(x)is str and re.fullmatch('n[0-9]{8}',x)for x in c['categories']))
    need(type(c['trial_ids'])is list and len(c['trial_ids'])==len(set(c['trial_ids']))=={'imagery':500,'perception':1750}[c['phase']] and all(type(x)is str and re.fullmatch('q[0-9a-f]{24}',x)for x in c['trial_ids']))
    need(set(c['inputs'])=={'path','bytes','sha256'} and c['inputs']['path']=='inputs.npz' and i['files']['inputs.npz']=={k:c['inputs'][k]for k in ('bytes','sha256')} and i['files']['case.json']==i['context_pin'])
    for n,p in i['files'].items():e.r.opaque_pin(view/n,p,200000000)
    return {'case':case,'identity':identity_pin,'files':len(files),'access':i['access'],'context_pin':i['context_pin'],'context':c,'allocated_bytes':used,'input_authority':'exact protected stager and owned natural-zero child; no array decode in candidate dispatcher'}

def validate_output(value,context,context_pin):
    need(type(value)is dict and set(value)=={'protocol','case_id','context_sha256','categories','trial_ids','scores'})
    need(value['protocol']=='neural075-v1' and value['case_id']==context['case_id'] and value['context_sha256']==context_pin['sha256'] and value['categories']==context['categories'] and value['trial_ids']==context['trial_ids'])
    rows=value['scores'];need(type(rows)is list and len(rows)==len(context['trial_ids']))
    need(all(type(row)is list and len(row)==50 and all(type(v)in (int,float)and math.isfinite(v)and abs(v)<=1000000 for v in row)for row in rows))

def capture_output(e,d,keeper,end,destination,writer):
    # Reachable only after exact producer removal in the reviewed lifecycle.
    destination=Path(destination);writer.mkdir(destination);name='prediction.json';cap=4*2**20
    base=['exec',keeper['id'],'python','-I','-B','/trusted/holder.py']
    idx=e.r.parse(e.r.call(d,base+['index','--name',name],end,'output_index',4096))
    need(set(idx)=={'schema','bytes','sha256'}and idx['schema']=='neural075_output_index_v1'and type(idx['bytes'])is int and 0<idx['bytes']<=cap and re.fullmatch('[a-f0-9]{64}',idx['sha256']))
    v=e.r.parse(e.r.call(d,base+['chunk','--name',name,'--offset','0'],end,'output_chunk',6000000,15))
    need(set(v)=={'schema','offset','total_bytes','bytes','sha256','base64'}and v['schema']=='neural075_output_chunk_v1'and v['offset']==0 and v['total_bytes']==idx['bytes'])
    raw=base64.b64decode(v['base64'],validate=True);need(len(raw)==idx['bytes'] and pin(raw)=={k:v[k]for k in ('bytes','sha256')}=={k:idx[k]for k in ('bytes','sha256')})
    return {name:writer.bytes(destination/name,raw,cap)}

def output_check(e,case,directory,pins,context,context_pin):
    files,dirs,_=tree_names(directory,3);need(files=={'prediction.json'} and not dirs and set(pins)==files and context['case_id']==case)
    validate_output(e.r.parse(capture(Path(directory)/'prediction.json',pins['prediction.json'],4*2**20)),context,context_pin)

def worker(*args):return timed_call(_worker,7800,*args)
def _worker(repo,sp,commit,cp,case,view,ip,out,other,socket,*,_start):
    start=_start;e=dependencies(repo);bodies,sraw=source(sp);c,program=read_commit(e,commit,cp,sp);out=path(out);view=path(view)
    need(case in CASES and not os.path.lexists(out)and out not in view.parents and view not in out.parents)
    end=start+c['seconds']+600;arm_remaining(end)
    w=Writer(e,out,other,45000000);owned=False
    try:
        admission=view_admit(e,case,view,ip,True);need(admission['access']==c['access']);w.mkdir(out);owned=True;snapshot=out/'snapshot';w.mkdir(snapshot,0o755)
        for n,b in {**bodies,'program.py':program,'SOURCE_MANIFEST.json':sraw}.items():w.bytes(snapshot/n,b,150000)
        snapshot.chmod(0o555)
        intent=w.json(out/'INTENT.json',{'source':sp,'commit':cp,'case':case,'view':str(view),'admission':admission,'condition':CONDITION,'image':e.r.IMAGE,'seconds':c['seconds']+600,'other':other})
        d=e.r.Docker(shutil.which('docker')or'/usr/local/bin/docker',path(socket))
        lc={**c,'candidate_seconds':c['seconds'],'memory_bytes':c['memory']}
        x=e.life(e,d,snapshot,lc,view,out,out/'captured',w,min(end-60,time.monotonic()+c['seconds']+420))
        xp=w.json(out/'EXECUTION.json',x);e.closed(x);need(x['program']==c['program']and x['condition']==CONDITION)
        # Detect external source mutation; operator must hold view immutable during use.
        need(view_admit(e,case,view,ip,True)==admission);output_check(e,case,out/'captured',x['score'],admission['context'],admission['context_pin'])
        need(time.monotonic()<end)
        done={'schema':'neural075_invocation_complete_v1','status':'closed','source':sp,'commit':cp,'program':c['program'],'case':case,'condition':CONDITION,'intent':intent,'execution':xp,'outputs':x['score'],'input_identity':ip,'elapsed':time.monotonic()-start,'limit':c['seconds']+600,'grading_performed':False,'runtime_qualified':False}
        p=w.json(out/'COMPLETE.json',done);need(time.monotonic()<end);return {'status':'closed','completion':p,'case':case}
    except BaseException as exc:
        if owned:
            try:w.json(out/'FAILURE.json',{'status':'failed','error_type':type(exc).__name__,'resource_recovery_may_be_required':True,'automatic_retry':False})
            except BaseException:pass
        raise

def child_ok(v):
    need(v['natural_exit']is True and v['process_reaped']is True and v['streams_closed']is True and v['timed_out']is False and type(v['exit_code'])is int and v['exit_code']==0 and v['error_type']is None and v['process_group_absent']is True and v['timer_disable_error']is None and v['timer_restore_error']is None)

def closed_case(e,attempt,c,cp,sp,case,done_pin):
    need(not os.path.lexists(attempt/'FAILURE.json'));done=e.r.parse(capture(attempt/'COMPLETE.json',done_pin))
    need(done['schema']=='neural075_invocation_complete_v1'and done['status']=='closed'and done['source']==sp and done['commit']==cp and done['program']==c['program']and done['case']==case and done['condition']==CONDITION and done['grading_performed']is False and done['runtime_qualified']is False and 0<=done['elapsed']<=done['limit']==c['seconds']+600)
    i=e.r.parse(capture(attempt/'INTENT.json',done['intent']));need(i['source']==sp and i['commit']==cp and i['case']==case and i['condition']==CONDITION and i['admission']['identity']==done['input_identity']and i['admission']['access']==c['access'] and i['image']==e.r.IMAGE)
    x=e.r.parse(capture(attempt/'EXECUTION.json',done['execution']));e.closed(x);need(x['program']==c['program']and x['condition']==CONDITION and x['image']==e.r.IMAGE and x['score']==done['outputs']and x['limit_seconds']==c['seconds']+420)
    prefixes=set()
    for role,kind in [('volume','volume'),('holder','container'),('candidate','container')]:
        it=e.r.parse(capture(attempt/('INTENT-'+role+'.json')));need(it['kind']==kind and it['attempted']is False and it['acknowledged']is False and re.fullmatch('neural075-[a-f0-9]{24}-'+role,it['name']))
        prefix=it['name'].removesuffix('-'+role);prefixes.add(prefix);need(it['owner']==prefix+'/'+role and sum(z['name']==it['name']and z['kind']==kind for z in x['closures'])==1)
    need(len(prefixes)==1)
    bodies,sraw=source(sp)
    for n,b in {**bodies,'SOURCE_MANIFEST.json':sraw}.items():capture(attempt/'snapshot'/n,pin(b),150000)
    capture(attempt/'snapshot/program.py',c['program'],131072)
    output_check(e,case,attempt/'captured',done['outputs'],i['admission']['context'],i['admission']['context_pin'])
    f,d,_=tree_names(attempt,50);need(d=={'snapshot','captured'}and f=={'COMPLETE.json','INTENT.json','EXECUTION.json',*('INTENT-'+r+'.json'for r in ('volume','holder','candidate')),*('snapshot/'+n for n in FILES|{'SOURCE_MANIFEST.json','program.py'}),'captured/prediction.json'})
    return done

def supervise(*args):return timed_call(_supervise,7860,*args)
def _supervise(repo,sp,commit,cp,case,view,ip,out,other,socket,*,_start):
    start=_start;e=dependencies(repo);bodies,sraw=source(sp);c,_=read_commit(e,commit,cp,sp);out=path(out);view=path(view);need(case in CASES and not os.path.lexists(out)and out not in view.parents and view not in out.parents)
    limit=c['seconds']+660;end=start+limit;arm_remaining(end);w=Writer(e,out,other,48000000);w.mkdir(out);snapshot=out/'source';w.mkdir(snapshot,0o755)
    for n,b in {**bodies,'SOURCE_MANIFEST.json':sraw}.items():w.bytes(snapshot/n,b,150000)
    snapshot.chmod(0o555)
    context_raw=capture(view/'case.json',cap=2**20);w.bytes(out/'context.json',context_raw,2**20)
    try:
        argv=[str(Path(sys.executable).resolve()),'-I','-B',str(snapshot/'invoke.py'),'worker','--repo',str(e.repo),'--source-pin',json.dumps(sp),'--commit',str(path(commit)),'--commit-pin',json.dumps(cp),'--case',case,'--view',str(view),'--identity-pin',json.dumps(ip),'--output',str(out/'attempt'),'--other',str(other+3000000),'--socket',str(path(socket))]
        env={k:v for k,v in os.environ.items()if not k.startswith(('PYTHON','LD_','DYLD_'))and k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
        raw,ch=e.ch.child(argv,end-10,env);child_ok(ch);t=e.r.parse(raw);need(set(t)=={'status','completion','case'}and t['status']=='closed'and t['case']==case)
        done=closed_case(e,out/'attempt',c,cp,sp,case,t['completion']);need(time.monotonic()<end)
        hp=w.json(out/'HOST_EXIT.json',{'schema':'neural075_host_exit_v1','status':'closed','source':sp,'commit':cp,'case':case,'child':ch,'completion':t['completion'],'program':c['program'],'elapsed':time.monotonic()-start,'limit':limit,'condition':CONDITION,'grading_performed':False,'runtime_qualified':False});need(time.monotonic()<end)
        return {'status':'closed','case':case,'host_exit':hp}
    except BaseException as exc:
        v={'status':'failed','error_type':type(exc).__name__,'automatic_retry':False,'resource_recovery_may_be_required':True}
        if isinstance(exc,e.ch.ChildFailure):v['child']=exc.record
        try:w.json(out/'FAILURE.json',v)
        except BaseException:pass
        raise

def receipt(e,c,cp,sp,case,directory,hp):
    directory=path(directory);need(not os.path.lexists(directory/'FAILURE.json'))
    h=e.r.parse(capture(directory/'HOST_EXIT.json',hp));child_ok(h['child'])
    need(h['schema']=='neural075_host_exit_v1'and h['status']=='closed'and h['source']==sp and h['commit']==cp and h['case']==case and h['program']==c['program']and h['condition']==CONDITION and h['grading_performed']is False and h['runtime_qualified']is False and 0<=h['elapsed']<=h['limit']==c['seconds']+660)
    need({p.name for p in directory.iterdir()}=={'source','attempt','HOST_EXIT.json','context.json'})
    bodies,sraw=source(sp)
    need({p.name for p in (directory/'source').iterdir()}==FILES|{'SOURCE_MANIFEST.json'})
    for n,b in {**bodies,'SOURCE_MANIFEST.json':sraw}.items():capture(directory/'source'/n,pin(b),150000)
    return closed_case(e,directory/'attempt',c,cp,sp,case,h['completion'])

def collect(*args):return timed_call(_collect,600,*args)
def _collect(repo,sp,commit,cp,receipts,rp,out,other,*,_start):
    start=_start;e=dependencies(repo);source(sp);c,_=read_commit(e,commit,cp,sp)
    records=e.r.parse(capture(receipts,rp,100000));need(type(records)is list and len(records)==30 and [x['case']for x in records]==list(CASES)and all(set(x)=={'case','directory','host_exit','enclosing_natural_zero_observed'}and x['enclosing_natural_zero_observed']is True for x in records))
    need(len({str(path(x['directory']))for x in records})==30);out=path(out);need(not os.path.lexists(out));admitted=[]
    for x in records:
        need(time.monotonic()-start<600)
        d=path(x['directory']);need(out!=d and out not in d.parents and d not in out.parents);admitted.append(receipt(e,c,cp,sp,x['case'],d,x['host_exit']))
    # Complete30 and exact lifecycle admitted before final collection creation.
    w=Writer(e,out,other,160000000);w.mkdir(out);sub=out/'submission';w.mkdir(sub);rows=[];contexts=out/'contexts';w.mkdir(contexts);ci=[]
    for k,(x,done) in enumerate(zip(records,admitted)):
        need(time.monotonic()-start<600);name=f'{k:02d}.json';q=done['outputs']['prediction.json']
        w.bytes(sub/name,capture(Path(x['directory'])/'attempt/captured/prediction.json',q,4*2**20),4*2**20);rows.append(dict(case_id=x['case'],path=name,**q))
        i=e.r.parse(capture(Path(x['directory'])/'attempt/INTENT.json',done['intent']));raw=capture(Path(x['directory'])/'context.json',i['admission']['context_pin'],2**20)
        need(e.r.parse(raw)==i['admission']['context']);w.bytes(contexts/name,raw,2**20);ci.append(dict(case_id=x['case'],path=name,**pin(raw)))
    collection=w.json(sub/'collection.json',{'protocol':'neural075-v1','program':c['program'],'cases':rows},2**20)
    index=w.json(contexts/'CONTEXTS.json',{'protocol':'neural075-v1','design_sha256':e.lock['design']['sha256'],'access_condition':c['access'],'cases':ci},2**20)
    need(time.monotonic()-start<600)
    cp2=w.json(out/'COMPLETE.json',{'schema':'neural075_full30_collection_v1','source':sp,'commit':cp,'program':c['program'],'condition':CONDITION,'access':c['access'],'operator_receipts':rp,'cases':list(CASES),'collection':collection,'context_index':index,'outputs':30,'grading_performed':False,'runtime_qualified':False});need(time.monotonic()-start<600);return {'status':'collected','completion':cp2,'submission_dir':str(sub),'outputs':30}

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('freeze','run-case','worker','collect'));p.add_argument('--repo',required=True);p.add_argument('--source-pin',required=True);p.add_argument('--output',required=True);p.add_argument('--other',type=int,required=True)
    for n in ('program','commit','commit-pin','case','view','identity-pin','socket','receipts','receipts-pin','exposure'):p.add_argument('--'+n)
    p.add_argument('--seconds',type=int);p.add_argument('--memory',type=int);p.add_argument('--access',choices=('A','B'));a=p.parse_args();sp=json.loads(a.source_pin)
    try:
        if a.action=='freeze':v=freeze(a.repo,sp,a.program,a.output,a.seconds,a.memory,a.exposure,a.other,a.access)
        elif a.action=='collect':v=collect(a.repo,sp,a.commit,json.loads(a.commit_pin),a.receipts,json.loads(a.receipts_pin),a.output,a.other)
        else:v=(worker if a.action=='worker'else supervise)(a.repo,sp,a.commit,json.loads(a.commit_pin),a.case,a.view,json.loads(a.identity_pin),a.output,a.other,a.socket)
        print(json.dumps(v,separators=(',',':')));return 0
    except BaseException as exc:print(json.dumps({'status':'failed','error_type':type(exc).__name__}));return 2
if __name__=='__main__':raise SystemExit(main())
