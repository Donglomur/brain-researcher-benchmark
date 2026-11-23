"""Bind NEURAL-026's matched whole-trial design to aligned session identities.

This operator-only successor consumes existing aligned outputs. It never reads
raw MAT files, fits a model, or runs a participant. Its design operation reads
metadata only; staging reads one private aligned session after full design
validation. Authentication pins must come independently from the operator.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
META_CAP = 1024**2
ARRAY_CAP = 2 * 1024**3
SESSION_KEYS = {'x', 'z', 'y', 'trial_id', 'target'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def backend():
    """Reuse the byte-pinned original protocol and bounded array decoder."""
    path = HERE.parent / 'understanding-metrics-v1' / 'score.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() ==
         'e5e2f21432e6d474cf2a5fb0d92823ee49c790cfd8721b137fd8720d698e22ff',
         'Pinned measured-score loader source')
    spec = importlib.util.spec_from_loader('neural026_preparation_score', loader=None)
    score = importlib.util.module_from_spec(spec)
    score.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), score.__dict__)
    api = score.backend()
    api.score = score
    inventory_path = HERE.parent / 'delivery-source' / 'private' / 'source_inventory.json'
    raw = api.io.capture(inventory_path, META_CAP)
    need(hashlib.sha256(raw).hexdigest() ==
         '7337530c65cd81344228941f966f0eb2c2c8bfee35ac60665640eef03ab4e7e8',
         'Pinned original ten-session source inventory')
    api.inventory = score.decode_metadata(raw)['imaging_assets']
    return api


def valid_hash(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def session_id(asset):
    return f"{asset['mouse']}_{asset['date']}_{asset['area']}"


def descriptor(value, filename, cap):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}
         and value['path'] == filename and type(value['bytes']) is int
         and 0 < value['bytes'] <= cap and valid_hash(value['sha256']),
         'Exact bounded file identity: ' + filename)


def read_pinned(path, expected, api, cap):
    descriptor(expected, Path(path).name, cap)
    body = api.io.capture(path, cap)
    need(api.io.identity(body) == {k: expected[k] for k in ('bytes', 'sha256')},
         'Pinned file bytes: ' + Path(path).name)
    return body


def validate_metadata(metadata, api):
    expected = {session_id(asset): asset for asset in api.inventory}
    need(type(metadata) is dict and set(metadata) == set(expected),
         'Exactly the original ten imaging sessions')
    for cid, asset in expected.items():
        row = metadata[cid]
        need(type(row) is dict and row.get('schema') == 'neural026_aligned_v1'
             and row.get('session') == cid and row.get('source_asset') == asset
             and valid_hash(row.get('source_sha256')),
             'Original source asset, mouse, area and session join: ' + cid)
        descriptor(row.get('aligned'), cid + '.npz', ARRAY_CAP)
        ids, target = row.get('trial_id'), row.get('target')
        need(type(ids) is list and type(target) is list and len(ids) == len(target)
             and 20 <= len(ids) <= 4096
             and all(type(i) is int and 0 < i < 2**63 for i in ids)
             and ids == sorted(set(ids))
             and all(type(t) is int and t in (1, 2) for t in target),
             'Complete chronological trial and LR target roster: ' + cid)


def load_metadata(folder, binding, expected_sha256, api):
    """Capture all metadata under an independently supplied binding hash."""
    manifest = api.score.metadata_pin(binding, expected_sha256, api)
    expected = {session_id(asset) for asset in api.inventory}
    need(type(manifest) is dict and set(manifest) == {'schema', 'sessions'}
         and manifest['schema'] == 'neural026_session_metadata_binding_v1'
         and type(manifest['sessions']) is dict
         and set(manifest['sessions']) == expected,
         'Complete independently pinned metadata binding')
    metadata = {}
    for cid in sorted(expected):
        body = read_pinned(Path(folder) / (cid + '.json'), manifest['sessions'][cid], api, META_CAP)
        metadata[cid] = api.score.decode_metadata(body)
    validate_metadata(metadata, api)
    return metadata


def matched_design(metadata, api):
    """Reconstruct the unchanged first-min, target-stratified ordinal folds."""
    validate_metadata(metadata, api)
    cases = []
    for mouse in api.p.MICE:
        sessions = {asset['area']: session_id(asset) for asset in api.inventory
                    if asset['mouse'] == mouse}
        groups = {}
        for area, cid in sessions.items():
            row = metadata[cid]
            groups[area] = {k: [i for i, t in zip(row['trial_id'], row['target']) if t == k]
                            for k in (1, 2)}
        counts = {k: min(len(groups[a][k]) for a in api.p.AREAS) for k in (1, 2)}
        need(min(counts.values()) >= 10, 'At least ten matched trials per target/area')
        for area in api.p.AREAS:
            cid = sessions[area]
            selected = {k: groups[area][k][:counts[k]] for k in (1, 2)}
            universe = set(selected[1] + selected[2])
            for fold in range(5):
                query = sorted(t for k in (1, 2) for j, t in enumerate(selected[k]) if j % 5 == fold)
                cases.append(dict(case_id=f'{mouse}_{area}_fold{fold}', mouse=mouse,
                    area=area, session=cid, fold=fold, query_id=query,
                    train_id=sorted(universe - set(query)),
                    matched_counts={str(k): counts[k] for k in (1, 2)},
                    aligned=copy.deepcopy(metadata[cid]['aligned'])))
    design = dict(schema='neural026_design_v1', cases=cases)
    api.p.validate_design(design)
    return design


def validate_design(design, metadata, api):
    api.p.validate_design(design)
    expected = matched_design(metadata, api)
    # Retained legacy top-level flags are not scientific evidence. Exact case
    # fields, including aligned pins, must equal metadata-derived identities.
    need(design['cases'] == expected['cases'],
         'Design must equal authentic roster-derived chronological target folds')


def validate_session(values, metadata, api):
    need(type(values) is dict and set(values) == SESSION_KEYS, 'Exact aligned session arrays')
    ids, target = values['trial_id'], values['target']
    n = len(metadata['trial_id'])
    need(ids.dtype.kind in 'iu' and target.dtype.kind in 'iu'
         and ids.shape == target.shape == (n,)
         and np.array_equal(ids, metadata['trial_id'])
         and np.array_equal(target, metadata['target']),
         'Aligned arrays must equal the complete metadata trial/target roster')
    for name, width in (('x', 128), ('z', 141), ('y', 24)):
        value = values[name]
        need(value.dtype.kind == 'f' and value.shape == (n, 51, width)
             and np.isfinite(value).all(), 'Complete finite aligned ' + name)


def stage_case(design, metadata, sessions, case_id, public_output, private_output, api):
    """Stage one unchanged public ABI after validating every design identity."""
    public_output, private_output = Path(public_output), Path(private_output)
    api.io.fresh_output(public_output)
    api.io.fresh_output(private_output)
    public_path, private_path = public_output.resolve(), private_output.resolve()
    need(public_path != private_path and public_path not in private_path.parents
         and private_path not in public_path.parents, 'Distinct nonnested public/private roots')
    session_path = Path(sessions).resolve()
    need(public_path != session_path and public_path not in session_path.parents,
         'Public root cannot contain operator sessions')
    validate_design(design, metadata, api)
    matches = [row for row in design['cases'] if row['case_id'] == case_id]
    need(len(matches) == 1, 'Exact original case ID')
    case = matches[0]
    row = metadata[case['session']]
    raw = read_pinned(Path(sessions) / row['aligned']['path'], row['aligned'], api, ARRAY_CAP)
    values = api.io.arrays(raw, SESSION_KEYS, ARRAY_CAP)
    validate_session(values, row, api)
    lookup = {int(t): i for i, t in enumerate(values['trial_id'])}
    indices = {side: np.array([lookup[t] for t in case[side + '_id']])
               for side in ('train', 'query')}
    public = {side + '_' + dest: values[src][ix] for side, ix in indices.items()
              for src, dest in (('x', 'x'), ('z', 'z'), ('trial_id', 'id'), ('target', 'target'))}
    public['train_y'] = values['y'][indices['train']]
    api.p.validate_packet(public)
    public_output.mkdir(parents=True)
    private_output.mkdir(parents=True)
    np.savez(public_output / 'input.npz', **public)
    np.savez(private_output / 'target.npz', trial_id=public['query_id'],
             y=values['y'][indices['query']])
    api.common.save_json(public_output / 'case.json', dict(schema='neural026_case_v1',
        **{k: case[k] for k in ('case_id', 'mouse', 'area', 'fold', 'train_id', 'query_id')},
        output_file='predictions.npz', output_keys=['trial_id', *api.p.ARMS]))
    api.common.save_json(private_output / 'binding.json', dict(case_id=case_id,
        aligned=copy.deepcopy(row['aligned']), input=api.common.pin(public_output / 'input.npz'),
        target=api.common.pin(private_output / 'target.npz')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('design', 'stage-case'):
        command = commands.add_parser(name)
        command.add_argument('--sessions', required=True, type=Path)
        command.add_argument('--metadata-binding', required=True, type=Path)
        command.add_argument('--metadata-binding-sha256', required=True)
        if name == 'design':
            command.add_argument('--output', required=True, type=Path)
        else:
            command.add_argument('--design', required=True, type=Path)
            command.add_argument('--design-sha256', required=True)
            command.add_argument('--case-id', required=True)
            command.add_argument('--public-output', required=True, type=Path)
            command.add_argument('--private-output', required=True, type=Path)
    args = parser.parse_args(argv)
    api = backend()
    if args.command == 'design':
        api.io.fresh_output(args.output)
    else:
        api.io.fresh_output(args.public_output)
        api.io.fresh_output(args.private_output)
    metadata = load_metadata(args.sessions, args.metadata_binding,
                             args.metadata_binding_sha256, api)
    if args.command == 'design':
        api.common.save_json(args.output, matched_design(metadata, api))
    else:
        design = api.score.metadata_pin(args.design, args.design_sha256, api)
        stage_case(design, metadata, args.sessions, args.case_id,
                   args.public_output, args.private_output, api)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
