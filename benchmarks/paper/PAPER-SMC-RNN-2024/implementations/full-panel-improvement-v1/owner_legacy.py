"""Source-selected full-panel adapter for an authenticated operational overlay.

This file occupies legacy.py only in a fresh explicitly constructed overlay.
The published strict owner source and module globals remain unchanged.
"""
import importlib.util
from pathlib import Path
from common import HERE, body, descriptor, need, pin, read

RUNTIME_FILES = {'common.py', 'legacy.py', 'cli_custody.py', 'journal.py', 'process_owner.py',
                 'group_bootstrap.py', 'trusted_controller.py', 'owned_episode.py', 'controller.py',
                 'runner.py', 'cgroup.py', 'COMPOSITION.json'}
FACADE_PIN = {'bytes': 41057, 'sha256': '7becc1746b068699070bc28f16286246427233e1a0082274b01a6ad75bcf8c3a'}
COMPOSITION = read(HERE / 'COMPOSITION.json')
need(set(COMPOSITION) == {'schema', 'repository_root', 'component_root', 'component_source', 'episode',
                         'retained_owner_source'}
     and COMPOSITION['schema'] == 'smc_full_panel_owner_composition_v1'
     and FACADE_PIN is not None and COMPOSITION['episode'] == FACADE_PIN, 'Exact fixed overlay composition')
LEGACY_SOURCE = descriptor(COMPOSITION['component_source'])
LEGACY_EPISODE = descriptor(COMPOSITION['episode'])
_legacy = None


def source_identity():
    manifest = read(HERE / 'SOURCE.json')
    need(set(manifest) == {'schema', 'files', 'retained_owner_source', 'component_source'}
         and manifest['schema'] == 'smc_full_panel_owner_overlay_v1'
         and set(manifest['files']) == RUNTIME_FILES
         and manifest['component_source'] == LEGACY_SOURCE
         and manifest['retained_owner_source'] == COMPOSITION['retained_owner_source'],
         'Closed exact source overlay')
    for name, expected in manifest['files'].items():
        need(pin(body(HERE / name)) == descriptor(expected), 'Every overlaid owner byte remains pinned')
    return pin(body(HERE / 'SOURCE.json'))


def load():
    global _legacy
    source_identity()
    root = Path(COMPOSITION['component_root'])
    need(pin(body(root / 'RUNTIME_SOURCE.json')) == LEGACY_SOURCE, 'New component runtime source identity')
    raw = body(root / 'full_panel_episode.py', LEGACY_EPISODE)
    if _legacy is None:
        spec = importlib.util.spec_from_file_location('_smc_full_panel_owner_episode', root / 'full_panel_episode.py')
        module = importlib.util.module_from_spec(spec)
        exec(compile(raw, str(root / 'full_panel_episode.py'), 'exec'), module.__dict__)
        _legacy = module.FullPanelEpisode(COMPOSITION['repository_root'], root)
        need(_legacy.source_identity() == LEGACY_SOURCE, 'Complete new condition composition')
    return _legacy
