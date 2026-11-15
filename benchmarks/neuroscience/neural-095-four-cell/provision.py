"""Provision the exact original DMFC packets from a retained pinned NWB.

Trusted offline conversion only. No download, candidate execution or model fit.
An operator must supply the three existing fixed-reference metadata operands.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

HERE = Path(__file__).absolute().parent
SUPPORT = HERE / 'provision_support'
MAX_OUTPUT_BYTES = 4 * 1024**2
DATA_NOTICE = '''DMFC_RSG: macaque dorsomedial frontal cortex spiking activity during time interval reproduction task
Sohn, Hansem; Jazayeri, Mehrdad (2024).
DANDI 000130, version 0.241017.1448; https://doi.org/10.48324/dandi.000130/0.241017.1448
Data license: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
Associated paper: https://doi.org/10.1016/j.neuron.2019.06.012

Derived packet changes: retain all original 748 TRAIN and 258 validation trials;
sort each split stably by Set time; retain all 40 source held-in units in source
order; bin [Set-0.2 seconds, Set) into four half-open 50 ms bins; retain released
behavioral tp in milliseconds, cues and elapsed session clock; use five fixed
chronological TRAIN folds; omit counts in the paired cue-only projection.
No target/outlier filtering, new reference fitting or source-code redistribution
from the original paper repository is performed by this converter.
Query targets and reference metadata are evaluator-only operands, not candidate
inputs. These are historical public development data, not a secret test set.
'''
SUPPORT_PINS = {
    'convert.py': (10697, '7cf3a36d0bd3a2ba7a52e05b9ad5fecf0d38d765de09d0e000bcae956086e0f9'),
    'core.py': (5344, '0a8af5db1b66531af00a5625d233506bc654ca6c392fb4789b15ab862bb86a2e'),
    'project.py': (3826, '873bdf5fe17c498923471aaa5b2948a849f4c3fa080e79aa796bdeff858bf481'),
    'contract.json': (5194, 'eb332e622e352c72014fbefdaf283c6ad313a90730c2ea110a49a8fbcfcdcb64'),
    'expected.json': (3298, 'e2aa37b8e3237b15da0f33fd36595a21f0ba309628b3064eb3426ac7da93ee1c'),
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink)


def ordinary(path, cap):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked file and ancestors required')
    st = path.stat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and 0 < st.st_size <= cap, 'Bounded ordinary file required')
    return path, st


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def capture(path, expected):
    need(set(expected) == {'bytes', 'sha256'} and type(expected['bytes']) is int
         and 0 < expected['bytes'] <= 1000000, 'Bounded immutable operand descriptor')
    path, before = ordinary(path, expected['bytes'])
    with path.open('rb') as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), 'Operand changed before capture')
        body = stream.read(expected['bytes'] + 1)
        need(identity(os.fstat(stream.fileno())) == identity(before), 'Operand changed during capture')
    need(all(not p.is_symlink() for p in (path, *path.parents))
         and identity(path.stat()) == identity(before) and pin(body) == expected, 'Exact stable operand required')
    return body


def decode(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def bad(value):
        raise ValueError('Nonfinite JSON')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def save(path, body, mode=0o444):
    need(type(body) is bytes and len(body) <= 1000000, 'Bounded output body')
    with path.open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    path.chmod(mode)


def captured_module(name, filename, source):
    need(name not in sys.modules, 'Fresh trusted converter module namespace')
    module = types.ModuleType(name); module.__file__ = str(filename)
    sys.modules[name] = module
    try:
        exec(compile(source, str(filename), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def project_views(project, original, contract):
    train, unused = project.members(original['train.npz'], project.TRAIN | {'counts'}, 748)
    query, unused = project.members(original['query.npz'], project.COMMON | {'counts'}, 258)
    cue_train, cue_query = project.cue_archive(train), project.cue_archive(query)
    common_schema = decode(original['schema.json'])
    need(common_schema['train_n'] == 748 and common_schema['query_n'] == 258 and
         set(common_schema['public_keys']['train']) == project.TRAIN | {'counts'} and
         set(common_schema['public_keys']['query']) == project.COMMON | {'counts'}, 'Exact complete source schema')
    schemas = {}
    for arm in ('cue_only', 'neural'):
        obj = dict(common_schema)
        obj['paired_observation_view'] = arm
        obj['public_keys'] = {'train': sorted(project.TRAIN | ({'counts'} if arm == 'neural' else set())),
                              'query': sorted(project.COMMON | ({'counts'} if arm == 'neural' else set()))}
        obj['counts_available'] = arm == 'neural'
        obj['scope'] = 'Retrospective public single-session development; matched-procedure claims require review.'
        schemas[arm] = (json.dumps(obj, sort_keys=True, indent=2) + '\n').encode()
    for body, source, fields, n in ((cue_train, train, project.TRAIN, 748),
                                    (cue_query, query, project.COMMON, 258)):
        actual, unused = project.members(body, fields, n)
        need(all(actual[k] == source[k] for k in fields), 'Exact common NPY bytes; no casting, filtering or reordering')
    outputs = {}
    for view in ('cue_only', 'neural'):
        outputs[view + '/train.npz'] = cue_train if view == 'cue_only' else original['train.npz']
        outputs[view + '/query.npz'] = cue_query if view == 'cue_only' else original['query.npz']
        outputs[view + '/schema.json'] = schemas[view]
        outputs[view + '/units.json'] = original['units.json']
        outputs[view + '/contract.json'] = contract
    return outputs


def provision(source, out, reference_paths):
    started = time.monotonic()
    sources = {name: capture(SUPPORT / name, {'bytes': size, 'sha256': sha})
               for name, (size, sha) in SUPPORT_PINS.items()}
    expected = decode(sources['expected.json'])
    need(set(reference_paths) == set(expected['references']), 'Exactly three existing reference operands required')
    references = {name: capture(reference_paths[name], descriptor)
                  for name, descriptor in expected['references'].items()}
    source, before = ordinary(source, expected['source']['bytes'])
    need(before.st_size == expected['source']['bytes'], 'Exact source size; converter authenticates full source SHA')
    out = Path(out).absolute()
    need(not out.exists() and out.parent.is_dir() and all(not p.is_symlink() for p in (out, *out.parents)),
         'Fresh ordinary output directory; no automatic retry or overwrite')
    fixed_bytes = sum(p['bytes'] for p in expected['base_packet'].values()) + sum(p['bytes'] for p in expected['views'].values())
    need(fixed_bytes + sum(len(b) for b in references.values()) + 250000 < MAX_OUTPUT_BYTES, 'Whole fixed output reserve')
    project = captured_module('_dmfc_exact_view_projection', SUPPORT / 'project.py', sources['project.py'])
    captured_module('core', SUPPORT / 'core.py', sources['core.py'])
    converter = captured_module('_dmfc_exact_converter', SUPPORT / 'convert.py', sources['convert.py'])
    out.mkdir(mode=0o700)
    old_argv = sys.argv
    try:
        sys.argv = [str(SUPPORT / 'convert.py'), '--source', str(source), '--out', str(out / 'packet')]
        converter.main()
    finally:
        sys.argv = old_argv
    need(all(not p.is_symlink() for p in (source, *source.parents))
         and identity(source.stat()) == identity(before), 'Pinned source identity unchanged throughout conversion')
    base = {name: capture(out / 'packet' / name, descriptor) for name, descriptor in expected['base_packet'].items()}
    original = {name: base['public/' + name] for name in ('train.npz', 'query.npz', 'schema.json', 'units.json')}
    views = project_views(project, original, sources['contract.json'])
    need(set(views) == set(expected['views']) and all(pin(body) == expected['views'][name] for name, body in views.items()),
         'All ten complete view artifacts exactly equal registered originals')
    (out / 'views').mkdir(mode=0o700)
    for view in ('cue_only', 'neural'):
        (out / 'views' / view).mkdir(mode=0o755)
    for name, body in views.items(): save(out / 'views' / name, body)
    (out / 'evaluator').mkdir(mode=0o700)
    evaluator = {**references, 'public_identity.json': base['public_identity.json'],
                 'query_targets.npz': base['private/query_targets.npz']}
    for name, body in evaluator.items(): save(out / 'evaluator' / name, body, mode=0o400)
    save(out / 'DATA_NOTICE.md', DATA_NOTICE.encode())
    # Only this freshly owned, finite tree is inventoried; never traverse input parents.
    files = [p for p in out.rglob('*') if p.is_file()]
    need(len(files) == 24 and all(not p.is_symlink() for p in out.rglob('*'))
         and sum(p.stat().st_size for p in files) + 10000 < MAX_OUTPUT_BYTES, 'Complete bounded provisioned tree')
    receipt = {'schema': 'dmfc-portable-provisioning-receipt/v1', 'status': 'complete_exact_packet_and_view_parity',
        'candidate_id': 'NEURAL-095', 'source': expected['source'], 'base_packet': expected['base_packet'],
        'views': expected['views'], 'evaluator': {name: pin(body) for name, body in evaluator.items()},
        'train_cases': 748, 'query_cases': 258, 'heldin_units': 40, 'pre_Set_bins': 4,
        'new_candidate_fits': 0, 'new_reference_fits': 0, 'original_scientific_endpoint_changed': False,
        'candidate_execution_or_scoring_performed': False, 'elapsed_seconds': time.monotonic() - started}
    save(out / 'PROVISIONING_RECEIPT.json', (json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode(), mode=0o400)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    for name in ('reference-grade', 'reference-commit', 'reference-audit'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = provision(args.source, args.out, {name + '.json': getattr(args, name)
                       for name in ('reference_grade', 'reference_commit', 'reference_audit')})
    print(json.dumps({'status': result['status'], 'candidate_id': 'NEURAL-095',
                      'train_cases': 748, 'query_cases': 258, 'new_fits': 0}))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
