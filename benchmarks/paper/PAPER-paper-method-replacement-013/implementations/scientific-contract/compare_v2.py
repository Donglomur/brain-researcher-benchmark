"""Neuroformer declared-comparability checks; no model, data or provenance verifier.

Inputs are trusted operator records, never candidate attestations. Matching strings
and true flags are assertions, not independent evidence. No scientific claim is
awarded, even when the declared comparison is internally consistent.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
HISTORICAL = 'released_computational_path_10ms'
PROTECTED = 'protected_support_source_amended_10ms'
ARMS = {'paper_and_data', 'paper_data_official_code'}
INTENTS = {'released_replay', 'protected_improvement', 'code_access_effect'}
# Each identity names an operator-frozen object/policy. This module never resolves it.
PROTOCOL_FIELDS = {
    'paper_revision', 'data_revision', 'recording_identity', 'train_support',
    'selection_support', 'evaluation_support', 'preprocessing', 'features',
    'metric_implementation', 'aggregation', 'selection_policy', 'context_policy',
    'resource_budget', 'pretraining_resources', 'noncode_resources',
    'feedback_policy', 'comparison_plan', 'target', 'task_kind',
}
DECLARATION_FIELDS = {
    'evaluation_targets_used_for_selection', 'checkpoint_frozen_before_final_queries',
    'evaluation_targets_hidden_until_predictions_committed',
    'physical_isolation_enforced', 'full_context_purge_enforced',
    'training_only_preprocessing',
}
RECORD_FIELDS = {'schema', 'run_id', 'cell_id', 'access_arm', 'method_identity',
                 'seed', 'protocol', 'declarations', 'prior_evaluation_access',
                 'metric_profile', 'metric', 'n_total', 'n_scored', 'value',
                 'undefined_reason'}
SCALAR_PROFILES = {'released_plot_first200_pearson', 'protected_full_support_pearson'}


class ContractError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ContractError(message)


def _pairs(items):
    out = {}
    for key, value in items:
        require(key not in out, f'duplicate JSON key: {key}')
        out[key] = value
    return out


def read_json(path):
    # Small ordinary operator documents only. No data/checkpoint acquisition.
    with open(path, 'rb') as handle:
        raw = handle.read(1048577)
    require(len(raw) <= 1048576, 'record exceeds 1 MiB')
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ContractError('nonfinite JSON')))


def _text(value):
    return type(value) is str and 0 < len(value) <= 512 and value.strip() == value


def _scope():
    scope = read_json(HERE / 'scope.json')
    return {cell['id']: cell for cell in scope['cells']}


def _record(record):
    require(type(record) is dict and set(record) == RECORD_FIELDS, 'closed observation fields required')
    require(record['schema'] == 'neuroformer_operator_observation_v1', 'unknown observation schema')
    for key in ('run_id', 'cell_id', 'method_identity'):
        require(_text(record[key]), f'invalid {key}')
    require(type(record['access_arm']) is str and record['access_arm'] in ARMS, 'unknown access arm')
    require(type(record['seed']) is int and 0 <= record['seed'] < 2**32, 'invalid seed')
    protocol = record['protocol']
    require(type(protocol) is dict and set(protocol) == PROTOCOL_FIELDS, 'complete closed protocol required')
    require(all(_text(value) for value in protocol.values()), 'protocol identities must be nonempty strings')
    declarations = record['declarations']
    require(type(declarations) is dict and set(declarations) == DECLARATION_FIELDS, 'complete closed declarations required')
    require(all(type(value) is bool for value in declarations.values()), 'declarations must be booleans')
    require(type(record['prior_evaluation_access']) is str and record['prior_evaluation_access'] in {'yes', 'no', 'unknown'}, 'invalid exposure declaration')
    require(type(record['metric_profile']) is str and type(record['metric']) is str, 'metric strings required')
    require(type(record['n_total']) is int and record['n_total'] > 0, 'positive total support required')
    require(type(record['n_scored']) is int and 0 <= record['n_scored'] <= record['n_total'], 'invalid scored support')
    value = record['value']
    if value is None:
        require(_text(record['undefined_reason']), 'null score needs an explicit reason')
    else:
        require(type(value) in (int, float) and math.isfinite(value), 'finite numeric score required')
        require(record['undefined_reason'] is None, 'numeric score cannot have undefined reason')
        if record['metric'] == 'pearson_r':
            require(-1 <= value <= 1 and record['n_scored'] >= 2, 'invalid Pearson value or support')
    cells = _scope()
    require(record['cell_id'] in cells, 'cell absent from complete 85-cell scope')
    cell = cells[record['cell_id']]
    require(record['metric_profile'] == cell['metric_profile'], 'metric profile does not belong to cell')
    if record['metric_profile'] in SCALAR_PROFILES:
        require(record['metric'] == 'pearson_r', 'scalar behavior profile requires Pearson')
        require(protocol['target'] in {'speed', 'phi', 'th'}, 'unknown scalar behavior target')
        if cell['case']['kind'] == 'regression':
            require(protocol['target'] == 'speed', 'speed regression cell cannot score gaze')
        expected = min(200, record['n_total']) if cell['condition'] == HISTORICAL else record['n_total']
        require(record['n_scored'] == expected, 'score support violates metric profile')
    return cell


def observation_identity(record):
    """Retain declared endpoint/support identity; this is not an authentication receipt."""
    fields = ('run_id', 'cell_id', 'access_arm', 'method_identity', 'seed',
              'metric_profile', 'metric', 'n_total', 'n_scored', 'prior_evaluation_access')
    result = {key: record[key] for key in fields}
    result['protocol'] = dict(record['protocol'])
    return result


def _result(intent, reasons, reference=None, candidate=None):
    result = {
        'schema': 'neuroformer_declared_comparison_v2', 'intent': intent,
        'status': 'blocked' if reasons else 'comparable_under_operator_declarations',
        'reasons': reasons, 'signed_candidate_minus_reference': None,
        'absolute_difference': None, 'interpretation': None,
        'scientifically_qualified': False, 'claim_awarded': False,
        'evidence_authority': 'trusted_operator_assertions_not_independent_provenance',
        'limits': ['No paper reproduction pass, clean generalization, statistical significance or SOTA claim.',
                   'No uncertainty estimate or cross-cell/animal aggregation.',
                   'This checker does not authenticate support, resources, isolation or prior exposure.'],
    }
    if reference is not None:
        result['run_ids'] = [reference['run_id'], candidate['run_id']]
        result['cell_id'] = reference['cell_id']
        result['observations'] = [observation_identity(reference), observation_identity(candidate)]
    return result


def compare(reference, candidate, intent):
    """Check a paired scalar report. Positive effect means higher Pearson only.

    Method identities may differ for improvement/reimplementation. Every protocol
    identity, seed, cell, support size and metric must match. Access effects pair
    A then B; method differences are outcomes, not proof of a causal code benefit.
    """
    require(type(intent) is str and intent in INTENTS, 'unsupported comparison intent')
    left, right = _record(reference), _record(candidate)
    reasons = []
    def check(ok, reason):
        if not ok:
            reasons.append(reason)
    check(reference['run_id'] != candidate['run_id'], 'same run cannot be its own comparator')
    for key in ('cell_id', 'seed', 'metric_profile', 'metric', 'n_total', 'n_scored'):
        check(reference[key] == candidate[key], 'mismatched ' + key)
    for key in sorted(PROTOCOL_FIELDS):
        check(reference['protocol'][key] == candidate['protocol'][key], 'mismatched protocol.' + key)
    check(reference['metric_profile'] in SCALAR_PROFILES and candidate['metric_profile'] in SCALAR_PROFILES,
          'classification, generated neural and 5 ms metrics remain unqualified; no scalar substitution')
    check(reference['protocol']['task_kind'] == candidate['protocol']['task_kind'] == 'retrospective_decoding',
          'current behavior contract is retrospective decoding, not online forecasting')
    check(reference['protocol']['aggregation'] == candidate['protocol']['aggregation'] == 'pooled_ordered_rows_pearson',
          'only declared within-recording pooled Pearson is supported')
    if intent == 'code_access_effect':
        check(reference['access_arm'] == 'paper_and_data' and candidate['access_arm'] == 'paper_data_official_code',
              'access comparison must pair paper+data then paper+data+official code')
    else:
        check(reference['access_arm'] == candidate['access_arm'], 'mixed access arms confound method comparison')
    for record, cell in ((reference, left), (candidate, right)):
        declarations = record['declarations']
        if cell['condition'] == HISTORICAL:
            check(declarations['evaluation_targets_used_for_selection'], 'historical test selection must be disclosed')
            check(not declarations['evaluation_targets_hidden_until_predictions_committed'], 'historical targets were exposed before final prediction')
            check(record['protocol']['selection_support'] == record['protocol']['evaluation_support'],
                  'historical selection must name the evaluation support')
        if intent == 'released_replay':
            check(cell['condition'] == HISTORICAL, 'released replay requires historical condition')
        else:
            check(cell['condition'] == PROTECTED, 'protected comparison cannot use historical or 5 ms endpoints')
            check(len({record['protocol'][key] for key in ('train_support', 'selection_support', 'evaluation_support')}) == 3,
                  'protected train, selection and evaluation support identities must differ')
            check(not declarations['evaluation_targets_used_for_selection'], 'evaluation targets used for selection')
            for key in sorted(DECLARATION_FIELDS - {'evaluation_targets_used_for_selection'}):
                check(declarations[key], 'missing declared gate: ' + key)
            check(record['prior_evaluation_access'] == 'no', 'prior evaluation exposure is known or unresolved')
        check(record['value'] is not None, 'undefined score: ' + str(record['undefined_reason']))
    result = _result(intent, reasons, reference, candidate)
    result['unresolved_cell_holds'] = sorted(set(left['holds'] + right['holds']))
    if not reasons:
        difference = candidate['value'] - reference['value']
        result['signed_candidate_minus_reference'] = difference
        result['absolute_difference'] = abs(difference)
        result['interpretation'] = ('historical exposed-workflow discrepancy; not paper-result reproduction'
                                    if intent == 'released_replay' else
                                    'descriptive paired Pearson difference conditional on operator declarations')
    return result


def published_target_gap(observation, target_id):
    """Report a number's distance from Table 1; never adjudicate reproduction.

    A method-name match is deliberately not treated as source-run authentication.
    The local GRU slot is not automatically equated with the paper's bi-GRU.
    """
    cell = _record(observation)
    targets = read_json(HERE / 'published_targets_v2.json')
    require(type(target_id) is str, 'target id must be a string')
    matches = [target for target in targets['targets'] if target['id'] == target_id]
    require(len(matches) == 1, 'unknown published target')
    target = matches[0]
    reasons = list(targets['unresolved'])
    compatible = (cell['case']['cohort'] == target['cohort'] and observation['metric'] == target['metric']
                  and observation['protocol']['target'] == target['target']
                  and observation['metric_profile'] in SCALAR_PROFILES and observation['value'] is not None)
    if not compatible:
        reasons.append('observation has incompatible cohort/endpoint/metric or undefined value')
    return {'schema': 'neuroformer_unmapped_paper_target_v2', 'status': 'unmapped_not_reproduced',
            'target_id': target_id, 'published_value': target['value'],
            'source_url': target['source_url'], 'source_locator': target['source_locator'],
            'source_version': target['source_version'], 'observation': observation_identity(observation),
            'descriptive_gap_only': observation['value'] - target['value'] if compatible else None,
            'reasons': reasons, 'reproduction_pass': None, 'tolerance': None,
            'scientifically_qualified': False, 'claim_awarded': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference')
    parser.add_argument('candidate')
    parser.add_argument('--intent', choices=sorted(INTENTS), required=True)
    args = parser.parse_args()
    result = compare(read_json(args.reference), read_json(args.candidate), args.intent)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['status'] == 'comparable_under_operator_declarations' else 2


if __name__ == '__main__':
    raise SystemExit(main())
