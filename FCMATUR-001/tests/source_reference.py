"""Private FCMATUR original reconstruction, no oracle/stager/kernel imports.

Two complete authentication passes: all 1037 originals are first verified
before parsing; second-pass same-buffer parsing keeps each guarded descriptor
open through consumption. Final identity/inventory checks precede return.
No derived association, downstream fit, output acceptance cache or bank exists.
The consumed immutable buffers are the hash authority. Post-consumption stat
checks detect identity changes, not arbitrary same-inode rewrites hidden by
filesystem timestamp resolution. No claim of an atomic filesystem snapshot.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import types

import numpy as np

SOURCE_SHA = 'c62460fa4a0255f0efa60c562fdca425af98458f5a9cd8c93687551c893ab1c7'
METHOD_SHA = 'ae174eef6f838bd6e5925941dd095b8b703c15296d1d4578ab868255d2b6eb4c'
SCHEMA_SHA = '8c4760b3ce017c74317efd3f544d577280ca284bae5abad039624fb0fa44498a'
NUMERICS_SHA = '12864cc84f8f0269e4d0ef4c21e63eade2784c487f7dac247901146fc6ca7a2e'
HEADER_SHA = '259f94bc6482d009b0bd85400faa1a4f93058735b6d9283988c494a0cb96a103'
FIELDS = ('AGE_AT_SCAN', 'SITE_ID', 'SEX', 'DX_GROUP', 'func_mean_fd')
PHENOTYPE = 'Phenotypic_V1_0b_preprocessed1.csv'
NOTICE = 'provenance/nilearn_0_13_1_ABIDE_pcp.rst'


@dataclass(frozen=True)
class Policy:
    source_sha: str
    method_sha: str
    schema_sha: str
    file_count: int = 1037
    source_bytes: int = 406541576
    roi_count: int = 1035
    phenotype_rows: int = 1112
    columns: int = 200
    total_frames: int = 201321
    frame_min: int = 78
    frame_max: int = 316
    member_cap: int = 1000000
    source_cap: int = 420000000
    metadata_cap: int = 4*1024**2


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(value, length=64):
    return type(value) is str and re.fullmatch(f'[0-9a-f]{{{length}}}', value) is not None


def safe_path(value):
    literal = os.fspath(value)
    need(type(literal) is str and literal.startswith('/') and '\0' not in literal, 'absolute_path_required')
    need(not any(part in ('.', '..') for part in literal.split('/')), 'path_traversal')
    path = Path(literal)
    for node in (*reversed(path.parents), path):
        if os.path.lexists(node):
            info = node.lstat()
            need(not stat.S_ISLNK(info.st_mode), 'source_symlink')
            if node != path:
                need(stat.S_ISDIR(info.st_mode), 'source_parent_type')
    return path


def relative(value):
    need(type(value) is str and value and '\\' not in value and '\0' not in value
         and not value.startswith('/') and not re.match(r'^[A-Za-z]:', value)
         and all(part not in ('', '.', '..') for part in value.split('/')), 'source_relative_path')
    return PurePosixPath(value)


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def reader(path):
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode), 'source_regular_file')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            os.close(directory); directory = next_fd
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'source_changed_before_read')
        yield stream, before
        need(signature(os.fstat(stream.fileno())) == signature(before), 'source_changed_during_consumption')
        need(signature(safe_path(path).lstat()) == signature(before), 'source_path_changed')


def pinned_bytes(path, pin, cap):
    need(digest(pin), 'unfrozen_authority')
    with reader(path) as (stream, info):
        need(0 < info.st_size <= cap, 'metadata_size_cap')
        raw = stream.read(cap+1)
        need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == pin, 'metadata_digest')
    return raw


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    def invalid(unused):
        raise ValueError('nonfinite_json')
    obj = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    def walk(value, depth=0):
        need(depth <= 64, 'json_depth')
        if isinstance(value, float): need(math.isfinite(value), 'nonfinite_json')
        if isinstance(value, (list, dict)):
            for item in value.values() if isinstance(value, dict) else value: walk(item, depth+1)
    walk(obj)
    return obj


def load_numerics():
    path = Path(__file__).absolute().with_name('source_numerics.py')
    raw = pinned_bytes(path, NUMERICS_SHA, 128*1024)
    module = types.ModuleType('_fcmatur_private_source_numerics')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def manifest_entries(manifest, policy):
    need(type(manifest) is dict and manifest.get('schema_version') == 'fcmatur-source-v2'
         and manifest.get('task_id') == 'FCMATUR-001'
         and manifest.get('dataset_id') == 'ABIDE_pcp/cpac/filt_noglobal/rois_cc200', 'manifest_schema')
    rows, ids = manifest.get('files'), manifest.get('participant_file_ids')
    need(type(rows) is list and len(rows) == policy.file_count and type(ids) is list
         and len(ids) == policy.roi_count and len(set(ids)) == len(ids), 'manifest_counts')
    need(all(type(s) is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*_[0-9]{7}', s) for s in ids), 'literal_cohort')
    paths, indexes, subjects, ordered = set(), set(), set(), []
    counts, total = {}, 0
    for row in rows:
        need(type(row) is dict, 'manifest_row')
        path = row.get('path'); relative(path)
        need(path not in paths, 'duplicate_source_path'); paths.add(path)
        size = row.get('size_bytes')
        need(type(size) is int and 0 < size <= policy.member_cap and digest(row.get('sha256')), 'source_identity')
        total += size; need(total <= policy.source_cap, 'source_size_cap')
        for key, length in (('md5', 32), ('git_blob_sha1', 40)):
            if key in row: need(digest(row[key], length), 'source_secondary_identity')
        role = row.get('role'); need(type(role) is str, 'source_role')
        counts[role] = counts.get(role, 0)+1
        if role == 'roi_timeseries':
            sid, subject, index = row.get('file_id'), row.get('subject_id'), row.get('phenotype_row_index')
            need(sid in ids and path == f'roi/{sid}_rois_cc200.1D', 'source_file_id')
            need(type(subject) is str and re.fullmatch(r'[0-9]+', subject) is not None
                 and subject == str(int(sid.rsplit('_', 1)[1])) and subject not in subjects, 'source_subject_join')
            need(type(index) is int and 0 <= index < policy.phenotype_rows and index not in indexes, 'source_row_index')
            subjects.add(subject); indexes.add(index); ordered.append(sid)
        elif role == 'phenotype': need(path == PHENOTYPE, 'phenotype_path')
        elif role == 'provenance_abide_notice': need(path == NOTICE, 'notice_path')
        else: raise ValueError('source_role')
    need(counts == {'roi_timeseries': policy.roi_count, 'phenotype': 1, 'provenance_abide_notice': 1}, 'source_roles')
    need(ordered == ids and total == policy.source_bytes, 'source_membership_or_bytes')
    need(type(manifest.get('source_file_count')) is int and manifest['source_file_count'] == policy.file_count
         and type(manifest.get('source_bytes')) is int and manifest['source_bytes'] == total, 'source_declared_totals')
    need(not any(str(p) in paths for path in paths for p in PurePosixPath(path).parents), 'source_path_collision')
    return rows, ids


def inventory(root, rows):
    wanted = {r['path'] for r in rows} | {'source_manifest.json'}
    directories = {str(p) for name in wanted for p in relative(name).parents if str(p) != '.'}
    found, seen_dirs, stack = set(), set(), [root]
    while stack:
        folder = stack.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                path = Path(entry.path); rel = path.relative_to(root).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    need(rel in directories, 'unexpected_source_directory'); seen_dirs.add(rel); stack.append(path)
                else:
                    need(stat.S_ISREG(mode) and rel in wanted, 'unexpected_or_special_source'); found.add(rel)
    need(found == wanted and seen_dirs == directories, 'closed_source_inventory')


@contextmanager
def member(root, row, expected=None):
    with reader(root/row['path']) as (stream, info):
        sig = signature(info)
        need(expected is None or sig == expected, 'source_changed_since_authentication')
        need(info.st_size == row['size_bytes'], 'source_size')
        raw = stream.read(row['size_bytes']+1)
        need(len(raw) == row['size_bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'source_sha256')
        if 'md5' in row: need(hashlib.md5(raw).hexdigest() == row['md5'], 'source_md5')
        if 'git_blob_sha1' in row:
            need(hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() == row['git_blob_sha1'], 'source_git_blob')
        yield raw, sig


def normalized_token(token, kind):
    text = token.strip()
    if not text: return None, 'missing'
    if kind == 'site': return text, 'ok'
    try: value = float(text)
    except ValueError: return None, 'invalid_numeric'
    if not math.isfinite(value): return None, 'invalid_numeric'
    if kind == 'age' and not 0 < value < 120: return None, 'invalid_age'
    if kind == 'mean_fd' and value < 0: return None, 'invalid_mean_fd'
    if kind in ('sex', 'dx_group'):
        if value not in (1., 2.): return None, 'invalid_code'
        return int(value), 'ok'
    return value, 'ok'


def phenotype_rows(raw, source_rows, policy):
    text = raw.decode('utf-8-sig', errors='strict'); need('\0' not in text, 'phenotype_nul')
    old = csv.field_size_limit(); csv.field_size_limit(65536)
    try: data = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    finally: csv.field_size_limit(old)
    need(len(data) == policy.phenotype_rows+1, 'phenotype_rows')
    header = data[0]
    need(0 < len(header) <= 512 and len(header) == len(set(header)), 'phenotype_header_duplicate')
    need(all(h or j == 0 for j, h in enumerate(header)) and {'SUB_ID', 'FILE_ID', *FIELDS} <= set(header), 'phenotype_header')
    by_index = {r['phenotype_row_index']: r for r in source_rows if r['role'] == 'roi_timeseries'}
    ledger, seen, selected = [], set(), {}
    mapping = {'AGE_AT_SCAN':'age', 'SITE_ID':'site', 'SEX':'sex', 'DX_GROUP':'dx_group', 'func_mean_fd':'mean_fd'}
    for index, values in enumerate(data[1:]):
        need(len(values) == len(header), 'phenotype_width')
        record = dict(zip(header, values)); token = record['SUB_ID']; fid = record['FILE_ID']
        need(re.fullmatch(r'[0-9]{1,32}', token) is not None, 'phenotype_subject')
        sid = str(int(token)); need(sid not in seen, 'duplicate_phenotype_subject'); seen.add(sid)
        original = by_index.get(index)
        if fid == 'no_filename': need(original is None, 'phenotype_unavailable_join')
        else:
            need(original is not None and fid == original['file_id'] and sid == original['subject_id'], 'phenotype_literal_join')
            need(fid not in selected, 'phenotype_duplicate_file')
        tokens = {field: record[field] for field in FIELDS}
        normalized, statuses = {}, {}
        for field, kind in mapping.items():
            value, status = normalized_token(tokens[field], kind)
            key = 'site_id' if kind == 'site' else kind
            normalized[key], statuses[key] = value, status
        dx = normalized['dx_group']
        normalized['typical_control'] = None if dx is None else dx == 2
        row = dict(phenotype_row_index=index, subject_id=sid, source_subject_id_token=token, file_id=fid,
                   source_availability='no_filename' if original is None else 'released_filename',
                   source_path=None if original is None else original['path'], tokens=tokens,
                   normalized=normalized, covariate_status=statuses)
        ledger.append(row)
        if original is not None: selected[fid] = row
    need(len(selected) == policy.roi_count, 'phenotype_selected_count')
    return header, ledger, selected


def parse_roi(raw, policy):
    text = raw.decode('ascii', errors='strict'); need('\0' not in text, 'roi_nul')
    lines = text.splitlines(); need(len(lines) >= 2, 'roi_empty')
    header = lines[0]
    need(header.split('\t') == [f'#{i}' for i in range(1, policy.columns+1)], 'roi_header')
    n = len(lines)-1; need(policy.frame_min <= n <= policy.frame_max, 'roi_frame_count')
    need(all(line.strip() and '#' not in line and len(line.split()) == policy.columns for line in lines[1:]), 'roi_width_or_skipped_row')
    try: values = np.loadtxt(io.StringIO('\n'.join(lines[1:])), dtype=np.float64, comments=None, ndmin=2)
    except ValueError: raise ValueError('roi_numeric_parse') from None
    need(values.shape == (n, policy.columns) and bool(np.isfinite(values).all()), 'roi_nonfinite_or_shape')
    return values, dict(n_frames=n, n_columns=policy.columns,
                        header_sha256=hashlib.sha256(header.encode('ascii')).hexdigest(),
                        source_column_ids=list(range(1, policy.columns+1)), all_finite=True)


def _reconstruct(data_dir, method_path, schema_path, manifest_path, policy):
    need(type(policy) is Policy, 'explicit_private_policy')
    for pin in (policy.source_sha, policy.method_sha, policy.schema_sha): need(digest(pin), 'unfrozen_authority')
    root = safe_path(data_dir); need(root.is_dir(), 'source_root')
    public = safe_path(manifest_path)
    manifest_raw = pinned_bytes(public, policy.source_sha, policy.metadata_cap)
    need(pinned_bytes(root/'source_manifest.json', policy.source_sha, policy.metadata_cap) == manifest_raw, 'internal_manifest')
    method_raw = pinned_bytes(method_path, policy.method_sha, policy.metadata_cap)
    schema_raw = pinned_bytes(schema_path, policy.schema_sha, policy.metadata_cap)
    manifest, method, schema = map(strict_json, (manifest_raw, method_raw, schema_raw))
    need(type(method) is dict and type(schema) is dict, 'contract_objects')
    records, ids = manifest_entries(manifest, policy)
    inventory(root, records)
    signatures = {}; bytes_read = 0
    for record in records:
        with member(root, record) as (raw, sig):
            signatures[record['path']] = sig; bytes_read += len(raw)
    need(bytes_read == policy.source_bytes, 'first_authentication_total')
    pheno = next(r for r in records if r['role'] == 'phenotype')
    with member(root, pheno, signatures[pheno['path']]) as (raw, _):
        columns, ledger, selected = phenotype_rows(raw, records, policy); bytes_read += len(raw)
    numerics = load_numerics()
    people, normalized_rows = {}, []
    frames = 0
    for record in records:
        if record['role'] == 'phenotype': continue
        with member(root, record, signatures[record['path']]) as (raw, _):
            bytes_read += len(raw)
            if record['role'] != 'roi_timeseries': continue
            values, structural = parse_roi(raw, policy)
            primitive = numerics.connectivity(values)
            fid = record['file_id']; metadata = selected[fid]; frames += structural['n_frames']
            constant = np.all(values == values[:1], axis=0)
            primitive.update(exact_constant_columns=(np.flatnonzero(constant)+1).tolist())
            people[fid] = dict(source_path=record['path'], source_sha256=record['sha256'],
                               subject_id=record['subject_id'], phenotype_row_index=record['phenotype_row_index'],
                               **structural, **{k:v for k,v in primitive.items() if k not in structural})
            fields = metadata['normalized']
            normalized_rows.append(dict(subject=fid, connectivity=primitive['connectivity'],
                                        **{k:fields[k] for k in ('age','site_id','mean_fd','sex','typical_control')}))
    need(frames == policy.total_frames and bytes_read == 2*policy.source_bytes, 'complete_source_frames_or_authentication')
    inventory(root, records)
    for record in records:
        need(signature(safe_path(root/record['path']).lstat()) == signatures[record['path']], 'source_changed_after_consumption')
    for path, pin, expected in ((public, policy.source_sha, manifest_raw), (root/'source_manifest.json', policy.source_sha, manifest_raw),
                                (method_path, policy.method_sha, method_raw), (schema_path, policy.schema_sha, schema_raw)):
        need(pinned_bytes(path, pin, policy.metadata_cap) == expected, 'metadata_changed')
    need([row['subject'] for row in normalized_rows] == ids, 'reconstructed_cohort_order')
    return dict(status='complete', participant_ids=ids, canonical_rows=normalized_rows, persons=people,
                phenotype_ledger=ledger, phenotype_columns=columns, source_manifest=manifest,
                source_files=[dict(row) for row in records], method=method, schema=schema,
                pins=dict(source_manifest_sha256=policy.source_sha, method_contract_sha256=policy.method_sha,
                          output_schema_sha256=policy.schema_sha),
                source_observed=dict(n_source_files=len(records), source_bytes=policy.source_bytes,
                    n_phenotype_rows=len(ledger), n_no_filename=len(ledger)-len(ids), total_frames=frames,
                    phenotype_columns=columns, source_column_ids=list(range(1, policy.columns+1)),
                    persons={fid:{k:people[fid][k] for k in ('n_frames','n_columns','header_sha256','all_finite',
                        'active_columns','exact_constant_columns','n_active_columns','n_edges')} for fid in ids}),
                authentication=dict(full_source_passes=2, source_bytes_read=bytes_read, postconsumption_identity_check=True),
                downstream_statistics_computed=False)


def reconstruct(data_dir='/app/data/fcmatur', method_path='/app/method_contract.json',
                schema_path='/app/output_schema.json', manifest_path='/app/source_manifest.json'):
    """Full private reconstruction; no environment-controlled pin/bypass path."""
    return _reconstruct(data_dir, method_path, schema_path, manifest_path,
                        Policy(SOURCE_SHA, METHOD_SHA, SCHEMA_SHA))
