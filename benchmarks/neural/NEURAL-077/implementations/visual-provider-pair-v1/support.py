"""Pinned original N077 loaders and additive visual-provider implementation."""
from pathlib import Path
import hashlib
import json
import os
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
CONDITIONS = ("four_demo", "matched_waveform_programme")
FILES = ("support.py", "transport.py", "SOURCE_BINDINGS.json", "BASE_SOURCES.json",
         "protected_compare.py", "provider_arm.py", "visual_client.py", "visual_bridge.py", "transfer_png.py")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def module(name, path, raw, extra=None):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    if extra:
        value.__dict__.update(extra)
    sys.modules[name] = value
    exec(compile(raw, str(path), "exec"), value.__dict__)
    return value


def decode(raw):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate request/source key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite request/source")))


def capture(path, cap=131072, expected=None, *, budget=None):
    path = Path(path).absolute()
    need(all(not x.is_symlink() for x in (path, *path.parents)), "No linked source/request")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        fields = lambda x: (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_nlink)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "Bounded ordinary source/request")
        if budget is not None:
            budget.input(before.st_size + 1)
        raw = stream.read(before.st_size + 1 if budget is not None else cap + 1)
        need(len(raw) == before.st_size and fields(before) == fields(os.fstat(stream.fileno())) == fields(path.lstat()),
             "Source/request changed during capture")
    need(expected is None or pin(raw) == expected, "Exact source/request identity")
    return raw


SELF_PIN = pin(capture(HERE / "support.py"))


def load(root):
    root = Path(root).absolute()
    own = {name: capture(HERE / name) for name in FILES}
    operator = {name: pin(raw) for name,raw in own.items()}
    need(operator["support.py"] == SELF_PIN, "Loaded support source drift")
    manifest = decode(own["BASE_SOURCES.json"])
    name = "waveform-provider-v1/support.py"
    path = root / name
    raw = capture(path, expected=manifest[name])
    s = module("n077_visual_original_support", path, raw)
    bodies = {name: s.read(root / name, 131072, expected) for name, expected in manifest.items()}
    original = s.sources(root)
    need(all(manifest[name] == expected for name, expected in original["bindings"].items()),
         "Original numerical source closure changed")
    t = module("n077_visual_additive_transport", HERE / "transport.py", own["transport.py"],
               {"IMPLEMENTATIONS_ROOT": root})
    p = module("n077_visual_explicit_compare", HERE / "protected_compare.py", own["protected_compare.py"])
    bridge = module("n077_visual_image_bridge", HERE / "visual_bridge.py", own["visual_bridge.py"])
    need(identity(s) == operator, "Source changed during module loading")
    return {"root": root, "s": s, "original": original, "transport": t, "protected": p,
            "bridge": bridge, "bindings": manifest, "original_bodies": bodies, "operator": operator}


def identity(s, *, budget=None):
    return {name: pin(capture(HERE / name, 131072, budget=budget) if budget is not None
                      else s.read(HERE / name, 131072)) for name in FILES}
