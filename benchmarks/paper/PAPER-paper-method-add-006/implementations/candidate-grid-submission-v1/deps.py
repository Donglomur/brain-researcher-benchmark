"""Load the unchanged reviewed sibling algorithms; no fit or data read."""
from pathlib import Path
import hashlib
import importlib.util
import sys

PINS = {'initial-evaluator-v1/evaluator.py': {'bytes': 30192, 'sha256': 'fb208d1056b93438d157f927d60b5bd3b1a8dd1775fd0a9164203dc41ac43a62'}, 'oof-prediction-replay-v2/replay.py': {'bytes': 11345, 'sha256': '548b275393fac8e35937637d27e62dd5e7857ee3beda9874185ceedd6e74d461'}, 'original-grid-producer-v1/producer.py': {'bytes': 23188, 'sha256': '891cc87cb9ce825d375114dafd78f77e5f11f9ca0187f8108602876b27c54328'}, 'original-grid-producer-v1/geometry_results.py': {'bytes': 35540, 'sha256': '79cc4ec77d1cf32938ff1afac7998951919916c54eb6d871a1b7275e84ee036e'}, 'original-grid-producer-v1/native_inputs.py': {'bytes': 11379, 'sha256': '009723c68956af81cc2452f237740af4e901a1f99af6039397c5a0738987f370'}, 'original-grid-producer-v1/glm_search.py': {'bytes': 7766, 'sha256': '0d0ee0da6ef13e430bc8ce207a38d94d2eebffd82816c333b162e41a02ff1321'}, 'original-grid-producer-v1/RNG_POLICY.json': {'bytes': 3940, 'sha256': 'a1ddc9f0e85b4818bad0ae8a399497fb6058c37ba9e3253ad13b55a347784eca'}}
ROOT = Path(__file__).resolve().parent.parent

def need(condition, message):
    if not condition:
        raise ValueError(message)

def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

for _relative, _pin in PINS.items():
    _path = ROOT / _relative
    need(_path.is_file() and not _path.is_symlink(), "reviewed source member must be ordinary")
    need(_path.stat().st_size == _pin["bytes"], "reviewed source length changed")
    _body = _path.read_bytes()
    need(hashlib.sha256(_body).hexdigest() == _pin["sha256"], "reviewed source digest changed")
G = _load("glm_search", "original-grid-producer-v1/glm_search.py")
N = _load("native_inputs", "original-grid-producer-v1/native_inputs.py")
R = _load("geometry_results", "original-grid-producer-v1/geometry_results.py")
P = _load("_population_candidate_producer", "original-grid-producer-v1/producer.py")
V = _load("_population_candidate_replay", "oof-prediction-replay-v2/replay.py")
K = G.K
