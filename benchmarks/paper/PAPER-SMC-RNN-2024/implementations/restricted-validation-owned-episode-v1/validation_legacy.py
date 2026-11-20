"""Load the explicitly derived one-phase assisted VALID owner facade.

Installed only as legacy.py in a fresh source-authenticated private overlay.
No private target is exposed by this loader, and no module is monkeypatched.
"""
import importlib.util
from pathlib import Path
import sys
from common import HERE, body, descriptor, need, pin, read

COMPOSITION = read(HERE / 'COMPOSITION.json')
need(type(COMPOSITION) is dict and set(COMPOSITION) == {'schema', 'repository_root', 'component_root',
     'component_source', 'episode', 'retained_owner_source'}
     and COMPOSITION['schema'] == 'smc_validation_owned_owner_composition_v1', 'Explicit reference owner source')
LEGACY_SOURCE = descriptor(COMPOSITION['component_source'])
LEGACY_EPISODE = descriptor(COMPOSITION['episode'])
_legacy = None


def _component():
    root = Path(COMPOSITION['component_root'])
    manifest = read(root / 'SOURCE.json', LEGACY_SOURCE)
    need(manifest.get('schema') == 'smc_validation_owned_component_v1'
         and type(manifest.get('files')) is dict and len(manifest['files']) <= 128
         and manifest['files'].get('validation_episode.py') == LEGACY_EPISODE,
         'Source-selected reference component and episode')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        need(type(name) is str and not relative.is_absolute() and '..' not in relative.parts
             and str(relative) == name and name not in ('', '.', 'SOURCE.json'), 'Closed relative source member')
        body(root / relative, descriptor(expected), cap=1024**2)
    return root, manifest


def _module(name, path, expected, *, register=False):
    raw = body(path, descriptor(expected), cap=1024**2)
    if register and name in sys.modules:
        existing = sys.modules[name]
        need(Path(existing.__file__).absolute() == path.absolute()
             and pin(body(path, cap=1024**2)) == expected, 'Never replace a foreign source module')
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if register:
        sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    except BaseException:
        if register and sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise
    return module


def source_identity():
    root, manifest = _component()
    compiler = _module('_smc_validation_overlay_verifier', root / 'validation_overlay.py',
                       manifest['files']['validation_overlay.py'])
    result = compiler.verify_overlay(HERE)
    need(result['composition'] == COMPOSITION, 'Source derivation binds this exact component')
    return result['source']


def load():
    global _legacy
    source_identity()
    root, manifest = _component()
    core = _module('validation_core', root / 'validation_core.py', manifest['files']['validation_core.py'], register=True)
    core.source_identity(root, expected_sha=LEGACY_SOURCE['sha256'])
    if _legacy is None:
        module = _module('_smc_author_validation_episode', root / 'validation_episode.py', LEGACY_EPISODE, register=True)
        _legacy = module.create_episode(COMPOSITION['repository_root'], root)
    need(_legacy.source_identity() == LEGACY_SOURCE, 'Complete author-reference source before use')
    return _legacy
