"""Distinct TEST reference/candidate grading with the unchanged original scorer.

Both complete immutable predictions and both genuine role-specific freezes are
validated before target-capable scoring. The candidate is never represented as
an original author artifact. Physical supervision belongs to the bounded host.
"""
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
ROLES = ('reference', 'candidate')
METRICS = ('co-bps', 'vel R2', 'psth R2', 'fp-bps')
META_CAP = 2 * 1024**2
SCRATCH_CAP = 536870912
SOURCE_FILES = {'test_pair_grade.py', 'test_pair_child.py', 'scorer.py', 'reference_panel.json', 'gain_transform.py'}
PACKAGES = {'numpy': '1.26.3', 'scipy': '1.12.0', 'scikit-learn': '1.5.0', 'h5py': '3.10.0'}
REFERENCE_PREDICTION = {'bytes': 87250290, 'sha256': 'fcca208d1d09641a941dfdaf4290493e01ae98be560d665c22f066718c630896'}
REFERENCE_FREEZE = {'bytes': 814, 'sha256': '1d927a636ccc7e966c0390521b5f8daac13a8b6d345e8dbcf9d3a848322cf6f7'}
PINS = {
    'panel': {'bytes': 4333, 'sha256': '3b160dfb4aef8c68cbae8d4a02d5933576a77e4bc47a7c3a5b484369caf95be5'},
    'protocol': {'bytes': 11499, 'sha256': '71242e29e6fba3146a9ae0bfceef4de079390bad4ce02a450ec287c3ec759535'},
    'target': {'bytes': 105927616, 'sha256': 'f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865'},
    'evaluator': {'bytes': 18292, 'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'},
    'scorer.py': {'bytes': 15050, 'sha256': '48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8'},
    'reference_panel.json': {'bytes': 3665, 'sha256': '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3'},
    'gain_transform.py': {'bytes': 19658, 'sha256': 'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda'}}
GAIN_GRID = ((1, 1), (8, 9), (9, 8), (4, 5), (5, 4), (2, 3), (3, 2), (1, 2), (2, 1))
CUSTODY_CAP = 512 * 1024
METHOD_INPUTS = {'gain_kernel', 'gain_runtime', 'valid_selector_result', 'valid_selection',
    'valid_method', 'valid_reference_bindings', 'valid_materials', 'valid_author_manifest',
    'valid_component_source', 'test_panel', 'test_protocol', 'test_reference_freeze',
    'test_reference_prediction', 'test_source_manifest', 'test_source_postcheck', 'test_target', 'evaluator'}
CANDIDATE_RECIPE = {'role': 'candidate', 'arm': 'noncausal', 'seed': 0,
    'particles': None, 'repeats': None, 'source_author_commit': None}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def lexical(value):
    p = Path(value)
    need(p.is_absolute() and str(p) == str(value) and '..' not in p.parts and '\x00' not in str(p),
         'Canonical absolute input path required')
    return p


def path(value):
    p = lexical(value)
    need(not any(q.is_symlink() for q in (p, *p.parents)), 'Unlinked ordinary path required')
    return p


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(row):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}
         and type(row['bytes']) is int and 0 < row['bytes'] <= SCRATCH_CAP
         and type(row['sha256']) is str and len(row['sha256']) == 64
         and all(c in '0123456789abcdef' for c in row['sha256']), 'Exact bounded file descriptor required')
    lexical(row['path'])  # No target or prediction stat/body access here.
    return row


def body(filename, expected=None):
    p = path(filename)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        a = os.fstat(stream.fileno())
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= META_CAP,
             'Bounded single-link source or metadata file required')
        raw = stream.read(META_CAP + 1)
        b, c = os.fstat(stream.fileno()), p.lstat()
    keys = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == a.st_size and all(getattr(a, k) == getattr(b, k) == getattr(c, k) for k in keys),
         'Stable complete source/metadata read required')
    if expected is not None:
        need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'Selected metadata/source identity changed')
    return raw


def decode(raw):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'No duplicate metadata keys')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Finite JSON required'))


def checked(row):
    descriptor(row)
    return decode(body(row['path'], row))


def publish(filename, value):
    p = path(filename)
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    need(len(raw) <= META_CAP, 'Bounded report required')
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return {'path': str(p), **pin(raw)}


def copy_snapshot(source, destination, expected, cap):
    """Copy at most the precharged exact extent; growth is never written."""
    source, destination = path(source), path(destination)
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= cap,
         'Prospectively bounded exact snapshot descriptor')
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'], 'Exact ordinary snapshot source before copying')
        output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        count, digest = 0, hashlib.sha256()
        with os.fdopen(output_fd, 'wb') as sink:
            while count < expected['bytes']:
                chunk = stream.read(min(1024**2, expected['bytes'] - count))
                need(chunk, 'Snapshot source truncated during bounded copy')
                count += len(chunk)
                digest.update(chunk)
                sink.write(chunk)
            need(stream.read(1) == b'', 'Snapshot source grew beyond precharged extent')
            after, named = os.fstat(stream.fileno()), source.lstat()
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            need(all(getattr(before, key) == getattr(after, key) == getattr(named, key) for key in fields)
                 and digest.hexdigest() == expected['sha256'], 'Stable exact original snapshot bytes')
            sink.flush()
            os.fsync(sink.fileno())
    need(destination.lstat().st_size == expected['bytes'], 'Complete bounded snapshot output')
    return expected


def versions():
    actual = {name: importlib.metadata.version(name) for name in PACKAGES}
    need(actual == PACKAGES, 'Selected scoring environment differs from explicit package versions')
    return actual


def load_scorer():
    raw = body(HERE / 'scorer.py', PINS['scorer.py'])
    body(HERE / 'reference_panel.json', PINS['reference_panel.json'])
    spec = importlib.util.spec_from_file_location('_smc_historical_original_scorer', HERE / 'scorer.py')
    result = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(HERE / 'scorer.py'), 'exec'), result.__dict__)
    return result


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def content_identity(row):
    return {key: row[key] for key in ('bytes', 'sha256')}


def source_identity(selected):
    descriptor(selected)
    need(lexical(selected['path']) == HERE / 'SOURCE.json', 'Exact adjacent paired TEST source')
    manifest = checked(selected)
    need(type(manifest) is dict and set(manifest) == {'schema', 'files', 'test_kernel'}
         and manifest['schema'] == 'smc_test_gain_grade_source_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == SOURCE_FILES,
         'Exact five-file TEST grading source closure')
    for name, expected in manifest['files'].items():
        need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
             and type(expected['bytes']) is int and 0 < expected['bytes'] <= META_CAP,
             'Bounded exact source member pin')
        body(HERE / name, expected)
    for name in ('scorer.py', 'reference_panel.json', 'gain_transform.py'):
        need(manifest['files'][name] == PINS[name], 'Unchanged selected scorer, panel and arithmetic')
    kernel = manifest['test_kernel']
    need(type(kernel) is dict and set(kernel) == {'bytes', 'sha256'}
         and type(kernel['bytes']) is int and 0 < kernel['bytes'] <= META_CAP
         and type(kernel['sha256']) is str and len(kernel['sha256']) == 64
         and all(c in '0123456789abcdef' for c in kernel['sha256']), 'Exact TEST core source pin')
    return manifest


def load_transform():
    raw = body(HERE / 'gain_transform.py', PINS['gain_transform.py'])
    spec = importlib.util.spec_from_file_location('_smc_test_pair_gain_arithmetic', HERE / 'gain_transform.py')
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(HERE / 'gain_transform.py'), 'exec'), module.__dict__)
    return module


def verify_scaled_pair(reference_path, candidate_path, gain, *, expected_shapes):
    """Target-free, shape-generic exact eight-field transformation verification."""
    import h5py
    transform = load_transform()
    transform.validate_gain(gain)
    transform._validate_shapes(expected_shapes)
    reference_path, candidate_path = path(reference_path), path(candidate_path)
    reference_pin, candidate_pin = transform.read_pin(reference_path), transform.read_pin(candidate_path)
    if gain == [1, 1]:
        need(reference_pin == candidate_pin, 'Identity gain requires complete serialized byte equality')
    with h5py.File(reference_path, 'r') as reference, h5py.File(candidate_path, 'r') as candidate:
        original_metadata = transform._inspect(reference, expected_shapes, gain)
        actual_metadata = transform._inspect(candidate, expected_shapes, gain)
        need(transform.encoded(original_metadata) == transform.encoded(actual_metadata),
             'Exact unchanged dtype, field order, attributes and lossless storage metadata')
        for name in transform.RATE_KEYS:
            baseline = reference[transform.DATASET][name]
            observed = candidate[transform.DATASET][name]
            row_bytes = math.prod(baseline.shape[1:]) * baseline.dtype.itemsize
            step = max(1, transform.BLOCK_BYTES // row_bytes)
            for first in range(0, baseline.shape[0], step):
                expected = transform.scale_block(baseline[first:first + step], gain)
                actual = observed[first:first + step]
                need(actual.dtype == expected.dtype and actual.shape == expected.shape
                     and actual.tobytes(order='C') == expected.tobytes(order='C'),
                     'Every TEST and TRAIN field equals the frozen source-precision gain')
    need(transform.read_pin(reference_path) == reference_pin
         and transform.read_pin(candidate_path) == candidate_pin,
         'Both complete prediction identities remain stable during exact scale verification')
    return {'schema': 'smc_test_gain_scale_proof_v1', 'gain': list(gain),
            'reference': reference_pin, 'candidate': candidate_pin,
            'rate_fields': list(transform.RATE_KEYS), 'shapes': expected_shapes,
            'metadata_sha256': hashlib.sha256(transform.encoded(original_metadata)).hexdigest(),
            'executed_gains': {name: original_metadata['datasets'][name]['executed_gain']
                              for name in transform.RATE_KEYS},
            'all_eight_fields_exact': True, 'identity_whole_file_equal': gain == [1, 1],
            'target_accessed': False, 'inference_execution_qualified': False}


def embedded(record):
    need(type(record) is dict and set(record) == {'descriptor', 'raw_json'}
         and type(record['raw_json']) is str, 'Exact embedded immutable UTF-8 metadata record')
    descriptor(record['descriptor'])
    raw = record['raw_json'].encode('utf-8')
    need(0 < len(raw) <= CUSTODY_CAP and pin(raw) == content_identity(record['descriptor']),
         'Embedded raw JSON bytes match their original named descriptor without reserialization')
    return decode(raw)


def selected_row(selection):
    rows = selection['ordered_scores']
    need(type(rows) is list and len(rows) == len(GAIN_GRID), 'All nine frozen VALID scores required')
    for index, (row, gain) in enumerate(zip(rows, GAIN_GRID)):
        need(type(row) is dict and set(row) == {'index', 'gain', 'executed_gain', 'co_bps'}
             and type(row['index']) is int and row['index'] == index
             and type(row['gain']) is list and row['gain'] == list(gain)
             and all(type(x) is int for x in row['gain'])
             and type(row['co_bps']) is float and math.isfinite(row['co_bps']),
             'Finite exact ordered VALID gain grid')
    best = rows[0]
    for row in rows[1:]:
        if row['co_bps'] > best['co_bps']:
            best = row
    need(type(selection['selected_index']) is int and selection['selected_index'] == best['index']
         and encoded(selection['selected_gain']) == encoded(best['gain'])
         and encoded(selection['selected_executed_gain']) == encoded(best['executed_gain'])
         and type(selection['selected_co_bps']) is float
         and selection['selected_co_bps'] == best['co_bps'], 'Exact earliest maximum remains frozen')
    return best


def admit_host_custody(request, manifest):
    """Join the host's source-bound handoff; genuine prior closure is host-owned."""
    descriptor(request['host_custody'])
    need(request['host_custody']['bytes'] <= CUSTODY_CAP, 'Bounded host custody metadata')
    custody = checked(request['host_custody'])
    keys = {'schema', 'host_source', 'host_request', 'core_source', 'grader_source',
            'child_template', 'test_method', 'valid_selection', 'selected_row', 'lineage', 'inputs'}
    need(type(custody) is dict and set(custody) == keys
         and custody['schema'] == 'smc_test_gain_host_custody_v1', 'Exact host custody handoff')
    for key in ('host_source', 'host_request', 'core_source', 'grader_source'):
        descriptor(custody[key])
    template = embedded(custody['child_template'])
    need(type(template) is dict and set(template) == set(request)
         and template['host_custody'] is None, 'Original child template has no fabricated custody')
    patched = dict(template); patched['host_custody'] = request['host_custody']
    need(encoded(patched) == encoded(request), 'Only the internally derived custody field changes the template')
    method = embedded(custody['test_method'])
    need(custody['test_method']['descriptor'] == request['test_method']
         and type(method) is dict and set(method) == {'schema', 'source', 'grader_source',
             'runtime_source', 'inputs', 'selected_row', 'lineage', 'candidate_recipe'}
         and method['schema'] == 'smc_test_gain_method_v1', 'Frozen exact TEST method')
    need(encoded(method['candidate_recipe']) == encoded(CANDIDATE_RECIPE), 'Honest deterministic candidate recipe')
    for key in ('source', 'grader_source', 'runtime_source'):
        descriptor(method[key])
    need(method['source'] == custody['core_source']
         and method['runtime_source'] == custody['host_source']
         and method['grader_source'] == custody['grader_source'] == request['source']
         and content_identity(custody['core_source']) == manifest['test_kernel'],
         'Exact selected core, current grader and actual host-source joins')
    inputs = method['inputs']
    need(type(inputs) is dict and set(inputs) == METHOD_INPUTS, 'Exact named TEST and VALID lineage inputs')
    for row in inputs.values():
        descriptor(row)
    selection = embedded(custody['valid_selection'])
    need(custody['valid_selection']['descriptor'] == inputs['valid_selection']
         and selection['schema'] == 'smc_gain_selection_report_v1'
         and selection['phase'] == 'val' and selection['dataset'] == 'mc_maze_20'
         and selection['method'] == inputs['valid_method']
         and selection['source'] == inputs['gain_kernel'], 'Original exact source-bound VALID selection')
    best = selected_row(selection)
    need(encoded(best) == encoded(method['selected_row']) == encoded(custody['selected_row'])
         and encoded(method['lineage']) == encoded(custody['lineage']),
         'Frozen chosen gain and TEST lineage preserved by host handoff')
    merged = custody['inputs']
    need(type(merged) is dict and set(merged) == {'predictions', 'freezes', 'panel', 'protocol', 'target', 'evaluator'}
         and encoded(merged) == encoded({key: request[key] for key in merged}), 'Exact merged child scientific inputs')
    need(merged['predictions']['reference'] == inputs['test_reference_prediction']
         and merged['freezes']['reference'] == inputs['test_reference_freeze'], 'Original TEST reference lineage')
    for key, original in (('panel', 'test_panel'), ('protocol', 'test_protocol'),
                          ('target', 'test_target'), ('evaluator', 'evaluator')):
        need(merged[key] == inputs[original], 'Exact original TEST ' + key + ' lineage')
    return method, custody


def metadata(request_path, request_sha256):
    raw = body(request_path)
    need(pin(raw)['sha256'] == request_sha256, 'Selected TEST paired grade request changed')
    request = decode(raw)
    need(type(request) is dict and set(request) == {'schema', 'source', 'test_method', 'host_custody',
         'predictions', 'freezes', 'panel', 'protocol', 'target', 'evaluator', 'output_root', 'scratch_bytes'}
         and request['schema'] == 'smc_test_gain_grade_request_v1', 'Exact paired TEST request')
    manifest = source_identity(request['source'])
    descriptor(request['test_method'])
    for key in ('predictions', 'freezes'):
        need(type(request[key]) is dict and set(request[key]) == set(ROLES), 'Exactly reference and candidate ' + key)
        for row in request[key].values():
            descriptor(row)
    need(content_identity(request['predictions']['reference']) == REFERENCE_PREDICTION
         and content_identity(request['freezes']['reference']) == REFERENCE_FREEZE,
         'Exact unchanged noncausal TEST reference and original freeze')
    for key in ('panel', 'protocol', 'target', 'evaluator'):
        descriptor(request[key])
        need(content_identity(request[key]) == PINS[key], 'Fixed original TEST ' + key)
    method, custody = admit_host_custody(request, manifest)
    copies = sum(row['bytes'] for row in request['predictions'].values())
    need(type(request['scratch_bytes']) is int
         and copies + max(row['bytes'] for row in request['predictions'].values()) + 8 * META_CAP
             <= request['scratch_bytes'] <= SCRATCH_CAP,
         'Both full snapshots, one retained scorer snapshot and all bounded metadata precharged')
    panel, protocol = checked(request['panel']), checked(request['protocol'])
    need(panel['phase'] == 'test' and panel['n_train'] == 2295 and panel['n_eval'] == 574
         and panel['n_bins'] == 35 and panel['forward_bins'] == 10 and panel['bin_ms'] == 20,
         'Original TEST decoder base35 and separate forward10 geometry')
    need(protocol['input_commitments']['test_panel_sha256'] == request['panel']['sha256']
         and protocol['exposure']['target_sha256'] == request['target']['sha256'], 'Original TEST protocol provenance')
    freezes = {}
    for role in ROLES:
        frozen = checked(request['freezes'][role])
        need(frozen['schema'] == 'smc_nlb_prediction_freeze_v1' and frozen['dataset'] == 'mc_maze_20'
             and frozen['arm'] == 'noncausal'
             and frozen['submission_sha256'] == request['predictions'][role]['sha256']
             and frozen['panel_manifest_sha256'] == request['panel']['sha256']
             and frozen['protocol_sha256'] == request['protocol']['sha256']
             and frozen['reference_panel_sha256'] == PINS['reference_panel.json']['sha256']
             and frozen['target_exposure'] == 'public_original_test_targets_released_2026_01',
             'Complete original-format role-specific TEST freeze joins')
        if role == 'reference':
            need(frozen['role'] == 'author_calibration' and frozen['seed'] == 20261118
                 and frozen['particles'] == 192 and frozen['repeats'] == 32
                 and frozen['source_author_commit'] == 'c808c76ad940491b0a14d2671e3884140aa61258',
                 'Original author reference recipe retained without new inference')
        else:
            need(set(frozen) == {'schema', 'created_utc', 'submission_sha256', 'panel_manifest_sha256',
                 'reference_panel_sha256', 'protocol_sha256', 'arm', 'method_id', 'role', 'seed',
                 'particles', 'repeats', 'dataset', 'target_exposure', 'source_author_commit'}
                 and type(frozen['created_utc']) is str and 0 < len(frozen['created_utc']) <= 64
                 and frozen['role'] == 'candidate' and type(frozen['seed']) is int and frozen['seed'] == 0
                 and frozen['particles'] is None and frozen['repeats'] is None
                 and frozen['source_author_commit'] is None
                 and frozen['method_id'] == 'smc-test-gain/' + request['test_method']['sha256'],
                 'Genuine distinct gain candidate, never an author-calibration artifact')
        freezes[role] = frozen
    lexical(request['output_root'])
    return request, freezes, method, custody


def freeze_candidate(prediction_descriptor, panel_descriptor, protocol_descriptor, test_method_descriptor, output_path):
    """Target-free original candidate freeze, with no author or ownership claim."""
    for row in (prediction_descriptor, panel_descriptor, protocol_descriptor, test_method_descriptor):
        descriptor(row)
    need(content_identity(panel_descriptor) == PINS['panel']
         and content_identity(protocol_descriptor) == PINS['protocol'], 'Original exact TEST metadata')
    method = checked(test_method_descriptor)
    need(method['schema'] == 'smc_test_gain_method_v1'
         and encoded(method['candidate_recipe']) == encoded(CANDIDATE_RECIPE), 'Frozen deterministic TEST gain method')
    manifest = source_identity(method['grader_source'])
    need(content_identity(method['source']) == manifest['test_kernel'], 'Selected TEST method kernel')
    transform = load_transform()
    need(transform.read_pin(prediction_descriptor['path']) == content_identity(prediction_descriptor),
         'Exact candidate before target-free freeze')
    versions(); scorer = load_scorer()
    scorer.validate_submission(prediction_descriptor['path'], checked(panel_descriptor), require_author_arrays=True)
    destination = path(output_path)
    need(not destination.exists() and destination != path(prediction_descriptor['path']), 'Fresh separate candidate freeze')
    record = scorer.freeze_predictions(prediction_descriptor['path'], panel_descriptor['path'],
        protocol_descriptor['path'], destination, arm='noncausal',
        method_id='smc-test-gain/' + test_method_descriptor['sha256'], role='candidate', seed=0)
    need(record['source_author_commit'] is None and record['particles'] is None and record['repeats'] is None
         and transform.read_pin(prediction_descriptor['path']) == content_identity(prediction_descriptor),
         'Honest stable target-free candidate freeze')
    os.chmod(destination, 0o444)
    return {'path': str(destination), **pin(body(destination))}


def validate_score(report, role, request, freeze):
    need(report['schema'] == 'smc_nlb_operator_score_v1' and report['arm'] == 'noncausal'
         and report['role'] == ('author_calibration' if role == 'reference' else 'candidate')
         and report['method_id'] == freeze['method_id']
         and report['submission_sha256'] == request['predictions'][role]['sha256']
         and report['prediction_freeze_sha256'] == request['freezes'][role]['sha256']
         and report['panel_manifest_sha256'] == request['panel']['sha256']
         and report['protocol_sha256'] == request['protocol']['sha256']
         and report['reference_panel_sha256'] == PINS['reference_panel.json']['sha256']
         and report['scorer_sha256'] == request['evaluator']['sha256']
         and report['target_sha256'] == request['target']['sha256']
         and report['dependency_versions'] == PACKAGES, 'Unchanged canonical role, score and provenance joins')
    metric = report['metrics']
    need(type(metric) is dict and set(metric) == set(METRICS)
         and all(type(v) in (int, float) and math.isfinite(v) for v in metric.values()),
         'All four finite canonical metrics required')
    return {key: float(metric[key]) for key in METRICS}


def run(request_path, request_sha256):
    request, freezes, method, custody = metadata(request_path, request_sha256)
    root = path(request['output_root'])
    need(not root.exists() and root.parent.is_dir() and root.name == 'test-pair'
         and root.parent.name == 'report', 'Fresh bounded host report/test-pair root')
    need(not root.is_relative_to(HERE) and not HERE.is_relative_to(root), 'Report disjoint from selected source')
    selected_inputs = [request[k] for k in ('source', 'test_method', 'host_custody', 'panel', 'protocol', 'target', 'evaluator')]
    selected_inputs += list(request['predictions'].values()) + list(request['freezes'].values())
    for row in selected_inputs:
        selected = lexical(row['path'])
        need(not selected.is_relative_to(root) and not root.is_relative_to(selected), 'Report disjoint from exact inputs')
    root.mkdir(mode=0o755)
    snapshots = root / 'snapshots'; snapshots.mkdir(mode=0o755)
    started = publish(root / 'STARTED.json', {'schema': 'smc_test_gain_grade_started_v1',
        'request_sha256': request_sha256, 'source': request['source'], 'host_custody': request['host_custody'],
        'test_method': request['test_method'], 'phase': 'test', 'inference_executed': False})
    copies = {}
    for role in ROLES:
        destination = snapshots / (role + '.h5')
        actual = copy_snapshot(request['predictions'][role]['path'], destination,
                               content_identity(request['predictions'][role]), request['scratch_bytes'])
        copies[role] = {'path': str(destination), **actual}
    package_versions = versions()
    scorer = load_scorer()
    panel = checked(request['panel'])
    expected_shapes = scorer.validate_panel(panel)
    for role in ROLES:
        scorer.validate_submission(copies[role]['path'], panel, require_author_arrays=True)
        actual = scorer.validate_freeze(copies[role]['path'], request['panel']['path'],
                                        request['protocol']['path'], request['freezes'][role]['path'])
        need(encoded(actual) == encoded(freezes[role]), 'Authenticated complete snapshot freeze unchanged')
    proof = verify_scaled_pair(copies['reference']['path'], copies['candidate']['path'],
                               method['selected_row']['gain'], expected_shapes=expected_shapes)
    scale_proof = publish(root / 'SCALE_PROOF.json', proof)
    barrier = publish(root / 'BOTH_SNAPSHOTS.json', {'schema': 'smc_test_gain_both_snapshots_v1',
        'request_sha256': request_sha256, 'source': request['source'], 'host_custody': request['host_custody'],
        'test_method': request['test_method'], 'snapshots': copies, 'freezes': request['freezes'],
        'scale_proof': scale_proof, 'both_complete_original_freezes_validated': True,
        'candidate_transform_verified': True, 'target_payload_accessed': False})
    results = {}
    # Both complete immutable arrays, genuine freezes and exact transformation
    # finish before the unchanged scorer can open either evaluator or TEST target.
    for role in ROLES:
        destination = root / (role + '-score.json')
        report = scorer.score_predictions(copies[role]['path'], request['panel']['path'], request['protocol']['path'],
            request['freezes'][role]['path'], request['target']['path'], request['target']['sha256'],
            request['evaluator']['path'], destination)
        metric = validate_score(report, role, request, freezes[role])
        need(decode(body(destination)) == report, 'Original scorer return and actual saved report agree')
        os.chmod(destination, 0o444)
        results[role] = {'metrics': metric, 'snapshot': copies[role],
                         'score_report': {'path': str(destination), **pin(body(destination))}}
    result = {'schema': 'smc_test_gain_pair_grade_v1', 'status': 'both_test_predictions_scored',
        'phase': 'test', 'dataset': 'mc_maze_20', 'request_sha256': request_sha256,
        'source': request['source'], 'host_custody': request['host_custody'], 'test_method': request['test_method'],
        'selected_row': method['selected_row'], 'lineage': method['lineage'], 'barrier': barrier,
        'scale_proof': scale_proof, 'started': started, 'arms': results,
        'signed_candidate_minus_reference': {key: results['candidate']['metrics'][key]
            - results['reference']['metrics'][key] for key in METRICS},
        'dependency_versions': package_versions,
        'intentional_environment_variant': {'package': 'h5py', 'historical': '3.11.0', 'selected': '3.10.0'},
        'full_four_vectors': True, 'historical_noncausal_supervisor_success': False,
        'new_inference_executed': False, 'participant_episode_executed': False, 'AI_trial_executed': False,
        'scientific_equivalence': None, 'reproduction_claim': False, 'improvement_claim': False, 'SOTA_claim': False,
        'target_exposure': 'public_original_test_targets_released_2026_01'}
    publish(root / 'REPORT.json', result)
    return result
