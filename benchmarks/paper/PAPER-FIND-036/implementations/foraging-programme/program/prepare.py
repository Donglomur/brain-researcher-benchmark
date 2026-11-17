#!/usr/bin/env python3
"""Future protected preparation of every original FIND036 HW session.

This module does no acquisition, estimation or scoring. Completion is input
preparation only; a separate root/independent admission must authenticate the
whole resulting roster and the complete scientific execution environment.
"""
import argparse
import hashlib
import io
import json
import os
import platform
import re
import secrets
import stat
import struct
import sys
import time
import zipfile
import zlib
from pathlib import Path, PurePosixPath

from common import (TASK, Budget, authenticate_source, authority, descriptor,
                    encode, mkdir_owned, need, ordinary, pin, read, sync, write)

HERE = Path(__file__).resolve().parent
ARCHIVE = {'bytes': 15089711,
           'sha256': 'ed1e4551cc96acff35b895da5c608857c36c448e7b997f6f8fb4f7fefd462f2a'}
CAP_KEYS = {'archive_entries', 'expanded_bytes', 'member_bytes',
            'mat_decoded_bytes', 'numeric_array_bytes', 'receipt_bytes'}
VERSIONS = {'numpy': '2.2.6', 'scipy': '1.15.3', 'scikit_learn': '1.6.1'}
SESSION = re.compile(r'(#.*_\wL)_eventClassificationData\.mat')
NUMERIC_TYPES = {1: ('i1', 1), 2: ('u1', 1), 3: ('i2', 2), 4: ('u2', 2),
                 5: ('i4', 4), 6: ('u4', 4), 7: ('f4', 4), 9: ('f8', 8),
                 12: ('i8', 8), 13: ('u8', 8)}
CLASS_TYPE = {6: 9, 7: 7, 8: 1, 9: 2, 10: 3, 11: 4,
              12: 5, 13: 6, 14: 12, 15: 13}


def zip_count_before_open(raw, cap):
    """Bound ordinary ZIP central-directory materialization; ZIP64 is unqualified."""
    start = max(0, len(raw) - 65557)
    at = raw.rfind(b'PK\x05\x06', start)
    need(at >= 0 and at + 22 <= len(raw), 'ordinary ZIP EOCD required')
    _, disk, cd_disk, local_n, total_n, extent, offset, comment = struct.unpack_from('<4s4H2IH', raw, at)
    need(at + 22 + comment == len(raw) and disk == cd_disk == 0 and local_n == total_n,
         'single-disk complete ZIP; no appended suffix')
    need(total_n not in (0, 65535) and total_n <= cap and extent != 0xffffffff
         and offset != 0xffffffff and offset + extent == at,
         'bounded classic ZIP central directory; ZIP64 unsupported')
    return total_n


def inspect_inventory(infos, caps):
    """Classify every central-directory member, refusing unexplained scientific files."""
    need(0 < len(infos) <= caps['archive_entries'], 'archive entry ceiling')
    need(sum(i.file_size for i in infos) <= caps['expanded_bytes'], 'complete expanded extent ceiling')
    names, tokens, roots, selected, inventory = set(), set(), set(), [], []
    ancillary = {'README', 'README.md', 'README.txt', 'LICENSE', 'LICENSE.md', 'LICENSE.txt'}
    for info in infos:
        name = info.filename
        p = PurePosixPath(name)
        directory = info.is_dir()
        need(type(name) is str and name and name not in names and '\\' not in name
             and '\x00' not in name and not p.is_absolute() and '..' not in p.parts
             and name == p.as_posix() + ('/' if directory else ''), 'safe unique exact member path')
        names.add(name)
        mode = (info.external_attr >> 16) & 0xffff
        kind = stat.S_IFMT(mode)
        need(kind in (0, stat.S_IFDIR if directory else stat.S_IFREG), 'no linked or special ZIP member')
        need(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
             and 0 <= info.file_size <= caps['member_bytes'] and info.compress_size >= 0,
             'unencrypted supported bounded member')
        if directory:
            need(info.file_size == 0, 'directory contains no hidden payload')
            disposition = 'directory'
        elif p.name == '.DS_Store' or p.name.startswith('._'):
            disposition = 'platform_metadata_not_scientific'
        else:
            match = SESSION.fullmatch(p.name)
            if match:
                token = match.group(1)
                need(token not in tokens, 'unique complete source session token')
                tokens.add(token)
                roots.add(p.parent.as_posix())
                selected.append((info, token))
                disposition = 'full_original_classification_MAT'
            else:
                need(p.name in ancillary, 'unexplained nonplatform member; no scientific MAT omission')
                disposition = 'named_ancillary_metadata_only_body_not_separately_admitted'
        inventory.append({'name': name, 'bytes': info.file_size, 'compressed_bytes': info.compress_size,
                          'crc32': f'{info.CRC:08x}', 'compression': info.compress_type,
                          'external_attr': info.external_attr, 'disposition': disposition})
    need(len(selected) == len(tokens) == 40 and len(roots) == 1,
         'exactly40 unique full-session MAT members under one classification root')
    return sorted(selected, key=lambda x: x[0].filename), inventory, next(iter(roots))


def _tag(buf, pos, endian, compressed_unpadded=False):
    need(pos + 8 <= len(buf), 'complete MAT data-element tag')
    small_kind, small_n = struct.unpack_from(endian + 'HH', buf, pos)
    if small_kind and small_n:
        kind = small_kind
        need(1 <= small_n <= 4, 'MAT small-data extent')
        return kind, memoryview(buf)[pos + 4:pos + 4 + small_n], pos + 8
    kind, n = struct.unpack_from(endian + 'II', buf, pos)
    end = pos + 8 + n
    nxt = end if compressed_unpadded and kind == 15 else pos + 8 + ((n + 7) // 8) * 8
    need(end <= len(buf) and nxt <= len(buf), 'MAT payload and padding extent')
    return kind, memoryview(buf)[pos + 8:end], nxt


def _matrix(payload, endian):
    flags_type, flags, pos = _tag(payload, 0, endian)
    need(flags_type == 6 and len(flags) == 8, 'MAT array flags')
    flag = struct.unpack_from(endian + 'I', flags, 0)[0]
    class_id = flag & 0xff
    dim_type, dims, pos = _tag(payload, pos, endian)
    need(dim_type == 5 and len(dims) >= 8 and len(dims) % 4 == 0 and len(dims) <= 128,
         'bounded MAT dimension vector')
    shape = list(struct.unpack(endian + str(len(dims) // 4) + 'i', dims))
    need(all(n >= 0 for n in shape), 'nonnegative MAT dimensions')
    name_type, name_body, pos = _tag(payload, pos, endian)
    need(name_type in (1, 2, 16) and 0 < len(name_body) <= 256, 'bounded MAT variable name')
    name = bytes(name_body).decode('utf-8', errors='strict')
    need('\x00' not in name, 'ordinary MAT variable name')
    result = {'name': name, 'shape': shape, 'class_id': class_id,
              'logical': bool(flag & 0x200), 'complex': bool(flag & 0x800),
              'matrix_payload_bytes': len(payload)}
    if name in ('X', 'y'):
        need(class_id in CLASS_TYPE and not flag & (0x200 | 0x800) and len(shape) == 2,
             'selected variables must be real plain two-dimensional numeric arrays')
        dtype, values, pos = _tag(payload, pos, endian)
        need(dtype == CLASS_TYPE[class_id] and dtype in NUMERIC_TYPES, 'exact selected numeric storage class')
        elements = shape[0] * shape[1]
        need(len(values) == elements * NUMERIC_TYPES[dtype][1] and pos == len(payload),
             'selected MAT dimensions agree with complete numeric payload')
        result['numeric_payload_bytes'] = len(values)
        result['storage_dtype'] = endian + NUMERIC_TYPES[dtype][0]
    return result


def mat_census(raw, decoded_cap, numeric_cap, budget=None):
    """Bound compressed v5/v7 MAT contents before any scientific-array allocation.

    Nonselected fields remain metadata plus preserved original bytes. This is an
    explicitly qualified MAT-v5 profile, not a claim to support uninspected v7.3.
    Decoded cap covers cumulative uncompressed top-level payload materialization.
    """
    need(len(raw) >= 128 and raw[126:128] in (b'IM', b'MI'), 'classic MAT-v5 header; HDF5 unsupported')
    endian = '<' if raw[126:128] == b'IM' else '>'
    need(struct.unpack(endian + 'H', raw[124:126])[0] == 0x100, 'MAT-v5 version')
    pos, decoded, records, names = 128, 0, [], set()
    while pos < len(raw):
        if budget is not None:
            budget.tick()
        kind, payload, pos = _tag(raw, pos, endian, compressed_unpadded=True)
        if kind == 15:
            remaining = decoded_cap - decoded
            need(remaining >= 0, 'MAT decoded ceiling')
            dec = zlib.decompressobj()
            inflated = dec.decompress(payload, remaining + 1)
            if budget is not None:
                budget.reading(len(inflated))
            decoded += len(inflated)
            need(decoded <= decoded_cap and dec.eof and not dec.unused_data and not dec.unconsumed_tail,
                 'bounded complete single compressed MAT element')
            nested, matrix, end = _tag(inflated, 0, endian)
            need(nested == 14 and end == len(inflated), 'single complete compressed MAT matrix')
            row = _matrix(matrix, endian)
        else:
            need(kind == 14, 'top-level MAT matrix or bounded compression only')
            decoded += len(payload) + 8
            need(decoded <= decoded_cap, 'uncompressed MAT decoded ceiling')
            row = _matrix(payload, endian)
        need(row['name'] not in names, 'unique MAT variable names')
        names.add(row['name'])
        records.append(row)
    need(pos == len(raw) and {'X', 'y'} <= names, 'complete MAT source and exact X/y')
    selected = {row['name']: row for row in records if row['name'] in ('X', 'y')}
    r, d = selected['X']['shape']
    ys = selected['y']['shape']
    need(r > 0 and d > 0 and d % 40 == 0 and 1 in ys and ys[0] * ys[1] == r,
         'source event rows, complete40-bin unit features and aligned vector')
    # Conservative selected-array payload/workspace bound; it is not process RSS.
    numeric_bound = 32 * r * d + 128 * r
    need(numeric_bound <= numeric_cap, 'predeclared selected numeric workspace capacity')
    return {'format': 'MAT-v5-bounded-profile', 'endian': endian,
            'variables': records, 'decoded_bytes': decoded,
            'selected_numeric_workspace_bound': numeric_bound, 'source_R': r, 'features': d}


def validate_arrays(x, y, numeric_cap):
    import numpy as np
    need(isinstance(x, np.ndarray) and x.ndim == 2 and x.dtype.kind in 'fiu'
         and x.shape[0] > 0 and x.shape[1] > 0 and x.shape[1] % 40 == 0,
         'finite real event-by-(40*unit) X')
    need(32 * int(x.shape[0]) * int(x.shape[1]) + 128 * int(x.shape[0]) <= numeric_cap,
         'selected numeric workspace capacity')
    need(bool(np.isfinite(x).all()), 'all source features finite')
    need(isinstance(y, np.ndarray) and y.dtype.kind in 'fiu'
         and (y.ndim == 1 or (y.ndim == 2 and 1 in y.shape)), 'numeric y vector')
    source_y = y.reshape(-1)
    need(source_y.size == x.shape[0] and bool(np.isfinite(source_y).all())
         and bool(np.isin(source_y, [1, 2, 3, 4]).all()), 'all source labels1..4 aligned')
    need(bool((np.diff(source_y.astype(np.int64)) >= 0).all()), 'source class-block order')
    keep = (source_y == 3) | (source_y == 4)
    rows = np.flatnonzero(keep).astype(np.int64) + 1
    hw_x = x[keep].astype(np.float64)
    np.clip(hw_x, -5, 5, out=hw_x)
    hw_y = (source_y[keep] == 4).astype(np.int64)
    need(set(hw_y.tolist()) == {0, 1}, 'complete pooled HW session has both classes')
    return hw_x, hw_y, rows


def build_splits(labels, splitter=None, shuffler=None):
    """Persist all five native folds plus operator-only order randomization.

    Test injection allows small independent fixed memberships. Production caller
    verifies the exact sklearn version before using its native source recipe.
    """
    import numpy as np
    need(isinstance(labels, np.ndarray) and labels.ndim == 1 and labels.dtype == np.dtype('int64')
         and len(labels) >= 5 and set(labels.tolist()) == {0, 1}, 'valid complete binary HW labels')
    if splitter is None:
        from sklearn.model_selection import StratifiedKFold
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=622)
    if shuffler is None:
        shuffler = secrets.SystemRandom()
    n = len(labels)
    assignment = np.zeros(n, dtype=np.int64)
    folds = []
    for fold, pair in enumerate(splitter.split(np.zeros((n, 1), dtype=np.uint8), labels), 1):
        need(fold <= 5 and len(pair) == 2, 'exact five-fold partition')
        train, test = (np.asarray(x) for x in pair)
        need(train.ndim == test.ndim == 1 and train.dtype.kind in 'iu' and test.dtype.kind in 'iu'
             and len(train) > 0 and len(test) > 0, 'nonempty integer fold indices')
        tr, te = train.tolist(), test.tolist()
        need(len(set(tr)) == len(tr) and len(set(te)) == len(te)
             and not set(tr) & set(te) and set(tr) | set(te) == set(range(n)),
             'exact disjoint original-row training/test cover')
        need(tr == sorted(tr) and te == sorted(te), 'native original-order fold indices')
        need(not bool((assignment[test] != 0).any()), 'each HW row tested exactly once')
        counts = [int((labels[train] == c).sum()) for c in (0, 1)]
        need(min(counts) > 0, 'both classes in each native training fold')
        assignment[test] = fold
        training_order, query_order = tr.copy(), te.copy()
        shuffler.shuffle(training_order)
        shuffler.shuffle(query_order)
        need(sorted(training_order) == tr and sorted(query_order) == te,
             'private permutations retain exact fold membership')
        folds.append({'fold': fold, 'train_positions0': tr, 'test_positions0': te,
                      'train_order0': training_order, 'query_order0': query_order,
                      'training_class_counts': counts, 'native_supported': True,
                      'nested3_supported': min(counts) >= 3})
    need(len(folds) == 5 and bool((assignment > 0).all()), 'exact5 folds cover every HW row once')
    return assignment, folds, all(f['nested3_supported'] for f in folds)


def _npy(array, cap):
    import numpy as np
    need(array.dtype.kind in 'fi' and array.dtype.itemsize == 8 and array.nbytes + 1024 <= cap,
         'bounded plain64-bit NPY encoding')
    target = io.BytesIO()
    np.save(target, array, allow_pickle=False)
    raw = target.getvalue()
    need(len(raw) <= cap, 'complete bounded NPY')
    return raw


def _bounded_json(value, cap):
    # Iterative encoding rejects an excessive receipt before collecting all bytes.
    out = io.BytesIO()
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False)
    for text in encoder.iterencode(value):
        raw = text.encode('utf-8')
        need(out.tell() + len(raw) + 1 <= cap, 'complete private receipt ceiling')
        out.write(raw)
    out.write(b'\n')
    return out.getvalue()


def prepare(selection, origin, budget=None):
    """One complete preparation under an explicit root-selected authority.

    Partial output is retained as incomplete after failure. PREPARED.json is
    exclusive and written last; it is never an execution/admission authorization.
    """
    need(selection.get('schema') == 'foraging_preparation_authority_v1'
         and selection.get('task_id') == TASK
         and selection.get('selected_by_root') is True
         and selection.get('exclusive_operator_custody') is True
         and selection.get('source_environment_qualified_for_preparation') is True,
         'explicit root-owned source/environment/preparation authority')
    budget = budget if budget is not None else Budget(selection['limits'], origin)
    need(budget.origin == origin and budget.limits == selection['limits'], 'one original clock and complete budget')
    need(ordinary(selection['root_source']) == HERE, 'executing source root equals selected root')
    bodies, source = authenticate_source(HERE, selection['source_manifest'], budget, {'prepare.py', 'common.py'})
    del bodies
    caps = selection['caps']
    need(type(caps) is dict and set(caps) == CAP_KEYS and all(type(v) is int and v > 0 for v in caps.values()),
         'explicit complete preparation capacity profile')
    need(descriptor(selection['archive']) == ARCHIVE, 'exact original Dryad418976/file4552700 archive')
    output = ordinary(selection['output'])
    need(not output.exists(), 'fresh exclusive operator output')
    expected = selection['host_versions']
    need(type(expected) is dict and set(expected) == {'python', *VERSIONS}
         and all(expected[k] == v for k, v in VERSIONS.items())
         and expected['python'] == platform.python_version(), 'pinned preparation Python and numerical stack')
    import numpy as np
    import scipy
    import sklearn
    from scipy.io import loadmat
    need({'numpy': np.__version__, 'scipy': scipy.__version__, 'scikit_learn': sklearn.__version__} == VERSIONS,
         'exact construction library versions; no implicit installation')
    budget.tick()
    raw = read(selection['archive']['path'], ARCHIVE, budget, ARCHIVE['bytes'])
    count = zip_count_before_open(raw, caps['archive_entries'])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        need(len(infos) == count, 'central-directory count agreement')
        selected, inventory, classification_root = inspect_inventory(infos, caps)
        mkdir_owned(output, budget)
        records, seen_ids = [], set()
        for info, token in selected:
            budget.tick()
            # ZipExtFile validates CRC on complete bounded reads; exact original
            # archive hash binds ancillary bodies even though they are not opened.
            budget.reading(info.file_size + 1)
            with archive.open(info) as member:
                body = member.read(info.file_size + 1)
                need(len(body) == info.file_size and not member.read(1), 'complete scientific member and CRC')
            census = mat_census(body, caps['mat_decoded_bytes'], caps['numeric_array_bytes'], budget)
            # The second MAT decoder pass is charged; its maximum expansion was
            # established above, not guessed from the small compressed ZIP size.
            budget.reading(len(body) + census['decoded_bytes'])
            variables = loadmat(io.BytesIO(body), variable_names=['X', 'y'], verify_compressed_data_integrity=True)
            budget.tick()
            need('X' in variables and 'y' in variables, 'exact source variables')
            x, y, source_rows = validate_arrays(variables['X'], variables['y'], caps['numeric_array_bytes'])
            need(variables['X'].shape == (census['source_R'], census['features']), 'decoded X matches bounded census')
            fold_ids, folds, nested3 = build_splits(y)
            session_id = hashlib.sha256(info.filename.encode('utf-8')).hexdigest()[:24]
            need(session_id not in seen_ids, 'unique exact-name session digest')
            seen_ids.add(session_id)
            folder = output / 'sessions' / session_id
            mkdir_owned(folder, budget)
            mat_path = folder / 'original.mat'
            original_mat = {'path': str(mat_path), **write(mat_path, body, budget)}
            prepared = {}
            for name, array in [('X.npy', x), ('y.npy', y), ('source_rows.npy', source_rows), ('fold_ids.npy', fold_ids)]:
                path = folder / name
                prepared[name] = {'path': str(path), **write(path, _npy(array, caps['numeric_array_bytes']), budget)}
            subject = re.match(r'^#(.*?)-', token)
            records.append({'session_id': session_id, 'source_session_token': token,
                            'source_member': info.filename, 'source_R': census['source_R'],
                            'rows': int(x.shape[0]), 'features': int(x.shape[1]),
                            'unit_blocks': int(x.shape[1] // 40), 'original_mat': original_mat,
                            'prepared': prepared, 'folds': folds,
                            'native_supported': True, 'nested3_supported': nested3,
                            'source_subject_token_unverified': subject.group(1) if subject else None,
                            'source_area_token_unverified': token.rsplit('_', 1)[-1],
                            'source_HW_counts': {'avoidance': int((y == 0).sum()), 'escape': int((y == 1).sum())},
                            'original_X_dtype': str(variables['X'].dtype), 'mat_census': census,
                            'upstream_whole_session_normalized': True,
                            'window_seconds': [-1, 1], 'bin_seconds': 0.05,
                            'clip': [-5, 5], 'native_fold_seed': 622,
                            'private_row_maps_candidate_visible': False,
                            'source_rows_are_authenticated_episode_ids': False})
            # Do not accumulate every decoded session in live numeric objects.
            del body, variables, x, y, source_rows, fold_ids, folds, array
    need(len(records) == 40, 'full40 roster before complete preparation receipt')
    prepared_receipt = {'schema': 'foraging_full40_prepared_v1', 'task_id': TASK,
        'source': source, 'archive': {'path': selection['archive']['path'], **ARCHIVE},
        'classification_root': classification_root, 'archive_inventory': inventory,
        'records': records, 'input_preparation_only': True,
        'complete_native_support': all(r['native_supported'] for r in records),
        'complete_nested3_support': all(r['nested3_supported'] for r in records),
        'qualifications': False, 'scientific_admission': False,
        'full_paper_material_completeness': False, 'biological_identity_mapping_authenticated': False,
        'requires_external_natural_exit_admission': True,
        'native_historical_bitwise_parity': False,
        'preprocessing_limit': 'Released whole-session normalization and symmetric filtering are transductive; no causal or train-only raw processing claim.',
        'fold_library_versions': expected, 'caps': caps, 'limits': selection['limits'],
        'origin': origin, 'deadline': budget.end,
        'budget_before_final_receipt': {'read': budget.read, 'write': budget.write, 'retained': budget.retained},
        'clock_before_final_receipt': time.monotonic()}
    final_path = output / 'PREPARED.json'
    final = {'path': str(final_path), **write(final_path, _bounded_json(prepared_receipt, caps['receipt_bytes']), budget)}
    sync(output)
    budget.tick()
    return {'schema': 'foraging_preparation_completion_v1', 'task_id': TASK, 'prepared': final,
            'input_preparation_only': True, 'qualifications': False,
            'origin': origin, 'deadline': budget.end, 'post_durable_clock': time.monotonic(),
            'read_bytes': budget.read, 'write_bytes': budget.write, 'retained_charge_bytes': budget.retained,
            'requires_external_natural_exit_admission': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authority', required=True)
    p.add_argument('--authority-sha256', required=True)
    p.add_argument('--origin', type=float, required=True)
    args = p.parse_args()
    budget = None
    try:
        _, selection, budget = authority(args.authority, args.authority_sha256, args.origin)
        result = prepare(selection, args.origin, budget)
        print(encode(result).decode(), end='')
    except BaseException as exc:
        failure = {'schema': 'foraging_preparation_failure_v1', 'task_id': TASK,
                   'error_type': type(exc).__name__, 'error': str(exc)[:4096],
                   'qualifications': False, 'complete': False, 'origin': args.origin,
                   'observed_clock': time.monotonic(), 'partial_output_must_not_be_admitted': True,
                   'costs': None if budget is None else {'read': budget.read, 'write': budget.write,
                                                       'retained': budget.retained, 'deadline': budget.end}}
        print(encode(failure).decode(), file=sys.stderr, end='')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
