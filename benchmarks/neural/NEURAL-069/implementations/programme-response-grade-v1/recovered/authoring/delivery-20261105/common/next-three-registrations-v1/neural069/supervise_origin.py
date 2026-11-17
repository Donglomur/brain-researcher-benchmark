"""Commit a program or observe the real NEURAL069 executor and closed outputs.
No grader is imported. Command exit0 and returned receipt pin are both required.
"""
import argparse,hashlib,json,os,re,shutil,signal,stat,sys,time,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNTIME_SHA='0797676d819c7f59f8d17374fa99eaae5b3b60df04f157410216cad9cd3ab224'
def boot():
    p=HERE/'runtime.py';fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as f:
        s=os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=14052:raise ValueError('Frozen runtime extent')
        b=f.read(14053)
    if hashlib.sha256(b).hexdigest()!=RUNTIME_SHA:raise ValueError('Frozen runtime source')
    m=types.ModuleType('neural069_runtime');m.__file__=str(p);exec(compile(b,str(p),'exec'),m.__dict__);return m
r=boot();need=r.need;pin=r.pin;encoded=r.encoded;parse=r.parse;capture=r.capture;path=r.path
WRITE=None
def save(p,b,cap=1000000):
    need(WRITE is not None,'Configured preventive write budget');return WRITE.save(p,b,cap)
TOTAL_CAP=20000000

def module(raw,name,filename):
    m=types.ModuleType(name);m.__file__=str(filename);exec(compile(raw,str(filename),'exec'),m.__dict__);return m

def source(expected):
    b=capture(HERE/'SOURCE_MANIFEST.json',40000,expected);v=parse(b)
    need(v['schema']=='neural069_transport_source_v1'and set(v['runtime_files'])=={'runtime.py','child.py','holder.py','entry.py','executor.py','supervise.py','LOCK.json'},'Runtime closure')
    bodies={n:capture(HERE/n,150000,p)for n,p in v['runtime_files'].items()}
    need(pin(bodies['runtime.py'])['sha256']==RUNTIME_SHA,'Runtime root');return bodies,b

def inventory(root,cap=TOTAL_CAP):
    todo=[root];files={};dirs=set();usage=0;seen=0
    while todo:
        p=todo.pop();s=p.lstat();seen+=1;need(seen<=140,'Bounded total inventory');usage+=max(s.st_size,s.st_blocks*512);need(usage<=cap,'Total allocated cap')
        if stat.S_ISDIR(s.st_mode):
            dirs.add(str(p.relative_to(root)))
            with os.scandir(p)as scan:
                for x in scan:need(seen+len(todo)<140,'Bounded enumeration');todo.append(p/x.name)
        else:need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'Ordinary owned file');files[str(p.relative_to(root))]=s.st_size
    return files,dirs,usage

def freeze(program,dest,seconds,memory,source_pin,other):
    global WRITE
    start=time.monotonic();bodies,_=source(source_pin);lock=parse(bodies['LOCK.json']);dest=path(dest);need(not os.path.lexists(dest)and dest.parent.is_dir(),'Fresh commitment')
    need(type(other)is int and other>=0,'Other reservation');need(shutil.disk_usage(dest.parent).free>=r.FLOOR+other+300000,'Source commitment floor')
    need(type(seconds)is int and 1<=seconds<=7200 and type(memory)is int and 536870912<=memory<=4294967296,'Explicit fixed prospective resources')
    raw=capture(program,131072);raw.decode('utf-8')
    c={'schema':'neural069_program_commit_v1','task_id':'NEURAL-069','program':pin(raw),'source_manifest':source_pin,'lock':pin(bodies['LOCK.json']),'image':r.IMAGE,'candidate_seconds':seconds,'memory_bytes':memory,'cpu':1,'full_cases':[x['id']for x in lock['cases']]}
    WRITE=r.WriteBudget(dest,other,300000);WRITE.mkdir(dest);save(dest/'program.py',raw,131072);cp=save(dest/'COMMIT.json',encoded(c),10000);syncdir(dest);need(time.monotonic()-start<30,'Commitment deadline');return {'status':'committed','commit':cp,'program':c['program']}

def syncdir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def closed_files(output,c,commit_pin,source_pin,bodies):
    """No private callback exists. Reject all incomplete joins before handoff."""
    lock=parse(bodies['LOCK.json']);h=module(bodies['holder.py'],'closed_holder',output/'source/holder.py');attempt=output/'attempt'
    f,dirs,allocated=inventory(output)
    need(dirs=={'.','source','attempt','attempt/snapshot','attempt/captured'},'Exact successful directories')
    done_raw=capture(attempt/'COMPLETE.json',4096);done=parse(done_raw);execution_raw=capture(attempt/'EXECUTION.json',100000,done['execution']);x=parse(execution_raw)
    need(done['schema']=='neural069_executor_complete_v1'and done['outputs']==81 and done['private_scoring_called']is False and done['limit_seconds']==c['candidate_seconds']+420 and 0<=done['worker_seconds']<=done['limit_seconds'],'Complete worker evidence')
    need(x['schema']=='neural069_program_execution_v1'and x['status']=='captured'and x['program']==c['program']and x['commit']==commit_pin and x['source_manifest']==source_pin and x['lock']==pin(bodies['LOCK.json'])and x['image']==r.IMAGE and x['full_cases']==c['full_cases'],'Execution commitment joins')
    need(x['candidate_seconds']==c['candidate_seconds']and x['memory_bytes']==c['memory_bytes']and 0<=x['observed_candidate_seconds']<=c['candidate_seconds'],'Bound candidate resources')
    need(x['candidate_started']is True and x['candidate_closed_before_capture']is True and x['all_resources_closed']is True and x['cli_reaped']is True and x['private_scoring_called']is False and x['error_type']is None,'Producer and resource closure')
    need(x['natural_exit']=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'Observed natural nonOOM zero')
    inp_raw=capture(attempt/'INPUT.json',10000,x['input_binding']);inp=parse(inp_raw);need(done['input']==x['input_binding']and inp['commit']==commit_pin and inp['source_manifest']==source_pin,'Input/source join')
    public={'files':101,'bytes':lock['public_bytes'],'lock':pin(bodies['LOCK.json'])};need(inp['public_pre_pin']==x['public_post_pin']==public,'Full immutable public input checks')
    snapshots={'program.py':c['program'],**{n:pin(bodies[n])for n in ('holder.py','entry.py','LOCK.json')}};need(inp['snapshot']==snapshots,'Exact candidate source snapshot')
    for n,p in snapshots.items():capture(attempt/'snapshot'/n,150000,p)
    need(len(x['closures'])==3,'All three closures');prefix=None;intents={}
    for role,kind in (('volume','volume'),('holder','container'),('candidate','container')):
        raw=capture(attempt/f'INTENT-{role}.json',4096);v=parse(raw);match=re.fullmatch('neural069-([a-f0-9]{24})-'+role,v['name']);need(match is not None,'Owned name');p='neural069-'+match.group(1);need(prefix in (None,p)and v['owner']==p+'/'+role and v['kind']==kind and v['attempted']is False and v['acknowledged']is False,'Durable precreate intent');prefix=p
        rows=[z for z in x['closures']if z.get('name')==v['name']];need(len(rows)==1,'Exact closure identity');z=rows[0]
        need(z['kind']==kind and z['removed']is True and z['absence_observed']is True and z['creation_outcome_unknown']is False and z['closed']is True,'Observed removal/absence, no unknown create');intents[role]=pin(raw)
    raw=capture(attempt/'captured/submission.json',100000);rows=h.records(raw,lock);outputs=[{'path':'submission.json',**pin(raw)},*[{k:v[k]for k in ('path','bytes','sha256')}for v in rows]]
    need(x['outputs']==outputs,'Captured exact81 descriptors')
    for row in outputs:capture(attempt/'captured'/row['path'],524288,{k:row[k]for k in ('bytes','sha256')})
    capture(output/'source/SOURCE_MANIFEST.json',40000,source_pin)
    intent=parse(capture(output/'INTENT.json',10000));need(intent['schema']=='neural069_supervisor_intent_v1'and intent['source_manifest']==source_pin and intent['commit']==commit_pin and intent['attempt']==str(attempt)and intent['image']==r.IMAGE and intent['whole_seconds']==c['candidate_seconds']+480 and intent['private_scoring_called']is False and inp['package']==intent['package'],'Parent intent join')
    sources={n:pin(b)for n,b in bodies.items()}
    for n,p in sources.items():capture(output/'source'/n,150000,p)
    expected={'INTENT.json','source/SOURCE_MANIFEST.json',*('source/'+n for n in bodies),'attempt/INPUT.json','attempt/EXECUTION.json','attempt/COMPLETE.json',*('attempt/INTENT-'+role+'.json'for role in ('volume','holder','candidate')),*('attempt/snapshot/'+n for n in snapshots),*('attempt/captured/'+row['path']for row in outputs)}
    need(set(f)in(expected,expected|{'HOST_EXIT.pending.json'},expected|{'HOST_EXIT.json'}),'No failure, extra or missing file')
    return {'execution':pin(execution_raw),'completion':pin(done_raw),'input':pin(inp_raw),'creation_intents':intents,'outputs':outputs,'allocated_bytes':allocated}

def supervise(package,commit,commit_pin,source_pin,output,other,socket,*,started):
    global WRITE
    start=started;need(type(start)in(int,float)and 0<=start<=time.monotonic()<start+60,'Original startup deadline');record={'status':'failed','resource_recovery_may_be_required':False};owned=None;end=None;committed=False
    previous=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Supervisor bound')));timer=signal.setitimer(signal.ITIMER_REAL,max(.001,start+60-time.monotonic()))
    try:
        need(timer==(0.0,0.0),'Standalone supervisor');output=path(output);need(not os.path.lexists(output)and output.parent.is_dir(),'Fresh output');need(type(other)is int and other>=0,'Explicit other reservation')
        need(shutil.disk_usage(output.parent).free>=r.FLOOR+other+TOTAL_CAP,'Full future capacity')
        bodies,mraw=source(source_pin);e=module(bodies['executor.py'],'source_executor',HERE/'executor.py');lock=parse(bodies['LOCK.json']);c,_=e.commitment(path(commit),commit_pin,source_pin,lock);end=start+c['candidate_seconds']+480
        signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()));WRITE=r.WriteBudget(output,other,TOTAL_CAP);WRITE.mkdir(output);owned=output;src=output/'source';WRITE.mkdir(src,0o755)
        for n,b in {**bodies,'SOURCE_MANIFEST.json':mraw}.items():save(src/n,b,150000)
        src.chmod(0o555);syncdir(src);attempt=output/'attempt'
        intent={'schema':'neural069_supervisor_intent_v1','source_manifest':source_pin,'commit':commit_pin,'package':str(path(package)),'attempt':str(attempt),'image':r.IMAGE,'whole_seconds':c['candidate_seconds']+480,'private_scoring_called':False}
        save(output/'INTENT.json',encoded(intent),10000);syncdir(output)
        argv=[str(Path(sys.executable).resolve()),'-I','-B',str(src/'executor.py'),'--package',str(path(package)),'--commit',str(path(commit)),'--commit-bytes',str(commit_pin['bytes']),'--commit-sha256',commit_pin['sha256'],'--source-bytes',str(source_pin['bytes']),'--source-sha256',source_pin['sha256'],'--attempt',str(attempt),'--other-reserve-bytes',str(other),'--docker-socket',str(path(socket))]
        ch=module(bodies['child.py'],'trusted_child',src/'child.py');env={k:v for k,v in os.environ.items()if k not in ('DOCKER_HOST','DOCKER_CONTEXT','PYTHONPATH','PYTHONHOME')};record['resource_recovery_may_be_required']=True
        try:raw,child=ch.child(argv,end-10,env)
        except ch.ChildFailure as error:record['child']=error.record;raise
        record['child']=child;terminal=parse(raw);need(type(terminal)is dict and set(terminal)=={'status','completion','outputs'}and terminal['status']=='captured'and terminal['outputs']==81,'Exact executor terminal')
        joined=closed_files(output,c,commit_pin,source_pin,bodies);need(terminal['completion']==joined['completion'],'Observed child terminal joins')
        receipt={'schema':'neural069_host_exit_v1','status':'closed','source_manifest':source_pin,'commit':commit_pin,'program':c['program'],'image':r.IMAGE,'attempt':str(attempt),'child':child,'host_seconds_before_receipt':time.monotonic()-start,'whole_seconds':c['candidate_seconds']+480,'private_scoring_called':False,**joined}
        pending=output/'HOST_EXIT.pending.json';fp=save(pending,encoded(receipt),40000);inventory(output);need(time.monotonic()<end and shutil.disk_usage(output).free>=r.FLOOR+other+TOTAL_CAP,'Final enclosing bounds');need(not os.path.lexists(output/'HOST_EXIT.json'),'Fresh receipt')
        os.rename(pending,output/'HOST_EXIT.json');syncdir(output);committed=True;return {'status':'closed','receipt':fp,'outputs':81,'worker_natural_exit':True}
    except BaseException as error:
        record['error_type']=type(error).__name__
        if owned is not None and not committed:
            try:save(owned/'FAILURE.json',encoded(record),10000)
            except BaseException:pass
        raise
    finally:
        WRITE=None;signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        if timer!=(0.0,0.0):signal.setitimer(signal.ITIMER_REAL,*timer)

def admit_closed(output,receipt_pin,commit,commit_pin,source_pin):
    """Trusted operator receipt required; never treat candidate assertions as exit.
Return the captured artifact directory only. Unchanged grade.py is separate.
"""
    output=path(output);bodies,_=source(source_pin);lock=parse(bodies['LOCK.json']);e=module(bodies['executor.py'],'admit_executor',HERE/'executor.py');c,_=e.commitment(path(commit),commit_pin,source_pin,lock)
    receipt=parse(capture(output/'HOST_EXIT.json',40000,receipt_pin));need(receipt['schema']=='neural069_host_exit_v1'and receipt['status']=='closed'and receipt['source_manifest']==source_pin and receipt['commit']==commit_pin and receipt['program']==c['program']and receipt['image']==r.IMAGE and receipt['attempt']==str(output/'attempt')and receipt['private_scoring_called']is False,'Trusted operator receipt bindings')
    v=receipt['child'];need(v['natural_exit']is True and v['process_reaped']is True and v['streams_closed']is True and v['timed_out']is False and v['exit_code']==0 and type(v['exit_code'])is int and v['error_type']is None,'Observed executor natural exit')
    need(receipt['whole_seconds']==c['candidate_seconds']+480 and 0<=receipt['host_seconds_before_receipt']<=receipt['whole_seconds'],'Enclosing resource bound')
    joined=closed_files(output,c,commit_pin,source_pin,bodies)
    for key,value in joined.items():
        if key!='allocated_bytes':need(receipt[key]==value,'Complete external receipt join')
    return output/'attempt/captured/submission.json'

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('freeze');a.add_argument('--program',required=True,type=Path);a.add_argument('--destination',required=True,type=Path);a.add_argument('--candidate-seconds',required=True,type=int);a.add_argument('--memory-bytes',required=True,type=int);a.add_argument('--other-reserve-bytes',required=True,type=int)
    b=sub.add_parser('run');b.add_argument('--package',required=True,type=Path);b.add_argument('--output',required=True,type=Path);b.add_argument('--other-reserve-bytes',required=True,type=int);b.add_argument('--docker-socket',required=True,type=Path)
    c=sub.add_parser('admit');c.add_argument('--output',required=True,type=Path);c.add_argument('--receipt-bytes',required=True,type=int);c.add_argument('--receipt-sha256',required=True)
    for q in (a,b,c):q.add_argument('--source-bytes',required=True,type=int);q.add_argument('--source-sha256',required=True)
    for q in (b,c):q.add_argument('--commit',required=True,type=Path);q.add_argument('--commit-bytes',required=True,type=int);q.add_argument('--commit-sha256',required=True)
    z=p.parse_args();sp={'bytes':z.source_bytes,'sha256':z.source_sha256}
    try:
        if z.action=='freeze':v=freeze(z.program,z.destination,z.candidate_seconds,z.memory_bytes,sp,z.other_reserve_bytes)
        else:
            cp={'bytes':z.commit_bytes,'sha256':z.commit_sha256}
            if z.action=='run':v=supervise(z.package,z.commit,cp,sp,z.output,z.other_reserve_bytes,z.docker_socket)
            else:v={'status':'admitted_for_separate_artifact_grading','submission':str(admit_closed(z.output,{'bytes':z.receipt_bytes,'sha256':z.receipt_sha256},z.commit,cp,sp)),'grading_performed':False}
        print(json.dumps(v,separators=(',',':')));return 0
    except BaseException as e:print(json.dumps({'status':'failed','error_type':type(e).__name__}));return 2
if __name__=='__main__':sys.exit(main())
