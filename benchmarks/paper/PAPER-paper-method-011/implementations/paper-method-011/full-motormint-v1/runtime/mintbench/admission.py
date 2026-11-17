"""Operator-selected trust root; candidate metadata cannot close scientific gates."""
from . import catalog
from .validation import exact, need, ident, sha, integer, digest, descriptor

DESIGN = 'f664ed2fa346b79f593829a169eb003901151ab96f236fd3722312fb413838e0'
PURPOSES = ('reproduce', 'improve')
MODES = ('behavior_causal', 'behavior_acausal', 'neural_acausal', 'analysis')


def context_pair(pair):
    exact(pair, ('A', 'B', 'author_code_selection_sha256'), 'paired context')
    for arm in ('A', 'B'):
        row = pair[arm]
        exact(row, ('common', 'author_code', 'resources', 'model', 'prompt_sha256'), 'arm context')
        need(type(row['common']) is list and type(row['author_code']) is list, 'context inventories')
        for desc in row['common'] + row['author_code']:
            descriptor(desc)
        need(len({d['path'] for d in row['common'] + row['author_code']}) ==
             len(row['common'] + row['author_code']), 'no context aliases')
        sha(row['prompt_sha256'])
        need(type(row['resources']) is dict and 'role_seconds' in row['resources'], 'explicit common per-role time budget')
        integer(row['resources']['role_seconds'], 1)
    need(pair['A']['common'] == pair['B']['common'], 'identical public common data/code/resources')
    need(pair['A']['resources'] == pair['B']['resources'] and
         pair['A']['model'] == pair['B']['model'] and
         pair['A']['prompt_sha256'] == pair['B']['prompt_sha256'], 'paired resource/model/prompt equality')
    need(not pair['A']['author_code'] and pair['B']['author_code'], 'A no author implementation; B admitted bundle')
    sha(pair['author_code_selection_sha256'])
    need(digest(pair['B']['author_code']) == pair['author_code_selection_sha256'], 'exact differential code selection')
    return pair


def validate_plan(plan):
    exact(plan, ('schema', 'task', 'design_sha256', 'catalog_sha256', 'module_support', 'cases','aggregate_uncertainty'), 'full plan')
    need(plan['schema'] == 'motormint_full_plan_v2' and plan['task'] == 'PAPER-paper-method-011', 'full-plan identity')
    need(plan['design_sha256'] == DESIGN and plan['catalog_sha256'] == catalog.signature(), 'selected full scope')
    need(type(plan['module_support']) is list and
         [r['module'] for r in plan['module_support']] == list(catalog.MODULES), 'all17modules required')
    for row in plan['module_support']:
        exact(row, ('module', 'required_keys', 'original_support_evidence', 'comparator_roster_evidence','output_identities'), 'module support')
        keys = row['required_keys']
        need(type(keys) is list and keys and len(set(keys)) == len(keys), 'complete nonempty unique module support')
        for key in keys:
            ident(key)
        known = catalog.required_support(row['module'])
        need(known is None or set(known) <= set(keys), 'cannot shrink source-defined support')
        sha(row['original_support_evidence']); sha(row['comparator_roster_evidence'])
    need(type(plan['cases']) is list and plan['cases'], 'execution cases required')
    seen, coverage = set(), {m: set() for m in catalog.MODULES}
    primary_map = {s['id']: s for s in catalog.primary_slots()}
    loss_keys = set(catalog.loss_cells())
    for case in plan['cases']:
        exact(case, ('id', 'module', 'dataset', 'mode', 'purpose', 'method', 'repeat',
                     'outputs', 'source_recipe_sha256', 'reference_source_sha256',
                     'config_sha256', 'metric_recipe_sha256', 'input_index_sha256','factors','output_dimensions','output_identities','uncertainty_requirements'), 'case')
        from .bindings import validate_case
        validate_case(case)
        ident(case['id']); ident(case['dataset']); ident(case['method'])
        need(case['id'] not in seen and case['module'] in coverage, 'unique case and canonical module')
        seen.add(case['id'])
        need(case['mode'] in MODES and case['purpose'] in PURPOSES, 'scientifically distinct mode/purpose')
        if case['module'] in ('primary_behavior', 'small_training_sets', 'threshold_crossings',
                              'cycle_direction_generalization', 'pacman_generalization', 'network_ground_truth',
                              'averaged_training_control', 'maze_simulations'):
            need(case['mode'] in ('behavior_causal', 'analysis'), 'online decoding cannot gain future observations')
        if case['mode'] == 'behavior_acausal':
            need(case['module'] == 'factorial_ablations', 'acausal behavior only in declared factorial arm')
        if case['module'] == 'primary_behavior':
            need(case['mode'] == 'behavior_causal' and len(case['outputs']) == 1, 'one authentic primary prediction bundle per case')
            slot = primary_map.get(case['outputs'][0])
            need(slot and all(slot[k] == case[k] for k in ('dataset', 'method', 'repeat')), 'published primary method/run roster')
        if case['module'] == 'factorial_ablations':
            direction = {key.split(':')[3] for key in case['outputs']}
            need(len(direction) == 1 and case['mode'] == ('behavior_causal' if direction == {'causal'} else 'behavior_acausal'), 'factorial information boundary')
        if case['module'] == 'nlb_neural_state' and any(key in set(catalog.nlb_cells()) for key in case['outputs']):
            need(case['mode'] == 'neural_acausal', 'original NLB endpoints require complete train and test rate artifacts')
            need(all(key.split(':')[0] == case['dataset'] for key in case['outputs']), 'dataset-specific NLB output identity')
        if case['module'] == 'neuron_loss':
            if any(key in loss_keys for key in case['outputs']):
                need(case['mode'] == 'behavior_causal', 'neuron-loss scores require causal prediction artifacts')
        integer(case['repeat'], 0, 1000000)
        need(type(case['outputs']) is list and case['outputs'], 'declared complete output units')
        for key in case['outputs']:
            ident(key)
            need(key not in coverage[case['module']], 'exactly one producer per required output within plan')
            coverage[case['module']].add(key)
        for field in ('source_recipe_sha256', 'reference_source_sha256', 'config_sha256',
                      'metric_recipe_sha256', 'input_index_sha256'):
            sha(case[field])
    for row in plan['module_support']:
        need(coverage[row['module']] == set(row['required_keys']), 'no missing or extra module outputs')
        from .bindings import PREDICTIVE
        if row['module'] in PREDICTIVE:
            need(any(i['estimand']=='behavior_R2' for c in plan['cases'] if c['module']==row['module'] for i in c['output_identities']),'predictive family cannot consist only of documentation')
        expected=row['output_identities']
        need(type(expected) is dict and set(expected)==set(row['required_keys']), 'typed original obligation matrix')
        for case in plan['cases']:
            if case['module']==row['module']:
                for item in case['output_identities']:
                    need(expected[item['key']]==item, 'source support identity equals actual producer obligation')
    from .uncertainty import validate_aggregate_plan
    validate_aggregate_plan(plan)
    return plan


class Admission:
    """Construct only in trusted operator code using an independently selected hash.

    The selected hash is not read from a candidate packet. Python identity is not
    the security boundary: candidate code runs only in a separate sandbox.
    """
    def __init__(self, value, selected_sha256, plan):
        sha(selected_sha256)
        need(digest(value) == selected_sha256, 'operator-selected admission commitment')
        exact(value, ('schema', 'task', 'mode', 'plan_sha256', 'context_pair', 'bindings',
                      'gate_evidence', 'limits', 'independent_reference_owner',
                      'execution_selection_sha256', 'runtime_source_sha256'), 'admission')
        need(value['schema'] == 'motormint_execution_admission_v2' and
             value['task'] == 'PAPER-paper-method-011', 'selected execution admission')
        need(value['mode'] in ('authentic', 'invented_control'), 'explicit evidence mode')
        validate_plan(plan)
        need(value['plan_sha256'] == digest(plan), 'whole plan frozen before reads/execution')
        context_pair(value['context_pair'])
        sha(value['execution_selection_sha256']); sha(value['runtime_source_sha256'])
        ident(value['independent_reference_owner'])
        need(type(value['bindings']) is list and value['bindings'], 'independent input/source/runtime binding receipts')
        for pin in value['bindings']:
            descriptor(pin)
        need(len({p['path'] for p in value['bindings']}) == len(value['bindings']), 'unique binding paths')
        gates = value['gate_evidence']
        need(type(gates) is dict and set(gates) == {g['id'] for g in catalog.gaps()['gaps']}, 'retain every gate')
        if value['mode'] == 'authentic':
            for pin in gates.values():
                descriptor(pin)  # Original evidence must be captured and reviewed externally.
        else:
            need(all(p is None for p in gates.values()), 'invented controls never claim historical gate closure')
        exact(value['limits'], ('file_bytes', 'frame_bytes', 'output_bytes', 'attempts',
                                'normal_seconds', 'cleanup_seconds', 'numerical_bytes'), 'finite operation budgets')
        for field in value['limits']:
            integer(value['limits'][field], 1)
        need(value['limits']['frame_bytes'] <= 2 * 1024 * 1024 and
             value['limits']['cleanup_seconds'] <= 60, 'bounded protocol and cleanup')
        integer(value['limits']['numerical_bytes'], 1, 34359738368)
        self.value, self.plan = value, plan
        self.commitment, self.plan_commitment = selected_sha256, digest(plan)
        self.original_mode = value['mode']

    def recheck(self):
        need(digest(self.value) == self.commitment and digest(self.plan) == self.plan_commitment,
             'admission/whole plan unchanged')

    def require_authentic(self):
        self.recheck()
        need(self.original_mode == 'authentic', 'controls cannot authorize original data or native execution')

    def evidence_label(self):
        return 'engineering_invented_only' if self.original_mode == 'invented_control' else 'execution_pending_independent_qualification'
