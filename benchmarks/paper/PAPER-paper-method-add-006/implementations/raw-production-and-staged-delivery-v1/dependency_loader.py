"""Authenticate and load unchanged source dependencies; no data reads or fits."""
from pathlib import Path
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent.parent
PINS = {'initial-evaluator-v1/evaluator.py': {'bytes': 30192, 'sha256': 'fb208d1056b93438d157f927d60b5bd3b1a8dd1775fd0a9164203dc41ac43a62'}, 'oof-prediction-replay-v2/replay.py': {'bytes': 11345, 'sha256': '548b275393fac8e35937637d27e62dd5e7857ee3beda9874185ceedd6e74d461'}, 'original-grid-producer-v1/producer.py': {'bytes': 23188, 'sha256': '891cc87cb9ce825d375114dafd78f77e5f11f9ca0187f8108602876b27c54328'}, 'original-grid-producer-v1/glm_search.py': {'bytes': 7766, 'sha256': '0d0ee0da6ef13e430bc8ce207a38d94d2eebffd82816c333b162e41a02ff1321'}, 'original-grid-producer-v1/geometry_results.py': {'bytes': 35540, 'sha256': '79cc4ec77d1cf32938ff1afac7998951919916c54eb6d871a1b7275e84ee036e'}, 'original-grid-producer-v1/native_inputs.py': {'bytes': 11379, 'sha256': '009723c68956af81cc2452f237740af4e901a1f99af6039397c5a0738987f370'}, 'original-grid-producer-v1/RNG_POLICY.json': {'bytes': 3940, 'sha256': 'a1ddc9f0e85b4818bad0ae8a399497fb6058c37ba9e3253ad13b55a347784eca'}, 'candidate-grid-submission-v1/deps.py': {'bytes': 2260, 'sha256': '691e7c2553cb014dca9e83a8cbb7aa4ee2a5f0f304d9dc20f80bf130abe956fb'}, 'candidate-grid-submission-v1/collection.py': {'bytes': 19223, 'sha256': '76275ffe8971dfb7642dabdc83aaceacf385866ebfe7a685bbe1e67405a26d50'}, 'candidate-grid-submission-v1/glm_bridge.py': {'bytes': 7896, 'sha256': '28f8cee5509c2b66d5ab8c61f8ffd0fdd00ff03530f150eaf99695006b2ef66d'}, 'candidate-grid-submission-v1/geometry_bridge.py': {'bytes': 22281, 'sha256': 'c6e70214e75194ba15e4fa4ece5352dcf0e02bd6e3048d164abbb173d3abf57d'}}

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
    need(_path.is_file() and not _path.is_symlink(), "ordinary pinned dependency required")
    need(_path.stat().st_size == _pin["bytes"], "dependency source length differs")
    need(hashlib.sha256(_path.read_bytes()).hexdigest() == _pin["sha256"], "dependency source digest differs")

D = _load("_population_raw_frozen_deps", "candidate-grid-submission-v1/deps.py")
G, N, R, P, V, K = D.G, D.N, D.R, D.P, D.V, D.K
_previous_deps = sys.modules.get("deps")
try:
    sys.modules["deps"] = D
    C = _load("_population_raw_collection", "candidate-grid-submission-v1/collection.py")
    GB = _load("_population_raw_geometry_bridge", "candidate-grid-submission-v1/geometry_bridge.py")
    GLB = _load("_population_raw_glm_bridge", "candidate-grid-submission-v1/glm_bridge.py")
finally:
    if _previous_deps is None:
        sys.modules.pop("deps", None)
    else:
        sys.modules["deps"] = _previous_deps
