"""Prospective DREDge human-LFP evaluation components; not native DREDge."""
from __future__ import annotations
import argparse
import hashlib
import os
from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
import numpy as np

TASK_ID = 'PAPER-paper-method-add-003'
SOURCE_COMMIT = 'ed236113a0b6c29b376065440174da6341a1d875'
PATIENTS = ('Pt01', 'Pt02', 'Pt03')
REQUIRED_METHODS = ('default_dredge', 'alternate')
GATES = [
    'No independent human displacement ground truth; metrics describe signal consistency only.',
    'Authentic raw LFP/channel-map/gain/time and full-population validation not performed.',
    'Prospective score panel, segment selection, settings and tolerances require scientific freeze.',
    'Pinned native default DREDge and alternate execution remains unverified.',
    'Protected assessment, paper/data/code exposure and separate rights review remain unresolved.',
    'Engineering controls do not establish reproduction, improvement or scientific qualification.',
]


def _array(value, ndim, name):
    a = np.asarray(value, dtype=float)
    if a.ndim != ndim or not a.size or not np.isfinite(a).all():
        raise ValueError(f'{name} must be nonempty finite {ndim}D')
    return a


def _grid(value, name):
    a = _array(value, 1, name)
    if len(a) < 2 or np.any(np.diff(a) <= 0):
        raise ValueError(f'{name} must be strictly increasing, length >= 2')
    return a


def _file_identity(stream):
    info = os.fstat(stream.fileno())
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _verified_stream(path, expected_sha256, expected_bytes=None):
    """Keep authenticated bytes and decoded data on one unchanged descriptor."""
    with Path(path).open('rb') as stream:
        identity = _file_identity(stream)
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
                or digest.hexdigest() != expected_sha256
                or (expected_bytes is not None and identity[2] != expected_bytes)):
            raise ValueError(f'Content hash mismatch: {path}')
        if _file_identity(stream) != identity:
            raise ValueError('Input changed during authentication')
        stream.seek(0)
        try:
            yield stream
        finally:
            if _file_identity(stream) != identity:
                raise ValueError('Input changed during authenticated decoding')


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_meta(path):
    """Read SpikeGLX key/value text without assuming acquisition units."""
    result = {}
    text = path.read().decode() if hasattr(path, 'read') else Path(path).read_text()
    for line in text.splitlines():
        if not line.strip():
            continue
        if '=' not in line:
            raise ValueError('Malformed SpikeGLX metadata')
        key, value = line.split('=', 1)
        if key in result:
            raise ValueError(f'Duplicate metadata key: {key}')
        result[key] = value
    return result


def load_raw_lfp(binary, meta, channel_map, *, patient, start_sample, stop_sample,
                 expected_sha256, expected_meta_sha256, expected_map_sha256, column_x):
    """Memory-map raw int16 LFP; return one geometrical column in ADC counts.

    MATLAB chanMap is explicitly one-based. Raw file, metadata and map are pinned
    by operator content hashes, never by the canonical ambiguous digest fields.
    """
    from scipy.io import loadmat
    if patient not in PATIENTS or Path(binary).name != f'{patient}.imec0.lf.bin':
        raise ValueError('Only explicitly named raw human LFP inputs are accepted')
    with ExitStack() as stack:
        binary_stream = stack.enter_context(_verified_stream(binary, expected_sha256))
        meta_stream = stack.enter_context(_verified_stream(meta, expected_meta_sha256))
        map_stream = stack.enter_context(_verified_stream(channel_map, expected_map_sha256))
        m = read_meta(meta_stream)
        rate = float(m['imSampRate'])
        channels = int(m['nSavedChans'])
        if not np.isfinite(rate) or rate <= 0 or channels <= 0:
            raise ValueError('Invalid sample rate/channel count')
        n_ap, n_lf, n_sync = map(int, m['snsApLfSy'].split(','))
        if n_ap != 0 or n_lf <= 0 or n_lf + n_sync != channels:
            raise ValueError('Not a validated LF-only SpikeGLX layout')
        size = os.fstat(binary_stream.fileno()).st_size
        if size % (2 * channels):
            raise ValueError('Incomplete raw sample frame')
        n_samples = size // (2 * channels)
        if (type(start_sample) is not int or type(stop_sample) is not int or
                not 0 <= start_sample < stop_sample <= n_samples):
            raise ValueError('Invalid half-open sample segment')
        cm = loadmat(map_stream)
        ids, x, z, connected = [np.asarray(cm[k]).ravel() for k in
                               ('chanMap', 'xcoords', 'ycoords', 'connected')]
        if not len(ids) or not (len(ids) == len(x) == len(z) == len(connected)):
            raise ValueError('Channel-map shape mismatch')
        if not all(np.isfinite(a).all() for a in (ids, x, z, connected)):
            raise ValueError('Nonfinite geometry')
        if (not np.equal(ids, np.floor(ids)).all() or len(set(ids)) != len(ids)
                or ids.min() < 1 or ids.max() > n_lf or not np.isin(connected, [0, 1]).all()):
            raise ValueError('Invalid one-based raw signal channel map')
        use = np.flatnonzero((x == column_x) & (connected == 1))
        use = use[np.argsort(z[use])]
        depths = _grid(z[use], 'column depths')
        if len(use) < 6:
            raise ValueError('At least six connected depths required for channel holdout')
        raw = np.memmap(binary_stream, dtype='<i2', mode='r', shape=(n_samples, channels))
        values = np.asarray(raw[start_sample:stop_sample, ids[use].astype(int) - 1], dtype=float)
        return {'values': values, 'depths_um': depths,
                'times_s': np.arange(start_sample, stop_sample) / rate,
                'sample_rate_hz': rate, 'channel_ids_one_based': ids[use].astype(int),
                'units': 'ADC_counts_no_voltage_gain_claim', 'patient': patient,
                'recording_sha256': expected_sha256}


def preprocess(values, sample_rate_hz, *, target_rate_hz, cutoff_hz, order=4):
    """Explicit prospective low-pass/decimation, never an attributed native recipe.

    Filter each reserved segment separately. Edge transients must be excluded by
    the operator's predeclared guard; no fit/development signal is concatenated.
    """
    from scipy.signal import butter, sosfiltfilt
    values = _array(values, 2, 'values')
    ratio = sample_rate_hz / target_rate_hz
    if (not np.isfinite([sample_rate_hz, target_rate_hz, cutoff_hz]).all()
            or not 0 < cutoff_hz < target_rate_hz / 2 <= sample_rate_hz / 2
            or ratio != int(ratio) or type(order) is not int or order < 1):
        raise ValueError('Need integral decimation and valid explicit antialias cutoff/order')
    sos = butter(order, cutoff_hz, fs=sample_rate_hz, output='sos')
    return sosfiltfilt(sos, values, axis=0)[::int(ratio)]


def correlation(x, y):
    x = np.asarray(x, float).ravel(); y = np.asarray(y, float).ravel()
    if len(x) != len(y) or len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    x = x - x.mean(); y = y - y.mean()
    denom = np.linalg.norm(x) * np.linalg.norm(y)
    return None if denom == 0 else float(np.clip(x @ y / denom, -1, 1))


def rigid_reference(profiles, depths_um, *, max_shift_bins, min_correlation,
                    max_time_separation, huber_delta_um, iterations=5):
    """Independent rigid pairwise xcorr + Huber graph solver (not DREDge).

    Pair i,j observes d[j]-d[i]. Positive displacement means a feature moved
    towards larger raw depth. The zero-mean gauge is explicit, not motion truth.
    No regularization bridge silently connects an unidentifiable graph.
    """
    p = _array(profiles, 2, 'profiles'); z = _grid(depths_um, 'depths')
    if p.shape[1] != len(z) or len(p) < 2:
        raise ValueError('Profile/time/depth shape mismatch')
    step = np.diff(z)
    if not np.allclose(step, step[0], rtol=1e-8, atol=1e-8):
        raise ValueError('Rigid reference requires uniformly spaced channel depths')
    if (type(max_shift_bins) is not int or not 0 <= max_shift_bins <= len(z) - 3
            or not 0 <= min_correlation <= 1 or type(max_time_separation) is not int
            or max_time_separation < 1 or not np.isfinite(huber_delta_um)
            or huber_delta_um <= 0 or type(iterations) is not int or iterations < 1):
        raise ValueError('Invalid explicit rigid-reference settings')
    edges, shifts, weights = [], [], []
    for i in range(len(p)):
        for j in range(i + 1, min(len(p), i + max_time_separation + 1)):
            candidates = []
            for lag in range(-max_shift_bins, max_shift_bins + 1):
                start = max(0, -lag); stop = min(len(z), len(z) - lag)
                c = correlation(p[i, start:stop], p[j, start + lag:stop + lag])
                if c is not None:
                    candidates.append((c, -abs(lag), -lag, lag))
            if not candidates:
                continue
            best = max(candidates)
            if best[0] < min_correlation or best[0] <= 0:
                continue
            edges.append((i, j)); shifts.append(best[3] * step[0]); weights.append(best[0] ** 2)
    if not edges:
        raise ValueError('No identifiable registration edges')
    from scipy.sparse import coo_matrix, diags
    from scipy.sparse.csgraph import connected_components
    from scipy.sparse.linalg import lsqr
    edge_array = np.asarray(edges)
    a = coo_matrix((np.tile([-1., 1.], len(edges)),
                    (np.repeat(np.arange(len(edges)), 2), edge_array.ravel())),
                   shape=(len(edges), len(p))).tocsr()
    graph = coo_matrix((np.ones(len(edges)), (edge_array[:, 0], edge_array[:, 1])),
                       shape=(len(p), len(p))).tocsr()
    if connected_components(graph, directed=False, return_labels=False) != 1:
        raise ValueError('Disconnected registration graph; displacement unidentifiable')
    b = np.asarray(shifts); base = np.asarray(weights); w = base.copy()
    for _ in range(iterations):
        solution = lsqr(diags(np.sqrt(w)) @ a, b * np.sqrt(w),
                        atol=1e-10, btol=1e-10, iter_lim=max(100, len(p) * 4))
        if solution[1] not in (0, 1, 2):
            raise ValueError('Rigid solver did not converge')
        d = solution[0]; d -= d.mean()
        residual = np.abs(a @ d - b)
        w = base * np.minimum(1.0, huber_delta_um / np.maximum(residual, 1e-15))
    return {'displacement_um': d, 'edge_count': len(edges),
            'edge_residual_rmse_um': float(np.sqrt(np.mean((a @ d - b) ** 2))),
            'gauge': 'mean_displacement_zero', 'implementation': 'independent_rigid_control'}


def align(values, depths_um, displacement_um):
    """Invert native corrected-coordinate map z_corrected=z_observed-d(t,z_observed).

    For rigid motion this equals the pullback y_raw(t,z_target+d(t)).
    Nonrigid displacement is defined at the observed channel depths.
    """
    v = _array(values, 2, 'values'); z = _grid(depths_um, 'depths')
    if v.shape[1] != len(z):
        raise ValueError('Depth shape mismatch')
    d = np.asarray(displacement_um, dtype=float)
    if d.shape == (len(v),):
        d = np.broadcast_to(d[:, None], v.shape)
    if d.shape != v.shape or not np.isfinite(d).all():
        raise ValueError('Displacement must be time or time-by-depth array')
    corrected_coordinates = z[None, :] - d
    # Folded nonrigid maps are physically invalid for this interpolation contract.
    if np.any(np.diff(corrected_coordinates, axis=1) <= 0):
        raise ValueError('Nonrigid displacement folds the spatial coordinate map')
    output = np.empty_like(v)
    for t in range(len(v)):
        output[t] = np.interp(z, corrected_coordinates[t], v[t], left=np.nan, right=np.nan)
    return output


def _ratio(a, b):
    den = float(np.sum(np.square(b)))
    return None if den == 0 else float(np.sum(np.square(a)) / den)


def metric_panel(corrected, original):
    """Same finite rectangular support, no user-supplied score or scalar reward."""
    c = _array(corrected, 2, 'corrected'); o = _array(original, 2, 'original')
    if c.shape != o.shape or min(c.shape) < 3:
        raise ValueError('Need >=3 time samples and >=3 common channels')
    correlations = [correlation(c[i], c[i + 1]) for i in range(len(c) - 1)]
    defined = [v for v in correlations if v is not None]
    return {
        'adjacent_profile_correlation': float(np.mean(defined)) if defined else None,
        'complete_adjacent_profile_correlation': float(np.mean(defined)) if len(defined) == len(c)-1 else None,
        'defined_adjacent_pairs': len(defined), 'total_adjacent_pairs': len(c) - 1,
        'signal_energy_ratio': _ratio(c, o),
        'temporal_difference_energy_ratio': _ratio(np.diff(c, axis=0), np.diff(o, axis=0)),
        'spatial_difference_energy_ratio': _ratio(np.diff(c, axis=1), np.diff(o, axis=1)),
        'same_coordinate_waveform_correlation': correlation(c, o),
        'retained_time_samples': len(c), 'retained_depth_channels': c.shape[1],
    }


def evaluate_segment(values, depths_um, times_s, *, fit_channels, evaluation_channels,
                     displacements, rigid_settings, fixed_offset_um):
    """Registration uses fit channels; evaluation only held-out raw channels.

    Default/alternate displacements are supplied native results, NOT evidence
    that this function ran DREDge. All methods share the same interpolation and
    intersection support. No subset can silently become the canonical cohort.
    """
    v = _array(values, 2, 'values'); z = _grid(depths_um, 'depths'); t = _grid(times_s, 'times')
    if v.shape != (len(t), len(z)) or not np.allclose(np.diff(t), np.diff(t)[0]):
        raise ValueError('Signal requires matching regular time/depth axes')
    fit = np.asarray(fit_channels); ev = np.asarray(evaluation_channels)
    if (fit.ndim != 1 or ev.ndim != 1 or not np.issubdtype(fit.dtype, np.integer)
            or not np.issubdtype(ev.dtype, np.integer) or min(len(fit), len(ev)) < 3
            or len(set(fit)) != len(fit) or len(set(ev)) != len(ev)
            or set(fit) & set(ev) or min(fit.min(), ev.min()) < 0
            or max(fit.max(), ev.max()) >= len(z) or not np.isfinite(fixed_offset_um)):
        raise ValueError('Require disjoint explicit fit/evaluation channel indices')
    fit = np.sort(fit); ev = np.sort(ev)
    if set(displacements) != set(REQUIRED_METHODS):
        raise ValueError('Both default_dredge and alternate native results required')
    control = rigid_reference(v[:, fit], z[fit], **rigid_settings)
    all_d = {'no_correction': np.zeros(len(t)),
             'fixed': np.full(len(t), fixed_offset_um),
             'rigid_reference': control['displacement_um'], **displacements}
    aligned = {}
    for name, d in all_d.items():
        d = np.asarray(d, float)
        if d.shape == v.shape:
            d = d[:, ev]
        aligned[name] = align(v[:, ev], z[ev], d)
    # Common columns for ALL times/methods. A method cannot improve by losing
    # difficult time samples. Require contiguous common depth support.
    keep = np.logical_and.reduce([np.isfinite(a).all(axis=0) for a in aligned.values()])
    use = np.flatnonzero(keep)
    if len(use) < 3 or np.any(np.diff(use) != 1):
        raise ValueError('Insufficient contiguous common support; no score emitted')
    original = v[:, ev][:, use]
    panels = {name: metric_panel(a[:, use], original) for name, a in aligned.items()}
    baseline = panels['no_correction']['complete_adjacent_profile_correlation']
    for panel in panels.values():
        score = panel['complete_adjacent_profile_correlation']
        panel['paired_consistency_gain'] = None if score is None or baseline is None else score - baseline
    return {'methods': panels, 'fit_channel_count': len(fit),
            'evaluation_channel_count': len(ev), 'common_depths_um': z[ev][use].tolist(),
            'coverage_fraction': len(use) / len(ev), 'time_range_s': [float(t[0]), float(t[-1])],
            'rigid_control': {k: val for k, val in control.items() if k != 'displacement_um'},
            'displacement_summaries': {k: {'min_um': float(np.min(d)), 'max_um': float(np.max(d))}
                                       for k, d in all_d.items()},
            'scientific_readiness': 'unknown', 'gates': GATES}


def summarize_cohort(records):
    """Require Pt01–Pt03; segment mean within patient, then equal patient mean."""
    if not records or {r['patient'] for r in records} != set(PATIENTS):
        raise ValueError('Full human cohort requires exactly Pt01, Pt02, Pt03')
    identities = [(r['patient'], r['segment_id']) for r in records]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate patient/segment identity')
    patients = {}
    for patient in PATIENTS:
        rows = [r for r in records if r['patient'] == patient]
        methods = {}
        for method in ('no_correction', 'fixed', 'rigid_reference', *REQUIRED_METHODS):
            scores = [r['result']['methods'][method]['paired_consistency_gain'] for r in rows]
            methods[method] = None if any(v is None for v in scores) else float(np.mean(scores))
        patients[patient] = {'segment_count': len(rows), 'paired_consistency_gain': methods}
    macro = {}
    for method in patients[PATIENTS[0]]['paired_consistency_gain']:
        values = [patients[p]['paired_consistency_gain'][method] for p in PATIENTS]
        macro[method] = None if any(v is None for v in values) else float(np.mean(values))
    return {'patients': patients, 'patient_macro_paired_consistency_gain': macro,
            'patient_count': 3, 'segment_count': len(records),
            'scientific_readiness': 'unknown', 'full_contract_complete': False, 'gates': GATES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    protocol_bytes = args.protocol.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get('task_id') != TASK_ID or protocol.get('source_commit') != SOURCE_COMMIT:
        raise ValueError('Task/source identity mismatch')
    if protocol.get('metric_status') != 'prospective_unqualified':
        raise ValueError('This package implements a prospective unqualified panel')
    segments = protocol['segments']
    # Every reserved interval, including development, is checked before opening data.
    identities = set()
    for i, a in enumerate(segments):
        key = (a['patient'], a['segment_id'])
        if key in identities or a['role'] not in ('development', 'evaluation'):
            raise ValueError('Duplicate segment or undeclared role')
        identities.add(key)
        if not 0 <= a['start_sample'] < a['stop_sample']:
            raise ValueError('Invalid segment interval')
        for b in segments[:i]:
            if a['recording_sha256'] == b['recording_sha256'] and max(a['start_sample'], b['start_sample']) < min(a['stop_sample'], b['stop_sample']):
                raise ValueError('Reserved raw segments overlap')
    records = []
    for s in segments:
        if s['role'] != 'evaluation':
            continue
        base = args.protocol.parent
        packet = load_raw_lfp(*(base / s[k] for k in ('binary', 'meta', 'channel_map')),
                              patient=s['patient'], start_sample=s['start_sample'], stop_sample=s['stop_sample'],
                              expected_sha256=s['recording_sha256'], expected_meta_sha256=s['meta_sha256'],
                              expected_map_sha256=s['map_sha256'], column_x=s['column_x'])
        estimates = {}
        for method in REQUIRED_METHODS:
            spec = s['estimates'][method]; path = base / spec['path']
            if spec['recording_sha256'] != s['recording_sha256'] or spec['start_sample'] != s['start_sample'] or spec['stop_sample'] != s['stop_sample']:
                raise ValueError('Native displacement segment mismatch')
            if spec.get('fit_channels') != s['fit_channels']:
                raise ValueError('Native estimates must use the same reserved fit channels')
            if spec['source_commit'] != SOURCE_COMMIT or not isinstance(spec['settings'], dict) or not spec['settings']:
                raise ValueError('Native snapshot and nonempty declared settings metadata required')
            with _verified_stream(path, spec['sha256']) as stream, np.load(stream, allow_pickle=False) as f:
                if not np.array_equal(f['times_s'], packet['times_s']) or not np.array_equal(f['depths_um'], packet['depths_um']):
                    raise ValueError('Native displacement time/geometry mismatch; no implicit interpolation')
                estimates[method] = f['displacement_um'].copy()
        result = evaluate_segment(packet['values'], packet['depths_um'], packet['times_s'],
                                  fit_channels=s['fit_channels'], evaluation_channels=s['evaluation_channels'],
                                  displacements=estimates, rigid_settings=protocol['rigid_settings'],
                                  fixed_offset_um=protocol['fixed_offset_um'])
        records.append({'patient': s['patient'], 'segment_id': s['segment_id'], 'result': result})
    output = {'task_id': TASK_ID, 'protocol_sha256': hashlib.sha256(protocol_bytes).hexdigest(),
              'segment_results': records, 'cohort': summarize_cohort(records)}
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
