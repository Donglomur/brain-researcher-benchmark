"""Fail closed on missing/stale private reference provisioning, before scoring."""
from pathlib import Path
import hashlib
import stat
import sys

EXPECTED_SHA256 = '1db49c9bae2bc298896c50991e18f8cfbf6f4a11b6f814b98690c7f1c1ac437e'
EXPECTED_SIZE = 2495679


class PrivateReferenceError(RuntimeError):
    """Infrastructure failure; this is not an agent score."""


def require_reference(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("reference.npz")
    try:
        info = path.stat()
        if path.is_symlink() or not stat.S_ISREG(info.st_mode):
            raise PrivateReferenceError("Private reference must be a regular, non-symlink file")
        if info.st_size != EXPECTED_SIZE:
            raise PrivateReferenceError("Private reference size mismatch; provision the exact frozen bank")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != EXPECTED_SHA256:
            raise PrivateReferenceError("Private reference SHA256 mismatch; stale/wrong bank refused")
    except OSError as error:
        raise PrivateReferenceError("Private reference unavailable; see PRIVATE_ARTIFACTS.md") from error
    return path


if __name__ == "__main__":
    try:
        require_reference()
    except PrivateReferenceError as error:
        print("PROVISIONING_ERROR: " + str(error), file=sys.stderr)
        sys.exit(78)
