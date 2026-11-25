"""Authenticate and physically deliver the complete normalized localization input.

This is an owner-side delivery operation, not a source normalizer, participant
sandbox, waveform predictor or scientific qualification run. No reference input
is accepted. Only the four allowed normalized roles can enter a packet.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import types

NEUTRAL_SHA256 = '5069aca47290434f302c9c2b43fd51d81aa21c91f3ff281194bee04731aeeef8'
NEUTRAL_BYTES = 20365
DTYPES = {'<f4': ('f', 4), '<f8': ('d', 8), '<i4': ('i', 4),
          '<i8': ('q', 8), '|b1': ('B', 1)}
MAX_HEADER_BYTES = 65536
MAX_MANIFEST_BYTES = 16 * 1024 * 1024


class PacketError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PacketError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def pin(value):
    require(type(value) is str and len(value) == 64
            and all(x in '0123456789abcdef' for x in value), 'required SHA-256')


def read_regular(path, extent, expected, *, dir_fd=None):
    """Refuse links/devices; authenticate the exact bytes read from one descriptor."""
    pin(expected)
    require(type(extent) is int and extent > 0, 'positive exact byte extent')
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size == extent,
                'regular file with exact declared extent required')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(extent + 1)
    except OSError as exc:
        raise PacketError('input file refused: ' + str(exc)[:120]) from None
    finally:
        if fd is not None:
            os.close(fd)
    require(len(raw) == extent and hashlib.sha256(raw).hexdigest() == expected,
            'input bytes/hash mismatch')
    return raw


def load_neutral():
    path = Path(__file__).resolve().parent.parent / 'centroid-scorer' / 'neutral_contract.py'
    raw = read_regular(path, NEUTRAL_BYTES, NEUTRAL_SHA256)
    module = types.ModuleType('localization_accepted_neutral')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise PacketError('nonfinite JSON literal')
    try:
        require(type(raw) is bytes and len(raw) <= MAX_MANIFEST_BYTES,
                'bounded manifest bytes')
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PacketError('manifest JSON refused: ' + str(exc)[:120]) from None


def validate_array(raw, descriptor):
    """Check primitive NPY without pickle, dtype casts or inferred transposes.

    Returns ordered geometry coordinates only for the geometry role. All other
    values are inspected for finite/Boolean validity and discarded.
    """
    role, dtype, shape = descriptor['role'], descriptor['dtype'], descriptor['shape']
    require(role in {'waveforms', 'template', 'probe_geometry', 'observed_support'},
            'allowed array role')
    require(dtype in DTYPES and ((role == 'observed_support') == (dtype == '|b1')),
            'numeric signals/geometry and Boolean observed support required')
    require(type(raw) is bytes and len(raw) == descriptor['bytes']
            and hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'array bytes/hash')
    require(len(raw) >= 10 and raw[:6] == b'\x93NUMPY', 'NPY header/magic')
    version = tuple(raw[6:8])
    if version == (1, 0):
        start, length = 10, struct.unpack('<H', raw[8:10])[0]
    elif version == (2, 0):
        require(len(raw) >= 12, 'NPY v2 header')
        start, length = 12, struct.unpack('<I', raw[8:12])[0]
    else:
        raise PacketError('only normalized NPY versions 1.0/2.0')
    require(0 < length <= MAX_HEADER_BYTES and start + length <= len(raw), 'NPY header extent')
    header = raw[start:start + length]
    require(header.endswith(b'\n'), 'NPY header newline')
    try:
        tree = ast.parse(header.decode('ascii').strip(), mode='eval')
        require(isinstance(tree.body, ast.Dict), 'NPY header dictionary')
        keys = [ast.literal_eval(k) for k in tree.body.keys]
        require(len(keys) == 3 and set(keys) == {'descr', 'shape', 'fortran_order'},
                'exact unique NPY header keys')
        metadata = ast.literal_eval(tree)
    except (ValueError, TypeError, SyntaxError, UnicodeError, RecursionError) as exc:
        raise PacketError('NPY metadata refused: ' + str(exc)[:120]) from None
    require(type(metadata['shape']) is tuple and all(type(n) is int and n > 0
            for n in metadata['shape']) and list(metadata['shape']) == shape,
            'exact declared NPY shape')
    require(metadata['descr'] == dtype and type(metadata['fortran_order']) is bool,
            'exact declared dtype and Boolean storage order')
    code, width = DTYPES[dtype]
    count = math.prod(shape)
    payload = memoryview(raw)[start + length:]
    require(len(payload) == count * width, 'exact payload extent; no trailing bytes')
    geometry = [] if role == 'probe_geometry' else None
    for item in struct.iter_unpack('<' + code, payload):
        value = item[0]
        require((value in (0, 1)) if dtype == '|b1' else math.isfinite(value),
                'canonical Boolean support or finite numeric values required')
        if geometry is not None:
            geometry.append(value)
    if geometry is not None:
        require(len(shape) == 2 and shape[1] == 2, 'two-axis probe geometry')
        n = shape[0]
        if metadata['fortran_order']:
            return [(geometry[i], geometry[n + i]) for i in range(n)]
        return [(geometry[2 * i], geometry[2 * i + 1]) for i in range(n)]
    return None


def stage(neural, source_root, destination, *, expected_manifest_sha256,
          total_input_byte_budget, maximum_artifact_bytes):
    """Copy all admitted roles; publish manifest.json only after complete checks.

    Source root must contain inputs/<sha256>.npy. Destination is exclusively
    created and cannot be reused. A failed body validation leaves an incomplete
    directory without manifest.json, which must never be delivered. Parent path
    trust and owner-process filesystem access remain external responsibilities.
    """
    pin(expected_manifest_sha256)
    for value in (total_input_byte_budget, maximum_artifact_bytes):
        require(type(value) is int and value > 0, 'explicit positive byte allocations')
    neutral = load_neutral()
    try:
        # Snapshot caller containers before validation and file operations.
        raw = canonical(neural)
        require(len(raw) <= MAX_MANIFEST_BYTES, 'bounded normalized manifest')
        require(hashlib.sha256(raw).hexdigest() == expected_manifest_sha256,
                'whole normalized manifest identity')
        neural = strict_json(raw)
        cases = neutral.validate_neural(neural)
        public = neutral.project(neural)
    except (ValueError, TypeError, OverflowError) as exc:
        raise PacketError('normalized manifest refused: ' + str(exc)[:120]) from None
    artifacts = public['artifacts']
    total_bytes = sum(a['bytes'] for a in artifacts)
    require(total_bytes <= total_input_byte_budget, 'complete input byte allocation; no subset')
    require(all(a['bytes'] <= maximum_artifact_bytes for a in artifacts),
            'each complete artifact must fit allocation')
    require(all((a['role'] == 'observed_support') == (a['dtype'] == '|b1') for a in artifacts),
            'numeric signals/geometry and Boolean observed support required')
    # Do not accept a path in the manifest or follow inputs/ or body symlinks.
    root_fd = inputs_fd = None
    geometries = {}
    output = Path(destination)
    try:
        root_fd = os.open(source_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        inputs_fd = os.open('inputs', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
        (output / 'inputs').mkdir(mode=0o700)
        for artifact in artifacts:
            name = artifact['sha256'] + '.npy'
            body = read_regular(name, artifact['bytes'], artifact['sha256'], dir_fd=inputs_fd)
            geometry = validate_array(body, artifact)
            if geometry is not None:
                geometries[artifact['sha256']] = geometry
            with (output / 'inputs' / name).open('xb') as stream:
                stream.write(body)
        # Coordinate/contact identities must be fixed across each complete cell
        # trajectory; consistent channel permutations remain admissible.
        per_cell = {}
        for case in cases.values():
            coordinates = geometries[case['inputs']['probe_geometry']]
            mapping = tuple(sorted(zip(case['channel_ids'], coordinates)))
            cell = case['cell_id']
            require(cell not in per_cell or per_cell[cell] == mapping,
                    'inconsistent channel/coordinate map within fixed-cell trajectory')
            per_cell[cell] = mapping
        participant_bytes = canonical(public) + b'\n'
        with (output / '.manifest.pending').open('xb') as stream:
            stream.write(participant_bytes)
        (output / '.manifest.pending').rename(output / 'manifest.json')
    except OSError as exc:
        raise PacketError('packet filesystem operation refused: ' + str(exc)[:120]) from None
    finally:
        if inputs_fd is not None:
            os.close(inputs_fd)
        if root_fd is not None:
            os.close(root_fd)
    return {'schema': 'localization-participant-delivery-v1', 'status': 'COMPLETE_PACKET',
            'task_id': neutral.TASK, 'normalized_manifest_sha256': expected_manifest_sha256,
            'participant_manifest_sha256': hashlib.sha256(participant_bytes).hexdigest(),
            'neutral_source_sha256': NEUTRAL_SHA256,
            'cases': len(public['cases']),
            'requests': sum(len(c['requests']) for c in public['cases']),
            'artifact_count': len(artifacts), 'artifact_bytes': total_bytes,
            'roles': sorted({a['role'] for a in artifacts}),
            'reference_input_accepted': False, 'authentic_source_qualification': False,
            'access_mode_qualification': {'direct_observation': False, 'typed_viewer': False,
                                         'tool_assisted': False, 'frozen_program': False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'manifest-sha256', 'source-root', 'destination', 'receipt'):
        parser.add_argument('--' + name, required=True)
    for name in ('manifest-bytes', 'total-input-byte-budget', 'maximum-artifact-bytes'):
        parser.add_argument('--' + name, required=True, type=int)
    args = parser.parse_args(argv)
    require(0 < args.manifest_bytes <= MAX_MANIFEST_BYTES, 'manifest allocation')
    raw = read_regular(args.manifest, args.manifest_bytes, args.manifest_sha256)
    neural = strict_json(raw)
    # Refuse a receipt inside the participant packet; no owner evidence goes there.
    destination = Path(args.destination).resolve()
    receipt_path = Path(args.receipt).resolve()
    require(receipt_path != destination and destination not in receipt_path.parents,
            'owner receipt must be outside participant packet')
    with receipt_path.open('x', encoding='utf-8') as stream:
        try:
            receipt = stage(neural, args.source_root, args.destination,
                            expected_manifest_sha256=hashlib.sha256(canonical(neural)).hexdigest(),
                            total_input_byte_budget=args.total_input_byte_budget,
                            maximum_artifact_bytes=args.maximum_artifact_bytes)
            receipt['source_manifest_file_sha256'] = args.manifest_sha256
        except Exception as exc:
            json.dump({'schema': 'localization-participant-delivery-v1', 'status': 'FAILED',
                       'error': str(exc)}, stream)
            stream.write('\n')
            raise
        json.dump(receipt, stream, sort_keys=True, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
