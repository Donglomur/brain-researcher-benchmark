#!/usr/bin/env python3
"""Pinned local NEURAL-046 capacity successor; source-only until root installation."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'authoring/task-capacity-successors-20261102/neural046/score.py'
EXPECTED='de28139e91167517032a84c8176f776aad907454b2fb0fc4d8cee197804a2f0a'
if TARGET.is_symlink() or any(p.is_symlink() for p in TARGET.parents):
    raise ValueError('Linked scorer source')
body=TARGET.read_bytes()
if hashlib.sha256(body).hexdigest()!=EXPECTED:
    raise ValueError('Pinned capacity scorer entrypoint changed')
exec(compile(body,str(TARGET),'exec'),{'__name__':'__main__','__file__':str(TARGET)})
