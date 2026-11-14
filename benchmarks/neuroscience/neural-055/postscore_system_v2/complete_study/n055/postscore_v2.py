"""Actual current v2 producer/consumer joins; historical v1 stays distinct."""
from pathlib import Path

from .common import (require, keys, integer, finite, relative, parse, encoded,
                     sha, pin, FailureCarrier, diagnostic_type)
from .interpretation import Postscore as HistoricalPostscore, safe_aggregate, RESOURCES, COMPARISONS
from .reporting import interpretation as score_interpretation
from .postscore_policy import (SCHEMA, REQUEST_SCHEMA, RESPONSE_SCHEMA, OPERATION_SCHEMA,
                               RESOURCE_SCOPE, admit_policy, resource_identity)
from .postscore_dispatch import completed_descriptor, root_descriptor
from . import postscore_services as services


def validate_memory(value, whole_limit):
    names = ('schema', 'controller_peak_bytes', 'controller_peak_kind', 'role_peak_bytes',
             'role_peak_kind', 'component_peak_sum_upper_bound_bytes', 'component_peak_sum_scope',
             'simultaneous_peak_bytes', 'controller_cap_bytes', 'role_cap_bytes',
             'enforced_lifetime_cap_sum_bytes', 'whole_limit_bytes',
             'later_controller_work_is_not_in_closed_role_measurement')
    keys(value, names)
    require(value['schema'] == 'neural055-disjoint-component-memory-v2'
            and value['controller_peak_kind'] == 'checkpoint'
            and value['role_peak_kind'] == 'closed_subtree_final'
            and value['component_peak_sum_scope'] == 'through_controller_checkpoint'
            and value['simultaneous_peak_bytes'] is None
            and value['later_controller_work_is_not_in_closed_role_measurement'] is True,
            'typed component memory observations, never a claimed simultaneous whole peak')
    for name in ('controller_peak_bytes', 'role_peak_bytes', 'component_peak_sum_upper_bound_bytes',
                 'controller_cap_bytes', 'role_cap_bytes', 'enforced_lifetime_cap_sum_bytes',
                 'whole_limit_bytes'):
        integer(value[name])
    require(value['controller_peak_bytes'] <= value['controller_cap_bytes']
            and value['role_peak_bytes'] <= value['role_cap_bytes']
            and value['component_peak_sum_upper_bound_bytes'] ==
                value['controller_peak_bytes'] + value['role_peak_bytes']
            and value['enforced_lifetime_cap_sum_bytes'] ==
                value['controller_cap_bytes'] + value['role_cap_bytes']
            and value['enforced_lifetime_cap_sum_bytes'] <= value['whole_limit_bytes'] == whole_limit,
            'actual disjoint enforced whole bound and correctly labeled upper bound')


def validate_role_observation(value, operation, request, journal, root, now, deadline):
    """Join the closed owner observation; no future-controller-cost inference."""
    names = ('schema', 'request_sha256', 'source', 'role_owner', 'origin',
             'role_child_end', 'closed_groups', 'original_processes', 'provider_evidence',
             'controller_processes_nonadditive_to_role', 'usage', 'costs', 'memory',
             'component_allocation', 'controller_leaf', 'memory_observation',
             'controller_kernel_events', 'closed_role_end', 'closure_observation_end',
             'own_publication_is_continuing_original_controller_work', 'qualification_not_created_here')
    keys(value, names)
    require(value['schema'] == 'neural055-closed-role-observation-v2'
            and value['request_sha256'] == operation['request_sha256']
            and value['source'] == operation['source']
            and value['usage'] == operation['token_usage']
            and value['costs'] == operation['role_costs']
            and value['memory'] == operation['memory']
            and value['closed_role_end'] == operation['end']
            and value['own_publication_is_continuing_original_controller_work'] is True
            and value['qualification_not_created_here'] is True,
            'same closed native owner and continuing-controller boundary')
    timing = value['memory_observation']
    keys(timing, ('role_scope_origin', 'role_scope_created_observed_at', 'role_scope_closed_at',
                 'controller_checkpoint_at', 'controller_peak_scope', 'controller_partition_created_at',
                 'controller_peak_is_conservative_for_current_operation'))
    for key in ('role_scope_origin', 'role_scope_created_observed_at', 'role_scope_closed_at', 'controller_checkpoint_at'):
        finite(timing[key])
    finite(value['origin']); finite(value['role_child_end']); finite(value['closure_observation_end'])
    require(request['created'] <= value['origin'] <= operation['origin'] == timing['role_scope_origin']
            <= timing['role_scope_created_observed_at'] <= value['role_child_end']
            <= operation['end'] == timing['role_scope_closed_at']
            <= timing['controller_checkpoint_at'] <= value['closure_observation_end'] <= now <= deadline,
            'actual disjoint role and later observer checkpoints in the original lifetime')
    require(timing['controller_peak_scope'] == 'preexisting_partition_lifetime_through_checkpoint'
            and timing['controller_partition_created_at'] is None
            and timing['controller_peak_is_conservative_for_current_operation'] is True,
            'controller lifetime checkpoint is not a fabricated current-operation peak')
    require([root_descriptor(journal, root, item) for item in value['original_processes']]
            == operation['original_processes'], 'same actual role process observations')
    require(type(value['closed_groups']) is list and bool(value['closed_groups'])
            and all(item['created'] is True and item['closed'] is True
                    and item['final']['complete'] is True for item in value['closed_groups']),
            'complete original disjoint cgroup retirement observations')


class PostscoreV2(HistoricalPostscore):
    def __init__(self, plan, source, root, authority, journal, budget, context):
        self.plan = plan; self.source = source; self.root = Path(root)
        self.authority = authority; self.journal = journal; self.budget = budget
        self.policy = plan['interpretation']; admit_policy(self.policy)
        require(self.policy['schema'] == SCHEMA and self.policy['memory_bytes'] <= plan['native_profile']['memory_bytes'],
                'explicit v2 whole bound inside original native envelope')
        require(budget.token_ledger is not None, 'same existing original campaign tokens')
        require(context is not None and context.plan is plan and context.source is source
                and context.budget is budget and context.journal is journal
                and context.authority is authority and context.root == self.root,
                'actual preadmitted original controller/dispatcher owner')
        self.context = context; self.resource = resource_identity(source)
        self.campaign = sha(encoded(plan)); self.carrier = FailureCarrier()
        self.originals = []; self.records = {}; self.consumed = set()
        self.aggregate = None; self.started = None; self.deadline = None
        self.baseline = None; self.requests = []

    def publication(self, record, role):
        return completed_descriptor(self.journal, self.root, record, role)

    def operation(self, role, service, input_descriptor):
        sequence = len(self.requests)
        require(sequence < 4 and role not in self.consumed, 'finite current roles without retry')
        self.budget.admit('before current v2 reporting request', self.deadline)
        self.consumed.add(role); self.check('before original v2 request')
        point = self.point(); reserved_bytes, reserved_files = self.budget.reserved()
        remaining = {k: min(self.policy['limits'][k] - (point[k] - self.baseline[k]),
            self.budget.limits[k] - point[k] -
            (reserved_bytes if k == 'write_bytes' else reserved_files if k == 'files' else 0))
            for k in RESOURCES}
        require(all(v >= 0 for v in remaining.values()), 'same remaining original reporting resources')
        request = {'schema': REQUEST_SCHEMA, 'resource_policy': self.budget.resource_policy,
            'postscore_resource_policy': self.resource,
            'source': self.source.identity, 'campaign': self.campaign,
            'original_origin': self.budget.origin, 'original_deadline': self.budget.deadline,
            'postscore_deadline': self.deadline, 'clock_domain': self.policy['clock_domain'],
            'created': self.budget.clock(), 'sequence': sequence, 'role': role,
            'actor': service['identity'], 'actor_source': service['source'],
            'aggregate': self.aggregate, 'input': input_descriptor, 'rubric': self.policy['rubric'],
            'policy': self.policy['policy'], 'comparisons': list(COMPARISONS),
            'result_not_known_before_request': True, 'maximum_original_operation_resources': remaining,
            'input_namespace': 'exact files in this journal; no other journal or protected input is an actor capability'}
        tokens = self.budget.token_ledger.reserve_external(
            self.policy['maximum_input_tokens'], self.policy['maximum_output_tokens'])
        request['token_reservation'] = dict(tokens); request['memory_limit_bytes'] = self.policy['memory_bytes']
        raw = encoded(request); name = 'INTERPRETATION_REQUEST_%02d.json' % sequence
        path = self.journal.root / name
        request_pin = {'path': str(path.relative_to(self.root)), **pin(raw),
                       'mode': '0o600', 'role': 'original_postscore_request'}
        pending = [{'operation': 'postscore-' + sha(raw), 'quantity': 'pending_original_' + k,
                    'request': request_pin, 'observed': None} for k in RESOURCES]
        owned = {'request': request, 'request_pin': request_pin, 'publication': None,
                 'original_token_reservation': tokens, 'pending_original_costs': pending,
                 'publication_status': 'owned_before_visibility'}
        self.requests.append(owned); self.carrier.retain(owned); self.budget.unknown.extend(pending)
        try:
            owned['publication'] = self.journal.write(name, raw)
            owned['publication_status'] = 'complete_original_publication'
        except BaseException as error:
            owned['publication_status'] = 'failed_original_publication_effect_unresolved'
            owned['publication_error'] = {'type': diagnostic_type(error)}
            raise
        # The exact pending objects stay retained, not removed or zeroed. Only
        # this current source-owned producer may work while they are unresolved.
        with self.budget.postscore_dispatch(sha(raw), pending):
            self.context.complete_current(self, owned, service)
        response, response_pin, publication = self.await_response(sequence, role)
        original = {'role': role, 'request': request, 'response': response,
                    'response_pin': response_pin, 'publication': publication, 'admitted': False}
        self.originals.append(original); self.carrier.retain(original)
        fields = ('schema', 'role', 'request_sha256', 'actor', 'actor_source',
                  'result', 'original_operation', 'qualification')
        keys(response, (*fields, 'blinding_qualification') if role == 'author' else fields)
        require(response['schema'] == RESPONSE_SCHEMA and response['role'] == role
                and response['request_sha256'] == sha(raw)
                and response['actor'] == service['identity'] and response['actor_source'] == service['source'],
                'exact current response/service binding')
        local = owned.get('local_response_owner')
        require(type(local) is dict and local['status'] == 'complete_local_response'
                and local['response'] == response, 'actual current original finalizer publication')
        operation = parse(self.selected(response['original_operation'], 4194304))
        original['original_operation'] = operation
        op_fields = ('schema', 'resource_policy', 'postscore_resource_policy', 'resource_scope',
            'source', 'actor', 'actor_source', 'request_sha256', 'aggregate', 'input', 'result',
            'clock_domain', 'origin', 'end', 'natural', 'reaped', 'descendants_absent', 'status',
            'unknown', 'role_costs', 'original_processes', 'role_observation', 'memory',
            'token_usage', 'controller_finalization')
        keys(operation, op_fields)
        require(operation == local['operation'] and operation['schema'] == OPERATION_SCHEMA
                and operation['resource_policy'] == self.budget.resource_policy
                and operation['postscore_resource_policy'] == self.resource
                and operation['resource_scope'] == RESOURCE_SCOPE
                and operation['source'] == self.source.identity
                and operation['actor'] == service['identity'] and operation['actor_source'] == service['source']
                and operation['request_sha256'] == sha(raw) and operation['aggregate'] == self.aggregate
                and operation['input'] == input_descriptor and operation['result'] == response['result']
                and operation['clock_domain'] == self.policy['clock_domain'],
                'one actual typed closed-role operation and current inputs')
        finite(operation['origin']); finite(operation['end'])
        require(request['created'] <= operation['origin'] <= operation['end'] <= self.budget.clock() <= self.deadline,
                'actual role interval inside original same-clock deadline')
        require(operation['natural'] is True and operation['reaped'] is True
                and operation['descendants_absent'] is True and operation['status'] == 'closed_role_original'
                and operation['unknown'] == [], 'complete actual role custody')
        processes = operation['original_processes']
        require(type(processes) is list and processes
                and len({item['sha256'] for item in processes}) == len(processes),
                'distinct original role process census')
        for item in processes:
            process = parse(self.selected(item, 4194304))
            require(process['reaped'] is True and process['group_absent'] is True
                    and process['returncode'] == 0 and process['natural'] is True,
                    'actual natural original role process')
            require(operation['origin'] <= process['origin'] <= process['end'] <= operation['end'],
                    'same closed-role process chronology')
            finite(process['cpu_seconds']); require(process['cpu_seconds'] >= 0, 'known actual process CPU')
        actual_observation = parse(self.selected(operation['role_observation'], 4194304))
        require(type(actual_observation) is dict and actual_observation == local['role_observation_body'],
                'actual durable native owner/cgroup/daemon observation')
        validate_role_observation(actual_observation, operation, request, self.journal,
                                  self.root, self.budget.clock(), self.deadline)
        validate_memory(operation['memory'], self.policy['memory_bytes'])
        require(operation['controller_finalization'] ==
                'actual continuing original Budget; not future costs inside this receipt',
                'explicit live finalizer boundary')
        joined = owned.get('external_join')
        require(type(joined) is dict and joined is self.context.joins[sha(raw)]
                and joined['complete'] and joined['costs'] == operation['role_costs'],
                'same once-only actual external role join, no second CPU debit')
        subject = services.operation_subject(
            self.source.identity, self.campaign, self.budget.origin, self.policy,
            request_pin, response, self.aggregate, input_descriptor, service)
        self.authority.verify(response['qualification'], 'postscore_scientific_interpretation_operation', subject)
        usage = operation['token_usage']; keys(usage, ('input_tokens', 'output_tokens'))
        self.budget.token_ledger.settle_external(tokens, usage)
        for kind, value in operation['role_costs'].items():
            require(kind in RESOURCES and value <= remaining[kind],
                    'original closed-role remaining-resource cap')
        result = parse(self.selected(response['result'], self.policy['result_bytes']))
        original.update(result=result, admitted=True, exact_original_costs_joined=True)
        owned['pending_cost_resolution'] = {
            'status': 'joined_once_after_actual_local_production_and_independent_admission',
            'original_operation': response['original_operation'], 'role_costs': operation['role_costs'],
            'controller_costs': 'already on same original continuing Budget'}
        self.budget.unknown[:] = [item for item in self.budget.unknown
                                 if not any(item is own for own in pending)]
        self.check('after actual current v2 operation admission')
        return result, response['result']

    def request_documents(self):
        # Raw owners can contain cycles/process objects and remain in carriers.
        # Durable scientific metadata contains finite original evidence pins.
        result = []
        for owned in self.requests:
            row = {key: owned.get(key) for key in (
                'request', 'request_pin', 'publication', 'publication_status',
                'publication_error', 'original_token_reservation',
                'pending_original_costs', 'pending_cost_resolution')}
            join = owned.get('external_join')
            if join is not None:
                row['external_join'] = {key: join.get(key) for key in (
                    'request_sha256', 'joined', 'unknown', 'complete', 'costs',
                    'managed_live_upper_bound_debit')}
                row['external_join']['errors'] = [diagnostic_type(error) for error in join['errors']]
            local = owned.get('local_response_owner')
            if local is not None:
                row['local_response'] = {key: local.get(key) for key in (
                    'role', 'status', 'response', 'response_publication', 'actual_controller_checkpoint')}
            result.append(row)
        return result

    def run(self, paired, numerical_report):
        self.started = self.budget.clock(); self.baseline = self.point()
        whole = min(self.budget.deadline, *self.budget.action_deadlines) if self.budget.action_deadlines else self.budget.deadline
        self.deadline = min(whole, self.started + self.policy['limits']['wall_seconds']) - self.policy['closure_reserve_seconds']
        status = 'unavailable'; first = None
        try:
            require(self.started < self.deadline, 'postscore original closure reserve fits')
            with self.budget.action(self.deadline):
                self.budget.admit('v2 service policy admission', self.deadline)
                for service in [self.policy['author'], *self.policy['reviewers'], self.policy['adjudicator']]:
                    self.selected(service['source'], 16777216)
                    self.authority.verify(service['qualification'], 'postscore_service_qualification',
                        services.service_subject(self.source.identity, service, self.policy, self.budget.resource_policy))
                aggregate = safe_aggregate(paired, self.source.identity, self.campaign, numerical_report)
                published = self.journal.json('INTERPRETATION_SAFE_AGGREGATE.json', aggregate)
                self.aggregate = self.publication(published, 'safe_postscore_aggregate')
                author, author_pin = self.operation('author', self.policy['author'], self.aggregate)
                keys(author, ('schema', 'aggregate', 'comparisons'))
                require(author['schema'] == 'neural055-current-scientific-report-v1'
                        and author['aggregate'] == self.aggregate and set(author['comparisons']) == set(COMPARISONS),
                        'all four original scientific reports')
                for value in author['comparisons'].values():
                    keys(value, ('machine_interpretation', 'scientific_report'))
                    require(type(value['machine_interpretation']) is dict
                            and type(value['scientific_report']) is str and value['scientific_report'].strip(),
                            'actual machine and narrative report')
                self.authority.verify(self.originals[-1]['response']['blinding_qualification'], 'postscore_blinded_report',
                    services.blinded_report_subject(self.source.identity, self.campaign, self.aggregate, author_pin,
                                                    [s['identity'] for s in self.policy['reviewers']]))
                judgments = []; pins = []
                for number, service in enumerate(self.policy['reviewers'], 1):
                    result, result_pin = self.operation('reviewer_' + str(number), service, author_pin)
                    self.judgment(result, service, author_pin); judgments.append(result); pins.append(result_pin)
                disagreements = [c for c in COMPARISONS
                                 if judgments[0]['comparisons'][c]['scores'] != judgments[1]['comparisons'][c]['scores']]
                adjudication = None
                if disagreements:
                    body = {'schema': 'neural055-current-adjudication-input-v1', 'aggregate': self.aggregate,
                            'report': author_pin, 'judgments': pins, 'comparisons': disagreements, 'rubric': self.policy['rubric']}
                    published = self.journal.json('INTERPRETATION_ADJUDICATION_INPUT.json', body)
                    adjudication, _ = self.operation('adjudicator', self.policy['adjudicator'],
                        self.publication(published, 'current_adjudication_input'))
                    keys(adjudication, ('schema', 'aggregate', 'report', 'judgments', 'reviewer', 'comparisons'))
                    require(adjudication['schema'] == 'neural055-current-interpretation-adjudication-v1'
                            and adjudication['aggregate'] == self.aggregate and adjudication['report'] == author_pin
                            and adjudication['judgments'] == pins
                            and adjudication['reviewer'] == self.policy['adjudicator']['identity']
                            and set(adjudication['comparisons']) == set(disagreements),
                            'exact current disagreements and distinct adjudicator')
                    for value in adjudication['comparisons'].values():
                        self.ratings(value)
                for comparison in COMPARISONS:
                    self.records[comparison] = {**author['comparisons'][comparison], 'blinded_to_system': True,
                        'initial': {'reviewer_1': judgments[0]['comparisons'][comparison],
                                    'reviewer_2': judgments[1]['comparisons'][comparison]},
                        'adjudication': None if comparison not in disagreements else adjudication['comparisons'][comparison]}
                score_interpretation(self.records)
                self.check('complete current original interpretations')
                status = 'complete_current_postscore_interpretation'
        except BaseException as error:
            first = error; self.carrier.fail(error, 'postscore_v2_interpretation')
        result = {'schema': 'neural055-original-postscore-disposition-v2',
                  'resource_policy': self.budget.resource_policy, 'postscore_resource_policy': self.resource,
                  'status': status, 'records': self.records if first is None else {},
                  'aggregate': self.aggregate, 'original_requests': self.request_documents(),
                  'original_operations': self.originals, 'errors': self.carrier.document(),
                  'original_deadline': self.budget.deadline, 'postscore_deadline': self.deadline,
                  'numerical_report': numerical_report, 'numerical_validity_unchanged': True,
                  'no_retries': True, 'source_or_scientific_qualification_claim': False,
                  'controller_costs_at_return_checkpoint': self.budget.snapshot(),
                  'future_publication_costs_not_claimed_in_checkpoint': True}
        self.carrier.retain(result)
        return result


def make_handoff(plan, source, root, authority, journal, budget, context=None):
    if type(plan['interpretation']) is dict and plan['interpretation'].get('schema') == SCHEMA:
        return PostscoreV2(plan, source, root, authority, journal, budget, context)
    require(context is None, 'historical v1 has no hidden local dispatcher')
    return HistoricalPostscore(plan, source, root, authority, journal, budget)

