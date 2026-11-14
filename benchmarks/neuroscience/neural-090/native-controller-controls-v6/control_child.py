"""Captured one-attempt driver; actual test functions execute only after root selection."""
import argparse, base64, hashlib, importlib.abc, importlib.util, json, linecache, os, signal, stat, sys, time, traceback, types
from pathlib import Path

FINAL_CUSTODY={}

class PublicationFailure(RuntimeError):
    def __init__(self,first,secondary,body):
        self.first=first;self.secondary=tuple(secondary);self.body=body
        super().__init__('engineering publication failed; original bytes and all raw errors retained')

def publish(path,body):
    fd=None;first=None;secondary=[];offset=0
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        while offset<len(body):
            n=os.write(fd,body[offset:])
            if n<=0:raise OSError('short original engineering result write')
            offset+=n
        os.fsync(fd)
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                if first is None:first=error
                else:secondary.append(error)
    if first is not None:raise PublicationFailure(first,secondary,body)from first

def selected(path,n,h):
    p=Path(path);s=p.lstat()
    if p.is_symlink()or not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=n or n>1048576:raise ValueError('exact finite selected harness')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);first=None;second=[];raw=bytearray()
    try:
        while len(raw)<=n:
            b=os.read(fd,min(65536,n+1-len(raw)))
            if not b:break
            raw.extend(b)
    except BaseException as e:first=e
    finally:
        try:os.close(fd)
        except BaseException as e:
            if first is None:first=e
            else:second.append(e)
    if first is not None:first.retained_secondary=tuple(second);first.retained_prefix=bytes(raw);raise first
    if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=h:raise ValueError('whole selected harness identity')
    return bytes(raw)

def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    for n in ('manifest','manifest-bytes','manifest-sha256','source-root','output','work-end','publication-end'):parser.add_argument('--'+n,required=True)
    args=parser.parse_args();work_end=float(args.work_end);publication_end=float(args.publication_end)
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize):raise ValueError('actual isolated no-site no-cache driver')
    raw=selected(args.manifest,int(args.manifest_bytes),args.manifest_sha256);selection=json.loads(raw)
    if selection['schema']!='n090_finite_controller_engineering_selection_v1'or selection['execution_selected']is not False:raise ValueError('fixed prospective harness selection')
    base=Path(args.manifest).absolute().parent;output=Path(args.output).absolute();source=Path(args.source_root).absolute()
    if output.parent!=base or output.name!='actual-v1':raise ValueError('one fixed outer-owned output')
    rows=selection['files'];captured={r['path']:selected(base/r['path'],r['bytes'],r['sha256'])for r in rows}
    if len(captured)!=len(rows)or set(captured)!={'control_owner.py','control_child.py','harness_core.py','primary_cases.py','barrier_cases.py','native_cases.py'}:raise ValueError('closed six-file engineering graph')
    # All supporting source is compiled from captured bytes, never sibling imports.
    old_modules=dict(sys.modules);modules={}
    for name,body in captured.items():
        path=str(base/name);linecache.cache[path]=(len(body),None,body.decode('utf-8').splitlines(True),path)
    for name in ('harness_core','primary_cases','barrier_cases','native_cases'):
        m=types.ModuleType(name);m.__file__=str(base/(name+'.py'));sys.modules[name]=m;modules[name]=m
        exec(compile(captured[name+'.py'],m.__file__,'exec',dont_inherit=True),m.__dict__)
    fixtures=output/'fixtures';forbidden=('numpy','scipy','torch','pytorch_lightning','torchmetrics','h5py','soundfile','ctypes')
    stdlib=Path(os.__file__).absolute().parent
    def inside(p,root):return p==root or p.is_relative_to(root)
    def audit(event,values):
        if event in ('subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.posix_spawnp','os.exec','os.kill','os.killpg','socket.__new__','socket.connect','ctypes.dlopen'):raise RuntimeError('engineering child forbids actual native/provider/process effect: '+event)
        if event=='import'and any(values[0]==n or values[0].startswith(n+'.')for n in forbidden):raise RuntimeError('engineering child forbids scientific native import')
        if event=='open'and not isinstance(values[0],int):
            p=Path(values[0]).absolute();mode=values[1]or '';flags=values[2]if len(values)>2 else 0
            writing=any(c in str(mode)for c in 'wax+')or isinstance(flags,int)and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing and not inside(p,output):raise RuntimeError('engineering write escaped output custody')
            if not writing and not any(inside(p,q)for q in (source,output,stdlib)):raise RuntimeError('engineering read escaped source/fixture/stdlib custody')
        if event in ('os.scandir','os.listdir')and values and not isinstance(values[0],int):
            p=Path(values[0]).absolute()
            if not any(inside(p,q)for q in (source,output)):raise RuntimeError('engineering inventory escaped ordinary custody')
    sys.addaudithook(audit)
    def timeout(signum,frame):raise TimeoutError('original finite24 engineering work endpoint')
    old_alarm=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,max(.001,work_end-time.monotonic()))
    ctx=None;first=None;secondary=[];start=time.monotonic()
    try:
        ctx=modules['harness_core'].Context(source,fixtures,work_end,selection['case_transfer_bounds'])
        modules['primary_cases'].run(ctx);modules['native_cases'].run(ctx);modules['barrier_cases'].run(ctx)
        if [r['case']for r in ctx.results]!=selection['case_roster']:raise AssertionError('whole exact24 roster; no subset pass')
        ctx.tick()
    except BaseException as e:first=e
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException as e:
            if first is None:first=e
            else:secondary.append(e)
        if ctx is not None:
            try:ctx.restore()
            except BaseException as e:
                if first is None:first=e
                else:secondary.append(e)
        try:signal.signal(signal.SIGALRM,old_alarm)
        except BaseException as e:
            if first is None:first=e
            else:secondary.append(e)
    def add(error):
        nonlocal first
        if first is None:first=error
        else:secondary.append(error)
    def exception(e):
        try:value={'type':type(e).__name__,'reason':str(e)[:4096],'traceback':''.join(traceback.format_exception(e,limit=24))[:24576]}
        except BaseException as error:
            add(error);return {'type':type(e).__name__,'projection_unavailable':True,'projection_error':type(error).__name__}
        # Raw errors remain alive; projection explicitly describes, never replaces them.
        if hasattr(e,'first'):value['carrier_first']={'type':type(e.first).__name__,'reason':str(e.first)[:2048]}
        if hasattr(e,'record'):value['carrier_record_repr']=repr(e.record)[:8192]
        return value
    if time.monotonic()>=publication_end and first is None:first=TimeoutError('original child publication cutoff')
    result={'schema':'n090_complete24_engineering_result_v1','status':'PASS'if first is None and not secondary else 'FAIL','case':None if ctx is None else ctx.current,'cases':[]if ctx is None else ctx.results,'attempted':0 if ctx is None else len(ctx.results)+(ctx.current is not None),'assertions':0 if ctx is None else ctx.assertions,'first':None if first is None else exception(first),'secondary':[exception(e)for e in tuple(secondary)],'original_error_objects_retained_in_process':True,'source_manifest_sha256':modules['harness_core'].SOURCE_SHA,'native_scientific_provider_effects':0,'full_scope_invocations':76800,'fixed_case_transfer_reserved':0 if ctx is None else ctx.reserved,'selected_charge_observations':None if ctx is None else ctx.used,'fixture_bytes_via_put':0 if ctx is None else ctx.retained,'seconds':time.monotonic()-start,'physical_IO_or_RSS_measured':False}
    body=None;durable=False
    FINAL_CUSTODY.update(result=result,first=first,secondary=secondary)
    try:
        result['status']='PASS'if first is None and not secondary else'FAIL'
        body=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()
        if len(body)>131072:raise RuntimeError('bounded original engineering result')
        publish(output/'CHILD_RESULT.json',body);durable=True
    except BaseException as error:add(error)
    if time.monotonic()>=publication_end:add(TimeoutError('original child final publication endpoint'))
    status='PASS'if first is None and not secondary else'FAIL'
    try:print(json.dumps({'status':status,'case':result['case'],'passed':len(result['cases']),'assertions':result['assertions'],'durable_child_record':durable}),flush=True)
    except BaseException as error:add(error)
    if first is not None:
        # Compact fallback does not overwrite a partial or already frozen record.
        fallback={'status':'FAIL','case':result['case'],'durable_child_record':durable,'first_type':type(first).__name__,'first_reason':str(first)[:2048],'secondary_types':[type(x).__name__ for x in secondary[:32]],'original_result_retained_in_process':True}
        try:sys.stderr.write(json.dumps(fallback,sort_keys=True)+'\n');sys.stderr.flush()
        except BaseException as error:secondary.append(error)
    FINAL_CUSTODY.update(first=first,secondary=tuple(secondary),intended_body=body,durable=durable)
    return 0 if first is None and not secondary and time.monotonic()<publication_end else 1

if __name__=='__main__':raise SystemExit(main())
