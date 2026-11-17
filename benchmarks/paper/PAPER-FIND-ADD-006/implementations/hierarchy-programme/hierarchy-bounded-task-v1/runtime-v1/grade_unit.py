"""One held summary lifecycle with a bounded trusted-only full-score file.

Only the <=16 KiB terminal summary is read while the grader exists. The full
score is sealed, hashed and decoded after immutable-ID and name absence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid
from common import need, ordinary, strict_json
from runtime import SummaryEngine, mounts_for, SCORE_CAP, TERMINAL_CAP, GRADE_SECONDS

CHECK_NAMES = [
    'complete_valid_and_orientation_invariant_scoring',
    'malformed_nonfinite_oversized_and_invalid_tree_zero_private_callback',
    'missing_session_and_public_support_partition_zero_private_callback',
    'wrong_normalizer_scores_full_label_consistency_penalty',
    'alternate_topology_consistent_curves_union_heights_and_no_floor',
    'missing_reference_support_full_session_penalty_complete25_outcomes',
    'undefined_normalizers_raw_nulls_and_explicit_comparison_denominators',
    'equivalent_internal_ids_and_finite_extreme_distance_metrics',
]


def admit_checks(value):
    need(type(value) is dict and set(value) == {'status', 'cases', 'count', 'names', 'invented_only',
         'empirical_inputs_opened', 'model_fits', 'ward_optimizations', 'scope'},
         'Exact generated-guard summary fields')
    need(value['status'] == 'central_generated_checks_passed' and value['names'] == CHECK_NAMES
         and value['invented_only'] is True and value['scope'] ==
         'Invented structural/scoring controls only; no candidate or protected empirical body read',
         'Exact completed eight invented guard groups')
    need(all(type(value[key]) is int and value[key] == count for key, count in
         {'cases': 8, 'count': 8, 'empirical_inputs_opened': 0, 'model_fits': 0, 'ward_optimizations': 0}.items()),
         'Literal guard counts and zero empirical/fit/Ward control work')
    need(len(json.dumps(value, allow_nan=False, separators=(',', ':')).encode()) <= 8192,
         'Compact complete generated-guard summary')
    return value


class EvidenceSummaryEngine(SummaryEngine):
    def write(self, name, obj, cap=262144):
        if name != 'receipt.json':
            return super().write(name, obj, cap)
        body = (json.dumps(obj, indent=2, allow_nan=False) + '\n').encode()
        limit = min(cap, 262144)
        note = (json.dumps({'record_name': name, 'serialized_bytes': len(body), 'cap_bytes': limit,
                'full_record_retained_without_truncation': len(body) <= limit}, indent=2) + '\n').encode()
        self.budget.write(self.out / 'receipt_serialization.json', note, receipt=True, mode=0o444)
        need(len(body) <= limit, 'Bounded complete grader lifecycle receipt')
        self.budget.write(self.out / name, body, receipt=True, mode=0o444)
        return self.out / name


def admit_terminal(value, exit_code):
    need(type(value) is dict and set(value) == {'status', 'score_file', 'score_pin',
         'private_reference_reads', 'generated_checks'} and value['score_file'] == 'score.json',
         'Exact compact grader terminal protocol')
    need((exit_code, value['status']) in ((0, 'scored'), (2, 'invalid_submission')),
         'Existing scored/public-rejection exit/status pairs')
    expected = value['score_pin']
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= SCORE_CAP
         and type(expected['sha256']) is str and re.fullmatch('[a-f0-9]{64}', expected['sha256']) is not None,
         'Exact bounded full-score commitment')
    need(type(value['private_reference_reads']) is int
         and value['private_reference_reads'] == (2 if value['status'] == 'scored' else 0),
         'Exactly two private bodies after public admission; zero on public rejection')
    admit_checks(value['generated_checks'])
    return value


def stopped_score(folder, terminal):
    """Called only after the exact grader ID and name are independently absent."""
    need(folder.is_dir() and all(not p.is_symlink() for p in (folder, *folder.parents))
         and {p.name for p in folder.iterdir()} == {'score.json'}, 'Exactly one completed trusted score file')
    path = folder / 'score.json'; info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= SCORE_CAP,
         'Ordinary single-link bounded full score')
    need(stat.S_IMODE(info.st_mode) == 0o444, 'Trusted worker sealed score before publication')
    folder.chmod(0o555)
    body = ordinary(path, SCORE_CAP)
    observed = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    need(observed == terminal['score_pin'], 'Stopped full score matches terminal byte commitment')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    descriptor = os.open(folder, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    value = strict_json(body)
    need(type(value) is dict and value.get('status') == terminal['status'], 'Full-score and terminal status agree')
    need(value.get('private_reference_reads') == terminal['private_reference_reads'] and
         admit_checks(value.get('generated_checks')) == terminal['generated_checks'],
         'Full-score and terminal private accounting and exact guard summary agree')
    expected = {'private_loader_calls': 1, 'private_reference_reads': 2,
                'private_reference_read_attempts': 2} if value['status'] == 'scored' else {
                'private_loader_calls': 0, 'private_reference_reads': 0,
                'private_reference_read_attempts': 0}
    need(all(type(value.get(key)) is int and value[key] == count for key, count in expected.items()),
         'One private callback and two captured bodies only after complete public admission')
    return value, observed


def run_one(path, label, config, run, budget, end, negative_guards=False):
    run = Path(run).absolute(); path = Path(path).absolute(); started_at = time.monotonic()
    need(label == 'ordinary' and negative_guards is False, 'One ordinary hierarchy grader, no hidden guard execution')
    need(end - started_at >= GRADE_SECONDS, 'Full60-second grading envelope remains')
    grade_end = started_at + GRADE_SECONDS
    need(budget.limit == 22000000 and budget.reserve == 8000000,
         'Shared22MB host budget with8MB receipt reserve')
    outcome = strict_json(ordinary(run / 'unit/outcome_commit.json', 65536))
    need(type(outcome) is dict and outcome.get('unit_status') == 'unit_committed'
         and outcome.get('all_unit_resources_absent') is True and outcome.get('before_any_private_grade') is True,
         'Producer/holder/volume absent before creating trusted writable grade directory')
    need(path == run / 'unit/submission.json'
         and Path(config['grade_output_dir']) == run / 'grade', 'Exact committed submission and score paths')
    grade = run / 'grade'
    need(not grade.exists() and all(not p.is_symlink() for p in (grade, *grade.parents)), 'Fresh grade directory')
    budget.check(SCORE_CAP, receipt=True)
    grade.mkdir(mode=0o777); grade.chmod(0o777)
    folder = run / 'metadata' / label
    folder.mkdir(mode=0o755)
    engine = EvidenceSummaryEngine(grade_end, folder, budget)
    name = 'summary-score-' + uuid.uuid4().hex[:12]
    record = {'case': label, 'name': name, 'status': 'started', 'grade_envelope_seconds': GRADE_SECONDS,
              'full_score_host_decoded_before_absence': False, 'private_inputs_host_body_read': False}
    failure = None; terminal = None
    try:
        mounts = mounts_for(config, path)
        inspected, record['boundary'] = engine.create_summary(name, mounts)
        created_id = inspected['Id']; record['immutable_id'] = created_id
        need(time.monotonic() < grade_end - 10, 'Cleanup and complete score admission reserve')
        started = engine.run(['start', created_id], timeout=2)
        need(started.returncode == 0, 'Trusted grader startup by immutable ID')
        waited = engine.run(['wait', created_id], timeout=max(.001, grade_end - 10 - time.monotonic()))
        need(waited.returncode == 0, 'Trusted grader wait')
        observed = engine.inspect('container', name)
        state = observed['State']; record['exit_state'] = state
        need(observed['Id'] == created_id and state['Status'] == 'exited' and state['Running'] is False
             and state['Pid'] == 0 and type(state['ExitCode']) is int and state['ExitCode'] in (0, 2)
             and state['OOMKilled'] is False, 'Same immutable stopped grader and normal bounded exit')
        logs = engine.logs(created_id)
        # Preserve the returned bounded transport before any admission assertion.
        # SummaryEngine.run already limits each raw stream to 32 KiB. JSON escape
        # expansion of both streams fits this 512 KiB evidence cap/8 MB reserve.
        record['log_transport'] = {key: logs[key] for key in (
            'returncode', 'capture_truncated', 'captured_stdout_bytes',
            'captured_stderr_bytes')}
        log_body = (json.dumps(logs, ensure_ascii=False, allow_nan=False,
                               separators=(',', ':')) + '\n').encode()
        need(len(log_body) <= 524288, 'Bounded complete terminal transport evidence')
        budget.write(folder / 'terminal_transport.json', log_body, receipt=True, mode=0o444)
        record['terminal_transport_file'] = {
            'path': 'metadata/ordinary/terminal_transport.json',
            'bytes': len(log_body), 'sha256': hashlib.sha256(log_body).hexdigest()}
        need(logs['returncode'] == 0 and not logs['capture_truncated']
             and logs['captured_stdout_bytes'] <= TERMINAL_CAP and logs['captured_stderr_bytes'] == 0,
             'Complete compact terminal summary, no full-score log transport')
        terminal = admit_terminal(strict_json(logs['stdout']), state['ExitCode'])
        record.update(terminal=terminal, stdout_bytes=logs['captured_stdout_bytes'])
    except BaseException as error:
        failure = error; record.update(status='failed', error=repr(error)[:2000])
    finally:
        # Always remove/verify absence before full-score file access, including
        # timeout, malformed terminal and partial score-write paths.
        try:
            record['cleanup'] = engine.cleanup('container', name) if engine.owned else {
                'status': 'not_created', 'absence_verified': True}
        except BaseException as error:
            record['cleanup'] = {'absence_verified': False, 'error': repr(error)[:2000]}
        cleanup = record['cleanup']
        if failure is None:
            try:
                need(cleanup.get('absence_verified') is True and cleanup.get('id_absent') is True
                     and cleanup.get('name_absent') is True and cleanup.get('immutable_id') == record['immutable_id']
                     and cleanup.get('create_extent_unknown') is False, 'Exact grader ID/name absent before full-score read')
                result, score_pin = stopped_score(grade, terminal)
                budget.check(0, receipt=True)
                record.update(status='completed', result=result, score_pin=score_pin,
                              full_score_file='grade/score.json', full_score_status=result['status'])
            except BaseException as error:
                failure = error; record.update(status='failed', admission_error=repr(error)[:2000])
        # The full score is already retained once; keep this lifecycle receipt
        # compact while retaining record.result for the existing caller API.
        receipt = {key: value for key, value in record.items() if key != 'result'}
        receipt['full_result_returned_in_memory'] = 'result' in record
        engine.write('receipt.json', receipt)
    if failure is not None:
        raise failure
    need(record['status'] == 'completed' and record['cleanup']['absence_verified'] is True,
         'Completed grade only after owned-resource absence')
    return record
