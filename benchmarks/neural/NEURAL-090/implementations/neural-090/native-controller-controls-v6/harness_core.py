"""Whole captured source and finite invented fixtures; no native/scientific effects."""
import contextlib, gc, hashlib, importlib, importlib.abc, importlib.util, json, linecache, os, stat, sys, time, types
from pathlib import Path

SOURCE_SHA = '4cec25d6083a51a43e50e65318ac598be5e2a32ac74cd07a3eb8647c4304e8d8'
SOURCE_BYTES = 7199
SOURCE_TOTAL = 298323
FORBIDDEN = ('numpy','scipy','torch','pytorch_lightning','torchmetrics','h5py','soundfile','requests','httpx','urllib.request','ctypes')

class InjectedRead(OSError): pass
class InjectedClose(OSError): pass
class InjectedPublication(OSError): pass
class StopBeforeScience(RuntimeError): pass

class Proxy:
    def __init__(self, original, **overrides): self._original=original; self.__dict__.update(overrides)
    def __getattr__(self,name): return getattr(self._original,name)

class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self, root, bodies):
        self.root=root; self.members={}; self.packages={}
        for rel,raw in bodies.items():
            if not rel.endswith('.py') or rel.startswith('donor/'): continue
            if '/' not in rel: name='n090native.'+rel[:-3]
            elif rel.startswith('runtime/vendor/experiments/'): name=rel[len('runtime/vendor/experiments/'):-3].replace('/','.')
            elif rel.startswith('runtime/'): name=rel[len('runtime/'):-3].replace('/','.')
            else: continue
            ispackage=name.endswith('.__init__')
            if ispackage: name=name[:-9]
            self.members[name]=(rel,raw)
            if ispackage:self.packages[name]=str(root/rel).rsplit('/',1)[0]
            parts=name.split('.')
            for i in range(1,len(parts)):self.packages.setdefault('.'.join(parts[:i]),str(root))
    def find_spec(self,fullname,path=None,target=None):
        if any(fullname==n or fullname.startswith(n+'.') for n in FORBIDDEN):
            raise RuntimeError('scientific/native library import forbidden: '+fullname)
        if fullname in self.members or fullname in self.packages:
            return importlib.util.spec_from_loader(fullname,self,is_package=fullname in self.packages)
    def create_module(self,spec): return None
    def exec_module(self,module):
        n=module.__name__; module.__file__=str(self.root/(self.members[n][0] if n in self.members else '__namespace__'))
        if n in self.packages:module.__path__=[self.packages[n]]
        if n in self.members:
            body=self.members[n][1]
            linecache.cache[module.__file__]=(len(body),None,body.decode('utf-8').splitlines(True),module.__file__)
            exec(compile(body,module.__file__,'exec',dont_inherit=True),module.__dict__)

def checked_source(path, size, sha):
    p=Path(path); before=p.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=size or any(q.is_symlink() for q in (p,*p.parents)):
        raise ValueError('selected ordinary whole source')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); first=None; secondary=[]; body=bytearray()
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mode,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
    try:
        if stamp(os.fstat(fd))!=stamp(before):raise ValueError('source identity at open')
        while len(body)<=size:
            part=os.read(fd,min(65536,size+1-len(body)))
            if not part:break
            body.extend(part)
        if stamp(os.fstat(fd))!=stamp(before) or stamp(p.lstat())!=stamp(before):raise ValueError('source identity after capture')
    except BaseException as e:first=e
    finally:
        try:os.close(fd)
        except BaseException as e:
            if first is None:first=e
            else:secondary.append(e)
    if first is not None:
        first.engineering_secondary=tuple(secondary);first.engineering_prefix=bytes(body);raise first
    if len(body)!=size or hashlib.sha256(body).hexdigest()!=sha:raise ValueError('exact selected source digest')
    return bytes(body)

class Context:
    def __init__(self, source, fixtures, work_end, bounds):
        self.source=Path(source);self.root=Path(fixtures);self.root.mkdir(mode=0o700)
        self.work_end=work_end;self.bounds=bounds;self.current=None;self.results=[];self.assertions=0
        self.reserved=0;self.used={'read':0,'write':0};self.case_used=0;self.retained=0;self.fixture_serial=0
        manifest=checked_source(self.source/'SOURCE_MANIFEST.json',SOURCE_BYTES,SOURCE_SHA)
        rows=json.loads(manifest)['files']
        if len(rows)!=43 or sum(r['bytes'] for r in rows)+SOURCE_BYTES!=SOURCE_TOTAL:raise ValueError('complete44 source roles')
        self.bodies={r['path']:checked_source(self.source/r['path'],r['bytes'],r['sha256']) for r in rows}
        self.selection={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']}for r in rows}
        self.source_reads=SOURCE_TOTAL+44
        self.finder=Captured(self.source,self.bodies);self.old_meta=list(sys.meta_path);self.old_modules=dict(sys.modules)
        if any(n in sys.modules for n in self.finder.members):raise ValueError('clean project namespaces')
        self.modules={}
        try:self.activate()
        except BaseException as first:
            secondary=[]
            try:self.restore()
            except BaseException as error:secondary.append(error)
            first.engineering_activation_secondary=tuple(secondary)
            raise
    def activate(self):
        sys.meta_path.insert(0,self.finder)
        for n in ('common','source_loader','process','cgroup','token_budget','broker','native','owner','controller','entry','place_entry'):
            self.modules['n090native.'+n]=importlib.import_module('n090native.'+n)
        for n in ('programme.contracts','broad090.protocol','broad090.custody','broad090.catalogue','broad090.planning','broad090.features','broad090.views','broad090.capture','broad090.operator','broad090.runtime_source'):
            self.modules[n]=importlib.import_module(n)
        for name,mod in list(self.modules.items()):
            if name.startswith('n090native.'):self.modules[name.replace('n090native.','n090_native.')]=mod
    def tick(self):
        if time.monotonic()>=self.work_end:raise TimeoutError('original engineering work endpoint')
    def check(self, condition, reason):
        self.tick();self.assertions+=1
        if not condition:raise AssertionError(reason)
    def reject(self,call,expected,reason):
        try:call()
        except BaseException as error:
            self.check(type(error)is expected,'exact expected exception '+expected.__name__+', got '+type(error).__name__)
            self.check(reason in str(error),'exact selected negative reason: '+reason)
            return error
        raise AssertionError('selected negative path returned: '+reason)
    def charge(self,kind,n):
        if kind not in self.used or type(n)is not int or n<0:raise ValueError('exact managed harness charge')
        self.tick();self.case_used+=n;self.used[kind]+=n
        if self.current is None or self.case_used>self.bounds[self.current]:raise RuntimeError('selected per-case transfer allowance')
    @contextlib.contextmanager
    def patch(self,obj,**changes):
        absent=object();old={k:getattr(obj,k,absent)for k in changes}
        try:
            for k,v in changes.items():setattr(obj,k,v)
            yield obj
        finally:
            for k,v in old.items():
                if v is absent:delattr(obj,k)
                else:setattr(obj,k,v)
    def fixture(self,name):
        if not name or name in ('.','..') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for c in name):raise ValueError('finite local fixture name')
        self.fixture_serial+=1;p=self.root/(str(self.fixture_serial)+'-'+name)
        self.charge('write',len(p.name)+1);p.mkdir(mode=0o700);return p
    def put(self,path,body,mode=0o600):
        if type(body)is not bytes:raise TypeError('exact fixture bytes')
        p=Path(path);p=p.absolute()
        if not p.is_relative_to(self.root)or any(q.is_symlink()for q in(p,*p.parents)):raise ValueError('fixture custody root')
        if self.retained+len(body)>3*1048576:raise RuntimeError('fixture retention bound')
        self.charge('write',len(body));self.retained+=len(body)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        try:
            with os.fdopen(fd,'wb')as f:fd=None;f.write(body)
        finally:
            if fd is not None:os.close(fd)
        return p
    def case(self,name,call):
        if self.current is not None or name in {x['case']for x in self.results}:raise ValueError('one exact engineering case')
        self.current=name;self.case_used=0;self.reserved+=self.bounds[name];before=self.assertions;start=time.monotonic()
        try:
            call();collected=gc.collect();self.tick()
            self.results.append({'case':name,'status':'PASS','assertions':self.assertions-before,'managed_transfer':self.case_used,'unreachable_objects_collected_after_case':collected,'seconds':time.monotonic()-start})
        finally:
            # On failure current remains available for the top-level original error record.
            if self.results and self.results[-1]['case']==name:self.current=None
    def restore(self):
        sys.meta_path[:]=self.old_meta
        for n in list(sys.modules):
            if n not in self.old_modules:sys.modules.pop(n,None)
        for n,m in self.old_modules.items():sys.modules[n]=m

def budget(ctx,read=2**28,write=2**28):return ctx.modules['n090native.common'].Budget(read,write,ctx.work_end)
def bare_owner(ctx):
    m=ctx.modules['n090native.owner'];o=m.NativeOwner.__new__(m.NativeOwner)
    o.root=ctx.fixture('owner');o.package=ctx.source;o.cfg={'image_id':'sha256:'+'1'*64};o.end=100.;o.work_end=90.
    o.errors=ctx.modules['n090native.common'].Ledger();o.budget=budget(ctx);o.command_count=0;o.command_records=[];o.program_paths={};o.isolations=[];o.keys={};o.sealed={};o.protected=False;o.completed=False;o.closed=False
    return o
