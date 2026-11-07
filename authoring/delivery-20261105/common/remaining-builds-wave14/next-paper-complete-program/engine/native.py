"""Owned iSTTC Docker transport. Source construction only; no qualification transfer."""
import base64, hashlib, json, math, os, re, selectors, signal, stat, subprocess, time, uuid
from pathlib import Path, PurePosixPath
LABEL='org.neurobench.isttc-program-owner'
READY_OPTIONS='rw,nosuid,nodev,noexec,size=4096,mode=0700,uid=65534,gid=65534'
HOLDER_MEMORY=134217728
CHUNK=4194304
CHUNK_REPLY=5596504
INVENTORY_REPLY=262144
PROFILES={
 role:dict(memory=8589934592,volume=536870912,file=100000000,files=2,dirs=1,scratch=134217728,scratch_target='/work' if role=='reference' else '/tmp',cpu='4',nano=4000000000)
 for role in ('reproduction','improvement','reference')
}
OUTPUTS={role:{'estimates.csv':100000000,'methods.json':20000} for role in PROFILES}
SUPPORT={
 'reproduction':{'/trusted/entry_common.py':'entry_common.py'},
 'improvement':{'/trusted/entry_common.py':'entry_common.py'},
 'reference':{'/trusted/entry_common.py':'entry_common.py','/trusted/baseline.py':'baseline/baseline.py','/trusted/read_inputs.py':'baseline/read_inputs.py'},
}
for _suffix in ('__init__.py','acfunc.py','tau.py','spike_utils.py','scripts/__init__.py','scripts/calculate_acf.py','scripts/calculate_tau.py','scripts/spike_train_utils.py'):
    SUPPORT['reference']['/trusted/source/src/isttc/'+_suffix]='baseline/source/src/isttc/'+_suffix
CLI_CAPS={name:131072 for name in ('image','volume_admit','admit_holder','admit_reproduction','admit_improvement','admit_reference','producer_exit','cleanup_inspect')}
CLI_CAPS.update({name:4096 for name in ('volume_create','create_holder','holder_start','holder_ready','create_reproduction','create_improvement','create_reference','producer_start','producer_wait','cleanup_kill','cleanup_wait','cleanup_remove')})
CLI_CAPS.update({a+'_'+b+'_'+c:8192 for a in ('before','cleanup','absence') for b in ('container','volume') for c in ('owner','name')})
CLI_CAPS.update(artifact_inventory=INVENTORY_REPLY,artifact_chunk=CHUNK_REPLY)

def need(ok,message):
    if not ok:raise ValueError(message)

def cli_cap(phase):
    need(type(phase)is str and phase in CLI_CAPS,'source-selected CLI phase');return CLI_CAPS[phase]

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))

def path(p):
    p=Path(p);need(p.is_absolute(),'absolute custody path')
    need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unlinked canonical path')
    need(not any(x in str(p) for x in (',','\n','\r','\0')),'unambiguous mount path');return p

def descriptor(p,allow_empty=False):
    need(type(p)is dict and set(p)=={'bytes','sha256'} and type(p['bytes'])is int and p['bytes']>=(0 if allow_empty else 1) and type(p['sha256'])is str and re.fullmatch('[0-9a-f]{64}',p['sha256']),'exact source descriptor');return p

def validate_natural_exit(v):
    need(type(v)is dict and set(v)=={'Status','Running','Dead','Pid','ExitCode','OOMKilled'},'exact natural-six state')
    need(type(v['Status'])is str and v['Status']=='exited','natural exit status')
    for k in ('Running','Dead','OOMKilled'):need(v[k]is False,'strict false stopped/OOM flags')
    for k in ('Pid','ExitCode'):need(type(v[k])is int and v[k]==0,'strict natural integer zero')
    return v

def validate_cli_records(records):
    keys={'phase','returncode','error_type','observed_retained_bytes','seconds','client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed','leader_exited_with_group_alive','group_probe_or_cleanup_error'}
    need(type(records)is list and len(records)>0,'nonempty CLI record list')
    for v in records:
        need(type(v)is dict and set(v)==keys,'strict eleven CLI fields')
        cap=cli_cap(v['phase'])
        need(type(v['returncode'])is int and v['returncode']==0 and v['error_type']is None and v['group_probe_or_cleanup_error']is None,'successful CLI')
        need(type(v['observed_retained_bytes'])is int and 0<=v['observed_retained_bytes']<=cap,'actual phase-specific CLI bytecap')
        need(type(v['seconds'])in (int,float) and math.isfinite(v['seconds']) and v['seconds']>=0,'finite actual CLI duration')
        for k in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed'):need(v[k]is True,'literal completed CLI custody')
        need(v['leader_exited_with_group_alive']is False,'no surviving owned CLI group')
    return records

class CommandError(RuntimeError):pass

class Docker:
    """Streaming-capped CLI, no attachment to candidate stdout or log retrieval."""
    def __init__(self,binary,socket,*,max_calls,reply_budget,publish=lambda name,value:None):
        self.max_calls=max_calls;self.reply_budget=reply_budget;self.reserved=0;self.publish=publish
        self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
    def __call__(self,args,end,phase,cap=131072):
        start=time.monotonic();need(end-start>1,'Command deadline')
        need(type(cap)is int and cap==cli_cap(phase) and len(self.records)<self.max_calls,'exact source-selected command cap/count')
        need(self.reserved+cap<=self.reply_budget,'cumulative CLI response reservation')
        self.reserved+=cap
        self.publish('CLI-INTENT',{'index':len(self.records),'phase':phase,'cap':cap,'original_end':end})
        p=None;s=None;bufs={'out':bytearray(),'err':bytearray()};error=None;rc=None
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;group_error=None
        self.reaped=False
        try:
            p=subprocess.Popen(self.prefix+args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True)
            self.publish('CLI-CHILD',{'index':len(self.records),'phase':phase,'pid':p.pid,'pgid':p.pid,'original_end':end,'independent_group':True})
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    if not raw:s.unregister(k.fileobj);continue
                    need(sum(map(len,bufs.values()))+len(raw)<=cap,'Streaming CLI cap');bufs[k.data].extend(raw)
            rc=p.wait(timeout=max(0,end-time.monotonic()));child_reaped=True
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

def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('isttc-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

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


TIMES={role:dict(setup_seconds=120,producer_seconds=172800,capture_seconds=1800,cleanup_seconds=120) for role in PROFILES}

def relative_name(v):
    need(type(v)is str and 0<len(v.encode())<=512 and not any(c in v for c in ('\\','\0','\n','\r',',')),'bounded relative artifact name')
    p=PurePosixPath(v);need(not p.is_absolute() and str(p)==v and all(x not in ('','.','..') and re.fullmatch('[A-Za-z0-9_][A-Za-z0-9._-]*',x) for x in p.parts) and len(p.parts)<=8,'canonical relative artifact name')
    return v

def validate_request(phase,r):
    keys={'schema','phase_id','image','source','expected_files','entry','entry_support',*TIMES['reproduction']}
    need(type(r)is dict and set(r)==keys and r['schema']=='isttc_owned_phase_request_v1','exact phase request')
    need(phase in PROFILES and type(r['phase_id'])is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',r['phase_id']),'finite phase identity')
    need(type(r['image'])is str and re.fullmatch('sha256:[0-9a-f]{64}',r['image']),'immutable existing image')
    descriptor(r['source'])
    for k,v in TIMES[phase].items():need(type(r[k])is int and r[k]==v,'fixed prospective full phase clocks')
    expected=r['expected_files']
    need(type(expected)is list and expected==sorted(OUTPUTS[phase]),'exact complete role output filenames')
    need(r['entry']==phase+'_entry.py','source-selected fixed role entry')
    support=r['entry_support'];need(type(support)is dict and support==SUPPORT[phase],'exact frozen role helper source-target map')
    for target,source in support.items():
        need(type(target)is str and target.startswith('/trusted/') and relative_name(target[9:]) and relative_name(source),'exact source support target')
        if phase!='reference':need(target=='/trusted/entry_common.py','candidate has no private reference operator')
    return r

def phase_budget(phase,files):
    p=PROFILES[phase]
    # Sum ceil(file_i/chunk) <= ceil(sum/chunk)+n; one additional EOF probe/file.
    need(type(files)is int and files==len(OUTPUTS[phase]),'exact finite role file count')
    total=sum(OUTPUTS[phase].values())
    chunks=(total+CHUNK-1)//CHUNK+2*files
    other_calls=128
    return dict(max_calls=chunks+other_calls+2,
                reply_budget=chunks*CHUNK_REPLY+other_calls*131072+2*INVENTORY_REPLY,
                max_chunks=chunks,host_artifact_bytes=total)

def source_auth(root,expected,executor):
    root=path(root);total=0
    def get(name,declared,cap,allow_empty=False):
        nonlocal total
        relative_name(name);p=path(root/name);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and (0 if allow_empty else 1)<=a.st_size<=cap,'bounded source file')
            total+=a.st_size+1;need(total<=4194304,'full source pass ceiling');executor.read(a.st_size+1);executor.tick()
            b=bytearray()
            while len(b)<=a.st_size:
                executor.tick();x=os.read(fd,min(65536,a.st_size+1-len(b)))
                if not x:break
                b.extend(x)
            z=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
            need(all(getattr(a,k)==getattr(z,k)==getattr(named,k) for k in fields),'stable source capture')
        finally:os.close(fd)
        b=bytes(b);need(pin(b)==descriptor(declared,allow_empty=allow_empty),'full immutable source pin');return b
    raw=get('SOURCE_MANIFEST.json',expected,262144);m=parse(raw)
    need(type(m)is dict and type(m.get('files'))is dict and 1<=len(m['files'])<=128,'bounded source closure')
    need({'engine/native.py','engine/holder.py','reproduction_entry.py','improvement_entry.py','reference_entry.py'}<=set(m['files']),'concrete engine+entries in selected source closure')
    for name,p in sorted(m['files'].items()):get(name,p,1048576,allow_empty=True)
    return {'manifest':expected,'members':len(m['files']),'read_bytes':total,'files':m['files']}

def command(role,item,phase):
    if role=='holder':return ['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--role',phase]
    need(role==phase and phase in PROFILES,'exact producer phase');return ['-I','-B','/entry.py','--request','/request.json']

def create_args(item,role,mounts,memory,image,phase):
    p=PROFILES[phase];size=256 if role=='holder' else p['file']
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--cpus',('1' if role=='holder' else p['cpu']),'--memory',str(memory),'--memory-swap',str(memory),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize='+str(size)+':'+str(size)]
    if role=='holder':args+=['--init=false','--tmpfs','/ready:'+READY_OPTIONS]
    else:args+=['--tmpfs',p['scratch_target']+':rw,nosuid,nodev,noexec,size='+str(p['scratch'])]
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):args+=['--env',key+'=1']
    return args+mounts_argv(mounts)+['--entrypoint','python',image,*command(role,item,phase)]

def admission(v,item,role,mounts,memory,image,phase):
    owned(v,item,item['owner']);h=v['HostConfig'];cfg=v['Config'];p=PROFILES[phase]
    need(v['Image']==cfg['Image']==image and cfg['User']=='65534:65534' and cfg['Entrypoint']==['python'] and cfg['Cmd']==command(role,item,phase),'exact image/user/entry/command')
    for k,want in [('Memory',memory),('MemorySwap',memory),('NanoCpus',1000000000 if role=='holder' else p['nano']),('PidsLimit',64),('ShmSize',16777216)]:need(type(h[k])is int and h[k]==want,'exact typed resource')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs']is True and h['CgroupnsMode']=='private' and h['LogConfig']['Type']=='none','isolation/no logs')
    need(h.get('Privileged')is False and not h.get('CapAdd') and not h.get('Devices') and not h.get('DeviceRequests') and h.get('PidMode')in ('','private') and h.get('IpcMode')=='private','no device/host namespace')
    need(h['CapDrop']==['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no' and h['AutoRemove']is False,'no capability/restarts')
    need(type(v['Mounts'])is list and len(v['Mounts'])==len(mounts),'exact mount cardinality')
    actual={}
    for x in v['Mounts']:
        need(type(x['RW'])is bool and x['Destination'] not in actual,'strict mount flags and unique targets')
        actual[x['Destination']]=(x['Type'],x['Name'] if x['Type']=='volume' else x['Source'],x['RW'])
    need(actual=={k:(kind,str(source),rw) for k,(kind,source,rw) in mounts.items()},'exact mounts')
    need(all(rw is False for kind,_,rw in mounts.values() if kind=='bind'),'no writable host binding')
    if role=='holder':need(h.get('Init')is False,'explicit PID1 keeper without daemon init')
    want_tmp={'/ready':READY_OPTIONS} if role=='holder' else {p['scratch_target']:'rw,nosuid,nodev,noexec,size='+str(p['scratch'])}
    need(h.get('Tmpfs')==want_tmp,'exact private scratch/readiness')
    size=256 if role=='holder' else p['file'];limits={}
    for x in h['Ulimits']:
        need(x['Name'] not in limits and type(x['Soft'])is int and type(x['Hard'])is int,'typed exact limits');limits[x['Name']]=(x['Soft'],x['Hard'])
    need(limits=={'core':(0,0),'nofile':(128,128),'fsize':(size,size)},'exact file bound')

def checked_mounts(phase,readonly_mounts,program,source_dir,request):
    need(type(readonly_mounts)is dict,'explicit readonly mounts')
    need(set(readonly_mounts)=={'/input','/request.json'},'exact role input/request mount whitelist')
    mounts={}
    for target,source in readonly_mounts.items():
        source=path(source);s=source.lstat()
        if target=='/input':need(stat.S_ISDIR(s.st_mode),'preauthenticated complete-view directory')
        else:need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'preauthenticated single-link request')
        mounts[target]=('bind',source,False)
    source_dir=path(source_dir);mounts['/entry.py']=('bind',source_dir/request['entry'],False)
    for target,source in request['entry_support'].items():mounts[target]=('bind',source_dir/source,False)
    if phase!='reference':
        need(program is not None,'one globally frozen program');p=path(program);s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=8388608,'new8MiB candidate-program domain');mounts['/program/program.py']=('bind',p,False)
    else:need(program is None,'trusted reference has no candidate program')
    return mounts

def stamp(v):
    need(type(v)is list and len(v)==9 and all(type(x)is int and x>=0 for x in v),'nine typed immutable stat fields');return v

def artifact_inventory(raw,holder,phase,expected):
    need(type(raw)is bytes and len(raw)<=INVENTORY_REPLY,'bounded inventory response');v=parse(raw);p=PROFILES[phase]
    need(type(v)is dict and set(v)=={'schema','owner','role','root_stamp','directories','files','total_bytes'} and v['schema']=='isttc_capture_inventory_v1' and v['owner']==holder['owner'] and v['role']==phase,'exact attempt-bound inventory')
    stamp(v['root_stamp']);need(type(v['files'])is list and len(v['files'])==len(expected),'complete file inventory')
    total=0;names=[]
    for x in v['files']:
        need(type(x)is dict and set(x)=={'name','bytes','stamp'},'exact file metadata');relative_name(x['name']);stamp(x['stamp'])
        need(type(x['bytes'])is int and 0<x['bytes']<=OUTPUTS[phase].get(x['name'],0) and x['bytes']==x['stamp'][3],'bounded positive artifact extent');total+=x['bytes'];names.append(x['name'])
    need(names==expected and total<=p['volume'] and type(v['total_bytes'])is int and v['total_bytes']==total,'all expected files and exact total')
    ancestors=sorted({str(a) for n in expected for a in PurePosixPath(n).parents if str(a)!='.'})
    need(type(v['directories'])is list and len(v['directories'])==len(ancestors) and len(ancestors)+1<=p['dirs'],'exact necessary directory inventory')
    got=[]
    for x in v['directories']:
        need(type(x)is dict and set(x)=={'name','stamp'},'directory schema');relative_name(x['name']);stamp(x['stamp']);got.append(x['name'])
    need(got==ancestors,'no unlisted or extra empty output directories');return v

def chunk_reply(raw,holder,phase,item,offset,wanted):
    need(type(raw)is bytes and len(raw)<=CHUNK_REPLY,'bounded chunk response');v=parse(raw)
    fields={'schema','owner','role','name','offset','bytes','stamp','eof','sha256','base64'}
    need(type(v)is dict and set(v)==fields and v['schema']=='isttc_capture_chunk_v1' and v['owner']==holder['owner'] and v['role']==phase and v['name']==item['name'],'exact attempt-bound chunk')
    need(type(v['offset'])is int and v['offset']==offset and type(v['bytes'])is int and v['bytes']==wanted,'exact requested chunk interval')
    need(stamp(v['stamp'])==item['stamp'] and type(v['eof'])is bool and v['eof']==(offset+wanted==item['bytes']),'immutable stamp and exact EOF disposition')
    need(type(v['base64'])is str and len(v['base64'])==4*((wanted+2)//3),'exact encoded extent')
    body=base64.b64decode(v['base64'],validate=True)
    need(type(v['sha256'])is str and re.fullmatch('[0-9a-f]{64}',v['sha256']) and pin(body)=={'bytes':wanted,'sha256':v['sha256']},'exact bounded chunk digest');return body

def holder_argv(holder,phase,action):return ['exec',holder['id'],'python','-I','-B','/trusted/holder.py',action,'--owner-token',holder['owner'],'--role',phase]

def wait_ready(d,holder,work,phase):
    ready_end=min(work,time.monotonic()+30)
    for i in range(16):
        need(time.monotonic()<ready_end,'original readiness window')
        v=parse(call(d,holder_argv(holder,phase,'ready'),ready_end,'holder_ready',4096))
        need(type(v)is dict and set(v)=={'ready'} and type(v['ready'])is bool,'strict readiness result')
        if v['ready']is True:return
        if i<15:
            left=ready_end-time.monotonic();need(left>0,'original readiness timeout');time.sleep(min(1.,left))
    raise ValueError('bounded16 readiness probes exhausted')

def fsync_dir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def capture_artifacts(d,holder,phase,expected,output_dir,executor,end):
    first=artifact_inventory(call(d,holder_argv(holder,phase,'inventory'),end,'artifact_inventory',INVENTORY_REPLY,30),holder,phase,expected)
    root=output_dir/'artifacts';root.mkdir(mode=0o700);pins={};written=0
    for row in first['directories']:(root/row['name']).mkdir(mode=0o700)
    for item in first['files']:
        executor.tick();executor.write(item['bytes']);dest=path(root/item['name'])
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);h=hashlib.sha256();offset=0
        try:
            while offset<item['bytes']:
                executor.tick();need(time.monotonic()<end,'original capture deadline')
                count=min(CHUNK,item['bytes']-offset)
                args=holder_argv(holder,phase,'chunk')+['--name',item['name'],'--offset',str(offset),'--length',str(count),'--stamp',encoded(item['stamp']).decode().strip()]
                body=chunk_reply(call(d,args,end,'artifact_chunk',CHUNK_REPLY,60),holder,phase,item,offset,count)
                h.update(body);view=memoryview(body)
                while view:
                    executor.tick();n=os.write(fd,view);need(n>0,'complete stopped artifact write');view=view[n:]
                offset+=len(body);written+=len(body)
            args=holder_argv(holder,phase,'chunk')+['--name',item['name'],'--offset',str(offset),'--length','0','--stamp',encoded(item['stamp']).decode().strip()]
            chunk_reply(call(d,args,end,'artifact_chunk',CHUNK_REPLY,60),holder,phase,item,offset,0)
            os.fsync(fd);need(os.fstat(fd).st_size==item['bytes'],'exact captured extent')
        finally:os.close(fd)
        pins[item['name']]={'bytes':offset,'sha256':h.hexdigest()};executor.tick()
    last=artifact_inventory(call(d,holder_argv(holder,phase,'inventory'),end,'artifact_inventory',INVENTORY_REPLY,30),holder,phase,expected)
    need(encoded(first)==encoded(last),'unchanged whole stopped inventory after complete capture')
    for directory in sorted((root/row['name'] for row in first['directories']),key=lambda p:len(p.parts),reverse=True):fsync_dir(directory)
    fsync_dir(root);fsync_dir(output_dir)
    return dict(files=pins,total_bytes=written,inventory=pin(encoded(first)),capture_complete=True)

def execute(executor,docker,*,phase,request,program,readonly_mounts,output_dir,source_dir,original_deadline,publish):
    """Complete one isolated phase; caller owns source-approved scientific/input joins.

    `publish(name, metadata)` must durably journal before returning. Output bytes
    remain quarantined in output_dir/artifacts until the returned captured receipt.
    A lost worker cannot establish transitive host/Docker closure from its PGID.
    """
    validate_request(phase,request);need(type(original_deadline)in (int,float) and math.isfinite(original_deadline),'original finite absolute deadline')
    started=time.monotonic();timing=TIMES[phase];span=sum(timing.values());end=started+span
    need(end<=original_deadline,'full phase allowance remains inside original whole clock')
    setup_end=started+timing['setup_seconds'];work=end-timing['cleanup_seconds'];p=PROFILES[phase]
    need(type(docker)is dict and set(docker)=={'binary','socket'},'exact local Docker endpoint')
    source_dir=path(source_dir);output_dir=path(output_dir);need(output_dir.is_dir(),'caller-owned fresh phase directory')
    with os.scandir(output_dir) as scan:need(next(scan,None)is None,'fresh output directory before phase')
    limits=phase_budget(phase,len(request['expected_files']));executor.read(limits['reply_budget']);executor.tick()
    prefix='isttc-'+uuid.uuid4().hex[:24];journal_index=0
    def journal(name,v):
        nonlocal journal_index
        publish(str(journal_index).zfill(5)+'-'+name,dict(v,phase_id=request['phase_id'],attempt_prefix=prefix));journal_index+=1
    d=Docker(docker['binary'],docker['socket'],max_calls=limits['max_calls'],reply_budget=limits['reply_budget'],publish=journal)
    items=[];closures=[];natural=None;captured=None;before_source=None;after_source=None;closed_before_capture=False;error=None
    def item(label,kind):
        row=dict(kind=kind,name=prefix+'-'+label,owner=prefix+'/'+label,attempted=False,acknowledged=False)
        journal('RESOURCE-INTENT',dict(resource=row.copy(),creation_obligation_until_closed=True));items.append(row);return row
    def fresh(row):need(resource_inventory(d,row,row['owner'],setup_end,'before_'+row['kind'])==[],'fresh exact resource namespace')
    def container(row,role,mounts,memory):
        fresh(row);row['attempted']=True
        ident=call(d,create_args(row,role,mounts,memory,request['image'],phase),setup_end,'create_'+role,4096,12).decode('ascii').strip()
        need(re.fullmatch('[a-f0-9]{64}',ident),'acknowledged exact container ID');row.update(id=ident,acknowledged=True);journal('RESOURCE-ACK',dict(resource=row.copy()))
        admission(inspect(d,'container',ident,setup_end,'admit_'+role),row,role,mounts,memory,request['image'],phase)
    try:
        before_source=source_auth(source_dir,request['source'],executor)
        mounts=checked_mounts(phase,readonly_mounts,program,source_dir,request)
        need(request['entry'] in before_source['files'] and all(s in before_source['files'] for s in request['entry_support'].values()),'all mounted runtime support in authenticated source closure')
        need(stat.S_ISSOCK(path(docker['socket']).stat().st_mode),'existing Unix socket')
        image=parse(call(d,['image','inspect',request['image'],'--format','{{json .}}'],setup_end,'image'))
        need(image['Id']==request['image'] and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']),'exact existing image without implicit volume/healthprocess')
        volume=item('volume','volume');fresh(volume);volume['attempted']=True
        options='size='+str(p['volume'])+',uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
        returned=call(d,['volume','create','--driver','local','--label',LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,volume['name']],setup_end,'volume_create',4096).decode('ascii').strip()
        need(returned==volume['name'],'exact volume acknowledgement');volume['acknowledged']=True;journal('RESOURCE-ACK',dict(resource=volume.copy()))
        v=inspect(d,'volume',volume['name'],setup_end,'volume_admit');owned(v,volume,volume['owner'])
        need(v['Driver']=='local' and v['Options']==dict(type='tmpfs',device='tmpfs',o=options),'exact output tmpfs profile')
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',source_dir/'engine/holder.py',False),'/capture':('volume',volume['name'],False)}
        container(holder,'holder',hm,HOLDER_MEMORY);call(d,['container','start',holder['id']],setup_end,'holder_start',4096);wait_ready(d,holder,setup_end,phase)
        producer=item(phase,'container');mounts['/output']=('volume',volume['name'],True);container(producer,phase,mounts,p['memory'])
        need(time.monotonic()<setup_end and work-time.monotonic()>timing['producer_seconds']+timing['capture_seconds'],'full producer and capture intervals remain')
        begin=time.monotonic();call(d,['container','start',producer['id']],setup_end,'producer_start',4096)
        raw=d(['container','wait',producer['id']],begin+timing['producer_seconds'],'producer_wait',4096)
        need(raw.strip()==b'0','natural producer zero')
        v=inspect(d,'container',producer['id'],work,'producer_exit');owned(v,producer,producer['owner'])
        natural=validate_natural_exit({k:v['State'][k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')})
        closed=retire(d,producer,work);closures.append(closed);need(closed['closed']is True,'producer removed before capture');items.remove(producer);closed_before_capture=True
        capture_end=min(work,time.monotonic()+timing['capture_seconds'])
        captured=capture_artifacts(d,holder,phase,request['expected_files'],output_dir,executor,capture_end)
    except BaseException as exc:error=type(exc).__name__
    finally:
        for row in reversed(items):
            try:closures.append(retire(d,row,end))
            except BaseException as exc:closures.append(dict(kind=row['kind'],name=row['name'],closed=False,error_type=type(exc).__name__))
    good=error is None and captured is not None and closed_before_capture and len(closures)==3 and all(x['closed']is True for x in closures) and d.reaped is True and natural is not None and time.monotonic()<end
    if good:
        try:
            validate_cli_records(d.records);after_source=source_auth(source_dir,request['source'],executor)
            need(encoded(before_source)==encoded(after_source),'full runtime source closure unchanged');executor.tick();need(time.monotonic()<end,'original full phase deadline')
        except BaseException as exc:error=type(exc).__name__;good=False
    result=dict(schema='isttc_owned_phase_v1',phase=phase,phase_id=request['phase_id'],status='captured' if good else 'failed',source=request['source'],attempt_prefix=prefix,natural_exit=natural,producer_closed_before_capture=closed_before_capture,closures=closures,all_native_resources_closed=(len(closures)==3 and all(x['closed']is True for x in closures)),cli_reaped=d.reaped,command_metadata=d.records,transport_limits=limits,source_before=before_source,source_after=after_source,artifacts=captured if good else None,error_type=error,original_deadline=original_deadline,started=started,phase_end=end,elapsed_seconds=time.monotonic()-started,failure_custody_complete=False,forced_stop_independent_host_and_daemon_state='unknown',automatic_retry_authorized=False,qualification_inherited=False,numerical_grading_called=False)
    journal('PHASE',result)
    executor.tick();need(time.monotonic()<end,'original phase deadline after durable receipt')
    need(good,'phase failed; preserve attempt journal/quarantine for explicit recovery')
    return result
