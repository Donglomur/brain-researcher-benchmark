"""Original CCEP prospective native-metadata consumer. Never reads MEF or targets."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

COMMIT = 'c896ca41b28f2af927836d18b0afc8ba719b8d57'
MAX_FILE = 8 * 1024 * 1024
MAX_BLOCKS = 100000
INT_FIELDS = ('acquisition_channel_number', 'start_sample', 'number_of_samples',
              'number_of_blocks', 'number_of_discontinuities')
REAL_FIELDS = ('sampling_frequency', 'units_conversion_factor',
               'low_frequency_filter_setting', 'high_frequency_filter_setting',
               'notch_filter_frequency_setting', 'AC_line_frequency')


def require(value, message):
    if not value:
        raise ValueError(message)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), 'unexpected object fields')


def text(value, limit=128, empty=False):
    require(type(value) is str and len(value) <= limit and (empty or value), 'invalid text')
    require(not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value), 'invalid text codepoint')
    return value


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'invalid digest')
    return value


def integer(value, bits=64, signed=True):
    require(type(value) is str and len(value) <= 20 and
            re.fullmatch(r'0|-[1-9][0-9]*|[1-9][0-9]*', value), 'integer must be canonical decimal text')
    number = int(value)
    low, high = (-(1 << (bits-1)), (1 << (bits-1))-1) if signed else (0, (1 << bits)-1)
    require(low <= number <= high, 'integer outside native type')
    return number


def real(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{16}', value), 'binary64 must be exact hexadecimal bits')
    return struct.unpack('>d', bytes.fromhex(value))[0]


def metadata(value):
    keys(value, (*INT_FIELDS, *(f'{x}_hex' for x in REAL_FIELDS), 'units_description'))
    result = {x: integer(value[x]) for x in INT_FIELDS}
    result.update({x: real(value[x+'_hex']) for x in REAL_FIELDS})
    text(value['units_description'], 512, empty=True)
    return result


def sequence(value, minimum=0, maximum=100000):
    require(type(value) is list and minimum <= len(value) <= maximum, 'invalid list extent')
    return value


def audit_packet(packet):
    keys(packet, ('schema', 'reader_commit', 'recording_key', 'source_manifest_sha256',
                 'number_of_time_series_channels', 'number_of_video_channels', 'channels'))
    require(packet['schema'] == 'clinical-ccep-native-metadata-v1' and
            packet['reader_commit'] == COMMIT, 'wrong packet producer declaration')
    text(packet['recording_key']); digest(packet['source_manifest_sha256'])
    nch = integer(packet['number_of_time_series_channels'], 32)
    nvideo = integer(packet['number_of_video_channels'], 32)
    require(nch >= 0 and nvideo >= 0, 'invalid channel counts')
    channels = sequence(packet['channels'], 0, 4096)
    require(len(channels) == nch, 'incomplete native channel inventory')
    names, acquisition, channel_reports = [], [], []
    total_blocks = 0
    for channel in channels:
        keys(channel, ('native_name', 'number_of_segments', 'earliest_start_time',
                       'latest_end_time', 'metadata', 'segments'))
        names.append(text(channel['native_name'], 512))
        integer(channel['earliest_start_time']); integer(channel['latest_end_time'])
        cm = metadata(channel['metadata']); acquisition.append(cm['acquisition_channel_number'])
        segments = sequence(channel['segments'], 0, 4096)
        require(integer(channel['number_of_segments']) == len(segments), 'incomplete native segment inventory')
        reports, counts, sample_ends = [], 0, []
        for segment in segments:
            keys(segment, ('metadata', 'indices'))
            sm = metadata(segment['metadata'])
            indices = sequence(segment['indices'], 0, MAX_BLOCKS)
            total_blocks += len(indices)
            require(total_blocks <= MAX_BLOCKS, 'complete packet exceeds reviewed index bound')
            require(sm['number_of_blocks'] == len(indices), 'incomplete native block inventory')
            issues, expected_start, flags, previous_time, time_breaks = [], 0, 0, None, 0
            unknown_counts, unknown_times, known_samples = 0, 0, 0
            if not indices:
                issues.append('empty_index_inventory')
            for index in indices:
                keys(index, ('start_sample', 'start_time', 'number_of_samples', 'RED_block_flags'))
                start = integer(index['start_sample']); clock = integer(index['start_time'])
                count = integer(index['number_of_samples'], 32, False)
                flag = integer(index['RED_block_flags'], 8, False)
                if start < 0:
                    issues.append('missing_or_invalid_index_start_sample')
                if count == (1 << 32)-1:
                    unknown_counts += 1
                    issues.append('index_sample_count_unknown')
                else:
                    known_samples += count
                if expected_start is not None and start != expected_start or count == 0:
                    issues.append('noncontiguous_or_empty_stored_sample_block')
                expected_start = None if expected_start is None or start < 0 or count == (1 << 32)-1 else start + count
                flags += bool(flag & 1)
                if clock == -(1 << 63):
                    unknown_times += 1
                    issues.append('index_start_time_unknown')
                    previous_time = None
                else:
                    if previous_time is not None and clock <= previous_time:
                        time_breaks += 1
                    previous_time = clock
            if expected_start is not None and expected_start != sm['number_of_samples']:
                issues.append('segment_sample_count_disagrees_with_indices')
            if sm['start_sample'] < 0 or sm['number_of_samples'] < 0:
                issues.append('missing_or_invalid_segment_sample_extent')
            if not math.isfinite(sm['sampling_frequency']) or sm['sampling_frequency'] <= 0:
                issues.append('missing_or_invalid_segment_frequency')
            if not math.isfinite(sm['units_conversion_factor']) or sm['units_conversion_factor'] == 0:
                issues.append('missing_or_invalid_segment_conversion_factor')
            if not segment['metadata']['units_description']:
                issues.append('missing_segment_units_description')
            if sm['number_of_discontinuities'] < 0:
                issues.append('declared_discontinuity_count_unknown')
            sample_ends.append((sm['start_sample'], sm['start_sample'] + sm['number_of_samples']))
            counts += sm['number_of_samples']
            reports.append({'blocks': len(indices), 'issues': sorted(set(issues)),
                            'native_time_order_breaks': time_breaks,
                            'RED_discontinuity_flag_count': flags,
                            'unknown_index_sample_counts': unknown_counts,
                            'unknown_index_start_times': unknown_times,
                            'known_index_samples_subtotal': str(known_samples),
                            'complete_index_derived_sample_end': None if expected_start is None else str(expected_start),
                            'declared_native_sample_start': str(sm['start_sample']),
                            'declared_native_sample_end_exclusive': str(sample_ends[-1][1])})
        channel_issues = [] if segments else ['empty_segment_inventory']
        if cm['number_of_samples'] < 0 or counts != cm['number_of_samples']:
            channel_issues.append('channel_sample_total_unknown_or_inconsistent')
        if cm['number_of_blocks'] < 0 or sum(x['blocks'] for x in reports) != cm['number_of_blocks']:
            channel_issues.append('channel_block_total_unknown_or_inconsistent')
        if any(sample_ends[i-1][1] != sample_ends[i][0] for i in range(1,len(sample_ends))):
            channel_issues.append('segment_stored_sample_extents_not_contiguous_in_native_order')
        for name in ('sampling_frequency_hex', 'units_conversion_factor_hex', 'units_description'):
            if any(s['metadata'][name] != channel['metadata'][name] for s in segments):
                channel_issues.append('channel_and_segment_'+name+'_differ')
        channel_reports.append({'segments': reports, 'issues': channel_issues})
    require(len(names) == len(set(names)), 'duplicate exact native channel name')
    folded = [x.casefold() for x in names]
    return {'native_channels': nch, 'empty_time_series_inventory': not channels,
            'unprojected_video_channels': nvideo,
            'blocks': total_blocks, 'channels': channel_reports,
            'casefold_name_collisions': len(folded) - len(set(folded)),
            'duplicate_acquisition_numbers': len(acquisition) - len(set(acquisition)),
            'missing_acquisition_numbers': sum(x < 0 for x in acquisition),
            'input_channel_ordinals_in_acquisition_order': sorted(range(1,nch+1), key=lambda i: (acquisition[i-1],i)),
            'acquisition_order_ambiguous': len(acquisition) != len(set(acquisition)) or any(x < 0 for x in acquisition)}


def validate(binding, packets):
    keys(binding, ('schema', 'reader_commit', 'recordings'))
    require(binding['schema'] == 'clinical-ccep-native-metadata-binding-v1' and
            binding['reader_commit'] == COMMIT, 'wrong operator binding')
    roster = sequence(binding['recordings'], 5, 5)
    expected = {}
    for row in roster:
        keys(row, ('recording_key', 'native_source_manifest_sha256'))
        key = text(row['recording_key']); digest(row['native_source_manifest_sha256'])
        require(key not in expected, 'duplicate binding recording')
        expected[key] = row['native_source_manifest_sha256']
    sequence(packets, 5, 5)
    observed, reports = {}, {}
    for packet in packets:
        report = audit_packet(packet)
        key = packet['recording_key']
        require(key in expected and key not in observed, 'missing, foreign or duplicate recording')
        require(packet['source_manifest_sha256'] == expected[key], 'native source binding differs')
        observed[key] = True; reports[key] = report
    require(set(observed) == set(expected), 'incomplete five-recording input')
    return {'schema': 'clinical-ccep-native-metadata-audit-v1',
            'complete_declared_recording_and_index_inventory': True,
            'native_io_authenticated_by_this_validator': False,
            'native_to_annotation_channel_join_established': False,
            'clock_offset_interpretation_established': False,
            'scientifically_qualified': False,
            'recordings_in_operator_order': [reports[x['recording_key']] for x in roster]}


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON object key')
        result[key] = value
    return result


def read_json(path):
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    before = os.lstat(path)
    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_FILE, 'input file extent/type refused')
    require(hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_NONBLOCK'), 'safe ordinary-file flags unavailable')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(identity(info) == identity(before) and stat.S_ISREG(info.st_mode), 'input changed before open')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(MAX_FILE+1)
        require(len(body) == before.st_size and len(body) <= MAX_FILE, 'input extent changed')
        require(identity(os.fstat(fd)) == identity(before) and identity(os.lstat(path)) == identity(before),
                'input identity changed during read')
        result = json.loads(body.decode('utf-8'), object_pairs_hook=no_duplicates,
                            parse_constant=lambda x: (_ for _ in ()).throw(ValueError('JSON nonfinite number')))
        return result, hashlib.sha256(body).hexdigest()
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', required=True)
    parser.add_argument('--packets', nargs=5, required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    binding, bh = read_json(args.binding)
    packets, hashes = [], []
    for path in args.packets:
        value, digest_value = read_json(path); packets.append(value); hashes.append(digest_value)
    report = validate(binding, packets)
    report['operator_binding_sha256'] = bh
    report['packet_sha256_in_argument_order'] = hashes
    with open(args.report, 'x', encoding='utf-8') as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'five_recordings_inspected': True, 'scientifically_qualified': False}))


if __name__ == '__main__':
    main()
