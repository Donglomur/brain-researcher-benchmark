"""Complete seven-trace calibration preparation; no physical-odor inference."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
from fractions import Fraction

from pid_types import Held, inspect_pid_text

SELECT = (0, 1, 14, 17, 18)
NAMES = ('timestamp', 'frame', 'wind', 'odor', 'detector')
ARCHIVE_CAP = 2 * 1024 * 1024
OUTPUT_CAP = 16 * 1024 * 1024
DECIMAL = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?\Z')


def require(ok, code):
    if not ok:
        raise Held(code)


def rational(value):
    return {'numerator': str(value.numerator), 'denominator': str(value.denominator)}


def number(token):
    """Keep exact decimal value and reject silent binary64 under/overflow."""
    if token.lower() in ('', 'nan', '+nan', '-nan', 'inf', '+inf', '-inf',
                         'infinity', '+infinity', '-infinity'):
        return None, 'missing_or_nonfinite'
    match = DECIMAL.fullmatch(token)
    require(match is not None and len(token) <= 128, 'numeric_token_limit_or_syntax')
    exponent = match.group(1)
    require(exponent is None or len(exponent.lstrip('+-')) <= 4, 'numeric_exponent_limit')
    require(exponent is None or abs(int(exponent)) <= 400, 'numeric_exponent_limit')
    exact = Fraction(token)
    approximate = float(token)
    if not math.isfinite(approximate):
        return None, 'binary64_overflow'
    if approximate == 0.0 and exact != 0:
        return None, 'binary64_underflow'
    return exact, None


def command_report(rows, column):
    """Adjacent observed transitions only; invalid rows never get bridged."""
    transitions, episodes = [], []
    active = None
    for i, row in enumerate(rows):
        current = row['values'][column]
        previous = rows[i - 1]['values'][column] if i else None
        if i and current is not None and previous is not None and current != previous:
            transitions.append({'before_row': i, 'after_row': i + 1,
                                'from': int(previous), 'to': int(current),
                                'native_time_bracket_tokens': [rows[i - 1]['tokens'][0], row['tokens'][0]],
                                'clock_increasing': (row['values'][0] is not None and
                                                     rows[i - 1]['values'][0] is not None and
                                                     row['values'][0] > rows[i - 1]['values'][0])})
        if current == 1 and active is None:
            active = {'first_on_row': i + 1,
                      'onset_observed': i > 0 and previous == 0,
                      'onset_after_row': i + 1 if i > 0 and previous == 0 else None}
        if active is not None and current != 1:
            active.update(last_on_row=i, offset_observed=current == 0,
                          offset_after_row=i + 1 if current == 0 else None,
                          ending='observed_off' if current == 0 else 'invalid_command')
            episodes.append(active)
            active = None
    if active is not None:
        active.update(last_on_row=len(rows), offset_observed=False,
                      offset_after_row=None, ending='right_censored')
        episodes.append(active)
    for episode in episodes:
        episode['complete_command_cycle'] = episode['onset_observed'] and episode['offset_observed']
    return {'transitions': transitions, 'on_episodes': episodes,
            'time_semantics': 'Adjacent-sample command transition bracket; not physical odor time.'}


def prepare_trace(body, expected):
    require(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
            'trace_identity')
    profile = inspect_pid_text(body, expected_bytes=len(body))
    require(profile['local_profile_pass'], 'trace_lexical_profile')
    require(profile['counts']['data_rows'] == expected['rows'], 'complete_trace_rows')
    rows, issues = [], []
    # The accepted parser has already checked all line endings, widths and tokens.
    for i, line in enumerate(body.splitlines()[2:], 1):
        tokens = [line.split(b',')[c].decode('ascii') for c in SELECT]
        values, flags = [], []
        for c, token in enumerate(tokens):
            value, issue = number(token.strip(' \t'))
            if issue is None and c == 1 and value.denominator != 1:
                issue, value = 'nonintegral_frame', None
            if issue is None and c in (2, 3) and value not in (0, 1):
                issue, value = 'nonbinary_command', None
            values.append(value)
            flags.append(issue)
            if issue:
                issues.append({'row': i, 'field': NAMES[c], 'code': issue})
        rows.append({'row': i, 'tokens': tokens, 'values': values, 'flags': flags})
    clock_events, frame_events = [], []
    for i in range(1, len(rows)):
        left, right = rows[i - 1]['values'], rows[i]['values']
        if left[0] is not None and right[0] is not None and right[0] <= left[0]:
            clock_events.append({'before_row': i, 'after_row': i + 1,
                                 'kind': 'duplicate' if right[0] == left[0] else 'decreasing'})
        if left[1] is not None and right[1] is not None:
            difference = int(right[1] - left[1])
            if difference != 1:
                frame_events.append({'before_row': i, 'after_row': i + 1,
                                     'delta': difference,
                                     'kind': 'missing_frames' if difference > 1 else
                                             'duplicate' if difference == 0 else 'decreasing'})
    clock = {'duplicate_or_decreasing_pairs': clock_events, 'frame_discontinuities': frame_events,
             'nominal_behavior_hz': 100, 'historical_coordinate': None,
             'arithmetic': 'Exact decimal tokens; historical formula diagnostic, not MATLAB floating-point parity.'}
    all_times = all(row['values'][0] is not None for row in rows)
    if len(rows) >= 2 and all_times and not clock_events:
        first, last = rows[0]['values'][0], rows[-1]['values'][0]
        mean_dt = (last - first) / (len(rows) - 1)
        rate = 1 / mean_dt
        rounded = (rate.numerator * 2 + rate.denominator) // (2 * rate.denominator)
        clock.update(mean_dt=rational(mean_dt), rate_before_rounding=rational(rate), rounded_rate_hz=rounded)
        if rounded > 0 and rows[0]['values'][1] is not None:
            shift = rows[0]['values'][1] / rounded - first
            residuals = [r['values'][0] + shift - r['values'][1] / rounded
                         for r in rows if r['values'][1] is not None]
            clock['historical_coordinate'] = {
                'formula': 'calc_ts = native_ts + first_frame/rounded_rate - first_native_ts',
                'shift': rational(shift), 'first': rational(first + shift), 'last': rational(last + shift),
                'frame_coordinate_residual_min': rational(min(residuals)),
                'frame_coordinate_residual_max': rational(max(residuals)),
                'frame_coordinate_comparison_rows': len(residuals)}
    diagnostic = {'schema': 'fly-complete-pid-trace-diagnostic-v1',
                  'source': expected, 'rows': len(rows), 'all_rows_preserved': True,
                  'selected_fields': list(NAMES), 'numeric_issues': issues, 'clock': clock,
                  'wind': command_report(rows, 2), 'odor': command_report(rows, 3),
                  'physical_odor_offsets': None, 'absolute_concentration_calibrated': False,
                  'scientific_admission': False,
                  'remaining': ['physical_response_rule', 'imaging_alignment', 'animal_identity',
                                'released_derivative_exposure', 'protected_reference_and_baselines']}
    projected = [{'row': r['row'], 'tokens': r['tokens'], 'flags': r['flags']} for r in rows]
    return projected, diagnostic


def checked_archive(body, binding):
    require(len(body) == binding['archive']['bytes'] and len(body) <= ARCHIVE_CAP and
            hashlib.sha256(body).hexdigest() == binding['archive']['sha256'], 'archive_identity')
    members = binding['members']
    require(len(members) == 14 and [m['index'] for m in members] == list(range(14)) and
            [m['role'] for m in members] == ['trace', 'companion'] * 7, 'complete_fixed_member_roles')
    archive = zipfile.ZipFile(io.BytesIO(body))
    try:
        infos = archive.infolist()
        require(len(infos) == 14, 'complete_archive_members')
        names, offsets = set(), set()
        for info, member in zip(infos, members):
            path = PurePosixPath(info.filename)
            require(not path.is_absolute() and '..' not in path.parts and
                    '\\' not in info.filename and '\x00' not in info.filename and
                    not info.is_dir() and info.filename not in names and info.header_offset not in offsets,
                    'archive_member_path_or_alias')
            require(not (info.flag_bits & 1) and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                    'archive_compression_or_encryption')
            mode = info.external_attr >> 16
            require(not stat.S_ISLNK(mode), 'archive_symlink')
            require(info.file_size == member['bytes'] and
                    info.file_size <= (2097152 if member['role'] == 'trace' else 4096), 'archive_member_extent')
            names.add(info.filename)
            offsets.add(info.header_offset)
        require(sum(m['bytes'] for m in members) <= 16777216, 'archive_expansion_limit')
    except BaseException:
        archive.close()
        raise
    return archive


def _write(path, data, budget):
    require(budget[0] + len(data) <= OUTPUT_CAP, 'output_byte_limit')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    budget[0] += len(data)
    return {'file': path.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def prepare_archive(body, binding, output):
    """Trusted local artifact API. Production CLI fixes the authentic binding."""
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), 'output_already_exists')
    archive = checked_archive(body, binding)
    output.mkdir(mode=0o700)
    budget, products = [0], []
    try:
        with archive:
            for member, info in zip(binding['members'], archive.infolist()):
                if member['role'] != 'trace':
                    continue
                with archive.open(info) as source:
                    trace = source.read(member['bytes'] + 1)
                    require(len(trace) == member['bytes'] and source.read(1) == b'', 'trace_complete_crc_read')
                rows, diagnostic = prepare_trace(trace, member)
                stem = 'trace-%02d' % member['index']
                products.append(_write(output / (stem + '.jsonl'), b''.join(json_bytes(r) for r in rows), budget))
                products.append(_write(output / (stem + '-diagnostic.json'), json_bytes(diagnostic), budget))
        outcome = {'schema': 'fly-complete-pid-preparation-outcome-v1', 'status': 'complete_preparation',
                   'archive': binding['archive'], 'trace_count': 7, 'products': products,
                   'rows': sum(m['rows'] for m in binding['members'] if m['role'] == 'trace'),
                   'companions': 'Unchanged exact archive-bound ancestry; not decompressed or scientifically discarded.',
                   'scientific_admission': False, 'physical_offset_calibration': False,
                   'imaging_body_reads': 0, 'animal_count_inferred': False}
        _write(output / 'OUTCOME.json', json_bytes(outcome), budget)
        return outcome
    except BaseException as error:
        failure = {'schema': 'fly-complete-pid-preparation-outcome-v1', 'status': 'failed_partial_preserved',
                   'code': getattr(error, 'code', type(error).__name__), 'products': products,
                   'scientific_admission': False}
        # A failure receipt has a separate small reserve, never replacing outputs.
        _write(output / 'FAILURE.json', json_bytes(failure), [0])
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    binding_body = (root / 'BINDING.json').read_bytes()
    require(hashlib.sha256(binding_body).hexdigest() == BINDING_SHA256, 'binding_source_identity')
    require(hashlib.sha256((root / 'pid_types.py').read_bytes()).hexdigest() ==
            '5c63951901a202efb7a2f724d1279e2017bbd6537be54b633d73b3a28386827d', 'lexical_source_identity')
    with open(args.archive, 'rb') as source:
        body = source.read(ARCHIVE_CAP + 1)
    require(len(body) <= ARCHIVE_CAP, 'archive_byte_limit')
    result = prepare_archive(body, json.loads(binding_body), args.output)
    print(json.dumps({'status': result['status'], 'trace_count': 7, 'rows': result['rows']}))


BINDING_SHA256 = '41df8c86740b663ea77b8ecfa457091240b09138e0edfc4a835bf7f8a6772956'

if __name__ == '__main__':
    main()
