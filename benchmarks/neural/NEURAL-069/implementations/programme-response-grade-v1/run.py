"""Observe the original complete programme, validate public bytes, then grade separately."""
import time
ORIGIN = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import types
import uuid

HERE = Path(__file__).resolve().parent
DISK_FLOOR = 60 * 1024**3
EXTRA_BYTES = 32 * 1024**2
CLI_ACTIVE = False


def runtime_check(b):
    import numpy
    b.need(sys.version_info[:3] == (3, 12, 8) and numpy.__version__ == '2.2.6',
           'Original selected Python3.12.8/NumPy2.2.6 environment; not inherited scorer qualification')


def load_bridge(expected):
    def bounded(filename, cap):
        with filename.open('rb') as stream:
            raw = stream.read(cap + 1)
        if len(raw) > cap:
            raise ValueError('Bounded startup source')
        return raw
    raw = bounded(HERE / 'SOURCE.json', 65536)
    if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != expected:
        raise ValueError('Externally frozen source manifest')
    manifest = json.loads(raw)
    filename = HERE / 'bridge.py'
    body = bounded(filename, 1048576)
    identity = manifest['files'][str(filename.relative_to(HERE.parents[4]))]
    if {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} != identity:
        raise ValueError('Pinned bridge source')
    value = types.ModuleType('neural069_bridge')
    value.__file__ = str(filename)
    exec(compile(body, str(filename), 'exec'), value.__dict__)
    value.source(expected)
    return value


def limits(seconds, memory):
    return {'setup_seconds': 30, 'producer_seconds': seconds, 'capture_seconds': 15, 'cleanup_seconds': 15,
            'memory_bytes': memory, 'cpu_nanos': 1000000000, 'pids': 64, 'scratch_bytes': 64 * 1024**2,
            'max_files': 3, 'max_directories': 1, 'max_file_bytes': 1000000, 'max_output_bytes': 1048576,
            'manifest_bytes': 16384, 'max_cli_calls': 128, 'max_cli_bytes': 4194304,
            'inventory_bytes': 65536, 'source_read_bytes': 134217728, 'host_write_bytes': 8388608}


def setup(b, configuration, source_pin, origin):
    cfg = b.parse(b.read(configuration, 32768))
    b.need(set(cfg) == {'schema', 'source', 'producer_review', 'numeric_authority', 'operator_output',
                       'grade_control_root', 'grade_quarantine_root'}, 'Exact operator configuration')
    b.need(cfg['schema'] == 'neural069_programme_response_configuration_v1' and cfg['source'] == source_pin,
           'Exact source-bound configuration')
    manifest, captured = b.source(source_pin)
    original = b.original(captured)
    adapter = original[0]
    selected = cfg['producer_review']
    review_pin = {k: selected[k] for k in ('bytes', 'sha256')}
    review = b.parse(b.read(selected['path'], 32768, review_pin))
    record = cfg['numeric_authority']
    authority_pin = {k: record[k] for k in ('bytes', 'sha256')}
    authority = b.parse(b.read(record['path'], 32768, authority_pin))
    b.need(set(authority) == {'schema', 'source', 'producer_review', 'approved', 'numeric_reference_calls',
        'image', 'image_inventory_sha256', 'docker_binary', 'grade_resources', 'holder_memory_bytes',
        'holder_cpu_nanos', 'outside_reserved_bytes', 'additional_artifact_bytes', 'public_validation_seconds',
        'host_memory_bytes', 'host_memory_enforcement', 'whole_seconds', 'runtime_versions',
        'runtime_qualification_inherited'}, 'Separate prospective grading and public-custody authority')
    b.need(authority['schema'] == 'neural069_separate_numeric_authority_v1'
           and authority['source'] == source_pin and authority['producer_review'] == review_pin
           and authority['approved'] is True and type(authority['numeric_reference_calls']) is int
           and authority['numeric_reference_calls'] == 1 and authority['image'] == adapter.IMAGE
           and re.fullmatch('[0-9a-f]{64}', authority['image_inventory_sha256'])
           and authority['runtime_versions'] == {'python': '3.12.8', 'numpy': '2.2.6'}
           and authority['runtime_qualification_inherited'] is False, 'Explicit separate fixed-image authority')
    resources = authority['grade_resources']
    seconds, memory = resources['producer_seconds'], resources['memory_bytes']
    b.need(type(seconds) is int and 1 <= seconds <= 7200 and type(memory) is int
           and 268435456 <= memory <= 8 * 1024**3 and memory % 1048576 == 0
           and resources == limits(seconds, memory), 'Explicit bounded numeric phase')
    b.need(authority['holder_memory_bytes'] == 134217728 and authority['holder_cpu_nanos'] == 1000000000
           and authority['host_memory_bytes'] == 1073741824 and authority['host_memory_enforcement'] == 'cooperative',
           'Holder and public-validation memory scope; host is not an OS memory sandbox')
    outside, validation = authority['outside_reserved_bytes'], authority['public_validation_seconds']
    b.need(type(outside) is int and outside >= 0 and type(validation) is int and 1 <= validation <= 300
           and authority['additional_artifact_bytes'] == EXTRA_BYTES, 'Additional complete-custody allocation')
    b.need(review['resources']['other_bytes'] == outside + EXTRA_BYTES + DISK_FLOOR - 21474836480,
           'Original ongoing floor includes new custody and current sixty-GiB floor')
    b.need(authority['whole_seconds'] == review['resources']['candidate_seconds'] + 480 + 180 + validation + seconds + 60 + 30,
           'Original programme, public-validation, numerical, outer and cleanup clocks all allocated')
    args = types.SimpleNamespace(program=Path(review['program']['path']), output=Path(review['output']),
                                 review=Path(selected['path']), other_reserve_bytes=review['resources']['other_bytes'])
    prepared = adapter.prepare(args, origin)
    b.need(prepared['review_pin'] == review_pin, 'Same captured review on original validation')
    for key in ('operator_output', 'grade_control_root', 'grade_quarantine_root'):
        b.need(type(cfg[key]) is str and Path(cfg[key]).is_absolute(), 'Absolute operator custody path')
        b.path(cfg[key])
    b.need(type(authority['docker_binary']) is str and Path(authority['docker_binary']).is_absolute(),
           'Explicit numeric provider Docker binary path')
    return cfg, authority, authority_pin, original, prepared, manifest, captured


def observe_producer(b, cfg, original, prepared, output, origin, deadline):
    adapter, child, supervisor, lock = original
    review = prepared['review']
    # Original child reserves 40 seconds for owned emergency reaping.
    end = min(deadline, origin + review['resources']['candidate_seconds'] + 480 + 150)
    b.need(time.monotonic() + review['resources']['candidate_seconds'] + 480 + 40 < end,
           'Full original adapter interval and original cleanup reserve remain')
    argv = [sys.executable, '-I', '-S', '-B', str(adapter.HERE / 'run_program.py'),
            '--program', review['program']['path'], '--output', review['output'],
            '--review', cfg['producer_review']['path'], '--other-reserve-bytes', str(review['resources']['other_bytes'])]
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'LD_', 'DYLD_'))
           and k not in ('DOCKER_HOST', 'DOCKER_CONTEXT')}
    for key, value in review['environment'].items():
        b.need(os.environ.get(key) == value, 'Original reviewed inherited environment')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    b.save(output / 'PRODUCER_INTENT.json', b.encode({'argv': argv, 'review': prepared['review_pin'], 'deadline': end}))
    try:
        terminal, record = child.child(argv, end, env)
    except child.ChildFailure as exc:
        b.save(output / 'PRODUCER_PROCESS_FAILURE.json', b.encode(exc.record))
        raise
    b.save(output / 'PRODUCER_PROCESS.json', b.encode(record))
    admitted = b.admit_producer(original, prepared, terminal, record)
    b.save(output / 'PRODUCER_ADMITTED.json', b.encode(admitted))
    return admitted


def public_custody(b, admitted, captured, output, seconds):
    """Complete public validation finishes before constructing any target mounts."""
    old = signal.getitimer(signal.ITIMER_REAL)
    b.need(CLI_ACTIVE and old[0] > 0, 'Public stage uses the dedicated enclosing CLI timer')
    start = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, min(old[0], seconds))
    try:
        return _public_custody(b, admitted, captured, output, seconds)
    finally:
        signal.setitimer(signal.ITIMER_REAL, max(.001, old[0] - (time.monotonic() - start)))


def _public_custody(b, admitted, captured, output, seconds):
    end = time.monotonic() + seconds
    scorer = HERE.parent / 'response-scorer-v1'
    identities = {name: b.pin(captured[str(scorer / (name + '.py'))]) for name in b.NUMERICAL}
    packet = b.path(admitted['packet'])
    # Metadata authentication only. No protected target path/stat/body in this phase.
    b.read(packet / 'private/DATA_BINDING.json', 2_000_000, b.BINDING)
    b.read(packet / 'public/input/ROSTER.json', 2_000_000, b.ROSTER)
    with b.numerical_modules(scorer, identities) as modules:
        contract, bodies = b.validate_public(modules, packet, b.BINDING['sha256'], admitted['submission'], admitted['outputs'])
    b.need(time.monotonic() < end, 'Complete public-validation deadline')
    receipt = b.publish_public(output / 'validated', contract, bodies, admitted['outputs'])
    b.need(time.monotonic() < end, 'Public-custody publication deadline')
    return {'receipt': receipt, 'contract': contract, 'directory': output / 'validated', 'numerical_sources': identities}


def score_native(b, cfg, authority, authority_pin, original, captured, admitted, custody,
                 output, origin, deadline, source_pin):
    b.need(CLI_ACTIVE, 'Production numerical execution requires the dedicated enclosing CLI timer')
    need_complete = custody['receipt']
    b.need(need_complete['outputs'] == admitted['outputs'] and need_complete['private_target_files_accessed'] is False
           and need_complete['complete_cases'] == 80, 'Complete public-only validation must precede any target mount')
    packet, contract = b.path(admitted['packet']), custody['contract']
    Provider, mount_identity, provider_source = b.transport(captured)
    def file(filename, identity, purpose='operator_reference'):
        return {'path': str(b.path(filename)), 'kind': 'file', 'purpose': purpose,
                'files': {Path(filename).name: identity}}
    mounts = {}
    for name, identity in admitted['outputs'].items():
        mounts['/submission/' + name] = file(custody['directory'] / name, identity, 'input')
    mounts['/packet/private/DATA_BINDING.json'] = file(packet / 'private/DATA_BINDING.json', b.BINDING)
    mounts['/packet/public/input/ROSTER.json'] = file(packet / 'public/input/ROSTER.json', b.ROSTER)
    target_names = set()
    for row in contract['binding']['cases']:
        target = row['target']
        name = target['path']
        b.need(type(name) is str and name.startswith('private/targets/') and '..' not in Path(name).parts
               and str(Path(name)) == name and name not in target_names, 'Exact distinct packet-relative target')
        target_names.add(name)
        mounts['/packet/' + name] = file(packet / name, {k: target[k] for k in ('bytes', 'sha256')})
    b.need(len(target_names) == 80, 'Full original target panel')
    scorer = HERE.parent / 'response-scorer-v1'
    for name, identity in custody['numerical_sources'].items():
        mounts['/library/scorer/' + name + '.py'] = file(scorer / (name + '.py'), identity)
    for name in ('bridge.py', 'grade_worker.py'):
        mounts['/library/' + name] = file(HERE / name, b.pin(captured[str(HERE / name)]))
    invocation = {'schema': 'neural069_response_grade_invocation_v1', 'source': source_pin,
                  'outputs': admitted['outputs'], 'binding_sha256': b.BINDING['sha256'],
                  'numerical_sources': custody['numerical_sources'],
                  'bridge_source': b.pin(captured[str(HERE / 'bridge.py')]), 'public_validation': need_complete}
    invocation_path = output / 'NUMERIC_INVOCATION.json'
    invocation_pin = b.save(invocation_path, b.encode(invocation), 0o444)
    mounts['/invocation.json'] = file(invocation_path, invocation_pin)
    command = ['/usr/local/bin/python', '-I', '-B', '/library/grade_worker.py']
    exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'reference', 'image': authority['image'],
                'source': source_pin, 'command': command, 'mounts': mount_identity(mounts),
                'approved_image_inventory_sha256': authority['image_inventory_sha256'],
                'boundary_audit': authority_pin, 'role_boundary_verified': True}
    exposure_path = output / 'NUMERIC_EXPOSURE.json'
    exposure_pin = b.save(exposure_path, b.encode(exposure))
    provider = Provider(cfg['grade_control_root'], cfg['grade_quarantine_root'], authority['docker_binary'],
                        admitted['docker_socket'],
                        b.pin(captured[str(provider_source / 'SOURCE_MANIFEST.json')]),
                        {exposure_pin['sha256']: str(exposure_path)}, 135266304, 8388608)
    phase = 'neural069-grade-' + uuid.uuid4().hex
    request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': phase, 'action': 'held_attempt',
               'role': 'reference', 'image': authority['image'], 'command': command, 'workdir': '/work',
               'source': source_pin, 'exposure': exposure_pin, 'clock': {'origin': origin, 'phase_deadline': deadline},
               'resources': authority['grade_resources'], 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
    b.save(output / 'NUMERIC_REQUEST.json', b.encode(request))
    returned = provider.execute_phase(request, mounts, deadline, lambda *_: None)
    observed = provider.observe(phase, b.pin(b.encode(request))['sha256'], returned['receipt_pin'], deadline)
    receipt = observed['receipt']
    b.need(receipt['status'] == 'captured' and receipt['producer_closed_before_capture'] is True
           and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True
           and receipt['error'] is None and type(receipt['natural_exit']['ExitCode']) is int
           and receipt['natural_exit']['ExitCode'] == 0 and receipt['natural_exit']['OOMKilled'] is False,
           'Stopped trusted numeric worker and observed resource closure')
    b.need(receipt['source'] == source_pin and receipt['image'] == authority['image']
           and receipt['role'] == 'reference' and receipt['exposure'] == exposure_pin
           and receipt['input_before'] == receipt['input_after'], 'Identical numeric phase input/source exposure')
    directory = b.path(receipt['quarantine_root'])
    b.need(directory == b.path(Path(cfg['grade_quarantine_root']) / phase), 'Exact private capture directory')
    inventory = receipt['output_inventory']
    b.need(inventory['complete'] is True and set(inventory['files']) == {'score.json', 'RESULT.json', 'OUTPUTS.json'},
           'Complete bounded numeric report')
    score = b.parse(b.read(directory / 'score.json', 1000000, inventory['files']['score.json']))
    result = b.parse(b.read(directory / 'RESULT.json', 16384, inventory['files']['RESULT.json']))
    b.need(result == {'schema': 'neural069_response_grade_result_v1', 'status': score['status'],
                      'participant_code_executed': False, 'scientific_qualification': False}
           and score['status'] in ('scored', 'undefined_required_support', 'invalid_submission'), 'Current scorer disposition')
    b.need(score['producer_custody']['outputs'] == admitted['outputs'], 'Score binds every stopped output')
    if score['status'] != 'invalid_submission':
        b.need(score['producer_custody']['complete_capture'] and score['producer_custody']['captured_count'] == 81
               and score['binding_sha256'] == b.BINDING['sha256'] and score['roster_sha256'] == b.ROSTER['sha256']
               and score['analysis']['metric'] == 'participant_macro_roi_macro_voxel_pearson'
               and score['analysis']['legacy_companion']['metric'] == 'participant_macro_family_macro_voxel_pearson',
               'Current primary and separate historical-family companion; same source contract')
    return {'status': score['status'], 'score_path': str(directory / 'score.json'),
            'score': inventory['files']['score.json'], 'provider_receipt': returned['receipt_pin'],
            'source': source_pin, 'outputs': admitted['outputs'], 'public_validation': need_complete,
            'scientific_qualification': False, 'runtime_qualification': False, 'automatic_retry': False}


def main(argv=None, *, origin=ORIGIN):
    global CLI_ACTIVE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-pin', required=True)
    p.add_argument('--configuration', required=True, type=Path)
    args = p.parse_args(argv)
    b = load_bridge(json.loads(args.source_pin))
    b.WRITE_LIMIT = EXTRA_BYTES - 8388608  # Additional provider owns its separate 8 MiB share.
    source_pin = b.parse(args.source_pin)
    b.need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'Standalone enclosing timer')
    output = None
    deadline = origin + 60
    def hard(*unused):
        os._exit(124)
    def stop(*unused):
        signal.signal(signal.SIGALRM, hard)
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
        raise TimeoutError('Whole run deadline or interruption')
    previous = {number: signal.signal(number, stop) for number in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM)}
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
    CLI_ACTIVE = True
    try:
        runtime_check(b)
        cfg, authority, authority_pin, original, prepared, manifest, captured = setup(b, args.configuration, source_pin, origin)
        deadline = origin + authority['whole_seconds']
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - 10 - time.monotonic()))
        destination = b.path(cfg['operator_output'])
        b.need(not destination.exists() and destination.parent.is_dir(), 'Fresh operator output')
        paths = [destination, b.path(prepared['review']['output']), b.path(cfg['grade_control_root']),
                 b.path(cfg['grade_quarantine_root'])]
        b.need(all(a != z and not a.is_relative_to(z) and not z.is_relative_to(a)
                   for i, a in enumerate(paths) for z in paths[i+1:]), 'Disjoint producer and numerical custody roots')
        b.need(shutil.disk_usage(destination.parent).free >= DISK_FLOOR + authority['outside_reserved_bytes']
               + 20300000 + EXTRA_BYTES, 'Current disk floor and complete separate custody allocation')
        destination.mkdir(mode=0o700)
        output = destination
        b.save(output / 'PLAN.json', b.encode({'source': source_pin, 'numeric_authority': authority_pin,
               'producer_review': prepared['review_pin'], 'origin': origin, 'deadline': deadline,
               'additional_artifact_bytes': EXTRA_BYTES, 'public_stage_before_private_target_access': True}))
        admitted = observe_producer(b, cfg, original, prepared, output, origin, deadline - 10)
        b.source(source_pin)
        try:
            custody = public_custody(b, admitted, captured, output, authority['public_validation_seconds'])
        except b.CandidateInvalid as error:
            score_pin = b.save(output / 'score.json', b.encode(error.result))
            b.save(output / 'COMPLETE.json', b.encode({'status': 'invalid_submission', 'score': score_pin,
                   'score_path': str(output / 'score.json'), 'source': source_pin, 'outputs': admitted['outputs'],
                   'private_target_files_accessed': False, 'numeric_phase_dispatched': False,
                   'scientific_qualification': False, 'runtime_qualification': False, 'automatic_retry': False}))
            return 2
        b.need(shutil.disk_usage(output).free >= DISK_FLOOR + authority['outside_reserved_bytes'] + EXTRA_BYTES,
               'Separate reference phase current disk floor')
        result = score_native(b, cfg, authority, authority_pin, original, captured, admitted, custody,
                              output, origin, deadline - 10, source_pin)
        b.need(time.monotonic() < deadline - 10, 'Complete outer interval')
        b.save(output / 'COMPLETE.json', b.encode(result))
        return 0 if result['status'] == 'scored' else 2
    except BaseException as exc:
        if output is not None:
            b.save(output / 'FAILURE.json', b.encode({'error_type': type(exc).__name__, 'source': source_pin,
                'automatic_retry': False, 'native_or_nested_process_cleanup_not_inferred': True,
                'preserve_all_original_and_numeric_receipts': True,
                'outer_cumulative_charged_bytes_before_failure_receipt': b.WRITTEN,
                'whole_wall_seconds': time.monotonic() - origin}))
        raise
    finally:
        CLI_ACTIVE = False
        signal.setitimer(signal.ITIMER_REAL, 0)
        for number, handler in previous.items():
            signal.signal(number, handler)


if __name__ == '__main__':
    raise SystemExit(main())
