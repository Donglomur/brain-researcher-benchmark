#!/usr/bin/env python3
"""Pinned local NEURAL046 artifact-scoring bridge; no shell or candidate code."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'authoring/reward-dopamine-adaptation-v1/released-fluorescence-cli-v1/score.py'
EXPECTED='968b3091c0432f9e8051aabab362d02e0ad26d2de92fe658c9a7f2d047908036'
if TARGET.is_symlink() or any(p.is_symlink() for p in TARGET.parents):
    raise ValueError('Linked scorer source')
body=TARGET.read_bytes()
if hashlib.sha256(body).hexdigest()!=EXPECTED:
    raise ValueError('Pinned neural scorer entrypoint changed')
exec(compile(body,str(TARGET),'exec'),{'__name__':'__main__','__file__':str(TARGET)})
