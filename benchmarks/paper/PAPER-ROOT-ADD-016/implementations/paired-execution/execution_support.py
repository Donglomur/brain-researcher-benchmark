"""Cardiac A41/B46 binding to unchanged protected producer/collector modules."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

LOCAL = Path(__file__).resolve().parent
ROOT = LOCAL.parents[4]
HERE = LOCAL/'protected'
DEPENDENCIES = ROOT/'benchmarks/integrity/current-closures/cardiac-paired-execution/DEPENDENCIES.json'
TRANSPORT = 'benchmarks/neural/NEURAL-095/implementations/neural-095-four-cell-runner/source/'
SHARED = ROOT/TRANSPORT/'authoring/shared-program-runner-v2'
ID = 'PAPER-ROOT-ADD-016'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
PAIR_REL = 'benchmarks/paper/PAPER-ROOT-ADD-016/implementations/matched-artifacts/paired.py'
_BINDING = None
_API = None
_PAIR = None
_ALLOWED = set()

def need(ok, text):
    if not ok: raise ValueError(text)

def unlinked(path):
    path = Path(path).absolute()
    need('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)), 'Unlinked canonical path')
    return path

def ordinary(path, cap=262144):
    path = unlinked(path)
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        before = os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap, 'Bounded single-link source/metadata')
        body=f.read(cap+1); after=os.fstat(f.fileno()); named=path.lstat()
    fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
    need(len(body)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields), 'Stable complete source/metadata')
    return body

def pin(body): return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
def encode(value): return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def decode(body):
    def unique(rows):
        out={}
        for k,v in rows:
            need(k not in out,'Duplicate metadata key');out[k]=v
        return out
    return json.loads(body,object_pairs_hook=unique,parse_constant=lambda x:need(False,'Nonfinite metadata'))
def read(path, cap=262144): return decode(ordinary(path,cap))
def save(path, value, budget, cap=250000, private=False):
    body=encode(value);need(len(body)<=cap,'Complete bounded receipt')
    budget.write(path,body,receipt=True,mode=0o600 if private else 0o444)
    return pin(body)['sha256']

def source(rel):
    p=Path(rel);need(not p.is_absolute() and '..' not in p.parts and p.as_posix()==rel,'Exact repository source')
    rows=read(DEPENDENCIES)['files'];need(rel in rows,'Declared source dependency')
    body=ordinary(ROOT/p);need(pin(body)==rows[rel],'Frozen source dependency')
    return body

def module(name,rel):
    body=source(rel);path=ROOT/rel
    if name in sys.modules:
        need(getattr(sys.modules[name],'__file__',None)==str(path),'Exact module namespace')
        return sys.modules[name]
    out=types.ModuleType(name);out.__file__=str(path);out.__package__='';sys.modules[name]=out
    try:exec(compile(body,str(path),'exec'),out.__dict__)
    except BaseException:sys.modules.pop(name,None);raise
    return out

def bind_packet(binding):
    """Exact operator metadata only; never opens the private target."""
    global _PAIR, _BINDING
    need(type(binding) is dict and set(binding)=={'operands','reference_binding'},'Exact public operand binding')
    operands=unlinked(binding['operands']);row=binding['reference_binding']
    need(type(row) is dict and set(row)=={'path','bytes','sha256'},'Exact reference metadata descriptor')
    raw=ordinary(row['path'],20000)
    need(pin(raw)=={k:row[k] for k in ('bytes','sha256')},'Reference binding metadata unchanged')
    if _BINDING is not None:
        need(binding==_BINDING,'One immutable packet binding per process')
        return _PAIR
    p=module('_cardiac_current_pair',PAIR_REL)
    _PAIR=p.configured(operands,unlinked(row['path']))
    _BINDING=decode(encode(binding))
    return _PAIR

def packet():
    need(_PAIR is not None and _BINDING is not None,'Explicit admitted operator packet metadata required')
    return _PAIR

def expected_unit(pair_root,condition):
    p=packet();pair_root=unlinked(pair_root);receipt=p.pair(pair_root)
    need(condition in ('A','B'),'One exact paired condition')
    members=p.members(condition)
    need(len(members)==(41 if condition=='A' else 46),'Current complete packet cardinality')
    need(all(Path(n).name not in ('model.py','posterior_summary.py') for n in members),'No developer numerical helpers')
    inputs=[]
    for name,item in sorted(members.items()):
        path=unlinked(pair_root/condition/name);_ALLOWED.add(path)
        inputs.append({'path':str(path),'bytes':item['bytes'],'sha256':item['sha256'],'mount_destination':'/input/'+name})
    return {'unit_id':condition,'candidate_seconds':120,'output_filename':'summary.json','max_output_bytes':200000,'public_inputs':inputs}

def repo(value):
    path=Path(value)
    if not path.is_absolute():return unlinked(ROOT/path)
    path=unlinked(path);need(path in _ALLOWED,'Only bound current packet files may be external')
    return path

def public_file_cap(asset):
    need(repo(asset['path']) in _ALLOWED and asset['mount_destination'].startswith('/input/'),'Exact public packet member')
    need(Path(asset['mount_destination']).name not in ('model.py','posterior_summary.py'),'No developer numerical helper')
    return 42000000 if asset['mount_destination'].endswith('.whl') else 600000

def runtime_manifest(run):
    run=unlinked(run);raw=ordinary(run/'runtime_manifest.json',32768);commit=read(run/'runtime_manifest_commit.json')
    need(commit=={'manifest':pin(raw),'before_any_Docker_resource_creation':True},'Pre-resource manifest commitment')
    m=decode(raw);need(set(m)=={'candidate_id','condition','pair_root','pair_receipt','program_path','program_sha256','unit','packet_binding','docker'},'Exact paired runtime manifest')
    bind_packet(m['packet_binding'])
    configure_transport(m['docker'])
    need(m['candidate_id']==ID and m['condition'] in ('A','B') and m['program_path']==str(run/'program.py'),'Captured program and condition')
    need(pin(ordinary(Path(m['pair_root'])/'receipt.json',100000))==m['pair_receipt'],'Exact physical pair receipt')
    need(m['unit']==expected_unit(m['pair_root'],m['condition']),'Current complete A/B unit identity')
    need(pin(ordinary(run/'program.py',131072))['sha256']==m['program_sha256'],'Committed program unchanged')
    return m

def admit_unit(unit,program_sha,run=None):
    need(run is not None,'Owned arm root required');m=runtime_manifest(run)
    need(unit==m['unit'] and program_sha==m['program_sha256'],'Exact program/current packet admission')
    for asset in unit['public_inputs']:public_file_cap(asset)

def verify_grade_config(*unused):raise ValueError('No per-arm private grading in paired execution')
def worker_bindings(*unused):raise ValueError('No per-arm private mounts in paired execution')

def api():
    global _API
    if _API is not None:return _API
    current=sys.modules[__name__]
    need('support' not in sys.modules or sys.modules['support'] is current,'No unrelated support namespace')
    sys.modules['support']=current
    # Verify the complete explicitly frozen source closure before donor imports.
    for rel in read(DEPENDENCIES)['files']:source(rel)
    base='benchmarks/paper/PAPER-ROOT-ADD-016/implementations/paired-execution/protected/'
    module('files','benchmarks/paper/PAPER-ROOT-ADD-016/implementations/matched-artifacts/files.py')
    core=module('qualified_core',TRANSPORT+'authoring/shared-program-runner-v2/qualified_core.py')
    contract=module('contract_profile',base+'contract_profile.py')
    engine=module('engine_profile',base+'engine_profile.py')
    profile=module('profile',base+'profile.py')
    unit=module('_cardiac_paired_protected_unit',base+'unit.py')
    identity=module('_cardiac_paired_identity',base+'recovery_identity.py')
    from absence import absence
    need(contract.IMAGE==IMAGE,'Explicit385454 runtime; no9aaf substitution')
    _API={'BaseEngine':core.BaseEngine,'HostBudget':core.HostBudget,'ProfileEngine':engine.ProfileEngine,'contract_profile':contract,'runtime':profile.runtime,'run_unit':unit.run_unit,'absence':absence,'identity':identity}
    return _API

def recovery():
    api()
    return module('_cardiac_paired_strict_recovery','benchmarks/paper/PAPER-ROOT-ADD-016/implementations/paired-execution/protected/panel_recovery.py')

def configure_transport(value):
    """Use explicit operator bindings for the public transport placeholders."""
    api()
    need(type(value) is dict and set(value)=={'executable','config','host'},'Explicit Docker binding')
    executable=unlinked(value['executable']);config=unlinked(value['config'])
    need(executable.is_file() and config.is_dir(),'Existing operator Docker paths; no install')
    need(type(value['host']) is str and value['host'].startswith('unix:///') and
         not any(ord(c)<32 or ord(c) in (92,127) for c in value['host']),'Local explicit socket address')
    engine=sys.modules['engine']
    engine.DOCKER=str(executable)
    engine.ENV=dict(os.environ,DOCKER_CONFIG=str(config),DOCKER_HOST=value['host'])

def owner(review_path,entry):
    api()
    review=read(review_path)
    need(review.get('execution_authority') is True and review.get('operator_admission_reviewed') is True,'Operator selection remains required')
    row=review.get('ownership_admission')
    need(type(row) is dict and set(row)=={'path','bytes','sha256'},'Explicit current owner qualification evidence')
    raw=ordinary(row['path'],32768);need(pin(raw)=={k:row[k] for k in ('bytes','sha256')},'Pinned owner evidence')
    evidence=decode(raw)
    need(evidence.get('candidate_id')==ID and evidence.get('accepted') is True and
         evidence.get('source_closure')==pin(ordinary(DEPENDENCIES)) and
         evidence.get('entrypoint')==pin(ordinary(entry)) and
         evidence.get('controller')==review['controller'] and
         evidence.get('route_interrupt_qualification_current') is True,'Operator-reviewed current route evidence, not implicit historical adoption')
    configure_transport(review['docker'])
    module('trusted_controller','benchmarks/shared/program-execution/ownership-v4/trusted_controller.py')
    return module('_cardiac_public_owner','benchmarks/shared/program-execution/ownership-v4/process_owner.py')
