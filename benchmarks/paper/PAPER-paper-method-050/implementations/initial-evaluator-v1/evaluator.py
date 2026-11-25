"""Pinned spikeInfo bridge and prospective paired longitudinal-tracking assessment.

This module never runs DANT/UnitMatch, unpickles native output, infers identity
labels, or promotes engineering controls to scientific admission.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np

TASK_ID = 'PAPER-paper-method-050'
CONTRACT_SHA256 = 'fcd65edd8550ca28997a59ad5199df24179aea1c304ad4140177ba1d45b707d3'
REVISION = '96060c1dd816181f32f089aaa686801aeae821bb'
CORRELATION_ENDPOINT_TOLERANCE = 8 * np.finfo(float).eps
ROSTER = json.loads(Path(__file__).with_name('roster.json').read_text())
HOLDS = [
    'Authentic all-13-dataset schema and complete session/unit populations unverified.',
    'Native DANT and UnitMatch runs, first/second-half UnitMatch waveforms and exact matched quality filters unverified.',
    'Functional consistency is indirect evidence, not same-neuron ground truth or confidence calibration.',
    'Independent feature lineage and matching/tuning exclusions require operator audit.',
    'Motion-correction accuracy and probability calibration have no frozen protected reference.',
    'Paper Figure 5 day-specific rate-filtered common-three-method median/Friedman comparison, unmatched outlier/EMD endpoints and numeric targets remain unimplemented.',
    'Paper numeric reconstruction, grading tolerances, native measured resources and difficulty unqualified.',
    'Public source exposure and GPL-3.0 code / CC-BY-4.0 data rights remain applicable.',
]

class ContractError(ValueError):
    """Input cannot support the declared assessment."""

def require(ok, message):
    if not ok:
        raise ContractError(message)

def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def _source_stat(stream):
    record = os.fstat(stream.fileno())
    return (record.st_dev, record.st_ino, record.st_size,
            record.st_mtime_ns, record.st_ctime_ns)


@contextmanager
def _authenticated_spikeinfo(source, asset, source_kind):
    """Hash and decode one descriptor; refuse observed in-place mutations."""
    with source.open('rb') as stream:
        before = _source_stat(stream)
        if source_kind == 'source_asset':
            require(before[2] == asset['bytes'], 'source byte size differs from frozen inventory')
        sha256, md5 = hashlib.sha256(), hashlib.md5()
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            sha256.update(part)
            md5.update(part)
        require(_source_stat(stream) == before, 'source changed during authentication')
        if source_kind == 'source_asset':
            require('md5:' + md5.hexdigest() == asset['checksum'],
                    'source MD5 differs from frozen inventory')
        stream.seek(0)
        yield stream, {'name': source.name, 'bytes': before[2],
                       'sha256': sha256.hexdigest()}
        require(_source_stat(stream) == before, 'source changed during conversion')


def integer(value, label):
    require(isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)), f'{label} must be integer')
    return int(value)

def finite_array(value, label):
    a = np.asarray(value)
    require(a.dtype.kind in 'iuf' and np.isfinite(a).all(), f'{label} must be finite numeric')
    return a

def json_number(value):
    if value is None:
        return None
    if math.isnan(value):
        return None
    if math.isinf(value):
        return 'positive_infinity' if value > 0 else 'negative_infinity'
    return float(value)

def extended_mean(values):
    if not values:
        return None
    pos = any(v == math.inf for v in values)
    neg = any(v == -math.inf for v in values)
    if pos and neg:
        return None
    if pos:
        return math.inf
    if neg:
        return -math.inf
    return math.fsum(values) / len(values)

def convert_spikeinfo(source, destination, dataset, *, source_kind='source_asset'):
    """Convert the pinned MATLAB v7.3 reference layout without renumbering units.

    Production input is bound to the exact contract bytes and source-reported MD5.
    Generated fixture mode is explicit and permanently marked in the receipt.
    Destination must not exist. Writes are staged and atomically renamed.
    """
    import h5py
    source, destination = Path(source), Path(destination)
    require(dataset in ROSTER, 'unknown dataset')
    require(source_kind in ('source_asset', 'generated_engineering_control'), 'invalid source_kind')
    require(not destination.exists(), 'destination already exists')
    asset = ROSTER[dataset]
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.spikeinfo-', dir=destination.parent))
    try:
        with _authenticated_spikeinfo(source, asset, source_kind) as (source_stream, source_identity):
            with h5py.File(source_stream, 'r') as h:
                require('spikeInfo' in h, 'missing spikeInfo')
                g = h['spikeInfo']
                require('RatName' in g and g['RatName'].ndim == 2 and g['RatName'].shape[1] == 1, 'RatName must have source N x 1 reference layout')
                n = g['RatName'].shape[0]
                require(n > 0, 'empty unit population')
                fields = ['SpikeTimes', 'SessionIndex', 'Waveform', 'Kcoords', 'Xcoords', 'Ycoords']
                if 'PETH' in g:
                    fields.append('PETH')
                for name in fields:
                    require(name in g and g[name].shape == (n, 1), f'{name} must have source N x 1 reference layout')
                    require(h5py.check_dtype(ref=g[name].dtype) is not None, f'{name} must contain HDF5 references')
                def deref(name, unit):
                    ref = g[name][unit, 0]
                    require(bool(ref), f'null {name} reference')
                    return finite_array(h[ref][()], name)
                coords = {name: deref(name, 0).reshape(-1) for name in ('Kcoords','Xcoords','Ycoords')}
                channels = len(coords['Xcoords'])
                require(channels > 0 and all(len(v) == channels for v in coords.values()), 'coordinate channel counts differ')
                require(np.equal(coords['Kcoords'], np.floor(coords['Kcoords'])).all(), 'channel shanks must be integral')
                waveforms, sessions, peths = [], [], []
                (staging / 'spike_times').mkdir()
                for unit in range(n):
                    # The author uses the first coordinate reference; reject disagreement
                    # so this independent bridge cannot silently discard a channel map.
                    for name in coords:
                        require(np.array_equal(deref(name, unit).reshape(-1), coords[name]), f'{name} varies by unit')
                    waveform = deref('Waveform', unit)
                    require(waveform.ndim == 2 and waveform.shape[1] == channels, 'source waveform must be samples x channels')
                    waveform = waveform.T
                    require(not waveforms or waveform.shape == waveforms[0].shape, 'inconsistent waveform shape')
                    waveforms.append(waveform)
                    session = deref('SessionIndex', unit).reshape(-1)
                    require(session.size == 1 and session[0] >= 1 and session[0] == math.floor(session[0]), 'session must be positive integer scalar')
                    sessions.append(int(session[0]))
                    times = deref('SpikeTimes', unit).reshape(-1)
                    require(np.all(times >= 0) and np.all(np.diff(times) >= 0), 'spike times must be ordered nonnegative milliseconds')
                    np.save(staging / 'spike_times' / f'Unit{unit}.npy', times, allow_pickle=False)
                    if 'PETH' in g:
                        feature = deref('PETH', unit).squeeze()
                        require(feature.ndim == 1 and len(feature) > 1, 'PETH must be a vector')
                        require(not peths or feature.shape == peths[0].shape, 'inconsistent PETH shape')
                        peths.append(feature)
                unique = sorted(set(sessions))
                require(unique[0] == 1 and unique[-1] == len(unique), 'session indices must be contiguous from one; no silent renumbering')
                arrays = {
                    'waveform_all.npy': np.stack(waveforms),
                    'session_index.npy': np.asarray(sessions, dtype=np.int64),
                    'channel_locations.npy': np.column_stack((coords['Xcoords'], coords['Ycoords'])),
                    'channel_shanks.npy': coords['Kcoords'],
                }
                if peths:
                    arrays['peth.npy'] = np.stack(peths)
                for name, array in arrays.items():
                    np.save(staging / name, array, allow_pickle=False)
        files = [{ 'path': str(p.relative_to(staging)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(staging.rglob('*.npy'))]
        receipt = {
            'task_id': TASK_ID, 'contract_sha256': CONTRACT_SHA256,
            'source_kind': source_kind, 'dataset': dataset, 'source_code_revision': REVISION,
            'source': source_identity,
            'frozen_asset': asset, 'unit_count': n, 'session_count': len(unique),
            'units': [{'unit_id': i, 'session': s} for i, s in enumerate(sessions)],
            'files': files, 'spike_time_unit': 'source values unchanged; pinned settings assume milliseconds; native metadata verification held',
            'unit_identity': 'zero-based position in the original spikeInfo struct; not neuron identity',
            'scientific_qualified': False, 'holds': HOLDS,
        }
        (staging / 'conversion.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        staging.rename(destination)
        return receipt
    except BaseException:
        shutil.rmtree(staging)
        raise

def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_strings(child)

def validate_feature_boundary(method):
    """Check declared execution settings, not merely an exclusion assertion.

    All upstream matching/tuning settings must be supplied; this cannot verify
    whether external executable code actually honored the declared boundary.
    """
    require(method.get('validation_feature') == 'PETH', 'only prospective PETH validation is supported')
    require(method.get('validation_used_for_selection') is False, 'validation feature must not select/tune matches')
    require(method.get('all_matching_settings_supplied') is True, 'complete matching settings declaration required')
    settings = method.get('settings')
    require(isinstance(settings, dict) and bool(settings), 'nonempty matching settings required')
    strings = list(_all_strings(settings))
    require(not any('peth' in x.casefold() for x in strings), 'PETH appears in matching settings; independence violated')
    require(isinstance(method.get('settings_provenance'), str) and bool(method['settings_provenance']), 'settings provenance required')
    require(isinstance(method.get('quality_filter_provenance'), str) and bool(method['quality_filter_provenance']), 'quality-filter provenance required')
    if method.get('role') == 'reference':
        require(method.get('algorithm') == 'UnitMatch', 'reference must be UnitMatch')
        require(method.get('half_waveforms_verified') is True, 'UnitMatch first/second-half waveform availability must be declared')

def _assignment_map(rows, units):
    expected = {(u['dataset'], u['unit_id']) for u in units}
    result = {}
    for row in rows:
        key = (row['dataset'], integer(row['unit_id'], 'unit_id'))
        require(key in expected, 'assignment includes unknown unit')
        require(key not in result, 'duplicate unit assignment')
        label = integer(row['track_id'], 'track_id')
        require(label == -1 or label > 0, 'track_id must be positive or -1 unmatched')
        result[key] = label
    require(set(result) == expected, 'assignments must cover every declared unit exactly once')
    return result

def _fisher_z(a, b):
    # Rescale before centering to avoid overflow/underflow for finite inputs.
    aa = a / max(float(np.max(np.abs(a))), np.finfo(float).tiny)
    bb = b / max(float(np.max(np.abs(b))), np.finfo(float).tiny)
    ac, bc = aa - aa.mean(), bb - bb.mean()
    norm_a, norm_b = float(np.linalg.norm(ac)), float(np.linalg.norm(bc))
    if norm_a == 0 or norm_b == 0:
        return None
    r = float(np.dot(ac / norm_a, bc / norm_b))
    require(-1 - 1e-12 <= r <= 1 + 1e-12, 'correlation outside numeric tolerance')
    r = min(1., max(-1., r))
    if 1 - abs(r) <= CORRELATION_ENDPOINT_TOLERANCE:
        r = math.copysign(1., r)
    return math.copysign(math.inf, r) if abs(r) == 1 else math.atanh(r)

def _per_dataset(dataset_units, assignments, feature_by_key):
    sessions = sorted({u['session'] for u in dataset_units})
    counts = {s: sum(u['session'] == s for u in dataset_units) for s in sessions}
    tracks = defaultdict(list)
    for u in dataset_units:
        key = (u['dataset'], u['unit_id'])
        if assignments[key] > 0:
            tracks[assignments[key]].append(u)
    for members in tracks.values():
        require(len({u['shank'] for u in members}) == 1, 'track crosses probe shanks')
        require(len({u['session'] for u in members}) == len(members), 'track contains multiple units from one session')
        require(len(members) >= 2, 'positive singleton track must be encoded as -1 unmatched')
    matched_counts = {(s,t): 0 for s in sessions for t in sessions if s != t}
    zs, undefined = [], 0
    for members in tracks.values():
        for i, left in enumerate(members):
            for right in members[i+1:]:
                s, t = left['session'], right['session']
                matched_counts[s,t] += 1
                matched_counts[t,s] += 1
                z = _fisher_z(feature_by_key[left['dataset'],left['unit_id']], feature_by_key[right['dataset'],right['unit_id']])
                if z is None:
                    undefined += 1
                else:
                    zs.append(z)
    directional = [{'source_session':s,'target_session':t,'matched_tracks':matched_counts[s,t],
                    'source_units':counts[s], 'fraction':matched_counts[s,t]/counts[s]} for s,t in sorted(matched_counts)]
    mean_z = extended_mean(zs)
    return {
        'unit_count': len(dataset_units), 'session_count': len(sessions),
        'longitudinal_track_count': len(tracks),
        'tracked_unit_fraction': sum(len(v) for v in tracks.values()) / len(dataset_units),
        'all_session_track_count': sum(len(v) == len(sessions) for v in tracks.values()),
        'directional_session_yield': directional,
        'macro_directional_session_yield': extended_mean([r['fraction'] for r in directional]),
        'matched_pair_count': len(zs) + undefined,
        'peth_fisher_z': {'mean': json_number(mean_z), 'defined_pairs': len(zs), 'constant_feature_pairs': undefined,
                          'positive_infinite_pairs': sum(v == math.inf for v in zs), 'negative_infinite_pairs':sum(v == -math.inf for v in zs),
                          'status': 'undefined_or_no_pairs' if mean_z is None else 'defined'},
    }

def evaluate(packet):
    """Score two complete, identity-bound assignment tables on the same population.

    A packet carries protected PETH vectors and should be accessible only to the
    operator, never to the matcher. The returned metrics are diagnostics.
    """
    require(packet.get('task_id') == TASK_ID and packet.get('contract_sha256') == CONTRACT_SHA256, 'wrong task/contract binding')
    kind = packet.get('source_kind')
    require(kind in ('source_asset','generated_engineering_control'), 'invalid source_kind')
    units = packet.get('units')
    require(isinstance(units,list) and bool(units), 'nonempty complete unit inventory required')
    keys = set()
    features = {}
    by_dataset = defaultdict(list)
    for u in units:
        require(u['dataset'] in ROSTER, 'unknown dataset')
        uid = integer(u['unit_id'], 'unit_id')
        session = integer(u['session'], 'session')
        require(integer(u['shank'], 'shank') >= 0, 'shank must be nonnegative integer metadata')
        require(uid >= 0 and session >= 1, 'invalid unit/session identity')
        key = (u['dataset'], uid)
        require(key not in keys, 'duplicate population unit')
        keys.add(key)
        f = finite_array(u['peth'], 'peth')
        require(f.ndim == 1 and len(f) >= 2, 'peth must be vector')
        if kind == 'source_asset':
            require(len(f) == 3000, 'paper PETH comparison requires 3000 press/release/poke bins')
        features[key] = f.astype(float)
        by_dataset[u['dataset']].append(u)
    require(len({len(f) for f in features.values()}) == 1, 'PETH feature lengths differ')
    if kind == 'source_asset':
        require(set(by_dataset) == set(ROSTER), 'all 13 released datasets are required')
        require(packet.get('peth_schema') == 'press_release_poke_3x1000_bins_1ms_plus_minus_500ms', 'paper PETH event/bin schema must be verified')
    require(packet.get('feature_lineage_frozen_before_matching') is True, 'protected feature lineage must be frozen before matching')
    grouping = packet.get('dataset_to_animal')
    require(isinstance(grouping,dict) and set(grouping) == set(by_dataset), 'complete dataset-to-biological-animal grouping required')
    require(all(isinstance(v,str) and v for v in grouping.values()), 'animal group IDs must be nonempty strings')
    for pair in [('EkkoM1','EkkoDMS'),('PunchM1','PunchDMS')]:
        if all(d in grouping for d in pair):
            require(grouping[pair[0]] == grouping[pair[1]], 'same named rat regions cannot cross animal groups')
    require(isinstance(packet.get('animal_grouping_provenance'),str) and packet['animal_grouping_provenance'], 'animal grouping metadata provenance required')
    splits = packet.get('animal_splits')
    require(isinstance(splits,dict) and set(splits) == {'train','validation','test'}, 'three explicit dataset split lists required')
    flattened = [dataset for group in splits.values() for dataset in group]
    require(len(set(flattened)) == len(flattened) and set(flattened) == set(grouping.values()), 'biological animal splits must disjointly cover the full population')
    require(bool(splits['test']), 'held-out test dataset group cannot be empty')
    receipts = packet.get('conversion_receipts')
    require(isinstance(receipts,list) and len(receipts) == len(by_dataset), 'one conversion receipt per dataset required')
    seen = set()
    for receipt in receipts:
        dataset = receipt['dataset']
        require(dataset in by_dataset and dataset not in seen, 'duplicate/unknown conversion dataset')
        seen.add(dataset)
        require(receipt.get('contract_sha256') == CONTRACT_SHA256 and receipt.get('source_code_revision') == REVISION, 'conversion contract/source mismatch')
        require(receipt.get('source_kind') == kind, 'source/control mixing forbidden')
        expected = sorted((u['unit_id'],u['session']) for u in by_dataset[dataset])
        received = sorted((u['unit_id'],u['session']) for u in receipt['units'])
        require(expected == received and receipt['unit_count'] == len(expected), 'population differs from conversion receipt')
        require([x[0] for x in expected] == list(range(len(expected))), 'original unit order must be retained completely')
        sessions = sorted({s for _,s in expected})
        require(sessions[0] == 1 and sessions[-1] == len(sessions), 'complete contiguous sessions required')
        if kind == 'source_asset':
            require(receipt.get('frozen_asset') == ROSTER[dataset] and receipt['source']['bytes'] == ROSTER[dataset]['bytes'], 'source asset receipt mismatch')
    methods = packet.get('methods')
    require(isinstance(methods,list) and len(methods) == 2 and {m.get('role') for m in methods} == {'candidate','reference'}, 'candidate and UnitMatch reference required')
    require(methods[0].get('quality_filter_provenance') == methods[1].get('quality_filter_provenance'), 'candidate/reference quality filters differ')
    outputs = {}
    for method in methods:
        validate_feature_boundary(method)
        assignments = _assignment_map(method['assignments'],units)
        datasets = {dataset:_per_dataset(rows,assignments,features) for dataset,rows in sorted(by_dataset.items())}
        biological = {}
        for animal in sorted(set(grouping.values())):
            members = [d for d in datasets if grouping[d] == animal]
            ys = [datasets[d]['macro_directional_session_yield'] for d in members if datasets[d]['macro_directional_session_yield'] is not None]
            zs = []
            for d in members:
                z = datasets[d]['peth_fisher_z']['mean']
                if isinstance(z,(int,float)):
                    zs.append(z)
                elif z in ('positive_infinity','negative_infinity'):
                    zs.append(math.inf if z == 'positive_infinity' else -math.inf)
            biological[animal] = {'datasets':members, 'dataset_count':len(members), 'datasets_with_defined_yield':len(ys), 'datasets_with_defined_peth_z':len(zs), 'macro_dataset_directional_yield':json_number(extended_mean(ys)), 'macro_dataset_peth_fisher_z':json_number(extended_mean(zs))}
        groups = {}
        for split, names in splits.items():
            yields, zs = [], []
            for animal in names:
                y = biological[animal]['macro_dataset_directional_yield']
                if y is not None:
                    yields.append(y)
                z = biological[animal]['macro_dataset_peth_fisher_z']
                if isinstance(z,(int,float)):
                    zs.append(z)
                elif z in ('positive_infinity','negative_infinity'):
                    zs.append(math.inf if z == 'positive_infinity' else -math.inf)
            groups[split] = {'animal_count':len(names), 'animals_with_yield':len(yields), 'macro_animal_directional_yield':json_number(extended_mean(yields)), 'animals_with_defined_peth_z':len(zs), 'macro_animal_peth_fisher_z':json_number(extended_mean(zs))}
        outputs[method['role']] = {'algorithm':method.get('algorithm'), 'datasets':datasets,'biological_animals':biological,'animal_split_summary':groups}
    paired = {}
    for dataset in sorted(by_dataset):
        a,b = outputs['candidate']['datasets'][dataset],outputs['reference']['datasets'][dataset]
        az,bz = a['peth_fisher_z']['mean'],b['peth_fisher_z']['mean']
        ay,by = a['macro_directional_session_yield'],b['macro_directional_session_yield']
        paired[dataset] = {'directional_yield_difference':None if ay is None or by is None else ay-by,
                          'peth_fisher_z_difference':az-bz if isinstance(az,(int,float)) and isinstance(bz,(int,float)) else None}
    return {'task_id':TASK_ID,'contract_sha256':CONTRACT_SHA256,'source_kind':kind,
            'assessment':'prospective_diagnostic_not_registered_reward','methods':outputs,'paired_candidate_minus_reference':paired,
            'population':{'dataset_count':len(by_dataset),'biological_animal_count':len(set(grouping.values())),'unit_count':len(units),'all_13_datasets_present':set(by_dataset)==set(ROSTER)},
            'scientific_qualified':False,'full_contract_complete':False,'native_runs_performed':0,
            'identity_accuracy':None,'probability_calibration':None,'motion_accuracy':None,'holds':HOLDS}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    conv = sub.add_parser('convert')
    conv.add_argument('source'); conv.add_argument('destination'); conv.add_argument('--dataset',choices=sorted(ROSTER),required=True)
    conv.add_argument('--generated-engineering-control',action='store_true')
    score = sub.add_parser('score')
    score.add_argument('packet'); score.add_argument('output')
    args = parser.parse_args()
    if args.command == 'convert':
        result = convert_spikeinfo(args.source,args.destination,args.dataset,source_kind='generated_engineering_control' if args.generated_engineering_control else 'source_asset')
        print(json.dumps(result,indent=2,allow_nan=False))
    else:
        result = evaluate(json.loads(Path(args.packet).read_text()))
        with Path(args.output).open('x') as out:
            json.dump(result,out,indent=2,allow_nan=False)
            out.write('\n')

if __name__ == '__main__':
    main()
