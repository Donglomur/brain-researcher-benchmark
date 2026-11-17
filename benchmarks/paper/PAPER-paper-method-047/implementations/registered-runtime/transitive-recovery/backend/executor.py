"""SliceTCA fixed-panel program commitment and one fresh owned case lifecycle.

No candidate or scorer is run by import, freeze, or source tests. Actual execution
requires explicit case CLI invocation under a separately selected resource phase.
"""
import argparse,base64,hashlib,json,os,re,selectors,shutil,signal,stat,subprocess,time,types,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
LABEL='org.neurobench.slicetca-program-owner'
CASES=tuple(f'{r}-r{i:02d}-f{j}' for r in ('straight','curved') for i in range(20) for j in range(5))
PRED_CAP=524288;VOLUME_BYTES=8388608;CASE_WRITE_RESERVE=2000000
VOLUME_OPTIONS='size=8388608,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
FLOOR=21474836480

def need(ok,msg):
    if not ok:raise ValueError(msg)

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))
def path(p):
    p=Path(p).absolute();need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'Unlinked canonical path')
    need(not any(c in str(p) for c in ',\n\r\0'),'Unambiguous mount path');return p

def capture(p,cap,expected=None):
    p=path(p);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb',buffering=0) as f:
        s=os.fstat(f.fileno());need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=cap,'Bounded regular file')
        body=f.read(s.st_size+1);z=os.fstat(f.fileno());n=p.lstat()
        need(len(body)==s.st_size and all(getattr(s,k)==getattr(z,k)==getattr(n,k) for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')),'Stable complete capture')
    need(expected is None or pin(body)==expected,'Exact input identity');return body

def opaque_pin(p,expected,cap=56000000):
    """Stream the shared immutable neural file without retaining/decoding it."""
    p=path(p);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb',buffering=0) as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==expected['bytes'] and 0<a.st_size<=cap,'Bounded shared neural source')
        total=0;digest=hashlib.sha256()
        while total<=a.st_size:
            b=f.read(min(65536,a.st_size+1-total))
            if not b:break
            total+=len(b);digest.update(b)
        z=os.fstat(f.fileno());named=p.lstat()
        need(all(getattr(a,k)==getattr(z,k)==getattr(named,k) for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')),'Shared source changed during hash')
        need({'bytes':total,'sha256':digest.hexdigest()}==expected,'Shared source exact identity')
    return dict(expected)

def save(p,body,cap=1000000):
    need(type(body)is bytes and len(body)<=cap,'Bounded owned write');p=Path(p)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    with os.fdopen(fd,'wb',buffering=0) as f:
        view=memoryview(body)
        while view:
            n=f.write(view);need(type(n)is int and n>0,'Full owned write');view=view[n:]
        os.fsync(f.fileno())
    p.chmod(0o444);return pin(body)

def bindings(repo):
    # This source manifest contains code/contract metadata only, never answer data.
    b=parse(capture(HERE/'BINDINGS.json',65536));root=path(repo);modules={}
    for name,row in b['modules'].items():
        raw=capture(root/row['path'],100000,{k:row[k] for k in ('bytes','sha256')})
        mod=types.ModuleType('slice_'+name);mod.__file__=str(root/row['path']);exec(compile(raw,mod.__file__,'exec'),mod.__dict__);modules[name]=mod
    return b,modules

def freeze(program_a,program_b,destination,seconds,memory):
    need(type(seconds)is int and 1<=seconds<=600,'Fixed candidate seconds 1..600')
    need(type(memory)is int and 536870912<=memory<=4294967296 and memory%1048576==0,'Fixed memory 512MiB..4GiB')
    dest=path(destination);need(not os.path.lexists(dest) and dest.parent.is_dir(),'Fresh panel commitment')
    sources={a:capture(p,131072) for a,p in [('A',program_a),('B',program_b)]}
    for raw in sources.values():need('\0' not in raw.decode('utf-8'),'UTF-8 self-contained Python')
    b=parse(capture(HERE/'BINDINGS.json',65536))
    record={'schema':'slicetca_frozen_panel_v1','task_id':'PAPER-paper-method-add-002','cases':list(CASES),'programs':{a:pin(raw) for a,raw in sources.items()},'image':IMAGE,'candidate_seconds':seconds,'memory_bytes':memory,'cpus':1,'paired_access_binding':b['paired_access_binding'],'shared_neural':b['shared_neural'],'authoring_access_attested_by_this_executor':False}
    dest.mkdir(mode=0o700)
    for a,raw in sources.items():save(dest/(a+'.py'),raw,131072)
    pp=save(dest/'PANEL.json',encoded(record));dest.chmod(0o555);return pp

def panel(directory,expected):
    directory=path(directory);raw=capture(directory/'PANEL.json',65536,expected);p=parse(raw)
    need(p['schema']=='slicetca_frozen_panel_v1' and p['task_id']=='PAPER-paper-method-add-002' and p['cases']==list(CASES),'Exact full fixed panel')
    need(p['image']==IMAGE and p['cpus']==1 and set(p['programs'])=={'A','B'},'Fixed paired source/image')
    need(type(p['candidate_seconds'])is int and 1<=p['candidate_seconds']<=600 and type(p['memory_bytes'])is int and 536870912<=p['memory_bytes']<=4294967296 and p['memory_bytes']%1048576==0,'Bounded frozen resources')
    b=parse(capture(HERE/'BINDINGS.json',65536));need(p['paired_access_binding']==b['paired_access_binding'] and p['shared_neural']==b['shared_neural'],'Same A/B source view definition')
    for arm in ('A','B'):capture(directory/(arm+'.py'),131072,p['programs'][arm])
    return p

class CommandError(RuntimeError):pass
class Docker:
    """Streaming-capped CLI, no attachment to candidate stdout or log retrieval."""
    def __init__(self,binary,socket):
        self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        # GCaMP8's aborting case has one failing command plus at most six
        # independent retirement commands. Recovery has at most six failures.
        self.original_failures=[];self.failure_bound_refusal=None
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
    def __call__(self,args,end,phase,cap=131072):
        if len(self.original_failures)>=7:
            if self.failure_bound_refusal is None:
                self.failure_bound_refusal=CommandError('GCaMP8 original failure bound; no further command started')
            raise self.failure_bound_refusal
        start=time.monotonic()
        p=None;s=None;bufs={'out':bytearray(),'err':bytearray()};error=None;rc=None
        original=None;secondary=[];original_result=None;wait_returns=[]
        eof={'out':False,'err':False};command=tuple(self.prefix+args)
        failure={'exception':None,'rawstdout':bufs['out'],'rawstderr':bufs['err'],
                 'record':None,'secondary_exceptions':secondary,'command':command,
                 'original_result':None,'wait_returns':wait_returns,'eof':eof}
        failure_retained=False
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;group_error=None
        self.reaped=False
        try:
            need(end-start>1,'Command deadline')
            p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True)
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    if not raw:eof[k.data]=True;s.unregister(k.fileobj);continue
                    # Preserve the actual overflow byte before admission fails.
                    bufs[k.data].extend(raw)
                    need(sum(map(len,bufs.values()))<=cap,'Streaming CLI cap')
            rc=p.wait(timeout=max(.01,end-time.monotonic()));wait_returns.append(rc);child_reaped=True
            need(rc==0,'Docker command failure')
            try:os.killpg(p.pid,0)
            except ProcessLookupError:group_absent=True
            else:
                survivor_observed=True
                raise CommandError('Owned CLI group survives leader exit')
            need(time.monotonic()<end,'CLI group observation before original deadline')
            original_result=bytes(bufs['out'])
            return original_result
        except BaseException as e:
            original=e;error=type(e).__name__
            failure['exception']=e
            self.original_failures.append(failure);failure_retained=True
            raise
        finally:
            # One shared cleanup interval, never a new per-descendant allowance.
            cleanup_end=end;cleanup_in_time=False;elapsed=None
            try:
                cleanup_end=min(end,time.monotonic()+1)
                if p is not None and not group_absent:
                    live=False
                    try:os.killpg(p.pid,0);live=True
                    except ProcessLookupError:group_absent=True
                    except BaseException as e:secondary.append(e);cleanup_ok=False;group_error=type(e).__name__
                    if live:
                        try:os.killpg(p.pid,signal.SIGKILL)
                        except ProcessLookupError:group_absent=True
                        except BaseException as e:secondary.append(e);cleanup_ok=False;group_error=type(e).__name__
                if p is not None and not child_reaped:
                    try:rc=p.wait(timeout=max(0,cleanup_end-time.monotonic()));wait_returns.append(rc);child_reaped=True
                    except BaseException as e:secondary.append(e);cleanup_ok=False
                if p is not None and not group_absent:
                    while True:
                        try:os.killpg(p.pid,0)
                        except ProcessLookupError:group_absent=True;break
                        except BaseException as e:secondary.append(e);cleanup_ok=False;group_error=type(e).__name__;break
                        left=cleanup_end-time.monotonic()
                        if left<=0:break
                        time.sleep(min(.01,left))
                if p is not None and not group_absent:cleanup_ok=False
            except BaseException as e:
                secondary.append(e);cleanup_ok=False
            finally:
                # A probe/clock interruption must not skip independent handles.
                if s is not None:
                    try:s.close()
                    except BaseException as e:secondary.append(e);cleanup_ok=False
                if p is not None:
                    for stream in (p.stdout,p.stderr):
                        if stream is not None:
                            try:stream.close()
                            except BaseException as e:secondary.append(e);cleanup_ok=False
                try:
                    elapsed=time.monotonic()-start
                    cleanup_in_time=time.monotonic()<cleanup_end
                except BaseException as e:secondary.append(e);cleanup_ok=False
                cleanup_ok=cleanup_ok and cleanup_in_time
                self.reaped=previous_reaped and child_reaped and cleanup_ok and group_absent
                record={'phase':phase,'returncode':rc,'error_type':error,'observed_retained_bytes':sum(map(len,bufs.values())),'seconds':elapsed,'client_reaped':child_reaped,'cleanup_complete':cleanup_ok,'cleanup_before_original_cutoff':cleanup_in_time,'owned_group_absence_observed':group_absent,'leader_exited_with_group_alive':survivor_observed,'group_probe_or_cleanup_error':group_error}
                self.records.append(record)
                try:
                    if time.monotonic()>=cleanup_end:
                        cleanup_ok=False;self.reaped=False
                        record['cleanup_complete']=False;record['cleanup_before_original_cutoff']=False
                except BaseException as e:
                    secondary.append(e);cleanup_ok=False;self.reaped=False
                    record['cleanup_complete']=False;record['cleanup_before_original_cutoff']=False
                if not cleanup_ok and original is None:
                    original=secondary[0] if secondary else CommandError('CLI cleanup incomplete')
                failure.update(exception=original,record=record,secondary_exceptions=tuple(secondary),
                               original_result=original_result,wait_returns=tuple(wait_returns),eof=dict(eof))
                if original is not None and not failure_retained:
                    self.original_failures.append(failure)
            if not cleanup_ok and error is None:raise original

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)
def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('slicetca-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

def inspect(d,kind,name,end,phase):
    rows=parse(call(d,[kind,'inspect',name],end,phase));need(type(rows)is list and len(rows)==1,'One inspected resource');return rows[0]
def owned(v,item,owner):
    need(v['Name']==(item['name'] if item['kind']=='volume' else '/'+item['name']),'Exact resource name')
    labels=v.get('Labels') if item['kind']=='volume' else v['Config'].get('Labels')
    need(labels is not None and labels.get(LABEL)==owner,'Exact owner label')
    if item.get('id') is not None:need(v['Id']==item['id'],'Exact returned container ID')

def resource_inventory(d,item,owner,end,prefix):
    a=inventory(d,item['kind'],'label='+LABEL+'='+owner,end,prefix+'_owner')
    # The owner is unique per resource (same panel/case suffix plus role).
    b=inventory(d,item['kind'],'name=^'+('/' if item['kind']=='container' else '')+item['name']+'$',end,prefix+'_name')
    need(a==b and len(a)<=1,'Exact owner/name join');return a

def retire(d,item,end):
    owner=item['owner'];rows=resource_inventory(d,item,owner,end,'cleanup_'+item['kind']);removed=False
    if not item.get('attempted',False):
        return {'kind':item['kind'],'name':item['name'],'create_not_attempted':True,'collision_preserved':bool(rows),'observed_namespace_empty':rows==[],'removed':False,'closed':rows==[]}
    if rows:
        value=inspect(d,item['kind'],rows[0],end,'cleanup_inspect');owned(value,item,owner)
        if item['kind']=='container' and value['State']['Running']:
            call(d,['container','kill','--signal','KILL',rows[0]],end,'cleanup_kill',4096)
            call(d,['container','wait',rows[0]],end,'cleanup_wait',4096)
        call(d,[item['kind'],'rm',rows[0]],end,'cleanup_remove',4096);removed=True
    after=resource_inventory(d,item,owner,end,'absence_'+item['kind'])
    unknown=item.get('attempted',False) and not item.get('acknowledged',False) and not removed
    return {'kind':item['kind'],'name':item['name'],'removed':removed,'absence_observed':after==[],'creation_outcome_unknown':unknown,'closed':after==[] and not unknown}

def mounts_argv(mounts):
    result=[]
    for target,(kind,source,rw) in mounts.items():
        value='type='+kind+',src='+str(source)+',dst='+target+(',volume-nocopy' if kind=='volume' else '')+('' if rw else ',readonly')
        result+=['--mount',value]
    return result

def create_args(item,role,mounts,memory):
    cmd=['-I','-B','/trusted/holder.py','hold'] if role=='holder' else ['-I','-B','/entry.py',str(memory)]
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--cpus','1','--memory',str(memory),'--memory-swap',str(memory),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize=524288:524288']
    if role=='candidate':args+=['--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=33554432']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):args+=['--env',key+'=1']
    return args+mounts_argv(mounts)+['--entrypoint','python',IMAGE,*cmd]

def admission(value,item,role,mounts,memory):
    owned(value,item,item['owner']);h=value['HostConfig'];c=value['Config']
    need(value['Image']==c['Image']==IMAGE and c['User']=='65534:65534' and c['Entrypoint']==['python'],'Exact image/user/entry')
    expected=['-I','-B','/trusted/holder.py','hold'] if role=='holder' else ['-I','-B','/entry.py',str(memory)]
    need(c['Cmd']==expected and h['Memory']==h['MemorySwap']==memory and h['NanoCpus']==1000000000 and h['PidsLimit']==64,'Exact command/resources')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['CgroupnsMode']=='private' and h['LogConfig']['Type']=='none','Isolation and no logs')
    need(h.get('Privileged') is False and not h.get('CapAdd') and not h.get('Devices') and not h.get('DeviceRequests') and h.get('PidMode') in ('','private') and h.get('IpcMode')=='private','No device or host namespace access')
    need(h['CapDrop']==['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no' and h['AutoRemove'] is False and h['ShmSize']==16777216,'No capabilities/restarts or extra shared memory')
    actual={x['Destination']:(x['Type'],x['Name'] if x['Type']=='volume' else x['Source'],x['RW']) for x in value['Mounts']}
    need(len(value['Mounts'])==len(mounts) and actual=={k:(kind,str(source),rw) for k,(kind,source,rw) in mounts.items()},'Exact mounts; no host writable candidate bind')
    need(all(not rw for kind,_,rw in mounts.values() if kind=='bind'),'All host bindings read-only')
    need(h.get('Tmpfs') in ({},None) if role=='holder' else h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size=33554432'},'Only bounded scratch')
    limits={x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']};need(limits=={'core':(0,0),'nofile':(128,128),'fsize':(524288,524288)},'Bounded file extent')

def output_reply(raw):
    obj=parse(raw);need(type(obj)is dict and set(obj)=={'schema','bytes','sha256','base64'} and obj['schema']=='slicetca_capture_v1','Trusted capture schema')
    need(type(obj['bytes'])is int and 0<obj['bytes']<=PRED_CAP and type(obj['base64'])is str and len(obj['base64'])<=4*((PRED_CAP+2)//3),'Bounded captured output')
    body=base64.b64decode(obj['base64'],validate=True);need(pin(body)=={k:obj[k] for k in ('bytes','sha256')},'Opaque output pin');return body

def lifecycle(d,snapshot,p,arm,case_id,attempt,shared_neural,verify_shared,operation_deadline=None):
    started=time.monotonic();end=min(operation_deadline or float('inf'),started+p['candidate_seconds']+100);work_end=end-35
    suffix=uuid.uuid4().hex[:24];prefix='slicetca-'+suffix;items=[];closures=[];prediction=None;err=None;natural=None
    result={'schema':'slicetca_case_execution_v1','status':'failed','case_id':case_id,'arm':arm,'program':p['programs'][arm],'candidate_seconds':p['candidate_seconds'],'candidate_started':False,'candidate_closed_before_capture':False,'private_scoring_called':False}
    def item(role,kind):
        row={'kind':kind,'name':prefix+'-'+role,'owner':prefix+'/'+role,'attempted':False,'acknowledged':False};items.append(row)
        save(attempt/('INTENT-'+role+'.json'),encoded({'kind':kind,'name':row['name'],'owner':row['owner'],'possible_creation_obligation_until_closed':True}))
        return row
    def before(row):need(resource_inventory(d,row,row['owner'],work_end,'before_'+row['kind'])==[],'Fresh scoped resource')
    def create_container(row,role,mounts,memory):
        before(row);row['attempted']=True
        value=call(d,create_args(row,role,mounts,memory),work_end,'create_'+role,4096,12).decode().strip();need(re.fullmatch('[a-f0-9]{64}',value),'Exact created ID');row.update(id=value,acknowledged=True)
        admission(inspect(d,'container',value,work_end,'admit_'+role),row,role,mounts,memory)
    try:
        image=parse(call(d,['image','inspect',IMAGE,'--format','{{json .}}'],work_end,'image',131072))
        need(image['Id']==IMAGE and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']),'Existing image without implicit anonymous volumes or health processes')
        volume=item('volume','volume');before(volume);volume['attempted']=True
        returned=call(d,['volume','create','--driver','local','--label',LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+VOLUME_OPTIONS,volume['name']],work_end,'create_volume',4096).decode().strip()
        need(returned==volume['name'],'Exact volume acknowledgment');volume['acknowledged']=True
        v=inspect(d,'volume',volume['name'],work_end,'admit_volume');owned(v,volume,volume['owner']);need(v['Driver']=='local' and v['Options']=={'type':'tmpfs','device':'tmpfs','o':VOLUME_OPTIONS},'Memory-backed bounded volume')
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',snapshot/'holder.py',False),'/capture':('volume',volume['name'],False)}
        create_container(holder,'holder',hm,134217728);call(d,['container','start',holder['id']],work_end,'start_holder',4096)
        need(parse(call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','ready'],work_end,'holder_ready',4096))=={'ready':True},'Observed live tmpfs holder')
        candidate=item('candidate','container');cm={'/submission/program.py':('bind',snapshot/'program.py',False),'/entry.py':('bind',snapshot/'entry.py',False),'/output':('volume',volume['name'],True)}
        cm.update({'/input/'+n:('bind',snapshot/n,False) for n in ('train_positions.npy','CASE.json')})
        cm['/input/neural.npy']=('bind',path(shared_neural),False)
        create_container(candidate,'candidate',cm,p['memory_bytes'])
        begin=time.monotonic();result['candidate_started']=True
        call(d,['container','start',candidate['id']],work_end,'candidate_start',4096)
        raw=d(['container','wait',candidate['id']],min(work_end,begin+p['candidate_seconds']),'candidate_wait',4096)
        need(raw.strip()==b'0','Candidate exit 0')
        v=inspect(d,'container',candidate['id'],work_end,'candidate_exit');owned(v,candidate,candidate['owner']);s=v['State']
        need(s['Status']=='exited' and s['Running'] is False and s['Dead'] is False and s['Pid']==0 and s['ExitCode']==0 and s['OOMKilled'] is False,'Natural zero non-OOM exit')
        natural={k:s[k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
        closed=retire(d,candidate,work_end);closures.append(closed);need(closed['closed'],'Candidate removed before capture');items.remove(candidate);result['candidate_closed_before_capture']=True
        prediction=output_reply(call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','capture'],work_end,'capture',710000))
    except BaseException as e:err=type(e).__name__
    finally:
        for row in reversed(items):
            try:closures.append(retire(d,row,end))
            except BaseException as e:closures.append({'kind':row['kind'],'name':row['name'],'closed':False,'error_type':type(e).__name__})
    result.update(elapsed_seconds=time.monotonic()-started,closures=closures,all_resources_closed=all(x['closed'] for x in closures),cli_reaped=d.reaped,natural_exit=natural,command_metadata=d.records)
    if err is None and prediction is not None and result['all_resources_closed'] and result['cli_reaped'] and result['elapsed_seconds']<=p['candidate_seconds']+100:
        try:
            result['shared_neural_post_pin']=verify_shared()
            need(time.monotonic()<end,'Native lifecycle deadline before publication')
            result['prediction']=save(attempt/'predictions.json',prediction,PRED_CAP);result['status']='captured'
        except BaseException as e:result['error_type']=type(e).__name__
    else:result['error_type']=err or 'UnclosedLifecycle'
    result['elapsed_seconds']=time.monotonic()-started
    if result['elapsed_seconds']>p['candidate_seconds']+100:
        result['status']='failed';result['error_type']='WholeCaseDeadline'
    return result

def _run_case(repo,panel_dir,panel_pin,arm,case_root,case_binding_pin,neural,attempt,other,socket,state):
    need(arm in ('A','B') and type(other)is int and other>=0,'Explicit arm/current reservation')
    attempt=path(attempt);need(not os.path.lexists(attempt) and attempt.parent.is_dir(),'Fresh attempt')
    need(shutil.disk_usage(attempt.parent).free>=FLOOR+other+CASE_WRITE_RESERVE,'Prospective complete case capacity')
    b,mods=bindings(repo);p=panel(panel_dir,panel_pin);case_root=path(case_root)
    state['deadline']=state['started']+p['candidate_seconds']+180
    need(time.monotonic()<state['deadline']-100,'Complete preflight and cleanup reserve')
    signal.setitimer(signal.ITIMER_REAL,state['deadline']-time.monotonic())
    boundraw=capture(case_root/'CASE_BINDING.json',65536,case_binding_pin);bound=parse(boundraw)
    casebody=capture(case_root/'public/CASE.json',65536,bound['case']);case=parse(casebody);mods['score'].validate_case(case)
    need(bound['schema']=='slicetca_operator_case_binding_v1' and case['case_id']==bound['case_id'] and case['case_id'] in CASES and bound['shared_neural']==case['input_files']['neural.npy']==p['shared_neural'],'Exact fixed public case binding')
    # Snapshot exactly the three scientific inputs. Never read private/TRUTH.json.
    neural=path(neural);neural_pin=opaque_pin(neural,case['input_files']['neural.npy'])
    bodies={'CASE.json':casebody,'train_positions.npy':capture(case_root/'public/train_positions.npy',275000,case['input_files']['train_positions.npy']),'program.py':capture(Path(panel_dir)/(arm+'.py'),131072,p['programs'][arm])}
    for name in ('holder.py','entry.py'):bodies[name]=capture(HERE/name,20000,b['local_sources'][name])
    need(sum(map(len,bodies.values()))+1000000<=CASE_WRITE_RESERVE,'Complete snapshot/output allowance')
    attempt.mkdir(mode=0o700);state['owned_attempt']=attempt;snapshot=attempt/'snapshot';snapshot.mkdir(mode=0o755)
    for name,raw in bodies.items():save(snapshot/name,raw,56000000)
    snapshot.chmod(0o555)
    save(attempt/'INPUT_BINDING.json',encoded({'panel':panel_pin,'case_binding':case_binding_pin,'case_id':case['case_id'],'arm':arm,'truth':bound['truth'],'shared_neural':{'path':str(neural),**neural_pin},'snapshot':{n:pin(raw) for n,raw in bodies.items()},'truth_body_read':False}))
    binary=shutil.which('docker');need(binary is not None and stat.S_ISSOCK(path(socket).stat().st_mode),'Existing local Docker only')
    result=lifecycle(Docker(binary,socket),snapshot,p,arm,case['case_id'],attempt,neural,lambda:opaque_pin(neural,neural_pin),state['deadline']-10)
    result['panel']=panel_pin;result['input_binding']=pin(capture(attempt/'INPUT_BINDING.json',100000))
    return result

def owned_usage(attempt):
    total=0;count=0
    for p in [attempt,*attempt.rglob('*')]:
        st=p.lstat();need(stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode),'Only owned regular files/directories')
        if stat.S_ISREG(st.st_mode):need(st.st_nlink==1,'No linked owned files')
        count+=1;need(count<=20,'Bounded owned inventory');total+=max(st.st_size,st.st_blocks*512)
    return total

def run_case(*args):
    state={'started':time.monotonic(),'owned_attempt':None,'deadline':None}
    def expired(*_):raise TimeoutError('Whole operation deadline')
    old=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,30)
    try:
        result=_run_case(*args,state)
        attempt=state['owned_attempt'];need(attempt is not None,'Owned attempt')
        need(time.monotonic()<state['deadline'] and owned_usage(attempt)+131072<=CASE_WRITE_RESERVE,'Final metadata reservation before publication')
        result['whole_operation_limit_seconds']=state['deadline']-state['started']
        result['whole_operation_elapsed_before_record']=time.monotonic()-state['started']
        execution=save(attempt/'EXECUTION.json',encoded(result),100000)
        need(time.monotonic()<state['deadline'] and owned_usage(attempt)+8192<=CASE_WRITE_RESERVE,'Final record bound')
        completion={'schema':'slicetca_entry_completion_v1','status':result['status'],'execution':execution,'whole_operation_limit_seconds':result['whole_operation_limit_seconds'],'whole_operation_elapsed_before_completion':time.monotonic()-state['started'],'allocated_before_completion':owned_usage(attempt),'private_scoring_called':False}
        pending=attempt/'ENTRY_COMPLETION.pending.json';terminal=attempt/'ENTRY_COMPLETION.json'
        completion_pin=save(pending,encoded(completion),4096)
        capture(pending,4096,completion_pin)
        need(time.monotonic()<state['deadline'] and owned_usage(attempt)<=CASE_WRITE_RESERVE,'Deadline and allocation before final atomic publication')
        need(not os.path.lexists(terminal),'Fresh final completion')
        os.rename(pending,terminal)
        return result
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0)
        if state['owned_attempt'] is not None:
            try:save(state['owned_attempt']/'FAILURE.json',encoded({'status':'failed','error_type':type(error).__name__,'success_not_admitted':True,'partial_state_preserved':True}),4096)
            except BaseException:pass
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def closed_for_score(attempt,panel_dir,panel_pin,host_receipt,host_receipt_pin):
    attempt=path(attempt);need(not os.path.lexists(attempt/'FAILURE.json'),'Failed/partial attempt cannot score');p=panel(panel_dir,panel_pin)
    terminal_raw=capture(attempt/'ENTRY_COMPLETION.json',4096);terminal=parse(terminal_raw);need(terminal['schema']=='slicetca_entry_completion_v1' and terminal['status']=='captured' and terminal['whole_operation_elapsed_before_completion']<terminal['whole_operation_limit_seconds'],'Successful bounded entry completion')
    record=parse(capture(attempt/'EXECUTION.json',100000,terminal['execution']));bind=parse(capture(attempt/'INPUT_BINDING.json',100000,record['input_binding']))
    need(record['status']=='captured' and record['all_resources_closed'] is True and record['cli_reaped'] is True and record['candidate_closed_before_capture'] is True,'Closed producer/capture lifecycle required')
    need(len(record['closures'])==3 and all(x['closed'] for x in record['closures']) and sorted(x['kind'] for x in record['closures'])==['container','container','volume'],'All three exact resources closed')
    need(record['case_id'] in p['cases'] and record['natural_exit']=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'Natural successful fixed-case result')
    need(record['panel']==bind['panel']==panel_pin and record['case_id']==bind['case_id'] and record['arm']==bind['arm'] and record['program']==p['programs'][record['arm']] and record['shared_neural_post_pin']=={k:bind['shared_neural'][k] for k in ('bytes','sha256')}==p['shared_neural'],'Committed panel/case join')
    # Independent operator-supplied successful HOST exit evidence is required;
    # this worker never derives it from any self-present completion marker.
    host_path=path(host_receipt);need(not host_path.is_relative_to(attempt),'Supervisor receipt outside child-owned attempt')
    need(type(host_receipt_pin)is dict and set(host_receipt_pin)=={'bytes','sha256'} and type(host_receipt_pin['bytes'])is int and 0<host_receipt_pin['bytes']<=8192 and type(host_receipt_pin['sha256'])is str and re.fullmatch('[0-9a-f]{64}',host_receipt_pin['sha256']),'Externally pinned host receipt')
    host=parse(capture(host_path,8192,host_receipt_pin))
    need(host['schema']=='slicetca_host_exit_v1' and type(host['exit_code'])is int and host['exit_code']==0 and host['natural_exit'] is True and host['process_reaped'] is True and host['timed_out'] is False,'Observed successful natural host exit required')
    need(host['attempt']==str(attempt) and host['panel']==panel_pin and host['execution']==terminal['execution'] and host['entry_completion']==pin(terminal_raw) and host['prediction']==record['prediction'],'Exact external host completion joins')
    need(type(host['host_seconds']) in (int,float) and 0<=host['host_seconds']<=terminal['whole_operation_limit_seconds'] and type(host['owned_allocated_bytes'])is int and 0<host['owned_allocated_bytes']<=CASE_WRITE_RESERVE,'Bounded enclosing host supervisor and final allocation')
    capture(attempt/'predictions.json',PRED_CAP,record['prediction']);capture(attempt/'snapshot/CASE.json',65536,bind['snapshot']['CASE.json'])
    return record,bind

def score_closed(repo,attempt,panel_dir,panel_pin,truth,truth_sha,output,host_receipt,host_receipt_pin):
    output=path(output);need(not os.path.lexists(output) and output.parent.is_dir(),'Fresh private grade path')
    record,bind=closed_for_score(attempt,panel_dir,panel_pin,host_receipt,host_receipt_pin)
    need(truth_sha==bind['truth']['sha256'],'Truth pin from the same operator case binding')
    _,mods=bindings(repo)
    # Existing scorer validates the entire candidate artifact before opening truth.
    result=mods['score'].score_files(Path(attempt)/'predictions.json',Path(attempt)/'snapshot/CASE.json',path(truth),truth_sha)
    need(result['input_pins']=={'case':bind['snapshot']['CASE.json'],'submission':record['prediction'],'truth':bind['truth']},'Grader consumed the same captured case/prediction and bound private truth')
    result['executor_panel']=panel_pin;result['executor_program']=record['program'];result['executor_arm']=record['arm']
    return save(output,encoded(result),100000)

def main():
    a=argparse.ArgumentParser();sub=a.add_subparsers(dest='action',required=True)
    f=sub.add_parser('freeze');f.add_argument('--program-a',required=True);f.add_argument('--program-b',required=True);f.add_argument('--panel',required=True);f.add_argument('--candidate-seconds',required=True,type=int);f.add_argument('--memory-bytes',required=True,type=int)
    for action in ('case','score-closed'):
        q=sub.add_parser(action);q.add_argument('--repo',required=True);q.add_argument('--panel',required=True);q.add_argument('--panel-bytes',required=True,type=int);q.add_argument('--panel-sha256',required=True);q.add_argument('--attempt',required=True)
        if action=='case':
            q.add_argument('--arm',choices=['A','B'],required=True);q.add_argument('--case-root',required=True);q.add_argument('--case-binding-bytes',type=int,required=True);q.add_argument('--case-binding-sha256',required=True);q.add_argument('--neural',required=True);q.add_argument('--other-reserve-bytes',required=True,type=int);q.add_argument('--docker-socket',required=True)
        else:
            q.add_argument('--truth',required=True);q.add_argument('--truth-sha256',required=True);q.add_argument('--output',required=True)
            q.add_argument('--host-exit-receipt',required=True);q.add_argument('--host-exit-bytes',required=True,type=int);q.add_argument('--host-exit-sha256',required=True)
    v=a.parse_args()
    if v.action=='freeze':result=freeze(v.program_a,v.program_b,v.panel,v.candidate_seconds,v.memory_bytes)
    else:
        pp={'bytes':v.panel_bytes,'sha256':v.panel_sha256}
        if v.action=='case':result=run_case(v.repo,v.panel,pp,v.arm,v.case_root,{'bytes':v.case_binding_bytes,'sha256':v.case_binding_sha256},v.neural,v.attempt,v.other_reserve_bytes,v.docker_socket)
        else:result=score_closed(v.repo,v.attempt,v.panel,pp,v.truth,v.truth_sha256,v.output,v.host_exit_receipt,{'bytes':v.host_exit_bytes,'sha256':v.host_exit_sha256})
    print(json.dumps({k:v for k,v in result.items() if k in ('status','bytes','sha256','all_resources_closed')}))
    return 0 if v.action!='case' or result['status']=='captured' else 1
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'failed','error_type':type(error).__name__,'partials_preserved':True}));raise SystemExit(1)
