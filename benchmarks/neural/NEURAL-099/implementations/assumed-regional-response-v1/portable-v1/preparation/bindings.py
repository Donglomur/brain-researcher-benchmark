"""Metadata-only portable binding factory; never imported by native preparation.

The release bootstrap authenticates this authoring helper separately. Runtime
launcher/coordinator validation does not execute this helper. Relative paths are
locators, not containment promises: '..' is allowed for operator-local metadata.
Moving a binding requires preserving the relative layout of all referenced files.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

SCHEMA = 'neural099-portable-preparation-binding/v1'
MODULES = ('runtime_io', 'event_source', 'stream_counts', 'count_oracle', 'count_packet')
INPUTS = ('schema', 'timing', 'support', 'cohort', 'protocol')
PROFILE = {'source_files':26,'source_trial_rows':5238,'region_cells':49,
           'eligible_clusters':1387,'unassigned_clusters':666,'source_events':1224589,
           'source_units':2053,'source_hash_bytes':455615424,'case_count':9867}
MAX_SOURCE_BYTES = 65536
MAX_METADATA_BYTES = 4194304
CONTRACT_PINS = {
    'support': {'bytes':69757,'sha256':'35a59c971f015b2b58d923098be21ff208fd889e7fbbe7dd6af233afa38b5e8b'},
    'cohort': {'bytes':11197,'sha256':'87f7087dce132a08d4edbc89ab0f982f0672c2bc8f89e29fd2ee40fda5e575eb'},
    'protocol': {'bytes':3365,'sha256':'9d76c4d149b2a99c2609225d511c720607f77f547d3b3aae0cfe50dd2fe71a7a'},
}

def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate binding/metadata JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite binding/metadata JSON value')
    def number(value):
        result=float(value)
        if not math.isfinite(result):nonfinite(value)
        return result
    return json.loads(body, object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=number)

def relative_path(value):
    if (type(value) is not str or not value or len(value) > 4096 or '\x00' in value
            or '\\' in value or PurePosixPath(value).is_absolute()
            or str(PurePosixPath(value)) != value or value == '.'):
        raise ValueError('Expected a canonical relative POSIX file locator')
    return value

def resolve_path(binding_path, locator):
    return (Path(binding_path).resolve().parent / relative_path(locator)).resolve()

def validate_binding(value):
    if type(value) is not dict or set(value) != {'schema','profile','coordinator','modules','inputs'}:
        raise ValueError('Exact portable binding fields required')
    if value['schema'] != SCHEMA:
        raise ValueError('Unsupported portable binding version')
    if (type(value['profile']) is not dict or set(value['profile']) != set(PROFILE)
            or any(type(value['profile'][key]) is not int or value['profile'][key] != expected
                   for key, expected in PROFILE.items())):
        raise ValueError('Unselected complete-source profile')
    if type(value['modules']) is not dict or set(value['modules']) != set(MODULES):
        raise ValueError('Exact sibling source-module roles required')
    if type(value['inputs']) is not dict or set(value['inputs']) != set(INPUTS):
        raise ValueError('Exact five scientific metadata inputs required')
    entries = [(value['coordinator'], MAX_SOURCE_BYTES, True)]
    entries += [(entry, MAX_SOURCE_BYTES, False) for entry in value['modules'].values()]
    entries += [(entry, MAX_METADATA_BYTES, True) for entry in value['inputs'].values()]
    for entry, maximum, has_path in entries:
        fields = {'bytes','sha256','path'} if has_path else {'bytes','sha256'}
        if type(entry) is not dict or set(entry) != fields:
            raise ValueError('Unexpected pin fields or source-location override')
        if type(entry['bytes']) is not int or not 0 < entry['bytes'] <= maximum:
            raise ValueError('Invalid bounded source/metadata size')
        digest = entry['sha256']
        if (type(digest) is not str or len(digest) != 64
                or any(character not in '0123456789abcdef' for character in digest)):
            raise ValueError('Invalid SHA-256 pin')
        if has_path:
            relative_path(entry['path'])
    for role, expected in CONTRACT_PINS.items():
        if {key:value['inputs'][role][key] for key in ('bytes','sha256')} != expected:
            raise ValueError('Scientific input differs from the selected published contract: '+role)
    return deepcopy(value)

def _pin(path, maximum, *, metadata=False):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
            raise ValueError('Expected a bounded nonempty regular source/metadata file')
        parts, total = [], 0
        while True:
            part = os.read(fd, min(65536, maximum + 1 - total))
            if not part:
                break
            parts.append(part); total += len(part)
            if total > maximum:
                raise ValueError('Source/metadata file exceeded its bound')
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if total != before.st_size or signature(before) != signature(after):
            raise ValueError('Source/metadata file changed while pinning')
        body = b''.join(parts)
    finally:
        os.close(fd)
    if metadata:
        if type(strict_json(body)) is not dict:
            raise ValueError('Scientific metadata must be a JSON object')
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def create_binding(package_root, schema_path, timing_path, *, binding_path):
    """Return a binding without writing it or opening NWB/count/case payloads.

    binding_path is the actual intended output location, not the working
    directory. The owner writes that new artifact and pins it separately.
    Only metadata and the coordinator plus five sibling source files are read.
    """
    root = Path(package_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Package root must be a directory')
    base = Path(binding_path).resolve().parent
    def entry(path, *, source=False):
        path = Path(path).absolute()
        path = path.parent.resolve() / path.name
        pin = _pin(path, MAX_SOURCE_BYTES if source else MAX_METADATA_BYTES, metadata=not source)
        return {'path':relative_path(Path(os.path.relpath(path, base)).as_posix()), **pin}
    prep, contract = root/'preparation', root/'contract'
    value = {
        'schema':SCHEMA,'profile':dict(PROFILE),
        'coordinator':entry(prep/'prepare_counts.py',source=True),
        'modules':{name:_pin(prep/(name+'.py'),MAX_SOURCE_BYTES) for name in MODULES},
        'inputs':{
            'schema':entry(schema_path), 'timing':entry(timing_path),
            'support':entry(contract/'DECLARED_SUPPORT.json'),
            'cohort':entry(contract/'COHORT_BINDING.json'),
            'protocol':entry(contract/'PROTOCOL.json'),
        },
    }
    return validate_binding(value)
