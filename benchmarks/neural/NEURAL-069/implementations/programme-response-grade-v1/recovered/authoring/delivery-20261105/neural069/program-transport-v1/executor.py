"""NEURAL069 all80-output program executor. Source only until selected externally.
Grader, private modules and numeric targets are never imported or opened here.
"""
import argparse,base64,hashlib,json,os,re,shutil,signal,stat,sys,time,types,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNTIME_SHA='0797676d819c7f59f8d17374fa99eaae5b3b60df04f157410216cad9cd3ab224'
def _load():
    p=HERE/'runtime.py';fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as f:
        s=os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=14052:raise ValueError('Frozen runtime extent')
        b=f.read(14053)
    if hashlib.sha256(b).hexdigest()!=RUNTIME_SHA:raise ValueError('Frozen runtime source')
    m=types.ModuleType('neural069_runtime');m.__file__=str(p);exec(compile(b,str(p),'exec'),m.__dict__);return m
r=_load();need=r.need;pin=r.pin;encoded=r.encoded;parse=r.parse;capture=r.capture;path=r.path
WRITE=None
def save(p,b,cap=1000000):
    need(WRITE is not None,'Configured preventive write budget');return WRITE.save(p,b,cap)
ATTEMPT_CAP=18000000;TOTAL_CAP=20000000;META_CAP=1000000

def syncdir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def usage(root):
    todo=[root];total=0;count=0
    while todo:
        p=todo.pop();s=p.lstat();count+=1;need(count<=120,'Bounded attempt inventory')
        need(stat.S_ISDIR(s.st_mode)or(stat.S_ISREG(s.st_mode)and s.st_nlink==1),'Owned ordinary paths');total+=max(s.st_size,s.st_blocks*512);need(total<=ATTEMPT_CAP,'Attempt allocation cap')
        if stat.S_ISDIR(s.st_mode):
            with os.scandir(p)as rows:
                for x in rows:need(count+len(todo)<120,'Bounded traversal');todo.append(p/x.name)
    return total

def frozen(here,expected):
    raw=capture(here/'SOURCE_MANIFEST.json',40000,expected);m=parse(raw);need(m['schema']=='neural069_transport_source_v1','Source manifest')
    names={'runtime.py','child.py','holder.py','entry.py','executor.py','supervise.py','LOCK.json'};rows=m['runtime_files']
    need(type(rows)is dict and set(rows)==names,'Exact runtime source closure')
    bodies={n:capture(here/n,150000,p)for n,p in rows.items()}
    need(pin(bodies['runtime.py'])['sha256']==RUNTIME_SHA,'Pinned reused runtime');return bodies,m

def commitment(directory,expected,source_pin,lock):
    raw=capture(directory/'COMMIT.json',10000,expected);c=parse(raw)
    need(type(c)is dict and set(c)=={'schema','task_id','program','source_manifest','lock','image','candidate_seconds','memory_bytes','cpu','full_cases'},'Commitment shape')
    need(c['schema']=='neural069_program_commit_v1' and c['task_id']=='NEURAL-069' and c['source_manifest']==source_pin and c['lock']==pin(capture(HERE/'LOCK.json',100000)) and c['image']==r.IMAGE and c['full_cases']==[x['id']for x in lock['cases']],'Task/source/panel commitment')
    need(type(c['candidate_seconds'])is int and 1<=c['candidate_seconds']<=7200 and type(c['memory_bytes'])is int and 536870912<=c['memory_bytes']<=4294967296 and c['cpu']==1 and type(c['cpu'])is int,'Prospective fixed resources')
    body=capture(directory/'program.py',131072,c['program']);body.decode('utf-8');return c,body

def public_paths(package,lock):
    raw=capture(package/'DELIVERY_MANIFEST.json',100000,lock['export_manifest']);m=parse(raw)
    # The exported manifest is an exact trusted metadata identity. Its file rows
    # are additionally joined to the predeclared public-only allowlist.
    rows=m['files'];by={x['path'] if 'path'in x else x['target']:x for x in rows}
    result={}
    for row in lock['public_files']:
        name=row['target'];need(name.startswith('public/') and '..'not in Path(name).parts,'Public path')
        held=by[name];need(held['visibility']=='public' and all(held[k]==row[k]for k in ('bytes','sha256','role')),'Selected public descriptor')
        result[name]=path(package/name)
    need(len(result)==101 and sum(x['bytes']for x in lock['public_files'])==lock['public_bytes'],'Full public support');return result

def verify_public(paths,lock):
    for row in lock['public_files']:r.opaque_pin(paths[row['target']],{k:row[k]for k in ('bytes','sha256')},250000000)
    return {'files':len(paths),'bytes':lock['public_bytes'],'lock':pin(capture(HERE/'LOCK.json',100000))}

def holder_module(body):
    m=types.ModuleType('trusted_neural069_holder');exec(compile(body,'holder.py','exec'),m.__dict__);return m

def lifecycle(d,snapshot,c,lock,paths,attempt,holder,verify_inputs,end):
    started=time.monotonic();work=end-60;items=[];closures=[];captured={};natural=None;failure=None;candidate_closed=False
    prefix='neural069-'+uuid.uuid4().hex[:24]
    def item(role,kind):
        v={'kind':kind,'name':prefix+'-'+role,'owner':prefix+'/'+role,'attempted':False,'acknowledged':False};items.append(v)
        save(attempt/('INTENT-'+role+'.json'),encoded(v),4096);syncdir(attempt);return v
    def before(v):need(r.resource_inventory(d,v,v['owner'],work,'before_'+v['kind'])==[],'Fresh scoped resource')
    def create(v,role,mounts,memory):
        before(v);v['attempted']=True
        identity=r.call(d,r.create_args(v,role,mounts,memory),work,'create_'+role,4096,12).decode('ascii').strip();need(re.fullmatch('[a-f0-9]{64}',identity)is not None,'Created ID');v.update(id=identity,acknowledged=True)
        r.admission(r.inspect(d,'container',identity,work,'admit_'+role),v,role,mounts,memory)
    result={'schema':'neural069_program_execution_v1','status':'failed','program':c['program'],'source_manifest':c['source_manifest'],'lock':c['lock'],'image':r.IMAGE,'full_cases':c['full_cases'],'candidate_seconds':c['candidate_seconds'],'memory_bytes':c['memory_bytes'],'candidate_started':False,'private_scoring_called':False}
    try:
        image=parse(r.call(d,['image','inspect',r.IMAGE,'--format','{{json .}}'],work,'image',131072))
        need(image['Id']==r.IMAGE and not image['Config'].get('Volumes')and(not image['Config'].get('Healthcheck')or image['Config']['Healthcheck'].get('Test')==['NONE']),'Existing image without implicit resources')
        volume=item('volume','volume');before(volume);volume['attempted']=True
        response=r.call(d,['volume','create','--driver','local','--label',r.LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+r.VOLUME_OPTIONS,volume['name']],work,'create_volume',4096).decode().strip();need(response==volume['name'],'Volume acknowledgment');volume['acknowledged']=True
        v=r.inspect(d,'volume',volume['name'],work,'admit_volume');r.owned(v,volume,volume['owner']);need(v['Driver']=='local'and v['Options']=={'type':'tmpfs','device':'tmpfs','o':r.VOLUME_OPTIONS},'Exact tmpfs')
        keeper=item('holder','container');hm={'/trusted/holder.py':('bind',snapshot/'holder.py',False),'/trusted/LOCK.json':('bind',snapshot/'LOCK.json',False),'/capture':('volume',volume['name'],False)}
        create(keeper,'holder',hm,134217728);r.call(d,['container','start',keeper['id']],work,'start_holder',4096)
        need(parse(r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','ready'],work,'holder_ready',4096))=={'ready':True},'Live readonly keeper')
        producer=item('candidate','container');cm={'/entry.py':('bind',snapshot/'entry.py',False),'/submission/program.py':('bind',snapshot/'program.py',False),'/output':('volume',volume['name'],True)}
        cm.update({'/'+n:('bind',p,False)for n,p in paths.items()});create(producer,'candidate',cm,c['memory_bytes'])
        begin=time.monotonic();result['candidate_started']=True;r.call(d,['container','start',producer['id']],work,'candidate_start',4096)
        raw=d(['container','wait',producer['id']],min(work,begin+c['candidate_seconds']),'candidate_wait',4096)
        wait_reply=raw.strip();v=r.inspect(d,'container',producer['id'],work,'candidate_exit');r.owned(v,producer,producer['owner']);s=v['State']
        natural={k:s[k]for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')};need(wait_reply==b'0'and s['Status']=='exited'and s['Running']is False and s['Dead']is False and s['Pid']==0 and s['ExitCode']==0 and s['OOMKilled']is False,'Observed exit0/noOOM')
        natural={k:s[k]for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')};result['observed_candidate_seconds']=time.monotonic()-begin;need(result['observed_candidate_seconds']<=c['candidate_seconds'],'Candidate elapsed')
        close=r.retire(d,producer,work);closures.append(close);need(close['closed']and close['removed'],'Removed producer before capture');items.remove(producer);candidate_closed=True
        idx=parse(r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','index'],work,'capture_index',40000))
        need(type(idx)is dict and set(idx)=={'schema','submission','predictions'}and idx['schema']=='neural069_capture_index_v1','Trusted index')
        rows=[idx['submission'],*idx['predictions']];need(len(rows)==81 and rows[0]['path']=='submission.json','Complete captured outputs')
        for i,row in enumerate(rows):
            if i==0:need(type(row['bytes'])is int and 0<row['bytes']<=100000,'Submission extent')
            else:
                # Validate all manifest records before using any candidate path.
                synthetic=encoded({'task_id':'NEURAL-069','roster_sha256':lock['roster']['sha256'],'predictions':idx['predictions']});holder.records(synthetic,lock)
            n=row['path'];raw=r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','file','--name',n],work,'capture_file',4*((row['bytes']+2)//3)+1024)
            reply=parse(raw);need(type(reply)is dict and set(reply)=={'schema','path','bytes','sha256','base64'}and reply['schema']=='neural069_capture_file_v1'and reply['path']==n,'Capture reply')
            body=base64.b64decode(reply['base64'],validate=True);need(pin(body)=={k:row[k]for k in ('bytes','sha256')}=={k:reply[k]for k in ('bytes','sha256')},'Exact same bytes captured');captured[n]=body
            need(sum(map(len,captured.values()))<=lock['output_bytes_cap'],'Complete output byte cap')
        need(holder.records(captured['submission.json'],lock)==idx['predictions'],'Manifest captured-byte join')
    except BaseException as error:failure=type(error).__name__
    finally:
        # The internal alarm reserves this cleanup tail; no retries/new work.
        for v in reversed(items):
            try:closures.append(r.retire(d,v,end))
            except BaseException as error:closures.append({'kind':v['kind'],'name':v['name'],'closed':False,'error_type':type(error).__name__})
    result.update(closures=closures,all_resources_closed=len(closures)==3 and all(v['closed']for v in closures),cli_reaped=d.reaped,natural_exit=natural,candidate_closed_before_capture=candidate_closed,command_metadata=d.records,error_type=failure)
    if failure is None and len(captured)==81 and result['all_resources_closed']and result['cli_reaped']:
        try:
            result['public_post_pin']=verify_inputs();need(time.monotonic()<end,'Before publication deadline')
            output=attempt/'captured';WRITE.mkdir(output);rows=[]
            for n,b in captured.items():rows.append({'path':n,**save(output/n,b,524288)})
            syncdir(output);result.update(status='captured',outputs=rows)
        except BaseException as error:result.update(status='failed',error_type=type(error).__name__)
    result['elapsed_seconds']=time.monotonic()-started;return result

def run(package,commit,commit_pin,source_pin,attempt,other,socket):
    global WRITE
    start=time.monotonic();previous=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Worker bound')));timer=signal.setitimer(signal.ITIMER_REAL,60);owned=None
    try:
        need(timer==(0.0,0.0),'Standalone worker');attempt=path(attempt);need(not os.path.lexists(attempt)and attempt.parent.is_dir(),'Fresh attempt');need(type(other)is int and other>=0,'Other reservation')
        need(shutil.disk_usage(attempt.parent).free>=r.FLOOR+other+TOTAL_CAP,'Bulk floor')
        bodies,_=frozen(HERE,source_pin);lock=parse(bodies['LOCK.json']);c,program=commitment(path(commit),commit_pin,source_pin,lock);end=start+c['candidate_seconds']+420
        signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()-60));paths=public_paths(path(package),lock);pre=verify_public(paths,lock)
        need(time.monotonic()<end-120,'Preflight deadline');WRITE=r.WriteBudget(attempt,other,ATTEMPT_CAP);WRITE.mkdir(attempt);owned=attempt;snapshot=attempt/'snapshot';WRITE.mkdir(snapshot,0o755)
        for n,b in {'program.py':program,**{n:bodies[n]for n in ('holder.py','entry.py','LOCK.json')}}.items():save(snapshot/n,b,150000)
        snapshot.chmod(0o555);syncdir(snapshot);syncdir(attempt)
        bind={'schema':'neural069_execution_input_v1','commit':commit_pin,'source_manifest':source_pin,'public_pre_pin':pre,'package':str(package),'snapshot':{n:pin(b)for n,b in {'program.py':program,**{n:bodies[n]for n in ('holder.py','entry.py','LOCK.json')}}.items()}}
        input_pin=save(attempt/'INPUT.json',encoded(bind),10000)
        d=r.Docker(shutil.which('docker')or '/usr/local/bin/docker',path(socket));result=lifecycle(d,snapshot,c,lock,paths,attempt,holder_module(bodies['holder.py']),lambda:verify_public(paths,lock),end)
        result.update(input_binding=input_pin,commit=commit_pin,source_manifest=source_pin)
        execution=save(attempt/'EXECUTION.json',encoded(result),100000);need(result['status']=='captured','Lifecycle unsuccessful')
        need(time.monotonic()<end-1,'Worker final deadline');usage(attempt);need(shutil.disk_usage(attempt).free>=r.FLOOR+other+TOTAL_CAP,'Final bulk floor')
        done={'schema':'neural069_executor_complete_v1','execution':execution,'input':input_pin,'outputs':len(result['outputs']),'private_scoring_called':False,'worker_seconds':time.monotonic()-start,'limit_seconds':c['candidate_seconds']+420}
        pending=attempt/'COMPLETE.pending.json';fp=save(pending,encoded(done),4096);usage(attempt);need(time.monotonic()<end,'Completion bound');os.rename(pending,attempt/'COMPLETE.json');syncdir(attempt)
        return {'status':'captured','completion':fp,'outputs':81}
    except BaseException as error:
        if owned is not None:
            try:save(owned/'FAILURE.json',encoded({'status':'failed','error_type':type(error).__name__,'resource_recovery_may_be_required':True}),4096)
            except BaseException:pass
        raise
    finally:
        WRITE=None;signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        if timer!=(0.0,0.0):signal.setitimer(signal.ITIMER_REAL,*timer)

def main():
    p=argparse.ArgumentParser();p.add_argument('--package',required=True,type=Path);p.add_argument('--commit',required=True,type=Path);p.add_argument('--commit-bytes',required=True,type=int);p.add_argument('--commit-sha256',required=True);p.add_argument('--source-bytes',required=True,type=int);p.add_argument('--source-sha256',required=True);p.add_argument('--attempt',required=True,type=Path);p.add_argument('--other-reserve-bytes',required=True,type=int);p.add_argument('--docker-socket',required=True,type=Path);a=p.parse_args()
    try:v=run(a.package,a.commit,{'bytes':a.commit_bytes,'sha256':a.commit_sha256},{'bytes':a.source_bytes,'sha256':a.source_sha256},a.attempt,a.other_reserve_bytes,a.docker_socket);print(json.dumps(v,separators=(',',':')));return 0
    except BaseException as e:print(json.dumps({'status':'failed','error_type':type(e).__name__}));return 2
if __name__=='__main__':sys.exit(main())
