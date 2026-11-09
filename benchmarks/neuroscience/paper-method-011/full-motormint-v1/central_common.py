"""Bounded central metadata custody; no neural/provider/native imports."""
import hashlib
import json
import os
import stat
import time


class Refusal(RuntimeError):
    def __init__(self, reason, **facts):
        super().__init__(reason)
        self.facts=facts
        self.secondary=[]


def need(ok, reason, **facts):
    if not ok:
        raise Refusal(reason, **facts)


def keys(value, expected):
    need(type(value) is dict and set(value)==set(expected), 'closed central schema', expected=sorted(expected))
    return value


def pin(body):
    need(type(body) is bytes, 'actual bytes required')
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def check_pin(value):
    keys(value,('bytes','sha256'))
    need(type(value['bytes']) is int and value['bytes']>=0 and type(value['sha256']) is str
         and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']), 'content pin')
    return value


def relative(value):
    need(type(value) is str and 0<len(value)<=4096 and '\\' not in value and not value.startswith('/')
         and all(p not in ('','.','..') for p in value.split('/')), 'canonical relative path')
    return value


def absolute(value):
    need(type(value) is str and len(value)<=4096 and value.startswith('/') and '\\' not in value
         and all(p not in ('','.','..') for p in value.split('/')[1:]), 'canonical absolute path')
    return value


def exact_json(body, maximum):
    need(type(body) is bytes and len(body)<=maximum,'bounded JSON body')
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate JSON member')
            out[k]=v
        return out
    return json.loads(body,object_pairs_hook=pairs,
        parse_constant=lambda x:(_ for _ in ()).throw(Refusal('nonfinite JSON')))


def extent(value, cap, depth=0):
    need(depth<=64,'bounded metadata nesting')
    if value is None:return 4
    if type(value) is bool:return 5
    if type(value) is int:
        need(value.bit_length()<=4096,'bounded metadata integer')
        return len(str(value))
    if type(value) is str:
        n=2+sum(2 if c in '\\"' else 1 if 32<=ord(c)<=126 else 6 if ord(c)<=65535 else 12 for c in value)
        need(n<=cap,'bounded metadata string');return n
    if type(value) is float:
        import math
        need(math.isfinite(value),'finite JSON float');return 32
    need(type(value) in (list,dict),'literal metadata type')
    n=2
    for k,v in (enumerate(value) if type(value) is list else value.items()):
        n+=extent(v,cap,depth+1)+1
        if type(value) is dict:
            need(type(k) is str,'string JSON keys');n+=extent(k,cap,depth+1)+1
        need(n<=cap,'preventive encoded metadata extent')
    return n


def encode(value, cap):
    extent(value,cap)
    b=(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)).encode('ascii')
    need(len(b)<=cap,'encoded metadata extent');return b


class Meter:
    """Finite logical bounds, not physical I/O or RSS. Attempts never refund."""
    dimensions=('read_bytes','write_bytes','metadata_bytes','open_attempts','objects')
    def __init__(self, limits, clock=None):
        keys(limits,self.dimensions)
        need(all(type(x) is int and x>0 for x in limits.values()),'explicit positive central limits')
        self.limits=dict(limits);self.used={k:0 for k in limits};self.clock=clock;self.attempts=0
    def tick(self, phase='scientific'):
        if self.clock is not None:
            keys(self.clock,('origin_ns','scientific_ns','closure_ns','outer_ns'))
            need(0<=self.clock['origin_ns']<self.clock['scientific_ns']<=self.clock['closure_ns']<=self.clock['outer_ns'], 'original clock order')
            need(self.clock['origin_ns']<=time.monotonic_ns()<self.clock[phase+'_ns'],'original central cutoff',phase=phase)
    def charge(self, **amounts):
        self.attempts+=1
        for k,v in amounts.items():
            need(k in self.used and type(v) is int and v>=0,'named finite charge')
            self.used[k]+=v
        need(all(self.used[k]<=self.limits[k] for k in self.used),'central capacity exhausted',prefix=self.snapshot())
    def snapshot(self):
        return {'limits':dict(self.limits),'attempted':dict(self.used),'attempts':self.attempts,
                'scope':'logical source/metadata reservations; no physical or remote usage inference'}


def cleanup(fds, primary):
    while fds:
        fd=fds.pop()
        try:os.close(fd)
        except BaseException as error:
            if primary is None:primary=error
            else:primary.secondary=getattr(primary,'secondary',[])+[{'operation':'close','type':type(error).__name__}]
    return primary


def ident(s):
    return [s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def open_dir(path, meter, *, uid=None, phase='scientific'):
    absolute(path);owned=[];primary=None
    meter.charge(open_attempts=len(path.split('/')))
    try:
        meter.tick(phase);fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);owned.append(fd)
        for part in path.split('/')[1:]:
            fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);owned.append(fd)
        s=os.fstat(fd)
        need(uid is None or s.st_uid==uid,'selected directory owner')
        result=(owned.pop(),[s.st_dev,s.st_ino])
    except BaseException as error:primary=error
    primary=cleanup(owned,primary)
    if primary is not None:
        if 'result' in locals():primary=cleanup([result[0]],primary)
        raise primary
    return result


def capture(path, expected, meter, *, maximum, phase='scientific', uid=None):
    absolute(path)
    if expected is None:
        # First observation of a fixed newly produced name, not source admission.
        meter.charge(open_attempts=1)
        initial=os.stat(path,follow_symlinks=False)
        need(stat.S_ISREG(initial.st_mode) and initial.st_nlink==1,'ordinary produced metadata')
        extent_bytes=initial.st_size
    else:
        check_pin(expected);extent_bytes=expected['bytes']
    need(extent_bytes<=maximum,'selected file ceiling')
    meter.charge(read_bytes=extent_bytes+1,metadata_bytes=2*extent_bytes+4096,objects=1)
    owned=[];primary=None;out=None
    try:
        meter.tick(phase);parent,di=open_dir(path.rsplit('/',1)[0],meter,phase=phase);owned.append(parent)
        meter.charge(open_attempts=1)
        fd=os.open(path.rsplit('/',1)[1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent);owned.append(fd)
        a=os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==extent_bytes
             and (uid is None or a.st_uid==uid),'ordinary selected file extent/owner')
        chunks=[];left=a.st_size
        while left:
            meter.tick(phase);b=os.read(fd,min(left,65536));need(b,'early EOF');chunks.append(b);left-=len(b)
        need(os.read(fd,1)==b'','exact EOF');raw=b''.join(chunks)
        need((expected is None or pin(raw)==expected) and ident(a)==ident(os.fstat(fd))==ident(os.stat(path.rsplit('/',1)[1],dir_fd=parent,follow_symlinks=False)), 'changed captured bytes or identity')
        out=(raw,{'path':path,'pin':pin(raw),'identity':ident(a),'EOF':True})
        meter.tick(phase)
    except BaseException as error:primary=error
    primary=cleanup(owned,primary)
    if primary is not None:
        primary.central_capture_prefix={'path':path,'pin':expected,'meter':meter.snapshot(),'captured':None if out is None else out[1]}
        raise primary
    return out


class Publisher:
    def __init__(self,path,meter,uid):
        self.path=absolute(path);self.meter=meter;self.uid=uid;self.records=[];self.closed=False
        self.fd,self.identity=open_dir(path,meter,uid=uid)
    def put(self,name,value,*,maximum,phase='scientific'):
        relative(name);need('/' not in name and not self.closed,'one fixed flat output name')
        self.meter.charge(metadata_bytes=3*maximum,write_bytes=maximum,objects=1,open_attempts=1)
        raw=encode(value,maximum);owned=[];primary=None;record=None
        try:
            self.meter.tick(phase)
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.fd);owned.append(fd)
            record={'path':self.path+'/'+name,'pin':pin(raw),'state':'created_incomplete'};self.records.append(record)
            at=0
            while at<len(raw):
                self.meter.tick(phase);n=os.write(fd,raw[at:]);need(n>0,'short metadata write');at+=n
            os.fsync(fd);os.fsync(self.fd);self.meter.tick(phase);record['state']='durably_written'
        except BaseException as error:primary=error
        primary=cleanup(owned,primary)
        if primary is not None:
            primary.central_publication_prefix={'records':list(self.records),'meter':self.meter.snapshot()};raise primary
        return {'path':record['path'],'pin':record['pin']}
    def put_bytes(self,name,raw,*,maximum,phase='scientific'):
        relative(name);need('/' not in name and not self.closed,'flat owned metadata output')
        need(type(raw) is bytes and len(raw)<=maximum,'bounded selected metadata body')
        self.meter.charge(metadata_bytes=2*len(raw)+4096,write_bytes=len(raw),objects=1,open_attempts=1)
        owned=[];primary=None;record=None
        try:
            self.meter.tick(phase)
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.fd);owned.append(fd)
            record={'path':self.path+'/'+name,'pin':pin(raw),'state':'created_incomplete'};self.records.append(record)
            at=0
            while at<len(raw):
                self.meter.tick(phase);n=os.write(fd,raw[at:]);need(n>0,'short metadata write');at+=n
            os.fsync(fd);os.fsync(self.fd);self.meter.tick(phase);record['state']='durably_written'
        except BaseException as error:primary=error
        primary=cleanup(owned,primary)
        if primary is not None:
            primary.central_publication_prefix={'records':list(self.records),'meter':self.meter.snapshot()};raise primary
        return {'path':record['path'],'pin':record['pin']}

    def close(self,primary=None):
        if not self.closed:self.closed=True;primary=cleanup([self.fd],primary)
        return primary
