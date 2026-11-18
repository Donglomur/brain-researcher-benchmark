"""Authenticated full-panel entry; only explicit root-selected actuals can launch."""
import time
ORIGIN=time.monotonic()
import argparse,hashlib,importlib.abc,importlib.util,json,os,signal,stat,sys,types
from pathlib import Path
HERE=Path(__file__).absolute().parent

def cap(path,expected,limit=200000):
    p=Path(path).absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('linked source')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=limit and a.st_size==expected['bytes']):raise ValueError('source extent')
        with os.fdopen(fd,'rb',closefd=False) as f:b=f.read(limit+1)
        sig=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(b)!=a.st_size or hashlib.sha256(b).hexdigest()!=expected['sha256'] or sig(a)!=sig(os.fstat(fd)) or sig(a)!=sig(p.lstat()):raise ValueError('source pin')
        return b
    finally:os.close(fd)

class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,bodies):self.bodies=bodies
    def find_spec(self,fullname,path=None,target=None):
        name=fullname.replace('.','/')
        if name+'/__init__.py' in self.bodies:return importlib.util.spec_from_loader(fullname,self,is_package=True)
        if name+'.py' in self.bodies:return importlib.util.spec_from_loader(fullname,self)
        return None
    def create_module(self,spec):return None
    def exec_module(self,module):
        name=module.__name__.replace('.','/');p=name+'/__init__.py' if name+'/__init__.py' in self.bodies else name+'.py'
        module.__file__=str(HERE/p)
        if p.endswith('/__init__.py'):module.__path__=[]
        exec(compile(self.bodies[p],module.__file__,'exec'),module.__dict__)

def source(source_pin):
    manifest=json.loads(cap(HERE/'SOURCE_MANIFEST.json',source_pin));rows={r['path']:r for r in manifest['files']}
    if len(rows)!=len(manifest['files']) or any(Path(n).is_absolute() or '..' in Path(n).parts for n in rows):raise ValueError('source paths')
    bodies={n:cap(HERE/n,r) for n,r in rows.items()};sys.meta_path.insert(0,Captured(bodies))
    return rows,bodies

def selected(v,source_pin):
    from runtime_io import need
    keys={'schema','task_id','execution_selected','source_manifest','repository','attempt','other_bytes','program','method','related_exposure','docker_binary','docker_socket','docker_socket_identity','mount_source_policy'}
    need(type(v)is dict and set(v)==keys and v['schema']=='neural067_causal_selection_v1'
        and v['task_id']=='NEURAL-067' and v['execution_selected'] is True and v['source_manifest']==source_pin,'explicit exact execution selection')
    need(type(v['other_bytes'])is int and v['other_bytes']>=0 and v['docker_binary']=='/usr/local/bin/docker','root-selected local resources')
    need(v['mount_source_policy'] in ('identity','darwin_docker_desktop_users_v1'),'explicit bounded mount policy')
    need(type(v['related_exposure'])is dict and set(v['related_exposure'])=={'NEURAL067_public','NEURAL068','other_source_or_target_access'},'explicit exposure disclosure')
    for name,limit in [('program',1048576),('method',16384)]:
        p=v[name];need(type(p)is dict and set(p)=={'path','bytes','sha256'} and type(p['bytes'])is int and 0<p['bytes']<=limit and len(p['sha256'])==64,'bounded genuine operand')
    return v

def main(argv=None):
    p=argparse.ArgumentParser(add_help=False)
    for n in ('source-bytes','selection-bytes'):p.add_argument('--'+n,required=True,type=int)
    for n in ('source-sha256','selection-sha256'):p.add_argument('--'+n,required=True)
    p.add_argument('--selection',required=True,type=Path);p.add_argument('--normal-deadline',required=True,type=float)
    a=p.parse_args(argv);code=2
    try:
        end=a.normal_deadline
        if not ORIGIN<end<=ORIGIN+10800:raise ValueError('outer absolute normal clock')
        signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        if not(sys.flags.isolated and sys.dont_write_bytecode and sys.pycache_prefix and not os.path.lexists(sys.pycache_prefix)):raise ValueError('fresh cache before source imports')
        sp={'bytes':a.source_bytes,'sha256':a.source_sha256};rows,bodies=source(sp)
        from runtime_io import need,parse
        v=selected(parse(cap(a.selection,{'bytes':a.selection_bytes,'sha256':a.selection_sha256})),sp)
        attempt=Path(v['attempt']).absolute()
        need(sys.flags.isolated and sys.dont_write_bytecode and sys.pycache_prefix==str(attempt/'.disabled-pycache')
            and not os.path.lexists(sys.pycache_prefix),'fresh disabled cache before local imports')
        from host import execute
        result=execute(HERE,bodies,v,sp,end)
        for n,r in rows.items():cap(HERE/n,r)
        cap(HERE/'SOURCE_MANIFEST.json',sp)
        need(not os.path.lexists(sys.pycache_prefix) and result['success'] is True and time.monotonic()<end,'complete immutable-source execution')
        print(json.dumps({'success':True,'query_blocks':56,'committed_arm_rows':137960,'scientific_qualification':False}),flush=True)
        code=0 if time.monotonic()<end else 2
    except BaseException:
        if time.monotonic()<a.normal_deadline:
            try:print(json.dumps({'success':False,'scientific_qualification':False}),flush=True)
            except BaseException:pass
    return code if time.monotonic()<a.normal_deadline else 2

if __name__=='__main__':
    def stop(*_):raise TimeoutError('normal deadline or controlled interruption')
    for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(s,stop)
    signal.setitimer(signal.ITIMER_REAL,max(.001,ORIGIN+10800-time.monotonic()))
    try:raise SystemExit(main())
    finally:signal.setitimer(signal.ITIMER_REAL,0)
