"""Source-pinned Area2 spike preparation. Native execution needs an operator lease.

Read only the named training NWB. No behavior, test asset, model or network access.
The existing evaluator remains the packet/scoring authority; this fills its native
conversion boundary without changing either condition-wise endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = '639b1a03ab813f96fec76681110a1634942476badc0fd4c93d406c24701f5db2'
SOURCE_BYTES = 1822876234
NLB_COMMIT = '42f8410b88e12db136910fa2f888b025ea0aa2ae'
EVALUATOR_SHA256 = '4a6263059ca21aadfeec97bf405ba4f8a454da6a1d92d7f205cb468a25916d23'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def evaluator():
    path = HERE.parent / 'initial-evaluator-v1' / 'evaluator.py'
    require(sha256_file(path) == EVALUATOR_SHA256, 'predecessor evaluator source changed')
    spec = importlib.util.spec_from_file_location('neural020_pinned_evaluator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def ragged(values, ends, rows, name):
    ends = np.asarray(ends)
    require(ends.shape == (rows,) and ends.dtype.kind in 'iu', name + ': bad ragged index')
    require(np.all(ends >= 0) and np.all(ends[1:] >= ends[:-1]) and int(ends[-1]) == len(values),
            name + ': incomplete or reversed ragged index')
    starts = np.r_[0, ends[:-1]]
    return [np.asarray(values[int(a):int(b)], dtype=np.float64) for a, b in zip(starts, ends)]


def read_nwb(path):
    """Authenticate bytes before HDF5 decoding. Do not call during generated tests."""
    path = Path(path)
    require(path.is_file() and path.stat().st_size == SOURCE_BYTES, 'exact training NWB size required')
    require(sha256_file(path) == SOURCE_SHA256, 'exact training NWB SHA256 required')
    # Optional only for native preparation, never a global install action.
    import h5py
    with h5py.File(path, 'r') as source:
        require(text(source['session_start_time'][()]) == '2017-12-07T17:06:09.727000-05:00',
                'wrong source session')
        require(text(source['general/subject/subject_id'][()]) == 'Han', 'wrong source subject')
        units, trials = source['units'], source['intervals/trials']
        unit_ids, trial_ids = units['id'][()], trials['id'][()]
        require(len(unit_ids) == 65 and len(trial_ids) == 826, 'complete 65 units and 826 trials required')
        result = {
            'unit_ids': [text(x) for x in unit_ids],
            'heldout_mask': units['heldout'][()],
            'spike_times': ragged(units['spike_times'], units['spike_times_index'][()], 65, 'spikes'),
            'obs_intervals': ragged(units['obs_intervals'], units['obs_intervals_index'][()], 65, 'observations'),
            'trial_ids': [text(x) for x in trial_ids],
            'move_onset_time': np.asarray(trials['move_onset_time'][()], dtype=np.float64),
            'native_split': [text(x) for x in trials['split'][()]],
            'ctr_hold_bump': trials['ctr_hold_bump'][()],
        }
    return result


def validate_snapshot(snapshot):
    ids = snapshot['unit_ids']
    require(len(ids) > 1 and len(set(ids)) == len(ids), 'unique source unit IDs required')
    heldout = np.asarray(snapshot['heldout_mask'])
    require(heldout.shape == (len(ids),) and heldout.dtype == np.bool_ and
            heldout.any() and (~heldout).any(), 'boolean source heldout flags required')
    require(len(snapshot['spike_times']) == len(ids) == len(snapshot['obs_intervals']), 'unit axis mismatch')
    for spikes, intervals in zip(snapshot['spike_times'], snapshot['obs_intervals']):
        spikes, intervals = np.asarray(spikes), np.asarray(intervals)
        require(spikes.ndim == 1 and np.isfinite(spikes).all() and np.all(spikes >= 0) and
                np.all(spikes[1:] >= spikes[:-1]), 'nonnegative sorted finite spike times required')
        require(intervals.ndim == 2 and intervals.shape[1] == 2 and len(intervals) > 0 and
                np.isfinite(intervals).all() and np.all(intervals >= 0) and
                np.all(intervals[:, 1] > intervals[:, 0]) and
                np.all(intervals[1:, 0] >= intervals[:-1, 1]), 'ordered nonoverlapping observation intervals required')
    # Upstream applies the FIRST unit's intervals to its entire heldin/heldout
    # group. Reject unequal groups instead of silently treating that as truth.
    for code in (False, True):
        group = np.flatnonzero(heldout == code)
        reference = np.asarray(snapshot['obs_intervals'][group[0]])
        require(all(np.array_equal(reference, snapshot['obs_intervals'][u]) for u in group),
                'within-group observation intervals differ; upstream first-unit mask is unsupported')
    trial_ids = snapshot['trial_ids']
    require(len(trial_ids) > 0 and len(set(trial_ids)) == len(trial_ids), 'unique source trial IDs required')
    for field in ('move_onset_time', 'native_split', 'ctr_hold_bump'):
        require(np.asarray(snapshot[field]).shape == (len(trial_ids),), 'source trial axis mismatch: ' + field)
    require(np.isfinite(snapshot['move_onset_time']).all(), 'all source movement onsets must be finite')
    labels = np.asarray(snapshot['ctr_hold_bump'])
    require(labels.dtype.kind in 'iuf' and np.isfinite(labels).all() and
            np.isin(labels, [0, 1]).all(), 'source ctr_hold_bump must be exactly 0/1')


def native_clock(move_onset_time, width_ms, end_ms):
    """Pinned global grid and 1-us inclusive-slice guard, via integer ns."""
    require(type(width_ms) is int and width_ms in (5, 20), 'official 5 or 20 ms bins required')
    events = pd.to_timedelta(np.asarray(move_onset_time), unit='s').asi8
    width_ns = width_ms * 1_000_000
    first = -(-(events - 100_000_000) // width_ns)
    last = (events + 500_000_000 - 1000) // width_ns
    require(np.all(last - first + 1 == 600 // width_ms),
            'native microsecond slicing does not produce a complete 600 ms row')
    left = (first[:, None] + np.arange(600 // width_ms)) * width_ms
    require(np.all(left >= 0) and np.all(left < end_ms), 'trial window exceeds source clock support')
    return left.astype(np.int64)


def bin_spikes(snapshot, width_ms):
    """Sparse equivalent of pinned load/resample with complete overlapping rows.

    Source counts are float16. Refuse values whose integer identity would be
    lost in that storage format rather than silently claim exact count parity.
    """
    validate_snapshot(snapshot)
    end_ms = int(round(max(float(x[-1, 1]) for x in snapshot['obs_intervals']) * 1000))
    left = native_clock(snapshot['move_onset_time'], width_ms, end_ms)
    output = np.empty((*left.shape, len(snapshot['unit_ids'])), dtype=np.float64)
    for unit, (spikes, intervals) in enumerate(zip(snapshot['spike_times'], snapshot['obs_intervals'])):
        ms = np.round(np.asarray(spikes) * 1000, 6).astype(np.int64)
        require(np.all(ms < end_ms), 'spike falls outside native allocated clock')
        indices, counts = np.unique(ms, return_counts=True)
        require(np.array_equal(counts.astype(np.float16).astype(np.float64), counts),
                'source float16 would lose 1-ms integer count identity')
        starts = np.asarray([int(np.ceil(round(start * 1000, 6))) for start, _ in intervals])
        stops = np.asarray([int(np.floor(round(stop * 1000, 6))) for _, stop in intervals])
        def in_observed(milliseconds):
            location = np.searchsorted(starts, milliseconds, side='right') - 1
            return (location >= 0) & (milliseconds < stops[np.maximum(location, 0)])
        observed, valid_left = in_observed(indices), in_observed(left)
        # Native resampling zero-fills missing milliseconds before summing,
        # then restores NaN ONLY from the first millisecond in each coarse bin.
        coarse, inverse = np.unique(indices[observed] // width_ms, return_inverse=True)
        totals = np.zeros(len(coarse), dtype=np.float64)
        np.add.at(totals, inverse, counts[observed])
        require(np.array_equal(totals.astype(np.float16).astype(np.float64), totals),
                'source float16 would lose rebinned integer count identity')
        wanted = left // width_ms
        positions = np.searchsorted(coarse, wanted)
        values = np.zeros(left.shape, dtype=np.float64)
        if len(coarse):
            present = (positions < len(coarse)) & (coarse[np.minimum(positions, len(coarse) - 1)] == wanted)
            values[present] = totals[positions[present]]
        values[~valid_left] = np.nan
        output[:, :, unit] = values
    return output, left


def continuous_blocks(snapshot, left, width_ms):
    """Union of actual observation intervals; no trial-specific invented blocks."""
    intervals = sorted((float(a), float(b)) for group in snapshot['obs_intervals'] for a, b in group)
    merged = []
    for start, stop in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], stop)
        else:
            merged.append([start, stop])
    blocks = []
    for row in left:
        start, stop = row[0] / 1000, (row[-1] + width_ms) / 1000
        matches = [i for i, (a, b) in enumerate(merged) if a <= start and stop <= b]
        require(len(matches) == 1, 'complete aligned trial crosses a recording gap or support edge')
        blocks.append('source-block-%04d' % matches[0])
    return blocks


def prepare_snapshot(snapshot, protocol, width_ms, exclusions):
    """Complete-source adapter; exclusions are explicit native-split reasons.

    This pure boundary is exercised with generated snapshots. Only read_nwb()
    establishes source-file authentication in the native command.
    """
    require(len(snapshot['unit_ids']) == 65 and len(snapshot['trial_ids']) == 826,
            'complete 65-unit/826-row source required')
    require(isinstance(exclusions, dict), 'exclusions must map excluded native splits to reasons')
    e = evaluator()
    counts, left = bin_spikes(snapshot, width_ms)
    blocks = continuous_blocks(snapshot, left, width_ms)
    roles = protocol['native_split_roles']
    require(set(snapshot['native_split']) <= set(roles), 'native split lacks a frozen role')
    require(set(exclusions) == {name for name, role in roles.items() if role == 'excluded'},
            'one explicit reason is required for each excluded native split')
    roster = []
    for i, trial_id in enumerate(snapshot['trial_ids']):
        split = snapshot['native_split'][i]
        role = roles[split]
        roster.append({'trial_id': trial_id, 'block_id': blocks[i], 'native_split': split,
                       'role': role, 'ctr_hold_bump': int(snapshot['ctr_hold_bump'][i]),
                       'window_start_seconds': float(left[i, 0]) / 1000,
                       'window_stop_seconds': float(left[i, -1] + width_ms) / 1000,
                       'exclusion_reason': exclusions.get(split) if role == 'excluded' else None})
    metadata = {
        'schema_version': 1, 'task_id': e.TASK_ID, 'contract_sha256': e.CONTRACT_SHA256,
        'source': {'dandiset': '000127', 'version': '0.220113.0359', 'subject': 'Han',
                   'session_start_time': '2017-12-07T17:06:09.727000-05:00',
                   'asset_id': 'ded26b6c-418d-43f5-8a37-dfd072c2dbd4', 'asset_sha256': SOURCE_SHA256},
        'bin_width_ms': width_ms, 'unit_ids': list(snapshot['unit_ids']),
        'heldout_mask': np.asarray(snapshot['heldout_mask']).tolist(), 'trial_roster': roster,
        'protocol': protocol,
        'conversion_receipt': {'nlb_commit': NLB_COMMIT, 'alignment_event': 'move_onset_time',
                               'window_ms': [-100, 500], 'rate_units': 'spikes_per_bin',
                               'mask_source': 'NWB units.heldout',
                               'counts_sha256': hashlib.sha256(counts.tobytes()).hexdigest(),
                               'operator_evidence': 'native-spike-preparation-v1; see private_native_audit.json'},
    }
    # Also rejects native train/val mixing in a true continuous block. The
    # adapter MUST NOT silently replace the frozen split or relabel each trial.
    packets = e.prepare_packet(metadata, counts)
    audit = {'task_id': e.TASK_ID, 'source_rows': len(roster), 'source_units': len(snapshot['unit_ids']),
             'source_clock_left_edges_ms': left.tolist(),
             'source_move_onset_seconds': np.asarray(snapshot['move_onset_time']).tolist(),
             'block_count': len(set(blocks)), 'bin_width_ms': width_ms,
             'source_sha256': SOURCE_SHA256, 'source_file_authenticated': False,
             'binning': 'source_global_1ms_round6_truncate_then_sum_left_edge_nan',
             'training_overlap_policy': 'complete_rows_with_overlap_retained; no native training-row truncation',
             'research_qualified': False, 'authentic_reference_executed': False}
    return metadata, packets, audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nwb', required=True)
    parser.add_argument('--protocol', required=True, help='JSON with protocol and exclusions fields')
    parser.add_argument('--bin-width-ms', type=int, choices=(5, 20), required=True)
    parser.add_argument('--output-directory', required=True, help='new private directory outside Git')
    args = parser.parse_args(argv)
    out = Path(args.output_directory).resolve()
    require(not any((p / '.git').exists() for p in [out, *out.parents]), 'native outputs must remain outside Git')
    require(not out.exists(), 'output directory already exists')
    config = json.loads(Path(args.protocol).read_text())
    require(set(config) == {'protocol', 'exclusions'}, 'protocol document fields differ')
    snapshot = read_nwb(args.nwb)
    metadata, packets, audit = prepare_snapshot(snapshot, config['protocol'], args.bin_width_ms, config['exclusions'])
    audit['source_file_authenticated'] = True
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, packet in zip(('public_query', 'public_training', 'private_gold'), packets):
        with (out / (name + '.npz')).open('xb') as stream:
            np.savez_compressed(stream, **packet)
    for name, value in (('private_protocol.json', metadata), ('private_native_audit.json', audit)):
        (out / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    receipt = {'task_id': 'NEURAL-020', 'packet_sha256': str(packets[0]['packet_sha256']),
               'files_sha256': {p.name: sha256_file(p) for p in sorted(out.iterdir())},
               'research_qualified': False, 'submission_ready': False}
    (out / 'private_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
