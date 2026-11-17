#!/usr/bin/env python3
"""Exact reviewed local paired scorer; copied byte-for-byte into its package."""
from pathlib import Path
import hashlib
import runpy
import stat
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / 'authoring/sleep-eog/investigation-scorer-v2/run_outer.py'
EXPECTED = 'd824ef00c39f84db32481f24102ea128a1f3c2ec2f14766a25061678ef381395'
info = TARGET.lstat()
if any(p.is_symlink() for p in (TARGET, *TARGET.parents)) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 100000:
    raise ValueError('Exact bounded ordinary reviewed scorer source')
if hashlib.sha256(TARGET.read_bytes()).hexdigest() != EXPECTED:
    raise ValueError('Reviewed paired scorer source drift')
runpy.run_path(str(TARGET), run_name='__main__')
