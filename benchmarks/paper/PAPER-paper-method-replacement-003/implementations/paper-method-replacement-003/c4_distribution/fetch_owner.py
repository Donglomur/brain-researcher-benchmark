"""One owned source-fetch process; no original imports or publication in the child.

The parent deadline starts once OS process creation returns an owned PID. The
child cannot access the network before the parent's GO message. Process creation
itself is not claimed interruptible. All bootstrap/GO/fetch/EOF/reap observation
shares one deadline; bounded error retirement has its separate fixed grace.
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import struct
import subprocess
import sys
import time

from .io_core import SourceError, OwnedFD, _raise_with_close, capture_path, strict_json

FETCH_SECONDS = 120.0
TERM_GRACE = 0.25
KILL_GRACE = 1.0
MAX_BUNDLE = 2097152
MAX_ERROR = 65536
MODULES = (('c4_distribution', '__init__.py'),
           ('c4_distribution.io_core', 'io_core.py'),
           ('c4_distribution.dependencies', 'dependencies.py'),
           ('c4_distribution.fetch_owner', 'fetch_owner.py'))

# This exact literal is passed as argv, not loaded from an ambient helper path.
# The child compiles only the four transferred current owned helper bodies.
_BOOTSTRAP = r'''
import base64, hashlib, json, os, struct, sys, types
def exact(n):
    out=bytearray()
    while len(out)<n:
        b=os.read(0,min(65536,n-len(out)))
        if not b:raise RuntimeError('incomplete captured helper bundle')
        out.extend(b)
    return bytes(out)
n=struct.unpack('!I',exact(4))[0]
if not 0<n<=2097152:raise RuntimeError('helper bundle extent')
bundle=json.loads(exact(n))
expected=[('c4_distribution','__init__.py'),('c4_distribution.io_core','io_core.py'),('c4_distribution.dependencies','dependencies.py'),('c4_distribution.fetch_owner','fetch_owner.py')]
if set(bundle)!={'modules','manifest'} or len(bundle['modules'])!=4:raise RuntimeError('helper bundle roster')
if any(n=='c4_distribution' or n.startswith('c4_distribution.') for n in sys.modules):raise RuntimeError('foreign helper preload')
identities=[];total=0
for row,(name,filename) in zip(bundle['modules'],expected):
    if set(row)!={'name','filename','body'} or row['name']!=name or row['filename']!=filename:raise RuntimeError('helper bundle identity')
    raw=base64.b64decode(row['body'],validate=True);total+=len(raw)
    if len(raw)>1048576 or total>1048576 or b'\0' in raw:raise RuntimeError('helper source extent')
    raw.decode('utf-8')
    module=types.ModuleType(name);module.__file__='<captured-c4-source>/'+filename
    module.__package__='c4_distribution';module.__cached__=None
    if name=='c4_distribution':module.__path__=[]
    sys.modules[name]=module
    exec(compile(raw,module.__file__,'exec',dont_inherit=True,optimize=0),module.__dict__)
    if name!='c4_distribution':setattr(sys.modules['c4_distribution'],name.rsplit('.',1)[1],module)
    identities.append({'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
manifest=base64.b64decode(bundle['manifest'],validate=True)
if len(manifest)>1048576:raise RuntimeError('fixed manifest extent')
sys.modules['c4_distribution.fetch_owner']._child_main(manifest,identities)
'''

class FetchFailure(SourceError):
    """Transported failure metadata, never an invented in-process raw exception."""

def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()

def _frame(kind, body):
    if type(body) is not bytes or len(kind)!=1 or len(body)>1048576:
        raise SourceError('bounded fetch frame')
    return kind+struct.pack('!I',len(body))+body

def _child_write(kind, body):
    raw=memoryview(_frame(kind,body))
    while raw:
        n=os.write(1,raw)
        if n<=0:raise SourceError('fetch child output write failed')
        raw=raw[n:]

def _child_read(n):
    raw=bytearray()
    while len(raw)<n:
        chunk=os.read(0,n-len(raw))
        if not chunk:raise SourceError('fetch GO missing')
        raw.extend(chunk)
    return bytes(raw)

def _remote_error(exc, depth=0):
    # No raw HTTP/source body, exception args or resource objects are serialized.
    text=str(exc)
    result={'type':type(exc).__module__+'.'+type(exc).__qualname__,
            'message':text[:4096], 'message_truncated':len(text)>4096}
    if getattr(exc,'c4_close_owner',None) is not None:result['close_state']='uncertain; child resource owner existed'
    if depth>=8:
        result['cause_depth_truncated']=True
    elif isinstance(exc,BaseExceptionGroup):
        result['exceptions']=[_remote_error(e,depth+1)for e in exc.exceptions[:16]]
        result['exceptions_truncated']=len(exc.exceptions)>16
    elif exc.__cause__ is not None:result['cause']=_remote_error(exc.__cause__,depth+1)
    return result

def _child_main(manifest, identities):
    from . import dependencies as dep
    try:
        spec=dep._specification_bytes(manifest)
        _child_write(b'R',_json({'modules':identities,'manifest_sha256':hashlib.sha256(manifest).hexdigest()}))
        length=struct.unpack('!I',_child_read(4))[0]
        if not 0<length<=256:raise SourceError('bounded single GO required')
        go=strict_json(_child_read(length))
        if set(go)!={'deadline'} or type(go['deadline'])is not float or not math.isfinite(go['deadline']):
            raise SourceError('finite fetch deadline required')
        deadline=go['deadline']
        if not time.monotonic()<deadline<=time.monotonic()+FETCH_SECONDS:
            raise SourceError('expired or renewed fetch deadline')
        opener=dep.urllib.request.build_opener(dep.urllib.request.ProxyHandler({}),dep._NoRedirect())
        for row in spec['files']:
            body=dep._fetch(row,opener,deadline)
            if time.monotonic()>=deadline:raise SourceError('fetch deadline after complete member')
            _child_write(b'B',body)
        if time.monotonic()>=deadline:raise SourceError('fetch deadline before terminal record')
        _child_write(b'D',_json({'files':len(spec['files']),'bytes':spec['total_bytes']}))
    except BaseException as exc:
        try:
            raw=_json(_remote_error(exc))
            if len(raw)>MAX_ERROR:raw=_json({'type':'bounded_remote_error','detail_truncated':True})
            _child_write(b'E',raw)
        except BaseException:
            os._exit(4)
        os._exit(3)
    os._exit(0)

class _Owner:
    def __init__(self):
        self.proc=None;self.launch_attempted=False;self.fds=[];self.selector=None
        self.stdout_prefix=bytearray();self.stderr_prefix=bytearray();self.files=[]
        self.pending=bytearray();self.frames=[];self.eof=set();self.deadline=None
        self.retirement='not_started';self.signal_attempts=[];self.wait_observations=[]
        self.remote_failure=None;self.closed=False
    def own(self, fd):
        owner=OwnedFD(fd);self.fds.append(owner);return owner
    def _check_deadline(self):
        if time.monotonic()>=self.deadline:raise SourceError('owned full source-fetch deadline exhausted')
    def _poll(self):
        value=self.proc.poll();self.wait_observations.append(value)
        return value
    def _wait_until(self, deadline):
        while True:
            value=self._poll()
            if value is not None:return value
            remaining=deadline-time.monotonic()
            if remaining<=0:return None
            time.sleep(min(0.01,remaining))
    def _group_absent(self):
        try:os.killpg(self.proc.pid,0)
        except ProcessLookupError:return True
        return False
    def retire(self):
        errors=[]
        if self.proc is None:
            self.retirement='launch_cleanup_unknown'if self.launch_attempted else'not_started'
            return errors
        try:
            status=self._poll()
        except BaseException as exc:
            errors.append(exc);status=None
        try:
            absent=status is not None and self._group_absent()
        except BaseException as exc:
            errors.append(exc);absent=False
        # A reaped leader is not proof that its owned session group is empty.
        # Retire a remaining observed group under the same bounded graces.
        if not absent:
            for sig,grace in [(signal.SIGTERM,TERM_GRACE),(signal.SIGKILL,KILL_GRACE)]:
                self.signal_attempts.append(int(sig))
                try:os.killpg(self.proc.pid,sig)
                except ProcessLookupError:pass
                except BaseException as exc:errors.append(exc)
                until=time.monotonic()+grace
                try:
                    while True:
                        status=self._poll()
                        absent=status is not None and self._group_absent()
                        if absent or time.monotonic()>=until:break
                        time.sleep(min(0.01,max(0,until-time.monotonic())))
                except BaseException as exc:
                    errors.append(exc);absent=False
                if absent:break
        try:
            absent=status is not None and self._group_absent()
        except BaseException as exc:
            errors.append(exc);absent=False
        self.retirement='observed_reaped_and_group_absent'if absent else'unknown'
        if not absent:
            errors.append(SourceError('fetch retirement unknown after bounded signal/reap attempts'))
        return errors
    def close(self):
        if self.closed:return []
        self.closed=True;errors=[]
        if self.selector is not None:
            try:self.selector.close()
            except BaseException as exc:
                exc.c4_close_owner=self;errors.append(exc)
        for owner in reversed(self.fds):
            if owner.fd is None or owner.close_attempted:continue
            try:owner.close()
            except BaseException as exc:errors.append(exc)
        return errors
    def pump(self, outgoing=None):
        self._check_deadline()
        view=memoryview(outgoing)if outgoing is not None else None
        if view is not None:self.selector.register(self.input.fd,selectors.EVENT_WRITE,'stdin')
        try:
            while True:
                self._check_deadline()
                ready=self.selector.select(min(0.05,max(0,self.deadline-time.monotonic())))
                self._check_deadline()
                for key,_ in ready:
                    if key.data=='stdin':
                        try:n=os.write(key.fd,view[:65536])
                        except BlockingIOError:continue
                        if n<=0:raise SourceError('fetch bootstrap/GO write failed')
                        view=view[n:]
                        if not view:
                            self.selector.unregister(key.fd);return
                    else:
                        try:b=os.read(key.fd,65536)
                        except BlockingIOError:continue
                        self._check_deadline()
                        if not b:
                            self.eof.add(key.data);self.selector.unregister(key.fd)
                        elif key.data=='stderr':
                            self.stderr_prefix.extend(b[:MAX_ERROR+1-len(self.stderr_prefix)])
                            if len(self.stderr_prefix)>MAX_ERROR:raise SourceError('fetch child stderr bound exceeded')
                        else:
                            self.stdout_prefix.extend(b[:self.stdout_cap+1-len(self.stdout_prefix)])
                            if len(self.stdout_prefix)>self.stdout_cap:raise SourceError('fetch child stdout bound exceeded')
                            self.pending.extend(b)
                            while len(self.pending)>=5:
                                kind=self.pending[:1];size=struct.unpack('!I',self.pending[1:5])[0]
                                if kind not in (b'R',b'B',b'D',b'E')or size>1048576:
                                    raise SourceError('fetch output frame refused')
                                if len(self.pending)<5+size:break
                                self.frames.append((bytes(kind),bytes(self.pending[5:5+size])))
                                del self.pending[:5+size]
                                if len(self.frames)>2052:raise SourceError('fetch frame-count bound exceeded')
                if view is None and(self.frames or self.eof):return
                if self._poll() is not None and not ready and 'stdout'in self.eof:return
        finally:
            if view is not None and len(view):
                try:self.selector.unregister(self.input.fd)
                except KeyError:pass
    def next_frame(self):
        while not self.frames:
            if 'stdout'in self.eof:raise SourceError('fetch child exited without complete protocol')
            self.pump()
        return self.frames.pop(0)

def _capture_bundle(spec):
    from . import dependencies as dep
    package=Path(__file__).absolute().parent
    manifest=capture_path(package.parent/'REQUIRED_ORIGINAL_SOURCE.json',dep.MANIFEST_BYTES)
    if dep._specification_bytes(manifest)!=spec:raise SourceError('caller differs from exact fixed source manifest')
    rows=[];identities=[];total=0
    for name,filename in MODULES:
        raw=capture_path(package/filename,1048576);total+=len(raw)
        if total>1048576 or b'\0'in raw:raise SourceError('bounded captured helper closure')
        raw.decode('utf-8')
        rows.append({'name':name,'filename':filename,'body':base64.b64encode(raw).decode('ascii')})
        identities.append({'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    bundle=_json({'modules':rows,'manifest':base64.b64encode(manifest).decode('ascii')})
    if len(bundle)>MAX_BUNDLE:raise SourceError('captured helper envelope bound')
    return bundle,{'modules':identities,'manifest_sha256':hashlib.sha256(manifest).hexdigest()}

def _run_owned(bundle, expected_ready, spec):
    from . import dependencies as dep
    owner=_Owner();primary=None;secondary=[];answer=None
    try:
        if os.name!='posix':raise SourceError('owned fetch process requires POSIX pipes/process group')
        # No arbitrary source/URL/command selection enters this process API.
        child_in,owner_in=[owner.own(fd)for fd in os.pipe()]
        owner_out,child_out=[owner.own(fd)for fd in os.pipe()]
        owner_err,child_err=[owner.own(fd)for fd in os.pipe()]
        owner.launch_attempted=True
        owner.proc=subprocess.Popen([sys.executable,'-I','-S','-B','-c',_BOOTSTRAP],
            stdin=child_in.fd,stdout=child_out.fd,stderr=child_err.fd,
            close_fds=True,start_new_session=True,env={'LC_ALL':'C','LANG':'C'})
        owner.deadline=time.monotonic()+FETCH_SECONDS
        owner.retirement='live_owned_child'
        for fd in (child_in,child_out,child_err):fd.close()
        owner.input=owner_in;owner.stdout_cap=spec['total_bytes']+3*MAX_ERROR+5*(len(spec['files'])+3)
        owner.selector=selectors.DefaultSelector()
        for fd,label in [(owner_out,'stdout'),(owner_err,'stderr')]:
            os.set_blocking(fd.fd,False);owner.selector.register(fd.fd,selectors.EVENT_READ,label)
        os.set_blocking(owner_in.fd,False)
        owner.pump(struct.pack('!I',len(bundle))+bundle)
        kind,body=owner.next_frame()
        if kind!=b'R'or len(body)>MAX_ERROR or strict_json(body)!=expected_ready:
            raise SourceError('child did not execute the captured complete helper closure')
        go=_json({'deadline':float(owner.deadline)})
        owner.pump(struct.pack('!I',len(go))+go)
        for row in spec['files']:
            kind,body=owner.next_frame()
            if kind==b'E':
                owner.remote_failure=strict_json(body);raise FetchFailure('source-fetch child reported an error; exact bounded metadata retained on owner')
            if kind!=b'B':raise SourceError('incomplete or reordered whole source collection')
            owner.files.append((row['path'],dep._verified_body(row,body)))
        kind,body=owner.next_frame()
        if kind==b'E':
            owner.remote_failure=strict_json(body);raise FetchFailure('source-fetch child reported a final error')
        if kind!=b'D'or strict_json(body)!={'files':len(spec['files']),'bytes':spec['total_bytes']}:
            raise SourceError('complete fixed-source terminal record missing')
        while owner.eof!={'stdout','stderr'}:
            owner.pump()
            if owner.frames:raise SourceError('extra fetch output after terminal record')
        owner._check_deadline()
        if owner.pending:raise SourceError('partial trailing fetch frame')
        status=owner._wait_until(owner.deadline)
        owner._check_deadline()
        if status!=0:raise SourceError('fetch child did not retire successfully')
        if not owner._group_absent():raise SourceError('fetch group remains after leader exit; retirement unknown')
        owner.retirement='observed_reaped_and_group_absent'
        answer=owner.files
    except BaseException as exc:
        primary=exc;secondary.extend(owner.retire())
    secondary.extend(owner.close())
    if primary is not None or secondary:
        if primary is not None:primary.c4_fetch_owner=owner
        for exc in secondary:exc.c4_fetch_owner=owner
        try:_raise_with_close(primary,secondary)
        except BaseException as exc:
            exc.c4_fetch_owner=owner
            exc.add_note('Fetch source prefix retained in owner, never published; retirement='+owner.retirement)
            raise
    return answer

def fetch_sources(spec):
    """Fetch all fixed originals once; return only after complete verified retirement."""
    bundle,ready=_capture_bundle(spec)
    return _run_owned(bundle,ready,spec)
