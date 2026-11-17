"""Observe the unchanged original producer, then run a separately selected grade."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import time
import types
import uuid

HERE = Path(__file__).resolve().parent
DISK_FLOOR = 60 * 1024**3


def load_bridge(expected):
    # The interpreter entry source is trusted; dependencies execute verified bytes.
    manifest_raw = (HERE / 'SOURCE.json').read_bytes()
    if {'bytes': len(manifest_raw), 'sha256': hashlib.sha256(manifest_raw).hexdigest()} != expected:
        raise ValueError('Externally frozen bridge source manifest')
    manifest = json.loads(manifest_raw)
    filename = HERE / 'bridge.py'
    raw = filename.read_bytes()
    identity = manifest['files'][str(filename.relative_to(HERE.parents[4]))]
    if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != identity:
        raise ValueError('Bridge source bytes differ')
    value = types.ModuleType('neural052_bridge')
    value.__file__ = str(filename)
    exec(compile(raw, str(filename), 'exec'), value.__dict__)
    value.source(expected)
    return value


def limits(seconds, memory):
    return {'setup_seconds': 30, 'producer_seconds': seconds, 'capture_seconds': 15, 'cleanup_seconds': 15,
            'memory_bytes': memory, 'cpu_nanos': 1000000000, 'pids': 64, 'scratch_bytes': 64 * 1024**2,
            'max_files': 3, 'max_directories': 1, 'max_file_bytes': 262144, 'max_output_bytes': 1048576,
            'manifest_bytes': 16384, 'max_cli_calls': 128, 'max_cli_bytes': 4194304,
            'inventory_bytes': 65536, 'source_read_bytes': 512000000, 'host_write_bytes': 2097152}


def setup(b, configuration_path, source_pin):
    cfg = b.parse(b.read(configuration_path, 32768))
    b.need(set(cfg) == {'schema', 'source', 'producer_selection', 'numeric_authority', 'operator_output',
                       'grade_control_root', 'grade_quarantine_root'}, 'Exact operator configuration')
    b.need(cfg['schema'] == 'neural052_full_panel_configuration_v1' and cfg['source'] == source_pin,
           'Exact source-bound configuration')
    manifest, captured = b.source(source_pin)
    original = b.original(captured)
    common, policy, observer, process, binding, legacy_source = original
    selected = cfg['producer_selection']
    selection_pin = {k: selected[k] for k in ('bytes', 'sha256')}
    selection = policy.selection(b.parse(b.read(selected['path'], 32768, selection_pin)), legacy_source)
    record = cfg['numeric_authority']
    authority_pin = {k: record[k] for k in ('bytes', 'sha256')}
    authority = b.parse(b.read(record['path'], 32768, authority_pin))
    b.need(set(authority) == {'schema', 'source', 'producer_source', 'producer_selection', 'image',
                             'image_inventory_sha256', 'grade_resources', 'holder_memory_bytes',
                             'holder_cpu_nanos', 'approved', 'numeric_reference_calls',
                             'outside_reserved_bytes', 'additional_artifact_bytes', 'whole_seconds',
                             'runtime_versions', 'runtime_qualification_inherited'}, 'Separate explicit numeric authority')
    b.need(authority['schema'] == 'neural052_separate_numeric_authority_v1'
           and authority['source'] == source_pin and authority['producer_source'] == legacy_source
           and authority['producer_selection'] == selection_pin and authority['image'] == selection['image']
           and re.fullmatch('[0-9a-f]{64}', authority['image_inventory_sha256'])
           and authority['approved'] is True and type(authority['numeric_reference_calls']) is int
           and authority['numeric_reference_calls'] == 1 and authority['runtime_qualification_inherited'] is False
           and authority['runtime_versions'] == {'python': '3.12.8', 'numpy': '2.2.6'},
           'Separate source/image/one-reference-run authority; no inherited qualification')
    resources = authority['grade_resources']
    seconds, memory = resources['producer_seconds'], resources['memory_bytes']
    b.need(type(seconds) is int and 1 <= seconds <= 14400 and type(memory) is int
           and 134217728 <= memory <= 8 * 1024**3 and memory % 1048576 == 0
           and resources == limits(seconds, memory), 'Exact separately selected grade envelope')
    b.need(authority['holder_memory_bytes'] == 134217728 and authority['holder_cpu_nanos'] == 1000000000,
           'Unchanged additional provider-holder resources')
    b.need(authority['outside_reserved_bytes'] == selection['other_future_bytes']
           and authority['additional_artifact_bytes'] == 4 * 1024**2
           and authority['whole_seconds'] == policy.whole(selection['candidate_seconds']) + 180 + seconds + 60 + 30,
           'Cumulative producer plus grade and outer costs explicitly allocated')
    for key in ('operator_output', 'grade_control_root', 'grade_quarantine_root'):
        b.need(type(cfg[key]) is str and Path(cfg[key]).is_absolute(), 'Absolute operator-owned path')
        b.path(cfg[key])
    return cfg, authority, authority_pin, selection, selection_pin, original, manifest, captured


def observe_producer(b, cfg, selection, selection_pin, original, output, origin, deadline):
    common, policy, observer, process, binding, legacy_source = original
    external = output / 'producer-external.json'
    producer_end = origin + policy.whole(selection['candidate_seconds']) + 150
    b.need(time.monotonic() + policy.whole(selection['candidate_seconds']) + 60 < producer_end,
           'Entire unchanged original observer interval remains')
    argv = [sys.executable, '-I', '-S', '-B', str(HERE / 'producer/observe.py'),
            '--source-pin', b.encode(legacy_source).decode().strip(),
            '--selection', cfg['producer_selection']['path'],
            '--selection-pin', b.encode(selection_pin).decode().strip(), '--external-output', str(external)]
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'LD_', 'DYLD_'))
           and k not in ('DOCKER_HOST', 'DOCKER_CONTEXT')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    b.save(output / 'PRODUCER_INTENT.json', b.encode({'argv': argv, 'source': legacy_source,
           'selection': selection_pin, 'normal_deadline': producer_end, 'cleanup_deadline': producer_end + 30}))
    try:
        stdout, observed = process.run(argv, producer_end, producer_end + 30, env)
    except process.ChildFailure as exc:
        b.save(output / 'PRODUCER_PROCESS_FAILURE.json', b.encode(exc.record))
        raise
    b.natural(observed)
    b.need(not stdout.strip(), 'Original observer has no candidate stdout channel')
    process_pin = b.save(output / 'PRODUCER_PROCESS.json', b.encode(observed))
    external_pin = b.pin(b.read(external, 8192))
    admitted = b.admit_producer(common, observer, binding, selection, selection_pin, legacy_source,
                               external, external_pin, observed, min(deadline, producer_end + 30))
    admitted['observed_process'] = process_pin
    b.save(output / 'PRODUCER_ADMITTED.json', b.encode(admitted))
    return admitted


def score_native(b, cfg, authority, authority_pin, selection, original, manifest, captured,
                 admitted, output, origin, deadline, source_pin):
    common, policy, observer, process, binding, legacy_source = original
    Provider, mount_identity, provider_source = b.transport(captured)
    packet = b.path(admitted['package'])
    b.need(packet == b.path(selection['repository']) / binding['package'], 'Same complete original packet')
    original_rows = {r['target']: r for r in binding['files']}
    public = {str(Path(name).relative_to('public')): {k: row[k] for k in ('bytes', 'sha256')}
              for name, row in original_rows.items() if row['visibility'] == 'public'}
    b.need(len(public) == 14 and sum(row['bytes'] for row in public.values()) == 71207593,
           'All fourteen original public inputs enter the trusted grader')
    def file(path, identity, purpose='operator_reference'):
        return {'path': str(b.path(path)), 'kind': 'file', 'purpose': purpose, 'files': {Path(path).name: identity}}
    mounts = {'/packet/public': {'path': str(packet / 'public'), 'kind': 'directory',
                                'purpose': 'input', 'files': public}}
    for name in ('DESIGN.json', 'PACKET_BINDING.json'):
        row = original_rows['private/' + name]
        mounts['/packet/private/' + name] = file(packet / 'private' / name, {k: row[k] for k in ('bytes', 'sha256')})
    scorer = HERE.parent / 'numerical-recovery-v1'
    numerical = {}
    for name in b.NUMERICAL:
        filename = scorer / (name + '.py')
        numerical[name] = b.pin(captured[str(filename)])
        mounts['/library/scorer/' + name + '.py'] = file(filename, numerical[name])
    for name in ('bridge.py', 'grade_worker.py'):
        mounts['/library/' + name] = file(HERE / name, b.pin(captured[str(HERE / name)]))
    for name, identity in admitted['outputs'].items():
        filename = Path(admitted['root']) / 'candidate' / name
        b.read(filename, {'result.json': 4000000, 'METHODS.md': 1048576}[name], identity)
        mounts['/submission/' + name] = file(filename, identity, 'input')
    invocation = {'schema': 'neural052_separate_numerical_invocation_v1', 'source': source_pin,
                  'outputs': admitted['outputs'], 'numerical_sources': numerical,
                  'bridge_source': b.pin(captured[str(HERE / 'bridge.py')])}
    invocation_path = output / 'NUMERIC_INVOCATION.json'
    invocation_pin = b.save(invocation_path, b.encode(invocation))
    invocation_path.chmod(0o444)
    mounts['/invocation.json'] = file(invocation_path, invocation_pin)
    command = ['/usr/local/bin/python', '-I', '-B', '/library/grade_worker.py']
    exposure = {'schema': 'osl_transport_exposure_v1', 'role': 'reference', 'image': selection['image'],
                'source': source_pin, 'command': command, 'mounts': mount_identity(mounts),
                'approved_image_inventory_sha256': authority['image_inventory_sha256'],
                'boundary_audit': authority_pin, 'role_boundary_verified': True}
    exposure_path = output / 'NUMERIC_EXPOSURE.json'
    exposure_pin = b.save(exposure_path, b.encode(exposure))
    provider = Provider(cfg['grade_control_root'], cfg['grade_quarantine_root'], selection['docker_binary'],
                        selection['docker_socket'], b.pin(captured[str(provider_source / 'SOURCE_MANIFEST.json')]),
                        {exposure_pin['sha256']: str(exposure_path)}, 513048576, 2097152)
    phase = 'neural052-grade-' + uuid.uuid4().hex
    request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': phase, 'action': 'held_attempt',
               'role': 'reference', 'image': selection['image'], 'command': command, 'workdir': '/work',
               'source': source_pin, 'exposure': exposure_pin,
               'clock': {'origin': origin, 'phase_deadline': deadline},
               'resources': authority['grade_resources'], 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
    b.save(output / 'NUMERIC_REQUEST.json', b.encode(request))
    returned = provider.execute_phase(request, mounts, deadline, lambda *_: None)
    observed = provider.observe(phase, b.pin(b.encode(request))['sha256'], returned['receipt_pin'], deadline)
    receipt = observed['receipt']
    b.need(receipt['status'] == 'captured' and receipt['producer_closed_before_capture'] is True
           and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True
           and receipt['error'] is None and type(receipt['natural_exit']['ExitCode']) is int
           and receipt['natural_exit']['ExitCode'] == 0 and receipt['natural_exit']['OOMKilled'] is False,
           'Successful stopped trusted numerical phase and complete closure')
    b.need(receipt['source'] == source_pin and receipt['image'] == selection['image']
           and receipt['role'] == 'reference' and receipt['exposure'] == exposure_pin
           and receipt['input_before'] == receipt['input_after'], 'Same exact numeric source/input exposure')
    directory = b.path(receipt['quarantine_root'])
    b.need(directory == b.path(Path(cfg['grade_quarantine_root']) / phase), 'Exact numerical capture directory')
    inventory = receipt['output_inventory']
    b.need(inventory['complete'] is True and set(inventory['files']) == {'score.json', 'RESULT.json', 'OUTPUTS.json'},
           'Complete bounded numerical output inventory')
    score = b.parse(b.read(directory / 'score.json', 262144, inventory['files']['score.json']))
    result = b.parse(b.read(directory / 'RESULT.json', 16384, inventory['files']['RESULT.json']))
    b.need(result == {'schema': 'neural052_separate_numerical_result_v1', 'status': score['status'],
                      'scientific_qualification': False, 'participant_code_executed': False}
           and score['status'] in ('scored', 'invalid_submission'), 'Exact unchanged scientific disposition')
    b.need(score['producer_custody']['expected_outputs'] == admitted['outputs'], 'Score bound to original paired outputs')
    if score['status'] == 'scored':
        b.need(all(score['producer_custody']['exact_capture_observed'].values()), 'Both original bytes captured before score')
    for name, identity in admitted['outputs'].items():
        b.read(Path(admitted['root']) / 'candidate' / name, {'result.json': 4000000, 'METHODS.md': 1048576}[name], identity)
    return {'status': score['status'], 'score': inventory['files']['score.json'], 'score_path': str(directory / 'score.json'),
            'provider_receipt': returned['receipt_pin'], 'source': source_pin, 'outputs': admitted['outputs'],
            'scientific_qualification': False, 'runtime_qualification': False, 'automatic_retry': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pin', required=True)
    parser.add_argument('--configuration', required=True, type=Path)
    args = parser.parse_args(argv)
    origin = time.monotonic()
    source_pin = json.loads(args.source_pin)
    b = load_bridge(source_pin)
    cfg, authority, authority_pin, selection, selection_pin, original, manifest, captured = setup(b, args.configuration, source_pin)
    deadline = origin + authority['whole_seconds']
    output = b.path(cfg['operator_output'])
    b.need(not output.exists() and output.parent.is_dir(), 'Fresh operator output in existing parent')
    producer_output = b.path(selection['output'])
    b.need(output != producer_output and not output.is_relative_to(producer_output)
           and not producer_output.is_relative_to(output), 'Disjoint operator and original producer custody')
    b.need(shutil.disk_usage(output.parent).free >= DISK_FLOOR + authority['outside_reserved_bytes']
           + original[0].RETAIN + authority['additional_artifact_bytes'], 'Current sixty-GiB free-disk floor and holds')
    b.need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'No conflicting outer process timer')
    def hard(*unused):
        os._exit(124)
    def stop(*unused):
        signal.signal(signal.SIGALRM, hard)
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
        raise TimeoutError('Original whole-run deadline or interruption')
    previous = {number: signal.signal(number, stop) for number in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM)}
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - 10 - time.monotonic()))
    output.mkdir(mode=0o700)
    try:
        b.save(output / 'PLAN.json', b.encode({'source': source_pin, 'numeric_authority': authority_pin,
               'producer_selection': selection_pin, 'origin': origin, 'deadline': deadline,
               'producer_remains_ungraded': True, 'numeric_phase_separately_selected': True}))
        admitted = observe_producer(b, cfg, selection, selection_pin, original, output, origin, deadline - 10)
        b.source(source_pin)
        result = score_native(b, cfg, authority, authority_pin, selection, original, manifest, captured,
                              admitted, output, origin, deadline - 10, source_pin)
        b.save(output / 'COMPLETE.json', b.encode(result))
        return 0 if result['status'] == 'scored' else 2
    except BaseException as exc:
        b.save(output / 'FAILURE.json', b.encode({'error_type': type(exc).__name__, 'source': source_pin,
               'native_or_nested_process_cleanup_not_inferred': True, 'automatic_retry': False,
               'preserve_original_and_grade_ownership_receipts': True}))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for number, handler in previous.items():
            signal.signal(number, handler)


if __name__ == '__main__':
    raise SystemExit(main())
