"""Explicit future runtime qualification gate; source build supplies none."""
import importlib
import os
from pathlib import Path
import platform
import sys

from custody import need, read_pinned
from source_plan import descriptor

MODULES = ('numpy', 'scipy', 'pandas', 'mne', 'mne._fiff.open', 'mne._fiff.tag',
           'mne._fiff.tree', 'mne.io.fiff.raw', 'mne.epochs', 'mne.annotations',
           'mne.event', 'mne.io.base', 'mne.utils._logging')
PACKAGES = ('numpy', 'scipy', 'pandas', 'mne')


def absolute_pin(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact runtime source pin')
    path = Path(value['path'])
    need(path.is_absolute() and str(path) == value['path'], 'selected absolute runtime path')
    descriptor(dict(value, path=value['path'][1:]))
    return path


def envelope(receipt, *, selection, manifest_sha256):
    keys = {'schema', 'qualified', 'source_manifest_sha256', 'source_plan', 'caps', 'profile',
            'python', 'python_version', 'versions', 'modules', 'qualification_record', 'reader_profile', 'capacity', 'launch_custody'}
    need(type(receipt) is dict and set(receipt) == keys
         and receipt['schema'] == 'neural098-native-runtime-qualification-v1'
         and receipt['qualified'] is True, 'independent native runtime qualification required')
    need(receipt['source_manifest_sha256'] == manifest_sha256
         and receipt['source_plan'] == selection['source_plan']
         and receipt['caps'] == selection['caps'] and receipt['profile'] == selection['profile']
         and receipt['capacity'] == selection['capacity'],
         'runtime/source/whole-scope qualification binding')
    need(receipt['reader_profile'] == 'mne1.13.2_serial_ordinary_fif_counted_v1', 'reviewed explicit native reader profile')
    need(type(receipt['qualification_record']) is str and 0 < len(receipt['qualification_record']) <= 512,
         'root selected independent qualification record')
    need(type(receipt['versions']) is dict and set(receipt['versions']) == set(PACKAGES)
         and receipt['versions']['mne'] == '1.13.2'
         and all(type(v) is str and 0 < len(v) < 64 for v in receipt['versions'].values()), 'exact selected package versions')
    need(receipt['launch_custody'] == {'authenticated_entry_bytes': True, 'immutable_source_tree': True,
        'exclusive_trusted_worker': True} and all(type(v) is bool for v in receipt['launch_custody'].values()),
        'externally qualified frozen entry/source launch custody')
    need(type(receipt['python_version']) is str and 0 < len(receipt['python_version']) < 64,
         'selected exact interpreter version string')
    absolute_pin(receipt['python'])
    need(type(receipt['modules']) is dict and set(receipt['modules']) == set(MODULES), 'all reviewed native source dependencies')
    for pin in receipt['modules'].values(): absolute_pin(pin)
    need(sum(v['bytes'] for v in [receipt['python']] + list(receipt['modules'].values())) <= 256_000_000,
         'bounded whole runtime authentication')
    return receipt['python']


def qualify(receipt, *, selection, manifest_sha256, root_fd, budget):
    envelope(receipt, selection=selection, manifest_sha256=manifest_sha256)
    need(sys.version_info >= (3, 11), 'Python3.11+ cleanup exception semantics')
    need(receipt['python_version'] == platform.python_version(), 'selected exact interpreter version')
    need(absolute_pin(receipt['python']) == Path(sys.executable).resolve(), 'selected exact interpreter')
    need(type(receipt['modules']) is dict and set(receipt['modules']) == set(MODULES), 'all reviewed native source dependencies')
    pins = [receipt['python']] + [receipt['modules'][name] for name in MODULES]
    need(sum(v['bytes'] for v in pins) <= 256_000_000, 'bounded runtime authentication')
    # Authenticate selected paths before any native imports. The qualification
    # attests the whole environment; these source pins bind the reviewed seams,
    # not every transitive compiled dependency or publisher identity.
    for pin in pins:
        absolute_pin(pin)
        read_pinned(root_fd, dict(pin, path=pin['path'][1:]), budget, 256_000_000)
    modules = {}
    for name in MODULES:
        module = importlib.import_module(name)
        need(Path(module.__file__).resolve() == absolute_pin(receipt['modules'][name]), 'selected imported native module')
        if name in PACKAGES: need(module.__version__ == receipt['versions'][name], 'selected native version')
        modules[name] = module
    # Detect source drift across importing the selected environment.
    for pin in pins:
        read_pinned(root_fd, dict(pin, path=pin['path'][1:]), budget, 256_000_000)
    budget.check()
    return modules
