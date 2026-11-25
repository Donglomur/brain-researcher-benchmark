"""Load retained scientific dependencies and the bounded probability successor."""
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1] / "registered-runtime" / "complete-process-v1" / "scientific"
PINS = {
    "__init__.py": "bb5787781385927b7c93bda57d56888b18597a56b45f734350ad8ea0c95ca7ab",
    "contracts.py": "bfac56e3f7c30fb6a9f8d263706dd7578ee58e383a40d88f626cfcea52098557",
    "diagnostics.py": "1a3aeb8defa32d1fa5b339a2f2501b176d21e4fb7beb2791a639c436cff87054",
    "evaluation.py": "40a02d51e8db4d9aee0a4c0f983431b96caa769da2513d5591dd34826799e09d",
}
NAME = "_neural059_probability_scientific_v2"
EVALUATION_SHA256 = "bb145291cc0a0c2e23393887d6c5c2cf9df9bc3a96e37239cecd45e850995313"


def _captured_module(name, path, body, *, package=False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def load():
    # Keep both the immutable source lineage and the active successor checks,
    # then execute only the authenticated bytes. Normal file imports would
    # reopen these paths and can select a changed file or stale module cache.
    bodies = {}
    for filename, expected in PINS.items():
        body = (ROOT / filename).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("retained_scientific_source_changed:" + filename)
        bodies[filename] = body
    body = (HERE / "evaluation.py").read_bytes()
    if hashlib.sha256(body).hexdigest() != EVALUATION_SHA256:
        raise ValueError("probability_successor_source_changed")
    bodies["successor_evaluation.py"] = body
    names = (NAME, NAME + ".diagnostics", NAME + ".contracts", NAME + ".evaluation")
    missing = object()
    prior = {name: sys.modules.get(name, missing) for name in names}
    try:
        package = _captured_module(NAME, ROOT / "__init__.py",
                                   bodies["__init__.py"], package=True)
        for stem in ("diagnostics", "contracts", "evaluation"):
            path = HERE / "evaluation.py" if stem == "evaluation" else ROOT / (stem + ".py")
            key = "successor_evaluation.py" if stem == "evaluation" else stem + ".py"
            module = _captured_module(NAME + "." + stem, path, bodies[key])
            setattr(package, stem, module)
        return package.contracts, package.evaluation
    finally:
        # The bootstrap remains trusted and sequential. Do not retain mutable
        # scoring modules or disturb an earlier operator import after loading.
        for name, module in prior.items():
            if module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
