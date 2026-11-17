"""Trusted public-first pair validation/grade. Invoked only in an offline unit."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import math
import sys
import numpy as np


def need(ok, message):
    if not ok:
        raise ValueError(message)


def strict(body):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            need(k not in out, 'Duplicate JSON key'); out[k] = v
        return out
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def read_pin(path, pin, cap=100_000):
    need(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1 and
         path.stat().st_size == pin['bytes'] and 0 < pin['bytes'] <= cap, 'Bounded pinned file')
    raw = path.read_bytes()
    need(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Exact file bytes')
    return raw


def pair_difference(cue, neural, truth, conditions, contexts):
    # Independently derive paired losses; do not infer increment from a report.
    rows = [abs(float(a) - float(y)) - abs(float(b) - float(y))
            for a, b, y in zip(cue, neural, truth, strict=True)]
    need(all(math.isfinite(v) for v in rows), 'Finite derived paired losses')
    def mean(values):
        values = list(values); value = math.fsum(x / len(values) for x in values)
        need(math.isfinite(value), 'Finite paired mean; no clipping'); return value
    result = {'cue_minus_neural_mae_ms': mean(rows),
            'by_condition': {str(k): {'n': int(np.sum(conditions == k)),
                'cue_minus_neural_mae_ms': mean(v for v, g in zip(rows, conditions) if g == k)} for k in range(40)},
            'by_context': {str(k): {'n': int(np.sum(contexts == k)),
                'cue_minus_neural_mae_ms': mean(v for v, g in zip(rows, contexts) if g == k)} for k in range(8)},
            'sign': 'positive means neural arm lower absolute error on this finite panel',
            'scientific_pass_floor': None, 'matched_method_proven': False,
            'RL_or_neural_understanding_reward': False}
    result['cue_minus_neural_eight_context_macro_mae_ms'] = mean(
        row['cue_minus_neural_mae_ms'] for row in result['by_context'].values())
    return result


def verify_paired_arithmetic(paired, cue_score, neural_score):
    """Check aggregate consistency without destroying a small paired increment.

    A subtraction of separately rounded large MAEs can lose a representable
    per-trial increment. The stable paired mean remains the reported metric.
    The 64-ULP envelope is a conservative arithmetic guard at the absolute-arm
    scale, not a scientific success threshold; no prediction/value is changed.
    """
    checks = []
    def compare(name, paired_value, cue_value, neural_value):
        direct = cue_value - neural_value
        need(all(math.isfinite(v) for v in (paired_value, cue_value, neural_value, direct)),
             'Finite derived arithmetic before consistency check')
        bound = 1e-10 + 64 * max(math.ulp(v) for v in (paired_value, cue_value, neural_value, direct))
        need(abs(paired_value - direct) <= bound, 'Independent paired arithmetic outside roundoff envelope')
        checks.append({'metric': name, 'aggregate_subtraction_ms': direct,
                       'absolute_difference_ms': abs(paired_value - direct), 'roundoff_bound_ms': bound})
    compare('mae_ms', paired['cue_minus_neural_mae_ms'], cue_score['mae_ms'], neural_score['mae_ms'])
    for group in ('by_condition', 'by_context'):
        for key, row in paired[group].items():
            cue, neural = cue_score[group][key], neural_score[group][key]
            need(row['n'] == cue['n'] == neural['n'], 'Same group support for paired arithmetic')
            compare(group + '/' + key, row['cue_minus_neural_mae_ms'], cue['mae_ms'], neural['mae_ms'])
    compare('eight_context_macro_mae_ms', paired['cue_minus_neural_eight_context_macro_mae_ms'],
            cue_score['eight_context_macro_mae_ms'], neural_score['eight_context_macro_mae_ms'])
    return checks


def run(root, out):
    result = {'candidate_id': 'NEURAL-095', 'status': 'started', 'private_target_reads': 0,
              'private_target_decodes': 0, 'private_reference_reads': 0,
              'new_fits_in_trusted_grader': 0, 'candidate_fit_count': 'not_measured_by_grader',
              'physical_read_scope': 'this isolated worker; host private hashes permitted only after successful validation-unit commit',
              'full_candidate_contract_complete': False, 'research_qualified': False}
    stage = 'operator_setup'
    try:
        config = strict((root / 'grade_contract.json').read_bytes())
        need(config['mode'] in ('validate', 'grade') and config['candidate_id'] == 'NEURAL-095', 'Fixed worker mode')
        for filename in ('validator.py', 'metrics.py'):
            read_pin(root / filename, config['sources'][filename])
        sys.path.insert(0, str(root))
        from validator import validate
        from metrics import score_candidate
        identity = strict(read_pin(root / 'identity.json', config['identity']))
        need(set(identity) == {'schema_version', 'case_id'} and identity['schema_version'] == 1 and
             len(identity['case_id']) == 258, 'Complete canonical public identity')
        ids = identity['case_id']; ordered = {}
        for arm in ('cue_only', 'neural'):
            read_pin(root / (arm + '.npz'), config['submissions'][arm], 1_048_576)
        stage = 'candidate_public_validation'
        for arm in ('cue_only', 'neural'):
            ordered[arm] = validate(root / (arm + '.npz'), ids)
        result.update(public_pair_validated=True, submissions=config['submissions'],
                      identity=config['identity'], joint_commit_sha256=config['joint_commit_sha256'])
        if config['mode'] == 'validate':
            result['status'] = 'valid_complete_pair'; return result
        stage = 'private_grade'
        need(config['prior_validation']['status'] == 'valid_complete_pair' and
             config['prior_validation']['submissions'] == config['submissions'] and
             config['prior_validation']['joint_commit_sha256'] == config['joint_commit_sha256'],
             'Same pair validated before this private-bearing worker')
        assets = strict(read_pin(root / 'assets.json', config['assets']))
        references = {}
        for key, filename in [('reference_grade', 'reference_grade.json'),
                              ('reference_commit', 'reference_commit.json'), ('reference_audit', 'reference_audit.json')]:
            references[key] = strict(read_pin(root / filename, assets['private'][key]))
            result['private_reference_reads'] += 1
        grade, commit, audit = (references[k] for k in ('reference_grade', 'reference_commit', 'reference_audit'))
        need(commit['status'] == 'producer_removed_outputs_committed' and commit['all_owned_producers_absent'] is True,
             'Original stopped reference lineage')
        for ck, pin in [('predictions', assets['verification_references']),
                        ('public_identity', assets['public']['identity']), ('private_targets', assets['private']['targets'])]:
            need(commit[ck] == {k: pin[k] for k in ('bytes', 'sha256')}, 'Original committed reference identities')
        need(grade['status'] == 'continuous_fixed_reference_panel_scored' and grade['candidate_id'] == 'NEURAL-095' and
             grade['predictions'] == commit['predictions'] and audit['status'] == 'passed' and
             audit['independent_scalar_checks'] == 280 and audit['score_sha256'] == assets['private']['reference_grade']['sha256'],
             'Audited original reference grade')
        result['private_target_reads'] += 1
        raw = read_pin(root / 'targets.npz', assets['private']['targets'])
        with np.load(io.BytesIO(raw), allow_pickle=False) as bundle:
            values = {key: bundle[key] for key in bundle.files}
        result['private_target_decodes'] += 1
        need(set(values) == {'case_id', 'tp_ms', 'condition', 'context'} and values['case_id'].tolist() == ids,
             'Exact private/public canonical join')
        scores = {arm: score_candidate(ordered[arm], lambda: values, grade) for arm in ('cue_only', 'neural')}
        paired = pair_difference(ordered['cue_only'], ordered['neural'], values['tp_ms'], values['condition'], values['context'])
        checks = verify_paired_arithmetic(paired, scores['cue_only']['candidate'], scores['neural']['candidate'])
        result.update(status='paired_predictions_scored', arms=scores, paired=paired,
                      logical_metric_calls=2, independent_paired_arithmetic_checks=len(checks),
                      paired_arithmetic_diagnostics=checks,
                      assessment_unit='same258cases,onepublicHaydn20161211session',
                      matching_evidence='Source/fit review required; same program hash alone is insufficient.')
    except Exception as error:
        result.update(status='invalid_pair' if stage == 'candidate_public_validation' else 'scoring_error',
                      failure_stage=stage,
                      error=type(error).__name__ + ': ' + str(error))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--input', type=Path); parser.add_argument('--out', type=Path)
    args = parser.parse_args(); value = run(args.input, args.out)
    body = (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode()
    need(len(body) <= 100_000, 'Bounded complete pair result')
    with (args.out / 'result.json').open('xb') as stream:
        stream.write(body)
