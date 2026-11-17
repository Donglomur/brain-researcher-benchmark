"""Inspect an already built, selected role environment without importing its packages."""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

def need(ok, why):
    if not ok:
        raise ValueError(why)

def unique(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, "duplicate lock key")
        out[key] = value
    return out

def captured(path, cap):
    stream = path.open('rb'); first = None; raw = None
    try:
        raw = stream.read(cap + 1)
        need(len(raw) <= cap, 'bounded complete selected metadata')
    except BaseException as error:
        first = error
    finally:
        try:
            stream.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                first.__dict__.setdefault('cleanup_failures', []).append(error)
    if first is not None:
        raise first
    return raw

def capabilities(role):
    numpy = importlib.import_module('numpy')
    need(callable(numpy.linalg.solve) and callable(numpy.linalg.svd), 'actual numerical APIs')
    if role == 'ingestion':
        need(callable(numpy._core.multiarray._reconstruct) and
             callable(numpy._core.numeric._frombuffer), 'actual fixed NumPy2 ingestion APIs')
    elif role == 'controller':
        ed = importlib.import_module('cryptography.hazmat.primitives.asymmetric.ed25519')
        need(callable(ed.Ed25519PublicKey.from_public_bytes), 'actual qualification verification API')
    elif role == 'campaign':
        need(os.environ.get('HF_HUB_OFFLINE') == '1' and
             os.environ.get('TRANSFORMERS_OFFLINE') == '1', 'explicit offline model environment')
        torch = importlib.import_module('torch')
        transformers = importlib.import_module('transformers')
        need(torch.version.cuda is None and hasattr(torch, 'float32') and
             callable(torch.inference_mode), 'actual CPU float32 model APIs')
        need(callable(transformers.AutoTokenizer.from_pretrained) and
             callable(transformers.AutoModelForCausalLM.from_pretrained) and
             callable(transformers.StoppingCriteriaList), 'actual selected text provider APIs')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True)
    parser.add_argument('--capabilities', action='store_true')
    args = parser.parse_args()
    path = Path(args.lock)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and not path.is_symlink() and before.st_size <= 131072,
         "bounded ordinary role lock")
    raw = captured(path, 131072)
    need(len(raw) == before.st_size and len(raw) <= 131072, "complete bounded role lock")
    lock = json.loads(raw, object_pairs_hook=unique)
    need(type(lock) is dict and lock["schema"] == "neural055-role-environment-lock-v1",
         "source-owned role lock")
    need(lock["role"] in ("ingestion", "controller", "campaign"),
         "one fixed role")
    need(platform.python_implementation() == "CPython" and sys.platform == "linux" and
         platform.machine() == "x86_64", "exact selected interpreter platform")
    need(platform.python_version() == lock["python"], "exact selected Python micro version")
    need(sys.flags.isolated and sys.flags.dont_write_bytecode, "isolated no-bytecode inspection")
    packages = lock["packages"]
    need(type(packages) is list and 0 < len(packages) <= 64, "finite exact package roster")
    observed = []
    seen = set()
    for row in packages:
        name = row["name"]
        need(type(name) is str and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) and
             name not in seen, "unique normalized package name")
        seen.add(name)
        version = importlib.metadata.version(name)
        need(version == row["version"], "exact installed package version: " + name)
        observed.append({"name": name, "version": version})
    if args.capabilities:
        capabilities(lock['role'])
    result = {"schema": "neural055-role-environment-inspection-v1", "role": lock["role"],
              "python": platform.python_version(), "machine": platform.machine(),
              "platform": sys.platform, "packages": observed,
              "lock_sha256": hashlib.sha256(raw).hexdigest(),
              "scope": "Selected version metadata and optional API/native-library imports; no model or scientific computation.",
              "image_identity_observed": False, "native_qualified": False,
              "native_packages_imported": args.capabilities,
              "model_checkpoint_or_data_loaded": False}
    encoded = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    need(len(encoded) <= 16384, "bounded inspection result")
    offset = 0
    while offset < len(encoded):
        count = os.write(1, encoded[offset:])
        need(count > 0, "inspection output progress")
        offset += count
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
