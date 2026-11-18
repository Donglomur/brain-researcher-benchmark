"""Evaluate one complete, externally selected NEURAL-099 paired collection.

The production entry point always authenticates the fixed full cases/packet.
It validates both complete prediction arms, then replays every original history
observation and token, and only then decodes response counts for the unchanged
scorer. It never launches a participant, trains a model, or opens an NWB.

Pinned finish/closure documents are operator-selected evidence, not proof of
actual isolation, process state or successful runtime enforcement. The operator
must qualify those facts separately. A self-consistent journal alone is not
accepted. The underscore-prefixed record functions are internal test seams,
not a generated-data or partial-production command.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from access import profile, schedule
from cli import CASE_FILE_SHA, manifest as collection_manifest, read_json, strict_json
from dependencies import load
from observations import ObservationAdapter
from session import ARMS, EDGES, canonical, digest, check_hash, validate_study_id
from transports import build_request

SCORER = load('scoring')
PACKET = load('count_packet')
VISIBLE = ('case_id', 'animal_id', 'asset_id', 'region',
           'source_trial_row', 'source_cluster_count')
MAX_FILES = 5238 * 2 + 2
MAX_RECORD_BYTES = 262144
MAX_JOURNAL_BYTES = 2 ** 32


def _require(value, message):
    if not value:
        raise ValueError(message)


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink, stat.S_IMODE(info.st_mode))


def _read_fd(fd, cap, *, expected_bytes=None):
    before = os.fstat(fd)
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
             'A single-link regular file is required')
    _require(0 <= before.st_size <= cap, 'File exceeds its byte bound')
    if expected_bytes is not None:
        _require(before.st_size == expected_bytes, 'Pinned file extent differs')
    chunks = bytearray()
    while len(chunks) <= cap:
        part = os.read(fd, min(65536, cap + 1 - len(chunks)))
        if not part:
            break
        chunks.extend(part)
    _require(len(chunks) == before.st_size and len(chunks) <= cap
             and _signature(os.fstat(fd)) == _signature(before),
             'File changed or exceeded its byte bound')
    return bytes(chunks), _signature(before)


def _read_pin(path, expected_bytes, expected_sha256, cap):
    _require(type(expected_bytes) is int and 0 < expected_bytes <= cap,
             'Invalid pinned document byte bound')
    check_hash(expected_sha256)
    _require(type(path) is str and Path(path).is_absolute(),
             'Pinned document path must be absolute')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
                 | getattr(os, 'O_CLOEXEC', 0))
    try:
        data, _ = _read_fd(fd, cap, expected_bytes=expected_bytes)
    finally:
        os.close(fd)
    _require(hashlib.sha256(data).hexdigest() == expected_sha256,
             'Pinned document digest differs')
    return strict_json(data)


class _JournalFiles:
    """Bounded, task-specific private journal reader; no participant access."""
    def __init__(self, path, max_files):
        _require(type(max_files) is int and 0 < max_files <= MAX_FILES,
                 'Invalid journal file-count bound')
        _require(Path(path).is_absolute(), 'Journal path must be absolute')
        self._fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW
                           | getattr(os, 'O_DIRECTORY', 0)
                           | getattr(os, 'O_CLOEXEC', 0))
        try:
            info = os.fstat(self._fd)
            _require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700,
                     'Private journal directory must have mode0700')
            self._signature = _signature(info)
            names = os.listdir(self._fd)
            _require(len(names) <= max_files, 'Journal has too many files')
            self.names = frozenset(names)
            self._read_signatures = {}
        except BaseException:
            os.close(self._fd)
            self._fd = None
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def read(self, name, cap):
        _require(name in self.names and '/' not in name and name not in ('.', '..'),
                 'Unknown journal member')
        _require(name not in self._read_signatures, 'Journal members are read once')
        fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
                     | getattr(os, 'O_CLOEXEC', 0), dir_fd=self._fd)
        try:
            _require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o600,
                     'Private journal members must have mode0600')
            data, signature = _read_fd(fd, cap)
        finally:
            os.close(fd)
        self._read_signatures[name] = signature
        return data

    def verify_unchanged(self):
        _require(self._fd is not None and _signature(os.fstat(self._fd)) == self._signature,
                 'Journal directory changed')
        _require(frozenset(os.listdir(self._fd)) == self.names,
                 'Journal inventory changed')
        for name, signature in self._read_signatures.items():
            info = os.stat(name, dir_fd=self._fd, follow_symlinks=False)
            _require(stat.S_ISREG(info.st_mode) and _signature(info) == signature,
                     'Journal member changed after reading')


def _validate_evidence(manifest, manifest_sha, finish, finish_sha, closure):
    """Check selected document consistency; do not attest to runtime facts."""
    check_hash(manifest_sha)
    check_hash(finish_sha)
    _require(type(finish) is dict and set(finish) == {'operation', 'completion'}
             and finish['operation'] == 'finish' and type(finish['completion']) is dict,
             'Exact successful operator finish document required')
    done = finish['completion']
    _require(done.get('study_id') == manifest['study_id']
             and done.get('procedures') == manifest['procedure_hashes']
             and done.get('production') is True
             and done.get('state') == 'all_configured_predictions_locked'
             and done.get('cases_per_arm') == {arm: 9867 for arm in ARMS}
             and type(done.get('trials_per_arm')) is int and done['trials_per_arm'] == 5238,
             'Finish document is not for the complete selected production pair')
    expected = {
        'schema': 'neural099-selected-collection-closure/v1',
        'study_id': manifest['study_id'], 'manifest_sha256': manifest_sha,
        'finish_receipt_sha256': finish_sha, 'exit_code': 0,
        'owned_process_group_absent': True, 'lease_closed': True,
    }
    _require(type(closure) is dict and canonical(closure) == canonical(expected),
             'Externally selected closure evidence is missing or inconsistent')


def _visible(cases):
    return [{field: case[field] for field in VISIBLE} for case in cases]


def _no_history(*args, **kwargs):
    raise AssertionError('Prediction admission must not request history')


def _verify_locked_pair(cases, schedule_rows, reader, *, study_id, procedures,
                        finish, max_record_bytes, max_journal_bytes):
    """Internal finite record verification, before history or response access."""
    validate_study_id(study_id)
    _require(type(procedures) is dict and set(procedures) == set(ARMS),
             'Both frozen procedures are required')
    for value in procedures.values():
        check_hash(value)
    _require(type(max_record_bytes) is int and 0 < max_record_bytes <= MAX_RECORD_BYTES
             and type(max_journal_bytes) is int
             and max_record_bytes <= max_journal_bytes <= MAX_JOURNAL_BYTES,
             'Invalid finite journal limits')
    adapter = ObservationAdapter(cases, _no_history)
    _require(type(schedule_rows) is list and schedule_rows, 'Nonempty selected schedule required')
    keys = [(row['asset_id'], row['source_trial_row']) for row in schedule_rows]
    _require(len(keys) == len(set(keys)) and set(keys) == set(adapter.keys()),
             'Schedule does not cover the complete case roster once')
    for row in schedule_rows:
        _require(set(row) == {'outer_fold', 'animal_id', 'asset_id', 'source_trial_row'}
                 and type(row['outer_fold']) is int and 0 <= row['outer_fold'] < 5,
                 'Invalid selected schedule row')
        _require(all(case['animal_id'] == row['animal_id']
                     for case in adapter.group_cases((row['asset_id'], row['source_trial_row']))),
                 'Schedule animal differs from selected cases')
    records = len(schedule_rows) * len(ARMS)
    expected_names = {'BEGIN.json', 'COMPLETE.json'} | {f'{i:06d}.json' for i in range(records)}
    _require(set(reader.names) == expected_names and len(reader.names) == len(expected_names),
             'Missing, duplicate or extra journal members')
    chain, total = '0' * 64, 0

    def read(name):
        nonlocal chain, total
        body = reader.read(name, max_record_bytes)
        _require(type(body) is bytes and 0 < len(body) <= max_record_bytes,
                 'Journal record exceeds its byte bound')
        total += len(body)
        _require(total <= max_journal_bytes, 'Journal exceeds cumulative byte bound')
        value = strict_json(body)
        _require(type(value) is dict and canonical(value) + b'\n' == body,
                 'Journal record is not exact canonical JSON with newline')
        sha = hashlib.sha256(body).hexdigest()
        chain = hashlib.sha256(bytes.fromhex(chain) + bytes.fromhex(sha)).hexdigest()
        return value, sha

    begin, _ = read('BEGIN.json')
    nonce = check_hash(begin.get('attempt_nonce'))
    production = begin.get('production')
    _require(type(production) is bool, 'Invalid journal production flag')
    expected_begin = {
        'schema': 'neural099-paired-study-start/v1', 'study_id': study_id,
        'attempt_nonce': nonce, 'production': production,
        'case_metadata_sha256': digest(cases), 'procedures': procedures,
        'arms': list(ARMS), 'profiles': [profile(arm) for arm in ARMS],
        'cases_per_arm': len(cases), 'trials_per_arm': len(schedule_rows),
        'schedule_sha256': digest(schedule_rows),
        'state': 'incomplete_no_score_or_label_release',
    }
    _require(canonical(begin) == canonical(expected_begin), 'Journal BEGIN differs from selection')
    predictions = {arm: [] for arm in ARMS}
    replay = []
    record_fields = {'schema', 'study_id', 'attempt_nonce', 'trial_ordinal', 'outer_fold',
                     'condition_id', 'procedure_sha256', 'trial_token', 'payload_sha256',
                     'predictions_sha256', 'predictions'}
    for ordinal, row in enumerate(schedule_rows):
        current_cases = adapter.group_cases((row['asset_id'], row['source_trial_row']))
        expected_ids = [case['case_id'] for case in current_cases]
        replay_pair = []
        for arm_index, arm in enumerate(ARMS):
            record, _ = read(f'{ordinal * len(ARMS) + arm_index:06d}.json')
            _require(set(record) == record_fields, 'Invalid locked record fields')
            identity = {'schema': 'neural099-locked-prediction/v1', 'study_id': study_id,
                        'attempt_nonce': nonce, 'trial_ordinal': ordinal,
                        'outer_fold': row['outer_fold'], 'condition_id': arm,
                        'procedure_sha256': procedures[arm]}
            _require(all(type(record[key]) is type(value) and record[key] == value
                         for key, value in identity.items()),
                     'Locked record identity, ordering or procedure differs')
            token = check_hash(record['trial_token'])
            payload_sha = check_hash(record['payload_sha256'])
            supplied = record['predictions']
            _require(type(supplied) is list and len(supplied) == len(expected_ids),
                     'Incomplete current-trial predictions')
            _require(all(type(item) is dict and set(item) == {'case_id', 'rates'} for item in supplied)
                     and [item['case_id'] for item in supplied] == expected_ids,
                     'Changed current-trial prediction identity or canonical order')
            _require(record['predictions_sha256'] == digest(supplied),
                     'Locked predictions digest differs')
            predictions[arm].extend(supplied)
            replay_pair.append((token, payload_sha))
        replay.append(tuple(replay_pair))
    prior_chain = chain
    complete, complete_sha = read('COMPLETE.json')
    expected_result = {
        'schema': 'neural099-paired-completion/v1', 'study_id': study_id,
        'attempt_nonce': nonce, 'production': production,
        'state': 'all_configured_predictions_locked',
        'cases_per_arm': {arm: len(cases) for arm in ARMS},
        'trials_per_arm': len(schedule_rows), 'fold_groups': 5,
        'case_metadata_sha256': digest(cases), 'procedures': procedures,
        'score_and_label_release': 'eligible_for_separate_evaluator_admission_only',
        'scores_computed': 0, 'target_values_released': 0,
    }
    expected_complete = dict(expected_result,
                             requires_successful_operator_finish_receipt=True,
                             locked_records=records, prior_chain_sha256=prior_chain)
    _require(canonical(complete) == canonical(expected_complete),
             'Collection COMPLETE is missing or inconsistent')
    expected_finish = {'operation': 'finish', 'completion': dict(
        expected_result, journal_receipt={'record_sha256': complete_sha,
                                        'chain_sha256': chain, 'logical_bytes': total})}
    _require(canonical(finish) == canonical(expected_finish),
             'Successful external finish receipt does not bind the complete journal')
    visible = _visible(cases)
    # Admit BOTH complete arms before invoking even the history projection.
    # Replace each assembled representation with the scorer's canonical copy.
    for arm in ARMS:
        admitted = SCORER.admit_predictions(visible, predictions[arm], edges_seconds=EDGES)
        predictions[arm] = [{'case_id': case['case_id'], 'rates': admitted[case['case_id']]}
                            for case in visible]
    reader.verify_unchanged()
    return {'predictions': predictions, 'replay': replay, 'attempt_nonce': nonce,
            'chain_sha256': chain, 'journal_bytes': total, 'records': records,
            'production': production, 'visible_cases': visible}


def _verify_payloads(cases, schedule_rows, locked, *, study_id, procedures, history_projection):
    adapter = ObservationAdapter(cases, history_projection)
    for ordinal, row in enumerate(schedule_rows):
        observations = adapter.observations(row['asset_id'], row['source_trial_row'],
                                            view='timing_history')
        # Exact recipe from unchanged Study.current(), using session.digest.
        token = digest({'study_id': study_id, 'attempt_nonce': locked['attempt_nonce'],
                        'procedures': procedures, 'ordinal': ordinal, 'schedule_row': row})
        for index, arm in enumerate(ARMS):
            request = build_request(profile(arm), observations, study_id, token)
            _require(locked['replay'][ordinal][index] == (token, request['payload_sha256']),
                     'Locked observation payload or original trial token differs')


def _evaluate_records(cases, schedule_rows, reader, *, study_id, procedures, finish,
                      history_projection, load_response_gold,
                      max_record_bytes, max_journal_bytes):
    """Internal generated-test seam; public entry point supplies authenticated inputs."""
    locked = _verify_locked_pair(cases, schedule_rows, reader, study_id=study_id,
                                 procedures=procedures, finish=finish,
                                 max_record_bytes=max_record_bytes,
                                 max_journal_bytes=max_journal_bytes)
    _verify_payloads(cases, schedule_rows, locked, study_id=study_id,
                     procedures=procedures, history_projection=history_projection)
    reader.verify_unchanged()
    # The first response-count access occurs only after every preceding check.
    gold = load_response_gold()
    scores = {arm: SCORER.score(locked['visible_cases'], locked['predictions'][arm], gold,
                               edges_seconds=EDGES, coarsening_factor=5) for arm in ARMS}
    reader.verify_unchanged()
    return {
        'schema': 'neural099-complete-pair-evaluation/v1', 'study_id': study_id,
        'cases_per_arm': len(cases), 'trials_per_arm': len(schedule_rows),
        'locked_records': locked['records'], 'journal_chain_sha256': locked['chain_sha256'],
        'journal_logical_bytes': locked['journal_bytes'], 'procedures': dict(procedures),
        'scores': scores, 'response_access_after_both_arms_and_all_payload_checks': True,
        'candidate_runtime_qualified': False,
        'external_evidence_scope': 'Operator-selected pinned document consistency only; no runtime or isolation attestation',
        'graphical_viewer_or_live_tool_agent': False,
    }


def _write_result(path, value, max_bytes):
    _require(type(max_bytes) is int and 0 < max_bytes <= 65536,
             'Explicit bounded score-output size required')
    _require(type(path) is str and Path(path).is_absolute(), 'Output path must be absolute')
    data = canonical(value) + b'\n'
    _require(len(data) <= max_bytes, 'Score output exceeds its byte bound')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                 | getattr(os, 'O_CLOEXEC', 0), 0o600)
    try:
        os.fchmod(fd, 0o600)
        remainder = memoryview(data)
        while remainder:
            n = os.write(fd, remainder)
            _require(n > 0, 'No score-output write progress')
            remainder = remainder[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(Path(path).parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def evaluate_sealed_pair(*, manifest_path, manifest_bytes, manifest_sha256,
                         finish_path, finish_bytes, finish_sha256,
                         closure_path, closure_bytes, closure_sha256,
                         output_path, max_output_bytes=65536):
    """Production-only evaluator. Never pass its inputs or output stream to candidates."""
    selected = collection_manifest(_read_pin(manifest_path, manifest_bytes, manifest_sha256, 65536))
    finish = _read_pin(finish_path, finish_bytes, finish_sha256, 65536)
    closure = _read_pin(closure_path, closure_bytes, closure_sha256, 65536)
    _validate_evidence(selected, manifest_sha256, finish, finish_sha256, closure)
    cases = read_json(selected['cases_path'], 3 * 1024 ** 2, CASE_FILE_SHA)
    selected_schedule = schedule(cases, production=True)
    # Exact full production metadata is admitted before the packet opens.
    with PACKET.verify_packet(selected['packet_path'], cases, selected['packet_binding'],
                              max_bytes=15787200) as packet:
        def load_gold():
            rows = []
            for case in cases:
                decoded = packet.read_private(case['case_id'])
                _require(decoded['case'] == case, 'Response identity differs from selected cases')
                rows.append({'case': {field: case[field] for field in VISIBLE},
                             'counts': decoded['response_counts']})
            return rows
        with _JournalFiles(selected['output_path'], MAX_FILES) as journal:
            result = _evaluate_records(
                cases, selected_schedule, journal, study_id=selected['study_id'],
                procedures=selected['procedure_hashes'], finish=finish,
                history_projection=packet.history_projection, load_response_gold=load_gold,
                max_record_bytes=selected['max_record_bytes'],
                max_journal_bytes=selected['max_journal_bytes'])
    result['selected_input_documents'] = {
        'collection_manifest': {'bytes': manifest_bytes, 'sha256': manifest_sha256},
        'successful_finish': {'bytes': finish_bytes, 'sha256': finish_sha256},
        'closure_evidence': {'bytes': closure_bytes, 'sha256': closure_sha256},
    }
    return _write_result(output_path, result, max_output_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'finish', 'closure'):
        parser.add_argument('--' + name + '-path', required=True)
        parser.add_argument('--' + name + '-bytes', required=True, type=int)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--output-path', required=True)
    parser.add_argument('--max-output-bytes', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_sealed_pair(**vars(args)), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'failed_or_incomplete', 'error_type': type(error).__name__,
                          'scores_released': False}), file=sys.stderr)
        raise SystemExit(2)
