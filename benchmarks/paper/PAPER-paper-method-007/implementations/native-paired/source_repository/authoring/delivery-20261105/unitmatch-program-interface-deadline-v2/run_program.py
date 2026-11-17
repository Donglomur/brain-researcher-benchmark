"""Five fresh held-mouse jobs from one sealed program; no grading or baseline."""
import time
ORIGIN=time.monotonic()
import argparse,hashlib,json,math,os,selectors,shutil,signal,stat,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from bound_io import need,ordinary,capture,parse,identity,encoded,fsync_dir,source_capture,Budget as BaseBudget
import transport

TASK='PAPER-paper-method-007'
MICE=tuple('Mouse'+str(i) for i in range(1,6))
SIZES=(534,109,96,59,466)
PINS={'private/PACKET_MAP.json':{'bytes':1320185,'sha256':'8f361ac6074f5306ba4cf0c07e6593ec4eaefe6d5a4e0851448a89fa73917a89'},
      'public/cohort.json':{'bytes':532569,'sha256':'7ed4a18626ca53c13d97beb12182e2240dbd6e8131dd9bdceecd696985b904f1'}}
PROGRAM_CAP=65536;FOLD_CAP=16000000;FINAL_CAP=100000000
OWN_CAP=3000000000;WRITE_CAP=13000000000;READ_CAP=40000000000;WHOLE=1800
ARMED=False


def before(end):need(time.monotonic()<end,'Original whole deadline')


class Budget(BaseBudget):
    def __init__(self,root,other,end):
        super().__init__(root);self.other=other;self.end=end;self.reads=10000000
    def used(self):
        root=self.root.lstat();total=max(root.st_size,root.st_blocks*512);count=0
        for parent,dirs,files in os.walk(self.root,followlinks=False):
            before(self.end)
            for name in dirs+files:
                count+=1;need(count<=10000,'Bounded owned tree inventory')
                s=(Path(parent)/name).lstat()
                need(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) and s.st_nlink==1,'Ordinary single-link retained tree')
                total+=max(s.st_size,s.st_blocks*512)
        return total
    def check(self,n,receipt=False):
        before(self.end);need(type(n)is int and n>=0 and self.written+n<=WRITE_CAP,'Cumulative writes')
        used=self.used();need(used+n+8192<=OWN_CAP-(0 if receipt else 10000000),'Owned allocated cap and publication margin')
        fs=os.statvfs(self.root)
        need(fs.f_bavail*fs.f_frsize>=20*1024**3+self.other+max(0,OWN_CAP-used),'Current floor and remaining owned reservation')
    def charge_read(self,n):
        need(type(n)is int and n>=0 and self.reads+n<=READ_CAP,'Aggregate controlled read reservation');self.reads+=n


def closure(here,sha,package):
    source=source_capture(here,sha)
    for name in ('run_program.py','bound_io.py','transport.py'):
        need(capture(here/name,200000)==source[name],'Captured executable source')
    package=ordinary(package)
    body={name:capture(package/name,p['bytes'],p) for name,p in PINS.items()}
    packet=parse(body['private/PACKET_MAP.json']);cohort=parse(body['public/cohort.json'])
    need(type(packet.get('files'))is list and len(packet['files'])==4000,'Complete4000-entry packet map')
    need(tuple(m['mouse_id'] for m in cohort['mice'])==MICE
         and tuple(len(m['units']) for m in cohort['mice'])==SIZES,'Complete original five-mouse cohort')
    transport.loaded('io_utils',source['vendor/io_utils.py'],here/'vendor/io_utils.py')
    interface=transport.loaded('_unitmatch_frozen_interface',source['vendor/interface.py'],here/'vendor/interface.py')
    stage=transport.loaded('_unitmatch_frozen_stage',source['vendor/stage_view.py'],here/'vendor/stage_view.py')
    validate_map(packet,stage)
    return source,packet,cohort,interface,stage


def validate_map(packet,stage):
    rows=packet['files'];seen=set()
    for r in rows:
        need(type(r)is dict and set(r) in ({'source','target','arm','bytes','sha256'},
             {'source','target','arm','bytes','sha256','validation_mouse'}),'Exact packet descriptor')
        for key in ('source','target'):
            p=Path(r[key]);need(type(r[key])is str and not p.is_absolute() and '..'not in p.parts,'Packet relative path')
        need(r['target']not in seen and type(r['bytes'])is int and r['bytes']>0,'Unique complete positive input');seen.add(r['target'])
        need(r['arm']in('both','B'),'Only common or author-B source')
        if 'validation_mouse'in r:need(r['validation_mouse']in MICE and r['arm']=='both','Development functional source')
    need(sum(r['arm']=='both' for r in rows)==3860 and sum(r['arm']=='B' for r in rows)==140,'Exact common/code counts')
    need(sum('validation_mouse'in r for r in rows)==10,'All ten functional sources')
    for mouse in MICE:
        a,b=(stage.selected(rows,v,mouse) for v in ('A','B'))
        need(len(a)==3858 and len(b)==3998 and b==[r for r in rows if r in a or r['arm']=='B'],'Exact arm difference')
        need([r for r in a if 'validation_mouse'in r]==[r for r in b if 'validation_mouse'in r]
             and len([r for r in a if 'validation_mouse'in r])==8,'Same four-mouse development inputs')
        need(all(r.get('validation_mouse')!=mouse for r in a+b),'Held functional source excluded')


def fold_output(raw,unit,cohort):
    need(0<len(raw)<=FOLD_CAP,'Fold output extent');value=parse(raw)
    need(type(value)is dict and set(value)=={'schema','access_view','method_name','held_out_mouse',
         'development_mice','program_sha256','probabilities'},'Exact fold output fields')
    need(value['schema']=='unitmatch_fold_output_v1' and value['access_view']==unit['view']
         and value['method_name']==unit['method_name'] and value['held_out_mouse']==unit['unit_id']
         and value['development_mice']==[m for m in MICE if m!=unit['unit_id']]
         and value['program_sha256']==unit['program_sha256'],'Same sealed method and exact held fold')
    n=next(len(m['units']) for m in cohort['mice'] if m['mouse_id']==unit['unit_id']);matrix=value['probabilities']
    need(type(matrix)is list and len(matrix)==n,'All ordered unit rows')
    for row in matrix:
        need(type(row)is list and len(row)==n,'All directed columns including diagonal')
        need(all(type(x)in(int,float) and math.isfinite(x) and 0<=x<=1 for x in row),'Finite probability values')
    return {k:value[k] for k in ('held_out_mouse','development_mice','probabilities')}


def assemble(folds,view,method,cohort,interface):
    need(type(folds)is list and len(folds)==5 and [r['held_out_mouse'] for r in folds]==list(MICE),'No missing/reordered fold')
    value={'schema':'unitmatch_submission_v1','access_view':view,'method_name':method,'folds':folds}
    interface.validate(value,cohort,view)
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    need(len(raw)<=FINAL_CAP,'Unchanged full-five artifact cap');return raw


def staged_tree(view,rows):
    """Verify owned stage geometry/modes; exact content was checked by frozen stage."""
    ordinary(view);wanted={r['target']:r for r in rows};seen=set()
    for parent,dirs,files in os.walk(view,followlinks=False):
        for name in dirs+files:
            p=Path(parent)/name;s=p.lstat();need(not stat.S_ISLNK(s.st_mode),'No linked view item')
            if stat.S_ISDIR(s.st_mode):need(stat.S_IMODE(s.st_mode)==0o555,'Sealed view directory')
            else:
                need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o444,'Ordinary sealed view file')
                rel=str(p.relative_to(view));seen.add(rel)
                need(rel=='VIEW.json' or rel in wanted and s.st_size==wanted[rel]['bytes'],'Exact staged extent')
    need(seen==set(wanted)|{'VIEW.json'} and stat.S_IMODE(view.stat().st_mode)==0o555,'Complete staged inventory')


def prepare_view(stage,package,view,rows,arm,mouse,budget):
    total=sum(r['bytes'] for r in rows)
    # Frozen stager: source hash + copy source + saved copy hash, with full failures charged.
    budget.charge_read(3*total+3*len(rows)+PINS['private/PACKET_MAP.json']['bytes']+1)
    dirs={str(p) for row in rows for p in Path(row['target']).parents}
    budget.check(total+4096*(len(rows)+len(dirs)+4)+8192);budget.written+=total+8192
    stage.stage(package,view,arm,mouse)
    need(parse(capture(view/'VIEW.json',8192))=={'access_view':arm,'held_out_mouse':mouse,
         'development_mice':[m for m in MICE if m!=mouse],'access_attestation':False},'Original unqualified view marker')
    for parent,dirs,files in os.walk(view,topdown=False):
        for name in files:(Path(parent)/name).chmod(0o444)
        Path(parent).chmod(0o555)
    staged_tree(view,rows);s=view.stat();return (s.st_dev,s.st_ino)


def retire_view(view,rows,owned):
    staged_tree(view,rows);s=view.stat();need((s.st_dev,s.st_ino)==owned,'Only owned sealed view may retire')
    for parent,dirs,files in os.walk(view):Path(parent).chmod(0o700)
    shutil.rmtree(view);fsync_dir(view.parent)


def execute(here,package,program,out,sha,binary,env,arm,method,other,*,bind=transport.bind):
    started=ORIGIN;end=ORIGIN+WHOLE;before(end)
    need(arm in ('A','B') and type(method)is str and 1<=len(method)<=160,'One explicit arm and method')
    need(type(other)is int and other>=0,'Explicit current OTHER')
    source,packet,cohort,interface,stage=closure(here,sha,package)
    program_body=capture(program,PROGRAM_CAP);program_pin=identity(program_body)
    out=ordinary(out);package=ordinary(package)
    need(not out.exists() and out.parent.is_dir() and not out.is_relative_to(package),'Fresh attempt outside source package')
    fs=os.statvfs(out.parent);need(fs.f_bavail*fs.f_frsize>=20*1024**3+other+OWN_CAP,'Full future phase reserve')
    out.mkdir(mode=0o700);fsync_dir(out.parent);budget=Budget(out,other,end);lib=None;folds=[];commits=[];previous=None
    # All source and the only program are committed before any held-fold staging.
    snapshot=out/'source';snapshot.mkdir()
    for name,body in source.items():
        if name.startswith('vendor/'):budget.write(snapshot/Path(name).name,body)
    budget.write(out/'program.py',program_body)
    seal={'schema':'unitmatch_method_seal_v1','task_id':TASK,'access_view':arm,'method_name':method,
          'program':program_pin,'source_manifest_sha256':sha,'packet_pins':PINS,'folds':list(MICE),
          'sealed_before_any_input_stage':True,'public_data_exposure_remains':True}
    budget.save(out/'SEAL.json',seal)
    result={'schema':'unitmatch_program_attempt_v1','success':False,'program':program_pin,'access_view':arm,
            'method_name':method,'folds_committed':0,'runtime_qualified':False,'scientific_qualification':False,
            'private_grading_performed':False,'native_baseline_executed':False,'failed_partials_preserved':True}
    try:
        for mouse in MICE:
            need(time.monotonic()<end-100,'Full next unit and cleanup reserve')
            job=out/mouse;job.mkdir();view=job/'view';rows=stage.selected(packet['files'],arm,mouse)
            owned=prepare_view(stage,package,view,rows,arm,mouse,budget)
            descriptor={'path':str(view.relative_to(out)),'mount_destination':'/input',
                'logical_bytes':sum(r['bytes'] for r in rows),'files':len(rows),
                'selected_packet_rows_sha256':hashlib.sha256(encoded(rows)).hexdigest()}
            unit={'unit_id':mouse,'view':arm,'method_name':method,'program_sha256':program_pin['sha256'],
                  'output_filename':'fold.json','max_output_bytes':FOLD_CAP,'public_inputs':[descriptor]}
            def mounts(got,program_sha):
                need(got==unit and program_sha==program_pin['sha256'],'Exact owned invocation')
                staged_tree(view,rows);s=view.stat();need((s.st_dev,s.st_ino)==owned,'Owned staged directory')
                return {'/input':view}
            validate=lambda raw,got:fold_output(raw,got,cohort)
            lib=bind(source,snapshot,out,unit,binary,env,budget,mounts,lambda raw,got=unit:validate(raw,got))
            budget.save(job/'RELEASE.json',{'method_seal':identity(capture(out/'SEAL.json',32768)),
                'unit':unit,'held_functional_source_absent':True,'same_program':program_pin,
                'view_marker_is_not_runtime_attestation':True})
            unit_start=time.monotonic()
            returned=lib['task'].run_unit(out/'program.py',program_pin['sha256'],unit,job/'unit',budget,
                min(end-60,unit_start+40),min(end-50,unit_start+50),previous,TASK,validate)
            need(time.monotonic()-unit_start<=50,'Bounded fresh job including cleanup')
            observed=transport.barrier(lib,min(end-40,time.monotonic()+10));budget.save(job/'ABSENCE.json',observed)
            need(returned['status']=='unit_committed' and returned['all_owned_absent'] is True,'Trusted successful job only')
            commit=parse(capture(job/'unit/commit.json',65536))
            need(commit['candidate_id']==TASK and commit['unit_id']==mouse and commit['program_sha256']==program_pin['sha256']
                 and commit['previous_commit_sha256']==previous and commit['public_inputs']==[descriptor]
                 and commit['producer_removed_before_capture'] is True and commit['all_candidate_holder_volume_absent'] is True,
                 'Exact internal producer commit chain')
            budget.charge_read(FOLD_CAP+1)
            raw=capture(job/'unit/fold.json',FOLD_CAP,commit['output']);folds.append(fold_output(raw,unit,cohort))
            previous=hashlib.sha256(capture(job/'unit/commit.json',65536)).hexdigest();commits.append(previous)
            result['folds_committed']=len(folds)
            retire_view(view,rows,owned);budget.save(job/'RETIRED.json',{'owned_view_retired_after_job_absence':True,'commit_sha256':previous})
            lib=None
        need(capture(out/'program.py',PROGRAM_CAP,program_pin)==program_body,'Same program through all five jobs')
        raw=assemble(folds,arm,method,cohort,interface);budget.write(out/'submission.json',raw)
        before(end);result.update(success=True,submission=identity(raw),commit_chain=commits,
            all_five_jobs_closed=True,all_transient_views_retired=True,complete_five_mouse_schema_admitted=True)
    except BaseException as error:
        result.update(success=False,error_type=type(error).__name__ if type(error).__name__ in
             ('ValueError','TypeError','OSError','TimeoutError','MemoryError','OverflowError','FileNotFoundError') else 'Exception')
    finally:
        if ARMED:signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        if lib is not None:
            cleanup=[]
            for engine in reversed(lib['engines']):
                engine.end=end-1
                for row in reversed(engine.owned):cleanup.append(engine.cleanup(row['kind'],row['name']))
            result['failure_cleanup']=cleanup
        result.update(elapsed_seconds=time.monotonic()-started,reserved_read_bytes=budget.reads,
                      cumulative_write_bytes=budget.written,external_natural_zero_required=True)
        result['success']=bool(result['success'] and result['elapsed_seconds']<WHOLE)
        budget.save(out/'ATTEMPT.json',result,100000)
        if result['success']:
            before(end);budget.save(out/'COMPLETION.json',{'schema':'unitmatch_five_job_completion_v1',
                'attempt':identity(capture(out/'ATTEMPT.json',100000)),'seal':identity(capture(out/'SEAL.json',32768)),
                'submission':result['submission'],'full_cohort':list(MICE),'trusted_job_commit_chain':commits,
                'private_grade_or_native_baseline_performed':False,'external_natural_zero_required':True},32768);before(end)
    return result


def emit(value,end):
    body=encoded(value);need(len(body)<=4096,'Bounded terminal')
    before(end);blocking=os.get_blocking(1);os.set_blocking(1,False)
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(1,selectors.EVENT_WRITE);view=memoryview(body)
            while view:
                before(end)
                if not ready.select(min(.1,end-time.monotonic())):continue
                try:n=os.write(1,view)
                except BlockingIOError:continue
                need(n>0,'Terminal write');view=view[n:]
    finally:os.set_blocking(1,blocking)


def main():
    global ARMED
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['plan','run']);p.add_argument('--package',type=Path,required=True)
    p.add_argument('--source-sha256',required=True);p.add_argument('--view',choices=['A','B'],required=True)
    p.add_argument('--program',type=Path);p.add_argument('--method-name');p.add_argument('--output',type=Path)
    p.add_argument('--other-bytes',type=int);p.add_argument('--docker',default='/usr/local/bin/docker')
    p.add_argument('--docker-host');p.add_argument('--docker-config',type=Path);a=p.parse_args()
    if a.mode=='plan':
        _,packet,_,_,stage=closure(HERE,a.source_sha256,a.package)
        print(json.dumps({'task_id':TASK,'view':a.view,'held_mice':MICE,'program_bytes_cap':PROGRAM_CAP,
            'fold_bytes_cap':FOLD_CAP,'final_artifact_bytes_cap':FINAL_CAP,'whole_seconds':WHOLE,
            'per_fold_input_bytes':[sum(r['bytes'] for r in stage.selected(packet['files'],a.view,m)) for m in MICE],
            'candidate_seconds':20,'isolated_fresh_jobs':5,'runtime_qualified':False,'actual_run_selected':False}));return 0
    need(a.program is not None and a.output is not None and a.method_name is not None and a.other_bytes is not None,'Explicit selected run operands')
    need(a.docker_host is not None and a.docker_host.startswith('unix://') and a.docker_config is not None,'Explicit local daemon/config')
    env=dict(os.environ)
    for key in ('DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(key,None)
    env['DOCKER_HOST']=a.docker_host;env['DOCKER_CONFIG']=str(ordinary(a.docker_config));binary=str(ordinary(a.docker))
    def alarm(*unused):raise TimeoutError('Whole work cutoff preserving cleanup')
    old={sig:signal.signal(sig,alarm) for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    before(ORIGIN+WHOLE-60);ARMED=True
    signal.setitimer(signal.ITIMER_REAL,ORIGIN+WHOLE-60-time.monotonic());code=2
    try:
        r=execute(HERE,a.package,a.program,a.output,a.source_sha256,binary,env,a.view,a.method_name,a.other_bytes)
        before(ORIGIN+WHOLE);emit({'success':r['success'],'folds_committed':r['folds_committed'],
             'private_grade_or_native_baseline_performed':False},ORIGIN+WHOLE);before(ORIGIN+WHOLE)
        code=0 if r['success'] else 2
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,handler in old.items():signal.signal(sig,handler)
        ARMED=False
    return code if time.monotonic()<ORIGIN+WHOLE else 2


if __name__=='__main__':raise SystemExit(main())
