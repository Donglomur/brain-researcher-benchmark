"""Bounded declarative P-tier evaluator; no eval/import/fitting or signal I/O."""
import time
from .base import require, finite, loads, digest
from .contracts import cell, specifications, assert_endpoint_applicable


def validate_packet(packet, c, task):
    _, spec = specifications()
    require(c['tier'] == 'P', 'packet_tier')
    require(set(packet) == {'schema', 'bank_schema_id', 'packet_id', 'task_id',
                           'control_id', 'fields', 'closed_receipt_digest'},
            'packet_keys')
    require(packet['schema'] == spec['packet_schema'], 'packet_schema')
    require(packet['task_id'] == task and packet['control_id'] == c['control'],
            'packet_binding')
    for key in ('bank_schema_id', 'packet_id', 'closed_receipt_digest'):
        require(isinstance(packet[key], str) and 0 < len(packet[key]) <= 128,
                'packet_identifier')
    fields = packet['fields']
    require(isinstance(fields, dict), 'packet_fields')
    require(set(fields) <= set(c[task]['packet_fields']), 'packet_field_backfill')
    if fields.get('endpoint_id') is not None:
        assert_endpoint_applicable(c['cell_id'], task, fields['endpoint_id'], 'packet_evidence')
    catalogue = spec['packet_field_catalogue']
    for key, value in fields.items():
        if value is None:
            continue
        rule = catalogue[key]
        kind = rule['type']
        if kind == 'enum':
            require(value in rule['values'], 'packet_enum')
        elif kind == 'boolean':
            require(type(value) is bool, 'packet_boolean')
        elif kind == 'nonnegative_integer_or_unavailable':
            require(type(value) is int and value >= 0, 'packet_count')
        else:
            finite(value)
            if kind == 'finite_nonnegative_number':
                require(value >= 0, 'packet_negative_loss')
    return fields


def validate_policy(raw, c, task, packet):
    require(isinstance(raw, bytes) and len(raw) <= 16384, 'policy_bytes')
    policy = loads(raw)
    _, spec = specifications()
    require(set(policy) == {'schema', 'packet_schema', 'task_id', 'control_id',
                           'binding', 'claim_slots'}, 'policy_keys')
    require(policy['schema'] == 'packet_claim_policy_v1' and
            policy['packet_schema'] == spec['packet_schema'], 'policy_schema')
    require(policy['task_id'] == task and policy['control_id'] == c['control'],
            'policy_binding')
    binding = policy['binding']
    required_binding = {'bank_schema_id'} | ({'packet_id'} if c['mode'] == 'I' else set())
    require(set(binding) == required_binding, 'policy_binding_fields')
    require(all(binding[k] == packet[k] for k in binding), 'policy_binding_value')
    slots = policy['claim_slots']
    require(set(slots) == set(spec['claim_slots']), 'policy_slots')
    allowed = set(c[task]['packet_fields'])
    catalogue = spec['packet_field_catalogue']

    def action(a, slot):
        require(isinstance(a, dict) and set(a) == {'claim', 'evidence'}, 'action')
        require(a['claim'] in spec['claim_slots'][slot], 'claim_enum')
        require(isinstance(a['evidence'], list) and len(a['evidence']) <= 4 and
                len(set(a['evidence'])) == len(a['evidence']) and
                set(a['evidence']) <= allowed, 'action_evidence')

    count = 0
    for slot, ruleset in slots.items():
        require(set(ruleset) == {'rules', 'default'}, 'ruleset_keys')
        require(isinstance(ruleset['rules'], list) and len(ruleset['rules']) <= 8,
                'rule_cap')
        action(ruleset['default'], slot)
        require(ruleset['default'] == {'claim': 'insufficient_evidence', 'evidence': []},
                'default')
        count += len(ruleset['rules'])
        for rule in ruleset['rules']:
            require(set(rule) == {'when', 'then'} and isinstance(rule['when'], list)
                    and len(rule['when']) <= 4, 'rule')
            action(rule['then'], slot)
            for test in rule['when']:
                require(isinstance(test, dict), 'predicate')
                op = test.get('op')
                require(op in ('present', 'equals', 'compare'), 'predicate_op')
                keys = {'op', 'field'} | ({'value'} if op == 'equals' else
                       {'relation', 'rhs'} if op == 'compare' else set())
                require(set(test) == keys and test['field'] in allowed, 'predicate_fields')
                kind = catalogue[test['field']]['type']
                if op == 'equals':
                    value = test['value']
                    require((kind == 'boolean' and type(value) is bool) or
                            (kind == 'enum' and value in catalogue[test['field']]['values']),
                            'equality_type')
                elif op == 'compare':
                    require(kind not in ('boolean', 'enum'), 'comparison_type')
                    require(test['relation'] in ('lt', 'le', 'eq', 'ge', 'gt'), 'relation')
                    rhs = test['rhs']
                    require(isinstance(rhs, dict) and len(rhs) == 1, 'rhs')
                    if set(rhs) == {'literal'}:
                        finite(rhs['literal'])
                    else:
                        require(set(rhs) == {'field'} and rhs['field'] in allowed and
                                catalogue[rhs['field']]['type'] not in ('boolean', 'enum'),
                                'rhs_field')
    require(count <= 64, 'total_rule_cap')
    return policy


def evaluate(raw, packet, cell_id, task, rubric):
    started = time.monotonic()
    c = cell(cell_id, task)
    fields = validate_packet(packet, c, task)
    policy = validate_policy(raw, c, task, packet)
    evaluations = 0

    def match(test):
        nonlocal evaluations
        evaluations += 1
        require(evaluations <= 256, 'predicate_budget')
        value = fields.get(test['field'])
        if test['op'] == 'present':
            return value is not None
        if value is None:
            return False
        if test['op'] == 'equals':
            return value == test['value']
        rhs = test['rhs']
        other = rhs.get('literal') if 'literal' in rhs else fields.get(rhs['field'])
        if other is None:
            return False
        return {'lt': value < other, 'le': value <= other, 'eq': value == other,
                'ge': value >= other, 'gt': value > other}[test['relation']]

    require(set(rubric) == set(policy['claim_slots']), 'rubric_slots')
    reports = {}
    correct = overclaims = 0
    for slot, ruleset in policy['claim_slots'].items():
        selected = ruleset['default']
        for rule in ruleset['rules']:
            if all(match(t) for t in rule['when']):
                selected = rule['then']
                break
        require(all(fields.get(k) is not None for k in selected['evidence']),
                'selected_missing_evidence')
        expected = rubric[slot]
        require(set(expected) == {'accepted_claims', 'unsupported_claims'} and
                isinstance(expected['accepted_claims'], list) and
                isinstance(expected['unsupported_claims'], list), 'rubric_entry')
        correct += selected['claim'] in expected['accepted_claims']
        overclaims += selected['claim'] in expected['unsupported_claims']
        reports[slot] = {'claim': selected['claim'],
                         'evidence': {k: fields[k] for k in selected['evidence']}}
    return {'schema': 'packet_interpretation_result_v1', 'cell_id': cell_id,
            'task_id': task, 'reports': reports, 'correct_claim_slots': correct,
            'eligible_claim_slots': len(reports), 'unsupported_overclaims': overclaims,
            'predicate_evaluations': evaluations, 'policy_bytes': len(raw),
            'evaluator_wall_seconds': time.monotonic() - started,
            'packet_digest': digest(packet), 'numeric_prediction_scores': {},
            'scientific_qualification': False}
