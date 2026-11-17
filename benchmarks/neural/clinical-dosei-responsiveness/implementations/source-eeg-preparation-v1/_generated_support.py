"""Load the pinned archived guard for generated controls, without native admission.

Importing this module reads only sibling Python source. It never instantiates
GuardContext, opens a scientific input, or calls the archived producer CLI.
"""
import hashlib
from pathlib import Path
import sys
import types


HERE = Path(__file__).resolve().parent
GUARDS_SHA256 = '3ab7bf7d4e13818be3812391b0482e19f7e544b1908c62b2cf743d60925109cb'


def load_guard():
    path = HERE / 'archived-source' / 'eeg_guards.py'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != GUARDS_SHA256:
        raise ValueError('archived guard source hash differs')
    module = types.ModuleType('dosei_generated_archived_guards')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


guards = load_guard()
