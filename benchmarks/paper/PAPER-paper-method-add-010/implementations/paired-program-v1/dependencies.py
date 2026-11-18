"""Exact retained preparation/scoring source, with no numerical substitution."""
import types
from pathlib import Path

from storage import read

HERE = Path(__file__).resolve().parent
PINS = {
    "inputs": ("original-feature-producer-v1/inputs.py", 13911,
               "187e2cb626814e82e043c65c2a4b9350ce29d64b869f39551c41b43ab8008ae2"),
    "score": ("original-fold-score-v1/score.py", 11905,
              "d8d3b0c95c6b18ad1f84c74f728ecfd1089344a34e55125dc3a5c3bf27051b97"),
    "roster": ("nested-connectivity-v1/published_participants.txt", 563,
               "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a"),
}


def load(name):
    # inputs.py itself loads the unchanged scorer to obtain its source roster.
    # Authenticate the complete small dependency set before any module executes.
    captured = {}
    for key, (relative, size, sha) in PINS.items():
        path = HERE.parent / relative
        captured[key] = (path, read(path, size, {"bytes": size, "sha256": sha}))
    path, body = captured[name]
    module = types.ModuleType("meg_paired_retained_" + name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module
