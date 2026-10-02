"""Private closed-source FCSTAB reconstruction; import-safe and bank-free.

All42 original members authenticate before parsing. Each consumed immutable
buffer is pinned before parse and its still-open descriptor is checksummed
after consumption. Final inventory/path/metadata checks precede return. This
does not claim an atomic filesystem snapshot or arbitrary process isolation.
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

SOURCE_SHA = 'c57fed19c165e8a606c2b6a9aef89099103a2642d6ab54b93bf525d71ea46171'
IDS_SHA = '7645fc4276e63ed4f09e4135bac9d38da3b036a2e4e522fae432ae490d4d28cb'
METHOD_SHA = '004a396e4f4f37db956083939c84465819b7d3cd1a69569721c39e7884734ee4'
SCHEMA_SHA = 'bedafa3a91bcb6d6b83dd3ae6d4f2d4d9f7a58cc1f65631be3e5e7e86a47fadf'
NUMERICS_SHA = '037b2db400e999303aa18381f7c6686e64bc29d9ca6b39e3bc86eed6e62bf62b'
PHENOTYPE = 'Phenotypic_V1_0b_preprocessed1.csv'
NOTICE = 'provenance/nilearn_0_13_1_ABIDE_pcp.rst'
FIELDS = ('SITE_ID', 'EYE_STATUS_AT_SCAN')


@dataclass(frozen=True)
class Policy:
    source_sha: str
    method_sha: str
    schema_sha: str
    ids_sha: str
    file_count: int = 42
    source_bytes: int = 16147721
    roi_count: int = 40
    phenotype_rows: int = 1112
    named_phenotype_rows: int = 1035
    no_filename_rows: int = 77
    frames: int = 196
    columns: int = 200
    member_cap: int = 1000000
    source_cap: int = 20000000
    metadata_cap: int = 2*1024**2


def need(ok, reason):
    if not ok: raise ValueError(reason)


def digest(value, width=64):
    return type(value) is str and re.fullmatch(f'[0-9a-f]{{{width}}}', value) is not None


def safe_path(value):
    literal = os.fspath(value)
    need(type(literal) is str and literal.startswith('/') and '\0' not in literal
         and all(p not in ('.', '..') for p in literal.split('/')), 'unsafe_absolute_path')
    path = Path(literal)
    for node in (*reversed(path.parents), path):
        if os.path.lexists(node):
            mode = node.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'source_symlink')
            need(node == path or stat.S_ISDIR(mode), 'source_parent_type')
    return path


def relative(value):
    need(type(value) is str and value and '\\' not in value and '\0' not in value
         and not value.startswith('/') and not re.match('^[A-Za-z]:', value)
         and all(p not in ('', '.', '..') for p in value.split('/')), 'unsafe_source_member')
    return PurePosixPath(value)


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def reader(path):
    path = safe_path(path); before = path.lstat()
    need(stat.S_ISREG(before.st_mode), 'source_regular_file')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for name in path.parts[1:-1]:
            nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            os.close(directory); directory = nxt
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    finally: os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'source_changed_before_read')
        yield stream, before
        need(signature(os.fstat(stream.fileno())) == signature(before), 'source_changed_descriptor')
        need(signature(safe_path(path).lstat()) == signature(before), 'source_changed_path')


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
            need(key not in out, 'duplicate_json_key'); out[key] = value
        return out
    def invalid(unused): raise ValueError('nonfinite_json')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    def walk(item, depth=0):
        need(depth <= 64, 'json_depth')
        if isinstance(item, float): need(math.isfinite(item), 'nonfinite_json')
        elif isinstance(item, (dict, list)):
            for child in item.values() if isinstance(item, dict) else item: walk(child, depth+1)
    walk(value); return value


def load_numerics():
    path = Path(__file__).absolute().with_name('source_numerics.py')
    raw = pinned_bytes(path, NUMERICS_SHA, 128*1024)
    module = types.ModuleType('_fcstab_private_source_numerics'); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def manifest_entries(manifest, ids, policy):
    need(type(manifest) is dict and manifest.get('schema_version') == 'fcstab-source-v1'
         and manifest.get('task_id') == 'FCSTAB-001'
         and manifest.get('dataset_id') == 'ABIDE_pcp/cpac/filt_noglobal/rois_cc200', 'source_manifest_schema')
    rows = manifest.get('files')
    need(type(rows) is list and len(rows) == policy.file_count
         and manifest.get('participant_file_ids') == ids, 'source_manifest_membership')
    paths, indexes, subjects, ordered, roles, total = set(), set(), set(), [], {}, 0
    for row in rows:
        need(type(row) is dict, 'source_row')
        path = row.get('path'); relative(path)
        need(path not in paths, 'duplicate_source_path'); paths.add(path)
        size = row.get('size_bytes')
        need(type(size) is int and 0 < size <= policy.member_cap and digest(row.get('sha256')), 'source_identity')
        total += size; need(total <= policy.source_cap, 'aggregate_source_cap')
        for key, width in (('md5', 32), ('git_blob_sha1', 40)):
            if key in row: need(digest(row[key], width), 'secondary_source_identity')
        role = row.get('role'); need(type(role) is str, 'source_role'); roles[role] = roles.get(role, 0)+1
        if role == 'roi_timeseries':
            fid, sid, index = row.get('file_id'), row.get('subject_id'), row.get('phenotype_row_index')
            need(fid in ids and path == f'roi/{fid}_rois_cc200.1D', 'source_file_id')
            need(type(sid) is str and sid == str(int(fid.split('_')[1])) and sid not in subjects, 'source_subject')
            need(type(index) is int and 0 <= index < policy.phenotype_rows and index not in indexes, 'source_row_index')
            subjects.add(sid); indexes.add(index); ordered.append(fid)
        elif role == 'phenotype': need(path == PHENOTYPE, 'phenotype_path')
        elif role == 'provenance_abide_notice': need(path == NOTICE, 'notice_path')
        else: raise ValueError('source_role')
    need(roles == {'roi_timeseries': policy.roi_count, 'phenotype': 1, 'provenance_abide_notice': 1}, 'source_role_counts')
    need(ordered == ids and total == policy.source_bytes, 'source_totals')
    need(type(manifest.get('source_file_count')) is int and manifest['source_file_count'] == policy.file_count
         and type(manifest.get('source_bytes')) is int and manifest['source_bytes'] == total, 'source_declared_totals')
    need(not any(str(parent) in paths for name in paths for parent in relative(name).parents), 'source_path_collision')
    return rows


def inventory(root, rows):
    wanted = {r['path'] for r in rows} | {'source_manifest.json'}
    directories = {str(p) for path in wanted for p in relative(path).parents if str(p) != '.'}
    files, found_dirs, pending = set(), set(), [root]
    while pending:
        folder = pending.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                path = Path(entry.path); rel = path.relative_to(root).as_posix(); mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    need(rel in directories, 'unexpected_source_directory'); found_dirs.add(rel); pending.append(path)
                else:
                    need(stat.S_ISREG(mode) and rel in wanted, 'unexpected_or_special_source'); files.add(rel)
    need(files == wanted and found_dirs == directories, 'closed_source_inventory')


@contextmanager
def member(root, row, expected=None, *, consumed=False):
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
        if consumed:
            stream.seek(0); h = hashlib.sha256(); count = 0
            while True:
                block = stream.read(min(65536, row['size_bytes']-count+1))
                if not block: break
                count += len(block); need(count <= row['size_bytes'], 'postconsumption_overrun'); h.update(block)
            need(count == row['size_bytes'] and h.hexdigest() == row['sha256'], 'postconsumption_digest')


def phenotype_rows(raw, records, policy):
    text = raw.decode('utf-8-sig', errors='strict'); need('\0' not in text, 'phenotype_nul')
    old = csv.field_size_limit(); csv.field_size_limit(65536)
    try: table = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    finally: csv.field_size_limit(old)
    need(len(table) == policy.phenotype_rows+1, 'phenotype_row_count')
    columns = table[0]
    need(0 < len(columns) <= 512 and len(columns) == len(set(columns))
         and all(name or index == 0 for index, name in enumerate(columns))
         and {'SUB_ID', 'FILE_ID', *FIELDS} <= set(columns), 'phenotype_header')
    by_index = {r['phenotype_row_index']: r for r in records if r['role'] == 'roi_timeseries'}
    selected_ids = {r['file_id'] for r in by_index.values()}
    seen_subjects, seen_named, selected, ledger = set(), set(), {}, []
    for index, values in enumerate(table[1:]):
        need(len(values) == len(columns), 'phenotype_width')
        row = dict(zip(columns, values)); token, fid = row['SUB_ID'], row['FILE_ID']
        need(re.fullmatch('[0-9]{1,32}', token) is not None, 'phenotype_subject_token')
        sid = str(int(token)); need(sid not in seen_subjects, 'phenotype_duplicate_subject'); seen_subjects.add(sid)
        if fid != 'no_filename':
            need(re.fullmatch('[A-Za-z][A-Za-z0-9_]*_[0-9]{7}', fid) is not None
                 and fid not in seen_named, 'phenotype_duplicate_or_invalid_file'); seen_named.add(fid)
        source = by_index.get(index)
        if source is not None:
            need(fid == source['file_id'] and sid == source['subject_id'], 'phenotype_selected_join')
        else: need(fid not in selected_ids, 'phenotype_selected_row_index')
        receipt = dict(phenotype_row_index=index, file_id=fid, subject_id=sid, source_subject_id_token=token,
                       selected_derivative=source is not None, source_path=None if source is None else source['path'],
                       tokens={key: row[key] for key in FIELDS})
        ledger.append(receipt)
        if source is not None: selected[fid] = receipt
    need(len(selected) == policy.roi_count and len(seen_named) == policy.named_phenotype_rows
         and len(ledger)-len(seen_named) == policy.no_filename_rows, 'phenotype_full_and_selected_counts')
    return columns, ledger, selected


def parse_roi(raw, policy):
    text = raw.decode('ascii', errors='strict'); need('\0' not in text, 'roi_nul')
    lines = text.splitlines(); need(len(lines) == policy.frames+1, 'roi_frame_count')
    header = lines[0]
    need(header.split('\t') == [f'#{i}' for i in range(1, policy.columns+1)], 'roi_original_header')
    need(all(line.strip() and '#' not in line and len(line.split()) == policy.columns for line in lines[1:]),
         'roi_width_or_skipped_row')
    try: values = np.loadtxt(io.StringIO('\n'.join(lines[1:])), dtype=np.float64, comments=None, ndmin=2)
    except ValueError: raise ValueError('roi_numeric_parse') from None
    need(values.shape == (policy.frames, policy.columns) and bool(np.isfinite(values).all()), 'roi_nonfinite_or_shape')
    return np.ascontiguousarray(values), dict(n_frames=policy.frames, n_columns=policy.columns, L=policy.frames//2,
             header=header, header_sha256=hashlib.sha256(header.encode('ascii')).hexdigest(),
             source_column_ids=list(range(1, policy.columns+1)), all_finite=True)


def _reconstruct(data_dir, method_path, schema_path, manifest_path, subject_ids_path, policy):
    need(type(policy) is Policy, 'explicit_private_policy')
    for pin in (policy.source_sha, policy.method_sha, policy.schema_sha, policy.ids_sha, NUMERICS_SHA):
        need(digest(pin), 'unfrozen_authority')
    root = safe_path(data_dir); need(root.is_dir(), 'source_root')
    documents = [(manifest_path, policy.source_sha), (root/'source_manifest.json', policy.source_sha),
                 (method_path, policy.method_sha), (schema_path, policy.schema_sha), (subject_ids_path, policy.ids_sha)]
    packed = [pinned_bytes(path, pin, policy.metadata_cap) for path, pin in documents]
    need(packed[0] == packed[1], 'internal_manifest')
    manifest, method, schema = map(strict_json, (packed[0], packed[2], packed[3]))
    need(type(method) is dict and type(schema) is dict and method.get('task_id') == schema.get('task_id') == 'FCSTAB-001',
         'public_contract_identity')
    ids = packed[4].decode('ascii').splitlines()
    need(len(ids) == policy.roi_count and len(set(ids)) == len(ids)
         and all(re.fullmatch('Pitt_[0-9]{7}', sid) for sid in ids), 'public_literal_ids')
    records = manifest_entries(manifest, ids, policy); inventory(root, records)
    signatures = {}; read_bytes = 0
    for row in records:
        with member(root, row) as (raw, sig): signatures[row['path']] = sig; read_bytes += len(raw)
    need(read_bytes == policy.source_bytes, 'full_authentication_total')
    pheno = next(r for r in records if r['role'] == 'phenotype')
    with member(root, pheno, signatures[pheno['path']], consumed=True) as (raw, _):
        columns, ledger, selected = phenotype_rows(raw, records, policy)
    read_bytes += 2*pheno['size_bytes']
    persons, raw_arrays = {}, []
    for row in records:
        if row['role'] == 'phenotype': continue
        with member(root, row, signatures[row['path']], consumed=True) as (raw, _):
            if row['role'] == 'roi_timeseries':
                array, structural = parse_roi(raw, policy); fid = row['file_id']
                raw_arrays.append(array)
                persons[fid] = dict(source_path=row['path'], source_sha256=row['sha256'], subject_id=row['subject_id'],
                                    phenotype_row_index=row['phenotype_row_index'], tokens=selected[fid]['tokens'], **structural)
        read_bytes += 2*row['size_bytes']
    need(list(persons) == ids and read_bytes == 3*policy.source_bytes, 'complete_source_consumption')
    raw_values = np.ascontiguousarray(np.stack(raw_arrays))
    primitives = load_numerics().reconstruct(raw_values)
    for index, fid in enumerate(ids):
        persons[fid]['segment_support'] = {name: primitives['segment_support'][index, k].tolist()
                                          for k, name in enumerate(primitives['segment_ids'])}
        persons[fid]['exact_constant_mask'] = {name: primitives['exact_constant_mask'][index, k].tolist()
                                              for k, name in enumerate(primitives['segment_ids'])}
    inventory(root, records)
    for row in records:
        need(signature(safe_path(root/row['path']).lstat()) == signatures[row['path']], 'source_changed_after_consumption')
    for (path, pin), expected in zip(documents, packed):
        need(pinned_bytes(path, pin, policy.metadata_cap) == expected, 'public_metadata_changed')
    return dict(status='complete', participant_file_ids=ids, subject_ids=[persons[fid]['subject_id'] for fid in ids],
                raw=raw_values, persons=persons, phenotype_columns=columns, phenotype_ledger=ledger,
                source_files=records, source_manifest=manifest, method=method, schema=schema, **primitives,
                pins=dict(source_manifest_sha256=policy.source_sha, method_contract_sha256=policy.method_sha,
                          output_schema_sha256=policy.schema_sha, subject_ids_sha256=policy.ids_sha),
                source_observed=dict(n_source_files=len(records), source_bytes=policy.source_bytes,
                    n_selected_derivatives=len(ids), total_frames=policy.frames*len(ids),
                    n_phenotype_rows=len(ledger), n_named_phenotype_rows=policy.named_phenotype_rows,
                    n_no_filename_rows=policy.no_filename_rows, phenotype_columns=columns, phenotype_ledger=ledger,
                    persons=persons, segment_ids=primitives['segment_ids'], roi_ids=primitives['roi_ids'].tolist(),
                    common_roi_mask=primitives['common_roi_mask'].tolist(),
                    clock=dict(TR_verified=False, frame_order='original source row order')),
                authentication=dict(full_source_read_passes=3, source_bytes_read=read_bytes,
                    all_members_authenticated_before_parse=True, consumed_bytes_pinned=True,
                    postconsumption_same_descriptor_checksum=True, closed_internal_bundle_members=len(records)+1),
                selections_computed=False, downstream_endpoints_computed=False)


def reconstruct(data_dir='/app/data/fcstab', method_path='/app/method_contract.json',
                schema_path='/app/output_schema.json', manifest_path='/app/source_manifest.json',
                subject_ids_path='/app/subject_ids.txt'):
    """Full fixed cohort only. No environment-authority pin or partial bypass."""
    return _reconstruct(data_dir, method_path, schema_path, manifest_path, subject_ids_path,
                        Policy(SOURCE_SHA, METHOD_SHA, SCHEMA_SHA, IDS_SHA))
