"""Live early H custody, protected nested partitions, and original raw failures.

The actual parent Share must predate this owner. This module never constructs a
replacement Share from JSON or turns a seed/selection into a qualification.
"""
import time
from .common import need, integer, same, DependencyUnavailable
from .resources import Share
from .precommit_records import DIMENSIONS, CONDITIONS, validate_type
from . import dependencies

_PARENT = object()
_OWNER = object()
_VIEW = object()

def _spent(share):
    return {**share.spent, 'process_starts': share.process_starts,
            'cpu_ns': share.cpu_ns, 'wall_ns': share.wall_ns}

class ParentCustody:
    """Only an independently admitted earlier fixed parent bootstrap may bind."""
    def __init__(self, token, share, *, clock, identity, custody, source, nonce):
        need(token is _PARENT and type(share) is Share, 'actual earlier fixed Share owner')
        self.share = share
        self.raw_errors = []
        self.first_raw = None
        # The inherited Share stores prospective charges, not completed I/O.
        # Until an independently admitted earlier completion producer supplies
        # them, never relabel those reservations as measured observations.
        self.unknown = {'read_bytes', 'write_bytes', 'work_units', 'retained_bytes'}
        self.owner = None
        self.attach_attempted = False
        self.clock, self.identity = clock, identity
        self.custody, self.source, self.nonce = custody, source, nonce
        self.selection = None
        self.seed_pin = None
        self.binding_pin = None
        self.known_records = []
        self.creation_captures = []
        self.failure_publication_attempted = False
        # No cost observations are reset here. The parent Share, active span,
        # starts, raw errors and cache references remain owned by the parent.
        self.initial_share_object = share
        self.initial_counter_object = share.spent
        self.original_active = share._active
        self.original_origin = share.origin_ns
        self.original_deadline = share.deadline_ns
        need(share._early_parent_custody is None,'one original early raw-error custody binding')
        share._early_parent_custody=self
        for error,dimension in share._raw_error_history:
            self.retain(error,'source_capture','unknown_failure','ParentCustody.earlier_error')
    def retain(self, error, phase, code, site, unknown=None):
        # First action stores the actual exception, before any fallible type,
        # clock, diagnostic projection, cleanup or publication operation.
        if self.first_raw is None:
            self.first_raw = error
        if not self.raw_errors or self.raw_errors[-1][0] is not error:
            self.raw_errors.append((error, phase, code, site))
        if unknown is not None:
            need(unknown in DIMENSIONS, 'closed unknown resource dimension')
            self.unknown.add(unknown)
    def assert_live(self):
        need(self.share is self.initial_share_object and self.share.spent is self.initial_counter_object,
             'same original Share and counter storage')
        need(self.share.origin_ns == self.original_origin and self.share.deadline_ns == self.original_deadline,
             'no origin or deadline renewal')

def bind_parent(share, *, clock, identity, custody, source, nonce, qualification):
    # This fixed external prerequisite remains absent until separately selected.
    dependencies.require('ci_early_parent_source_and_qualification', qualification)
    need(type(share) is Share, 'earlier admitted live parent Share')
    for typ, value in [('OriginalClock', clock), ('OriginalProcessIdentity', identity),
                       ('Pin', custody), ('Pin', source), ('Text', nonce)]:
        validate_type(typ, value)
    need(share.origin_ns == clock['origin_monotonic_ns'] and share.deadline_ns == clock['evidence_deadline_ns'],
         'exact existing parent clock and evidence cutoff')
    need(share.row['owner_role'] == 'H' and share._active is not None,
         'parent H accounting was live before seed construction')
    return ParentCustody(_PARENT, share, clock=clock, identity=identity, custody=custody, source=source, nonce=nonce)

class PartitionMeter:
    """A view into one owner, not a second Share or independent allowance."""
    def __init__(self, token, owner, name, terminal=False):
        need(token is _VIEW, 'source-owned nested partition view')
        self.owner = owner; self.name = name; self.terminal = terminal
        self.deadline_ns = owner.parent.original_deadline
        self.origin_ns = owner.parent.original_origin
        self.cleanup_errors = []
    def check(self): self.owner.check()
    def charge(self, kind, amount): self.owner.charge(self.name, kind, amount, terminal=self.terminal)
    def spawn_attempt(self): self.charge('process_starts', 1)
    def own_error(self, error, dimension=None):
        mapped = None
        if dimension is not None:
            if 'read' in dimension: mapped = 'read_bytes'
            elif 'write' in dimension: mapped = 'write_bytes'
            elif 'cpu' in dimension: mapped = 'cpu_ns'
            elif 'clock' in dimension or 'wall' in dimension: mapped = 'wall_ns'
        self.owner.parent.retain(error, 'source_capture', 'unknown_failure', 'early_resources.PartitionMeter', mapped)
    def record(self): return self.owner.cost_prefix()

class EarlyResources:
    def __init__(self, token, parent):
        need(token is _OWNER and type(parent) is ParentCustody, 'source-owned original early custody')
        self.parent = parent
        self.plan = self.seed = None
        self.partitions = None
        self.used = None
        self.terminal_reserve = None
        self.terminal = False
        self.adopted = False
        self.host = self.terminal_host = None
        self.arms = {}
        self._host_clock_prefix = {'wall_ns': 0, 'cpu_ns': 0}
        self.observed = _spent(parent.share)
        self.initial_completed = {'wall_ns': parent.share.wall_ns, 'cpu_ns': parent.share.cpu_ns}
    @classmethod
    def attach_seed_v2(cls, parent, seed, plan):
        need(type(parent) is ParentCustody, 'actual earlier parent capability, never a wire record')
        need(not parent.attach_attempted, 'one seed attachment attempt including failures')
        parent.attach_attempted = True
        owner = cls(_OWNER, parent); parent.owner = owner
        try:
            parent.assert_live()
            # Earlier parent meters validation before a nested plan is admitted.
            # Bound is fixed by selected parent's remaining source budget.
            from .common import bounded_size
            parent.share.charge('work_units', bounded_size(seed) + bounded_size(plan))
            validate_type('EarlyOwnerSeed', seed); validate_type('ConstructionPlan', plan)
            need(same(seed['clock'], parent.clock) and same(seed['host_identity'], parent.identity) and
                 same(seed['parent_owner_custody'], parent.custody) and same(seed['host_source'], parent.source),
                 'exact earlier source/clock/host/custody binding')
            need(same(seed['early_reservation'], parent.share.row), 'same original reservation row')
            need(seed['campaign_id'] == plan['campaign_id'] == parent.clock['campaign_id'], 'same original campaign')
            for field in ('host_subshare', 'arm_subshare', 'terminal_host_reserve'):
                need(same(seed[field], plan[field]), 'same exact earlier partition plan')
            row = parent.share.row; host = seed['host_subshare']; arm = seed['arm_subshare']; terminal = seed['terminal_host_reserve']
            for dimension in DIMENSIONS:
                need(host[dimension] + 2*arm[dimension] <= row[dimension], 'nested reservations inside original row')
                need(terminal[dimension] <= host[dimension], 'terminal reserve nested inside original host')
            used = _spent(parent.share)
            for dimension in DIMENSIONS:
                need(used[dimension] <= host[dimension]-terminal[dimension], 'earlier spent prefix cannot consume protected terminal reserve')
            owner.plan, owner.seed = plan, seed
            owner.partitions = {'host': dict(host), **{name: dict(arm) for name in CONDITIONS}}
            owner.used = {'host': used, **{name: dict.fromkeys(DIMENSIONS, 0) for name in CONDITIONS}}
            owner.terminal_reserve = dict(terminal)
            owner.host = PartitionMeter(_VIEW, owner, 'host')
            owner.terminal_host = PartitionMeter(_VIEW, owner, 'host', True)
            owner.arms = {name: PartitionMeter(_VIEW, owner, name) for name in CONDITIONS}
            owner.check()
            return owner
        except BaseException as error:
            parent.retain(error, 'seed_admission', 'identity_refusal', 'EarlyResources.attach_seed_v2')
            raise
    def check(self):
        try:
            return self._check()
        except BaseException as error:
            self.parent.retain(error, 'development_observe', 'identity_refusal', 'EarlyResources.check')
            raise
    def _check(self):
        self.parent.assert_live()
        need(self.partitions is not None, 'completed protected partition admission')
        for dimension, amount in self.parent.share.spent.items():
            need(amount == sum(row[dimension] for row in self.used.values()),
                 'all actual original counter changes have a protected partition owner')
        need(self.parent.share.process_starts == sum(row['process_starts'] for row in self.used.values()),
             'same original process-attempt accounting')
        primary = None
        for dimension, reader in (('wall_ns', time.monotonic_ns), ('cpu_ns', time.process_time_ns)):
            try:
                observed = reader(); integer(observed)
            except BaseException as error:
                self.parent.retain(error, 'development_observe', 'clock_failure',
                                   'EarlyResources.check.clock', dimension)
                if primary is None: primary = error
                continue
            try:
                self._observe_clock(dimension, observed)
                if dimension == 'wall_ns':
                    need(observed < self.parent.original_deadline, 'unchanged original evidence deadline')
            except BaseException as error:
                self.parent.retain(error, 'development_observe', 'budget_refusal', 'EarlyResources.check.limit')
                if primary is None: primary = error
        if primary is not None: raise primary
        if getattr(self, 'native_receiver_ledgers', ()):
            from .backend_native_reservations import check_native_physical_holds
            for partition in self.partitions:
                for dimension in ('cpu_ns', 'wall_ns'):
                    limit=self.partitions[partition][dimension]
                    if partition=='host' and not self.terminal:limit-=self.terminal_reserve[dimension]
                    check_native_physical_holds(self,partition,dimension,0,limit)
    def _observe_clock(self, dimension, observed):
        share = self.parent.share
        index = 0 if dimension == 'wall_ns' else 1
        start = self.parent.original_active
        if start is None or share._active is not start:
            self.parent.unknown.add(dimension)
            need(False, 'same original unfinished parent span')
        delta = observed - start[index]
        if delta < self._host_clock_prefix[dimension]:
            self.parent.unknown.add(dimension)
            need(False, 'nondecreasing original active clock')
        integer(delta)
        total = self.initial_completed[dimension] + delta
        limit = self.partitions['host'][dimension] - (0 if self.terminal else self.terminal_reserve[dimension])
        # Actual known over-cap use is retained before refusing; never rolled back.
        self._host_clock_prefix[dimension] = delta
        self.used['host'][dimension] = total
        self.observed[dimension] = total + sum(self.used[name][dimension] for name in CONDITIONS)
        need(total <= limit, 'same protected original host time reservation')
        # Share.end later admits this full span once. We do not add the sampled
        # active prefix into its completed counters and charge it a second time.
    def charge(self, partition, dimension, amount, *, terminal=False):
        try:
            return self._charge(partition, dimension, amount, terminal=terminal)
        except BaseException as error:
            self.parent.retain(error, 'source_capture', 'budget_refusal', 'EarlyResources.charge')
            raise
    def _charge(self, partition, dimension, amount, *, terminal=False):
        integer(amount); need(dimension in DIMENSIONS, 'source-closed seven cost dimensions')
        need(partition in self.partitions, 'same original protected partition')
        need(not terminal or partition == 'host', 'terminal reserve belongs only to H')
        need(not terminal or self.terminal, 'terminal source phase entered before terminal charges')
        self.check()
        limit = self.partitions[partition][dimension]
        if partition == 'host' and not terminal: limit -= self.terminal_reserve[dimension]
        current = self.used[partition][dimension]
        if getattr(self, 'native_receiver_ledgers', ()):
            from .backend_native_reservations import check_native_physical_holds
            check_native_physical_holds(self,partition,dimension,amount,limit)
        need(current + amount <= limit, 'no protected partition borrowing or allowance renewal')
        if partition == 'host' and dimension in ('cpu_ns', 'wall_ns'):
            need(amount == 0, 'host clocks observed from original span, not charged twice')
        # Atomic preadmission: all checks precede the original parent mutation.
        parent = self.parent.share
        if dimension in parent.spent:
            need(parent.spent[dimension] + amount <= parent.limits[dimension], 'original parent aggregate logical cap')
            parent.spent[dimension] += amount
        elif dimension == 'process_starts':
            need(parent.process_starts + amount <= parent.row['process_starts'], 'original parent process-start cap')
            parent.process_starts += amount
        self.used[partition][dimension] += amount
        if dimension == 'process_starts':
            self.observed[dimension] = parent.process_starts
    def observe_child_cpu(self, condition, total):
        integer(total); need(condition in CONDITIONS, 'fixed candidate arm')
        previous = self.used[condition]['cpu_ns']
        need(total >= previous, 'monotonic actual child-group cumulative CPU')
        self.charge(condition, 'cpu_ns', total-previous)
        self.observed['cpu_ns'] = sum(row['cpu_ns'] for row in self.used.values())
        # Whole physical CPU is sampled independently once; never add that
        # aggregate into H own CPU or these exclusive child-group counters.
    def enter_terminal(self):
        self.terminal = True
    def cost_prefix(self):
        parent = self.parent
        charged = _spent(parent.share) if self.used is None else {
            key: sum(row[key] for row in self.used.values()) for key in DIMENSIONS}
        # Even rejected unattributed parent mutations remain in the known
        # charged prefix. No stale partition table can conceal their cost.
        charged.update(parent.share.spent)
        charged['process_starts'] = parent.share.process_starts
        unknown = sorted(parent.unknown)
        observed = {key: None if key in parent.unknown else self.observed.get(key, charged[key]) for key in DIMENSIONS}
        active = parent.share._active
        return {'schema': 'ci_costprefix_v2', 'charged': charged, 'observed': observed,
                'unknown_dimensions': unknown, 'unfinished_span': active is not None,
                'original_active_wall_start_ns': None if active is None else active[0],
                'original_active_cpu_start_ns': None if active is None else active[1],
                'cleanup_reservation_retained': True}

def failure_observations(parent):
    """No exception repr, attribute lookup, new clock or unbounded diagnostic."""
    need(type(parent) is ParentCustody and parent.raw_errors, 'retained actual original failure')
    result = []
    for ordinal, (_, phase, code, site) in enumerate(parent.raw_errors):
        row = {'schema': 'ci_failureobservation_v2', 'ordinal': ordinal, 'phase': phase,
               'code': code, 'source_site': site, 'observation_ns': None, 'raw_error_retained': True}
        validate_type('FailureObservation', row)
        result.append(row)
    return result

def preselection_failure_v2(parent, attempt, selection_capture):
    """Truthful seed-only or earlier failure; cannot claim future selection."""
    need(type(parent) is ParentCustody and parent.owner is not None, 'actual retained parent and attempted owner')
    need(parent.selection is None, 'authenticated selection requires the separate postselection carrier')
    validate_type('SelectionCapturePrefix', selection_capture)
    need(selection_capture['authenticated'] is False, 'no authenticated selection in preselection failure')
    errors = failure_observations(parent)
    row = {'schema': 'ci_preselectionfailureprefix_v2', 'attempt': attempt,
           'parent_owner_custody': parent.custody, 'host_identity': parent.identity,
           'clock': parent.clock, 'reservation': parent.share.row, 'owner_nonce': parent.nonce,
           'seed': parent.seed_pin, 'owner_binding': parent.binding_pin, 'selection': None,
           'selection_capture': selection_capture, 'creation_captures': list(parent.creation_captures),
           'known_records': list(parent.known_records), 'cost_prefix': parent.owner.cost_prefix(),
           'first_error': errors[0], 'secondary_errors': errors[1:], 'dependent_execution_allowed': False}
    validate_type('PreselectionFailurePrefix', row)
    return row
