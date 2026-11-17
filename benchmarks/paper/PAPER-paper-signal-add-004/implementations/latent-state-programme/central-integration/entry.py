"""Isolated campaign entry for the complete OSL native/held A/B programme.

No qualification or external natural-closure evidence is manufactured here.
"""
import time
ORIGIN = time.monotonic()
import signal
INITIAL = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
CLOCK_OWNED = False
OUTER = 120


def expired(*_):
    raise TimeoutError('OSL central original clock')


def cleanup(primary=None):
    errors = []
    for action in [lambda: signal.setitimer(signal.ITIMER_REAL, 0)] + [
            lambda s=s,h=h: signal.signal(s,h) for s,h in INITIAL.items()]:
        try: action()
        except BaseException as error: errors.append(type(error).__name__)
    if errors:
        if primary is not None: primary.add_note('Independent alarm cleanup uncertainty: '+','.join(errors))
        else: raise RuntimeError('Independent alarm cleanup uncertainty: '+','.join(errors))


def enter_startup():
    global CLOCK_OWNED
    if signal.getitimer(signal.ITIMER_REAL) != (0.,0.):
        raise RuntimeError('fresh inactive timer required')
    try:
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, max(.001, ORIGIN+120-time.monotonic()))
    except BaseException as error:
        cleanup(error)
        raise
    CLOCK_OWNED = True


if __name__ == '__main__': enter_startup()
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import types
import importlib
import shutil
import re

HERE = Path(__file__).absolute().parent
RELATIVE = Path('authoring/delivery-20261105/common/remaining-builds-wave19/paper-program-c/central-integration')
TASK = 'PAPER-paper-signal-add-004'
TARGET = 'benchmarks/neuroscience/osl-dynamics-paper/manifest.json'
BINDING_PIN = {'bytes': 1168, 'sha256': 'd5a20c95b2bfa0693b5f20b6fadaf3071535dd2f9b7cfac62aba816f650a37ce'}
ADAPTER_RETAINED = 8*1024**2


def need(ok,message):
    if not ok: raise ValueError(message)


def pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            need(k not in out,'unique JSON keys');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'finite JSON'))


def encode(v):
    return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def descriptor(v,cap,*,path=True):
    need(type(v)is dict and set(v)==({'path','bytes','sha256'} if path else {'bytes','sha256'}),'exact descriptor')
    need(type(v['bytes'])is int and 0<v['bytes']<=cap and type(v['sha256'])is str
         and len(v['sha256'])==64 and all(x in '0123456789abcdef' for x in v['sha256']),'bounded SHA descriptor')
    if path: need(type(v['path'])is str and bool(v['path']),'literal descriptor path')
    return v


def ordinary(path):
    p=Path(path).absolute()
    need('..'not in p.parts and not any(x.is_symlink()for x in(p,*p.parents)),'ordinary absolute path chain')
    return p


class IO:
    def __init__(self, read_limit=256*1024**2): self.read=0;self.written=0;self.read_limit=read_limit
    def capture(self,path,expected=None,cap=1048576,*,allow_empty=False):
        p=ordinary(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
        try:
            a=os.fstat(fd)
            need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and (0<=a.st_size if allow_empty else 0<a.st_size) and a.st_size<=cap,'bounded ordinary single-link input')
            if expected is not None: need(a.st_size==expected['bytes'],'exact input size')
            self.read+=a.st_size+1;need(self.read<=self.read_limit,'separate adapter read cap')
            chunks=[];left=a.st_size
            while left:
                need(time.monotonic()<ORIGIN+OUTER,'original capture clock')
                part=os.read(fd,min(65536,left));need(bool(part),'complete input');chunks.append(part);left-=len(part)
            need(not os.read(fd,1),'input EOF')
            fields=lambda x:(x.st_dev,x.st_ino,x.st_mode,x.st_nlink,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
            need(fields(a)==fields(os.fstat(fd))==fields(p.lstat()),'stable input identity')
            raw=b''.join(chunks)
            if expected is not None:need(pin(raw)=={k:expected[k]for k in('bytes','sha256')},'full input SHA')
            return raw
        except BaseException as error:primary=error;raise
        finally:
            try:os.close(fd)
            except BaseException as error:
                if primary is None:raise
                primary.add_note('Input close uncertainty: '+type(error).__name__)
    def save(self,path,raw):
        self.written+=len(raw);need(self.written<=ADAPTER_RETAINED,'adapter metadata write cap')
        p=ordinary(path);need(p.parent.is_dir(),'existing durable adapter parent')
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);primary=None
        try:
            v=memoryview(raw)
            while v:
                need(time.monotonic()<ORIGIN+OUTER,'original publication clock')
                n=os.write(fd,v);need(n>0,'complete metadata write');v=v[n:]
            os.fsync(fd)
        except BaseException as error:primary=error;raise
        finally:
            try:os.close(fd)
            except BaseException as error:
                if primary is None:raise
                primary.add_note('Output close uncertainty: '+type(error).__name__)
        sync(p.parent);return pin(raw)


def sync(path):
    need(time.monotonic()<ORIGIN+OUTER,'original durability clock')
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);primary=None
    try:os.fsync(fd)
    except BaseException as error:primary=error;raise
    finally:
        try:os.close(fd)
        except BaseException as error:
            if primary is None:raise
            primary.add_note('Directory close uncertainty: '+type(error).__name__)
    need(time.monotonic()<ORIGIN+OUTER,'durability before original cutoff')


def module(name,path,body):
    value=types.ModuleType(name);value.__file__=str(path);sys.modules[name]=value
    exec(compile(body,str(path),'exec'),value.__dict__);return value


def source_and_qualification(io,repo):
    """Actual registered gate before even statting operation/candidate operands."""
    b=parse(io.capture(HERE/'BINDINGS.json',BINDING_PIN,8192))
    tools={k:io.capture(repo/d['path'],d,1048576) for k,d in b['central_tools'].items()}
    gate=module('_osl_registered_campaign',repo/b['central_tools']['neurobench_campaign.py']['path'],tools['neurobench_campaign.py'])
    doc=parse(io.capture(repo/TARGET,cap=262144))
    need(doc.get('id')==TASK,'exact registered task')
    need(gate.verified_program_runtime(repo/TARGET,doc,repo),
         'Program runner has no separate passing qualification; score verification is insufficient')
    meta=doc['program_execution'];registered,wrapper=gate._program_entry(meta,repo)
    need(wrapper==HERE/'entry.py','registered exact complete OSL wrapper')
    frozen=meta['source_freeze']
    freeze_raw=io.capture(repo/frozen['path'],{'bytes':(repo/frozen['path']).stat().st_size,'sha256':frozen['sha256']},262144)
    freeze=parse(freeze_raw);own_raw=io.capture(HERE/'SOURCE_MANIFEST.json',freeze['files'][str(RELATIVE/'SOURCE_MANIFEST.json')],262144)
    own=parse(own_raw);own_bodies={}
    for name,d in own['files'].items():
        need(freeze['files'].get(str(RELATIVE/name))==d,'own source is in independent qualified closure')
        own_bodies[name]=io.capture(HERE/name,d)
    for relative,d in parse(own_bodies['CAMPAIGN_SOURCE_CLOSURE.json'])['files'].items():
        need(freeze['files'].get(relative)==d,'every static campaign dependency is qualified')
    for d in b['central_tools'].values():
        need(freeze['files'].get(d['path'])=={k:d[k] for k in ('bytes','sha256')},'all central tools qualified')
    parent_raw=io.capture(repo/b['parent_manifest']['path'],b['parent_manifest'],262144)
    need(freeze['files'].get(b['parent_manifest']['path'])==pin(parent_raw),'parent manifest independently qualified')
    parent=parse(parent_raw);rows=parent['files']
    need(parent['schema']=='osl_complete_executable_source_v1' and len(rows)==42
         and len({x['path'] for x in rows})==42,'complete unchanged42-member production source')
    bodies={}
    for d in rows:
        rel=str(Path(b['parent_module_root'])/d['path']);expected={k:d[k] for k in ('bytes','sha256')}
        need(freeze['files'].get(rel)==expected,'every parent member independently qualified')
        bodies[d['path']]=io.capture(repo/rel,expected)
    q=meta['verification']
    qualified=parse(io.capture(repo/q['qualification_path'],{'bytes':(repo/q['qualification_path']).stat().st_size,'sha256':q['qualification_sha256']},2*1024**2))
    return {'bindings':b,'manifest':pin(own_raw),'freeze':pin(freeze_raw),
            'qualification_sha256':q['qualification_sha256'],'profile':qualified.get('osl_full_runtime_profile'),
            'parent_manifest':parent_raw,'parent_bodies':bodies,'own_bodies':own_bodies}


def bind(io,repo,program,review,output,other,q):
    """Root metadata and four independent contexts; no numeric data is opened."""
    need(type(other)is int and other>=0,'nonnegative external reserve')
    raw=io.capture(review,cap=32768);r=parse(raw)
    keys={'schema','task_id','selected','exclusive_operator_custody','source_manifest','source_freeze',
          'qualification_sha256','bundle','work','output','other_future_bytes','runtime_profile',
          'protected_final_assessment_authorized','external_final_exit_observer_required'}
    need(type(r)is dict and set(r)==keys and r['schema']=='osl_central_authorization_v1' and r['task_id']==TASK,'exact root authorization')
    need(all(r[k]is True for k in ('selected','exclusive_operator_custody','protected_final_assessment_authorized','external_final_exit_observer_required')),
         'explicit entire scientific operation and original final assessment authority')
    need(r['source_manifest']==q['manifest'] and r['source_freeze']==q['freeze']
         and r['qualification_sha256']==q['qualification_sha256'],'independent source and qualification joins')
    out=ordinary(output)
    need(type(r['output'])is str and out==ordinary(r['output']) and not out.exists() and out.parent.is_dir(),'exact fresh output')
    need(not ordinary(review).is_relative_to(out) and not ordinary(program).is_relative_to(out),'authority outside fresh output')
    descriptor(r['bundle'],65536);descriptor(r['work'],2*1024**2)
    need(ordinary(r['work']['path'])==ordinary(repo/'authoring/delivery-20261105/WORK_ASSIGNMENTS.json'),'exact fixed WORK descriptor')
    need(ordinary(program)==ordinary(r['bundle']['path']),'selected program operand is exact bundle')
    workraw=io.capture(r['work']['path'],r['work'],2*1024**2);work=parse(workraw)
    current=work['latest_construction_state']['global_future_bytes']
    need(type(current)is int and type(r['other_future_bytes'])is int and current==other==r['other_future_bytes'],'current complete global future reserve')
    bundleraw=io.capture(program,r['bundle'],65536);bundle=parse(bundleraw)
    need(type(bundle)is dict and set(bundle)=={'schema','task_id','operation','authorship'}
         and bundle['schema']=='osl_full_four_program_bundle_v1' and bundle['task_id']==TASK,'complete four-program operation bundle')
    descriptor(bundle['operation'],1048576)
    need(not ordinary(bundle['operation']['path']).is_relative_to(out),'original operation is outside fresh output')
    opraw=io.capture(bundle['operation']['path'],bundle['operation']);op=parse(opraw)
    need(op.get('schema')=='osl_complete_program_operation_v1' and op.get('task_id')==TASK
         and op.get('scientific_execution_authorized')is True and op.get('scientific_qualification')is False,
         'original separately authorized complete operation')
    need(op.get('exclusive_operator_custody')is True and op.get('native_linux_host')is True,'original native custody conditions')
    parent=q['bindings']['parent_manifest']
    need(op.get('source_manifest')=={'path':str(repo/parent['path']),'bytes':parent['bytes'],'sha256':parent['sha256']},'exact original executable manifest')
    need(set(op['programs'])=={'A','B'} and all(set(x)=={'native','held_hmm'} for x in op['programs'].values()),'four original candidate programme entries')
    profile=r['runtime_profile']
    need(type(profile)is dict and profile==q['profile'],'independently qualified full runtime profile')
    profile_keys={'schema','host_python','docker','images','boundaries','provider_source_pin','environment',
                  'initial_interpreter_startup_reviewed','physical_capacity_reviewed','adapter_host_memory_bytes',
                  'controller_host_memory_bytes','outer_receipt_max_bytes','receipt_read_bytes','disk_floor_bytes'}
    need(set(profile)==profile_keys and profile['schema']=='osl_full_runtime_environment_v1','exact qualified runtime profile')
    need(profile['initial_interpreter_startup_reviewed']is True and profile['physical_capacity_reviewed']is True,'qualified startup/whole-host capacity')
    for k in ('host_python','docker','images','boundaries'):
        need(profile[k]==op[k],'exact original environment '+k)
    need(profile['provider_source_pin']==op['engine_source_pin'],'exact actual transport identity')
    for k in ('adapter_host_memory_bytes','controller_host_memory_bytes','outer_receipt_max_bytes','receipt_read_bytes'):
        need(type(profile[k])is int and profile[k]>0,'positive qualified '+k)
    need(type(profile['disk_floor_bytes'])is int and profile['disk_floor_bytes']>=0,'explicit disk floor')
    need(profile['controller_host_memory_bytes']==op['host_memory_bytes'],'original controller memory cap')
    need(profile['outer_receipt_max_bytes']<=op['outer_write_bytes']
         and profile['receipt_read_bytes']>=3*profile['outer_receipt_max_bytes']+op['controller_log_bytes']+5,
         'separate full receipt, inner/controller and log read allocation')
    descriptor(profile['environment'],2*1024**2);io.capture(profile['environment']['path'],profile['environment'],2*1024**2)
    host=op['host_python'];need(set(host)=={'path','pin'},'original located interpreter')
    descriptor(host['pin'],64*1024**2,path=False)
    need(ordinary(sys.executable)==ordinary(host['path']),'exact qualified interpreter path')
    io.capture(sys.executable,host['pin'],64*1024**2)
    need(type(bundle['authorship'])is list and len(bundle['authorship'])==4,'all four independent authoring records')
    contexts=set();pairs=set();paths=set();authors=[]
    for located in bundle['authorship']:
        descriptor(located,32768);body=io.capture(located['path'],located,32768);v=parse(body)
        ak={'schema','task_id','context_id','role','family','program','access_condition','materials_sha256',
            'independent_context','no_other_candidate_outputs','no_native_to_held_feedback','no_operator_reference_access'}
        need(type(v)is dict and set(v)==ak and v['schema']=='osl_independent_authorship_v1' and v['task_id']==TASK,'exact authoring attestation')
        pair=(v['role'],v['family']);need(pair in {(a,f)for a in ('A','B')for f in ('native','held_hmm')} and pair not in pairs,'distinct original authoring role/family')
        need(type(v['context_id'])is str and re.fullmatch('[A-Za-z0-9._:-]{1,96}',v['context_id']) and v['context_id']not in contexts,'four distinct independent author contexts')
        need(all(v[k]is True for k in ('independent_context','no_other_candidate_outputs','no_native_to_held_feedback','no_operator_reference_access')),'independent source contexts without cross-family feedback')
        need(v['access_condition']==('paper_data' if v['role']=='A' else 'paper_data_author_code'),'correct paper/data/code access condition')
        need(type(v['materials_sha256'])is str and re.fullmatch('[a-f0-9]{64}',v['materials_sha256']),'source-bound authoring materials identity')
        item=op['programs'][v['role']][v['family']]
        need(v['program']==item and set(item)=={'path','pin'},'original frozen program descriptor')
        descriptor(item['pin'],1048576,path=False);path=ordinary(item['path'])
        need(path not in paths and not path.is_relative_to(out),'no reused program path or future output dependency')
        io.capture(path,item['pin'],1048576)
        contexts.add(v['context_id']);pairs.add(pair);paths.add(path)
        authors.append({'attestation':pin(body),'context_id':v['context_id'],'role':v['role'],'family':v['family'],'program':item})
    wall=op['limits']['wall_seconds']
    need(type(wall)in(int,float) and math.isfinite(wall) and wall>0 and time.monotonic()<ORIGIN+min(120,wall),'entire startup within original clock')
    retained=op['limits']['retained_bytes'];need(type(retained)is int and retained>0,'original full retained limit')
    need(shutil.disk_usage(out.parent).free>=profile['disk_floor_bytes']+other+retained+ADAPTER_RETAINED,'explicit complete prospective capacity')
    return {'review':pin(raw),'bundle':pin(bundleraw),'work':pin(workraw),'operation':pin(opraw),
            'operation_body':opraw,'operation_value':op,'authors':authors,'profile':profile,'other_future_bytes':other}


def make_directory(path):
    """Only a single bounded owned level at a time; persist its parent entry."""
    p=ordinary(path);need(p.parent.is_dir() and not p.exists(),'fresh owned directory with existing parent')
    p.mkdir(mode=0o700);sync(p);sync(p.parent)


def clone_parent(io,out,q):
    root=out/'source';make_directory(root)
    for name,body in sorted(q['parent_bodies'].items()):
        relative=Path(name);need(not relative.is_absolute() and '..' not in relative.parts,'exact captured source relative path')
        parent=root
        for part in relative.parts[:-1]:
            parent=parent/part
            if not parent.exists():make_directory(parent)
        io.save(root/relative,body)
    io.save(root/'EXECUTABLE_SOURCE_MANIFEST.json',q['parent_manifest'])
    for directory in sorted([root,*[x for x in root.rglob('*')if x.is_dir()]],key=lambda x:len(x.parts),reverse=True):
        os.chmod(directory,0o500);sync(directory)
    sync(root.parent);return root


def invoke(io,out,bound,q):
    """Concrete captured supervisor -> unchanged original controller/Provider."""
    global OUTER
    op=bound['operation_value'];OUTER=op['limits']['wall_seconds'];end=ORIGIN+OUTER
    need(CLOCK_OWNED and signal.getsignal(signal.SIGALRM)is expired and time.monotonic()<end,'owned original operation clock')
    signal.setitimer(signal.ITIMER_REAL,max(.000001,end-time.monotonic()))
    import resource
    memory=bound['profile']['adapter_host_memory_bytes'];_,hard=resource.getrlimit(resource.RLIMIT_AS)
    need(hard==resource.RLIM_INFINITY or hard>=max(memory,op['host_memory_bytes']),
         'inherited hard address-space cap supports both independently qualified host roles')
    # Preserve the inherited hard limit: the original supervisor's child must
    # still be able to install its separately selected controller soft/hard cap.
    resource.setrlimit(resource.RLIMIT_AS,(memory,hard))
    out=ordinary(out);make_directory(out)
    operation_path=out/'OPERATION.json';io.save(operation_path,bound['operation_body'])
    commitments={k:v for k,v in bound.items()if k not in ('operation_body','operation_value','profile')}
    io.save(out/'ADAPTER_COMMITMENTS.json',encode(commitments))
    source=clone_parent(io,out,q)
    roots={Path(n).parts[0].removesuffix('.py')for n in q['parent_bodies'] if n.endswith('.py')}
    need(not any(n.split('.')[0]in roots for n in sys.modules),'fresh host module namespace for exact captured source')
    prior_path=list(sys.path);primary=None
    try:
        sys.path.insert(0,str(source))
        supervisor=importlib.import_module('supervisor')
        need(ordinary(supervisor.__file__)==source/'supervisor.py','captured supervisor module location')
        # Literal existing API; BOOT default is deliberately unused.
        result=supervisor.run(str(operation_path),bound['operation'],str(out/'attempt'),origin=ORIGIN)
        receipt_io=IO(bound['profile']['receipt_read_bytes']);cap=bound['profile']['outer_receipt_max_bytes']
        descriptor(result,cap,path=False)
        outer_raw=receipt_io.capture(out/'attempt/OUTER_RECEIPT.json',result,cap);outer=parse(outer_raw)
        close_raw=receipt_io.capture(out/'attempt/CONTROLLER_CLOSE.json',outer['controller_close'],cap)
        inner_raw=receipt_io.capture(out/'attempt/work/INNER_RETURN.json',outer['inner_return']['pin'],cap)
        logs={name:pin(receipt_io.capture(out/'attempt'/(name+'.log'),d,op['controller_log_bytes'],allow_empty=True))
              for name,d in parse(close_raw)['logs'].items()}
        checker=module('_osl_central_receipt_checks',HERE/'receipt_check.py',q['own_bodies']['receipt_check.py'])
        core=sys.modules['core']
        expected=[j for factory in (core.native_jobs,core.held_jobs) for role in core.ROLES for j in factory(role)]
        summary=checker.validate(outer,parse(close_raw),parse(inner_raw),logs,expected,op,bound['operation'],ORIGIN,str(out/'attempt'))
    except BaseException as error:primary=error;raise
    finally:
        errors=[]
        try:sys.path[:]=prior_path
        except BaseException as error:errors.append(type(error).__name__)
        for name in list(sys.modules):
            if name.split('.')[0]in roots:
                try:del sys.modules[name]
                except BaseException as error:errors.append(type(error).__name__)
        if errors:
            if primary is not None:primary.add_note('Captured source namespace cleanup uncertainty: '+','.join(errors))
            else:raise RuntimeError('Captured source namespace cleanup uncertainty: '+','.join(errors))
    need(time.monotonic()<end and signal.getsignal(signal.SIGALRM)is expired,'original clock survives source return')
    io.save(out/'ADAPTER_RESULT.json',encode({'schema':'osl_central_dispatch_result_v1','task_id':TASK,
        'source_manifest':q['manifest'],'source_freeze':q['freeze'],'parent_source':pin(q['parent_manifest']),
        'operation':bound['operation'],'outer_receipt':result,'original_origin':ORIGIN,'original_deadline':end,
        'complete_original_receipt_checks':summary,'original_final_assessment_was_authorized':True,
        'result_provisional_until_external_adapter_natural_exit':True,'adapter_final_exit_observed':False,
        'runtime_qualified':False,'scientific_qualification':False,'whole_paper_reproduced':False,
        'automatic_retry_authorized':False,'forced_stop_host_and_daemon_custody':'unknown',
        'adapter_source_operand_read_bytes':io.read,'separate_receipt_read_bytes':receipt_io.read,
        'central_gate_source_derived_read_ceiling_bytes':128*1024**2,'adapter_metadata_written_before_result':io.written}))
    need(time.monotonic()<end,'all publication within original operation deadline');return 0


def main(argv=None):
    primary=None
    try:
        need(CLOCK_OWNED and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated owned-clock campaign launch')
        parser=argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument('--program',required=True);parser.add_argument('--output',required=True)
        parser.add_argument('--review',required=True);parser.add_argument('--other-reserve-bytes',required=True,type=int)
        args=parser.parse_args(argv);repo=HERE
        for _ in RELATIVE.parts:repo=repo.parent
        need(repo/RELATIVE==HERE,'exact repository source location')
        io=IO();q=source_and_qualification(io,repo)
        bound=bind(io,repo,args.program,args.review,args.output,args.other_reserve_bytes,q)
        return invoke(io,args.output,bound,q)
    except BaseException as error:primary=error;raise
    finally:
        if CLOCK_OWNED:cleanup(primary)


if __name__=='__main__':
    result=main()
    need(time.monotonic()<ORIGIN+OUTER,'actual final adapter completion after independent cleanup')
    raise SystemExit(result)


