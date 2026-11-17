"""Capture exact local source closure before importing task code."""
import builtins,hashlib,json,os,stat,types
from pathlib import Path

def load(here,expected):
    here=Path(here).absolute()
    if any(x.is_symlink()for x in(here,*here.parents)):raise ValueError('unlinked source')
    def read(p,cap):
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode)or a.st_nlink!=1 or not 0<a.st_size<=cap:raise ValueError('bounded source')
            b=os.read(fd,a.st_size+1);z=os.fstat(fd);n=p.lstat()
            if len(b)!=a.st_size or any(getattr(a,k)!=getattr(z,k)or getattr(a,k)!=getattr(n,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError('stable source')
            return b
        finally:os.close(fd)
    raw=read(here/'SOURCE_MANIFEST.json',131072)
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('root source pin')
    manifest=json.loads(raw);bodies={};mods={}
    for name,p in manifest['files'].items():
        if '/'in name or name.startswith('.')or name not in manifest['files']:raise ValueError('flat source')
        b=read(here/name,262144)
        if len(b)!=p['bytes']or hashlib.sha256(b).hexdigest()!=p['sha256']:raise ValueError('source identity')
        bodies[name]=b
    def module(name):
        if name in mods:return mods[name]
        filename=name+'.py'
        if filename not in bodies:raise ValueError('fixed source module')
        m=types.ModuleType('_neural076_'+name);m.__file__=str(here/filename);scope=dict(vars(builtins));orig=builtins.__import__
        def importer(target,globals=None,locals=None,fromlist=(),level=0):
            if level==0 and target+'.py'in bodies:return module(target)
            return orig(target,globals,locals,fromlist,level)
        scope['__import__']=importer;m.__dict__['__builtins__']=scope;mods[name]=m
        try:exec(compile(bodies[filename],m.__file__,'exec'),m.__dict__)
        except BaseException:mods.pop(name,None);raise
        return m
    return module,bodies,manifest,{'bytes':len(raw),'sha256':expected}
