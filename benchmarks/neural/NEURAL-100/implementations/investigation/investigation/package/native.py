"""Task-specific native lifecycle primitives; exact reviewed Docker class retained."""
import base64,hashlib,json,os,re,selectors,signal,stat,subprocess,time,uuid
from pathlib import Path
IMAGE=None
READY_TMPFS='rw,nosuid,nodev,noexec,size=4096,uid=65534,gid=65534,mode=0700'
MAX_READY_PROBES=16
READY_SECONDS=30
LABEL="org.neurobench.neural100-program-owner"
PRED_CAP=64000000
CLAIMS_CAP=1000000
GRADE_CAP=2000000
AGGREGATE_CAP=65000000
CAPTURE_REPLY=86670000
OUTPUT_CAPS={'candidate':{'report.json':PRED_CAP,'claims.json':CLAIMS_CAP},'grade':{'grade.json':GRADE_CAP}}
HOLDER_MEMORY=1073741824
VOLUME_OPTIONS="size=67108864,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev"
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

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)

def wait_holder_ready(d,holder,end,kind):
    need(kind in OUTPUT_CAPS,'Exact initialized holder output role')
    # One readiness allowance is clipped by the original phase work deadline.
    ready_end=min(end,time.monotonic()+READY_SECONDS)
    argv=['exec',holder['id'],'python','-I','-B','/trusted/holder.py','ready','--owner-token',holder['owner'],'--role',kind]
    for probe in range(MAX_READY_PROBES):
        need(time.monotonic()<ready_end,'original holder readiness deadline')
        value=parse(call(d,argv,ready_end,'holder_ready',4096))
        need(type(value)is dict and set(value)=={'ready','role'} and value['role']==kind and type(value['ready'])is bool,'exact typed holder readiness')
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
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('neural100-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

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


def grade_command(memory,export_sha,source):
    need(type(source)is dict and set(source)=={'bytes','sha256'} and type(source['bytes'])is int and source['bytes']>0
        and type(source['sha256'])is str and re.fullmatch('[0-9a-f]{64}',source['sha256']),'Exact externally selected source manifest')
    need(type(export_sha)is str and re.fullmatch('[0-9a-f]{64}',export_sha),'Exact selected export identity')
    return ['-I','-B','/entry.py',str(memory),export_sha,str(source['bytes']),source['sha256']]

def create_args(item,role,mounts,memory,image,export_sha,source=None):
    if role=='holder':
        need(item.get('capture_role') in OUTPUT_CAPS,'Exact holder output role')
        cmd=['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--role',item['capture_role']]
    elif role=='candidate':cmd=['-I','-B','/entry.py',str(memory)]
    else:need(role=='grade','exact phase role');cmd=grade_command(memory,export_sha,source)
    size=PRED_CAP if role!='grade' else GRADE_CAP
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--cpus','1','--memory',str(memory),'--memory-swap',str(memory),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize='+str(size)+':'+str(size)]
    if role=='holder':args+=['--init=false','--tmpfs','/ready:'+READY_TMPFS]
    else:args+=['--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=33554432']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):args+=['--env',key+'=1']
    return args+mounts_argv(mounts)+['--entrypoint','python',image,*cmd]

def admission(value,item,role,mounts,memory,image,export_sha,source=None):
    owned(value,item,item['owner']);h=value['HostConfig'];cfg=value['Config']
    need(value['Image']==cfg['Image']==image and cfg['User']=='65534:65534' and cfg['Entrypoint']==['python'],'exact selected image/user/entry')
    need(role in ('holder','candidate','grade'),'exact admitted phase role')
    if role=='holder':
        need(item.get('capture_role') in OUTPUT_CAPS,'Exact admitted holder role')
        expected=['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--role',item['capture_role']]
    elif role=='candidate':expected=['-I','-B','/entry.py',str(memory)]
    else:expected=grade_command(memory,export_sha,source)
    need(cfg['Cmd']==expected and h['Memory']==h['MemorySwap']==memory and h['NanoCpus']==1000000000 and h['PidsLimit']==64,'exact command/resources')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['CgroupnsMode']=='private' and h['LogConfig']['Type']=='none','isolation/no logs')
    need(h.get('Privileged') is False and not h.get('CapAdd') and not h.get('Devices') and not h.get('DeviceRequests') and h.get('PidMode') in ('','private') and h.get('IpcMode')=='private','no device/host namespaces')
    need(h['CapDrop']==['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no' and h['AutoRemove'] is False and h['ShmSize']==16777216,'no capabilities/restarts/extra shared memory')
    actual={x['Destination']:(x['Type'],x['Name'] if x['Type']=='volume' else x['Source'],x['RW']) for x in value['Mounts']}
    need(len(value['Mounts'])==len(mounts) and actual=={k:(kind,str(source),rw) for k,(kind,source,rw) in mounts.items()},'exact mounts')
    need(all(not rw for kind,_,rw in mounts.values() if kind=='bind'),'all host bindings readonly')
    need(h.get('Tmpfs')=={'/ready':READY_TMPFS} if role=='holder' else h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size=33554432'},'exact private readiness or producer scratch')
    if role=='holder':need(h.get('Init') is False,'Holder PID1 profile disables injected init')
    size=GRADE_CAP if role=='grade' else PRED_CAP
    limits={x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']};need(limits=={'core':(0,0),'nofile':(128,128),'fsize':(size,size)},'exact file bound')

def capture_chars(n):
    need(type(n)is int and 0<n<=PRED_CAP,"exact decimal report extent")
    return 4*((n+2)//3)

def output_reply(raw,role):
    need(type(role)is str and role in OUTPUT_CAPS,"selected capture role")
    need(type(raw)is bytes and len(raw)<=CAPTURE_REPLY,'bounded envelope')
    obj=parse(raw);need(type(obj)is dict and set(obj)=={'schema','role','outputs'}
        and obj['schema']=='neural100_multi_output_capture_v1' and obj['role']==role,'trusted role-bound opaque schema')
    rows=obj['outputs'];caps=OUTPUT_CAPS[role]
    need(type(rows)is dict and set(rows)==set(caps),'exact role output names')
    outputs={}
    for name,cap in caps.items():
        row=rows[name]
        need(type(row)is dict and set(row)=={'bytes','sha256','base64'},'exact opaque artifact')
        need(type(row['bytes'])is int and 0<row['bytes']<=cap and type(row['base64'])is str
            and len(row['base64'])==capture_chars(row['bytes']),'bounded exact encoded length')
        need(type(row['sha256'])is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'exact output digest')
        body=base64.b64decode(row['base64'],validate=True)
        need(pin(body)=={k:row[k] for k in ('bytes','sha256')},'opaque output pin')
        outputs[name]=body
    need(sum(map(len,outputs.values()))<=(AGGREGATE_CAP if role=='candidate' else GRADE_CAP),'exact aggregate capture cap')
    return outputs

def phase(s,here,mount_input,program_or_report,attempt,role,source,budget,deadline,export_sha):
    """One producer/holder/volume; independent CLI groups must close on success."""
    need(role in ('candidate','grade'),'exact phase')
    seconds=s['candidate_seconds'] if role=='candidate' else s['grade_seconds']
    memory=s['memory_bytes'] if role=='candidate' else s['grade_memory_bytes']
    need(type(seconds)is int and seconds>0 and type(memory)is int and memory>0,'Explicit positive phase resources')
    caps=OUTPUT_CAPS[role]
    if role=='grade':grade_command(memory,export_sha,source)
    started=time.monotonic();end=min(deadline,started+seconds+150);work=end-45
    prefix='neural100-'+uuid.uuid4().hex[:24]
    d=Docker(s['docker_binary'],s['docker_socket']);items=[];closures=[]
    output=None;natural=None;error=None;closed_before_capture=False
    def publish(path,value,extent=8192):return c.save(path,c.encoded(value),extent,budget.tick,budget.write)
    def item(label,kind):
        row=dict(kind=kind,name=prefix+'-'+label,owner=prefix+'/'+label,attempted=False,acknowledged=False)
        if label=='holder':row['capture_role']=role
        publish(attempt/('INTENT-'+label+'.json'),dict(resource=row,creation_obligation_until_closed=True,phase=role))
        items.append(row);return row
    def before(row):need(resource_inventory(d,row,row['owner'],work,'before_'+row['kind'])==[],'fresh exact resource')
    def container(row,kind,mounts,mem):
        before(row);row['attempted']=True
        ident=call(d,create_args(row,kind,mounts,mem,s['image'],export_sha,source),work,'create_'+kind,4096,12).decode().strip()
        need(re.fullmatch('[a-f0-9]{64}',ident),'acknowledged exact container');row.update(id=ident,acknowledged=True)
        admission(inspect(d,'container',ident,work,'admit_'+kind),row,kind,mounts,mem,s['image'],export_sha,source)
    try:
        need(stat.S_ISSOCK(path(s['docker_socket']).stat().st_mode),'existing Unix socket')
        image=parse(call(d,['image','inspect',s['image'],'--format','{{json .}}'],work,'image'))
        need(image['Id']==s['image'] and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']),'existing exact image without implicit processes/volumes')
        volume=item('volume','volume');before(volume);volume['attempted']=True
        returned=call(d,['volume','create','--driver','local','--label',LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+VOLUME_OPTIONS,volume['name']],work,'volume_create',4096).decode().strip()
        need(returned==volume['name'],'exact volume ack');volume['acknowledged']=True
        v=inspect(d,'volume',volume['name'],work,'volume_admit');owned(v,volume,volume['owner'])
        need(v['Driver']=='local' and v['Options']==dict(type='tmpfs',device='tmpfs',o=VOLUME_OPTIONS),'exact64MiB output volume')
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',here/'holder.py',False),'/capture':('volume',volume['name'],False)}
        container(holder,'holder',hm,HOLDER_MEMORY);call(d,['container','start',holder['id']],work,'holder_start',4096)
        wait_holder_ready(d,holder,work,role)
        producer=item(role,'container')
        entry='candidate_entry.py' if role=='candidate' else 'trusted_entry.py'
        mounts={'/entry.py':('bind',here/entry,False),'/output':('volume',volume['name'],True)}
        if role=='candidate':mounts.update({'/input':('bind',mount_input,False),'/submission/program.py':('bind',program_or_report,False)})
        else:mounts.update({'/package':('bind',mount_input,False),'/trustedgrade':('bind',here,False),
            '/submission/report.json':('bind',program_or_report/'report.json',False),
            '/submission/claims.json':('bind',program_or_report/'claims.json',False),
            '/submission/CLOSURE.json':('bind',program_or_report/'CLOSURE.json',False)})
        container(producer,role,mounts,memory)
        begin=time.monotonic();need(work-begin>seconds+1,'Original work must cover selected producer interval and one-second transport margin');call(d,['container','start',producer['id']],work,'producer_start',4096)
        raw=d(['container','wait',producer['id']],min(work,begin+seconds),'producer_wait',4096)
        need(raw.strip()==b'0','natural producer zero')
        v=inspect(d,'container',producer['id'],work,'producer_exit');owned(v,producer,producer['owner']);state=v['State']
        natural={k:state[k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
        c.validate_natural_exit(natural)
        closed=retire(d,producer,work);closures.append(closed);need(closed['closed'],'producer gone before capture');items.remove(producer);closed_before_capture=True
        # The complete two-artifact envelope fits; artifact contents never enter journals.
        output=output_reply(call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','capture','--owner-token',holder['owner'],'--role',role],work,'opaque_capture',CAPTURE_REPLY,60),role)
    except BaseException as exc:error=type(exc).__name__
    finally:
        for row in reversed(items):
            try:closures.append(retire(d,row,end))
            except BaseException as exc:closures.append(dict(kind=row['kind'],name=row['name'],closed=False,error_type=type(exc).__name__))
    good=error is None and output is not None and closed_before_capture and len(closures)==3 and all(x['closed'] is True for x in closures) and d.reaped and natural is not None and time.monotonic()<end
    result=dict(schema='neural100_owned_phase_v1',phase=role,source=source,status='failed',attempt_prefix=prefix,closures=closures,all_native_resources_closed=bool(good),cli_reaped=d.reaped,natural_exit=natural,producer_closed_before_capture=closed_before_capture,error_type=error,command_metadata=d.records,numerical_grading_not_certified_by_capture=True,recovery_may_be_required=not good)
    if good:
        c.before(end);result['outputs']={}
        for name,body in output.items():
            result['outputs'][name]=c.save(attempt/name,body,caps[name],budget.tick,budget.write)
        result['status']='captured'
    result['elapsed_seconds']=time.monotonic()-started
    publish(attempt/'NATIVE.json',result,262144)
    need(good and time.monotonic()<end and result['status']=='captured','complete native closure before original phase deadline')
    return result
