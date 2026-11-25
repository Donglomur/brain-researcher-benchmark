"""Complete probe-geometry-centroid negative control, never a competent baseline.

Only authenticated normalized probe geometry is decoded. Waveform, template,
support-mask and spatial-reference bodies are never requested by this producer.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import statistics
import struct
import types

NEUTRAL_PATH = 'neutral_contract.py'
NEUTRAL_BYTES = 20365
NEUTRAL_SHA256 = '5069aca47290434f302c9c2b43fd51d81aa21c91f3ff281194bee04731aeeef8'
DTYPES = {'<f4': ('f', 4), '<f8': ('d', 8), '<i4': ('i', 4), '<i8': ('q', 8)}
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_HEADER_BYTES = 65536


class ControlError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ControlError(message)


def pin(value):
    require(type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value), 'required SHA-256 identity')


def read_regular(path, maximum, expected):
    pin(expected)
    require(type(maximum) is int and maximum >= 0, 'finite input byte allocation')
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'regular file required')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(maximum + 1)
    except OSError as exc:
        raise ControlError('input refused: ' + str(exc)[:100]) from None
    finally:
        if fd is not None:
            os.close(fd)
    require(len(raw) <= maximum and hashlib.sha256(raw).hexdigest() == expected,
            'input extent/hash mismatch')
    return raw


def load_neutral(repo_root):
    path = Path(repo_root) / NEUTRAL_PATH
    raw = read_regular(path, NEUTRAL_BYTES, NEUTRAL_SHA256)
    require(len(raw) == NEUTRAL_BYTES, 'exact accepted neutral source')
    module = types.ModuleType('accepted_localization_neutral')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def strict_json(raw):
    require(type(raw) is bytes and len(raw) <= MAX_JSON_BYTES, 'bounded JSON bytes')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise ControlError('nonfinite JSON literal')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ControlError('invalid manifest JSON: ' + str(exc)[:100]) from None


def decode_geometry(raw, descriptor):
    """Decode only the normalized primitive NPY N-by-2 geometry role.

    NPY v1/v2 header handling is task-local, with no pickle, object dtype,
    compression, transpose guess, trailing payload or unverified unit conversion.
    """
    require(descriptor['role'] == 'probe_geometry' and descriptor['dtype'] in DTYPES,
            'only primitive coordinate geometry')
    require(type(raw) is bytes and len(raw) == descriptor['bytes']
            and hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'geometry bytes/hash')
    require(len(raw) >= 10 and raw[:6] == b'\x93NUMPY', 'NPY magic/header')
    version = tuple(raw[6:8])
    if version == (1, 0):
        start, length = 10, struct.unpack('<H', raw[8:10])[0]
    elif version == (2, 0):
        require(len(raw) >= 12, 'NPY v2 header extent')
        start, length = 12, struct.unpack('<I', raw[8:12])[0]
    else:
        raise ControlError('only normalized NPY versions1.0/2.0')
    require(0 < length <= MAX_HEADER_BYTES and start + length <= len(raw), 'NPY header bound')
    header = raw[start:start + length]
    require(header.endswith(b'\n'), 'NPY header terminator')
    try:
        tree = ast.parse(header.decode('ascii').strip(), mode='eval')
        require(isinstance(tree.body, ast.Dict), 'NPY header dictionary')
        keys = [ast.literal_eval(k) for k in tree.body.keys]
        require(len(keys) == 3 and set(keys) == {'descr', 'shape', 'fortran_order'},
                'exact unique NPY header fields')
        values = ast.literal_eval(tree)
    except (SyntaxError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ControlError('invalid NPY metadata: ' + str(exc)[:100]) from None
    shape = values['shape']
    require(type(shape) is tuple and len(shape) == 2
            and all(type(n) is int and n > 0 for n in shape)
            and shape[1] == 2 and list(shape) == descriptor['shape'], 'exact N-by-2 geometry shape')
    require(values['descr'] == descriptor['dtype'] and type(values['fortran_order']) is bool,
            'declared primitive dtype/order')
    code, width = DTYPES[descriptor['dtype']]
    payload = raw[start + length:]
    require(len(payload) == shape[0] * 2 * width, 'exact NPY payload; no trailing bytes')
    flat = [item[0] for item in struct.iter_unpack('<' + code, payload)]
    require(all(type(v) in (int, float) and math.isfinite(v) for v in flat), 'finite geometry')
    if values['fortran_order']:
        return [[flat[i], flat[shape[0] + i]] for i in range(shape[0])]
    return [[flat[2 * i], flat[2 * i + 1]] for i in range(shape[0])]


def centroid(coordinates):
    require(type(coordinates) is list and coordinates, 'all geometry contacts required')
    def finite(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except (OverflowError, ValueError):
            return False
    require(all(type(row) is list and len(row) == 2 and all(
        finite(v) for v in row) for row in coordinates),
        'finite two-axis contact coordinates')
    # statistics.mean accumulates exact rational values for these finite inputs;
    # a direct floating sum could overflow even when the centroid is finite.
    return [statistics.mean(row[axis] for row in coordinates) for axis in (0, 1)]


def produce(neural, geometry_loader, *, repo_root, expected_manifest_sha256,
            expected_program_sha256, geometry_byte_budget):
    """Return (existing_submission_ABI, control_receipt) for every requested row.

    The owner authenticates the complete normalized manifest. Its reconstructed
    participant projection supplies all scientific inputs to the centroid rule.
    Original cell IDs are used only for the all-condition geometry-consistency
    check; no spatial target, animal grouping, waveform or private mask is used.
    """
    pin(expected_manifest_sha256)
    pin(expected_program_sha256)
    require(type(geometry_byte_budget) is int and geometry_byte_budget > 0,
            'positive whole geometry byte budget')
    source = read_regular(__file__, MAX_JSON_BYTES, expected_program_sha256)
    neutral = load_neutral(repo_root)
    try:
        cases = neutral.validate_neural(neural)
        encoded = neutral.canonical(neural)
        require(hashlib.sha256(encoded).hexdigest() == expected_manifest_sha256,
                'whole normalized manifest identity')
        public = neutral.project(neural)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ControlError('normalized manifest refused: ' + str(exc)[:120]) from None
    artifacts = {a['sha256']: a for a in public['artifacts']}
    selected = {c['inputs']['probe_geometry'] for c in public['cases']}
    required_bytes = sum(artifacts[h]['bytes'] for h in selected)
    require(required_bytes <= geometry_byte_budget, 'whole unique geometry allocation; no subset')
    geometry, read_receipts = {}, []
    for h in sorted(selected):
        descriptor = artifacts[h]
        require(descriptor['dtype'] in DTYPES, 'normalized geometry dtype')
        raw = geometry_loader(dict(descriptor))
        geometry[h] = decode_geometry(raw, descriptor)
        read_receipts.append({'sha256': h, 'bytes': len(raw), 'contacts': len(geometry[h])})
    per_cell, per_case, predictions = {}, [], []
    for case in public['cases']:
        coordinates = geometry[case['inputs']['probe_geometry']]
        require(len(coordinates) == len(case['channel_ids']), 'complete channel/geometry join')
        mapping = tuple(sorted((channel, tuple(row)) for channel, row in
                               zip(case['channel_ids'], coordinates)))
        cell_id = cases[case['case_id']]['cell_id']
        require(cell_id not in per_cell or per_cell[cell_id] == mapping,
                'inconsistent contacts/coordinates within one fixed-cell degradation trajectory')
        per_cell[cell_id] = mapping
        point = centroid(coordinates)
        for request in case['requests']:
            predictions.append({'request_id': request['request_id'], 'case_id': case['case_id'],
                                'status': 'ok', 'coordinate_um': list(point)})
        per_case.append({'case_id': case['case_id'], 'condition_id': case['condition_id'],
                         'geometry_sha256': case['inputs']['probe_geometry'],
                         'contact_count': len(coordinates), 'requested_rows': len(case['requests'])})
    submission = {'schema': 'localization-predictions-v1', 'program_sha256': expected_program_sha256,
                  'coordinate_unit': 'um', 'axis_names': list(public['axis_names']), 'rows': predictions}
    receipt = {'schema': 'localization-centroid-control-v1', 'task_id': neutral.TASK,
               'method': 'probe_geometry_centroid_negative_control',
               'competent_reference': False, 'scientific_qualification': False,
               'normalized_manifest_sha256': expected_manifest_sha256,
               'participant_projection_sha256': hashlib.sha256(neutral.canonical(public)).hexdigest(),
               'program_sha256': hashlib.sha256(source).hexdigest(),
               'neutral_source_sha256': NEUTRAL_SHA256,
               'cases': len(per_case), 'requested_rows': len(predictions),
               'cells': 11, 'conditions': 16, 'realizations': 5,
               'unique_geometry_body_bytes': required_bytes, 'geometry_reads': read_receipts,
               'per_case': per_case, 'forbidden_body_requests': 0,
               'limits': ['The synthetic loader controls prove only this producer requests geometry bodies.',
                          'Authentication of normalized units, axis/channel joins, geometry provenance and the original corpus is external.',
                          'A stable geometry-only estimate is not accurate localization or evidence of absent biological drift.',
                          'This is a declared negative control, not a competent method or a scientific benchmark result.']}
    return submission, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo-root', 'manifest', 'manifest-sha256', 'program-sha256',
                 'participant-root', 'output', 'receipt'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--geometry-byte-budget', type=int, required=True)
    args = parser.parse_args(argv)
    for expected in (args.manifest_sha256, args.program_sha256):
        pin(expected)
    require(args.geometry_byte_budget > 0, 'positive geometry allocation')
    raw = read_regular(args.manifest, MAX_JSON_BYTES, args.manifest_sha256)
    neural = strict_json(raw)
    canonical = json.dumps(neural, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=True, allow_nan=False).encode('ascii')
    def load(descriptor):
        # Reconstruct one hash-named geometry path; no arbitrary artifact path.
        path = Path(args.participant_root) / 'inputs' / (descriptor['sha256'] + '.npy')
        return read_regular(path, descriptor['bytes'], descriptor['sha256'])
    submission, receipt = produce(neural, load, repo_root=args.repo_root,
                                   expected_manifest_sha256=hashlib.sha256(canonical).hexdigest(),
                                   expected_program_sha256=args.program_sha256,
                                   geometry_byte_budget=args.geometry_byte_budget)
    receipt['manifest_file_sha256'] = args.manifest_sha256
    for path, doc in ((args.output, submission), (args.receipt, receipt)):
        with Path(path).open('x', encoding='utf-8') as stream:
            json.dump(doc, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
            stream.write('\n')


if __name__ == '__main__':
    main()
