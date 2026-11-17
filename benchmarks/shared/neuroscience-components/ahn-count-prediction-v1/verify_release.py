"""BYO-data integrity verifier; no network, extraction, or scientific inference."""
import hashlib
import json
import os
from pathlib import Path
import stat

COMMIT = "256d17237e6d2786eac1a947c4828cb654c315d7"
FILES = (
    ("17/FosCounts/countsummary_cleaned.csv", 2240620, "7c716391de26a93ef54ceda4d95b84cf11e334ae"),
    ("17/FosCounts/allgraylabels.csv", 73538, "715524e846786e787b50379a3340473d86cfdb54"),
    ("17/SEFL17_Groups.csv", 1290, "169d1851f2595a2c05c306c053b0cd9073c42c2e"),
    ("17/SEFL17_Design.xlsx", 17372, "736fb55478566c64443d934aea148e704b05ad0a"),
    ("17/Behavior/SEFL17_MildStressor.csv", 558246, "ab0789c0c91812ba2d1968b33652873d879d30f0"),
    ("17/Behavior/SEFL17_vfData.csv", 54341, "949612f040e06e5c5feebc850e5288b111dd475c"),
)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)


def verify_one(root, relative, size, blob):
    root = Path(root)
    path = root / relative
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("symlink refused")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
        raise ValueError("ordinary single-link exact-size file required")
    git_hash = hashlib.sha1(b"blob " + str(size).encode() + b"\0")
    strong_hash = hashlib.sha256()
    read = 0
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if identity(opened) != identity(before):
            raise ValueError("file changed before open")
        for chunk in iter(lambda: stream.read(65536), b""):
            read += len(chunk)
            if read > size:
                raise ValueError("body grew")
            git_hash.update(chunk)
            strong_hash.update(chunk)
        after_open = os.fstat(stream.fileno())
    if identity(before) != identity(after_open) or identity(before) != identity(path.lstat()):
        raise ValueError("file identity changed")
    if read != size or git_hash.hexdigest() != blob:
        raise ValueError("Git blob identity mismatch")
    return {"path": relative, "bytes": read, "git_blob": blob, "sha256": strong_hash.hexdigest()}


def verify(root):
    rows = [verify_one(root, *row) for row in FILES]
    return {"schema": "ahn-six-input-integrity-v1", "commit": COMMIT, "files": rows,
            "body_bytes": sum(row["bytes"] for row in rows),
            "cohort_and_region_semantics_verified": False,
            "redistribution_permission_granted": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = verify(args.root)
    with Path(args.output).open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
