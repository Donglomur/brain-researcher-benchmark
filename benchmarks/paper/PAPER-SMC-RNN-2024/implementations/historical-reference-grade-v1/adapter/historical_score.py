"""Score two immutable historical author predictions, never a participant attempt.

Both bounded private copies and both original freeze validations precede any
call capable of opening TEST-target contents. Historical protocol text is input
provenance, not fresh authorization. Native supervision belongs to the host.
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
ARMS = ('causal', 'noncausal')
METRICS = ('co-bps', 'vel R2', 'psth R2', 'fp-bps')
META_CAP = 2 * 1024**2
SCRATCH_CAP = 536870912
SOURCE_FILES = {'historical_score.py', 'historical_grade_child.py', 'scorer.py', 'reference_panel.json'}
PACKAGES = {'numpy': '1.26.3', 'scipy': '1.12.0', 'scikit-learn': '1.5.0', 'h5py': '3.10.0'}
PREDICTIONS = {
    'causal': {'bytes': 87217346, 'sha256': '3e315fbf27e790e29f7ad44cb2e1415157eaa8dbe1b68fdf0b38087c193addcc'},
    'noncausal': {'bytes': 87250290, 'sha256': 'fcca208d1d09641a941dfdaf4290493e01ae98be560d665c22f066718c630896'}}
FREEZES = {
    'causal': {'bytes': 808, 'sha256': 'b7b9d3f3e95d9aadd214d3323c602e3e35525d0524b62b22aaafc28221eb738f'},
    'noncausal': {'bytes': 814, 'sha256': '1d927a636ccc7e966c0390521b5f8daac13a8b6d345e8dbcf9d3a848322cf6f7'}}
PINS = {
    'panel': {'bytes': 4333, 'sha256': '3b160dfb4aef8c68cbae8d4a02d5933576a77e4bc47a7c3a5b484369caf95be5'},
    'protocol': {'bytes': 11499, 'sha256': '71242e29e6fba3146a9ae0bfceef4de079390bad4ce02a450ec287c3ec759535'},
    'historical_calibration': {'bytes': 41406, 'sha256': 'e2b33c75d5aa834de6d16403ed9e63c397e6dac95eebe3b482b0dbb9eb925cd1'},
    'target': {'bytes': 105927616, 'sha256': 'f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865'},
    'evaluator': {'bytes': 18292, 'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'},
    'scorer.py': {'bytes': 15050, 'sha256': '48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8'},
    'reference_panel.json': {'bytes': 3665, 'sha256': '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3'}}
SNAPSHOT_DONOR = {'bytes': 26406, 'sha256': 'edfd16c24f726af9d39b9b6fb911f6f232619c26dbd17eaaf83cfddda0a0a0f6',
                  'function': 'copy_snapshot', 'lines': [61, 89]}


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


def source_identity(selected):
    descriptor(selected)
    need(lexical(selected['path']) == HERE / 'SOURCE.json', 'This exact adapter source directory required')
    manifest = checked(selected)
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_historical_reference_grade_source_v1'
         and set(manifest['files']) == SOURCE_FILES, 'Closed historical adapter source roster required')
    for name, expected in manifest['files'].items():
        need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}, 'Exact source member pin required')
        body(HERE / name, expected)
    for name in ('scorer.py', 'reference_panel.json'):
        need(manifest['files'][name] == PINS[name], 'Unchanged original scorer and complete panel required')
    return selected


def metadata(request_path, request_sha256):
    raw = body(request_path)
    need(pin(raw)['sha256'] == request_sha256, 'Selected historical grade request changed')
    request = decode(raw)
    need(type(request) is dict and set(request) == {'schema', 'source', 'predictions', 'freezes', 'panel',
         'protocol', 'historical_calibration', 'target', 'evaluator', 'output_root', 'scratch_bytes'}
         and request['schema'] == 'smc_historical_reference_grade_request_v1', 'Exact historical-only request required')
    source_identity(request['source'])
    for key in ('predictions', 'freezes'):
        need(type(request[key]) is dict and set(request[key]) == set(ARMS), 'Exactly both original reference arms required')
        wanted = PREDICTIONS if key == 'predictions' else FREEZES
        for arm, selected in request[key].items():
            descriptor(selected)
            need({k: selected[k] for k in ('bytes', 'sha256')} == wanted[arm], 'Exact historical ' + key + ' identity required')
    for name in ('panel', 'protocol', 'historical_calibration', 'target', 'evaluator'):
        descriptor(request[name])
        need({k: request[name][k] for k in ('bytes', 'sha256')} == PINS[name], 'Fixed original ' + name + ' identity required')
    snapshots = sum(row['bytes'] for row in PREDICTIONS.values())
    need(type(request['scratch_bytes']) is int
         and snapshots + max(row['bytes'] for row in PREDICTIONS.values()) + META_CAP <= request['scratch_bytes'] <= SCRATCH_CAP,
         'Both snapshots, largest retained scorer snapshot and metadata must be precharged')
    panel, protocol, calibration = (checked(request[k]) for k in ('panel', 'protocol', 'historical_calibration'))
    need(panel['n_eval'] == 574 and panel['n_train'] == 2295 and panel['bin_ms'] == 20,
         'Complete original test panel required')
    need(protocol['input_commitments']['test_panel_sha256'] == request['panel']['sha256']
         and protocol['exposure']['target_sha256'] == request['target']['sha256'], 'Historical protocol joins original inputs')
    need(calibration['completion']['author_reference_calibration_outputs_accepted'] is True
         and calibration['completion']['both_supervised_scoring_stages_passed'] is False,
         'Accepted historical scalars remain distinct from supervision success')
    freezes = {}
    for index, arm in enumerate(ARMS):
        freeze = checked(request['freezes'][arm]); old = calibration['arms'][arm]
        need(freeze['schema'] == 'smc_nlb_prediction_freeze_v1' and freeze['arm'] == arm
             and freeze['dataset'] == 'mc_maze_20' and freeze['role'] == 'author_calibration'
             and freeze['particles'] == 192 and freeze['repeats'] == 32 and freeze['seed'] == 20261117 + index
             and freeze['submission_sha256'] == request['predictions'][arm]['sha256']
             and freeze['panel_manifest_sha256'] == request['panel']['sha256']
             and freeze['protocol_sha256'] == request['protocol']['sha256']
             and freeze['reference_panel_sha256'] == PINS['reference_panel.json']['sha256']
             and old['prediction_sha256'] == freeze['submission_sha256']
             and old['prediction_bytes'] == request['predictions'][arm]['bytes']
             and old['freeze_receipt_sha256'] == request['freezes'][arm]['sha256'], 'Full historical freeze and scalar provenance join required')
        need(set(old['observed_metrics']) == set(METRICS)
             and all(type(v) in (int, float) and math.isfinite(v) for v in old['observed_metrics'].values()),
             'Complete finite accepted historical metric vector required')
        freezes[arm] = freeze
    old_failure = calibration['arms']['noncausal']['scoring_execution']
    need(old_failure['supervisor_success'] is False and old_failure['supervisor_exit_code'] == 1
         and old_failure['failure'] == 'ValueError: Scorer identity changed', 'Historical failed supervisor must remain failed')
    lexical(request['output_root'])
    return request, freezes, calibration


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


def validate_score(report, arm, request, freeze):
    need(report['schema'] == 'smc_nlb_operator_score_v1' and report['arm'] == arm
         and report['role'] == 'author_calibration' and report['method_id'] == freeze['method_id']
         and report['submission_sha256'] == request['predictions'][arm]['sha256']
         and report['prediction_freeze_sha256'] == request['freezes'][arm]['sha256']
         and report['panel_manifest_sha256'] == request['panel']['sha256']
         and report['protocol_sha256'] == request['protocol']['sha256']
         and report['reference_panel_sha256'] == PINS['reference_panel.json']['sha256']
         and report['scorer_sha256'] == request['evaluator']['sha256']
         and report['target_sha256'] == request['target']['sha256']
         and report['dependency_versions'] == PACKAGES, 'Original scored arm/provenance changed')
    metric = report['metrics']
    need(set(metric) == set(METRICS) and all(type(v) in (int, float) and math.isfinite(v) for v in metric.values()),
         'Complete finite original four-metric vector required')
    return {key: float(metric[key]) for key in METRICS}


def run(request_path, request_sha256):
    request, freezes, calibration = metadata(request_path, request_sha256)
    root = path(request['output_root'])
    need(not root.exists() and root.parent.is_dir(), 'Fresh historical report root required')
    need(not root.is_relative_to(HERE) and not HERE.is_relative_to(root), 'Report root disjoint from adapter source')
    selected_inputs = ([request[k] for k in ('source', 'panel', 'protocol', 'historical_calibration', 'target', 'evaluator')]
                       + list(request['predictions'].values()) + list(request['freezes'].values()))
    for row in selected_inputs:
        selected = lexical(row['path'])
        need(not selected.is_relative_to(root) and not root.is_relative_to(selected), 'Report root disjoint from exact inputs')
    root.mkdir(mode=0o755)
    snapshots = root / 'snapshots'; snapshots.mkdir(mode=0o755)
    published = publish(root / 'STARTED.json', {'schema': 'smc_historical_score_started_v1',
        'request_sha256': request_sha256, 'reference_only': True, 'inference_executed': False})
    copies = {}
    for arm in ARMS:
        destination = snapshots / (arm + '.h5')
        actual = copy_snapshot(request['predictions'][arm]['path'], destination, PREDICTIONS[arm], request['scratch_bytes'])
        copies[arm] = {'path': str(destination), **actual}
    package_versions = versions()
    scorer = load_scorer()
    # Both original full-array/freeze validations finish before the first score call.
    for arm in ARMS:
        actual = scorer.validate_freeze(copies[arm]['path'], request['panel']['path'], request['protocol']['path'],
                                        request['freezes'][arm]['path'])
        need(actual == freezes[arm], 'Snapshot freeze differs from authenticated historical metadata')
    barrier = publish(root / 'BOTH_SNAPSHOTS.json', {'schema': 'smc_historical_both_snapshots_v1',
        'request_sha256': request_sha256, 'snapshots': copies, 'both_complete_original_freezes_validated': True,
        'target_payload_accessed': False, 'source': request['source']})
    results = {}
    for arm in ARMS:
        destination = root / (arm + '-score.json')
        report = scorer.score_predictions(copies[arm]['path'], request['panel']['path'], request['protocol']['path'],
            request['freezes'][arm]['path'], request['target']['path'], request['target']['sha256'],
            request['evaluator']['path'], destination)
        metric = validate_score(report, arm, request, freezes[arm])
        need(decode(body(destination)) == report, 'Actual original scorer report bytes must match its returned result')
        os.chmod(destination, 0o444)  # Only this newly created report; original inputs are immutable.
        old = calibration['arms'][arm]
        results[arm] = {'metrics': metric, 'historical_metrics': old['observed_metrics'],
            'signed_delta_from_historical': {key: metric[key] - old['observed_metrics'][key] for key in METRICS},
            'historical_score_sha256': old['score_report_sha256'],
            'historical_supervision': old['scoring_execution'], 'snapshot': copies[arm],
            'score_report': {'path': str(destination), **pin(body(destination))}}
    result = {'schema': 'smc_historical_reference_score_qualification_v1', 'status': 'both_original_predictions_scored',
        'role': 'historical_current_released_checkpoint_calibration_grader_compatibility', 'request_sha256': request_sha256,
        'source': request['source'], 'barrier': barrier, 'started': published, 'arms': results,
        'historical_calibration': request['historical_calibration'], 'dependency_versions': package_versions,
        'historical_dependency_versions': {arm: calibration['arms'][arm]['scoring_dependency_versions'] for arm in ARMS},
        'intentional_environment_variant': {'package': 'h5py', 'historical': '3.11.0', 'selected': '3.10.0'},
        'full_four_vectors': True, 'historical_noncausal_supervisor_success': False,
        'new_inference_executed': False, 'participant_episode_executed': False, 'AI_trial_executed': False,
        'scientific_equivalence': None, 'reproduction_claim': False, 'improvement_claim': False, 'SOTA_claim': False,
        'printed_checkpoint_row_linkage_established': False, 'supervised_completion_qualified_by_this_child': False,
        'target_exposure': 'public_original_test_targets_released_2026_01',
        'interpretation': 'Complete descriptive rescores of historical/current released-checkpoint predictions. No tolerance pass or scientific win; '
                          'fresh host closure is separate, and the failed historical noncausal supervision remains failed.'}
    publish(root / 'REPORT.json', result)
    return result
