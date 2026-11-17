"""Trusted conversion; prepared only. Metadata lock/support gate precede spikes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import h5py
import numpy as np
from core import require, conditions, support_gate, bin_spikes, validate_packet

SOURCE_SHA = '6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198'
ID_SHA = '0b936d421cc4709487704b53954e1b4858e302f44ce3f800b8d943e648afa48e'
CAP = 10_000_000


def pin(path):
    st = path.lstat()
    require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'regular single-link file')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'bytes': st.st_size, 'sha256': h.hexdigest()}


def save_json(path, obj):
    data = (json.dumps(obj, indent=2, allow_nan=False) + '\n').encode()
    require(len(data) < 1_000_000, 'metadata cap')
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def dataset(file, path):
    current = file
    for part in path.strip('/').split('/'):
        require(isinstance(current, h5py.Group) and isinstance(current.get(part, getlink=True), h5py.HardLink), 'hard/local HDF5 path ' + path)
        current = current[part]
    require(isinstance(current, h5py.Dataset) and not current.is_virtual and not current.external, 'local nonvirtual dataset ' + path)
    return current


def ragged_spans(obs, index, unit_count):
    require(index.shape == (unit_count,) and index.dtype.kind in 'iu', 'observation ragged index')
    ends = index.astype(np.int64)
    require(np.all(ends[1:] >= ends[:-1]) and ends[0] >= 0 and ends[-1] == len(obs), 'complete monotonic observation index')
    return [obs[a:b] for a, b in zip(np.r_[0, ends[:-1]], ends)]


def metadata_selection(trial, units, obs, obs_index, spike_index, spike_n):
    n = len(trial['id'])
    require(n == 1160 and all(np.asarray(a).shape == (n,) for a in trial.values()), 'exact parallel source trial columns')
    require(trial['id'].dtype.kind in 'iu' and len(np.unique(trial['id'])) == n, 'unique integer source trial IDs')
    require(hashlib.sha256(np.ascontiguousarray(trial['id']).tobytes()).hexdigest() == ID_SHA, 'pinned native trial ID order')
    split = np.array([x.decode('utf8') if isinstance(x, bytes) else x for x in trial['split']])
    require(set(split.tolist()) == {'train', 'val', 'none'}, 'known source split values')
    train, query = np.flatnonzero(split == 'train'), np.flatnonzero(split == 'val')
    require(len(train) == 748 and len(query) == 258, 'exact all-source train/validation counts')
    require({618, 729}.issubset(set(trial['id'][train].tolist())), 'both known early-response rows retained in training')
    require(units['id'].shape == units['heldout'].shape == (54,) and units['heldout'].dtype.kind == 'b', 'source unit flags')
    require(units['id'].dtype.kind in 'iu' and len(np.unique(units['id'])) == 54, 'unique source unit IDs')
    heldin = np.flatnonzero(~units['heldout'])
    require(len(heldin) == 40, 'all40 source held-in units')
    spans = ragged_spans(obs, obs_index, 54)
    require(spike_index.shape == (54,) and spike_index.dtype.kind in 'iu', 'spike ragged index schema')
    ends = spike_index.astype(np.int64)
    require(ends[0] >= 0 and np.all(ends[1:] >= ends[:-1]) and ends[-1] == spike_n == 1706196, 'complete monotonic spike ragged index')
    # Chronology is determined from the observation clock, never from target/Go.
    train = train[np.argsort(trial['set_time'][train], kind='stable')]
    query = query[np.argsort(trial['set_time'][query], kind='stable')]
    selected = np.r_[train, query]
    condition, context = conditions(trial['is_short'][selected], trial['is_eye'][selected], trial['theta'][selected], trial['ts'][selected])
    target = trial['tp'][selected]
    require(target.dtype.kind == 'f' and np.isfinite(target).all() and np.all(target > 0), 'all selected targets positive finite; stop rather than filter')
    require(set(condition[:748].tolist()) == set(range(40)), 'all40 training conditions')
    support_gate(*[trial[k][selected] for k in ['start_time', 'stop_time', 'ready_time', 'set_time']], [spans[i] for i in heldin])
    clock_origin = min(float(spans[i][0, 0]) for i in heldin)
    return {'train_rows': train, 'query_rows': query, 'selected_rows': selected, 'heldin_rows': heldin,
            'condition': condition, 'context': context, 'spike_ends': ends, 'clock_origin': clock_origin}


def main():
    a = argparse.ArgumentParser(); a.add_argument('--source', type=Path, required=True); a.add_argument('--out', type=Path, required=True); args = a.parse_args()
    began = time.monotonic()
    require(pin(args.source) == {'bytes': 14119912, 'sha256': SOURCE_SHA}, 'exact pinned NWB')
    require(not args.out.exists(), 'fresh output directory')
    args.out.mkdir(mode=0o700, parents=False)
    (args.out / 'public').mkdir(mode=0o755); (args.out / 'private').mkdir(mode=0o700)
    read_log = []
    with h5py.File(args.source, 'r', rdcc_nbytes=1024 * 1024) as f:
        def read(path, expected_shape):
            ds = dataset(f, path)
            require(ds.shape == expected_shape, 'metadata shape ' + path)
            values = ds[()]; read_log.append({'path': path, 'shape': list(ds.shape), 'dtype': str(ds.dtype)})
            return values
        fields = ('id', 'split', 'start_time', 'stop_time', 'ready_time', 'set_time', 'is_short', 'is_eye', 'theta', 'ts', 'tp')
        trial = {k: read('/intervals/trials/' + k, (1160,)) for k in fields}
        units = {k: read('/units/' + k, (54,)) for k in ('id', 'heldout')}
        obs = read('/units/obs_intervals', (324, 2)); obs_index = read('/units/obs_intervals_index', (54,))
        spike_index = read('/units/spike_times_index', (54,))
        spikes = dataset(f, '/units/spike_times')
        require(spikes.shape == (1706196,) and spikes.dtype == np.dtype('float64'), 'pinned spike schema, values not yet read')
        selection = metadata_selection(trial, units, obs, obs_index, spike_index, spikes.shape[0])
        selected = selection['selected_rows']; heldin = selection['heldin_rows']
        lock = {'schema_version': 1, 'source': {'bytes': 14119912, 'sha256': SOURCE_SHA},
                'train_ids': trial['id'][selection['train_rows']].tolist(), 'query_ids': trial['id'][selection['query_rows']].tolist(),
                'heldin_unit_ids': units['id'][heldin].tolist(), 'clock_origin_seconds': selection['clock_origin'],
                'selection': 'id+split, source heldout flags, chronology; no omitted source train/val row',
                'metadata_support_gate_passed': True, 'spike_values_read_before_lock': 0}
        save_json(args.out / 'private/selection_lock.json', lock)
        lock_pin = pin(args.out / 'private/selection_lock.json')
        counts = np.empty((1006, 4, 40), dtype=np.uint32)
        ends = selection['spike_ends']; begins = np.r_[0, ends[:-1]]
        spike_values_read = 0
        for j, unit in enumerate(heldin):
            vector = spikes[int(begins[unit]):int(ends[unit])]
            spike_values_read += len(vector)
            counts[:, :, j] = bin_spikes(vector, trial['set_time'][selected])
        require(pin(args.out / 'private/selection_lock.json') == lock_pin, 'selection commitment unchanged')
    ids = np.array([f'dmfc-{int(i):06d}' for i in trial['id'][selected]])
    shared = {'case_id': ids, 'counts': counts, 'condition': selection['condition'], 'context': selection['context'],
              'nominal_ts_ms': trial['ts'][selected].astype(np.float64),
              'clock_seconds': trial['set_time'][selected].astype(np.float64) - selection['clock_origin']}
    train = {k: v[:748] for k, v in shared.items()}; query = {k: v[748:] for k, v in shared.items()}
    train['tp_ms'] = trial['tp'][selected[:748]].astype(np.float64)
    train['fold'] = np.empty(748, dtype=np.int64)
    for fold, idx in enumerate(np.array_split(np.arange(748), 5)):
        train['fold'][idx] = fold
    validate_packet(train, True); validate_packet(query, False)
    private = {'case_id': ids[748:], 'tp_ms': trial['tp'][selected[748:]].astype(np.float64),
               'condition': selection['condition'][748:], 'context': selection['context'][748:]}
    projected = sum(v.nbytes + 1024 for packet in (train, query, private) for v in packet.values()) + 2_000_000
    require(projected <= CAP, 'prewrite aggregate output projection')
    np.savez(args.out / 'public/train.npz', **train); np.savez(args.out / 'public/query.npz', **query)
    np.savez(args.out / 'private/query_targets.npz', **private)
    save_json(args.out / 'public_identity.json', {'schema_version': 1, 'case_id': ids[748:].tolist()})
    save_json(args.out / 'public/units.json', {'unit_id': units['id'][heldin].tolist(), 'source': 'all40 source held-in units; no activity selection'})
    save_json(args.out / 'public/schema.json', {'schema_version': 1, 'candidate_id': 'NEURAL-095', 'train_n': 748, 'query_n': 258,
        'bin_edges_seconds_relative_to_Set': [-.2, -.15, -.1, -.05, 0.], 'bin_convention': '[left,right)',
        'target': 'released behavioral tp milliseconds; do not replace with Go−Set', 'prediction_clock': 'AT observed Set',
        'population': 'public development Haydn20161211; no animal/session transfer', 'units': 40,
        'clock_origin': 'earliest observation support among40held-in units; independent of outcomes',
        'public_keys': {'train': sorted(train), 'query': sorted(query)}, 'shape_counts': ['case', 4, 40],
        'fold': 'five contiguous chronological training groups; no validation-target access',
        'no_target_filter': True, 'no_outlier_field_read': True})
    pins = {str(p.relative_to(args.out)): pin(p) for p in sorted(args.out.rglob('*')) if p.is_file()}
    receipt = {'status': 'conversion_complete_support_gate_passed', 'source': {'bytes': 14119912, 'sha256': SOURCE_SHA},
        'selection_lock': lock_pin, 'files': pins, 'metadata_reads': read_log, 'spike_values_read': spike_values_read,
        'spike_access': 'whole ragged vectors for40held-in units after metadata lock; transient unselected timestamps read',
        'counts_shape': list(counts.shape), 'target_filtering': False, 'models_fit': 0, 'wall_seconds': time.monotonic() - began}
    save_json(args.out / 'conversion_receipt.json', receipt)
    require(sum(p.stat().st_size for p in args.out.rglob('*') if p.is_file()) <= CAP, 'aggregate output cap')
    for p in (args.out / 'public').iterdir():
        p.chmod(0o444)
    (args.out / 'public').chmod(0o555)


if __name__ == '__main__':
    main()
