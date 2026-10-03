"""DEVCONN original-source oracle: staged auth, nibabel values, Nilearn operators.

No private source_reference/source_numerics imports or source access at import.
Generic TSV/phenotype/literal and coordinate parsing, declared activity and
coordinate-only distance bins are shared explicitly; no endpoints are calculated. The source stager is authenticated as code and
used only for local identity guards; no transport/staging function is called.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
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
SOURCE_COUNT, SOURCE_BYTES = 316, 940543951
REPORTING_SHA = '2b3abe5fe37d3ad68db57301afa68cf6b0f5409abaf81bc5b06494ae4bf88638'
CODE_PINS = {
    'stage_data.py': 'b653f7c9522055cbfed634e8a08352d556059110f027b5a58d69cd229e4b6210',
    'inspect_structure.py': 'b0474f9de46a4a76e9307928f0a7f1999f7e51c23c1b3dd3657860a9374f9a15',
    'oracle_numerics.py': 'ba579f1502f6752fe6314dad9a044596ddac85ae7288a325329163e41627d5f2',
    'reporting_kernel.py': REPORTING_SHA,
    'coordinate_contract.py': '40991bfa9e2d78e14163b58a1f5f6ed30b9d14be6143c2671b5b87e5be8fc00e',
}
SUBJECTS = tuple(f'sub-pixar{i:03d}' for i in range(1, 156))
SOFTWARE = {'numpy': '2.1.3', 'scipy': '1.14.1', 'nibabel': '5.3.2',
            'nilearn': '0.12.1', 'scikit-learn': '1.5.2', 'pandas': '2.2.3'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sig(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def frozen_bytes(path, expected, maximum=4 * 1024**2):
    require(type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected), 'unfrozen_document')
    literal = os.fspath(path)
    require(type(literal) is str and literal.startswith('/') and '\0' not in literal
            and not any(p in ('.', '..') for p in literal.split('/')), 'unsafe_input_path')
    path = Path(literal)
    for parent in (*reversed(path.parents), path):
        if os.path.lexists(parent):
            require(not stat.S_ISLNK(parent.lstat().st_mode), 'symlink_input')
            if parent != path:
                require(stat.S_ISDIR(parent.lstat().st_mode), 'input_ancestor')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum, 'input_cap_or_type')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        require(sig(os.fstat(stream.fileno())) == sig(before), 'changed_input')
        payload = stream.read(maximum + 1)
        require(sig(os.fstat(stream.fileno())) == sig(before), 'changed_input')
    require(sig(path.lstat()) == sig(before), 'changed_input_path')
    require(len(payload) == before.st_size and hashlib.sha256(payload).hexdigest() == expected, 'input_identity')
    return payload


@dataclass(frozen=True)
class Policy:
    source_sha: str | None
    method_sha: str | None
    schema_sha: str | None
    source_count: int | None
    source_bytes: int | None
    reporting_sha: str | None
    code_pins: dict
    software: dict
    subjects: tuple = SUBJECTS
    expected_rois: int = 264
    decoded_byte_cap: int = 512 * 1024**2
    header_byte_cap: int = 1024**2
    wall_seconds: int = 1800


def production_policy():
    return Policy(SOURCE_SHA, METHOD_SHA, SCHEMA_SHA, SOURCE_COUNT, SOURCE_BYTES,
                  REPORTING_SHA, dict(CODE_PINS), dict(SOFTWARE))


def code_modules(policy):
    require(set(policy.code_pins) == set(CODE_PINS), 'code_closure')
    require(policy.code_pins['reporting_kernel.py'] == policy.reporting_sha, 'reporting_pin')
    directory = Path(__file__).absolute().parent
    buffers = {name: frozen_bytes(directory / name, pin, 1024**2) for name, pin in policy.code_pins.items()}
    result = {}
    for name, raw in buffers.items():
        key = '_devconn_oracle_' + name[:-3]
        module = types.ModuleType(key)
        module.__file__ = str(directory / name)
        sys.modules[key] = module
        try:
            exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        result[name[:-3]] = module
    return result


def image_header(compressed, dimensions, documentary, policy, check):
    """Independent header constructor; no image value loader for unselected BOLD."""
    import nibabel as nib
    import numpy as np
    inflater = zlib.decompressobj(31)
    prefix, position = bytearray(), 0

    def through(limit):
        nonlocal position
        while len(prefix) < limit:
            check()
            if inflater.unconsumed_tail:
                part = inflater.unconsumed_tail
            else:
                end = min(position + 2048, len(compressed), policy.header_byte_cap)
                require(end > position, 'header_prefix_cap_or_truncated')
                part = compressed[position:end]
                position = end
            decoded = inflater.decompress(part, limit - len(prefix))
            prefix.extend(decoded)
            require(decoded or not inflater.eof, 'header_truncated')

    through(352)
    h = nib.Nifti1Header(bytes(prefix[:348]), check=False)
    require(int(h['sizeof_hdr']) == 348 and h['magic'].tobytes() == b'n+1\0', 'nifti1_single_file')
    shape = [int(v) for v in h.get_data_shape()]
    dtype = h.get_data_dtype()
    require(len(shape) == dimensions and all(v > 0 for v in shape), 'image_dimensions')
    require(dtype.kind in 'iuf' and dtype.itemsize <= 8 and int(h['bitpix']) == 8 * dtype.itemsize, 'image_storage_type')
    offset = float(h['vox_offset'])
    require(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= policy.header_byte_cap, 'image_offset')
    offset = int(offset)
    through(offset)
    if prefix[348]:
        cursor = 352
        while cursor < offset:
            require(cursor + 8 <= offset, 'extension_header')
            extent, code = struct.unpack(h.endianness + 'ii', prefix[cursor:cursor + 8])
            require(extent >= 16 and extent % 16 == 0 and cursor + extent <= offset, 'extension_length')
            cursor += extent
    else:
        require(not any(prefix[352:]), 'unflagged_extension')
    affine = h.get_best_affine()
    require(np.isfinite(affine).all() and np.array_equal(affine[3], [0., 0., 0., 1.]), 'image_affine')
    determinant = float(np.linalg.det(affine[:3, :3]))
    require(math.isfinite(determinant) and determinant != 0, 'image_affine_singular')
    units = h.get_xyzt_units()
    slope, intercept = h.get_slope_inter()
    record = dict(shape=shape, selected_affine=affine.tolist(), storage_dtype=dtype.str,
        spatial_units=units[0], temporal_units=units[1], zooms=[documentary.literal(v) for v in h.get_zooms()],
        raw_toffset=documentary.literal(h['toffset']), raw_scl_slope=documentary.literal(h['scl_slope']),
        raw_scl_inter=documentary.literal(h['scl_inter']), effective_slope=1. if slope is None else float(slope),
        effective_intercept=0. if intercept is None else float(intercept))
    require(all(type(v) is float and math.isfinite(v) and v > 0 for v in record['zooms']), 'image_zooms')
    return record, offset + math.prod(shape) * dtype.itemsize


def image_values(compressed, record, expected_bytes, policy, check):
    """Strict bounded gzip bytes, then nibabel's independent calibrated proxy."""
    import nibabel as nib
    import numpy as np
    require(expected_bytes <= policy.decoded_byte_cap, 'decoded_image_cap')
    inflater = zlib.decompressobj(31)
    pieces, total, position = [], 0, 0
    while not inflater.eof:
        check()
        if inflater.unconsumed_tail:
            part = inflater.unconsumed_tail
        else:
            require(position < len(compressed), 'image_gzip_truncated')
            part = compressed[position:position + 32768]
            position += len(part)
        block = inflater.decompress(part, min(1024**2, expected_bytes + 1 - total))
        total += len(block)
        require(total <= expected_bytes, 'image_gzip_overrun')
        pieces.append(block)
    require(total == expected_bytes and position == len(compressed)
            and not inflater.unused_data and not inflater.unconsumed_tail, 'image_gzip_length_or_trailing')
    uncompressed = b''.join(pieces)
    image = nib.Nifti1Image.from_bytes(uncompressed)
    require(list(image.shape) == record['shape'] and np.array_equal(image.affine, record['selected_affine']),
            'image_header_consistency')
    # Calibrated float64 values via nibabel, not private direct-buffer arithmetic.
    return np.array(image.get_fdata(dtype=np.float64, caching='unchanged'), dtype=np.float64, order='C', copy=True)


def nuisance_table(raw, documentary, table_policy, names, missing, count):
    """Fourteen nuisance columns; FD is parsed separately and never regressed."""
    import numpy as np
    columns, tokens = documentary.table(raw, table_policy)
    require(len(tokens) == count and all(name in columns for name in (*names, 'framewise_displacement')),
            'nuisance_columns_or_frames')
    require(type(missing['missing_tokens']) is list
            and missing['missing_tokens'] == ['', 'n/a'] and missing['fill_value'] == 0,
            'missingness_policy')
    require('framewise_displacement' not in names, 'fd_is_not_nuisance')
    indices = [columns.index(name) for name in names]
    fd_index = columns.index('framewise_displacement')
    array = np.zeros((count, len(names)), dtype=np.float64)
    ledger, fd, fd_ledger = [], [], []

    def number(token):
        try: value = float(token)
        except ValueError as exc: raise ValueError('nuisance_token') from exc
        require(math.isfinite(value), 'nuisance_nonfinite')
        return value

    for frame, row in enumerate(tokens):
        for j, index in enumerate(indices):
            name, token = names[j], row[index]
            if token in missing['missing_tokens']:
                ledger.append(dict(frame_index=frame, column_name=name, original_token=token, applied_value=0.))
            else:
                array[frame, j] = number(token)
        token = row[fd_index]
        if token in missing['missing_tokens']:
            fd_ledger.append(dict(frame_index=frame, column_name='framewise_displacement',
                                  original_token=token, applied_value=0.))
        else:
            fd.append(number(token))
    ledger.sort(key=lambda row: (names.index(row['column_name']), row['frame_index']))
    total = math.fsum(fd)  # Empty finite list correctly gives zero; denominator remains T.
    require(math.isfinite(total), 'fd_sum_nonfinite')
    return dict(array=array, columns=columns, ledger=ledger, fd_ledger=fd_ledger,
                missing_fd=[row['frame_index'] for row in fd_ledger],
                fd_sum=total, fd_count=len(fd), mean_fd=total / count)


def reconstruct(data_dir='/app/data/devconn', manifest_path='/app/source_manifest.json',
                method_path='/app/method_contract.json', schema_path='/app/output_schema.json',
                *, pilot=False, geometry_only=False, _policy=None):
    require(type(pilot) is bool and type(geometry_only) is bool and not (pilot and geometry_only), 'mode_flags')
    policy = production_policy() if _policy is None else _policy
    require(all(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin) for pin in
                (policy.source_sha, policy.method_sha, policy.schema_sha, policy.reporting_sha)), 'unfrozen_document')
    require(type(policy.expected_rois) is int and policy.expected_rois >= 2, 'roi_count')
    modules = code_modules(policy)
    stage, doc, numerics, reporting, coordinate = (modules[k] for k in
        ('stage_data', 'inspect_structure', 'oracle_numerics', 'reporting_kernel', 'coordinate_contract'))
    import numpy as np
    started = time.monotonic()

    def check(): require(time.monotonic() - started < policy.wall_seconds, 'oracle_source_deadline')

    require({key: importlib.metadata.version(key) for key in policy.software} == policy.software, 'oracle_software')
    method_raw = frozen_bytes(method_path, policy.method_sha)
    schema_raw = frozen_bytes(schema_path, policy.schema_sha)
    method, schema = doc.strict_json(method_raw), doc.strict_json(schema_raw)
    require(method.get('task_id') == schema.get('task_id') == 'DEVCONN-001', 'document_task')
    require(method['source']['source_manifest_sha256'] == schema.get('source_manifest_sha256') == policy.source_sha
            and schema.get('method_sha256') == policy.method_sha
            and schema.get('reporting_kernel_sha256') == method.get('reporting_kernel_sha256') == policy.reporting_sha,
            'document_pins')
    counts = method['source']['frame_counts_by_subject']
    require(type(counts) is dict and set(counts) == set(policy.subjects)
            and all(type(v) is int and v >= 2 for v in counts.values()), 'unfrozen_frames')
    require(method['source']['n_subjects'] == len(policy.subjects)
            and method['source']['total_frames'] == sum(counts.values()), 'source_cohort')
    units = method['source']['spatial_unit_policy']
    require(units['world_coordinate_unit'] == 'mm'
            and type(units['allowed_bold_header_units']) is list and units['allowed_bold_header_units']
            and set(units['allowed_bold_header_units']) <= {'unknown', 'mm'}, 'spatial_policy')
    require(method['activity']['relative_threshold'] == 1e-12, 'activity_policy')
    require(method['source']['documented_TR_s'] == 2
            and method['roi_geometry']['radius_mm'] == 5
            and type(method['roi_geometry']['n_rois']) is int
            and method['roi_geometry']['n_rois'] == policy.expected_rois, 'operator_geometry')
    filter_spec = method['temporal_cleaning']['filter']
    require(filter_spec['order'] == 5 and filter_spec['high_pass_hz'] == .009
            and filter_spec['low_pass_hz'] == .08 and filter_spec['sampling_hz'] == .5
            and filter_spec['padtype'] == 'odd' and filter_spec['padlen'] is None, 'operator_filter')
    # A fresh SHA-authenticated stager instance, solely its local identity guards.
    stage.MANIFEST_SHA256, stage.EXPECTED_COUNT, stage.EXPECTED_BYTES = policy.source_sha, policy.source_count, policy.source_bytes
    stage.SUBJECTS = policy.subjects
    source = stage.safe_path(data_dir)
    manifest, manifest_raw = stage.load_manifest(manifest_path)
    require(manifest['n_files'] == method['source']['n_files']
            and manifest['total_bytes'] == method['source']['total_bytes'], 'method_inventory')
    internal, internal_raw = stage.load_manifest(source / 'source_manifest.json')
    require(manifest_raw == internal_raw, 'internal_manifest')
    stage.inventory(source, manifest['files'])
    buffers, signatures, rows = {}, {}, {row['path']: row for row in manifest['files']}
    for name, row in rows.items():
        check()
        with stage.reader(source / name) as (stream, info):
            require(info.st_size == row['size_bytes'], 'source_size')
            payload = stream.read(row['size_bytes'] + 1)
        hashes = stage.hashers(row)
        for digest in hashes.values(): digest.update(payload)
        stage.check_hashes(row, hashes, len(payload))
        buffers[name], signatures[name] = payload, stage.signature(info)
    # Every original/provenance member is authenticated BEFORE any parser.
    keyed = {(row['role'], row.get('participant_id')): name for name, row in rows.items()}
    coordinate_path = keyed['coordinates', None]
    require(coordinate_path == method['roi_geometry']['coordinates_path']
            and rows[coordinate_path]['sha256'] == method['roi_geometry']['coordinates_sha256'], 'coordinate_pin')
    power = coordinate.parse_power(buffers[coordinate_path], expected_rois=policy.expected_rois)
    require(power['columns'] == method['roi_geometry']['source_columns'], 'coordinate_columns')
    roi_ids, centers = power['roi_ids'], power['coordinates']
    bins = coordinate.bin_record(reporting.distance_bins(centers, roi_ids))
    table_policy = doc.Policy(policy.source_sha, policy.software, participant_ids=policy.subjects)
    phenotype = doc.phenotype(buffers[keyed['participants', None]], table_policy)
    require(phenotype['group_token_counts'] == method['source']['expected_group_counts']
            and all(p['age_kind'] == 'finite' and p['group_known'] for p in phenotype['selected']), 'source_phenotype')
    demographic = {p['participant_id']: p for p in phenotype['selected']}
    names = method['confounds']['columns']
    require(tuple(names) == doc.NUISANCE == numerics.CONF_COLS, 'operator_confound_axis')
    chosen = () if geometry_only else policy.subjects[:1] if pilot else policy.subjects
    cohort, source_people, analysis_people, covariates, persons, grids, prepared = [], [], [], {}, {}, {}, {}
    # Complete all-participant headers/tables/geometry BEFORE the first BOLD values.
    for sid in policy.subjects:
        check()
        bpath, cpath = keyed['bold', sid], keyed['confounds', sid]
        header, length = image_header(buffers[bpath], 4, doc, policy, check)
        require(header['shape'][3] == counts[sid] and header['spatial_units'] in units['allowed_bold_header_units'],
                'bold_frames_or_units')
        c = nuisance_table(buffers[cpath], doc, table_policy, names, method['confounds']['missingness'], counts[sid])
        covariates[sid] = dict(age=demographic[sid]['age'], group=demographic[sid]['group_token'], mean_fd=c['mean_fd'])
        cohort.append(dict(subject_id=sid, **covariates[sid], mean_fd_observed_count=c['fd_count'],
                           mean_fd_missing_frame_indices=c['missing_fd']))
        shape, affine = tuple(header['shape'][:3]), np.asarray(header['selected_affine'], dtype=np.float64)
        key = (shape, affine.tobytes())
        if key not in grids:
            supports = numerics.sphere_supports(shape, affine, centers, method['roi_geometry']['radius_mm'])
            require(len(supports) == len(roi_ids) and all(len(indices) > 0 for indices in supports), 'empty_roi_support')
            grids[key] = supports
        supports = grids[key]
        support_records = [dict(roi_id=rid, n_voxels=int(len(indices)),
            support_sha256=numerics.support_digest(shape, affine, indices)) for rid, indices in zip(roi_ids, supports)]
        source_people.append(dict(subject_id=sid, bold_path=bpath, confounds_path=cpath, bold_header=header,
            frame_count=counts[sid], confound_column_names=c['columns'], selected_confound_columns=list(names),
            excluded_confound_columns=[name for name in c['columns'] if name not in names],
            missing_selected_entries=c['ledger'], mean_fd_sum=c['fd_sum'], mean_fd_observed_count=c['fd_count'],
            mean_fd_missing_entries=c['fd_ledger'], mean_fd_missing_frame_indices=c['missing_fd'],
            mean_fd_zero_filled_sum=c['fd_sum'], mean_fd_denominator=counts[sid], roi_supports=support_records))
        prepared[sid] = (bpath, header, length, c['array'], supports)
    for sid in chosen:
        check()
        bpath, header, length, nuisance, supports = prepared[sid]
        image = image_values(buffers[bpath], header, length, policy, check)
        raw = numerics.extract_raw(image, supports)
        del image
        cleaned = numerics.clean_roi(raw, nuisance, activity_fn=reporting.residual_active)
        persons[sid] = dict(raw_roi=raw, frame_indices=np.arange(counts[sid], dtype=np.int64),
                           cleaned_roi=cleaned['cleaned'], canonical_active=cleaned['active'])
        analysis_people.append(dict(subject_id=sid, cleaning_rank=cleaned['rank'],
            n_active_rois=int(cleaned['active'].sum()),
            roi_activity=[dict(roi_id=rid, raw_centered_l2=float(cleaned['raw_centered_l2'][j]),
                residual_centered_l2=float(cleaned['residual_centered_l2'][j]),
                activity_threshold=float(cleaned['activity_threshold'][j]),
                active=bool(cleaned['active'][j])) for j, rid in enumerate(roi_ids)]))
    stage.inventory(source, manifest['files'])
    for name, row in rows.items():
        check(); stage.file_identity(source / name, row, started + policy.wall_seconds)
        require(stage.signature((source / name).lstat()) == signatures[name], 'post_source_changed')
    stage.load_manifest(manifest_path); stage.load_manifest(source / 'source_manifest.json')
    frozen_bytes(method_path, policy.method_sha); frozen_bytes(schema_path, policy.schema_sha)
    return dict(status='geometry_only' if geometry_only else 'resource_pilot' if pilot else 'complete',
        subject_ids=list(chosen), structural_subject_ids=list(policy.subjects),
        roi_ids=roi_ids, coordinates=centers, persons=persons,
        covariates=covariates, cohort=cohort, roi_definitions=power['roi_definitions'],
        source_files=[dict(path=name, role=row['role'], subject_id=row.get('participant_id'), size_bytes=row['size_bytes'],
                           sha256=row['sha256']) for name, row in rows.items()],
        source_observed=dict(participants_column_names=phenotype['columns'],
            coordinates=dict(path=coordinate_path, sha256=rows[coordinate_path]['sha256'], column_names=power['columns']),
            persons=source_people, frame_alignment='All released frames kept in original row order; measured movie onset is not asserted.'),
        analysis_observed=dict(persons=analysis_people, distance_bins=bins),
        pins=dict(source_manifest_sha256=policy.source_sha, method_sha256=policy.method_sha,
                  output_schema_sha256=policy.schema_sha, reporting_kernel_sha256=policy.reporting_sha),
        method=method, schema=schema, warnings=[])
