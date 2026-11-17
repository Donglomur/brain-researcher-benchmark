"""Pinned SliceTCA lifecycle helpers with task namespace/tmpfs constants only.
No private module, numeric payload or Docker operation runs on import.
"""
import argparse,base64,hashlib,json,os,re,selectors,shutil,signal,stat,subprocess,time,types,uuid
from pathlib import Path
IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
LABEL='org.neurobench.cascade44-program-owner'
VOLUME_BYTES=33554432
VOLUME_OPTIONS='size=33554432,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
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
            need(rc==0,'Docker command failure');return bytes(bufs['out'])
        except BaseException as e:
            error=type(e).__name__;raise
        finally:
            # Selector creation, nonblocking setup and registration are also
            # post-launch operations. None may escape client cleanup.
            if p is not None and not child_reaped:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except BaseException:cleanup_ok=False
                try:rc=p.wait(timeout=1);child_reaped=True
                except BaseException:cleanup_ok=False
            if s is not None:
                try:s.close()
                except BaseException:cleanup_ok=False
            if p is not None:
                for stream in (p.stdout,p.stderr):
                    if stream is not None:
                        try:stream.close()
                        except BaseException:cleanup_ok=False
            self.reaped=previous_reaped and child_reaped and cleanup_ok
            self.records.append({'phase':phase,'returncode':rc,'error_type':error,'observed_retained_bytes':sum(map(len,bufs.values())),'seconds':time.monotonic()-start,'client_reaped':child_reaped,'cleanup_complete':cleanup_ok})
            if not cleanup_ok and error is None:raise CommandError('CLI cleanup incomplete')

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)

def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('cascade44-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

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
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--cpus','1','--memory',str(memory),'--memory-swap',str(memory),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize=1048576:1048576']
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
    limits={x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']};need(limits=={'core':(0,0),'nofile':(128,128),'fsize':(1048576,1048576)},'Bounded file extent')

class WriteBudget:
    """Task-local preventive host writes; cleanup never depends on this guard.

    Full own reservation is conservatively retained in every fresh free-space
    check. Failure evidence receives no below-floor exception. File/dir counts
    and allocated extents are bounded before adding each next write.
    """
    def __init__(self,root,other,cap):
        self.root=path(root);need(type(other)is int and other>=0 and type(cap)is int and cap>0,'Write reservation');self.other=other;self.cap=cap;self.written=0
    def check(self,extra=0):
        need(type(extra)is int and extra>=0 and self.written+extra<=self.cap,'Cumulative write budget')
        need(shutil.disk_usage(self.root.parent).free>=FLOOR+self.other+self.cap,'Physical bulk floor')
        used=0;count=0;todo=[self.root]if os.path.lexists(self.root)else []
        while todo:
            p=todo.pop();s=p.lstat();count+=1;need(count<=140,'Bounded owned write tree')
            need(stat.S_ISDIR(s.st_mode)or(stat.S_ISREG(s.st_mode)and s.st_nlink==1),'Ordinary owned write tree');used+=max(s.st_size,s.st_blocks*512);need(used<=self.cap,'Allocated write budget')
            if stat.S_ISDIR(s.st_mode):
                with os.scandir(p)as scan:
                    for x in scan:need(count+len(todo)<140,'Bounded write traversal');todo.append(p/x.name)
        # 64KiB allocation quantum is an explicit conservative filesystem gate.
        need(used+((extra+65535)//65536)*65536+65536<=self.cap,'Prospective allocation budget')
    def destination(self,p):
        p=path(p);need(p==self.root or self.root in p.parents,'Owned write destination');return p
    def sync(self,p):
        fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    def mkdir(self,p,mode=0o700):
        p=self.destination(p);self.check(65536);p.mkdir(mode=mode);self.written+=65536;self.sync(p.parent)
    def save(self,p,body,cap=1000000):
        p=self.destination(p);need(type(body)is bytes and len(body)<=cap,'Bounded next write');self.check(len(body));fp=save(p,body,cap);self.written+=len(body);self.sync(p.parent);return fp
