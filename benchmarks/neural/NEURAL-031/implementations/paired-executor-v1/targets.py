"""Operator-only, source-bound legacy target conversion; never a candidate tool.

prepare_targets authenticates the three fixed original operands before decoding.
The unbound in-memory seam is for generated controls and conveys no source
authority. Authentic conversion requires separately admitted operator execution.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
import types
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE_METADATA = {'bytes': 10723, 'sha256': 'fd469f56e97e1e352342665d8d9f26bd0e79560a6d6557b82751d1e8596f8188'}
TARGET_KEYS = ('rowid', 'mouse', 'y', 'request', 'observed', 'baseline_new', 'compartment')
CENSUS_KEYS = {'rowid', 'member_index0', 'source_row0', 'source_member', 'mouse_id',
              'FOV', 'session', 'compartment', 'dendrite_id', 'baseline_new', 'request',
              'target_observed', 'baseline_reasons', 'target_reasons',
              'local_missing', 'coincident_missing'}
BASE_REASONS = {'baseline_eliminated_spine', 'baseline_absent', 'baseline_shaft_spine',
                'baseline_nonfinite', 'baseline_not_positive'}
TARGET_REASONS = {'followup_eliminated_spine', 'followup_absent', 'followup_new_spine',
                  'followup_shaft_spine', 'followup_nonfinite', 'followup_negative',
                  'ratio_nonfinite'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def read_pinned(path, expected, cap):
    """Read bounded regular bytes, then authenticate before any decoding."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= cap, 'Bounded regular source file')
        body = handle.read(cap + 1)
        need(len(body) == info.st_size and len(body) <= cap, 'Stable bounded source extent')
    need(pin(body) == expected, 'Exact independent source bytes and SHA-256 required')
    return body


def sources():
    return decode(read_pinned(HERE / 'TARGET_SOURCES.json', SOURCE_METADATA, 32768))


def endpoint():
    """Capture the unchanged accepted scoring validator by its independent pin."""
    source = sources()['endpoint']
    need(source['relative'] == '../ratio-scoring-v1/endpoint.py', 'Fixed endpoint dependency')
    path = HERE.parent / 'ratio-scoring-v1/endpoint.py'
    body = read_pinned(path, {key: source[key] for key in ('bytes', 'sha256')}, 65536)
    module = types.ModuleType('_neural031_target_bridge_endpoint')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def decode_legacy_npz(np, body):
    """Bounded numeric format parser only; this does not authenticate source bytes."""
    need(type(body) is bytes and 0 < len(body) <= 262144, 'Bounded target archive bytes')
    result = {}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        need(sorted(item.filename for item in entries) == sorted(key + '.npy' for key in TARGET_KEYS),
             'Exactly seven unique original target arrays')
        for item in entries:
            need(0 < item.file_size <= 16384 and not item.flag_bits & 1 and
                 item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                 'Bounded ordinary numeric archive entry')
            with archive.open(item) as entry:
                raw = entry.read(16385)
            need(len(raw) == item.file_size and len(raw) <= 16384, 'Bounded decompressed target vector')
            stream = io.BytesIO(raw)
            version = np.lib.format.read_magic(stream)
            need(version in ((1, 0), (2, 0)), 'Original numeric NPY format')
            header = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                      else np.lib.format.read_array_header_2_0)
            shape, fortran_order, dtype = header(stream, max_header_size=1024)
            key = item.filename[:-4]
            expected_dtype = '<f8' if key == 'y' else '<i8'
            need(shape == (1143,) and fortran_order is False and dtype.str == expected_dtype and
                 not dtype.hasobject, 'Exact original 1143-row float64/int64 target geometry')
            need(len(raw) - stream.tell() == 1143 * 8, 'Exact numeric vector payload, no trailing bytes')
            result[key] = np.frombuffer(raw, dtype=dtype, count=1143, offset=stream.tell()).copy()
    return result


def decode_census(body):
    """Strict JSONL parser only; no authenticity claim or target reconstruction."""
    need(type(body) is bytes and 0 < len(body) <= 1048576, 'Bounded full row census')
    lines = body.splitlines()
    need(len(lines) == 1143 and all(0 < len(line) <= 8192 for line in lines),
         'All 1143 nonempty bounded original census rows')
    return [decode(line) for line in lines]


def _reason_list(value, allowed):
    need(type(value) is list and all(type(item) is str and item in allowed for item in value) and
         len(value) == len(set(value)), 'Known nonexclusive source reasons without duplicates')


def build_unbound_target(np, arrays, census, support):
    """Validate generated/in-memory operands; callers receive no provenance receipt.

    Ratios are copied from legacy y. Their source formula is pinned upstream;
    baseline/follow-up volumes do not exist in these operands for re-division.
    """
    ep = endpoint()
    ep.validate_support(support)
    source = sources()
    need(type(arrays) is dict and set(arrays) == set(TARGET_KEYS), 'Exact original target columns')
    for key, value in arrays.items():
        need(type(value) is np.ndarray and value.shape == (ep.RAW_ROWS,) and
             value.dtype.str == ('<f8' if key == 'y' else '<i8'), 'Exact numeric source vectors')
    need(np.array_equal(arrays['rowid'], np.arange(ep.RAW_ROWS, dtype=np.int64)),
         'All original row IDs exactly once in source order')
    for key in ('request', 'observed', 'baseline_new', 'compartment'):
        need(bool(np.all((arrays[key] == 0) | (arrays[key] == 1))), 'Binary original target fields')
    need(bool(np.all((arrays['mouse'] >= 0) & (arrays['mouse'] < 20))), 'Original mouse index range')
    need(type(census) is list and len(census) == ep.RAW_ROWS, 'Complete source census required')
    rows, current_member, current_local = [], -1, -1
    for rowid, original in enumerate(census):
        need(type(original) is dict and set(original) == CENSUS_KEYS, 'Exact original census schema')
        need(type(original['rowid']) is int and original['rowid'] == rowid and
             type(original['member_index0']) is int and 0 <= original['member_index0'] < 27 and
             type(original['source_row0']) is int and original['source_row0'] >= 0,
             'Original census row/member identities')
        member_index = original['member_index0']
        if member_index != current_member:
            need(member_index == current_member + 1 and original['source_row0'] == 0,
                 'All 27 source members in order with local rows starting at zero')
            current_member, current_local = member_index, -1
        need(original['source_row0'] == current_local + 1, 'No missing, duplicate or reordered source row')
        current_local += 1
        member = source['members'][member_index]
        for key, source_key in (('source_member', 'name'), ('mouse_id', 'mouse_id_from_path'),
                                ('FOV', 'fov_from_path'), ('session', 'session_from_path'),
                                ('compartment', 'compartment_from_path')):
            need(original[key] == member[source_key], 'Exact frozen original source member identity')
        for key in ('request', 'target_observed', 'baseline_new', 'local_missing', 'coincident_missing'):
            need(type(original[key]) is bool, 'Original census flags must remain booleans')
        mouse = int(arrays['mouse'][rowid])
        request, observed = (int(arrays[key][rowid]) for key in ('request', 'observed'))
        new, compartment = (int(arrays[key][rowid]) for key in ('baseline_new', 'compartment'))
        need(original['mouse_id'] == ep.MICE[mouse] and
             original['request'] == bool(request) and original['target_observed'] == bool(observed) and
             original['baseline_new'] == bool(new) and
             compartment == int(original['compartment'] == 'basal'), 'Array/census identity and eligibility join')
        _reason_list(original['baseline_reasons'], BASE_REASONS)
        _reason_list(original['target_reasons'], TARGET_REASONS | {'not_requested'})
        need(bool(original['baseline_reasons']) == (request == 0), 'Baseline reasons define requests')
        if request:
            need('not_requested' not in original['target_reasons'] and
                 bool(original['target_reasons']) == (observed == 0), 'Follow-up reasons define observation only')
        else:
            need(observed == 0 and original['target_reasons'] == ['not_requested'], 'Nonrequested row has no target')
        y = float(arrays['y'][rowid])
        if observed:
            need(request == 1 and math.isfinite(y) and y >= 0, 'Observed original nonnegative ratio; zero retained')
        else:
            need(math.isnan(y), 'Unavailable legacy target must be NaN, never zero or infinity')
        rows.append({'rowid': rowid, 'mouse': mouse, 'request': request, 'observed': observed,
                     'baseline_new': new, 'compartment': compartment, 'y': y if observed else None})
    need(current_member == 26, 'All 27 source members required')
    target = {'schema': 'neural031_ratio_targets_v1', 'candidate_id': 'NEURAL-031',
              'mice': list(ep.MICE), 'rows': rows}
    ep.validate_targets(target, support)  # Unmodified scientific acceptance validator.
    return target


def _write_private(path, body, cap):
    need(0 < len(body) <= cap, 'Bounded private output')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    return pin(body)


def prepare_targets(targets_path, census_path, support_path, output_dir):
    """Authenticate fixed original inputs and emit a fresh private JSON target set."""
    source = sources()
    output_dir = Path(output_dir)
    need(not output_dir.exists() and not output_dir.is_symlink(), 'Fresh private target output directory')
    support_body = read_pinned(support_path, source['public_support'], 131072)
    support = decode(support_body)
    endpoint().validate_support(support)
    archive_body = read_pinned(targets_path, source['target_archive'], 262144)
    census_body = read_pinned(census_path, source['row_census'], 1048576)
    import numpy as np
    target = build_unbound_target(np, decode_legacy_npz(np, archive_body), decode_census(census_body), support)
    body = encoded(target)
    need(len(body) <= 524288, 'Accepted scorer target byte limit')
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    target_pin = _write_private(output_dir / 'targets.json', body, 524288)
    receipt = {'schema': 'neural031_target_bridge_receipt_v1', 'candidate_id': 'NEURAL-031',
               'source_authenticated': True, 'source_metadata': dict(SOURCE_METADATA),
               'inputs': {'targets_npz': pin(archive_body), 'row_census': pin(census_body),
                          'support': pin(support_body)}, 'output': target_pin,
               'raw_rows': 1143, 'mice': 20, 'members': 27, 'request_rows': 774,
               'observed_rows': 731, 'unobserved_requested_rows': 43,
               'unavailable_json_null_rows': 412,
               'observed_zero_rows': sum(row['observed'] and row['y'] == 0 for row in target['rows']),
               'ratio_recomputed': False, 'source_ratio_preserved': True,
               'endpoint': source['endpoint'], 'implementation': pin(Path(__file__).read_bytes()),
               'score_or_candidate_executed': False}
    _write_private(output_dir / 'TARGETS_RECEIPT.json', encoded(receipt), 16384)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets-npz', required=True)
    parser.add_argument('--row-census', required=True)
    parser.add_argument('--support', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        receipt = prepare_targets(args.targets_npz, args.row_census, args.support, args.output)
        print(json.dumps({'status': 'converted', 'target': receipt['output']}))
    except (ValueError, OSError, TypeError, KeyError, OverflowError, zipfile.BadZipFile) as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'error': str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
