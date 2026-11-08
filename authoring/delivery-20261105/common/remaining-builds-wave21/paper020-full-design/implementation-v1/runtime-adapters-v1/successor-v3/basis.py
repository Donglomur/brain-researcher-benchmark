"""Authenticate the immutable reviewed scientific source before importing it."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types

EXPECTED = "0be6179b8ed5ac62960f867901310293de781f6815bee20c9723fe1a2b9d8898"
FILES = ("entry.py", "lib/__init__.py", "lib/admission.py", "lib/controller.py", "lib/dispatcher.py",
         "lib/native_capture.m", "lib/native_scoring.py", "lib/packets.py", "lib/programme.py",
         "lib/references.py", "lib/reproduction.py", "lib/scoring.py", "lib/splits.py",
         "lib/strict.py", "lib/units.py", "lib/source_identity.py", "contracts/programme.json",
         "contracts/OPERATOR_PROTOCOL.json")
_ROOT = Path(__file__).resolve().parents[2] / "successor-v2"
_NAME = "_it_reviewed_" + EXPECTED
_verified = False

def scientific_root():
    """Exact immutable V2 scientific source sibling of the adapter parent."""
    return _ROOT
ADAPTER_FILES=("__init__.py","authority.py","basis.py","candidate_worker.py","entry.py","guardian.py",
               "host_observer.py","mat_source.py","native_execution.py","native_worker.m",
               "process_control.py","provider.py","runtime.py","runtime_worker.py","wire.py")

def authenticate_adapters(document):
    root=Path(__file__).resolve().parent
    path=root/"ADAPTER_SOURCE_MANIFEST.json"
    if path.is_symlink() or path.stat().st_size>32768:
        raise ValueError("Bounded immutable adapter manifest required")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=document.get("adapter_source_digest"):
        raise ValueError("Signed adapter source manifest differs")
    manifest=json.loads(raw)
    if manifest.get("scientific_source_digest")!=EXPECTED or [p["path"] for p in manifest.get("files",[])]!=list(ADAPTER_FILES):
        raise ValueError("Exact reviewed adapter source set required")
    total=0
    for pin in manifest["files"]:
        p=root/pin["path"];size=p.stat().st_size;total+=size
        if p.is_symlink() or size!=pin["bytes"] or total>2_000_000:
            raise ValueError("Adapter source custody/extent differs")
        body=p.read_bytes()
        if len(body)!=size or hashlib.sha256(body).hexdigest()!=pin["sha256"]:
            raise ValueError("Adapter source bytes differ")
    return document["adapter_source_digest"]

def authenticate():
    global _verified
    pins = []
    total = 0
    for name in FILES:
        path = _ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Reviewed scientific source is absent or symlinked")
        size = path.stat().st_size
        total += size
        if size > 1_000_000 or total > 2_000_000:
            raise ValueError("Reviewed scientific source exceeds its source bound")
        raw = path.read_bytes()
        if len(raw) != size:
            raise ValueError("Reviewed scientific source changed during read")
        pins.append({"path": name, "bytes": size, "sha256": hashlib.sha256(raw).hexdigest()})
    value = hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if value != EXPECTED:
        raise ValueError("Reviewed scientific source identity differs")
    if _NAME not in sys.modules:
        package = types.ModuleType(_NAME)
        package.__path__ = [str(_ROOT)]
        sys.modules[_NAME] = package
    _verified = True
    return value

def basis(name):
    if name not in {Path(p).stem for p in FILES if p.startswith("lib/") and p.endswith(".py")} | {"entry"}:
        raise ValueError("Unreviewed scientific module requested")
    if not _verified:
        authenticate()
    return importlib.import_module(_NAME + (".entry" if name == "entry" else ".lib." + name))
