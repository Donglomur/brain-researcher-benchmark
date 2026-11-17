#!/usr/bin/env python3
"""Common-CLI bridge for a fixed, actually qualified result-artifact scorer.

No candidate program, empirical payload, Docker or model is invoked. The only
adapter hook verifies the approved reference bytes at the held deferred read.
"""
import os
import sys

# The shared CLI requires argv[1] to be its package-local script. Enter the
# held facade's isolated interpreter mode in this same process before importing
# any path-searchable dependencies; this creates no child process.
if __name__ == '__main__' and (not sys.flags.isolated or not sys.dont_write_bytecode):
    os.execv(sys.executable, [sys.executable, '-I', '-B', __file__, *sys.argv[1:]])

import argparse
import hashlib
from pathlib import Path
import signal
import stat
import types

INSTALLED = 'benchmarks/neuroscience/paper-find-rep-012/score.py'
FACADE = 'authoring/compartment-plasticity-v1/bounded-task-v1/score.py'
FACADE_PIN = (5699, 'a8cad32aeb96b319dbe360c913aea8433840a65d72c8667d48aa52f94269270a')
REFERENCE = 'artifacts-build/compartment-bounded-preparation-001/scientific/private_expected.json'
REFERENCE_PIN = {'bytes':1976, 'sha256':'1f3c61c9286b0e3df7825a10eb878d8711d974a70d38e4a2d0a6dad90004b898'}
INPUT_SHA = 'd5f1d739eb1da61e01c2bb2e510dbd85d1c958f8243bc4b653c087a8c118cb1e'


def need(okay, message):
    if not okay:
        raise ValueError(message)


def trusted_facade(root):
    path = root/FACADE
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked trusted source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == FACADE_PIN[0],
             'Exact ordinary trusted facade extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream: body = stream.read(FACADE_PIN[0]+1)
        after = os.fstat(fd)
        need(all(getattr(before,k)==getattr(after,k) for k in
                 ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
             and (len(body),hashlib.sha256(body).hexdigest()) == FACADE_PIN,
             'Exact stable trusted facade bytes')
    finally:
        os.close(fd)
    module=types.ModuleType('rep012_registered_artifact_facade'); module.__file__=str(path)
    exec(compile(body,str(path),'exec'),module.__dict__)
    original_read=module.read_bounded
    reference=root/REFERENCE
    def approved_read(value, cap):
        # The held main reaches this private read only after candidate admission.
        body,pin=original_read(value,cap)
        if Path(os.path.abspath(value)) == reference:
            need(pin==REFERENCE_PIN,'Approved fixed private reference bytes changed')
        return body,pin
    module.read_bounded=approved_read
    return module


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submission',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    root=Path.cwd().resolve()
    need(Path(__file__).absolute()==root/INSTALLED,'Use the root-installed package-local bridge')
    need(Path(args.submission).resolve() != root/REFERENCE,
         'The private reference cannot be used as a submitted artifact')
    # A scalar scoring attempt has one process and no descendants. A timeout
    # terminates it without a successful result; an opaque temporary may remain.
    signal.signal(signal.SIGALRM,signal.SIG_DFL); signal.alarm(30)
    try:
        facade=trusted_facade(root)
        return facade.main(['--submission',str(Path(args.submission).absolute()),
          '--reference',str(root/REFERENCE),'--input-manifest-sha256',INPUT_SHA,
          '--output',str(Path(args.output).absolute())])
    finally:
        signal.alarm(0)


if __name__=='__main__':
    raise SystemExit(main())
