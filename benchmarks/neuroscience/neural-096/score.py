#!/usr/bin/env python3
"""Installed-package bridge to the exact local ordinary scorer; no shell."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'authoring/dmfc-timing/context-trajectory-v1/scoring-cli-v1/score.py'
EXPECTED='e14f2c16fc464faabbd860e27b5db14fe29b00d72a615ffacbdda4db761b4676'
if TARGET.is_symlink() or any(p.is_symlink() for p in TARGET.parents):
    raise ValueError('Linked scorer source')
body=TARGET.read_bytes()
if hashlib.sha256(body).hexdigest()!=EXPECTED:
    raise ValueError('Pinned scorer entrypoint changed')
exec(compile(body,str(TARGET),'exec'),{'__name__':'__main__','__file__':str(TARGET)})
