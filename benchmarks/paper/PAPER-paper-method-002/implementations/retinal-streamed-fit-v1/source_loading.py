"""Portable, bounded source and input checks. No scientific modules at import."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys
import sysconfig
import types
import zipfile

ARRAY_NAMES = frozenset(('images', 'currents', 'mask', 'train_targets', 'val_targets'))
META_FIELDS = frozenset(('schema', 'cell_id', 'identity_sha256', 'sites', 'splits', 'site_comps',
                         'connections', 'arrays', 'test_targets_included', 'validation_access', 'source_preprocessing'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON token')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def ordinary_file(path, maximum):
    path = Path(path)
    require(path.is_absolute(), 'explicit absolute file path')
    for ancestor in (path, *path.parents):
        st = os.lstat(ancestor)
        require(not stat.S_ISLNK(st.st_mode), 'no symlink input or source ancestry')
    st = os.stat(path)
    require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and 0 < st.st_size <= maximum,
            'bounded ordinary single-link file')
    return st


def read_json(path, maximum):
    before = ordinary_file(path, maximum)
    raw = Path(path).read_bytes()
    after = os.stat(path)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'stable metadata file')
    return strict_json(raw)


def authenticate_file(path, descriptor, maximum):
    require(type(descriptor) is dict and set(descriptor) == {'bytes', 'sha256'}, 'exact file descriptor')
    require(type(descriptor['bytes']) is int and 0 < descriptor['bytes'] <= maximum and
            type(descriptor['sha256']) is str and len(descriptor['sha256']) == 64, 'bounded descriptor')
    before = ordinary_file(path, maximum)
    require(before.st_size == descriptor['bytes'], 'file extent pin')
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        opened = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'stable open identity')
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
        closed = os.fstat(handle.fileno())
    after = os.stat(path)
    identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    require(identity(before) == identity(opened) == identity(closed) == identity(after), 'stable authenticated body')
    require(digest.hexdigest() == descriptor['sha256'], 'file digest pin')


def packet_preflight(array_path, metadata_path):
    """Reject forbidden archive members BEFORE any member's bytes are loaded."""
    metadata = read_json(metadata_path, 2 * 1024**2)
    require(type(metadata) is dict and set(metadata) == META_FIELDS, 'exact source metadata fields')
    require(metadata['test_targets_included'] is False, 'private TEST targets excluded')
    require(type(metadata['arrays']) is dict and set(metadata['arrays']) == ARRAY_NAMES,
            'only TRAIN and VAL target arrays')
    ordinary_file(array_path, 3 * 1024**3 + 1024**2)
    with zipfile.ZipFile(array_path, 'r') as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        require(len(names) == 5 and len(set(names)) == 5 and
                set(names) == {name + '.npy' for name in ARRAY_NAMES},
                'exact unique NPZ members; no TEST targets')
        require(all(not member.is_dir() and not member.flag_bits & 1 and member.file_size > 0 for member in members),
                'plain unencrypted numeric member descriptors')
        require(sum(member.file_size for member in members) <= 3 * 1024**3 + 65536,
                'bounded decompressed numeric member extent')
    return metadata


def input_paths(manifest_path):
    manifest = read_json(manifest_path, 16384)
    require(type(manifest) is dict and set(manifest) == {'schema', 'files'} and
            manifest['schema'] == 'jaxley-streamed-fit-input-files-v1', 'input file-manifest schema')
    expected = {'model_arrays.npz', 'model_metadata.json', 'morphologies/20161028_1.swc'}
    require(type(manifest['files']) is dict and set(manifest['files']) == expected, 'exact fit input file set')
    root = Path(manifest_path).parent
    limits = {'model_arrays.npz': 3 * 1024**3 + 1024**2, 'model_metadata.json': 2 * 1024**2,
              'morphologies/20161028_1.swc': 16 * 1024**2}
    # Inspect metadata and ZIP names before streaming the original packet body.
    packet_preflight(root / 'model_arrays.npz', root / 'model_metadata.json')
    for name in sorted(expected):
        authenticate_file(root / name, manifest['files'][name], limits[name])
    return root, manifest


def runtime_requirements(component):
    authenticate_file(component / 'RUNTIME_REQUIREMENTS.v1.json', {'bytes': 5991, 'sha256': '57c563bebf6b761493b57f372591e150b6620227397f1d3249d6341b86134a61'}, 32768)
    requirements = read_json(component / 'RUNTIME_REQUIREMENTS.v1.json', 32768)
    require(platform.python_version() == requirements['python'] and platform.system() == requirements['system'] and
            platform.machine() == requirements['machine'], 'frozen scientific Python/platform profile')
    for name, version in requirements['distributions'].items():
        require(importlib.metadata.version(name) == version, 'frozen distribution version: ' + name)
    purelib = Path(sysconfig.get_path('purelib'))
    for item in requirements['installed_sources']:
        path = Path(item['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'relative installed source member')
        authenticate_file(purelib / path, {'bytes': item['bytes'], 'sha256': item['sha256']}, 1024**2)
    for key, value in requirements['thread_environment'].items():
        os.environ[key] = value
    return requirements


def load_frozen_sources(component):
    """Authenticate immutable component-relative definitions before loading them."""
    authenticate_file(component / 'FROZEN_PINS.v1.json', {'bytes': 944, 'sha256': '604cf7448b81c9092dc73861b95215efba5385066c21e505e9f0590fc9262f67'}, 32768)
    pins = read_json(component / 'FROZEN_PINS.v1.json', 16384)
    expected = {'fixed_coordinate_policy.py', 'context_codec.py', 'model_operation.py',
                'comparison_streamed_batch.py', 'author_model_utils.py', 'author_simulate.py', 'author_transforms.py'}
    require(set(pins) == expected, 'exact frozen source member set')
    bodies = {}
    for name in sorted(expected):
        path = component / 'frozen' / name
        authenticate_file(path, pins[name], 65536)
        raw = path.read_bytes()
        require(len(raw) == pins[name]['bytes'] and hashlib.sha256(raw).hexdigest() == pins[name]['sha256'],
                'loaded source equals authenticated source')
        bodies[name] = raw
    # Definitions are loaded under the names used by the unchanged author sources.
    # Refuse collisions; never silently replace a pre-imported scientific module.
    order = ('fixed_coordinate_policy', 'context_codec', 'model_operation', 'comparison_streamed_batch',
             'author_model_utils', 'author_simulate', 'author_transforms')
    for name in order:
        require(name not in sys.modules, 'frozen module name already occupied: ' + name)
        if name == 'author_model_utils':
            sys.modules['model_operation'].configure_model_runtime()
        path = component / 'frozen' / (name + '.py')
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        try:
            exec(compile(bodies[name + '.py'], str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules['model_operation']
