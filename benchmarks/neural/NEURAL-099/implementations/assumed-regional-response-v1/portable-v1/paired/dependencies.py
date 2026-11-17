"""Load exact frozen authored dependencies, without native libraries or data."""
import hashlib
import importlib.util
from pathlib import Path

PINS = {
    'scoring': (16322, '4dd059367fea59dc14d7be83bdb99449376373140bf752b89fa5a2b48b29f316'),
    'condition': (21199, 'c6daada7521ca3cd583bb7ff2c7b123de327bfc62e9b18271602d7f138c9b74a'),
    'count_packet': (16320, '11edbb2691b7f4588fac833a3caa590490fd76119a51d6636da63c3cdf1be7ec'),
}


def load(name):
    if name not in PINS:
        raise ValueError('Unknown dependency')
    path = Path(__file__).with_name('deps') / (name+'.py')
    size, digest = PINS[name]
    with path.open('rb') as handle:
        body = handle.read(size+1)
    if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('Frozen dependency differs from its admitted source')
    spec = importlib.util.spec_from_file_location('neural099_paired_'+name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module
