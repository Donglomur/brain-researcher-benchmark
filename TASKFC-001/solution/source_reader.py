"""Prospective independent TASKFC oracle source reader; import is I/O-free.

Only pinned source buffers are decoded. No stager, verifier, bank or access
script is imported. SHA pins and operational clock remain fail-closed pending
the parent's public source/structure freeze. Nibabel supplies calibrated arrays;
the separately implemented grader streams source volumes instead.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

import nibabel as nib
import numpy as np
import oracle_core as core

SOURCE_SHA = '6a463aec353017c1c1b514fe2073b43088b1a9e8da4febcb0acfbd759ae397c6'
METHOD_SHA = 'fb6a014e793013f41c80d8dcb3cbacd5d6567143dc6f8f8c93f339acd5eb136a'
SCHEMA_SHA = '6383d2043d09b8834a8b80133a877137111d904621a7777e1d7c5b4ee09a00c6'
PARTICIPANTS = tuple(f'sub-{i:02d}' for i in range(1, 11))
PERSON_ROLES = ('bold', 'events', 'confounds', 'bold_json')
DOCUMENT_ROLES = ('participants', 'dataset_description', 'derivative_description',
                  'source_readme', 'source_changes', 'bidsignore',
                  'source_access_script_inert', 'nilearn_description')
MAX_MEMBER = 1024**3
MAX_SMALL = 16*1024**2
SUPPORT_PREFIX = b'TASKFC_support_v2\n'
need = core.need


def safe_path(value):
    text = os.fspath(value)
    need(isinstance(text, str) and text.startswith('/') and '\0' not in text
         and all(p not in ('.', '..') for p in text.split('/')), 'absolute_lexical_path')
    path = Path(text)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_path')
            need(part == path or stat.S_ISDIR(mode), 'directory_ancestors')
    return path


def signature(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def stable_bytes(path, cap, sha=None):
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'bounded_regular_file')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        need(signature(os.fstat(handle.fileno())) == signature(before), 'source_replaced_before_read')
        raw = handle.read(cap+1)
        need(len(raw) == before.st_size and signature(os.fstat(handle.fileno())) == signature(before),
             'source_changed_during_read')
    need(signature(path.lstat()) == signature(before), 'source_replaced_after_read')
    if sha is not None:
        need(hashlib.sha256(raw).hexdigest() == sha, 'source_sha256')
    return raw


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def reject(_):
        raise ValueError('nonfinite_json_constant')
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=reject)
    def visit(v, depth=0):
        need(depth <= 64, 'json_depth')
        if isinstance(v, float):
            need(math.isfinite(v), 'nonfinite_json_exponent')
        elif isinstance(v, dict):
            for child in v.values(): visit(child, depth+1)
        elif isinstance(v, list):
            for child in v: visit(child, depth+1)
    visit(value)
    return value


def read_member(root, row):
    raw = stable_bytes(root / row['path'], row['size_bytes'], row['sha256'])
    need(len(raw) == row['size_bytes'], 'exact_member_size')
    if row.get('md5') is not None:
        need(hashlib.md5(raw).hexdigest() == row['md5'], 'member_md5')
    if row.get('git_blob_sha1') is not None:
        git_hash = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        need(git_hash == row['git_blob_sha1'], 'member_git_content')
    return raw


def authenticate(data_dir, manifest_path, method_path, schema_path):
    for pin in (SOURCE_SHA, METHOD_SHA, SCHEMA_SHA):
        need(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin), 'pins_not_frozen')
    root = safe_path(data_dir)
    need(root.is_dir(), 'source_directory')
    manifest_raw = stable_bytes(manifest_path, 4*1024**2, SOURCE_SHA)
    need(stable_bytes(root / 'source_manifest.json', 4*1024**2, SOURCE_SHA) == manifest_raw,
         'matching_internal_external_manifest')
    manifest = strict_json(manifest_raw)
    method = strict_json(stable_bytes(method_path, MAX_SMALL, METHOD_SHA))
    schema = strict_json(stable_bytes(schema_path, MAX_SMALL, SCHEMA_SHA))
    need(all(x.get('task_id') == 'TASKFC-001' for x in (manifest, method, schema)), 'task_identity')
    need(method.get('status', '').startswith('frozen') and schema.get('status', '').startswith('frozen'),
         'public_contract_not_frozen')
    need(manifest['participant_ids'] == list(PARTICIPANTS), 'literal_cohort_order')
    need(method['cohort']['n_expected'] == 10, 'ten_person_contract')
    rows = manifest.get('files')
    need(isinstance(rows, list) and len(rows) == 48, '48_source_members')
    names, role_keys = set(), set()
    for row in rows:
        name = row.get('path')
        need(isinstance(name, str) and '\\' not in name and '\0' not in name,
             'source_path_string')
        p = PurePosixPath(name)
        need(not p.is_absolute() and not re.match('[A-Za-z]:', name)
             and name != 'source_manifest.json' and p.as_posix() == name and len(p.parts) > 0
             and all(v not in ('', '.', '..') for v in name.split('/')) and name not in names,
             'unique_relative_source_path')
        need(type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= MAX_MEMBER,
             'source_size_bound')
        need(isinstance(row.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', row['sha256']),
             'measured_source_sha_required')
        role, sid = row.get('role'), row.get('participant_id')
        need((role in PERSON_ROLES and sid in PARTICIPANTS)
             or (role in DOCUMENT_ROLES and sid is None), 'source_role_participant')
        key = (sid, role)
        need(key not in role_keys, 'unique_source_role_join')
        role_keys.add(key); names.add(name)
    expected = {(s, r) for s in PARTICIPANTS for r in PERSON_ROLES}
    expected |= {(None, r) for r in DOCUMENT_ROLES}
    need(role_keys == expected, 'complete_role_inventory')
    directories = {str(p) for n in names for p in PurePosixPath(n).parents if str(p) != '.'}
    actual_files, actual_dirs = set(), set()
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        need(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'source_link_or_special')
        (actual_dirs if stat.S_ISDIR(mode) else actual_files).add(path.relative_to(root).as_posix())
    need(actual_files == names | {'source_manifest.json'} and actual_dirs == directories, 'closed_source_inventory')
    for row in rows:
        read_member(root, row)
    return dict(root=root, manifest=manifest, method=method, schema=schema,
                pins=dict(source_manifest_sha256=SOURCE_SHA, method_sha256=METHOD_SHA,
                          output_schema_sha256=SCHEMA_SHA))


def member(inputs, sid, role):
    matched = [r for r in inputs['manifest']['files']
               if r['participant_id'] == sid and r['role'] == role]
    need(len(matched) == 1, 'unique_member')
    return matched[0]


def literal(value):
    x = float(value)
    return x if math.isfinite(x) else 'NaN' if math.isnan(x) else '+Inf' if x > 0 else '-Inf'


def image_header(raw):
    need(len(raw) == 352, 'nifti_header_length')
    h = nib.Nifti1Header(binaryblock=raw[:348], check=False)
    need(int(h['sizeof_hdr']) == 348 and h['magic'].tobytes() == b'n+1\0', 'single_file_nifti1')
    shape, dtype = tuple(map(int, h.get_data_shape())), h.get_data_dtype()
    need(len(shape) == 4 and all(v > 0 for v in shape) and math.prod(shape[:3]) <= 20_000_000
         and 2 <= shape[3] <= 10000, 'bounded_4d_image')
    need(dtype.kind in 'iuf' and dtype.itemsize <= 8 and int(h['bitpix']) == dtype.itemsize*8,
         'real_image_dtype')
    offset = float(h['vox_offset'])
    need(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= 1024**2,
         'bounded_integral_image_offset')
    logical_size = int(offset)+math.prod(shape)*dtype.itemsize
    need(logical_size <= 2*1024**3, 'decoded_image_bound')
    affine = np.asarray(h.get_best_affine(), dtype=np.float64)
    need(np.isfinite(affine).all() and np.array_equal(affine[3], [0, 0, 0, 1])
         and np.linalg.det(affine[:3, :3]) != 0, 'finite_nonsingular_affine')
    slope, inter = h.get_slope_inter()
    slope, inter = (1., 0.) if slope is None else (float(slope), float(inter))
    need(math.isfinite(slope) and math.isfinite(inter), 'finite_effective_scaling')
    spatial, temporal = h.get_xyzt_units()
    record = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
                  spatial_units=spatial, temporal_units=temporal, zooms=[literal(x) for x in h.get_zooms()],
                  raw_toffset=literal(h['toffset']), raw_scl_slope=literal(h['scl_slope']),
                  raw_scl_inter=literal(h['scl_inter']), effective_slope=slope, effective_intercept=inter)
    return record, affine, logical_size


def image_from_buffer(raw, compressed, decode=False):
    stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw)
    with stream:
        head = stream.read(352)
        record, affine, size = image_header(head)
        if not decode:
            return record, affine, None
        logical = head+stream.read(size-352+1)
        need(len(logical) == size, 'exact_decoded_image_length_eof')
    image = nib.Nifti1Image.from_bytes(logical)
    values = image.get_fdata(dtype=np.float64)
    need(values.shape == tuple(record['shape']), 'decoded_shape')
    # Do not impose an all-voxel QC rule: core.voxel_mean checks measured support.
    return record, affine, values


def table(raw):
    need(len(raw) <= MAX_SMALL, 'table_byte_bound')
    records = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter='\t'))
    need(records and records[0] and len(records) <= 100001 and len(records[0]) <= 256,
         'table_shape_bound')
    names = records[0]
    need(all(names) and len(set(names)) == len(names), 'unique_table_header')
    need(all(len(r) == len(names) for r in records[1:]), 'table_width')
    return names, [dict(zip(names, r)) for r in records[1:]]


def numeric_token(token):
    need(isinstance(token, str) and token.strip() != '', 'missing_numeric_token')
    value = float(token)
    need(math.isfinite(value), 'finite_numeric_token')
    return value


def event_table(raw, sid):
    columns, rows = table(raw)
    need({'onset', 'duration', 'trial_type'} <= set(columns), 'event_columns')
    events, ledger = [], []
    for index, row in enumerate(rows):
        values = dict(trial_type=row['trial_type'], onset=numeric_token(row['onset']),
                      duration=numeric_token(row['duration']),
                      modulation=numeric_token(row['modulation']) if 'modulation' in columns else 1.)
        need(values['trial_type'] in core.TASK_NAMES and values['duration'] >= 0
             and math.isfinite(values['onset']+values['duration']), 'event_domain')
        events.append(values)
        ledger.append(dict(subject=sid, source_event_index=index, trial_type=row['trial_type'],
                           onset_token=row['onset'], duration_token=row['duration'],
                           modulation_token=row.get('modulation', ''), onset_s=values['onset'],
                           duration_s=values['duration'], modulation=values['modulation']))
    need({e['trial_type'] for e in events} == set(core.TASK_NAMES), 'both_conditions')
    return columns, events, ledger


def motion_table(raw, n_frames):
    columns, rows = table(raw)
    need(set(core.MOTION_NAMES) <= set(columns) and len(rows) == n_frames, 'six_motion_rows')
    motion = np.asarray([[numeric_token(r[k]) for k in core.MOTION_NAMES] for r in rows], dtype=np.float64)
    return columns, motion


def load_primitives(inputs, subjects=None):
    """All headers/tables are observed; decode only the explicit pilot/full IDs."""
    ids = list(PARTICIPANTS if subjects is None else subjects)
    need(ids == list(PARTICIPANTS) or ids == [PARTICIPANTS[0]], 'full_or_fixed_first_pilot')
    root, method = inputs['root'], inputs['method']
    tr = core.scalar(method['clock']['TR_s'])
    origin = core.scalar(method['clock']['frame_origin_s'])
    need(tr > 0, 'positive_operational_tr')
    observed = dict(headers={}, event_column_names={}, confound_column_names={},
                    selected_motion_columns=list(core.MOTION_NAMES), operational_clock={})
    persons, cohort, all_events = {}, [], []
    for sid in PARTICIPANTS:
        br, er, cr = (member(inputs, sid, r) for r in ('bold', 'events', 'confounds'))
        header, affine, values = image_from_buffer(read_member(root, br), br['path'].endswith('.gz'), sid in ids)
        n = header['shape'][3]
        need(n == method['source']['n_frames_by_participant'][sid], 'frozen_frame_count')
        eh, events, ledger = event_table(read_member(root, er), sid)
        ch, motion = motion_table(read_member(root, cr), n)
        need(all(e['onset'] >= origin+method['design']['hrf']['min_onset_s'] for e in events),
             'event_before_supported_clock')
        indices = core.sphere_support(tuple(header['shape'][:3]), affine)
        support = [dict(roi_id=roi, n_voxels=len(v), support_sha256=hashlib.sha256(
                   SUPPORT_PREFIX+np.asarray(v, dtype='<i8').tobytes()).hexdigest())
                   for roi, v in zip(core.ROI_NAMES, indices)]
        observed['headers'][sid] = header
        observed['event_column_names'][sid] = eh
        observed['confound_column_names'][sid] = ch
        observed['operational_clock'][sid] = dict(TR_s=tr, frame_origin_s=origin)
        all_events.extend(ledger)
        cohort.append(dict(subject=sid, bold_path=br['path'], events_path=er['path'], confounds_path=cr['path'],
                           n_frames=n, operational_TR_s=tr, operational_frame_origin_s=origin,
                           left_n_voxels=support[0]['n_voxels'], right_n_voxels=support[1]['n_voxels'],
                           left_support_sha256=support[0]['support_sha256'], right_support_sha256=support[1]['support_sha256']))
        if sid not in ids:
            continue
        raw = np.asarray([[core.voxel_mean(values[..., t], v) for v in indices] for t in range(n)], dtype=np.float64)
        del values
        designs = core.build_design(n, tr, origin, events, motion,
                                   high_pass=method['design']['cosine']['high_pass_hz'],
                                   oversampling=method['design']['hrf']['oversampling'],
                                   min_onset=method['design']['hrf']['min_onset_s'])
        analyzed = core.analyze_person(raw, designs)
        persons[sid] = dict(raw=raw, designs=designs, **analyzed)
    return dict(participant_ids=ids, participants=persons, cohort=cohort,
                events=all_events, source_observed=observed)
