"""Exact accepted cell registry and availability enforcement (no data access)."""
from pathlib import Path
from functools import lru_cache
import copy
from .base import read_json, require, digest

SPEC = Path(__file__).resolve().parents[1] / 'spec'


@lru_cache(maxsize=1)
def _specifications():
    matrix = read_json(SPEC / 'APPLICABILITY_MATRIX.json')
    packet = read_json(SPEC / 'PACKET_DECLARATIVE_SPEC.json')
    require(len(matrix['cells']) == 84, 'registry_cell_count')
    require(len({r['cell_id'] for r in matrix['cells']}) == 84, 'duplicate_cell')
    return matrix, packet


def specifications():
    # Ordinary immutable source is read once per process; callers cannot mutate the cache.
    return copy.deepcopy(_specifications())


def cell(cell_id, task):
    require(task in ('NEURAL-045', 'NEURAL-046'), 'task')
    matrix, _ = _specifications()
    matches = [r for r in matrix['cells'] if r['cell_id'] == cell_id]
    require(len(matches) == 1, 'unknown_cell')
    result = matches[0]
    require(task in result, 'task_cell')
    return copy.deepcopy(result)


def available_models(cell_id):
    c = cell(cell_id, 'NEURAL-046')
    return tuple(c['NEURAL-046']['models_produced'])


def assert_numerical(cell_id, task):
    c = cell(cell_id, task)
    require(c['tier'] != 'P', 'packet_has_no_numerical_endpoint')
    require(c['intentional_cell_applicability'] != 'structurally_not_applicable',
            'structurally_not_applicable')
    return c


def assert_endpoint_applicable(cell_id, task, endpoint, purpose='numerical'):
    """Single source of endpoint/cell permission for preparation through reporting.

    P remains a separate diagnostic; this function only checks whether its named
    scientific evidence endpoint is permitted, never grants numerical execution.
    """
    c = cell(cell_id, task)
    require(purpose in ('numerical', 'packet_evidence'), 'endpoint_permission_purpose')
    require((purpose == 'packet_evidence' and c['tier'] == 'P') or
            (purpose == 'numerical' and c['tier'] != 'P'), 'endpoint_tier_mismatch')
    require(c['intentional_cell_applicability'] != 'structurally_not_applicable',
            'structurally_not_applicable')
    require(isinstance(endpoint, str), 'endpoint_identity')
    pieces = endpoint.split('/')
    require(len(pieces) <= 2 and (len(pieces) == 1 or pieces[1] in (
        'mean_difference', 'baseline_span_corrected_auc')), 'endpoint_sensitivity_identity')
    base = pieces[0]
    if task == 'NEURAL-045':
        require(base in ('cue', 'native_fluorescence_trajectory', 'cue_time_native_fluorescence',
                         'protocol_only'), 'native_endpoint_identity')
    else:
        aliases = {'cue_AUC': 'cue', 'reward_AUC': 'reward', 'omission_AUC': 'omission',
                   'aversive_cue_AUC': 'aversive'}
        base = aliases.get(base, base)
        require(base in ('cue', 'reward', 'omission', 'aversive', 'delivery', 'protocol_only'),
                'scalar_endpoint_identity')
        if base == 'reward':
            # P's own flag is false because it produces no scientific endpoint.
            # Its given evidence must come from the same control's admissible X analysis.
            evidence_cell = cell(c['mode'] + '_X_' + c['control'], task) if purpose == 'packet_evidence' else c
            require(evidence_cell[task]['consumption_anchored_reward_endpoint_applicable'] is True,
                    'consumption_reward_endpoint_structurally_inapplicable')
    require(base != 'protocol_only' or purpose == 'packet_evidence', 'protocol_only_has_no_numerical_endpoint')
    return c


def validate_model_tool(cell_id, tool, training_view_digest, task='NEURAL-046'):
    c = assert_numerical(cell_id, task)
    require(c['tier'] == 'XM', 'model_tool_not_permitted')
    require(set(tool) == {'cell_id', 'training_digest', 'model_names',
                         'feature_contract_digest', 'qualified'}, 'tool_fields')
    require(tool['cell_id'] == cell_id, 'tool_cell')
    require(tool['training_digest'] == training_view_digest, 'tool_training')
    require(tool['feature_contract_digest'] == digest(c['input_control_contract']),
            'tool_feature_backfill')
    require(tool['qualified'] is True, 'reference_unqualified')
    if task == 'NEURAL-046':
        permitted = set(available_models(cell_id))
    else:
        rights = c['input_control_contract']; permitted = {'R1'}
        if rights['elapsed_conditioning_E_authorized']: permitted.add('R0')
        if rights['delivered_reward_N_authorized']: permitted.add('R2')
        if rights['elapsed_conditioning_E_authorized'] and rights['delivered_reward_N_authorized']: permitted.add('R3')
    require(set(tool['model_names']) <= permitted,
            'tool_model_backfill')
    require(bool(tool['model_names']), 'empty_model_tool')
    return tool


def gate_report(support, qualification):
    """Every original condition stays in the report, including unsupported cells."""
    shared = read_json(SPEC / 'SHARED_SOURCE_CONTRACT.json')
    expected = {x['source_condition'] for x in shared['cohorts']}
    require(set(support) == expected, 'full13_condition_support_required')
    allowed = {'verified', 'source_unscorable', 'behavior_only_no_neural_target'}
    for condition, record in support.items():
        require(record['state'] in allowed, 'support_state')
        require(isinstance(record['reason'], str) and bool(record['reason']),
                'support_reason')
    design = read_json(SPEC / 'DESIGN.json')
    gates = {name: qualification.get(name, False) is True
             for name in design['required_open_gates']}
    return {'conditions': support, 'gates': gates,
            'scientifically_qualified': all(gates.values()),
            'independent_corpora': 1, 'new_tasks': 0}
