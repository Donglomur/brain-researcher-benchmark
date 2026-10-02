"""Independent FCSTAB oracle source loader; import performs no source I/O.

Generic descriptor/hash safeguards follow earlier repairs. Scientific table
parsing is separate from the private reference: explicit token-to-float rows
and DictReader phenotype joins. The public math kernel is authenticated separately before oracle computation;
this loader returns original arrays and identity/metadata only.
Two source passes authenticate all members before any scientific parsing.
Immutable consumed buffers are authoritative; final stat checks detect common
changes, not arbitrary same-inode rewrites hidden by timestamp granularity.
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
import sys
import types

import numpy as np

SOURCE_SHA = 'c57fed19c165e8a606c2b6a9aef89099103a2642d6ab54b93bf525d71ea46171'
METHOD_SHA = '004a396e4f4f37db956083939c84465819b7d3cd1a69569721c39e7884734ee4'
SCHEMA_SHA = 'bedafa3a91bcb6d6b83dd3ae6d4f2d4d9f7a58cc1f65631be3e5e7e86a47fadf'
KERNEL_SHA = 'a58264a5bb3ffd82b291434b2ca22843c276a42dab66d5e5abe220eb77ed7a49'
PHENOTYPE = 'Phenotypic_V1_0b_preprocessed1.csv'
NOTICE = 'provenance/nilearn_0_13_1_ABIDE_pcp.rst'
TOKEN_FIELDS = ('SITE_ID', 'EYE_STATUS_AT_SCAN')
SUBJECT_IDS_SHA = '7645fc4276e63ed4f09e4135bac9d38da3b036a2e4e522fae432ae490d4d28cb'


@dataclass(frozen=True)
class Policy:
    source_sha: str = SOURCE_SHA
    method_sha: str = METHOD_SHA
    schema_sha: str = SCHEMA_SHA
    kernel_sha: str = KERNEL_SHA
    members: int = 42
    source_bytes: int = 16147721
    subjects: int = 40
    phenotype_rows: int = 1112
    phenotype_named: int = 1035
    subject_ids_sha: str = SUBJECT_IDS_SHA
    columns: int = 200
    total_frames: int = 7840
    frame_min: int = 196
    frame_max: int = 196
    member_cap: int = 1000000
    document_cap: int = 4 * 1024**2


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe_path(value):
    text = os.fspath(value)
    require(type(text) is str and text.startswith('/') and '\0' not in text
            and all(p not in ('.', '..') for p in text.split('/')), 'unsafe_absolute_path')
    path = Path(text)
    for node in (*reversed(path.parents), path):
        if os.path.lexists(node):
            mode = node.lstat().st_mode
            require(not stat.S_ISLNK(mode), 'linked_path')
            if node != path:
                require(stat.S_ISDIR(mode), 'non_directory_parent')
    return path


def relative_path(text):
    require(type(text) is str and text and not text.startswith('/')
            and '\\' not in text and '\0' not in text and ':' not in text
            and all(p not in ('', '.', '..') for p in text.split('/')), 'source_relative_path')
    return PurePosixPath(text)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def opened(path):
    path = safe_path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), 'source_not_regular')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:-1]:
            successor = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=directory)
            os.close(directory)
            directory = successor
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'source_open_changed')
        yield stream, before
        require(identity(os.fstat(stream.fileno())) == identity(before), 'source_consumption_changed')
        require(identity(safe_path(path).lstat()) == identity(before), 'source_path_changed')


def hashed_bytes(path, expected, cap):
    require(type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected), 'unfrozen_pin')
    with opened(path) as (stream, info):
        require(0 < info.st_size <= cap, 'document_size')
        raw = stream.read(cap + 1)
        require(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == expected,
                'document_sha256')
    return raw


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def bad(unused):
        raise ValueError('nonfinite_json')
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=bad)
    def visit(item, depth=0):
        require(depth <= 64, 'json_depth')
        if isinstance(item, float):
            require(math.isfinite(item), 'nonfinite_json')
        if isinstance(item, (dict, list)):
            for child in item.values() if isinstance(item, dict) else item:
                visit(child, depth + 1)
    visit(value)
    return value


def load_kernel(path='/app/selection_kernel.py', pin=KERNEL_SHA):
    """Authenticate source text before execution; no cached pyc import route."""
    raw = hashed_bytes(path, pin, 128 * 1024)
    name = '_fcstab_authenticated_public_kernel'
    module = types.ModuleType(name)
    module.__file__ = str(path)
    previous = sys.modules.get(name)
    sys.modules[name] = module  # dataclass resolves its own module at definition.
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


def validate_manifest(manifest, policy):
    require(type(manifest) is dict and manifest.get('schema_version') == 'fcstab-source-v1'
            and manifest.get('task_id') == 'FCSTAB-001'
            and manifest.get('dataset_id') == 'ABIDE_pcp/cpac/filt_noglobal/rois_cc200', 'manifest_schema')
    rows, ids = manifest.get('files'), manifest.get('participant_file_ids')
    require(type(rows) is list and len(rows) == policy.members and type(ids) is list
            and len(ids) == policy.subjects and all(type(s) is str for s in ids)
            and len(set(ids)) == len(ids), 'manifest_membership')
    require(all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*_[0-9]{7}', s) for s in ids), 'literal_FILE_ID')
    paths, indexes, subjects, ordered, roles = set(), set(), set(), [], {}
    total = 0
    for row in rows:
        require(type(row) is dict, 'manifest_row')
        path = row.get('path')
        relative_path(path)
        require(path not in paths and path != 'source_manifest.json', 'source_duplicate_path')
        paths.add(path)
        size = row.get('size_bytes')
        require(type(size) is int and 0 < size <= policy.member_cap, 'source_size')
        total += size
        require(total <= policy.source_bytes, 'source_total_cap')
        for field, length in (('sha256', 64), ('md5', 32), ('git_blob_sha1', 40)):
            if field == 'sha256' or field in row:
                require(type(row.get(field)) is str and re.fullmatch(f'[0-9a-f]{{{length}}}', row[field]),
                        'source_digest_identity')
        role = row.get('role')
        require(type(role) is str, 'source_role')
        roles[role] = roles.get(role, 0) + 1
        if role == 'roi_timeseries':
            fid, sid, index = row.get('file_id'), row.get('subject_id'), row.get('phenotype_row_index')
            require(fid in ids and path == f'roi/{fid}_rois_cc200.1D', 'source_FILE_ID_path')
            require(type(sid) is str and sid == str(int(fid.rsplit('_', 1)[1])) and sid not in subjects,
                    'source_SUB_ID')
            require(type(index) is int and 0 <= index < policy.phenotype_rows and index not in indexes,
                    'source_row_index')
            subjects.add(sid); indexes.add(index); ordered.append(fid)
        elif role == 'phenotype':
            require(path == PHENOTYPE, 'phenotype_path')
        elif role == 'provenance_abide_notice':
            require(path == NOTICE, 'notice_path')
        else:
            raise ValueError('source_role')
    require(roles == {'phenotype': 1, 'roi_timeseries': policy.subjects, 'provenance_abide_notice': 1}
            and ordered == ids and total == policy.source_bytes, 'source_complete_inventory')
    require(type(manifest.get('source_file_count')) is int and manifest['source_file_count'] == len(rows)
            and type(manifest.get('source_bytes')) is int and manifest['source_bytes'] == total,
            'manifest_totals')
    require(not any(str(p) in paths for path in paths for p in PurePosixPath(path).parents),
            'source_path_collision')
    return rows, ids


def closed_inventory(root, records):
    files = {r['path'] for r in records} | {'source_manifest.json'}
    folders = {str(p) for f in files for p in relative_path(f).parents if str(p) != '.'}
    observed_files, observed_folders, stack = set(), set(), [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                key = Path(entry.path).relative_to(root).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    require(key in folders, 'unexpected_source_directory')
                    observed_folders.add(key); stack.append(Path(entry.path))
                else:
                    require(stat.S_ISREG(mode) and key in files, 'unexpected_source_file')
                    observed_files.add(key)
    require(observed_files == files and observed_folders == folders, 'closed_inventory')


@contextmanager
def source_member(root, row, signature=None):
    with opened(root / row['path']) as (stream, info):
        current = identity(info)
        require(signature is None or current == signature, 'source_identity_changed')
        require(info.st_size == row['size_bytes'], 'source_length')
        raw = stream.read(row['size_bytes'] + 1)
        require(len(raw) == row['size_bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'source_hash')
        if 'md5' in row:
            require(hashlib.md5(raw).hexdigest() == row['md5'], 'source_md5')
        if 'git_blob_sha1' in row:
            require(hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() == row['git_blob_sha1'],
                    'source_git_blob')
        yield raw, current


def decode_phenotype(raw, records, policy):
    """DictReader joins, with a separate literal-row width/count guard."""
    text = raw.decode('utf-8-sig')
    require('\0' not in text, 'phenotype_nul')
    previous = csv.field_size_limit()
    csv.field_size_limit(65536)
    try:
        literal = list(csv.reader(io.StringIO(text, newline=''), strict=True))
        require(len(literal) == policy.phenotype_rows + 1 and literal[0]
                and all(len(r) == len(literal[0]) for r in literal[1:]), 'phenotype_literal_rows')
        table = csv.DictReader(io.StringIO(text, newline=''), strict=True)
        header = table.fieldnames
        require(header and len(header) <= 512 and len(set(header)) == len(header)
                and all(label or i == 0 for i, label in enumerate(header))
                and {'SUB_ID', 'FILE_ID', *TOKEN_FIELDS}.issubset(header), 'phenotype_columns')
        rows = list(table)
    finally:
        csv.field_size_limit(previous)
    require(len(rows) == policy.phenotype_rows, 'phenotype_count')
    wanted = {r['phenotype_row_index']: r for r in records if r['role'] == 'roi_timeseries'}
    wanted_ids = {r['file_id'] for r in wanted.values()}
    ledger, selected, subjects, named = [], {}, set(), set()
    for index, row in enumerate(rows):
        require(set(row) == set(header) and all(type(v) is str for v in row.values()), 'phenotype_width')
        original_subject, fid = row['SUB_ID'], row['FILE_ID']
        require(re.fullmatch(r'[0-9]{1,32}', original_subject) is not None, 'phenotype_SUB_ID')
        sid = str(int(original_subject))
        require(sid not in subjects, 'duplicate_SUB_ID')
        subjects.add(sid)
        if fid != 'no_filename':
            require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*_[0-9]{7}', fid) is not None
                    and fid not in named, 'duplicate_or_invalid_FILE_ID')
            named.add(fid)
        record = wanted.get(index)
        if record is None:
            require(fid not in wanted_ids, 'selected_phenotype_row_index')
        else:
            require(fid == record['file_id'] and sid == record['subject_id'], 'phenotype_exact_join')
        entry = dict(phenotype_row_index=index, file_id=fid, subject_id=sid,
                     source_subject_id_token=original_subject,
                     tokens={k: row[k] for k in TOKEN_FIELDS},
                     selected_derivative=record is not None,
                     source_path=None if record is None else record['path'])
        ledger.append(entry)
        if record is not None:
            selected[fid] = entry
    require(len(selected) == policy.subjects and len(named) == policy.phenotype_named, 'phenotype_scope')
    return header, ledger, selected


def decode_roi(raw, policy):
    lines = raw.decode('ascii').splitlines()
    require(len(lines) >= 2 and lines[0] == '\t'.join(f'#{i}' for i in range(1, policy.columns + 1)),
            'ROI_header')
    n = len(lines) - 1
    require(policy.frame_min <= n <= policy.frame_max, 'ROI_frame_count')
    values = np.empty((n, policy.columns), dtype=np.float64, order='C')
    for i, line in enumerate(lines[1:]):
        fields = line.split()
        require(len(fields) == policy.columns and '#' not in line and '\0' not in line, 'ROI_row_width')
        try:
            values[i] = [float(token) for token in fields]
        except ValueError:
            raise ValueError('ROI_numeric_token') from None
    require(bool(np.isfinite(values).all()), 'ROI_nonfinite')
    return values, hashlib.sha256(lines[0].encode('ascii')).hexdigest()


def load(data_dir='/app/data/fcstab', manifest_path='/app/source_manifest.json',
         method_path='/app/method_contract.json', schema_path='/app/output_schema.json',
         subject_ids_path='/app/subject_ids.txt', *, policy=None, progress=None):
    policy = Policy() if policy is None else policy
    require(type(policy) is Policy, 'source_policy')
    root = safe_path(data_dir)
    require(root.is_dir(), 'source_root')
    docs = [(safe_path(manifest_path), policy.source_sha), (root/'source_manifest.json', policy.source_sha),
            (safe_path(method_path), policy.method_sha), (safe_path(schema_path), policy.schema_sha),
            (safe_path(subject_ids_path), policy.subject_ids_sha)]
    saved = [hashed_bytes(path, pin, policy.document_cap) for path, pin in docs]
    require(saved[0] == saved[1], 'manifest_copies')
    manifest, method, schema = [strict_json(saved[i]) for i in (0, 2, 3)]
    require(type(method) is dict and type(schema) is dict, 'contract_objects')
    records, ids = validate_manifest(manifest, policy)
    require(saved[4].decode('ascii').splitlines() == ids, 'subject_ids_exact_order')
    closed_inventory(root, records)
    signatures, byte_count = {}, 0
    for record in records:
        with source_member(root, record) as (raw, sig):
            signatures[record['path']] = sig
            byte_count += len(raw)
    require(byte_count == policy.source_bytes, 'first_pass_total')
    pheno = next(r for r in records if r['role'] == 'phenotype')
    with source_member(root, pheno, signatures[pheno['path']]) as (raw, _):
        columns, ledger, selected = decode_phenotype(raw, records, policy)
        byte_count += len(raw)
    persons, signals, subject_ids, frames = {}, [], [], 0
    for record in records:
        if record['role'] == 'phenotype':
            continue
        with source_member(root, record, signatures[record['path']]) as (raw, _):
            byte_count += len(raw)
            if record['role'] != 'roi_timeseries':
                continue
            values, header_sha = decode_roi(raw, policy)
            fid = record['file_id']
            persons[fid] = dict(subject_id=record['subject_id'], phenotype_row_index=record['phenotype_row_index'],
                source_path=record['path'], source_sha256=record['sha256'], header_sha256=header_sha,
                header='\t'.join(f'#{i}' for i in range(1, policy.columns+1)),
                tokens=dict(selected[fid]['tokens']), source_column_ids=list(range(1, policy.columns+1)),
                n_frames=values.shape[0], n_columns=values.shape[1], L=values.shape[0]//2, all_finite=True)
            signals.append(values); subject_ids.append(record['subject_id'])
            frames += values.shape[0]
            if progress is not None:
                progress(len(persons), len(ids))
    require(frames == policy.total_frames and byte_count == 2 * policy.source_bytes, 'complete_frames_and_passes')
    closed_inventory(root, records)
    for record in records:
        require(identity(safe_path(root/record['path']).lstat()) == signatures[record['path']],
                'source_changed_after_consumption')
    for (path, pin), expected in zip(docs, saved):
        require(hashed_bytes(path, pin, policy.document_cap) == expected, 'document_changed')
    return dict(status='complete', participant_file_ids=ids, subject_ids=subject_ids,
        raw=np.stack(signals), persons=persons, phenotype_ledger=ledger, selected=selected,
        source_files=[dict(r) for r in records], method=method, schema=schema,
        pins=dict(source_manifest_sha256=policy.source_sha, method_contract_sha256=policy.method_sha,
                  output_schema_sha256=policy.schema_sha, subject_ids_sha256=policy.subject_ids_sha),
        source_observed=dict(n_source_files=len(records), source_bytes=policy.source_bytes,
            n_phenotype_rows=len(ledger), n_named_phenotype_rows=policy.phenotype_named,
            n_no_filename_rows=len(ledger)-policy.phenotype_named, n_selected_derivatives=len(ids),
            total_frames=frames, phenotype_columns=columns, phenotype_ledger=ledger,
            persons=persons, clock=dict(TR_verified=False, frame_order='original source row order')),
        authentication=dict(full_source_passes=2, source_bytes_read=byte_count, postconsumption_identity_check=True))
