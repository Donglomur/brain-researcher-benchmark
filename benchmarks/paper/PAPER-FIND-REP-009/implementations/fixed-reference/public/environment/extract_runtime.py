"""Verified software archive extraction only; no R/package/model execution."""
import gzip
import hashlib
from pathlib import Path, PurePosixPath
import sys
import tarfile

archive = Path(sys.argv[1])
if archive.stat().st_size != 98877128:
    raise ValueError("Exact compressed software archive size")
digest = hashlib.sha256()
with archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1048576), b""): digest.update(block)
if digest.hexdigest() != "0e0f41dfb4313192f99958abed5f2834a17dc775047cbd1e71a02fcaa5eb983a":
    raise ValueError("Exact compressed software archive hash")
digest = hashlib.sha256(); count = 0
with gzip.open(archive, "rb") as stream:
    for block in iter(lambda: stream.read(1048576), b""):
        count += len(block)
        if count > 159436800: raise ValueError("Original archive size bound")
        digest.update(block)
if count != 159436800 or digest.hexdigest() != "ca15b595d5439ab729db2eba84941a51a26c88ca8f99ded02cb575fefb528330":
    raise ValueError("Exact original sealed software tar")
with tarfile.open(archive, "r:gz") as source:
    members = source.getmembers()
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or not (member.isdir() or member.isfile()):
            raise ValueError("Only ordinary relative software archive members")
        if member.name not in ("opt", "opt/thalamus", "opt/thalamus/R-4.3.1") and not member.name.startswith("opt/thalamus/R-4.3.1/"):
            raise ValueError("Exact software prefix only")
        if member.mode & 0o7000: raise ValueError("No special permission bits")
    source.extractall("/", members=members, filter="data")
print("Pinned R software prefix extracted; no scientific execution")
