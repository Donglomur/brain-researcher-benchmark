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

# Source fragment2: complete immutable source instance construction/admission.
LAYOUT_CANONICAL_SHA='fb0881ee2616017f079f402218de2f2f2b956c5b55b38c83019cd6edf9baed08'
ORIGIN_MAP_PIN={'bytes':100847,'sha256':'1ef7cbe8500fee76e88deefe331a838c72fc4e48620bedb0da53273e21a7d3eb'}
ORIGINAL_PARENT_MANIFEST_PIN={'bytes': 10356, 'sha256': '1344647cfff641c7682ced4ddf0f66a03607094b4544b8352a73c77a7d50b954'}
PARENT_MANIFEST_PIN={'bytes': 10356, 'sha256': '6585fe967ebf845ee3b089b603970d69548ba4116dc8360035a413648dfd5ddd'}
PORTABLE_ROLES={'central/entry.py','central/routing.py','central/dispatch.py','central/portable_gate.py','constructor/neural049_instance.py','shared/stage_launcher.py','parent/program/authority.py','parent/program/bank.py','parent/RUNTIME_SOURCE_V3.json'}
CENTRAL_NAMES={'entry.py','routing.py','dispatch.py','portable_gate.py','io.py','readback.py','BINDINGS.json'}
LOCAL_GATE_LIMITS={'single_pass_read_bound':6*(131072+1),'two_pass_read_bound':12*(131072+1),'body_bytes':131072,'review_bytes':32768,'route_evidence_bytes':2097152,'evidence_count':32}
STATE_FIELDS={'schema','instance','source_manifest','parent_manifest','source_freeze','declaration','current_registry','predecessor_state','activation'}

def _dir(io,root,relative):
    relative_path(relative);p=root
    for part in relative.split('/'):
        p=p/part
        if not p.exists():io.mkdir(p)
        else:need(p.is_dir() and not p.is_symlink(),'ordinary selected build directory')
    return p

def _publish(io,root,relative,value,inventory,cap=2097152):
    relative_path(relative);_dir(io,root,str(Path(relative).parent)) if '/' in relative else None
    d=io.put(root/relative,value,cap=cap);inventory[relative]=d['pin'];return d

def _template(source,condition='default',grade=False):
    return ['{python}',SCORE_REL if grade else 'central/entry.py','--operation','grade' if grade else 'collect',
            '--panel','review' if grade else PROFILE,'--condition',condition,'--program','{program}','--output','{output}',
            '--review','{review}','--other-reserve-bytes','{other_reserve_bytes}','--source-bytes',str(source['bytes']),'--source-sha256',source['sha256']]

def _registry(original,root,source,freeze,selection,construction,entry_pin,parent_pin):
    # Preserve only explicitly selected original scientific fields; no old installation identity.
    keep={'schema_version','id','track','title','scientific_scope','counting_unit','complete_support'}
    need(keep<=set(original) and original['id']==TASK,'original canonical registry geometry')
    result={k:copy.deepcopy(original[k]) for k in keep}
    result.update({'status':'source_only_unqualified','admission':{'runnable':False,'scientifically_qualified':False},
                   'verification':{'status':'not_run'},'parent_source':{'path':'parent/RUNTIME_SOURCE_V3.json','pin':parent_pin},
                   'portable_instance':{'construction':construction,'selection':selection}})
    preferred={'path':'central','source':{'path':'central/SOURCE_MANIFEST.json',**source}}
    def meta(argv):return {'entrypoint':{'argv':argv,'sha256':entry_pin['sha256'],'working_directory':'.'},
                          'full_panel':PROFILE,'preferred_source_interface':preferred,
                          'source_freeze':{'path':'central/QUALIFICATION_SOURCE_FREEZE.json',**freeze['pin']},
                          'verification':{'status':'not_run','reason':'Local source constructed; execution and scientific qualifications remain unverified.'}}
    result['program_execution']=meta(_template(source))
    result['program_conditions']={PROFILE:meta(_template(source,PROFILE))}
    result['protected_grading_execution']=meta(_template(source,grade=True))
    score=_template(source,grade=True);score[score.index('{program}')]='{submission}'
    result['entrypoints']={'score':{'argv':score,'sha256':entry_pin['sha256'],'working_directory':'.'}}
    return result

def _profile(io,profile,root,requirements):
    exact(profile,{'schema','instance_name','root','external_operator_metadata_root','selected_profile','requested_modules','cache_preference','unresolved','construction_limits'},'build profile fields')
    need(profile['schema']=='neural049_portable_build_profile_v1' and profile['selected_profile']==PROFILE,'selected full profile')
    token(profile['instance_name']);need(canonical_path(profile['root'])==root,'exact selected output root');modules(profile['requested_modules'])
    need(type(profile['cache_preference']) is bool,'explicit intended cache preference')
    exact(profile['construction_limits'],{'read_cap','write_cap','live_cap'},'construction caps')
    need(typed_equal(profile['construction_limits'],{k:getattr(io,k) for k in ('read_cap','write_cap','live_cap')}),'profile cannot reset caps')
    p=canonical_path(profile['external_operator_metadata_root']);io._parents(p)
    need(p!=root and root not in p.parents and p not in root.parents,'external protected metadata root outside instance')
    need(type(profile['unresolved']) is list and len(profile['unresolved'])==len(requirements),'complete unresolved requirement inventory')
    names=[]
    for item in profile['unresolved']:
        exact(item,{'name','status','reason','role'},'unresolved slot fields');token(item['name'])
        need(item['status']=='missing' and type(item['reason']) is str and item['reason'] and type(item['role']) is str,'unresolved slots are never qualified')
        names.append(item['name'])
    need(len(names)==len(set(names)) and set(names)=={r['name'] for r in requirements},'exact unresolved names')
    return p

def build_instance(io,release_descriptor,public_root,root,profile_descriptor):
    descriptor(release_descriptor);descriptor(profile_descriptor);root=canonical_path(root);public_root=canonical_path(public_root)
    release_path=canonical_path(release_descriptor['path']);release_base=release_path.parent
    need(root!=public_root and root not in public_root.parents and public_root not in root.parents,'fresh output disjoint public source')
    need(root!=release_base and root not in release_base.parents and release_base not in root.parents,'output disjoint portable release')
    release_raw=io.read(release_path,release_descriptor['pin'],readonly=True);release=parse_json(release_raw)
    exact(release,{'schema','task_id','profile','public_origin_map','public_files','portable_sources','variant_pairs','context_order','source_layout','requirements'},'release fields')
    need(release['schema']=='neural049_portable_release_v1' and release['task_id']==TASK and release['profile']==PROFILE,'portable release identity')
    layout=release['source_layout'];need(hashlib.sha256(encode(layout).rstrip(b'\n')).hexdigest()==LAYOUT_CANONICAL_SHA,'exact accepted109 source layout')
    rows=layout['files'];need(len(rows)==109 and len({x['path'] for x in rows})==109,'full unique active layout')
    originals=[x for x in rows if x['kind']=='unchanged_original']
    need(len([x for x in originals if x['path'].startswith('parent/') and x['path']!='parent/RUNTIME_SOURCE_V3.json'])==68,'exact68 unchanged operative parent bodies plus2 variants')
    contexts=[x['path'] for x in rows if x['role']=='scientific_context']
    need(release['context_order']==contexts and len(contexts)==22,'exact22 context order')
    public=release['public_files'];need(type(public) is dict and len(public)==137,'exact137 archive public map')
    for path,pin in public.items():relative_path(path);valid_pin(pin)
    descriptor(release['public_origin_map']);relative_path(release['public_origin_map']['path'])
    need(release['public_origin_map']['pin']==ORIGIN_MAP_PIN,'reviewed original public map pin')
    map_raw=io.read(release_base/release['public_origin_map']['path'],ORIGIN_MAP_PIN,readonly=True);origin_map=parse_json(map_raw)
    need({x['path']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in origin_map['files']}==public,'all137 public identities, no private source-path read')
    need(set(release['portable_sources'])==PORTABLE_ROLES,'exact nine supplied portable source roles')
    for value in release['portable_sources'].values():descriptor(value);relative_path(value['path'])
    variants={x['path']:x for x in rows if x['kind']=='future_reviewed_variant'}
    need(set(release['variant_pairs'])==set(variants),'exact five declared source variant relationships')
    for target,pair in release['variant_pairs'].items():
        exact(pair,{'original','replacement'},'variant pair');need(pair['original']==variants[target]['original'] and pair['replacement']==release['portable_sources'][target]['pin'],'exact original/new variant pins')
    requirements=release['requirements'];need(type(requirements) is list and requirements,'real unresolved requirements')
    for req in requirements:exact(req,{'name','role','reason'},'release requirement');token(req['name'])
    profile=read_descriptor(io,profile_descriptor);operator_metadata=_profile(io,profile,root,requirements)
    total=sum(x['bytes'] for x in public.values())+sum(x['pin']['bytes'] for x in release['portable_sources'].values())
    with io.hold(total*3+8*(len(release_raw)+len(map_raw))+4194304,'all captured source and metadata construction'):
        bodies={path:io.read(public_root/path,pin,cap=max(2097152,pin['bytes']),readonly=False) for path,pin in public.items()}
        portable={target:io.read(release_base/value['path'],value['pin'],cap=max(2097152,value['pin']['bytes']),readonly=True)
                  for target,value in release['portable_sources'].items()}
        for row in originals:need(row['public_path'] in public and public[row['public_path']]==row['original']['pin'],'active original identity')
        parentrow=next(x for x in rows if x['path']=='parent/RUNTIME_SOURCE_V3.json')
        need(parentrow['original']['pin']==ORIGINAL_PARENT_MANIFEST_PIN,'preserved original parent manifest pin')
        original_parent=parse_json(bodies[parentrow['public_path']])
        parent_manifest=parse_json(portable['parent/RUNTIME_SOURCE_V3.json'])
        need(pin_bytes(portable['parent/RUNTIME_SOURCE_V3.json'])==PARENT_MANIFEST_PIN,'exact selected derived parent manifest')
        expected_parent=copy.deepcopy(original_parent);expected_parent['revision']=4
        for name in ('program/authority.py','program/bank.py'):
            expected_parent['files'][name]=release['portable_sources']['parent/'+name]['pin']
        need(typed_equal(parent_manifest,expected_parent),'only2 operative bank-proof variants and declared revision')
        need(len(parent_manifest['files'])==70 and len(parent_manifest['overrides'])==2,'complete parent and original2 overlays')
        parent_members=parent_manifest['files']
        io.claim_root(root);inventory={}
        for path,body in bodies.items():_publish(io,root,'origin/'+path,body,inventory,cap=max(2097152,len(body)))
        for row in originals:_publish(io,root,row['path'],bodies[row['public_path']],inventory,cap=max(2097152,row['original']['pin']['bytes']))
        for target,body in portable.items():_publish(io,root,target,body,inventory,cap=max(2097152,len(body)))
        _publish(io,root,SCORE_REL,portable['central/entry.py'],inventory)
        rel=_publish(io,root,'PORTABLE_RELEASE.json',release_raw,inventory)
        origin=_publish(io,root,'PUBLIC_ORIGIN_MAP.json',map_raw,inventory)
        construction={'schema':'neural049_portable_construction_v1','task_id':TASK,'profile':PROFILE,'root':str(root),
                      'release':relative_descriptor(root,rel),'public_origin_map':relative_descriptor(root,origin),
                      'active_originals':{x['path']:x['original'] for x in originals},'portable_sources':{x:release['portable_sources'][x]['pin'] for x in sorted(PORTABLE_ROLES)},
                      'variant_pairs':release['variant_pairs'],'context':{p:inventory[p] for p in contexts},'parent_overrides':parent_manifest['overrides'],
                      'scope':{'people':12,'days':55,'parent_members':70,'archive_members':137,'active_members':109,'profile':PROFILE},'status':'source_constructed_unqualified'}
        construction_d=_publish(io,root,'CONSTRUCTION.json',construction,inventory)
        earlier={p:pin for p,pin in inventory.items() if not p.startswith('origin/') and not p.startswith('central/') and p!=SCORE_REL}
        need(len(earlier)==100,'exact100 earlier source rows')
        bindings={'schema':'neural049_portable_bindings_v1','parent_root':'parent','parent_manifest':{'path':'parent/RUNTIME_SOURCE_V3.json','pin':PARENT_MANIFEST_PIN},
                  'parent_runtime_members':parent_members,'parent_overrides':parent_manifest['overrides'],'source_rows':earlier,
                  'shared':{'qualification':'shared/qualification.py','launch_parser':'shared/launch_parser.py','stage_launcher':'shared/stage_launcher.py'},
                  'construction':relative_descriptor(root,construction_d),'local_gate_limits':LOCAL_GATE_LIMITS}
        _publish(io,root,'central/BINDINGS.json',bindings,inventory)
        central={'schema':'neural049_portable_central_runtime_source_v1','files':{name:inventory['central/'+name] for name in sorted(CENTRAL_NAMES)}}
        central_d=_publish(io,root,'central/SOURCE_MANIFEST.json',central,inventory)
        active={x['path']:inventory[x['path']] for x in rows};need(len(active)==109 and sum(p['bytes'] for p in active.values())<=16*2**20,'exact active closure/source-capture cap')
        freeze_d=_publish(io,root,'central/QUALIFICATION_SOURCE_FREEZE.json',{'schema':'neural049_portable_source_freeze_v1','task_id':TASK,'files':active},inventory)
        selection={'schema':'neural049_portable_source_selection_v1','task_id':TASK,'profile':PROFILE,'root':str(root),'construction':construction_d,
                   'central_source':central_d['pin'],'parent_source':PARENT_MANIFEST_PIN,'source_freeze':freeze_d,
                   'registered_templates':{'default':_template(central_d['pin']),'named':_template(central_d['pin'],PROFILE),'grade':_template(central_d['pin'],grade=True)},
                   'module_options':['core','T1','D'],'status':'selected_source_only','scientific_qualification':False}
        selection_d=_publish(io,root,'SELECTION.json',selection,inventory)
        registry_key=J_REL if J_REL in bodies else None;need(registry_key is not None,'original scientific registry template supplied')
        registry=_registry(parse_json(bodies[registry_key]),root,central_d['pin'],freeze_d,selection_d,construction_d,inventory['central/entry.py'],PARENT_MANIFEST_PIN)
        _dir(io,root,V_REL);_dir(io,root,Q_REL);_dir(io,root,R_REL)
        generation=_publish(io,root,V_REL+'/initial-registry.json',registry,inventory)
        j=io.put(root/J_REL,encode(registry));need(j['pin']==generation['pin'],'separate exact initial J copy')
        state={'schema':'neural049_portable_registry_state_v1','instance':construction_d,'source_manifest':central_d,
               'parent_manifest':{'path':str(root/'parent/RUNTIME_SOURCE_V3.json'),'pin':PARENT_MANIFEST_PIN},'source_freeze':freeze_d,
               'declaration':selection_d,'current_registry':j['pin'],'predecessor_state':None,'activation':None}
        state_d=_publish(io,root,V_REL+'/initial-state.json',state,inventory)
        req_d=_publish(io,root,'REQUIREMENTS.json',{'schema':'neural049_portable_requirements_v1','status':'unresolved_unqualified',
                      'instance':construction_d,'slots':profile['unresolved'],'scientific_qualification':False},inventory)
        result={'schema':'neural049_portable_build_result_v1','status':'source_constructed_unqualified','root':str(root),'profile':profile,
                'instance':construction_d,'release':rel,'public_origin_map':origin,'central_source':central_d,'parent_source':state['parent_manifest'],
                'source_freeze':freeze_d,'selection':selection_d,'initial_registry_state':state_d,
                'historical_initial_registry':{'generation':generation,'pin':j['pin']},'requirements':req_d,
                'immutable':inventory,'source_counts':{'parent':70,'archive':137,'active':109},'costs_before_this_publication':io.record(),
                'scientific_operation':False,'qualification_generated':False}
        built=io.put(root/'BUILD_RESULT.json',result);io.tick()
        return {'build':built,'result':result,'costs':io.record()}

def _state(io,root,state_d,build,selection_d,freeze_d,instance,central_d,parent_d):
    descriptor(state_d);need(canonical_path(state_d['path']).parent==root/V_REL,'state directly in V')
    state=read_descriptor(io,state_d);exact(state,STATE_FIELDS,'typed registry-state fields')
    need(state['schema']=='neural049_portable_registry_state_v1','state schema')
    invariants={'instance':instance,'source_manifest':central_d,'parent_manifest':parent_d,'source_freeze':freeze_d,'declaration':selection_d}
    for k,v in invariants.items():need(typed_equal(state[k],v),'state immutable invariant '+k)
    valid_pin(state['current_registry'])
    if state['predecessor_state'] is None:
        need(state['activation'] is None and state_d==build['initial_registry_state'] and state['current_registry']==build['historical_initial_registry']['pin'],'exact initial state')
    else:
        descriptor(state['predecessor_state']);descriptor(state['activation'])
        need(canonical_path(state['predecessor_state']['path']).parent==root/V_REL and canonical_path(state['activation']['path']).parent==root/V_REL,'transition evidence confined V')
        old=read_descriptor(io,state['predecessor_state']);exact(old,STATE_FIELDS,'predecessor state fields')
        need(old['schema']=='neural049_portable_registry_state_v1','predecessor schema')
        for k,v in invariants.items():need(typed_equal(old[k],v),'predecessor immutable invariant '+k)
        valid_pin(old['current_registry'])
        a=read_descriptor(io,state['activation']);need(a.get('schema')=='neural049_portable_activation_v1' and a.get('status')=='observed_complete'
              and a.get('new_registry')==state['current_registry'] and a.get('old_state')==state['predecessor_state'] and a.get('old_registry')==old['current_registry'] and a.get('instance')==instance,'actual activation/state join')
        descriptor(a['transaction']);need(canonical_path(a['transaction']['path']).parent==root/V_REL,'transaction direct V')
        tx=read_descriptor(io,a['transaction'])
        need(tx.get('schema')=='neural049_portable_registry_transaction_v1' and tx.get('state')=='prepared' and tx.get('old_state')==state['predecessor_state'] and tx.get('old_registry')==old['current_registry'] and tx.get('new_registry')==state['current_registry'] and tx.get('instance')==instance and tx.get('source_freeze')==freeze_d and tx.get('allowed_path')==str(root/J_REL),'actual retained transaction/state')
        need(a.get('rename_returned') is True and a.get('v_synced') is True and a.get('j_parent_synced') is True and a.get('readback_pin')==state['current_registry'],'complete publication facts')
        cp=canonical_path(a['closure_path']);need(cp.parent==root/V_REL,'closure direct V child')
        closed=io.json(cp,cap=131072,readonly=True)
        need(closed.get('schema')=='neural049_portable_activation_closure_v1' and closed.get('status')=='observed_complete'
             and closed.get('activation')==state['activation'] and closed.get('registry_state')==state_d
             and closed.get('lock_released_and_v_synced') is True and closed.get('registry')==state['current_registry'],'actual state/lock closure')
    current=io.read(root/J_REL,state['current_registry'],cap=131072,readonly=True)
    return state,parse_json(current)

def _immutable_geometry(io,root,build,inventory,release,construction,central,parent,freeze,selection,bindings):
    need(build['scientific_operation'] is False and build['qualification_generated'] is False
         and build['source_counts']=={'parent':70,'archive':137,'active':109},'source-only complete build scope')
    layout=release['source_layout']
    need(hashlib.sha256(encode(layout).rstrip(b'\n')).hexdigest()==LAYOUT_CANONICAL_SHA,'exact accepted source layout on reload')
    rows=layout['files'];active={r['path'] for r in rows}
    need(len(active)==109 and set(freeze['files'])==active,'exact active path membership')
    public=release['public_files'];need(type(public) is dict and len(public)==137,'complete public source archive')
    need(set(inventory)==active|{'origin/'+p for p in public}|{'central/QUALIFICATION_SOURCE_FREEZE.json','SELECTION.json','REQUIREMENTS.json',V_REL+'/initial-registry.json',V_REL+'/initial-state.json'},'exact immutable source/metadata inventory')
    fixed={'instance':'CONSTRUCTION.json','release':'PORTABLE_RELEASE.json','public_origin_map':'PUBLIC_ORIGIN_MAP.json',
           'central_source':'central/SOURCE_MANIFEST.json','parent_source':'parent/RUNTIME_SOURCE_V3.json',
           'source_freeze':'central/QUALIFICATION_SOURCE_FREEZE.json','selection':'SELECTION.json',
           'initial_registry_state':V_REL+'/initial-state.json','requirements':'REQUIREMENTS.json'}
    for key,rel in fixed.items():need(build[key]=={'path':str(root/rel),'pin':inventory[rel]},'fixed build descriptor '+key)
    need(build['parent_source']['pin']==PARENT_MANIFEST_PIN and build['public_origin_map']['pin']==ORIGIN_MAP_PIN,'unchanged parent/map source pins')
    for p,pin in public.items():relative_path(p);valid_pin(pin);need(inventory['origin/'+p]==pin,'exact archived public member')
    origin_map=read_descriptor(io,build['public_origin_map'])
    need({r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in origin_map['files']}==public,'original reviewed public map join')
    originals=[r for r in rows if r['kind']=='unchanged_original']
    for r in originals:need(inventory[r['path']]==public[r['public_path']]==r['original']['pin'],'unchanged active original member')
    need(set(release['portable_sources'])==PORTABLE_ROLES,'exact nine supplied portable roles')
    for path,d in release['portable_sources'].items():descriptor(d);relative_path(d['path']);need(inventory[path]==d['pin'],'portable reviewed body pin')
    need(inventory[SCORE_REL]==inventory['central/entry.py'],'literal score/entry copy')
    need(central=={'schema':'neural049_portable_central_runtime_source_v1','files':{n:inventory['central/'+n] for n in sorted(CENTRAL_NAMES)}},'exact seven-member central manifest')
    members={r['path'][7:]:r['original']['pin'] for r in originals if r['path'].startswith('parent/')}
    need(len(members)==68,'exact unchanged operative parent subset')
    for name in ('program/authority.py','program/bank.py'):
        members[name]=release['portable_sources']['parent/'+name]['pin']
    parentrow=next(r for r in rows if r['path']=='parent/RUNTIME_SOURCE_V3.json')
    original_parent=io.json(root/'origin'/parentrow['public_path'],ORIGINAL_PARENT_MANIFEST_PIN,readonly=True)
    expected_parent=copy.deepcopy(original_parent);expected_parent['revision']=4;expected_parent['files']=members
    need(typed_equal(parent,expected_parent) and len(members)==70 and len(parent['overrides'])==2,'exact original70 with only2 selected variants and revision')
    contexts=[r['path'] for r in rows if r['role']=='scientific_context'];need(release['context_order']==contexts and len(contexts)==22,'exact context order')
    variants={r['path']:r for r in rows if r['kind']=='future_reviewed_variant'}
    need(set(release['variant_pairs'])==set(variants),'exact variant path membership')
    for target,pair in release['variant_pairs'].items():need(pair=={'original':variants[target]['original'],'replacement':inventory[target]},'exact source variant pair')
    expected_construction={'schema':'neural049_portable_construction_v1','task_id':TASK,'profile':PROFILE,'root':str(root),
          'release':relative_descriptor(root,build['release']),'public_origin_map':relative_descriptor(root,build['public_origin_map']),
          'active_originals':{r['path']:r['original'] for r in originals},'portable_sources':{p:inventory[p] for p in sorted(PORTABLE_ROLES)},
          'variant_pairs':release['variant_pairs'],'context':{p:inventory[p] for p in contexts},'parent_overrides':parent['overrides'],
          'scope':{'people':12,'days':55,'parent_members':70,'archive_members':137,'active_members':109,'profile':PROFILE},'status':'source_constructed_unqualified'}
    need(typed_equal(construction,expected_construction),'exact construction declaration')
    earlier={p:inventory[p] for p in active if not p.startswith('central/') and p!=SCORE_REL}
    need(len(earlier)==100,'exact earlier source count')
    need(bindings=={'schema':'neural049_portable_bindings_v1','parent_root':'parent','parent_manifest':{'path':'parent/RUNTIME_SOURCE_V3.json','pin':PARENT_MANIFEST_PIN},
           'parent_runtime_members':members,'parent_overrides':parent['overrides'],'source_rows':earlier,
           'shared':{'qualification':'shared/qualification.py','launch_parser':'shared/launch_parser.py','stage_launcher':'shared/stage_launcher.py'},
           'construction':relative_descriptor(root,build['instance']),'local_gate_limits':LOCAL_GATE_LIMITS},'exact bindings closure')
    need(selection=={'schema':'neural049_portable_source_selection_v1','task_id':TASK,'profile':PROFILE,'root':str(root),'construction':build['instance'],
           'central_source':build['central_source']['pin'],'parent_source':PARENT_MANIFEST_PIN,'source_freeze':build['source_freeze'],
           'registered_templates':{'default':_template(build['central_source']['pin']),'named':_template(build['central_source']['pin'],PROFILE),'grade':_template(build['central_source']['pin'],grade=True)},
           'module_options':['core','T1','D'],'status':'selected_source_only','scientific_qualification':False},'exact fixed selection/routes')
    need(build['historical_initial_registry']=={'generation':{'path':str(root/V_REL/'initial-registry.json'),'pin':inventory[V_REL+'/initial-registry.json']},'pin':inventory[V_REL+'/initial-registry.json']},'historical initial J identity')
    original=io.json(root/'origin'/J_REL,public[J_REL],readonly=True)
    initial=io.json(root/V_REL/'initial-registry.json',inventory[V_REL+'/initial-registry.json'],readonly=True)
    expected=_registry(original,root,build['central_source']['pin'],build['source_freeze'],build['selection'],build['instance'],inventory['central/entry.py'],PARENT_MANIFEST_PIN)
    need(typed_equal(initial,expected),'exact initial inactive registry from original public scientific fields')
    return initial

def _tree_geometry(io,root,inventory):
    allowed=set(inventory)|{J_REL,'BUILD_RESULT.json'};dirs={'.'}
    for path in allowed:
        p=Path(path).parent
        while p.as_posix()!='.':dirs.add(p.as_posix());p=p.parent
    dirs|={Q_REL,R_REL,V_REL};todo=[root];count=0
    while todo:
        directory=todo.pop();io.tick();before=_directory_identity(os.lstat(directory));parents=io._parents(directory)
        with os.scandir(directory) as stream:
            for entry in stream:
                count+=1;need(count<=4096,'bounded instance metadata inventory');io.tick()
                path=Path(entry.path);rel=path.relative_to(root).as_posix();s=entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(s.st_mode):need(rel in dirs,'no undeclared source directories');todo.append(path)
                else:
                    dynamic=path.parent in (root/Q_REL,root/R_REL,root/V_REL)
                    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and (rel in allowed or dynamic),'ordinary declared source or selected metadata file')
                    if dynamic:need(len(path.name)<=128 and (path.name.endswith('.json') or rel==V_REL+'/ACTIVATION.lock'),'bounded direct metadata filenames')
        need(_directory_identity(os.lstat(directory))==before,'inventory directory custody');io._check_parents(parents);io.tick()

def load_instance(io,build_descriptor,registry_state_descriptor=None):
    build=read_descriptor(io,build_descriptor);need(build.get('schema')=='neural049_portable_build_result_v1' and build.get('status')=='source_constructed_unqualified','complete source build')
    root=canonical_path(build['root']);need(canonical_path(build_descriptor['path'])==root/'BUILD_RESULT.json','fixed BUILD_RESULT path')
    inventory=build['immutable'];need(type(inventory) is dict and len(inventory)<=512,'bounded immutable inventory')
    for rel,pin in inventory.items():relative_path(rel);valid_pin(pin);io.read(root/rel,pin,cap=max(2097152,pin['bytes']),readonly=True)
    release=read_descriptor(io,build['release']);construction=read_descriptor(io,build['instance'])
    central=read_descriptor(io,build['central_source']);parent=read_descriptor(io,build['parent_source'])
    freeze=read_descriptor(io,build['source_freeze']);selection=read_descriptor(io,build['selection'])
    bindings=io.json(root/'central/BINDINGS.json',inventory['central/BINDINGS.json'],readonly=True)
    need(freeze.get('schema')=='neural049_portable_source_freeze_v1' and freeze.get('task_id')==TASK and len(freeze.get('files',{}))==109,'exact source freeze')
    need({k:inventory[k] for k in freeze['files']}==freeze['files'],'freeze inventory join')
    need(len(parent.get('files',{}))==70 and len([p for p in inventory if p.startswith('origin/')])==137,'all70 parent/137 archive identities')
    need(construction['root']==str(root) and construction['status']=='source_constructed_unqualified','construction identity')
    need(selection['construction']==build['instance'] and selection['source_freeze']==build['source_freeze'] and selection['central_source']==build['central_source']['pin'] and selection['parent_source']==build['parent_source']['pin'],'immutable selection joins')
    initial=_immutable_geometry(io,root,build,inventory,release,construction,central,parent,freeze,selection,bindings)
    _tree_geometry(io,root,inventory)
    state_d=registry_state_descriptor or build['initial_registry_state']
    state,registry_doc=_state(io,root,state_d,build,build['selection'],build['source_freeze'],build['instance'],build['central_source'],build['parent_source'])
    _route_static_unchanged(initial,registry_doc)
    need(registry_doc.get('id')==TASK and registry_doc.get('portable_instance')=={'construction':build['instance'],'selection':build['selection']},'current registry instance')
    io.tick()
    return {'root':root,'parent':root/'parent','central':root/'central','operator_metadata':canonical_path(build['profile']['external_operator_metadata_root']),
            'release':release,'construction':construction,'instance':build['instance'],'construction_descriptor':build['instance'],
            'central_source':build['central_source']['pin'],'parent_source':build['parent_source']['pin'],
            'freeze':build['source_freeze'],'selection':build['selection'],'registry':root/J_REL,'registry_document':registry_doc,
            'registry_state':state,'registry_state_descriptor':state_d,'immutable':inventory,'build':build_descriptor,'build_result':build,
            'bindings':bindings,'parent_manifest':parent,'central_manifest':central,'selection_body':selection,'source_freeze':freeze}

# Source fragment3: actual generic qualification, V-only one-path publication/state.
VERIFICATION_FIELDS={'status','receipt_path','receipt_sha256','qualification_path','qualification_sha256','source_binding_path','source_binding_sha256'}
QUALIFICATION_ORIGINAL='authoring/delivery-20261105/common/campaign-exposure-capacity-successor-v1/tools/neurobench_campaign.py'

def _generic(io,instance):
    root=instance['root'];inventory=instance['immutable']
    q=io.read(root/'shared/qualification.py',inventory['shared/qualification.py'],readonly=True)
    p=io.read(root/'shared/launch_parser.py',inventory['shared/launch_parser.py'],readonly=True)
    parser=types.ModuleType('_neural049_original_python_parser');parser.__file__=str(root/'shared/launch_parser.py')
    io.tick();exec(compile(p,parser.__file__,'exec'),parser.__dict__);io.tick()
    base=types.ModuleType('_neural049_original_generic_qualification');base.__file__=str(root/'origin'/QUALIFICATION_ORIGINAL)
    io.tick();exec(compile(q,base.__file__,'exec'),base.__dict__);io.tick()
    base._campaign_module=lambda unused_root=root:parser
    return base,parser

def _verification(value,evidence,root):
    exact(value,VERIFICATION_FIELDS,'original verification fields');need(value['status']=='passed','actual external qualification required')
    for prefix in ('receipt','qualification','source_binding'):
        path=value[prefix+'_path'];relative_path(path)
        need(Path(path).parent.as_posix()==Q_REL,'all route evidence direct Q child')
        name=Path(path).name;need(name.endswith('.json'),'metadata evidence extension');token(name[:-5])
        need(path in evidence and evidence[path]['sha256']==value[prefix+'_sha256'],'typed registered evidence pin')
    return value

def _generic_check(io,instance,base,parser,doc,kind,evidence):
    root=instance['root'];meta=doc['program_execution']
    expected_wrapper=SCORE_REL if kind=='grade' else 'central/entry.py'
    entry=meta['entrypoint'];idx=parser.python_launch(entry['argv'])
    need(idx==1 and entry['argv']==instance['selection_body']['registered_templates'][kind]
         and entry['argv'][idx]==expected_wrapper and entry['sha256']==instance['immutable'][expected_wrapper]['sha256']
         and entry['working_directory']=='.','actual original parser/template/source join')
    need(meta['source_freeze']=={'path':'central/QUALIFICATION_SOURCE_FREEZE.json',**instance['freeze']['pin']},'exact complete freeze descriptor')
    _verification(meta['verification'],evidence,root)
    need(instance['source_freeze']['files']=={p:instance['immutable'][p] for p in instance['source_freeze']['files']},'all109 exact dependency pins')
    G=4*(2097152+1)+2*(16777216+1)+sum(x['bytes']+1 for x in instance['source_freeze']['files'].values())
    io.reserve_read(G,'actual original generic qualification conservative full maximum')
    io.unobserved_external_read_reservations=getattr(io,'unobserved_external_read_reservations',0)+G
    io.tick();passed=base.verified_program_runtime(root/J_REL,doc,root);io.tick()
    need(passed is True,'actual unchanged generic helper must pass')
    return {'kind':kind,'reserved_read_maximum':G,'direct_helper_actual_bytes':'not instrumented; reservation retained'}

def _route_static_unchanged(old,new):
    x=copy.deepcopy(new);y=copy.deepcopy(old)
    for z in (x,y):
        z['program_execution']['verification']=None
        z['program_conditions'][PROFILE]['verification']=None
        z['protected_grading_execution']['verification']=None
        z['verification']=None;z['admission']['runnable']=False
    need(typed_equal(x,y),'only explicit route verification/runnable fields may change')
    need(new['admission']['scientifically_qualified'] is False and new['status']=='source_only_unqualified','no scientific/status promotion')

def _apply_routes(current,routes):
    new=copy.deepcopy(current)
    new['program_execution']['verification']=copy.deepcopy(routes['default'])
    new['program_conditions'][PROFILE]['verification']=copy.deepcopy(routes['named'])
    if routes['grade'] is not None:
        new['protected_grading_execution']['verification']=copy.deepcopy(routes['grade']['program'])
        new['verification']=copy.deepcopy(routes['grade']['scoring']);new['admission']['runnable']=True
    else:
        new['protected_grading_execution']['verification']={'status':'not_run','reason':'Protected grading source route is not qualified by this selection.'}
        new['verification']={'status':'not_run'};new['admission']['runnable']=False
    _route_static_unchanged(current,new)
    return new

def bind_route(io,build_descriptor,input_descriptor):
    request=read_descriptor(io,input_descriptor)
    exact(request,{'schema','registry_state','name','routes','evidence'},'bind route input')
    need(request['schema']=='neural049_portable_bind_route_v1','bind route schema');name=token(request['name'])
    instance=load_instance(io,build_descriptor,request['registry_state']);root=instance['root'];v=root/V_REL
    need(not (v/(name+'-transaction.json')).exists() and not (v/(name+'-registry.json')).exists(),'fresh generation namespace')
    routes=request['routes'];exact(routes,{'default','named','grade'},'all route conditions')
    supplied=request['evidence'];need(type(supplied) is dict and 1<=len(supplied)<=32,'bounded externally issued route evidence set')
    captured={};pins={}
    for basename,d in supplied.items():
        need(type(basename) is str and basename.endswith('.json'),'route evidence JSON names');token(basename[:-5]);descriptor(d)
        path=canonical_path(d['path']);need(root not in path.parents,'external evidence input outside instance')
        raw=io.read(path,d['pin'],cap=2097152,readonly=True);parse_json(raw)
        rel=Q_REL+'/'+basename;captured[rel]=raw;pins[rel]=d['pin']
    for kind in ('default','named'):_verification(routes[kind],pins,root)
    if routes['grade'] is not None:
        exact(routes['grade'],{'program','scoring'},'grade proof pair');_verification(routes['grade']['program'],pins,root)
        score=routes['grade']['scoring'];exact(score,{'status','receipt_path','receipt_sha256'},'separate scoring receipt')
        need(score['status']=='passed' and score['receipt_path'] in pins and score['receipt_sha256']==pins[score['receipt_path']]['sha256'],'score receipt exact Q pin')
        terminal=parse_json(captured[score['receipt_path']])
        need(terminal.get('candidate_id')==TASK and terminal.get('status')=='passed' and type(terminal.get('returncode')) is int
             and terminal['returncode']==0 and terminal.get('source_freeze_sha256')==instance['freeze']['pin']['sha256'],'separate grade terminal/freeze join')
    for rel,raw in captured.items():
        if (root/rel).exists():io.read(root/rel,pins[rel],readonly=True)
        else:io.put(root/rel,raw)
    new=_apply_routes(instance['registry_document'],routes)
    base,parser=_generic(io,instance);checks=[]
    checks.append(_generic_check(io,instance,base,parser,new,'default',pins))
    checks.append(_generic_check(io,instance,base,parser,{**new,'program_execution':new['program_conditions'][PROFILE]},'named',pins))
    if routes['grade'] is not None:checks.append(_generic_check(io,instance,base,parser,{**new,'program_execution':new['protected_grading_execution']},'grade',pins))
    # Actual live J and every immutable source remain current after helper direct reads.
    load_instance(io,build_descriptor,request['registry_state'])
    generation=io.put(v/(name+'-registry.json'),new,cap=131072)
    transaction={'schema':'neural049_portable_registry_transaction_v1','instance':instance['instance'],
                 'old_registry':instance['registry_state']['current_registry'],'new_registry':generation['pin'],'source_freeze':instance['freeze'],
                 'allowed_path':str(root/J_REL),'state':'prepared','qualified_evidence':{'inputs':pins,'checks':checks},
                 'generation':generation,'old_state':request['registry_state'],'name':name}
    tx=io.put(v/(name+'-transaction.json'),transaction)
    return {'transaction':tx,'generation':generation,'registry_state':request['registry_state'],'costs':io.record()}

def _publication_geometry(io,instance):
    root=instance['root'];v=root/V_REL;j=root/J_REL
    io.tick();io._parents(v);io._parents(j)
    a=os.lstat(v);b=os.lstat(j.parent)
    need(stat.S_ISDIR(a.st_mode) and stat.S_ISDIR(b.st_mode) and a.st_dev==b.st_dev,'same-device V/J-parent atomic publication')
    return v,j,_directory_identity(a),_directory_identity(b)

def activate_route(io,build_descriptor,input_descriptor):
    request=read_descriptor(io,input_descriptor);exact(request,{'schema','registry_state','transaction'},'activation input')
    need(request['schema']=='neural049_portable_activate_route_v1','activation schema')
    instance=load_instance(io,build_descriptor,request['registry_state']);root=instance['root'];v,j,vid,jpid=_publication_geometry(io,instance)
    publication_parents=io._parents(v)
    descriptor(request['transaction']);need(canonical_path(request['transaction']['path']).parent==v,'transaction in exact V')
    tx=read_descriptor(io,request['transaction']);exact(tx,{'schema','instance','old_registry','new_registry','source_freeze','allowed_path','state','qualified_evidence','generation','old_state','name'},'transaction positive fields')
    name=token(tx['name'])
    need(tx['schema']=='neural049_portable_registry_transaction_v1' and tx['state']=='prepared' and tx['instance']==instance['instance']
         and tx['source_freeze']==instance['freeze'] and tx['allowed_path']==str(j) and tx['old_state']==request['registry_state']
         and tx['old_registry']==instance['registry_state']['current_registry'],'transaction exact old instance/state/registry')
    descriptor(tx['generation']);need(canonical_path(tx['generation']['path'])==v/(name+'-registry.json') and tx['generation']['pin']==tx['new_registry'],'fixed generation identity')
    new_raw=io.read(tx['generation']['path'],tx['new_registry'],cap=131072,readonly=True)
    _route_static_unchanged(instance['registry_document'],parse_json(new_raw))
    # Re-run actual original predicates on the actual proposed bytes, not transaction booleans.
    evidence=tx['qualified_evidence']['inputs'];base,parser=_generic(io,instance);new=parse_json(new_raw)
    _generic_check(io,instance,base,parser,new,'default',evidence)
    _generic_check(io,instance,base,parser,{**new,'program_execution':new['program_conditions'][PROFILE]},'named',evidence)
    if new['protected_grading_execution']['verification']['status']=='passed':
        scoring=new['verification'];exact(scoring,{'status','receipt_path','receipt_sha256'},'separate scoring receipt')
        need(scoring['status']=='passed' and scoring['receipt_path'] in evidence and scoring['receipt_sha256']==evidence[scoring['receipt_path']]['sha256'],'actual scoring evidence pin')
        terminal=io.json(root/scoring['receipt_path'],evidence[scoring['receipt_path']],cap=2097152,readonly=True)
        need(terminal.get('candidate_id')==TASK and terminal.get('status')=='passed' and type(terminal.get('returncode')) is int and terminal['returncode']==0 and terminal.get('source_freeze_sha256')==instance['freeze']['pin']['sha256'],'actual scoring terminal/freeze')
        _generic_check(io,instance,base,parser,{**new,'program_execution':new['protected_grading_execution']},'grade',evidence)
    lock=v/'ACTIVATION.lock';need(not os.path.lexists(lock),'abandoned/active lock requires separate inspection')
    lock_d=io.put(lock,{'schema':'neural049_portable_activation_lock_v1','transaction':request['transaction'],'old_state':request['registry_state']})
    lock_id=_stamp(os.lstat(lock));staged=v/(name+'-staged.json')
    facts={'schema':'neural049_portable_activation_v1','status':'entered_incomplete','transaction':request['transaction'],
           'instance':instance['instance'],'old_state':request['registry_state'],'old_registry':tx['old_registry'],'new_registry':tx['new_registry'],
           'rename_returned':False,'v_synced':False,'j_parent_synced':False,'readback_pin':None,'lock':lock_d,
           'closure_path':str(v/(name+'-closed.json')),'automatic_retry':False}
    try:
        io.put(staged,new_raw,cap=131072)
        io.read(j,tx['old_registry'],cap=131072,readonly=True)
        # All fixed sources/state remain exact while this invocation owns the global lock.
        load_instance(io,build_descriptor,request['registry_state'])
        need(_directory_identity(os.lstat(v))==vid and _directory_identity(os.lstat(j.parent))==jpid and _stamp(os.lstat(lock))==lock_id,'publication namespace and lock custody')
        io.tick();os.replace(staged,j);io.operations+=1;facts['rename_returned']=True;io.tick()
        io.sync_dir(v);facts['v_synced']=True;io.sync_dir(j.parent);facts['j_parent_synced']=True
        io.read(j,tx['new_registry'],cap=131072,readonly=True);facts['readback_pin']=tx['new_registry'];io.tick()
        facts['status']='observed_complete';facts['costs_before_publication']=io.record()
        observation=io.put(v/(name+'-activation.json'),facts)
        state=copy.deepcopy(instance['registry_state']);state.update({'current_registry':tx['new_registry'],'predecessor_state':request['registry_state'],'activation':observation})
        state_d=io.put(v/(name+'-state.json'),state)
        # Retain exact owned lock bytes before releasing only that still-owned namespace.
        io.put(v/(name+'-lock-history.json'),io.read(lock,lock_d['pin'],readonly=True))
        need(_stamp(os.lstat(lock))==lock_id,'release only original owned lock');io.tick();os.unlink(lock);io.operations+=1;io.tick();io.sync_dir(v)
        closed=io.put(v/(name+'-closed.json'),{'schema':'neural049_portable_activation_closure_v1','status':'observed_complete',
                 'activation':observation,'registry_state':state_d,'lock_released_and_v_synced':True,'registry':tx['new_registry']})
        # No remembered current-J cache advances before the actual successful bounded observation.
        verified=load_instance(io,build_descriptor,state_d);need(verified['registry_state']['current_registry']==tx['new_registry'],'post-activation full invariant check')
        instance['registry_state']=verified['registry_state'];instance['registry_state_descriptor']=state_d
        io.tick();return {'activation':observation,'closure':closed,'registry_state':state_d,'registry':tx['new_registry'],'costs':io.record()}
    except BaseException as error:
        io.later.append(_error(error,'activation partial/unknown publication; retain V artifacts'))
        try:
            need(_directory_identity(os.lstat(v))==vid and _directory_identity(os.lstat(j.parent))==jpid,'failure publication namespace remains owned')
            io._check_parents(publication_parents)
            io.put(v/(name+'-failure.json'),{'schema':'neural049_portable_activation_failure_v1','facts':facts,'error':_error(error,'activation'),'costs':io.record(),'automatic_retry':False})
        except BaseException as later:io.later.append(_error(later,'activation failure receipt'))
        raise

# Concatenated after common/build/route. No sibling-file import or producer call.
import builtins as _s_builtins
import types as _s_types
import math as _s_math
import re as _s_re
import time as _s_time
from contextlib import contextmanager as _s_contextmanager
from pathlib import Path as _SPath

_S_TASK = 'NEURAL-049'
_S_PROFILE = 'curated_retrospective_full_v1'
_S_ACTIONS = {
    'select-run': {'profile'}, 'request-prepare': {'run','payload'},
    'bind-prepare': {'request','qualifications','launcher'},
    'request-bank': {'run','payload','preparation_completion'},
    'bind-bank': {'request','qualification','launcher'},
    'request-execution': {'run','payload','preparation_completion','bank_completion','bank_qualification'},
    'bind-execution': {'request','qualifications'},
    'request-review': {'run','authority','selection'},
    'bind-request': {'request','approval'},
    'bind-review': {'review_plan','request_bundle','qualification'},
    'admit-approved-review': {'review','approval_registry'},
    'bind-collection-completion': {'run','authority','collection','completion'},
    'request-late-grade': {'run','authority','collection_bundle','payload'},
    'bind-late-grade': {'request','declaration'},
}
_S_RUN_FIELDS = {'schema','task_id','profile','instance','original_clock','modules','cache','roots',
    'execution_fields','preparation_fields','bank_fields','resource_selection','observer_selection',
    'operator_identity','unresolved','status'}
_S_PREP_FIELDS = {'schema','status','origin','deadline','limits','source_root','output_root','metadata_root',
    'protected_roots','source_closure','roster','sources','axes','environment','module_D'}
_S_BANK_FIELDS = {'schema','active','source_manifest','backend','context','operator_identity','evidence_cap',
    'preparation_context','packet','copy_bytes','root','packet_root','source_root','output_root','operator_root',
    'secrets_root','kernel_read_per_file','kernel_write_per_file','array_cap','manifest_cap','kernel_read_manifest','kernel_write_manifest'}
_S_EXEC_FIELDS = {'schema','active','task_id','profile','source_manifest','modules','cache','roots','clock',
    'resources','profiles','provider_profiles','episode_limits','native_public','native_private','grading',
    'method_admissions','operator_identity','packet','bank','preparation_context','provider','host_python',
    'host_environment','actor_environment_inventory','reference_tolerance','seed_contract','numerical_contract',
    'base_generation','numerical_environments'}
_S_REVIEW_FIELDS = {'schema','task_id','selected','operation','panel','condition','selected_modules','cache',
    'central_source','parent_source','registry','authority','instance_request','instance_declaration','original_origin',
    'central_observation_deadline','central_validation_deadline','other_reserve_bytes','limits',
    'collection','collection_completion','grading_selection','roots'}
_S_REVIEW_LIMITS = {'read_bytes','write_bytes','host_memory_bytes','parent_retained_storage_bytes','free_floor_bytes',
    'qualification_read_bytes','validation_read_bytes','validation_cpu_ns','validation_numeric'}
_S_CENTRAL_FINDINGS = {'complete_panel','inherited_clock','central_resources','public_array_validation_resources',
    'actual_caller_observation','physical_root_custody','interpreter_environment','protected_scoring_boundary'}
_S_ROOTS = {'source','packet','targets','reference','output','operator','observation','secrets','store'}
_S_CAP = 2097152
_S_BANK_RESOURCE_KEYS = {'context','evidence_cap','copy_bytes','kernel_read_per_file','kernel_write_per_file',
                        'array_cap','manifest_cap','kernel_read_manifest','kernel_write_manifest'}
_S_EXEC_RESOURCE_KEYS = {'resources','profiles','provider_profiles','episode_limits','preparation_context'}
_S_CENTRAL_SELECTION_KEYS = {'central_observation_deadline','central_validation_deadline','limits','other_reserve_bytes'}
_S_PORTABLE_CLOCK_KEYS = ('original_origin','central_observation_deadline','central_validation_deadline')


def _s_equal(a, b):
    if type(a) is not type(b): return False
    if type(a) is dict: return set(a) == set(b) and all(_s_equal(a[k],b[k]) for k in a)
    if type(a) is list: return len(a) == len(b) and all(_s_equal(x,y) for x,y in zip(a,b))
    return a == b


def _s_pos(value, zero=False):
    need(type(value) is int and value >= (0 if zero else 1), 'stage ordinary integer')
    return value


def _s_finite(value):
    need(type(value) in (int,float) and _s_math.isfinite(value), 'stage finite clock')
    return value


def _s_portable_clock(value):
    """Exactly the consumer's finite-float projection; never samples a clock."""
    return float(_s_finite(value))


def _s_portable_clock_projection(values):
    return {k:_s_portable_clock(values[k]) for k in _S_PORTABLE_CLOCK_KEYS}


def _s_require_portable_clocks(value):
    for k in _S_PORTABLE_CLOCK_KEYS:
        need(type(value[k]) is float,'issued portable clock must already be canonical float: '+k)
        _s_portable_clock(value[k])


def _s_central_selection_projection(value):
    return {k:(_s_portable_clock(value[k]) if k in _S_PORTABLE_CLOCK_KEYS else value[k])
            for k in _S_CENTRAL_SELECTION_KEYS}


def _s_approval_entries(entries):
    need(type(entries) is list and 1<=len(entries)<=32,'bounded final approval entries')
    return entries


def _s_under(path, root, direct=False):
    path,root=canonical_path(str(path)),canonical_path(str(root))
    need(path.parent == root if direct else root in path.parents, 'fixed stage metadata namespace')
    return path


def _s_disjoint(a,b):
    a,b=canonical_path(str(a)),canonical_path(str(b))
    return a != b and a not in b.parents and b not in a.parents


def _s_descriptor(value):
    descriptor(value);canonical_path(value['path']);return value


def _s_read(io, d, root=None, cap=_S_CAP):
    _s_descriptor(d)
    path=canonical_path(d['path'])
    need(path.suffix == '.json', 'constructor accepts bounded JSON metadata only')
    if root is not None: _s_under(path,root)
    held=getattr(io,'_neural049_stage_retained',None)
    if held is not None:
        reservation=io.hold(14*(d['pin']['bytes']+1)+4096,'retained stage metadata until terminal result')
        reservation.__enter__();held.append(reservation)
    return io.json(path,expected=d['pin'],cap=cap,readonly=True)


def _s_put(io, root, name, value, cap=_S_CAP):
    need(type(name) is str and _s_re.fullmatch('[A-Z][A-Z0-9_]*[.]json',name), 'fixed source-owned stage output name')
    return io.put(root/name,value,cap=cap)


@_s_contextmanager
def _s_capsule(io, instance):
    """Private captured metadata definitions; no sys.modules mutation or producer import."""
    names={'core':'program/core.py','contracts':'program/contracts.py','configuration':'program/configuration.py',
           'prep_contracts':'preparation/contracts.py','authority':'program/authority.py'}
    bodies={}
    size=sum(instance['immutable']['parent/'+v]['bytes']+1 for v in names.values())
    with io.hold(size*16+65536,'captured metadata-only definitions'):
        for name,relative in names.items():
            expected=instance['immutable']['parent/'+relative]
            bodies[name]=io.read(instance['parent']/relative,expected=expected,cap=_S_CAP,readonly=True)
        modules={}
        def imported(name,globals=None,locals=None,fromlist=(),level=0):
            need(level == 0,'no relative capsule import')
            if name in names:
                need(name in modules,'capsule dependency order')
                return modules[name]
            need(name.split('.')[0] in {'hashlib','json','math','os','stat','sys','time','pathlib','re'},
                 'metadata-only standard library import')
            return _s_builtins.__import__(name,globals,locals,fromlist,level)
        for name in names:
            module=_s_types.ModuleType('_neural049_metadata_'+name)
            module.__dict__['__builtins__']={**vars(_s_builtins),'__import__':imported}
            io.tick();exec(compile(bodies[name],str(instance['parent']/names[name]),'exec',dont_inherit=True),module.__dict__);io.tick()
            modules[name]=module
        yield modules


def _s_route_admission(io,instance,registry,operation,condition):
    """Invoke actual captured routing, including its selected generic/scoring checks."""
    need(operation in ('collect','grade') and condition in (None,_S_PROFILE)
         and (operation!='grade' or condition is None),'exact selected operation and condition')
    names=('central/io.py','central/routing.py','shared/qualification.py','shared/launch_parser.py')
    retained=sum(instance['immutable'][n]['bytes']+1 for n in names)*16+65536
    with io.hold(retained,'complete source-bound routing and generic metadata definitions'):
        modules={}
        for name in ('io','routing'):
            relative='central/'+name+'.py';expected=instance['immutable'][relative]
            body=io.read(instance['root']/relative,expected=expected,cap=_S_CAP,readonly=True)
            module=_s_types.ModuleType('_neural049_stage_route_'+name)
            module.__file__=str(instance['root']/relative)
            io.tick();exec(compile(body,module.__file__,'exec',dont_inherit=True),module.__dict__);io.tick()
            modules[name]=module
        modules['routing'].u=modules['io']
        base,parser=_generic(io,instance)
        class MetadataHost:
            def read(self,path,cap,expected=None,readonly=False,retain=True):
                return io.read(path,expected=expected,cap=cap,readonly=readonly)
            def reserve(self,n):
                io.reserve_read(n,'actual selected route generic maximum')
                io.unobserved_external_read_reservations=getattr(io,'unobserved_external_read_reservations',0)+n
            def tick(self):return io.tick()
        env={'repo':instance['root'],'here':instance['central'],'freeze_files':instance['source_freeze']['files'],
             'manifest':instance['central_manifest'],'base':base,'gate':parser}
        return modules['routing'].qualify(registry,{'operation':operation,'condition':condition},env,MetadataHost())


def _s_roots(instance, roots):
    exact(roots,_S_ROOTS,'exact complete parent roots')
    need(canonical_path(roots['source']) == instance['parent'],'unchanged parent source root')
    need(canonical_path(roots['targets']) == canonical_path(roots['packet'])/'private','fixed protected target subtree')
    names=[k for k in roots if k != 'targets']
    need(all(_s_disjoint(roots[a],roots[b]) for i,a in enumerate(names) for b in names[i+1:]),'pairwise disjoint parent roots')
    need(all(_s_disjoint(instance['root'],roots[k]) for k in names if k != 'source'),'external roots outside entire instance')
    _s_under(instance['operator_metadata'],roots['operator'])


def _s_run(io, instance, desc):
    run=_s_read(io,desc,instance['operator_metadata'])
    exact(run,_S_RUN_FIELDS,'exact run selection')
    need(run['schema']=='neural049_portable_run_selection_v1' and run['task_id']==_S_TASK
         and run['profile']==_S_PROFILE and _s_equal(run['instance'],instance['instance'])
         and run['status']=='selected_not_qualified','same selected source-only run')
    clock=run['original_clock'];exact(clock,{'origin','production_end','observation_end','readback_end'},'original run clock')
    times=[_s_finite(clock[k]) for k in ('origin','production_end','observation_end','readback_end')]
    need(all(x<y for x,y in zip(times,times[1:])) and io.origin==times[0] and io.deadline<=times[-1],
         'same original clock, never extend parent grading')
    need(type(run['modules']) is list and run['modules'] and run['modules']==[x for x in ('core','T1','D') if x in run['modules']]
         and run['modules'][0]=='core' and len(run['modules'])==len(set(run['modules'])) and type(run['cache']) is bool,'complete modules/cache')
    need(type(run['operator_identity']) is str and run['operator_identity'],'selected independent external operator')
    need(type(run['unresolved']) is list,'explicit unresolved inventory')
    for row in run['unresolved']:
        exact(row,{'name','status','reason','role'},'unresolved slot')
        need(row['status']=='missing' and all(type(row[k]) is str and row[k] for k in ('name','reason','role')),'truthful missing slot')
    _s_roots(instance,run['roots']);_s_selected_fields(run);io.tick();return run


def _s_selected_fields(run):
    """Positive stable projections; no future completion or proof hash placeholders."""
    names=('preparation_fields','bank_fields','execution_fields','resource_selection','observer_selection')
    if run['unresolved']:
        need(all(run[k] is None or type(run[k]) is dict for k in names),'unresolved maps are not admissible')
        return
    prep,bank,execution=(run[k] for k in names[:3])
    exact(prep,_S_PREP_FIELDS,'all stable preparation settings selected')
    exact(bank,_S_BANK_FIELDS-{'packet'},'all stable bank settings selected')
    exact(execution,_S_EXEC_FIELDS-{'packet','bank'},'all stable execution settings selected')
    expected={'preparation':prep['limits'],'bank':{k:bank[k] for k in _S_BANK_RESOURCE_KEYS},
              'execution':{k:execution[k] for k in _S_EXEC_RESOURCE_KEYS}}
    need(_s_equal(run['resource_selection'],expected),'one exact typed resource selection')
    obs=run['observer_selection']
    exact(obs,{'host_python','host_environment','native_public','native_private','central','prepare_launcher',
               'bank_launcher','execution_bank_qualification_path'},'positive observer selection')
    for k in ('host_python','host_environment','native_public','native_private'):
        need(_s_equal(obs[k],execution[k]),'exact preselected observer '+k)
    exact(obs['central'],_S_CENTRAL_SELECTION_KEYS,'preselected central limits and capture clocks')
    for k in ('prepare_launcher','bank_launcher'):
        exact(obs[k],{'python','context','operation_live_bytes'},'preselected complete original launcher')
        canonical_path(obs[k]['python']);need(type(obs[k]['context']) is dict,'explicit complete launcher context')
    proof=_s_under(obs['execution_bank_qualification_path'],run['roots']['operator'])
    need(proof.suffix=='.json','preselected bank proof metadata slot')


def _s_packet_operand(run,packet):
    exact(packet,{'root','complete'},'only actual complete packet operands')
    need(packet['root']==run['roots']['packet'],'fixed selected packet root')
    exact(packet['complete'],{'path','pin'},'fixed actual packet completion')
    need(packet['complete']['path']=='COMPLETE.json','only actual fixed packet completion')
    _s_descriptor({'path':str(canonical_path(packet['root'])/'COMPLETE.json'),'pin':packet['complete']['pin']})


def _s_stable(run,kind,payload,allow_unresolved_bank=False):
    deferred={'prepare':set(),'bank':{'packet'},'execution':{'packet','bank'}}[kind]
    selected=run[{'prepare':'preparation_fields','bank':'bank_fields','execution':'execution_fields'}[kind]]
    need(_s_equal({k:v for k,v in payload.items() if k not in deferred},selected),
         'no drift from selected stable '+kind+' fields')
    if kind in ('bank','execution'):_s_packet_operand(run,payload['packet'])
    if kind=='execution':
        bank=payload['bank'];exact(bank,{'manifest','manifest_kernel','qualification'},'only named future bank operands')
        exact(bank['manifest'],{'path','pin'},'actual immutable STORE descriptor')
        need(bank['manifest']['path']=='STORE.json','fixed STORE metadata')
        _s_descriptor({'path':str(canonical_path(run['roots']['store'])/'STORE.json'),'pin':bank['manifest']['pin']})
        exact(bank['qualification'],{'path','pin'},'explicit fixed bank proof slot')
        if allow_unresolved_bank and bank['qualification']['pin'] is None:
            canonical_path(bank['qualification']['path'])
        else:_s_descriptor(bank['qualification'])
        need(bank['qualification']['path']==run['observer_selection']['execution_bank_qualification_path']
             and type(bank['manifest_kernel']) is dict and bank['manifest_kernel'],'preselected proof path and actual kernel metadata')


def _s_ready(run):
    need(not run['unresolved'],'dependent authentic fields unresolved; no binding')


def _s_evidence(io, rows, run):
    need(type(rows) is list and 1<=len(rows)<=32,'bounded nonempty independent metadata evidence')
    for d in rows:
        _s_read(io,d,run['roots']['operator'],cap=1048576)


def _s_original_evidence(io,rows,run):
    need(type(rows) is list and 1<=len(rows)<=32,'bounded original relative evidence set')
    for row in rows:
        exact(row,{'path','pin'},'original relative evidence descriptor')
        relative=relative_path(row['path'])
        _s_read(io,{'path':str(canonical_path(run['roots']['operator'])/relative),'pin':row['pin']},
                run['roots']['operator'],cap=1048576)


def _s_projection(kind, payload):
    proof='qualification' if kind=='bank' else 'qualifications'
    other='qualifications' if proof=='qualification' else 'qualification'
    need(type(payload) is dict and proof not in payload and other not in payload,'exact original proof omission; no singular/plural substitution')
    raw=encode(payload);need(raw.endswith(b'\n'),'new metadata encoding has exactly final newline')
    # Original prep.canonical/core.encoded selection predicates exclude that newline.
    return pin_bytes(raw[:-1])


def _s_prepare_fields(io, instance, run, payload, capsule):
    _s_stable(run,'prepare',payload)
    exact(payload,_S_PREP_FIELDS,'full preparation projection')
    c=capsule['prep_contracts']
    need(payload['schema']=='neural049_prepare_authority_v1' and payload['status']=='selected_qualified_prepare'
         and payload['module_D'] is ('D' in run['modules']),'planned original preparation values')
    need(payload['origin']==run['original_clock']['origin'] and payload['deadline']==run['original_clock']['readback_end'], 'preparation original clock')
    exact(payload['limits'],c.BASE_LIMITS|c.EXTRA_LIMITS,'complete original preparation caps')
    for x in payload['limits'].values():_s_pos(x)
    need(payload['limits']['files']==payload['limits']['output_files'],'original output-file cap alias')
    need(canonical_path(payload['output_root'])==canonical_path(run['roots']['packet']),'prepared complete packet destination')
    need(canonical_path(payload['metadata_root'])==instance['operator_metadata'],'original authority base is selected external P')
    paths=[payload['source_root'],payload['output_root'],payload['metadata_root'],*payload['protected_roots']]
    need(all(_s_disjoint(a,b) for i,a in enumerate(paths) for b in paths[i+1:]),'exact preparation disjoint roots')
    need(_s_disjoint(payload['source_root'],instance['root']),'RAW recording root is not code root')
    exact(payload['environment'],{'numpy','h5py','memory_profile'},'preparation environment')
    for k in ('source_closure','roster'):c.artifact(payload[k])
    c.artifact(payload['environment']['memory_profile'])
    for k in ('numpy','h5py'):need(type(payload['environment'][k]) is str and payload['environment'][k],'pinned preparation libraries')
    roster_pin={'bytes':15248,'sha256':'d40b7d1e197d30c8e895d35d86dd567e7927bb16e72a9e136ade168784b09a51'}
    need(payload['roster']['pin']==roster_pin,'exact original55 source roster')
    roster=_s_read(io,{'path':str(canonical_path(payload['metadata_root'])/c.relative(payload['roster']['path'])),'pin':roster_pin},payload['metadata_root'])
    need(roster.get('schema')=='neural049_held_roster_v1' and type(roster.get('sources')) is list and len(roster['sources'])==55,'complete roster metadata')
    sources=payload['sources'];need(type(sources) is list and len(sources)==55,'all55 source descriptors; no bodies read')
    for original,row in zip(roster['sources'],sources):
        exact(row,{'person','day','path','pin','geometry'},'source metadata fields')
        need((row['person'],row['day'],row['path'],row['pin'])==(original['person'],original['day'],original['source_path'],
             {'bytes':original['advertised_bytes'],'sha256':original['held_metadata_payload_sha256_not_reverified']}),'exact55 identity ordering')
        need(type(row['geometry']) is dict and row['geometry'].get('schema')==c.SCHEMA,'authentic selected schema declaration')
    need(set(payload['axes'])==set(capsule['contracts'].PEOPLE),'all12 channel unions')
    for person,axis in payload['axes'].items():
        need(type(axis) is list and 0<len(axis)<=payload['limits']['channels'] and len(axis)==len(set(axis)),'complete unique channel axis')
        for item in axis:c.opaque(item)
        union={item['axis_id'] for row in sources if row['person']==person for item in row['geometry']['channel_map']}
        need(union==set(axis),'complete authentic within-person channel union')


def _s_bank_fields(instance,run,payload):
    _s_stable(run,'bank',payload)
    exact(payload,_S_BANK_FIELDS,'full original bank projection')
    need(payload['schema']=='neural049_bank_build_authority_v1' and payload['active'] is True
         and payload['source_manifest']==instance['parent_source'] and payload['backend']=='linux-x86_64-fsverity-sha256-4096-v1'
         and payload['operator_identity']==run['operator_identity'],'actual source-bound planned bank')
    context=payload['context'];exact(context,{'origin','deadline','read_cap','write_cap'},'original bank context')
    need(context['origin']==run['original_clock']['origin'] and context['deadline']==run['original_clock']['readback_end'],'bank original clock')
    for k in ('read_cap','write_cap'):_s_pos(context[k])
    for k in ('evidence_cap','copy_bytes','kernel_read_per_file','kernel_write_per_file','array_cap','manifest_cap','kernel_read_manifest','kernel_write_manifest'):_s_pos(payload[k])
    mapping={'root':'store','packet_root':'packet','source_root':'source','output_root':'output','operator_root':'operator','secrets_root':'secrets'}
    for key,r in mapping.items():need(canonical_path(payload[key])==canonical_path(run['roots'][r]),'bank root correspondence')
    need(payload['packet']['root']==run['roots']['packet'],'bank complete packet identity')
    need(payload['preparation_context']['origin']==context['origin'] and payload['preparation_context']['deadline']==context['deadline'],'same original preparation subcontext')


def _s_execution_fields(instance,run,payload,allow_unresolved_bank=False):
    _s_stable(run,'execution',payload,allow_unresolved_bank)
    exact(payload,_S_EXEC_FIELDS,'complete original execution projection')
    need(payload['schema']=='neural049_execution_authority_v1' and payload['active'] is True
         and payload['task_id']==_S_TASK and payload['profile']==_S_PROFILE
         and payload['source_manifest']==instance['parent_source'],'original source execution schema')
    for key,expected in [('roots',run['roots']),('clock',run['original_clock']),('modules',run['modules']),('cache',run['cache']),('operator_identity',run['operator_identity'])]:
        need(_s_equal(payload[key],expected),'same run execution '+key)
    need(payload['grading']=={'selected':False},'no future completion/grade authority')


def _s_request(io,instance,d,kind):
    request=_s_read(io,d,instance['operator_metadata'])
    exact(request,{'schema','kind','run','source','payload','payload_pin'},'authority request schema')
    need(request['schema']=='neural049_portable_authority_request_v1' and request['kind']==kind
         and request['source']==instance['parent_source'],'same original authority request')
    need(request['payload_pin']==_s_projection(kind,request['payload']),'unmodified original selection projection')
    run=_s_run(io,instance,request['run']);_s_ready(run)
    return request,run


def _s_external_completion(io,instance,run,run_desc,descriptor_,kind):
    doc=_s_read(io,descriptor_,run['roots']['operator'])
    required={'schema','issuer','realm','instance','source_manifest','run','kind','result','natural_exit','exit_code',
              'streams_complete','capture_completed','provisional','original_origin','evidence'}
    exact(doc,required,'portable original-operation completion metadata')
    need(doc['schema']=='neural049_portable_external_operation_completion_v1' and doc['issuer']==run['operator_identity']
         and doc['realm']=='actual_original_tool_capture' and _s_equal(doc['instance'],instance['instance'])
         and doc['source_manifest']==instance['parent_source'] and doc['kind']==kind
         and _s_equal(doc['run'],run_desc)
         and doc['natural_exit'] is True and type(doc['exit_code']) is int and doc['exit_code']==0
         and doc['streams_complete'] is True and doc['capture_completed'] is True and doc['provisional'] is False
         and doc['original_origin']==run['original_clock']['origin'],'actual externally observed operation closure')
    _s_evidence(io,doc['evidence'],run)
    result_root=canonical_path(run['roots']['packet' if kind=='prepare' else 'store'])
    need(canonical_path(doc['result']['path'])==result_root/'COMPLETE.json','fixed original complete metadata path')
    result=_s_read(io,doc['result'],result_root)
    if kind=='prepare':
        need(result.get('schema')=='neural049_prepare_complete_v1' and result.get('status')=='complete_core_bank'
             and result.get('source_count')==55 and result.get('person_count')==12,'actual full preparation completion')
        if 'D' in run['modules']:need(result.get('assignment_status')=='complete','full selected assignment feasibility')
    else:
        need(result.get('schema')=='neural049_bank_build_result_v1' and result.get('status')=='complete'
             and result.get('source')==instance['parent_source'] and result.get('external_natural_closure_required') is True,
             'actual complete immutable bank metadata')
    return doc,result


def _s_execution_request_payload(io,instance,run,params,capsule,root,outputs):
    """Two explicit request passes; unresolved self-pin never enters a full request."""
    payload=params['payload']
    _s_execution_fields(instance,run,payload,allow_unresolved_bank=True)
    need(payload['bank']['qualification']['pin'] is None,'base-only explicit unresolved bank proof pin')
    pc,pr=_s_external_completion(io,instance,run,params['run'],params['preparation_completion'],'prepare')
    bc,br=_s_external_completion(io,instance,run,params['run'],params['bank_completion'],'bank')
    need(payload['packet']['complete']['pin']==pc['result']['pin'] and payload['bank']['manifest']==br['manifest']
         and payload['bank']['manifest_kernel']==br['manifest_kernel'],'actual complete packet/store before either execution request')
    selected=capsule['authority'].bank_selection_pin(payload,allow_unresolved=True)
    bank={k:v for k,v in payload['bank'].items() if k!='qualification'}
    proof=params['bank_qualification']
    if proof is None:
        outputs['bank_qualification_request']=_s_put(io,root,'BANK_QUALIFICATION_REQUEST.json',{
            'schema':'neural049_portable_bank_qualification_request_v1','run':params['run'],
            'source':instance['parent_source'],'base_payload':payload,'bank_selection':selected,
            'bank':bank,'proof_path':payload['bank']['qualification']['path'],
            'required_proof_schema':'neural049_bank_qualification_v2',
            'status':'bank_prequalification_only_not_executable','executable_authority':False,
            'general_qualification_requests_emitted':False})
        return None
    _s_descriptor(proof)
    need(proof['path']==payload['bank']['qualification']['path'],'exact preselected bank proof path')
    q=_s_read(io,proof,run['roots']['operator'],cap=1048576)
    flags={'natural_build_closure','kernel_enforcement','physical_namespace','individual_mount_custody','complete_packet_join'}
    exact(q,{'schema','qualified','realm','issuer','selection','bank','evidence'}|flags,'exact acyclic bank-consumption proof')
    need(q['schema']=='neural049_bank_qualification_v2' and q['qualified'] is True
         and q['realm']=='actual_external_evidence' and q['issuer']==run['operator_identity']
         and q['selection']==selected and _s_equal(q['bank'],bank) and all(q[k] is True for k in flags),
         'independent bank proof before full authority selection')
    _s_original_evidence(io,q['evidence'],run)
    complete={**payload,'bank':{**payload['bank'],'qualification':proof}}
    _s_execution_fields(instance,run,complete)
    need(capsule['authority'].bank_selection_pin(complete)==selected,'same acyclic domain after exact proof pin attachment')
    return complete


def _s_launcher(io,instance,run,kind,launcher,request_desc):
    need(_s_equal(launcher,run['observer_selection'][kind+'_launcher']),'exact preselected original launcher settings')
    exact(launcher,{'python','context','operation_live_bytes'},'explicit stage launcher selection')
    python=str(canonical_path(launcher['python']));context=launcher['context']
    exact(context,{'schema','operation','origin','deadline','source_read_cap','request_read_cap','outer_read_cap',
        'outer_write_cap','outer_live_cap','failure_write_reserve','operation_context'},'exact stage context')
    need(context['schema']=='neural049_portable_stage_context_v1' and context['operation']==kind
         and context['origin']==run['original_clock']['origin'] and context['deadline']==run['original_clock']['readback_end'],'original stage envelope')
    for k in ('source_read_cap','request_read_cap','outer_read_cap','outer_write_cap','outer_live_cap','failure_write_reserve'):_s_pos(context[k])
    op=context['operation_context']
    need(op['origin']==context['origin'] and op['deadline']==context['deadline'],'no child clock reset')
    if kind=='prepare':
        exact(op,{'origin','deadline','limits'},'preparation operation context')
        need(launcher['operation_live_bytes'] is None,'prepare live bound comes from original limits')
    else:
        exact(op,{'origin','deadline','read_cap','write_cap'},'bank operation context')
        _s_pos(launcher['operation_live_bytes'])
    _s_launch_bounds(instance,kind,launcher,request_desc)
    boot=instance['immutable']['parent/program/bootstrap.py'];source=instance['parent_source']
    argv=[python,'-I','-S','-B',str(instance['root']/'shared/stage_launcher.py'),'--operation',kind,
          '--parent-root',str(instance['parent']),'--source-bytes',str(source['bytes']),'--source-sha256',source['sha256'],
          '--bootstrap-bytes',str(boot['bytes']),'--bootstrap-sha256',boot['sha256'],'--request',request_desc['path'],
          '--request-bytes',str(request_desc['pin']['bytes']),'--request-sha256',request_desc['pin']['sha256'],
          '--context-json',encode(context).decode('ascii')]
    return {'schema':'neural049_portable_stage_command_v1','instance':instance['instance'],'operation':kind,
            'argv':argv,'cwd':str(instance['root']),'launcher':{'path':str(instance['root']/'shared/stage_launcher.py'),
            'pin':instance['immutable']['shared/stage_launcher.py']},'request':request_desc,'context':context,
            'status':'bound_external_launch_required','own_future_exit_not_self_certified':True}


def _s_launch_bounds(instance,kind,launcher,request_desc):
    """Same conservative source/request/child/stdout envelope as dormant launcher."""
    c=launcher['context'];op=c['operation_context'];sc=c['source_read_cap'];rc=c['request_read_cap']
    rows=instance['parent_manifest']['files'];source=instance['parent_source']
    boot=instance['immutable']['parent/program/bootstrap.py']
    need(len(rows)==70 and rows.get('program/bootstrap.py')==boot,'full source schedule and bootstrap join')
    exact_source_reads=boot['bytes']+2*source['bytes']+3+sum(v['bytes']+1 for v in rows.values())
    need(sc>=exact_source_reads and rc>=request_desc['pin']['bytes']+1,'complete prospective source/request captures')
    if kind=='prepare':
        limits=op['limits']
        exact(limits,{'read_bytes','write_bytes','array_bytes','metadata_bytes','files','array_elements','live_bytes',
                      'rows','channels','source_files','output_files'},'all original preparation limits')
        for v in limits.values():_s_pos(v)
        need(limits['files']==limits['output_files'],'original output count alias')
        r,w,live=limits['read_bytes'],limits['write_bytes'],limits['live_bytes']
        stdout=12*limits['metadata_bytes']+65536
    else:
        r,w,live=_s_pos(op['read_cap']),_s_pos(op['write_cap']),_s_pos(launcher['operation_live_bytes']);stdout=0
    paths=[str(instance['parent']/relative_path(n)) for n in rows]
    paths += [str(instance['parent']/'program/bootstrap.py'),str(instance['parent']/'RUNTIME_SOURCE_V3.json'),request_desc['path']]
    failure_floor=65536+12*sum(len(n)+32 for n in paths)
    need(c['failure_write_reserve']>=failure_floor,'full source and outer path accounting publication reserve')
    need(c['outer_read_cap']>=sc+rc+r,'whole source/request/child read allowance')
    need(c['outer_write_cap']>=c['failure_write_reserve']+w+16*stdout,'whole child and escaped stdout allowance')
    need(c['outer_live_cap']>=16*(sc+rc)+65536+live+80*stdout+4*c['failure_write_reserve'],
         'whole source/child/escaped-output declared live allowance')


def _s_exec_proofs(io,instance,run,payload,proofs,capsule):
    exact(proofs,set(capsule['contracts'].GATES),'all20 execution gate dispositions')
    selected=_s_projection('execution',payload);bound={}
    for kind in capsule['contracts'].GATES:
        optional=(kind=='tool_custody' and 'T1' not in run['modules']) or (kind=='assignment_feasibility' and 'D' not in run['modules']) or (kind=='reference_cache_custody' and not run['cache'])
        if optional:
            need(proofs[kind]=={'status':'not_selected'},'explicit unselected optional gate')
            bound[kind]=proofs[kind];continue
        d=proofs[kind];q=_s_read(io,d,run['roots']['operator'],cap=1048576)
        exact(q,{'schema','qualified','realm','issuer','kind','task_id','profile','selection','source_manifest','evidence'},'positive actual execution proof')
        need(q['schema']=='neural049_actual_qualification_v1' and q['qualified'] is True
             and q['realm']=='actual_external_evidence' and q['issuer']==run['operator_identity'] and q['kind']==kind
             and q['task_id']==_S_TASK and q['profile']==_S_PROFILE and q['selection']==selected
             and q['source_manifest']==instance['parent_source'],'exact independent execution proof')
        _s_original_evidence(io,q['evidence'],run)
        bound[kind]={'path':str(canonical_path(d['path']).relative_to(canonical_path(run['roots']['operator']))),'pin':d['pin']}
    a={**payload,'qualifications':bound}
    capsule['configuration'].validate(a,instance['parent_source']);io.tick();return a


def _s_authority(io,instance,run,d,capsule):
    a=_s_read(io,d,run['roots']['operator'])
    exact(a,_S_EXEC_FIELDS|{'qualifications'},'bound original execution authority')
    _s_execution_fields(instance,run,{k:v for k,v in a.items() if k!='qualifications'})
    capsule['configuration'].validate(a,instance['parent_source'])
    return a


def _s_request_body(io,instance,d):
    request=_s_read(io,d,instance['operator_metadata'],cap=131072)
    fields={'schema','task_id','profile','instance_declaration','central_source','parent_source','source_freeze','registry',
        'run','authority','operation','condition','program','output','review_slot','original_origin','parent_clock',
        'central_observation_deadline','central_validation_deadline','selected_modules','cache','limits','other_reserve_bytes'}
    exact(request,fields,'positive portable request')
    _s_require_portable_clocks(request)
    need(request['schema']=='neural049_portable_request_v1' and request['task_id']==_S_TASK and request['profile']==_S_PROFILE
         and _s_equal(request['instance_declaration'],instance['selection']) and request['central_source']==instance['central_source']
         and request['parent_source']==instance['parent_source'] and _s_equal(request['source_freeze'],instance['freeze'])
         and request['registry']==instance['registry_state']['current_registry'],'current exact instance/source/request generation')
    _s_under(request['review_slot'],instance['central']/'operator-selections',direct=True)
    need(_SPath(request['review_slot']).suffix=='.json','sealed named review slot')
    return request


def _s_request_approval(io,instance,run,request_desc,d):
    q=_s_read(io,d,run['roots']['operator'],cap=131072)
    exact(q,{'schema','issuer','realm','approved','instance','request','source_freeze','evidence'},'request approval fields')
    need(q['schema']=='neural049_portable_request_approval_v1' and q['issuer']==run['operator_identity']
         and q['realm']=='actual_external_evidence' and q['approved'] is True
         and _s_equal(q['instance'],instance['instance']) and _s_equal(q['request'],request_desc)
         and _s_equal(q['source_freeze'],instance['freeze']),'independent current request approval')
    _s_evidence(io,q['evidence'],run);return q


def _s_review_from_request(instance,request,a,pair):
    _s_require_portable_clocks(request)
    review={'schema':'neural049_portable_central_review_v1','task_id':_S_TASK,'selected':True,
        'operation':request['operation'],'panel':_S_PROFILE,'condition':request['condition'],
        'selected_modules':request['selected_modules'],'cache':request['cache'],'central_source':instance['central_source'],
        'parent_source':instance['parent_source'],'registry':request['registry'],'authority':request['authority'],
        'instance_request':pair,'instance_declaration':instance['selection'],'original_origin':request['original_origin'],
        'central_observation_deadline':request['central_observation_deadline'],
        'central_validation_deadline':request['central_validation_deadline'],'other_reserve_bytes':request['other_reserve_bytes'],
        'limits':request['limits'],'roots':a['roots'],'collection':None,'collection_completion':None,'grading_selection':None}
    return review


def _s_review(io,instance,d,capsule):
    need(canonical_path(d['path']).parent==instance['central']/'operator-selections','fixed final review namespace')
    review=_s_read(io,d,instance['central']/'operator-selections',cap=32768)
    exact(review,_S_REVIEW_FIELDS|{'qualification'},'exact portable final review')
    _s_require_portable_clocks(review)
    pair=review['instance_request'];exact(pair,{'request','approval'},'embedded request/approval pair; no seventh capture')
    request=_s_request_body(io,instance,pair['request']);run=_s_run(io,instance,request['run']);_s_ready(run)
    a=_s_authority(io,instance,run,request['authority'],capsule)
    _s_request_approval(io,instance,run,pair['request'],pair['approval'])
    expected=_s_review_from_request(instance,request,a,pair)
    for k in ('collection','collection_completion','grading_selection'):expected[k]=review[k]
    need(_s_equal({k:v for k,v in review.items() if k!='qualification'},expected)
         and request['review_slot']==d['path'],'review binds exact preceding request and immutable slot')
    _s_review_scope(io,instance,run,a,request,review)
    _s_central_proof(io,instance,run,review,review['qualification'])
    return review,request,run,a


def _s_review_scope(io,instance,run,a,request,review):
    _s_require_portable_clocks(request);_s_require_portable_clocks(review)
    need(_s_equal({k:request[k] for k in _S_CENTRAL_SELECTION_KEYS},
         _s_central_selection_projection(run['observer_selection']['central'])),'exact projected central resource/clock settings')
    need(request['operation'] in ('collect','grade') and request['condition'] in (None,_S_PROFILE)
         and request['original_origin']==_s_portable_clock(a['clock']['origin']) and _s_equal(request['parent_clock'],a['clock'])
         and _s_equal(request['selected_modules'],a['modules']) and request['cache'] is a['cache'],
         'request preserves exact parent operation/clock/modules/cache')
    need(a['clock']['readback_end']<_s_finite(request['central_observation_deadline'])
         <_s_finite(request['central_validation_deadline']), 'capture deadlines cannot extend parent work')
    output=canonical_path(request['output'])
    need(all(_s_disjoint(output,p) for p in [instance['root'],*a['roots'].values()]),'external central output')
    exact(request['limits'],_S_REVIEW_LIMITS,'central limit fields')
    for k,v in request['limits'].items():
        if k!='validation_numeric':_s_pos(v)
    exact(request['limits']['validation_numeric'],{'allocation_bytes','elements','serialized_bytes','files','work'},'validation resources')
    for v in request['limits']['validation_numeric'].values():_s_pos(v)
    _s_pos(request['other_reserve_bytes'],zero=True)
    if request['operation']=='collect':
        need(request['program']==request['authority']['path']
             and all(review[k] is None for k in ('collection','collection_completion','grading_selection')),
             'collection has no invented future grading completion')
    else:
        need(request['condition'] is None and request['program']==review['collection']['path'],'grade uses completed collection')
        doc,end=_s_collection(io,instance,run,a,request['authority'],review['collection'],review['collection_completion'])
        bundle={'collection':review['collection'],'completion':review['collection_completion'],
                'observation':doc['joined']['observation'],'nested_caller':doc['receipts']['CALLER.json']}
        late=_s_read(io,review['grading_selection'],run['roots']['operator'])
        _s_late_fields(instance,run,a,request['authority'],bundle,late)
        _s_late_proof(io,instance,run,a,bundle,late)


def _s_central_proof(io,instance,run,review,d):
    _s_require_portable_clocks(review)
    q=_s_read(io,d,run['roots']['operator'],cap=1048576)
    exact(q,{'schema','realm','qualified','issuer','task_id','central_source','parent_source','selection',
             'authority','original_origin','findings','evidence'},'central qualification schema')
    selected=pin_bytes(encode({k:v for k,v in review.items() if k not in ('qualification','grading_document')}))
    need(q['schema']=='neural049_actual_central_qualification_v1' and q['realm']=='actual_external_evidence'
         and q['qualified'] is True and q['issuer']==run['operator_identity'] and q['task_id']==_S_TASK
         and q['central_source']==instance['central_source'] and q['parent_source']==instance['parent_source']
         and q['selection']==selected and q['authority']==review['authority']['pin']
         and q['original_origin']==review['original_origin'],'exact actual central qualification')
    exact(q['findings'],_S_CENTRAL_FINDINGS,'all8 central findings')
    need(all(v is True for v in q['findings'].values()),'actual external central findings, never constructor-issued')
    _s_evidence(io,q['evidence'],run)


def _s_command(instance,request,a):
    key='grade' if request['operation']=='grade' else ('named' if request['condition']==_S_PROFILE else 'default')
    template=instance['selection_body']['registered_templates'][key]
    need(type(template) is list and template and all(type(x) is str for x in template),'registered literal argv')
    replacements={'{python}':a['host_python'],'{program}':request['program'],'{output}':request['output'],
                  '{review}':request['review_slot'],'{other_reserve_bytes}':str(request['other_reserve_bytes'])}
    argv=[replacements.get(x,x) for x in template]
    need(argv[0]==a['host_python'] and not any('{' in x or '}' in x for x in argv),'whole-token exact registered substitution')
    argv[1]=str(instance['root']/relative_path(template[1]))
    return argv


def _s_collection(io,instance,run,a,authority,collection,completion):
    path=canonical_path(collection['path']);need(path.name=='RESULT.json','original central RESULT only')
    need(_s_disjoint(path.parent,instance['root']) and all(_s_disjoint(path.parent,r) for r in a['roots'].values()),'central output outside source/every parent root')
    doc=_s_read(io,collection,cap=131072)
    need(doc.get('schema')=='neural049_central_result_v1' and doc.get('status')=='complete' and doc.get('operation')=='collect'
         and doc.get('panel')==_S_PROFILE and doc.get('central_source')==instance['central_source']
         and doc.get('parent_source')==instance['parent_source'] and doc.get('authority')==authority['pin']
         and doc.get('original_origin')==a['clock']['origin'] and doc.get('selected_modules')==a['modules']
         and doc.get('cache') is a['cache'] and doc.get('private_grading_performed') is False
         and doc.get('actual_parent_operation_observed') is True and doc.get('own_future_exit_not_self_certified') is True,'original complete collection is not its future-exit witness')
    end=_s_read(io,completion,run['roots']['operator'],cap=1048576)
    fields={'schema','realm','issuer','central_source','parent_source','authority','collection','review','provisional',
            'exit_code','natural_exit','streams_complete','observed_after_central_return','completed_at','argv','cwd','capture_artifacts'}
    exact(end,fields,'external original central completion')
    need(end['schema']=='neural049_external_central_completion_v1' and end['realm']=='actual_original_tool_capture'
         and end['issuer']==run['operator_identity'] and end['central_source']==instance['central_source']
         and end['parent_source']==instance['parent_source'] and end['authority']==authority['pin']
         and _s_equal(end['collection'],collection) and end['review']==doc['review']
         and end['provisional'] is False and type(end['exit_code']) is int and end['exit_code']==0
         and end['natural_exit'] is True and end['streams_complete'] is True and end['observed_after_central_return'] is True
         and _s_finite(doc['observed_end'])<=_s_finite(end['completed_at'])<run['original_clock']['readback_end']
         and end['completed_at']<=_s_time.monotonic(),
         'actual central wait/stream/chronology witness before original late-grade deadline')
    intent=_s_read(io,{'path':str(path.parent/'INTENT.json'),'pin':doc['receipts']['intent']},cap=131072)
    need(end['argv']==intent['central_argv'] and end['cwd']==str(instance['root'])
         and intent['review']==doc['review'] and intent['authority']==authority['pin'],'same original argv/cwd/review/authority')
    _s_evidence(io,end['capture_artifacts'],run);io.tick();return doc,end


def _s_late_fields(instance,run,a,authority,collection_bundle,payload):
    exact(payload,{'schema','active','issuer','selection','source_manifest','original_origin','observation','external_completion','output'},'original late-grading declaration fields')
    selected=_s_projection('execution',{k:v for k,v in a.items() if k!='qualifications'})
    need(payload['schema']=='neural049_late_grading_authority_v1' and payload['active'] is True
         and payload['issuer']==run['operator_identity'] and payload['selection']==selected
         and payload['source_manifest']==instance['parent_source'] and payload['original_origin']==a['clock']['origin']
         and payload['observation']==collection_bundle['observation'],'exact original late target-last declaration')
    need(canonical_path(payload['output']).parent==canonical_path(a['roots']['observation']),'fixed protected score output leaf')


def _s_late_proof(io,instance,run,a,bundle,payload):
    rel=payload['external_completion'];exact(rel,{'path','pin'},'original relative outer-completion proof')
    p=canonical_path(run['roots']['operator'])/relative_path(rel['path'])
    end=_s_read(io,{'path':str(p),'pin':rel['pin']},run['roots']['operator'],cap=1048576)
    need(end.get('schema')=='neural049_external_outer_completion_v1' and end.get('natural') is True
         and type(end.get('exit_code')) is int and end['exit_code']==0 and end.get('source_manifest')==instance['parent_source']
         and end.get('observation')==payload['observation'] and end.get('original_origin')==a['clock']['origin']
         and end.get('issuer')==run['operator_identity'] and end.get('streams_closed') is True
         and end.get('capture_completed') is True and end.get('provisional') is False
         and end.get('central_collection')==bundle['collection'] and end.get('central_external_completion')==bundle['completion']
         and end.get('nested_caller')==bundle['nested_caller'],'independent nested/original central outer completion join')
    _s_evidence(io,[{'path':str(canonical_path(run['roots']['operator'])/relative_path(d['path'])),'pin':d['pin']} for d in end['evidence']],run)


def assemble_stage(io, action, build_descriptor, input_descriptor):
    need(not hasattr(io,'_neural049_stage_retained'),'no nested stage retention scope')
    held=[];io._neural049_stage_retained=held
    try:return _s_assemble_stage(io,action,build_descriptor,input_descriptor)
    finally:
        for reservation in reversed(held):reservation.__exit__(None,None,None)
        del io._neural049_stage_retained


def _s_assemble_stage(io, action, build_descriptor, input_descriptor):
    """All14 finite metadata stages. No scientific producer or subprocess call."""
    need(action in _S_ACTIONS,'selected finite metadata action')
    inp=_s_read(io,input_descriptor)
    exact(inp,{'schema','action','registry_state','name','parameters'},'stage input wrapper')
    need(inp['schema']=='neural049_portable_stage_input_v1' and inp['action']==action,'explicit selected stage')
    name=inp['name'];need(type(name) is str and _s_re.fullmatch('[A-Za-z0-9_-]{1,64}',name),'fixed fresh stage token')
    params=inp['parameters'];exact(params,_S_ACTIONS[action],'positive action parameters')
    instance=load_instance(io,build_descriptor,inp['registry_state'])
    _s_under(input_descriptor['path'],instance['operator_metadata'])
    with _s_capsule(io,instance) as capsule:
        root=instance['operator_metadata']/(action+'--'+name)
        io.claim_root(root)
        outputs={};status='metadata_bound_external_execution_required'
        if action=='select-run':
            profile=_s_read(io,params['profile'],instance['operator_metadata'])
            fields=(_S_RUN_FIELDS-{'task_id','profile','instance','status'})
            exact(profile,fields,'exact source-only run profile')
            need(profile['schema']=='neural049_portable_run_profile_v1','run profile schema')
            run={**profile,'schema':'neural049_portable_run_selection_v1','task_id':_S_TASK,'profile':_S_PROFILE,
                 'instance':instance['instance'],'status':'selected_not_qualified'}
            outputs['run']=_s_put(io,root,'RUN.json',run)
            _s_run(io,instance,outputs['run']);status='selected_not_qualified'
        elif action in ('request-prepare','request-bank','request-execution'):
            kind=action[len('request-'):];run=_s_run(io,instance,params['run'])
            if run['unresolved']:
                outputs['plan']=_s_put(io,root,'PLAN.json',{'schema':'neural049_portable_unresolved_stage_plan_v1',
                    'action':action,'run':params['run'],'status':'selected_not_qualified','unresolved':run['unresolved'],
                    'no_authority_or_admissible_payload_pin':True})
            else:
                payload=params['payload']
                if kind=='prepare':_s_prepare_fields(io,instance,run,payload,capsule)
                elif kind=='bank':
                    _s_bank_fields(instance,run,payload)
                    completion,result=_s_external_completion(io,instance,run,params['run'],params['preparation_completion'],'prepare')
                    need(payload['packet']['complete']['pin']==completion['result']['pin'],'bank exact actual complete packet')
                else:payload=_s_execution_request_payload(io,instance,run,params,capsule,root,outputs)
                if payload is not None:
                    selected=_s_projection(kind,payload)
                    request={'schema':'neural049_portable_authority_request_v1','kind':kind,'run':params['run'],
                             'source':instance['parent_source'],'payload':payload,'payload_pin':selected}
                    outputs['request']=_s_put(io,root,'REQUEST.json',request)
                    kinds=capsule['prep_contracts'].QUALIFICATIONS if kind=='prepare' else capsule['contracts'].GATES if kind=='execution' else ('immutable_bank_build',)
                    rows=[]
                    for gate in kinds:
                        off=kind=='execution' and ((gate=='tool_custody' and 'T1' not in run['modules']) or
                            (gate=='assignment_feasibility' and 'D' not in run['modules']) or (gate=='reference_cache_custody' and not run['cache']))
                        rows.append({'kind':gate,'selection':selected,'source_manifest':instance['parent_source'],
                            'issuer':run['operator_identity'],'status':'not_selected' if off else 'external_actual_evidence_required'})
                    outputs['qualification_requests']=_s_put(io,root,'QUALIFICATION_REQUESTS.json',{'schema':'neural049_portable_qualification_requests_v1',
                        'request':outputs['request'],'requests':rows,'method_admissions':payload.get('method_admissions',{}),
                        'status':'selected_not_qualified','no_verdicts_generated':True})
            status='selected_not_qualified'
        elif action=='bind-prepare':
            request,run=_s_request(io,instance,params['request'],'prepare');a=request['payload']
            _s_prepare_fields(io,instance,run,a,capsule)
            qmap=params['qualifications'];exact(qmap,set(capsule['prep_contracts'].QUALIFICATIONS),'all10 original preparation proofs')
            bound={}
            for kind,d in qmap.items():
                q=_s_read(io,d,instance['operator_metadata'],cap=1048576)
                exact(q,{'schema','status','check','selection','independent_producer','evidence','external_completion'},'preparation proof schema')
                need(q['schema']=='neural049_independent_qualification_v1' and q['status']=='qualified'
                     and q['check']==kind and q['selection']==request['payload_pin']
                     and q['independent_producer']==run['operator_identity'],'same independently issued preparation selection')
                rows=[q['external_completion'],*q['evidence']]
                need(type(q['evidence']) is list and 1<=len(q['evidence'])<=32,'actual preparation evidence')
                for row in rows:
                    capsule['prep_contracts'].artifact(row)
                    _s_read(io,{'path':str(instance['operator_metadata']/row['path']),'pin':row['pin']},instance['operator_metadata'],cap=1048576)
                bound[kind]={'path':str(canonical_path(d['path']).relative_to(instance['operator_metadata'])),'pin':d['pin']}
            for key,d in [('source_closure',a['source_closure']),('memory_profile',a['environment']['memory_profile'])]:
                value=_s_read(io,{'path':str(instance['operator_metadata']/d['path']),'pin':d['pin']},instance['operator_metadata'])
                if key=='source_closure':need(value.get('schema')=='neural049_preparation_source_closure_v1' and value.get('files')
                    and _s_equal(value.get('environment'),a['environment']),'real preparation source/environment closure')
            authority={**a,'qualifications':bound}
            need(_s_projection('prepare',{k:v for k,v in authority.items() if k!='qualifications'})==request['payload_pin'],'unchanged prepare projection')
            # The ONLY extra selected P leaf; original authority bootstrap fixes its parent.
            outputs['authority']=io.put(instance['operator_metadata']/('prepare-authority-'+name+'.json'),authority,cap=_S_CAP)
            worker={'schema':'neural049_preparation_worker_request_v1','operation':'prepare',
                    'authority_path':outputs['authority']['path'],'authority_pin':outputs['authority']['pin']}
            need(_s_equal(params['launcher']['context']['operation_context'],{'origin':a['origin'],'deadline':a['deadline'],'limits':a['limits']}),'exact original preparation subcontext')
            outputs['worker_request']=_s_put(io,root,'WORKER_REQUEST.json',worker)
            outputs['command']=_s_put(io,root,'COMMAND.json',_s_launcher(io,instance,run,'prepare',params['launcher'],outputs['worker_request']))
        elif action=='bind-bank':
            request,run=_s_request(io,instance,params['request'],'bank');a=request['payload'];_s_bank_fields(instance,run,a)
            q=_s_read(io,params['qualification'],run['roots']['operator'],cap=1048576)
            flags={'backend','exclusive_namespace','source_completion','full_resource_plan','external_observer'}
            exact(q,{'qualified','realm','selection','source_manifest','issuer','evidence'}|flags,'original bank proof positive fields')
            need(q['qualified'] is True and q['realm']=='actual_external_evidence' and q['selection']==request['payload_pin']
                 and q['source_manifest']==instance['parent_source'] and q['issuer']==run['operator_identity']
                 and all(q[k] is True for k in flags),'actual independently issued bank proof')
            _s_evidence(io,q['evidence'],run)
            authority={**a,'qualification':params['qualification']}
            need(_s_projection('bank',{k:v for k,v in authority.items() if k!='qualification'})==request['payload_pin'],'unchanged bank projection')
            need(_s_equal(params['launcher']['context']['operation_context'],a['context']),'exact original bank context')
            outputs['authority']=_s_put(io,root,'AUTHORITY.json',authority)
            worker={'schema':'neural049_portable_bank_stage_request_v1','authority':outputs['authority'],
                    'source_manifest':instance['parent_source'],'operation_live_bytes':_s_pos(params['launcher']['operation_live_bytes'])}
            outputs['worker_request']=_s_put(io,root,'WORKER_REQUEST.json',worker)
            outputs['command']=_s_put(io,root,'COMMAND.json',_s_launcher(io,instance,run,'bank',params['launcher'],outputs['worker_request']))
        elif action=='bind-execution':
            request,run=_s_request(io,instance,params['request'],'execution');payload=request['payload']
            _s_execution_fields(instance,run,payload)
            authority=_s_exec_proofs(io,instance,run,payload,params['qualifications'],capsule)
            need(_s_projection('execution',{k:v for k,v in authority.items() if k!='qualifications'})==request['payload_pin'],'original execution projection unchanged')
            outputs['authority']=_s_put(io,root,'AUTHORITY.json',authority)
        elif action=='request-review':
            run=_s_run(io,instance,params['run']);_s_ready(run);a=_s_authority(io,instance,run,params['authority'],capsule)
            registry=io.json(instance['registry'],expected=instance['registry_state']['current_registry'],cap=131072,readonly=True)
            s=params['selection'];exact(s,{'operation','condition','output','review_slot','central_observation_deadline',
                 'central_validation_deadline','limits','other_reserve_bytes','collection','collection_completion','grading_selection'},'central selection fields')
            need(_s_equal(_s_central_selection_projection(s),_s_central_selection_projection(run['observer_selection']['central'])),'exact projected preselected central settings')
            need(s['operation'] in ('collect','grade') and s['condition'] in (None,_S_PROFILE),'registered operation/alias')
            _s_route_admission(io,instance,registry,s['operation'],s['condition'])
            if s['operation']=='collect':need(all(s[k] is None for k in ('collection','collection_completion','grading_selection')),'no future grade placeholders')
            else:
                need(s['condition'] is None,'grade default alias')
                doc,end=_s_collection(io,instance,run,a,params['authority'],s['collection'],s['collection_completion'])
                late=_s_read(io,s['grading_selection'],run['roots']['operator'])
                bundle={'collection':s['collection'],'completion':s['collection_completion'],'observation':doc['joined']['observation'],'nested_caller':doc['receipts']['CALLER.json']}
                _s_late_fields(instance,run,a,params['authority'],bundle,late);_s_late_proof(io,instance,run,a,bundle,late)
            output=canonical_path(s['output']);need(all(_s_disjoint(output,p) for p in [instance['root'],*a['roots'].values()]),'central output disjoint from every source/parent root')
            slot=_s_under(s['review_slot'],instance['central']/'operator-selections',direct=True)
            need(slot.suffix=='.json' and _s_re.fullmatch('[A-Za-z0-9_-]{1,64}',slot.stem) and not slot.exists(),'fresh named final review slot')
            exact(s['limits'],_S_REVIEW_LIMITS,'full central selected limits')
            for k,v in s['limits'].items():
                if k!='validation_numeric':_s_pos(v)
            exact(s['limits']['validation_numeric'],{'allocation_bytes','elements','serialized_bytes','files','work'},'full central public validation resources')
            for v in s['limits']['validation_numeric'].values():_s_pos(v)
            _s_pos(s['other_reserve_bytes'],zero=True)
            need(a['clock']['readback_end']<_s_finite(s['central_observation_deadline'])<_s_finite(s['central_validation_deadline']),'later capture bounds never extend parent grade')
            request={'schema':'neural049_portable_request_v1','task_id':_S_TASK,'profile':_S_PROFILE,'instance_declaration':instance['selection'],
                'central_source':instance['central_source'],'parent_source':instance['parent_source'],'source_freeze':instance['freeze'],
                'registry':instance['registry_state']['current_registry'],'run':params['run'],'authority':params['authority'],
                'operation':s['operation'],'condition':s['condition'],'program':params['authority']['path'] if s['operation']=='collect' else s['collection']['path'],
                'output':str(output),'review_slot':str(slot),'original_origin':a['clock']['origin'],'parent_clock':a['clock'],
                'central_observation_deadline':s['central_observation_deadline'],'central_validation_deadline':s['central_validation_deadline'],
                'selected_modules':a['modules'],'cache':a['cache'],'limits':s['limits'],'other_reserve_bytes':s['other_reserve_bytes']}
            request.update(_s_portable_clock_projection(request))
            outputs['request']=_s_put(io,root,'REQUEST.json',request,131072)
            review=_s_review_from_request(instance,request,a,None)
            for k in ('collection','collection_completion','grading_selection'):review[k]=s[k]
            outputs['review_plan']=_s_put(io,root,'REVIEW_PLAN.json',{'schema':'neural049_portable_review_plan_v1','request':outputs['request'],
                'review':review,'status':'selected_not_qualified','request_approval_and_central_qualification_absent':True})
            status='selected_not_qualified'
        elif action=='bind-request':
            request=_s_request_body(io,instance,params['request']);run=_s_run(io,instance,request['run']);_s_ready(run)
            _s_request_approval(io,instance,run,params['request'],params['approval'])
            bundle={'schema':'neural049_portable_request_bundle_v1','request':params['request'],'approval':params['approval']}
            outputs['request_bundle']=_s_put(io,root,'REQUEST_BUNDLE.json',bundle)
            outputs['qualification_next_step']=_s_put(io,root,'QUALIFICATION_NEXT_STEP.json',{'schema':'neural049_portable_review_qualification_next_step_v1',
                'request_bundle':outputs['request_bundle'],'required':'independently issue central qualification over the full review plan plus this pair, excluding qualification only',
                'no_qualification_verdict_generated':True})
        elif action=='bind-review':
            plan=_s_read(io,params['review_plan'],instance['operator_metadata'])
            exact(plan,{'schema','request','review','status','request_approval_and_central_qualification_absent'},'earlier review plan')
            need(plan['schema']=='neural049_portable_review_plan_v1' and plan['status']=='selected_not_qualified'
                 and plan['request_approval_and_central_qualification_absent'] is True,'unqualified earlier review projection')
            bundle=_s_read(io,params['request_bundle'],instance['operator_metadata']);exact(bundle,{'schema','request','approval'},'request bundle')
            need(bundle['schema']=='neural049_portable_request_bundle_v1' and _s_equal(bundle['request'],plan['request']),'same approved request')
            request=_s_request_body(io,instance,bundle['request']);run=_s_run(io,instance,request['run']);_s_ready(run)
            a=_s_authority(io,instance,run,request['authority'],capsule);_s_request_approval(io,instance,run,bundle['request'],bundle['approval'])
            pair={k:bundle[k] for k in ('request','approval')};review=_s_review_from_request(instance,request,a,pair)
            for k in ('collection','collection_completion','grading_selection'):review[k]=plan['review'][k]
            expected={**review,'instance_request':None};need(_s_equal(plan['review'],expected),'exact untouched earlier review plan')
            _s_review_scope(io,instance,run,a,request,review)
            _s_central_proof(io,instance,run,review,params['qualification']);review['qualification']=params['qualification']
            need(pin_bytes(encode(review))['bytes']<=32768,'original final review ceiling')
            outputs['review']=io.put(canonical_path(request['review_slot']),review,cap=32768)
            outputs['approval_request']=_s_put(io,root,'APPROVAL_REQUEST.json',{'schema':'neural049_portable_final_approval_request_v1',
                'instance':instance['instance'],'source_freeze':instance['freeze'],'review':outputs['review'],'request':bundle['request'],
                'registry':request['registry'],'actual_argv':_s_command(instance,request,a),'cwd':str(instance['root']),
                'environment_pin':pin_bytes(encode(a['host_environment'])),'status':'external_actual_approval_required'})
        elif action=='admit-approved-review':
            review,request,run,a=_s_review(io,instance,params['review'],capsule)
            expected_path=instance['central']/'operator-selections'/'APPROVAL_REGISTRY.json'
            need(canonical_path(params['approval_registry']['path'])==expected_path,'fixed independent final approval registry')
            q=_s_read(io,params['approval_registry'],instance['central']/'operator-selections',cap=131072)
            exact(q,{'schema','instance','issuer','source_freeze','entries','evidence_set'},'final review approvals')
            need(q['schema']=='neural049_portable_review_approvals_v1' and _s_equal(q['instance'],instance['instance'])
                 and q['issuer']==run['operator_identity'] and _s_equal(q['source_freeze'],instance['freeze']),'same actual external final approvals')
            _s_approval_entries(q['entries'])
            matches=[]
            for entry in q['entries']:
                exact(entry,{'review','request','registry','actual_argv','cwd','environment_pin','approved','evidence'},'positive final approval entry')
                if _s_equal(entry['review'],params['review']):matches.append(entry)
            need(len(matches)==1,'exactly one matching final review approval')
            entry=matches[0];argv=_s_command(instance,request,a)
            need(entry['approved'] is True and _s_equal(entry['request'],review['instance_request']['request'])
                 and entry['registry']==instance['registry_state']['current_registry'] and entry['actual_argv']==argv
                 and entry['cwd']==str(instance['root']) and entry['environment_pin']==pin_bytes(encode(a['host_environment'])),'exact original argv/cwd/environment/current-J approval')
            _s_evidence(io,entry['evidence'],run)
            evidence=_s_read(io,q['evidence_set'],run['roots']['operator'],cap=131072)
            exact(evidence,{'schema','instance','issuer','realm','approved_entries_pin','evidence','independent_producer'},'complete approval evidence set')
            need(evidence['schema']=='neural049_portable_approval_evidence_set_v1' and _s_equal(evidence['instance'],instance['instance'])
                 and evidence['issuer']==run['operator_identity'] and evidence['realm']=='actual_external_evidence'
                 and evidence['approved_entries_pin']==pin_bytes(encode(q['entries'])) and type(evidence['independent_producer']) is str
                 and evidence['independent_producer'],'exact full approved entry set binding')
            _s_evidence(io,evidence['evidence'],run)
            outputs['command']=_s_put(io,root,'COMMAND.json',{'schema':'neural049_portable_approved_command_v1','instance':instance['instance'],
                'review':params['review'],'approval_registry':params['approval_registry'],'argv':argv,'cwd':str(instance['root']),
                'environment':a['host_environment'],'environment_pin':entry['environment_pin'],'status':'external_launch_required',
                'own_future_exit_not_self_certified':True})
        elif action=='bind-collection-completion':
            run=_s_run(io,instance,params['run']);_s_ready(run);a=_s_authority(io,instance,run,params['authority'],capsule)
            doc,end=_s_collection(io,instance,run,a,params['authority'],params['collection'],params['completion'])
            outputs['collection_bundle']=_s_put(io,root,'COLLECTION_BUNDLE.json',{'schema':'neural049_portable_collection_completion_bundle_v1',
                'instance':instance['instance'],'run':params['run'],'authority':params['authority'],'collection':params['collection'],
                'completion':params['completion'],'observation':doc['joined']['observation'],'nested_caller':doc['receipts']['CALLER.json'],
                'original_origin':a['clock']['origin'],'observed_completion_at':end['completed_at'],'status':'external_original_completion_bound'})
        elif action in ('request-late-grade','bind-late-grade'):
            if action=='request-late-grade':
                run_desc=params['run'];authority_desc=params['authority'];bundle_desc=params['collection_bundle'];payload=params['payload']
            else:
                req=_s_read(io,params['request'],instance['operator_metadata'])
                exact(req,{'schema','run','authority','collection_bundle','payload','payload_pin','status'},'late-grade request')
                need(req['schema']=='neural049_portable_late_grade_request_v1' and req['status']=='external_actual_declaration_required'
                     and req['payload_pin']==pin_bytes(encode(req['payload'])),'unchanged late-grade request')
                run_desc=req['run'];authority_desc=req['authority'];bundle_desc=req['collection_bundle'];payload=req['payload']
            run=_s_run(io,instance,run_desc);_s_ready(run);a=_s_authority(io,instance,run,authority_desc,capsule)
            bundle=_s_read(io,bundle_desc,instance['operator_metadata'])
            exact(bundle,{'schema','instance','run','authority','collection','completion','observation','nested_caller','original_origin','observed_completion_at','status'},'completed collection bundle')
            need(bundle['schema']=='neural049_portable_collection_completion_bundle_v1' and _s_equal(bundle['instance'],instance['instance'])
                 and _s_equal(bundle['run'],run_desc) and _s_equal(bundle['authority'],authority_desc)
                 and bundle['status']=='external_original_completion_bound','same completed original collection')
            doc,end=_s_collection(io,instance,run,a,authority_desc,bundle['collection'],bundle['completion'])
            need(bundle['observation']==doc['joined']['observation'] and bundle['nested_caller']==doc['receipts']['CALLER.json'],'actual nested metadata unchanged')
            _s_late_fields(instance,run,a,authority_desc,bundle,payload)
            _s_late_proof(io,instance,run,a,bundle,payload)
            if action=='request-late-grade':
                outputs['request']=_s_put(io,root,'REQUEST.json',{'schema':'neural049_portable_late_grade_request_v1','run':run_desc,
                    'authority':authority_desc,'collection_bundle':bundle_desc,'payload':payload,'payload_pin':pin_bytes(encode(payload)),
                    'status':'external_actual_declaration_required'});status='selected_not_qualified'
            else:
                actual=_s_read(io,params['declaration'],run['roots']['operator'])
                need(_s_equal(actual,payload),'independently issued exact late declaration; no constructor verdict')
                outputs['declaration_bundle']=_s_put(io,root,'DECLARATION_BUNDLE.json',{'schema':'neural049_portable_late_grade_bundle_v1',
                    'request':params['request'],'declaration':params['declaration'],'collection_bundle':bundle_desc,
                    'status':'external_grade_review_request_required','protected_targets_read':False})
        else:raise Refusal('unimplemented stage')
        # No usable final result survives a current-J change during metadata assembly.
        io.read(instance['registry'],expected=instance['registry_state']['current_registry'],cap=131072,readonly=True)
        io.tick()
        result={'schema':'neural049_portable_stage_result_v1','action':action,'status':status,'instance':instance['instance'],
                'registry_state':instance['registry_state_descriptor'],'outputs':outputs,'costs':io.record(),'automatic_retry':False}
        result_desc=_s_put(io,root,'STAGE_RESULT.json',result)
        io.tick();return {'result':result_desc,'action':action,'status':status,'instance':instance['instance'],
                'registry_state':instance['registry_state_descriptor'],'outputs':outputs,'costs_after_result_publication':io.record()}

# Owner CLI fragment, concatenated after the three exact helper fragments.
import argparse
import sys
import time


_PORTABLE_STAGE_ACTIONS = (
    'select-run','request-prepare','bind-prepare','request-bank','bind-bank',
    'request-execution','bind-execution','request-review','bind-request','bind-review',
    'admit-approved-review','bind-collection-completion','request-late-grade','bind-late-grade')


def _cli_descriptor(args, name):
    return descriptor({'path':getattr(args,name),
                       'pin':{'bytes':getattr(args,name+'_bytes'),
                              'sha256':getattr(args,name+'_sha256')}})


def _cli_parser():
    parser = argparse.ArgumentParser(description='NEURAL049 portable metadata constructor; no scientific workers')
    subs = parser.add_subparsers(dest='action',required=True)
    for name in ('build','bind-route','activate-route',*_PORTABLE_STAGE_ACTIONS):
        p = subs.add_parser(name)
        p.add_argument('--origin-monotonic',type=float,required=name!='build')
        for flag in ('deadline-monotonic',):
            p.add_argument('--'+flag,type=float,required=True)
        for flag in ('read-cap-bytes','write-cap-bytes','live-cap-bytes'):
            p.add_argument('--'+flag,type=int,required=True)
        if name == 'build':
            names = ('release','profile')
            p.add_argument('--public-root',required=True)
            p.add_argument('--root',required=True)
        else:
            names = ('instance','input')
        for item in names:
            p.add_argument('--'+item,required=True)
            p.add_argument('--'+item+'-bytes',type=int,required=True)
            p.add_argument('--'+item+'-sha256',required=True)
    return parser


def _cli_bound(value, depth=0):
    need(depth <= 16, 'CLI envelope depth')
    if type(value) is dict:
        size = 2
        for key, item in value.items():
            need(type(key) is str, 'CLI envelope key')
            size += _cli_bound(key, depth+1) + 1 + _cli_bound(item, depth+1) + 1
            need(size <= 65535, 'CLI envelope bound')
        return size
    if type(value) in (list, tuple):
        size = 2
        for item in value:
            size += _cli_bound(item, depth+1) + 1
            need(size <= 65535, 'CLI envelope bound')
        return size
    if type(value) is str:
        need(len(value) <= 5461, 'CLI envelope string')
        return 2 + 12 * len(value)
    if value is None or type(value) is bool:
        return 5
    if type(value) is int:
        need(value.bit_length() <= 128, 'CLI integer extent')
        return 41
    if type(value) is float:
        return 32
    raise Refusal('CLI envelope primitive')


def _cli_emit(value):
    need(_cli_bound(value) + 1 <= 65536, 'CLI envelope bound')
    raw = encode(value)
    need(len(raw) <= 65536, 'CLI envelope encoded extent')
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def portable_cli_main(argv=None):
    io = None
    try:
        args = _cli_parser().parse_args(argv)
        origin = time.monotonic() if args.origin_monotonic is None else args.origin_monotonic
        io = IO({'origin':origin,'deadline':args.deadline_monotonic,
                 'read_cap':args.read_cap_bytes,'write_cap':args.write_cap_bytes,
                 'live_cap':args.live_cap_bytes})
        if args.action == 'build':
            result = build_instance(io,_cli_descriptor(args,'release'),
                                    canonical_path(args.public_root),canonical_path(args.root),
                                    _cli_descriptor(args,'profile'))
            # The complete immutable BUILD_RESULT is retained at its descriptor;
            # do not replicate its entire source inventory into a PIPE result.
            result = {k:v for k,v in result.items() if k != 'result'}
        elif args.action == 'bind-route':
            result = bind_route(io,_cli_descriptor(args,'instance'),_cli_descriptor(args,'input'))
        elif args.action == 'activate-route':
            result = activate_route(io,_cli_descriptor(args,'instance'),_cli_descriptor(args,'input'))
        else:
            result = assemble_stage(io,args.action,_cli_descriptor(args,'instance'),_cli_descriptor(args,'input'))
        io.close();io.tick()
        _cli_emit({'schema':'neural049_portable_constructor_cli_v1','status':'returned',
                   'action':args.action,'result':result,'costs':io.record(),
                   'automatic_retry':False,'own_future_exit_not_self_certified':True,
                   'scientific_operation_performed':False})
        io.tick()
        return 0
    except SystemExit:
        if io is not None:
            try:io.close()
            except BaseException:pass
        raise
    except BaseException as error:
        later = []
        failure = {'error_type':type(error).__name__,'message':str(error)[:1024],
                   'costs':None,'automatic_retry':False,'durability':'unknown'}
        if io is not None:
            try:
                failure = io.failure(error)
            except BaseException as cleanup:
                later.append({'error_type':type(cleanup).__name__,'failure_publication':'unknown'})
            try:
                io.close()
            except BaseException as cleanup:
                later.append({'error_type':type(cleanup).__name__,'ownership_descriptor_closure':'unknown_or_failed'})
            try:
                failure['costs'] = io.record()
            except BaseException as accounting:
                later.append({'error_type':type(accounting).__name__,'accounting':'unknown'})
        try:
            _cli_emit({'schema':'neural049_portable_constructor_cli_v1','status':'failed',
                       'error_type':type(error).__name__,'failure':failure,'later_errors':later,
                       'costs':failure.get('costs'),'automatic_retry':False,
                       'own_future_exit_not_self_certified':True})
        except BaseException as output_error:
            # The primary record remains with the owned failure handler when it
            # was durably published. A stream failure cannot become success.
            try:
                _cli_emit({'status':'failed','error_type':type(error).__name__,
                           'output_error_type':type(output_error).__name__,
                           'costs_unexported':True,'automatic_retry':False})
            except BaseException:
                pass
        return 1


if __name__ == '__main__':
    raise SystemExit(portable_cli_main())
