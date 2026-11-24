"""Complete localization candidate callback lifecycle; no sandbox or qualification.

An owner supplies the complete normalized neural manifest, four allowed array
roles, and one frozen Python source file. No reference argument is accepted.
The owner must isolate this operation from protected files before real use.
"""
import ast
import builtins
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import struct
import types

PACKET_SHA256 = 'c21434fe37da998dc53449e15e530427ae0a7187c9a2cc960ec7218a078c401d'
PACKET_BYTES = 12760
MAX_PROGRAM_BYTES = 256 * 1024
ALLOWED_IMPORTS = {'math', 'statistics', 'struct'}


class ParticipantError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ParticipantError(message)


def load_packet():
    path = Path(__file__).resolve().parent.parent / 'participant-packet' / 'packet.py'
    # Owner-controlled package path, with exact bytes authenticated before import.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        import stat
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size == PACKET_BYTES,
                'pinned packet source extent/type')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(PACKET_BYTES + 1)
    finally:
        if fd is not None:
            os.close(fd)
    require(len(raw) == PACKET_BYTES and hashlib.sha256(raw).hexdigest() == PACKET_SHA256,
            'pinned packet source identity')
    module = types.ModuleType('localization_accepted_packet')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _load_predictor(raw):
    """Freeze one source body and admit only the documented standard-library API.

    This constrains declared dependencies; Python reflection can defeat these
    restrictions. It is deliberately NOT a hostile-code execution sandbox.
    """
    try:
        tree = ast.parse(raw, filename='<frozen-localization-participant>')
    except (SyntaxError, UnicodeError) as exc:
        raise ParticipantError('candidate source syntax refused') from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            require(all(alias.name in ALLOWED_IMPORTS for alias in node.names),
                    'only declared standard-library imports')
        elif isinstance(node, ast.ImportFrom):
            require(node.level == 0 and node.module in ALLOWED_IMPORTS,
                    'only declared standard-library imports')
    def admitted_import(name, globals=None, locals=None, fromlist=(), level=0):
        require(level == 0 and name in ALLOWED_IMPORTS,
                'only declared standard-library imports')
        return builtins.__import__(name, globals, locals, fromlist, level)
    names = ('abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int',
             'isinstance', 'len', 'list', 'max', 'min', 'range', 'reversed',
             'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip', 'Exception',
             'ValueError', 'RuntimeError')
    namespace = {'__name__': 'frozen_localization_participant',
                 '__builtins__': {name: getattr(builtins, name) for name in names}}
    namespace['__builtins__']['__import__'] = admitted_import
    exec(compile(tree, '<frozen-localization-participant>', 'exec'), namespace)
    predictor = namespace.get('predict')
    require(callable(predictor), 'candidate must define predict(case, observations)')
    return predictor


def _decode(packet, raw, descriptor):
    packet.validate_array(raw, descriptor)
    # The accepted validator has already checked the exact unique header keys,
    # primitive dtype, finite values, shape, storage order and payload extent.
    start = 10 if raw[6] == 1 else 12
    size = struct.unpack('<H' if start == 10 else '<I', raw[8:start])[0]
    metadata = ast.literal_eval(raw[start:start + size].decode('ascii').strip())
    code = packet.DTYPES[descriptor['dtype']][0]
    values = tuple(item[0] for item in struct.iter_unpack('<' + code, raw[start + size:]))
    return {'dtype': descriptor['dtype'], 'shape': tuple(descriptor['shape']),
            'fortran_order': metadata['fortran_order'], 'values': values}


def produce(neural, source_root, program_path, *, expected_manifest_sha256,
            expected_program_sha256, program_bytes, total_input_byte_budget,
            maximum_artifact_bytes):
    """Run one immutable entry source on every case; return a complete submission.

    Candidate observations contain flat storage-order values and explicit shape,
    dtype and order. No implicit transpose, crop, masking or waveform estimator
    is applied. Any invalid output aborts the whole operation, never a subset.
    """
    packet = load_packet()
    neutral = packet.load_neutral()
    for digest in (expected_manifest_sha256, expected_program_sha256):
        packet.pin(digest)
    require(type(program_bytes) is int and 0 < program_bytes <= MAX_PROGRAM_BYTES,
            'bounded exact program bytes')
    for value in (total_input_byte_budget, maximum_artifact_bytes):
        require(type(value) is int and value > 0, 'explicit positive array allocations')
    raw_manifest = packet.canonical(neural)
    require(len(raw_manifest) <= packet.MAX_MANIFEST_BYTES and
            hashlib.sha256(raw_manifest).hexdigest() == expected_manifest_sha256,
            'whole normalized manifest identity')
    neural = packet.strict_json(raw_manifest)
    neutral.validate_neural(neural)
    public = neutral.project(neural)
    artifacts = public['artifacts']
    total_bytes = sum(a['bytes'] for a in artifacts)
    require(total_bytes <= total_input_byte_budget and
            all(a['bytes'] <= maximum_artifact_bytes for a in artifacts),
            'complete input allocation; no subset')
    # Read the immutable program body before input bodies, but execute no
    # participant code until the complete input and geometry trajectory pass.
    program = packet.read_regular(program_path, program_bytes, expected_program_sha256)
    root_fd = inputs_fd = None
    arrays, geometry = {}, {}
    try:
        root_fd = os.open(source_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        inputs_fd = os.open('inputs', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root_fd)
        for artifact in artifacts:
            digest = artifact['sha256']
            body = packet.read_regular(digest + '.npy', artifact['bytes'], digest,
                                       dir_fd=inputs_fd)
            arrays[digest] = _decode(packet, body, artifact)
            if artifact['role'] == 'probe_geometry':
                geometry[digest] = packet.validate_array(body, artifact)
    finally:
        if inputs_fd is not None:
            os.close(inputs_fd)
        if root_fd is not None:
            os.close(root_fd)
    per_cell = {}
    for case in neural['cases']:
        mapping = tuple(sorted(zip(case['channel_ids'], geometry[case['inputs']['probe_geometry']])))
        cell = case['cell_id']
        require(cell not in per_cell or per_cell[cell] == mapping,
                'inconsistent channel/coordinate map within fixed-cell trajectory')
        per_cell[cell] = mapping
    predictor = _load_predictor(program)
    rows = []
    for case in public['cases']:
        observations = {role: dict(arrays[digest]) for role, digest in case['inputs'].items()}
        candidate_case = copy.deepcopy(case)
        # The axes/unit live at the projection's top level but are necessary to
        # interpret geometry columns and return coordinates in the verified order.
        candidate_case['axis_names'] = list(public['axis_names'])
        candidate_case['coordinate_unit'] = public['coordinate_unit']
        result = predictor(candidate_case, observations)
        expected = {r['request_id'] for r in case['requests']}
        require(type(result) is dict and set(result) == expected,
                'candidate must return every request exactly once; no extra requests')
        for request in case['requests']:
            point = result[request['request_id']]
            require(type(point) in (list, tuple) and len(point) == 2 and
                    all(neutral.finite_number(x) for x in point),
                    'two finite ordered coordinates per request')
            rows.append({'request_id': request['request_id'], 'case_id': case['case_id'],
                         'status': 'ok', 'coordinate_um': list(point)})
    # Detect changed on-disk entry source as well as using one loaded byte body.
    packet.read_regular(program_path, program_bytes, expected_program_sha256)
    submission = {'schema': 'localization-predictions-v1',
                  'program_sha256': expected_program_sha256, 'coordinate_unit': 'um',
                  'axis_names': list(public['axis_names']), 'rows': rows}
    receipt = {'schema': 'localization-frozen-participant-v1', 'status': 'COMPLETE_OUTPUT',
               'task_id': neutral.TASK, 'program_sha256': expected_program_sha256,
               'normalized_manifest_sha256': expected_manifest_sha256,
               'participant_projection_sha256': hashlib.sha256(packet.canonical(public)).hexdigest(),
               'submission_sha256': hashlib.sha256(packet.canonical(submission)).hexdigest(),
               'cases': len(public['cases']), 'requests': len(rows),
               'artifact_bytes': total_bytes, 'runtime_python': platform.python_version(),
               'declared_standard_library_imports': sorted(ALLOWED_IMPORTS),
               'reference_input_accepted': False, 'sandbox_enforced': False,
               'authentic_source_qualification': False, 'scientific_qualification': False}
    return submission, receipt
