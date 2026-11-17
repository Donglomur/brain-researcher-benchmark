"""Closed captured project-module loader, no ambient task import or data access."""
from pathlib import Path
import sys
import types
from regional_custody import read, parsed, need


NUMERICAL = ('reference', 'choice', 'validator', 'worker', 'metric_core', 'score_adapter', 'support', 'census')
TRANSPORT = ('morse_protocol', 'morse_broker', 'morse_docker', 'morse_bootstrap')


def load_group(root, manifest_pin, budget, names):
    """Trusted caller pins the manifest and authorizes this fixed group first."""
    need(tuple(names) in (NUMERICAL, TRANSPORT), 'Fixed source groups only')
    raw = read(root, 'SOURCE_MANIFEST.json', manifest_pin, budget)
    inventory = parsed(raw)
    need(set(inventory) == set(names), 'Exact closed module group')
    bodies = {}
    for name in names:
        row = inventory[name]
        need(row['path'] == name + '.py' and row['bytes'] <= 1048576, 'Fixed ordinary source alias')
        bodies[name] = read(root, row['path'], {k: row[k] for k in ('bytes', 'sha256')}, budget)
    absent = object()
    previous = {name: sys.modules.get(name, absent) for name in names}
    modules = {}
    try:
        for name in names:
            module = types.ModuleType(name)
            module.__file__ = str(Path(root, name + '.py').absolute())
            sys.modules[name] = module
            exec(compile(bodies[name], module.__file__, 'exec'), module.__dict__)
            modules[name] = module
    finally:
        for name, prior in previous.items():
            if prior is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior
    return modules
