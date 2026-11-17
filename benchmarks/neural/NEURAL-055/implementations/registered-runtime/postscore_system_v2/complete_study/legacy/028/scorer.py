"""NEURAL-055 pure target-private scorer. No data loading or runtime dispatch.

Caller adds this package's public/ directory to its source import path.
Only the zero-argument private_target_loader may reveal query-to-image truth,
and it is called after complete public validation and secondary-policy checks.
Policy syntax validation cannot establish when/how the operator selected a rule;
predeclared gold-independent policy provenance remains an external construction gate.
"""
import math
from interface import SIZE, ContractError, exact_keys, need, opaque_id, validate_prediction


def _policies(case, independent_tie_order, log_loss_policy):
    if independent_tie_order is not None:
        need(type(independent_tie_order) is list and len(independent_tie_order) == SIZE
             and all(type(x) is str for x in independent_tie_order)
             and len(set(independent_tie_order)) == SIZE
             and set(independent_tie_order) == set(case['candidate_ids']),
             'explicit tie order must be a complete candidate permutation')
    need(log_loss_policy in (None, 'natural_log_no_clipping'), 'unsupported log-loss policy')


def _truth(case, target):
    exact_keys(target, ['schema', 'case_id', 'query_to_candidate'], 'private target')
    need(target['schema'] == 'neural055-private-target-v1' and target['case_id'] == case['case_id'],
         'private target identity mismatch')
    join = target['query_to_candidate']
    need(type(join) is dict and set(join) == set(case['query_ids']), 'complete private query roster required')
    for candidate in join.values():
        opaque_id(candidate)
    need(len(set(join.values())) == SIZE and set(join.values()) == set(case['candidate_ids']),
         'private target must satisfy the declared one-of-each design')
    return join


def _number(value):
    return {'state': 'infinite', 'value': None} if math.isinf(value) else {'state': 'finite', 'value': value}


def score_case(case, prediction, private_target_loader, *, row_sum_abs_tolerance,
               independent_tie_order=None, log_loss_policy=None):
    """Score one200-item participant. Secondary policies deliberately have no selected defaults.

    None means unresolved contract: report that secondary metric as unavailable,
    retaining valid primary assignment accuracy. Actual task admission still needs
    frozen secondary conventions and a development-only calibration recipe.
    """
    validate_prediction(case, prediction, row_sum_abs_tolerance=row_sum_abs_tolerance)
    _policies(case, independent_tie_order, log_loss_policy)
    need(callable(private_target_loader), 'private truth callback required')
    truth = _truth(case, private_target_loader())
    candidates = prediction['candidate_ids']
    index = {c: i for i, c in enumerate(candidates)}
    tie_index = None if independent_tie_order is None else {c: i for i, c in enumerate(independent_tie_order)}
    assigned_correct = 0
    independent_correct = 0
    tied_rows = 0
    zero_true_class = 0
    losses = []
    for q, row, assigned in zip(prediction['query_ids'], prediction['probabilities'], prediction['assignment']):
        true = truth[q]
        assigned_correct += assigned == true
        maximum = max(row)
        tied = [candidates[i] for i, value in enumerate(row) if value == maximum]
        tied_rows += len(tied) > 1
        if tie_index is not None:
            selected = min(tied, key=tie_index.__getitem__)
            independent_correct += selected == true
        p = row[index[true]]
        zero_true_class += p == 0
        if log_loss_policy is not None:
            losses.append(math.inf if p == 0 else -math.log(p))
    loss = None
    if log_loss_policy is not None:
        loss = _number(math.inf if zero_true_class else math.fsum(losses) / SIZE)
    unresolved = []
    if independent_tie_order is None:
        unresolved.append('independent_top1_tie_policy')
    if log_loss_policy is None:
        unresolved.append('log_loss_policy')
    return {
        'schema': 'neural055-case-score-v1', 'case_id': case['case_id'],
        'status': 'scored_primary_secondary_contract_incomplete' if unresolved else 'scored',
        'queries': SIZE, 'assignment_correct': assigned_correct,
        'assignment_top1': assigned_correct / SIZE,
        'independent_correct': independent_correct if tie_index is not None else None,
        'independent_top1': independent_correct / SIZE if tie_index is not None else None,
        'independent_log_loss': loss, 'tied_probability_rows': tied_rows,
        'zero_true_class_probability_rows': zero_true_class,
        'unresolved_secondary_policies': unresolved,
        'row_sum_abs_tolerance': row_sum_abs_tolerance,
        'independent_tie_order': independent_tie_order,
        'log_loss_policy': log_loss_policy,
        'calibration_provenance_verified': False,
        'operator_policy_provenance_verified': False,
        'interpretation': 'Conditional on one fixed200-image panel; no performance threshold or scientific-admission decision.'
    }


def aggregate_panel(reports, *, expected_case_ids):
    """Exactly ten trusted scorer reports, one participant each; no favorable subset.

    The private operator must bind participant identity and ensure one distinct
    participant per case. These scalar reports are internal scorer products, never
    accepted directly as candidate submissions.
    """
    need(type(expected_case_ids) is list and len(expected_case_ids) == 10, 'ten expected participant cases required')
    for key in expected_case_ids:
        opaque_id(key)
    need(len(set(expected_case_ids)) == 10, 'distinct case IDs required')
    need(type(reports) is list and len(reports) == 10, 'all ten participant reports required')
    need(all(type(r) is dict and r.get('schema') == 'neural055-case-score-v1'
             and r.get('queries') == SIZE and r.get('status') in
             ('scored', 'scored_primary_secondary_contract_incomplete') for r in reports), 'trusted complete case reports required')
    need(len({r['case_id'] for r in reports}) == 10
         and {r['case_id'] for r in reports} == set(expected_case_ids), 'complete unique participant support required')
    tolerance = reports[0]['row_sum_abs_tolerance']
    need(all(r['row_sum_abs_tolerance'] == tolerance for r in reports), 'same normalization convention across panel required')
    policy = reports[0]['log_loss_policy']
    need(all(r['log_loss_policy'] == policy for r in reports), 'same log-loss policy across panel required')
    tie_defined = [r['independent_tie_order'] is not None for r in reports]
    need(all(tie_defined) or not any(tie_defined), 'tie policy must be bound consistently across panel')
    primary = math.fsum(r['assignment_top1'] for r in reports) / 10
    secondary = math.fsum(r['independent_top1'] for r in reports) / 10 if all(tie_defined) else None
    loss = None
    if policy is not None:
        loss = {'state': 'infinite', 'value': None} if any(r['independent_log_loss']['state'] == 'infinite' for r in reports) else _number(math.fsum(r['independent_log_loss']['value'] for r in reports) / 10)
    return {'schema': 'neural055-panel-score-v1', 'participants': 10, 'queries': 2000,
            'primary_participant_macro_assignment_top1': primary,
            'secondary_participant_macro_independent_top1': secondary,
            'secondary_participant_macro_independent_log_loss': loss,
            'complete_participant_support': True,
            'secondary_contract_complete': all(tie_defined) and policy is not None,
            'calibration_provenance_verified': False,
        'operator_policy_provenance_verified': False,
            'scope': 'Ten public people; fixed image panel; no uncertainty, causal, calibration or acceptance claim.'}
