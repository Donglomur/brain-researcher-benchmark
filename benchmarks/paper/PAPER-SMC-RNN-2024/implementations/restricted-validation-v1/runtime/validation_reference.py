"""Source-bound restricted VALID preparation; native owner admission is separate."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import stat

ROUTE='smc_restricted_validation_v1'
OUTCOME='restricted_validation_reference'
ACCESS='paper_data_author_code_and_weights'
PHASE='validation_reference'
REFERENCE_CEILINGS={'wall_seconds':10800,'memory_bytes':8589934592,'threads':6}
CPU_CEILING=64800
META_CAP=1024**2
FILE_CAP=512*1024**2
PROJECTOR_PIN={'bytes':19882,'sha256':'47adbe1428345d6303243eadcc90efec33dc35b8f6bb519058211d4a1b79d3fb'}
AUTHOR_MANIFEST_PIN={'bytes':3704,'sha256':'907d9209d9bcb281a7aabc95ad4234cae12e5dfbc94a106fa53953cfeea48404'}
RETAINED_WORKER_PIN={'bytes':11424,'sha256':'2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'}
HERE=Path(__file__).absolute().parent
HELPERS={'author_predict_val.py','prepare.py','memory_reduction.py','particle_reduction.patch','validation_author_manifest.json'}
SOURCE_FILES={'validation_reference.py','validation_adapter.py','validation_worker.py'}|{'helpers/'+n for n in HELPERS}

def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(raw):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate reference metadata field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite reference metadata'))


def path(value):
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts
         and not any(x.is_symlink() for x in (p, *p.parents)), 'Unlinked absolute reference path')
    return p


def body(value, expected=None, cap=META_CAP):
    p = path(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'Bounded ordinary reference file')
        raw = stream.read(cap + 1)
        after, named = os.fstat(stream.fileno()), p.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
         for k in fields), 'Stable complete reference body')
    if expected is not None:
        need(pin(raw) == expected, 'Exact reference content identity')
    return raw


def read(value, expected=None):
    return decode(body(value, expected))


def write_new(value, raw, mode=0o400):
    p = path(value)
    need(type(raw) is bytes and 0 < len(raw) <= META_CAP, 'Bounded new reference metadata/source')
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(raw)


def load_module(name, filename, expected):
    raw = body(filename, expected)
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(filename), 'exec'), module.__dict__)
    return module


def descriptor(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Exact named descriptor')
    path(value['path']);need(type(value['bytes']) is int and 0<value['bytes']<=FILE_CAP
        and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']), 'Finite exact descriptor')
    return value


def checked(value,cap=META_CAP):
    descriptor(value)
    return body(value['path'],{k:value[k] for k in ('bytes','sha256')},cap)


def ref(value):
    return {'path':str(path(value)),**pin(body(value))}


def source_identity(root,expected_sha=None):
    root=path(root);raw=body(root/'SOURCE.json')
    need(expected_sha is None or pin(raw)['sha256']==expected_sha,'Selected restricted VALID source')
    manifest=decode(raw)
    need(set(manifest)=={'schema','route','files','projector'} and manifest['schema']=='smc_restricted_validation_source_v1'
         and manifest['route']==ROUTE and set(manifest['files'])==SOURCE_FILES,'Exact restricted VALID source roster')
    for name,expected in manifest['files'].items():body(root/name,expected)
    body(root.parent/'projection/project_validation.py',PROJECTOR_PIN)
    need(manifest['projector']==PROJECTOR_PIN
         and manifest['files']['helpers/validation_author_manifest.json']==AUTHOR_MANIFEST_PIN,
         'Exact projector and original noncausal material selection')
    return pin(raw),manifest


def inspect_inputs(inputs,packet_sha256):
    inputs=path(inputs)
    projector=load_module('_smc_restricted_validation_projector',HERE.parent/'projection/project_validation.py',PROJECTOR_PIN)
    return projector.inspect_packet(inputs/'PACKET.json',packet_sha256)


def author_manifest():
    value=read(HERE/'helpers/validation_author_manifest.json',AUTHOR_MANIFEST_PIN)
    need(value['schema']=='smc_restricted_validation_author_manifest_v1' and value['arm']=='noncausal'
         and value['checkpoint_training_cohort']=='unknown' and len(value['files'])==16,
         'Fixed minimal original software and noncausal checkpoint manifest')
    return value


def recipe():
    return {'arm':'noncausal','seed':20261118,'particles':192,'repeats':32,'smooth':False,
            'device':'cpu','training':False,'checkpoint_search':False,'access_condition':ACCESS}


def validate_reference_profile(value):
    need(type(value) is dict and set(value)=={'cpu_seconds','wall_seconds','memory_bytes','threads'}
         and all(type(v) is int for v in value.values())
         and 0<value['cpu_seconds']<=CPU_CEILING
         and all(value[k]==v for k,v in REFERENCE_CEILINGS.items()),
         'Explicit finite author reference profile; CPU1..64800 and retained wall/RAM/threads')
    return dict(value)


def validate_owner_resources(resources,profile):
    profile=validate_reference_profile(profile)
    expected={'cpu_seconds':profile['cpu_seconds'],'producer_seconds':profile['wall_seconds'],
              'memory_bytes':profile['memory_bytes'],'cpu_nanos':profile['threads']*1000000000}
    need(type(resources) is dict and all(type(resources.get(k)) is int and resources[k]==v for k,v in expected.items())
         and type(resources.get('pids')) is int and resources['pids']>0,
         'Genuine owner resources exactly match the frozen author reference profile')
    return profile


def method_plan(program_pin,bindings_pin,packet_sha256,author_reference_resource_profile):
    profile=validate_reference_profile(author_reference_resource_profile)
    return {'schema':'smc_restricted_validation_method_v1','route':ROUTE,'phase':'val',
            'role':'reference','program':program_pin,'bindings':bindings_pin,'recipe':recipe(),
            'packet_sha256':packet_sha256,'author_reference_resource_profile':profile,'AI_attempt':False,'scientific_improvement':False}


def validate_job(plan,job,program_pin,bindings_pin):
    need(encode(plan)==encode(method_plan(program_pin,bindings_pin,plan.get('packet_sha256'),plan.get('author_reference_resource_profile')))
         and re.fullmatch('[0-9a-f]{64}',plan['packet_sha256']), 'Exact frozen restricted VALID reference method')
    fields={'schema','route','outcome','condition','phase_id','access_condition','source','resource_profile',
            'submission_keys','program_sha256','declaration_sha256','method_freeze_sha256','bindings','max_file_bytes','packet_sha256'}
    need(type(job) is dict and set(job)==fields and job['schema']=='smc_restricted_validation_execution_job_v1'
         and job['route']==ROUTE and job['outcome']==OUTCOME and job['condition']==job['phase_id']==PHASE
         and job['access_condition']==ACCESS
         and encode(validate_reference_profile(job['resource_profile']))==encode(plan['author_reference_resource_profile']) and job['submission_keys']==['offline']
         and job['program_sha256']==program_pin['sha256'] and job['bindings']==bindings_pin
         and job['packet_sha256']==plan['packet_sha256'] and job['max_file_bytes']==FILE_CAP,
         'Exact restricted VALID job, frozen fallible author resource profile and complete outputs')
    need(re.fullmatch('[0-9a-f]{64}',job['method_freeze_sha256']) is not None,'Actual frozen method identity required')
    return recipe()


def relative(name):
    p=Path(name)
    need(type(name) is str and name and not p.is_absolute() and '..' not in p.parts and str(p)==name,
         'Exact relative material leaf')
    return p


def copy_exact(source,destination,expected):
    source,destination=path(source),path(destination)
    need(type(expected) is dict and set(expected)=={'bytes','sha256'} and type(expected['bytes']) is int
         and 0<=expected['bytes']<=FILE_CAP and re.fullmatch('[0-9a-f]{64}',expected['sha256']),
         'Exact bounded material copy')
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],
             'Ordinary exact-size material before copy')
        out=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        count=0;digest=hashlib.sha256()
        with os.fdopen(out,'wb') as sink:
            while count<expected['bytes']:
                chunk=stream.read(min(1024**2,expected['bytes']-count));need(chunk,'Complete material source')
                count+=len(chunk);digest.update(chunk);sink.write(chunk)
            need(stream.read(1)==b'','Material source extent cannot grow')
            after,named=os.fstat(stream.fileno()),source.lstat()
            keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            need(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in keys)
                 and digest.hexdigest()==expected['sha256'],'Stable exact original material bytes')
            sink.flush();os.fsync(sink.fileno())
    return expected


def inventory(root):
    root=path(root);files=set();folders={'.'}
    for base,dirs,names in os.walk(root,followlinks=False):
        need(len(files)+len(folders)<=64,'Finite material inventory')
        for name in dirs:
            p=Path(base)/name;need(not p.is_symlink(),'No material directory symlink');folders.add(p.relative_to(root).as_posix())
        for name in names:
            p=Path(base)/name;st=p.lstat()
            need(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'Only ordinary single-copy material leaves')
            files.add(p.relative_to(root).as_posix())
    return files,folders


def validate_material_record(record):
    need(type(record) is dict and set(record)=={'schema','route','packet','author_manifest','files','train_rate_scope',
         'checkpoint_training_cohort','resource_adequacy'} and record['schema']=='smc_restricted_validation_materials_v1'
         and record['route']==ROUTE and record['author_manifest']==AUTHOR_MANIFEST_PIN
         and record['train_rate_scope']=='canonical_metric_decoder_inputs_not_restricted_calibration'
         and record['checkpoint_training_cohort']=='unknown' and record['resource_adequacy'] is False,
         'Exact restricted material capsule and disclosed scientific limits')
    author={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in author_manifest()['files']}
    expected={'inputs/PACKET.json','inputs/mc_maze/val/train_input_20ms.h5','inputs/mc_maze/val/eval_input_20ms.h5'}|{'official_source/'+n for n in author}
    need(set(record['files'])==expected and record['files']['inputs/PACKET.json']==record['packet'],
         'Only projected packet and exact original noncausal software/checkpoint leaves')
    need(all(record['files']['official_source/'+n]==v for n,v in author.items()),'No substituted or causal author materials')
    return record


def prepare_materials(packet_descriptor,author_source_root,output_root):
    """Future operator copy: no original raw input/target path is accepted."""
    packet_descriptor=descriptor(packet_descriptor);checked(packet_descriptor)
    packet_root=path(packet_descriptor['path']).parent;need(Path(packet_descriptor['path']).name=='PACKET.json','Selected projected packet')
    packet=inspect_inputs(packet_root,packet_descriptor['sha256'])
    author_source_root=path(author_source_root);output=path(output_root)
    need(not os.path.lexists(output) and output.parent.is_dir()
         and not any(output.is_relative_to(p) or p.is_relative_to(output) for p in (packet_root,author_source_root)),
         'Fresh disjoint material capsule')
    output.mkdir(mode=0o700)
    selections={'inputs/PACKET.json':(Path(packet_descriptor['path']),{k:packet_descriptor[k] for k in ('bytes','sha256')})}
    for name,row in packet['files'].items():selections['inputs/'+name]=(packet_root/relative(name),{k:row[k] for k in ('bytes','sha256')})
    for row in author_manifest()['files']:
        selections['official_source/'+row['path']]=(author_source_root/relative(row['path']),{k:row[k] for k in ('bytes','sha256')})
    files={}
    for name,(source,expected) in sorted(selections.items()):
        dst=output/relative(name);dst.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        files[name]=copy_exact(source,dst,expected)
    record={'schema':'smc_restricted_validation_materials_v1','route':ROUTE,'packet':files['inputs/PACKET.json'],
        'author_manifest':AUTHOR_MANIFEST_PIN,'files':files,'train_rate_scope':'canonical_metric_decoder_inputs_not_restricted_calibration',
        'checkpoint_training_cohort':'unknown','resource_adequacy':False}
    validate_material_record(record);write_new(output/'MATERIALS.json',encode(record))
    return ref(output/'MATERIALS.json')


def inspect_materials(material_descriptor):
    record=validate_material_record(decode(checked(material_descriptor)));root=path(material_descriptor['path']).parent
    need(Path(material_descriptor['path']).name=='MATERIALS.json','Exact capsule metadata basename')
    files,folders=inventory(root);expected=set(record['files'])|{'MATERIALS.json'}
    expected_dirs={'.'}
    for name in expected:
        expected_dirs.update(str(p) for p in Path(name).parents if str(p)!='.')
    need(files==expected and folders==expected_dirs,'No raw input, target, extra source or parent tree exposed')
    for name,expected_pin in record['files'].items():
        p=root/name
        if expected_pin['bytes']:
            body(p,expected_pin,FILE_CAP)
        else:
            need(p.lstat().st_size==0 and expected_pin['sha256']==hashlib.sha256(b'').hexdigest(),'Exact empty package initializer')
    packet=inspect_inputs(root/'inputs',record['packet']['sha256'])
    for name,row in packet['files'].items():
        need(record['files']['inputs/'+name]=={k:row[k] for k in ('bytes','sha256')},'Copied packet leaf content identity')
    return record


def prepare_reference(component_root,component_sha256,material_descriptor,output_root,*,author_reference_resource_profile):
    profile=validate_reference_profile(author_reference_resource_profile)
    component_root=path(component_root);source,manifest=source_identity(component_root,component_sha256)
    materials=inspect_materials(material_descriptor);out=path(output_root)
    need(not os.path.lexists(out) and out.parent.is_dir()
         and not any(out.is_relative_to(p) or p.is_relative_to(out) for p in (component_root,path(material_descriptor['path']).parent)),
         'Fresh method metadata root disjoint from source and materials');out.mkdir(mode=0o700)
    bindings={'schema':'smc_restricted_validation_bindings_v1','helpers':{n:manifest['files']['helpers/'+n] for n in HELPERS},
              'packet':materials['packet'],'materials':{k:material_descriptor[k] for k in ('bytes','sha256')}}
    binding_raw=encode(bindings);binding_pin=write_new(out/'BINDINGS.json',binding_raw)
    program=manifest['files']['validation_adapter.py'];plan=method_plan(program,binding_pin,materials['packet']['sha256'],profile)
    declaration=write_new(out/'declaration.json',encode(plan))
    job={'schema':'smc_restricted_validation_execution_job_v1','route':ROUTE,'outcome':OUTCOME,'condition':PHASE,
         'phase_id':PHASE,'access_condition':ACCESS,'source':source,'resource_profile':profile,'submission_keys':['offline'],
         'program_sha256':program['sha256'],'declaration_sha256':declaration['sha256'],'method_freeze_sha256':declaration['sha256'],
         'bindings':binding_pin,'max_file_bytes':FILE_CAP,'packet_sha256':materials['packet']['sha256']}
    validate_job(plan,job,program,binding_pin);write_new(out/'execution.json',encode(job))
    prepared={'schema':'smc_restricted_validation_prepared_v1','component_source':{'path':str(component_root/'SOURCE.json'),**source},
              'materials':material_descriptor,'bindings':ref(out/'BINDINGS.json'),'declaration':ref(out/'declaration.json'),
              'execution':ref(out/'execution.json'),'preparation_launched_processes':False,'runtime_qualified_by_preparation':False,
              'resource_adequacy':False,'required_external_owner':'Genuine selected phase request, attachment ACK, release, captured outputs and closed process/cgroup proofs; no such proof is emitted here.'}
    write_new(out/'PREPARED.json',encode(prepared));return ref(out/'PREPARED.json')


def build_invocation(prepared_descriptor,owner_request_descriptor,retained_worker_descriptor,output_root):
    """Bind exact readonly leaves; owner request/attachment/release remain real prerequisites."""
    prepared=decode(checked(prepared_descriptor));need(prepared['schema']=='smc_restricted_validation_prepared_v1'
        and prepared['runtime_qualified_by_preparation'] is False and prepared['resource_adequacy'] is False,
        'Typed unqualified preparation, never an owner success record')
    component=path(prepared['component_source']['path']).parent
    source,manifest=source_identity(component,prepared['component_source']['sha256'])
    materials=inspect_materials(prepared['materials']);material_root=path(prepared['materials']['path']).parent
    bindings=decode(checked(prepared['bindings']));plan=decode(checked(prepared['declaration']));job=decode(checked(prepared['execution']))
    validate_job(plan,job,manifest['files']['validation_adapter.py'],{k:prepared['bindings'][k] for k in ('bytes','sha256')})
    need(job['source']==source and job['declaration_sha256']==job['method_freeze_sha256']==prepared['declaration']['sha256']
         and job['packet_sha256']==materials['packet']['sha256'] and bindings['packet']==materials['packet']
         and bindings['materials']=={k:prepared['materials'][k] for k in ('bytes','sha256')},'Exact prepared method/source/material joins')
    request_raw=checked(owner_request_descriptor);request=decode(request_raw)
    need(request_raw==encode(request) and request['schema']=='smc_aggregate_phase_request_v1'
         and request['phase_id']==PHASE and request['role']=='B' and request['source']==source,
         'Genuine source-bound retained phase request; not a synthetic completion flag')
    profile=validate_owner_resources(request['resources'],job['resource_profile'])
    need({k:retained_worker_descriptor[k] for k in ('bytes','sha256')}==RETAINED_WORKER_PIN,'Original custody/release worker')
    checked(retained_worker_descriptor)
    output=path(output_root);need(output.is_dir() and not any(output.iterdir()),'Fresh separate worker output')
    roots=(component,material_root,path(prepared_descriptor['path']).parent)
    need(not any(output.is_relative_to(p) or p.is_relative_to(output) for p in roots),'Output disjoint from admitted readonly roots')
    mounts=[]
    def add(src,dst,expected,purpose):
        need(type(dst) is str and dst.startswith('/') and '..' not in Path(dst).parts,'Exact guest leaf')
        mounts.append({'source':str(path(src)),'destination':dst,'readonly':True,'bytes':expected['bytes'],'sha256':expected['sha256'],'purpose':purpose})
    for name,expected in sorted(materials['files'].items()):add(material_root/name,'/materials/'+name,expected,'restricted_material')
    add(component/'validation_adapter.py','/program/program.py',manifest['files']['validation_adapter.py'],'program')
    for name,dst in [('validation_worker.py','/runner/worker.py'),('validation_reference.py','/runner/validation_reference.py'),('helpers/validation_author_manifest.json','/runner/helpers/validation_author_manifest.json')]:
        add(component/name,dst,manifest['files'][name],'trusted_worker')
    add(component.parent/'projection/project_validation.py','/projection/project_validation.py',PROJECTOR_PIN,'packet_inspector')
    for key,dst in [('bindings','/selected_artifacts/BINDINGS.json'),('declaration','/declaration.json'),('execution','/execution.json')]:
        row=prepared[key];add(row['path'],dst,row,'contract')
    for name in sorted(HELPERS):add(component/'helpers'/name,'/selected_artifacts/restricted_validation/'+name,manifest['files']['helpers/'+name],'author_helper')
    add(owner_request_descriptor['path'],'/request.json',owner_request_descriptor,'owner_request')
    add(retained_worker_descriptor['path'],'/runner/retained_worker.py',retained_worker_descriptor,'custody_release')
    need(len({r['destination'] for r in mounts})==len(mounts),'No overlapping guest destination')
    validate_worker_mounts(mounts,mounts)
    validate_mount_operands(mounts,output)
    return {'schema':'smc_restricted_validation_worker_invocation_v1','argv':['/usr/local/bin/python3.11','-I','-S','-B','/runner/worker.py'],
            'release_argv':['/usr/local/bin/python3.11','-I','-S','-B','/runner/worker.py','--release'],
            'readonly_mounts':mounts,'writable_mounts':[{'source':str(output),'destination':'/output','readonly':False}],
            'working_dir':'/work','readonly_rootfs':True,'ephemeral_write_paths':['/work','/tmp'],
            'additional_bind_mounts_allowed':False,'resource_profile':profile,'resource_adequacy':False,'runtime_qualified':False,
            'required_owner_custody':'Original parent-cgroup attachment ACK and Provider release before scientific entry; actual capture and closure after it.'}


def validate_worker_mounts(actual,selected):
    need(type(actual) is list and encode(actual)==encode(selected),'Exact selected leaf mounts; no raw or parent mount substitution')
    destinations=[]
    for row in actual:
        need(set(row)=={'source','destination','readonly','bytes','sha256','purpose'} and row['readonly'] is True,
             'Readonly exact source leaf only')
        dst=Path(row['destination']);need(dst.is_absolute() and '..' not in dst.parts and str(dst)==row['destination'],'Canonical guest leaf')
        need(not any(dst==other or dst in other.parents or other in dst.parents for other in destinations),
             'No duplicate or parent-directory mount exposure')
        destinations.append(dst)
    return actual


def validate_mount_operands(mounts,output_root):
    """Actual builder gate: each bind is a stable admitted leaf, never a parent tree.

    The future physical owner must realize this complete mount list, a readonly
    image root and only isolated /work and /tmp scratch plus /output writes.
    Scratch must be charged inside its admitted memory/storage envelope.
    """
    output=path(output_root)
    need(output.is_dir() and not any(output.iterdir()),'Empty isolated output directory')
    identities={}
    for row in mounts:
        src=path(row['source']);st=src.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==row['bytes'],
             'Every bind source is an exact ordinary single-link file, never a directory')
        need(not (src==output or src.is_relative_to(output) or output.is_relative_to(src)),
             'Output never contains or replaces any readonly operand')
        identity=(st.st_dev,st.st_ino)
        need(identity not in identities or identities[identity]==str(src),'No aliased distinct input paths')
        identities[identity]=str(src)
        need(not any(Path(row['destination'])==Path(dst) or Path(dst) in Path(row['destination']).parents
                     or Path(row['destination']) in Path(dst).parents for dst in ('/output','/work','/tmp')),
             'Readonly leaf cannot overlap writable output or isolated scratch')
        if row['bytes']:
            body(src,{k:row[k] for k in ('bytes','sha256')},FILE_CAP)
        else:
            need(row['sha256']==hashlib.sha256(b'').hexdigest(),'Exact empty initializer identity')
    return True
