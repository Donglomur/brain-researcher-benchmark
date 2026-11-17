#!/usr/bin/env python3
"""Exact local ACh finished-file scoring bridge; no shell or candidate code."""
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / 'authoring/ach-da-timing-v1/scoring-cli-v1/score.py'
EXPECTED = '134a19aef2cb5e4e0ad4e988ab8ea649122b5592bcfeedc67e2a8537bb5c159e'
if TARGET.is_symlink() or any(p.is_symlink() for p in TARGET.parents):
    raise ValueError('Linked scorer source')
body = TARGET.read_bytes()
if hashlib.sha256(body).hexdigest() != EXPECTED:
    raise ValueError('Pinned scorer entrypoint changed')
exec(compile(body, str(TARGET), 'exec'), {'__name__': '__main__', '__file__': str(TARGET)})
