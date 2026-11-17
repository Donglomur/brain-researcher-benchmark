"""Load exact existing owner-side source without changing global import paths."""
from __future__ import annotations

import builtins
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import stat
import sys
from types import ModuleType, SimpleNamespace
import uuid

ORIGINAL = "docs/provenance/registrations/expansion-20261113/helsinki-recorded-grid-construction-v1"
PINS = {
    "helsinki_profile.py": "0ce0f9aab10711583f5d398967fe90fbd0b2930b6a044e298d0a7b950bf5c279",
    "helsinki_intake.py": "4e37951aad09c10176fabb9c54e11bf94f1266d19647d9b86ab0ec9c28ff51b2",
    "helsinki_protocol.py": "7b62023099c76c6625a53d2277cf5b2350b4de056bafd1453c31b45066e5abc2",
    "helsinki_score.py": "46bf01688a64e974b81e1aaed59b14ed5b934c52a8a6a23c43cc0bdb0570eaff",
    "helsinki_fixture.py": "00913ab75d671bdaa6e680db3369e46b5bc256c66773841790149681b02acf74",
    "release_manifest.json": "84ad5381159c34a592a8177b2d2b2b03d6dc3a352a1e8e566201f5cd40f8aa8a",
    "HEADER_SOURCE_EXPECTATIONS.json": "2de359fbe43307261d03677a7a35682d4bb72e9b81b24c8f53832a86b3e31c67",
    "SOURCE_EXCEPTION_ALLOWLIST.json": "15a78c9f6e17ca17e9168186d94b1049c934f197db645ebbffdda1901122a160",
    "ANNOTATION_LAYOUT_PROFILE.json": "6758b1c968b67059e737c19422766ea39518d885be087a9d711917dda0b06778",
}
CURRENT_PROTOCOL_PIN = "9ca5ae8f2c1085503b8775d9598c7a495ed532457fb917d4a38654144957add5"


class SourceError(ValueError):
    pass


def read_pinned(path, expected):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1024 * 1024:
            raise SourceError("source must be a bounded ordinary non-aliased file")
        body = handle.read(1024 * 1024 + 1)
        after = os.fstat(handle.fileno())
        if len(body) > 1024 * 1024 or (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise SourceError("source changed while read")
    if len(body) != info.st_size or hashlib.sha256(body).hexdigest() != expected:
        raise SourceError("source hash differs: " + path.name)
    return body


def _module(path, body, namespace, imports):
    name = namespace + "." + path.stem
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = namespace
    original_import = builtins.__import__

    def source_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in imports:
            return imports[name]
        return original_import(name, globals, locals, fromlist, level)

    module.__dict__["__builtins__"] = dict(vars(builtins), __import__=source_import)
    # dataclasses resolves forward annotations through this exact module name.
    sys.modules[name] = module
    try:
        exec(compile(body, str(path), "exec"), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


@lru_cache(maxsize=1)
def load_sources():
    root = Path(__file__).resolve().parents[5]
    original = root / ORIGINAL
    bodies = {name: read_pinned(original / name, pin) for name, pin in PINS.items()}
    current_path = Path(__file__).resolve().parent.parent / "complete-support-evaluator" / "protocol.py"
    current_body = read_pinned(current_path, CURRENT_PROTOCOL_PIN)
    namespace = "_helsinki_source_admission_" + uuid.uuid4().hex
    profile = _module(original / "helsinki_profile.py", bodies["helsinki_profile.py"], namespace, {})
    intake = _module(original / "helsinki_intake.py", bodies["helsinki_intake.py"], namespace,
                     {"helsinki_profile": profile})
    current = _module(current_path, current_body, namespace, {})
    profile.source_profiles()
    if dict(profile.source_code_identity()) != {name: pin for name, pin in PINS.items() if name.endswith(".py")}:
        raise SourceError("predecessor source identity differs from authenticated bodies")
    if tuple("-".join(pair) for pair in intake.MONTAGE) != current.MONTAGE:
        raise SourceError("original and current montage disagree")
    return SimpleNamespace(intake=intake, profile=profile, current=current,
                           manifest=original / "release_manifest.json",
                           dependencies={**{ORIGINAL + "/" + n: h for n, h in PINS.items()},
                                         "benchmarks/neural/NEURAL-EXP-005/implementations/complete-support-evaluator/protocol.py": CURRENT_PROTOCOL_PIN})
