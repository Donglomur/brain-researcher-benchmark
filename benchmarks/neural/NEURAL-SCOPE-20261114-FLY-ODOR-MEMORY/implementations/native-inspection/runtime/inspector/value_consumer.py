"""Complete private Fly MAT5 clock/command census; no targets or inferred offsets.

The immutable metadata plan is the complete population authority. This successor
reuses the unchanged streaming Cursor/Inflater/run grammar; matrix traversal adds
bounded scalar consumption and correct endian-aware small tags. It is source-only
until separately selected against authentic inputs. No module reads data on import.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import time
import zipfile

from structural_stream import Cursor, Held, Mat5, need
from optional_inputs import OPTIONAL, OPTIONAL_BYTES, OPTIONAL_SHA, load_and_join
import diagnostics

PLAN_BYTES = 3419523
PLAN_SHA = '7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c'
ARCHIVE_BYTES = 789165393
ARCHIVE_SHA = '6c263d5037fef4e84c1ed33fa03b6673da35cb8a8cb3aace340a1db58b300302'
FIELDS = ('filename', 'thorname', 'thortime', 'fps', 'wind_speed', 'winddir',
          'wind_on', 'odor_on', 'closed_loop', 'calc_ts', 'wind', 'odor',
          'calc_heading', 'calc_speed', 'frame', 'dff_ts', 'dff_green',
          'dff_red', 'dff_diff', 'plume_t', 'plume_x', 'plume_y',
          'plume_speed', 'plume_valve')
STRINGS = ('filename', 'thorname', 'thortime')
SCALARS = ('fps', 'wind_speed', 'winddir', 'wind_on', 'odor_on', 'closed_loop')
BEHAVIOR = ('wind', 'odor', 'calc_heading', 'calc_speed', 'plume_t', 'plume_x',
            'plume_y', 'plume_speed', 'plume_valve')
NUMERIC = {1: ('b', 1), 2: ('B', 1), 3: ('h', 2), 4: ('H', 2),
           5: ('i', 4), 6: ('I', 4), 7: ('f', 4), 9: ('d', 8),
           12: ('q', 8), 13: ('Q', 8)}
INT_CLASS = {8: (-2**7, 2**7-1), 9: (0, 2**8-1), 10: (-2**15, 2**15-1),
             11: (0, 2**16-1), 12: (-2**31, 2**31-1), 13: (0, 2**32-1),
             14: (-2**63, 2**63-1), 15: (0, 2**64-1)}


class Budget:
    """Finite source caps, not a host/process sandbox or native booking."""
    def __init__(self, *, wall_seconds=900, overrides=None):
        self.caps = dict(member_bytes=268435456, nodes=2000000,
                         mat_expanded=4294967296, zip_bytes=800000000,
                         selected_values=160000000, report_bytes=67108864)
        if overrides:
            need(all(k in self.caps and type(v) is int and 0 < v <= self.caps[k]
                     for k, v in overrides.items()), 'caps may only be reduced')
            self.caps.update(overrides)
        need(type(wall_seconds) in (int, float) and 0 < wall_seconds <= 900,
             'finite bounded reader wall')
        self.deadline = time.monotonic() + wall_seconds
        self.counts = dict.fromkeys(self.caps, 0)

    def check(self):
        need(time.monotonic() < self.deadline, 'reader wall ceiling')

    def allow(self, key, count):
        self.check()
        need(type(count) is int and count >= 0 and
             self.counts[key] + count <= self.caps[key], key + ' ceiling')

    def add(self, key, count):
        self.allow(key, count)
        self.counts[key] += count


def finite(value):
    return type(value) is int or math.isfinite(value)


def exact(value):
    """Private JSON scalar spelling without binary64 conversion of integers."""
    if type(value) is int:
        return {'integer': str(value)}
    if math.isnan(value):
        return {'nonfinite': 'nan'}
    if math.isinf(value):
        return {'nonfinite': '+inf' if value > 0 else '-inf'}
    return {'binary_float_hex': value.hex()}


def runs(mask):
    result, start = [], None
    for index, present in enumerate(mask):
        if present and start is None:
            start = index
        if not present and start is not None:
            result.append([start, index]); start = None
    if start is not None:
        result.append([start, len(mask)])
    return result


def numeric_summary(values):
    mask = [finite(v) for v in values]
    observed = [v for v, ok in zip(values, mask) if ok]
    return {'elements': len(values), 'finite': len(observed),
            'nan': sum(type(v) is float and math.isnan(v) for v in values),
            'positive_infinity': sum(v == math.inf for v in values),
            'negative_infinity': sum(v == -math.inf for v in values),
            'finite_index_runs': runs(mask),
            'zero': sum(v == 0 for v in observed),
            'minimum': exact(min(observed)) if observed else None,
            'maximum': exact(max(observed)) if observed else None}


def clock_summary(values):
    result = numeric_summary(values)
    breaks = [i for i in range(1, len(values))
              if finite(values[i-1]) and finite(values[i]) and values[i] <= values[i-1]]
    result['nonincreasing_edges_right_index'] = breaks
    result['strictly_increasing_finite_runs'] = []
    cut = set(breaks)
    for start, end in result['finite_index_runs']:
        for at in range(start+1, end):
            if at in cut:
                result['strictly_increasing_finite_runs'].append([start, at]); start = at
        result['strictly_increasing_finite_runs'].append([start, end])
    result['gap_threshold_applied'] = False
    return result


def transitions(values, clock):
    """Observed changes only; never physical event labels or NaN bridging."""
    events, missing_pairs = [], 0
    for i in range(1, len(values)):
        a, b = values[i-1], values[i]
        if not (finite(a) and finite(b)):
            missing_pairs += 1
            continue
        if a == b:
            continue
        left = clock[i-1] if i-1 < len(clock) else None
        right = clock[i] if i < len(clock) else None
        valid = (left is not None and right is not None and
                 finite(left) and finite(right) and left < right)
        events.append({'left_index': i-1, 'right_index': i,
                       'from': exact(a), 'to': exact(b),
                       'left_clock': exact(left) if left is not None else None,
                       'right_clock': exact(right) if right is not None else None,
                       'clock_bracket_strict_finite': valid})
    return {'changes': events, 'adjacent_pairs_with_nonfinite_command': missing_pairs,
            'command_elements': len(values), 'clock_elements': len(clock),
            'physical_offset_inference': False}


def frame_summary(values, clock):
    integer = [finite(v) and (type(v) is int or v.is_integer()) for v in values]
    domain = [ok and 1 <= v <= len(clock) for v, ok in zip(values, integer)]
    seen, duplicates, jumps = set(), [], []
    for i, (v, ok) in enumerate(zip(values, domain)):
        if not ok:
            continue
        v = int(v)
        if v in seen:
            duplicates.append(i)
        seen.add(v)
        if i and domain[i-1]:
            previous = int(values[i-1])
            if v != previous + 1:
                jumps.append({'right_index': i, 'previous': str(previous), 'current': str(v)})
    finite_clock = {i+1 for i, v in enumerate(clock) if finite(v)}
    integral_values = [int(v) for v, ok in zip(values, integer) if ok]
    return {'elements': len(values),
            'minimum_integral_frame': str(min(integral_values)) if integral_values else None,
            'maximum_integral_frame': str(max(integral_values)) if integral_values else None,
            'nonintegral_or_nonfinite_indices':
            [i for i, ok in enumerate(integer) if not ok],
            'outside_saved_clock_domain_indices': [i for i, ok in enumerate(domain) if not ok],
            'duplicate_occurrence_indices': duplicates, 'nonconsecutive_edges': jumps,
            'padding_support_matches_finite_saved_clock':
            all(domain) and not duplicates and seen == finite_clock,
            'frame_indices_absent_from_finite_saved_clock': sorted(seen-finite_clock),
            'finite_saved_clock_positions_absent_from_frame': sorted(finite_clock-seen),
            'positions_one_based': True, 'no_alignment_or_repair': True}


def trial_report(values, descriptors, original):
    available = {k for k, v in original['optional_fields'].items() if v is not None}
    need(set(values) == set(FIELDS) | available, 'all 24 plus source-present optional fields required')
    need(all(name in descriptors for name in FIELDS), 'all typed field records required')
    result = {'trial_index_zero_based': original['trial_index_zero_based'],
              'condition': None, 'biological_animal': None, 'physical_offsets': None,
              'fields': {k: descriptors[k] for k in FIELDS},
              'saved_strings': {k: values[k] for k in STRINGS}}
    for name in SCALARS:
        need(len(values[name]) == 1, 'declared scalar extent')
    result['scalars'] = {k: exact(values[k][0]) for k in SCALARS}
    clock, imaging = values['calc_ts'], values['dff_ts']
    result['clocks'] = {k: clock_summary(values[k]) for k in ('calc_ts', 'dff_ts')}
    result['virtual_plume_frame_index'] = numeric_summary(values['plume_t'])
    result['frame'] = frame_summary(values['frame'], clock)
    result['behavior_length_mismatches'] = [k for k in BEHAVIOR if len(values[k]) != len(clock)]
    result['commands'] = {k: transitions(values[k], clock) for k in ('odor', 'wind', 'plume_valve')}
    result['literal_declaration_checks'] = {
        scalar: {'declared_scalar': exact(values[scalar][0]),
                 'vector_has_finite_nonzero': any(finite(v) and v != 0 for v in values[vector]),
                 'semantic_inconsistency_not_inferred': True}
        for scalar, vector in (('odor_on', 'odor'), ('wind_on', 'wind'))}
    shape = descriptors['dff_green']['dims']
    result['imaging_shape_matches_own_clock'] = (len(shape) == 2 and shape[1] == len(imaging)
        and all(descriptors[k]['dims'] == shape for k in ('dff_red', 'dff_diff')))
    result['imaging_empty'] = any(not values[k] for k in ('dff_ts', 'dff_green', 'dff_red', 'dff_diff'))
    result['imaging_finite_by_source_row'] = {}
    for name in ('dff_green', 'dff_red', 'dff_diff'):
        dims = descriptors[name]['dims']
        if len(dims) == 2 and dims[0]:
            result['imaging_finite_by_source_row'][name] = [
                sum(finite(v) for v in values[name][r::dims[0]]) for r in range(dims[0])]
        else:
            result['imaging_finite_by_source_row'][name] = None
    result['optional_fields'] = {}
    for name in OPTIONAL:
        if name not in available:
            result['optional_fields'][name] = {'source_present': False, 'descriptor': None,
                                               'values_or_changes': None}
        else:
            result['optional_fields'][name] = {
                'source_present': True, 'descriptor': descriptors[name],
                'values_or_changes': ([exact(v) for v in values[name]] if name == 'shift'
                                      else transitions(values[name], clock)),
                'command_boundary_diagnostics': (None if name == 'shift' else
                    diagnostics.command_boundaries(values[name], clock)),
                'condition_not_inferred': True}
    result['source_join_diagnostics'] = diagnostics.describe(values)
    result['disposition'] = 'native_values_inspected_no_scientific_eligibility_assigned'
    return result


class ValueMat5(Mat5):
    def __init__(self, cursor, budget, expected_file):
        super().__init__(cursor, budget)
        self.expected = expected_file
        self.rows, self.values, self.typed = [], {}, {}

    def tag(self, c, *, eof=False):
        raw = c.read(8)
        if not raw and eof:
            return None
        need(len(raw) == 8, 'short MAT tag')
        small_kind, small_size = struct.unpack(self.endian+'HH', raw[:4])
        # Small tags are two endian-aware uint16s, not uint32 high/low bits.
        if small_size and small_kind in (1, 2, 3, 4, 5, 6, 7, 9, 12, 13, 16, 17, 18):
            need(small_size <= 4, 'invalid small MAT tag')
            return small_kind, small_size, Cursor(io.BytesIO(raw[4:4+small_size]), self.budget), 0
        kind, count = struct.unpack(self.endian+'II', raw)
        need(kind in tuple(NUMERIC)+(14, 15, 16, 17, 18), 'unknown MAT primitive tag')
        need(count <= self.budget.caps['member_bytes'], 'MAT element extent cap')
        return kind, count, c, 0 if kind == 15 else (-count) % 8

    def payload(self, source, length, kind, cls, logical, dims, selected):
        size = math.prod(dims)
        width = self.widths[kind]
        if not selected:
            source.skip(length)
            return None, None
        need(size <= 20000 and length <= 160000, 'selected per-field retained extent')
        self.budget.add('selected_values', size)
        raw = source.exact(length)
        typed = {'primitive_tag': kind, 'byte_order': self.endian, 'payload_bytes': length,
                 'payload_sha256': hashlib.sha256(raw).hexdigest()}
        if cls == 4:
            need(len(dims) == 2 and (dims[0] == 1 or size == 0), 'char row-vector route only')
            if kind in (1, 2, 16):
                text = raw.decode('utf-8' if kind == 16 else 'latin-1', 'strict')
                need(len(text) == size, 'char dimension/encoding mismatch')
            else:
                need(length == size*width, 'char code-unit extent mismatch')
                codec = ('utf-16-' if kind in (4, 17) else 'utf-32-') + ('le' if self.endian == '<' else 'be')
                text = raw.decode(codec, 'strict')
            typed['text_encoding'] = ('utf-8' if kind == 16 else 'latin-1') if kind in (1, 2, 16) else codec
            return text, typed
        fmt, width = NUMERIC[kind]
        values = [v[0] for v in struct.iter_unpack(self.endian+fmt, raw)]
        for v in values:
            if logical:
                need(v in (0, 1), 'nonboolean logical value')
            if cls in INT_CLASS:
                lo, hi = INT_CLASS[cls]
                need(finite(v) and lo <= v <= hi and (type(v) is int or v.is_integer()),
                     'storage value not exact in integer MATLAB class')
            elif cls in (6, 7) and finite(v):
                try:
                    cast = float(v) if cls == 6 else struct.unpack('f', struct.pack('f', v))[0]
                except (OverflowError, struct.error):
                    raise Held('storage value exceeds MATLAB float class') from None
                need(cast == v, 'storage value not exact in MATLAB float class')
        typed['summary'] = numeric_summary(values)
        return values, typed

    def matrix(self, c, count, path, depth):
        need(depth <= 32, 'MAT nesting cap')
        start = c.pos
        kind, flags = self.small(c, 8)
        need(kind == 6 and len(flags) == 8, 'MAT flags')
        flag, unused = struct.unpack(self.endian+'II', flags)
        cls = flag & 255
        need(cls in self.classes and not flag & ~0xeff and unused == 0, 'unsupported MAT class/flags')
        kind, dimsraw = self.small(c, 64)
        need(kind == 5 and len(dimsraw) >= 8 and len(dimsraw) % 4 == 0, 'MAT dimensions')
        dims = list(struct.unpack(self.endian+'i'*(len(dimsraw)//4), dimsraw))
        need(all(x >= 0 for x in dims), 'negative MAT shape')
        size = math.prod(dims)
        kind, nameraw = self.small(c, 1024)
        need(kind in (1, 16) and b'\x00' not in nameraw, 'MAT name')
        name = nameraw.decode('utf-8' if kind == 16 else 'ascii', 'strict')
        current = path if path else [name]
        need(bool(current[0]), 'empty top variable')
        self.budget.add('nodes', 1)
        node = {'path': current, 'class': self.classes[cls], 'dims': dims,
                'complex': bool(flag & 0x800), 'logical': bool(flag & 0x200)}
        self.nodes.append(node)
        selected = len(current) == 3 and current[0] == 'syncstruct' and current[2] in FIELDS + OPTIONAL
        if selected:
            index, field = current[1:]
            need(index == len(self.rows) and index < self.expected['trial_count'], 'trial identity/order')
            trial = self.expected['trials'][index]
            expected = (trial['fields'][field] if field in FIELDS else trial['optional_fields'][field])
            need(expected is not None, 'source-absent optional field unexpectedly present')
            need(all(node[k] == expected[k] for k in ('class', 'dims', 'complex', 'logical')),
                 'native selected descriptor mismatch')
            need(not node['complex'] and cls not in (1, 2), 'selected real scalar/array route only')
            need(field not in self.values, 'duplicate selected field')
        if cls in (1, 2):
            need(not flag & 0xa00, 'invalid container flags')
            fields = None
            if cls == 2:
                kind, raw = self.small(c, 4)
                need(kind == 5 and len(raw) == 4, 'MAT field width')
                width, = struct.unpack(self.endian+'i', raw)
                need(1 <= width <= 256, 'MAT field width cap')
                kind, raw = self.small(c, 131072)
                need(kind == 1 and len(raw) % width == 0, 'MAT field names')
                fields = []
                for i in range(0, len(raw), width):
                    slot = raw[i:i+width]; at = slot.find(b'\x00')
                    need(at > 0 and not any(slot[at:]), 'MAT field termination')
                    fields.append(slot[:at].decode('ascii', 'strict'))
                need(len(fields) <= 512 and len(fields) == len(set(fields)), 'MAT fields cap/duplicate')
                node['fields'] = fields
            if current == ['syncstruct']:
                need(cls == 2 and size == self.expected['trial_count'] and
                     set(FIELDS) <= set(fields), 'complete declared source trials/fields')
                expected_optional = {k for k, v in self.expected['trials'][0]['optional_fields'].items()
                                     if v is not None}
                need(set(fields) & set(OPTIONAL) == expected_optional,
                     'exact optional source presence including absences')
            slots = size*(len(fields) if fields is not None else 1)
            need(slots <= self.budget.caps['nodes']-self.budget.counts['nodes'], 'MAT children cap')
            for index in range(size):
                for field in fields if fields is not None else [None]:
                    kind, length, source, pad = self.tag(c)
                    need(kind == 14 and source is c, 'MAT child matrix')
                    self.matrix(c, length, current+[index]+([field] if field is not None else []), depth+1)
                    c.skip(pad)
                if current == ['syncstruct']:
                    self.rows.append(trial_report(self.values, self.typed, self.expected['trials'][index]))
                    self.values, self.typed = {}, {}
        else:
            components = 2 if flag & 0x800 else 1
            need(not (cls == 4 and flag & 0xa00), 'invalid char flags')
            for _ in range(components):
                kind, length, source, pad = self.tag(c)
                need(kind in self.widths, 'unsupported MAT data type')
                if cls != 4:
                    need(kind in NUMERIC and length == size*self.widths[kind], 'MAT numerical shape mismatch')
                else:
                    need(kind in (1, 2, 4, 16, 17, 18), 'MAT char storage')
                value, typed = self.payload(source, length, kind, cls, node['logical'], dims, selected)
                source.skip(pad)
                if selected:
                    self.values[current[2]] = value
                    self.typed[current[2]] = dict(typed, **{k: node[k] for k in ('class', 'dims', 'complex', 'logical')})
                    self.typed[current[2]]['array_flags_uint32'] = flag
                    self.typed[current[2]]['flags_aux_uint32'] = unused
        need(c.pos-start == count, 'MAT matrix extent mismatch')

    def inspect(self):
        super().run()
        need(len(self.rows) == self.expected['trial_count'] and not self.values, 'full trial closure')
        maxima = [int(r['frame']['maximum_integral_frame']) for r in self.rows
                  if r['frame']['maximum_integral_frame'] is not None]
        all_integral = all(not r['frame']['nonintegral_or_nonfinite_indices'] for r in self.rows)
        maxframe = max(maxima) if maxima and all_integral else None
        return {'archive_member_id': self.expected['archive_member_id'],
                'official_lookup_index': self.expected['official_lookup_index'],
                'population_label': self.expected['population_label'],
                'trial_count': len(self.rows), 'trials': self.rows,
                'file_wide_padding_extent_hypothesis': {
                    'maximum_integral_frame': str(maxframe) if maxframe is not None else None,
                    'all_frames_integral_finite': all_integral,
                    'saved_clock_lengths_equal_file_maximum':
                    [r['clocks']['calc_ts']['elements'] == maxframe for r in self.rows],
                    'writer_application_not_inferred': True},
                'complete_mat_stream': True, 'byte_order': self.endian,
                'numeric_values_inspected': True, 'scientific_admission': False}


class HashedStream:
    def __init__(self, raw):
        self.raw, self.sha, self.bytes = raw, hashlib.sha256(), 0

    def read(self, count):
        raw = self.raw.read(count)
        self.sha.update(raw); self.bytes += len(raw)
        return raw


def consume_member(raw, expected_file, budget):
    wrapped = HashedStream(raw)
    reader = ValueMat5(Cursor(wrapped, budget, charge='zip_bytes'), budget, expected_file)
    result = reader.inspect()
    result['MAT_bytes'] = wrapped.bytes
    result['MAT_sha256'] = wrapped.sha.hexdigest()
    return result


def load_plan(path, optional_path):
    return load_and_join(path, optional_path)


def write_record(handle, record, budget):
    for part in json.JSONEncoder(ensure_ascii=True, allow_nan=False, separators=(',', ':')).iterencode(record):
        raw = part.encode('ascii')
        budget.add('report_bytes', len(raw)); handle.write(raw)
    budget.add('report_bytes', 1); handle.write(b'\n')


def inspect_archive(archive_path, plan_path, output_path, *, optional_path, budget=None):
    """Future trusted-local invocation. No native operation is selected by source.

    One file record is retained at a time. A 0600 .partial sibling is preserved on
    refusal; final name is linked exclusively only after all 42 files and custody
    close. No durability/power-loss guarantee. Trusted private operator directory
    required. This is not an OS-level owner; native execution needs separate review.
    """
    budget = budget or Budget()
    plan = load_plan(plan_path, optional_path)
    output_path = Path(output_path)
    partial = output_path.with_name(output_path.name+'.partial')
    need(not output_path.exists() and not output_path.is_symlink(), 'fresh private output required')
    need(not partial.exists() and not partial.is_symlink(), 'fresh partial output required')
    descriptor = os.open(archive_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(descriptor, 'rb') as handle:
            descriptor = None
            before = os.fstat(handle.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                 before.st_size == ARCHIVE_BYTES, 'exact ordinary archive extent')
            sha = hashlib.sha256()
            remaining = ARCHIVE_BYTES
            while remaining:
                budget.check()
                block = handle.read(min(65536, remaining))
                need(bool(block), 'truncated archive during identity pass')
                sha.update(block); remaining -= len(block)
            need(handle.read(1) == b'', 'archive grew during identity pass')
            need(sha.hexdigest() == ARCHIVE_SHA, 'authentic archive identity')
            handle.seek(0)
            fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            file_count, trial_count = 0, 0
            with os.fdopen(fd, 'wb') as target:
                write_record(target, {'record_type': 'header', 'schema': 'fly-complete-native-joins-census-jsonl-v2',
                    'operand_plan_sha256': PLAN_SHA, 'archive_sha256': ARCHIVE_SHA,
                    'optional_plan_bytes': OPTIONAL_BYTES, 'optional_plan_sha256': OPTIONAL_SHA,
                    'scientific_admission': False, 'condition_map': None, 'animal_map': None,
                    'physical_offsets': None, 'byte_caps': budget.caps}, budget)
                with zipfile.ZipFile(handle) as archive:
                    entries = archive.infolist()
                    offsets = {entry.header_offset: entry for entry in entries}
                    need(len(offsets) == len(entries), 'duplicate ZIP local-header offsets')
                    for expected in plan['files']:
                        m = expected['native_member']
                        info = offsets.get(m['storage_locator']['local_header_offset'])
                        need(info is not None and info.compress_size == m['compressed_bytes'] and
                             info.file_size == m['declared_uncompressed_bytes'] and
                             info.compress_type == m['compression'] and info.CRC == m['crc32'] and
                             not info.is_dir() and not info.flag_bits & 1, 'exact selected ZIP member')
                        with archive.open(info) as raw:
                            result = consume_member(raw, expected, budget)
                            need(raw.read(1) == b'', 'complete ZIP member including CRC')
                        need(result['MAT_bytes'] == info.file_size, 'full member extent')
                        write_record(target, dict(record_type='file', **result), budget)
                        file_count += 1; trial_count += result['trial_count']
                        del result
                after = os.fstat(handle.fileno())
                fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
                need(all(getattr(before, k) == getattr(after, k) for k in fields), 'archive custody changed')
                need(file_count == 42 and trial_count == 1345, 'complete native population')
                write_record(target, {'record_type': 'footer', 'complete_native_census': True,
                    'file_count': file_count, 'trial_count': trial_count, 'scientific_admission': False,
                    'counters_before_footer': dict(budget.counts)}, budget)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    os.link(partial, output_path, follow_symlinks=False)
    partial.unlink()
    return {'output_bytes': budget.counts['report_bytes'], 'files': 42, 'trials': 1345,
            'scientific_admission': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Private full Fly clock/command census; no scoring or physical-offset inference.')
    parser.add_argument('--archive', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--optional-plan', required=True)
    args = parser.parse_args()
    print(json.dumps(inspect_archive(args.archive, args.plan, args.output, optional_path=args.optional_plan), sort_keys=True))
