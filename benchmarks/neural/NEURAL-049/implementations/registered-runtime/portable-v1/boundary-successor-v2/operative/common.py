# Source fragment1: stdlib-only primitives and bounded owned-root IO.
import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types
from contextlib import contextmanager

class Refusal(ValueError):
    pass

def need(value,message):
    if not value:raise Refusal(message)

def exact(value,keys,message):
    need(type(value) is dict and set(value)==set(keys),message)
    return value

def pin_bytes(body):
    need(type(body) is bytes,'literal bytes')
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def valid_pin(value):
    exact(value,{'bytes','sha256'},'exact pin fields')
    need(type(value['bytes']) is int and value['bytes']>=0 and type(value['sha256']) is str
         and re.fullmatch('[0-9a-f]{64}',value['sha256']),'typed SHA256 pin')
    return value

def descriptor(value):
    exact(value,{'path','pin'},'exact descriptor fields')
    need(type(value['path']) is str and value['path'],'descriptor literal path')
    valid_pin(value['pin']);return value

def relative_path(value):
    need(type(value) is str and value and not value.startswith('/') and '\\' not in value
         and '\0' not in value and len(value)<=4096 and all(x not in ('','.','..') for x in value.split('/')),'canonical relative path')
    return value

def canonical_path(value):
    need(type(value) in (str,Path) or isinstance(value,Path),'path string/Path')
    s=str(value);need(s.startswith('/') and s!='/' and len(s)<=4096 and not s.startswith('//') and '\\' not in s and '\0' not in s
                     and all(x not in ('','.','..') for x in s.split('/')[1:]) and str(Path(s))==s,'canonical absolute path')
    return Path(s)

def typed_equal(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:return a.keys()==b.keys() and all(typed_equal(a[k],b[k]) for k in a)
    if type(a) is list:return len(a)==len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
    return a==b

def encode_bound(value,cap=2097152):
    stack=set()
    def visit(v,depth):
        need(depth<=64,'bounded JSON nesting')
        if v is None:return 4
        if type(v) is bool:return 5
        if type(v) is int:return v.bit_length()//3+4
        if type(v) is float:need(math.isfinite(v),'finite JSON number');return 32
        if type(v) is str:return 2+12*len(v)
        need(type(v) in (dict,list),'positive primitive JSON types')
        need(id(v) not in stack,'acyclic JSON');stack.add(id(v));n=2
        if type(v) is dict:
            for k,x in v.items():
                need(type(k) is str,'JSON keys are strings');n+=visit(k,depth+1)+visit(x,depth+1)+2
                need(n<=cap,'prospective JSON encoding cap')
        else:
            for x in v:n+=visit(x,depth+1)+1;need(n<=cap,'prospective JSON encoding cap')
        stack.remove(id(v));return n
    n=visit(value,0);need(n<=cap,'prospective JSON encoding cap');return n

def encode(value,cap=2097152):
    encode_bound(value,cap)
    body=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')+b'\n'
    need(len(body)<=cap,'JSON actual encoding cap');return body

def parse_json(body):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(value):raise Refusal('nonfinite JSON literal')
    out=json.loads(body,object_pairs_hook=pairs,parse_constant=bad)
    encode_bound(out,max(2097152,len(body)*12+128))
    return out

def _stamp(s):
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_nlink)

def _directory_identity(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)

def _error(exc,where):
    try:message=str(exc)[:384]
    except BaseException:message='message unavailable'
    return {'where':str(where)[:96],'type':type(exc).__name__[:96],'message':message}

class IO:
    FAILURE_CAP=16384
    def __init__(self,context):
        exact(context,{'origin','deadline','read_cap','write_cap','live_cap'},'exact IO context')
        need(all(type(context[k]) in (float,int) and math.isfinite(context[k]) for k in ('origin','deadline'))
             and context['origin']<context['deadline'],'finite original construction clock')
        need(all(type(context[k]) is int and context[k]>0 for k in ('read_cap','write_cap','live_cap')),'positive typed IO caps')
        self.context=dict(context)
        for k,v in context.items():setattr(self,k,v)
        self.read_reserved=self.read_observed=self.write_reserved=self.write_observed=0
        self.live=self.peak_live=0;self.operations=0;self.later=[];self.owned=None
        self.attempted_paths=[];self.events=[];self._owned_fd=None;self.ownership_closure="not_acquired";self.tick()
        self.reserve_read(self.FAILURE_CAP+1,'failure readback reserve')
        self.reserve_write(self.FAILURE_CAP,'failure write reserve')
    def tick(self):
        now=time.monotonic();need(self.origin<=now<self.deadline,'original clock expired/rolled back')
    def reserve_read(self,n,label):
        self.tick();need(type(n) is int and n>=0 and self.read_reserved+n<=self.read_cap,'read reservation '+label)
        self.read_reserved+=n
    def reserve_write(self,n,label):
        self.tick();need(type(n) is int and n>=0 and self.write_reserved+n<=self.write_cap,'write reservation '+label)
        self.write_reserved+=n
    @contextmanager
    def hold(self,n,label):
        self.tick();need(type(n) is int and n>=0 and self.live+n<=self.live_cap,'live reservation '+label)
        self.live+=n;self.peak_live=max(self.peak_live,self.live)
        try:yield
        finally:self.live-=n
    def _parents(self,path):
        path=canonical_path(path);rows=[]
        for p in reversed(path.parents):
            s=os.lstat(p);need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode),'ordinary parent directory')
            rows.append((p,_directory_identity(s)))
        return rows
    def _check_parents(self,rows):
        for p,old in rows:
            s=os.lstat(p);need(stat.S_ISDIR(s.st_mode) and _directory_identity(s)==old,'parent custody changed')
    def _close(self,fd,phase):
        try:os.close(fd)
        except BaseException as e:self.later.append(_error(e,phase))
    def _finish(self,primary,base_later,phase):
        try:self.tick()
        except BaseException as e:self.later.append(_error(e,phase+' final clock'))
        if primary is not None:raise primary
        if len(self.later)>base_later:raise Refusal('independent cleanup/durability failure: '+phase)
    def read(self,path,expected=None,cap=2097152,readonly=False,_prepaid=False,_reserved=False):
        p=canonical_path(path);need(type(cap) is int and cap>=0,'read cap')
        if expected is not None:valid_pin(expected)
        n=expected['bytes'] if expected is not None else cap
        need(n<=cap,'expected body within cap')
        if _prepaid:need(n+1<=self.FAILURE_CAP+1,'prepaid failure read size')
        elif not _reserved:self.reserve_read(n+1,'capture '+p.name)
        self.tick();parents=self._parents(p);initial=os.lstat(p)
        need(stat.S_ISREG(initial.st_mode) and initial.st_nlink==1 and initial.st_size<=n,'ordinary bounded file')
        if expected is not None:need(initial.st_size==n,'exact expected extent')
        if readonly:need(initial.st_mode&0o222==0,'sealed readonly operand')
        self.attempted_paths.append(str(p));fd=None;primary=None;body=None;start_later=len(self.later)
        try:
            self.tick();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);self.operations+=1
            self.tick();need(_stamp(os.fstat(fd))==_stamp(initial),'same-open initial custody')
            with self.hold(2*(n+1)+4096,'capture bytes and chunks'):
                blocks=[];left=n+1
                while left:
                    self.tick();block=os.read(fd,min(left,1048576));self.operations+=1
                    self.read_observed+=len(block);self.tick()
                    if not block:break
                    blocks.append(block);left-=len(block)
                body=b''.join(blocks)
            need(len(body)==initial.st_size,'EOF/extent changed or sentinel overflow')
            if expected is not None:need(pin_bytes(body)==expected,'exact body hash')
            need(_stamp(os.fstat(fd))==_stamp(initial)==_stamp(os.lstat(p)),'same-open/current-name capture')
            self._check_parents(parents);self.tick()
        except BaseException as e:primary=e
        finally:
            if fd is not None:self._close(fd,'read close')
            try:
                need(_stamp(os.lstat(p))==_stamp(initial),'post-close current-name capture');self._check_parents(parents)
            except BaseException as e:self.later.append(_error(e,'read postclose'))
            self._finish(primary,start_later,'read')
        return body
    def json(self,path,expected=None,cap=2097152,readonly=False):
        n=expected['bytes'] if expected is not None else cap
        with self.hold(14*(n+1)+4096,'JSON capture/parse/encoding validation'):
            result=parse_json(self.read(path,expected,cap,readonly))
        self.tick();return result
    def _owned_check(self):
        if self.owned is None:return
        need(self._owned_fd is not None,'owned directory descriptor is not held')
        p=self.owned['path'];identity=self.owned['identity']
        need(_directory_identity(os.fstat(self._owned_fd))==identity,'held original root identity')
        now=os.lstat(p)
        need(stat.S_ISDIR(now.st_mode) and _directory_identity(now)==identity,'owned root replaced')
        self._check_parents(self.owned['parents'])
    @contextmanager
    def _parent_fd(self,path):
        # Every namespace mutation uses a held parent descriptor. If an ancestor
        # is renamed after checking, an openat/mkdirat cannot follow its new name.
        p=canonical_path(path);self.tick();self._owned_check()
        fds=[];rows=[];primary=None;start=len(self.later)
        try:
            absolute=Path('/');initial=os.lstat(absolute)
            self.tick();fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);self.operations+=1
            fds.append(fd);need(_directory_identity(os.fstat(fd))==_directory_identity(initial),'root directory same-open')
            rows.append((absolute,_directory_identity(initial)))
            for name in p.parts[1:-1]:
                self.tick();self._owned_check()
                before=os.stat(name,dir_fd=fd,follow_symlinks=False)
                need(stat.S_ISDIR(before.st_mode),'ordinary descriptor-relative parent')
                child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);self.operations+=1
                fds.append(child);self.tick()
                need(_directory_identity(os.fstat(child))==_directory_identity(before)==_directory_identity(os.stat(name,dir_fd=fd,follow_symlinks=False)),'parent child same-open/name')
                absolute=absolute/name;rows.append((absolute,_directory_identity(before)));fd=child
            self._check_parents(rows);self._owned_check();self.tick()
            yield fd,p.name,rows
        except BaseException as error:primary=error
        finally:
            try:self._check_parents(rows);self._owned_check()
            except BaseException as error:self.later.append(_error(error,'anchored namespace final custody'))
            for fd in reversed(fds):self._close(fd,'anchored directory close')
            self._finish(primary,start,'anchored namespace')
    def sync_dir(self,path):
        p=canonical_path(path);fd=None;primary=None;start=len(self.later)
        with self._parent_fd(p) as (parent,name,rows):
            initial=os.stat(name,dir_fd=parent,follow_symlinks=False)
            need(stat.S_ISDIR(initial.st_mode),'ordinary sync directory')
            try:
                self.tick();fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);self.operations+=1;self.tick()
                need(_directory_identity(os.fstat(fd))==_directory_identity(initial),'sync same-open directory')
                self._owned_check();self.tick();os.fsync(fd);self.operations+=1;self.tick()
            except BaseException as error:primary=error
            finally:
                if fd is not None:self._close(fd,'sync directory close')
                try:need(_directory_identity(os.stat(name,dir_fd=parent,follow_symlinks=False))==_directory_identity(initial),'sync current-name identity')
                except BaseException as error:self.later.append(_error(error,'sync directory postclose'))
                self._finish(primary,start,'sync_dir')
    def mkdir(self,path,exclusive=True):
        p=canonical_path(path);fd=None;primary=None;start=len(self.later)
        with self._parent_fd(p) as (parent,name,rows):
            try:
                try:existing=os.stat(name,dir_fd=parent,follow_symlinks=False)
                except FileNotFoundError:existing=None
                if not exclusive and existing is not None:
                    need(stat.S_ISDIR(existing.st_mode),'ordinary existing selected directory');return
                need(existing is None,'fresh selected directory')
                self._owned_check();self.tick();os.mkdir(name,0o700,dir_fd=parent);self.operations+=1;self.tick()
                before=os.stat(name,dir_fd=parent,follow_symlinks=False)
                fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);self.operations+=1
                need(_directory_identity(os.fstat(fd))==_directory_identity(before),'new directory same-open/name')
                self._owned_check();self.tick();os.fsync(fd);self.operations+=1;self.tick()
                os.fsync(parent);self.operations+=1;self.tick()
            except BaseException as error:primary=error
            finally:
                if fd is not None:self._close(fd,'mkdir directory close')
                self._finish(primary,start,'mkdir')
    def claim_root(self,path):
        p=canonical_path(path);need(self.owned is None,'one owned root per command');fd=None;primary=None;start=len(self.later)
        with self._parent_fd(p) as (parent,name,parents):
            try:
                try:os.stat(name,dir_fd=parent,follow_symlinks=False)
                except FileNotFoundError:pass
                else:raise Refusal('fresh root; preexisting never owned')
                self.tick();os.mkdir(name,0o700,dir_fd=parent);self.operations+=1
                observed=os.stat(name,dir_fd=parent,follow_symlinks=False)
                fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);self.operations+=1
                need(stat.S_ISDIR(observed.st_mode) and _directory_identity(os.fstat(fd))==_directory_identity(observed),'new root same-open/name')
                self.owned={'path':p,'identity':_directory_identity(observed),'parents':list(parents),'created':True,'durability':'unknown'}
                self._owned_fd=fd;fd=None;self.ownership_closure='held'
                self._owned_check();self.tick();os.fsync(self._owned_fd);self.operations+=1;self.tick()
                os.fsync(parent);self.operations+=1;self.tick();self._owned_check()
                self.owned['durability']='observed_synced'
            except BaseException as error:primary=error
            finally:
                if fd is not None:self._close(fd,'unacquired root close')
                self._finish(primary,start,'claim_root')
    def owned_root(self):
        need(self.owned is not None and self.owned['created'],'no root ownership')
        self._owned_check();return self.owned['path']
    def close(self):
        # The final CLI closes this held root before reporting success. On failure
        # its bounded failure publication precedes independent descriptor cleanup.
        if self._owned_fd is None:return
        primary=None;start=len(self.later);fd=self._owned_fd
        try:self._owned_check();self.tick()
        except BaseException as error:primary=error
        self._owned_fd=None
        try:os.close(fd);self.ownership_closure='closed'
        except BaseException as error:
            self.ownership_closure='unknown';self.later.append(_error(error,'owned root close'))
        try:
            need(_directory_identity(os.lstat(self.owned['path']))==self.owned['identity'],'owned root postclose name')
            self._check_parents(self.owned['parents'])
        except BaseException as error:self.later.append(_error(error,'owned root postclose custody'))
        self._finish(primary,start,'owned root close')
    def _read_published(self,parent,name,observed,body):
        # Publication already reserved len(body)+1. Use the same held parent
        # for readback, never a newly resolved replacement pathname.
        fd=None;primary=None;start=len(self.later);got=None;n=len(body)+1
        try:
            self._owned_check();self.tick()
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent);self.operations+=1;self.tick()
            need(_stamp(os.fstat(fd))==_stamp(observed),'published readback same inode')
            with self.hold(2*n+4096,'anchored publication readback'):
                blocks=[];left=n
                while left:
                    self._owned_check();self.tick();block=os.read(fd,min(left,1048576));self.operations+=1
                    self.read_observed+=len(block);self.tick()
                    if not block:break
                    blocks.append(block);left-=len(block)
                got=b''.join(blocks)
            need(got==body,'exact anchored publication EOF/readback')
            need(_stamp(os.fstat(fd))==_stamp(observed)==_stamp(os.stat(name,dir_fd=parent,follow_symlinks=False)),'anchored publication readback custody')
        except BaseException as error:primary=error
        finally:
            if fd is not None:self._close(fd,'publication readback close')
            try:need(_stamp(os.stat(name,dir_fd=parent,follow_symlinks=False))==_stamp(observed),'publication readback postclose')
            except BaseException as error:self.later.append(_error(error,'publication readback postclose'))
            self._finish(primary,start,'publication readback')
        return got
    def put(self,path,value,cap=2097152,_prepaid=False):
        p=canonical_path(path);self.tick()
        bound=len(value) if type(value) is bytes else encode_bound(value,cap)+1
        need(bound<=cap,'positive output extent')
        with self.hold(bound*3+4096,'output canonical bytes/readback'):
            body=value if type(value) is bytes else encode(value,cap)
            if not _prepaid:
                self.reserve_read(len(body)+1,'prospective publication readback '+p.name)
                self.reserve_write(len(body),'fresh publication '+p.name)
            else:need(len(body)<=self.FAILURE_CAP,'prepaid failure output')
            with self._parent_fd(p) as (parent,name,parents):
                fd=None;primary=None;start=len(self.later);observed=None
                try:
                    try:os.stat(name,dir_fd=parent,follow_symlinks=False)
                    except FileNotFoundError:pass
                    else:raise Refusal('fresh leaf; never overwrite')
                    self._owned_check();self.tick()
                    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent);self.operations+=1;self.tick()
                    before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'ordinary new output')
                    at=0
                    while at<len(body):
                        self._owned_check();self.tick();n=os.write(fd,memoryview(body)[at:]);self.operations+=1;self.write_observed+=n;self.tick()
                        need(n>0,'short output write');at+=n
                    self._owned_check();self.tick();os.fchmod(fd,0o444);self.operations+=1;self.tick()
                    os.fsync(fd);self.operations+=1;self.tick()
                    observed=os.fstat(fd)
                    need(_stamp(observed)==_stamp(os.stat(name,dir_fd=parent,follow_symlinks=False)) and observed.st_nlink==1,'output FD/held-parent name custody')
                    self._check_parents(parents);self._owned_check()
                except BaseException as error:primary=error
                finally:
                    if fd is not None:self._close(fd,'output close')
                    try:
                        if observed is not None:need(_stamp(os.stat(name,dir_fd=parent,follow_symlinks=False))==_stamp(observed),'output postclose identity')
                        self._check_parents(parents);self._owned_check()
                    except BaseException as error:self.later.append(_error(error,'output postclose'))
                    self._finish(primary,start,'put')
                self._owned_check();self.tick();os.fsync(parent);self.operations+=1;self.tick()
                self._read_published(parent,name,observed,body)
            pin=pin_bytes(body);self._owned_check();self.tick()
        return {'path':str(p),'pin':pin}
    def record(self):
        return {'origin':self.origin,'deadline':self.deadline,'read_cap':self.read_cap,'write_cap':self.write_cap,'live_cap':self.live_cap,
                'read_reserved':self.read_reserved,'read_observed':self.read_observed,'unused_max_read_reservations':self.read_reserved-self.read_observed-getattr(self,'unobserved_external_read_reservations',0),
                'unobserved_external_read_reservations':getattr(self,'unobserved_external_read_reservations',0),
                'write_reserved':self.write_reserved,'write_observed':self.write_observed,'unused_write_reservations':self.write_reserved-self.write_observed,
                'ownership_descriptor_closure':self.ownership_closure,'planned_live':self.live,'peak_planned_live':self.peak_live,'operations':self.operations,'attempted_path_count':len(self.attempted_paths),
                'recent_attempted_paths':self.attempted_paths[-8:],'later_errors':self.later[-16:],'physical_IO_and_RSS':'unmeasured'}
    def failure(self,error):
        out={'schema':'neural049_portable_constructor_failure_v1','primary':_error(error,'constructor'),
             'later_errors':self.later[-16:],'costs':self.record(),'automatic_retry':False,'failure_publication':'not_attempted',
             'ownership':None if self.owned is None else {'created':True,'durability':self.owned['durability']},
             'unknowns':['partial output/durability and interrupted external work require inspection']}
        try:
            root=self.owned_root();self.tick()
            raw=encode(out,self.FAILURE_CAP)
            saved=self.put(root/'FAILED.json',raw,cap=self.FAILURE_CAP,_prepaid=True)
            out['failure_publication']={'descriptor':saved,'status':'returned_readback'}
        except BaseException as e:
            out['failure_publication']='not_written_or_uncertain';out['later_errors']=(out['later_errors']+[_error(e,'failure publication')])[-16:]
        out['costs']=self.record();return out

TASK='NEURAL-049'
PROFILE='curated_retrospective_full_v1'
J_REL='benchmarks/neuroscience/neural-049/manifest.json'
SCORE_REL='benchmarks/neuroscience/neural-049/score.py'
V_REL='central/registry-generations'
Q_REL='central/runtime-qualification'
R_REL='central/operator-selections'

def beneath(path,root):
    path=canonical_path(path);root=canonical_path(root)
    need(path!=root and root in path.parents,'selected strict path domain');return path

def token(value):
    need(type(value) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}',value),'bounded metadata name');return value

def absolute_descriptor(root,d):
    descriptor(d);relative_path(d['path']);return {'path':str(root/d['path']),'pin':d['pin']}

def relative_descriptor(root,d):
    descriptor(d);p=beneath(d['path'],root);return {'path':p.relative_to(root).as_posix(),'pin':d['pin']}

def read_descriptor(io,d,cap=2097152,readonly=True):
    descriptor(d);canonical_path(d['path']);return io.json(d['path'],d['pin'],cap,readonly)

def modules(value):
    need(type(value) is list and value in (['core'],['core','T1'],['core','D'],['core','T1','D']),'complete ordered core/T1/D modules');return value
