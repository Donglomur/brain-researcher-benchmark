"""Finite captured worker entry, exact source/clock before any numeric operand.
This launcher is itself authenticated by the external immutable-ID transport.
"""
import hashlib,importlib.abc,importlib.util,json,math,os,stat,sys,time
from pathlib import Path

def run(path,size,digest,origin,deadline):
    if not(math.isfinite(origin)and math.isfinite(deadline)and origin<deadline):raise ValueError('original finite clocks')
    reserved=0;cap=2<<20
    def tick():
        if not origin<=time.monotonic()<deadline:raise ValueError('original sandbox clock')
    def capture(p,n,h):
        nonlocal reserved
        tick()
        if type(n)is not int or n<0 or reserved+n+1>cap:raise ValueError('precharged sandbox source/request read')
        reserved+=n+1;p=Path(p)
        if not str(p).startswith('/inputs/')or '..'in p.parts:raise ValueError('fixed individual input path')
        for parent in p.parents:
            if not stat.S_ISDIR(os.lstat(parent).st_mode):raise ValueError('no indirect input parents')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode)or before.st_nlink!=1 or before.st_size!=n or before.st_mode&0o222:raise ValueError('sealed exact file')
            chunks=[];left=n
            while left:
                tick();v=os.read(fd,min(65536,left))
                if not v:raise ValueError('short input')
                chunks.append(v);left-=len(v)
            stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if os.read(fd,1)or stamp(before)!=stamp(os.fstat(fd))or stamp(before)!=stamp(os.lstat(p)):raise ValueError('changed mounted input')
            raw=b''.join(chunks)
            if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('exact input hash')
            tick();return raw
        finally:
            primary=sys.exception()
            try:os.close(fd)
            except BaseException as error:
                if primary is not None:raise BaseExceptionGroup('input and close',[primary,error])from None
                raise
    def parse(raw):
        def pairs(rows):
            d={}
            for k,v in rows:
                if k in d:raise ValueError('duplicate JSON key')
                d[k]=v
            return d
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite')))
    config=parse(capture(path,size,digest));tick()
    if config['schema']!='neural049_sandbox_v1'or config['original_origin']!=origin or config['deadline']!=deadline or config['clock_domain']!='qualified_shared_host_monotonic':raise ValueError('exact clocks and schema')
    cap=config['source_read_bytes']
    if type(cap)is not int or not reserved<=cap<=32<<20:raise ValueError('bounded selected source cap')
    bodies={};packages=set()
    for name,pin in config['files'].items():
        if not name.endswith('.py')or any(x in('','.','..')for x in name.split('/'))or '\\'in name:raise ValueError('source path')
        raw=capture('/inputs/source/'+name,pin['bytes'],pin['sha256']);module=name[:-3].replace('/','.')
        ispackage=module.endswith('.__init__')
        if ispackage:module=module[:-9];packages.add(module)
        bodies[module]=(raw,'/inputs/source/'+name)
        packages|={'.'.join(module.split('.')[:i])for i in range(1,len(module.split('.')))}
    class Finder(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,name,path=None,target=None):
            if name in bodies or name in packages:return importlib.util.spec_from_loader(name,self,is_package=name in packages)
            return None
        def create_module(self,spec):return None
        def exec_module(self,module):
            tick()
            if module.__name__ in bodies:
                raw,name=bodies[module.__name__];module.__file__=name;code=compile(raw,name,'exec',dont_inherit=True);tick();exec(code,module.__dict__);tick()
    if any(name in sys.modules for name in bodies):raise ValueError('no stale source module')
    sys.meta_path.insert(0,Finder())
    reqpin=config['request'];request=parse(capture('/inputs/REQUEST.json',reqpin['bytes'],reqpin['sha256']))
    entries={'candidate':'candidate_worker','analysis':'analysis_worker','reference':'reference_worker',
             'selection':'selection_worker'}
    entry=entries[config['role']]
    if entry!=config['entry']:raise ValueError('fixed entry identity')
    wc=config['worker_config']
    if wc['request_pin']!=reqpin or wc['request_path']!='/inputs/REQUEST.json' or wc['origin']!=origin or wc['deadline']!=deadline:
        raise ValueError('exact worker request/source/clock bridge')
    if wc.get('qualified_execution') is not True:raise ValueError('inactive worker before operands')
    target=wc['output']
    if target!='/output' and not(target.startswith('/artifacts/') and len(target)==75 and all(c in '0123456789abcdef' for c in target[11:])):
        raise ValueError('exact output namespace')
    tick();module=__import__(entry);tick()
    try:return module.run(wc)
    except BaseException as error:
        record={'status':'failed','error':type(error).__name__,'source_read_reserved':reserved,
                'worker_failure':getattr(error,'failure_record',getattr(error,'record',None)),
                'unknown_unpublished_tail':True,'clock_may_be_expired':True}
        try:
            raw=json.dumps(record,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
            if len(raw)>65536:raise ValueError('fallback record cap')
            fd=os.open(target+'/FALLBACK.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            first=None;later=None
            try:
                view=memoryview(raw)
                while view:
                    n=os.write(fd,view)
                    if n<=0:raise ValueError('short fallback')
                    view=view[n:]
                os.fsync(fd)
            except BaseException as primary:first=primary
            finally:
                try:os.close(fd)
                except BaseException as cleanup:later=cleanup
            if first is not None or later is not None:
                raise BaseExceptionGroup('fallback write/close',[x for x in (first,later) if x is not None])
        except BaseException as later:
            raise BaseExceptionGroup('worker and fallback publication',[error,later])from None
        raise

if __name__=='__main__':
    if len(sys.argv)!=6:raise ValueError('exact bounded launch argv')
    try:run(sys.argv[1],int(sys.argv[2]),sys.argv[3],float(sys.argv[4]),float(sys.argv[5]))
    except BaseException as error:
        # Bounded stderr is diagnostic; independent host retains lifecycle and costs.
        print(json.dumps({'status':'failed','error':type(error).__name__,'unknown_unpublished_costs':True}),file=sys.stderr);raise
