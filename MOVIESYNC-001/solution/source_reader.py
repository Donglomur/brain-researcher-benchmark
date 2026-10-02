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
from nilearn.image import resample_img
import core

require = core.require


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
    root = safe_path(data_dir)
    method_raw = stable_bytes(contract_path, 1024 * 1024)
    schema_raw = stable_bytes(schema_path, 1024 * 1024)
    method, schema = strict_json(method_raw), strict_json(schema_raw)
    require(method['task_id'] == 'MOVIESYNC-001' and method['source']['participant_ids'] == list(core.IDS), 'fixed public task/cohort')
    require(method['contract_status'].startswith('frozen'), 'public method not frozen')
    source_pin = method['source']['source_manifest_sha256']
    require(isinstance(source_pin, str) and re.fullmatch(r'[0-9a-f]{64}', source_pin), 'frozen source manifest pin')
    manifest_raw = stable_bytes(root / 'source_manifest.json', 2 * 1024 * 1024, source_pin)
    manifest = strict_json(manifest_raw)
    require(isinstance(manifest.get('files'), list) and manifest['files'], 'manifest inventory')
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


def table(raw, delimiter):
    reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=delimiter)
    header = next(reader, None)
    require(header and all(header) and len(header) == len(set(header)), 'unique nonempty source table header')
    rows = []
    for values in reader:
        require(len(values) == len(header), 'source table width')
        rows.append(dict(zip(header, values)))
    return header, rows


def decode_image(raw, compressed):
    stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw)
    with stream:
        head = stream.read(352)
        require(len(head) == 352, 'NIfTI header length')
        header = nib.Nifti1Header.from_fileobj(io.BytesIO(head), check=True)
        shape = tuple(int(v) for v in header.get_data_shape())
        dtype = header.get_data_dtype()
        require(len(shape) == 4 and all(v > 0 for v in shape) and dtype.kind in 'iuf', 'real4D NIfTI')
        offset = float(header['vox_offset'])
        require(math.isfinite(offset) and offset >= 352 and offset.is_integer(), 'NIfTI payload offset')
        length = int(offset) + math.prod(shape) * dtype.itemsize
        require(length <= 1024**3, 'bounded decoded NIfTI')
        logical = head + stream.read(length - 352 + 1)
        require(len(logical) == length, 'exact NIfTI payload and EOF')
    affine = np.asarray(header.get_best_affine(), dtype=np.float64)
    require(np.isfinite(affine).all() and np.linalg.matrix_rank(affine) == 4, 'finite invertible affine')
    slope, inter = float(header['scl_slope']), float(header['scl_inter'])
    slope, inter = (1., 0.) if not math.isfinite(slope) or slope == 0 else (slope, inter)
    require(math.isfinite(inter), 'finite effective scaling')
    image = nib.Nifti1Image.from_bytes(logical)
    values = np.asarray(image.get_fdata(dtype=np.float64), dtype=np.float64)
    require(values.shape == shape and np.isfinite(values).all(), 'finite scaled original image')
    units = header.get_xyzt_units()
    raw_tr = float(header.get_zooms()[3])
    toffset = float(header['toffset'])
    meta = dict(shape=list(shape), affine=affine.tolist(), source_dtype=dtype.str,
                spatial_units=units[0], temporal_units=units[1],
                raw_TR=raw_tr if math.isfinite(raw_tr) else None,
                raw_toffset=toffset if math.isfinite(toffset) else None,
                effective_scaling_slope=slope, effective_scaling_intercept=inter)
    return values, affine, meta


def load_common(inputs):
    root = inputs['root']
    header, rows = table(read_member(root, member(inputs, 'participants')), '\t')
    require('participant_id' in header, 'participant source key')
    ids = [r['participant_id'] for r in rows]
    require(len(ids) == len(set(ids)) and set(core.IDS) <= set(ids), 'literal fixed cohort exists')
    original_rows = {pid: i for i, pid in enumerate(ids)}
    atlas_row = member(inputs, 'atlas_image')
    atlas, affine, atlas_header = decode_image(read_member(root, atlas_row), atlas_row['path'].endswith('.gz'))
    require(atlas.shape[-1] == 39, '39 original MSDL maps')
    lut_header, lut = table(read_member(root, member(inputs, 'atlas_labels')), ',')
    require('name' in lut_header and len(lut) == 39, 'MSDL labels count/name column')
    labels = [r['name'].strip() for r in lut]
    require(all(labels) and all(labels.count(name) == 1 for name in core.VISUAL), 'three unique visual names')
    visual_ids = [labels.index(name) for name in core.VISUAL]
    return dict(participant_header=header, participant_source_rows=original_rows,
                atlas=atlas, atlas_affine=affine, atlas_header=atlas_header,
                map_labels=labels, visual_ids=visual_ids)


def load_person(inputs, common, participant):
    root = inputs['root']
    br, cr = member(inputs, 'bold', participant), member(inputs, 'confounds', participant)
    bold, affine, header = decode_image(read_member(root, br), br['path'].endswith('.gz'))
    require(bold.shape[-1] == core.N_FRAMES, '168 released frames')
    columns, rows = table(read_member(root, cr), '\t')
    require(set(core.CONFOUNDS) <= set(columns) and len(rows) == core.N_FRAMES, '15 confounds and168 rows')
    values = np.empty((core.N_FRAMES, len(core.CONFOUNDS)), dtype=np.float64)
    for i, row in enumerate(rows):
        for j, name in enumerate(core.CONFOUNDS):
            try:
                values[i, j] = float(row[name])
            except (ValueError, TypeError) as exc:
                raise core.PreconditionError('finite selected confound required') from exc
    require(np.isfinite(values).all(), 'finite selected confounds without imputation')
    maps_image = nib.Nifti1Image(common['atlas'], common['atlas_affine'])
    maps = resample_img(maps_image, target_affine=affine, target_shape=bold.shape[:3],
                        interpolation='linear', clip=True, fill_value=0, force_resample=True,
                        copy_header=True).get_fdata(dtype=np.float64)
    require(np.isfinite(maps).all(), 'finite resampled maps')
    coefficients, rank, singular = core.extract_coefficients(maps, bold)
    cleaned, nuisance_rank, private = core.clean_coefficients(coefficients, values)
    cohort = dict(participant_id=participant, participant_source_row=common['participant_source_rows'][participant],
                  bold_path=br['path'], confounds_path=cr['path'], n_frames=core.N_FRAMES,
                  n_confound_rows=len(rows), n_maps=39, map_rank=rank, nuisance_rank=nuisance_rank,
                  n_active_visual=0, status='ok')
    private.update(map_singular_values=singular, original_confounds=values, cleaned_coefficients=cleaned)
    header['participant_id'] = participant
    return dict(cohort=cohort, header=header, confound_columns=columns, raw_coefficients=coefficients,
                isc_inputs=cleaned[:, common['visual_ids']], private=private)
