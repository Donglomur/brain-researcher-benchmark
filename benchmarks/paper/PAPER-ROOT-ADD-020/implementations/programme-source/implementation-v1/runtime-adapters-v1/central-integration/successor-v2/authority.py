"""Fixed operator trust, signed whole-study operands; no deployment included."""
import base64
import os
from pathlib import Path
import stat
import sys

INSTALLATION=Path('/etc/neurobench/paper020-central/INSTALLATION.json')
PUBLIC_KEY=Path('/etc/neurobench/paper020-central/PUBLIC_KEY.ed25519')
ENVIRONMENT=Path('/etc/neurobench/paper020-central/PYTHON_ENVIRONMENT.json')
QUALIFICATIONS=('source_and_environment_custody','original_clock_coverage_before_entry',
 'complete_host_and_worker_accounting','immutable_full_bundle_publication',
 'independent_terminal_observer_and_costs','credential_broker_custody')
PARENT_QUALIFICATIONS=('full_source_identity','full_mat_schema_and_units','global_face_identity',
 'independent_native_output_schema','all_original_clock_support','immutable_store_custody',
 'candidate_image_excludes_trusted_evaluator','a_b_exposure_equal_except_author_code',
 'host_and_worker_lossless_accounting','protected_target_custody','full_workload_resource_profile',
 'provider_spending_and_data_transfer','native_image_and_conversion_parity')

def signed(envelope,key):
    u.need(type(envelope)is dict and set(envelope)=={'document','signature'} and type(key)is bytes and len(key)==32,
           'exact signed operator envelope and installed public verification key required')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(envelope['signature'],validate=True),u.canonical(envelope['document']))
    return envelope['document']

def installed(env,reader):
    for path in (INSTALLATION,PUBLIC_KEY,ENVIRONMENT):
        u.components(path);current=path
        while str(current)!='/':
            info=current.lstat();u.need(info.st_uid==0 and not stat.S_IMODE(info.st_mode)&0o022,
                                       'fixed operator installation must be root-owned, not group/world writable')
            current=current.parent
    # -I -S has no ambient site packages. A fixed root-owned environment file
    # supplies only separately qualified dependency directories, before crypto.
    environment,epin=reader.json(ENVIRONMENT,131072)
    u.need(type(environment)is dict and set(environment)=={'schema','python','version','platform','dependency_roots'}
           and environment['schema']=='paper020_python_environment_v1' and environment['version']==sys.version
           and environment['platform']==sys.platform=='linux','exact qualified Linux interpreter environment')
    p=u.descriptor(environment['python']);u.need(os.path.realpath(sys.executable)==p['path'],'installed interpreter differs')
    reader.file_pin(p['path'],u.only_pin(p))
    u.need(type(environment['dependency_roots'])is list and 1<=len(environment['dependency_roots'])<=8,'bounded explicit qualified dependencies')
    for root in environment['dependency_roots']:
        path=u.components(u.absolute(root));info=path.lstat()
        u.need(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not stat.S_IMODE(info.st_mode)&0o022,'immutable operator dependency root')
        if root not in sys.path:sys.path.append(root)
    key=reader.read(PUBLIC_KEY,32);envelope,_=reader.json(INSTALLATION,131072);doc=signed(envelope,key)
    u.need(doc.get('schema')=='paper020_central_installation_v1' and doc.get('installed')is True
           and doc.get('central_source')==env['source_pin'] and doc.get('source_closure_digest')==u.sha(u.canonical(env['source_rows']))
           and set(doc.get('qualifications',{}))==set(QUALIFICATIONS)
           and all(doc['qualifications'][k]is True for k in QUALIFICATIONS) and doc.get('python_environment')==epin,
           'independently qualified installed central deployment required')
    return doc,key

def admit(env,reader,program_path,output,condition_mode,registered,*,observing=False):
    installation,key=installed(env,reader)
    envelope,program_pin=reader.json(program_path,1_048_576)
    job=signed(envelope,key)
    fields={'schema','task_id','central_source','run_id','mode','origin_ns','deadline_ns','output_root',
            'runtime_envelope','contract','admission','mapping','metadata_limits','credential_broker','other_reserve_bytes'}
    u.need(type(job)is dict and set(job)==fields and job['schema']=='paper020_central_job_v1'
           and job['task_id']=='PAPER-ROOT-ADD-020' and job['central_source']==env['source_pin']
           and job['mode']==condition_mode,'exact signed full-study central job required')
    u.need(type(job['run_id'])is str and 1<=len(job['run_id'])<=128,'bounded run identity')
    u.need(type(job['other_reserve_bytes'])is int and job['other_reserve_bytes']>=0
           and str(job['other_reserve_bytes'])==env['operands']['{other_reserve_bytes}'],'signed concurrent-work reserve differs')
    u.need(type(job['origin_ns'])is int and type(job['deadline_ns'])is int
           and job['origin_ns']<=env['entry_start']<job['deadline_ns'],'original clock must cover bootstrap; never reset')
    reader.origin=job['origin_ns'];reader.deadline=job['deadline_ns']
    limits=job['metadata_limits'];u.need(type(limits)is dict and set(limits)=={'read_bytes','write_bytes','trace_bytes','artifact_index_bytes'},'complete central metadata limits')
    for value in limits.values():u.need(type(value)is int and value>0,'positive metadata limit')
    u.need(limits['read_bytes']>=reader.read_reserved and limits['write_bytes']>=reader.write_bytes,'no central accounting refunds')
    reader.read_limit=limits['read_bytes'];reader.write_limit=limits['write_bytes'];reader.tick()
    u.need(str(u.absolute(output))==job['output_root'],'signed output root differs')
    runtime_ref=u.descriptor(job['runtime_envelope']);runtime,_=reader.json(runtime_ref['path'],16_777_216,u.only_pin(runtime_ref))
    d=signed(runtime,key)
    u.need(d.get('schema')=='paper020_runtime_installation_v1' and d.get('installed')is True
           and set(d.get('qualifications',{}))==set(PARENT_QUALIFICATIONS)
           and all(d['qualifications'][k]is True for k in PARENT_QUALIFICATIONS),
           'all actual parent deployment qualifications required before scientific operand reads')
    u.need(d.get('origin_ns')==job['origin_ns'] and d.get('deadline_ns')==job['deadline_ns']
           and d.get('profile',{}).get('duration_ns')==job['deadline_ns']-job['origin_ns']
           and d.get('profile',{}).get('max_phases')==23786,'same original complete runtime clock/profile required')
    u.need(d.get('adapter_source_digest')==env['parent']['adapter_manifest_pin']['sha256']
           and d.get('scientific_source_digest')==env['parent']['scientific_source_digest'],'signed captured parent source differs')
    out=u.absolute(job['output_root'])
    for name in ('source_root','store_root'):
        other=u.absolute(d[name]);u.need(not(out==other or out.is_relative_to(other)or other.is_relative_to(out)),
                                        'central output, original source and private store roots must be separate')
    for actor in ('A','B'):
        for track in ('native','prediction'):
            policy=d.get('candidate_policies',{}).get(actor,{}).get(track,{})
            u.need(policy.get('mode')==job['mode'] and policy==d['candidate_policies']['A'][track],
                   'both modes retain equal A/B policy on both complete tracks')
    values={}
    for name in ('contract','admission','mapping'):
        ref=u.descriptor(job[name]);values[name],_=reader.json(ref['path'],67_108_864,u.only_pin(ref))
    u.need(u.scientific_digest(values['admission'])==d.get('admission_digest')
           and u.sha(u.canonical(values['mapping']))==d.get('mapping_digest'),'exact signed source operands differ')
    # Declarations below are independently qualified capabilities, not self-issued runtime evidence.
    u.need(installation.get('deployment_source_closure')==registered['deployment'],'registered deployment source closure differs')
    u.need(job['credential_broker']==installation.get('credential_broker'),'fixed signed credential broker differs')
    reader.tick()
    return {'job':job,'program_pin':program_pin,'installation':installation,'public_key':key,
            'runtime_envelope':runtime,'runtime_document':d,**values}
