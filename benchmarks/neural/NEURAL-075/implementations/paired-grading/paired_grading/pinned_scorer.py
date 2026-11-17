"""Load the unchanged selected scorer functions from authenticated source bytes.

No candidate module is imported. There is no fallback scorer, data acquisition,
fit, native worker invocation or reinterpretation of the original metric.
"""
import ast
import hashlib
import io
import math
import re
import stat
import types
import zipfile
from pathlib import Path

EXPORT = 'authoring/delivery-20261105/common/exports/neural075'
PINS = {
    'private/score.py': (7695, 'a9a68f879ce6252754dcee35b297caa807337883d7ee02ed5adf7e58bf388473'),
    'private/scorer_core.py': (1720, 'd9858b825e02b2412819e79a4619c5436ba4c114a62bf4ba1358386803bf3822'),
    'public/protocol.py': (522, '3dce0781f06a10b5ebb33e99e2e0580d752e5262857bd4550df821223a449ea9'),
    'public/delivery_io.py': (4396, '9ba54409ff3aae8e17d2c0e96f1c5f335fa46cd33aeaf83d3be427a8ebf585d7'),
    'public/array_io.py': (3519, '0b0b0977dad0d65817e9da346554901ebe2032526600c27fc195c9e5cc736602'),
}


def _selected(raw, names, namespace, filename):
    tree = ast.parse(raw, filename=filename)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))
             and ((isinstance(n, ast.FunctionDef) and n.name in names)
                  or (isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in names for t in n.targets)))]
    found = {n.name if isinstance(n, ast.FunctionDef) else t.id for n in nodes
             for t in ([None] if isinstance(n, ast.FunctionDef) else n.targets)}
    if found != set(names):
        raise ValueError('Exact selected incumbent declarations required')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)


def load_scorer(repository, reader):
    """Source pins are fixed; reader is a trusted bounded ordinary-source reader."""
    import numpy as np
    bodies = {}
    for name, (size, sha) in PINS.items():
        bodies[name] = reader.read(str(Path(repository) / EXPORT / name),
                                   {'bytes': size, 'sha256': sha}, 2**20)
    return scorer_from_sources(bodies, np)


def scorer_from_sources(bodies, np):
    """Same fixed authentication for retained source used by invented controls."""
    if set(bodies) != set(PINS):
        raise ValueError('Exact scorer source set')
    for name, (size, sha) in PINS.items():
        raw = bodies[name]
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Changed original scorer source: ' + name)
    ns = {'np': np, 're': re, 'io': io, 'zipfile': zipfile, 'stat': stat, 'math': math}
    _selected(bodies['public/delivery_io.py'], {'need', 'exact'}, ns, 'pinned/delivery_io.py')
    _selected(bodies['public/protocol.py'],
              {'VERSION', 'PEOPLE', 'ARMS', 'PHASES', 'ROWS', 'REPEATS', 'N_CATEGORY', 'ROI', 'FEATURE', 'SCORE_CAP', 'case_ids'},
              ns, 'pinned/protocol.py')
    _selected(bodies['public/array_io.py'], {'arrays'}, ns, 'pinned/array_io.py')
    _selected(bodies['private/scorer_core.py'], {'metrics', 'summarize'}, ns, 'pinned/scorer_core.py')
    _selected(bodies['private/score.py'], {'admit', 'evaluate'}, ns, 'pinned/score.py')
    ns['source_pins'] = {name: {'bytes': p[0], 'sha256': p[1]} for name, p in PINS.items()}
    return types.SimpleNamespace(**ns)
