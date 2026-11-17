"""Isolated campaign entry for the complete FIND036 native/held A/B programme.

No qualification or external natural-closure evidence is manufactured here.
"""
import time
ORIGIN = time.monotonic()
import signal
INITIAL = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
CLOCK_OWNED = False
OUTER = 120


def expired(*_):
    raise TimeoutError('FIND036 central original clock')


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
RELATIVE = Path('authoring/delivery-20261105/common/remaining-builds-wave20/paper-program-g/central-integration')
TASK = 'PAPER-FIND-036'
TARGET = 'benchmarks/neuroscience/foraging-decision-paper/manifest.json'
BINDING_PIN = {'bytes': 1171, 'sha256': 'ac76336c6e14d85f6cdafc5df415baa25b356571667cd415cd7e93259755c08c'}
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
    gate=module('_foraging_registered_campaign',repo/b['central_tools']['neurobench_campaign.py']['path'],tools['neurobench_campaign.py'])
    doc=parse(io.capture(repo/TARGET,cap=262144))
    need(doc.get('id')==TASK,'exact registered task')
    need(gate.verified_program_runtime(repo/TARGET,doc,repo),
         'Program runner has no separate passing qualification; score verification is insufficient')
    meta=doc['program_execution'];registered,wrapper=gate._program_entry(meta,repo)
    need(wrapper==HERE/'entry.py','registered exact complete FIND036 wrapper')
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
    need(parent['schema']=='foraging_program_source_v1' and parent['task_id']==TASK
         and type(rows)is dict and len(rows)==37,'complete unchanged37-member production source')
    bodies={}
    for name,d in rows.items():
        rel=str(Path(b['parent_module_root'])/name)
        need(freeze['files'].get(rel)==d,'every parent member independently qualified')
        bodies[name]=io.capture(repo/rel,d,16*1024**2)
    q=meta['verification']
    qualified=parse(io.capture(repo/q['qualification_path'],{'bytes':(repo/q['qualification_path']).stat().st_size,'sha256':q['qualification_sha256']},2*1024**2))
    return {'bindings':b,'manifest':pin(own_raw),'freeze':pin(freeze_raw),
            'qualification_sha256':q['qualification_sha256'],'profile':qualified.get('foraging_full_runtime_profile'),
            'parent_manifest':parent_raw,'parent_bodies':bodies,'own_bodies':own_bodies}


def typed_equal(a,b):
    if type(a)is not type(b):return False
    if type(a)is dict:return set(a)==set(b) and all(typed_equal(a[k],b[k])for k in a)
    if type(a)is list:return len(a)==len(b) and all(typed_equal(x,y)for x,y in zip(a,b))
    return a==b


def limits(v):
    keys={'read_bytes','write_bytes','retained_bytes','other_future_bytes','free_floor_bytes','wall_seconds'}
    need(type(v)is dict and set(v)==keys,'exact original budget fields')
    for k in keys-{'wall_seconds'}:need(type(v[k])is int and v[k]>=(0 if k=='other_future_bytes' else 1),'integer original budget '+k)
    need(type(v['wall_seconds'])in(int,float) and math.isfinite(v['wall_seconds']) and v['wall_seconds']>0,'positive finite original wall')
    return v


def bind(io,repo,program,review,output,other,q):
    """Authenticated root metadata and four sources; no prepared/numeric operands."""
    need(type(other)is int and other>=0,'nonnegative standing reserve')
    raw=io.capture(review,cap=32768);r=parse(raw)
    keys={'schema','task_id','selected','exclusive_operator_custody','source_manifest','source_freeze',
          'qualification_sha256','bundle','work','output','other_future_bytes','runtime_profile',
          'protected_evaluation_deferred','external_final_exit_observer_required'}
    need(type(r)is dict and set(r)==keys and r['schema']=='foraging_central_authorization_v1' and r['task_id']==TASK,'exact independent central authority')
    need(all(r[k]is True for k in ('selected','exclusive_operator_custody','protected_evaluation_deferred','external_final_exit_observer_required')),'complete operation authority; no automatic grade')
    need(typed_equal(r['source_manifest'],q['manifest']) and typed_equal(r['source_freeze'],q['freeze'])
         and r['qualification_sha256']==q['qualification_sha256'],'qualified exact source and freeze')
    out=ordinary(output)
    need(type(r['output'])is str and out==ordinary(r['output']) and not out.exists() and out.parent.is_dir(),'root-selected fresh output')
    for p in (review,program):need(not ordinary(p).is_relative_to(out),'original authority outside output')
    descriptor(r['bundle'],65536);descriptor(r['work'],2*1024**2)
    need(ordinary(r['work']['path'])==ordinary(repo/'authoring/delivery-20261105/WORK_ASSIGNMENTS.json'),'exact current WORK path')
    need(ordinary(program)==ordinary(r['bundle']['path']),'program operand is the selected four-program bundle')
    workraw=io.capture(r['work']['path'],r['work'],2*1024**2);work=parse(workraw)
    current=work['latest_construction_state']['global_future_bytes']
    need(type(current)is int and type(r['other_future_bytes'])is int and current==other==r['other_future_bytes'],'current standing future reserve')
    bundleraw=io.capture(program,r['bundle'],65536);bundle=parse(bundleraw)
    need(type(bundle)is dict and set(bundle)=={'schema','task_id','observer_envelope'}
         and bundle['schema']=='foraging_central_four_program_bundle_v1' and bundle['task_id']==TASK,'exact whole-program bundle')
    envdesc=descriptor(bundle['observer_envelope'],1048576)
    need(not ordinary(envdesc['path']).is_relative_to(out),'original envelope outside output')
    envraw=io.capture(envdesc['path'],envdesc);env=parse(envraw)
    ek={'schema','task_id','outer_limits','metadata_cap_bytes','controller_selection','root_source','source_manifest','outer_control'}
    need(type(env)is dict and set(env)==ek and env['schema']=='foraging_outer_selection_v1' and env['task_id']==TASK,'original observer envelope')
    parent=q['bindings']['parent_manifest'];source={'path':str(repo/parent['path']),**{k:parent[k]for k in('bytes','sha256')}}
    need(typed_equal(env['source_manifest'],source) and ordinary(env['root_source'])==repo/q['bindings']['parent_module_root'],'original complete source selection')
    need(ordinary(env['outer_control'])==out/'observer','exact future observer ownership')
    opdesc=descriptor(env['controller_selection'],1048576)
    need(not ordinary(opdesc['path']).is_relative_to(out),'original controller selection outside output')
    opraw=io.capture(opdesc['path'],opdesc);op=parse(opraw)
    need(op.get('schema')=='foraging_full40_operation_v1' and op.get('task_id')==TASK,'complete full40 controller')
    need(all(op.get(k)is True for k in ('selected_by_root','native_linux_host','exclusive_operator_custody','source_environment_qualified'))
         and op.get('source_qualification_inherited')is False,'independent original operation qualification')
    need(typed_equal(op['source_manifest'],source) and op['root_source']==env['root_source'] and ordinary(op['output'])==out/'work','same original source and controller output')
    controller=limits(op['controller_limits']);outer=limits(env['outer_limits'])
    need(controller['wall_seconds']<outer['wall_seconds'] and time.monotonic()<ORIGIN+min(120,controller['wall_seconds']),'original startup and closure reserve')
    need(controller['other_future_bytes']==other+outer['retained_bytes']+ADAPTER_RETAINED
         and outer['other_future_bytes']==other+controller['retained_bytes']+ADAPTER_RETAINED,'full cross-role retention reservations; no double spending')
    cap=env['metadata_cap_bytes'];need(type(cap)is int and cap>=1048576 and cap==op['metadata_cap_bytes']
         and cap<=min(controller['read_bytes'],outer['read_bytes'],outer['retained_bytes']),'qualified complete receipt capacity')
    profile=r['runtime_profile'];need(type(profile)is dict and typed_equal(profile,q['profile']),'independent complete environment profile')
    pk={'schema','host_python','environment','images','host_versions','container_versions','phase_profile',
        'initial_interpreter_startup_reviewed','child_site_startup_reviewed','physical_capacity_reviewed',
        'host_address_space_bytes','receipt_read_bytes','disk_floor_bytes'}
    need(set(profile)==pk and profile['schema']=='foraging_full_runtime_environment_v1','exact full host/child runtime profile')
    need(all(profile[k]is True for k in ('initial_interpreter_startup_reviewed','child_site_startup_reviewed','physical_capacity_reviewed')),'independent startup/site/whole-host capacity qualification')
    for k in ('images','host_versions','container_versions'):
        need(typed_equal(profile[k],op[k]),'original environment binding '+k)
    need(typed_equal(profile['phase_profile'],op['profile']),'matched original native resource profile')
    for k in ('host_address_space_bytes','receipt_read_bytes','disk_floor_bytes'):
        need(type(profile[k])is int and profile[k]>0,'explicit qualified '+k)
    # OUTER, DISPATCH, derived selection, COLLECTION and COMMITMENT each <=cap;
    # all four committed source programs retain their original8MiB domains.
    need(profile['receipt_read_bytes']>=5*(cap+1)+4*(8*1024**2+1),'separate complete receipt plus source read budget')
    descriptor(profile['environment'],2*1024**2);io.capture(profile['environment']['path'],profile['environment'],2*1024**2)
    host=descriptor(profile['host_python'],64*1024**2)
    need(ordinary(sys.executable)==ordinary(host['path']),'qualified exact current interpreter')
    io.capture(host['path'],host,64*1024**2)
    pairdesc=descriptor(op['paired_authoring'],1048576)
    need(not ordinary(pairdesc['path']).is_relative_to(out),'original four-program pair outside output')
    pairraw=io.capture(pairdesc['path'],pairdesc);pair=parse(pairraw)
    need(pair['schema']=='foraging_four_program_pair_v1' and pair['task_id']==TASK and set(pair['programs'])=={'A','B'},'four original program definitions')
    need(pair['separate_contexts_attested']is True and pair['numeric_exposure_before_freeze']is False and pair['cross_program_feedback']is False,'independent context history explicitly attested, not proven')
    binding=parse(q['parent_bodies']['BINDING.json']);common=binding['common_static_paper_materials']
    seen=set();paths=set();programs={}
    for arm in ('A','B'):
        need(set(pair['programs'][arm])=={'native','improvement'},'distinct native/improvement programs')
        expected=[{'target':x['target'],'bytes':x['bytes'],'sha256':x['sha256']}for x in common]
        if arm=='B':expected += [{'target':x['target'],'bytes':x['bytes'],'sha256':x['sha256']}for x in binding['author_files']]
        programs[arm]={}
        for purpose in ('native','improvement'):
            v=pair['programs'][arm][purpose];ctx=v['context_id']
            need(type(ctx)is str and bool(ctx) and ctx not in seen,'four distinct authoring contexts')
            need(v['image']==op['images'][arm] and v['authoring_protocol']==pair['authoring_protocol']
                 and v['numeric_inputs_seen']is False and v['operator_material_seen']is False,'matched authoring protocol without privileged input')
            need(typed_equal(v['visible_materials'],expected) and v['interface_sha256']==pin(q['parent_bodies']['CANDIDATE_ABI.md'])['sha256'],'exact common paper and B-only relevant author sources')
            d=descriptor(v['program'],8*1024**2);path=ordinary(d['path'])
            need(path not in paths and not path.is_relative_to(out),'four distinct source paths outside output')
            body=io.capture(path,d,8*1024**2);need('\0'not in body.decode('utf8'),'original UTF8 source domain')
            programs[arm][purpose]={'context_id':ctx,'program':d};seen.add(ctx);paths.add(path)
    # Preparations/labels are descriptors only here. Original controller admits
    # all four programmes before opening any prepared numeric views.
    for key in ('prepared_authority','paper_material_admission'):descriptor(op[key],cap)
    retained=controller['retained_bytes']+outer['retained_bytes']+ADAPTER_RETAINED
    floor=max(profile['disk_floor_bytes'],controller['free_floor_bytes'],outer['free_floor_bytes'])
    need(shutil.disk_usage(out.parent).free>=floor+other+retained,'full-role prospective retention without small proxy')
    return {'review':pin(raw),'bundle':pin(bundleraw),'work':pin(workraw),'envelope':pin(envraw),
            'envelope_value':env,'operation':pin(opraw),'operation_value':op,'pair':pin(pairraw),
            'programs':programs,'profile':profile,'other_future_bytes':other}


def make_directory(path):
    p=ordinary(path);need(p.parent.is_dir() and not p.exists(),'fresh owned directory with existing parent')
    p.mkdir(mode=0o700);sync(p);sync(p.parent)


def clone_parent(io,out,q):
    root=out/'source';make_directory(root)
    for name,body in sorted(q['parent_bodies'].items()):
        relative=Path(name);need(not relative.is_absolute() and '..'not in relative.parts,'captured relative source path')
        parent=root
        for part in relative.parts[:-1]:
            parent=parent/part
            if not parent.exists():make_directory(parent)
        io.save(root/relative,body)
    io.save(root/'SOURCE_MANIFEST.json',q['parent_manifest'])
    for directory in sorted([root,*[x for x in root.rglob('*')if x.is_dir()]],key=lambda x:len(x.parts),reverse=True):
        os.chmod(directory,0o500);sync(directory)
    sync(root.parent);return root


def relocate(bound,source,out,q):
    """Only explicit source locators change; science and resource fields do not."""
    parent_pin=pin(q['parent_manifest'])
    op={**bound['operation_value'],'root_source':str(source),
        'source_manifest':{'path':str(source/'SOURCE_MANIFEST.json'),**parent_pin}}
    opraw=encode(op);opdesc={'path':str(out/'CONTROLLER_SELECTION.json'),**pin(opraw)}
    env={**bound['envelope_value'],'root_source':str(source),'source_manifest':op['source_manifest'],
         'controller_selection':opdesc}
    return opraw,encode(env)


def invoke(io,out,bound,q):
    """Concrete unchanged adapter -> observe -> controller -> native Provider."""
    global OUTER
    op=bound['operation_value'];env=bound['envelope_value'];OUTER=env['outer_limits']['wall_seconds'];end=ORIGIN+OUTER
    need(CLOCK_OWNED and signal.getsignal(signal.SIGALRM)is expired and time.monotonic()<ORIGIN+120,'owned original startup clock')
    signal.setitimer(signal.ITIMER_REAL,max(.000001,end-time.monotonic()))
    import resource
    memory=bound['profile']['host_address_space_bytes'];_,hard=resource.getrlimit(resource.RLIMIT_AS)
    need(hard==resource.RLIM_INFINITY or hard>=memory,'qualified host/child address-space ceiling supported')
    resource.setrlimit(resource.RLIMIT_AS,(memory,hard))
    out=ordinary(out);make_directory(out);source=clone_parent(io,out,q)
    opraw,envraw=relocate(bound,source,out,q)
    io.save(out/'CONTROLLER_SELECTION.json',opraw);io.save(out/'OBSERVER_ENVELOPE.json',envraw)
    commitments={k:v for k,v in bound.items()if k not in ('envelope_value','operation_value','profile')}
    commitments['source_relocation']={'original_envelope':bound['envelope'],'original_controller':bound['operation'],
        'derived_envelope':pin(envraw),'derived_controller':pin(opraw),
        'controller_only_delta':['root_source','source_manifest.path'],
        'envelope_only_delta':['root_source','source_manifest.path','controller_selection']}
    io.save(out/'ADAPTER_COMMITMENTS.json',encode(commitments))
    roots={Path(n).parts[0].removesuffix('.py')for n in q['parent_bodies']if n.endswith('.py')}
    need(not any(n.split('.')[0]in roots for n in sys.modules),'fresh captured-source module namespace')
    previous=list(sys.path);primary=None
    try:
        sys.path.insert(0,str(source));adapter=importlib.import_module('adapter')
        need(ordinary(adapter.__file__)==source/'adapter.py','captured original adapter source')
        result=adapter.dispatch('run',str(out/'OBSERVER_ENVELOPE.json'),pin(envraw)['sha256'],ORIGIN)
        checker=module('_foraging_central_receipt',HERE/'receipt_check.py',q['own_bodies']['receipt_check.py'])
        receipt_io=IO(bound['profile']['receipt_read_bytes'])
        summary=checker.capture_and_validate(receipt_io,out,result,bound,q,parse(opraw),parse(envraw),
             ORIGIN,sys.modules['observe'].validate_collection)
    except BaseException as error:primary=error;raise
    finally:
        errors=[]
        try:sys.path[:]=previous
        except BaseException as error:errors.append(type(error).__name__)
        for name in list(sys.modules):
            if name.split('.')[0]in roots:
                try:del sys.modules[name]
                except BaseException as error:errors.append(type(error).__name__)
        if errors:
            if primary is not None:primary.add_note('Captured namespace restoration uncertainty: '+','.join(errors))
            else:raise RuntimeError('Captured namespace restoration uncertainty: '+','.join(errors))
    need(time.monotonic()<end and signal.getsignal(signal.SIGALRM)is expired,'unchanged original clock after observer return')
    io.save(out/'ADAPTER_RESULT.json',encode({'schema':'foraging_central_dispatch_result_v1','task_id':TASK,
        'source_manifest':q['manifest'],'source_freeze':q['freeze'],'parent_source':pin(q['parent_manifest']),
        'original_envelope':bound['envelope'],'original_controller':bound['operation'],
        'derived_envelope':pin(envraw),'derived_controller':pin(opraw),'original_origin':ORIGIN,'original_deadline':end,
        'observer_result':result,'complete_collection_metadata_checks':summary,
        'protected_grade_called':False,'protected_grade_requires_separate_future_authority':True,
        'result_provisional_until_external_adapter_natural_exit':True,'adapter_final_exit_observed':False,
        'runtime_qualified':False,'scientific_qualified':False,'whole_paper_reproduced':False,
        'automatic_retry_authorized':False,'forced_stop_host_and_daemon_custody':'unknown',
        'adapter_source_operand_read_bytes':io.read,'separate_receipt_read_bytes':receipt_io.read,
        'central_gate_source_derived_read_ceiling_bytes':128*1024**2,'adapter_metadata_written_before_result':io.written}))
    need(time.monotonic()<end,'all publication before original operation cutoff');return 0


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
    need(time.monotonic()<ORIGIN+OUTER,'actual final completion after independent cleanup')
    raise SystemExit(result)
