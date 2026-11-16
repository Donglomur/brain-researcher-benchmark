"""Task-local operator admission. No candidate/science imports or Docker calls."""
from pathlib import Path
import hashlib,json,math,os,re,stat,types
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
ID='NEURAL-034';RUNTIME_ID='neural034_ordinary_completion_v1';SECONDS=480
OWN=16000000;MIN_OTHER=400000000
DYNAMIC={'path':'authoring/task-dynamic-capacity-20261103/shared/capacity.py','bytes':11272,'sha256':'69830afd10817893b9c1334d3dfeeb14c2bed6102375c4d270b70fa86f8bf227'}
COST={'path':'authoring/task-capacity-successors-20261102/astrocyte/ROOT_COST_RECONCILIATION_ADOPTION.json','bytes':875,'sha256':'943e17c5407fbf91b1038eb7bae63ec891356119f96f790641e8f9912d7a9968'}
BASELINE=2679.932040249051
HISTORICAL_SOURCE_FREEZE={'path': 'authoring/glial-context-v1/ordinary-completion-v1/SOURCE_FREEZE.json', 'bytes': 5621, 'sha256': '37d5797c474fa2f64e2bb7a1d27832b3fc94146e0ef3c8d95bfe16cef86cd84c'}
IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'

def need(ok,message):
    if not ok:raise ValueError(message)

def ordinary(path,cap):
    path=Path(path).absolute();need('..'not in path.parts and all(not x.is_symlink()for x in(path,*path.parents)),'Unlinked literal path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and 0<a.st_size<=cap,'Bounded ordinary single-link bytes')
        with os.fdopen(fd,'rb',closefd=False)as f:body=f.read(cap+1)
        b=os.fstat(fd);keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        need(len(body)==a.st_size and all(getattr(a,k)==getattr(b,k)for k in keys),'Stable captured bytes');return body
    finally:os.close(fd)

def decode(body):
    def pairs(rows):
        value={}
        for key,val in rows:need(key not in value,'Duplicate JSON key');value[key]=val
        return value
    return json.loads(body.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:need(False,'Nonfinite JSON'))

def descriptor(path,cap=2000000):
    path=Path(path).absolute();need(path.is_relative_to(ROOT),'Repository descriptor');body=ordinary(path,cap)
    return {'path':path.relative_to(ROOT).as_posix(),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def checked(pin,cap=2000000):
    need(type(pin)is dict and set(pin)=={'path','bytes','sha256'},'Exact descriptor')
    rel=pin['path'];need(type(rel)is str and len(rel)<=512 and not Path(rel).is_absolute()and '..'not in Path(rel).parts and Path(rel).as_posix()==rel and not any(x in rel for x in('\0','\r','\n')),'Canonical relative descriptor')
    need(type(pin['bytes'])is int and 0<pin['bytes']<=cap and type(pin['sha256'])is str and re.fullmatch('[0-9a-f]{64}',pin['sha256']),'Typed descriptor')
    body=ordinary(ROOT/rel,cap);need(len(body)==pin['bytes']and hashlib.sha256(body).hexdigest()==pin['sha256'],'Authenticated descriptor bytes');return body

def pinned(pin):return decode(checked(pin))

def module(path,body,values=None):
    m=types.ModuleType('_glial_'+Path(path).stem);m.__file__=str(path);m.__package__='';m.__dict__.update(values or {})
    exec(compile(body,str(path),'exec'),m.__dict__);return m

def source_gate(pin):
    need(pin['path']==(HERE/'SOURCE_FREEZE.json').relative_to(ROOT).as_posix(),'Current task source freeze')
    v=pinned(pin);need(v.get('schema')=='neural034_ordinary_source_v1'and v.get('candidate_id')==ID and v.get('execution_authority')is False,'Non-authorizing exact source hold')
    files=v['files'];need(type(files)is dict and 12<=len(files)<=100,'Bounded direct source roster')
    bodies={rel:checked({'path':rel,**p})for rel,p in files.items()}
    for name in ['run.py','scheduler.py','admission.py','runtime.py']:
        need((HERE/name).relative_to(ROOT).as_posix()in bodies,'Required entry source held')
    need(DYNAMIC['path']in bodies and hashlib.sha256(bodies[DYNAMIC['path']]).hexdigest()==DYNAMIC['sha256'],'Exact shared capacity helper')
    need(v.get('historical_source_freeze')==HISTORICAL_SOURCE_FREEZE,'Exact historical source lineage; not inherited execution authority')
    return v,bodies

def known_cost(pin,source_pin):
    prior=pinned(pin)
    if pin==COST:
        need(prior['schema']=='root-astrocyte-cost-reconciliation-adoption-v1'and prior['decision']=='adopt_explicit_disjoint_saved_receipt_reconciliation'and prior['execution_authority']is False and prior['known_source_family_seconds']==BASELINE,'Exact adopted family reconciliation')
        proposal=pinned(prior['proposal']);need(proposal['cost_family_id']=='astrocyte_source_family'and proposal['proposed_known_source_family_seconds']==BASELINE,'Adopted disjoint prefix');return BASELINE
    need(prior.get('candidate_id')==ID and prior.get('runtime_id')==RUNTIME_ID and prior.get('cost_family_id')=='astrocyte_source_family'and prior.get('source_freeze') in (source_pin,HISTORICAL_SOURCE_FREEZE),'Later closed same-runtime cost lineage')
    need(prior.get('all_owned_absent')is True and prior.get('all_process_groups_absent_and_reaped')is True and prior.get('all_owned_cli_processes_absent')is True and prior.get('controller_direct_handle_reaped')is True,'Prior failure or success is closed')
    need(prior.get('status')in('program_scored','invalid_unit_submission','output_boundary_rejected','candidate_program_failed','execution_failed_preserved'),'Typed prior outcome')
    before=prior['known_seconds_before'];after=prior['known_seconds_after']
    need(type(before)in(int,float)and math.isfinite(before)and before>=BASELINE and type(prior['charged_seconds'])is int and prior['charged_seconds']==SECONDS and type(after)in(int,float)and math.isfinite(after)and after==before+SECONDS,'Full additive prior allowance')
    return after

def runtime_environment(review):
    """Task-local explicit transport binding; no probe or admission is manufactured."""
    value=review.get('portable_runtime')
    need(type(value)is dict and set(value)=={'image','docker_binary','docker_host','qualification','qualified'},'Exact portable runtime binding')
    need(value['image']==IMAGE and value['qualified'] is True,'Same385454 runtime must be independently qualified')
    binary=value['docker_binary'];host=value['docker_host']
    need(type(binary)is str and Path(binary).is_absolute()and Path(binary).as_posix()==binary and '..'not in Path(binary).parts and not any(c in binary for c in ('\0','\r','\n')),'Explicit literal Docker binary')
    need(type(host)is str and host.startswith('unix:///')and not any(c in host for c in ('\0','\r','\n','?','#')),'Explicit local Engine socket; no implicit context')
    socket=host[len('unix://'):]
    need(Path(socket).as_posix()==socket and '..'not in Path(socket).parts,'Canonical Engine socket')
    need(os.environ.get('NEURAL034_DOCKER')==binary and os.environ.get('NEURAL034_DOCKER_HOST')==host,'Inherited transport equals exact operator review')
    need(not any(v for k,v in os.environ.items()if k.startswith('DOCKER_')and k not in ('DOCKER_HOST','DOCKER_CONFIG')),'No unbound inherited Docker override; host/config are explicitly replaced')
    evidence=pinned(value['qualification'])
    need(evidence.get('candidate_id')==ID and evidence.get('image')==IMAGE and evidence.get('docker_binary')==binary and evidence.get('docker_host')==host and evidence.get('qualified')is True,'External qualification must bind the same task/image/transport')
    return value


def authority(review_path,program,out,other):
    review_pin=descriptor(review_path,131072);r=pinned(review_pin)
    need(r.get('decision')=='go_neural034_ordinary_completion_v1'and r.get('reviewer')=='root'and r.get('candidate_id')==ID and r.get('execution_authorized')is True,'Explicit exact root attempt authority')
    need(r.get('latest_cost_confirmed')is True and r.get('no_active_same_family_stage')is True,'Root confirms latest closed shared family')
    runtime_environment(r)
    v,bodies=source_gate(r['source_freeze']);peer=pinned(r['independent_source_review'])
    need(peer.get('status')=='passed'and peer.get('findings')==[] and peer.get('source_freeze')==r['source_freeze'],'Independent exact source integration review')
    program=Path(program).absolute();out=Path(out).absolute();need(program.suffix=='.py'and r['program_source']==descriptor(program,65536),'Exact committed program source')
    ordinary(program,65536).decode('utf-8')
    need(r['output_path']==str(out)and out.is_relative_to(ROOT/'artifacts-build')and not out.exists()and all(not x.is_symlink()for x in(out,*out.parents)),'Fresh exact authorized output')
    need(type(other)is int and other>=MIN_OTHER and r['other_reserve_bytes']==other and type(r['other_reserve_bytes'])is int,'Actual complete non-image other reserve')
    a=pinned(r['budget_allocation']);need(a.get('candidate_id')==ID and a.get('runtime_id')==RUNTIME_ID and a.get('prospective')is True and a.get('status')=='allocated_before_dispatch'and a.get('output_path')==str(out),'Prospective attempt allocation')
    for key,val in [('whole_seconds',480),('work_seconds',420),('cleanup_seconds',60),('candidate_seconds_per_fold',20),('folds',7),('own_reserve_bytes',OWN),('other_reserve_bytes',other)]:
        need(type(r.get(key))is int and r[key]==val and type(a.get(key))is int and a[key]==val,'Fixed allocated '+key)
    need(r.get('other_reserves_exclude_images')is True and a.get('other_reserves_exclude_images')is True,'Full image census counted once')
    rows=r['other_reservations'];need(type(rows)is list and 1<=len(rows)<=32 and len(json.dumps(rows,ensure_ascii=True).encode())<=16384,'Bounded explicit non-image reservation roster')
    names=[];total=0
    for row in rows:
        need(set(row)=={'name','bytes','basis','evidence'}and type(row['name'])is str and row['name'].strip()and type(row['bytes'])is int and row['bytes']>0 and type(row['basis'])is str and 0<len(row['basis'])<=2000,'Typed active reservation')
        checked(row['evidence']);names.append(row['name']);total+=row['bytes']
    need(len(names)==len(set(names))and total==other and a.get('other_reservations')==rows,'Complete exact reservation sum')
    prior=known_cost(r['prior_receipt'],r['source_freeze'])
    need(type(r['known_seconds_before'])in(int,float)and not isinstance(r['known_seconds_before'],bool)and r['known_seconds_before']==prior and a['known_seconds_before']==prior and a['charged_seconds']==SECONDS and type(a['charged_seconds'])is int and a['known_seconds_after']==prior+SECONDS,'Current full allowance; no cost reset')
    cap=module(ROOT/DYNAMIC['path'],bodies[DYNAMIC['path']]);admitted=cap.validate(r,a,pinned,candidate_id=ID,own_reserve=OWN,minimum_other=MIN_OTHER)
    need(admitted['other_reserve_bytes']==other,'Nested dynamic reserve equals actual CLI reserve')
    return {'review_pin':review_pin,'source_freeze':r['source_freeze'],'budget_allocation':r['budget_allocation'],'prior_receipt':r['prior_receipt'],'known_seconds_before':prior,'known_seconds_after':prior+SECONDS,'dynamic_capacity':admitted,'program_source':r['program_source']},bodies,cap
