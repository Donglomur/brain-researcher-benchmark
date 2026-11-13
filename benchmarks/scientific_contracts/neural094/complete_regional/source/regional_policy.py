"""Prospective deployment-strategy policy; no production budget defaults.

F authoring and I investigation consume equal total nonrefundable reservations.
This does not assert equal per-stage model access, realized cost, or computation.
"""
import copy
import math
from regional_custody import need, check_pin, encoded, pin
from regional_scope import bundles, geometry

MODEL = ('max_calls', 'input_tokens', 'output_tokens')
RESOURCE = ('cpu_seconds', 'wall_seconds', 'memory_bytes', 'storage_bytes', 'tool_calls')


def positive(value, label):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0, label)


def limits(row):
    need(type(row) is dict and set(row) == set(RESOURCE), 'Exact positive resource allocation')
    for key, value in row.items():
        positive(value, key)
        if key.endswith('_bytes') or key == 'tool_calls':
            need(type(value) is int, 'Typed integral resource count')


def model(row):
    need(type(row) is dict and set(row) == set(MODEL), 'Exact model reservation')
    for value in row.values():
        need(type(value) is int and value > 0, 'Explicit positive model reservation')


def validate(plan, scope):
    """Full exact allocations are frozen before any candidate staging.

    Authoring resource reservations and each condition's fit/query reservations
    are counted separately. F and I have equal aggregate strategy ceilings and
    identical per-condition CPU/RAM/wall/storage/tool limits. I preparation is
    part of its global authoring stage; no omitted 'free' prompt development.
    """
    fields = {'schema', 'source', 'model_spec', 'F_authoring', 'I_authoring',
              'I_contexts', 'condition_resources', 'authoring_resources', 'semantics'}
    need(type(plan) is dict and set(plan) == fields and plan['schema'] == 'neural094_deployment_policy_v1',
         'Exact paired strategy policy')
    need(set(plan['source']) == {'F', 'I'}, 'Both globally frozen sources')
    for p in plan['source'].values():
        check_pin(p)
    check_pin(plan['model_spec'])
    model(plan['F_authoring']); model(plan['I_authoring'])
    need(type(plan['I_contexts']) is list, 'Complete explicit context allocations')
    total = dict(plan['I_authoring'])
    expected = list(bundles(scope))
    need(len(expected) == len(plan['I_contexts']) == geometry(scope)['candidate_bundles_per_mode'],
         'Full prospective I context allocation')
    for item, allocation in zip(expected, plan['I_contexts']):
        need(type(allocation) is dict and set(allocation) == {'key', 'train', 'query'}
             and allocation['key'] == item['key'], 'Exact bundle order and source support')
        for phase in ('train', 'query'):
            model(allocation[phase])
            for key in MODEL:
                total[key] += allocation[phase][key]
    need(total == plan['F_authoring'], 'Equal total model reservations including both strategies authoring')
    conditions = plan['condition_resources']
    need(type(conditions) is dict and set(conditions) == {'F', 'I'}, 'Both condition envelopes')
    for strategy in ('F', 'I'):
        need(set(conditions[strategy]) == {'train', 'query'}, 'Both numerical stages')
        for row in conditions[strategy].values():
            limits(row)
    need(conditions['F'] == conditions['I'], 'Identical per-condition non-model ceilings')
    authoring = plan['authoring_resources']
    need(type(authoring) is dict and set(authoring) == {'F', 'I'}, 'Both authoring resource records')
    for value in authoring.values():
        limits(value)
    need(authoring['F'] == authoring['I'], 'Equal separately charged authoring resource ceilings')
    wanted = {'F_runtime_model_access': False, 'I_policy_globally_frozen': True,
              'within_arm_unlabeled_query_adaptation': True, 'cross_bundle_feedback': False,
              'query_targets_visible': False, 'all_models_sealed_before_paired_query': True,
              'authoring_and_failed_requests_counted': True, 'nonrefunded_maximum_reservations': True}
    need(plan['semantics'] == wanted and all(type(plan['semantics'][k]) is bool for k in wanted),
         'Exact selected deployment-strategy semantics')
    return copy.deepcopy(plan)


def authoring_receipt(receipt, allocation, source, model_spec, resource_allocation):
    """Arithmetic only; outer authority must authenticate complete historical logs."""
    need(type(receipt) is dict and set(receipt) == {'source', 'model_spec', 'requests',
         'prepared_before_first_assessment_input', 'resources'}, 'Complete authoring evidence')
    need(receipt['source'] == source and receipt['model_spec'] == model_spec
         and receipt['prepared_before_first_assessment_input'] is True, 'Frozen source and pre-staging chronology')
    need(type(receipt['requests']) is list, 'Complete requests including failed/preparatory calls')
    resources = receipt['resources']
    need(type(resources) is dict and set(resources) == {'reserved','actual'}
         and resources['reserved'] == resource_allocation and type(resources['actual']) is dict
         and set(resources['actual']) == set(RESOURCE), 'Complete authoring resource reservation and observations')
    for key,value in resources['actual'].items():
        need(value is None or type(value) in (int,float) and math.isfinite(value)
             and 0 <= value <= resource_allocation[key], 'Actual authoring use or explicit unknown')
    reserved = dict.fromkeys(MODEL, 0)
    actual = {'input_tokens': 0, 'output_tokens': 0}
    ids = set(); unknown = False
    for row in receipt['requests']:
        need(type(row) is dict and set(row) == {'id', 'status', 'preparation', 'input_reserved',
             'output_reserved', 'input_actual', 'output_actual'}, 'Exact reservation record')
        need(type(row['id']) is str and row['id'] and row['id'] not in ids, 'Unique request identity')
        ids.add(row['id'])
        need(row['status'] in ('complete', 'failed') and type(row['preparation']) is bool, 'Outcome and preparation')
        reserved['max_calls'] += 1
        for kind in ('input', 'output'):
            value, observed = row[kind+'_reserved'], row[kind+'_actual']
            need(type(value) is int and value > 0, 'Positive dispatched maximum, no refunds')
            reserved[kind+'_tokens'] += value
            if observed is None:
                need(row['status'] == 'failed', 'Successful requests have observed usage')
                unknown = True
            else:
                need(type(observed) is int and 0 <= observed <= value, 'Actual usage bounded by reservation')
                actual[kind+'_tokens'] += observed
        need(all(reserved[k] <= allocation[k] for k in MODEL), 'Every prefix fits original ceiling')
    return {'reserved': reserved, 'unused_capacity': {k: allocation[k]-reserved[k] for k in MODEL},
            'actual_known_subtotal': actual, 'actual_complete': not unknown,
            'resource_reservations':copy.deepcopy(resources['reserved']),
            'actual_resource_observations':copy.deepcopy(resources['actual']),
            'source_receipt_pin': pin(encoded(receipt)), 'external_authentication_established_here': False}
