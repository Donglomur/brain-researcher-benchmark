"""Bounded complete member inspections. SOURCE PROPOSAL: not executed or admitted.

Pure bytes -> metadata functions; no filenames, file/network IO, or signal arrays.
The caller owns ZIP verification, exact member identities and aggregate budgets.
"""
import hashlib
import re
import struct

TRACE_MAX_BYTES = 2 * 1024 * 1024
PID_ALL_LOGICAL_BYTES = 16 * 1024 * 1024
SIDECAR_MAX_BYTES = 4096
PID_COLUMNS = (
    'ts', 'frame_count', 'FTheading', 'FTspeed', 'heading', 'delta_roll',
    'delta_pitch', 'unfilt_delta_heading', 'delta_heading', 'motorvoltage',
    'motorsign', 'motorposition', 'gain', 'shift', 'wind', 'windspeed',
    'start_pos', 'odor', 'AnalogIn', 'filtmotorpos', 'reset_windpos',
)
DECIMAL = re.compile(rb'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
DATE_HEADER = re.compile(r'PyBMT data [0-9]{8}-[0-9]{6}\Z')


class Held(ValueError):
    """Malformed or resource-inadmissible input, without echoing its contents."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _limit(n, code, low=1):
    if type(n) is not int or n < low:
        raise Held(code)
    return n


def _body(body, expected_bytes, cap):
    _limit(cap, 'invalid_byte_cap')
    _limit(expected_bytes, 'invalid_expected_bytes', 0)
    if type(body) is not bytes:
        raise Held('body_must_be_bytes')
    if len(body) != expected_bytes:
        raise Held('whole_member_length_mismatch')
    if len(body) > cap:
        raise Held('whole_member_byte_cap')


def inspect_pid_text(body, *, expected_bytes, max_bytes=TRACE_MAX_BYTES,
                     max_lines=262144, max_line_bytes=4096, max_columns=128):
    """Complete UTF8/lexical census, not a signal decoder or MATLAB importer.

    The local 21-column profile is the complete cached-header evidence, not an
    assertion that the published 35-field reader is equivalent. Empty and NaN
    cells are counted and remain held for scientific missingness policy. Numeric spelling
    is checked only; no token becomes a float or a scientific observation.
    """
    _body(body, expected_bytes, max_bytes)
    for n in (max_lines, max_line_bytes, max_columns):
        _limit(n, 'invalid_text_cap')
    if max_bytes > TRACE_MAX_BYTES or max_lines > 262144 or max_line_bytes > 4096 or max_columns > 128:
        raise Held('text_cap_above_selected_source_limit')
    if max_columns < len(PID_COLUMNS):
        raise Held('text_column_cap_below_profile')
    counts = dict(lines=0, data_rows=0, blank_data_rows=0, lf=0, crlf=0,
                  unterminated_lines=0, decimal_tokens=0, empty_tokens=0,
                  nan_tokens=0, infinity_tokens=0, other_tokens=0, wrong_width_rows=0)
    widths = {}
    holds = set()
    quality_holds = set()
    column_counts = [dict(column=i + 1, name=name, decimal=0, empty=0,
                          nan=0, infinity=0, other=0) for i, name in enumerate(PID_COLUMNS)]
    header_hashes = []
    header_matches = [False, False]
    max_seen_line = 0
    bom = body.startswith(b'\xef\xbb\xbf')
    cursor = 0
    while cursor < len(body):
        end = body.find(b'\n', cursor)
        terminated = end >= 0
        if not terminated:
            end = len(body)
        row = body[cursor:end]
        cursor = end + 1 if terminated else end
        if len(row) > max_line_bytes:
            raise Held('text_line_byte_cap')
        max_seen_line = max(max_seen_line, len(row))
        if terminated and row.endswith(b'\r'):
            counts['crlf'] += 1
            row = row[:-1]
        elif terminated:
            counts['lf'] += 1
        else:
            counts['unterminated_lines'] += 1
        if b'\r' in row:
            raise Held('bare_carriage_return')
        if any((c < 32 and c != 9) or c == 127 for c in row):
            raise Held('text_control_character')
        counts['lines'] += 1
        if counts['lines'] > max_lines:
            raise Held('text_line_count_cap')
        try:
            decoded = row.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            raise Held('text_not_complete_strict_utf8') from None
        if counts['lines'] == 1 and bom:
            decoded = decoded[1:]
        if counts['lines'] <= 2:
            header_hashes.append(hashlib.sha256(row).hexdigest())
            if counts['lines'] == 1:
                header_matches[0] = DATE_HEADER.fullmatch(decoded) is not None
            elif decoded.startswith('Format:'):
                names = tuple(x.strip() for x in decoded[7:].split(','))
                header_matches[1] = names == PID_COLUMNS
            continue
        counts['data_rows'] += 1
        if not row.strip(b' \t'):
            counts['blank_data_rows'] += 1
            holds.add('blank_data_row_policy_unresolved')
        # This split is bounded first by the 4096-byte line and then by 128 cells.
        width = row.count(b',') + 1
        if width > max_columns:
            raise Held('text_column_count_cap')
        widths[str(width)] = widths.get(str(width), 0) + 1
        if width != len(PID_COLUMNS):
            counts['wrong_width_rows'] += 1
            holds.add('data_row_not_21_columns')
        for column, token in enumerate(row.split(b',')):
            token = token.strip(b' \t')
            if not token:
                counts['empty_tokens'] += 1
                kind = 'empty'
            elif token.lower() in (b'nan', b'+nan', b'-nan'):
                counts['nan_tokens'] += 1
                kind = 'nan'
            elif token.lower() in (b'inf', b'+inf', b'-inf', b'infinity', b'+infinity', b'-infinity'):
                counts['infinity_tokens'] += 1
                kind = 'infinity'
            elif DECIMAL.fullmatch(token) is not None:
                counts['decimal_tokens'] += 1
                kind = 'decimal'
            else:
                counts['other_tokens'] += 1
                kind = 'other'
                holds.add('nondecimal_data_token')
            if width == len(PID_COLUMNS):
                column_counts[column][kind] += 1
                if kind in ('empty', 'nan', 'infinity'):
                    quality_holds.add('critical_column_missing_or_nonfinite' if column in (0, 1, 14, 17, 18)
                                      else 'optional_column_missing_or_nonfinite')
    if not all(header_matches):
        holds.add('local_header_profile_not_established')
    if counts['data_rows'] == 0:
        holds.add('no_data_rows')
    return dict(
        type='complete_strict_utf8_text', full_member_bytes=len(body),
        member_sha256=hashlib.sha256(body).hexdigest(), complete_member_scan=True,
        utf8_bom=bom, maximum_line_bytes=max_seen_line, counts=counts,
        row_width_histogram=widths, header_sha256=header_hashes,
        per_column_lexical_counts_for_21_column_rows=column_counts,
        local_header_matches=header_matches, local_profile='PyBMT_21_COLUMN_RELEASE_HEADER_V1',
        local_profile_pass=not holds, holds=sorted(holds),
        scientific_quality_holds=sorted(quality_holds),
        published_reader_numeric_fields=35, local_profile_fields=21,
        published_reader_equivalence=False, numeric_values_decoded=False,
        clocks_units_alignment_verified=False, scientific_admission=False,
    )


def _gaps_zero(body, start, stop, ranges, code):
    """Reject undeclared nonzero storage, but permit bounded zero padding."""
    cursor = start
    for lo, hi in sorted(ranges):
        if lo < cursor or hi < lo or hi > stop:
            raise Held(code + '_overlap_or_bounds')
        if any(body[cursor:lo]):
            raise Held(code + '_nonzero_gap')
        cursor = hi
    if any(body[cursor:stop]):
        raise Held(code + '_nonzero_tail')


def _attributes(body, entry, entries, max_attributes):
    """The bounded contemporary Apple copyfile ATTR layout, not all variants."""
    begin, size = entry['offset'], entry['length']
    end = begin + size
    if begin != 50 or len(entries) != 2 or [e['id'] for e in entries] != [9, 2]:
        raise Held('unsupported_extended_finder_layout')
    if size < 70 or body[82:84] != b'\0\0':
        raise Held('truncated_or_nonzero_attr_padding')
    values = struct.unpack_from('>8I2H', body, 84)
    magic, debug, total, data_start, data_length, r1, r2, r3, flags, count = values
    if magic != 0x41545452:
        raise Held('finder_extension_not_ATTR')
    if debug != 0 or flags != 0 or any((r1, r2, r3)):
        raise Held('unsupported_ATTR_flags_or_reserved')
    if count > max_attributes:
        raise Held('attribute_count_cap')
    if total != end or data_start < 120 or data_start > end or data_start + data_length != end:
        raise Held('ATTR_data_extent_mismatch')
    if entries[1]['offset'] != end:
        raise Held('ATTR_resource_start_mismatch')
    cursor = 120
    found = []
    names = set()
    ranges = []
    for _ in range(count):
        if cursor + 11 > data_start:
            raise Held('truncated_attribute_descriptor')
        offset, length, attr_flags, name_length = struct.unpack_from('>IIHB', body, cursor)
        if attr_flags != 0 or name_length < 2 or name_length > 128:
            raise Held('unsupported_attribute_flags_or_name_length')
        next_cursor = cursor + ((11 + name_length + 3) & ~3)
        if next_cursor > data_start:
            raise Held('attribute_descriptor_extent')
        raw_name = body[cursor + 11:cursor + 11 + name_length]
        if raw_name[-1:] != b'\0' or b'\0' in raw_name[:-1]:
            raise Held('attribute_name_termination')
        try:
            name = raw_name[:-1].decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            raise Held('attribute_name_utf8') from None
        if any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise Held('attribute_name_control_character')
        if name in names:
            raise Held('duplicate_attribute_name')
        names.add(name)
        if any(body[cursor + 11 + name_length:next_cursor]):
            raise Held('attribute_descriptor_padding')
        if offset < data_start or offset > end or length > end - offset:
            raise Held('attribute_value_extent')
        if length:
            ranges.append((offset, offset + length))
        found.append(dict(name=name, offset=offset, length=length,
                          value_sha256=hashlib.sha256(body[offset:offset + length]).hexdigest(),
                          semantic_disposition='extended_attribute_semantics_unbound'))
        cursor = next_cursor
    if cursor != data_start:
        raise Held('ATTR_descriptor_extent_mismatch')
    _gaps_zero(body, data_start, end, ranges, 'attribute_data')
    return dict(type='Apple_copyfile_ATTR', total_size=total, data_start=data_start,
                data_length=data_length, attributes=found)


def inspect_appledouble(body, *, expected_bytes, max_bytes=SIDECAR_MAX_BYTES,
                        max_entries=64, max_attributes=32):
    """Identify AppleDouble from complete bytes; names cannot establish its type.

    Complete structural acceptance is distinct from scientific exclusion. All
    opaque attributes/nonempty resource forks keep an explicit semantic hold.
    No binary values or general attribute contents are emitted.
    """
    _body(body, expected_bytes, max_bytes)
    _limit(max_entries, 'invalid_entry_cap')
    _limit(max_attributes, 'invalid_attribute_cap')
    if max_bytes > SIDECAR_MAX_BYTES or max_entries > 64 or max_attributes > 32:
        raise Held('sidecar_cap_above_selected_source_limit')
    if len(body) < 26:
        raise Held('truncated_appledouble_header')
    magic, version, filler, count = struct.unpack_from('>II16sH', body)
    if magic != 0x00051607:
        raise Held('not_appledouble_magic')
    if version != 0x00020000:
        raise Held('unsupported_appledouble_version')
    if filler not in (b'\0' * 16, b'Mac OS X        '):
        raise Held('unsupported_appledouble_filler')
    if count > max_entries:
        raise Held('appledouble_entry_count_cap')
    table_end = 26 + 12 * count
    if table_end > len(body):
        raise Held('truncated_appledouble_table')
    entries, ids, ranges, holds = [], set(), [], set()
    for i in range(count):
        ident, offset, length = struct.unpack_from('>III', body, 26 + 12 * i)
        if ident in (0, 1):
            raise Held('invalid_appledouble_entry_id')
        if ident in ids:
            raise Held('duplicate_appledouble_entry_id')
        ids.add(ident)
        if offset < table_end or offset > len(body) or length > len(body) - offset:
            raise Held('appledouble_entry_extent')
        if length:
            ranges.append((offset, offset + length))
        entries.append(dict(id=ident, offset=offset, length=length,
                            payload_sha256=hashlib.sha256(body[offset:offset + length]).hexdigest()))
    _gaps_zero(body, table_end, len(body), ranges, 'appledouble_payload')
    for entry in entries:
        ident, length = entry['id'], entry['length']
        if ident == 2:
            entry['type'] = 'resource_fork'
            if length:
                holds.add('nonempty_resource_fork_semantics_unbound')
        elif ident == 9:
            entry['type'] = 'finder_info'
            if length == 32:
                pass
            elif length > 32:
                entry['extension'] = _attributes(body, entry, entries, max_attributes)
                if entry['extension']['attributes']:
                    holds.add('extended_attribute_semantics_unbound')
            else:
                raise Held('truncated_finder_info')
        elif ident == 8:
            entry['type'] = 'file_dates'
            if length != 16:
                raise Held('file_dates_length')
        else:
            entry['type'] = 'other_entry'
            holds.add('other_entry_semantics_unbound')
    return dict(type='AppleDouble_v2', complete_member_scan=True,
                full_member_bytes=len(body), member_sha256=hashlib.sha256(body).hexdigest(),
                header_filler='RFC_zero' if not any(filler) else 'Apple_Mac_OS_X',
                entries=entries, complete_structure_pass=True, holds=sorted(holds),
                suffix_used_to_infer_type=False, scientific_payload_exclusion=False,
                requires_official_reader_and_paired_member_role_join=True,
                attribute_values_exposed=False, scientific_admission=False)
