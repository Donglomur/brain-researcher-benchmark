"""Trusted arbitrary velocity-submission validator/scorer; no candidate code or fits."""
from pathlib import Path
import hashlib
import json
import math
import os
import resource
import sys
import time
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import io_contract as contract
import reference_core as metric

ARMS = ('phase_only', 'raw137', 'pca10', 'random10')
REFERENCE_FREEZE = '4d004f6bc17b0b26713759ed9b6bb20a53ddfef7e25f90ca56586ac2e8698555'
REFERENCE_FILES = {'selection.json', 'phase_only.npz', 'raw137.npz', 'pca10.npz',
                   'random10.npz', 'raw137_model.npz', 'pca10_model.npz', 'random10_model.npz'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_text(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def pinned(path, pin, cap):
    require(type(pin['bytes']) is int and 0 < pin['bytes'] <= cap and sha256_text(pin['sha256']),
            'Invalid bounded asset pin')
    path = contract.regular(path, cap)
    require(path.stat().st_size == pin['bytes'] and contract.sha(path) == pin['sha256'],
            'Pinned operator/public asset changed: ' + str(path))
    return path


def score_value(value, name):
    require(value is None or (type(value) in (int, float) and math.isfinite(value)),
            'Nonfinite or invalid score: ' + name)
    return None if value is None else float(value)


def difference(candidate, reference, name):
    if candidate is None or reference is None:
        return None
    return score_value(candidate - reference, name)


def close_reference_value(value, independent, name):
    value = score_value(value, name)
    independent = score_value(independent, 'independent ' + name)
    if value is None or independent is None:
        require(value is None and independent is None, 'Reference undefined-state mismatch: ' + name)
    else:
        require(abs(value - independent) <= 1e-10 + 1e-10 * abs(independent),
                'Reference arithmetic receipt mismatch: ' + name)
    return value


def qualified_reference(assets):
    """Read only pinned reference evidence, after the candidate validation gate."""
    grade_path = pinned('/input/reference_grade.json', assets['private']['reference_grade'], 2000000)
    commit_path = pinned('/input/reference_commit.json', assets['private']['reference_commit'], 262144)
    grade = json.loads(grade_path.read_text())
    commit = json.loads(commit_path.read_text())
    require(assets['reference_source_freeze'] == REFERENCE_FREEZE
            and commit['source_freeze_sha256'] == REFERENCE_FREEZE
            and commit['status'] == 'predictions_frozen_before_private_grade'
            and commit['producer_removed_and_absent'] is True
            and sha256_text(commit['producer_execution_sha256'])
            and set(commit['files']) == REFERENCE_FILES, 'Exact stopped/frozen four-stream reference lineage required')
    for pin in commit['files'].values():
        require(type(pin['bytes']) is int and 0 < pin['bytes'] <= 3000000
                and sha256_text(pin['sha256']), 'Invalid committed reference output identity')
    require(grade['status'] == 'scored_with_independent_arithmetic_check'
            and grade['scientific_score_computed'] is True
            and grade['all_public_submissions_validated_before_targets'] is True
            and grade['target_loader_invocations'] == 1 and grade['new_fits'] == 0
            and grade['pass_threshold'] is None and grade['trial_count'] == 126
            and grade['groups'] == 8 and grade['units'] == 'm/s'
            and set(grade['metrics']) == set(ARMS) and set(grade['validations']) == set(ARMS),
            'Qualified complete four-arm reference grade required')
    independent = grade['independent_arithmetic']
    require(independent['passed'] is True and independent['checks'] == 704
            and independent['trials'] == 126 and independent['groups'] == 8
            and independent['fits_performed_by_auditor'] == 0
            and independent['reference_core_imported_by_auditor'] is False
            and independent['tolerance'] == {'absolute': 1e-10, 'relative_to_independent_value': 1e-10}
            and set(independent['metrics']) == set(ARMS), 'Pinned scalar-arithmetic qualification required')
    held = assets['held_trial_types']
    require(type(held) is list and len(held) == 8 and all(type(value) is int for value in held)
            and len(set(held)) == 8, 'Exactly eight frozen assessment groups required')
    values = {}
    group_counts = None
    for arm in ARMS:
        validation = grade['validations'][arm]
        require(validation['status'] == 'public_submission_valid' and validation['cases'] == 126
                and validation['bins'] == 140 and validation['axes'] == ['x', 'y']
                and validation['units'] == 'm/s' and validation['target_loader_invocations'] == 0,
                'Reference public-submission qualification missing: ' + arm)
        row = grade['metrics'][arm]
        scalar_row = independent['metrics'][arm]
        entries = row['per_type']
        require(len(entries) == 8 and all(type(item['trial_type']) is int
                and type(item['trials']) is int and item['trials'] > 0 for item in entries),
                'Reference group identities/counts invalid')
        counts = {item['trial_type']: item['trials'] for item in entries}
        require(set(counts) == set(held) and sum(counts.values()) == 126,
                'Reference omitted or duplicated an assessment group')
        require(group_counts is None or counts == group_counts, 'Reference group counts differ across arms')
        group_counts = counts
        macro = close_reference_value(row['macro_r2'], scalar_row['macro_r2'], arm + ' macro')
        pooled = close_reference_value(row['pooled']['uniform_axis_r2'],
                                       scalar_row['pooled']['uniform_axis_r2'], arm + ' pooled')
        require(type(row['defined']) is bool and row['defined'] == (macro is not None),
                'Reference defined-state mismatch')
        values[arm] = {'macro_r2': macro, 'pooled_uniform_axis_r2': pooled}
    return values, group_counts


def frozen_submission(expected_sha256):
    source = contract.regular('/input/submission.npz', contract.MAX_BYTES)
    destination = Path('/tmp/submission.npz')
    digest = hashlib.sha256()
    total = 0
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        while block := incoming.read(65536):
            total += len(block)
            require(total <= contract.MAX_BYTES, 'Candidate grew beyond the submission cap')
            digest.update(block)
            outgoing.write(block)
    destination.chmod(0o400)
    require(digest.hexdigest() == expected_sha256, 'Candidate changed after host SHA256 binding')
    return destination


def main():
    start = time.monotonic()
    stage = 'operator_inputs'
    result = {'candidate_id': 'NEURAL-019', 'status': 'started', 'prediction_contract_valid': False,
              'candidate_code_executed': False, 'target_loader_invocations': 0, 'new_fits': 0,
              'scientific_score_computed': False, 'scientific_success': None,
              'scientific_success_threshold': None}
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in ('score', 'validate'), 'Action must be score or validate')
        action = sys.argv[1]
        assets = json.loads((HERE / 'assets.json').read_text())
        require(assets['candidate_id'] == 'NEURAL-019', 'Exact task asset manifest required')
        path = pinned('/input/public.npz', assets['public']['packet'], 65000000)
        with np.load(path, allow_pickle=False) as packet:
            public = {key: packet['assessment_trial_ids' if key == 'trial_ids' else key]
                      for key in ('trial_ids', 'velocity_left_edges_ms', 'velocity_axes',
                                  'velocity_units', 'panel_fingerprint')}
        expected = os.environ.get('EXPECTED_SUBMISSION_SHA256')
        require(sha256_text(expected), 'Host must bind the exact candidate SHA256')
        stage = 'candidate_validation'
        frozen = frozen_submission(expected)
        prediction, validation = contract.validate_candidate(contract.candidate_npz(frozen), public)
        result.update(prediction_contract_valid=True, validation=validation, submission_sha256=expected)
        if action == 'validate':
            result.update(status='valid_prediction_contract', units='m/s', private_assets_read=False)
            return result, 0
        stage = 'private_score'
        references, reference_counts = qualified_reference(assets)
        gold_path = pinned('/input/gold.npz', assets['private']['targets'], 1000000)
        result['target_loader_invocations'] = 1
        with np.load(gold_path, allow_pickle=False) as archive:
            gold = {key: archive[key] for key in archive.files}
        require(set(gold) == {'velocity', 'trial_ids', 'trial_types', 'velocity_left_edges_ms',
                             'velocity_axes', 'velocity_units', 'panel_fingerprint'},
                'Exact private target field allowlist required')
        require(all(np.array_equal(gold[key], value) for key, value in public.items()),
                'Exact private/public trial, axis, clock, unit and fingerprint join required')
        require(gold['velocity'].shape == (126, 140, 2) and gold['velocity'].dtype == np.dtype('float64')
                and np.isfinite(gold['velocity']).all(), 'Exact finite target geometry required')
        groups = gold['trial_types']
        require(groups.shape == (126,) and groups.dtype.kind in 'iu'
                and set(groups.tolist()) == set(assets['held_trial_types']),
                'All eight frozen assessment groups required')
        counts = {int(group): int(np.count_nonzero(groups == group)) for group in np.unique(groups)}
        require(counts == reference_counts, 'Candidate target panel and reference group counts differ')
        metrics = metric.metrics(gold['velocity'], prediction, groups)
        macro = score_value(metrics['macro_r2'], 'candidate macro')
        pooled = score_value(metrics['pooled']['uniform_axis_r2'], 'candidate pooled')
        signed = {'candidate_minus_' + arm:
                  {'macro_r2': difference(macro, values['macro_r2'], arm + ' macro difference'),
                   'pooled_uniform_axis_r2': difference(pooled, values['pooled_uniform_axis_r2'],
                                                       arm + ' pooled difference')}
                  for arm, values in references.items()}
        result.update(status='scored', scientific_score_computed=True, metrics=metrics,
                      primary_metric=macro, metric_name='equal_group_macro_uniform_axis_r2',
                      higher_is_better=True, reference_values=references, signed_differences=signed,
                      units='m/s', trial_count=126, groups=8,
                      panel_fingerprint=contract.scalar(public['panel_fingerprint']),
                      reference_lineage={'source_freeze_sha256': REFERENCE_FREEZE,
                                         'grade_sha256': assets['private']['reference_grade']['sha256'],
                                         'commit_sha256': assets['private']['reference_commit']['sha256'],
                                         'prior_independent_arithmetic_checks': 704,
                                         'reference_predictions_recomputed': False},
                      reference_scope='Fixed authored development references; no published SOTA or scientific acceptance floor',
                      limits=['One macaque/session; maze groups and trials are not independent animals.',
                              'Historical public MC_Maze source; prior017/018 use and current movement-reference assessment are exposed.',
                              'Retrospective movement-aligned task with symmetric neural and target filters; not causal or online.',
                              'PCA10 versus random10 is the matched reference contrast; raw137 has different feature capacity.',
                              'Prediction accuracy does not establish biological mechanisms, true latent states or native LLM understanding.'])
        return result, 0
    except Exception as exc:
        result.update(status='invalid_submission' if stage == 'candidate_validation' else 'scoring_error',
                      error=type(exc).__name__ + ': ' + str(exc), scientific_score_computed=False)
        return result, 2
    finally:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result['resources'] = {'elapsed_seconds': time.monotonic() - start,
                               'cpu_seconds_including_imports': usage.ru_utime + usage.ru_stime,
                               'peak_rss_bytes': usage.ru_maxrss * 1024,
                               'cgroup_peak_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text())}


if __name__ == '__main__':
    value, code = main()
    print(json.dumps(value, allow_nan=False, separators=(',', ':')))
    raise SystemExit(code)
