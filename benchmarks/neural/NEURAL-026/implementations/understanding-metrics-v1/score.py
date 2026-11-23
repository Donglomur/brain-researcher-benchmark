"""Measured-target NEURAL-026 grading with an operator-fixed nuisance reference.

This additive endpoint accepts arbitrary neural predictions. It preserves the
legacy complete support while leaving the legacy reconstruction scorer intact.
No candidate nuisance prediction enters the new primary metric. The trusted
loader is an operator API, never a participant tool; the CLI authenticates its
operator-supplied design and private binding before using the referenced arrays.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
FILE_CAP = 128 * 1024**2
TOTAL_CAP = 2 * 1024**3
NEW_SCHEMA = 'neural026_understanding_submission_v1'
LEGACY_SCHEMA = 'neural026_submission_v1'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def backend():
    """Load only pinned existing protocol/I/O source, restoring module aliases."""
    pins = json.loads((HERE / 'DEPENDENCIES.json').read_text())
    expected = ('protocol', 'common', 'array_io')
    need(tuple(pins) == expected, 'Exact protocol and primitive I/O dependencies')
    captured = {}
    for name in expected:
        item = pins[name]
        path = HERE.parent / 'delivery-source' / item['path']
        need(not path.is_symlink() and path.is_file(), 'Ordinary dependency source')
        body = path.read_bytes()
        need(len(body) == item['bytes'] and hashlib.sha256(body).hexdigest() == item['sha256'],
             'Pinned unchanged dependency source: ' + name)
        captured[name] = (path, body)
    saved = {name: sys.modules.get(name) for name in expected}
    loaded = {}
    try:
        for name in expected:
            path, body = captured[name]
            module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
            module.__file__ = str(path)
            sys.modules[name] = module
            exec(compile(body, str(path), 'exec'), module.__dict__)
            loaded[name] = module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return SimpleNamespace(p=loaded['protocol'], io=loaded['array_io'], common=loaded['common'])


def decode_metadata(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'No duplicate JSON fields')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('Finite JSON constants only')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def metadata_pin(path, expected_sha256, api):
    need(type(expected_sha256) is str and re.fullmatch('[0-9a-f]{64}', expected_sha256),
         'Independent expected metadata SHA256 required')
    body = api.io.capture(path, 1024**2)
    need(hashlib.sha256(body).hexdigest() == expected_sha256, 'Operator metadata checksum')
    return decode_metadata(body)


def flat_path(root, name):
    need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_-]+\.npz', name),
         'Fixed flat NPZ basename')
    return Path(root) / name


def validate_predictions(values, expected_ids, keys):
    need(set(values) == keys, 'Exact declared prediction keys')
    ids = values['trial_id']
    need(ids.dtype.kind in 'iu' and ids.ndim == 1 and np.array_equal(ids, expected_ids),
         'Complete frozen query ID order')
    result = {'trial_id': ids}
    for name in keys - {'trial_id'}:
        a = values[name]
        need(a.dtype.kind == 'f' and a.dtype.itemsize in (4, 8)
             and a.shape == (len(ids), 51, 24) and np.isfinite(a).all(),
             'Complete finite 24-joint prediction arrays')
        result[name] = a.astype(np.float64, copy=False)
    return result


def admit_submission(folder, design, api):
    """Admit all 50 complete outputs before any trusted target callback."""
    api.p.validate_design(design)
    folder = Path(folder)
    manifest = decode_metadata(api.io.capture(folder / 'submission.json', 1024**2))
    need(type(manifest) is dict and set(manifest) == {'schema', 'cases'}
         and manifest['schema'] in (NEW_SCHEMA, LEGACY_SCHEMA)
         and type(manifest['cases']) is list and len(manifest['cases']) == 50,
         'Exact complete prediction submission')
    keys = {'trial_id', 'neural'} if manifest['schema'] == NEW_SCHEMA else {'trial_id', *api.p.ARMS}
    need({f.name for f in folder.iterdir()} == {'submission.json', *[c + '.npz' for c in api.p.case_ids()]},
         'All 50 case files and no extra artifacts')
    admitted, total = {}, 0
    for row, case in zip(manifest['cases'], design['cases'], strict=True):
        cid = case['case_id']
        need(type(row) is dict and set(row) == {'case_id', 'file', 'bytes', 'sha256'}
             and row['case_id'] == cid and row['file'] == cid + '.npz'
             and type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
             and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
             'Exact typed case identity and descriptor')
        raw = api.io.capture(flat_path(folder, row['file']), FILE_CAP)
        ident = api.io.identity(raw)
        need(ident == {k: row[k] for k in ('bytes', 'sha256')}, 'Candidate bytes authenticate')
        total += ident['bytes']
        need(total <= TOTAL_CAP, 'Aggregate candidate cap')
        validate_predictions(api.io.arrays(raw, keys, FILE_CAP), case['query_id'], keys)
        admitted[cid] = ident
    return manifest['schema'], keys, admitted


def validate_target(target, expected_ids):
    need(type(target) is dict and set(target) == {'trial_id', 'y'}, 'Exact private target fields')
    ids, y = target['trial_id'], target['y']
    need(ids.dtype.kind in 'iu' and ids.ndim == 1 and np.array_equal(ids, expected_ids),
         'Exact target query IDs')
    need(y.dtype.kind == 'f' and y.dtype.itemsize in (4, 8)
         and y.shape == (len(ids), 51, 24) and np.isfinite(y).all(),
         'Complete finite private joint targets')
    return y.astype(np.float64, copy=False)


def moments_add(state, y):
    """Stable pooled moments; five folds form one session, not five replicates."""
    a = y.reshape(-1, 24)
    n, mean = len(a), a.mean(axis=0)
    m2 = np.square(a - mean).sum(axis=0)
    if state is None:
        return n, mean, m2
    old, mu, s = state
    delta = mean - mu
    return old+n, mu+delta*(n/(old+n)), s+m2+np.square(delta)*old*n/(old+n)


@np.errstate(over='raise', under='raise', invalid='raise', divide='raise')
def evaluate(folder, design, trusted_private_loader, *, expected_admission=None):
    """Grade complete measured predictions, using an operator-only private loader.

    The loader returns (target, reference) for each fixed case; reference must
    contain independently committed nuisance/neural/shifted arrays. This Python
    API assumes a trusted caller. Use the CLI to enforce exact external bindings.
    A paired operator may supply the tuple returned by admit_submission as
    expected_admission, fixing the complete candidate before any protected read.
    """
    api = backend()
    schema, keys, admitted = admit_submission(folder, design, api)
    if expected_admission is not None:
        need((schema, keys, admitted) == expected_admission,
             "Candidate unchanged since paired complete admission")
    cells = {}
    for case in design['cases']:
        cid = case['case_id']
        raw = api.io.capture(flat_path(folder, cid + '.npz'), FILE_CAP)
        need(api.io.identity(raw) == admitted[cid], 'Candidate unchanged after complete admission')
        candidate = validate_predictions(api.io.arrays(raw, keys, FILE_CAP), case['query_id'], keys)
        target, reference = trusted_private_loader(cid)
        y = validate_target(target, case['query_id'])
        reference = validate_predictions(reference, case['query_id'], {'trial_id', *api.p.ARMS})
        cell = cells.setdefault((case['mouse'], case['area']), {
            'moments': None, 'candidate_sse': np.zeros(24),
            'reference_sse': {arm: np.zeros(24) for arm in api.p.ARMS}, 'cases': 0})
        cell['moments'] = moments_add(cell['moments'], y)
        cell['candidate_sse'] += np.square(candidate['neural'] - y).sum(axis=(0, 1))
        for arm in api.p.ARMS:
            cell['reference_sse'][arm] += np.square(reference[arm] - y).sum(axis=(0, 1))
        cell['cases'] += 1
    detail, effects = [], {}
    for mouse in api.p.MICE:
        for area in api.p.AREAS:
            cell = cells[mouse, area]
            n, _, sst = cell['moments']
            need(cell['cases'] == 5 and np.isfinite(sst).all() and (sst > 0).all(),
                 'All five folds and positive pooled variance for every joint; no target dropping')
            c_sse, r_sse = cell['candidate_sse'], cell['reference_sse']
            effect = (r_sse['nuisance'] - c_sse) / sst
            fixed_effect = (r_sse['nuisance'] - r_sse['neural']) / sst
            shifted_effect = (r_sse['shifted'] - c_sse) / sst
            metrics = [effect, fixed_effect, shifted_effect, c_sse/n,
                       *[value/n for value in r_sse.values()]]
            need(all(np.isfinite(value).all() for value in metrics), 'Finite score arithmetic')
            effects[mouse, area] = effect
            detail.append(dict(mouse=mouse, area=area, complete_folds=5, query_samples=n,
                joint_incremental_ev=effect.tolist(), candidate_joint_mse=(c_sse/n).tolist(),
                candidate_joint_sse=c_sse.tolist(), pooled_target_joint_sst=sst.tolist(),
                fixed_nuisance_joint_mse=(r_sse['nuisance']/n).tolist(),
                fixed_neural_joint_mse=(r_sse['neural']/n).tolist(),
                fixed_shifted_joint_mse=(r_sse['shifted']/n).tolist(),
                fixed_neural_joint_incremental_ev=fixed_effect.tolist(),
                candidate_minus_fixed_neural_incremental_ev=(effect-fixed_effect).tolist(),
                candidate_over_fixed_shifted_incremental_ev=shifted_effect.tolist(),
                candidate_joint_r2=(1-c_sse/sst).tolist(),
                fixed_nuisance_joint_r2=(1-r_sse['nuisance']/sst).tolist()))
    per_mouse = [dict(mouse=m,
        incremental_ev=float(np.mean([effects[m, a] for a in api.p.AREAS])),
        S1_minus_M1=float(np.mean(effects[m, 'S1']-effects[m, 'M1']))) for m in api.p.MICE]
    value = float(np.mean([row['incremental_ev'] for row in per_mouse]))
    need(np.isfinite(value), 'Finite equal-mouse primary')
    return dict(schema='neural026_understanding_grade_v1', candidate_schema=schema,
        complete_cases=50, independent_mice=5, areas_per_mouse=2, joints_per_area=24,
        primary_metric='equal_mouse_area_joint_fixed_nuisance_incremental_EV',
        primary_value=value, direction='higher', biological_effects=detail, per_mouse=per_mouse,
        comparator='operator_committed_reference_nuisance_predictions',
        candidate_nuisance_used=False, candidate_shifted_used=False,
        paired_area_difference=float(np.mean([row['S1_minus_M1'] for row in per_mouse])),
        inference='descriptive; no interval, significance, causal or source-paper improvement claim',
        neural_dependence_established=False,
        neural_dependence_requirement='Separately matched candidate context-only and neural-disruption '
            'ablations; gain over a fixed nuisance learner alone cannot identify neural dependence.',
        arbitrary_neural_method_allowed=True, candidate_execution_verified=False,
        input_isolation_verified=False, authentic_inputs_verified=False,
        scientific_qualification=False, binary_pass=None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('submission', 'design', 'private-root', 'binding', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--design-sha256', required=True)
    parser.add_argument('--binding-sha256', required=True)
    args = parser.parse_args(argv)
    api = backend()
    api.io.fresh_output(args.output)
    design = metadata_pin(args.design, args.design_sha256, api)
    binding = metadata_pin(args.binding, args.binding_sha256, api)
    need(type(binding) is dict and binding.get('schema') == 'neural026_private_binding_v1'
         and type(binding.get('cases')) is dict and set(binding['cases']) == set(api.p.case_ids()),
         'All independently committed targets and fixed reference predictions')
    def loader(cid):
        result = []
        for role, expected in (('target', {'trial_id', 'y'}), ('reference', {'trial_id', *api.p.ARMS})):
            row = binding['cases'][cid][role]
            need(type(row) is dict and {'file', 'bytes', 'sha256'} <= set(row)
                 and type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
                 and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                 'Typed trusted array identity')
            raw = api.io.capture(flat_path(args.private_root, row['file']), FILE_CAP)
            need(api.io.identity(raw) == {k: row[k] for k in ('bytes', 'sha256')},
                 'Independently pinned private array')
            result.append(api.io.arrays(raw, expected, FILE_CAP))
        return result
    grade = evaluate(args.submission, design, loader)
    grade['operator_design_sha256'] = args.design_sha256
    grade['operator_binding_sha256'] = args.binding_sha256
    api.common.save_json(args.output, grade)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
