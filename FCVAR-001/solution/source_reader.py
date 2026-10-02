"""External prospective FCVAR oracle reader; import-safe, no fetches.

Generic closed-byte/safe-path patterns adapt the reviewed PR191 reader.
HO label decoding, source joins and voxel enumeration are independent of the
grader. The public signal kernel is deliberately shared for temporal arithmetic.
Final source/method/schema pins fail closed until parent installation.
"""
from __future__ import annotations
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import xml.etree.ElementTree as ET

import nibabel as nib
import numpy as np
from scipy import linalg, ndimage
import signal_kernel as kernel

require = kernel.require
SOURCE_SHA = 'a3d0f6aa1901361c55e29cf6e09a5ee31c8c084d52e4ba7e9a1f7ccddf00609f'
METHOD_SHA = '6268f618e7945a9be5ce08bd4adcae38b76bd65f8c510a9cbec4885a5713e080'
SCHEMA_SHA = '02211cbf7606a980ba2737a7418d16b446ea7f8b0e5d3cf569df5b2118d62b27'
SOURCE_MEMBER_COUNT = 67
FIXED_IDS = ('0010042', '0010064', '0010128', '0021019', '0023008', '0023012',
    '0027011', '0027018', '0027034', '0027037', '1019436', '1206380', '1552181',
    '1679142', '2014113', '2497695', '3007585', '3154996', '3699991', '3884955',
    '3902469', '4046678', '4134561', '4164316', '4275075', '6115230', '7774305',
    '8409791', '8697774', '9750701')
SINGLE_ROLES = frozenset(('cohort_ids', 'phenotype_metadata', 'slice_timing_metadata',
    'atlas_image', 'atlas_labels', 'provenance_adhd_notice', 'provenance_ho_notice'))


def safe_path(value):
    text = os.fspath(value)
    require(text.startswith('/') and '\0' not in text and
            all(v not in ('.', '..') for v in text.split('/')), 'absolute lexical path required')
    path = Path(text)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            require(not stat.S_ISLNK(mode), 'symlink path refused')
            require(part == path or stat.S_ISDIR(mode), 'directory ancestors required')
    return path


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def stable_bytes(path, cap, sha=None):
    path = safe_path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'bounded regular source')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        require(signature(os.fstat(handle.fileno())) == signature(before), 'source replaced before read')
        raw = handle.read(cap + 1)
        require(len(raw) == before.st_size and signature(os.fstat(handle.fileno())) == signature(before),
                'source changed during read')
    require(signature(path.lstat()) == signature(before), 'source replaced after read')
    if sha is not None:
        require(hashlib.sha256(raw).hexdigest() == sha, 'source SHA256 mismatch')
    return raw


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def reject(_):
        raise kernel.PreconditionError('nonfinite JSON constant')
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=reject)
    def walk(item, depth=0):
        require(depth <= 64, 'JSON depth bound')
        if isinstance(item, float): require(math.isfinite(item), 'nonfinite JSON exponent')
        if isinstance(item, dict):
            for v in item.values(): walk(v, depth + 1)
        if isinstance(item, list):
            for v in item: walk(v, depth + 1)
    walk(value)
    return value


def read_member(root, row):
    raw = stable_bytes(root / row['path'], row['size_bytes'], row['sha256'])
    require(len(raw) == row['size_bytes'], 'exact source size')
    if row.get('md5') is not None:
        require(hashlib.md5(raw).hexdigest() == row['md5'], 'source MD5 mismatch')
    if row.get('git_blob_sha1') is not None:
        digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        require(digest == row['git_blob_sha1'], 'source Git-content mismatch')
    return raw


def authenticate(data_dir, method_path, schema_path):
    for pin in (SOURCE_SHA, METHOD_SHA, SCHEMA_SHA):
        require(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin), 'private pins not frozen')
    root = safe_path(data_dir)
    require(root.is_dir(), 'source directory required')
    method = strict_json(stable_bytes(method_path, 2*1024**2, METHOD_SHA))
    schema = strict_json(stable_bytes(schema_path, 2*1024**2, SCHEMA_SHA))
    require(method.get('task_id') == schema.get('task_id') == 'FCVAR-001', 'fixed task identity')
    require(method['contract_status'].startswith('frozen'), 'method not frozen')
    require(method['source']['participant_ids'] == list(FIXED_IDS), 'fixed sorted legacy30 membership')
    require(method['temporal_cleaning']['confound_columns'] == list(kernel.CONFOUND_COLUMNS), 'fixed13 nuisance order')
    frame_counts = method['source']['n_frames_by_participant']
    trs = method['source']['tr_sec_by_participant']
    require(isinstance(frame_counts, dict) and set(frame_counts) == set(FIXED_IDS), 'frozen frame-count membership')
    require(isinstance(trs, dict) and set(trs) == set(FIXED_IDS), 'frozen clock membership')
    require(all(type(v) is int and 33 < v <= 10000 for v in frame_counts.values()), 'bounded frozen frames')
    manifest = strict_json(stable_bytes(root / 'source_manifest.json', 4*1024**2, SOURCE_SHA))
    require(manifest.get('task_id') == 'FCVAR-001', 'source task identity')
    rows = manifest.get('files')
    require(isinstance(rows, list) and len(rows) == SOURCE_MEMBER_COUNT, 'exact67 source members')
    names, roles, person_roles = set(), [], set()
    for row in rows:
        name = row.get('path')
        require(isinstance(name, str) and name and '\\' not in name and '\0' not in name,
                'literal source member path')
        p = PurePosixPath(name)
        require(not p.is_absolute() and str(p) == name and all(x not in ('.', '..') for x in name.split('/')),
                'relative canonical source path')
        require(name not in names and name != 'source_manifest.json', 'unique source member')
        role, sid = row.get('role'), row.get('participant_id')
        require(role in SINGLE_ROLES | {'bold', 'confounds'}, 'known source role')
        if role in ('bold', 'confounds'):
            require(sid in FIXED_IDS and (sid, role) not in person_roles, 'exact person-role join')
            person_roles.add((sid, role))
        else:
            require(sid is None, 'nonperson source role')
            roles.append(role)
        require(type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= 512*1024**2, 'bounded source size')
        require(isinstance(row.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'source SHA')
        names.add(name)
    require(set(roles) == SINGLE_ROLES and len(roles) == len(SINGLE_ROLES), 'complete unique nonperson roles')
    require(person_roles == {(sid, role) for sid in FIXED_IDS for role in ('bold', 'confounds')}, 'complete30 person pairs')
    require(sum(r['size_bytes'] for r in rows) <= 4*1024**3, 'source total-byte bound')
    expected_dirs = {str(p) for name in names for p in PurePosixPath(name).parents if str(p) != '.'}
    files, dirs = set(), set()
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'source link or special member')
        (dirs if stat.S_ISDIR(mode) else files).add(path.relative_to(root).as_posix())
    require(files == names | {'source_manifest.json'} and dirs == expected_dirs, 'closed source inventory')
    for row in rows:
        read_member(root, row)
    return dict(root=root, manifest=manifest, method=method, schema=schema,
                pins=dict(source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA,
                          output_schema_sha256=SCHEMA_SHA))


def member(inputs, role, subject=None):
    rows = [r for r in inputs['manifest']['files'] if r['role'] == role and r.get('participant_id') == subject]
    require(len(rows) == 1, 'unique source role join')
    return rows[0]


def table(raw, delimiter, *, allow_leading_unnamed=False):
    require(len(raw) <= 16*1024**2, 'bounded source table bytes')
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=delimiter))
    require(rows and rows[0] and len(rows) <= 10001 and len(rows[0]) <= 256, 'bounded source table')
    # The original phenotype CSV carries one unnamed documentary row index.
    # It is retained literally, never used for identity; other tables stay strict.
    named = rows[0][1:] if allow_leading_unnamed and rows[0][0] == '' else rows[0]
    require(named and all(named) and len(set(rows[0])) == len(rows[0]), 'unique nonempty table columns')
    require(all(len(r) == len(rows[0]) for r in rows[1:]), 'source table width')
    require(all(len(field) <= 1024**2 for row in rows for field in row), 'source field bound')
    return rows[0], [dict(zip(rows[0], row)) for row in rows[1:]]


def original_id(token):
    require(isinstance(token, str), 'source ID token')
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise kernel.PreconditionError('source ID token not decimal') from exc
    require(value.is_finite() and value == value.to_integral_value() and 0 <= value <= 9999999,
            'source ID exact integer')
    return f'{int(value):07d}'


def literal(value):
    x = float(value)
    return x if math.isfinite(x) else 'NaN' if math.isnan(x) else '+Inf' if x > 0 else '-Inf'


def documentary_at_header_precision(seconds, temporal_units):
    factors = {'sec': 1., 'msec': 1e-3, 'usec': 1e-6}
    require(temporal_units in factors and math.isfinite(seconds) and .1 < seconds < 10,
            'finite documentary TR and declared header time units')
    factor = factors[temporal_units]
    # NIfTI1 pixdim stores float32 in the declared header unit. This checks
    # documentary consistency without replacing the operational header clock.
    represented = float(np.float32(seconds/factor))*factor
    require(math.isfinite(represented) and represented > 0, 'representable documentary clock')
    return represented


def image_header(raw, compressed):
    stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw)
    with stream:
        block = stream.read(352)
    require(len(block) == 352, 'NIfTI header bytes')
    h = nib.Nifti1Header(binaryblock=block[:348], check=False)
    require(int(h['sizeof_hdr']) == 348 and h['magic'].tobytes() == b'n+1\0', 'single-file NIfTI1')
    shape, dtype = tuple(map(int, h.get_data_shape())), h.get_data_dtype()
    require(len(shape) in (3, 4) and all(x > 0 for x in shape) and dtype.kind in 'iuf', 'bounded real NIfTI shape')
    offset = float(h['vox_offset'])
    require(math.isfinite(offset) and offset >= 352 and offset.is_integer(), 'integral image offset')
    expected = int(offset) + math.prod(shape)*dtype.itemsize
    require(expected <= 1024**3, 'bounded decompressed NIfTI')
    affine = np.asarray(h.get_best_affine(), dtype=np.float64)
    require(np.isfinite(affine).all() and np.linalg.det(affine[:3, :3]) != 0, 'finite nonsingular affine')
    slope, inter = h.get_slope_inter()
    slope, inter = (1., 0.) if slope is None else (float(slope), float(inter))
    require(math.isfinite(slope) and math.isfinite(inter), 'finite effective scaling')
    spatial, temporal = h.get_xyzt_units()
    meta = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
        spatial_units=spatial, temporal_units=temporal, zooms=[literal(x) for x in h.get_zooms()],
        raw_toffset=literal(h['toffset']), raw_scl_slope=literal(h['scl_slope']),
        raw_scl_inter=literal(h['scl_inter']), effective_slope=slope, effective_intercept=inter)
    return h, affine, meta, expected


def decode_image(raw, compressed):
    header, affine, metadata, expected = image_header(raw, compressed)
    stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw)
    with stream:
        logical = stream.read(expected + 1)
    require(len(logical) == expected, 'exact decompressed NIfTI length/EOF')
    image = nib.Nifti1Image.from_bytes(logical)
    values = np.asarray(image.get_fdata(dtype=np.float64), dtype=np.float64)
    require(values.shape == tuple(header.get_data_shape()), 'decoded image shape')
    # BOLD outside contributing support may be nonfinite; finite check occurs
    # only after geometry enumeration, before any global activity filtering.
    return values, affine, metadata


def atlas_labels(raw):
    require(len(raw) <= 1024**2, 'bounded XML labels')
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'external/entity XML refused')
    root = ET.fromstring(raw)
    entries = {}
    for node in root.findall('.//label'):
        index = node.get('index')
        require(isinstance(index, str) and re.fullmatch('[0-9]+', index), 'original XML index')
        roi = int(index) + 1
        label = ''.join(node.itertext()).strip()
        require(1 <= roi <= 48 and roi not in entries and label, 'unique complete source label')
        entries[roi] = label
    require(set(entries) == set(range(1, 49)), 'all48 original XML labels')
    return [entries[i] for i in range(1, 49)]


def spatial_support(atlas, atlas_affine, shape, affine):
    labels = np.asarray(atlas)
    require(labels.ndim == 3 and np.isfinite(labels).all() and
            np.all(labels == np.floor(labels)) and np.all((labels >= 0) & (labels <= 48)),
            'all atlas values finite integer0..48')
    if labels.shape == tuple(shape) and np.array_equal(atlas_affine, affine):
        resampled = labels.copy()
    else:
        transform = np.eye(4) if np.array_equal(atlas_affine, affine) else linalg.inv(atlas_affine) @ affine
        resampled = ndimage.affine_transform(labels, matrix=transform[:3, :3], offset=transform[:3, 3],
            output_shape=tuple(shape), order=0, mode='constant', cval=0, prefilter=False)
    flat = resampled.reshape(-1, order='C')
    supports = [np.flatnonzero(flat == i).astype(np.int64) for i in range(1, 49)]
    prefix = (b'FCVAR_support_v3\n' + np.asarray(shape, dtype='<i8').tobytes() +
              np.asarray(affine, dtype='<f8').tobytes(order='C'))
    digests = [hashlib.sha256(prefix + a.astype('<i8').tobytes()).hexdigest() for a in supports]
    return supports, digests


def extract_means(bold, supports):
    require(bold.ndim == 4 and len(supports) == 48, 'full4D source and48 supports')
    union = np.unique(np.concatenate(supports))
    result = np.zeros((bold.shape[-1], 48), dtype=np.float64)
    for t in range(bold.shape[-1]):
        flat = bold[..., t].reshape(-1, order='C')
        require(np.isfinite(flat[union]).all(), 'nonfinite contributing source voxel before activity')
        for roi, support in enumerate(supports):
            if len(support):
                result[t, roi] = np.mean(np.ascontiguousarray(flat[support], dtype=np.float64), dtype=np.float64)
    require(np.isfinite(result).all(), 'finite ROI means')
    return result


def load(inputs, subjects=None, progress=None, on_person=None):
    root, method = inputs['root'], inputs['method']
    selected = list(FIXED_IDS) if subjects is None else list(subjects)
    require(selected and len(set(selected)) == len(selected) and set(selected) <= set(FIXED_IDS), 'selected original identities')
    if subjects is not None:
        require(selected == [FIXED_IDS[0]], 'only fixed first-person primitive pilot subset')
    ph_cols, ph_rows = table(read_member(root, member(inputs, 'phenotype_metadata')), ',', allow_leading_unnamed=True)
    time_cols, time_rows = table(read_member(root, member(inputs, 'slice_timing_metadata')), ',')
    joins = method['source']['phenotype_join']
    timing = method['source']['site_timing_join']
    require(isinstance(joins, dict) and set(('id_column', 'site_column')) <= set(joins), 'frozen phenotype join needed')
    require(isinstance(timing, dict) and set(('site_column', 'tr_column', 'tr_units')) <= set(timing), 'frozen site timing join needed')
    require(joins['id_column'] in ph_cols and joins['site_column'] in ph_cols, 'source phenotype column membership')
    require(timing['site_column'] in time_cols and timing['tr_column'] in time_cols and timing['tr_units'] in ('sec', 'msec', 'usec'),
            'source timing column/unit membership')
    phenotype = {}
    for row in ph_rows:
        sid = original_id(row[joins['id_column']])
        require(sid not in phenotype, 'duplicate source phenotype ID')
        phenotype[sid] = row
    source_ids = read_member(root, member(inputs, 'cohort_ids')).decode('utf-8-sig').split()
    require(len(set(source_ids)) == len(source_ids) and set(FIXED_IDS) <= set(source_ids), 'exact source ID membership')
    timing_by_site = {}
    for row in time_rows:
        site = row[timing['site_column']]
        require(site and site not in timing_by_site, 'unique source timing site')
        timing_by_site[site] = float(row[timing['tr_column']])*{'sec': 1., 'msec': 1e-3, 'usec': 1e-6}[timing['tr_units']]
    atlas_row = member(inputs, 'atlas_image')
    atlas, atlas_affine, atlas_header = decode_image(read_member(root, atlas_row), atlas_row['path'].endswith('.gz'))
    require(atlas.ndim == 3 and atlas_header['spatial_units'] == 'mm', '3D hard-label atlas in mm required')
    labels = atlas_labels(read_member(root, member(inputs, 'atlas_labels')))
    persons, observed = {}, {}
    for sid in FIXED_IDS:
        if progress is not None: progress('source structure ' + sid)
        bold_row, conf_row = member(inputs, 'bold', sid), member(inputs, 'confounds', sid)
        raw_bytes = read_member(root, bold_row)
        _, affine, header, _ = image_header(raw_bytes, bold_row['path'].endswith('.gz'))
        require(len(header['shape']) == 4, '4D source BOLD required')
        require(header['spatial_units'] == 'mm', 'source BOLD spatial units mm required')
        n = header['shape'][-1]
        require(n == method['source']['n_frames_by_participant'][sid], 'frozen original frame count')
        require(header['temporal_units'] in ('sec', 'msec', 'usec'), 'known source temporal units')
        tr = float(header['zooms'][3])*{'sec': 1., 'msec': 1e-3, 'usec': 1e-6}[header['temporal_units']]
        require(math.isfinite(tr) and .1 < tr < 10 and .08 < .5/tr, 'valid source TR/Nyquist')
        require(math.isclose(tr, method['source']['tr_sec_by_participant'][sid], rel_tol=1e-9, abs_tol=1e-9), 'frozen source clock')
        require(sid in phenotype, 'exact phenotype join')
        site = phenotype[sid][joins['site_column']]
        require(site in timing_by_site, 'source site timing membership')
        documentary_tr = documentary_at_header_precision(timing_by_site[site], header['temporal_units'])
        require(math.isclose(tr, documentary_tr, rel_tol=1e-9, abs_tol=1e-9), 'source site/header TR agreement')
        columns, rows = table(read_member(root, conf_row), '\t')
        chosen = list(kernel.CONFOUND_COLUMNS)
        require(set(chosen) <= set(columns) and len(rows) == n, 'complete required13 nuisances and frames')
        c = np.array([[float(row[key]) for key in chosen] for row in rows], dtype=np.float64, order='C')
        require(np.isfinite(c).all(), 'finite complete selected nuisances')
        supports, digests = spatial_support(atlas, atlas_affine, header['shape'][:3], affine)
        observed[sid] = dict(bold_header=header, confound_columns=columns, selected_confound_columns=chosen,
            excluded_confound_columns=[x for x in columns if x not in chosen], n_confound_rows=n,
            frame_count=n, site=site, operational_TR_s=tr, frame_origin_s=0.,
            source_participant_token=phenotype[sid][joins['id_column']])
        if sid not in selected:
            continue
        if progress is not None: progress('source values and cleaning ' + sid)
        bold, decoded_affine, decoded_header = decode_image(raw_bytes, bold_row['path'].endswith('.gz'))
        require(decoded_header == header and np.array_equal(decoded_affine, affine), 'same-buffer header identity')
        raw = extract_means(bold, supports)
        geometry = np.array([len(a) > 0 for a in supports], dtype=bool)
        cleaned = kernel.clean_roi_signals(raw, c, tr, geometry)
        persons[sid] = dict(site=site, n_frames=n, tr_sec=tr,
            source_paths=dict(bold=bold_row['path'], confounds=conf_row['path']), raw=raw,
            geometry_present=geometry, n_voxels=np.array([len(a) for a in supports], dtype=np.int64),
            support_sha256=np.array(digests), **cleaned)
        if on_person is not None:
            on_person(sid, persons[sid])
        del bold
    return dict(pins=inputs['pins'], participant_ids=selected, roi_ids=np.arange(1, 49, dtype=np.int64),
        roi_labels=labels, persons=persons,
        source_files=[{key: row.get(key) for key in ('path', 'role', 'participant_id', 'size_bytes', 'sha256')}
                      for row in inputs['manifest']['files']],
        source_observed=dict(atlas_header=atlas_header, roi_labels=[dict(roi_id=i+1, roi_label=v) for i, v in enumerate(labels)],
            persons=observed, phenotype_columns=ph_cols, slice_timing_columns=time_cols))
