"""Offline, source-bound NETSEG reference; import has no IO or execution."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import warnings

import nibabel as nib
import numpy as np
import scipy

from segregation_contract import (require, PreconditionError, nearest_labels,
    parcel_means, clean_parcels, edge_connectivity, segregation_edges,
    cohort_summary, complete_summary)

TASK_ID = 'NETSEG-001'
METHOD_ID = 'development-movie-schaefer100-zero-clipped-pooled-pairs-v2'
METHOD_SHA256 = 'd3b67c864af6855b654ddf5e803e7908bc0d973ae7d5ea45b27604fc5787db47'
SOURCE_SHA256 = 'd0c4f2afdfe9161907fe64d74ab07e85e6162726f5efc0b10ff46cf2ece954f1'
DEFAULT_SOURCE = '/app/data/netseg'
DEFAULT_METHOD = '/app/method_contract.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(value):
    path = Path(value).absolute()
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink(), 'symlink path or ancestor: ' + str(ancestor))
    return path.resolve(strict=False)


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def destinations(data_dir, method_path, output_dir, private_dir=None):
    source, method, output = map(safe_path, (data_dir, method_path, output_dir))
    private = safe_path(private_dir) if private_dir else None
    for target in [output] + ([private] if private else []):
        require(disjoint(source, target) and disjoint(method, target),
                'evidence overlaps source or method')
        require(not target.exists() or (target.is_dir() and not any(target.iterdir())),
                'evidence destination must be fresh or empty')
    require(private is None or disjoint(output, private), 'public/private evidence overlap')
    for target in [output] + ([private] if private else []):
        target.mkdir(parents=True, exist_ok=True)
    return source, method, output, private


def strict_json(path):
    require(path.is_file() and not path.is_symlink(), 'JSON input is not a regular file')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise PreconditionError('nonfinite JSON: ' + value)
    result = json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=constant)
    def check(value):
        if isinstance(value, float):
            require(np.isfinite(value), 'nonfinite JSON value')
        elif isinstance(value, dict):
            for child in value.values(): check(child)
        elif isinstance(value, list):
            for child in value: check(child)
    check(result)
    return result


def source_verifier():
    candidates = [Path(__file__).resolve().parents[1] / 'environment/stage_data.py',
                  Path('/opt/source/stage_data.py')]
    for path in candidates:
        if path.is_file() and not path.is_symlink():
            spec = importlib.util.spec_from_file_location('netseg_source_stage', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.verify_staged
    raise PreconditionError('offline source-integrity helper unavailable')


def read_tsv(path):
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        names = reader.fieldnames
        require(names and len(names) == len(set(names)), 'duplicate or absent TSV header')
        rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            'malformed TSV rows')
    return rows, names


def header_record(image, relative, participant=None):
    hdr = image.header
    slope, intercept = float(image.dataobj.slope), float(image.dataobj.inter)
    affine = np.asarray(image.affine, dtype=np.float64)
    zooms = [float(x) for x in hdr.get_zooms()]
    require(np.isfinite(affine).all() and np.isfinite([slope, intercept, *zooms]).all(),
            'nonfinite NIfTI header/calibration')
    spatial, temporal = hdr.get_xyzt_units()
    result = {'source_path': relative, 'shape': list(image.shape), 'affine': affine.tolist(),
              'storage_dtype': image.get_data_dtype().name, 'intensity_slope': slope,
              'intensity_intercept': intercept, 'zooms': zooms, 'spatial_units': spatial,
              'temporal_units': temporal, 'qform_code': int(hdr['qform_code']),
              'sform_code': int(hdr['sform_code'])}
    if participant is not None:
        result['participant_id'] = participant
    return result


def validate_header(header, expected, kind):
    for key in ('shape', 'affine', 'storage_dtype', 'spatial_units', 'temporal_units',
                'qform_code', 'sform_code'):
        require(header[key] == expected[kind + '_' + key], 'source header mismatch: ' + kind + ' ' + key)
    if kind == 'bold':
        require(header['zooms'] == expected['bold_zooms'], 'source BOLD zoom mismatch')
    else:
        require(header['intensity_slope'] == 1.0 and header['intensity_intercept'] == 0.0,
                'atlas effective calibration mismatch')


def load_inputs(data_dir, method_path):
    source, method_path = safe_path(data_dir), safe_path(method_path)
    method = strict_json(method_path)
    require(digest(method_path) == METHOD_SHA256 and method['method_id'] == METHOD_ID,
            'method contract identity mismatch')
    manifest_path = source / 'source_manifest.json'
    require(manifest_path.is_file() and not manifest_path.is_symlink(), 'missing source manifest')
    require(digest(manifest_path) == SOURCE_SHA256, 'source manifest identity mismatch')
    manifest = source_verifier()(source)
    files = manifest['files']
    require(len(files) == method['source']['n_files'], 'source file count mismatch')
    one = {}
    paths = {pid: {} for pid in method['source']['participant_ids']}
    for entry in files:
        role, pid = entry['role'], entry.get('participant_id')
        if role in ('bold', 'confounds'):
            require(pid in paths and role not in paths[pid], 'source participant identity mismatch')
            paths[pid][role] = entry['path']
        elif role != 'provenance':
            require(role not in one, 'duplicate source role')
            one[role] = entry['path']
    require(set(one) == {'atlas_image', 'atlas_labels', 'participants'}, 'missing source role')
    require(all(set(x) == {'bold', 'confounds'} for x in paths.values()), 'incomplete source pairs')
    phenotype, names = read_tsv(source / one['participants'])
    require({'participant_id', 'Child_Adult', 'Age'} <= set(names), 'phenotype columns missing')
    require(len(phenotype) == method['source']['cohort']['n_source_phenotype_rows'], 'phenotype row count')
    ids = [row['participant_id'] for row in phenotype]
    require(len(ids) == len(set(ids)), 'duplicate phenotype identity')
    selected = {}
    for index, row in enumerate(phenotype):
        if row['participant_id'] in paths:
            age = float(row['Age'])
            require(np.isfinite(age) and row['Child_Adult'] in {'child', 'adult'}, 'invalid phenotype')
            selected[row['participant_id']] = {'participant_id': row['participant_id'],
                'source_row_index': index, 'group': row['Child_Adult'], 'age': age}
    require(set(selected) == set(paths), 'missing selected phenotype')
    counts = {g: sum(row['group'] == g for row in selected.values()) for g in ('child', 'adult')}
    require(counts == method['source']['cohort']['group_counts'], 'source group counts mismatch')
    expected = method['source']['observed_structure']
    images, headers = {}, []
    for pid in paths:
        image = nib.load(source / paths[pid]['bold'], mmap='r', keep_file_open=False)
        header = header_record(image, paths[pid]['bold'], pid)
        validate_header(header, expected, 'bold')
        images[pid] = image
        headers.append(header)
    atlas = nib.load(source / one['atlas_image'], mmap='r', keep_file_open=False)
    atlas_header = header_record(atlas, one['atlas_image'])
    validate_header(atlas_header, expected, 'atlas')
    return {'source': source, 'method': method, 'manifest': manifest, 'paths': paths,
            'single': one, 'phenotype': selected, 'images': images, 'atlas': atlas,
            'observed': {'n_source_participants': len(phenotype), 'n_selected_participants': len(paths),
                         'n_frames': expected['bold_shape'][-1], 'n_parcels': 100,
                         'group_counts': counts, 'bold_headers': headers, 'atlas_header': atlas_header,
                         'selected_confound_columns': method['preprocessing']['confound_columns'],
                         'tr_seconds_used': None}}


def read_lut(path, networks):
    rows = []
    for index, line in enumerate(path.read_text().splitlines()):
        parts = line.split()
        require(len(parts) == 6, 'invalid atlas LUT row')
        roi = int(parts[0])
        tokens = parts[1].split('_')
        require(len(tokens) >= 4 and tokens[0] == '7Networks' and tokens[1] in ('LH', 'RH')
                and tokens[2] in networks, 'invalid original atlas label')
        require(all(0 <= int(x) <= 255 for x in parts[2:]), 'invalid LUT color')
        rows.append({'parcel_id': roi, 'source_lut_row_index': index, 'label': parts[1],
                     'hemisphere': tokens[1], 'network': tokens[2]})
    require(sorted(row['parcel_id'] for row in rows) == list(range(1, 101)), 'atlas IDs not exactly1..100')
    return sorted(rows, key=lambda row: row['parcel_id'])


def selected_confounds(path, columns, n_frames):
    rows, names = read_tsv(path)
    require(set(columns) <= set(names) and len(rows) == n_frames, 'confound columns or frame count')
    values = np.asarray([[float(row[name]) for name in columns] for row in rows], dtype=np.float64)
    require(values.shape == (n_frames, len(columns)) and np.isfinite(values).all(), 'nonfinite selected confounds')
    return values


def prepare_geometry(inputs):
    method, atlas = inputs['method'], inputs['atlas']
    labels = np.asarray(atlas.dataobj, dtype=np.float64)
    require(np.isfinite(labels).all() and np.array_equal(labels, np.floor(labels)), 'invalid atlas values')
    require(set(np.unique(labels).tolist()) == set(range(101)), 'native atlas labels differ')
    rows = read_lut(inputs['source'] / inputs['single']['atlas_labels'], method['geometry']['network_names'])
    image = next(iter(inputs['images'].values()))
    grid = nearest_labels(labels, atlas.affine, image.shape[:3], image.affine)
    for row in rows:
        roi = row['parcel_id']
        row.update(native_voxel_count=int(np.count_nonzero(labels == roi)),
                   target_voxel_count=int(np.count_nonzero(grid == roi)), grid_id=method['geometry']['grid_id'])
        require(row['target_voxel_count'] > 0, 'atlas label absent from target grid: ' + str(roi))
    return rows, grid


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def write_csv(path, rows, columns):
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)


def write_npz(path, arrays):
    require(all(np.asarray(value).dtype.kind != 'O' for value in arrays.values()), 'object diagnostic array')
    with path.open('xb') as stream:
        np.savez_compressed(stream, **arrays)


def analyze(inputs, pilot_subject=None):
    method = inputs['method']
    parcels, grid = prepare_geometry(inputs)
    roi_ids = np.asarray([row['parcel_id'] for row in parcels], dtype=np.int64)
    networks = [row['network'] for row in parcels]
    people = method['source']['participant_ids']
    if pilot_subject is not None:
        require(pilot_subject == 'sub-pixar001' and pilot_subject in people, 'only fixed sub-pixar001 pilot allowed')
        people = [pilot_subject]
    participants, segregation, values = [], [], []
    tensors = {name: [] for name in ('raw_mean', 'standardized_clean', 'raw_sd', 'residual_sd',
                                    'pearson_r', 'fisher_z', 'positive_z')}
    private = {'target_label_grid': grid}
    last_edges = None
    for pid in people:
        image = inputs['images'][pid]
        data = np.asarray(image.dataobj, dtype=np.float64)
        raw, counts = parcel_means(data, grid, roi_ids)
        del data
        require(np.array_equal(counts, [row['target_voxel_count'] for row in parcels]), 'parcel support changed')
        confounds = selected_confounds(inputs['source'] / inputs['paths'][pid]['confounds'],
                                      method['preprocessing']['confound_columns'], raw.shape[0])
        cleaned = clean_parcels(raw, confounds)
        edges = edge_connectivity(cleaned['cleaned'], roi_ids)
        endpoint = segregation_edges(edges['fisher_z'], roi_ids, networks,
                                    edges['edge_roi_i'], edges['edge_roi_j'])
        person = dict(inputs['phenotype'][pid])
        person.update(bold_path=inputs['paths'][pid]['bold'], confounds_path=inputs['paths'][pid]['confounds'],
                      n_frames=raw.shape[0], n_parcels=len(roi_ids), n_confounds=confounds.shape[1],
                      nuisance_rank=cleaned['nuisance_rank'], grid_id=method['geometry']['grid_id'])
        participants.append(person)
        segregation.append({'participant_id': pid, 'group': person['group'], **endpoint})
        values.append(endpoint['segregation'])
        tensors['raw_mean'].append(raw)
        tensors['standardized_clean'].append(cleaned['cleaned'])
        for name in ('raw_sd', 'residual_sd'): tensors[name].append(cleaned[name])
        for name in ('pearson_r', 'fisher_z', 'positive_z'): tensors[name].append(edges[name])
        private[pid + '_confounds_original'] = confounds
        for name, value in cleaned.items(): private[pid + '_' + name] = np.asarray(value)
        last_edges = edges
        print('processed ' + pid + ' (' + str(len(participants)) + '/' + str(len(people)) + ')', flush=True)
    arrays = {name: np.stack(value) for name, value in tensors.items()}
    arrays.update(participant_id=np.asarray(people), frame_index=np.arange(arrays['raw_mean'].shape[1]),
                  parcel_id=roi_ids, edge_i=last_edges['edge_roi_i'], edge_j=last_edges['edge_roi_j'])
    groups = [person['group'] for person in participants]
    if pilot_subject is None:
        summaries = cohort_summary(values, groups)
    else:
        summaries = {'cohort': complete_summary(values),
                     'groups': {g: complete_summary([v for v, group in zip(values, groups) if group == g])
                                for g in sorted(set(groups))},
                     'adult_minus_child': {'status': 'resource_pilot', 'estimate': None, 'se': None, 'ci95': None}}
    result = {'status': 'resource_pilot' if pilot_subject else 'ok', 'task_id': TASK_ID, 'method_id': METHOD_ID,
              'n_participants': len(people), 'n_defined': sum(v is not None for v in values),
              'n_undefined': sum(v is None for v in values), **summaries}
    if pilot_subject:
        result['resource_pilot_scope'] = {'numerical_participant_ids': people, 'full_cohort_analysis': False}
    return participants, parcels, arrays, segregation, result, private


def run(data_dir, method_path, output, private=None, pilot_subject=None):
    captured = []
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            inputs = load_inputs(data_dir, method_path)
            participants, parcels, arrays, segregation, result, diagnostics = analyze(inputs, pilot_subject)
    finally:
        for warning in captured:
            print(warning.category.__name__ + ': ' + str(warning.message), file=sys.stderr)
    metadata = {'status': result['status'], 'task_id': TASK_ID, 'method_id': METHOD_ID,
                'source_manifest_sha256': SOURCE_SHA256, 'method_contract_sha256': METHOD_SHA256,
                'source_sha256': {entry['path']: entry['sha256'] for entry in inputs['manifest']['files']},
                'source_observed': inputs['observed'],
                'software_versions': {'python': platform.python_version(), 'numpy': np.__version__,
                                      'scipy': scipy.__version__, 'nibabel': nib.__version__},
                'warnings': [{'category': w.category.__name__, 'message': str(w.message)} for w in captured]}
    if pilot_subject: metadata['resource_pilot_scope'] = result['resource_pilot_scope']
    schema = inputs['method']['artifacts']
    write_csv(output / 'participants.csv', participants, schema['participants.csv']['columns'])
    write_csv(output / 'parcels.csv', parcels, schema['parcels.csv']['columns'])
    write_npz(output / 'connectivity.npz', arrays)
    write_csv(output / 'segregation.csv', segregation, schema['segregation.csv']['columns'])
    if private:
        diagnostics.update(metadata_json=np.asarray(json.dumps(metadata, sort_keys=True, allow_nan=False)),
                           results_json=np.asarray(json.dumps(result, sort_keys=True, allow_nan=False)))
        write_npz(private / 'analysis_arrays.npz', diagnostics)
    mean = result['cohort']['mean']
    difference = result['adult_minus_child']['estimate']
    text = ('# Descriptive movie-watching segregation\n\n'
            + ('Resource pilot only; no full-cohort result.\n\n' if pilot_subject else '')
            + f"Participants processed: {len(participants)}; defined endpoints: {result['n_defined']}. "
            + f"Complete-scope mean: {mean!r}; adult-minus-child estimate: {difference!r}.\n\n"
            + 'Negative Fisher-z pairs contribute zero while all within/between pairs remain in their denominators. '
            + 'The 4-mm teaching derivatives, nuisance recipe and cross-template identity-world atlas transfer '
            + 'define a method adaptation, not verified anatomical registration or either original-paper replication. '
            + 'The selected cross-sectional groups share a movie; this is not within-person development or a causal age effect. '
            + 'Header units remain unknown; no seconds-based filter is applied.\n')
    with (output / 'findings.md').open('x', encoding='utf-8') as stream: stream.write(text)
    # Completion markers follow all numerical and optional private artifact writes.
    write_json(output / 'cohort_results.json', result)
    write_json(output / 'run_metadata.json', metadata)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=os.environ.get('SOURCE_DIR', DEFAULT_SOURCE))
    parser.add_argument('--method-contract', default=os.environ.get('METHOD_CONTRACT', DEFAULT_METHOD))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir', default=os.environ.get('PRIVATE_DIR'))
    parser.add_argument('--pilot-subject', choices=['sub-pixar001'])
    args = parser.parse_args(argv)
    output = None
    try:
        source, method, output, private = destinations(args.data_dir, args.method_contract, args.output_dir, args.private_dir)
        result = run(source, method, output, private, args.pilot_subject)
        print(json.dumps({'status': result['status'], 'n_participants': result['n_participants']}), flush=True)
        return 0
    except Exception as error:
        reason = str(error) or type(error).__name__
        if output is not None:
            receipt = output / 'failure_receipt.json'
            if not os.path.lexists(receipt):
                write_json(receipt, {'status': 'failed_precondition', 'reason': reason,
                                     'task_id': TASK_ID, 'method_id': METHOD_ID})
        print('failed_precondition: ' + reason, file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
