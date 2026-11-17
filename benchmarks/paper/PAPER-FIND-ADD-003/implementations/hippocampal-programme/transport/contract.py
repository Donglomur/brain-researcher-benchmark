"""Exact generic phase ABI and complete manifest-guided output admission."""
import math
from pathlib import PurePosixPath
import re
from .engine import need, descriptor
from .bounds import relative, mount_identity

ACTIONS=('prepare_originals','prepare_fold','native_attempt','train_model','analytic_prior','evaluate_model','grade','report')
ROLES=('A','B','reference','operator')
RESOURCE_KEYS={'setup_seconds','producer_seconds','capture_seconds','cleanup_seconds','memory_bytes','cpu_nanos','pids','scratch_bytes',
               'max_files','max_directories','max_file_bytes','max_output_bytes','manifest_bytes','max_cli_calls','max_cli_bytes',
               'inventory_bytes','source_read_bytes','host_write_bytes'}


def validate_request(request,mounts,original_deadline):
    need(type(request) is dict and set(request)=={'schema','phase_id','action','role','image','command','workdir','source','exposure','clock','resources','output'},'Exact transport phase ABI')
    r=request
    need(r['schema']=='h_owned_phase_request_v1' and r['action'] in ACTIONS and r['role'] in ROLES,'Bounded phase/action/role')
    need(type(r['phase_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',r['phase_id']),'Unique phase ID')
    if r['action'] not in ('native_attempt','train_model','analytic_prior'):need(r['role']=='operator','Fixed private operator action')
    else:need(r['role'] in ('A','B','reference'),'Exact producer role')
    need(type(r['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}',r['image']),'Immutable local image digest')
    need(type(r['command']) is list and 1<=len(r['command'])<=64 and all(type(x) is str and 0<len(x.encode())<=4096 and '\0' not in x for x in r['command']), 'Bounded exact argv')
    need(r['command'][0].startswith('/') and r['workdir']=='/work','Absolute approved entry executable and private working directory')
    descriptor(r['source']);descriptor(r['exposure'])
    need(type(r['clock']) is dict and set(r['clock'])=={'origin','phase_deadline'},'Original clock binding')
    for value in (original_deadline,*r['clock'].values()):need(type(value) in (int,float) and math.isfinite(value),'Finite monotonic clock')
    need(0<=r['clock']['origin']<r['clock']['phase_deadline']<=original_deadline,'Original global cutoff is never refreshed')
    limits=r['resources'];need(type(limits) is dict and set(limits)==RESOURCE_KEYS,'Explicit complete transport bounds')
    for k,v in limits.items():need(type(v) is int and v>0,'Prospective positive integer bound '+k)
    need(limits['memory_bytes']>=134217728 and limits['scratch_bytes']%4096==0 and limits['max_output_bytes']%4096==0,'Page-exact tmpfs and finite memory')
    need(limits['manifest_bytes']<=limits['max_file_bytes']<=limits['max_output_bytes'],'Nested file/manifest ceilings')
    need(limits['inventory_bytes']>=4096 and limits['max_cli_calls']>=1,'Explicit CLI metadata limits')
    need(type(r['output']) is dict and set(r['output'])=={'kind','manifest'},'Exact output contract')
    need(r['output']=={'kind':'generic','manifest':'OUTPUTS.json'},'All H phases use the complete generic envelope')
    need(type(mounts) is dict and mounts,'Complete nonempty immutable mounts')
    for target,desc in mounts.items():
        need(type(target) is str and target.startswith('/') and str(PurePosixPath(target))==target
             and '..' not in PurePosixPath(target).parts and not any(c in target for c in (',','\n','\r','\0')),'Canonical target')
        need(target not in ('/','/work','/output','/request.json','/proc','/sys','/dev','/tmp','/trusted/holder.py','/trusted/POLICY.json')
             and not any(target.startswith(p+'/') for p in ('/output','/proc','/sys','/dev')),'No shadowed isolation or output path')
        need(type(desc) is dict and set(desc)=={'path','kind','purpose','files'},'Exact input descriptor')
        allowed={'paper','contract','input','program'}
        if r['role'] in ('B','reference','operator'):allowed.add('historical_author_source')
        if r['role'] in ('reference','operator'):allowed.add('operator_reference')
        need(desc['purpose'] in allowed,'Exact role source/mount boundary')
    targets=sorted(mounts)
    need(not any(b.startswith(a+'/') for i,a in enumerate(targets) for b in targets[i+1:]),'No nested overlapping caller bindings')
    return r


def validate_exposure(value,request,mounts):
    keys={'schema','role','image','source','command','mounts','approved_image_inventory_sha256','boundary_audit','role_boundary_verified'}
    need(type(value) is dict and set(value)==keys and value['schema']=='h_transport_exposure_v1','Complete external approved transport binding')
    for key in ('role','image','source','command'):need(value[key]==request[key],'Externally approved '+key)
    need(value['mounts']==mount_identity(mounts),'Exact audited complete immutable mount membership')
    need(value['role_boundary_verified'] is True and re.fullmatch('[0-9a-f]{64}',value['approved_image_inventory_sha256']), 'Externally reviewed complete image/source boundary')
    descriptor(value['boundary_audit'])
    return value


def output_files(manifest,request,request_sha256,inventory):
    """Envelope determines dynamic names only; scientific admission is separate."""
    need(type(manifest) is dict and set(manifest)=={'schema','phase_id','request_sha256','files'} and manifest['schema']=='h_transport_output_manifest_v1','Exact generic output envelope')
    need(manifest['phase_id']==request['phase_id'] and manifest['request_sha256']==request_sha256,'Current exact phase/request output')
    files=manifest['files'];need(type(files) is dict and 'RESULT.json' in files,'Generic result required')
    for name,p in files.items():relative(name);descriptor(p,allow_empty=True)
    header=request['output']['manifest'];need(header not in files,'Manifest never self-declares its hash')
    got={row['name']:row['bytes'] for row in inventory['files']}
    need(len(got)==len(inventory['files']) and set(got)==set(files)|{header},'Complete output directory equals envelope; no undeclared exports')
    need(all(got[name]==p['bytes'] for name,p in files.items()),'All exact declared output extents')
    return files
