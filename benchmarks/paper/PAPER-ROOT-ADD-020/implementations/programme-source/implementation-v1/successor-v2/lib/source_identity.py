"""Bounded source-only implementation fingerprint, separate from data identity."""
from pathlib import Path
import hashlib
from .strict import need, digest

FILES = ("entry.py", "lib/__init__.py", "lib/admission.py", "lib/controller.py", "lib/dispatcher.py",
         "lib/native_capture.m", "lib/native_scoring.py", "lib/packets.py", "lib/programme.py",
         "lib/references.py", "lib/reproduction.py", "lib/scoring.py", "lib/splits.py",
         "lib/strict.py", "lib/units.py", "lib/source_identity.py", "contracts/programme.json",
         "contracts/OPERATOR_PROTOCOL.json")


def implementation_fingerprint():
    root = Path(__file__).resolve().parents[1]
    pins = []
    total = 0
    for name in FILES:
        path = root/name
        need(path.is_file() and not path.is_symlink(), "source", "Installed source member absent or symlinked")
        size = path.stat().st_size
        total += size
        need(size <= 1_000_000 and total <= 2_000_000, "source", "Bounded exact source tree required")
        raw = path.read_bytes()
        need(len(raw) == size, "source", "Source changed during fingerprint")
        pins.append({"path":name,"bytes":size,"sha256":hashlib.sha256(raw).hexdigest()})
    return digest(pins)
