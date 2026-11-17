"""Declared offline environment helper; no data or model is read by setup."""
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


def setup(root):
    root = Path(root)
    sys.path.insert(0, str(root))
    from wheel_verifier import verify_wheel
    manifest = json.loads((root / 'runtime_manifest.json').read_text())
    if len(manifest['wheels']) != 29:
        raise ValueError('Exact offline wheel roster')
    paths, expanded = [], 0
    for row in manifest['wheels']:
        path = root / 'wheels' / row['filename']
        checked = verify_wheel(path, row)
        expanded += checked['uncompressed_bytes']
        if expanded > 500000000:
            raise ValueError('Qualified aggregate expansion cap')
        paths.append(str(path))
    installed = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
        '--no-cache-dir', '--disable-pip-version-check', '--no-compile', '-q',
        '--target', '/tmp/overlay', *paths], capture_output=True, timeout=40)
    if installed.returncode or len(installed.stdout) + len(installed.stderr) > 131072:
        raise ValueError('Bounded offline installation failed')
    sys.path.insert(0, '/tmp/overlay')
    versions = {name: importlib.metadata.version(name) for name in manifest['expected_versions']}
    if versions != manifest['expected_versions']:
        raise ValueError('Exact previously qualified numerical versions')
    import pytensor
    if (pytensor.config.cxx, pytensor.config.mode, pytensor.config.floatX,
        pytensor.config.cast_policy, pytensor.config.numba__fastmath,
        pytensor.config.numba__vectorize_target) != ('', 'NUMBA', 'float64', 'numpy+floatX', False, 'cpu'):
        raise ValueError('Exact qualified NUMBA configuration')
    return versions
