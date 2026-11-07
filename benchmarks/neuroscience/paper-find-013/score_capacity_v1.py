#!/usr/bin/env python3
"""Pinned local PAPER-FIND-013 capacity successor; requires a separate attempt grant."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'authoring/task-capacity-successors-20261102/placefield-ca/score.py'
EXPECTED='1642b6ecd0dceb72b7cfc5ef65132320e95512a5abcac281040fd441058da9a3'
if TARGET.is_symlink() or any(p.is_symlink() for p in TARGET.parents):
    raise ValueError('Linked scorer source')
body=TARGET.read_bytes()
if hashlib.sha256(body).hexdigest()!=EXPECTED:
    raise ValueError('Pinned capacity scorer entrypoint changed')
exec(compile(body,str(TARGET),'exec'),{'__name__':'__main__','__file__':str(TARGET)})
