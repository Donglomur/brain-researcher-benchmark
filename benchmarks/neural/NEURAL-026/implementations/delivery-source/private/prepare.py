"""Deterministic operator preparation; never fit, predict, or score models.

Original neural files are absent from this delivery. These commands are a
prospective recipe, not evidence that any dataset or case has been prepared.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import numpy as np
import h5py

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'public'))
import protocol as p
import portable_export as donor
import portable_alignment as align
from common import SESSIONS, context_id, need, json_load, save_json, pin, npz_load

SESSION_KEYS = {'x', 'z', 'y', 'trial_id', 'target'}
PUBLIC_KEYS = {'train_x', 'train_z', 'train_y', 'train_id', 'train_target',
               'query_x', 'query_z', 'query_id', 'query_target'}


def same_pin(path, expected):
    need(set(expected) == {'path', 'bytes', 'sha256'} and expected['path'] == Path(path).name,
         'Exact selected basename and complete identity')
    need(pin(path) == expected and not Path(path).is_symlink(), 'Exact authenticated source file')


class Reader(donor.Mat73):
    """Same bounded reader; only additional consumed field is original R.LR."""
    def __init__(self, file):
        super().__init__(file)
        self.refs['LR'] = self.reference_values(self.child(self.r, 'LR'))
        need(len(self.refs['LR']) == self.n, 'LR covers exact original trial roster')


def roi_indices(session, count):
    need(type(count) is int and p.N_ROIS <= count <= 4096, 'At least fixed 128 ROIs')
    # Anatomical ROI ordinal only; never neural variance, targets, or fit quality.
    order = sorted(range(count), key=lambda i: hashlib.sha256(
        f'NEURAL026:{session}:{i}'.encode('ascii')).digest())
    return np.asarray(sorted(order[:p.N_ROIS]), dtype=np.int64)


def coarse_motion(pos, camera_times, event, sync, dt):
    pos = np.asarray(pos)
    need(pos.ndim == 3 and pos.shape[1:] == (3, 25) and len(pos) >= 2,
         'Exact source time x xyz x 25-marker array')
    # Author default centroidMarkers=9:12 (one based). Do not export markers.
    c = pos[:, :, 8:12].mean(axis=2)
    c = align.gauss_filt1(c, 15. / dt)
    velocity = np.diff(c, axis=0)
    velocity = np.concatenate((velocity, velocity[-1:]), axis=0)
    velocity = align.gauss_filt1(velocity, 15. / dt) / (dt / 1000.)
    times = np.asarray(camera_times).reshape(-1) + sync - event
    return np.concatenate((align.interp1_linear(times, c, p.TIME_MS),
                           align.interp1_linear(times, velocity, p.TIME_MS)), axis=1)


def align_session(mat, inventory, asset_id, sha256, output):
    row = donor.verify_source(mat, inventory, asset_id, sha256)
    cid = context_id(row['mouse'], row['date'], row['area'])
    need(not output.exists(), 'Fresh aligned session folder')
    xs, zs, ys, ids, targets, incomplete = [], [], [], [], [], []
    with h5py.File(mat, 'r') as h:
        r = Reader(h)
        cycle = r.metadata_array('cycleDurMs')
        need(cycle.size == 1, 'Scalar cycle')
        cycle = float(cycle.reshape(-1)[0])
        lags = r.metadata_array('ROILags').reshape(-1)
        need(np.isfinite(cycle) and cycle >= 10 and np.isfinite(lags).all(), 'Acquisition timing')
        chosen = roi_indices(cid, len(lags))
        rows, excluded, quality_count, dt = donor.select_rows(r, cycle, lags, row['mouse'], row['date'])
        incomplete.extend(excluded)
        for i, number in rows:
            posobj = r.object('posXYZ', i)
            if posobj.attrs.get('MATLAB_empty', 0) or posobj.size == 0:
                incomplete.append(number)
                continue
            lr = r.scalar('LR', i)
            need(lr in (1., 2.), 'Actual source target is exactly LR 1 or 2')
            event, sync = r.scalar('liftTimeDLC', i), r.scalar('syncTime', i)
            duration = r.scalar('grabTimeC', i) - event
            need(np.isfinite(duration) and duration > 0, 'Same-clock positive lift-to-grab duration')
            cameras = r.camera_times(i)
            x = align.event_lock_data_smooth(r.array('events', i), r.array('frameTimes', i),
                                             event, sync, cycle, lags, p.TIME_MS)
            y48 = align.event_lock_kinematics(r.array('jointAngles', i), cameras,
                                             event, sync, dt, p.TIME_MS)
            coarse = coarse_motion(r.array('posXYZ', i), cameras, event, sync, dt)
            if x is None or y48 is None or not all(np.isfinite(v).all() for v in (x, y48, coarse)):
                incomplete.append(number)
                continue
            z = p.nuisance(np.array([int(lr)]), np.array([duration]), coarse[None])[0]
            xs.append(x[:, chosen]); ys.append(y48[:, :24]); zs.append(z)
            ids.append(number); targets.append(int(lr))
            need(len(ids) <= 4096, 'Bounded full session support')
        source_n = r.n
    need(len(ids) >= 20 and len(set(ids)) == len(ids), 'At least 20 eligible original trials')
    order = np.argsort(ids)
    packet = dict(x=np.asarray(xs)[order], z=np.asarray(zs)[order], y=np.asarray(ys)[order],
                  trial_id=np.asarray(ids, dtype=np.int64)[order], target=np.asarray(targets, dtype=np.int64)[order])
    validate_session(packet)
    output.mkdir(parents=True)
    path = output / (cid + '.npz')
    np.savez(path, **packet)
    save_json(output / (cid + '.json'), dict(schema='neural026_aligned_v1', session=cid,
        source_asset=row, source_sha256=sha256, aligned=pin(path),
        trial_id=packet['trial_id'].tolist(), target=packet['target'].tolist(),
        source_trial_count=source_n, quality_count=quality_count, incomplete_trial_ids=incomplete,
        roi_ordinal_zero_based=chosen.tolist(), global_camera_dt_ms=dt,
        matlab_parity_measured=False, model_fits=0, scientific_scoring=False))


def validate_session(v):
    need(set(v) == SESSION_KEYS, 'Exact aligned session arrays')
    ids, target = v['trial_id'], v['target']
    n = len(ids)
    need(ids.shape == target.shape == (n,) and ids.dtype.kind in 'iu' and target.dtype.kind in 'iu'
         and 20 <= n <= 4096 and (ids > 0).all() and (np.diff(ids) > 0).all()
         and np.isin(target, [1, 2]).all(), 'Whole chronological source trials')
    for name, shape in (('x', (n, 51, 128)), ('z', (n, 51, 141)), ('y', (n, 51, 24))):
        need(v[name].shape == shape and v[name].dtype.kind == 'f' and np.isfinite(v[name]).all(),
             'Complete finite aligned shapes')


def matched_design(metadata):
    """Support decisions consume only source identities/target strata, not arrays."""
    expected = [context_id(*s) for s in SESSIONS]
    need(set(metadata) == set(expected), 'All five mice / both areas / ten sessions')
    cases = []
    for mouse in p.MICE:
        by_area = {area: next(c for c in expected if c.startswith(mouse + '_') and c.endswith('_' + area))
                   for area in p.AREAS}
        groups = {}
        for area, cid in by_area.items():
            m = metadata[cid]
            need(m['schema'] == 'neural026_aligned_v1' and m['session'] == cid, 'Session metadata identity')
            ids, target = m['trial_id'], m['target']
            need(type(ids) is list and type(target) is list and len(ids) == len(target)
                 and 20 <= len(ids) <= 4096 and all(type(x) is int and x > 0 for x in ids)
                 and ids == sorted(set(ids)) and all(type(x) is int and x in (1, 2) for x in target),
                 'Typed complete chronological ID/target roster')
            groups[area] = {k: [i for i, t in zip(ids, target) if t == k] for k in (1, 2)}
        matched = {k: min(len(groups[a][k]) for a in p.AREAS) for k in (1, 2)}
        need(min(matched.values()) >= 10, 'At least ten matched trials per target/area; no shortened task')
        for area, cid in by_area.items():
            selected = {k: groups[area][k][:matched[k]] for k in (1, 2)}
            all_ids = sorted(selected[1] + selected[2])
            for fold in range(p.N_FOLDS):
                query = sorted([v for k in (1, 2) for j, v in enumerate(selected[k]) if j % 5 == fold])
                train = sorted(set(all_ids) - set(query))
                cases.append(dict(case_id=f'{mouse}_{area}_fold{fold}', mouse=mouse, area=area,
                    session=cid, fold=fold, train_id=train, query_id=query,
                    matched_counts={str(k): matched[k] for k in (1, 2)}, aligned=metadata[cid]['aligned']))
    need([c['case_id'] for c in cases] == p.case_ids(), 'Fixed fifty-case order')
    return dict(schema='neural026_design_v1', cases=cases, packet_prepared=False,
                external_per_case_isolation_required=True, full_cohort=True)


def stage_case(design, sessions, case_id, public_output, private_output):
    p.validate_design(design)
    rows = [r for r in design['cases'] if r['case_id'] == case_id]
    need(len(rows) == 1, 'Exact case')
    row = rows[0]
    path = sessions / (row['session'] + '.npz')
    same_pin(path, row['aligned'])
    v = npz_load(np, path, SESSION_KEYS)
    validate_session(v)
    lookup = {int(t): i for i, t in enumerate(v['trial_id'])}
    train = np.array([lookup[t] for t in row['train_id']])
    query = np.array([lookup[t] for t in row['query_id']])
    public = {side + '_' + dest: v[src][ix] for side, ix in (('train', train), ('query', query))
              for src, dest in (('x', 'x'), ('z', 'z'), ('trial_id', 'id'), ('target', 'target'))}
    public['train_y'] = v['y'][train]
    p.validate_packet(public)
    need(not public_output.exists() and not private_output.exists()
         and public_output.resolve() != private_output.resolve(), 'Fresh distinct public/private folders')
    # Operator must put these in separate permission/isolation roots. Never mount sessions or all folds.
    need(public_output.resolve() not in private_output.resolve().parents
         and private_output.resolve() not in public_output.resolve().parents, 'No nested public/private roots')
    public_output.mkdir(parents=True); private_output.mkdir(parents=True)
    np.savez(public_output / 'input.npz', **public)
    np.savez(private_output / 'target.npz', trial_id=v['trial_id'][query], y=v['y'][query])
    save_json(public_output / 'case.json', dict(schema='neural026_case_v1',
        **{k: row[k] for k in ('case_id', 'mouse', 'area', 'fold', 'train_id', 'query_id')},
        output_file='predictions.npz', output_keys=['trial_id', *p.ARMS]))
    save_json(private_output / 'binding.json', dict(case_id=case_id,
        input=pin(public_output / 'input.npz'), target=pin(private_output / 'target.npz')))


def main():
    q = argparse.ArgumentParser(description=__doc__)
    sub = q.add_subparsers(dest='command', required=True)
    a = sub.add_parser('align'); a.add_argument('--mat', type=Path, required=True)
    a.add_argument('--asset-id', type=int, required=True); a.add_argument('--sha256', required=True)
    a.add_argument('--output', type=Path, required=True)
    d = sub.add_parser('design'); d.add_argument('--sessions', type=Path, required=True)
    d.add_argument('--output', type=Path, required=True)
    s = sub.add_parser('stage-case'); s.add_argument('--sessions', type=Path, required=True)
    s.add_argument('--design', type=Path, required=True); s.add_argument('--case-id', required=True)
    s.add_argument('--public-output', type=Path, required=True); s.add_argument('--private-output', type=Path, required=True)
    args = q.parse_args()
    if args.command == 'align':
        align_session(args.mat, json_load(Path(__file__).with_name('source_inventory.json')),
                      args.asset_id, args.sha256, args.output)
    elif args.command == 'design':
        m = {context_id(*s): json_load(args.sessions / (context_id(*s) + '.json')) for s in SESSIONS}
        save_json(args.output, matched_design(m))
    else:
        stage_case(json_load(args.design), args.sessions, args.case_id, args.public_output, args.private_output)


if __name__ == '__main__':
    main()
