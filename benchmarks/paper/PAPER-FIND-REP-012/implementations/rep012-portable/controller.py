"""REP012 paired offline tools. Importing this module launches nothing.

The owner supplies current admitted Docker/software identities and an exclusive
daemon window. This source does not grant native execution or model authority.
Candidate input is only ever an argv operand inside its own container.
"""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import threading
import time
import types
import unicodedata

IMAGE = 'sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff'
PYTHON = '/usr/local/bin/python3.12'
RUNTIME_PROFILE = 'rep012-shared-science-arm64-paired-v1'
PACKETS = 'artifacts-build/rep012-matched-paper-packets-001'
DONOR = ('support/lifecycle_engine.py', 7458, '0ce1286318d161adecb3e90cd96b5327f63cf278cd57d2d32b5f7b14b6d2a735')
RECEIPT = (4678, '3956d73682f9ab1150e9acdb298df894bfd24328900b61687f38cd5dc9a9296c')
TMPFS = {'/tmp':'rw,noexec,nosuid,nodev,size=15728640,nr_inodes=2048,mode=1777',
         '/scratch':'rw,noexec,nosuid,nodev,size=16777216,nr_inodes=2048,mode=1777',
         '/output':'rw,noexec,nosuid,nodev,size=1048576,nr_inodes=32,mode=1777'}
THREADS = ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS')
CAP = 32768
HOLDER = 'import time; time.sleep(1790)'


def public_runtime_contract():
    """Identical visible override in both arms; accepted packet bytes stay fixed."""
    return {'schema':'rep012_shared_runtime_invocation_v1',
            'task_id':'PAPER-FIND-REP-012',
            'scientific_profile':'method_assisted_main_text_paired_access_v1',
            'runtime_profile':RUNTIME_PROFILE,'image_id':IMAGE,'platform':'linux/arm64',
            'python_executable':PYTHON,'python_arguments':['-I','-B'],
            'versions':{'python':'3.12.8','numpy':'2.2.6','scipy':'1.15.3'},
            'readonly_bind_destinations':['/public','/task'],
            'software_location':'Immutable image; no host software bind.',
            'thread_environment':{key:'1' for key in THREADS},
            'network':'none','memory_bytes':1073741824,'pids':32,
            'writable_tmpfs_bytes':{'/tmp':15728640,'/scratch':16777216,'/output':1048576},
            'tools':{'terminal':['/bin/sh','-c','COMMAND'],
                     'python':[PYTHON,'-I','-B','/scratch/SCRIPT.py']},
            'working_directory':'/scratch','output_file':'/output/result.json','output_max_bytes':32768,
            'whole_condition_wall_seconds':1800,'tool_deadline_seconds':1780,
            'aggregate_CPU_ceiling_seconds':1800,'CPU_bandwidth':0.99,'model_tokens':32000,
            'override':'Replaces only runtime/image/interpreter/software-mount declarations '
                       'in the unchanged task/CONDITION_CONTRACT.json. All four scientific '
                       'endpoints, data, scoring and paper/code information difference remain unchanged.'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def pin(body):
    return {'bytes':len(body), 'sha256':hashlib.sha256(body).hexdigest()}


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def decode(body):
    def unique(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON key'); out[key] = value
        return out
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def plain(value):
    need(type(value) in (str, type(Path())), 'path string or native Path')
    p = Path(value)
    need(p.is_absolute() and str(p) == str(value) and '..' not in p.parts
         and not any(c in str(p) for c in ',\n\r\0'), 'canonical absolute Docker operand')
    need(all(not x.is_symlink() for x in (p,*p.parents)), 'no symlink path components')
    return p


def signature(st):
    return tuple(getattr(st,k) for k in ('st_dev','st_ino','st_mode','st_nlink',
                                      'st_size','st_mtime_ns','st_ctime_ns'))


def captured(path, maximum, expected=None, sealed=False):
    p=plain(path); before=p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1
         and 0<=before.st_size<=maximum, 'bounded ordinary single-link file')
    need(not sealed or stat.S_IMODE(before.st_mode)==0o444, 'sealed packet member')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(signature(before)==signature(os.fstat(fd)), 'stable open')
        with os.fdopen(fd,'rb',closefd=False) as f: body=f.read(maximum+1)
        need(signature(before)==signature(os.fstat(fd))==signature(p.lstat())
             and len(body)==before.st_size, 'stable complete file')
    finally: os.close(fd)
    need(expected is None or pin(body)==expected, 'exact file identity')
    return body


def validate_receipt(value):
    need(value['task_id']=='PAPER-FIND-REP-012' and
         value['profile']=='method_assisted_main_text_paired_access_v1'
         and value['status']=='complete_exact_paired_candidate_views', 'fixed finite packet')
    a,b=value['views']['A'],value['views']['B']
    need(len(a)==9 and len(b)==17 and set(a)<=set(b)
         and all(a[k]==b[k] for k in a), 'nine exact common files')
    need(len(set(b)-set(a))==8 and all(k.startswith('task/author_code/')
         for k in set(b)-set(a)), 'only eight approved author-code additions')
    for arm,rows in value['views'].items():
        need(arm in ('A','B'), 'two arms only')
        for name,row in rows.items():
            p=Path(name)
            need(not p.is_absolute() and str(p)==name and '..' not in p.parts
                 and p.parts[0] in ('task','public'), 'public relative member')
            need(set(row)=={'bytes','sha256'} and type(row['bytes']) is int
                 and 0<row['bytes']<=300000 and re.fullmatch('[a-f0-9]{64}',row['sha256']),
                 'fixed member descriptor')
    need(set(value['views'])=={'A','B'}, 'two complete views')
    return value


def admit_packets(repo, binding):
    """Authenticates the exact 26 payloads only at selected native admission."""
    receipt=validate_receipt(decode(captured(binding,RECEIPT[0],
        {'bytes':RECEIPT[0],'sha256':RECEIPT[1]})))
    root=plain(repo)/PACKETS; physical=set()
    for arm,rows in receipt['views'].items():
        view=plain(root/arm); observed=set()
        for current,dirs,files in os.walk(view,followlinks=False):
            p=Path(current)
            need(not p.is_symlink() and stat.S_IMODE(p.stat().st_mode)==0o555,
                 'sealed ordinary packet directory')
            for name in dirs: need(not (p/name).is_symlink(),'no linked packet directory')
            for name in files: observed.add(str((p/name).relative_to(view)))
        need(observed==set(rows), 'complete exact packet census')
        for name,row in rows.items():
            path=view/name; captured(path,300000,row,sealed=True)
            st=path.lstat(); identity=(st.st_dev,st.st_ino)
            need(identity not in physical,'distinct physical packet files'); physical.add(identity)
    return receipt


def mounts(repo,arm):
    need(arm in ('A','B'), 'fixed arm')
    root=plain(repo)
    return {'/public':str(plain(root/PACKETS/arm/'public')),
            '/task':str(plain(root/PACKETS/arm/'task'))}


def overlaps(left,right):
    """Conservative Unicode/case check plus existing-directory alias identities.

    macOS case-insensitive and firmlink aliases are not symlinks. New owner
    leaves do not yet exist, so join every existing parent as well.
    """
    left,right=plain(left),plain(right)
    fold=lambda p: tuple(unicodedata.normalize('NFD',s).casefold() for s in p.parts)
    a,b=fold(left),fold(right)
    if a[:len(b)]==b or b[:len(a)]==a: return True
    def identities(p):
        out=set()
        for q in (p,*p.parents):
            try: st=q.stat()
            except FileNotFoundError: continue
            out.add((st.st_dev,st.st_ino))
        return out
    for direct,other in ((left,right),(right,left)):
        try: st=direct.stat()
        except FileNotFoundError: continue
        if (st.st_dev,st.st_ino) in identities(other): return True
    return False


def owner_layout(repo,root,docker_config,docker_socket):
    protected=[plain(root),plain(docker_config),plain(docker_socket)]
    public={Path(src) for arm in ('A','B') for src in mounts(repo,arm).values()}
    for private in protected:
        need(all(not overlaps(private,src) for src in public),
             'owner evidence/config/socket disjoint from every candidate mount and physical alias')
    need(not overlaps(protected[0],plain(repo)/PACKETS),'owner root disjoint from packet parent')


def create_argv(repo,arm,nonce):
    need(re.fullmatch('[a-f0-9]{32}',nonce) is not None,'fresh nonce')
    name='rep012-pair-'+nonce+'-'+arm.lower()
    argv=['create','--pull','never','--name',name,'--network','none','--read-only',
          '--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true',
          '--memory','1073741824','--memory-swap','1073741824','--cpus','0.99',
          '--pids-limit','32','--restart','no','--log-driver','none','--workdir','/scratch',
          '--label','neuro.rep012.owner='+nonce,'--label','neuro.rep012.arm='+arm,
          '--ulimit','nofile=128:128','--ulimit','core=0:0','--ulimit','fsize=1048576:1048576']
    for dest,src in sorted(mounts(repo,arm).items()):
        argv += ['--mount','type=bind,src='+src+',dst='+dest+',readonly,bind-recursive=disabled']
    for dest,options in TMPFS.items(): argv += ['--tmpfs',dest+':'+options]
    for key in THREADS: argv += ['--env',key+'=1']
    argv += ['--env','REP012_RUNTIME_CONTRACT_JSON='+encode(public_runtime_contract()).decode().strip()]
    argv += ['--env','PYTHONDONTWRITEBYTECODE=1','--env','HOME=/scratch',
             '--entrypoint',PYTHON,IMAGE,'-I','-B','-c',HOLDER]
    return name,argv


def verify_inspect(row,repo,arm,nonce,cid):
    name,argv=create_argv(repo,arm,nonce); h=row['HostConfig']; c=row['Config']
    need(row['Id']==cid and row['Name']=='/'+name and row['Image']==IMAGE,
         'same exact immutable owned container/image')
    need(c['User']=='65534:65534' and c['WorkingDir']=='/scratch'
         and c['Entrypoint']==[PYTHON] and c['Cmd']==['-I','-B','-c',HOLDER],
         'fixed non-root holder')
    need(c['Labels'].get('neuro.rep012.owner')==nonce and c['Labels'].get('neuro.rep012.arm')==arm,
         'ownership labels')
    need(h['ReadonlyRootfs'] is True and h['NetworkMode']=='none' and h['Privileged'] is False
         and h['Memory']==1073741824 and h['MemorySwap']==1073741824
         and h['NanoCpus']==990000000 and h['PidsLimit']==32
         and h['RestartPolicy']['Name']=='no' and h['LogConfig']['Type']=='none'
         and h['CapDrop']==['ALL'] and not h.get('CapAdd')
         and h['SecurityOpt']==['no-new-privileges:true'] and h['Tmpfs']==TMPFS,
         'complete resource and isolation settings')
    need(not h.get('Devices') and not h.get('DeviceRequests') and not h.get('DeviceCgroupRules') and not h.get('Binds')
         and not h.get('VolumesFrom') and h.get('PidMode','')=='' and h.get('IpcMode')=='private'
         and h.get('OomKillDisable') in (False,None), 'no extra host/device/namespace access')
    expected=mounts(repo,arm); rows=row['Mounts']
    need(len(rows)==2 and {m['Destination'] for m in rows}==set(expected), 'only two packet binds')
    for m in rows:
        need(m['Type']=='bind' and m['Source']==expected[m['Destination']] and m['RW'] is False
             and m.get('Propagation')=='rprivate', 'exact read-only unshared mount')
    configs=h.get('Mounts',[])
    need(len(configs)==2 and all(m.get('BindOptions',{}).get('NonRecursive') is True
         for m in configs), 'recursive submounts disabled')
    entries=[x.split('=',1) for x in c['Env']]
    need(all(len(x)==2 for x in entries) and len(entries)==len({x[0] for x in entries}),
         'unique complete environment keys; no first/last lookup ambiguity')
    env=dict(entries)
    need(all(env.get(k)=='1' for k in THREADS) and env.get('HOME')=='/scratch'
         and env.get('PYTHONDONTWRITEBYTECODE')=='1'
         and env.get('REP012_RUNTIME_CONTRACT_JSON')==encode(public_runtime_contract()).decode().strip(),
         'fixed one-thread tool environment and identical explicit runtime override')
    return True


# Docker cp does not read a container's tmpfs contents. This fixed reader runs
# inside the live namespace as the same unprivileged UID as the participant.
# It captures a bounded ordinary file, not an atomic paused-filesystem snapshot.
OUTPUT_CAPTURE = r'''import os,stat,json,base64,hashlib
p='/output/result.json'
schema='rep012_live_namespace_output_v1'
def require(ok,message):
 if not ok: raise ValueError(message)
def signature(s):
 return [getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')]
try:
 b=os.lstat(p)
except FileNotFoundError:
 print(json.dumps({'schema':schema,'status':'missing'},sort_keys=True));raise SystemExit(0)
require(stat.S_ISREG(b.st_mode) and b.st_nlink==1 and 0<=b.st_size<=32768,'bounded ordinary single-link output')
fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
try:
 require(signature(b)==signature(os.fstat(fd)),'stable output open')
 with os.fdopen(fd,'rb',closefd=False) as stream: body=stream.read(32769)
 require(signature(b)==signature(os.fstat(fd))==signature(os.lstat(p)) and len(body)==b.st_size,'stable complete output')
finally: os.close(fd)
print(json.dumps({'schema':schema,'status':'ordinary','signature':signature(b),
 'body_b64':base64.b64encode(body).decode('ascii'),'sha256':hashlib.sha256(body).hexdigest()},sort_keys=True))
'''


def namespace_output(body):
    """Validate one complete trusted-reader frame; never extract archive paths."""
    need(type(body) is bytes and 0<len(body)<=65536, 'bounded complete output frame')
    row=decode(body)
    if row=={'schema':'rep012_live_namespace_output_v1','status':'missing'}: return None
    need(type(row) is dict and set(row)=={'schema','status','signature','body_b64','sha256'}
         and row['schema']=='rep012_live_namespace_output_v1' and row['status']=='ordinary'
         and type(row['signature']) is list and len(row['signature'])==7
         and all(type(x) is int and x>=0 for x in row['signature']), 'complete exact output metadata')
    s=row['signature']
    need(stat.S_ISREG(s[2]) and s[3]==1 and s[4]<=CAP, 'bounded ordinary single-link output')
    need(type(row['body_b64']) is str and len(row['body_b64'])<=43692
         and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}',row['sha256']),
         'bounded exact payload identity')
    result=base64.b64decode(row['body_b64'],validate=True)
    need(len(result)==s[4] and base64.b64encode(result).decode('ascii')==row['body_b64']
         and hashlib.sha256(result).hexdigest()==row['sha256'], 'complete authenticated output frame')
    return result


class Budget:
    def __init__(self,root): self.root=plain(root); self.written=0; self.engines=[]; self.recovery=False
    def check(self,size,receipt=False):
        ceiling=(32 if self.recovery else 30)*1024*1024
        need(self.written+sum(e.raw for e in self.engines)+size<=ceiling,
             'whole owner evidence cap, including inherited direct raw captures')
    def write(self,path,body,receipt=False,mode=0o444):
        self.check(len(body)); p=plain(path)
        need(p.is_relative_to(self.root),'owner evidence only')
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        try:
            with os.fdopen(fd,'wb',closefd=False) as f: f.write(body); f.flush(); os.fsync(fd)
            os.fchmod(fd,mode)
        finally: os.close(fd)
        sync_directory(p.parent)
        self.written+=len(body)


def engine_class(repo):
    """Exact reviewed selector/capture implementation; explicit globals only."""
    body=captured(plain(Path(__file__).absolute().parent)/DONOR[0],DONOR[1],{'bytes':DONOR[1],'sha256':DONOR[2]})
    tree=ast.parse(body); names={'need','encode','short','Engine'}
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    need({n.name for n in nodes}==names,'exact inherited capture definitions')
    env={'os':os,'Path':Path,'hashlib':hashlib,'json':json,'time':time,
         'selectors':selectors,'subprocess':subprocess}
    # One larger interactive command census; original capped capture/EOF/reap
    # implementation is unchanged. Calls/bytes preserve an explicit close reserve.
    env.update(COMMAND_LIMIT=1024,WORK_COMMAND_LIMIT=1000,RAW_LIMIT=24*1024*1024,
               WORK_RAW_LIMIT=20*1024*1024,METADATA_LIMIT=4*1024*1024,
               WORK_METADATA_LIMIT=3*1024*1024,FINAL_RECOVERY_COMMAND_LIMIT=12,
               FINAL_RECOVERY_RAW_LIMIT=2*1024*1024,FINAL_RECOVERY_METADATA_LIMIT=1024*1024,
               CAPTURE_LIMIT=65536)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(plain(Path(__file__).absolute().parent)/DONOR[0]),'exec'),env)
    return env


class Condition:
    def __init__(self,pair,arm):
        self.pair=pair; self.arm=arm; self.cid=None; self.closed=False; self.frozen=None
        self.started=time.monotonic(); self.tool_end=self.started+1780
        self.whole_end=self.started+1800; self.lock=threading.RLock(); self.failed=None
        self.tokens=0; self.calls=0; self.folder=pair.root/arm; self.folder.mkdir(mode=0o700)
        self.runtime_invocation=public_runtime_contract()
        sync_directory(pair.root)
        self.engine=pair.engine(self.folder,pair.budget,self.whole_end)
        pair.budget.engines.append(self.engine)
        self.engine.env=dict(pair.environment)
        self.thread=None

    def execute(self,args,timeout=3,cap=65536):
        result=self.engine.run(args,timeout=timeout,cap=cap)
        need(result.returncode==0,'Docker command failed; full original streams retained')
        return result

    def inspect(self):
        rows=decode(self.execute(['inspect','--type','container',self.cid]).stdout)
        need(type(rows) is list and len(rows)==1,'one container')
        verify_inspect(rows[0],self.pair.repo,self.arm,self.pair.nonce,self.cid)
        return rows[0]

    def failure(self,phase,error):
        self.failed=phase+': '+repr(error)
        close_error=None
        try: self.close()
        except BaseException as e:
            close_error=repr(e); self.failed+='; close failed: '+close_error
        record={'phase':phase,'original_exception':repr(error)[:2048],
                'close_exception':None if close_error is None else close_error[:2048],
                'cid':self.cid,'closed':self.closed,'qualification':False}
        try: self.pair.budget.write(self.folder/'FAILURE.json',encode(record))
        except BaseException as e:
            # Original command files remain. An unavailable failure receipt is
            # explicitly an in-memory error, never claimed as durable evidence.
            self.failed+='; failure receipt unavailable: '+repr(e)

    def start(self):
        name,args=create_argv(self.pair.repo,self.arm,self.pair.nonce)
        # A nonce collision fails create; never remove a pre-existing name.
        result=self.execute(args); cid=result.stdout.decode('ascii').strip()
        need(re.fullmatch('[a-f0-9]{64}',cid) is not None and not result.stderr,'complete create ID')
        self.cid=cid; self.inspect(); self.execute(['start',cid]); self.inspect()
        self.thread=threading.Thread(target=self.watch,name='rep012-deadline-'+self.arm,daemon=False)
        self.thread.start()

    def watch(self):
        while not self.closed:
            if time.monotonic()>=self.tool_end:
                with self.lock:
                    if not self.closed:
                        self.failure('deadline',TimeoutError('condition tool deadline expired'))
                return
            time.sleep(.05)

    def call(self,tool,argument,usage_tokens=0):
        with self.lock:
            need(not self.closed and not self.failed and self.frozen is None,'active uncommitted condition')
            need(type(usage_tokens) is int and usage_tokens>=0 and self.tokens+usage_tokens<=32000,
                 'trusted owner token accounting ceiling')
            need(type(argument) is str and 0<len(argument.encode())<=16384 and '\0' not in argument,
                 'bounded tool argument')
            self.tokens+=usage_tokens; self.calls+=1
            need(self.calls<=256,'finite interactive tool census')
            remaining=self.tool_end-time.monotonic(); need(remaining>0,'same condition deadline')
            if tool=='terminal': command=['/bin/sh','-c',argument]
            elif tool=='python':
                p=Path(argument)
                need(str(p)==argument and p.is_absolute() and p.parts[:2]==('/','scratch')
                     and '..' not in p.parts and p.suffix=='.py','Python script in scratch')
                command=[PYTHON,'-I','-B',argument]
            else: raise ValueError('only terminal and Python tools')
            # No shell interpolation on host. Arbitrary candidate commands are
            # confined to this exact CID, with no optional Docker flags accepted.
            try:
                reply=self.engine.run(['exec','--user','65534:65534','--workdir','/scratch',
                                       self.cid,*command],timeout=remaining,cap=65536)
                need(time.monotonic()<self.tool_end,'tool within original condition deadline')
                self.inspect()
            except BaseException as error:
                self.failure('tool failure',error)
                raise
            return {'returncode':reply.returncode,'stdout':reply.stdout,'stderr':reply.stderr}

    def freeze(self):
        try:
            return self._freeze_locked()
        except BaseException as error:
            self.failure('commit failure',error)
            raise

    def _freeze_locked(self):
        with self.lock:
            need(not self.closed and self.frozen is None and not self.failed,'one active commit')
            need(time.monotonic()<self.tool_end,'commit before shared tool deadline')
            self.inspect()
            remaining=self.tool_end-time.monotonic()
            need(remaining>0,'capture within original tool deadline')
            capture=self.execute(['exec','--user','65534:65534',self.cid,PYTHON,
                                  '-I','-S','-B','-c',OUTPUT_CAPTURE],timeout=min(5,remaining))
            need(not capture.stderr,'complete fixed namespace output reader')
            body=namespace_output(capture.stdout)
            need(time.monotonic()<self.tool_end,'capture before original tool deadline')
            if body is None: result={'status':'missing'}
            else:
                path=self.folder/'submission.json'; self.pair.budget.write(path,body)
                result={'status':'captured','path':str(path),**pin(body)}
            self.close()
            need(self.closed and self.failed is None,'closed resources before frozen receipt')
            self.frozen={'arm':self.arm,'output':result,'closed':True,'tokens':self.tokens,
                         'tool_calls':self.calls,'candidate_result_semantics':'opaque; unchanged private evaluator'}
            self.pair.budget.write(self.folder/'FROZEN.json',encode(self.frozen))
            return self.frozen

    def close(self):
        with self.lock:
            if self.closed: return
            need(self.cid is not None,'ambiguous create is preserved for owner recovery')
            self.engine.recovery=True
            self.pair.budget.recovery=True
            row=self.inspect()
            if row['State']['Running']: self.execute(['kill','--signal','KILL',self.cid],timeout=3)
            row=self.inspect(); need(row['State']['Running'] is False,'container and descendants stopped')
            self.execute(['rm',self.cid],timeout=3)
            reply=self.engine.run(['inspect','--type','container',self.cid],timeout=3)
            need(reply.returncode==1 and reply.stdout.strip()==b'[]'
                 and reply.stderr.decode().strip()=='Error: No such container: '+self.cid,
                 'exact immutable CID absence; daemon errors are not absence')
            self.closed=True
            self.pair.budget.write(self.folder/'CLOSED.json',encode({'cid':self.cid,'closed':True,
                'elapsed_seconds':time.monotonic()-self.started,'all_direct_CLI_reaped':self.engine.all_cli_reaped}))
            need(time.monotonic()<=self.whole_end,'whole condition including close within 1800 seconds')


class PairController:
    """Owner API. It accepts no grader/reference path and never imports candidates.

    Provider authentication/token accounting belongs to a future selected owner
    adapter. No provider or paid API is implemented or implicitly configured.
    """
    def __init__(self,repo,binding,root,docker,docker_config,docker_socket,nonce):
        self.repo=plain(repo); self.root=plain(root); self.nonce=nonce
        need(not self.root.exists(),'fresh exclusive owner root')
        owner_layout(self.repo,self.root,docker_config,docker_socket)
        admit_packets(self.repo,binding)
        self.root.mkdir(mode=0o700); sync_directory(self.root.parent)
        self.budget=Budget(self.root); self.conditions={}
        docker=plain(docker); config=plain(docker_config); socket=plain(docker_socket)
        self.environment={'PATH':'/usr/bin:/bin','DOCKER_CONFIG':str(config),
                          'DOCKER_HOST':'unix://'+str(socket),'PYTHON_DOTENV_DISABLED':'1'}
        env=engine_class(self.repo); env['ROOT']=self.root; env['DOCKER']=str(docker)
        self.engine=env['Engine']; self.completed=False

    def begin(self,arm):
        need(arm in ('A','B') and arm not in self.conditions,'one fresh session per arm')
        need(all(c.closed and c.frozen is not None and c.failed is None
                 for c in self.conditions.values()),'serial independent successfully frozen sessions')
        self.budget.recovery=False
        c=Condition(self,arm); self.conditions[arm]=c
        try: c.start()
        except BaseException:
            if c.cid is not None:
                try: c.close()
                except BaseException: pass
            raise
        return c

    def finish(self):
        need(not self.completed and set(self.conditions)=={'A','B'},'both independent conditions required')
        for c in self.conditions.values():
            need(c.closed and c.frozen is not None and c.failed is None,'both frozen closed outputs before grading')
            if c.thread is not None: c.thread.join(timeout=1); need(not c.thread.is_alive(),'watchdog closed')
        result={'schema':'rep012_paired_frozen_outputs_v1','task_id':'PAPER-FIND-REP-012',
                'runtime_profile':RUNTIME_PROFILE,'runtime_invocation':public_runtime_contract(),
                'profile':'method_assisted_main_text_paired_access_v1','outputs':
                {a:self.conditions[a].frozen for a in ('A','B')},'private_grading_started':False,
                'native_qualification_claimed':False,'model_code_benefit_claimed':False}
        self.budget.write(self.root/'PAIR_BARRIER.json',encode(result)); self.completed=True
        return result
