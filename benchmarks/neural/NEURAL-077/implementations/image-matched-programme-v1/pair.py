"""Additive frozen image-programme arm; original transport and scoring kernels.

A source-bound adapter permits computation on visible pixels. Programme admission
requires the exact macOS policy, not a protocol-only fixture. Neither recorded
policy nor generated controls prove OS enforcement or remote provider policy.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import time
import types

HERE = Path(__file__).resolve().parent
PREFIX = 'benchmarks/neural/NEURAL-077/implementations/'
CONDITION = 'matched_image_programme'
COUNT = 400
COLLECTION_RESERVE = 8 * 1024**2
FINAL_RESERVE = 1024**2
READABLE = tuple(Path(p) for p in ('/System', '/usr', '/Library/Frameworks'))
OWN = ('pair.py', 'adapters.py', 'SOURCE_BINDINGS.json')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate field')
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite field')))


def ordinary(path):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Ordinary unlinked path')
    return path


def protected_path(path):
    path = ordinary(path).resolve(strict=False)
    need(all(not path.is_relative_to(root) and not root.is_relative_to(path) for root in READABLE),
         'Protected input overlaps readable runtime root')
    return path


def disjoint(output, *inputs):
    output = protected_path(output)
    for item in inputs:
        other = ordinary(item).resolve(strict=False)
        need(not output.is_relative_to(other) and not other.is_relative_to(output), 'Output/source/input overlap')
    return output


def read(path, cap=1048576, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        a = os.fstat(f.fileno())
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'Bounded ordinary file')
        body = f.read(cap + 1)
        b = os.fstat(f.fileno())
    state = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns, x.st_nlink)
    need(state(a) == state(b) == state(path.lstat()) and len(body) == a.st_size, 'File changed during capture')
    need(expected is None or pin(body) == expected, 'Committed content changed')
    return body


def write(path, body):
    need(type(body) is bytes and len(body) <= 2 * 1024**2, 'Bounded operator metadata')
    fd = os.open(ordinary(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as f:
        f.write(body); f.flush(); os.fsync(f.fileno())
    return pin(body)


def module(name, path, body):
    value = types.ModuleType(name); value.__file__ = str(path)
    sys.modules[name] = value
    exec(compile(body, str(path), 'exec'), value.__dict__)
    return value


def source_identity(root):
    own = {name: read(HERE / name, 131072) for name in OWN}
    bindings = decode(own['SOURCE_BINDINGS.json'])
    need(bindings['schema'] == 'neural077_image_programme_sources_v1', 'Exact source binding schema')
    repo = ordinary(root).parents[3]
    bodies = {}
    for relative, expected in bindings['members'].items():
        need(relative.startswith('benchmarks/') and '..' not in Path(relative).parts, 'Repository relative source')
        bodies[relative] = read(repo / relative, 131072, expected)
    return {'own': {k: pin(v) for k, v in own.items()}, 'dependencies': bindings}, own, bodies


def dependencies(implementations_root=None):
    root = ordinary(implementations_root or HERE.parent)
    identity, own, bodies = source_identity(root)
    old = root / 'visual-provider-pair-v1'
    support = module('n077_image_donor_support', old / 'support.py', bodies[PREFIX + 'visual-provider-pair-v1/support.py'])
    deps = support.load(root)
    previous = sys.modules.get('support')
    try:
        sys.modules['support'] = support
        provider = module('n077_image_donor_provider', old / 'provider_arm.py', bodies[PREFIX + 'visual-provider-pair-v1/provider_arm.py'])
    finally:
        if previous is None:
            sys.modules.pop('support', None)
        else:
            sys.modules['support'] = previous
    adapter = module('n077_image_permission_adapter', HERE / 'adapters.py', own['adapters.py'])
    deps.update(provider=provider, adapter=adapter, identity=identity,
                donor_transport_body=bodies[PREFIX + 'visual-provider-pair-v1/transport.py'],
                bundle=deps['original']['pair'].bundle)
    deps['image_transport'] = adapter.make_transport(deps, identity['own']['adapters.py'])
    protected, comparator, derivation = adapter.make_compare(
        deps, bodies[PREFIX + 'visual-provider-pair-v1/protected_compare.py'],
        bodies[PREFIX + 'paired-condition-v1/compare.py'])
    deps.update(image_protected=protected, image_comparator=comparator, compare_derivation=derivation)
    need(source_identity(root)[0] == identity, 'Source changed while loading')
    return deps


def finite_limits(deps, limits, campaign_seconds, max_artifact_bytes):
    need(type(limits) is dict and set(limits) == {'max_actions', 'max_images', 'max_output_bytes', 'wall_seconds'},
         'Exact image action limits')
    deps['transport'].Limits(**limits).validate()
    need(type(campaign_seconds) in (int, float) and math.isfinite(campaign_seconds)
         and limits['wall_seconds'] + 2 < campaign_seconds <= 86400, 'Finite whole campaign')
    need(type(max_artifact_bytes) is int and 0 < max_artifact_bytes <= 1024**4, 'Finite artifact allocation')
    return dict(limits)


def exposure_record(value):
    need(type(value) is dict and set(value) == {'schema', 'statement', 'held_query_access_declared', 'provider_output_access_declared'}
         and value['schema'] == 'neural077_image_programme_exposure_v1'
         and type(value['statement']) is str and 0 < len(value['statement']) <= 8192
         and value['held_query_access_declared'] is False and value['provider_output_access_declared'] is False,
         'Explicit pre-query authoring exposure declaration required')
    return value


def freeze(bundle_root, manifest_file, exposure_file, packet, python, output, *, limits,
           campaign_seconds, max_artifact_bytes, protected_roots, implementations_root=None):
    deps = dependencies(implementations_root)
    root, packet = deps['root'], protected_path(packet)
    output = disjoint(output, root, bundle_root, manifest_file, exposure_file, packet)
    need(not output.exists(), 'Fresh freeze output')
    limits = finite_limits(deps, limits, campaign_seconds, max_artifact_bytes)
    roots = sorted(set(str(protected_path(p)) for p in protected_roots))
    need(roots and any(packet.is_relative_to(Path(p)) for p in roots), 'Declared protected roots must contain packet')
    frozen = deps['bundle'].capture(bundle_root, decode(read(manifest_file, 32768)))
    exposure = exposure_record(decode(read(exposure_file, 16384)))
    executable = ordinary(python).resolve(strict=True)
    need(any(executable.is_relative_to(p) for p in READABLE), 'Interpreter must fit unchanged runtime policy')
    runtime = {'path': str(executable), **pin(read(executable, 64 * 1024**2))}
    sandbox = {'path': '/usr/bin/sandbox-exec', **pin(read('/usr/bin/sandbox-exec', 1048576))}
    # This is source metadata only. No packet members or held waveforms are opened.
    _, modules = deps['transport'].v.dependencies(root)
    packet_members = {k: {'bytes': n, 'sha256': h} for k, (n, h) in modules['exporter'].PINS.items()}
    contract = {'schema': 'neural077_image_programme_frozen_v1', 'condition': CONDITION,
                'queries': COUNT, 'demonstrations': 4, 'source': deps['identity'],
                'packet_path': str(packet), 'packet_members': packet_members, 'bundle': frozen,
                'exposure': exposure, 'exposure_scope': 'operator_declaration_not_hidden_pretraining_proof',
                'runtime': runtime, 'sandbox_executable': sandbox, 'protected_roots': roots,
                'limits': limits, 'campaign_seconds': campaign_seconds, 'max_artifact_bytes': max_artifact_bytes,
                'frozen_monotonic': time.monotonic(), 'clock_scope': 'trusted_operator_same_host_monotonic',
                'permission_adapter': deps['image_transport'].participant_permission_adapter,
                'compare_derivation': deps['compare_derivation'], 'scientific_qualification': False}
    need(source_identity(root)[0] == deps['identity'], 'Source changed before freeze')
    output.mkdir(mode=0o700)
    # Persist programme/config/exposure/source before the clock compared with A.
    commitment = {k:v for k,v in contract.items() if k != 'frozen_monotonic'}
    contract['commitment'] = write(output / 'COMMITMENT.json', encode(commitment))
    contract['frozen_monotonic'] = time.monotonic()
    receipt = write(output / 'FROZEN.json', encode(contract))
    return {'status': 'frozen_before_packet_access', 'contract': receipt, 'private_target_reads': 0,
            'query_payload_reads': 0, 'scientific_qualification': False}


def validate_frozen(frozen, expected_pin, deps):
    raw = read(frozen, 2 * 1024**2, expected_pin)
    c = decode(raw)
    keys = {'schema','condition','queries','demonstrations','source','packet_path','packet_members','bundle','exposure',
            'exposure_scope','runtime','sandbox_executable','protected_roots','limits','campaign_seconds','max_artifact_bytes',
            'frozen_monotonic','clock_scope','permission_adapter','compare_derivation','scientific_qualification','commitment'}
    need(set(c) == keys and c['schema'] == 'neural077_image_programme_frozen_v1' and c['condition'] == CONDITION
         and type(c['queries']) is int and c['queries'] == COUNT and c['demonstrations'] == 4,
         'Exact complete image programme contract')
    need(c['source'] == deps['identity'] == source_identity(deps['root'])[0], 'Committed source changed')
    committed = read(Path(frozen).parent / 'COMMITMENT.json', 2 * 1024**2, c['commitment'])
    need(committed == encode({k:v for k,v in c.items() if k not in ('frozen_monotonic','commitment')}),
         'Persisted programme/config/exposure commitment changed')
    exposure_record(c['exposure'])
    need(c['exposure_scope'] == 'operator_declaration_not_hidden_pretraining_proof'
         and c['clock_scope'] == 'trusted_operator_same_host_monotonic' and c['scientific_qualification'] is False,
         'Declared qualification scope')
    need(type(c['frozen_monotonic']) in (int, float) and math.isfinite(c['frozen_monotonic'])
         and c['frozen_monotonic'] > 0, 'Finite recorded freeze clock')
    finite_limits(deps, c['limits'], c['campaign_seconds'], c['max_artifact_bytes'])
    roots = [protected_path(p) for p in c['protected_roots']]
    packet = protected_path(c['packet_path'])
    need(roots and any(packet.is_relative_to(p) for p in roots), 'Frozen protected packet roots')
    for name in ('runtime', 'sandbox_executable'):
        row = c[name]
        need(set(row) == {'path','bytes','sha256'}, 'Exact runtime descriptor')
        read(row['path'], 64 * 1024**2, {k: row[k] for k in ('bytes','sha256')})
    need(c['sandbox_executable']['path'] == '/usr/bin/sandbox-exec'
         and any(Path(c['runtime']['path']).is_relative_to(p) for p in READABLE), 'Unchanged permitted runtime route')
    _, modules = deps['transport'].v.dependencies(deps['root'])
    need(c['packet_members'] == {k: {'bytes': n, 'sha256': h} for k,(n,h) in modules['exporter'].PINS.items()},
         'Original complete packet identity')
    client = deps['bundle'].verify(c['bundle'])
    need(c['permission_adapter'] == deps['image_transport'].participant_permission_adapter
         and c['compare_derivation'] == deps['compare_derivation'], 'Exact transformed condition identity')
    return c, client


def packet_data(deps, contract):
    data = deps['provider'].dataset_for(deps, contract['packet_path'])
    need(data['packet'] == {k: p['sha256'] for k,p in contract['packet_members'].items()}, 'Frozen packet drift')
    return data


def audit_programme_episode(root, data, ordinal, deps, contract, client):
    t = deps['image_transport']; root = ordinary(root); client = protected_path(client)
    need(pin(read(client, 1048576)) == contract['bundle']['launcher'], 'Frozen launcher changed')
    manifest = decode(read(root / 'transport/MANIFEST.json', 32768))
    need(manifest.get('sandbox') == 'macos', 'Production programme requires macOS sandbox')
    profile = t.sandbox_profile(client)
    need(read(root / 'transport/sandbox.sb', 32768) == profile.encode(), 'Exact frozen sandbox profile required')
    expected = t.boundary_manifest(t.Limits(**contract['limits']), 'macos', client, manifest.get('episode_id'), profile)
    need(manifest == expected, 'Frozen client/limits/permission profile mismatch')
    return t.audit_transport(root, data, ordinal, 'four_demo')


def tree_bytes(root):
    total = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            ordinary(Path(base) / name)
        for name in files:
            path = ordinary(Path(base) / name); info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Ordinary output tree')
            total += info.st_size
    return total


@contextmanager
def deadline(seconds):
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'No inherited campaign timer')
    def stop(signum, frame):
        raise TimeoutError('Whole programme campaign deadline')
    old = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGTERM)}
    try:
        for s in old: signal.signal(s, stop)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for s,h in old.items(): signal.signal(s,h)


def run_programme(frozen, frozen_pin, output, *, implementations_root=None):
    deps = dependencies(implementations_root)
    c, client_body = validate_frozen(frozen, frozen_pin, deps)
    output = disjoint(output, deps['root'], frozen, c['packet_path'], *c['protected_roots'])
    need(not output.exists() and sys.platform == 'darwin', 'Fresh macOS programme execution required')
    # Reserve initial metadata, one complete episode and durable closeout before queries.
    reserve = 2*c['limits']['max_output_bytes'] + c['limits']['max_actions']*65536 + 1048576
    need(len(client_body)+262144+reserve+COLLECTION_RESERVE+FINAL_RESERVE <= c['max_artifact_bytes'],
         'Artifact cap cannot hold initial episode and closeout reserve')
    # Frozen descriptor and source verification precede any viewer packet loading.
    output.mkdir(mode=0o700)
    started = time.monotonic(); completed = []; initial_frames = []
    try:
        with deadline(c['campaign_seconds']):
            client = output / 'CLIENT.py'; write(client, client_body)
            data = packet_data(deps, c)
            (output / 'sessions').mkdir(mode=0o700)
            manifest = {'schema':'neural077_image_programme_campaign_v1','condition':CONDITION,
                        'contract':frozen_pin,'source':deps['identity'],'packet':data['packet'],
                        'queries':COUNT,'demonstrations':4,'started_monotonic':started,
                        'deadline':started+c['campaign_seconds'],'limits':c['limits'],
                        'client':pin(client_body),'runtime':c['runtime'],'sandbox_executable':c['sandbox_executable'],
                        'sandbox':'macos','retry_policy':'none','private_target_reads':0,'scoring_performed':False}
            write(output / 'MANIFEST.json', encode(manifest))
            for i in range(COUNT):
                need(time.monotonic()+c['limits']['wall_seconds']+2 < manifest['deadline'], 'Whole campaign reserve exhausted')
                # Viewer and transport retain separate copies; reserve their finite full bounds.
                need(tree_bytes(output)+reserve+COLLECTION_RESERVE+FINAL_RESERVE <= c['max_artifact_bytes'],
                     'Remaining artifact allocation exhausted')
                row = deps['image_transport'].run_episode(data,i,'four_demo',output/'sessions'/f'{i:03d}',client,
                        c['runtime']['path'],'macos',deps['transport'].Limits(**c['limits']))
                need(row['status']=='valid_unscored', 'First failed programme query stops campaign')
                audit_programme_episode(output/'sessions'/f'{i:03d}',data,i,deps,c,client)
                completed.append(pin(read(output/'sessions'/f'{i:03d}/transport/END.json',32768)))
                initial_frames.append(pin(read(output/'sessions'/f'{i:03d}/transport/0000-out.bin',5*1024**2)))
            collection = deps['image_transport'].collect(c['packet_path'],output/'sessions','four_demo',output/'collection',deps['root'])
            need(source_identity(deps['root'])[0] == deps['identity'], 'Source drift after programme')
            for key in ('runtime','sandbox_executable'):
                read(c[key]['path'],64*1024**2,{k:c[key][k] for k in ('bytes','sha256')})
            finished = time.monotonic()
            need(finished <= manifest['deadline'] and tree_bytes(output)+FINAL_RESERVE <= c['max_artifact_bytes'],
                 'Whole campaign exceeded allocation or closeout reserve')
            record = {'schema':'neural077_image_programme_arm_v1','status':'closed_unscored_image_programme_arm',
                      'condition':CONDITION,'queries':COUNT,'demonstrations':4,'contract':frozen_pin,
                      'manifest':pin(read(output/'MANIFEST.json',262144)),'episodes':completed,'initial_frames':initial_frames,
                      'collection':pin(read(output/'collection/TRANSPORT_COMPLETE.json',16384)),
                      'submission':pin(read(output/'collection/submission.npz',1048576)),
                      'finished_monotonic':finished,'sandbox':'macos','private_target_reads':0,'scoring_performed':False,
                      'os_enforcement_independently_qualified':False,'scientific_qualification':False}
            body=encode(record)
            need(len(body)<=FINAL_RESERVE and tree_bytes(output)+len(body)<=c['max_artifact_bytes'], 'Final ARM quota')
            write(output/'ARM.json',body); return record
    except BaseException as error:
        body=encode({'status':'unscoreable_image_programme_arm','completed_queries':len(completed),
              'error_type':type(error).__name__,'retry_allowed':False,'private_target_reads':0,'scoring_performed':False})
        need(len(body)<=FINAL_RESERVE and tree_bytes(output)+len(body)<=c['max_artifact_bytes'], 'Failure closeout quota')
        write(output/'FAILED.json',body)
        raise


def admit_programme(root, expected_receipt, contract, deps):
    root = protected_path(root)
    need({p.name for p in root.iterdir()} == {'CLIENT.py','MANIFEST.json','sessions','collection','ARM.json'},
         'Complete programme inventory required')
    raw = read(root/'ARM.json',262144,expected_receipt); arm = decode(raw)
    fixed = {'schema':'neural077_image_programme_arm_v1','status':'closed_unscored_image_programme_arm',
             'condition':CONDITION,'queries':COUNT,'demonstrations':4,'sandbox':'macos','private_target_reads':0,
             'scoring_performed':False,'os_enforcement_independently_qualified':False,'scientific_qualification':False}
    need(set(arm)==set(fixed)|{'contract','manifest','episodes','initial_frames','collection','submission','finished_monotonic'}
         and all(type(arm.get(k)) is type(v) and arm[k]==v for k,v in fixed.items()), 'Exact complete programme arm')
    need(arm['contract'] == pin(encode(contract)), 'Arm/frozen contract mismatch')
    need(type(arm['episodes']) is list and len(arm['episodes'])==COUNT
         and type(arm['initial_frames']) is list and len(arm['initial_frames'])==COUNT
         and {p.name for p in (root/'sessions').iterdir()} == {f'{i:03d}' for i in range(COUNT)}, 'All400 first responses required')
    manifest = decode(read(root/'MANIFEST.json',262144,arm['manifest']))
    need(manifest.get('schema')=='neural077_image_programme_campaign_v1' and manifest.get('contract')==arm['contract']
         and manifest.get('source')==deps['identity'] and manifest.get('queries')==COUNT and manifest.get('demonstrations')==4
         and manifest.get('condition')==CONDITION and manifest.get('limits')==contract['limits']
         and manifest.get('client')==contract['bundle']['launcher'] and manifest.get('runtime')==contract['runtime']
         and manifest.get('sandbox_executable')==contract['sandbox_executable'] and manifest.get('sandbox')=='macos'
         and manifest.get('retry_policy')=='none' and manifest.get('private_target_reads')==0
         and manifest.get('scoring_performed') is False, 'Frozen programme campaign metadata')
    need(all(type(manifest.get(k)) in (int,float) and math.isfinite(manifest[k]) for k in ('started_monotonic','deadline'))
         and type(arm['finished_monotonic']) in (int,float) and math.isfinite(arm['finished_monotonic'])
         and contract['frozen_monotonic'] <= manifest['started_monotonic'] <= arm['finished_monotonic'] <= manifest['deadline']
         and manifest['deadline']==manifest['started_monotonic']+contract['campaign_seconds'], 'Programme frozen clock/closure')
    need(pin(read(root/'CLIENT.py',1048576)) == contract['bundle']['launcher'], 'Frozen programme bytes changed')
    data = packet_data(deps,contract)
    need(data['packet']==manifest['packet'], 'Programme packet mismatch')
    probabilities=[]; episode_ids=[]
    for i in range(COUNT):
        session=root/'sessions'/f'{i:03d}'
        read(session/'transport/0000-out.bin',5*1024**2,arm['initial_frames'][i])
        audit_programme_episode(session,data,i,deps,contract,root/'CLIENT.py')
        need(pin(read(session/'transport/END.json',32768))==arm['episodes'][i], 'First final closure changed')
        m=decode(read(session/'transport/MANIFEST.json',32768)); episode_ids.append(m['episode_id'])
        probabilities.append(data['parser'].parse(read(session/'response.txt',4096),data['rows'][i]['trial_id']))
    need(len(set(episode_ids))==COUNT, 'Unique fresh programme episodes required')
    collection=decode(read(root/'collection/TRANSPORT_COMPLETE.json',16384,arm['collection']))
    need(collection == {'schema':'neural077_transport_collection_v1','status':'complete_unscored_transport_collection',
         'queries':COUNT,'condition':'four_demo','submission_sha256':arm['submission']['sha256'],
         'configuration_sha256':pin(encode({k:v for k,v in m.items() if k!='episode_id'}))['sha256'],
         'scoring_performed':False,'performance_claim':'none','provider_qualification':'not_established'},
         'Complete image transport collection')
    body=read(root/'collection/submission.npz',1048576,arm['submission'])
    ids={case:[r['trial_id'] for r in data['rows'] if r['trial_id'].startswith(case+'-')] for case in deps['original']['pair'].CASES}
    import numpy as np
    with tempfile.TemporaryDirectory(prefix='n077-image-programme-public-') as folder:
        snapshot=Path(folder).resolve()/'submission.npz'; write(snapshot,body)
        data['validator'].validate(snapshot,ids)
        with np.load(io.BytesIO(body),allow_pickle=False) as a:
            need(set(a.files)=={'trial_ids','target_probability'} and a['trial_ids'].tolist()==[r['trial_id'] for r in data['rows']]
                 and np.array_equal(a['target_probability'],np.asarray(probabilities,dtype=np.float64)), 'Submission equals every first response')
    return root/'collection/submission.npz',arm['submission'],pin(raw)


def match_arm_information(provider_root, programme_root, data, deps, contract, a_manifest, b_manifest,
                          provider_receipt, programme_receipt):
    need(a_manifest['packet']==b_manifest['packet']==data['packet']
         and a_manifest['queries']==b_manifest['queries']==COUNT
         and a_manifest['demonstrations']==b_manifest['demonstrations']==4,
         'Same complete public packet and demonstration budget required')
    need(a_manifest['limits']['transport']==b_manifest['limits']==contract['limits'], 'Same available viewer action/byte/time limits required')
    need(contract['frozen_monotonic']<=a_manifest['started_monotonic']
         and contract['frozen_monotonic']<=b_manifest['started_monotonic'], 'Programme freeze must precede both query campaigns')
    aa=decode(read(Path(provider_root)/'ARM.json',262144,provider_receipt))
    bb=decode(read(Path(programme_root)/'ARM.json',262144,programme_receipt))
    need(decode(read(Path(provider_root)/'MANIFEST.json',65536,aa['manifest']))==a_manifest
         and decode(read(Path(programme_root)/'MANIFEST.json',262144,bb['manifest']))==b_manifest,
         'Matched manifests retain admitted arm custody')
    for i in range(COUNT):
        client_end=decode(read(Path(provider_root)/'providers'/f'{i:03d}/custody/CLIENT_END.json',65536,aa['episodes'][i]['client_end']))
        a,png_a=deps['transport'].unpack(read(Path(provider_root)/'sessions'/f'{i:03d}/transport/0000-out.bin',
                                            5*1024**2,client_end['initial_frame']))
        b,png_b=deps['transport'].unpack(read(Path(programme_root)/'sessions'/f'{i:03d}/transport/0000-out.bin',
                                            5*1024**2,bb['initial_frames'][i]))
        expected=dict(a); expected['episode_id']=b['episode_id']; expected['prompt']=deps['adapter'].programme_prompt(a['prompt'])
        need(b==expected and png_a==png_b, 'Same initial raster/header apart from explicit permission and episode identity')
    return {'same_public_packet':True,'same_available_demonstrations':True,'same_available_actions_and_limits':True,
            'same_initial_raster_bytes':True,'remote_png_encoding_bytes_identical_claimed':False,
            'remote_initial_pixel_equivalence':'established_by_existing_provider_codec_audit',
            'later_viewer_trajectories_identical_claimed':False,'equal_information_proven':False,
            'clock_order_scope':'trusted_operator_same_host_monotonic_not_external_timestamp_attestation'}


def _ordered_pair(admit_a, admit_b, match, score):
    a=admit_a(); b=admit_b(); matching=match(); return score(a,b,matching)


def compare(provider_root, provider_receipt, programme_root, programme_receipt, frozen_file, frozen_pin,
            private_locations, output, *, implementations_root=None):
    deps=dependencies(implementations_root); c,_=validate_frozen(frozen_file,frozen_pin,deps)
    output=disjoint(output,deps['root'],provider_root,programme_root,frozen_file,c['packet_path'],private_locations)
    need(not output.exists(), 'Fresh paired evaluation output')
    output.mkdir(mode=0o700)
    accounting={'both_public_validated_before_private':False,'private_reference_attempts':0,
                'target_loader_attempts':0,'temporary_submission_bytes_created':0}
    try:
        def matching():
            data=packet_data(deps,c)
            aa=decode(read(Path(provider_root)/'ARM.json',262144,provider_receipt))
            bb=decode(read(Path(programme_root)/'ARM.json',262144,programme_receipt))
            am=decode(read(Path(provider_root)/'MANIFEST.json',65536,aa['manifest']))
            bm=decode(read(Path(programme_root)/'MANIFEST.json',262144,bb['manifest']))
            return match_arm_information(provider_root,programme_root,data,deps,c,am,bm,provider_receipt,programme_receipt)
        def score(a,b,matched):
            # Only reached after both400 first-response arms and matching pass.
            location=protected_path(private_locations)
            roots=[Path(p) for p in c['protected_roots']]
            need(any(location.is_relative_to(p) for p in roots), 'Private descriptor outside frozen protected roots')
            original=deps['original']['pair']
            private_pair=types.SimpleNamespace(**original.__dict__)
            captured=[]
            def frozen_read(path,cap=1048576,expected=None):
                if ordinary(path)==location:
                    # The unchanged protected loader reaches this only after both validators.
                    if not captured:
                        body=read(location,65536); locations=decode(body)
                        paths=[locations['reference_grade'],locations['reference_commit'],*locations['targets'].values()]
                        for item in paths:
                            item=protected_path(item)
                            need(any(item.is_relative_to(p) for p in roots), 'Actual private operand outside frozen protected roots')
                        captured.append(body)
                    need(expected is None or pin(captured[0])==expected,'Private descriptor pin'); return captured[0]
                return original.read(path,cap,expected)
            private_pair.read=frozen_read
            data=packet_data(deps,c)
            ids={case:[r['trial_id'] for r in data['rows'] if r['trial_id'].startswith(case+'-')] for case in original.CASES}
            result=deps['image_protected'].protected_compare(private_pair,deps['image_comparator'],deps['original']['original_bodies'],
                     (a,b),ids,location,accounting,('four_demo',CONDITION))
            result.update(operator_route='visual_provider_vs_frozen_image_programme_v1',matching=matched,
                          source=deps['identity'],compare_derivation=deps['compare_derivation'],programme_contract=frozen_pin,
                          participant_code_executed_in_evaluator=False,remote_context_qualified=False,
                          os_enforcement_independently_qualified=False,scientific_qualification=False,accounting=accounting)
            write(output/'RESULT.json',encode(result)); return result
        return _ordered_pair(lambda:deps['provider'].admit_arm(provider_root,provider_receipt,c['packet_path'],deps),
                             lambda:admit_programme(programme_root,programme_receipt,c,deps),matching,score)
    except BaseException as error:
        write(output/'FAILED.json',encode({'status':'unscored_failure','error_type':type(error).__name__,
                                          'accounting':accounting,'retry_allowed':False})); raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    f=sub.add_parser('freeze')
    for name in ('bundle-root','manifest-file','exposure-file','packet','python','output'): f.add_argument('--'+name,required=True)
    f.add_argument('--protected-root',action='append',dest='protected_roots',required=True)
    f.add_argument('--limits',required=True,help='JSON file containing existing transport Limits')
    f.add_argument('--campaign-seconds',type=float,required=True); f.add_argument('--max-artifact-bytes',type=int,required=True)
    r=sub.add_parser('run-programme')
    for name in ('frozen','output'): r.add_argument('--'+name,required=True)
    r.add_argument('--frozen-bytes',type=int,required=True); r.add_argument('--frozen-sha256',required=True)
    c=sub.add_parser('compare')
    for name in ('provider-root','programme-root','frozen-file','private-locations','output'): c.add_argument('--'+name,required=True)
    for name in ('provider','programme','frozen'):
        c.add_argument('--'+name+'-bytes',type=int,required=True); c.add_argument('--'+name+'-sha256',required=True)
    args=vars(parser.parse_args(argv)); command=args.pop('command')
    if command=='freeze':
        args['limits']=decode(read(args['limits'],16384)); result=freeze(**args)
    else:
        args['frozen_pin']={'bytes':args.pop('frozen_bytes'),'sha256':args.pop('frozen_sha256')}
        if command=='compare':
            for name in ('provider','programme'):
                args[name+'_receipt']={'bytes':args.pop(name+'_bytes'),'sha256':args.pop(name+'_sha256')}
            result=compare(**args)
        else: result=run_programme(**args)
    print(result['status']); return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print('Refused: '+type(error).__name__,file=sys.stderr); raise SystemExit(2)
