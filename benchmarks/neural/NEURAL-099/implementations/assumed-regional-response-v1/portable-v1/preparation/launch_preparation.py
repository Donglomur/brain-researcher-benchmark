"""Authenticate the input binding and execute its exact verified coordinator bytes.

The root separately authenticates this launcher and admits any actual data run.
No native libraries, HDF5 objects, or subprocesses are opened by this launcher.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re


class LaunchError(ValueError):
    pass


PROFILE = {'source_files':26,'source_trial_rows':5238,'region_cells':49,
           'eligible_clusters':1387,'unassigned_clusters':666,'source_events':1224589,
           'source_units':2053,'source_hash_bytes':455615424,'case_count':9867}


def _relative(path):
    if (type(path) is not str or not path or len(path) > 4096 or '\x00' in path
            or '\\' in path or PurePosixPath(path).is_absolute()
            or str(PurePosixPath(path)) != path or path == '.'):
        raise LaunchError('Expected a canonical binding-relative file locator')
    return path


def _verified_bytes(path, size, digest):
    if type(size) is not int or not 0 < size <= 65536:
        raise LaunchError('Expected an explicitly bounded source size <=64KiB')
    if type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise LaunchError('Expected a lowercase SHA-256 digest')
    with Path(path).open('rb') as handle:
        body = handle.read(size + 1)
    if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
        raise LaunchError('Source size or SHA-256 mismatch: ' + str(path))
    return body


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise LaunchError('Duplicate binding JSON key')
        value[key] = item
    return value


def launch(binding_path, binding_bytes, binding_sha256):
    raw_binding = _verified_bytes(binding_path, binding_bytes, binding_sha256)
    def nonfinite(value):
        raise LaunchError('Nonfinite binding JSON value')
    def number(value):
        result=float(value)
        if not math.isfinite(result):nonfinite(value)
        return result
    binding = json.loads(raw_binding, object_pairs_hook=_unique_pairs, parse_constant=nonfinite,parse_float=number)
    if (type(binding) is not dict
            or set(binding) != {'schema','profile','coordinator','modules','inputs'}
            or binding['schema'] != 'neural099-portable-preparation-binding/v1'
            or type(binding['coordinator']) is not dict
            or type(binding['inputs']) is not dict
            or set(binding['inputs']) != {'schema','timing','support','cohort','protocol'}
            or type(binding['modules']) is not dict
            or set(binding['modules']) != {'runtime_io','event_source','stream_counts','count_oracle','count_packet'}):
        raise LaunchError('Exact versioned portable preparation binding required')
    if (type(binding['profile']) is not dict or set(binding['profile']) != set(PROFILE)
            or any(type(binding['profile'][key]) is not int or binding['profile'][key] != value
                   for key,value in PROFILE.items())):
        raise LaunchError('Unselected complete-source profile')
    pins = [(binding['coordinator'],65536,True)]
    pins += [(value,65536,False) for value in binding['modules'].values()]
    pins += [(value,4194304,True) for value in binding['inputs'].values()]
    for pin,maximum,has_path in pins:
        fields = {'path','bytes','sha256'} if has_path else {'bytes','sha256'}
        if (type(pin) is not dict or set(pin) != fields
                or type(pin['bytes']) is not int or not 0 < pin['bytes'] <= maximum
                or type(pin['sha256']) is not str or re.fullmatch(r'[0-9a-f]{64}',pin['sha256']) is None):
            raise LaunchError('Invalid bounded source/metadata pin or location override')
        if has_path: _relative(pin['path'])
    entry = binding['coordinator']
    if set(entry) != {'path', 'bytes', 'sha256'}:
        raise LaunchError('Coordinator entry requires exact path, bytes, and SHA-256')
    path = entry['path']
    _relative(path)
    path = str((Path(binding_path).resolve().parent / path).resolve())
    source = _verified_bytes(path, entry['bytes'], entry['sha256'])
    namespace = {'__file__': path, '__name__': '__main__',
                 '__package__': None, '__cached__': None, '__spec__': None}
    # Compile the exact immutable bytes authenticated above, without reopening.
    # sys.argv is deliberately untouched for the coordinator's own parser.
    exec(compile(source, path, 'exec'), namespace)
    return namespace


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--binding', required=True)
    parser.add_argument('--binding-bytes', required=True, type=int)
    parser.add_argument('--binding-sha256', required=True)
    args, _ = parser.parse_known_args()
    return launch(args.binding, args.binding_bytes, args.binding_sha256)


if __name__ == '__main__':
    main()
