"""Exact outer child: fixed request identity and inherited original clock."""
import hashlib,json,sys,time,os,stat,types,builtins,importlib.util
from pathlib import Path


def _json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate child JSON member')
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite child metadata')))

def _source_capture(path,cap,pin,end):
    if not isinstance(path,str) or not path.startswith('/') or any(x in ('','.','..') for x in path.split('/')[1:]):raise ValueError('canonical child source path')
    owned=[];primary=None;raw=None
    try:
        if time.monotonic()>=end:raise ValueError('original child source cutoff')
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);owned.append(fd)
        for part in path.split('/')[1:-1]:
            fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);owned.append(fd)
        parent=fd;fd=os.open(path.rsplit('/',1)[1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent);owned.append(fd)
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>cap:raise ValueError('bounded ordinary child source')
        chunks=[];remaining=before.st_size
        while remaining:
            if time.monotonic()>=end:raise ValueError('child capture deadline')
            b=os.read(fd,min(65536,remaining))
            if not b:raise ValueError('child capture early EOF')
            chunks.append(b);remaining-=len(b)
        if os.read(fd,1):raise ValueError('child capture changed extent')
        raw=b''.join(chunks);fields=('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
        after=os.fstat(fd);named=os.stat(path.rsplit('/',1)[1],dir_fd=parent,follow_symlinks=False)
        if any(getattr(before,k)!=getattr(after,k) or getattr(before,k)!=getattr(named,k) for k in fields):raise ValueError('changed child source')
        if pin is not None and {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=pin:raise ValueError('child source pin mismatch')
    except BaseException as error:primary=error
    while owned:
        try:os.close(owned.pop())
        except BaseException as error:
            if primary is None:primary=error
            else:primary.add_note('child capture close uncertainty: '+type(error).__name__)
    if primary is not None:raise primary
    if time.monotonic()>=end:raise ValueError('child post-capture deadline')
    return raw

def _captured_runtime(request,end):
    campaigns=request['campaigns']
    if not campaigns:raise ValueError('complete paired campaigns required')
    c=campaigns[0];root=c['runtime_root'];desc=c['runtime_manifest']
    if any((x['runtime_root'],x['metadata_root'],x['runtime_manifest'])!=(root,c['metadata_root'],desc) for x in campaigns):raise ValueError('one exact runtime closure')
    raw=_source_capture(c['metadata_root']+'/'+desc['path'],1048576,{k:desc[k] for k in ('bytes','sha256')},end)
    manifest=_json(raw)
    encoded=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    if hashlib.sha256(encoded).hexdigest()!=request['admission_value']['runtime_source_sha256']:raise ValueError('admitted whole runtime identity')
    if set(manifest)!= {'files'} or not 1<=len(manifest['files'])<=512:raise ValueError('bounded complete runtime source')
    bodies={};total=0
    for d in manifest['files']:
        name=d['path']
        if not isinstance(name,str) or name.startswith('/') or any(x in ('','.','..') for x in name.split('/')) or name in bodies:raise ValueError('unique runtime source member')
        total+=d['bytes']+1
        if d['bytes']>1048576 or total>16777216:raise ValueError('runtime source capture ceiling')
        bodies[name]=_source_capture(root+'/'+name,1048576,{k:d[k] for k in ('bytes','sha256')},end)
    if 'mintbench' in sys.modules:raise ValueError('unowned child project namespace')
    loaded={}
    def load(name):
        if name in loaded:return loaded[name]
        path=name.replace('.','/')+('/__init__.py' if name=='mintbench' else '.py')
        if path not in bodies:raise ValueError('unselected child project module')
        m=types.ModuleType(name);m.__file__=root+'/'+path;m.__package__=name if name=='mintbench' else name.rsplit('.',1)[0]
        if name=='mintbench':m.__path__=[root+'/mintbench']
        loaded[name]=m;sys.modules[name]=m
        def imp(n,g=None,l=None,fromlist=(),level=0):
            if level:n=importlib.util.resolve_name('.'*level+n,g['__package__'])
            if n=='mintbench' or n.startswith('mintbench.'):
                found=load(n)
                if fromlist:
                    for child in fromlist:
                        full=n+'.'+child
                        if child!='*' and not hasattr(found,child) and full.replace('.','/')+'.py' in bodies:setattr(found,child,load(full))
                    return found
                return load('mintbench')
            return builtins.__import__(n,g,l,fromlist,0)
        b=dict(vars(builtins));b['__import__']=imp;m.__dict__['__builtins__']=b
        exec(compile(bodies[path],m.__file__,'exec',dont_inherit=True),m.__dict__)
        if '.' in name:setattr(load(name.rsplit('.',1)[0]),name.rsplit('.',1)[1],m)
        return m
    # Capture and load all definition-only runtime modules before standard
    # imports can fall back to a project search path. __main__ is CLI-only.
    load('mintbench')
    for name in bodies:
        if name.startswith('mintbench/') and name.endswith('.py') and name not in ('mintbench/__init__.py','mintbench/__main__.py','mintbench/campaign_child.py'):
            load(name[:-3].replace('/','.'))
    return {'files':len(bodies),'source_read_bytes':total,'captured_project_imports':True}


def main():
    if len(sys.argv)!=9:raise ValueError('selected outer request and clocks required')
    request_path,expected,origin,end,cleanup_end,output,total,reserve=sys.argv[1:]
    if sys.stdin.buffer.readline(7)!=b'START\n':raise ValueError('outer custody handshake required')
    origin,end,cleanup_end=map(float,(origin,end,cleanup_end))
    raw=_source_capture(request_path,33554432,None,end)
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('original whole request bytes')
    request=_json(raw)
    _captured_runtime(request,end)
    from mintbench.validation import need,decode,digest
    from mintbench.custody import SharedBudget,Session
    from mintbench.observer import CgroupObserver
    from mintbench.schedule import validate_block
    from mintbench.campaign import run
    origin,end,cleanup_end=map(float,(origin,end,cleanup_end));need(time.monotonic()<end,'unchanged original clock before preparation')
    need(len(raw)<=33554432 and hashlib.sha256(raw).hexdigest()==expected,'whole request bytes selected by outer')
    validate_block(request['campaigns'])
    need(len(request['campaigns'])==len(request['campaign_sha256']),'every selected campaign hash before execution')
    budget=SharedBudget(output,int(total),int(reserve))
    results=[]
    for campaign,selected in zip(request['campaigns'],request['campaign_sha256']):
        need(time.monotonic()<end and digest(campaign)==selected,'precommitted campaign and original deadline')
        root=Path(campaign['output_root']);root.mkdir()
        session=Session(root,budget,origin,end,cleanup_end,lambda:CgroupObserver(campaign['cgroup_path'],campaign['gpu_devices']))
        result=run(request['admission_value'],request['selected_admission_sha256'],request['plan'],campaign,selected,session=session)
        results.append({'pair':campaign['schedule']['pair_id'],'order':campaign['schedule']['order'],'fatal':result['fatal']})
    need(len(results)==len(request['campaigns'])==len(request['campaign_sha256']),'complete balanced block')
    budget.persist(output,'block-result.json',{'pairs':results,'complete_execution':all(r['fatal'] is None for r in results),'scientifically_qualified':False},final=True)
    need(all(r['fatal'] is None for r in results),'paired block retains failures')


if __name__=='__main__':main()
