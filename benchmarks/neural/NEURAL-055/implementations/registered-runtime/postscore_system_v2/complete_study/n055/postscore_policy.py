"""Prospective post-score policy admission; historical v1 remains unchanged."""
from .common import require, keys, descriptor, integer
from .interpretation import admit_policy as admit_v1

SCHEMA = 'neural055-postscore-interpretation-policy-v2'
RESOURCE_VERSION = 'neural055-postscore-resources-v2'
REQUEST_SCHEMA = 'neural055-postscore-operation-request-v2'
RESPONSE_SCHEMA = 'neural055-postscore-operation-response-v2'
OPERATION_SCHEMA = 'neural055-original-postscore-operation-v2'
RESOURCE_SCOPE = 'closed_role_plus_original_controller_finalization_v2'


def is_v2(value):
    return type(value) is dict and value.get('schema') == SCHEMA


def admit_policy(value):
    if not is_v2(value):
        return admit_v1(value)
    # Reuse exact original scientific/ordinal/identity/deadline/cap admission.
    original = {k: v for k, v in value.items() if k != 'execution'}
    original['schema'] = 'neural055-postscore-interpretation-policy-v1'
    admit_v1(original)
    require(set(value) == set(original) | {'execution'}, 'closed explicit v2 policy')
    keys(value['execution'], ('source', 'qualification'))
    for item in value['execution'].values():
        descriptor(item); integer(item['bytes'], 1)
    require(value['execution']['source']['bytes'] <= 1048576,
            'bounded exact v2 execution configuration')
    require(value['execution']['qualification']['bytes'] <= 4194304,
            'bounded independent v2 execution qualification')


def resource_identity(source):
    from .common import parse, pin
    raw = source.bodies['contracts/POSTSCORE_RESOURCE_V2.json']
    value = parse(raw)
    require(value['schema'] == RESOURCE_VERSION
            and value['scope'] == RESOURCE_SCOPE
            and value['controller_observer_is_accounted'] is True
            and value['memory_measurement'] == 'sum_of_disjoint_component_peaks_upper_bound'
            and value['native_cumulative_io_and_churn'] == 'unobserved',
            'exact typed post-score resource semantics')
    return dict(version=RESOURCE_VERSION, **pin(raw))


def execution_subject(plan, source, configuration):
    policy = plan['interpretation']
    return {'schema': 'neural055-postscore-execution-subject-v2',
            'source': source.identity, 'execution': policy['execution']['source'],
            'configuration': configuration,
            'resource_policy': plan['resource_policy'],
            'postscore_resource_policy': resource_identity(source),
            'policy_schema': SCHEMA, 'policy': policy['policy'],
            'clock_domain': policy['clock_domain'],
            'whole_limits': plan['limits'], 'phase_limits': plan['phase_limits'],
            'postscore_limits': policy['limits'], 'memory_bytes': policy['memory_bytes'],
            'maximum_input_tokens': policy['maximum_input_tokens'],
            'maximum_output_tokens': policy['maximum_output_tokens'],
            'services': [{'identity': item['identity'], 'source': item['source']}
                         for item in (policy['author'], *policy['reviewers'], policy['adjudicator'])]}

