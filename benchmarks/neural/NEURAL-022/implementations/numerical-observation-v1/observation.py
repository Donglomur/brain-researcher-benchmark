"""Full-panel count/text export and target-free collection; no participant execution."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / 'artifact-grading/private/vendor'
PUBLIC = ('training.npz', 'queries.npz', 'cases.json', 'TASK.md')
PACKET = (*PUBLIC, 'reference.private.npz', 'receipt.json')
CAPS = dict(zip(PACKET, (524288, 393216, 16384, 16384, 65536, 65536)))
OBSERVATION_CAP = 2 * 1024 * 1024
CONDITION = 'direct_numerical_full_panel_v1'
APP_FILES = {'observation.py', 'INSTRUCTIONS.md', 'DEPENDENCIES.json', 'ORIGINAL_TASK.md'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value, maximum):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= maximum
         and type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']),
         'Exact bounded byte descriptor')
    return value


def ordinary(path):
    value = Path(os.path.abspath(path))
    need(all(not p.is_symlink() for p in (value, *value.parents)), 'No symbolic path components')
    return value


def capture(path, maximum, expected=None):
    value = ordinary(path)
    if expected is not None:
        descriptor(expected, maximum)
    fd = os.open(value, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= maximum, 'Bounded ordinary single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(before.st_size + 1)
        after = os.fstat(fd)
        keys = ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in keys),
             'Stable complete captured file')
        need(expected is None or pin(raw) == expected, 'Exact committed bytes')
        return raw
    finally:
        os.close(fd)


def sha_capture(path, maximum, sha256):
    need(type(sha256) is str and re.fullmatch('[a-f0-9]{64}', sha256), 'Explicit exact SHA256')
    raw = capture(path, maximum)
    need(pin(raw)['sha256'] == sha256, 'Selected exact SHA256')
    return raw


def source(source_sha256):
    """Authenticate before executing captured canonical source; never load local pyc."""
    manifest_raw = sha_capture(HERE / 'SOURCE.json', 32768, source_sha256)
    manifest = strict(manifest_raw)
    need(set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'neural022_numerical_source_v1'
         and set(manifest['files']) == APP_FILES, 'Exact application source closure')
    bodies = {name: capture(HERE / name, 65536, manifest['files'][name]) for name in sorted(APP_FILES)}
    dependencies = strict(bodies['DEPENDENCIES.json'])
    need(dependencies['schema'] == 'neural022_numerical_dependencies_v1'
         and set(dependencies['canonical_vendor']) == {'candidate.py', 'io_support.py', 'packet.py'},
         'Exact public canonical dependencies')
    need(pin(bodies['ORIGINAL_TASK.md']) == dependencies['packet_producer']['public_task'], 'Pinned original public task copy')
    modules = {}
    # These source modules import only stdlib and NumPy, not neighboring source files.
    for name, identity in dependencies['canonical_vendor'].items():
        body = capture(VENDOR / name, 16384, identity)
        module = types.ModuleType('neural022_numerical_' + name[:-3])
        exec(compile(body, str(VENDOR / name), 'exec'), module.__dict__)
        modules[name[:-3]] = module
    return {'identity': pin(manifest_raw), 'dependencies': dependencies,
            'instructions': bodies['INSTRUCTIONS.md'].decode('utf-8'), **modules}


def packet_public(root, packet_sha256, runtime):
    """Read metadata and exactly four public files; never inspect private operands."""
    root = ordinary(root)
    raw = sha_capture(root / 'PACKET.json', 32768, packet_sha256)
    value = strict(raw)
    producer = runtime['dependencies']['packet_producer']
    need(set(value) == {'schema', 'source', 'source_contract', 'files', 'public_training_rows',
                       'public_query_rows', 'projection_resources_absent', 'projection_closure',
                       'new_model_fits', 'new_reference_predictions', 'runtime_qualified', 'scientific_qualification'}
         and value['schema'] == 'neural022_delivery_packet_v1'
         and value['source'] == producer['source'] and value['source_contract'] == producer['source_contract']
         and type(value['public_training_rows']) is int and value['public_training_rows'] == 141
         and type(value['public_query_rows']) is int and value['public_query_rows'] == 92
         and value['projection_resources_absent'] is True
         and type(value['new_model_fits']) is int and value['new_model_fits'] == 0
         and type(value['new_reference_predictions']) is int and value['new_reference_predictions'] == 0,
         'Complete original no-refit projection metadata')
    need(type(value['files']) is dict and set(value['files']) == set(PACKET), 'Complete packet file descriptors')
    for name in PACKET:
        descriptor(value['files'][name], CAPS[name])  # Metadata only, no private path construction.
    closure = value['projection_closure']
    need(type(closure) is dict and set(closure) == {'phase', 'receipt', 'source',
         'producer_removed_before_capture', 'all_native_resources_closed'}
         and closure['source'] == producer['source'] and closure['producer_removed_before_capture'] is True
         and closure['all_native_resources_closed'] is True
         and type(closure['phase']) is str and re.fullmatch('[a-f0-9]{32}', closure['phase']),
         'Source-bound complete projection closure declaration')
    descriptor(closure['receipt'], 1048576)
    need(value['files']['TASK.md'] == producer['public_task'], 'Unchanged original public task')
    public = {name: capture(root / name, CAPS[name], value['files'][name]) for name in PUBLIC}
    return value, pin(raw), public


def numerical_panel(public, runtime):
    io, packet, candidate = runtime['io_support'], runtime['packet'], runtime['candidate']
    schema = {'ids': ('<U24', (141,)), 'counts': ('<i8', (141, 390)),
              'velocity': ('<f8', (141, 2)), 'directions': ('<i8', (141,))}
    training = io.npz(public['training.npz'], schema)
    query = io.npz(public['queries.npz'], io.schema('query', candidate.METHODS))
    cases = candidate.strict(public['cases.json']); rows = candidate.cases(cases)
    packet.identifiers(training['ids'], 141); packet.counts(training['counts'], 141)
    packet.velocity(training['velocity'], 141)
    packet.identifiers(query['ids'], 92); packet.counts(query['counts'], 92)
    need(set(training['directions'].tolist()) == set(candidate.DIRECTIONS), 'All active training directions')
    need(query['ids'].tolist() == [r['id'] for r in rows]
         and query['directions'].tolist() == [r['direction'] for r in rows]
         and query['modes'].tolist() == [r['mode'] for r in rows], 'Exact complete ordered query context')
    need(not set(training['ids'].tolist()) & set(query['ids'].tolist()), 'Disjoint training/query identities')
    task = public['TASK.md'].decode('utf-8')
    start, stop = task.index('The primary score is '), task.index('The prospective reused runner allows ')
    need(start < stop, 'Original public scientific-contract excerpt')
    train_rows = [{'id': str(training['ids'][i]), 'direction': int(training['directions'][i]),
                   'counts': training['counts'][i].reshape(6, 65).tolist(),
                   'velocity': training['velocity'][i].tolist()} for i in range(141)]
    query_rows = [row | {'counts': query['counts'][i].reshape(6, 65).tolist()} for i, row in enumerate(rows)]
    value = {'schema': 'neural022_numerical_observation_v1', 'task_id': 'NEURAL-022',
             'condition': CONDITION, 'instructions': runtime['instructions'],
             'original_public_scientific_contract': task[start:stop],
             'representation': {'counts': 'nonnegative_integer_spikes_per_bin', 'axes': ['bin', 'unit'],
                                'unit_positions': list(range(65)), 'bin_edges_ms': [0, 20, 40, 60, 80, 100, 120],
                                'velocity_units': 'nominal_m/s', 'relative_clock': 'retrospective_movement_onset'},
             'training': train_rows, 'queries': query_rows}
    raw = encoded(value)
    need(len(raw) <= OBSERVATION_CAP, 'Complete observation fits declared byte cap; never truncate')
    return raw, cases


def fresh(root):
    root = ordinary(root)
    need(not root.exists() and root.parent.is_dir(), 'Fresh output under an existing operator directory')
    root.mkdir(mode=0o700)
    return root


def publish(root, name, raw):
    path = ordinary(root / name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return pin(raw)


def export(root, packet_sha256, output, runtime):
    metadata, packet_pin, public = packet_public(root, packet_sha256, runtime)
    raw, cases = numerical_panel(public, runtime)
    out = fresh(output)
    observation_pin = publish(out, 'OBSERVATION.json', raw)
    record = {'schema': 'neural022_numerical_export_v1', 'source': runtime['identity'],
              'condition': CONDITION, 'packet': packet_pin, 'packet_producer': metadata['source'],
              'public_inputs': {name: metadata['files'][name] for name in PUBLIC},
              'observation': observation_pin, 'training_rows': 141, 'query_rows': 92,
              'count_values': 90870, 'training_velocity_values': 282,
              'provider_delivery_qualified': False, 'authenticity_requires_external_packet_custody': True}
    record_pin = publish(out, 'EXPORT.json', encoded(record))
    return record_pin


def observation_cases(raw, runtime):
    value = strict(raw)
    need(type(value) is dict and set(value) == {'schema', 'task_id', 'condition', 'instructions',
         'original_public_scientific_contract', 'representation', 'training', 'queries'}
         and value['schema'] == 'neural022_numerical_observation_v1' and value['task_id'] == 'NEURAL-022'
         and value['condition'] == CONDITION and value['instructions'] == runtime['instructions'],
         'Exact committed observation condition')
    need(type(value['training']) is list and len(value['training']) == 141
         and type(value['queries']) is list and len(value['queries']) == 92, 'Complete observation denominator')
    # The externally selected EXPORT hash commits all contents, including training values;
    # this projection supplies the original public validator without re-reading packet bodies.
    cases = {'schema': 'neural022_public_cases_v1',
             'cases': [{key: row[key] for key in ('id', 'mode', 'direction')} for row in value['queries']]}
    runtime['candidate'].cases(cases)
    return cases


def collect(root, export_sha256, response, response_sha256, output, runtime):
    root = ordinary(root)
    manifest_raw = sha_capture(root / 'EXPORT.json', 32768, export_sha256)
    record = strict(manifest_raw)
    need(type(record) is dict and set(record) == {'schema', 'source', 'condition', 'packet', 'packet_producer',
         'public_inputs', 'observation', 'training_rows', 'query_rows', 'count_values', 'training_velocity_values',
         'provider_delivery_qualified', 'authenticity_requires_external_packet_custody'}
         and record['schema'] == 'neural022_numerical_export_v1' and record['source'] == runtime['identity']
         and record['condition'] == CONDITION and record['packet_producer'] == runtime['dependencies']['packet_producer']['source']
         and record['training_rows'] == 141 and record['query_rows'] == 92 and record['count_values'] == 90870
         and record['training_velocity_values'] == 282 and record['provider_delivery_qualified'] is False
         and record['authenticity_requires_external_packet_custody'] is True,
         'Exact source-bound complete export')
    descriptor(record['packet'], 32768)
    need(set(record['public_inputs']) == set(PUBLIC), 'Exact public input bindings')
    for name in PUBLIC:
        descriptor(record['public_inputs'][name], CAPS[name])
    raw = capture(root / 'OBSERVATION.json', OBSERVATION_CAP, record['observation'])
    cases = observation_cases(raw, runtime)
    prediction = sha_capture(response, 65536, response_sha256)
    runtime['candidate'].validate(prediction, cases)
    out = fresh(output)
    prediction_pin = publish(out, 'predictions.json', prediction)
    submission = {'schema_version': 1, 'task_id': 'NEURAL-022',
                  'file': {'path': 'predictions.json', **prediction_pin}}
    submission_pin = publish(out, 'submission.json', encoded(submission))
    collection = {'schema': 'neural022_numerical_collection_v1', 'source': runtime['identity'],
                  'condition': CONDITION, 'export': pin(manifest_raw), 'observation': pin(raw),
                  'predictions': prediction_pin, 'submission': submission_pin,
                  'complete_prediction_rows': 92, 'provider_session_verified': False,
                  'no_tools_boundary_verified': False, 'training_only_method_verified': False,
                  'scientific_qualification': False, 'private_files_accessed': False}
    return publish(out, 'COLLECTION.json', encoded(collection))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True)
    modes = parser.add_subparsers(dest='mode', required=True)
    exp = modes.add_parser('export')
    exp.add_argument('--packet', type=Path, required=True); exp.add_argument('--packet-sha256', required=True)
    exp.add_argument('--output', type=Path, required=True)
    col = modes.add_parser('collect')
    col.add_argument('--export', dest='export_root', type=Path, required=True)
    col.add_argument('--export-sha256', required=True)
    col.add_argument('--response', type=Path, required=True); col.add_argument('--response-sha256', required=True)
    col.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    runtime = source(args.source_sha256)
    if args.mode == 'export':
        result = export(args.packet, args.packet_sha256, args.output, runtime)
    else:
        result = collect(args.export_root, args.export_sha256, args.response, args.response_sha256, args.output, runtime)
    print(json.dumps({'stage': args.mode, 'output': result, 'provider_delivery_qualified': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
