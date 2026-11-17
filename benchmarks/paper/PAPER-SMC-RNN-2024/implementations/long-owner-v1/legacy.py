"""Exact source composition; no old active-owner refusal is patched or removed."""
import importlib.util
import sys
from common import HERE, body, descriptor, need, pin, read

LEGACY_SOURCE = {'bytes': 1295, 'sha256': 'fd188e19d5ca4ed996d21b285210c0dc355c45789ec7312931b6533e8fffe278'}
LEGACY_EPISODE = {'bytes': 34367, 'sha256': '29c200d0022ba5c36818719993b7b12224901a6fba2f7c515f3b278fcee1b1db'}
RUNTIME_FILES = {'common.py', 'legacy.py', 'cli_custody.py', 'journal.py',
                 'process_owner.py', 'group_bootstrap.py', 'trusted_controller.py',
                 'owned_episode.py', 'controller.py', 'runner.py'}
_legacy = None


def source_identity():
    manifest_raw = body(HERE / 'SOURCE.json')
    manifest = read(HERE / 'SOURCE.json')
    need(manifest['schema'] == 'smc_long_owner_source_v1'
         and set(manifest['files']) == RUNTIME_FILES and manifest['legacy_source'] == LEGACY_SOURCE
         and manifest['legacy_episode'] == LEGACY_EPISODE, 'Exact successor and predecessor closure')
    for name, expected in manifest['files'].items():
        need(pin(body(HERE / name)) == descriptor(expected), 'Frozen complete owner source')
    return pin(manifest_raw)


def load():
    global _legacy
    directory = HERE.parent / 'protected-episode-v1'
    need(pin(body(directory / 'SOURCE.json')) == LEGACY_SOURCE, 'Reviewed SMC composition source')
    raw = body(directory / 'episode.py', LEGACY_EPISODE)
    if _legacy is None:
        name = '_smc_long_owner_legacy'
        need(name not in sys.modules, 'Fresh fixed legacy namespace')
        spec = importlib.util.spec_from_file_location(name, directory / 'episode.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            exec(compile(raw, str(directory / 'episode.py'), 'exec'), module.__dict__)
            need(module.source_identity() == LEGACY_SOURCE, 'Full unchanged predecessor source closure')
        except BaseException:
            sys.modules.pop(name, None)
            raise
        _legacy = module
    return _legacy
