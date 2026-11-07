"""Load exact unchanged arithmetic modules without global import-name injection."""
import builtins
import hashlib
import json
from pathlib import Path
import types


def load():
    base = Path(__file__).resolve().parent
    lock = json.loads((base / 'VENDOR_LOCK.json').read_bytes())
    modules = {}
    real_import = builtins.__import__

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in modules:
            return modules[name]
        return real_import(name, globals, locals, fromlist, level)

    for name in ('protocol', 'forward', 'metrics', 'interface', 'score_core'):
        row = lock[name]
        path = base / row['path']
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('changed original arithmetic source')
        module = types.ModuleType('_visual_alpha_spatial_' + name)
        module.__file__ = str(path)
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': imports}
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        modules[name] = module
    return types.SimpleNamespace(**modules)
