"""Trusted worker entry after exact mandatory external-source verification.

Preparation establishes only current byte possession; native/source/rights and
protected validation gates remain. Use a fresh isolated worker for execution.
"""
from pathlib import Path
import sys
from prepare_upstream import verify_prepared, Refusal
ROOT = Path(__file__).resolve().parent


def run(catalog, plan, output_root, *, limits, upstream_root):
    # All35 exact originals are mandatory before any programme import/effect.
    verify_prepared(upstream_root)
    if any(name == 'kilosort' or name.startswith('kilosort.') for name in sys.modules):
        raise Refusal('fresh worker required: preloaded upstream modules are not verified source')
    previous_path = list(sys.path)
    try:
        sys.path[:0] = [str(Path(upstream_root)), str(ROOT / 'payload'), str(ROOT / 'payload/legacy')]
        from k4programme.controller import Programme
        return Programme(catalog, plan, output_root, limits=limits).run()
    finally:
        sys.path[:] = previous_path
