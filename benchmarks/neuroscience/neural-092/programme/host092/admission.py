"""Root-selected operands and real OS custody, without self-certifying evidence."""
import os,stat,sys,weakref
from pathlib import Path
from .storage import Store,Ledger,ErrorOwner,digest,decode,encode
from gain.cost import session_plan

PROFILE_FIELDS={'schema','run_id','packet_root','packet','source_root','source_files','candidate_root','candidate_files','rootfs','rootfs_manifest','runc','python','work_parent','cgroup_parent','limits','candidate_limits','control_seconds','wall_seconds','poll_seconds','runtime_output_bytes','external_memory_bytes','total_memory_bytes','io_limits','candidate_argv','observed_argv','binding_pins'}
LIMIT_FIELDS={'memory_bytes','pids','cpu_quota_us','cpu_period_us'}
class Selection:
    """Original loader-issued captured selection. Not native/science authority."""
    pass
_SELECTIONS=weakref.WeakKeyDictionary()
def selected_profile(selection):
    r=_SELECTIONS.get(selection)
    if r is None or r[0]!=os.getpid():raise RuntimeError('original root selection capture required')
    return validate_profile(decode(r[1]))
def validate_profile(p):
    if type(p)is not dict or set(p)!=PROFILE_FIELDS or p['schema']!='neural092_root_host_selection_v1':raise ValueError('closed independently selected host profile')
    import re
    if type(p['run_id'])is not str or not re.fullmatch('[a-z0-9][a-z0-9-]{1,47}',p['run_id']):raise ValueError('fresh fixed run ID')
    for k in ('control_seconds','wall_seconds','poll_seconds','runtime_output_bytes','total_memory_bytes'):
        if type(p[k])not in (int,float)or isinstance(p[k],bool)or not 0<p[k]<float('inf'):raise ValueError('independent positive '+k)
    if type(p['runtime_output_bytes'])is not int or type(p['total_memory_bytes'])is not int:raise ValueError('integer byte caps')
    for k in ('limits','candidate_limits'):
        if set(p[k])!=LIMIT_FIELDS or any(type(v)is not int or v<=0 for v in p[k].values()):raise ValueError('full kernel limits')
    if p['limits']['memory_bytes']!=p['total_memory_bytes']or p['candidate_limits']['memory_bytes']>p['total_memory_bytes']or p['candidate_limits']['pids']>p['limits']['pids']:raise ValueError('enclosing resource limits')
    if set(p['io_limits'])!={'supervisor','coordinator'}:raise ValueError('disjoint original owner I/O reservations')
    for value in p['io_limits'].values():Ledger(value)
    if type(p['packet'])is not dict or set(p['packet'])!={'roster','index','dimensions'}:raise ValueError('exact original packet selection')
    if not str(p['cgroup_parent']).startswith('/sys/fs/cgroup/'):raise ValueError('real unified cgroup subtree only')
    expected={'python_metadata','allocator_and_scalar_overhead','decoder_peak','io_buffers','writer_buffers','all_fit_logs_and_errors','complete_outputs','candidate_memory','legacy_observation_memory'}
    if set(p['external_memory_bytes'])!=expected or any(type(v)is not int or v<=0 for v in p['external_memory_bytes'].values()):raise ValueError('independent full overhead bounds; no zero unknowns')
    if p['external_memory_bytes']['candidate_memory']<p['candidate_limits']['memory_bytes']:raise ValueError('candidate peak reserve')
    for k in ('source_files','candidate_files'):
        if type(p[k])is not dict or not p[k]or any(set(v)!={'bytes','sha256'}for v in p[k].values()):raise ValueError('exact selected '+k)
    from .source_lock import REQUIRED_SOURCE_FILES
    if set(p['source_files'])!=set(REQUIRED_SOURCE_FILES):raise ValueError('complete49 source roles required; no subset authority')
    for k in ('runc','python'):
        if set(p[k])!={'path','bytes','sha256'}:raise ValueError('selected executable')
    if type(p['rootfs_manifest'])is not dict or set(p['rootfs_manifest'])!={'path','bytes','sha256'}:raise ValueError('independent complete image manifest')
    image=Path(p['rootfs'])
    if str(image)=='/'or any(image==Path(p[k])or image in Path(p[k]).parents for k in ('packet_root','source_root','candidate_root','work_parent')):raise ValueError('image may not contain host inputs/work/credentials ancestry')
    for k in ('candidate_argv','observed_argv'):
        if type(p[k])is not list or not p[k]or any(type(v)is not str or '\x00'in v for v in p[k]):raise ValueError('fixed argv')
    # The two ABIs are explicit, including the post-freeze observation route.
    if p['candidate_argv'][-8:]!=['--condition','prediction','--public-index','/packet/public/INDEX.json','--packet-root','/packet','--output','/output/PREDICTIONS.json']:raise ValueError('prediction ABI')
    if p['observed_argv'][-8:]!=['--condition','observed','--public-index','/packet/public/INDEX.json','--packet-root','/packet','--output','/output/submission.json']:raise ValueError('observed ABI')
    from prospective.phase_order import BINDINGS
    if set(p['binding_pins'])!=set(BINDINGS)or any(type(v)is not str or not re.fullmatch('[0-9a-f]{64}',v)for v in p['binding_pins'].values()):raise ValueError('independent source/method binding operands')
    if p['binding_pins']['cohort']!='9afc2888bf5200c0362d5adbc951fc90cce2c5e120d58fe00bb83aa5926949fb':raise ValueError('original Neuropixels cohort binding')
    return p

def root_owned(path,directory=False):
    # This is a privilege boundary, not a signed-looking JSON assertion.
    p=Path(path)
    if not p.is_absolute():raise ValueError('absolute selected path')
    for q in reversed([p,*p.parents]):
        s=q.lstat()
        if stat.S_ISLNK(s.st_mode)or s.st_uid!=0 or s.st_mode&0o022:raise PermissionError('root-owned non-writable ancestry required: '+str(q))
    s=p.lstat()
    if directory and not stat.S_ISDIR(s.st_mode):raise ValueError('selected directory')
    return p

def load_selection(path,expected_sha256):
    # Original bootstrap owner precedes every Store acquisition. A failed
    # profile/executable read cannot be replaced by a later Store close.
    errors=ErrorOwner();stores=[];selected=None
    def body():
        nonlocal selected
        if sys.platform!='linux'or os.geteuid()!=0:raise RuntimeError('Linux root supervisor required; no fallback')
        selected_path=root_owned(path);size=selected_path.stat().st_size
        if size>1048576:raise ValueError('host selection <=1MiB')
        ledger=Ledger({'read_bytes':1048576,'write_bytes':1,'files':1,'decoded_bytes':1,'metadata_bytes':1048576})
        source=Store.__new__(Store);stores.append(source)
        Store.__init__(source,str(selected_path.parent),ledger,errors=errors)
        p=validate_profile(decode(source.read(selected_path.name,{'bytes':size,'sha256':expected_sha256},1048576)))
        for k in ('packet_root','source_root','candidate_root','rootfs','work_parent','cgroup_parent'):root_owned(p[k],True)
        for k in ('python','runc'):
            entry=p[k];ep=root_owned(entry['path'])
            store=Store.__new__(Store);stores.append(store)
            Store.__init__(store,str(ep.parent),Ledger({'read_bytes':entry['bytes'],'write_bytes':1,'files':1,'decoded_bytes':1,'metadata_bytes':1}),errors=errors)
            store.read(ep.name,{a:entry[a]for a in ('bytes','sha256')},entry['bytes'])
        selected=Selection();captured=encode(p)
        return selected,captured
    value=None
    try:value=errors.call('selection_loader',body)
    except BaseException:pass
    finally:
        for store in reversed(stores):errors.cleanup('selection_store_retirement',store.close)
    errors.finish()
    # Registry issuance follows successful complete retirement, never precedes it.
    selected,captured=value;_SELECTIONS[selected]=(os.getpid(),captured)
    return selected

def full_plan(p):
    dims=p['packet']['dimensions']
    if type(dims)is not dict or len(dims)!=32:raise ValueError('full32 dimension selection')
    plans={sid:session_plan(*(d[k]for k in ('FIT','VALIDATION','QUERY','units','categories')))for sid,d in dims.items()}
    payload=sum(x['logical_array_payload_bytes']for x in plans.values())
    requested=payload+sum(p['external_memory_bytes'].values())
    if requested>p['total_memory_bytes']:raise RuntimeError('full simultaneous resource admission refused; no subset')
    return plans,{'logical_payload_bytes':payload,'independently_selected_overheads':p['external_memory_bytes'],'admitted_peak_bytes':requested,'kernel_memory_max':p['total_memory_bytes'],'physical_feasibility_qualified':False}
