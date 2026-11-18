"""NEURAL067 task-specific sealed training and causal query phases."""
import hashlib,json,math,os,re,stat,time,uuid
from pathlib import Path
from .io_guard import need,parse,pin,signature
from . import lifecycle as life
from . import profile
from .stream import Stream
STATE_CAP=33554432
TRAIN_CAP=60000000

def ordinary(path):return life.ordinary(Path(path))
def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def file_pin(path,cap,budget,expected=None,readonly=True):
    path=ordinary(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<before.st_size<=cap,'Bounded ordinary candidate operand')
        if readonly:need(before.st_mode&0o222==0,'Immutable candidate operand')
        if expected is not None:need(before.st_size==expected['bytes'],'Expected operand extent')
        budget.read(before.st_size+1);sha=hashlib.sha256();count=0
        while count<before.st_size:
            b=os.read(fd,min(65536,before.st_size-count));need(b,'Complete operand');count+=len(b);sha.update(b)
        need(os.read(fd,1)==b''and signature(before)==signature(os.fstat(fd))==signature(path.lstat()),'Stable same-open operand')
        result={'bytes':count,'sha256':sha.hexdigest()}
        if expected is not None:need(result=={k:expected[k]for k in result},'Pinned candidate operand')
        return result
    finally:os.close(fd)

def training_pin(root,budget):
    root=ordinary(root);need(root.is_dir()and root.stat().st_mode&0o022==0,'Training root forbids group/other write')
    rows={};total=0
    for base,dirs,files in os.walk(root,followlinks=False):
        need(len(Path(base).relative_to(root).parts)<=2,'Bounded training tree depth')
        for name in dirs:
            p=ordinary(Path(base)/name);need(p.is_dir()and p.stat().st_mode&0o022==0,'Training directory forbids group/other write')
        for name in files:
            p=Path(base)/name;need(len(rows)<64,'Bounded training file inventory')
            n=p.lstat().st_size;need(0<n<=TRAIN_CAP-total,'Bounded training tree bytes')
            rows[p.relative_to(root).as_posix()]=file_pin(p,n,budget);total+=n
    need('TRAIN.json'in rows and 1<len(rows)<=64 and total<=TRAIN_CAP,'Complete bounded masked training view')
    return rows

def sources(config,budget):
    need(config['image']==profile.IMAGE and config['binary']=='/usr/local/bin/docker','Existing exact candidate image/client')
    need(type(config['env'])is dict and type(config['env'].get('DOCKER_HOST'))is str and config['env']['DOCKER_HOST'].startswith('unix:///')and 'DOCKER_CONTEXT'not in config['env'],'Fixed local Docker socket')
    config['check_socket']()
    return {'program':file_pin(config['program'],1048576,budget,config['program_pin']),
            'contract':file_pin(config['contract'],65536,budget,config['contract_pin'])}

def wire(value):
    b=(json.dumps(value,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')
    need(len(b)<=4096,'Bounded input frame');return b

def decoded(body):
    need(type(body)is bytes and 0<len(body)<=1024 and body.endswith(b'\n'),'Bounded action frame')
    return parse(body)

def observation(row,arm,token,index):
    need(type(row)is dict and set(row)=={'token','ordinal','observation'},'Exact current-row source shape')
    need(type(row['token'])is str and re.fullmatch('[a-f0-9]{32,64}',row['token'])is not None,'Opaque run token')
    need((token is None or row['token']==token)and type(row['ordinal'])is int and row['ordinal']==index,'Current token and ordinal')
    value=row['observation'];wanted=set()
    if arm!='clock':wanted.add('spikes')
    if arm!='neural':wanted.update(('elapsed_run_s','observed_segment_age_s','segment_started_now'))
    need(type(value)is dict and set(value)==wanted,'Exact arm-supplied information domain')
    if 'spikes'in value:need(type(value['spikes'])is list and len(value['spikes'])==176 and all(type(x)in(int,float)and math.isfinite(x)for x in value['spikes']),'176 finite current counts')
    for k in ('elapsed_run_s','observed_segment_age_s'):
        if k in value:need(type(value[k])in(int,float)and math.isfinite(value[k])and value[k]>=0,'Finite current elapsed clock')
    if 'segment_started_now'in value:need(type(value['segment_started_now'])is bool,'Current segment-boundary boolean')
    return row['token']

def converse(stream,arm,row_source,journal,deadline):
    need(decoded(stream.line())=={'schema':'neural067_ready_v1','arm':arm},'Exact arm-ready handshake')
    rows=0;token=None
    while True:
        need(time.monotonic()<deadline,'Causal run absolute deadline');stream.idle()
        # Sole release point: after previous append returned its durable record pin.
        row=row_source.next()
        if row is None:break
        token=observation(row,arm,token,rows)
        stream.send(wire({'schema':'neural067_observation_v1',**row}))
        result=decoded(stream.line());stream.idle()
        need(type(result)is dict and set(result)=={'schema','token','ordinal','prediction'}and result['schema']=='neural067_action_v1'and result['token']==token and type(result['ordinal'])is int and result['ordinal']==rows,'One matching action for current request')
        vector=result['prediction'];need(type(vector)is list and len(vector)==7 and all(type(x)in(int,float)and math.isfinite(x)for x in vector),'Seven finite nonboolean actions')
        acknowledged=journal.append(row,vector)
        need(type(acknowledged)is dict and set(acknowledged)=={'bytes','sha256'}and acknowledged['bytes']==160 and re.fullmatch('[a-f0-9]{64}',acknowledged['sha256'])is not None,'Durable exact action record acknowledgement')
        need(time.monotonic()<deadline,'Commit completed within candidate deadline');rows+=1
    need(rows>0,'Nonempty original query run')
    stream.send(wire({'schema':'neural067_end_v1','token':token}))
    need(decoded(stream.line())=={'schema':'neural067_stopped_v1','token':token},'Exact stopped acknowledgement')
    stream.finish();need(time.monotonic()<deadline,'Natural run stream closure deadline')
    return {'rows':rows,'token':token}

def clean(docker,identifier,name,owner,source,deadline,attempted,ack):
    result=life.cleanup(docker,identifier,name,owner,deadline,source)
    unknown=attempted and not ack and not result.get('removed',False)
    result['creation_outcome_unknown']=unknown
    if unknown:result['owned_absence_confirmed']=False
    return result

def phase(config,arm,mode,mounts,phase_dir,budget,work_end,cleanup_end,action):
    need(arm in profile.ARMS and mode in('train','query'),'Fixed training/query arm')
    need(type(work_end)in(int,float)and type(cleanup_end)in(int,float)and work_end<cleanup_end<=budget.end,'Absolute ordered phase deadlines')
    seconds=600 if mode=='train'else 120;budget.tick();budget.guard();sealed=sources(config,budget)
    name='neural067-'+mode+'-'+uuid.uuid4().hex;owner=uuid.uuid4().hex;source=sealed['program']['sha256']
    mounts={k:str(ordinary(v))for k,v in mounts.items()};argv=profile.create_args(name,owner,source,mode,arm,mounts)
    phase_dir=ordinary(phase_dir);need(phase_dir.is_dir(),'Existing owned phase directory')
    budget.save(phase_dir/'INTENT.json',{'name':name,'owner':owner,'program_sha256':source,'arm':arm,'mode':mode,'argv':argv,'mounts':mounts,'work_end':work_end,'cleanup_end':cleanup_end,'attempted_before_dispatch':True})
    docker=life.Docker(config['binary'],config['env'],config['check_socket'],budget)
    identifier=None;attempted=False;ack=False;stream=None;result=None;state=None;absence=None;failure=None;pipe=None;mount_admissions={}
    try:
        need(work_end-time.monotonic()>=seconds,'Full candidate window before setup dispatch')
        for selector in ('label='+life.LABEL+'='+owner,'name=^/'+name+'$','label='+life.SOURCE_LABEL+'='+source):
            need(life.inventory(docker,selector,min(work_end,time.monotonic()+5),'fresh_owned_namespace')==[],'Fresh owner/name/program-source namespace; manual recovery before reuse')
        need(work_end-time.monotonic()>=seconds,'Full work allowance after fresh namespace checks')
        attempted=True;raw=docker(argv,min(work_end,time.monotonic()+5),'create',4096).decode().strip()
        need(re.fullmatch('[a-f0-9]{64}',raw)is not None,'Acknowledged immutable container ID');identifier=raw;ack=True
        budget.save(phase_dir/'CREATED.json',{'name':name,'owner':owner,'container_id':identifier,'program_sha256':source})
        value=life.inspected(docker,identifier,min(work_end,time.monotonic()+5),'created');life.ownership(value,identifier,name,owner,source);mount_admissions['created']=profile.verify(value,name,owner,source,mode,arm,mounts,mount_source_policy=config['mount_source_policy'])
        need(value['State']['Status']=='created'and value['State']['Running']is False and value['State']['Pid']==0,'Inspect before start')
        need(work_end-time.monotonic()>=seconds,'Full unshortened candidate window before attach')
        config['check_socket']();deadline=time.monotonic()+seconds
        stream=Stream(config['binary'],dict(config['env']),identifier,deadline,budget,mode=mode)
        result=action(stream,deadline)
        value=life.inspected(docker,identifier,min(cleanup_end,time.monotonic()+5),'finished');life.ownership(value,identifier,name,owner,source);mount_admissions['finished']=profile.verify(value,name,owner,source,mode,arm,mounts,mount_source_policy=config['mount_source_policy']);state=life.natural_exit(value)
    except BaseException as error:
        failure=type(error).__name__;pipe=getattr(error,'attach_closure',getattr(error,'closure',None))
    finally:
        if stream is not None:
            try:pipe=stream.close(cleanup_end)
            except BaseException as error:failure=failure or type(error).__name__
        try:absence=clean(docker,identifier,name,owner,source,cleanup_end,attempted,ack)
        except BaseException as error:failure=failure or type(error).__name__
        try:config['check_socket']()
        except BaseException as error:failure=failure or type(error).__name__
    evidence={'mode':mode,'arm':arm,'program_sha256':source,'name':name,'owner':owner,'container_id':identifier,'create_attempted':attempted,'create_acknowledged':ack,'natural_state':state,'attach':pipe,'cleanup':absence,'error_type':failure,'commands':docker.records,'mount_admissions':mount_admissions,'role_deadline_met':time.monotonic()<cleanup_end,'manual_recovery_required':True}
    ok=(failure is None and result is not None and state is not None and pipe and pipe.get('attach_reaped')is True and pipe.get('attach_group_absent')is True and type(pipe.get('streams_closed'))is dict and set(pipe['streams_closed'])=={'stdin','stdout','stderr'}and all(x is True for x in pipe['streams_closed'].values())and pipe.get('selector_closed')is True and pipe.get('finished')is True and pipe.get('natural_returncode')==0 and not pipe.get('forced_attach_stop')and pipe.get('error_type')is None and pipe.get('deadline_met')is True and absence and absence.get('owned_absence_confirmed')is True and not absence.get('forced_stop')and not absence.get('creation_outcome_unknown')and time.monotonic()<cleanup_end)
    if not ok:
        evidence['status']='failed_unqualified';budget.save(phase_dir/'HOST.json',evidence);raise RuntimeError('Unqualified candidate phase; explicit manual recovery required')
    need(sources(config,budget)==sealed and time.monotonic()<cleanup_end,'Sources unchanged after producer absence')
    evidence.update(status='complete',manual_recovery_required=False,all_owned_absent=True)
    return result,evidence

def mounts(config):return {'/program/program.py':config['program'],'/contract/CONTRACT.md':config['contract']}
def failed(phase_dir,budget,error):
    try:budget.save(Path(phase_dir)/'FAILED.json',{'status':'failed_unqualified','error_type':type(error).__name__,'manual_recovery_required':True,'partial_state_and_journals_preserved':True})
    except BaseException:pass

def train_phase(config,arm,train_root,state_path,phase_dir,budget,work_end,cleanup_end):
    pending=None;fd=None
    try:
        before=training_pin(train_root,budget);state_path=ordinary(state_path);need(not os.path.lexists(state_path),'Fresh final arm state')
        pending=state_path.with_name('.'+state_path.name+'.pending');need(not os.path.lexists(pending),'Fresh quarantine state')
        budget.debit(STATE_CAP);budget.guard();fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);written=0
        def sink(body):
            nonlocal written
            need(type(body)is bytes and len(body)<=STATE_CAP-written,'Preventive opaque state bound');budget.tick();budget.guard()
            view=memoryview(body);offset=0
            while offset<len(view):
                n=os.write(fd,view[offset:]);need(n>0,'Complete state write');offset+=n
            written+=len(body)
        def action(stream,deadline):
            result=stream.capture_state(sink);stream.finish();return result
        requested=mounts(config);requested['/train']=train_root
        result,evidence=phase(config,arm,'train',requested,phase_dir,budget,work_end,cleanup_end,action)
        need(training_pin(train_root,budget)==before,'Masked training tree unchanged after absence')
        need(result['bytes']==written,'Exact captured state extent');os.fsync(fd);os.fchmod(fd,0o444);os.fsync(fd);os.close(fd);fd=None
        state_pin=file_pin(pending,STATE_CAP,budget,result);need(time.monotonic()<cleanup_end,'State admission deadline')
        os.link(pending,state_path,follow_symlinks=False);pending.unlink();sync(state_path.parent)
        record={'path':str(state_path),**state_pin,'program_sha256':config['program_pin']['sha256'],'arm':arm}
        evidence.update(state=record,training_files=before,role_deadline_met=time.monotonic()<cleanup_end);host=budget.save(Path(phase_dir)/'HOST.json',evidence)
        budget.tick();need(time.monotonic()<cleanup_end,'State publication closure deadline')
        return {'state':record,'host':host,'all_owned_absent':True}
    except BaseException as error:failed(phase_dir,budget,error);raise
    finally:
        if fd is not None:os.close(fd)

def query_phase(config,arm,state_path,row_source,journal,phase_dir,budget,work_end,cleanup_end):
    try:
        expected=config['states'][arm];need(expected['program_sha256']==config['program_pin']['sha256']and ordinary(expected['path'])==ordinary(state_path)and expected.get('arm',arm)==arm,'Own arm state and same program seal')
        initial=file_pin(state_path,STATE_CAP,budget,expected)
        requested=mounts(config);requested['/state/STATE.bin']=state_path
        result,evidence=phase(config,arm,'query',requested,phase_dir,budget,work_end,cleanup_end,lambda stream,deadline:converse(stream,arm,row_source,journal,deadline))
        need(file_pin(state_path,STATE_CAP,budget,expected)==initial,'Identical arm reset state after run')
        journal_pin=journal.seal();need(file_pin(journal.path,2000000,budget,journal_pin)==journal_pin,'Sealed readonly journal after producer absence')
        evidence.update(rows=result['rows'],token=result['token'],journal=journal_pin,state=initial,role_deadline_met=time.monotonic()<cleanup_end);host=budget.save(Path(phase_dir)/'HOST.json',evidence)
        budget.tick();need(time.monotonic()<cleanup_end,'Run admission closure deadline')
        return {'journal':journal_pin,'host':host,'rows':result['rows'],'all_owned_absent':True}
    except BaseException as error:failed(phase_dir,budget,error);raise
