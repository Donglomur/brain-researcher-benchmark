"""Exact metadata and readonly-leaf composition for the owned VALID episode.

Preparation reads source and metadata only. Material body admission is explicit
and belongs after the retained parent-active acknowledgement.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import stat

META_CAP=1024**2
FILE_CAP=512*1024**2
FACADE_PIN={'bytes':41057,'sha256':'7becc1746b068699070bc28f16286246427233e1a0082274b01a6ad75bcf8c3a'}
VALIDATION_SOURCE_PIN={'bytes':1416,'sha256':'2f953188e39b51a7b76a79f8dc37adb6631b1803f762437a9d6c7a4974b44e83'}
VALIDATION_CORE_PIN={'bytes':25009,'sha256':'818c2cab8ecfe7d7d5fa553e3531529fcebf9a19012dabe043c3c2f40b690c80'}
GRADE_SOURCE_PIN={'bytes':501,'sha256':'0934b8e2f811cf3a8cfb9d2451a2dc09c15021912e42658e19a247ae45a68eee'}
RETAINED_WORKER_PIN={'bytes':11424,'sha256':'2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'}
COMPONENT_FILES={'validation_core.py','validation_episode.py','validation_overlay.py',
                 'validation_legacy.py','validation_owner.py','BINDINGS.json',
                 'DEPLOYMENT_BINDING.json','VALIDATION_TASK.json'}
BINDING_KEYS={'schema','facade','validation_source','prepared_reference','grade_source','transport_source','profile'}
TRANSPORT_FILES={'__init__.py','archive.py','bounds.py','contract.py','engine.py','holder.py','provider.py'}
GRADE_FILES={'VALID_PANEL.json','validation_grade.py','validation_grade_child.py'}

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


def exact_pin(value,allow_empty=False):
    need(type(value) is dict and set(value)=={'bytes','sha256'}
         and type(value['bytes']) is int and (0 if allow_empty else 1)<=value['bytes']<=FILE_CAP
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']),
         'Exact typed content pin')
    return value


def source_identity(root,expected_sha=None):
    root=path(root);raw=body(root/'SOURCE.json');selected=pin(raw)
    need(expected_sha is None or (type(expected_sha) is str and re.fullmatch('[0-9a-f]{64}',expected_sha)
         and selected['sha256']==expected_sha),'Selected owned VALID component source')
    value=decode(raw)
    need(type(value) is dict and set(value)=={'schema','files'}
         and value['schema']=='smc_validation_owned_component_v1'
         and type(value['files']) is dict and set(value['files'])==COMPONENT_FILES,
         'Exact eight-leaf owned VALID component')
    for name,expected in value['files'].items():body(root/name,exact_pin(expected))
    return selected


def load_inputs(root,verify_materials=False):
    """Default admission has no HDF5/checkpoint body access or owner claims."""
    need(type(verify_materials) is bool,'Explicit material-admission selection')
    root=path(root);source_identity(root)
    binding=read(root/'BINDINGS.json')
    need(type(binding) is dict and set(binding)==BINDING_KEYS
         and binding['schema']=='smc_validation_owned_bindings_v1','Exact owned VALID bindings')
    for key in BINDING_KEYS-{'schema','profile'}:descriptor(binding[key])
    need({k:binding['facade'][k] for k in ('bytes','sha256')}==FACADE_PIN,'Fixed full-panel facade source')
    checked(binding['facade'])
    need({k:binding['validation_source'][k] for k in ('bytes','sha256')}==VALIDATION_SOURCE_PIN
         and Path(binding['validation_source']['path']).name=='SOURCE.json','Fixed restricted VALID predecessor manifest')
    checked(binding['validation_source'])
    component=path(binding['validation_source']['path']).parent
    core=load_module('_smc_owned_validation_predecessor',component/'validation_reference.py',VALIDATION_CORE_PIN)
    old_source,manifest=core.source_identity(component,binding['validation_source']['sha256'])
    need(old_source==VALIDATION_SOURCE_PIN,'Full predecessor and projector source closure')
    need({k:binding['grade_source'][k] for k in ('bytes','sha256')}==GRADE_SOURCE_PIN
         and Path(binding['grade_source']['path']).name=='SOURCE.json','Fixed separate VALID grade manifest')
    grade=decode(checked(binding['grade_source']))
    need(type(grade) is dict and set(grade)=={'schema','files'}
         and grade['schema']=='smc_restricted_validation_grade_source_v1'
         and set(grade['files'])==GRADE_FILES,'Fixed separate VALID grade closure')
    grade_root=path(binding['grade_source']['path']).parent
    for name,expected in grade['files'].items():body(grade_root/name,exact_pin(expected))
    transport=decode(checked(binding['transport_source']))
    need(type(transport) is dict and set(transport)=={'schema','files'}
         and transport['schema']=='smc_aggregate_transport_source_manifest_v1'
         and type(transport['files']) is dict and set(transport['files'])==TRANSPORT_FILES,
         'Exact explicit seven-leaf VALID transport manifest')
    for expected in transport['files'].values():exact_pin(expected,allow_empty=True)
    # The episode providerloader separately pins and authenticates the selected
    # transport implementation before importing it. No transport import here.
    profile=core.validate_reference_profile(binding['profile'])
    prepared=decode(checked(binding['prepared_reference']))
    prepared_keys={'schema','component_source','materials','bindings','declaration','execution',
                   'preparation_launched_processes','runtime_qualified_by_preparation',
                   'resource_adequacy','required_external_owner'}
    need(type(prepared) is dict and set(prepared)==prepared_keys
         and prepared['schema']=='smc_restricted_validation_prepared_v1'
         and Path(binding['prepared_reference']['path']).name=='PREPARED.json'
         and prepared['component_source']==binding['validation_source']
         and prepared['preparation_launched_processes'] is False
         and prepared['runtime_qualified_by_preparation'] is False
         and prepared['resource_adequacy'] is False
         and type(prepared['required_external_owner']) is str and prepared['required_external_owner'],
         'Exact prepared metadata; no fabricated native completion')
    for key in ('materials','bindings','declaration','execution'):descriptor(prepared[key])
    need(Path(prepared['materials']['path']).name=='MATERIALS.json','Exact material metadata basename')
    material_root=path(prepared['materials']['path']).parent
    materials=core.validate_material_record(decode(checked(prepared['materials'])))
    method_binding=decode(checked(prepared['bindings']))
    plan=decode(checked(prepared['declaration']));job=decode(checked(prepared['execution']))
    method_binding_pin={k:prepared['bindings'][k] for k in ('bytes','sha256')}
    need(type(method_binding) is dict and set(method_binding)=={'schema','helpers','packet','materials'}
         and method_binding['schema']=='smc_restricted_validation_bindings_v1'
         and method_binding['helpers']=={n:manifest['files']['helpers/'+n] for n in core.HELPERS}
         and method_binding['packet']==materials['packet']
         and method_binding['materials']=={k:prepared['materials'][k] for k in ('bytes','sha256')},
         'Exact frozen helper, projected packet and material-record bindings')
    core.validate_job(plan,job,manifest['files']['validation_adapter.py'],method_binding_pin)
    need(job['source']==old_source
         and job['declaration_sha256']==job['method_freeze_sha256']==prepared['declaration']['sha256']
         and job['packet_sha256']==materials['packet']['sha256']
         and encode(job['resource_profile'])==encode(profile)
         and encode(plan['author_reference_resource_profile'])==encode(profile),
         'Exact prepared source/method/profile/material joins')
    if verify_materials:
        # Caller invokes this only after the unchanged parent-active ACK.
        verified=core.inspect_materials(prepared['materials'])
        need(encode(verified)==encode(materials),'Material admission preserves exact frozen metadata')
    return {'core':core,'binding':binding,'prepared':prepared,'materials':materials,
            'plan':plan,'job':job,'component':component,'manifest':manifest,'material_root':material_root}


def owner_mounts(inputs,program_path,declaration_path,job_path,job_pin,*,retained_worker_descriptor,component_source):
    """After active-parent ACK: exact RO leaves; Provider owns request/output."""
    core=inputs['core'];prepared=inputs['prepared'];manifest=inputs['manifest']
    materials=core.validate_material_record(inputs['materials'])
    component=path(inputs['component']);material_root=path(inputs['material_root'])
    exact_pin(component_source);exact_pin(job_pin)
    program_pin=manifest['files']['validation_adapter.py']
    program_path=path(program_path);declaration_path=path(declaration_path);job_path=path(job_path)
    body(program_path,program_pin)
    declaration_raw=body(declaration_path,{k:prepared['declaration'][k] for k in ('bytes','sha256')})
    need(encode(decode(declaration_raw))==encode(inputs['plan']),'Original frozen method declaration')
    job=decode(body(job_path,job_pin));expected_job=dict(inputs['job']);expected_job['source']=component_source
    need(encode(job)==encode(expected_job),'Only job.source may rebind to the authenticated owned component')
    core.validate_job(inputs['plan'],job,program_pin,{k:prepared['bindings'][k] for k in ('bytes','sha256')})
    need(job['source']==component_source
         and job['declaration_sha256']==job['method_freeze_sha256']==prepared['declaration']['sha256'],
         'Component source joins genuine request; original method SHA remains exact')
    descriptor(retained_worker_descriptor)
    need({k:retained_worker_descriptor[k] for k in ('bytes','sha256')}==RETAINED_WORKER_PIN,
         'Original retained custody and release worker')
    checked(retained_worker_descriptor)
    mounts=[]
    def add(src,dst,expected,purpose):
        src=path(src);exact_pin(expected,allow_empty=True)
        mounts.append({'source':str(src),'destination':dst,'readonly':True,
                       'bytes':expected['bytes'],'sha256':expected['sha256'],'purpose':purpose})
    for name,expected in sorted(materials['files'].items()):
        core.relative(name)
        purpose='input' if name.startswith('inputs/') else 'historical_author_source'
        need(name.startswith(('inputs/','official_source/')),'Finite capsule material roots')
        add(material_root/name,'/materials/'+name,expected,purpose)
    add(program_path,'/program/program.py',program_pin,'program')
    for name,dst in [('validation_worker.py','/runner/worker.py'),
                     ('validation_reference.py','/runner/validation_reference.py'),
                     ('helpers/validation_author_manifest.json','/runner/helpers/validation_author_manifest.json')]:
        add(component/name,dst,manifest['files'][name],'contract')
    add(component.parent/'projection/project_validation.py','/projection/project_validation.py',core.PROJECTOR_PIN,'contract')
    add(prepared['bindings']['path'],'/selected_artifacts/BINDINGS.json',
        {k:prepared['bindings'][k] for k in ('bytes','sha256')},'contract')
    add(declaration_path,'/declaration.json',{k:prepared['declaration'][k] for k in ('bytes','sha256')},'contract')
    add(job_path,'/execution.json',job_pin,'contract')
    for name in sorted(core.HELPERS):
        add(component/'helpers'/name,'/selected_artifacts/restricted_validation/'+name,
            manifest['files']['helpers/'+name],'historical_author_source')
    add(retained_worker_descriptor['path'],'/runner/retained_worker.py',RETAINED_WORKER_PIN,'contract')
    core.validate_worker_mounts(mounts,mounts)
    identities={}
    for row in mounts:
        need(row['purpose'] in {'input','program','contract','historical_author_source'},'Exact owner-purpose roster')
        guest=Path(row['destination'])
        need(not any(guest==Path(dst) or guest in Path(dst).parents or Path(dst) in guest.parents
                     for dst in ('/request.json','/output','/work','/tmp')),
             'Provider-owned request/output and isolated scratch are never supplied as inputs')
        src=path(row['source']);st=src.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==row['bytes'],
             'Exact ordinary single-link readonly leaf, never a raw parent mount')
        identity=(st.st_dev,st.st_ino)
        need(identity not in identities or identities[identity]==str(src),'No aliased distinct readonly operands')
        identities[identity]=str(src)
        if row['bytes']:body(src,{k:row[k] for k in ('bytes','sha256')},FILE_CAP)
        else:need(row['sha256']==hashlib.sha256(b'').hexdigest(),'Exact empty package initializer')
    return mounts
