"""OpenBMI adaptive-only derivative: retained tmpfs/holder lifecycle plus framed broker.

Frozen/reference panels continue to call the unchanged incumbent native module.
This source has not qualified or executed a native/model/scientific route.
"""
from broker_factory import ContextBroker
import base64,hashlib,json,os,re,selectors,signal,stat,subprocess,time,uuid
from pathlib import Path
IMAGE="sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156"
LABEL="org.neurobench.neural083-program-owner"
PROFILE={k:dict(cap=100000,volume=8388608,memory=134217728,reply=400000,responses=16000000,name="predictions.json") for k in ("infer",)}
PROFILE["fit"]=dict(cap=536870912,volume=553648128,memory=4294967296,reply=715840000,responses=1000000000,name="model.bin")
MAX_READY_PROBES=16
READY_SECONDS=30
READY_TMPFS="rw,noexec,nosuid,nodev,size=4096,mode=0700,uid=65534,gid=65534"
VOLUME_OPTIONS="size=8388608,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev"
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

class CommandError(RuntimeError):pass

class Docker:
    """Streaming-capped CLI, no attachment to candidate stdout or log retrieval."""
    def __init__(self,binary,socket):
        self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
    def __call__(self,args,end,phase,cap=131072):
        start=time.monotonic();need(end-start>1,'Command deadline')
        p=None;s=None;bufs={'out':bytearray(),'err':bytearray()};error=None;rc=None
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;group_error=None
        self.reaped=False
        try:
            p=subprocess.Popen(self.prefix+args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True)
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    if not raw:s.unregister(k.fileobj);continue
                    need(sum(map(len,bufs.values()))+len(raw)<=cap,'Streaming CLI cap');bufs[k.data].extend(raw)
            rc=p.wait(timeout=max(.01,end-time.monotonic()));child_reaped=True
            need(rc==0,'Docker command failure')
            try:os.killpg(p.pid,0)
            except ProcessLookupError:group_absent=True
            else:
                survivor_observed=True
                raise CommandError('Owned CLI group survives leader exit')
            need(time.monotonic()<end,'CLI group observation before original deadline')
            return bytes(bufs['out'])
        except BaseException as e:
            error=type(e).__name__;raise
        finally:
            # One shared cleanup interval, never a new per-descendant allowance.
            cleanup_end=min(end,time.monotonic()+1)
            if p is not None and not group_absent:
                live=False
                try:os.killpg(p.pid,0);live=True
                except ProcessLookupError:group_absent=True
                except BaseException as e:cleanup_ok=False;group_error=type(e).__name__
                if live:
                    try:os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError:group_absent=True
                    except BaseException as e:cleanup_ok=False;group_error=type(e).__name__
            if p is not None and not child_reaped:
                try:rc=p.wait(timeout=max(0,cleanup_end-time.monotonic()));child_reaped=True
                except BaseException:cleanup_ok=False
            if p is not None and not group_absent:
                while True:
                    try:os.killpg(p.pid,0)
                    except ProcessLookupError:group_absent=True;break
                    except BaseException as e:cleanup_ok=False;group_error=type(e).__name__;break
                    left=cleanup_end-time.monotonic()
                    if left<=0:break
                    time.sleep(min(.01,left))
            if p is not None and not group_absent:cleanup_ok=False
            if s is not None:
                try:s.close()
                except BaseException:cleanup_ok=False
            if p is not None:
                for stream in (p.stdout,p.stderr):
                    if stream is not None:
                        try:stream.close()
                        except BaseException:cleanup_ok=False
            cleanup_in_time=time.monotonic()<cleanup_end
            cleanup_ok=cleanup_ok and cleanup_in_time
            self.reaped=previous_reaped and child_reaped and cleanup_ok and group_absent
            self.records.append({'phase':phase,'returncode':rc,'error_type':error,'observed_retained_bytes':sum(map(len,bufs.values())),'seconds':time.monotonic()-start,'client_reaped':child_reaped,'cleanup_complete':cleanup_ok,'cleanup_before_original_cutoff':cleanup_in_time,'owned_group_absence_observed':group_absent,'leader_exited_with_group_alive':survivor_observed,'group_probe_or_cleanup_error':group_error})
            if time.monotonic()>=cleanup_end:
                cleanup_ok=False;self.reaped=False
                self.records[-1]['cleanup_complete']=False;self.records[-1]['cleanup_before_original_cutoff']=False
            if not cleanup_ok and error is None:raise CommandError('CLI cleanup incomplete')

class BoundedDocker(Docker):
    """Preventive per-case journal/response bound inside the existing16MB debit."""
    def __init__(self,binary,socket,kind):
        super().__init__(binary,socket);self.calls=0;self.response_reservations=0;self.profile=PROFILE[kind]
    def __call__(self,args,end,phase,cap=131072):
        need(type(cap)is int and 0<cap<=self.profile['reply'],'bounded exact CLI reply cap')
        need(self.calls<64 and self.response_reservations+cap+1<=self.profile['responses'],'whole case CLI allowance')
        self.calls+=1;self.response_reservations+=cap+1
        return super().__call__(args,end,phase,cap)

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)

def wait_holder_ready(d,holder,end,kind=None):
    # One readiness allowance is clipped by the original phase work deadline.
    ready_end=min(end,time.monotonic()+READY_SECONDS)
    argv=['exec',holder['id'],'python','-I','-B','/trusted/holder.py','ready','--owner-token',holder['owner'],'--kind',kind]
    for probe in range(MAX_READY_PROBES):
        need(time.monotonic()<ready_end,'original holder readiness deadline')
        value=parse(call(d,argv,ready_end,'holder_ready',4096))
        need(type(value)is dict and set(value)=={'ready'} and type(value['ready'])is bool,'exact typed holder readiness')
        need(time.monotonic()<ready_end,'holder readiness returned before original deadline')
        if value['ready'] is True:return
        if probe+1<MAX_READY_PROBES:
            left=ready_end-time.monotonic();need(left>0,'original holder readiness interval')
            time.sleep(min(.05,left))
    raise ValueError('holder readiness probe limit')

def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('neural083-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

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

def create_args(item,role,mounts,memory,kind,frame_bytes):
    cmd=['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--kind',kind] if role=='holder' else ['-I','-B','/entry.py',str(memory),kind,str(frame_bytes)]
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--cpus','1','--memory',str(memory),'--memory-swap',str(memory),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize=536870912:536870912']
    if role=='candidate':args+=['--interactive']
    if role=='holder':args+=['--init=false','--tmpfs','/ready:'+READY_TMPFS]
    else:args+=['--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=33554432']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):args+=['--env',key+'=1']
    return args+mounts_argv(mounts)+['--entrypoint','python',IMAGE,*cmd]

def admission(value,item,role,mounts,memory,kind,frame_bytes):
    owned(value,item,item['owner']);h=value['HostConfig'];c=value['Config']
    need(value['Image']==c['Image']==IMAGE and c['User']=='65534:65534' and c['Entrypoint']==['python'],'Exact image/user/entry')
    expected=['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--kind',kind] if role=='holder' else ['-I','-B','/entry.py',str(memory),kind,str(frame_bytes)]
    need(c['Cmd']==expected and h['Memory']==h['MemorySwap']==memory and h['NanoCpus']==1000000000 and h['PidsLimit']==64,'Exact command/resources')
    need(c.get('Tty') is False and c.get('OpenStdin') is (role=='candidate'),'Exact adaptive non-TTY stdin binding')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['CgroupnsMode']=='private' and h['LogConfig']['Type']=='none','Isolation and no logs')
    need(h.get('Privileged') is False and not h.get('CapAdd') and not h.get('Devices') and not h.get('DeviceRequests') and h.get('PidMode') in ('','private') and h.get('IpcMode')=='private','No device or host namespace access')
    need(h['CapDrop']==['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no' and h['AutoRemove'] is False and h['ShmSize']==16777216,'No capabilities/restarts or extra shared memory')
    actual={x['Destination']:(x['Type'],x['Name'] if x['Type']=='volume' else x['Source'],x['RW']) for x in value['Mounts']}
    need(len(value['Mounts'])==len(mounts) and actual=={k:(kind,str(source),rw) for k,(kind,source,rw) in mounts.items()},'Exact mounts; no host writable candidate bind')
    need(all(not rw for kind,_,rw in mounts.values() if kind=='bind'),'All host bindings read-only')
    need(h.get('Tmpfs')=={'/ready':READY_TMPFS} if role=='holder' else h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size=33554432'},'Exact private readiness or bounded scratch')
    if role=='holder':need(h.get('Init') is False,'Holder PID1 profile disables injected init')
    limits={x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']};need(limits=={'core':(0,0),'nofile':(128,128),'fsize':(536870912,536870912)},'Bounded file extent')

def output_reply(raw,kind):
    PRED_CAP=PROFILE[kind]["cap"]
    obj=parse(raw);need(type(obj)is dict and set(obj)=={'schema','kind','bytes','sha256','base64'} and obj['schema']=='neural083-capture-v1' and obj['kind']==kind,'Trusted capture schema')
    need(type(obj['bytes'])is int and 0<obj['bytes']<=PRED_CAP and type(obj['base64'])is str and len(obj['base64'])<=4*((PRED_CAP+2)//3),'Bounded captured output')
    body=base64.b64decode(obj['base64'],validate=True);need(pin(body)=={k:obj[k] for k in ('bytes','sha256')},'Opaque output pin');return body

def attached(d,identity,end,seconds,phase_broker,context):
    """Fixed interactive CLI plus unchanged bounded pump; own group cleanup.

    This is a concrete subprocess path, not a candidate-supplied callback.
    The pump owns framing; this adapter retains the incumbent stronger process
    group absence requirement, including descendants after a leader exits.
    """
    need(re.fullmatch('[a-f0-9]{64}',identity),'Exact attached container identity')
    need(end-time.monotonic()>seconds+1,'Original producer and cleanup interval')
    previous_reaped=d.reaped;d.reaped=False
    p=None;leader_reaped=False;group_absent=False;cleanup_ok=True
    survivor=False;error=None;cancel_error=None;raw=None
    started=time.monotonic()
    try:
        p=subprocess.Popen(d.prefix+['container','start','--attach','--interactive',identity],
              stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
              env=d.env,bufsize=0,start_new_session=True)
        remaining=min(end-1,started+seconds)-time.monotonic()
        raw=context.modules['morse_docker'].pump(p,phase_broker,context.pump_limits(remaining))
        need(type(p.returncode)is int and p.returncode==0 and raw['success'] is True,
             'Natural attached candidate zero and complete framed exchange')
        leader_reaped=True
        try:os.killpg(p.pid,0)
        except ProcessLookupError:group_absent=True
        else:
            survivor=True
            raise CommandError('Owned attached group survives leader exit')
    except BaseException as exc:
        error=type(exc).__name__
    finally:
        try:phase_broker.cancel()
        except BaseException as exc:cancel_error=type(exc).__name__;cleanup_ok=False
        cleanup_end=min(end,time.monotonic()+1)
        if p is not None and not group_absent:
            live=False
            try:os.killpg(p.pid,0);live=True
            except ProcessLookupError:group_absent=True
            except BaseException:cleanup_ok=False
            if live:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:group_absent=True
                except BaseException:cleanup_ok=False
        if p is not None and not leader_reaped:
            try:p.wait(timeout=max(0,cleanup_end-time.monotonic()));leader_reaped=True
            except BaseException:cleanup_ok=False
        if p is not None and not group_absent:
            while True:
                try:os.killpg(p.pid,0)
                except ProcessLookupError:group_absent=True;break
                except BaseException:cleanup_ok=False;break
                left=cleanup_end-time.monotonic()
                if left<=0:break
                time.sleep(min(.01,left))
        if p is not None:
            for stream in (p.stdin,p.stdout,p.stderr):
                try:stream.close()
                except BaseException:cleanup_ok=False
        cleanup_in_time=time.monotonic()<cleanup_end
        cleanup_ok=cleanup_ok and leader_reaped and group_absent and cleanup_in_time
        d.reaped=previous_reaped and cleanup_ok
    success=(error is None and cancel_error is None and cleanup_ok and raw is not None
             and raw.get('success') is True and raw.get('broker_thread_terminal') is True)
    return {'schema':'openbmi-adaptive-attached-v1','success':bool(success),
            'error_type':error,'cancel_error':cancel_error,'pump':raw,
            'client_reaped':leader_reaped,'owned_group_absence_observed':group_absent,
            'leader_exited_with_group_alive':survivor,'cleanup_complete':bool(cleanup_ok),
            'cleanup_before_original_cutoff':cleanup_in_time,'seconds':time.monotonic()-started,
            'native_qualification':False}

def phase(s,here,current,program,model,attempt,kind,ordinal,source,budget,deadline,broker):
    """Adaptive fit/infer only, full broker closure before holder capture."""
    need(isinstance(broker,ContextBroker) and broker.path=='real_future_https_child','Concrete adaptive context broker required')
    phase_broker=broker.begin_phase(kind)
    broker_record=None;attach_record=None;broker_closed=False
    need(kind in PROFILE and (model is not None)==(kind=='infer'),'sealed model only in inference')
    prof=PROFILE[kind];seconds=s[kind+'_seconds'] if kind in ('fit','infer') else s['reference_seconds'];started=time.monotonic();end=min(deadline,started+seconds+130);work=end-35
    prefix='neural083-'+uuid.uuid4().hex[:24];d=BoundedDocker(s['docker_binary'],s['docker_socket'],kind)
    items=[];closures=[];body=None;natural=None;error=None;closed_before_capture=False
    def publish(path,value,cap=8192):return c.save(path,c.encoded(value),cap,budget.tick,budget.write)
    def item(role,which):
        row=dict(kind=which,name=prefix+'-'+role,owner=prefix+'/'+role,attempted=False,acknowledged=False)
        publish(attempt/('INTENT-'+role+'.json'),dict(resource=row,creation_obligation_until_closed=True));items.append(row);return row
    def before(row):need(resource_inventory(d,row,row['owner'],work,'before_'+row['kind'])==[],'fresh exact resource')
    def container(row,role,mounts,memory):
        before(row);row['attempted']=True
        identity=call(d,create_args(row,role,mounts,memory,kind,broker.limits['frame_bytes']),work,'create_'+role,4096,12).decode().strip()
        need(re.fullmatch('[a-f0-9]{64}',identity),'exact acknowledged container');row.update(id=identity,acknowledged=True)
        admission(inspect(d,'container',identity,work,'admit_'+role),row,role,mounts,memory,kind,broker.limits['frame_bytes'])
    try:
        need(stat.S_ISSOCK(path(s['docker_socket']).stat().st_mode),'existing Unix Docker socket')
        image=parse(call(d,['image','inspect',IMAGE,'--format','{{json .}}'],work,'image'))
        need(image['Id']==IMAGE and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']),'fixed cached image without implicit processes/volumes')
        volume=item('volume','volume');before(volume);volume['attempted']=True
        options='size='+str(prof['volume'])+',uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
        returned=call(d,['volume','create','--driver','local','--label',LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,volume['name']],work,'volume_create',4096).decode().strip()
        need(returned==volume['name'],'exact volume acknowledgment');volume['acknowledged']=True
        v=inspect(d,'volume',volume['name'],work,'volume_admit');owned(v,volume,volume['owner'])
        need(v['Driver']=='local' and v['Options']==dict(type='tmpfs',device='tmpfs',o=options),'exact selected bounded tmpfs')
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',here/'holder.py',False),'/capture':('volume',volume['name'],False)}
        container(holder,'holder',hm,prof['memory']);call(d,['container','start',holder['id']],work,'holder_start',4096);wait_holder_ready(d,holder,work,kind)
        candidate=item('candidate','container')
        mounts={'/submission/program.py':('bind',program,False),'/entry.py':('bind',here/'adaptive_entry.py',False),'/input':('bind',current,False),'/output':('volume',volume['name'],True)}
        for name in ('openbmi_agent_tools.py','morse_bootstrap.py','morse_protocol.py','AGENT_INSTRUCTIONS.json'):
            mounts['/trusted/'+name]=('bind',here/name,False)
        if model is not None:mounts['/model/model.bin']=('bind',model,False)
        container(candidate,'candidate',mounts,s['memory_bytes'])
        need(work-time.monotonic()>seconds+1,'full selected producer interval remains')
        # Reserve the captured pump's bounded reads, including failure overshoot,
        # before starting candidate code. Host API child bytes have separate
        # explicit model request/response operands in the paired plan.
        budget.read(broker.stream_read_reservation()+broker.model_child_read_reservation())
        begin=time.monotonic()
        attach_record=attached(d,candidate['id'],work,seconds,phase_broker,broker)
        broker_record=broker.finish_phase(kind,successful=attach_record['success'],
            broker_thread_terminal=(attach_record.get('pump') or {}).get('broker_thread_terminal'))
        broker_closed=True
        need(attach_record['success'] and broker_record['successful'],'terminal adaptive broker/attached stage')
        raw=d(['container','wait',candidate['id']],work,'candidate_wait',4096);need(raw.strip()==b'0','natural candidate zero')
        v=inspect(d,'container',candidate['id'],work,'candidate_exit');owned(v,candidate,candidate['owner'])
        natural={k:v['State'][k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')};c.validate_natural_exit(natural)
        closed=retire(d,candidate,work);closures.append(closed);need(closed['closed'],'candidate removed before output capture')
        items.remove(candidate);closed_before_capture=True
        raw=call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','capture','--owner-token',holder['owner'],'--kind',kind],work,'opaque_capture',prof['reply'],30)
        body=output_reply(raw,kind)
    except BaseException as exc:error=type(exc).__name__
    finally:
        if not broker_closed:
            try:
                broker_record=broker.finish_phase(kind,successful=False,
                    broker_thread_terminal=((attach_record or {}).get('pump') or {}).get('broker_thread_terminal'));broker_closed=True
            except BaseException as exc:
                broker_record={'kind':kind,'context_id':broker.context_id,'successful':False,'closure_error':type(exc).__name__}
        for row in reversed(items):
            try:closures.append(retire(d,row,end))
            except BaseException as exc:closures.append(dict(kind=row['kind'],name=row['name'],closed=False,error_type=type(exc).__name__))
    try:c.validate_cli_commands(d.records,prof['reply'])
    except BaseException as exc:
        if error is None:error=type(exc).__name__
    good=error is None and body is not None and closed_before_capture and len(closures)==3 and all(x['closed'] is True for x in closures) and d.reaped and natural is not None and broker_closed and broker_record.get('successful') is True and time.monotonic()<end
    if not good and broker_closed:
        broker.invalidate_native_phase(kind)
        broker_record['successful']=False
        broker_record['native_lifecycle_failed']=True
    result=dict(image=IMAGE,producer_memory_bytes=s['memory_bytes'],producer_seconds=seconds,program=c.pin(c.capture(program,1048576,None,budget.tick,budget.read)),phase_started_monotonic=started,phase_deadline=end,worker_deadline=deadline,schema='neural083-sequential-native-phase-v2',kind=kind,ordinal=ordinal,source=source,status='failed',closures=closures,all_native_resources_closed=bool(good),cli_reaped=d.reaped,natural_exit=natural,producer_closed_before_capture=closed_before_capture,error_type=error,command_metadata=d.records,private_scoring_called=False)
    if good:result['output']=c.save(attempt/prof['name'],body,prof['cap'],budget.tick,budget.write);result['status']='captured'
    result['broker']={'schema':'openbmi-adaptive-stage-broker-v1','context_id':broker.context_id,'kind':kind,'phase_record':broker_record,'attached':attach_record,'stream_read_reservation_bytes':broker.stream_read_reservation(),'model_child_read_reservation_bytes':broker.model_child_read_reservation(),'native_qualified':False}
    result['elapsed_seconds']=time.monotonic()-started;publish(attempt/'NATIVE.json',result,broker.limits['native_receipt_bytes'])
    need(good and time.monotonic()<end,'complete phase deadline/closure');return result
