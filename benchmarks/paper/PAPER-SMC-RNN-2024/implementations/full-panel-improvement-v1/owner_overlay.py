"""Materialize an authenticated two-phase owner overlay; never execute it.

The public repository retains one copy of every unchanged owner primitive.
Only the explicitly pinned legacy adapter changes in this operational copy.
"""
from pathlib import Path
import hashlib
import json
import os
import stat

HERE = Path(__file__).resolve().parent
OWNER_REL = Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-owner-v1')
OWNER_SOURCE = {'bytes': 7569, 'sha256': '44026e04ca813e3a22a893b848c2249d642559c49d75d76e3173fa1966e27a86'}
ADAPTER_PIN = {'bytes': 2637, 'sha256': '472a06c537f86c5b4e3f01cfa38f801262707692c639f6860bd6309b6327b7fd'}
FACADE_PIN = {'bytes': 41057, 'sha256': '7becc1746b068699070bc28f16286246427233e1a0082274b01a6ad75bcf8c3a'}
OWNER_FILES = {'common.py', 'legacy.py', 'cli_custody.py', 'journal.py', 'process_owner.py',
               'group_bootstrap.py', 'trusted_controller.py', 'owned_episode.py', 'controller.py',
               'runner.py', 'cgroup.py'}


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def source(path, expected):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('No linked source paths')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= 1024**2:
            raise ValueError('Bounded ordinary single-copy source')
        raw = stream.read(1024**2 + 1)
        after, named = os.fstat(stream.fileno()), path.lstat()
    keys = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, k) != getattr(after, k) or getattr(after, k) != getattr(named, k) for k in keys):
        raise ValueError('Stable source snapshot')
    if expected is not None and pin(raw) != expected:
        raise ValueError('Fixed reviewed source identity')
    return raw


def build_overlay(repository_root, output, *, max_bytes):
    if ADAPTER_PIN is None or FACADE_PIN is None:
        raise ValueError('Reviewed composition not sealed')
    repository_root, output = Path(repository_root).absolute(), Path(output).absolute()
    if ('..' in repository_root.parts or '..' in output.parts
            or any(p.is_symlink() for p in (repository_root, *repository_root.parents, output, *output.parents))):
        raise ValueError('Canonical unlinked source and output paths')
    repository_root = repository_root.resolve(strict=True)
    output = output.parent.resolve(strict=True) / output.name
    if (type(max_bytes) is not int or max_bytes <= 0 or output.exists() or not output.parent.is_dir()
            or output.is_relative_to(repository_root) or repository_root.is_relative_to(output)
            or any(p.is_symlink() for p in (output, *output.parents))):
        raise ValueError('Fresh disjoint external overlay and finite byte cap')
    original = repository_root / OWNER_REL
    manifest = json.loads(source(original / 'SOURCE.json', OWNER_SOURCE))
    if manifest['schema'] != 'smc_aggregate_owner_source_v1' or set(manifest['files']) != OWNER_FILES:
        raise ValueError('Exact retained owner closure')
    bodies = {name: source(original / name, expected) for name, expected in manifest['files'].items()}
    bodies['legacy.py'] = source(HERE / 'owner_legacy.py', ADAPTER_PIN)
    source(HERE / 'full_panel_episode.py', FACADE_PIN)
    component_raw = source(HERE / 'RUNTIME_SOURCE.json', None)
    component = json.loads(component_raw)
    if (component['schema'] != 'smc_full_panel_runtime_source_v1'
            or component['route'] != 'smc_full_panel_aggregate_v1'
            or set(component['files']) != {'full_panel_episode.py', 'full_panel_worker.py', 'owner_overlay.py',
                'owner_legacy.py', 'RUNTIME_BINDING.json', 'MATERIAL_BINDING.json', 'DEPLOYMENT_BINDING.json'}):
        raise ValueError('New explicit runtime source manifest')
    for name, expected in component['files'].items():
        if '/' in name or name in ('.', '..'):
            raise ValueError('Fixed local component source member')
        source(HERE / name, expected)
    if component['files'].get('owner_legacy.py') != ADAPTER_PIN or component['files'].get('full_panel_episode.py') != FACADE_PIN:
        raise ValueError('Runtime manifest cannot select another adapter or facade')
    composition = {'schema': 'smc_full_panel_owner_composition_v1', 'repository_root': str(repository_root),
        'component_root': str(HERE), 'component_source': pin(component_raw), 'episode': FACADE_PIN,
        'retained_owner_source': OWNER_SOURCE}
    bodies['COMPOSITION.json'] = encode(composition)
    final_manifest = {'schema': 'smc_full_panel_owner_overlay_v1',
        'files': {name: pin(raw) for name, raw in sorted(bodies.items())},
        'retained_owner_source': OWNER_SOURCE, 'component_source': pin(component_raw)}
    bodies['SOURCE.json'] = encode(final_manifest)
    total = sum(len(raw) for raw in bodies.values())
    if total > max_bytes:
        raise ValueError('Complete overlay precharged before writing')
    folder = output / OWNER_REL
    folder.mkdir(parents=True, mode=0o700)
    for name, raw in sorted(bodies.items()):
        fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    return {'schema': 'smc_full_panel_owner_overlay_materialization_v1', 'source': pin(bodies['SOURCE.json']),
        'path': str(folder), 'files': len(bodies), 'bytes': total, 'unchanged_owner_primitives': sorted(OWNER_FILES - {'legacy.py'}),
        'adapter': ADAPTER_PIN, 'facade': FACADE_PIN, 'component_source': pin(component_raw),
        'execution_performed': False, 'native_runtime_qualified': False,
        'pre_test_authoring_isolation_verified': False}
