"""Source-only oracle reader: closed pinned bytes, no network/stager/grader import.

Method/schema pins were installed after the parent's structural review and
public freeze, before original functional values. No participant helper imports.
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
from nilearn.image import resample_img
import core

require = core.require
SOURCE_SHA = '465cfd8f113be362b39172782713c504432c51e529d82f222bda8ba9f1fb734e'
METHOD_SHA = 'a9d473e0192d723d023e16540040a6fde7dc9b3a0d878d5cef840e2c5f8cc40e'
SCHEMA_SHA = 'aa447d96db059f2bc824f5978dc48237c76474c5be8efa401b0ae05969093657'
PATH_ROLES = {
    'data/0010064/0010064_rest_tshift_RPI_voreg_mni.nii.gz': 'bold',
    'data/0010064/0010064_regressors.csv': 'confounds',
    'MSDL_rois/msdl_rois.nii': 'atlas_image',
    'MSDL_rois/msdl_rois_labels.csv': 'atlas_labels',
    'metadata/ADHD200_40subs_ID.txt': 'cohort_ids',
    'metadata/ADHD200_40subs_motion_parameters_and_phenotypics.csv': 'phenotype_metadata',
    'metadata/ADHD200_40subs_slice_timing_parameters.csv': 'slice_timing_metadata',
    'provenance/MSDL_README.txt': 'provenance',
    'provenance/nilearn_0_13_1_msdl_atlas.rst': 'provenance',
    'provenance/nilearn_0_13_1_adhd.rst': 'provenance',
}


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
    if sha is not None: require(hashlib.sha256(raw).hexdigest() == sha, 'source SHA256 mismatch')
    return raw


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def reject(_): raise core.PreconditionError('nonfinite JSON constant')
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=reject)
    def finite(v, depth=0):
        require(depth <= 64, 'JSON depth bound')
        if isinstance(v, float): require(math.isfinite(v), 'nonfinite JSON exponent')
        elif isinstance(v, dict):
            for item in v.values(): finite(item, depth + 1)
        elif isinstance(v, list):
            for item in v: finite(item, depth + 1)
    finite(value)
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
        require(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin), 'public pins not frozen')
    root = safe_path(data_dir)
    require(root.is_dir(), 'source directory required')
    method_raw = stable_bytes(method_path, 1024 ** 2, METHOD_SHA)
    schema_raw = stable_bytes(schema_path, 1024 ** 2, SCHEMA_SHA)
    method, schema = strict_json(method_raw), strict_json(schema_raw)
    require(method['task_id'] == 'RESTCONN-001', 'fixed task')
    require(method['source']['participant_id'] == core.PARTICIPANT, 'fixed participant')
    require(method['source']['map_ids'] == list(range(39)) and
            method['source']['target_labels'] == list(core.TARGETS), 'fixed map/target axes')
    require(type(method['source']['n_frames']) is int and 33 < method['source']['n_frames'] <= 10000,
            'frozen complete frame count')
    require(method['contract_status'].startswith('frozen'), 'public method not frozen')
    raw = stable_bytes(root / 'source_manifest.json', 2 * 1024 ** 2, SOURCE_SHA)
    manifest = strict_json(raw)
    rows = manifest.get('files')
    require(isinstance(rows, list) and len(rows) == 10, 'ten source members')
    names = set()
    for row in rows:
        name = row.get('path')
        require(name in PATH_ROLES and name not in names and row.get('role') == PATH_ROLES[name],
                'fixed source path/role membership')
        require(row.get('participant_id') == (core.PARTICIPANT if row['role'] in ('bold', 'confounds') else None),
                'fixed source participant key')
        require(type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= 128 * 1024 ** 2,
                'bounded source size')
        require(isinstance(row.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'source digest')
        names.add(name)
    require(names == set(PATH_ROLES), 'complete source membership')
    expected_dirs = {str(p) for n in names for p in PurePosixPath(n).parents if str(p) != '.'}
    found_files, found_dirs = set(), set()
    for p in root.rglob('*'):
        mode = p.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'source link or special member')
        (found_dirs if stat.S_ISDIR(mode) else found_files).add(p.relative_to(root).as_posix())
    require(found_files == names | {'source_manifest.json'} and found_dirs == expected_dirs, 'closed source inventory')
    for row in rows: read_member(root, row)
    return dict(root=root, method=method, schema=schema, manifest=manifest,
        identity=dict(source_manifest_sha256=SOURCE_SHA, method_sha256=METHOD_SHA, output_schema_sha256=SCHEMA_SHA))


def member(inputs, role):
    rows = [r for r in inputs['manifest']['files'] if r['role'] == role]
    require(len(rows) == 1, 'unique role join')
    return rows[0]


def table(raw, delimiter):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=delimiter))
    require(rows and rows[0] and len(rows) <= 10001 and len(rows[0]) <= 256, 'bounded source table')
    require(all(rows[0]) and len(set(rows[0])) == len(rows[0]), 'unique nonempty table columns')
    require(all(len(r) == len(rows[0]) for r in rows[1:]), 'source table width')
    return rows[0], [dict(zip(rows[0], row)) for row in rows[1:]]


def literal(value):
    x = float(value)
    return x if math.isfinite(x) else 'NaN' if math.isnan(x) else '+Inf' if x > 0 else '-Inf'


def decode_image(raw, compressed):
    stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw)
    with stream:
        head = stream.read(352)
        require(len(head) == 352, 'NIfTI header size')
        h = nib.Nifti1Header(binaryblock=head[:348], check=False)
        require(int(h['sizeof_hdr']) == 348 and h['magic'].tobytes() == b'n+1\0', 'single-file NIfTI1 required')
        shape = tuple(map(int, h.get_data_shape()))
        dtype = h.get_data_dtype()
        require(len(shape) == 4 and all(v > 0 for v in shape) and dtype.kind in 'iuf', 'finite-dimensional real4D source')
        offset = float(h['vox_offset'])
        require(math.isfinite(offset) and offset >= 352 and offset.is_integer(), 'integral NIfTI payload offset')
        size = int(offset) + math.prod(shape) * dtype.itemsize
        require(size <= 1024 ** 3, 'decoded image size bound')
        logical = head + stream.read(size - 352 + 1)
        require(len(logical) == size, 'exact decoded NIfTI length/EOF')
    affine = np.asarray(h.get_best_affine(), dtype=np.float64)
    require(np.isfinite(affine).all() and np.linalg.det(affine[:3, :3]) != 0, 'finite nonsingular image affine')
    slope, inter = h.get_slope_inter()
    slope, inter = (1., 0.) if slope is None else (float(slope), float(inter))
    require(math.isfinite(slope) and math.isfinite(inter), 'finite effective calibration')
    image = nib.Nifti1Image.from_bytes(logical)
    values = np.asarray(image.get_fdata(dtype=np.float64), dtype=np.float64)
    require(values.shape == shape and np.isfinite(values).all(), 'finite scaled full image')
    spatial, temporal = h.get_xyzt_units()
    meta = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
        spatial_units=spatial, temporal_units=temporal, zooms=[literal(v) for v in h.get_zooms()],
        raw_toffset=literal(h['toffset']), raw_scl_slope=literal(h['scl_slope']),
        raw_scl_inter=literal(h['scl_inter']), effective_slope=slope, effective_intercept=inter)
    return values, affine, meta


def resample_maps(atlas, atlas_affine, shape, affine):
    if atlas.shape[:3] == tuple(shape) and np.array_equal(atlas_affine, affine):
        return atlas.copy()
    result = resample_img(nib.Nifti1Image(atlas, atlas_affine), target_affine=affine,
        target_shape=tuple(shape), interpolation='linear', clip=True, fill_value=0,
        force_resample=True, copy_header=True).get_fdata(dtype=np.float64)
    require(np.isfinite(result).all(), 'finite resampled atlas')
    return result


def load(inputs):
    root, method = inputs['root'], inputs['method']
    n = method['source']['n_frames']
    br, ar = member(inputs, 'bold'), member(inputs, 'atlas_image')
    # Every decoded image comes from a fresh hash-checked, stable single buffer.
    bold, affine, bh = decode_image(read_member(root, br), br['path'].endswith('.gz'))
    atlas, aa, ah = decode_image(read_member(root, ar), ar['path'].endswith('.gz'))
    require(bold.shape[-1] == n and atlas.shape[-1] == 39, 'frozen frame/map counts')
    columns, rows = table(read_member(root, member(inputs, 'confounds')), '\t')
    selected = [c for c in columns if c in core.CONFOUND_SET]
    require(set(selected) == core.CONFOUND_SET and len(selected) == 13 and len(rows) == n,
            'complete exact nuisance membership/frames')
    require(selected == method['temporal_cleaning']['confound_columns'], 'source-order nuisance axis')
    c = np.array([[float(row[key]) for key in selected] for row in rows], dtype=np.float64)
    require(np.isfinite(c).all(), 'finite nuisance columns without imputation')
    lh, lut = table(read_member(root, member(inputs, 'atlas_labels')), ',')
    require(set(('name', 'net name', 'x', 'y', 'z')) <= set(lh) and len(lut) == 39, 'original atlas label schema')
    labels = [row['name'].strip() for row in lut]
    require(all(labels) and len(set(labels)) == 39 and set(core.TARGETS) <= set(labels), 'literal unique target labels')
    targets = [labels.index(name) for name in core.TARGETS]
    require(targets == method['source']['target_map_ids'], 'frozen target map indices')
    ids = read_member(root, member(inputs, 'cohort_ids')).decode('utf-8-sig').split()
    require(len(ids) == len(set(ids)) and core.PARTICIPANT in ids, 'literal participant source membership')
    maps = resample_maps(atlas, aa, bold.shape[:3], affine)
    raw, rank, singular = core.extract_coefficients(maps, bold)
    cleaned = core.clean_coefficients(raw, c)
    observed = dict(bold_header=bh, atlas_header=ah, frame_count=n, confound_columns=columns,
        selected_confound_columns=selected, excluded_confound_columns=[x for x in columns if x not in selected],
        n_confound_rows=len(rows), map_labels=[dict(map_id=i, map_label=v) for i, v in enumerate(labels)],
        target_map_ids=targets, operational_TR_s=2., frame_origin_s=0.)
    diagnostics = dict(map_rank=rank, confound_rank=cleaned['confound_rank'], target_support=[
        dict(map_id=i, map_label=labels[i], raw_sample_sd=float(cleaned['raw_sample_sd'][i]),
             residual_centered_l2=float(cleaned['residual_centered_l2'][i]),
             activity_threshold=float(cleaned['activity_threshold'][i]), active=bool(cleaned['active'][i])) for i in targets])
    return dict(raw_coefficients=raw, map_labels=labels, target_map_ids=targets,
        cleaned_series=cleaned['cleaned'][:, targets], active=cleaned['active'][targets],
        source_observed=observed, analysis_observed=diagnostics,
        private={k: v for k, v in cleaned.items() if isinstance(v, np.ndarray)} |
                dict(map_singular_values=singular, source_confounds=c))
