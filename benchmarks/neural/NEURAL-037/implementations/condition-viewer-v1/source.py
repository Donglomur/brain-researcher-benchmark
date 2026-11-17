"""Task-local captured dependency loading and fixed original case metadata."""
import builtins
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).absolute().parent
REPOSITORY = HERE.parents[4]


def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def captured(path, expected):
    # Bootstrap files are operator-controlled, stable source, not a sandbox.
    raw = path.read_bytes()
    if identity(raw) != expected:
        raise ValueError('Selected source bytes changed')
    return raw


def load():
    manifest_raw = (HERE / 'SOURCE_BINDINGS.json').read_bytes()
    manifest = json.loads(manifest_raw)
    modules = {}
    local_bodies = {name: captured(HERE / name, pin) for name, pin in manifest['local_implementation'].items()}
    real_import = builtins.__import__

    def importer(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name + '.py' in local_bodies and name not in modules:
            local(name)
        return modules[name] if level == 0 and name in modules else real_import(name, globals, locals, fromlist, level)

    def local(name):
        if name in modules:
            return modules[name]
        if name not in ('viewer', 'render', 'broker', 'collect'):
            raise ValueError('Only selected active task modules')
        module = types.ModuleType('_neural037_local_' + name)
        module.__file__ = str(HERE / (name + '.py'))
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': importer}
        modules[name] = module
        exec(compile(local_bodies[name + '.py'], module.__file__, 'exec'), module.__dict__)
        return module

    for name in ('delivery_io', 'array_io', 'scorer_core'):
        row = manifest['accepted_dependencies'][name]
        raw = captured(REPOSITORY / row['path'], row['pin'])
        module = types.ModuleType('_neural037_viewer_' + name)
        module.__file__ = str(REPOSITORY / row['path'])
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': importer}
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        modules[name] = module
    io = modules['delivery_io']
    originals = {name: captured(HERE / name, pin) for name, pin in manifest['original_metadata'].items()}
    lock = io.decode(originals['source/LOCK.json'])
    panel = io.decode(originals['source/PANEL.json'])
    modules['scorer_core'].public_contract(panel)
    io.need(lock['packet_id'] == panel['packet_id'] and
            lock['contexts'] == [x['context_id'] for x in panel['contexts']], 'Same original panel and lock')
    modules['io_guard'] = types.SimpleNamespace(need=io.need,
        parse=lambda value: io.decode(value.encode('utf-8') if isinstance(value, str) else value))
    contract = types.ModuleType('_neural037_original_context_contract')
    contract.__dict__['__builtins__'] = {**vars(builtins), '__import__': importer}
    exec(compile(originals['source/context_contract.py'], 'source/context_contract.py', 'exec'), contract.__dict__)
    instructions = captured(HERE / 'INSTRUCTIONS.md', manifest['instructions'])
    bundle = types.SimpleNamespace(io=io, array=modules['array_io'], core=modules['scorer_core'],
        contract=contract, lock=lock, panel=panel, instructions=instructions.decode('utf-8'),
        instructions_pin=identity(instructions), source_binding=identity(manifest_raw), local=local)
    modules['source'] = types.SimpleNamespace(load=lambda: bundle, selected_rows=selected_rows,
                                             HERE=HERE, REPOSITORY=REPOSITORY)
    return bundle


def selected_rows(bundle, context_id):
    io = bundle.io
    io.need(context_id in bundle.lock['contexts'], 'Original context identity')
    index = bundle.lock['contexts'].index(context_id)
    rows = [r for r in bundle.lock['files'] if r['fold'] is None or r['fold'] == index]
    io.need(len(rows) == 32 and len({r['target'] for r in rows}) == 32, 'Complete original selected view')
    return index, rows
