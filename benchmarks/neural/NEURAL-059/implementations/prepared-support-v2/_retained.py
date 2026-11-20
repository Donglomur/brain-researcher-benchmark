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


def load():
    for filename, expected in PINS.items():
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("retained_scientific_source_changed:" + filename)
    if hashlib.sha256((HERE / "evaluation.py").read_bytes()).hexdigest() != EVALUATION_SHA256:
        raise ValueError("probability_successor_source_changed")
    if NAME not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            NAME, ROOT / "__init__.py", submodule_search_locations=[str(HERE), str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[NAME] = module
        spec.loader.exec_module(module)
    return (__import__(NAME + ".contracts", fromlist=["contracts"]),
            __import__(NAME + ".evaluation", fromlist=["evaluation"]))
