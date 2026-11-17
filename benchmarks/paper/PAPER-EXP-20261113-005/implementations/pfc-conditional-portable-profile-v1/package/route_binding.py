"""PFC participant-only binding. Scientific reference/scorer remain unchanged."""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import time
import types

HERE = Path(__file__).absolute().parent
# Attempt roots and host executables are bound in each owner request.
MIB = 1024**2
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
PYTHON = '/usr/local/bin/python'

DEADLINES = (60,180,180,660,660)
OUTPUT_CAPS = (0,128*MIB,128*MIB,64*MIB,64*MIB)
MANAGED_CAP = 1536*MIB
RETAINED_CAP = 512*MIB

def need(value, message):
    if not value: raise RuntimeError(message)

class StreamFailure(RuntimeError):
    def __init__(self,primary,secondary,stdout_pin):
        self.stream_failure_custody={'primary':primary,'secondary':secondary,'stdout':stdout_pin}
        super().__init__(json.dumps(self.stream_failure_custody,sort_keys=True))

def ordinary(value):
    p=Path(value)
    need(p.is_absolute() and '..' not in p.parts and
         not any(x.is_symlink() for x in (p,*p.parents)), 'ordinary absolute path')
    return p

def canonical(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate JSON key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))

def extent(path, cap):
    p=ordinary(path);s=p.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<=s.st_size<=cap,'bounded single-link file')
    return s.st_size

def exact(pin,cap=MIB):
    need(set(pin)=={'path','bytes','sha256'} and type(pin['bytes']) is int and 0<pin['bytes']<=cap,'finite pin')
    p=ordinary(pin['path']);before=p.lstat()
    need(extent(p,cap)==pin['bytes'],'exact extent')
    with p.open('rb') as stream:raw=stream.read(pin['bytes']+1)
    after=p.lstat()
    need(len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'] and
         all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable exact pin')
    return raw

def module(pin,name):
    raw=exact(pin);out=types.ModuleType(name);out.__file__=pin['path']
    exec(compile(raw,pin['path'],'exec'),out.__dict__);return out

def write_new(path,value):
    raw=canonical(value);need(len(raw)<=MIB,'finite receipt');p=ordinary(path)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        at=0
        while at<len(raw):
            n=os.write(fd,raw[at:]);need(n>0,'complete receipt');at+=n
        os.fsync(fd)
    finally:os.close(fd)
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def validate_request(r,p):
    from deployment import validate_request_metadata
    validate_request_metadata(r,p,HERE)
    return Path(r['deployment']['attempts_root'])/r['attempt']


def load_request(path,size,digest):
    pin={'path':str(ordinary(path)),'bytes':size,'sha256':digest}
    r=decode(exact(pin,131072));p=decode(exact(r['policy']))
    root=validate_request(r,p)
    return pin,r,p,root

def candidate_mounts(r,p,arm):
    need(arm in ('A','B'),'declared arm')
    mounts=[(r['programs'][arm]['path'],'/candidate/solution.py',False),
            (p['packet']['path'],'/input/participant-packet.json',False)]
    mounts += [(pin['path'],'/instructions/'+name,False) for name,pin in p['common_assistance'].items()]
    if arm=='B':mounts += [(pin['path'],'/official/'+name,False) for name,pin in p['additional_B_assistance'].items()]
    return mounts

def validate_runtime(item,argv,mounts):
    need(item['image']==IMAGE and item['memory']==item['swap']==4*1024**3 and item['cpus']==2*10**9 and
         item['network']=='none' and item['readonly'] is True and item['pids']==64,'image/resources')
    need(item['tmpfs']=={'/tmp':'rw,noexec,nosuid,nodev,size=256m'} and item['caps']==['ALL'] and
         item['security']==['no-new-privileges'] and item['entrypoint']==[PYTHON] and item['args']==argv,'exact runtime policy')
    got=item['mounts'];need(len(got)==len(mounts) and all(x['Type']=='bind' for x in got),'exact bind count/type')
    need({(x['Source'],x['Destination'],x['RW']) for x in got}==set(mounts),'exact mount sources/destinations/write scope')

def stream_candidate(engine,args,timeout,destination,maximum=128*MIB):
    """Capture complete candidate stdout once to an immutable bounded file.

    No writable host directory is mounted into a participant container. On a
    limit/failure preserve the exact captured prefix and mark it incomplete.
    """
    number=len(engine.EVENTS)+1;argv=[*engine.DOCKER_ARGV,*args];start=time.monotonic()
    deadline=min(start+timeout,engine.WORK_END-4)
    path=ordinary(destination);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    total=0;digest=hashlib.sha256();err=bytearray();overflow=b'';received={'stdout':0,'stderr':0}
    selector=selectors.DefaultSelector();eof=set();proc=None;rc=None;issue=None;reaped=False;secondary=[]
    try:
        need(deadline>start,'original candidate deadline')
        proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True,env=engine.COMMAND_ENV)
        for name,stream in [('stdout',proc.stdout),('stderr',proc.stderr)]:
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or proc.poll() is None:
            need(time.monotonic()<deadline,'candidate stream deadline')
            for key,_ in selector.select(.025):
                left=maximum-total if key.data=='stdout' else 32768-len(err)
                part=os.read(key.fileobj.fileno(),min(65536,left+1))
                if not part:
                    eof.add(key.data);selector.unregister(key.fileobj);key.fileobj.close();continue
                received[key.data]+=len(part);kept=part[:left]
                if key.data=='stdout':
                    at=0
                    while at<len(kept):
                        n=os.write(fd,kept[at:]);need(n>0,'candidate stream write');at+=n
                    digest.update(kept);total+=len(kept)
                else:err.extend(kept)
                if len(part)>left:overflow=part[left:];raise RuntimeError('candidate '+key.data+' cap')
        rc=proc.wait(timeout=0);reaped=True
    except BaseException as error:
        issue={'class':type(error).__name__,'message':str(error)[:4000]}
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:proc.kill()
                rc=proc.wait(timeout=max(.01,min(1,engine.END-time.monotonic()-1)));reaped=True
            except BaseException as error:
                row={'class':type(error).__name__,'message':str(error)[:4000],'phase':'client_reap'}
                if issue is None:issue=row
                else:secondary.append(row)
            for name,stream in [('stdout',proc.stdout),('stderr',proc.stderr)]:
                try:
                    if stream is not None and not stream.closed:stream.close()
                except BaseException as error:
                    row={'class':type(error).__name__,'message':str(error)[:4000],'phase':name+'_pipe_close'}
                    if issue is None:issue=row
                    else:secondary.append(row)
        try:selector.close()
        except BaseException as error:
            row={'class':type(error).__name__,'message':str(error)[:4000],'phase':'selector_close'}
            if issue is None:issue=row
            else:secondary.append(row)
        try:os.fsync(fd)
        except BaseException as error:
            row={'class':type(error).__name__,'message':str(error)[:4000],'phase':'stdout_fsync'}
            if issue is None:issue=row
            else:secondary.append(row)
        try:os.close(fd)
        except BaseException as error:
            row={'class':type(error).__name__,'message':str(error)[:4000],'phase':'stdout_close'}
            if issue is None:issue=row
            else:secondary.append(row)
    pin={'path':str(path),'bytes':total,'sha256':digest.hexdigest()}
    try:
        stderr=engine.save('command-%02d.stderr'%number,bytes(err))
        over=engine.save('command-%02d.overflow'%number,overflow)
    except BaseException as error:
        row={'class':type(error).__name__,'message':str(error)[:4000],'phase':'capture_publication'}
        if issue is None:issue=row
        else:secondary.append(row)
        raise StreamFailure(issue,secondary,pin) from error
    event={'argv':argv,'returncode':rc,'issue':issue,'reaped':reaped,'received':received,'observed_EOF':sorted(eof),
           'complete':issue is None and reaped and eof=={'stdout','stderr'},'seconds':time.monotonic()-start,
           'outputs':{'stdout':pin,'stderr':stderr,'overflow':over},'stdout_is_fresh_immutable_submission':True}
    engine.EVENTS.append(event)
    primary=issue
    if primary is None and not(event['complete'] and rc==0 and total>0):
        primary={'class':'CandidateExitFailure','returncode':rc,'complete_transport':event['complete'],'stdout_bytes':total}
    try:engine.save('CALL-%02d.json'%number,event)
    except BaseException as error:
        row={'class':type(error).__name__,'message':str(error)[:4000],'phase':'call_receipt_publication'}
        if primary is None:primary=row
        else:secondary.append(row)
        raise StreamFailure(primary,secondary,pin) from error
    if primary is not None:raise StreamFailure(primary,secondary,pin)
    return pin,event
