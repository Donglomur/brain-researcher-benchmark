"""Authenticate fixed source, then defer imports to an admitted native operation."""
import ast
import copy
import importlib
import importlib.metadata
import json
import types
from pathlib import Path
from .schedule import need
from .storage import pin

EXPECTED_BINDING = {'bytes': 5552, 'sha256': '7563ffd66b97973a4b32a49a301d586ea6844e957dec62975a5b1ea4d007f485'}


def capture(admission, session):
    local = Path(__file__).parent / 'SOURCES.json'
    raw = session.read(local, EXPECTED_BINDING, source=True); doc = json.loads(raw)
    need(admission['source_binding'] == EXPECTED_BINDING, 'externally bound exact source manifest')
    root = Path(admission['source_root']); need(root.is_absolute(), 'absolute captured source root')
    bodies = {}
    for row in doc['files']:
        bodies[row.get('installed_relative', row.get('role'))] = session.read(root/row['path'], row, source=True)
    return doc, bodies


def load_native(admission, session, doc, bodies):
    need(importlib.metadata.version('hmp') == '1.0.0b2', 'exact source HMP release')
    versions = admission['environment']['package_versions']
    for name in ('numpy', 'scipy', 'pandas', 'xarray', 'scikit-learn', 'hmp', 'mne'):
        need(type(versions.get(name)) is str and importlib.metadata.version(name) == versions[name], 'selected package version: ' + name)
    distribution = importlib.metadata.distribution('hmp')
    for row in doc['files']:
        if 'installed_relative' in row:
            installed = Path(distribution.locate_file(row['installed_relative']))
            session.read(installed, row, source=True)
    session.tick(); hmp = importlib.import_module('hmp'); np = importlib.import_module('numpy'); session.tick()
    return hmp, np


def contract_module(name, raw, protocol=None):
    tree = ast.parse(raw)
    if protocol is not None:
        found = [n for n in tree.body if isinstance(n, ast.Import) and len(n.names) == 1 and n.names[0].name == 'protocol' and n.names[0].asname == 'p']
        need(len(found) == 1, 'exact local protocol import substitution')
        tree.body.remove(found[0])
    module = types.ModuleType(name)
    if protocol is not None: module.p = protocol
    exec(compile(tree, '<source-authenticated:'+name+'>', 'exec'), module.__dict__)
    return module


def function_tree(raw, name):
    tree = ast.parse(raw)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EventModel')
    func = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name))
    func.returns = None
    for arg in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs): arg.annotation = None
    return func


def mass_function(raw, np):
    """Retain source operations; add extraction at the pre-log/pre-division boundary."""
    func = function_tree(raw, 'estim_probs')
    matches = [i for i,n in enumerate(func.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'likelihood' for t in n.targets)]
    need(len(matches) == 1, 'one source likelihood boundary')
    insertion = ast.parse('trial_masses = eventprobs[:, :, 0].sum(axis=0).copy()\nevent_normalizers = eventprobs.sum(axis=0).copy()').body
    func.body[matches[0]:matches[0]] = insertion
    need(isinstance(func.body[-1], ast.Return) and ast.unparse(func.body[-1].value) == '[likelihood, eventprobs]', 'exact source return boundary')
    func.body[-1].value.elts += [ast.Name(id='trial_masses', ctx=ast.Load()), ast.Name(id='event_normalizers', ctx=ast.Load())]
    tree = ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])); space = {'np': np}
    exec(compile(tree, '<source-authenticated-mass-extraction>', 'exec'), space)
    return space['estim_probs']


def traced_em(raw, np, warn):
    func = function_tree(raw, 'EM')
    initial = [i for i,n in enumerate(func.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'lkh_prev' for t in n.targets)]
    need(len(initial) == 1, 'one original EM initial trace')
    hook = ast.parse('self._retain_em(i, lkh, channel_pars, time_pars)').body[0]
    func.body.insert(initial[0] + 1, copy.deepcopy(hook))
    loop = next(n for n in func.body if isinstance(n, ast.While))
    need(isinstance(loop.body[-1], ast.AugAssign) and ast.unparse(loop.body[-1]) == 'i += 1', 'exact EM update boundary')
    loop.body.append(copy.deepcopy(hook))
    tree = ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])); space = {'np': np, 'warn': warn}
    exec(compile(tree, '<source-authenticated-retained-EM>', 'exec'), space)
    return space['EM']
