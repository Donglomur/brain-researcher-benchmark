"""Task-scoped, source-frozen trusted controllers; never candidate code.

Derived from ownership-v4/trusted_controller.py. Descriptors bind source identity,
not scientific execution permission. The public launch accepts controller.py only.
The separate generated-control route accepts the fixed trusted_fixture.py only.
"""
from pathlib import Path
import hashlib
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PREFIX = 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-owner-v1/'


def validate_controller(value, argv, check_bytes=True, *, fixture=False):
    if type(value) is not dict or set(value) != {'path', 'bytes', 'sha256'}:
        raise ValueError('Exact trusted controller descriptor')
    wanted = PREFIX + ('trusted_fixture.py' if fixture else 'controller.py')
    size, sha = value['bytes'], value['sha256']
    if value['path'] != wanted or type(size) is not int or not 1 <= size <= 262144:
        raise ValueError('Only the fixed task controller for this launch mode')
    if type(sha) is not str or re.fullmatch('[a-f0-9]{64}', sha) is None:
        raise ValueError('Exact trusted controller hash')
    path = ROOT / wanted
    if (type(argv) is not list or len(argv) < 6
            or not all(type(x) is str and not any(c in x for c in ('\0', '\n', '\r')) for x in argv)
            or argv[:4] != [sys.executable, '-I', '-B', str(path)]):
        raise ValueError('Exact Python and fixed trusted controller argv')
    if check_bytes:
        if any(x.is_symlink() for x in (path, *path.parents)):
            raise ValueError('No linked trusted controller')
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise ValueError('Exact ordinary single-link controller')
        raw = path.read_bytes()
        after = path.stat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if (len(raw) != size or hashlib.sha256(raw).hexdigest() != sha
                or any(getattr(before, key) != getattr(after, key) for key in fields)):
            raise ValueError('Trusted controller changed')
    return path


def fixture_descriptor():
    """Fixed tiny software-control source, never an arbitrary programme."""
    raw = (HERE / 'trusted_fixture.py').read_bytes()
    return {'path': PREFIX + 'trusted_fixture.py', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}
