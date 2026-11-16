"""Complete condition-permitted training-count projection; no test-response opens.

This replaces only the response-loading branch, not stimulus reconstruction,
native reference fitting or original scientific census authentication.
"""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

TASK = 'marmoset-retinal-contrast-generalization'
DATASETS = {'20220412_SN_252MEA6010_le_s4', '20220426_SS_252MEA6010_le_n3'}
CLASSES = {'off_midget': 51, 'off_parasol': 69, 'on_parasol': 35, 'large_off_pooled': 15}
CONDITIONS = {
    'wn_to_wn': {'WN': 'fit'},
    'nm_to_nm_source_only': {'NM': 'fit'},
    'nm_to_nm_wn_calibrated_author': {'NM': 'fit', 'WN': 'calibration_only'},
    'wn_to_nm_source_only': {'WN': 'fit'},
    'nm_to_wn_source_only': {'NM': 'fit'},
    'nm_to_wn_wn_assisted': {'NM': 'fit', 'WN': 'calibration_only'},
}
DTYPES = {'|u1': ('B', 1), '|i1': ('b', 1), '<u2': ('H', 2), '<i2': ('h', 2),
          '<u4': ('I', 4), '<i4': ('i', 4), '<u8': ('Q', 8), '<i8': ('q', 8),
          '<f4': ('f', 4), '<f8': ('d', 8)}


class InputError(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise InputError(reason)


def pin(value):
    need(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
         'required external SHA-256 identity')


def exact(value, fields, name):
    need(type(value) is dict and set(value) == set(fields), name + ': exact fields')


def opaque(value):
    need(type(value) is str and len(value) == 32 and all(c in '0123456789abcdef' for c in value),
         'opaque identifier')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def unique(values):
    need(type(values) is list and values, 'nonempty complete identity list')
    for value in values:
        opaque(value)
    need(len(set(values)) == len(values), 'duplicate identity')


def validate_policy(policy, expected_sha256):
    """Source-qualified policy is external authority, never a self-issued flag."""
    pin(expected_sha256)
    need(hashlib.sha256(canonical(policy)).hexdigest() == expected_sha256, 'whole policy identity')
    exact(policy, ('schema', 'task_id', 'source_release', 'condition', 'cohort_evidence_sha256',
                   'complete_stream_census_sha256', 'preparations', 'streams'), 'policy')
    need(policy['schema'] == 'marmoset-train-only-policy-v1' and policy['task_id'] == TASK,
         'exact task and policy schema')
    need(policy['source_release'] == '10.12751/g-node.t43ph1', 'unchanged original release')
    need(policy['condition'] in CONDITIONS, 'declared evidence condition')
    pin(policy['cohort_evidence_sha256']); pin(policy['complete_stream_census_sha256'])
    need(type(policy['preparations']) is list and len(policy['preparations']) == 2,
         'both original preparations required')
    preparations, all_cells, classes = {}, set(), {k: 0 for k in CLASSES}
    for prep in policy['preparations']:
        exact(prep, ('dataset', 'cells'), 'preparation')
        dataset = prep['dataset']
        need(dataset in DATASETS and dataset not in preparations, 'both exact source datasets')
        need(type(prep['cells']) is list and prep['cells'], 'full selected cell support')
        cells = []
        for cell in prep['cells']:
            exact(cell, ('cell_id', 'published_class'), 'cell')
            ident = cell['cell_id']; opaque(ident)
            need(ident not in all_cells and cell['published_class'] in CLASSES, 'unique classified cell')
            classes[cell['published_class']] += 1; all_cells.add(ident); cells.append(ident)
        preparations[dataset] = cells
    need(set(preparations) == DATASETS and len(all_cells) == 170 and classes == CLASSES,
         'complete fixed paper-selected170-cell class census')
    need(type(policy['streams']) is list and policy['streams'], 'complete original stream declaration')
    seen, streams, coverage = set(), [], {d: {'WN': 0, 'NM': 0} for d in DATASETS}
    for stream in policy['streams']:
        exact(stream, ('dataset', 'stimulus', 'seed', 'source_cell_ids', 'train_trial_ids',
                       'train_frames_per_trial', 'test_frames_per_trial', 'timing_evidence_sha256',
                       'independent_extent_evidence_sha256', 'artifact'), 'stream')
        dataset, domain, seed = stream['dataset'], stream['stimulus'], stream['seed']
        need(dataset in preparations and domain in {'WN', 'NM'}, 'original dataset/stimulus')
        need((domain == 'WN' and seed is None) or (domain == 'NM' and type(seed) is int and seed in (1, 2)),
             'official source seed domain')
        key = (dataset, domain, seed); need(key not in seen, 'duplicate source stream')
        seen.add(key); coverage[dataset][domain] += 1
        unique(stream['source_cell_ids']); unique(stream['train_trial_ids'])
        need(set(preparations[dataset]) <= set(stream['source_cell_ids']), 'every selected cell in every stream')
        for field in ('train_frames_per_trial', 'test_frames_per_trial'):
            need(type(stream[field]) is int and stream[field] > 0, 'explicit complete frame extent')
        pin(stream['timing_evidence_sha256']); pin(stream['independent_extent_evidence_sha256'])
        art = stream['artifact']; exact(art, ('bytes', 'sha256', 'dtype', 'shape'), 'training artifact')
        need(type(art['bytes']) is int and art['bytes'] > 0, 'finite body extent')
        pin(art['sha256']); need(art['dtype'] in DTYPES, 'primitive count dtype')
        shape = [len(stream['source_cell_ids']), len(stream['train_trial_ids']), stream['train_frames_per_trial']]
        need(type(art['shape']) is list and all(type(n) is int for n in art['shape'])
             and art['shape'] == shape, 'complete cells/trials/frames source shape')
        streams.append(stream)
    need(all(v['WN'] == 1 and v['NM'] >= 1 for v in coverage.values()),
         'both domains for both preparations; do not infer a missing native seed')
    return preparations, streams


def official_training_path(stream):
    if stream['stimulus'] == 'WN':
        return Path('data') / 'white_noise' / stream['dataset'] / 'responses' / 'train_responses_binned.npy'
    return (Path('data') / 'naturalistic_movies' / 'responses' / stream['dataset'] /
            ('seed_' + str(stream['seed'])) / 'train_responses_binned.npy')


def read_training(root, stream):
    """Open only the reconstructed official training leaf, never its test sibling."""
    art = stream['artifact']; pin(art['sha256'])
    path = Path(root) / official_training_path(stream)
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == art['bytes'],
             'bounded ordinary single-link training file')
        with os.fdopen(fd, 'rb') as source:
            fd = None; raw = source.read(art['bytes'] + 1)
    except OSError as exc:
        raise InputError('training operand refused: ' + str(exc)[:100]) from None
    finally:
        if fd is not None: os.close(fd)
    need(len(raw) == art['bytes'] and hashlib.sha256(raw).hexdigest() == art['sha256'], 'training body identity')
    return raw


def project_counts(raw, artifact, source_cells, selected_cells):
    """Read primitive NPY counts and retain every selected cell/trial/frame."""
    need(type(raw) is bytes and len(raw) == artifact['bytes']
         and hashlib.sha256(raw).hexdigest() == artifact['sha256'], 'complete training bytes')
    need(len(raw) >= 10 and raw[:6] == b'\x93NUMPY', 'NPY training header')
    version = tuple(raw[6:8])
    if version == (1, 0): start, length = 10, struct.unpack('<H', raw[8:10])[0]
    elif version == (2, 0):
        need(len(raw) >= 12, 'NPY v2 extent'); start, length = 12, struct.unpack('<I', raw[8:12])[0]
    else: raise InputError('only primitive NPY v1/v2 training files')
    need(0 < length <= 65536 and start + length <= len(raw), 'bounded NPY metadata')
    header = raw[start:start + length]; need(header.endswith(b'\n'), 'NPY header terminator')
    try:
        tree = ast.parse(header.decode('ascii').strip(), mode='eval')
        need(isinstance(tree.body, ast.Dict), 'NPY header dictionary')
        keys = [ast.literal_eval(k) for k in tree.body.keys]
        need(len(keys) == 3 and set(keys) == {'descr', 'shape', 'fortran_order'}, 'exact unique NPY fields')
        meta = ast.literal_eval(tree)
    except (ValueError, TypeError, SyntaxError, UnicodeError, RecursionError):
        raise InputError('invalid NPY metadata') from None
    need(type(meta['shape']) is tuple and all(type(n) is int for n in meta['shape'])
         and list(meta['shape']) == artifact['shape'], 'exact complete source shape')
    need(meta['descr'] == artifact['dtype'] and meta['descr'] in DTYPES
         and type(meta['fortran_order']) is bool, 'primitive dtype/order')
    cells, trials, frames = artifact['shape']; code, width = DTYPES[meta['descr']]
    payload = memoryview(raw)[start + length:]
    need(len(payload) == cells * trials * frames * width, 'exact full payload; no trailing bytes')
    for (value,) in struct.iter_unpack('<' + code, payload):
        need(math.isfinite(value) and value >= 0 and (type(value) is int or value.is_integer()),
             'binned counts must be finite nonnegative integers; rates need separate conversion')
    index = {ident: i for i, ident in enumerate(source_cells)}
    output = bytearray()
    for ident in selected_cells:
        row = index[ident]
        if not meta['fortran_order']:
            first = row * trials * frames * width
            output.extend(payload[first:first + trials * frames * width])
        else:
            for trial in range(trials):
                for frame in range(frames):
                    first = (row + cells * (trial + trials * frame)) * width
                    output.extend(payload[first:first + width])
    return bytes(output)


def prepare_training(policy, *, policy_sha256, source_root, read_byte_budget, output_byte_budget):
    """Return complete typed count buffers and target-free timing descriptors.

    No files are written; a selected owner must retain/use the returned buffers
    under its own lifecycle/memory/output policy. All selected streams validate
    before a result is returned. The output buffers are raw little-endian C-order
    primitive counts with explicit shape/dtype, not pickles or implicit rates.
    """
    preparations, streams = validate_policy(policy, policy_sha256)
    for bound in (read_byte_budget, output_byte_budget):
        need(type(bound) is int and bound > 0, 'explicit complete byte allocation')
    allowed = CONDITIONS[policy['condition']]
    selected = [s for s in streams if s['stimulus'] in allowed]
    required_read = sum(s['artifact']['bytes'] for s in selected)
    required_output = sum(len(preparations[s['dataset']]) * len(s['train_trial_ids']) *
                          s['train_frames_per_trial'] * DTYPES[s['artifact']['dtype']][1] for s in selected)
    need(required_read <= read_byte_budget and required_output <= output_byte_budget,
         'complete condition allocation required; no stream/cell/trial/frame subset')
    packets = []
    for stream in selected:
        cells = preparations[stream['dataset']]; art = stream['artifact']
        raw = read_training(source_root, stream)
        counts = project_counts(raw, art, stream['source_cell_ids'], cells)
        packets.append({'dataset': stream['dataset'], 'stimulus': stream['stimulus'], 'seed': stream['seed'],
            'response_access': allowed[stream['stimulus']], 'cell_ids': list(cells),
            'train_trial_ids': list(stream['train_trial_ids']),
            'shape': [len(cells), len(stream['train_trial_ids']), stream['train_frames_per_trial']],
            'dtype': art['dtype'], 'unit': 'spike_count_per_stimulus_update', 'order': 'C',
            'counts': counts, 'counts_sha256': hashlib.sha256(counts).hexdigest(),
            'source_sha256': art['sha256'], 'test_frames_per_trial': stream['test_frames_per_trial'],
            'extent_source': 'externally frozen target-independent metadata; not a test-response read',
            'timing_evidence_sha256': stream['timing_evidence_sha256'],
            'independent_extent_evidence_sha256': stream['independent_extent_evidence_sha256']})
    return {'schema': 'marmoset-train-only-response-result-v1', 'task_id': TASK,
            'policy_sha256': policy_sha256, 'condition': policy['condition'], 'packets': packets,
            'selected_cells': 170, 'preparations': 2, 'source_body_bytes': required_read,
            'output_count_bytes': required_output, 'protected_response_reads': 0, 'original_sta_reads': 0,
            'historical_test_selected_cohort': True, 'scientific_qualification': False,
            'limits': ['Declared identities and timing/calibration provenance require external scientific authentication.',
                       'Response branch only: no stimulus construction, native RF/STA fit or protected execution.',
                       'Source-only NM fitting requires a separately qualified NM-only RF method.',
                       'Calibration-only response access does not enforce the behavior of a future fitting program.',
                       'Memory/process isolation and ancestor-directory trust are externally owned.']}
