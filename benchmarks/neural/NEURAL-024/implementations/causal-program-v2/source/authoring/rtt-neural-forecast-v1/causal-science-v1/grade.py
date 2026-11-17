"""Admit public commits first; then score complete private count targets."""
from pathlib import Path
import argparse
import hashlib
import math
import re
import sys
import time
sys.path.insert(0, '/source')
import numpy as np
import packet_core as p
import score_core
import score_generated_checks

COMMIT_KEYS = {'sequence', 'target_bin', 'scored', 'nonce', 'request_sha256',
               'mean_counts', 'previous_commit', 'revealed', 'received'}
PRIVATE_NAMES = {'prepare_receipt.json', 'observations.jsonl', 'schedule.json', 'references.json'}


def admit_submission(path, expected, counters, tick):
    """No private inputs are accepted or opened by this function."""
    counters['submission_reads_attempted'] += 1
    p.ordinary_size(path, p.ROUNDS * p.COMMIT_LINE_CAP, expected)
    means = np.empty((p.ROUNDS, p.CHANNELS), dtype=np.float64)
    identities = []
    previous, prior_received = None, None
    nonces, sha, total = set(), hashlib.sha256(), 0
    with Path(path).open('rb') as source:
        for sequence in range(p.ROUNDS):
            tick()
            body = source.readline(p.COMMIT_LINE_CAP + 1)
            total += len(body)
            counters['submission_bytes_read'] += len(body)
            p.need(0 < len(body) <= p.COMMIT_LINE_CAP and body.endswith(b'\n'),
                   'Complete bounded canonical commit record')
            value = p.parse(body, canonical_required=True)
            p.need(type(value) is dict and set(value) == COMMIT_KEYS,
                   'Exact complete public commit schema')
            p.need(type(value['sequence']) is int and value['sequence'] == sequence and
                   type(value['target_bin']) is int and value['target_bin'] == p.FIRST + sequence and
                   type(value['scored']) is bool and value['scored'] is (sequence >= p.WARMUP),
                   'Exact warm-up and scored commit identities')
            p.need(type(value['nonce']) is str and re.fullmatch('[0-9a-f]{32}', value['nonce']) is not None
                   and value['nonce'] not in nonces, 'Unique fixed-width round nonce')
            p.need(type(value['request_sha256']) is str and
                   re.fullmatch('[0-9a-f]{64}', value['request_sha256']) is not None,
                   'Canonical request byte-hash identity')
            nonces.add(value['nonce'])
            p.need(value['previous_commit'] == previous,
                   'Exact prior complete canonical record pin, including newline')
            if sequence:
                p.need(p.valid_pin(value['previous_commit']), 'Strict prior record pin schema')
            for name in ('revealed', 'received'):
                p.need(type(value[name]) in (int, float) and math.isfinite(value[name]) and value[name] >= 0,
                       'Finite nonnegative controller timestamp')
            p.need(value['received'] >= value['revealed'] and
                   (prior_received is None or value['revealed'] >= prior_received),
                   'Ordered controller request/reply timestamps')
            vector = value['mean_counts']
            # The trusted controller converts legal candidate numbers to float
            # before canonically committing them. Integers here are nonconforming.
            p.need(type(vector) is list and len(vector) == p.CHANNELS and
                   all(type(x) is float and math.isfinite(x) and x > 0 for x in vector),
                   'All 96 simultaneous strictly positive finite committed float means')
            means[sequence] = vector
            identities.append({'nonce': value['nonce'], 'request_sha256': value['request_sha256']})
            counters['committed_rows_admitted'] += 1
            counters['prediction_cells_admitted'] += p.CHANNELS
            previous, prior_received = p.digest(body), value['received']
            sha.update(body)
        extra = source.read(1)
        counters['submission_bytes_read'] += len(extra)
        p.need(extra == b'', 'No extra commit row or trailing byte')
    p.need({'bytes': total, 'sha256': sha.hexdigest()} == expected,
           'Complete submission pin after exact record admission')
    counters['submission_reads_completed'] += 1
    return means, identities


def private_json(name, invocation, cap, counters):
    counters['private_reads_attempted'] += 1
    body = p.read_bound('/private/' + name, cap, invocation['private_inputs'][name])
    counters['private_bytes_read'] += len(body)
    value = p.parse(body, canonical_required=True)
    counters['private_reads_completed'] += 1
    return value


def private_targets(invocation, schedule, identities, counters, tick):
    expected = invocation['private_inputs']['observations.jsonl']
    counters['private_reads_attempted'] += 1
    p.ordinary_size('/private/observations.jsonl', p.PREP_CAPS['observations.jsonl'], expected)
    target = np.empty((p.ROUNDS, p.CHANNELS), dtype=np.int64)
    previous, sha, total = None, hashlib.sha256(), 0
    with Path('/private/observations.jsonl').open('rb') as source:
        for sequence in range(p.ROUNDS):
            tick()
            # Construct the request before decoding this round's current counts.
            request = {'protocol': p.PROTOCOL, 'status': 'predict', 'sequence': sequence,
                       'target_bin': p.FIRST + sequence, 'interval': schedule['intervals'][sequence],
                       'scored': sequence >= p.WARMUP, 'nonce': identities[sequence]['nonce'],
                       'observation': previous}
            p.need(p.digest(p.canonical(request))['sha256'] == identities[sequence]['request_sha256'],
                   'Trusted request hash must contain only the lawful previous observation')
            counters['prefix_request_hashes_verified'] += 1
            body = source.readline(p.OBSERVATION_LINE_CAP + 1)
            total += len(body)
            counters['private_bytes_read'] += len(body)
            p.need(0 < len(body) <= p.OBSERVATION_LINE_CAP and body.endswith(b'\n'),
                   'Complete bounded private observation record')
            value = p.parse(body, canonical_required=True)
            counts = p.observation(value, p.FIRST + sequence)
            target[sequence] = counts
            previous = value
            sha.update(body)
            counters['private_observation_rows_decoded'] += 1
        extra = source.read(1)
        counters['private_bytes_read'] += len(extra)
        p.need(extra == b'', 'No extra private observation row or trailing byte')
    p.need({'bytes': total, 'sha256': sha.hexdigest()} == expected, 'Complete private observation identity')
    counters['private_reads_completed'] += 1
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--invocation', type=Path, required=True)
    parser.add_argument('--invocation-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    writer = p.Writer(args.out, p.GRADE_CAPS)
    counters = {'submission_reads_attempted': 0, 'submission_reads_completed': 0,
                'submission_bytes_read': 0, 'committed_rows_admitted': 0, 'prediction_cells_admitted': 0,
                'private_reads_attempted': 0, 'private_reads_completed': 0, 'private_bytes_read': 0,
                'private_observation_rows_decoded': 0, 'prefix_request_hashes_verified': 0,
                'generated_score_controls': 0, 'scored_rows': 0, 'unscored_warmup_rows': 0,
                'scientific_fits': 0, 'candidate_invocations': 0}
    phase, status, error, result = 'control', 'numerical_failure', None, None
    generated = None
    def tick():
        if time.monotonic() - start > 25:
            raise TimeoutError('Fixed private-grader computation window')
    try:
        raw = p.read_bound(args.inputs, 64000)
        p.need(p.digest(raw)['sha256'] == args.inputs_sha256, 'Frozen scientific input contract')
        config = p.parse(raw)
        p.need(config['candidate_id'] == 'NEURAL-024' and config['protocol'] == p.PROTOCOL,
               'Exact declared scientific task')
        raw = p.read_bound(args.invocation, 64000)
        p.need(p.digest(raw)['sha256'] == args.invocation_sha256, 'Exact current invocation pin')
        invocation = p.parse(raw, canonical_required=True)
        p.need(type(invocation) is dict and set(invocation) ==
               {'submission', 'producer_stopped_attested', 'protocol_complete', 'committed_rounds', 'private_inputs'},
               'Exact trusted invocation schema')
        p.need(p.valid_pin(invocation['submission'], allow_empty=True) and type(invocation['private_inputs']) is dict
               and set(invocation['private_inputs']) == PRIVATE_NAMES
               and all(p.valid_pin(v) for v in invocation['private_inputs'].values()),
               'Exact declared submission/private descriptors without private reads')
        phase = 'public_submission'
        p.need(invocation['producer_stopped_attested'] is True and invocation['protocol_complete'] is True
               and type(invocation['committed_rounds']) is int and invocation['committed_rounds'] == p.ROUNDS,
               'Complete stopped producer protocol required before private reads')
        means, identities = admit_submission('/submission/commits.jsonl', invocation['submission'], counters, tick)
        phase = 'generated_controls'
        generated = score_generated_checks.run_checks(score_core, tick=tick)
        counters['generated_score_controls'] = generated['checks']
        phase = 'private_contract'
        receipt = private_json('prepare_receipt.json', invocation, p.PREP_CAPS['prepare_receipt.json'], counters)
        p.need(receipt['status'] == 'rtt_neural_causal_packet_prepared' and receipt['complete'] is True and
               receipt['candidate_id'] == 'NEURAL-024' and receipt['protocol'] == p.PROTOCOL and
               receipt['inputs_sha256'] == args.inputs_sha256 and
               set(receipt['files']) == set(p.PREP_CAPS) - {'prepare_receipt.json'},
               'Complete exact preparation receipt')
        for name in ('observations.jsonl', 'schedule.json', 'references.json'):
            p.need(receipt['files'][name] == invocation['private_inputs'][name],
                   'Current private inputs join the sealed prepared artifacts')
        p.need(receipt['input_identity_pins'] ==
               {k: {z: v[z] for z in ('bytes', 'sha256')} for k, v in config['data'].items()},
               'Preparation joins exactly the original three qualified count projections')
        ref_pin = {k: config['reference_scores'][k] for k in ('bytes', 'sha256')}
        p.need(receipt['reference_scores_pin'] == ref_pin and receipt['files']['references.json'] == ref_pin,
               'Verbatim immutable completed six-arm reference')
        schedule = private_json('schedule.json', invocation, p.PREP_CAPS['schedule.json'], counters)
        p.need(type(schedule) is dict and set(schedule) ==
               {'candidate_id', 'first_target_bin', 'warmup_rounds', 'scored_rounds', 'intervals'} and
               schedule['candidate_id'] == 'NEURAL-024' and
               type(schedule['first_target_bin']) is int and schedule['first_target_bin'] == p.FIRST and
               type(schedule['warmup_rounds']) is int and schedule['warmup_rounds'] == p.WARMUP and
               type(schedule['scored_rounds']) is int and schedule['scored_rounds'] == p.SCORED and
               type(schedule['intervals']) is list and len(schedule['intervals']) == p.ROUNDS,
               'Complete fixed private clock-only schedule')
        prior_end = None
        for item in schedule['intervals']:
            p.interval(item)
            p.need(prior_end is None or item[0] == prior_end, 'Exact native schedule continuity')
            p.need(abs((item[1] - item[0]) - .02) <= 1e-7, 'Native interval duration tolerance')
            prior_end = item[1]
        p.need(abs(schedule['intervals'][0][0] - 60.) <= 1e-7 and
               abs(schedule['intervals'][10][0] - 60.2) <= 1e-7 and
               abs(schedule['intervals'][-1][1] - 502.) <= 1e-7, 'Fixed warm-up/scored physical support')
        targets = private_targets(invocation, schedule, identities, counters, tick)
        references = private_json('references.json', invocation, p.PREP_CAPS['references.json'], counters)
        phase = 'scoring'
        result = score_core.score(targets[p.WARMUP:], means[p.WARMUP:], references, tick=tick)
        if result['status'] == 'candidate_poisson_score_completed':
            status = 'scored'
            counters['scored_rows'] = p.SCORED
            counters['unscored_warmup_rows'] = p.WARMUP
        else:
            p.need(result['status'] == 'numerical_failure', 'Explicit bounded scientific failure status')
            status = 'numerical_failure'
            error = result.get('error', result.get('reason', 'Unsupported finite arithmetic'))
        tick()
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)[:1800]
        status = ('invalid_submission' if phase == 'public_submission' and
                  isinstance(exc, (ValueError, TypeError, OverflowError)) else 'numerical_failure')
        result = None
    if status == 'scored':
        score = dict(result)
        score['science_status'] = score['status']
        score['status'] = status
    else:
        score = {'status': status, 'candidate_score': None, 'bits_per_spike_vs_calibration_rate': None,
                 'comparisons': None, 'error': error, 'failure_phase': phase}
    score.update(candidate_id='NEURAL-024', protocol=p.PROTOCOL,
                 complete_scored_panel=status == 'scored', causal_interface_scope='trusted_controller_attested',
                 warmup_predictions_required_but_unscored=10)
    score_pin = writer.json('score.json', score)
    receipt = {'status': status, 'candidate_id': 'NEURAL-024', 'protocol': p.PROTOCOL,
               'error': error, 'failure_phase': None if status == 'scored' else phase,
               'inputs_sha256': args.inputs_sha256, 'invocation_sha256': args.invocation_sha256,
               'files': {'score.json': score_pin}, 'counters': counters,
               'generated_checks': generated, 'elapsed_seconds': time.monotonic() - start,
               'complete_scored_panel': status == 'scored',
               'invalid_submission_private_reads_zero': (counters['private_reads_attempted'] == 0
                                                         if status == 'invalid_submission' else None),
               'incomplete_operation_extent_unknown': (
                   counters['submission_reads_attempted'] != counters['submission_reads_completed'] or
                   counters['private_reads_attempted'] != counters['private_reads_completed'] or
                   writer.attempted != writer.completed)}
    writer.json('grade_receipt.json', receipt)
    print(p.canonical({'status': status, 'files': writer.pins, 'counters': counters}).decode('ascii'), end='')
    # A sealed failure disposition is a completed grading process, not a score.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
