"""Reconcile only this stage's private outputs after its worker has stopped.

Read durable descriptor metadata, never native or target bodies. Unbound partial
files remain recorded and prevent successful completion; nothing is deleted.
"""
from pathlib import Path
from .io import Artifact, ByteMeter, ContractError, capture, decode, ordinary


def retained_outputs(root, stage, attempt, *, cap):
    parent = ordinary(root, directory=True)
    directory = parent / stage
    if not directory.exists():
        return {"artifacts": {}, "unbound_paths": [], "read_bytes": 0}
    directory = ordinary(directory, directory=True)
    meter = ByteMeter(cap, 0)
    entries = sorted(directory.iterdir(), key=lambda p: p.name)
    artifacts, record_paths = {}, set()
    for path in entries:
        if not path.name.startswith("_custody_"):
            continue
        body = capture(path, cap, meter=meter)
        value = decode(body)
        if (set(value) != {"schema", "attempt", "stage", "filename", "artifact"} or
                value["schema"] != "neural063_output_custody_v1" or value["stage"] != stage or
                value["attempt"] != attempt or Path(value["filename"]).name != value["filename"]):
            raise ContractError("invalid durable output custody metadata")
        name = value["filename"]
        if name in artifacts or path.name != "_custody_" + name + ".json":
            raise ContractError("duplicate or mismatched durable output descriptor")
        descriptor = Artifact.parse(value["artifact"])
        observed = ordinary(directory / name)
        if (descriptor.path != str(observed) or descriptor.producer != stage or
                observed.stat().st_size != descriptor.bytes):
            raise ContractError("durable descriptor path/producer/size changed after worker")
        artifacts[name] = descriptor.object()
        record_paths.add(path.name)
    unbound = []
    for path in entries:
        if path.name in record_paths or path.name in artifacts:
            continue
        # No body access, symlink traversal or speculative partial-file hash.
        st = path.lstat()
        unbound.append({"path": str(path), "bytes": st.st_size, "mode": st.st_mode,
                        "sha256": None, "disposition": "unbound_partial_preserved"})
    return {"artifacts": artifacts, "unbound_paths": unbound, "read_bytes": meter.read_bytes,
            "body_hashes_recomputed": False}
