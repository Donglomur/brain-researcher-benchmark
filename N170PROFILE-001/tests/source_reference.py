"""Private source reconstruction for N170; no oracle, MNE, or answer-bank import.

All 74 members authenticate before any SET metadata is decoded. Each consumed
SET/FDT is read again into a size/SHA-bound immutable buffer. Only selected MAT
metadata fields enter the shared bounded scanner; external FDT signals use an
independent direct float32 decoder and analytic FIR. No endpoint is measured.
The public API has only full-cohort and explicitly labelled first-person pilot
scopes; no environment variable can replace pins or suppress source checking.
"""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

import numpy as np
import io_contract as io

SOURCE_SHA = '3970137c64990f680468baf1d51b89a73a61a748639795541e2c2734777b54cd'
METHOD_SHA = '549cf315f0175ab13c3007703cec298a6cc5080d695aecd9f93f49e98a08ce92'
SCHEMA_SHA = 'fab0dbf2ff1fb60f0596b065ff5f148d9d46da8c89c6e81203dbc346a2070814'
SCANNER_SHA = '66fb278c78255e382b85359d26e76df2059c3f9c9dfb2b3ca73ec138148623f7'
FIR_SHA = '86e0886c018517ab37b887677de140cf477cfc3d1a5d08f82f3b1d5d91de143f'
SUBJECTS = tuple(str(i) for i in range(1, 41) if i not in (1, 5, 16))
SOURCE_BYTES = 788438272
SCALP = ('FP1','F3','F7','FC3','C3','C5','P3','P7','P9','PO7','PO3','O1','Oz','Pz','CPz',
         'FP2','Fz','F4','F8','FC4','FCz','Cz','C4','C6','P4','P8','P10','PO8','PO4','O2')
EOG = ('HEOG_left', 'HEOG_right', 'VEOG_lower')
CONDITIONS = ('face', 'car')
OFFSETS = np.arange(-51, 103, dtype=np.int64)
REASONS = ('out_of_bounds', 'duplicate_target_sample', 'crosses_boundary', 'peak_to_peak', 'accepted')
HEADER_FIELDS = ('setname','filename','filepath','subject','group','condition','session',
                 'nbchan','trials','pnts','srate','xmin','xmax','ref','saved','datfile',
                 'history','comments','unit','units')


def _bound_module(filename, expected_sha):
    path = Path(__file__).absolute().with_name(filename)
    raw = io.read_bytes(path, limit=1024**2, sha256=expected_sha)
    module = types.ModuleType('_n170_private_' + path.stem)
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _source_bytes(root, row):
    raw = io.read_bytes(root / row['path'], size=row['size_bytes'], sha256=row['sha256'])
    if 'md5' in row:
        io.need(hashlib.md5(raw).hexdigest() == row['md5'], 'source_md5')
    return raw


def _inventory(root, rows):
    expected_files = {'source_manifest.json'} | {row['path'] for row in rows}
    expected_dirs = {str(p) for name in expected_files for p in Path(name).parents if str(p) != '.'}
    files, directories = set(), set()
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            entry = Path(parent) / name
            mode = entry.lstat().st_mode
            io.need(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'nonregular_source')
            (directories if stat.S_ISDIR(mode) else files).add(str(entry.relative_to(root)))
    io.need(files == expected_files and directories == expected_dirs, 'closed_source_inventory')


def authenticate(data_dir, manifest_path, method_path, schema_path):
    root = io.safe_path(data_dir)
    io.need(root.is_dir(), 'source_directory')
    manifest_raw = io.read_bytes(manifest_path, limit=262144, sha256=SOURCE_SHA)
    internal = io.read_bytes(root / 'source_manifest.json', limit=262144, sha256=SOURCE_SHA)
    io.need(internal == manifest_raw, 'source_manifest_copies')
    manifest = io.json_bytes(manifest_raw)
    method = io.json_bytes(io.read_bytes(method_path, limit=1024**2, sha256=METHOD_SHA))
    schema = io.json_bytes(io.read_bytes(schema_path, limit=1024**2, sha256=SCHEMA_SHA))
    io.need(manifest.get('task_id') == method.get('task_id') == schema.get('task_id') == 'N170PROFILE-001', 'task_identity')
    io.need(manifest.get('subjects') == [int(s) for s in SUBJECTS]
            and method.get('subjects') == list(SUBJECTS), 'canonical_cohort')
    io.need(method.get('source_manifest_sha256') == SOURCE_SHA, 'method_source_binding')
    rows = manifest.get('files')
    io.need(isinstance(rows, list) and len(rows) == 2 * len(SUBJECTS), 'source_member_count')
    keys, paths = set(), set()
    for row in rows:
        io.need(isinstance(row, dict), 'source_record')
        subject, role, path = row.get('subject'), row.get('role'), row.get('path')
        io.need(type(subject) is int and str(subject) in SUBJECTS and role in ('set', 'fdt'), 'source_subject_role')
        key = (str(subject), role)
        io.need(key not in keys, 'duplicate_source_key'); keys.add(key)
        io.need(type(path) is str and path and '\\' not in path and '\0' not in path
                and not path.startswith('/') and all(x not in ('', '.', '..') for x in path.split('/')), 'source_path')
        io.need(Path(path).name == f'{subject}_N170_shifted_ds.{role}' and path not in paths, 'source_filename')
        paths.add(path)
        io.need(type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= io.LIMIT, 'source_size')
        io.need(type(row.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'source_sha_format')
    io.need(keys == {(s, r) for s in SUBJECTS for r in ('set', 'fdt')}, 'source_membership')
    io.need(sum(row['size_bytes'] for row in rows) == SOURCE_BYTES
            and manifest.get('source_bytes') == SOURCE_BYTES
            and manifest.get('source_file_count') == len(rows), 'source_aggregate')
    _inventory(root, rows)
    for row in rows:
        _source_bytes(root, row)  # complete authentication before any parsing
    return root, manifest, method, schema


def documentary(value):
    """JSON-safe source metadata, retaining nonfinite values as explicit tags."""
    if isinstance(value, np.generic):
        return documentary(value.item())
    if isinstance(value, np.ndarray):
        if value.size == 0: return None
        if value.size == 1: return documentary(value.reshape(-1)[0])
        return documentary(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return {'__nonfinite__': 'NaN' if math.isnan(value) else ('Infinity' if value > 0 else '-Infinity')}
    if value is None or type(value) in (str, bool, int, float): return value
    if isinstance(value, bytes): return value.decode('utf-8')
    if isinstance(value, dict): return {str(k): documentary(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [documentary(v) for v in value]
    raise ValueError('unsupported_documentary_value')


def _finite_scalar(value):
    return type(value) in (int, float) and math.isfinite(value)


def _event_code(value):
    if _finite_scalar(value) and value == int(value): return int(value)
    if type(value) is str and re.fullmatch(r'[+-]?[0-9]+', value.strip()): return int(value.strip())
    return None


def annotate_events(subject, original_events, pnts):
    """Own discrete event policy; no MNE annotation parser or scanner ledger."""
    io.need(type(pnts) is int and pnts > 0, 'source_pnts')
    annotations, candidates, boundary_rows = [], [], []
    cuts = {0, pnts}
    for index, original in enumerate(original_events):
        io.need(isinstance(original, dict), 'event_record')
        fields = documentary(original)
        typ, latency = fields.get('type'), fields.get('latency')
        code = _event_code(typ)
        role = 'face' if code is not None and 1 <= code <= 40 else 'car' if code is not None and 41 <= code <= 80 else 'other'
        if code == -99 or type(typ) is str and typ.strip().casefold() == 'boundary': role = 'boundary'
        if role != 'other': io.need(_finite_scalar(latency), 'target_or_boundary_latency')
        annotation = dict(subject_id=subject, source_event_index=index,
                          normalized_event_code=code, event_role=role)
        for name in ('type', 'latency', 'duration', 'urevent'):
            annotation[name + '_json'] = json.dumps(fields.get(name), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        annotations.append(annotation)
        if role == 'boundary':
            cut = math.ceil(latency - 1)
            io.need(0 <= cut <= pnts, 'boundary_cut_out_of_range')
            cuts.add(cut); boundary_rows.append(index)
        elif role in CONDITIONS:
            sample = int(np.rint(latency - 1))
            candidates.append(dict(subject_id=subject, source_event_index=index, condition=role,
                                   event_sample=sample, epoch_first_sample=sample - 51,
                                   epoch_last_sample=sample + 102))
    edges = sorted(cuts)
    segments = [(a, b) for a, b in zip(edges, edges[1:]) if b > a]
    multiplicity = Counter(row['event_sample'] for row in candidates)
    for row in candidates:
        first, last = row['epoch_first_sample'], row['epoch_last_sample']
        if first < 0 or last >= pnts: reason = 'out_of_bounds'
        elif multiplicity[row['event_sample']] > 1: reason = 'duplicate_target_sample'
        elif not any(a <= first and last < b for a, b in segments): reason = 'crosses_boundary'
        else: reason = None
        row.update(epoch_status=reason or 'ok', accepted=False, rejection_reason=reason)
    return annotations, candidates, segments, boundary_rows, edges


def parse_header(raw, subject, set_row, fdt_row, scanner):
    scan = scanner.MatScan(raw)
    nodes, layout = scan.fields()
    io.need('data' in nodes and nodes['data']['matlab_class'] == 4, 'external_fdt_required')
    pointer = documentary(scan.decode(nodes['data']))
    io.need(pointer == Path(fdt_row['path']).name, 'external_fdt_pointer')
    fields = {name: documentary(scan.decode(nodes[name])) for name in HEADER_FIELDS if name in nodes}
    for name, expected in (('nbchan', 33), ('trials', 1), ('srate', 256), ('xmin', 0)):
        io.need(_finite_scalar(fields.get(name)) and fields[name] == expected, 'header_' + name)
    io.need(_finite_scalar(fields.get('pnts')) and fields['pnts'] == int(fields['pnts']) and fields['pnts'] > 0, 'header_pnts')
    pnts = int(fields['pnts'])
    io.need(fields.get('ref') == 'common', 'source_reference_token')
    io.need('unit' not in nodes and 'units' not in nodes, 'unexpected_source_unit_field')
    io.need(fdt_row['size_bytes'] == 4 * 33 * pnts, 'fdt_byte_equation')
    for name in scanner.ICA_FIELDS:
        if name in nodes: io.need(math.prod(nodes[name]['shape']) == 0, 'nonempty_source_ica')
    io.need('chanlocs' in nodes, 'source_channels')
    channel_records = [documentary(v) for v in scanner.records(scan.decode(nodes['chanlocs']))]
    io.need(len(channel_records) == 33 and all(isinstance(v, dict) for v in channel_records), 'source_channel_records')
    labels = [row.get('labels') for row in channel_records]
    io.need(all(type(x) is str for x in labels) and len(set(labels)) == 33 and set(labels) == set(SCALP + EOG), 'source_channel_labels')
    events = scanner.records(scan.decode(nodes['event'])) if 'event' in nodes else []
    io.need(len(events) <= 40000, 'source_event_bound')
    annotations, trials, segments, boundary_rows, cuts = annotate_events(subject, events, pnts)
    event_fields = sorted({k for row in events for k in row})
    observed = dict(subject_id=subject, set_path=set_row['path'], fdt_path=fdt_row['path'],
                    literal_data_pointer=pointer, mat_layout=layout, header_fields=fields,
                    channel_labels=labels, channel_records=channel_records, event_fields=event_fields,
                    n_events=len(events), boundary_event_indices=boundary_rows,
                    boundary_cut_samples=cuts, filter_segments=[list(v) for v in segments],
                    fdt_size_bytes=fdt_row['size_bytes'],
                    ica_field_shapes={k: nodes[k]['shape'] for k in sorted(scanner.ICA_FIELDS) if k in nodes})
    return dict(subject=subject, pnts=pnts, labels=labels, observed=observed,
                annotations=annotations, trials=trials, segments=segments)


def process_person(raw_fdt, header, fir_module):
    """Own same-buffer decoder, average reference, analytic FIR, trial averages."""
    pnts = header['pnts']
    io.need(isinstance(raw_fdt, bytes) and len(raw_fdt) == 4 * 33 * pnts, 'fdt_buffer_size')
    stored = np.frombuffer(raw_fdt, dtype='<f4').reshape((33, pnts), order='F')
    positions = [header['labels'].index(label) for label in SCALP]
    scalp = np.array(stored[positions], dtype=np.float64, order='C', copy=True)
    io.need(np.isfinite(scalp).all(), 'nonfinite_contributing_channel')
    with np.errstate(over='raise', invalid='raise'):
        scalp -= np.mean(scalp, axis=0, dtype=np.float64, keepdims=True)
        filtered = np.empty_like(scalp)
        for first, stop in header['segments']:
            filtered[:, first:stop] = fir_module.filter_segment(scalp[:, first:stop], 256.0)
        io.need(np.isfinite(filtered).all(), 'nonfinite_filtered_source')
        trials, epoch_keys, ptps, baselines = [], [], [], []
        accepted = {name: [] for name in CONDITIONS}
        po8 = SCALP.index('PO8')
        for original in header['trials']:
            row = dict(original)
            if row['epoch_status'] == 'ok':
                epoch = filtered[:, row['epoch_first_sample']:row['epoch_last_sample'] + 1]
                io.need(epoch.shape == (30, len(OFFSETS)), 'epoch_shape')
                ptp = np.max(epoch, axis=1) - np.min(epoch, axis=1)
                baseline = np.mean(epoch[:, :52], axis=1, dtype=np.float64)
                io.need(np.isfinite(ptp).all() and np.isfinite(baseline).all(), 'nonfinite_epoch_receipt')
                epoch_keys.append((header['subject'], row['source_event_index']))
                ptps.append(ptp); baselines.append(float(baseline[po8]))
                row['accepted'] = not bool(np.any(ptp > 150.0))
                row['rejection_reason'] = 'accepted' if row['accepted'] else 'peak_to_peak'
                if row['accepted']:
                    corrected = epoch - baseline[:, None]
                    accepted[row['condition']].append(corrected[po8].copy())
            trials.append(row)
        waves = np.zeros((2, len(OFFSETS)), dtype=np.float64)
        flags = np.array([bool(accepted[name]) for name in CONDITIONS], dtype=bool)
        for index, name in enumerate(CONDITIONS):
            if flags[index]: waves[index] = np.mean(np.stack(accepted[name]), axis=0, dtype=np.float64)
        io.need(np.isfinite(waves).all(), 'nonfinite_condition_average')
    counts = dict(subject_id=header['subject'])
    for name in CONDITIONS:
        n_candidates = sum(row['condition'] == name for row in trials)
        n_accepted = len(accepted[name])
        counts.update({f'n_{name}_candidates': n_candidates, f'n_{name}_accepted': n_accepted,
                       f'n_{name}_rejected': n_candidates - n_accepted})
    counts.update(condition_defined=flags.tolist(),
                  rejection_counts={reason: sum(row['rejection_reason'] == reason for row in trials) for reason in REASONS},
                  n_eligible_epochs=len(epoch_keys))
    return dict(trials=trials, epoch_keys=epoch_keys,
                epoch_peak_to_peak_uv=np.array(ptps, dtype=np.float64).reshape(-1, 30),
                epoch_po8_baseline_uv=np.asarray(baselines, dtype=np.float64),
                condition_defined=flags, evoked_po8_uv=waves, analysis=counts)


def reconstruct(data_dir, manifest_path, method_path, schema_path, *, pilot=False):
    io.need(type(pilot) is bool, 'explicit_pilot_boolean')
    root, manifest, method, schema = authenticate(data_dir, manifest_path, method_path, schema_path)
    scanner = _bound_module('mat_metadata.py', SCANNER_SHA)
    fir_module = _bound_module('independent_fir.py', FIR_SHA)
    rows = {(str(r['subject']), r['role']): r for r in manifest['files']}
    headers, annotations = {}, []
    for subject in SUBJECTS:
        set_row, fdt_row = rows[subject, 'set'], rows[subject, 'fdt']
        header = parse_header(_source_bytes(root, set_row), subject, set_row, fdt_row, scanner)
        headers[subject] = header
        annotations.extend(header['annotations'])
    io.need(len(annotations) <= 40000, 'complete_annotation_bound')
    io.need(sum(len(h['trials']) for h in headers.values()) <= 10000, 'complete_candidate_bound')
    selected = SUBJECTS[:1] if pilot else SUBJECTS
    results = []
    for subject in selected:
        results.append(process_person(_source_bytes(root, rows[subject, 'fdt']), headers[subject], fir_module))
    trials = [row for result in results for row in result['trials']]
    io.need(len(trials) <= 10000, 'complete_trial_bound')
    _inventory(root, manifest['files'])
    return dict(status='resource_pilot' if pilot else 'complete', subjects=list(selected),
                condition_labels=list(CONDITIONS), sample_offsets=OFFSETS.copy(),
                condition_defined=np.stack([r['condition_defined'] for r in results]),
                evoked_po8_uv=np.stack([r['evoked_po8_uv'] for r in results]),
                rejection_channel_labels=list(SCALP), annotations=annotations, trials=trials,
                epoch_keys=[key for r in results for key in r['epoch_keys']],
                epoch_peak_to_peak_uv=np.concatenate([r['epoch_peak_to_peak_uv'] for r in results]),
                epoch_po8_baseline_uv=np.concatenate([r['epoch_po8_baseline_uv'] for r in results]),
                source_files=[dict(subject_id=str(r['subject']), role=r['role'], path=r['path'],
                                   size_bytes=r['size_bytes'], sha256=r['sha256']) for r in manifest['files']],
                source_observed=dict(persons=[headers[s]['observed'] for s in SUBJECTS]),
                analysis_observed=dict(persons=[r['analysis'] for r in results]),
                pins=dict(source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA,
                          output_schema_sha256=SCHEMA_SHA), method=method, schema=schema)
