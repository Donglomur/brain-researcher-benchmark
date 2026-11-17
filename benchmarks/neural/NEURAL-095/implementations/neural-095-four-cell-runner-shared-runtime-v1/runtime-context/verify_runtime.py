"""Check versions/metadata in a later selected image; no science or fits."""
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


def check(lock, installed, python_version, system, machine):
    if (python_version, system, machine) != ('3.12.8', 'Linux', 'aarch64'):
        raise ValueError('selected CPython3.12.8 Linux ARM64 runtime required')
    expected = {w['name']: w['version'] for w in lock['wheels']}
    if any(installed.get(name) != version for name, version in expected.items()):
        raise ValueError('every locked package version must match')
    return {'status': 'declared_runtime_versions_match', 'python': python_version,
            'system': system, 'machine': machine, 'locked_versions': expected,
            'all_installed_distributions': dict(sorted(installed.items())),
            'native_libraries_or_scientific_outputs_verified': False,
            'consumer_compatibility_qualified': False}


def main():
    lock = json.loads(Path('/opt/science-lock/WHEELS.json').read_bytes())
    installed = {}
    for d in importlib.metadata.distributions():
        name = d.metadata['Name'].lower().replace('_', '-').replace('.', '-')
        if name in installed:
            raise ValueError('duplicate installed distribution')
        installed[name] = d.version
    print(json.dumps(check(lock, installed, platform.python_version(), platform.system(), platform.machine()), indent=2))


if __name__ == '__main__':
    main()
