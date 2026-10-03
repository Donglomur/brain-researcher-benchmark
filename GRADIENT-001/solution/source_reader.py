"""Oracle-only original-byte reader. No network, grader, cache or stage-helper import."""
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
from scipy import linalg, ndimage
import core

require = core.require
METHOD_SHA256 = 'c6575d9cc8a9f8d422dc3ec88c2a7aefa6ca971757180517948d2466fefce872'
SCHEMA_SHA256 = 'e9ceb1a15180ed086290c4c7f5eb079038302b4dd5feabc3e99c9acb688bcf16'


def safe_path(value):
    text = os.fspath(value)
    require(text.startswith('/') and '\0' not in text and
            all(s not in ('.', '..') for s in text.split('/')), 'absolute lexical path required')
    path = Path(text)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            require(not part.is_symlink(), 'symlink path refused')
            require(part == path or part.is_dir(), 'non-directory ancestor')
    return path


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def stable_bytes(path, limit, sha256=None):
    path = safe_path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, 'bounded regular source')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        require(signature(os.fstat(handle.fileno())) == signature(before), 'source replaced before read')
        raw = handle.read(limit + 1)
        require(len(raw) == before.st_size and signature(os.fstat(handle.fileno())) == signature(before), 'source changed during read')
    require(signature(path.lstat()) == signature(before), 'source replaced after read')
    if sha256 is not None:
        require(hashlib.sha256(raw).hexdigest() == sha256, 'source SHA256 mismatch')
    return raw


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad(_):
        raise core.PreconditionError('nonfinite JSON constant')
    obj = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=bad)
    def visit(x):
        if isinstance(x, float):
            require(math.isfinite(x), 'nonfinite JSON exponent')
        elif isinstance(x, dict):
            for v in x.values(): visit(v)
        elif isinstance(x, list):
            for v in x: visit(v)
    visit(obj)
    return obj


def read_member(root, row):
    raw = stable_bytes(root / row['path'], row['size_bytes'], row['sha256'])
    require(len(raw) == row['size_bytes'], 'source size mismatch')
    if row.get('md5') is not None:
        require(hashlib.md5(raw).hexdigest() == row['md5'], 'source MD5 mismatch')
    if row.get('git_blob_sha1') is not None:
        git = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        require(git == row['git_blob_sha1'], 'source Git-content mismatch')
    return raw


def authenticate(data_dir, contract_path, schema_path):
    require(all(isinstance(pin, str) and re.fullmatch(r'[0-9a-f]{64}', pin)
                for pin in (METHOD_SHA256, SCHEMA_SHA256)), 'unfrozen public document pin')
    root = safe_path(data_dir)
    method_raw = stable_bytes(contract_path, 1024 * 1024, METHOD_SHA256)
    schema_raw = stable_bytes(schema_path, 1024 * 1024, SCHEMA_SHA256)
    method, schema = strict_json(method_raw), strict_json(schema_raw)
    require(method['task_id'] == 'GRADIENT-001' and isinstance(method['source']['participant_ids'], list), 'fixed public task/cohort')
    require(method['contract_status'].startswith('frozen'), 'public method not frozen')
    ids = method['source']['participant_ids']
    require(len(ids) == 20 and len(set(ids)) == 20 and set(ids) == set(method['source']['candidate_membership']), 'fixed20 cohort')
    source_pin = method['source']['manifest_sha256']
    require(isinstance(source_pin, str) and re.fullmatch(r'[0-9a-f]{64}', source_pin), 'frozen source manifest pin')
    manifest_raw = stable_bytes(root / 'source_manifest.json', 2 * 1024 * 1024, source_pin)
    manifest = strict_json(manifest_raw)
    require(isinstance(manifest.get('files'), list) and manifest['files'], 'manifest inventory')
    require(manifest.get('task_id') == 'GRADIENT-001' and len(manifest['files']) == 46,
            'exact46 task source/provenance members')
    require(manifest.get('cohort', {}).get('ordered_participant_ids') == ids, 'frozen loader order agreement')
    scientific = [r for r in manifest['files'] if r.get('role') != 'provenance']
    expected = {(role, pid) for pid in ids for role in ('bold', 'confounds')}
    expected.update((role, None) for role in ('participants', 'atlas_image', 'atlas_labels'))
    require(len(scientific) == 43 and {(r.get('role'), r.get('participant_id')) for r in scientific} == expected,
            'exact43 original role/participant inventory')
    require(all(r.get('participant_id') is None for r in manifest['files'] if r.get('role') == 'provenance'),
            'provenance does not impersonate a participant')
    paths = set()
    directories = set()
    for row in manifest['files']:
        name = row['path']
        require(isinstance(name, str) and '\\' not in name and '\0' not in name, 'source path text')
        rel = PurePosixPath(name)
        require(not rel.is_absolute() and all(v not in ('', '.', '..') for v in name.split('/')),
                'safe relative source path')
        require(name not in paths and name != 'source_manifest.json', 'duplicate source path')
        require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= 1024**3, 'bounded source size')
        require(isinstance(row['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', row['sha256']), 'source digest')
        paths.add(name)
        directories.update(str(p) for p in rel.parents if str(p) != '.')
    seen_files, seen_dirs = set(), set()
    for path in root.rglob('*'):
        info = path.lstat()
        name = str(path.relative_to(root))
        require(not stat.S_ISLNK(info.st_mode), 'linked source member')
        if stat.S_ISDIR(info.st_mode):
            seen_dirs.add(name)
        else:
            require(stat.S_ISREG(info.st_mode), 'special source member')
            seen_files.add(name)
    require(seen_files == paths | {'source_manifest.json'} and seen_dirs == directories, 'closed source inventory')
    for row in manifest['files']:
        read_member(root, row)
    identity = dict(method_sha256=hashlib.sha256(method_raw).hexdigest(),
                    output_schema_sha256=hashlib.sha256(schema_raw).hexdigest(),
                    source_manifest_sha256=source_pin)
    return dict(root=root, method=method, schema=schema, manifest=manifest, identity=identity)


def member(inputs, role, participant=None):
    found = [r for r in inputs['manifest']['files'] if r['role'] == role and r.get('participant_id') == participant]
    require(len(found) == 1, 'unique source role/participant join')
    return found[0]


def reauthenticate(inputs, contract_path, schema_path):
    """Recheck the same closed original inventory and documents after consumption.

    This adds no numerical processing: read_member still authenticates each
    immutable buffer before parsing, and decode/calibration are unchanged.
    """
    current = authenticate(inputs['root'], contract_path, schema_path)
    require(current['identity'] == inputs['identity'] and current['manifest'] == inputs['manifest'],
            'source or public documents changed through consumption')


def table(raw, delimiter):
    reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=delimiter)
    header = next(reader, None)
    require(header and all(header) and len(header) == len(set(header)), 'unique nonempty source table header')
    rows = []
    for values in reader:
        require(len(values) == len(header), 'source table width')
        rows.append(dict(zip(header, values)))
    return header, rows



def decode_image(raw, compressed, ndim):
    require(type(raw) is bytes and 0 < len(raw) <= 1024**3, 'bounded immutable NIfTI bytes')
    require(type(compressed) is bool and type(ndim) is int and ndim in (3, 4), 'image decoding mode')
    stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw)
    with stream:
        head = stream.read(352)
        require(len(head) == 352, 'NIfTI header length')
        header = nib.Nifti1Header(binaryblock=head[:348], check=True)
        require(bytes(header['magic']).rstrip(b'\0') == b'n+1', 'single-file NIfTI1 required')
        shape = tuple(int(v) for v in header.get_data_shape())
        dtype = header.get_data_dtype()
        require(len(shape) == ndim and all(v > 0 for v in shape) and dtype.kind in 'iuf', 'real source NIfTI')
        offset = float(header['vox_offset'])
        require(math.isfinite(offset) and offset >= 352 and offset.is_integer(), 'NIfTI payload offset')
        length = int(offset) + math.prod(shape) * dtype.itemsize
        require(length <= 1024**3, 'bounded decoded NIfTI')
        logical = head + stream.read(length - 352 + 1)
        require(len(logical) == length, 'exact NIfTI payload and EOF')
    affine = np.asarray(header.get_best_affine(), dtype=np.float64)
    require(np.isfinite(affine).all() and np.linalg.matrix_rank(affine) == 4, 'finite invertible affine')
    slope, intercept = float(header['scl_slope']), float(header['scl_inter'])
    slope, intercept = (1., 0.) if not math.isfinite(slope) or slope == 0 else (slope, intercept)
    require(math.isfinite(intercept), 'finite effective scaling')
    image = nib.Nifti1Image.from_bytes(logical)
    values = np.asarray(image.get_fdata(dtype=np.float64), dtype=np.float64)
    require(values.shape == shape and np.isfinite(values).all(), 'finite calibrated source image')
    units = header.get_xyzt_units()
    zooms = [float(v) for v in header.get_zooms()]
    toffset = float(header['toffset'])
    metadata = dict(shape=list(shape), affine=affine.tolist(), source_dtype=dtype.str,
                    spatial_units=units[0], temporal_units=units[1], zooms=zooms,
                    raw_TR=zooms[3] if ndim == 4 else None,
                    raw_toffset=toffset if math.isfinite(toffset) else None,
                    effective_scaling_slope=slope, effective_scaling_intercept=intercept)
    return values, affine, metadata


def parse_lut(raw):
    labels = []
    for line in raw.decode('utf-8-sig').splitlines():
        if not line.strip():
            continue
        fields = line.split()
        require(len(fields) == 6 and fields[0].isdigit(), 'Schaefer original six-field LUT')
        parcel = int(fields[0])
        name = fields[1]
        tokens = name.split('_')
        require(len(tokens) >= 4 and tokens[0] == '7Networks' and tokens[1] in ('LH', 'RH')
                and tokens[2] in core.NETWORKS, 'Schaefer literal network mapping')
        require(all(v.isdigit() and 0 <= int(v) <= 255 for v in fields[2:]), 'LUT colour fields')
        labels.append(dict(parcel_id=parcel, label=name, network=tokens[2], hemisphere=tokens[1],
                           original_fields=fields))
    require(len(labels) == 400 and {r['parcel_id'] for r in labels} == set(range(1, 401)), 'complete unique400 LUT')
    return sorted(labels, key=lambda row: row['parcel_id'])


def load_common(inputs):
    root = inputs['root']
    ids = inputs['method']['source']['participant_ids']
    columns, rows = table(read_member(root, member(inputs, 'participants')), '\t')
    require({'participant_id', 'Age', 'Child_Adult'} <= set(columns), 'source phenotype fields')
    keys = [r['participant_id'] for r in rows]
    require(len(keys) == len(set(keys)) and set(ids) <= set(keys), 'literal fixed cohort exists')
    selected = {}
    for position, pid in enumerate(ids):
        i = keys.index(pid)
        age = float(rows[i]['Age'])
        require(math.isfinite(age) and rows[i]['Child_Adult'] in ('child', 'adult'), 'finite cohort age and group')
        selected[pid] = dict(participant_id=pid, source_position=position, phenotype_row_index=i,
                             age=age, child_adult=rows[i]['Child_Adult'], first_half=position < 10,
                             second_half=position >= 10)
    atlas_row = member(inputs, 'atlas_image')
    atlas, affine, atlas_header = decode_image(read_member(root, atlas_row), atlas_row['path'].endswith('.gz'), 3)
    require(np.array_equal(atlas, np.rint(atlas)) and np.all((atlas >= 0) & (atlas <= 400)), 'original atlas label domain')
    labels = parse_lut(read_member(root, member(inputs, 'atlas_labels')))
    return dict(participant_columns=columns, cohort=selected, atlas=atlas.astype(np.int32),
                atlas_affine=affine, atlas_header=atlas_header, labels=labels)


def support(atlas, atlas_affine, bold_shape, bold_affine):
    if tuple(atlas.shape) == tuple(bold_shape) and np.array_equal(atlas_affine, bold_affine):
        transferred = atlas
    else:
        transform = linalg.inv(atlas_affine) @ bold_affine
        transferred = ndimage.affine_transform(atlas, transform[:3, :3], offset=transform[:3, 3],
                    output_shape=tuple(bold_shape), order=0, mode='constant', cval=0, prefilter=False)
    require(np.array_equal(transferred, np.rint(transferred)) and
            np.all((transferred >= 0) & (transferred <= 400)), 'transferred source label domain')
    flat = transferred.ravel(order='C')
    return [np.flatnonzero(flat == parcel).astype(np.int64) for parcel in range(1, 401)]


def load_person(inputs, common, participant):
    root = inputs['root']
    br, cr = member(inputs, 'bold', participant), member(inputs, 'confounds', participant)
    bold, affine, header = decode_image(read_member(root, br), br['path'].endswith('.gz'), 4)
    require(bold.shape[-1] == core.N_FRAMES, '168 original frames')
    columns, rows = table(read_member(root, cr), '\t')
    require(set(core.CONFOUNDS) <= set(columns) and len(rows) == core.N_FRAMES, '15 confounds/168 rows')
    confounds = np.empty((core.N_FRAMES, len(core.CONFOUNDS)), dtype=np.float64)
    for i, row in enumerate(rows):
        for j, name in enumerate(core.CONFOUNDS):
            try:
                confounds[i, j] = float(row[name])
            except (TypeError, ValueError) as exc:
                raise core.PreconditionError('finite selected original confound required') from exc
    require(np.isfinite(confounds).all(), 'no selected confound imputation')
    indices = support(common['atlas'], common['atlas_affine'], bold.shape[:3], affine)
    raw = np.full((core.N_FRAMES, core.N_PARCELS), np.nan)
    for t in range(core.N_FRAMES):
        volume = bold[..., t].ravel(order='C')
        for r, idx in enumerate(indices):
            if len(idx):
                raw[t, r] = np.mean(np.ascontiguousarray(volume[idx], dtype=np.float64), dtype=np.float64)
    geometry = np.array([len(idx) > 0 for idx in indices], dtype=bool)
    processed = core.preprocess(raw, confounds, geometry)
    parcel_rows = []
    support_meta = []
    for label, idx in zip(common['labels'], indices):
        digest = hashlib.sha256(np.asarray(idx, dtype='<i8').tobytes()).hexdigest()
        row = dict(participant_id=participant, parcel_id=label['parcel_id'], label=label['label'],
                   network=label['network'], n_voxels=len(idx), support_sha256=digest,
                   geometry_status='ok' if len(idx) else 'empty_geometry')
        parcel_rows.append(row)
        support_meta.append(dict(parcel_id=label['parcel_id'], n_voxels=len(idx), support_sha256=digest))
    cohort = dict(common['cohort'][participant], bold_path=br['path'], confounds_path=cr['path'],
                  n_frames=core.N_FRAMES)
    return dict(cohort=cohort, header=header, confound_columns=columns, parcel_rows=parcel_rows,
                support_metadata=support_meta, support_indices=indices, raw_means=raw,
                geometry_valid=geometry, original_confounds=confounds, **processed)
