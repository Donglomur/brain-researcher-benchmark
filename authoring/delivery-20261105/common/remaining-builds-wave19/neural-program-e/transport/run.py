"""Captured outer observer for complete NEURAL089 production; never scientific qualification."""
import time
ORIGIN=globals().get('_CAPTURED_LAUNCH_ORIGIN')
import argparse,base64,hashlib,json,os,shutil,signal,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BOOT_PIN={'bytes': 1734, 'sha256': 'bf4545385dd30a3d01884ad184e6df80d4cab431d8c0f996265544f70a2077f4'}
CAPTURED_WORKER='''import time,signal,sys
end=float(sys.argv[3])
def expired(*_):raise TimeoutError("original captured worker startup clock")
if time.monotonic()>=end:raise TimeoutError("original worker startup expired")
for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,expired)
signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
import base64,hashlib
path=sys.argv[1];raw=base64.b64decode(sys.argv[2],validate=True)
pp={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
sys.argv=[path,*sys.argv[4:]]
exec(compile(raw,path,"exec"),{"__name__":"__main__","__file__":path,"_CAPTURED_WORKER_PIN":pp})
'''

def boot(deadline):
    p=ROOT/'transport/bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('ordinary bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT_PIN['bytes']+1)
    if len(raw)!=BOOT_PIN['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT_PIN['sha256']:raise ValueError('bootstrap pin')
    if time.monotonic()>=deadline:raise TimeoutError('original startup clock')
    m=types.ModuleType('neural089_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__)
    return m,len(raw)+1

def source_modules(c,bodies):
    science=c.module(bodies,'program/science.py',ROOT,c=c,source_bodies=bodies)
    packet=c.module(bodies,'program/packet.py',ROOT,c=c,science=science)
    policy=c.module(bodies,'program/policy.py',ROOT,c=c,packet=packet)
    outputs=c.module(bodies,'program/outputs.py',ROOT,c=c,packet=packet,policy=policy,science=science)
    return packet,policy,outputs

def main(argv=None):
    if ORIGIN is None or globals().get('_CAPTURED_OUTER_PIN') is None:raise ValueError('root-captured entry and original clock required')
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise ValueError('isolated no-site bytecode-free outer')
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','external-output'):p.add_argument('--'+name,required=True)
    a=p.parse_args(argv);deadline=ORIGIN+120;exitcode=2
    def stop(*_):raise TimeoutError('original outer deadline or stop')
    old={n:signal.signal(n,stop) for n in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    try:
        source=json.loads(a.source_pin);loader,boot_cost=boot(deadline)
        c,manifest,bodies,source_cost=loader.load(ROOT,source,deadline)
        c.need(c.pin(bodies['transport/run.py'])==globals()['_CAPTURED_OUTER_PIN'],'executing outer source matches full source closure')
        c.need(manifest['files']['transport/bootstrap.py']==BOOT_PIN,'full bootstrap source join')
        packet,policy,outputs=source_modules(c,bodies);selection_pin=json.loads(a.selection_pin)
        selection_body=c.capture(a.selection,32768,selection_pin,lambda:c.before(deadline))
        s=policy.selection(c.parse(selection_body),source)
        whole=ORIGIN+s['limits']['whole_seconds'];worker_end=whole-s['limits']['observer_seconds'];outer=whole+60
        c.need(time.monotonic()<worker_end and worker_end<whole,'original production and outer-admission intervals')
        output=c.path(a.external_output);root=c.path(s['output'])
        c.need(not os.path.lexists(output) and not os.path.lexists(root) and output!=root and not output.is_relative_to(root) and not root.is_relative_to(output),'fresh disjoint external receipt and attempt')
        c.need(root.parent.stat().st_dev==output.parent.stat().st_dev and os.statvfs(output.parent).f_frsize<=4096,'same bounded filesystem')
        c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+s['limits']['retained']+8192,'fresh full future allocation and receipt floor')
        slot=c.module(bodies,'transport/slot.py',ROOT)
        initial=slot.slot(output,c.encoded(dict(schema='neural089_complete_external_v1',status='started',source=source,selection=selection_pin)),deadline,create=True)
        proc=c.module(bodies,'transport/process.py',ROOT)
        cache=Path(str(output)+'.UNUSED-PYCACHE');c.need(not os.path.lexists(cache),'fresh unused worker cache')
        argv=[str(Path(sys.executable).resolve()),'-I','-S','-B','-X','pycache_prefix='+str(cache),'-c',CAPTURED_WORKER,str(ROOT/'transport/worker.py'),base64.b64encode(bodies['transport/worker.py']).decode('ascii'),repr(min(worker_end,ORIGIN+120)),'--source-pin',a.source_pin,'--selection',a.selection,'--selection-pin',a.selection_pin,'--origin',repr(ORIGIN),'--worker-end',repr(worker_end)]
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_')) and k not in ('DOCKER_HOST','DOCKER_CONTEXT')};env['PYTHONDONTWRITEBYTECODE']='1'
        reads=source_cost+boot_cost+len(selection_body)+1+globals().get('_EARLY_SOURCE_READ_CHARGE',0)
        c.need(reads<=s['limits']['observer_reads'],'initial outer read ceiling')
        record=None;error=None;join=None;success=False;worker_result=None;worker_result_pin=None
        def charge(n):
            nonlocal reads
            c.need(type(n)is int and n>=0 and reads+n<=s['limits']['observer_reads'],'whole outer read ceiling')
            reads+=n;c.before(whole)
        def read(path,cap,expected=None):return c.capture(path,cap,expected,lambda:c.before(whole),charge)
        signal.setitimer(signal.ITIMER_REAL,max(.001,worker_end-time.monotonic()))
        try:
            raw,record=proc.run(argv,worker_end,whole+40,env)
            c.need(time.monotonic()<worker_end,'natural child closure before original worker endpoint')
            c.need(record['natural_exit'] is True and type(record['exit_code'])is int and record['exit_code']==0 and record['process_reaped'] is True and record['process_group_absent'] is True and record['streams_closed'] is True,'exact natural worker closure')
            c.need(not os.path.lexists(cache),'worker disabled-cache absence')
            signal.setitimer(signal.ITIMER_REAL,max(.001,whole-time.monotonic()))
            worker_result=c.parse(raw);worker_result_pin=c.pin(raw)
            join=outputs.admit_collection(s,source,bodies,worker_result,root,read)
            c.need(type(join)is dict and join.get('status')=='complete_unqualified','all-panel independent admission')
            success=True
        except BaseException as exc:
            error=type(exc).__name__
            if isinstance(exc,proc.ChildFailure):record=exc.record
        deadline=whole if success else outer
        signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()));c.before(deadline)
        used=c.inventory(root,s['limits']['retained'],s['limits']['max_entries'])[2] if root.exists() else 0
        c.need(shutil.disk_usage(output.parent).free>=c.FLOOR+s['other_future_bytes']+max(0,s['limits']['retained']-used),'terminal retained allocation floor')
        value=dict(schema='neural089_complete_external_v1',status='complete_unqualified' if success else 'failed',source=source,selection=selection_pin,attempt=str(root),executing_outer_source=globals()['_CAPTURED_OUTER_PIN'],executing_worker_source=c.pin(bodies['transport/worker.py']),child=record,error_type=error,worker_result=worker_result,worker_result_pin=worker_result_pin,joined_collection=join,origin_monotonic=ORIGIN,worker_deadline=worker_end,whole_deadline=whole,outer_failure_deadline=outer,elapsed_before_publication=time.monotonic()-ORIGIN,observer_read_reservations=reads,observer_write_reservations=16384,scientific_qualified=False,runtime_qualified=False,grading_performed=False,nested_native_recovery_may_be_required=not success,automatic_retry=False)
        slot.slot(output,c.encoded(value),deadline,create=False,stamp=initial);c.before(deadline);exitcode=0 if success else 2
    except BaseException:exitcode=2
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:exitcode=2
        for number,handler in old.items():
            try:signal.signal(number,handler)
            except BaseException:exitcode=2
    return exitcode if time.monotonic()<deadline else 2
if __name__=='__main__':raise SystemExit(main())
