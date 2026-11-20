"""Exact generic phase ABI and complete manifest-guided output admission."""
import math
from pathlib import PurePosixPath
import re
from .engine import need, descriptor, path
from .bounds import relative, mount_identity

ACTIONS=('prepare_originals','prepare_fold','native_attempt','held_attempt','selection_evaluate','final_evaluate','report')
ROLES=('A','B','reference','operator')
RESOURCE_KEYS={'setup_seconds','producer_seconds','capture_seconds','cleanup_seconds','memory_bytes','cpu_nanos','cpu_seconds','pids','scratch_bytes',
               'max_files','max_directories','max_file_bytes','max_output_bytes','manifest_bytes','max_cli_calls','max_cli_bytes',
               'inventory_bytes','source_read_bytes','host_write_bytes'}


def validate_aggregate(value,phase_id):
    need(type(value) is dict and set(value)=={'schema','phase_id','name','parent','path','cgroup_parent','deployment_pin','invocation_pin'}
         and value['schema']=='smc_cgroup_plan_v1' and value['phase_id']==phase_id,'Exact parent-owned aggregate plan')
    need(type(value['name']) is str and re.fullmatch('smc-[0-9a-f]{32}-[ab]',value['name']),'Fresh invocation-derived cgroup name')
    for key in ('parent','path'):
        need(type(value[key]) is str and str(path(value[key]))==value[key],'Canonical unlinked cgroup path')
    need(value['parent']!='/' and value['path']==str(path(value['parent'])/value['name']),'One exact delegated child')
    daemon=value['cgroup_parent']
    need(type(daemon) is str and daemon.startswith('/') and str(PurePosixPath(daemon))==daemon
         and '..' not in PurePosixPath(daemon).parts and not any(x in daemon for x in (',','\n','\r','\0')),
         'Canonical hierarchy-relative daemon cgroup parent')
    suffix=PurePosixPath(daemon).parts[1:];filesystem=PurePosixPath(value['path']).parts
    need(suffix and suffix[-1]==value['name'] and len(filesystem)>len(suffix)
         and filesystem[-len(suffix):]==suffix,'Filesystem and daemon hierarchy suffix join; parent proves exact mount binding')
    descriptor(value['deployment_pin']);descriptor(value['invocation_pin'])
    return value


def validate_request(request,mounts,original_deadline):
    need(type(request) is dict and set(request)=={'schema','phase_id','action','role','image','command','workdir','source','exposure','clock','resources','output','aggregate'},'Exact aggregate transport phase ABI')
    r=request
    need(r['schema']=='smc_aggregate_phase_request_v1' and r['phase_id']=='validation_reference'
         and r['action']=='held_attempt' and r['role']=='B','Exact restricted VALID reference phase/action/role')
    need(type(r['phase_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',r['phase_id']),'Unique phase ID')
    validate_aggregate(r['aggregate'],r['phase_id'])
    if r['action'] not in ('native_attempt','held_attempt'):need(r['role']=='operator','Fixed private operator action')
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
    need(limits['memory_bytes']==8589934592 and limits['cpu_nanos']==6000000000
         and type(limits['cpu_seconds']) is int and 1<=limits['cpu_seconds']<=64800
         and limits['producer_seconds']==10800,
         'Explicit restricted VALID reference CPU profile; unchanged aggregate memory and CPU rate')
    need(limits['memory_bytes']>=134217728 and limits['scratch_bytes']%4096==0 and limits['max_output_bytes']%4096==0,'Page-exact tmpfs and finite memory')
    need(limits['manifest_bytes']<=limits['max_file_bytes']<=limits['max_output_bytes'],'Nested file/manifest ceilings')
    need(limits['inventory_bytes']>=4096 and limits['max_cli_calls']>=1,'Explicit CLI metadata limits')
    need(type(r['output']) is dict and set(r['output'])=={'kind','manifest'},'Exact output contract')
    need(r['output'] in ({'kind':'native_capture','manifest':'CAPTURE.json'},{'kind':'generic','manifest':'OUTPUTS.json'}),'Original native or generic envelope')
    need((r['output']['kind']=='native_capture')==(r['action']=='native_attempt'),'Complete native capture for every native attempt')
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
    need(type(value) is dict and set(value)==keys and value['schema']=='osl_transport_exposure_v1','Complete external approved transport binding')
    for key in ('role','image','source','command'):need(value[key]==request[key],'Externally approved '+key)
    need(value['mounts']==mount_identity(mounts),'Exact audited complete immutable mount membership')
    need(value['role_boundary_verified'] is True and re.fullmatch('[0-9a-f]{64}',value['approved_image_inventory_sha256']), 'Externally reviewed complete image/source boundary')
    descriptor(value['boundary_audit'])
    return value


def output_files(manifest,request,request_sha256,inventory):
    """Envelope determines dynamic names only; scientific admission is separate."""
    if request['output']['kind']=='native_capture':
        need(manifest.get('schema')=='osl19_primitive_native_capture_v1' and type(manifest.get('fields')) is list,'Native primitive capture envelope')
        files={}
        for field in manifest['fields']:
            need(type(field) is dict and {'file','bytes','sha256'}<=set(field),'Every native primitive field has a complete file pin')
            name=relative(field['file']);need(name not in files and name.endswith('.npy'),'Unique primitive native array files')
            files[name]=descriptor({k:field[k] for k in ('bytes','sha256')},allow_empty=True)
    else:
        need(type(manifest) is dict and set(manifest)=={'schema','phase_id','request_sha256','files'} and manifest['schema']=='osl_transport_output_manifest_v1','Exact generic output envelope')
        need(manifest['phase_id']==request['phase_id'] and manifest['request_sha256']==request_sha256,'Current exact phase/request output')
        files=manifest['files'];need(type(files) is dict and 'RESULT.json' in files,'Generic result required')
        for name,p in files.items():relative(name);descriptor(p,allow_empty=True)
    header=request['output']['manifest'];need(header not in files,'Manifest never self-declares its hash')
    got={row['name']:row['bytes'] for row in inventory['files']}
    need(len(got)==len(inventory['files']) and set(got)==set(files)|{header},'Complete output directory equals envelope; no undeclared exports')
    need(all(got[name]==p['bytes'] for name,p in files.items()),'All exact declared output extents')
    return files
