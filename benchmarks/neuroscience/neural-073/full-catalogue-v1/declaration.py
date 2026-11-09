"""Closed task declarations and portable source closure; no operational admission.

Reading this package authenticates explicit source/metadata bytes, not native
qualification or independent trust. No external L body is opened by inspect.
"""
from pathlib import Path, PurePosixPath
import ast
import hashlib
import json
import math
import os
import re
import stat


class DeclarationError(ValueError):
    pass


class ReadLedger:
    """Conservative logical reservations survive failed reads; not physical I/O."""
    def __init__(self, read_cap):
        if type(read_cap) is not int or not 0 < read_cap <= 2**53-1:
            raise DeclarationError('finite positive read cap')
        self.cap = read_cap
        self.reserved_bytes = 0
        self.actual_bytes = 0
        self.attempts = []

    def reserve(self, path, size):
        if type(size) is not int or size < 0 or self.reserved_bytes + size > self.cap:
            raise DeclarationError('source read reservation exceeds admitted cap')
        self.reserved_bytes += size
        row = {'path': str(path), 'reserved_bytes': size, 'read_bytes': 0,
               'status': 'attempted'}
        self.attempts.append(row)
        return row


def _need(ok, message):
    if not ok:
        raise DeclarationError(message)


def _keys(value, fields, name):
    _need(type(value) is dict and set(value) == set(fields), 'closed fields: ' + name)
    return value


def _sha(value):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
          'exact lowercase SHA256')
    return value


def _json_value(value, depth=0, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    _need(depth <= 64 and counter[0] <= 500000, 'bounded JSON structure')
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float:
        _need(math.isfinite(value), 'finite JSON number')
    elif type(value) is str:
        _need('\x00' not in value, 'NUL in JSON text')
        try:
            value.encode('utf-8')
        except UnicodeError as error:
            raise DeclarationError('invalid Unicode scalar text') from error
    elif type(value) is list:
        for item in value:
            _json_value(item, depth + 1, counter)
    elif type(value) is dict:
        for key, item in value.items():
            _need(type(key) is str, 'JSON object keys must be strings')
            _json_value(key, depth + 1, counter)
            _json_value(item, depth + 1, counter)
    else:
        raise DeclarationError('ordinary closed JSON values only')


def canonical_file_bytes(value):
    _json_value(value)
    try:
        return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise DeclarationError('cannot encode canonical JSON') from error


def _parse(raw):
    def pairs(items):
        out = {}
        for key, item in items:
            _need(key not in out, 'duplicate JSON key')
            out[key] = item
        return out
    def constant(value):
        raise DeclarationError('nonfinite JSON constant: ' + value)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=constant)
        _json_value(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise DeclarationError('invalid bounded JSON') from error


def relative_path(value):
    _need(type(value) is str and 0 < len(value.encode('utf-8')) <= 4096 and
          '\x00' not in value and '\\' not in value and not value.startswith('/'),
          'canonical relative path required')
    _need(value == PurePosixPath(value).as_posix() and
          all(x not in ('', '.', '..') for x in value.split('/')),
          'relative path traversal or alias')
    _need(not any(x in ('.git', '.ssh', '.aws', '.codex') for x in value.split('/')),
          'private control path excluded')
    return value


def _absolute(value):
    if isinstance(value, Path):
        value = str(value)
    _need(type(value) is str and value.startswith('/') and len(value.encode('utf-8')) <= 4096,
          'explicit absolute path required')
    _need(value != '/' and '\x00' not in value and '\\' not in value and
          value == PurePosixPath(value).as_posix() and
          all(x not in ('', '.', '..') for x in value.split('/')[1:]),
          'absolute path traversal or alias')
    return Path(value)


def _pin(value, *, path_allowed=True, max_bytes=16*1024*1024):
    _need(type(value) is dict, 'pin object required')
    fields = set(value)
    _need(fields == {'bytes', 'sha256'} or path_allowed and
          fields == {'path', 'bytes', 'sha256'}, 'closed pin fields')
    _need(type(value['bytes']) is int and 0 <= value['bytes'] <= max_bytes,
          'bounded exact pin byte count')
    _sha(value['sha256'])
    if 'path' in value:
        if type(value['path']) is str and value['path'].startswith('/'):
            _absolute(value['path'])
        else:
            relative_path(value['path'])
    return value


def _stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def _safe_read(path, pin, *, limit, ledger):
    path = _absolute(path)
    _need(type(limit) is int and 0 <= limit <= 64*1024*1024, 'finite body read limit')
    _need(type(ledger) is ReadLedger, 'concrete source ReadLedger required')
    if pin is not None:
        _pin(pin, max_bytes=limit)
        if 'path' in pin:
            declared = pin['path']
            _need(str(path) == declared if declared.startswith('/') else
                  tuple(path.parts[-len(PurePosixPath(declared).parts):]) == PurePosixPath(declared).parts,
                  'explicit pin path does not match selected path')
    _need(hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY'),
          'safe descriptor-relative reads unsupported on this host')
    held = []
    chain = []
    row = ledger.reserve(path, pin['bytes'] if pin is not None else 0)
    original = None
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        held.append(fd)
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            held.append(child)
            chain.append((fd, part, child, _stamp(os.fstat(child))))
            fd = child
        name = path.name
        body_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        held.append(body_fd)
        before = os.fstat(body_fd)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
              'ordinary single-link file required')
        _need(0 <= before.st_size <= limit, 'body exceeds selected limit')
        if pin is not None:
            _need(before.st_size == pin['bytes'], 'body size differs from pin')
        if pin is None:
            _need(ledger.reserved_bytes + before.st_size <= ledger.cap, 'source read reservation exceeds admitted cap')
            ledger.reserved_bytes += before.st_size
            row['reserved_bytes'] = before.st_size
        pieces = []
        left = before.st_size
        while left:
            block = os.read(body_fd, min(left, 65536))
            _need(bool(block), 'short source read')
            pieces.append(block)
            left -= len(block)
            row['read_bytes'] += len(block)
            ledger.actual_bytes += len(block)
        raw = b''.join(pieces)
        after = os.fstat(body_fd)
        _need(_stamp(before) == _stamp(after) and
              _stamp(after) == _stamp(os.stat(name, dir_fd=fd, follow_symlinks=False)),
              'source replaced or changed during read')
        for parent, part, child, stamp in chain:
            _need(_stamp(os.fstat(child)) == stamp and
                  _stamp(os.stat(part, dir_fd=parent, follow_symlinks=False)) == stamp,
                  'source ancestor changed during read')
        if pin is not None:
            _need(hashlib.sha256(raw).hexdigest() == pin['sha256'], 'source SHA256 differs')
        row['status'] = 'read_verified' if pin is not None else 'read_unanchored_metadata'
        return raw
    except BaseException as error:
        original = error
        if row is not None:
            row['status'] = 'failed'
            row['error_type'] = type(error).__name__
        raise
    finally:
        errors = []
        for fd in reversed(held):
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
        if errors:
            if original is not None:
                raise BaseExceptionGroup('source operation and close errors', [original, *errors]) from None
            raise ExceptionGroup('source descriptor close failed', errors)


def read_bytes_pinned(path, pin, *, limit, ledger=None):
    """Exact non-JSON source reader sharing every custody/byte guard."""
    _pin(pin, max_bytes=limit)
    if ledger is None:
        ledger = ReadLedger(max(1, limit))
    return _safe_read(path, pin, limit=limit, ledger=ledger)


def read_json_pinned(path, pin, *, limit, ledger=None):
    _pin(pin, max_bytes=limit)
    if ledger is None:
        ledger = ReadLedger(max(1, limit))
    raw = _safe_read(path, pin, limit=limit, ledger=ledger)
    return _parse(raw), raw


def _raw_pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


SECTIONS = ('trust_anchor', 'numerical', 'corpus', 'host', 'provider', 'capacity', 'private_output')
DEPLOYMENT_FIELDS = ('schema', 'status', 'execution_enabled', 'candidate_id', 'instance_id',
                     'accepted_parent_closure_digest', 'code_closure_digest', 'task_design_digest',
                     'allowed_policy_profile_digest', 'section_manifests')


def validate_deployment(value, *, configured_required=False):
    _keys(value, DEPLOYMENT_FIELDS, 'deployment')
    _need(type(configured_required) is bool, 'boolean configured requirement')
    _need(value['schema'] == 'n073_full_deployment_v1' and value['candidate_id'] == 'NEURAL-073',
          'deployment schema/task')
    for name in ('accepted_parent_closure_digest', 'code_closure_digest', 'task_design_digest'):
        _sha(value[name])
    _keys(value['section_manifests'], SECTIONS, 'seven explicit deployment sections')
    if value['status'] == 'unconfigured':
        _need(value['execution_enabled'] is False and value['instance_id'] is None and
              value['allowed_policy_profile_digest'] is None and
              all(x is None for x in value['section_manifests'].values()),
              'unconfigured deployment must contain no operational substitutes')
        _need(not configured_required, 'deployment is unconfigured; no execution admitted')
    else:
        _need(value['status'] == 'configured' and value['execution_enabled'] is True,
              'configured deployment status')
        _need(type(value['instance_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', value['instance_id']) is not None,
              'bounded instance ID')
        _sha(value['allowed_policy_profile_digest'])
        for row in value['section_manifests'].values():
            _keys(row, ('path', 'bytes', 'sha256'), 'external L metadata pin')
            _pin(row, max_bytes=64*1024*1024)
            _need(row['bytes'] > 0, 'nonempty selected L metadata')
    return json.loads(canonical_file_bytes(value))


def validate_policy(value):
    _keys(value, ('schema', 'policy_id', 'model_profile_id', 'max_response_tokens', 'inference_policy'),
          'fixed candidate policy')
    _need(value['schema'] == 'n073_full_policy_v1', 'policy schema')
    for name in ('policy_id', 'model_profile_id'):
        _need(type(value[name]) is str and re.fullmatch('[A-Za-z0-9_.:-]{1,128}', value[name]) is not None,
              'bounded fixed policy/profile ID')
    _need(type(value['max_response_tokens']) is int and 1 <= value['max_response_tokens'] <= 131072,
          'exact fixed output bound')
    # This accepted module is pure; imports neither NumPy nor host/provider code.
    from .runtime.core.inference import InferencePolicy
    try:
        policy = InferencePolicy.from_dict(value['inference_policy'])
    except (ValueError, TypeError, KeyError) as error:
        raise DeclarationError('invalid accepted inference policy') from error
    _need(policy.to_dict() == value['inference_policy'], 'noncanonical inference policy')
    return json.loads(canonical_file_bytes(value))

ACCEPTED_PARENT = {'runtime/__init__.py': {'bytes': 89,
                         'role': 'operative',
                         'sha256': '61fa15bbbcf1d7e5e2d7dbaa7f72b99e9a1ef2e6e14373b24ba3d0a074f67b60'},
 'runtime/admission/__init__.py': {'bytes': 803,
                                   'role': 'operative',
                                   'sha256': '1bef840eecd35419791707934e5bf7247da3275aa6157487563720d15ad854bb'},
 'runtime/admission/arrays.py': {'bytes': 22071,
                                 'role': 'operative',
                                 'sha256': '23439c8f686d7e48efa46262dd30f69f5e09ae72edf69c59f56134db9182fd8c'},
 'runtime/admission/catalogue.py': {'bytes': 11112,
                                    'role': 'operative',
                                    'sha256': '97b4125eee4d71748c39f51bb4a13e4c92d0999d7be435ca1f2a2bf8040d501a'},
 'runtime/admission/export.py': {'bytes': 19927,
                                 'role': 'operative',
                                 'sha256': 'dbd1163456c65e9bfa0eda8ce9f92cd710c0c960f945164c00e35d416de0c6e4'},
 'runtime/admission/history/pre-compact-index/export.py': {'bytes': 19718,
                                                           'role': 'inactive_history',
                                                           'sha256': 'f965dc5e6c5b3ec66fab384ccb9885f34fc1636bed83e8b393047427b5fb6e6e'},
 'runtime/context_io/__init__.py': {'bytes': 307,
                                    'role': 'operative',
                                    'sha256': '985fc4f925b1508e4eda5a26c2f2643b5c5a9020a8435a927d0370e7d0352dc3'},
 'runtime/context_io/capsules.py': {'bytes': 9746,
                                    'role': 'operative',
                                    'sha256': '15d3867f675b25d2e77c73dc91bae7a3d294af11049d9db902c262e0e533273f'},
 'runtime/context_io/filesystem.py': {'bytes': 16574,
                                      'role': 'operative',
                                      'sha256': 'e16e30040767d3219c97d74b4db7a976254f54d4880274eead51de7068c2836b'},
 'runtime/context_io/history/pre-failure-delta/capsules.py': {'bytes': 9557,
                                                              'role': 'inactive_history',
                                                              'sha256': '5a4c5e279aa60d63bfa2d6c508f03f24c4b40fd883fdc68ff1285224cbafc521'},
 'runtime/context_io/history/pre-failure-delta/filesystem.py': {'bytes': 15203,
                                                                'role': 'inactive_history',
                                                                'sha256': '60d384dec5c448dd783127b7289ac05edefa01f1c7df30f8a02ee77dc81c0c18'},
 'runtime/context_io/history/pre-failure-delta/snapshot.py': {'bytes': 7109,
                                                              'role': 'inactive_history',
                                                              'sha256': '845a215ec51b02032d0e123aed91720c04a412460345dce85494235a5ce3148b'},
 'runtime/context_io/native_seal_v1/__init__.py': {'bytes': 274,
                                                   'role': 'operative',
                                                   'sha256': 'ead8c57d5599ab74e4a56b56e592022078ab53827f031629a9be7c9300a45294'},
 'runtime/context_io/native_seal_v1/contracts.py': {'bytes': 12790,
                                                    'role': 'operative',
                                                    'sha256': '8639a676f23f5638e53d5095e12d8cbe607b81a7f0b6c3926e93e8a779bce139'},
 'runtime/context_io/native_seal_v1/history/pre-tool-support/contracts.py': {'bytes': 11262,
                                                                             'role': 'inactive_history',
                                                                             'sha256': '760f42040ee96183263a36f97af9866ea488e33aac26474ad394bd8ac2b4b899'},
 'runtime/context_io/native_seal_v1/history/pre-tool-support/native.py': {'bytes': 19710,
                                                                          'role': 'inactive_history',
                                                                          'sha256': '2da63444f4f6e000f32df892a461cafae13a26d4f4b6477b89942278c1d3f5cb'},
 'runtime/context_io/native_seal_v1/native.py': {'bytes': 19744,
                                                 'role': 'operative',
                                                 'sha256': 'cd0ac1bb4b709d658fde408c5015e32344a037b20635b2be59b82f9763679e24'},
 'runtime/context_io/snapshot.py': {'bytes': 9382,
                                    'role': 'operative',
                                    'sha256': 'b295102bc71fd79d712d0bf08e9a3aed2dfd08fed09152acb2a870a9a88cba0b'},
 'runtime/core/__init__.py': {'bytes': 52,
                              'role': 'operative',
                              'sha256': '0e612da1efc73df6448226188eabfb53e198f1e23e18c372b28b1b09f662ee72'},
 'runtime/core/artifact_outcomes.py': {'bytes': 9074,
                                       'role': 'operative',
                                       'sha256': '64cf6afc7a3fac5c278f9ebede694afbf7d6e95cdcf6688a96ce6366e2c4e2a0'},
 'runtime/core/custody.py': {'bytes': 10601,
                             'role': 'operative',
                             'sha256': '462fc7475cd53955fc24168c57ffa3921705de1927c546deb27b78c9c3169a65'},
 'runtime/core/inference.py': {'bytes': 10765,
                               'role': 'operative',
                               'sha256': 'b4064becd7f605c61cdd16d77a6c0aab4644fed9c7fe645d80d56541d0f41861'},
 'runtime/core/oom_witness.py': {'bytes': 14994,
                                 'role': 'operative',
                                 'sha256': '754171a79566d41b78a63dfa64d5445c4b049ae6c6c4c854b5b8389d6d450676'},
 'runtime/core/outcomes.py': {'bytes': 12435,
                              'role': 'operative',
                              'sha256': 'a50901f3cbfec6227f3d8cfb66fe1eedfd38546035f284aa80b77c59f74c20d7'},
 'runtime/core/phase_v2.py': {'bytes': 1230,
                              'role': 'operative',
                              'sha256': '70e68dcc18ad757a371755157a0746405f1e4c8d5465d185ebf7d16e8fb4a921'},
 'runtime/core/plan.py': {'bytes': 11183,
                          'role': 'operative',
                          'sha256': 'ddc546acd3f0111d99592460e5aff0303660bc8e2b6d1954d705e6095e375dc9'},
 'runtime/core/resources.py': {'bytes': 9740,
                               'role': 'operative',
                               'sha256': '94f0e41bd72c34b9cf91c4e246dfe50b632e22a7e59dd713c8a301c7ec7da262'},
 'runtime/estimators/__init__.py': {'bytes': 1257,
                                    'role': 'operative',
                                    'sha256': '204f4ca88501e4e6e0ac1ecc1f3650e4a3955752529cbec73ca18cc16630033b'},
 'runtime/estimators/_common.py': {'bytes': 9753,
                                   'role': 'operative',
                                   'sha256': '7a064b570a832641fff8f40db7c1c19557ce9f3cf369dcdede9682beb003f13e'},
 'runtime/estimators/history/pre-decode-order-v2/_common.py': {'bytes': 9626,
                                                               'role': 'inactive_history',
                                                               'sha256': 'c1379c4896c8cdb4d499c5d74c463a5e1d7e1f6f31bdc946332776ef76126eb3'},
 'runtime/estimators/history/pre-decode-order-v2/svm.py': {'bytes': 18939,
                                                           'role': 'inactive_history',
                                                           'sha256': '664b121c26b95fdface59de7bf38a9ea730b628e9c50b0a23a21f5f61952f27d'},
 'runtime/estimators/history/pre-decode-order-v2/trees.py': {'bytes': 14281,
                                                             'role': 'inactive_history',
                                                             'sha256': 'ecde1c0640d4d78f09282e7037f473e28413236951aac1c7d57a1fa969abdebd'},
 'runtime/estimators/history/pre-dimension-binding-v1/__init__.py': {'bytes': 1179,
                                                                     'role': 'inactive_history',
                                                                     'sha256': '5e49d1a4c9a2dd803123aa6b2ff7f75d278ad3438656d2b8479dab6b6e9875b0'},
 'runtime/estimators/history/pre-dimension-binding-v1/_common.py': {'bytes': 8545,
                                                                    'role': 'inactive_history',
                                                                    'sha256': '980da934ce9c8be2906be35e366b031c7dcebeb1df581d6eb022af2358ada1a5'},
 'runtime/estimators/history/pre-dimension-binding-v1/svm.py': {'bytes': 17545,
                                                                'role': 'inactive_history',
                                                                'sha256': '53670fc3bd23278f1e4fa500337631fde3e29f71304acea32098334e13a02450'},
 'runtime/estimators/history/pre-dimension-binding-v1/trees.py': {'bytes': 14021,
                                                                  'role': 'inactive_history',
                                                                  'sha256': 'e8f7f8c7b681764b99988734adcc504a021dee393d81464069353f6984152d49'},
 'runtime/estimators/history/pre-gamma-type-v4/kernel_bank.py': {'bytes': 8446,
                                                                 'role': 'inactive_history',
                                                                 'sha256': '9ddd7c732e5898cff2d550ec2fda9442d76c1f569c5971e219473b84b90af2da'},
 'runtime/estimators/history/pre-gamma-type-v4/svm.py': {'bytes': 19915,
                                                         'role': 'inactive_history',
                                                         'sha256': 'db2eb08d2d786e7f92d3d74c0ab340e405c50a0ec2cf9673053532c2b9f0e16c'},
 'runtime/estimators/history/pre-kernel-bank-v3/__init__.py': {'bytes': 1179,
                                                               'role': 'inactive_history',
                                                               'sha256': 'fb4c8bfec01344dd6df2604a8504fc3dbf97c0c2ca0e14be54b8a2193da37ab9'},
 'runtime/estimators/history/pre-kernel-bank-v3/svm.py': {'bytes': 18902,
                                                          'role': 'inactive_history',
                                                          'sha256': '476a15b2913821b0b5a319dd53ba9c5f9d8ed0875fc9429e9df01f32753a0ffc'},
 'runtime/estimators/kernel_bank.py': {'bytes': 8669,
                                       'role': 'operative',
                                       'sha256': '24618d740de65757328e1c10ca42163bc9e88d8a1829ce458cf8fa9f69810438'},
 'runtime/estimators/svm.py': {'bytes': 20006,
                               'role': 'operative',
                               'sha256': '03b754047ec286885616e353eaec3b3efb56148134b78aa9c2eb4f0e48fd909f'},
 'runtime/estimators/trees.py': {'bytes': 14285,
                                 'role': 'operative',
                                 'sha256': '106435cceac58e5fce74442838e4c567322ff36f9eb094f6ebedf0e1a4daf802'},
 'runtime/private_store/__init__.py': {'bytes': 187,
                                       'role': 'operative',
                                       'sha256': '69eaf8288e70b955216260984bfa980b376f7e805913e104a091f892e400fb62'},
 'runtime/private_store/store.py': {'bytes': 18454,
                                    'role': 'operative',
                                    'sha256': '82148e6f95449336378c29bb116c5d1b82000c44ad613c923656dff699e158f5'},
 'runtime/process_guard/__init__.py': {'bytes': 234,
                                       'role': 'operative',
                                       'sha256': 'a8054352381cb8327d5814ee3739261ab48b7978690395d51f224652d850430b'},
 'runtime/process_guard/aggregate_v3.py': {'bytes': 38787,
                                           'role': 'operative',
                                           'sha256': 'ea4b2b6e5c0487fbb09663c872bc44c09c27213ae35d8f29500247b13257d1f4'},
 'runtime/process_guard/barrier_v2.py': {'bytes': 8985,
                                         'role': 'operative',
                                         'sha256': 'fe59253306353773ecfa1de917632b5b6e226e0653aeb852904e28f3a04d9259'},
 'runtime/process_guard/contracts.py': {'bytes': 9007,
                                        'role': 'operative',
                                        'sha256': '92e2ce46ad3d0d7b5b25c07cec2d1acf670d67cd0803bec0071c86d704e7b20f'},
 'runtime/process_guard/linux.py': {'bytes': 21676,
                                    'role': 'operative',
                                    'sha256': '3f1d6c53094ef6359c6f039bcbd45639c795e7e1b16cfe6854e7337546a91e35'},
 'runtime/process_guard/monitor_v3.py': {'bytes': 16323,
                                         'role': 'operative',
                                         'sha256': 'a04bb3444ec308ee819770e4d857a055a2a4c1e34a47689ebcb74e41e75eafcc'},
 'runtime/provider_transport/__init__.py': {'bytes': 203,
                                            'role': 'operative',
                                            'sha256': 'd5c1642ab41844a02899e0e3c446227da1bf50030167050000468e1b40c27bd3'},
 'runtime/provider_transport/cgroup_v2.py': {'bytes': 11404,
                                             'role': 'operative',
                                             'sha256': '8cac2fc60ec4289addee0ce7d344fd046049d3b0c1f1de73551ff56add2a6431'},
 'runtime/provider_transport/protocol.py': {'bytes': 12025,
                                            'role': 'operative',
                                            'sha256': '07b1d4ef9061c6bee881eb68814b4377372312623cfe228450467cb2612f74da'},
 'runtime/provider_transport/stdio.py': {'bytes': 18595,
                                         'role': 'operative',
                                         'sha256': 'a7cfd24daecb4d7f38678b89a65ba1e04b24a290d6c65584cea42a3394a20c28'},
 'runtime/public_models/__init__.py': {'bytes': 459,
                                       'role': 'operative',
                                       'sha256': '00e00447b2898d8746e4538a2902bd4fd505220440e2ee7c4c39cc1502800631'},
 'runtime/public_models/model.py': {'bytes': 20843,
                                    'role': 'operative',
                                    'sha256': '4afbaed143275e4adf44f865d03a0da4fc11230e1dcbb4f33ca7d4ac312812f5'},
 'runtime/runner/__init__.py': {'bytes': 57,
                                'role': 'operative',
                                'sha256': 'b1ed3fd3597b681ec2b3432e24ae0c0a0af900a106592d502ee139ef290bd9bd'},
 'runtime/runner/authority.py': {'bytes': 1303,
                                 'role': 'operative',
                                 'sha256': '3b1a00ceffb2d32bf443af7768b92f001367052595477b79016c371c05e7b547'},
 'runtime/runner/candidate.py': {'bytes': 21852,
                                 'role': 'operative',
                                 'sha256': '462b3aac08fe53b6b75785664a0c544059d40611eb92c290bea79d8dfb6e978c'},
 'runtime/runner/policy.py': {'bytes': 6903,
                              'role': 'operative',
                              'sha256': '1732f4c94b767fbf82076737f8a4b180a2fa2f31c7fcbdf2db547d0991a463e6'},
 'runtime/runner/preparation.py': {'bytes': 6433,
                                   'role': 'operative',
                                   'sha256': '45ecb27a56704803966327f7ba264c116c7602e2548d3766b23b97b0bfed03f1'},
 'runtime/runner/public_tools.py': {'bytes': 7747,
                                    'role': 'operative',
                                    'sha256': '76b3d9e8bbce450184f20b2f7e7b32c8708a0ab4845a7d2d0312e1bf9fe1be00'},
 'runtime/runner/public_transform.py': {'bytes': 2457,
                                        'role': 'operative',
                                        'sha256': 'e60029d88fca88fa0319ccbfb298cfb4ef6a9a8f66d0394a86bdfd6ba5ed50ae'},
 'runtime/runner/reference.py': {'bytes': 35180,
                                 'role': 'operative',
                                 'sha256': '8ab0a91622f51bb2bc822e5611d7e644cc2e5bee823210da9043ba2e319414dd'},
 'runtime/runner/reference_cli.py': {'bytes': 4224,
                                     'role': 'operative',
                                     'sha256': '0197f8a7af089316ac401664e165bbe4e7c11f6defdcfbcc2b9d46238d084a22'},
 'runtime/runner/runtime_api.py': {'bytes': 8406,
                                   'role': 'operative',
                                   'sha256': '1768fc478a882f13fc331d2f47f16f841e80860a89bbe9c3afade76ad8de0d1d'},
 'runtime/runner/runtime_binding.py': {'bytes': 5418,
                                       'role': 'operative',
                                       'sha256': '62dd86499ca177f0fea07bb155eadf47c10a52782f42a53d3c1a4d61882407a4'},
 'runtime/runner/study.py': {'bytes': 11218,
                             'role': 'operative',
                             'sha256': '901b0a9873857a9425420d9b6e6f148f3b97a86773d82f931356ddfdb5f89abe'},
 'runtime/runtime-metadata-successor-v1/NUMPY_API_CONTRACT.json': {'bytes': 4443,
                                                                   'role': 'static',
                                                                   'sha256': '9a52fe0480e0ac99f7b7f4f2e77e845ded9bee4d273f2cb5b1e21d45e3c40d85'},
 'runtime/runtime-metadata-successor-v2/NUMPY_API_CONTRACT.json': {'bytes': 4404,
                                                                   'role': 'static',
                                                                   'sha256': '4d299c47e4b4c71e25386466efecbacc6de2745ef021d3912ec5f8d0170a4b14'},
 'runtime/runtime-metadata-successor-v2/SELECTION_BINDING.json': {'bytes': 2288,
                                                                  'role': 'static',
                                                                  'sha256': '3391beff2ec024bf75f4fd1fed3dd3127c50d364ac11d4a88bdd1eb9dfc7ba0e'},
 'runtime/scoring/__init__.py': {'bytes': 614,
                                 'role': 'operative',
                                 'sha256': '047b6542c406bef42e56854272e679ba58ed12895bd60753c41bafc6fa489c73'},
 'runtime/scoring/comparison.py': {'bytes': 8403,
                                   'role': 'operative',
                                   'sha256': '01710a6dafb23d81cc74cff780fa3805fb11eae8bb08409f9934e371c6ff7fb0'},
 'runtime/scoring/core.py': {'bytes': 12825,
                             'role': 'operative',
                             'sha256': '574f41eae8c880fc6f1abbe32c6a55ee6ba7f7dff468c01a2da3b9e39c9c7490'},
 'runtime/scoring/parsing.py': {'bytes': 7117,
                                'role': 'operative',
                                'sha256': 'ca672c6af7c3088f7669dd389b5979f85a68c14bd22954eb787d3df7e687bfc2'},
 'runtime/scoring/selection.py': {'bytes': 7572,
                                  'role': 'operative',
                                  'sha256': 'f8277b47d398ee3128648952d087ab803cf8049620f4efaed31f3031645039e1'},
 'runtime/scoring/workload.py': {'bytes': 12058,
                                 'role': 'operative',
                                 'sha256': 'ba2ab8f31627ea6427b94387840d1632a0a1bd0497e4af76fe0d063dc8b27103'},
 'runtime/transforms/NUMPY_API_CONTRACT.json': {'bytes': 3966,
                                                'role': 'static',
                                                'sha256': '5e41efbf592c6dc45ede018e695f7c7d4fd8d7a5c5a8f6060fffe3e522f73813'},
 'runtime/transforms/__init__.py': {'bytes': 460,
                                    'role': 'operative',
                                    'sha256': '4a7ea8cbf96f2c6744a696df562909d74003172ab0b29d72fa003d10c37987cb'},
 'runtime/transforms/dependency.py': {'bytes': 1636,
                                      'role': 'operative',
                                      'sha256': '2a3bddaba23c7c96a083b4fbea3fbac246815e3647ab39ed97b208532cc87123'},
 'runtime/transforms/history/pre-cache-binding-v2/numeric.py': {'bytes': 32081,
                                                                'role': 'inactive_history',
                                                                'sha256': '044a88699fb011dde334c2265c20336efbf20e03c8697eaa842c4d8785c68d61'},
 'runtime/transforms/history/pre-hardening-v1/__init__.py': {'bytes': 460,
                                                             'role': 'inactive_history',
                                                             'sha256': '4a7ea8cbf96f2c6744a696df562909d74003172ab0b29d72fa003d10c37987cb'},
 'runtime/transforms/history/pre-hardening-v1/dependency.py': {'bytes': 1493,
                                                               'role': 'inactive_history',
                                                               'sha256': 'fd6169b5010a36b72f41ffc1d53b6b00c6e82d3b75bc5b727d29d7f642846cdd'},
 'runtime/transforms/history/pre-hardening-v1/numeric.py': {'bytes': 31315,
                                                            'role': 'inactive_history',
                                                            'sha256': '922f87669bd605211cfd1e12d695185e3d459598ea7c683d840a6f48da6fa440'},
 'runtime/transforms/numeric.py': {'bytes': 32544,
                                   'role': 'operative',
                                   'sha256': '68deb2bc97e1644f4d8590ed2bd98daf155e8df228e54f289614db45430a19f2'},
 'runtime/transforms/public_tools_v1/__init__.py': {'bytes': 195,
                                                    'role': 'operative',
                                                    'sha256': '20b0c716c85230ccc55a9d2cea5ae80cc89b6e765860a25263dc1b852fb9898d'},
 'runtime/transforms/public_tools_v1/projection.py': {'bytes': 13393,
                                                      'role': 'operative',
                                                      'sha256': 'cd8e5e25ba6b5757a2d225e7f6773be86bcc85d84d48ab97ca4636b631684b72'},
 'runtime/transforms/public_tools_v1/run_controls.py': {'bytes': 8127,
                                                        'role': 'engineering_only',
                                                        'sha256': 'ac54e9e5bfd11e8a79a3c46537ace574bd2af3d573ba3d13517d27ff9efe9201'}}
PARENT_ACCEPTANCE = {'bytes': 205507, 'sha256': 'af338c1d12ff5fea829e05a99f9bff9c841e36c191f4fe892b2722c2d2f148a4'}
SCOPE = {'contexts': 234, 'people': 13, 'person_protocol_cells': 300, 'protocols': 25, 'records': 9532, 'tools': 39}
CONTRACTS = ('constructor_allowlist', 'output_contract', 'policy_schema', 'deployment_schema', 'instructions', 'operator_instructions')
CANDIDATE_CAPS = {'model_calls': 512, 'input_tokens': 2097152, 'output_tokens': 131072, 'tool_calls': 10000, 'wall_ns': 172800000000000, 'cpu_ns': 2764800000000000, 'simultaneous_cores': 16, 'private_rss_bytes': 68719476736, 'writable_bytes': 549755813888, 'output_stream_bytes': 16777216, 'output_line_bytes': 8192, 'gpu_devices': 0}

CATALOGUE_METADATA = {'static/catalogue/PAGE_PINS.json': {'bytes': 3260,
                                     'sha256': '2ba089e7057097298df3cecf63fb6b63b024754bd03fc641079d829e6c38dba1'},
 'static/catalogue/SUPPORT.json': {'bytes': 57956,
                                   'sha256': '51339ee2c7bce1c4dd293b695a3ce68fd123b6f65e1f4ffde7dcb8bfc105169b'},
 'static/catalogue/page_00.json': {'bytes': 319478,
                                   'sha256': 'aa466b76f2843ac2d4c065a177280ed56bf24ac1a32ec7dace85c9f845d2f3d1'},
 'static/catalogue/page_01.json': {'bytes': 318901,
                                   'sha256': 'd9bd545bc143d33df50120a8906db43e6e2c998b2121c888b5be7c7a1f18ccd2'},
 'static/catalogue/page_02.json': {'bytes': 319631,
                                   'sha256': '1c298774a4ebc80fa6ca666b821e4a33d8bb535634bc12a0b9db1b038abdf11b'},
 'static/catalogue/page_03.json': {'bytes': 159584,
                                   'sha256': 'c83967e15ba1cddb24fc9e97b78237a3ed5e8a06e46b5c6554b8406ff2daecdf'},
 'static/catalogue/page_04.json': {'bytes': 159604,
                                   'sha256': 'cf7a8c1865624aaf13ec5f09f584e384c6411049b827caee417911dd1ef3faf1'},
 'static/catalogue/page_05.json': {'bytes': 159818,
                                   'sha256': 'acea3600afb1708e709b47ed8f8ac03fd77f20541aef6ff8d4240a3b9b678a13'},
 'static/catalogue/page_06.json': {'bytes': 160368,
                                   'sha256': '40ff6aa7f5e93d001cef665da6606fefbe11277d584f472c04dd3574db480ce7'},
 'static/catalogue/page_07.json': {'bytes': 319205,
                                   'sha256': '395055c109d38469817daeb48014827c55ab0c251e1a4e773847a6a666e9d0f3'},
 'static/catalogue/page_08.json': {'bytes': 319037,
                                   'sha256': 'a86921f22b8ec1904a6a8aa37f90446270f39a06252b488274e7b70616339b31'},
 'static/catalogue/page_09.json': {'bytes': 314439,
                                   'sha256': '7e6de190adb87eada1e808ce4f59f7ae5633f3ffd6028d6907485b584009acc2'},
 'static/catalogue/page_10.json': {'bytes': 308713,
                                   'sha256': '50cb548ea7445df63959289a224bb1d8acdb70429a6674f84849742464667859'},
 'static/catalogue/page_11.json': {'bytes': 163467,
                                   'sha256': '5c511efbbf0e3354c0fe55f9084c48689daf3ad9156e60864ef6915c4913160e'}}

ARTIFACTS = {'A': 'PARENT_CLOSURE.json', 'B': 'CODE_CLOSURE.json',
             'T': 'TASK.json', 'D': 'DEPLOYMENT.json', 'F': 'SOURCE_FREEZE.json'}
ROLES = frozenset(('operative', 'static', 'engineering_only', 'inactive_history'))
REQUIRED_SOURCE = frozenset(('__init__.py', 'declaration.py', 'constructors.py', 'run.py',
                             'corpus.py', 'orchestrator.py', 'authority.py', 'evidence.py',
                             'observe.py', 'grade.py', 'registration.py', 'integrated_study.py'))


def _manifest(files, *, roles):
    _need(type(files) is dict and 1 <= len(files) <= 512, 'bounded source file dictionary')
    _need(list(files) == sorted(files), 'source member keys must be sorted')
    total = 0
    for path, pin in files.items():
        relative_path(path)
        _keys(pin, ('bytes', 'sha256', 'role') if roles else ('bytes', 'sha256'), 'source member pin')
        _pin({k: pin[k] for k in ('bytes', 'sha256')}, path_allowed=False)
        total += pin['bytes']
        if roles:
            _need(pin['role'] in ROLES, 'unknown source member role')
            if 'history' in path.split('/'):
                _need(pin['role'] == 'inactive_history', 'history can never be operative')
            elif pin['role'] == 'inactive_history':
                raise DeclarationError('inactive history role lacks literal history path')
    _need(total <= 64*1024*1024, 'source closure aggregate exceeds central64MiB')
    return total


def _named_pin(value, path, actual):
    _keys(value, ('path', 'bytes', 'sha256'), 'named artifact pin')
    _pin(value, max_bytes=2*1024*1024)
    _need(value == {'path': path, **actual}, 'artifact dependency pin mismatch: ' + path)


def _namespace(root, expected):
    """Bounded source-name census; never follow links or open an unlisted body."""
    held = []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        held.append(fd)
        for name in root.parts[1:]:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            held.append(fd)
        found = set()
        directories = [0]
        def visit(directory_fd, prefix, depth):
            _need(depth <= 32, 'source namespace depth')
            directories[0] += 1
            _need(directories[0] <= 512, 'source namespace directory bound')
            before = _stamp(os.fstat(directory_fd))
            with os.scandir(directory_fd) as entries:
                names = []
                for entry in entries:
                    names.append(entry.name)
                    _need(len(names) <= 512, 'source directory member bound')
            for name in sorted(names):
                relative = prefix + name
                relative_path(relative)
                st = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    _need(any(x.startswith(relative + '/') for x in expected), 'unlisted source directory')
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                    try:
                        _need(_stamp(os.fstat(child)) == _stamp(st), 'source directory raced')
                        visit(child, relative + '/', depth + 1)
                        _need(_stamp(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)) == _stamp(st),
                              'source directory replacement')
                    finally:
                        os.close(child)
                else:
                    _need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1,
                          'source namespace contains link/device/nonregular member')
                    _need(relative in expected or relative == 'SOURCE_PROPOSAL.json',
                          'unlisted source package member: ' + relative)
                    found.add(relative)
            _need(_stamp(os.fstat(directory_fd)) == before, 'source namespace changed')
        visit(fd, '', 0)
        _need(found - {'SOURCE_PROPOSAL.json'} == set(expected), 'incomplete source namespace')
    finally:
        errors = []
        for fd in reversed(held):
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup('source census close errors', errors)


def _history_import_check(relative, raw, role):
    if role != 'operative' or not relative.endswith('.py'):
        return
    try:
        tree = ast.parse(raw, filename=relative)
    except (SyntaxError, ValueError, RecursionError) as error:
        raise DeclarationError('invalid operative source syntax: ' + relative) from error
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [x.name for x in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '', *(x.name for x in node.names)]
        else:
            continue
        _need(not any('history' in n.split('.') for n in names), 'operative history import denied')


def load_package(task_root, *, read_cap):
    """Verify complete A/B/T/D/F identities at an explicitly selected source root.

    F itself is returned with its raw pin for the independent outer selection;
    this function does not manufacture a trust anchor from an unkeyed manifest.
    External L bodies, keys, neural arrays, models and native binaries are never
    read. A root relocation strips only F's exact declared package prefix.
    """
    root = _absolute(task_root)
    ledger = ReadLedger(read_cap)
    docs, raw, pins = {}, {}, {}
    raw['F'] = _safe_read(root / ARTIFACTS['F'], None, limit=2*1024*1024, ledger=ledger)
    docs['F'] = _parse(raw['F'])
    F = _keys(docs['F'], ('schema', 'package_prefix', 'files'), 'final source freeze')
    _need(F['schema'] == 'n073_final_source_freeze_v1', 'final source freeze schema')
    prefix = relative_path(F['package_prefix'])
    _manifest(F['files'], roles=False)
    local = {}
    for key, pin in F['files'].items():
        _need(key.startswith(prefix + '/'), 'foreign final-freeze prefix')
        suffix = relative_path(key[len(prefix)+1:])
        _need(suffix not in local and suffix not in ('SOURCE_FREEZE.json', 'SOURCE_PROPOSAL.json'),
              'self/descendant/duplicate final-freeze member')
        local[suffix] = pin
    for letter in ('A', 'B', 'T', 'D'):
        name = ARTIFACTS[letter]
        _need(name in local, 'missing required artifact: ' + letter)
        docs[letter], raw[letter] = read_json_pinned(root / name, local[name],
                                                  limit=2*1024*1024, ledger=ledger)
    for letter in ARTIFACTS:
        _need(canonical_file_bytes(docs[letter]) == raw[letter], 'noncanonical new artifact: ' + letter)
        pins[letter] = {'path': ARTIFACTS[letter], **_raw_pin(raw[letter])}
    A = _keys(docs['A'], ('schema', 'acceptance', 'files'), 'parent source closure')
    _pin(A['acceptance'], path_allowed=False)
    _need(A['schema'] == 'n073_parent_closure_v1' and A['acceptance'] == PARENT_ACCEPTANCE,
          'wrong accepted parent closure identity')
    _manifest(A['files'], roles=True)
    _need(A['files'] == ACCEPTED_PARENT, 'all89 exact accepted parent members/roles required')
    B = _keys(docs['B'], ('schema', 'parent_closure', 'files'), 'code closure')
    _need(B['schema'] == 'n073_code_closure_v1', 'code closure schema')
    _named_pin(B['parent_closure'], ARTIFACTS['A'], _raw_pin(raw['A']))
    _manifest(B['files'], roles=True)
    _need(not set(B['files']).intersection((*ARTIFACTS.values(), 'SOURCE_PROPOSAL.json')),
          'code closure includes self/downstream artifact')
    _need(REQUIRED_SOURCE <= set(B['files']), 'complete task-local source layer required')
    for path, descriptor in B['files'].items():
        if path.endswith('.py') and path not in ACCEPTED_PARENT:
            _need(descriptor['role'] == 'operative', 'new Python source must be operative, not hidden as static')
    for path, pin in ACCEPTED_PARENT.items():
        _need(B['files'].get(path) == pin, 'parent/code closure member mismatch')
    for path, pin in CATALOGUE_METADATA.items():
        _need(B['files'].get(path) == {**pin, 'role': 'static'}, 'exact full catalogue metadata closure required')
    T = _keys(docs['T'], ('schema', 'candidate_id', 'parent_closure', 'code_closure',
                           'scope', 'contracts', 'candidate_caps'), 'task declaration')
    _need(T['schema'] == 'n073_full_task_v1' and T['candidate_id'] == 'NEURAL-073', 'task identity')
    _named_pin(T['parent_closure'], ARTIFACTS['A'], _raw_pin(raw['A']))
    _named_pin(T['code_closure'], ARTIFACTS['B'], _raw_pin(raw['B']))
    _need(T['scope'] == SCOPE and all(type(x) is int for x in T['scope'].values()), 'full task scope')
    _need(T['candidate_caps'] == CANDIDATE_CAPS and
          all(type(x) is int for x in T['candidate_caps'].values()), 'fixed full candidate caps')
    _keys(T['contracts'], CONTRACTS, 'task static contract references')
    contract_paths = set()
    for value in T['contracts'].values():
        _keys(value, ('path', 'bytes', 'sha256'), 'task contract pin')
        relative_path(value['path'])
        _pin(value)
        _need(value['path'] not in contract_paths, 'aliased semantic contract paths')
        contract_paths.add(value['path'])
        _need(B['files'].get(value['path']) == {k: value[k] for k in ('bytes', 'sha256')} | {'role': 'static'},
              'task contract absent from static code closure')
    _need({k: T['contracts']['constructor_allowlist'][k] for k in ('bytes', 'sha256')} == ACTIVE_CONSTRUCTOR_CONTRACT_PIN,
          'exact operative26plus6 constructor contract required')
    D = validate_deployment(docs['D'])
    for name, letter in (('accepted_parent_closure_digest', 'A'), ('code_closure_digest', 'B'),
                         ('task_design_digest', 'T')):
        _need(D[name] == pins[letter]['sha256'], 'deployment upstream identity mismatch')
    expected = {path: {k: value[k] for k in ('bytes', 'sha256')} for path, value in B['files'].items()}
    expected.update({ARTIFACTS[k]: _raw_pin(raw[k]) for k in ('A', 'B', 'T', 'D')})
    _need(local == expected, 'final freeze is not exact B+A+B+T+D closure')
    _namespace(root, set(expected) | {'SOURCE_FREEZE.json'})
    for relative, descriptor in B['files'].items():
        body = _safe_read(root / relative, {k: descriptor[k] for k in ('bytes', 'sha256')},
                          limit=16*1024*1024, ledger=ledger)
        _history_import_check(relative, body, descriptor['role'])
    _namespace(root, set(expected) | {'SOURCE_FREEZE.json'})
    return {'root': root, **docs, 'pins': pins, 'ledger': ledger,
            'read_bytes': ledger.reserved_bytes, 'package_prefix': prefix}

# The fixed semantic constructor contract is a static upstream leaf, not a runtime callback.
ACTIVE_CONSTRUCTOR_CONTRACT_PIN = {'bytes': 13032, 'sha256': '6bd537fef83f02df1ed269eaf8de66328716bd8bbfaf4534570dcbd4de2e612e'}
