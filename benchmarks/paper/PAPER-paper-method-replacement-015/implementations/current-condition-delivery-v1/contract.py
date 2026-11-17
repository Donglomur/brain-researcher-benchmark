"""Frozen program and trusted fold bindings for current spinal delivery.

Opaque source sealing adapts the existing spinal program-contract mechanism;
submitted Python is never imported or executed by this operator module.
"""
import hashlib
import builtins
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
CONDITION = 'current_source_noise7_eligible_v1'
ARMS = ('paper_data', 'paper_data_author_code')
PROGRAM_LIMIT = 2_000_000
REUSED = {
    'runtime.py':'ad58d7adc14bf85cf20ef4536e623fc52b576c3e832491861c69fec5d48c1dea',
    'lifecycle.py':'33abb85b74d83e1be4a222a469c106b53ac1d190f03653e0be4c29fd339f39d3',
    'holder.py':'c7dfa37ab8a8f990be5e1098e08676ae2b9a01e415513ffa9e60e0a156a6f32b',
    'entry.py':'f7d9d5fb1ee53bc9ab704a82d96dc175cf76d58de798540978a752392f95b5a9',
    'child.py':'03efb659901d0998ccb737a9af3e844620b9542b53cc4bd17666c8bbe43c872b',
}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes':len(body), 'sha256':hashlib.sha256(body).hexdigest()}


def need(value, message):
    if not value:
        raise ValueError(message)


def name(value):
    need(isinstance(value, str) and 0 < len(value) <= 200, 'bounded relative name')
    p = PurePosixPath(value)
    need(str(p) == value and not p.is_absolute() and '..' not in p.parts
         and all(re.fullmatch(r'[A-Za-z0-9_.-]+', part) for part in p.parts), 'canonical program filename')
    return value


def capture(path, limit):
    path = Path(path)
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary unlinked input')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= limit, 'bounded regular single-link input')
        body = stream.read(before.st_size + 1); after = os.fstat(stream.fileno()); named = path.stat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(body) == before.st_size and all(getattr(before,k) == getattr(after,k) == getattr(named,k) for k in fields), 'stable source capture')
    return body


def source_files(root):
    root = Path(root).absolute()
    need(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)), 'real source directory')
    result = {}; pending = [root]; nodes = 0; total = 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                nodes += 1; need(nodes <= 256 and not entry.is_symlink(), 'bounded source tree without links')
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path); continue
                relative = name(path.relative_to(root).as_posix())
                need(relative != 'config.json' and len(result) < 128, 'reserved configuration and source file limit')
                body = capture(path, PROGRAM_LIMIT - total); total += len(body); result[relative] = body
    need('program.py' in result, 'fixed program.py entrypoint required')
    return dict(sorted(result.items()))


def configuration(arm, purpose, unit):
    need(arm in ARMS and purpose in ('reproduction', 'improvement'), 'explicit arm and purpose')
    need(unit in ('hz', 'expected_spikes_per_bin'), 'explicit candidate output unit')
    return {'schema':'spinal_current_program_config_v1', 'condition_id':CONDITION,
            'arm':arm, 'purpose':purpose, 'output_unit':unit,
            'training_policy':'eligible_same_cohort_except_entire_held_neuron'}


def freeze_pair(program_a, program_b, purpose, unit):
    """Capture both complete source trees BEFORE the caller may build label views."""
    pair = {'schema':'spinal_current_frozen_pair_v1', 'condition_id':CONDITION, 'arms':{}}
    contents = {}
    for arm, root in zip(ARMS, (program_a, program_b)):
        files = source_files(root)
        cfg = configuration(arm, purpose, unit)
        descriptor = {'schema':'spinal_current_program_seal_v1', 'entrypoint':'program.py',
                      'files':[{'path':n, **pin(b)} for n,b in files.items()], 'configuration':cfg}
        descriptor['configuration_pin'] = pin(encoded(cfg))
        pair['arms'][arm] = {'seal':descriptor, 'seal_pin':pin(encoded(descriptor))}
        contents[arm] = files | {'config.json':encoded(cfg)}
    pair['pair_pin'] = pin(encoded({k:v for k,v in pair.items() if k != 'pair_pin'}))
    return pair, contents


def check_pair(pair, contents):
    need(set(pair['arms']) == set(ARMS), 'both programs frozen before any label view')
    need(pair['pair_pin'] == pin(encoded({k:v for k,v in pair.items() if k != 'pair_pin'})), 'immutable pair binding')
    common = set()
    for arm in ARMS:
        entry = pair['arms'][arm]; seal = entry['seal']; cfg = seal['configuration']
        need(entry['seal_pin'] == pin(encoded(seal)), 'immutable program seal')
        need(cfg == configuration(arm, cfg['purpose'], cfg['output_unit']), 'exact arm configuration')
        need(seal['configuration_pin'] == pin(encoded(cfg)), 'immutable configuration')
        expected = {r['path']:{k:r[k] for k in ('bytes','sha256')} for r in seal['files']}
        expected['config.json'] = seal['configuration_pin']
        need({n:pin(b) for n,b in contents[arm].items()} == expected, 'complete frozen program bytes')
        common.add((cfg['purpose'], cfg['output_unit']))
    need(len(common) == 1, 'matched purpose and rate units across access arms')


def fold_binding(pair, arm, manifest, files):
    entry = pair['arms'][arm]
    need(manifest['arm'] == arm and manifest['purpose'] == entry['seal']['configuration']['purpose'], 'fold/program arm match')
    return {'schema':'spinal_current_program_binding_v1', 'condition_id':CONDITION,
            'held_neuron':manifest['held_neuron'], 'arm':arm, 'purpose':manifest['purpose'],
            'output_unit':entry['seal']['configuration']['output_unit'],
            'pair_pin':pair['pair_pin'], 'program_seal':entry['seal_pin'],
            'fold_manifest':pin(files['FOLD.json']),
            'input_files':{n:pin(b) for n,b in sorted(files.items())},
            'query_records':manifest['query_records'],
            'training_policy':'eligible_same_cohort_except_entire_held_neuron',
            'fresh_context_required':True}


def load_reused():
    bodies = {}
    for filename, sha in REUSED.items():
        raw = capture(HERE / 'reused' / filename, 100_000)
        need(pin(raw)['sha256'] == sha, 'exact reviewed reused runtime bytes')
        bodies[filename] = raw
    modules = {}
    ordinary_import = builtins.__import__
    def pinned_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'runtime' and level == 0:
            return modules['runtime']
        return ordinary_import(name, globals, locals, fromlist, level)
    for filename, raw in bodies.items():
        key = filename[:-3]
        module = types.ModuleType('spinal_reused_' + key)
        module.__file__ = str(HERE / 'reused' / filename)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=pinned_import)
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        modules[key] = module
    return modules
