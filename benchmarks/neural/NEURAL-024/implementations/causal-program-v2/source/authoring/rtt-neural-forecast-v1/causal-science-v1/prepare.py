"""Count-only projection and private future stream; trusted isolated worker."""
from pathlib import Path
import argparse
import io
import sys
import time
import zipfile
sys.path.insert(0, '/source')
import numpy as np
import packet_core as p
import generated_checks
import calibration_rate
import calibration_rate_checks


def load_counts(descriptor, role, counters, tick):
    counters['recording_reads_attempted'] += 1
    tick()
    body = p.read_bound(descriptor['worker_path'], descriptor['bytes'],
                        {k: descriptor[k] for k in ('bytes', 'sha256')})
    counters['recording_bytes_read'] += len(body)
    expected = {'counts.npy', 'bin_edges_seconds.npy', 'endpoint_bin.npy'}
    if role != 'query_counts':
        expected.add('velocity_m_s.npy')
    with zipfile.ZipFile(io.BytesIO(body)) as source:
        infos = source.infolist()
        p.need(len(infos) == len(expected) and {x.filename for x in infos} == expected,
               'Exact previously qualified conversion members')
        p.need(all(x.compress_type == zipfile.ZIP_STORED and not x.flag_bits & 1
                   and not x.is_dir() and x.file_size == x.compress_size for x in infos),
               'Stored unencrypted qualified conversion')
    with np.load(io.BytesIO(body), allow_pickle=False) as source:
        counts = source['counts']
        edges = source['bin_edges_seconds']
    counters['count_arrays_decoded'] += 1
    counters['clock_arrays_decoded'] += 1
    n = descriptor['bins']
    p.need(type(counts) is np.ndarray and counts.dtype == np.dtype('<u4') and
           counts.shape == (n, 96) and counts.flags.c_contiguous, 'Exact released count coordinates')
    p.need(type(edges) is np.ndarray and edges.dtype == np.dtype('<f8') and
           edges.shape == (n + 1,) and edges.flags.c_contiguous and np.isfinite(edges).all()
           and np.all(np.diff(edges) > 0), 'Native converted clock coordinates')
    p.need(abs(float(edges[0]) - descriptor['first_seconds']) <= 1e-7 and
           abs(float(edges[-1]) - descriptor['last_seconds']) <= 1e-7 and
           float(np.max(np.abs(np.diff(edges) - .02))) <= 1e-7,
           'Fixed native 20 ms clock support, unchanged values')
    counters['recording_reads_completed'] += 1
    return counts, edges


def count_packet(counts, edges):
    target = io.BytesIO()
    np.savez(target, counts=counts, bin_edges_seconds=edges)
    body = target.getvalue()
    # Verify the saved projection in this trusted worker, including exact values.
    with np.load(io.BytesIO(body), allow_pickle=False) as saved:
        saved_counts, saved_edges = saved['counts'], saved['bin_edges_seconds']
        p.need(len(saved.files) == 2 and set(saved.files) == {'counts', 'bin_edges_seconds'} and
               saved_counts.dtype == counts.dtype and saved_counts.shape == counts.shape and
               saved_edges.dtype == edges.dtype and saved_edges.shape == edges.shape and
               saved_counts.flags.c_contiguous and saved_edges.flags.c_contiguous and
               np.array_equal(saved_counts, counts) and np.array_equal(saved_edges, edges),
               'Count-only projection round-trip without velocity or endpoint arrays')
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    writer = p.Writer(args.out, p.PREP_CAPS)
    counters = {'recording_reads_attempted': 0, 'recording_reads_completed': 0,
                'recording_bytes_read': 0, 'count_arrays_decoded': 0, 'clock_arrays_decoded': 0,
                'behavior_arrays_decoded': 0, 'projection_roundtrips': 0,
                'projection_count_arrays_decoded': 0, 'projection_clock_arrays_decoded': 0,
                'observation_rows_encoded': 0, 'schedule_intervals': 0,
                'reference_json_reads_attempted': 0, 'reference_json_reads_completed': 0,
                'scientific_fits': 0, 'candidate_invocations': 0,
                'generated_packet_controls': 0, 'generated_candidate_controls': 0}
    status, error, config = 'rtt_neural_causal_packet_failed', None, None
    generated = {}
    def tick():
        if time.monotonic() - start > 25:
            raise TimeoutError('Fixed preparer computation window')
    try:
        raw = p.read_bound(args.inputs, 64000)
        p.need(p.digest(raw)['sha256'] == args.inputs_sha256, 'Frozen scientific inputs')
        config = p.parse(raw)
        p.need(config['candidate_id'] == 'NEURAL-024' and config['protocol'] == p.PROTOCOL,
               'Exact causal scientific task')
        generated['packet'] = generated_checks.run(p, count_packet, np, tick=tick)
        counters['generated_packet_controls'] = generated['packet']['checks']
        tick()
        generated['calibration_candidate'] = calibration_rate_checks.run(calibration_rate, np)
        tick()
        counters['generated_candidate_controls'] = generated['calibration_candidate']['guard_count']
        source, source_edges = load_counts(config['data']['source_counts'], 'source_counts', counters, tick)
        calibration, calibration_edges = load_counts(config['data']['calibration_counts'], 'calibration_counts', counters, tick)
        future, future_edges = load_counts(config['data']['query_counts'], 'query_counts', counters, tick)
        p.need(source.shape == (18700, 96) and calibration.shape == (3000, 96)
               and future.shape == (22100, 96) and calibration_edges[-1] == future_edges[0],
               'Exact complete calibration/future seam')
        first = float(calibration_edges[0])
        p.need(abs(float(future_edges[0] - first) - 60.) <= 1e-7 and
               abs(float(future_edges[10] - first) - 60.2) <= 1e-7 and
               abs(float(future_edges[-1] - first) - 502.) <= 1e-7,
               'Ten guard rounds followed by every scored future bin')
        source_body = count_packet(source, source_edges)
        counters['projection_roundtrips'] += 1
        counters['projection_count_arrays_decoded'] += 1
        counters['projection_clock_arrays_decoded'] += 1
        writer.write('source_counts.npz', source_body)
        del source_body, source, source_edges
        calibration_body = count_packet(calibration, calibration_edges)
        counters['projection_roundtrips'] += 1
        counters['projection_count_arrays_decoded'] += 1
        counters['projection_clock_arrays_decoded'] += 1
        writer.write('calibration_counts.npz', calibration_body)
        del calibration_body, calibration, calibration_edges
        def observations():
            for index in range(p.ROUNDS):
                tick()
                value = {'target_bin': p.FIRST + index, 'counts': future[index].tolist()}
                p.observation(value, p.FIRST + index)
                body = p.canonical(value)
                p.need(len(body) <= p.OBSERVATION_LINE_CAP, 'Bounded complete private observation line')
                counters['observation_rows_encoded'] += 1
                yield body
        writer.stream('observations.jsonl', observations())
        intervals = []
        for index in range(p.ROUNDS):
            if index % 1024 == 0:
                tick()
            value = [float(future_edges[index] - first), float(future_edges[index + 1] - first)]
            p.interval(value)
            if intervals:
                p.need(intervals[-1][1] == value[0], 'Exact adjacent native interval join')
            intervals.append(value)
        counters['schedule_intervals'] = len(intervals)
        writer.json('schedule.json', {'candidate_id': 'NEURAL-024', 'first_target_bin': p.FIRST,
                                     'warmup_rounds': p.WARMUP, 'scored_rounds': p.SCORED,
                                     'intervals': intervals})
        counters['reference_json_reads_attempted'] += 1
        ref = config['reference_scores']
        reference = p.read_bound(ref['worker_path'], 256000, {k: ref[k] for k in ('bytes', 'sha256')})
        saved = p.parse(reference, canonical_required=True)
        p.need(saved['status'] == 'complete_fixed_development_panel' and
               set(saved['arms']) == set(config['reference_arms']) and
               all(v['rows'] == p.SCORED and v['channels'] == p.CHANNELS
                   and v['cells'] == p.SCORED * p.CHANNELS for v in saved['arms'].values()),
               'Exact complete fixed six-arm comparator support')
        counters['reference_json_reads_completed'] += 1
        writer.write('references.json', reference)
        p.need(counters['observation_rows_encoded'] == counters['schedule_intervals'] == p.ROUNDS,
               'Complete private future roster')
        tick()
        status = 'rtt_neural_causal_packet_prepared'
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)[:1800]
    receipt = {'status': status, 'candidate_id': 'NEURAL-024', 'protocol': p.PROTOCOL,
               'complete': status == 'rtt_neural_causal_packet_prepared', 'error': error,
               'files': dict(writer.pins), 'counters': counters, 'generated_checks': generated,
               'inputs_sha256': args.inputs_sha256,
               'input_identity_pins': ({k: {f: v[f] for f in ('bytes', 'sha256')}
                                        for k, v in config['data'].items()} if config else None),
               'reference_scores_pin': ({k: config['reference_scores'][k] for k in ('bytes', 'sha256')}
                                        if config else None),
               'native_clock_edges_modified': False, 'public_projection_members': ['counts', 'bin_edges_seconds'],
               'private_future_rows': counters['observation_rows_encoded'], 'warmup_rows': p.WARMUP,
               'scored_rows': p.SCORED, 'elapsed_seconds': time.monotonic() - start,
               'incomplete_operation_extent_unknown': (
                   counters['recording_reads_attempted'] != counters['recording_reads_completed'] or
                   counters['reference_json_reads_attempted'] != counters['reference_json_reads_completed'] or
                   writer.attempted != writer.completed)}
    writer.json('prepare_receipt.json', receipt)
    print(p.canonical({'status': status, 'files': writer.pins, 'counters': counters}).decode('ascii'), end='')
    return 0 if receipt['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
