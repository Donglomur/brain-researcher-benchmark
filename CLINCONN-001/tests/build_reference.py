"""Third original-source bank route; no oracle imports or answer-array inputs.

Shares low-level nibabel reading and public SciPy filter/QR primitives, but has
its own source parsing, bincount reductions, cleaning and source construction.
Statistics/parsing helpers are shared with this grader, not the oracle. Native
oracle output is an optional post-construction validation target only.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import time

import nibabel as nib
import numpy as np
import scipy
from scipy import linalg, signal

import connectivity_contract as q
import proof_of_work as pw


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def no_symlinks(path):
    path = Path(path).absolute()
    q.require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlinked evidence/source path')
    return path


def destinations(source, output, report):
    source, output, report = [no_symlinks(p) for p in (source, output, report)]
    q.require(output != report and output not in report.parents and report not in output.parents,
              'Evidence destinations overlap')
    for path in (output, report):
        q.require(not path.exists(), 'Preserve existing evidence')
        q.require(path != source and source not in path.parents and path not in source.parents,
                  'Evidence cannot be inside/overlap original source')
    return source, output, report


def read_inputs(source_dir, method_path):
    root = no_symlinks(source_dir); method_path = no_symlinks(method_path)
    manifest_path = no_symlinks(root/'source_manifest.json')
    q.require(sha256(method_path) == pw.METHOD_SHA256, 'Frozen public method mismatch')
    q.require(sha256(manifest_path) == pw.SOURCE_MANIFEST_SHA256, 'Frozen source manifest mismatch')
    method, manifest = q.json_load(method_path), q.json_load(manifest_path)
    q.require(manifest['n_files'] == len(manifest['files']) == 697, 'Wrong original inventory')
    records = {}; paths = {}; hashes = {}
    for row in manifest['files']:
        relative = row['path']; normalized = PurePosixPath(relative)
        q.require(isinstance(relative, str) and not normalized.is_absolute() and
                  all(x not in ('', '.', '..') for x in relative.split('/')) and
                  '\\' not in relative and str(normalized) == relative, 'Unsafe source member')
        q.require(relative not in records, 'Duplicate source member')
        path = no_symlinks(root/relative)
        q.require(path.is_file() and path.stat().st_size == row['size_bytes'], 'Missing/changed source size')
        q.require(sha256(path) == row['sha256'], 'Original source SHA-256 mismatch')
        records[relative] = row; paths[relative] = path; hashes[relative] = row['sha256']
    allowed = set(paths) | {'source_manifest.json'}
    allowed_dirs = {str(p) for name in allowed for p in PurePosixPath(name).parents if str(p) != '.'}
    found = set()
    for path in root.rglob('*'):
        q.require(not path.is_symlink(), 'Symlink in source inventory')
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            found.add(relative)
        else:
            q.require(path.is_dir() and relative in allowed_dirs, 'Unexpected source directory/special file')
    q.require(found == allowed, 'Original source inventory changed')
    return dict(root=root, method=method, manifest=manifest, records=records, paths=paths, hashes=hashes,
                method_contract_json=method_path.read_text(), source_manifest_json=manifest_path.read_text())


def role_path(inputs, role, subject=None):
    rows = [r for r in inputs['records'].values() if r['role'] == role and
            (subject is None or r.get('participant') == subject)]
    q.require(len(rows) == 1, 'Ambiguous original source role')
    return inputs['paths'][rows[0]['path']], rows[0]


def source_cohort(inputs):
    with inputs['paths']['metadata/participants.tsv'].open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t'); rows = list(reader)
    q.require(len(rows) == 272 and len({r['participant_id'] for r in rows}) == 272, 'Wrong original phenotype table')
    frozen = {r['participant_id']: r for r in inputs['manifest']['cohort']['rows']}
    output = []
    for index, row in enumerate(rows):
        if row['rest'] != '1' or row['diagnosis'] not in ('SCHZ', 'CONTROL'):
            continue
        sid = row['participant_id']; expected = frozen.get(sid)
        q.require(expected and expected['diagnosis'] == row['diagnosis'], 'Availability/phenotype mismatch')
        available = {}
        for role in ('surface_left', 'surface_right', 'confounds'):
            available[role] = any(r['role'] == role and r.get('participant') == sid for r in inputs['records'].values())
        selected = all(available.values())
        q.require(selected == expected['selected'], 'Source availability changed')
        output.append(dict(source_participant_row=index, subject_id=sid, group=row['diagnosis'], source_rest=1,
            available_left=available['surface_left'], available_right=available['surface_right'],
            available_confounds=available['confounds'], selected=selected,
            exclusion_reason='selected' if selected else 'unavailable_released_derivatives'))
    output.sort(key=lambda r: r['subject_id'])
    q.require(len(output) == 177 and sum(r['selected'] for r in output) == 172, 'Incomplete frozen candidate cohort')
    q.require(sorted(r['subject_id'] for r in output if not r['selected']) ==
              sorted(inputs['method']['cohort']['unavailable_released_derivatives']), 'Unapproved participant exclusion')
    return output


def source_atlas(inputs):
    method = inputs['method']; required = method['outputs']['run_metadata.json']['source_observed']['atlas']['required_value']
    atlas = {k: v for k, v in required.items() if k != 'hemispheres'}
    atlas['hemispheres'] = {}; rows = []; groups = {}
    for hemisphere, name in [('L', 'left'), ('R', 'right')]:
        annot_path, annot_record = role_path(inputs, 'annotation_'+name)
        mesh_path, mesh_record = role_path(inputs, 'pial_'+name)
        labels, colors, names = nib.freesurfer.read_annot(annot_path, orig_ids=False)
        names = [n.decode('utf8') for n in names]
        image = nib.load(mesh_path)
        pointsets = [d for d in image.darrays if d.intent == 1008]
        triangles = [d for d in image.darrays if d.intent == 1009]
        q.require(len(pointsets) == len(triangles) == 1, 'Wrong pial intents')
        points = pointsets[0]; xyz = np.asarray(points.data, dtype=np.float64); faces = triangles[0].data
        q.require(xyz.shape == (10242, 3) and labels.shape == (10242,) and np.isfinite(xyz).all(), 'Invalid original pial/annotation dimensions')
        q.require(faces.shape == (20480, 3) and faces.dtype.kind in 'iu' and faces.min() >= 0 and faces.max() < len(xyz), 'Invalid source triangles')
        q.require(names[0] == 'Unknown' and names[42] == 'Medial_wall' and len(names) == 76, 'Original annotation legend changed')
        meta = dict(points.meta)
        observed = dict(annotation_sha256=annot_record['sha256'], pial_sha256=mesh_record['sha256'],
            n_vertices=len(labels), n_faces=len(faces), n_annotation_rows=len(names),
            unknown_annotation_index=0, medial_wall_annotation_index=42,
            n_unknown_vertices=int(np.sum(labels == 0)), n_medial_wall_vertices=int(np.sum(labels == 42)),
            n_unassigned_vertices=int(np.sum(labels == -1)),
            pointset_structure=meta.get('AnatomicalStructurePrimary'), pointset_surface=meta.get('AnatomicalStructureSecondary'),
            pointset_dataspace=int(points.coordsys.dataspace), pointset_xformspace=int(points.coordsys.xformspace),
            pointset_xform=np.asarray(points.coordsys.xform, float).tolist())
        q.match(observed, required['hemispheres'][hemisphere], 'original atlas', 'exact', closed=True)
        atlas['hemispheres'][hemisphere] = observed
        q.require(np.all((labels >= -1) & (labels < len(names))), 'Unknown original label index')
        indices = ([-1] if np.any(labels == -1) else [])+list(range(len(names)))
        included = []
        for index in indices:
            label = 'unassigned' if index == -1 else names[index]
            mask = labels == index; count = int(mask.sum())
            reason = 'unassigned' if index == -1 else method['geometry']['exclude_names'].get(label)
            reason = reason or ('empty_label' if count == 0 else 'included')
            center = xyz[mask].mean(axis=0) if count else [None]*3
            pid = f'{hemisphere}:{index}'
            rows.append(dict(parcel_id=pid, hemisphere=hemisphere, annotation_index=index,
                annotation_name=label, n_vertices=count, included=reason == 'included', exclusion_reason=reason,
                **{'centroid_'+axis: None if value is None else float(value) for axis, value in zip('xyz', center)}))
            if reason == 'included':
                included.append(index)
        q.require(len(included) == 74, 'Unexpected cortical parcel catalogue')
        groups[hemisphere] = dict(labels=labels, included=np.array(included, int), n_labels=len(names))
    included_rows = [r for r in rows if r['included']]
    centers = np.array([[r['centroid_'+axis] for axis in 'xyz'] for r in included_rows], float)
    ii, jj = np.triu_indices(len(included_rows), 1)
    edges = [dict(edge_id=index, parcel_i=included_rows[i]['parcel_id'], parcel_j=included_rows[j]['parcel_id'],
        distance=float(np.linalg.norm(centers[i]-centers[j]))) for index, (i, j) in enumerate(zip(ii, jj))]
    return rows, edges, groups, atlas


def parse_fd(tokens):
    values = []; first_defined = False
    for index, token in enumerate(tokens):
        if index == 0 and token in ('', 'n/a'):
            continue
        value = q.number(token)
        q.require(value >= 0, 'Negative source FD')
        values.append(value)
        if index == 0:
            first_defined = True
    q.require(values, 'No defined source FD')
    total = float(np.sum(np.array(values, dtype=np.float64)))
    return total, len(values), first_defined, total/len(values)


def detrend_columns(values):
    """Separate centered SciPy least-squares detrending, not the oracle helper."""
    values = np.asarray(values, dtype=np.float64)
    constant = np.all(values == values[:1], axis=0)
    centered = values-values.mean(axis=0)
    centered[:, constant] = 0
    return signal.detrend(centered, axis=0, type='linear')


def clean_parcels(parcel, confounds):
    parcel = np.asarray(parcel, np.float64); confounds = np.asarray(confounds, np.float64)
    q.require(parcel.ndim == confounds.ndim == 2 and len(parcel) == len(confounds) > 33
              and confounds.shape[1] == 13 and np.isfinite(parcel).all() and np.isfinite(confounds).all(), 'Invalid source cleaning arrays')
    n = len(parcel); constant = np.all(parcel == parcel[:1], axis=0)
    original_centered = parcel-parcel.mean(axis=0)
    original_centered[:, constant] = 0.
    original_norm = np.linalg.norm(original_centered, axis=0)
    sos = signal.butter(5, [.009, .08], btype='bandpass', fs=.5, output='sos')
    y = signal.sosfiltfilt(sos, detrend_columns(parcel), axis=0, padtype='odd', padlen=33)
    c = signal.sosfiltfilt(sos, detrend_columns(confounds), axis=0, padtype='odd', padlen=33)
    c -= c.mean(axis=0); sd = c.std(axis=0); sd[sd < q.EPS] = 1.; c /= sd
    basis, r, pivot = linalg.qr(c, mode='economic', pivoting=True)
    retained = np.abs(np.diag(r)) > 100*q.EPS
    basis = basis[:, retained]
    residual = y-basis@(basis.T@y)
    residual -= residual.mean(axis=0)
    norm = np.linalg.norm(residual, axis=0)
    bound = 10*max(n, 13)*q.EPS*np.maximum(original_norm, q.TINY)
    status = np.full(parcel.shape[1], 'ok', dtype='U24')
    status[norm <= bound] = 'numerical_zero_residual'; status[constant] = 'constant_input'
    normalized = np.zeros_like(residual); valid = status == 'ok'
    normalized[:, valid] = residual[:, valid]/(norm[valid]/np.sqrt(n-1))
    q.require(np.isfinite(normalized).all() and np.isfinite(norm).all(), 'Nonfinite cleaned source')
    return dict(normalized=normalized, parcel_status=status, parcel_original_centered_l2=original_norm,
        parcel_residual_l2=norm, parcel_zero_bound=bound, nuisance_rank=int(retained.sum()),
        qr_diagonal=np.diag(r).copy(), qr_pivot=pivot, filtered_nuisance=c)


def source_subject(inputs, sid, group, atlas):
    parcel_parts = []; frame_counts = []; observed = dict(subject_id=sid)
    for hemi, side in [('L', 'left'), ('R', 'right')]:
        path, _ = role_path(inputs, 'surface_'+side, sid)
        image = nib.load(path)
        q.require(dict(image.meta).get('AnatomicalStructurePrimary') == 'Cortex'+side.title(), 'Wrong source hemisphere')
        arrays = image.darrays
        q.require(arrays and all(d.data.shape == (10242,) and d.data.dtype == np.float32 and d.intent == 2001 for d in arrays), 'Wrong source surface axes/dtype')
        q.require(all(float(dict(d.meta)['TimeStep']) == 2000. for d in arrays), 'Unexpected original source time step')
        labels = atlas[hemi]['labels']; selected = atlas[hemi]['included']
        q.require(np.all(labels >= 0), 'Unassigned source vertices require explicit reduction handling')
        counts = np.bincount(labels, minlength=atlas[hemi]['n_labels'])
        parcel = np.empty((len(arrays), len(selected)), dtype=np.float64)
        for t, d in enumerate(arrays):
            values = np.asarray(d.data, dtype=np.float64)
            q.require(np.isfinite(values).all(), 'Nonfinite original surface value')
            sums = np.bincount(labels, weights=values, minlength=len(counts))
            parcel[t] = sums[selected]/counts[selected]
        parcel_parts.append(parcel); frame_counts.append(len(arrays))
        observed['n_vertices_'+side] = len(labels); observed['surface_dtype_'+side] = str(arrays[0].data.dtype)
    q.require(frame_counts[0] == frame_counts[1], 'Original hemisphere frame mismatch')
    path, _ = role_path(inputs, 'confounds', sid)
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t'); records = list(reader)
    q.require(len(records) == frame_counts[0] and len(set(reader.fieldnames)) == len(reader.fieldnames), 'Confound source alignment mismatch')
    columns = inputs['method']['temporal']['confounds']
    q.require(set(columns+['FramewiseDisplacement']) <= set(reader.fieldnames), 'Missing original nuisance columns')
    confounds = np.array([[q.number(row[name]) for name in columns] for row in records], np.float64)
    fd_sum, fd_n, first, fd_mean = parse_fd([row['FramewiseDisplacement'] for row in records])
    timing_path, _ = role_path(inputs, 'acquisition_metadata', sid)
    timing = q.json_load(timing_path); q.close(timing['RepetitionTime'], 2., 'exact', 'source TR')
    n = frame_counts[0]; observed.update(n_frames=n, n_confounds_rows=len(records), tr_s=2.)
    cleaned = clean_parcels(np.column_stack(parcel_parts), confounds)
    good = cleaned['parcel_status'] == 'ok'; ii, jj = np.triu_indices(len(good), 1)
    valid = good[ii] & good[jj]; raw = np.full(len(ii), np.nan)
    normalized = cleaned['normalized']; norms = np.linalg.norm(normalized, axis=0)
    for edge in np.flatnonzero(valid):
        i, j = ii[edge], jj[edge]
        raw[edge] = np.dot(normalized[:, i]/norms[i], normalized[:, j]/norms[j])
    q.require(np.all(np.abs(raw[valid]) <= 1+1e-12), 'Invalid source Pearson overshoot')
    raw[valid] = np.clip(raw[valid], -1, 1)
    z = np.arctanh(np.clip(raw, -.999, .999))
    record = dict(subject_id=sid, group=group, n_frames=n, tr_s=2., fd_sum=fd_sum, n_fd_defined=fd_n,
        first_fd_defined=first, mean_fd=fd_mean, qc_fd_lt_0_2=fd_mean < .2, n_confound_columns=13,
        nuisance_rank=cleaned['nuisance_rank'], nuisance_rank_threshold=100*q.EPS)
    result = {name: cleaned[name] for name in ('parcel_status', 'parcel_original_centered_l2', 'parcel_residual_l2', 'parcel_zero_bound')}
    result.update(raw_r=raw, fisher_z=z, edge_valid=valid, fisher_clipped=valid & (np.abs(raw) > .999))
    return result, record, observed


def source_reference(inputs, pilot=False):
    cohort = source_cohort(inputs); parcels, edges, atlas, atlas_observed = source_atlas(inputs)
    selected = [r for r in cohort if r['selected']]
    if pilot:
        selected = [r for r in selected if r['subject_id'] == 'sub-10159']
    arrays = []; rows = []; observed = []
    for index, row in enumerate(selected):
        measurements, record, header = source_subject(inputs, row['subject_id'], row['group'], atlas)
        arrays.append(measurements); rows.append(record); observed.append(header)
        print(f"Original source {index+1}/{len(selected)}: {row['subject_id']}", flush=True)
    ref = {name: np.stack([a[name] for a in arrays]) for name in arrays[0]}
    ref.update(subject_id=np.array([r['subject_id'] for r in selected]),
        parcel_id=np.array([r['parcel_id'] for r in parcels if r['included']]), edge_id=np.arange(len(edges)),
        cohort_rows=cohort, parcel_rows=parcels, edge_rows=edges, connectivity_rows=rows,
        method_contract_json=inputs['method_contract_json'], source_manifest_json=inputs['source_manifest_json'])
    status = 'resource_pilot' if pilot else 'complete'
    ref['metadata'] = dict(status=status, task_id='CLINCONN-001', dataset_id='ds000030',
        source_manifest_sha256=pw.SOURCE_MANIFEST_SHA256, method_contract_sha256=pw.METHOD_SHA256,
        source_sha256=inputs['hashes'], method_contract=inputs['method'],
        source_observed=dict(n_source_participants=272, n_candidates=177, n_selected=len(selected), n_unavailable=5,
            group_counts={g: sum(r['group'] == g for r in selected) for g in ('SCHZ', 'CONTROL')},
            atlas=atlas_observed, subjects=observed),
        software=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, nibabel=nib.__version__))
    ref['provenance'] = dict(builder_id=pw.BUILDER_ID, status=status, source_manifest_sha256=pw.SOURCE_MANIFEST_SHA256,
        method_contract_sha256=pw.METHOD_SHA256, source_construction='verified original GIFTI/confounds/annotations/pial only; no oracle arrays or outputs',
        shared_primitives='nibabel source reader; SciPy SOS design/filter and pivoted QR; local verifier statistics',
        source_subjects=[r['subject_id'] for r in selected])
    if not pilot:
        pw.validate_reference(ref)
    return ref


def save_reference(path, ref):
    payload = {k: ref[k] for k in ('cohort_rows', 'parcel_rows', 'edge_rows', 'connectivity_rows', 'metadata', 'provenance',
                                  'method_contract_json', 'source_manifest_json')}
    with Path(path).open('xb') as stream:
        np.savez_compressed(stream, **{'ref_'+k: ref[k] for k in q.ARRAY_FIELDS},
                            reference_json=np.array(json.dumps(payload, allow_nan=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=Path('/app/data/clinconn'))
    parser.add_argument('--method-contract', type=Path, default=Path('/app/method_contract.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--oracle-output', type=Path)
    args = parser.parse_args()
    source, output, report = destinations(args.source_dir, args.output, args.report)
    q.require(args.pilot or args.oracle_output is not None, 'Full bank needs a post-construction native validation target')
    started = time.monotonic()
    inputs = read_inputs(source, args.method_contract)
    ref = source_reference(inputs, args.pilot)
    if not args.pilot:
        # Oracle artifacts are FIRST consulted here, after original-source construction.
        q.validate_output_directory(args.oracle_output, ref)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    save_reference(output, ref)
    result = dict(status='resource_pilot' if args.pilot else 'complete', source_subjects=ref['subject_id'].tolist(),
        n_subjects=len(ref['subject_id']), n_parcels=len(ref['parcel_id']), n_candidate_edges=len(ref['edge_id']),
        n_valid_subject_edges=int(ref['edge_valid'].sum()), source_manifest_sha256=pw.SOURCE_MANIFEST_SHA256,
        method_contract_sha256=pw.METHOD_SHA256, bank_sha256=sha256(output), bank_size_bytes=output.stat().st_size,
        elapsed_seconds=time.monotonic()-started, original_source_construction=True,
        oracle_used_only_after_source_construction=not args.pilot, pilot_group_statistics_computed=False if args.pilot else None)
    with report.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
