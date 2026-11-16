"""Portable trusted-operator adapter for the unchanged ACh/DA report scorer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types

CORE = (17996, "df1631b0bed8d4fe0363f1ea45d180fa2e3330c3688b1cc9cc102c9172f994f2")
CONTRACT = (51303, "b2a24a29c17fd4291115f38afb2b97b3f644240956fb312480630a406187f94a")
MAX_REPORT = 30000


def ordinary_path(path):
    path = Path(path).absolute()
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError("Trusted parent path must be canonical and contain no aliases")
    return path


def fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def read_file(path, cap, expected=None):
    path = ordinary_path(path)
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 0 < before.st_size <= cap):
        raise ValueError("Nonempty bounded ordinary single-link file required")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if fingerprint(before) != fingerprint(opened):
            raise ValueError("Input changed before open")
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    if (fingerprint(before) != fingerprint(after)
            or fingerprint(before) != fingerprint(path.lstat())
            or len(body) != before.st_size or len(body) > cap):
        raise ValueError("Input changed during read")
    if expected is not None and (len(body), hashlib.sha256(body).hexdigest()) != expected:
        raise ValueError("Pinned input identity mismatch")
    return body


def load_source(directory):
    directory = Path(directory)
    body = read_file(directory / "score_core.py", CORE[0], CORE)
    core = types.ModuleType("achda_pinned_core")
    exec(compile(body, str(directory / "score_core.py"), "exec"), core.__dict__)
    contract = json.loads(read_file(directory / "PUBLIC_CONTRACT.json", CONTRACT[0], CONTRACT))
    return core, contract


def evaluate(core, contract, candidate, reference, reference_bytes, reference_sha256):
    if (type(reference_bytes) is not int or not 0 < reference_bytes <= core.MAX_BYTES
            or type(reference_sha256) is not str or len(reference_sha256) != 64
            or any(c not in "0123456789abcdef" for c in reference_sha256)):
        raise ValueError("Reference identity must come from separate accepted operator provenance")
    try:
        body = read_file(candidate, core.MAX_BYTES)
    except (OSError, ValueError) as error:
        return {"candidate_id": core.ID, "status": "invalid_submission",
                "reason": type(error).__name__, "private_reference_reads": 0}
    calls = 0
    def load_reference():
        nonlocal calls
        calls += 1
        return read_file(reference, core.MAX_BYTES, (reference_bytes, reference_sha256))
    result = core.grade(body, contract, load_reference)
    if result["private_reference_reads"] != calls:
        raise RuntimeError("Reference callback accounting mismatch")
    return result


def write_report(path, result):
    body = (json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n").encode()
    if len(body) > MAX_REPORT:
        raise ValueError("Complete report exceeds 30000-byte cap")
    path = ordinary_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-bytes", type=int, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    core, contract = load_source(Path(__file__).resolve().parent)
    result = evaluate(core, contract, args.candidate, args.reference,
                      args.reference_bytes, args.reference_sha256)
    write_report(args.output, result)
    return 2 if result["status"] in ("operator_error", "unsupported_derived_numerics") else 0


if __name__ == "__main__":
    raise SystemExit(main())
