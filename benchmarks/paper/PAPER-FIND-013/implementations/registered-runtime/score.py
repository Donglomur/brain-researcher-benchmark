#!/usr/bin/env python3
"""Pinned local CA artifact-scoring bridge; no shell or candidate code."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'authoring/paired-placefield-shifts-v1/scorer-cli-v1/score.py'
EXPECTED='9328a6d6abde5c3fb59bc117a15d7a2f5261c47a2621b69ed3f6cf9c818dc080'
if TARGET.is_symlink() or any(p.is_symlink() for p in TARGET.parents):
    raise ValueError('Linked scorer source')
body=TARGET.read_bytes()
if hashlib.sha256(body).hexdigest()!=EXPECTED:
    raise ValueError('Pinned CA scorer entrypoint changed')
exec(compile(body,str(TARGET),'exec'),{'__name__':'__main__','__file__':str(TARGET)})
