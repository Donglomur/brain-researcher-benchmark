"""Distinct whole-job HM capacities and retained original reservations.

This profile never reinterprets strict V5 rows. It constructs source owners;
runtime observations and scientific qualification remain separate obligations.
"""
import re
import time
from .common import need, closed, integer, encode, parse, pin, relative
from .resources import RootResources, Share

PROGRAMME = 'PAPER-paper-method-replacement-016'
SCHEMA = 'hm_whole_job_observed_stages_v1'
STAGES = ('reference', 'candidate:A', 'candidate:B')
# Explicit versioned interpretation for this new prospective profile only.
# The old strict profile's general process-start contract stays unchanged.
_PROCESS_START_ACCOUNTING_RAW = encode({
    'schema': 'hm_outer_worker_launch_accounting_v1',
    'stage_wire_field': 'physical.process_starts',
    'stage_meaning': 'outer_worker_launch_attempts',
    'attempts_per_stage': 1, 'attempt_latched_before_effect': True,
    'unused_attempts_transferred': False,
    'overhead_wire_field': 'overhead.process_starts',
    'overhead_meaning': 'source_owned_native_observer_launch_attempts',
    'full_descendant_creation_count': None,
    'full_descendant_creation_accounting_qualification': 'unknown_required',
    'pids_peak_meaning': 'concurrent_tasks_not_lifetime_creations',
    'old_general_process_start_contract_parity_claim': False})
LOGICAL = ('read_bytes', 'write_bytes', 'work')
PHYSICAL = ('cpu_ns', 'wall_ns', 'memory_bytes', 'pids',
            'retained_storage_bytes', 'process_starts', 'stream_bytes')
_PLAN = object()
_OWNER = object()
_ALLOCATION = object()
_LIVE = {}


def _identity(value):
    need(type(value) is dict and set(value) in
         ({'bytes', 'sha256'}, {'path', 'bytes', 'sha256'}),
         'exact finite source identity')
    integer(value['bytes'])
    need(type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']),
         'literal SHA256 identity')
    if 'path' in value:
        relative(value['path'])
    return value


def _dimensions(value, keys):
    closed(value, keys)
    for key in keys:
        integer(value[key], 1)
    return value


def _plain(value):
    need(type(value) is str and 0 < len(value) <= 256 and
         all(32 <= ord(c) < 127 for c in value), 'finite plain selection identity')


class HMWholeJobPlanV1:
    def __init__(self, token, body, resource_plan, resource_plan_pin):
        need(token is _PLAN, 'fixed whole-job plan compiler')
        self._body_raw = encode(body)
        self._resource_raw = encode(resource_plan)
        self.body = parse(self._body_raw, len(self._body_raw))
        self.resource_plan = parse(self._resource_raw, len(self._resource_raw))
        self.resource_plan_pin = dict(resource_plan_pin)
        self.pin = pin(self._body_raw)
        self.process_start_accounting = parse(_PROCESS_START_ACCOUNTING_RAW, len(_PROCESS_START_ACCOUNTING_RAW))
        hard = resource_plan['hard_envelope']
        self.origin_ns = hard['origin_monotonic_ns']
        self.run_deadline_ns = resource_plan['programme_budget']['deadline_ns']
        self.evidence_deadline_ns = hard['evidence_deadline_ns']

    def require_original(self):
        need(encode(self.body) == self._body_raw and
             encode(self.resource_plan) == self._resource_raw and
             pin(self._body_raw) == self.pin and
             encode(self.process_start_accounting) == _PROCESS_START_ACCOUNTING_RAW,
             'immutable whole-job source selection and explicit launch accounting')
        return self

    def stage(self, sequence):
        self.require_original()
        integer(sequence, 1)
        need(sequence <= 3, 'all and only original reference/A/B stages')
        # Copies are descriptions, never original allocation owners.
        return parse(encode(self.body['stages'][sequence - 1]),
                     len(encode(self.body['stages'][sequence - 1])))


def compile_original_hm_whole_job_plan_v1(body, *, resource_plan, resource_plan_pin):
    """Validate complete prospective capacities; no clock, I/O or allowance creation."""
    closed(body, ('schema', 'programme', 'campaign_id', 'resource_plan',
        'source_manifest', 'observer_source', 'worker_source', 'environment',
        'launch_policy', 'matched_arm_policy', 'native_configuration', 'storage',
        'host_reservation_id', 'controller', 'overhead', 'stages', 'polling'))
    need(body['schema'] == SCHEMA and body['programme'] == PROGRAMME,
         'distinct explicitly selected HM whole-job profile')
    _plain(body['campaign_id']);_plain(body['host_reservation_id'])
    for key in ('resource_plan', 'source_manifest', 'observer_source', 'worker_source',
                'environment', 'launch_policy', 'matched_arm_policy',
                'native_configuration', 'storage'):
        _identity(body[key])
    _identity(resource_plan_pin)
    need(pin(encode(resource_plan)) == {k: resource_plan_pin[k] for k in ('bytes', 'sha256')} and
         body['resource_plan'] == resource_plan_pin and
         resource_plan['programme'] == PROGRAMME and
         resource_plan['campaign_id'] == body['campaign_id'],
         'same complete original RootResources plan and campaign')
    original = resource_plan['programme_budget'];hard = resource_plan['hard_envelope']
    need(original['kind'] == 'hundred_models_shared_budget_v2' and
         body['matched_arm_policy'] == original['matched_arm_policy'],
         'unchanged original programme and matched-arm selection')
    for key in LOGICAL:integer(original[key], 1)
    for key in ('origin_monotonic_ns', 'run_deadline_ns', 'evidence_deadline_ns',
                'cpu_ns', 'memory_bytes', 'pids', 'retained_storage_bytes'):
        integer(hard[key], 1)
    need(hard['origin_monotonic_ns'] < original['deadline_ns'] <= hard['run_deadline_ns'] <
         hard['evidence_deadline_ns'], 'unchanged original run/evidence interval')
    _dimensions(body['controller'], LOGICAL);_dimensions(body['overhead'], PHYSICAL)
    closed(body['polling'], ('interval_ns', 'termination_grace_ns'))
    for key in ('interval_ns', 'termination_grace_ns'):integer(body['polling'][key], 1)
    need(body['polling']['termination_grace_ns'] <=
         hard['evidence_deadline_ns'] - hard['run_deadline_ns'],
         'original evidence interval retains complete selected termination grace')
    rows = body['stages']
    need(type(rows) is list and len(rows) == 3, 'complete fixed three stage roster')
    nonces = set();workspaces = set()
    for sequence, (stage, row) in enumerate(zip(STAGES, rows), 1):
        closed(row, ('sequence', 'stage', 'logical', 'physical', 'worker_nonce', 'workspace_nonce'))
        need(type(row['sequence']) is int and row['sequence'] == sequence and row['stage'] == stage,
             'literal original stage order, no subset or duplicate')
        _dimensions(row['logical'], LOGICAL);_dimensions(row['physical'], PHYSICAL)
        need(row['physical']['process_starts'] == 1,
             'one nonrefundable outer worker launch attempt per complete stage')
        _plain(row['worker_nonce']);_plain(row['workspace_nonce'])
        need(row['worker_nonce'] not in nonces and row['workspace_nonce'] not in workspaces,
             'distinct original worker and workspace attempts')
        nonces.add(row['worker_nonce']);workspaces.add(row['workspace_nonce'])
        need(body['polling']['interval_ns'] + body['polling']['termination_grace_ns'] < row['physical']['wall_ns'],
             'selected polling interval fits each complete stage lifetime')
    need(rows[1]['logical'] == rows[2]['logical'] and rows[1]['physical'] == rows[2]['physical'],
         'equal locked A/B opportunities under identical whole profile/environment/launch policy')
    for key in LOGICAL:
        need(body['controller'][key] + sum(r['logical'][key] for r in rows) <= original[key],
             'all programme logical reservations within unchanged original budget')
    adapters = resource_plan['adapter_reservations']
    host_rows = [r for r in adapters if r['reservation_id'] == body['host_reservation_id']]
    need(len(host_rows) == 1, 'one earlier original H overhead reservation')
    host = host_rows[0];overhead = body['overhead']
    need(overhead['cpu_ns'] <= host['cpu_ns'] and overhead['wall_ns'] <= host['wall_ns'] and
         overhead['retained_storage_bytes'] <= host['retained_bytes'] and
         overhead['process_starts'] <= host['process_starts'],
         'H/C/bootstrap/IPC/cleanup overhead fits one earlier unchanged adapter hold')
    need(sum(r['physical']['cpu_ns'] for r in rows) + sum(r['cpu_ns'] for r in adapters) <= hard['cpu_ns'],
         'three full W reservations plus all original adapter CPU holds fit whole CPU')
    need(sum(r['physical']['retained_storage_bytes'] for r in rows) +
         sum(r['retained_bytes'] for r in adapters) <= hard['retained_storage_bytes'],
         'no storage reuse/refund or additional stage capacity')
    for key in ('memory_bytes', 'pids'):
        need(overhead[key] + max(r['physical'][key] for r in rows) <= hard[key],
             'serial complete W lifetime plus live H/C overhead fits whole peak')
    need(overhead['wall_ns'] + sum(r['physical']['wall_ns'] for r in rows) <=
         original['deadline_ns'] - hard['origin_monotonic_ns'],
         'whole original time protects every full stage and overhead before execution')
    return HMWholeJobPlanV1(_PLAN, body, resource_plan, resource_plan_pin)


class HMWholeJobStageAllocationV1:
    def __init__(self, token, owner, sequence):
        need(token is _ALLOCATION, 'actual original whole-job reservation factory')
        self.owner = owner;self.plan = owner.plan;self.sequence = sequence
        self.row = self.plan.stage(sequence);self._row_raw = encode(self.row)
        self.stage = self.row['stage'];self.state = 'reserved'
        self.begin_entered = False;self.begin_ns = None;self.deadline_ns = None
        self.raw_first = None;self.secondaries = [];self.native_attempt = None
        self.finish_entered = False;self.complete = False

    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((error, site))
        self.owner.retain(error, 'stage:' + str(self.sequence) + ':' + site)
        self.state = 'failed'

    def require_original(self):
        self.owner.require_original()
        need(self.owner.allocations.get(self.sequence) is self and
             self.plan is self.owner.plan and encode(self.row) == self._row_raw,
             'same original nonrefundable stage allocation')
        if self.raw_first is not None:raise self.raw_first
        return self

    def begin_once(self):
        if self.raw_first is not None:raise self.raw_first
        need(not self.begin_entered, 'one stage clock and deadline attempt, including failure')
        self.begin_entered = True
        try:
            self.require_original()
            self.begin_ns = time.monotonic_ns();integer(self.begin_ns, 1)
            remaining = sum(self.plan.stage(s)['physical']['wall_ns']
                            for s in range(self.sequence + 1, 4))
            # Conservative entire overhead hold stays locked, never reassigned
            # using unused reference/earlier-arm time.
            self.deadline_ns = self.begin_ns + self.row['physical']['wall_ns']
            need(self.plan.origin_ns <= self.begin_ns and
                 self.deadline_ns + remaining + self.plan.body['overhead']['wall_ns'] <=
                 self.plan.run_deadline_ns, 'complete locked future opportunity remains available')
            self.state = 'active'
            return self
        except BaseException as error:
            self.retain(error, 'begin');raise self.raw_first


class HMWholeJobReservationOwnerV1:
    def __init__(self, token, *, resources, plan, host_share):
        need(token is _OWNER and type(resources) is RootResources and
             type(plan) is HMWholeJobPlanV1 and type(host_share) is Share,
             'actual original resource owner, compiled plan and earlier H Share')
        need(getattr(resources, '_hm_whole_job_owner_v1', None) is None,
             'one whole-job source reservation owner, including failed initialization')
        self.resources = resources;self.plan = plan;self.host_share = host_share
        self.allocations = {};self.raw_first = None;self.secondaries = []
        self.closed = False;self.delegation = None;self.campaign = None
        resources._hm_whole_job_owner_v1 = self;_LIVE[id(self)] = self
        try:
            plan.require_original()
            need(encode(resources.plan) == plan._resource_raw and resources.pin == plan.resource_plan_pin,
                 'actual original same RootResources selection')
            rows = [r for r in resources.rows.values()
                    if r['reservation_id'] == plan.body['host_reservation_id']]
            need(len(rows) == 1, 'same unique original adapter reservation')
            row = rows[0]
            need(resources.shares.get((row['owner_role'], row['stage'])) is host_share and
                 host_share.row == row and host_share.deadline_ns == plan.evidence_deadline_ns,
                 'actual existing host Share, not a new equal resource meter')
            need(getattr(host_share, '_hm_whole_job_owner_v1', None) is None,
                 'original overhead share not previously transferred')
            host_share._hm_whole_job_owner_v1 = self
            self.delegation = resources.delegate_programme(resources.plan['programme_budget'])
        except BaseException as error:
            self.retain(error, 'initialization');raise self.raw_first

    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((error, site))

    def require_original(self):
        need(_LIVE.get(id(self)) is self and self.resources._hm_whole_job_owner_v1 is self and
             self.host_share._hm_whole_job_owner_v1 is self and not self.closed,
             'same original live whole-job resource custody')
        self.plan.require_original()
        need(encode(self.resources.plan) == self.plan._resource_raw and
             self.resources.pin == self.plan.resource_plan_pin and self.resources.delegated,
             'unchanged original whole plan and retained programme delegation')
        if self.raw_first is not None:raise self.raw_first
        return self

    def reserve_stage_once(self, sequence):
        self.require_original();integer(sequence, 1)
        need(sequence <= 3 and sequence not in self.allocations and
             sequence == len(self.allocations) + 1 and
             all(a.complete for a in self.allocations.values()),
             'original serial complete stage sequence without replay or borrowing')
        allocation = HMWholeJobStageAllocationV1(_ALLOCATION, self, sequence)
        self.allocations[sequence] = allocation
        return allocation.begin_once()

    def finish_stage_once(self, allocation, actual_native_attempt):
        from .hm_whole_job_native_v1 import HMNativeStageAttemptV1
        need(type(allocation) is HMWholeJobStageAllocationV1 and allocation.owner is self and
             self.allocations.get(allocation.sequence) is allocation and not allocation.finish_entered,
             'one original retained allocation close attempt')
        allocation.finish_entered = True
        try:
            need(type(actual_native_attempt) is HMNativeStageAttemptV1 and
                 actual_native_attempt.allocation is allocation and
                 actual_native_attempt.campaign.reservations is self and
                 self.campaign is actual_native_attempt.campaign and
                 self.campaign.stages.get(allocation.sequence) is actual_native_attempt,
                 'actual source-owned registered native attempt, never a caller receipt')
            allocation.native_attempt = actual_native_attempt
            allocation.require_original()
            need(actual_native_attempt.finished and actual_native_attempt.closure_complete and
                 actual_native_attempt.eligible and actual_native_attempt.raw_first is None,
                 'actual original process/streams/tree/storage closure within selected operational policy')
            allocation.complete = True;allocation.state = 'complete'
            return allocation
        except BaseException as error:
            allocation.retain(error, 'finish');raise allocation.raw_first

    def record(self):
        return {'schema': 'hm_whole_job_retained_reservations_v1', 'profile': self.plan.pin,
            'process_start_accounting': self.plan.process_start_accounting,
            'resource_plan': self.plan.resource_plan_pin, 'programme_delegation': self.delegation,
            'stages': [{'sequence': a.sequence, 'stage': a.stage, 'state': a.state,
                'begin_ns': a.begin_ns, 'deadline_ns': a.deadline_ns,
                'complete': a.complete, 'full_original_reservation_retained': True}
                for a in self.allocations.values()],
            'all_future_stage_limits_locked': True, 'unused_capacity_transferred': False,
            'new_allowance': False, 'qualified_here': False}


def create_original_hm_whole_job_reservations_v1(*, resources, plan, host_share):
    return HMWholeJobReservationOwnerV1(_OWNER, resources=resources, plan=plan, host_share=host_share)
