"""Descriptor-relative bounded storage with caller-owned ordered error custody."""
import os,stat,json,hashlib,time
from pathlib import PurePosixPath

def digest(b):return hashlib.sha256(b).hexdigest()
def encode(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def decode(b):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    depth=0;quoted=False;escape=False
    for c in b.decode('utf8'):
        if quoted:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in '[{':
            depth+=1
            if depth>64:raise ValueError('JSON depth')
        elif c in ']}':depth-=1
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite JSON')))

class ErrorOwner:
    """Original raw occurrences; a propagated escape is not another failure.

    A checkpoint covers only one delegated call. A later independent operation
    raising the identical exception object still creates a new occurrence.
    No exception attributes, formatting, hooks or cross-process reconstruction.
    """
    def __init__(self):self.events=[]
    def fail(self,where,error):self.events.append({'where':where,'error':error})
    def call(self,where,callback):
        start=len(self.events)
        try:return callback()
        except BaseException as error:
            if not any(row['error']is error for row in self.events[start:]):
                self.fail(where,error)
            raise
    def cleanup(self,where,callback):
        try:self.call(where,callback)
        except BaseException:pass
    def finish(self,start=0):
        if len(self.events)>start:raise self.events[start]['error']

def parts(name):
    if type(name)is not str or not name or '\x00'in name or '\\'in name:raise ValueError('path')
    p=PurePosixPath(name)
    if p.is_absolute()or any(x in ('','.','..')for x in name.split('/')):raise ValueError('canonical relative path')
    return p.parts

class Ledger:
    """Independent selected hard I/O/metadata limits; pre-effect reservations."""
    def __init__(self,limits):
        required={'read_bytes','write_bytes','files','decoded_bytes','metadata_bytes'}
        if set(limits)!=required or any(type(v)is not int or v<=0 for v in limits.values()):raise ValueError('complete independently selected ledger limits')
        self.limits=dict(limits);self.used=dict.fromkeys(required,0);self.started=time.monotonic_ns()
    def take(self,kind,n):
        if type(n)is not int or n<0 or self.used[kind]+n>self.limits[kind]:raise RuntimeError('resource reservation refused: '+kind)
        self.used[kind]+=n

def identity(s):return(s.st_dev,s.st_ino,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)

def seal_readonly_tree(path):
    for root,dirs,files in os.walk(path,topdown=False,followlinks=False):
        for name in dirs+files:
            p=os.path.join(root,name);s=os.lstat(p)
            if stat.S_ISLNK(s.st_mode):raise ValueError('view link')
            os.chmod(p,0o555 if stat.S_ISDIR(s.st_mode)else 0o444,follow_symlinks=False)
        os.chmod(root,0o555,follow_symlinks=False)

class Store:
    def __init__(self,path,ledger,writable=False,errors=None):
        self.errors=ErrorOwner()if errors is None else errors
        if type(self.errors)is not ErrorOwner:raise TypeError('original ordinary ErrorOwner required')
        self.fd=None;self.closed=True;self.ledger=ledger;self.writable=writable
        start=len(self.errors.events);owned=[]
        def body():
            self.path=os.path.abspath(path)
            fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY);owned.append(fd)
            for component in parts(self.path[1:]):
                nxt=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                owned.append(nxt) # successor owned BEFORE previous retirement
                owned.remove(fd) # one close attempt; never retry an ambiguous FD
                self.errors.call('store_ancestor_close',lambda:os.close(fd))
                fd=nxt
            self.fd=fd;owned.remove(fd);self.closed=False
        try:self.errors.call('store_acquire',body)
        except BaseException:pass
        finally:
            while owned:
                fd=owned.pop()
                self.errors.cleanup('store_acquire_retirement',lambda fd=fd:os.close(fd))
        self.errors.finish(start)
    def _parent(self,name,create=False):
        start=len(self.errors.events);owned=[];result=None
        def body():
            nonlocal result
            if self.closed or self.fd is None:raise RuntimeError('closed original Store')
            xs=parts(name);fd=os.dup(self.fd);owned.append(fd)
            for x in xs[:-1]:
                if create:
                    try:os.mkdir(x,0o700,dir_fd=fd)
                    except FileExistsError:pass
                nxt=os.open(x,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                owned.append(nxt);owned.remove(fd)
                self.errors.call('store_parent_ancestor_close',lambda:os.close(fd))
                fd=nxt
            owned.remove(fd);result=(fd,xs[-1])
        try:self.errors.call('store_parent_acquire',body)
        except BaseException:pass
        finally:
            while owned:
                fd=owned.pop()
                self.errors.cleanup('store_parent_acquire_retirement',lambda fd=fd:os.close(fd))
        self.errors.finish(start);return result
    def read(self,name,pin,cap):
        start=len(self.errors.events);d=f=None;b=None
        def body():
            nonlocal d,f,b
            if set(pin)!={'bytes','sha256'}or type(pin['bytes'])is not int or not 0<=pin['bytes']<=cap:raise ValueError('exact admitted read pin/extent')
            self.ledger.take('files',1);self.ledger.take('read_bytes',pin['bytes'])
            d,n=self._parent(name)
            f=os.open(n,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=d);a=os.fstat(f)
            if not stat.S_ISREG(a.st_mode)or a.st_nlink!=1 or a.st_size!=pin['bytes']:raise ValueError('single regular exact extent')
            chunks=[];remaining=a.st_size
            while remaining:
                c=os.read(f,min(remaining,65536))
                if not c:raise EOFError('short capture')
                chunks.append(c);remaining-=len(c)
            b=b''.join(chunks)
            if identity(a)!=identity(os.fstat(f))or digest(b)!=pin['sha256']:raise ValueError('changed or unbound capture')
        try:self.errors.call('store_read',body)
        except BaseException:pass
        finally:
            if f is not None:
                fd=f;f=None;self.errors.cleanup('store_read_file_close',lambda fd=fd:os.close(fd))
            if d is not None:
                fd=d;d=None;self.errors.cleanup('store_read_parent_close',lambda fd=fd:os.close(fd))
        self.errors.finish(start);return b
    def capture_untrusted(self,name,cap):
        # Only after original worker stop. Worker hashes never grant identity.
        start=len(self.errors.events);d=f=None;b=None
        def body():
            nonlocal d,f,b
            self.ledger.take('files',1);d,n=self._parent(name)
            f=os.open(n,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=d);a=os.fstat(f)
            if not stat.S_ISREG(a.st_mode)or a.st_nlink!=1 or not 0<=a.st_size<=cap:raise ValueError('bounded untrusted regular output')
            self.ledger.take('read_bytes',a.st_size);chunks=[];left=a.st_size
            while left:
                c=os.read(f,min(left,65536))
                if not c:raise EOFError('short worker output')
                chunks.append(c);left-=len(c)
            if identity(a)!=identity(os.fstat(f)):raise ValueError('output changed after stop')
            b=b''.join(chunks)
        try:self.errors.call('store_capture_untrusted',body)
        except BaseException:pass
        finally:
            if f is not None:
                fd=f;f=None;self.errors.cleanup('store_capture_file_close',lambda fd=fd:os.close(fd))
            if d is not None:
                fd=d;d=None;self.errors.cleanup('store_capture_parent_close',lambda fd=fd:os.close(fd))
        self.errors.finish(start);return b
    def put(self,name,b):
        start=len(self.errors.events);d=f=None
        def body():
            nonlocal d,f
            if not self.writable or type(b)is not bytes:raise TypeError('owned bytes only')
            self.ledger.take('files',1);self.ledger.take('write_bytes',len(b));d,n=self._parent(name,True)
            f=os.open(n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
            pos=0
            while pos<len(b):
                wrote=os.write(f,b[pos:])
                if wrote<=0:raise OSError('publication write made no progress')
                pos+=wrote
            os.fsync(f);os.fchmod(f,0o444);os.fsync(d)
        try:self.errors.call('store_put',body)
        except BaseException:pass
        finally:
            if f is not None:
                fd=f;f=None;self.errors.cleanup('store_put_file_close',lambda fd=fd:os.close(fd))
            if d is not None:
                fd=d;d=None;self.errors.cleanup('store_put_parent_close',lambda fd=fd:os.close(fd))
        self.errors.finish(start)
        p={'bytes':len(b),'sha256':digest(b)}
        def readback():
            if self.read(name,p,len(b))!=b:raise ValueError('publication readback')
        self.errors.call('store_put_readback',readback)
        return p
    def json(self,name,pin,cap):
        def body():
            self.ledger.take('metadata_bytes',pin['bytes']);return decode(self.read(name,pin,cap))
        return self.errors.call('store_json',body)
    def close(self):
        if self.closed:return
        fd=self.fd;self.fd=None;self.closed=True
        # Claim of attempted retirement only if close raises; never retry an
        # FD that the OS may already have closed and another actor may reuse.
        self.errors.call('store_close',lambda:os.close(fd))
