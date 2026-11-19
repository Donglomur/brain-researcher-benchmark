"""Pinned public entry for training-only nested46 full-field preparation.

This is a trusted owner interface over normalized projections, not a MAT reader,
source authenticator, scientific evaluation or participant process sandbox.
"""
import builtins
import hashlib
import os
from pathlib import Path
import stat
import types


class PreparationError(ValueError):
    pass


DEPENDENCIES = {
    "roster": ("fullfield-preparation/roster.py", 2755,
        "0f1ac943d56edc5305be4ba74f5d27c8cfa626e555092b7a51a1f6f2641dd4c9"),
    "scorer": ("fullfield-preparation/scorer.py", 14394,
        "6956a375c850a21abab2febc99cb3579900e74606cf3dd199ac2661ab0270dc7"),
    "fullfield": ("fullfield-preparation/fullfield.py", 12927,
        "20fe65ee870ae6a7a18c8534e3b935cdd30b75b49993adb9a644ff0f9b1422d6"),
    "delivery": ("fullfield-delivery-v1/delivery.py", 16104,
        "ec555899123ff0b5732f77489f96508c755f1fe7fa79e6accb6e7d21e4f28a3e"),
    "admission": ("outer-training-selection-v1/admission.py", 10586,
        "66495eafec42da3dec4db0cb951e3419464237899261c1bf22b5b37405f57268"),
    "producer": ("nested-training-preparation-v1/producer.py", 21715, "4e735181b501d1e042edbe6ea590a344147c46de84c69541d2beeac99219b25b"),
}


def _dependencies(root=None):
    """Load exact bounded bytes in private namespaces; never ambient pyc."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    sources = {}
    for name, (relative, extent, digest) in DEPENDENCIES.items():
        path = root / relative
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise PreparationError("dependency must be ordinary source")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                body = handle.read(extent + 1)
            if len(body) != extent or hashlib.sha256(body).hexdigest() != digest:
                raise PreparationError("dependency identity mismatch: " + name)
            sources[name] = (path, body)
        finally:
            os.close(fd)
    modules = {}
    ordinary_import = builtins.__import__

    def private_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in DEPENDENCIES:
            if name not in modules:
                raise PreparationError("dependency order mismatch")
            return modules[name]
        return ordinary_import(name, globals, locals, fromlist, level)

    for name in DEPENDENCIES:
        path, body = sources[name]
        module = types.ModuleType("_fus_nested_training_" + name)
        module.__file__ = str(path)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": private_import}
        exec(compile(body, str(path), "exec"), module.__dict__)
        modules[name] = module
    return modules


def prepare_training(projection_wire, load_record, stage_packet, *,
                     expected_projection_sha256, max_projection_bytes,
                     max_record_bytes, max_total_record_bytes, max_map_bytes,
                     max_packet_bytes, max_total_packet_bytes,
                     max_manifest_bytes, max_receipt_bytes, dependency_root=None):
    """Construct one complete outer-training input for the existing selector.

    Both callbacks are trusted-owner capabilities. The producer receives only
    the47 admitted training records, and reauthenticates both loads per record.
    Outputs remain private staging until a complete returned receipt is accepted.
    Source and payload bounds do not constitute physical-I/O or OS-memory quotas.
    No record/scale/packet state is retained in a cross-outer-fold cache.
    """
    modules = _dependencies(dependency_root)
    return modules["producer"].prepare_training(
        projection_wire, load_record, stage_packet,
        expected_projection_sha256=expected_projection_sha256,
        max_projection_bytes=max_projection_bytes, max_record_bytes=max_record_bytes,
        max_total_record_bytes=max_total_record_bytes, max_map_bytes=max_map_bytes,
        max_packet_bytes=max_packet_bytes, max_total_packet_bytes=max_total_packet_bytes,
        max_manifest_bytes=max_manifest_bytes, max_receipt_bytes=max_receipt_bytes,
        deps={key: modules[key] for key in ("roster", "scorer", "fullfield", "delivery", "admission")})
