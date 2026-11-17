"""Relocatable, captured-byte component loading with stable class identity.

Loading this module imports no numerical library. ``affinity`` is an explicit
native boundary; it is never loaded by the source build or its controls.
"""
from pathlib import Path
from types import ModuleType
import hashlib
import sys

HERE = Path(__file__).resolve().parent
PINS = {
    "graph": ("common/remaining-builds-wave8/paper_b-work/graph_prepare.py", 8896, "a1b52f23b8a7ddcb72506090a7780be995c70f23b615a38d2145335610568616"),
    "affinity": ("common/remaining-builds-wave9/paper_b-work/affinity_prepare.py", 6167, "56c8bf35ebc55fec76baf0cd3acaa0a51dfb70a9f81714e370efe6528ee99918"),
    "community": ("common/remaining-builds-wave11/banc-community-program/community.py", 14803, "5314043b6b5e4ecdf4697151f22456d48d056e679861507e3339d3687c311966"),
    "community_R": ("common/remaining-builds-wave11/banc-community-program/community_R.R", 11815, "a90904929778b5acb8638e000060a78ff81c128100beafefd60c2d12ad0f5ae2"),
    "reciprocity": ("banc-control/an-dn-reciprocity-kernel-v1/reciprocity.py", 7072, "24116b3a323105405495809e0bd3e1e3fdcf4401b61c1892bdf632387b36dbea"),
    "centrality": ("common/remaining-builds-wave11/banc-full-program/banc_program/centrality.py", 10259, "1783d53228b3f2cd6514c9165ba626ae9f6b189867614e7d49f93206a23d10b6"),
    "cns": ("common/remaining-builds-wave11/banc-full-program/banc_program/cns.py", 10012, "ffaa3912742ba4d614f62839e85e19f5b1e3cc0ba40d9b8e3b7c1af3db0da9c6"),
}
_loaded = {}


def capture(key):
    relative, size, digest = PINS[key]
    path = HERE / "_sources" / relative
    with path.open("rb") as stream:
        raw = stream.read(size + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("bundled_source_pin_changed:" + key)
    return path, raw


def component(key):
    """Pin every access, execute captured bytes once, preserve dataclass identity."""
    if key == "community_R":
        raise ValueError("R_is_a_separate_native_source_use_capture")
    path, raw = capture(key)
    if key in _loaded:
        return _loaded[key]
    if key in ("community", "affinity"):
        component("graph")
    digest = PINS[key][2]
    name = ("banc_graph_prepare_" if key == "graph" else
            "banc_affinity_prepare_" if key == "affinity" else
            "banc_composition_" + key + "_") + digest
    if name in sys.modules:
        raise ValueError("unowned_component_module_identity:" + key)
    module = ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
        module.__reviewed_source_sha256__ = digest
    except BaseException:
        sys.modules.pop(name, None)
        raise
    _loaded[key] = module
    return module


def verify_closure():
    return tuple((key, len(capture(key)[1]), PINS[key][2]) for key in PINS)
