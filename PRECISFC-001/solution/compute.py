"""Offline MSC censoring sensitivity; no source acquisition or execution on import."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import platform
import stat
import sys

import nibabel as nib
import numpy as np

METHOD_SHA256 = '497b436132ee5723c3f7209489d77477fe2412ade1190f9aa95d0baf7bf9cda6'
SOURCE_SHA256 = '4f7fc73e548cfdf744fabbc382cebdd1edff968fe6edd7c1ca846958a1fbb967'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reject_links(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink path or ancestor refused')
    return path.resolve(strict=False)


def prepare_destinations(source, output, private):
    paths = [reject_links(p) for p in (source, output, private)]
    for a, b in itertools.combinations(paths, 2):
        require(a != b and a not in b.parents and b not in a.parents,
                'Source, output and private directories must be disjoint and non-nested')
    for path in paths[1:]:
        require(not path.exists() or (path.is_dir() and not any(path.iterdir())),
                'Refuse existing output/private evidence')
    for path in paths[1:]:
        path.mkdir(parents=True, exist_ok=True)
    return paths


def stage_helper_path(script_path=__file__):
    local = Path(script_path).resolve().parents[1]/'environment'/'stage_data.py'
    return local if local.is_file() else Path('/opt/source/stage_data.py')


def load_inputs(data_dir, method_path):
    method_path = reject_links(method_path)
    require(method_path.is_file() and stat.S_ISREG(method_path.stat().st_mode), 'Method must be a regular file')
    raw = method_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == METHOD_SHA256, 'Frozen public method SHA256 mismatch')
    method = json.loads(raw)
    helper = reject_links(stage_helper_path())
    require(helper.is_file(), 'Offline source integrity helper unavailable')
    spec = importlib.util.spec_from_file_location('precisfc_integrity', helper)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    manifest = module.verify_staged(data_dir)
    manifest_raw = (Path(data_dir)/'source_manifest.json').read_bytes()
    require(hashlib.sha256(manifest_raw).hexdigest() == SOURCE_SHA256 == method['source']['source_manifest_sha256'],
            'Frozen source manifest SHA256 mismatch')
    records = {(r['subject'], r['session'], r['role']): r for r in manifest['files'] if r['role'] in ('bold','tmask')}
    auxiliary = {r['role']: Path(data_dir)/r['path'] for r in manifest['files'] if r['role'] not in ('bold','tmask')}
    return dict(root=Path(data_dir), method=method, manifest=manifest, records=records, auxiliary=auxiliary)


def inspect_header(path, expected, subject, session):
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(352)
    require(len(raw) == 352, 'Truncated original NIfTI header')
    header = nib.Nifti1Header(binaryblock=raw[:348], check=True)
    image = nib.load(path)
    qform, qcode = header.get_qform(coded=True)
    sform, scode = header.get_sform(coded=True)
    units = header.get_xyzt_units()
    observed = dict(subject_id=subject, session_id=session, shape=list(header.get_data_shape()),
        stored_dtype=header.get_data_dtype().name, byte_order='little' if header.endianness == '<' else 'big',
        voxel_offset_bytes=int(header['vox_offset']), spatial_zooms_mm=[float(x) for x in header.get_zooms()[:3]],
        xyzt_units_code=int(header['xyzt_units']), spatial_unit=units[0], temporal_unit=units[1],
        qform_code=int(qcode), qform=None if qform is None else qform.tolist(),
        sform_code=int(scode), sform=None if sform is None else sform.tolist(),
        raw_scl_slope=float(header['scl_slope']), raw_scl_inter=float(header['scl_inter']),
        effective_scale=float(image.dataobj.slope), effective_offset=float(image.dataobj.inter),
        raw_header_tr_seconds=float(header.get_zooms()[3]), description=bytes(header['descrip']).rstrip(b'\0').decode('ascii'))
    for key, value in expected.items():
        if key == 'description_required_suffix':
            require(observed['description'].endswith(value), 'Unexpected original conversion description')
        else:
            require(observed[key] == value, 'Original header mismatch: '+key)
    require(np.array_equal(image.affine, np.asarray(expected['sform'])), 'Nibabel affine differs from original sform')
    return observed


def sphere_geometry(coords, affine, shape, transform, radius=5.0):
    coords = np.asarray(coords, dtype=np.float64)
    centres = (np.asarray(transform, dtype=np.float64) @ np.column_stack((coords, np.ones(len(coords)))).T).T[:, :3]
    ijk = np.indices(shape, dtype=np.int64).reshape(3, -1).T
    world = (np.asarray(affine, dtype=np.float64) @ np.column_stack((ijk, np.ones(len(ijk)))).T).T[:, :3]
    members, boundary = [], []
    for centre in centres:
        delta = world - centre
        d2 = (delta[:, 0]*delta[:, 0] + delta[:, 1]*delta[:, 1]) + delta[:, 2]*delta[:, 2]
        selected = ijk[d2 <= radius*radius]
        require(len(selected) > 0, 'Empty source sphere; no nearest-voxel rescue')
        members.append(selected); boundary.append(float(np.min(np.abs(d2-radius*radius))))
    offsets = np.concatenate(([0], np.cumsum([len(x) for x in members]))).astype(np.int64)
    membership = np.concatenate(members)
    union, inverse = np.unique(membership, axis=0, return_inverse=True)
    return dict(centres=centres, offsets=offsets, ijk=membership, union=union, membership_to_union=inverse,
                boundary=np.asarray(boundary))


def stable_vector(values):
    x = np.asarray(values, dtype=np.float64)
    require(x.ndim == 1 and np.isfinite(x).all(), 'Vector must be one-dimensional and finite')
    n = len(x)
    if n < 2:
        return dict(status='insufficient_frames', raw_l2=None, centered_l2=None, zero_bound=None, unit=None)
    scale = float(np.max(np.abs(x)))
    if scale == 0:
        return dict(status='constant', raw_l2=0.0, centered_l2=0.0, zero_bound=0.0, unit=None)
    exact = bool(np.max(x) == np.min(x))
    if exact:
        raw, centered, c = float(np.sqrt(n)), 0.0, None
    else:
        u = x/scale; c = u-np.mean(u)
        raw = float(np.sqrt(np.sum(u*u))); centered = float(np.sqrt(np.sum(c*c)))
    bound = 10*n*np.finfo(np.float64).eps*raw
    diagnostics = [scale*raw, scale*centered, scale*bound]
    require(np.isfinite(diagnostics).all(), 'Nonfinite original-unit norm or bound')
    status = 'constant' if exact else ('numerically_constant' if centered <= bound else 'ok')
    return dict(status=status, raw_l2=diagnostics[0], centered_l2=diagnostics[1], zero_bound=diagnostics[2],
                unit=c/centered if status == 'ok' else None)


def clamp_pearson(value):
    value = np.asarray(value, dtype=np.float64)
    require(np.isfinite(value).all() and np.all(np.abs(value) <= 1+1e-12), 'Invalid Pearson coefficient')
    return np.clip(value, -1, 1)


def pair_measure(a, b):
    first, second = stable_vector(a), stable_vector(b)
    statuses = {first['status'], second['status']}
    if 'insufficient_frames' in statuses:
        status = 'insufficient_common_edges'
    elif 'constant' in statuses:
        status = 'constant_edge_vector'
    elif 'numerically_constant' in statuses:
        status = 'numerically_constant_edge_vector'
    else:
        status = 'ok'
    value = float(clamp_pearson(np.dot(first['unit'], second['unit']))) if status == 'ok' else None
    return first, second, value, status


def load_mask(path, n_frames):
    mask = np.loadtxt(path, dtype=np.float64)
    require(mask.ndim == 1 and len(mask) == n_frames and np.isfinite(mask).all()
            and np.isin(mask, [0, 1]).all(), 'Source mask must be exactly one finite binary entry per frame')
    return mask.astype(bool)


def source_means(path, geometry, expected_shape):
    image = nib.load(path)
    values = np.asanyarray(image.dataobj)
    require(values.shape == tuple(expected_shape) and values.dtype == np.dtype('<f4'), 'Source array shape/dtype mismatch')
    require(np.isfinite(values).all(), 'Nonfinite original BOLD value; no dropping or imputation')
    union = geometry['union']
    selected = values[union[:, 0], union[:, 1], union[:, 2], :].T.copy()
    del values, image
    offsets, inverse = geometry['offsets'], geometry['membership_to_union']
    means = np.empty((selected.shape[0], len(offsets)-1), dtype=np.float64)
    peak = np.empty(len(offsets)-1, dtype=np.float64)
    for roi, (start, end) in enumerate(zip(offsets[:-1], offsets[1:])):
        voxels = selected[:, inverse[start:end]]
        means[:, roi] = np.mean(voxels, axis=1, dtype=np.float64)
        peak[roi] = float(np.max(np.abs(voxels)))
    require(np.isfinite(means).all() and np.isfinite(peak).all(), 'Nonfinite ROI reduction')
    return means, peak, selected


def derive_connectomes(means, masks, run_keys, arm_names):
    n_runs, _, n_rois = means.shape
    status = np.empty((n_runs, 2, n_rois), dtype='<U24')
    norms = {k: np.full((n_runs, 2, n_rois), np.nan) for k in ('raw_l2','centered_l2','zero_bound')}
    units, roi_rows = {}, []
    for run, (subject, session) in enumerate(run_keys):
        for arm, name in enumerate(arm_names):
            values = means[run] if name == 'all_frames' else means[run, masks[run]]
            unit = np.zeros_like(values)
            for roi in range(n_rois):
                result = stable_vector(values[:, roi]); status[run, arm, roi] = result['status']
                for key in norms:
                    norms[key][run, arm, roi] = np.nan if result[key] is None else result[key]
                if result['unit'] is not None:
                    unit[:, roi] = result['unit']
                roi_rows.append(dict(subject_id=subject, session_id=session, arm=name, roi_id=roi+1,
                    n_frames=len(values), status=result['status'], **{key:result[key] for key in norms}))
            units[run, arm] = unit
    common = np.all(status == 'ok', axis=(0, 1))
    for row in roi_rows:
        row['common_roi'] = bool(common[row['roi_id']-1])
    edge_i, edge_j = np.triu_indices(n_rois, 1)
    valid = common[edge_i] & common[edge_j]
    raw = np.full((n_runs, 2, len(edge_i)), np.nan)
    common_ids = np.flatnonzero(common)
    common_lookup = np.full(n_rois, -1, dtype=int); common_lookup[common_ids] = np.arange(len(common_ids))
    for key, unit in units.items():
        active = unit[:, common]
        correlations = clamp_pearson(active.T @ active)
        raw[key][valid] = correlations[common_lookup[edge_i[valid]], common_lookup[edge_j[valid]]]
    z = np.arctanh(np.clip(raw, -.999, .999))
    arrays = dict(common_roi=common, edge_roi_ids=np.column_stack((edge_i+1, edge_j+1)),
                  edge_valid=valid, raw_r=raw, fisher_z=z)
    private = dict(roi_status=status, **{'roi_'+key: value for key, value in norms.items()})
    return arrays, roi_rows, private


def summaries(arrays, masks, run_keys, method, roi_rows, status):
    subjects = list(dict.fromkeys(subject for subject, _ in run_keys))
    sessions, arms = method['source']['sessions'], method['numerics']['arm_names']
    lookup = {key: i for i, key in enumerate(run_keys)}
    n_candidates, n_common = len(arrays['edge_valid']), int(np.sum(arrays['edge_valid']))
    qc_rows, pair_rows, person_rows = [], [], []
    for run, (subject, session) in enumerate(run_keys):
        n_retained = int(np.sum(masks[run])); seconds = n_retained*11/5
        qc_rows.append(dict(subject_id=subject, session_id=session, n_frames=masks.shape[1], n_retained=n_retained,
            n_excluded=masks.shape[1]-n_retained, header_tr_seconds=1, analysis_tr_seconds=2.2,
            tr_policy=method['timing']['policy_id'], retained_seconds=seconds, retained_minutes=seconds/60,
            duration_qc_pass=11*n_retained >= 3000))
    for subject in subjects:
        qcs = [r for r in qc_rows if r['subject_id'] == subject]
        person = dict(subject_id=subject, n_sessions=len(sessions), n_frames_total=sum(r['n_frames'] for r in qcs),
            n_frames_retained=sum(r['n_retained'] for r in qcs),
            minimum_retained_seconds=min(r['retained_seconds'] for r in qcs),
            minimum_retained_minutes=min(r['retained_minutes'] for r in qcs),
            qc_pass=all(r['duration_qc_pass'] for r in qcs), n_pairs_expected=3)
        for arm, name in enumerate(arms):
            defined = []
            for sa, sb in method['numerics']['session_pairs']:
                a = arrays['fisher_z'][lookup[subject, sa], arm, arrays['edge_valid']]
                b = arrays['fisher_z'][lookup[subject, sb], arm, arrays['edge_valid']]
                da, db, value, pair_status = pair_measure(a, b)
                row = dict(subject_id=subject, arm=name, session_a=sa, session_b=sb,
                    n_candidate_edges=n_candidates, n_common_edges=n_common, pair_r=value, status=pair_status)
                row.update({key+'_'+suffix: result[key] for suffix, result in (('a',da),('b',db))
                            for key in ('raw_l2','centered_l2','zero_bound')})
                pair_rows.append(row)
                if value is not None:
                    defined.append(value)
            person[name+'_n_pairs_defined'] = len(defined)
            person['reliability_'+name] = float(np.mean(defined)) if len(defined) == 3 else None
            person[name+'_status'] = 'ok' if len(defined) == 3 else 'incomplete_pairs'
        person_rows.append(person)
    qc_ids = [p['subject_id'] for p in person_rows if p['qc_pass']]
    excluded = [p['subject_id'] for p in person_rows if not p['qc_pass']]
    groups = {}
    for label, ids in (('all_six', subjects), ('conditional_qc', qc_ids)):
        for arm in arms:
            values = [p['reliability_'+arm] for p in person_rows if p['subject_id'] in ids]
            defined = [value for value in values if value is not None]
            group_status = 'empty_qc_subset' if not ids else ('ok' if len(defined) == len(ids) else 'incomplete_subjects')
            groups[label+'_'+arm] = dict(value=float(np.mean(defined)) if group_status == 'ok' else None,
                status=group_status, n_expected=len(ids), n_defined=len(defined))
    result = dict(status=status, pipeline_id=method['pipeline_id'], n_subjects=len(subjects),
        n_sessions_per_subject=len(sessions), n_runs=len(run_keys), n_rois=len(arrays['common_roi']),
        n_candidate_edges=n_candidates, n_common_rois=int(np.sum(arrays['common_roi'])), n_common_edges=n_common,
        n_frames_total=int(masks.size), n_frames_retained=int(np.sum(masks)),
        qc_included_subject_ids=qc_ids, qc_excluded_subject_ids=excluded, group_mean_reliability=groups,
        roi_status_counts=dict(Counter(r['status'] for r in roi_rows)),
        pair_status_counts=dict(Counter(r['status'] for r in pair_rows)),
        fisher_clip_counts={name:int(np.sum(np.abs(arrays['raw_r'][:, arm, :]) > .999)) for arm,name in enumerate(arms)})
    if status == 'resource_pilot':
        result['resource_pilot_scope'] = dict(subject_ids=subjects, n_runs=len(run_keys),
            common_support='pilot runs only; no full-cohort conclusions',
            group_key_limitation='all_six labels are schema placeholders for this one-person resource pilot only')
    return qc_rows, pair_rows, person_rows, result


def metadata(inputs, headers, result):
    keys = ('n_common_rois','n_common_edges','n_frames_total','n_frames_retained','qc_included_subject_ids',
            'qc_excluded_subject_ids','roi_status_counts','pair_status_counts')
    source_files = []
    for item in inputs['manifest']['files']:
        if item['role'] in ('bold','tmask'):
            row = {key:item[key] for key in ('role','path','size_bytes','sha256','published_md5','git_blob_sha1','version_id','etag')}
            row.update(subject_id=item['subject'], session_id=item['session']); source_files.append(row)
    return dict(status=result['status'], pipeline_id=inputs['method']['pipeline_id'], method_contract=inputs['method'],
        method_contract_sha256=METHOD_SHA256, source_manifest_sha256=SOURCE_SHA256, source_files=source_files,
        source_observed=dict(n_subjects=6, n_runs=18, n_original_files=36, headers=headers,
            timing_policy=inputs['method']['timing'], original_files_modified=False),
        analysis_observed={key:result[key] for key in keys},
        software_versions=dict(python=platform.python_version(), numpy=np.__version__, nibabel=nib.__version__))


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def write_csv(path, columns, rows):
    with Path(path).open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='raise'); writer.writeheader()
        for row in rows:
            writer.writerow({key:('' if row[key] is None else int(row[key]) if isinstance(row[key], (bool,np.bool_)) else row[key])
                             for key in columns})


def save_npz(path, arrays):
    require(all(not np.asarray(value).dtype.hasobject for value in arrays.values()), 'Object arrays forbidden')
    with Path(path).open('xb') as stream:
        np.savez_compressed(stream, **arrays)


def run(data_dir, method_path, output_dir, private_dir, pilot_subject=None):
    inputs = load_inputs(data_dir, method_path)
    method, root, records = inputs['method'], inputs['root'], inputs['records']
    subjects, sessions = method['source']['subjects'], method['source']['sessions']
    require(pilot_subject in (None, 'MSC01'), 'Only the prospectively declared MSC01 resource pilot is supported')
    all_keys = list(itertools.product(subjects, sessions))
    headers = [inspect_header(root/records[s,t,'bold']['path'], method['source']['expected_header'], s, t) for s,t in all_keys]
    with inputs['auxiliary']['atlas_coordinates'].open(newline='', encoding='utf-8') as stream:
        atlas = list(csv.DictReader(stream))
    roi_ids = np.asarray([int(row['ROI']) for row in atlas], dtype=np.int64)
    require(np.array_equal(roi_ids, np.arange(1, 265)), 'Original atlas ROI identities/order changed')
    coords = np.asarray([[float(row[key]) for key in ('X','Y','Z')] for row in atlas], dtype=np.float64)
    require(np.isfinite(coords).all(), 'Nonfinite original coordinates')
    lines = inputs['auxiliary']['point_transform'].read_text().splitlines()
    start = lines.index('t4')+1
    transform = np.asarray([[float(x) for x in line.split()] for line in lines[start:start+4]])
    require(np.array_equal(transform, np.asarray(method['geometry']['mni_to_world_matrix'])), 'Published point transform changed')
    geometry = sphere_geometry(coords, method['source']['expected_header']['sform'],
        method['source']['expected_header']['shape'][:3], transform, method['geometry']['radius_mm'])
    geometry_rows = []
    for i, (mni, world) in enumerate(zip(coords, geometry['centres'])):
        geometry_rows.append(dict(roi_id=int(roi_ids[i]), geometry_id=method['geometry']['geometry_id'],
            mni_x_mm=float(mni[0]), mni_y_mm=float(mni[1]), mni_z_mm=float(mni[2]),
            world_x_mm=float(world[0]), world_y_mm=float(world[1]), world_z_mm=float(world[2]), radius_mm=5,
            n_voxels=int(geometry['offsets'][i+1]-geometry['offsets'][i]), boundary_min_abs_mm2=float(geometry['boundary'][i])))
    run_keys = [key for key in all_keys if pilot_subject is None or key[0] == pilot_subject]
    means, peaks, masks, private = [], [], [], {}
    for subject, session in run_keys:
        mask = load_mask(root/records[subject,session,'tmask']['path'], method['source']['expected_header']['shape'][3])
        mean, peak, voxels = source_means(root/records[subject,session,'bold']['path'], geometry,
                                         method['source']['expected_header']['shape'])
        means.append(mean); peaks.append(peak); masks.append(mask)
        private['source_voxel_ijk_'+subject+'_'+session] = geometry['union']
        private['source_voxels_'+subject+'_'+session] = voxels
        print('Source reduced: '+subject+' '+session, flush=True)
    means, masks = np.stack(means), np.stack(masks)
    derived, roi_rows, diagnostics = derive_connectomes(means, masks, run_keys, method['numerics']['arm_names'])
    arrays = dict(run_subject=np.asarray([s for s,t in run_keys]), run_session=np.asarray([t for s,t in run_keys]),
        roi_ids=roi_ids, arm_names=np.asarray(method['numerics']['arm_names']),
        frame_indices=np.tile(np.arange(means.shape[1], dtype=np.int64), (len(run_keys), 1)), tmask=masks,
        roi_means=means, roi_source_peak_abs=np.stack(peaks), voxel_offsets=geometry['offsets'], voxel_ijk=geometry['ijk'], **derived)
    require(set(arrays) == set(method['outputs']['connectivity_arrays.npz']['arrays']), 'Public primitive schema mismatch')
    status = 'resource_pilot' if pilot_subject else 'ok'
    qc_rows, pair_rows, person_rows, result = summaries(arrays, masks, run_keys, method, roi_rows, status)
    observed = metadata(inputs, headers, result)
    if pilot_subject:
        observed['resource_pilot_scope'] = result['resource_pilot_scope']
    private.update(arrays); private.update(diagnostics)
    private.update(metadata_json=np.asarray(json.dumps(observed, allow_nan=False)),
                   results_json=np.asarray(json.dumps(result, allow_nan=False)))
    output_dir, private_dir = Path(output_dir), Path(private_dir)
    tables = {'session_qc.csv':qc_rows, 'roi_geometry.csv':geometry_rows, 'roi_status.csv':roi_rows,
              'session_pairs.csv':pair_rows, 'reliability.csv':person_rows}
    for filename, rows in tables.items():
        write_csv(output_dir/filename, method['outputs'][filename]['columns'], rows)
    save_npz(output_dir/'connectivity_arrays.npz', arrays)
    # Evidence must exist before any complete-status marker is published.
    save_npz(private_dir/'analysis_arrays.npz', private)
    findings = ['# Released-session connectivity sensitivity', '',
        'Scope: '+('MSC01 resource pilot only; common support is pilot-only, not the full cohort.' if pilot_subject else
                  'All six fixed people and all three released sessions; both frame-selection arms remain primary.'), '',
        f"Common support: {result['n_common_rois']} ROIs and {result['n_common_edges']} edges.", '',
        '| Population / arm | People defined / expected | Mean within-person similarity |',
        '|---|---:|---:|']
    for name, entry in result['group_mean_reliability'].items():
        value = 'undefined ('+entry['status']+')' if entry['value'] is None else format(entry['value'], '.8g')
        findings.append(f"| {name} | {entry['n_defined']} / {entry['n_expected']} | {value} |")
    findings.extend(['', 'The conditional duration-QC subset is descriptive, not a causal motion intervention. '
        'The source is already processed, including interpolation/filtering. The recorded header interval remains 1 second; '
        'the declared 2.2-second acquisition-frame assumption is used only for duration accounting. '
        'The operational point bridge does not establish registration accuracy. Overlapping pairs and edges are not '
        'independent people, and within-person similarity alone is not individual identification or a paper-finding replication.'])
    with (output_dir/'findings.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(findings)+'\n')
    write_json(output_dir/'reliability_stats.json', result)
    write_json(output_dir/'run_metadata.json', observed)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='/app/data/precisfc')
    parser.add_argument('--method-contract', default='/app/method_contract.json')
    parser.add_argument('--output-dir', default='/app/output')
    parser.add_argument('--private-dir', default='/app/oracle_private')
    parser.add_argument('--pilot-subject', choices=['MSC01'])
    args = parser.parse_args(argv)
    ready = False
    try:
        prepare_destinations(args.data_dir, args.output_dir, args.private_dir); ready = True
        result = run(args.data_dir, args.method_contract, args.output_dir, args.private_dir, args.pilot_subject)
        print(json.dumps({key:result[key] for key in ('status','n_runs','n_common_rois','n_common_edges')}, allow_nan=False))
        return 0
    except Exception as error:
        if ready:
            failure = dict(status='failed_precondition', reason=str(error) or type(error).__name__,
                           error_type=type(error).__name__, method_contract_sha256=METHOD_SHA256,
                           source_manifest_sha256=SOURCE_SHA256)
            for filename in ('failure.json','reliability_stats.json','run_metadata.json'):
                target = Path(args.output_dir)/filename
                if not target.exists():
                    write_json(target, failure)
            findings = Path(args.output_dir)/'findings.md'
            if not findings.exists():
                with findings.open('x', encoding='utf-8') as stream:
                    stream.write('Failed precondition: '+failure['reason']+'\nNo complete scientific result is claimed.\n')
        print(type(error).__name__+': '+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
