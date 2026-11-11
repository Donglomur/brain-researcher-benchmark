"""Original HM C/H issuer credit transport and source-owned channel custody.

H reserves each complete issuer allocation once before granting disjoint C/H
views. Local cursors never refund that reservation. Actual frame failure leaves
the complete delegation outstanding. The qualified launch/source and physical
partition remain prerequisites; this module does not qualify its own execution.
"""
import os
import time
from .common import need, closed, integer, encode, parse, pin, bounded_size, failure, DependencyUnavailable
from .channel import RootChannel, HostEndpoint, HostEvent
from .source_session import SourceSession
from .resources import Share, RootResources
from .identity import process_identity
from . import dependencies

PROGRAMME = 'PAPER-paper-method-replacement-016'
_CUSTODY = object()
_CREDIT = object()
_HOST = object()
_TRANSFER = object()
DIMENSIONS = ('read_bytes', 'write_bytes', 'work_units', 'retained_bytes')
_LIVE = {}


def _module(session, name):
    need(type(session) is SourceSession and session.programme == PROGRAMME and not session.closed,
         'actual live original HM source session')
    module = session.modules.get(name)
    need(module is not None and vars(module).get('__loader__') is session and
         vars(module).get('__name__') == session.prefix + '.' + name,
         'already captured actual HM module; no guarded source import')
    return vars(module)


def _plan(session, plan):
    need(type(plan) is _module(session, 'reservations')['ReservationPlan'],
         'same original complete captured HM reservation plan')
    need(plan.body['source_manifest'] == session.catalog['programmes'][PROGRAMME]['source_manifest'] and
         pin(encode(plan.body)) == {k: plan.pin[k] for k in ('bytes', 'sha256')},
         'complete immutable original plan and full HM source selection')
    return plan


def _split(allocation):
    """Fixed complete four-frame demand; unchanged earlier caps must fit it.

    Request/response plus credit-return/ack each contain the existing 8-byte
    frame header. Work and retained-body estimates include complete canonical
    parsing of five issuer documents and original response admission. They are
    source reservations, never measured physical feasibility or new caps.
    """
    frame = integer(allocation['maximum_frame_bytes'], 1)
    c = {'read_bytes': 2 * (frame + 8), 'write_bytes': 2 * (frame + 8),
         'work_units': 1024 * frame + 262144, 'retained_bytes': 32 * frame + 262144}
    total = {'read_bytes': allocation['logical']['read_bytes'],
             'write_bytes': allocation['logical']['write_bytes'],
             'work_units': allocation['logical']['work'],
             'retained_bytes': allocation['physical']['retained_storage_bytes']}
    h = {}
    for kind in DIMENSIONS:
        integer(total[kind]);need(total[kind] >= 2 * c[kind],
            'complete two-ended four-frame issuer demand fits original ' + kind)
        h[kind] = total[kind] - c[kind]
    return {'C': c, 'H': h, 'total': total}


class HMFrameCreditV1:
    """One nontransferable local cursor beneath one retained H reservation."""
    def __init__(self, token, owner, slot, side, limits, window):
        need(token is _CREDIT and side in ('C', 'H'), 'fixed original frame-credit factory')
        self.owner = owner;self.slot = slot;self.side = side
        self.limits = dict(limits);self.spent = dict.fromkeys(DIMENSIONS, 0)
        self.window = dict(window);self.deadline_ns = window['stop_ns']
        self.raw_first = None;self.secondary = [];self.cleanup_errors = []
        self.entered = False;self.closed = False;self.transfers = []
    def own_error(self, error, dimension=None):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondary.append(error)
        self.owner.retain(error, 'frame_credit:' + str(dimension))
    def check(self):
        if self.raw_first is not None:raise self.raw_first
        need(self.entered and not self.closed, 'one active original credit view')
        now = time.monotonic_ns()
        need(self.window['start_ns'] <= now < self.window['stop_ns'],
             'original issuer interval only; no widened transport window')
    def enter(self):
        need(not self.entered and not self.closed, 'no second spend of original frame credit')
        self.entered = True;self.check();return self
    def charge(self, kind, amount):
        self.check();integer(amount);need(kind in DIMENSIONS, 'closed original transport category')
        self.spent[kind] += amount
        try:need(self.spent[kind] <= self.limits[kind], 'original frame credit exceeded; attempted prefix retained')
        except BaseException as error:self.own_error(error, kind);raise
    def state(self):
        return {'slot': self.slot, 'side': self.side, 'limits': dict(self.limits),
                'attempted': dict(self.spent), 'entered': self.entered, 'closed': self.closed,
                'full_H_reservation_retained': True,
                'failure': None if self.raw_first is None else failure(self.raw_first)}


class HMTransportMeterV1:
    """Fixed router: bootstrap Share before admission, exact slot cursor after."""
    def __init__(self, owner, bootstrap):
        need(type(bootstrap) is Share, 'actual earlier selected bootstrap transport Share')
        self.owner = owner;self.bootstrap = bootstrap;self.credit = None
        self.cleanup_errors = [];self.deadline_ns = bootstrap.deadline_ns
    def select(self, credit):
        need(type(credit) is HMFrameCreditV1 and credit.owner is self.owner and self.credit is None,
             'same original unselected local credit')
        self.credit = credit;self.deadline_ns = credit.deadline_ns;credit.enter()
    def release(self, credit):
        need(self.credit is credit and type(credit) is HMFrameCreditV1, 'same original terminal credit')
        credit.closed = True;self.credit = None;self.deadline_ns = self.bootstrap.deadline_ns
    def check(self):
        if self.owner.raw_first is not None:raise self.owner.raw_first
        return self.bootstrap.check() if self.credit is None else self.credit.check()
    def charge(self, kind, amount):
        return (self.bootstrap if self.credit is None else self.credit).charge(kind, amount)
    def own_error(self, error, dimension=None):
        self.owner.retain(error, dimension)
        if self.credit is not None:
            if self.credit.raw_first is None:self.credit.raw_first = error
            elif error is not self.credit.raw_first:self.credit.secondary.append(error)
        else:self.bootstrap.own_error(error, dimension)


class HMOwnProcessSpanV1:
    """Actual own-process monotonic/CPU observations, never W aggregate totals."""
    def __init__(self, owner, role, window, cpu_limit):
        self.owner = owner;self.role = role;self.window = dict(window);self.cpu_limit = integer(cpu_limit)
        self.pid = None;self.begin = None;self.end = None;self.raw_first = None
        self.begin_entered = False;self.end_entered = False;self.complete = False
        self.prefix_attempts = [];self.secondary = []
        # Construction has no clock effects. The caller first retains this
        # exact object on its transfer/slot/wait, then enters it inside cleanup.
        owner.spans.append(self)
    def begin_once(self):
        if self.raw_first is not None:raise self.raw_first
        need(not self.begin_entered, 'one original process-span entry attempt')
        self.begin_entered = True
        self.begin = {'monotonic_ns': None, 'process_cpu_ns': None, 'pid': None}
        try:
            self.pid = os.getpid();self.begin['pid'] = self.pid
            self._observe_into(self.begin, 'span_entry')
            need(self.window['start_ns'] <= self.begin['monotonic_ns'] < self.window['stop_ns'],
                 'actual own-process entry inside original window')
        except BaseException as error:self._retain(error, 'span_entry');raise self.raw_first
        return self
    def _retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondary.append((error, site))
        self.owner.retain(error, site)
    def _observe_into(self, observed, site):
        # Each independent returned value survives later-clock failure. Neither
        # a failed observation nor its bounds check may be silently retried.
        for key, clock in (('monotonic_ns', time.monotonic_ns), ('process_cpu_ns', time.process_time_ns)):
            try:observed[key] = clock();integer(observed[key])
            except BaseException as error:self._retain(error, site + ':' + key)
        if self.raw_first is not None:raise self.raw_first
    def observe_prefix(self):
        if self.raw_first is not None:raise self.raw_first
        need(self.begin is not None and not self.end_entered and os.getpid() == self.pid,
             'same actual original process span before its one end attempt')
        observed = {'monotonic_ns': None, 'process_cpu_ns': None, 'pid': self.pid}
        self.prefix_attempts.append(observed);self._observe_into(observed, 'span_prefix')
        now = observed['monotonic_ns'];cpu = observed['process_cpu_ns']
        try:need(self.begin['monotonic_ns'] <= now < self.window['stop_ns'] and
                 self.begin['process_cpu_ns'] <= cpu and cpu - self.begin['process_cpu_ns'] <= self.cpu_limit,
                 'known original own-process prefix inside selected physical bounds')
        except BaseException as error:self._retain(error, 'span_prefix_bounds');raise self.raw_first
        return {'role': self.role, 'begin': dict(self.begin),
                'observed': dict(observed),
                'cpu_ns': cpu - self.begin['process_cpu_ns'],
                'wall_ns': now - self.begin['monotonic_ns'], 'complete': False}
    def finish_once(self):
        need(not self.end_entered, 'one original own-process end attempt; never retry failed clocks')
        self.end_entered = True;observed = {'monotonic_ns': None, 'process_cpu_ns': None, 'pid': os.getpid()}
        self.end = observed;first = self.raw_first
        for key, clock in (('monotonic_ns', time.monotonic_ns), ('process_cpu_ns', time.process_time_ns)):
            try:observed[key] = clock();integer(observed[key])
            except BaseException as error:
                if first is None:first = error
                self._retain(error, 'span_end:' + key)
        try:
            need(self.begin is not None and observed['pid'] == self.pid and
                 all(self.begin[k] is not None and observed[k] is not None and observed[k] >= self.begin[k] for k in ('monotonic_ns', 'process_cpu_ns')),
                 'actual same-process known nondecreasing end observations')
            need(observed['monotonic_ns'] < self.window['stop_ns'] and
                 observed['process_cpu_ns'] - self.begin['process_cpu_ns'] <= self.cpu_limit,
                 'complete original own-process span inside original physical bounds')
        except BaseException as error:
            if first is None:first = error
            self._retain(error, 'span_end_bounds')
        if first is not None:self.raw_first = first;raise first
        self.complete = True;return self.record()
    def record(self):
        return {'role': self.role, 'pid': self.pid, 'window': dict(self.window),
                'begin': self.begin, 'end': self.end, 'complete': self.complete,
                'end_attempted': self.end_entered, 'prefix_attempts': list(self.prefix_attempts),
                'cpu_ns': None if not self.complete else self.end['process_cpu_ns'] - self.begin['process_cpu_ns'],
                'wall_ns': None if not self.complete else self.end['monotonic_ns'] - self.begin['monotonic_ns'],
                'aggregate_W_CPU_substituted': False}


class HMChannelCustodyV1:
    def __init__(self, token, *, session, plan, role, controller, mapping, bootstrap_share):
        need(token is _CUSTODY, 'fixed source-created HM channel owner')
        self.session = session;self.plan = plan;self.role = role
        self.controller = parse(encode(controller), 131072);self.mapping = parse(encode(mapping), 131072)
        self.bootstrap_share = bootstrap_share;self.pid = os.getpid();self._channel = None
        self.raw_first = None;self.secondaries = [];self.spans = [];self.waits = []
        self.close_entered = False;self.close_complete = False;self.grant_event = None
        self.grants = {};self.transfers = {};self.bootstrap_entered = False
        self.physical_rows = {};self.wait_targets = set()
        self.meter = HMTransportMeterV1(self, bootstrap_share)
        self._binding_raw = None;self._plan_raw = encode(plan.body)
    @property
    def channel(self):return self._channel
    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((error, site))
    def require_original(self):
        construction = getattr(self, 'construction', None)
        need(_LIVE.get(id(self)) is self and type(construction) is HMChannelConstructionV1 and
             construction.owner is self and construction.endpoint is False and construction.complete and
             construction.channel is self._channel and type(self._channel) is RootChannel and
             self._channel.meter is self.meter and self.meter.owner is self and os.getpid() == self.pid and
             not self.close_entered and not self.session.closed and encode(self.plan.body) == self._plan_raw and
             encode(self._channel.binding) == self._binding_raw,
             'same actual source-created channel, process, immutable binding and complete plan')
        if self.raw_first is not None:raise self.raw_first
        return self
    def close_owned_once(self, primary=None):
        # The creation occurrence, not a later same-meter replacement, owns
        # cleanup. Retain custody loss but still retire only that exact original.
        construction = getattr(self, 'construction', None)
        need(_LIVE.get(id(self)) is self and type(construction) is HMChannelConstructionV1 and
             construction.owner is self and construction.endpoint is False and
             type(construction.channel) is RootChannel and construction.channel.meter is self.meter,
             'only this actual retained factory construction may be retired')
        if primary is not None:self.retain(primary, 'caller_primary')
        if self._channel is not construction.channel:
            try:need(False, 'original C channel replaced after construction')
            except BaseException as error:self.retain(error, 'channel_custody_loss')
        if not construction.complete:
            return construction.close_failed_once(primary=self.raw_first)
        if self.close_entered:
            if self.raw_first is not None:raise self.raw_first
            return self.close_complete
        self.close_entered = True
        try:construction.channel.close();self.close_complete = True
        except BaseException as error:self.retain(error, 'channel_close')
        if self.raw_first is not None:raise self.raw_first
        return True
    def prepare_issuer_credits_once(self):
        self.require_original();need(self.role == 'issuer' and not self.bootstrap_entered,
            'one original issuer credit grant exchange before guarded programme work')
        self.bootstrap_entered = True
        try:
            event = self.channel.exchange('continuation', {'schema': 'hm_issuer_credit_bootstrap_request_v1',
                'reservation_plan': self.plan.pin, 'controller': self.controller})
            self.grant_event = event
            need(self.channel.owns_completed_event(event) and event.body['status'] == 'observed',
                 'actual original qualified H bootstrap response')
            result = event.body['result'];closed(result, ('schema', 'reservation_plan', 'controller', 'slots'))
            need(result['schema'] == 'hm_issuer_credit_bootstrap_response_v1' and
                 result['reservation_plan'] == self.plan.pin and result['controller'] == self.controller and
                 type(result['slots']) is list and len(result['slots']) == 3,
                 'all three original source-reserved issuer slots')
            for sequence, row in enumerate(result['slots'], 1):
                t = self.plan.stage(sequence);a = self.plan.rows[t['issuer_host_row']]['issuance']
                expected = {'slot': a['slot'], 'host_row': t['issuer_host_row'], 'window': a['window'],
                            'split': _split(a), 'reservation_plan': self.plan.pin}
                need(row == expected, 'exact fixed complete original two-ended credit grant')
                self.grants[a['slot']] = parse(encode(row), self.channel.cap)
            return event
        except BaseException as error:self.retain(error, 'credit_bootstrap');raise self.raw_first
    def wait_until_original_ns(self, target_ns):
        self.require_original();integer(target_ns, 1)
        need(self.role in ('issuer', 'stage') and target_ns not in self.wait_targets,
             'one actual C bridge wait at each original boundary')
        rows = self.plan.rows;allowed = {}
        for sequence in (1, 2, 3):
            t = self.plan.stage(sequence);c = rows[t['issue_from']];a = rows[t['issuer_host_row']]['issuance']
            if self.role == 'issuer':
                allowed[a['window']['start_ns']] = (c, a['window']['stop_ns'], True)
                allowed[a['window']['stop_ns']] = (c, c['window']['stop_ns'], True)
            restored = rows[t['restore_into']]
            if self.role == 'stage':
                allowed[restored['window']['start_ns']] = (restored, restored['window']['stop_ns'], False)
        for previous, following in (('C03', 'C04'), ('C04', 'C05')):
            if self.role == 'stage':
                allowed[rows[following]['window']['start_ns']] = (rows[following], rows[following]['window']['stop_ns'], False)
        need(target_ns in allowed, 'only selected original issuer/final-row boundaries')
        row, stop, within_row = allowed[target_ns];now = time.monotonic_ns()
        if now >= target_ns:
            need(now < stop, 'already reached only within the unchanged original destination window')
            self.wait_targets.add(target_ns)
            return {'target_ns': target_ns, 'observed_ns': now, 'waited': False,
                    'original_row': row['id'], 'new_allowance': False}
        if not within_row:
            # A pair of own-process clock samples cannot partition CPU across
            # an absolute H-terminal/C or C/C boundary. The actual stage row
            # enforcer must supply that original attribution; no H CPU proxy.
            raise DependencyUnavailable('HM_original_row_boundary_bridge_owner',
                'An early cross-row wait requires the actual original row-boundary physical owner; no extra allowance or inferred CPU partition is supplied')
        need(row['window']['start_ns'] <= now < target_ns < row['window']['stop_ns'],
             'ready within the same original C row; no renewed window')
        # The actual C bridge span is distinct from H own CPU. Its inclusion /
        # exclusion from whole-C physical accounting is independently qualified.
        self.wait_targets.add(target_ns)
        span = HMOwnProcessSpanV1(self, 'C_bridge_wait', {'start_ns': row['window']['start_ns'],
            'stop_ns': stop}, row['physical']['cpu_ns'])
        self.waits.append({'target_ns': target_ns, 'row': row['id'], 'span': span})
        primary = None
        try:
            span.begin_once()
            while time.monotonic_ns() < target_ns:
                self.bootstrap_share.check()
                time.sleep(min(.01, max(0, target_ns - time.monotonic_ns()) / 1e9))
        except BaseException as error:primary = error;self.retain(error, 'original_wait')
        try:span.finish_once()
        except BaseException as error:
            if primary is None:primary = error
            self.retain(error, 'original_wait_end')
        try:self.account_C_span_once(span, row['id'])
        except BaseException as error:
            if primary is None:primary = error
            self.retain(error, 'original_wait_physical_account')
        if primary is not None:raise self.raw_first
        return span.record()
    def account_C_span_once(self, span, row_id):
        need(type(span) is HMOwnProcessSpanV1 and span.owner is self and span in self.spans and
             span.role in ('C_bridge_wait', 'C_issuer_bridge') and row_id in self.plan.rows and
             self.plan.rows[row_id]['owner'] == 'C' and not getattr(span, 'accounted', False),
             'same original C bridge span, once in its selected C physical row')
        span.accounted = True
        row = self.physical_rows.setdefault(row_id, {'cpu_ns': 0, 'wall_ns': 0, 'unknown': [], 'spans': []})
        row['spans'].append(span)
        for clock, dimension in (('process_cpu_ns', 'cpu_ns'), ('monotonic_ns', 'wall_ns')):
            if span.begin is None or span.begin[clock] is None or span.end is None or span.end[clock] is None:
                row['unknown'].append(dimension);continue
            delta = span.end[clock] - span.begin[clock]
            need(delta >= 0, 'original nonnegative C bridge observation')
            row[dimension] += delta
        need(not row['unknown'] and row['cpu_ns'] <= self.plan.rows[row_id]['physical']['cpu_ns'],
             'cumulative actual C bridge CPU fits same original C row; unknown remains held')


class HMChannelConstructionV1:
    """Retained provisional exact endpoint and each selected FD before init.

    A mismatched/unknown descriptor is never adopted or closed. Every selected
    close attempt is latched before its final identity observation and effect.
    Native qualification must prevent descriptor reuse during these operations.
    """
    def __init__(self, token, owner, channel, *, endpoint):
        need(token is _CUSTODY and type(channel) is (HostEndpoint if endpoint else RootChannel),
             'fixed actual original provisional endpoint')
        self.owner = owner;self.channel = channel;self.endpoint = endpoint
        self.complete = False;self.entered = False;self.close_entered = False;self.fds = []
        owner.construction = self
        # Only safe non-owning state before independent identity validation.
        channel.meter = owner.meter;channel.closed = False
        channel.read_fd = None;channel.write_fd = None
    def initialize_once(self, read_fd, write_fd, *, binding, selected_qualification):
        need(not self.entered, 'one original endpoint initialization attempt');self.entered = True
        try:
            dependencies.require('root_issuer_source_and_qualification', selected_qualification)
            closed(binding, ('campaign', 'source', 'launch', 'read_identity', 'write_identity', 'maximum_frame_bytes'))
            integer(read_fd);integer(write_fd);need(read_fd != write_fd, 'distinct selected original channel ends')
            for name, fd, key in (('read_fd', read_fd, 'read_identity'), ('write_fd', write_fd, 'write_identity')):
                attempt = {'name': name, 'fd': fd, 'expected': list(binding[key]), 'observed': None,
                    'selected': False, 'close_entered': False, 'close_observed': None, 'closed': False}
                self.fds.append(attempt)
                s = os.fstat(fd);attempt['observed'] = [s.st_dev, s.st_ino, s.st_mode]
                need(attempt['observed'] == attempt['expected'], 'actual selected original descriptor before custody')
                attempt['selected'] = True;setattr(self.channel, name, fd)
            initializer = HostEndpoint.__init__ if self.endpoint else RootChannel.__init__
            initializer(self.channel, read_fd, write_fd, binding=binding,
                selected_qualification=selected_qualification, meter=self.owner.meter)
            self.complete = True;return self.channel
        except BaseException as error:
            self.owner.retain(error, 'channel_initialization')
            self.close_failed_once(primary=self.owner.raw_first)
    def close_failed_once(self, primary=None):
        if primary is not None:self.owner.retain(primary, 'constructor_primary')
        if not self.close_entered:
            self.close_entered = True;self.owner.close_entered = True;self.channel.closed = True
            for attempt in self.fds:
                if not attempt['selected']:continue
                attempt['close_entered'] = True
                try:
                    need(getattr(self.channel, attempt['name']) == attempt['fd'],
                         'same retained original descriptor before failed-constructor cleanup')
                    s = os.fstat(attempt['fd']);attempt['close_observed'] = [s.st_dev, s.st_ino, s.st_mode]
                    need(attempt['close_observed'] == attempt['expected'],
                         'never close a replaced or mismatched descriptor')
                    setattr(self.channel, attempt['name'], None)
                    os.close(attempt['fd']);attempt['closed'] = True
                except BaseException as error:self.owner.retain(error, 'constructor_close:' + attempt['name'])
            self.owner.close_complete = all(not x['selected'] or x['closed'] for x in self.fds)
        if self.owner.raw_first is not None:raise self.owner.raw_first
        return self.owner.close_complete


def open_hm_channel_custody_v1(*, session, plan, read_fd, write_fd, binding,
        selected_qualification, bootstrap_share, role, controller, mapping):
    _plan(session, plan)
    need(role in ('issuer', 'stage') and type(bootstrap_share) is Share,
         'fixed original channel role and actual earlier transport Share')
    dependencies.require('hm_issuer_transport_native_qualification', plan.body['native_qualification'])
    previous = getattr(plan, 'hm_channel_custodies_v1', None)
    if previous is None:previous = {};plan.hm_channel_custodies_v1 = previous
    need(role not in previous, 'one source-created channel attempt for each original HM role')
    need(bootstrap_share.row in plan.root['adapter_reservations'] and bootstrap_share.owner == 'H' and
         binding['campaign'] == plan.body['campaign_id'] and binding['launch'] == controller['parent_launch'] and
         binding['source'] == plan.body['root_issuer_source' if role == 'issuer' else 'observer_source'],
         'same earlier selected root transport, original launch and exact endpoint source')
    actual = process_identity(os.getpid(), launch_nonce=controller['launch_nonce'], source=controller['source'],
        parent_launch=controller['parent_launch'], mapping=mapping, meter=bootstrap_share)
    need(actual == controller and mapping['source'] == plan.body['clock_binding'],
         'actual original C process and independently selected original clock binding')
    owner = HMChannelCustodyV1(_CUSTODY, session=session, plan=plan, role=role,
        controller=controller, mapping=mapping, bootstrap_share=bootstrap_share)
    previous[role] = owner
    # Retain the exact provisional object before any fallible FD constructor.
    channel = object.__new__(RootChannel)
    owner._channel = channel;owner._binding_raw = encode(binding);_LIVE[id(owner)] = owner
    construction = HMChannelConstructionV1(_CUSTODY, owner, channel, endpoint=False)
    construction.initialize_once(read_fd, write_fd, binding=binding,
        selected_qualification=selected_qualification)
    owner.require_original();return owner


class HMIssuerTransferV1:
    def __init__(self, token, custody, budget, slot):
        need(token is _TRANSFER, 'fixed original issuer exchange factory')
        self.custody = custody;self.budget = budget;self.slot = slot;self.response_event = None
        self.return_event = None;self.span = None;self.token = None;self.complete = False
        self.prefix_checked = False;self.credit = None;self.raw_first = None
        self.request = None;self.phase = 'entered'
    def require_complete(self, token):
        c = self.custody;c.require_original()
        need(c.transfers.get(self.slot) is self and self.complete and self.raw_first is None and
             self.token is token and token.event is self.response_event and self.span.complete and
             c.channel.owns_completed_event(self.response_event) and
             c.channel.owns_completed_event(self.return_event) and self.credit.closed,
             'same original completed returned-credit issuer transfer and local C bridge exit')
        return self


def exchange_original_issuer_v1(*, custody, budget, invocation, subject_pin, guard_state_pin, controller):
    need(type(custody) is HMChannelCustodyV1, 'actual fixed HM channel custody')
    custody.require_original();sm = _module(custody.session, 'stage_budget');im = _module(custody.session, 'issuance')
    need(custody.role == 'issuer' and type(budget) is sm['ExclusiveBudget'] and budget.plan is custody.plan and
         budget.guard is not None and budget.guard['phase'] == 'waiting' and controller == custody.controller,
         'same actual guarded C, original issuer channel and controller')
    a = budget.guard['allocation'];slot = a['slot']
    need(slot in custody.grants and slot not in custody.transfers, 'one complete original grant spend including failure')
    transfer = HMIssuerTransferV1(_TRANSFER, custody, budget, slot);custody.transfers[slot] = transfer
    credit = HMFrameCreditV1(_CREDIT, custody, slot, 'C', custody.grants[slot]['split']['C'], a['window'])
    transfer.credit = credit;primary = None
    try:
        custody.meter.select(credit)
        transfer.span = HMOwnProcessSpanV1(custody, 'C_issuer_bridge', a['window'],
            custody.plan.rows[budget.row]['physical']['cpu_ns'])
        transfer.span.begin_once()
        credit.transfer = transfer
        request = im['request_body'](budget, subject_pin=subject_pin, invocation=invocation,
            guard_state_pin=guard_state_pin, controller=controller, adapter_meter=credit)
        transfer.request = request;transfer.phase = 'request_transfer'
        event = custody.channel.exchange('continuation', {'schema': 'hm_original_issuer_request_v1',
            'slot': slot, 'request': request, 'invocation': invocation,
            'C_entry': transfer.span.begin, 'credit_grant': custody.grants[slot]})
        transfer.response_event = event
        need(custody.channel.owns_completed_event(event) and event.body['status'] == 'observed',
             'actual original complete issuer response event')
        transfer.phase = 'credit_return_transfer'
        returned = {'schema': 'hm_issuer_credit_return_v1', 'slot': slot,
            'response': event.raw_pin, 'request': pin(encode(request)),
            'C_prefix': transfer.span.observe_prefix(), 'credit_prefix': credit.state(),
            'remaining_credit_fully_reserved': True}
        ack = custody.channel.exchange('continuation', returned);transfer.return_event = ack
        result = ack.body['result']
        closed(result, ('schema', 'slot', 'response', 'request', 'return_prefix', 'full_reservation_retained'))
        need(custody.channel.owns_completed_event(ack) and ack.body['status'] == 'observed' and
             result == {'schema': 'hm_issuer_credit_return_ack_v1', 'slot': slot,
                'response': event.raw_pin, 'request': pin(encode(request)),
                'return_prefix': pin(encode(returned)), 'full_reservation_retained': True},
             'actual original H-admitted return, never inferred from a successful write')
        transfer.phase = 'original_response_admission'
        transfer.token = im['capture_issuer_response'](event, budget=budget, invocation=invocation,
            subject_pin=subject_pin, adapter_meter=credit)
        need(transfer.prefix_checked, 'actual source-owned physical-prefix join completed')
    except BaseException as error:
        primary = error;transfer.raw_first = error;custody.retain(error, 'issuer_exchange');budget._own(error)
    finally:
        if transfer.span is not None and not transfer.span.end_entered:
            try:transfer.span.finish_once()
            except BaseException as error:
                if primary is None:primary = error;transfer.raw_first = error
                custody.retain(error, 'C_bridge_exit');budget._own(error)
        if transfer.span is not None and transfer.span.end_entered:
            try:custody.account_C_span_once(transfer.span, budget.row)
            except BaseException as error:
                if primary is None:primary = error;transfer.raw_first = error
                custody.retain(error, 'C_bridge_physical_account');budget._own(error)
        if custody.meter.credit is credit:
            try:custody.meter.release(credit)
            except BaseException as error:
                if primary is None:primary = error;transfer.raw_first = error
                custody.retain(error, 'credit_close');budget._own(error)
    if primary is not None:raise primary
    transfer.complete = True;transfer.phase = 'complete';transfer.require_complete(transfer.token)
    return transfer.token


def require_original_issuer_physical_prefix_v1(*, raw, descriptor, response, request, budget, adapter_meter):
    need(type(adapter_meter) is HMFrameCreditV1 and adapter_meter.side == 'C',
         'actual original C transport credit, no generic W/adapter totals')
    transfer = getattr(adapter_meter, 'transfer', None)
    need(type(transfer) is HMIssuerTransferV1 and transfer.credit is adapter_meter and transfer.budget is budget and
         transfer.custody.transfers.get(transfer.slot) is transfer and transfer.return_event is not None,
         'same actual source-owned exchange with original H return acknowledgement')
    need(pin(raw) == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'same original physical prefix bytes')
    body = parse(raw, len(raw));closed(body, ('schema', 'slot', 'request', 'reservation_plan',
        'host_row', 'H_identity', 'C_identity', 'H_prefix', 'C_entry', 'full_reservation_retained',
        'C_exit_not_yet_observed', 'whole_physical_reconciliation_required'))
    a = budget.guard['allocation'];t = budget.plan.stage(request['sequence'])
    need(body['schema'] == 'hm_original_issuer_physical_prefix_v1' and body['slot'] == transfer.slot and
         body['request'] == pin(encode(request)) and body['reservation_plan'] == budget.plan.pin and
         body['host_row'] == t['issuer_host_row'] and body['C_identity'] == request['controller'] and
         body['C_entry'] == transfer.span.begin and body['full_reservation_retained'] is True and
         body['C_exit_not_yet_observed'] is True and body['whole_physical_reconciliation_required'] is True,
         'honest original H prefix before response, distinct actual C entry and retained physical reservation')
    hp = body['H_prefix'];closed(hp, ('role', 'begin', 'observed', 'cpu_ns', 'wall_ns', 'complete'))
    need(hp['role'] == 'H_issuer_own_process' and hp['complete'] is False and
         hp['begin']['pid'] == hp['observed']['pid'] == body['H_identity']['pid'] and
         body['H_identity'] != body['C_identity'] and
         a['window']['start_ns'] <= hp['begin']['monotonic_ns'] <= hp['observed']['monotonic_ns'] <= response['response_prefix_observed_ns'] < a['window']['stop_ns'] and
         hp['cpu_ns'] == hp['observed']['process_cpu_ns'] - hp['begin']['process_cpu_ns'] and
         hp['wall_ns'] == hp['observed']['monotonic_ns'] - hp['begin']['monotonic_ns'],
         'actual authenticated H own-process prefix, no worker aggregate substitution')
    integer(hp['cpu_ns']);integer(hp['wall_ns'])
    need(hp['cpu_ns'] <= a['physical']['cpu_ns'], 'original issuer H CPU prefix bound')
    transfer.span.observe_prefix();transfer.prefix_checked = True
    return body
