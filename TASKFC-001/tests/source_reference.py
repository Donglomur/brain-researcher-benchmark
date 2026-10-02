"""Independent TASKFC source authentication and composition, no bank/oracle imports.

Frozen private pins bind source and public contracts. Structural inspection uses
only authenticate_sources plus headers/tables, never reconstruct. The optional
fixed first-person replay authenticates every source and validates every header
and table, then decodes/fits only sub-01 and never computes endpoints.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

import numpy as np
import source_primitives as p

IDS = tuple(f'sub-{i:02d}' for i in range(1, 11))
PERSON_ROLES = {'bold', 'events', 'confounds', 'bold_json'}
DOC_ROLES = {'participants', 'dataset_description', 'derivative_description',
             'source_readme', 'source_changes', 'bidsignore',
             'source_access_script_inert', 'nilearn_description'}
SOURCE_SHA = '6a463aec353017c1c1b514fe2073b43088b1a9e8da4febcb0acfbd759ae397c6'
METHOD_SHA = 'fb6a014e793013f41c80d8dcb3cbacd5d6567143dc6f8f8c93f339acd5eb136a'
SCHEMA_SHA = '6383d2043d09b8834a8b80133a877137111d904621a7777e1d7c5b4ee09a00c6'
HEADER_KEYS = ('shape', 'selected_affine', 'storage_dtype', 'spatial_units',
               'temporal_units', 'zooms', 'raw_toffset', 'raw_scl_slope',
               'raw_scl_inter', 'effective_slope', 'effective_intercept')


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            p.need(key not in out, 'duplicate_json_key'); out[key] = value
        return out
    def bad(_): raise ValueError('nonfinite_json')
    out = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    def finite(v, depth=0):
        p.need(depth <= 64, 'json_depth')
        if isinstance(v, float): p.need(math.isfinite(v), 'nonfinite_json')
        if isinstance(v, dict):
            for item in v.values(): finite(item, depth+1)
        elif isinstance(v, list):
            for item in v: finite(item, depth+1)
    finite(out)
    return out


def pinned_document(path, expected_sha):
    p.need(isinstance(expected_sha, str) and re.fullmatch('[a-f0-9]{64}', expected_sha),
           'frozen_pin_required')
    path = p.safe_path(path)
    size = path.lstat().st_size
    raw = p.small_bytes(path, {'size_bytes': size, 'sha256': expected_sha})
    return strict_json(raw)


def authenticate_sources(data_dir, manifest_sha):
    root = p.safe_path(data_dir)
    manifest = pinned_document(root/'source_manifest.json', manifest_sha)
    p.need(manifest['task_id'] == 'TASKFC-001' and manifest['participant_ids'] == list(IDS),
           'source_task_cohort_identity')
    rows = manifest['files']
    p.need(isinstance(rows, list) and len(rows) == 48, 'closed_48_source_members')
    paths, keyed = set(), {}
    for row in rows:
        name = row['path']
        p.need(isinstance(name, str) and name and '\\' not in name and '\0' not in name
               and not name.startswith('/') and not re.match('[A-Za-z]:', name)
               and all(v not in ('', '.', '..') for v in name.split('/')), 'source_path')
        p.need(name != 'source_manifest.json' and name not in paths, 'duplicate_source_path')
        p.need(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= p.MAX_FILE
               and isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256']),
               'source_identity')
        key = row['participant_id'], row['role']
        p.need(key not in keyed, 'duplicate_source_role')
        keyed[key] = row; paths.add(name)
    required = {(sid, role) for sid in IDS for role in PERSON_ROLES} | {(None, role) for role in DOC_ROLES}
    p.need(set(keyed) == required, 'source_participant_role_membership')
    directories = {str(q) for name in paths for q in PurePosixPath(name).parents if str(q) != '.'}
    actual_files, actual_dirs = set(), set()
    for base, ds, fs in os.walk(root, followlinks=False):
        for name in ds+fs:
            path = Path(base)/name; mode = path.lstat().st_mode
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(mode): actual_dirs.add(relative)
            else:
                p.need(stat.S_ISREG(mode), 'source_nonregular_inventory')
                actual_files.add(relative)
    p.need(actual_files == paths | {'source_manifest.json'} and actual_dirs == directories,
           'source_closed_inventory')
    for row in rows:
        with p.authenticated_stream(root/row['path'], row): pass
    return root, manifest, keyed


def source_identities(manifest):
    keys = ('path', 'role', 'participant_id', 'size_bytes', 'sha256')
    return [{k: row[k] for k in keys} for row in manifest['files']]


def source_structure(data_dir, manifest_sha):
    """Authenticated headers, original timing/nuisance tables and geometry only."""
    root, manifest, keyed = authenticate_sources(data_dir, manifest_sha)
    documents = {}
    for role in DOC_ROLES:
        row = keyed[(None, role)]
        if role == 'source_access_script_inert':
            documents[role] = {'path': row['path'], 'executed': False, 'parsed': False}
        else:
            raw = p.small_bytes(root/row['path'], row)
            documents[role] = strict_json(raw) if row['path'].endswith('.json') else raw.decode('utf-8-sig')
    people = {}
    for sid in IDS:
        br, er, cr, jr = [keyed[(sid, role)] for role in ('bold', 'events', 'confounds', 'bold_json')]
        header, _, affine = p.read_header(root/br['path'], br)
        ec, parsed, event_rows = p.events(p.small_bytes(root/er['path'], er))
        cc, confounds = p.motion(p.small_bytes(root/cr['path'], cr), header['shape'][3])
        sidecar = strict_json(p.small_bytes(root/jr['path'], jr))
        supports = p.sphere_support(tuple(header['shape'][:3]), affine)
        people[sid] = dict(header=header, bold_json=sidecar,
            geometry=p.support_records(supports), event_columns=ec, event_rows=event_rows,
            event_count=len(parsed), condition_counts={c: sum(e['trial_type'] == c for e in parsed)
                for c in ('language', 'string')}, onset_min=min(e['onset'] for e in parsed),
            offset_max=max(e['onset']+e['duration'] for e in parsed),
            confound_columns=cc, motion_rows=len(confounds), selected_motion_columns=list(p.MOTION),
            missing_motion_values=0, motion_imputation=False)
    return dict(status='structural_only_no_BOLD_samples', source_manifest_sha256=manifest_sha,
                n_files=len(manifest['files']), source_bytes=sum(r['size_bytes'] for r in manifest['files']),
                participant_ids=list(IDS), documents=documents, participants=people,
                bold_samples_read=0, roi_means_computed=False, designs_fitted=False,
                old_bank_loaded=False)


def prepare_reference(data_dir, method_path, schema_path):
    """Authenticate all 48 members and validate all ten structures; no BOLD samples."""
    method = pinned_document(method_path, METHOD_SHA)
    schema = pinned_document(schema_path, SCHEMA_SHA)
    p.need(method['task_id'] == schema['task_id'] == 'TASKFC-001', 'fixed_task')
    p.need(method['status'].startswith('frozen') and schema['status'].startswith('frozen'), 'public_contract_freeze')
    p.need(method['source']['source_manifest_sha256'] == SOURCE_SHA, 'method_source_binding')
    p.need(method['cohort']['n_expected'] == len(IDS), 'fixed_expected_cohort')
    p.need(method['design']['motion_columns'] == list(p.MOTION), 'fixed_motion_order')
    p.need(method['design']['conditions'] == ['language', 'string'], 'fixed_conditions')
    root, manifest, keyed = authenticate_sources(data_dir, SOURCE_SHA)
    structures = {sid: participant_structure(root, keyed, sid, method) for sid in IDS}
    return dict(root=root, manifest=manifest, keyed=keyed, method=method, schema=schema,
                structures=structures)


def participant_structure(root, keyed, sid, method):
    """Read authenticated headers/tables and enforce the frozen original facts."""
    p.need(sid in IDS, 'literal_participant')
    br, er, cr, jr = [keyed[(sid, role)] for role in ('bold', 'events', 'confounds', 'bold_json')]
    header, _, affine = p.read_header(root/br['path'], br)
    expected = method['source']
    n = expected['n_frames_by_participant'][sid]
    p.need(header['shape'] == expected['shape'] and header['shape'][3] == n, 'frozen_source_shape_frames')
    sidecar = strict_json(p.small_bytes(root/jr['path'], jr))
    tr = method['clock']['TR_s']
    tolerance = method['tolerances']['header']
    def same_tr(value):
        return type(value) in (int, float) and math.isfinite(value) and math.isclose(
            value, tr, abs_tol=tolerance['atol'], rel_tol=tolerance['rtol'])
    p.need(header['temporal_units'] == 'sec' and same_tr(header['zooms'][3]), 'frozen_header_TR')
    p.need(same_tr(sidecar.get('RepetitionTime')), 'frozen_sidecar_TR')
    event_columns, events, event_rows = p.events(p.small_bytes(root/er['path'], er))
    confound_columns, motion = p.motion(p.small_bytes(root/cr['path'], cr), n)
    p.need(event_columns == expected['event_columns'], 'frozen_event_columns')
    p.need(confound_columns == expected['confound_source_columns'], 'frozen_motion_columns')
    p.need(len(events) == expected['events_per_participant'], 'frozen_event_count')
    counts = {c: sum(e['trial_type'] == c for e in events) for c in method['design']['conditions']}
    p.need(counts == expected['conditions_per_participant'], 'frozen_condition_counts')
    minimum = method['clock']['frame_origin_s'] + method['design']['hrf']['min_onset_s']
    p.need(all(e['onset'] >= minimum for e in events), 'event_before_supported_clock')
    geometry = p.support_records(p.sphere_support(tuple(header['shape'][:3]), affine))
    return dict(header=header, geometry=geometry, events=events, event_rows=event_rows,
                event_columns=event_columns, confound_columns=confound_columns, motion=motion)


def reconstruct_participant(prepared, sid):
    """Decode one authenticated participant and return primitives, not FC endpoints."""
    import sensitivity_math as m
    p.need(sid in IDS, 'literal_participant')
    root, keyed, method = (prepared[k] for k in ('root', 'keyed', 'method'))
    structure = prepared['structures'][sid]
    br = keyed[(sid, 'bold')]
    raw, header, geometry = p.extract_series(root/br['path'], br, expected_header=structure['header'])
    p.need(geometry == structure['geometry'], 'source_geometry_changed')
    n = method['source']['n_frames_by_participant'][sid]
    p.need(raw.shape == (n, 2) and np.isfinite(raw).all(), 'source_primitive_shape')
    tr, origin = method['clock']['TR_s'], method['clock']['frame_origin_s']
    events, motion = structure['events'], structure['motion']
    times = np.arange(n, dtype=np.float64)*tr+origin
    designs = m.build_design(times, [e['onset'] for e in events],
        [e['duration'] for e in events], [e['trial_type'] for e in events],
        [e['modulation'] for e in events], motion,
        high_pass=method['design']['cosine']['high_pass_hz'],
        oversampling=method['design']['hrf']['oversampling'],
        min_onset=method['design']['hrf']['min_onset_s'])
    fits = [m.fit_residuals(raw, designs[key]) for key in ('nuisance_design', 'full_design')]
    residuals = np.stack([fit['residuals'] for fit in fits], axis=1)
    support = m.source_support(raw, residuals)
    columns = [designs['nuisance_columns'], designs['full_columns']]
    diagnostics = dict(models=[dict(model_id=model, column_ids=columns[i],
        rank=fits[i]['design_rank'], residual_df=fits[i]['residual_df'],
        singular_values=fits[i]['singular_values'].tolist(), rank_cutoff=fits[i]['rank_cutoff'],
        roi_support=[dict(roi_id=roi, raw_sample_sd=float(support['raw_sample_sd'][j]),
            residual_centered_l2=float(support['residual_centered_l2'][i, j]),
            activity_threshold=float(support['activity_threshold'][j]),
            active=bool(support['active'][i, j])) for j, roi in enumerate(p.ROIS)])
        for i, model in enumerate(m.MODELS)])
    return dict(frame_index=np.arange(n, dtype=np.int64), frame_times=times, raw=raw,
        designs=dict(zip(m.MODELS, [designs['nuisance_design'], designs['full_design']])),
        design_columns=dict(zip(m.MODELS, columns)), residuals=residuals, active=support['active'],
        source_observed=dict(header={k: header[k] for k in HEADER_KEYS},
            event_column_names=structure['event_columns'], confound_column_names=structure['confound_columns'],
            operational_clock=dict(TR_s=tr, frame_origin_s=origin)), analysis_observed=diagnostics)


def reconstruct(data_dir, method_path, schema_path, *, subjects=None):
    """All-member auth; full primitives or only fixed sub-01. No derived endpoints."""
    ids = list(IDS) if subjects is None else list(subjects)
    p.need(ids == list(IDS) or ids == [IDS[0]], 'full_or_fixed_first_pilot')
    prepared = prepare_reference(data_dir, method_path, schema_path)
    method, schema, manifest, keyed = (prepared[k] for k in ('method', 'schema', 'manifest', 'keyed'))
    people = {sid: reconstruct_participant(prepared, sid) for sid in ids}
    cohort, ledger = [], []
    tr, origin = method['clock']['TR_s'], method['clock']['frame_origin_s']
    for sid in IDS:
        br, er, cr = [keyed[(sid, role)] for role in ('bold', 'events', 'confounds')]
        structure = prepared['structures'][sid]
        n, geometry = structure['header']['shape'][3], structure['geometry']
        cohort.append(dict(subject=sid, bold_path=br['path'], events_path=er['path'], confounds_path=cr['path'],
            n_frames=n, operational_TR_s=tr, operational_frame_origin_s=origin,
            left_n_voxels=geometry[0]['n_voxels'], right_n_voxels=geometry[1]['n_voxels'],
            left_support_sha256=geometry[0]['support_sha256'], right_support_sha256=geometry[1]['support_sha256']))
        for row in structure['event_rows']:
            original, numeric = row['original'], row['numeric']
            ledger.append(dict(subject=sid, source_event_index=row['source_row_index'],
                trial_type=original['trial_type'], onset_token=original['onset'], duration_token=original['duration'],
                modulation_token=original.get('modulation', ''), onset_s=numeric['onset'],
                duration_s=numeric['duration'], modulation=numeric['modulation']))
    return dict(participant_ids=ids, participants=people, source_files=source_identities(manifest),
                events=ledger, cohort=cohort, method=method, schema=schema,
                source_observed=dict(
                    headers={s: {k: prepared['structures'][s]['header'][k] for k in HEADER_KEYS} for s in IDS},
                    event_column_names={s: prepared['structures'][s]['event_columns'] for s in IDS},
                    confound_column_names={s: prepared['structures'][s]['confound_columns'] for s in IDS},
                    selected_motion_columns=list(p.MOTION),
                    operational_clock={s: dict(TR_s=tr, frame_origin_s=origin) for s in IDS}),
                status='complete_primitives' if ids == list(IDS) else 'resource_pilot',
                structural_participant_ids=list(IDS), endpoints_computed=False,
                pins=dict(source_manifest_sha256=SOURCE_SHA, method_sha256=METHOD_SHA, output_schema_sha256=SCHEMA_SHA))
