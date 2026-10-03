"""Private DEVCONN source reconstruction; no downloads or endpoint analysis.

All source bytes are authenticated before parsing and immutable buffers are the
only numerical inputs. Generic header/table parsing is shared, disclosed code;
array decoding, extraction and cleaning are not imported from the oracle.
Production document pins deliberately fail closed until parent freeze. Import
does not load source/code documents, discover data, or compute any statistics.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import types
import zlib

SOURCE_SHA = '0fb419ee0dbea59376f5b0dc1e91d26502e8203d6e7b02334b979e6a1d9f66e3'
METHOD_SHA = 'e8ba3df50c7cc4bf8b83e2db559c0f1e515f10bf4c45498da84076306e883f6e'
SCHEMA_SHA = '3463740e8c55a9f549590fee013aa29d30480eb63e9984acafd2a41c1a1531b4'
REPORTING_SHA = '2b3abe5fe37d3ad68db57301afa68cf6b0f5409abaf81bc5b06494ae4bf88638'
MODULE_PINS = {
    'inspect_structure.py': 'b0474f9de46a4a76e9307928f0a7f1999f7e51c23c1b3dd3657860a9374f9a15',
    'source_numerics.py': 'cc39d43bfa3308433a71a0cdd5457d896625d33882c68bb6dfba0d44d4a19673',
    'reporting_kernel.py': REPORTING_SHA,
    'coordinate_contract.py': '40991bfa9e2d78e14163b58a1f5f6ed30b9d14be6143c2671b5b87e5be8fc00e',
}
IDS = tuple(f'sub-pixar{i:03d}' for i in range(1, 156))
VERSIONS = {'numpy': '2.1.3', 'scipy': '1.14.1', 'nibabel': '5.3.2',
            'nilearn': '0.12.1', 'scikit-learn': '1.5.2', 'pandas': '2.2.3'}
HEADER_FIELDS = ('shape', 'selected_affine', 'storage_dtype', 'spatial_units',
                 'temporal_units', 'zooms', 'raw_toffset', 'raw_scl_slope',
                 'raw_scl_inter', 'effective_slope', 'effective_intercept')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def signature(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def exact_read(value, digest, cap):
    """Small pinned code/document read before trusting imported helpers."""
    raw = os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw
         and not any(p in ('.', '..') for p in raw.split('/')), 'safe_absolute_path')
    path = Path(raw)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_input')
            if part != path:
                need(stat.S_ISDIR(mode), 'input_ancestor')
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'unfrozen_pin')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'input_size_or_type')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'input_changed')
        payload = stream.read(cap + 1)
        need(signature(os.fstat(stream.fileno())) == signature(before), 'input_changed')
    need(signature(path.lstat()) == signature(before), 'input_path_changed')
    need(len(payload) == before.st_size and hashlib.sha256(payload).hexdigest() == digest, 'input_hash')
    return payload


@dataclass(frozen=True)
class Policy:
    source_sha: str | None
    method_sha: str | None
    schema_sha: str | None
    reporting_sha: str | None
    module_pins: dict
    versions: dict
    subject_ids: tuple = IDS
    expected_rois: int = 264
    max_decoded_bytes: int = 512 * 1024**2
    wall_seconds: int = 1800


def production_policy():
    return Policy(SOURCE_SHA, METHOD_SHA, SCHEMA_SHA, REPORTING_SHA,
                  dict(MODULE_PINS), dict(VERSIONS))


def load_modules(policy):
    need(set(policy.module_pins) == set(MODULE_PINS), 'module_closure')
    need(policy.module_pins['reporting_kernel.py'] == policy.reporting_sha, 'reporting_pin')
    directory = Path(__file__).absolute().parent
    # Authenticate the complete closure before the first compile/import.
    payloads = {name: exact_read(directory / name, pin, 1024**2)
                for name, pin in policy.module_pins.items()}
    modules = {}
    for filename, payload in payloads.items():
        key = '_devconn_private_' + filename[:-3]
        module = types.ModuleType(key)
        module.__file__ = str(directory / filename)
        sys.modules[key] = module  # dataclass resolves its defining module.
        try:
            exec(compile(payload, module.__file__, 'exec'), module.__dict__)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        modules[filename[:-3]] = module
    return modules


def header(raw, ndim, helper, policy, check):
    """Decode only bounded logical NIfTI header/extensions from immutable gzip."""
    from nibabel import Nifti1Header
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    prefix = bytearray()
    cursor = 0

    def fill(target):
        nonlocal cursor
        while len(prefix) < target:
            check()
            if decoder.unconsumed_tail:
                chunk = decoder.unconsumed_tail
            else:
                need(cursor < min(len(raw), policy.max_header_bytes), 'header_compressed_cap')
                chunk = raw[cursor:min(cursor + 1024, len(raw), policy.max_header_bytes)]
                cursor += len(chunk)
            out = decoder.decompress(chunk, target - len(prefix))
            prefix.extend(out)
            need(out or not decoder.eof, 'header_truncated')

    fill(352)
    h = Nifti1Header(binaryblock=bytes(prefix[:348]), check=False)
    shape = tuple(int(v) for v in h.get_data_shape())
    dtype = h.get_data_dtype()
    need(int(h['sizeof_hdr']) == 348 and h['magic'].tobytes() == b'n+1\0', 'single_file_nifti1')
    need(len(shape) == ndim and all(v > 0 for v in shape), 'source_image_dimensions')
    need(dtype.kind in 'iuf' and dtype.itemsize <= 8 and int(h['bitpix']) == dtype.itemsize * 8,
         'source_image_dtype')
    offset = float(h['vox_offset'])
    need(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= policy.max_header_bytes,
         'header_offset')
    offset = int(offset)
    fill(offset)
    position = 352
    if prefix[348]:
        while position < offset:
            need(position + 8 <= offset, 'extension_header')
            length, unused_code = struct.unpack(h.endianness + 'ii', prefix[position:position + 8])
            need(length >= 16 and length % 16 == 0 and position + length <= offset, 'extension_length')
            position += length
    else:
        need(not any(prefix[352:]), 'unflagged_extension')
    affine = h.get_best_affine()
    import numpy as np
    need(np.isfinite(affine).all() and np.array_equal(affine[3], [0., 0., 0., 1.])
         and math.isfinite(float(np.linalg.det(affine[:3, :3])))
         and np.linalg.det(affine[:3, :3]) != 0, 'source_affine')
    slope, intercept = h.get_slope_inter()
    units = h.get_xyzt_units()
    result = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
                  spatial_units=units[0], temporal_units=units[1],
                  zooms=[helper.literal(v) for v in h.get_zooms()],
                  raw_toffset=helper.literal(h['toffset']), raw_scl_slope=helper.literal(h['scl_slope']),
                  raw_scl_inter=helper.literal(h['scl_inter']),
                  effective_slope=1. if slope is None else float(slope),
                  effective_intercept=0. if intercept is None else float(intercept))
    need(all(type(v) is float and math.isfinite(v) and v > 0 for v in result['zooms']), 'source_zooms')
    return result, offset, dtype


def decode_values(raw, observed_header, offset, dtype, policy, check):
    """Bounded strict gzip EOF and direct NIfTI Fortran storage decoding."""
    import numpy as np
    shape = tuple(observed_header['shape'])
    expected = offset + math.prod(shape) * dtype.itemsize
    need(expected <= policy.max_decoded_bytes, 'decoded_image_cap')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = bytearray()
    cursor = 0
    while not decoder.eof:
        check()
        if decoder.unconsumed_tail:
            chunk = decoder.unconsumed_tail
        else:
            need(cursor < len(raw), 'gzip_truncated')
            chunk = raw[cursor:cursor + 65536]
            cursor += len(chunk)
        output.extend(decoder.decompress(chunk, min(1024**2, expected + 1 - len(output))))
        need(len(output) <= expected, 'decoded_image_overrun')
    need(not decoder.unused_data and not decoder.unconsumed_tail and cursor == len(raw), 'gzip_trailing_bytes')
    need(len(output) == expected, 'decoded_image_length')
    values = np.frombuffer(output, dtype=dtype, count=math.prod(shape), offset=offset).reshape(shape, order='F')
    values = np.array(values, dtype=np.float64, order='C', copy=True)
    # Explicit two float64 operations match the declared calibrated arithmetic.
    values *= observed_header['effective_slope']
    values += observed_header['effective_intercept']
    return values


def confounds(raw, helper, policy, names, missing_policy, frames):
    """Fourteen regressors and separately consumed FD; original order retained."""
    import numpy as np
    columns, rows = helper.table(raw, policy)
    required = [*names, 'framewise_displacement']
    need(len(rows) == frames and set(required) <= set(columns), 'confound_frame_or_columns')
    need(missing_policy.get('missing_tokens') == ['', 'n/a']
         and type(missing_policy.get('fill_value')) in (int, float)
         and missing_policy['fill_value'] == 0., 'missing_policy')
    values = np.empty((frames, len(names)), dtype=np.float64)
    missing, fd_missing, fd_values = [], [], []
    for j, name in enumerate(required):
        index = columns.index(name)
        for i, row in enumerate(rows):
            token = row[index]
            absent = token in ('', 'n/a')
            if absent:
                value = 0.
                entry = dict(frame_index=i, column_name=name, original_token=token, applied_value=0.)
                (missing if j < len(names) else fd_missing).append(entry)
            else:
                try:
                    value = float(token)
                except ValueError as exc:
                    raise ValueError('invalid_confound_token') from exc
                need(math.isfinite(value), 'nonfinite_confound')
            if j < len(names):
                values[i, j] = value
            elif not absent:
                fd_values.append(value)
    fd_sum = math.fsum(fd_values)
    need(math.isfinite(fd_sum), 'fd_sum_nonfinite')
    return dict(values=values, columns=columns, excluded=[v for v in columns if v not in names],
                missing=missing, fd_sum=fd_sum, fd_count=len(fd_values),
                fd_missing=fd_missing, mean_fd=fd_sum / frames)


def validate_method(method, schema, policy):
    need(method.get('task_id') == schema.get('task_id') == 'DEVCONN-001', 'document_task')
    need(method['source']['source_manifest_sha256'] == policy.source_sha, 'method_source_pin')
    need(schema.get('source_manifest_sha256') == policy.source_sha
         and schema.get('method_sha256') == policy.method_sha
         and schema.get('reporting_kernel_sha256') == policy.reporting_sha
         and method.get('reporting_kernel_sha256') == policy.reporting_sha, 'schema_pins')
    frames = method['source']['frame_counts_by_subject']
    need(type(frames) is dict and set(frames) == set(policy.subject_ids)
         and all(type(v) is int and v >= 2 for v in frames.values()), 'frame_counts_unfrozen')
    need(method['source']['n_subjects'] == len(policy.subject_ids)
         and method['source']['total_frames'] == sum(frames.values()), 'method_cohort')
    need(method['activity']['relative_threshold'] == 1e-12, 'activity_method')
    unit = method['source']['spatial_unit_policy']
    need(unit['world_coordinate_unit'] == 'mm'
         and type(unit['allowed_bold_header_units']) is list
         and unit['allowed_bold_header_units']
         and set(unit['allowed_bold_header_units']) <= {'mm', 'unknown'}, 'spatial_policy_unfrozen')
    geometry = method['roi_geometry']
    need(type(geometry['n_rois']) is int and geometry['n_rois'] == policy.expected_rois
         and geometry['radius_mm'] == 5., 'geometry_method')
    need(geometry['source_columns'] == ['ROI', 'X', 'Y', 'Z'], 'coordinate_columns_unfrozen')
    need(type(geometry['coordinates_sha256']) is str
         and re.fullmatch('[0-9a-f]{64}', geometry['coordinates_sha256']), 'coordinate_pin_unfrozen')
    missing = method['confounds']['missingness']
    need(missing.get('missing_tokens') == ['', 'n/a'] and type(missing.get('fill_value')) in (int, float)
         and missing['fill_value'] == 0., 'missing_policy')
    return frames, unit


def reconstruct(data_dir='/app/data/devconn', manifest_path='/app/source_manifest.json',
                method_path='/app/method_contract.json', schema_path='/app/output_schema.json',
                *, pilot=False, geometry_only=False, _policy=None):
    """Always authenticate all members and all person metadata.

    Geometry mode decodes no BOLD values. Pilot decodes only the first literal
    participant; full mode decodes all. No correlations, ranks or bootstrap.
    _policy is an explicit manufactured-fixture dependency, never a CLI option.
    """
    need(type(pilot) is bool and type(geometry_only) is bool and not (pilot and geometry_only),
         'exclusive_boolean_modes')
    policy = production_policy() if _policy is None else _policy
    need(all(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin) for pin in
             (policy.source_sha, policy.method_sha, policy.schema_sha, policy.reporting_sha)), 'unfrozen_pin')
    need(type(policy.expected_rois) is int and policy.expected_rois >= 2, 'roi_count')
    modules = load_modules(policy)
    h, n, kernel, coordinate = (modules[key] for key in
        ('inspect_structure', 'source_numerics', 'reporting_kernel', 'coordinate_contract'))
    import numpy as np
    started = time.monotonic()

    def check():
        need(time.monotonic() - started < policy.wall_seconds, 'source_deadline')

    method_raw = exact_read(method_path, policy.method_sha, 4 * 1024**2)
    schema_raw = exact_read(schema_path, policy.schema_sha, 4 * 1024**2)
    method, schema = h.strict_json(method_raw), h.strict_json(schema_raw)
    frames, unit_policy = validate_method(method, schema, policy)
    source, manifest_path = h.safe_path(data_dir), h.safe_path(manifest_path)
    auth = h.Policy(policy.source_sha, policy.versions, participant_ids=policy.subject_ids)
    manifest, rows, originals, opaque, versions = h.frozen_manifest(source, manifest_path, auth)
    need(manifest['n_files'] == method['source']['n_files']
         and manifest['total_bytes'] == method['source']['total_bytes'], 'method_inventory')
    h.closed_inventory(source, rows, check)
    buffers, signatures = {}, {}
    for path, row in rows.items():
        buffers[path], signatures[path] = h.authenticated_bytes(source / path, row, check, retain=True)
    # No scientific header, table, or coordinate parsed before complete authentication.
    keyed = {(row['role'], row.get('participant_id')): path for path, row in rows.items()
             if row['role'] in ('bold', 'confounds', 'participants', 'coordinates')}
    need(sum(row['role'] == 'coordinates' for row in rows.values()) == 1, 'one_coordinates')
    coord_path = keyed['coordinates', None]
    coord_row = rows[coord_path]
    need(coord_path == method['roi_geometry']['coordinates_path']
         and coord_row['sha256'] == method['roi_geometry']['coordinates_sha256'], 'method_coordinates')
    parsed = coordinate.parse_power(buffers[coord_path], expected_rois=policy.expected_rois)
    roi_ids, coordinates = parsed['roi_ids'], parsed['coordinates']
    bin_record = coordinate.bin_record(kernel.distance_bins(coordinates, roi_ids))
    phenotype = h.phenotype(buffers[keyed['participants', None]], auth)
    need(all(row['age_kind'] == 'finite' and row['group_known'] for row in phenotype['selected']),
         'phenotype_values')
    need(phenotype['group_token_counts'] == method['source']['expected_group_counts'], 'group_counts')
    demographics = {row['participant_id']: row for row in phenotype['selected']}
    names = method['confounds']['columns']
    need(tuple(names) == h.NUISANCE == n.CONF_COLS, 'confound_names')
    selected = () if geometry_only else policy.subject_ids[:1] if pilot else policy.subject_ids
    persons, covariates, cohort, source_people, analysis_people = {}, {}, [], [], []
    geometry, prepared = {}, {}
    # Validate every header/table/geometry before consuming any selected BOLD values.
    for sid in policy.subject_ids:
        check()
        bold_path, conf_path = keyed['bold', sid], keyed['confounds', sid]
        observed, offset, dtype = header(buffers[bold_path], 4, h, auth, check)
        need(observed['shape'][3] == frames[sid], 'source_frame_count')
        need(observed['spatial_units'] in unit_policy['allowed_bold_header_units'], 'bold_units')
        c = confounds(buffers[conf_path], h, auth, names, method['confounds']['missingness'], frames[sid])
        cov = dict(age=demographics[sid]['age'], group=demographics[sid]['group_token'], mean_fd=c['mean_fd'])
        covariates[sid] = cov
        fd_indices = [entry['frame_index'] for entry in c['fd_missing']]
        cohort.append(dict(subject_id=sid, **cov, mean_fd_observed_count=c['fd_count'],
                           mean_fd_missing_frame_indices=fd_indices))
        shape = tuple(observed['shape'][:3])
        affine = np.asarray(observed['selected_affine'], dtype=np.float64)
        geometry_key = (shape, affine.tobytes())
        if geometry_key not in geometry:
            geometry[geometry_key] = n.sphere_supports(shape, affine, coordinates,
                                                       method['roi_geometry']['radius_mm'])
        support = geometry[geometry_key]
        roi_supports = [dict(roi_id=rid, n_voxels=int(indices.size),
                            support_sha256=n.support_digest(shape, affine, indices))
                       for rid, indices in zip(roi_ids, support)]
        source_people.append(dict(subject_id=sid, bold_path=bold_path, confounds_path=conf_path,
            bold_header=observed, frame_count=frames[sid], confound_column_names=c['columns'],
            selected_confound_columns=list(names), excluded_confound_columns=c['excluded'],
            missing_selected_entries=c['missing'], mean_fd_sum=c['fd_sum'], mean_fd_observed_count=c['fd_count'],
            mean_fd_missing_entries=c['fd_missing'], mean_fd_missing_frame_indices=fd_indices,
            mean_fd_zero_filled_sum=c['fd_sum'], mean_fd_denominator=frames[sid], roi_supports=roi_supports))
        prepared[sid] = (bold_path, observed, offset, dtype, c['values'], support)
    for sid in selected:
        check()
        bold_path, observed, offset, dtype, nuisance, support = prepared[sid]
        values = decode_values(buffers[bold_path], observed, offset, dtype, policy, check)
        raw_roi = n.extract_raw(values, support)
        del values
        result = n.clean_roi(raw_roi, nuisance, activity_fn=kernel.residual_active)
        persons[sid] = dict(raw_roi=raw_roi, cleaned_roi=result['cleaned'], canonical_active=result['active'],
                           frame_indices=np.arange(frames[sid], dtype=np.int64))
        activity = [dict(roi_id=rid, raw_centered_l2=float(result['raw_centered_l2'][j]),
            residual_centered_l2=float(result['residual_centered_l2'][j]),
            activity_threshold=float(result['activity_threshold'][j]), active=bool(result['active'][j]))
            for j, rid in enumerate(roi_ids)]
        analysis_people.append(dict(subject_id=sid, cleaning_rank=result['rank'], roi_activity=activity,
                                    n_active_rois=int(result['active'].sum())))
    # Recheck all source bytes/signatures/membership, then public docs, after consumption.
    h.closed_inventory(source, rows, check)
    for path, row in rows.items():
        _, after = h.authenticated_bytes(source / path, row, check)
        need(after == signatures[path], 'source_changed_after_consumption')
    h.frozen_manifest(source, manifest_path, auth)
    exact_read(method_path, policy.method_sha, 4 * 1024**2)
    exact_read(schema_path, policy.schema_sha, 4 * 1024**2)
    return dict(status='geometry_only' if geometry_only else 'resource_pilot' if pilot else 'complete',
        subject_ids=list(selected), structural_subject_ids=list(policy.subject_ids),
        roi_ids=roi_ids, coordinates=coordinates, persons=persons, covariates=covariates, cohort=cohort,
        roi_definitions=parsed['roi_definitions'],
        source_files=[dict(path=path, role=row['role'], subject_id=row.get('participant_id'),
                           size_bytes=row['size_bytes'], sha256=row['sha256']) for path, row in rows.items()],
        source_observed=dict(participants_column_names=phenotype['columns'],
            coordinates=dict(path=coord_path, sha256=coord_row['sha256'], column_names=parsed['columns']),
            persons=source_people, frame_alignment='All released frames kept in original row order; measured movie onset is not asserted.'),
        analysis_observed=dict(persons=analysis_people, distance_bins=bin_record),
        pins=dict(source_manifest_sha256=policy.source_sha, method_sha256=policy.method_sha,
                  output_schema_sha256=policy.schema_sha, reporting_kernel_sha256=policy.reporting_sha),
        method=method, schema=schema, warnings=[])
