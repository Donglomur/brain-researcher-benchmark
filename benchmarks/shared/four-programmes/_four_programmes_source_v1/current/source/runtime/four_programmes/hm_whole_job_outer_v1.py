"""Actual outer H/C completion and whole physical reconciliation.

O remains inside the original whole cgroup, outside H's aggregate. It finishes
the real H process, captures its fixed terminal only after tree closure, and
reconciles independent whole counters without adding overlapping own clocks.
An integrated qualified H bootstrap is still an external source prerequisite.
No native action occurs on import; no supplied callback/receipt completes H.
"""
import os
import time
from pathlib import Path
from .common import need, closed, integer, encode, parse, pin, failure, Store, descriptor, DependencyUnavailable
from .identity import kernel_read, process_identity
from .observer import HostObserver, RunningProcess, OriginalProcessObservation
from .resources import RootResources, Share
from .roots import BoundRoots
from .hm_whole_job_profile_v1 import HMWholeJobPlanV1, PROGRAMME
from .hm_whole_job_native_observations_v1 import HMFixedVolumeCustodyV1
from .hm_whole_job_native_v1 import _group_pids
from . import dependencies

CAP = 1048576
_TOKEN = object()
_LIVE = {}


class HMOuterProvisioningV1:
    """Re-open the same exact selected provisioning through the original O Share."""
    def __init__(self, owner, roots):
        self.owner = owner;self.complete = False;self.provisioning = None
        plan = owner.plan
        need(type(roots) is BoundRoots and roots.meter is owner.meter,
             'original separately selected O roots and existing Share')
        self.configuration_raw = roots.read(plan.body['native_configuration'], CAP, metadata=True)
        self.body = parse(self.configuration_raw, CAP)
        need(encode(self.body) == self.configuration_raw and
             self.body['schema'] == 'hm_whole_native_configuration_v1' and
             self.body['storage_provisioning'] == plan.body['storage'],
             'same canonical original H native configuration/storage selection')
        for key in ('source_manifest', 'observer_source', 'worker_source', 'environment', 'launch_policy'):
            need(self.body[key] == plan.body[key], 'same original selected ' + key)
        selected = {'environment': plan.body['environment'], 'observer_source': plan.body['observer_source'],
                    'source_manifest': plan.body['source_manifest'], 'fixed_volume_provisioning': plan.body['storage']}
        need(self.body['selected_host_qualification'] == selected, 'same independent native host binding')
        dependencies.require('root_observer_host_clock_environment', selected)
        self.provisioning_raw = roots.read(plan.body['storage'], CAP, metadata=True)
        p = parse(self.provisioning_raw, CAP);self.provisioning = p
        closed(p, ('schema', 'environment', 'observer_source', 'mountpoint', 'filesystem_id',
            'filesystem_device', 'filesystem_inode', 'block_device', 'block_device_rdev',
            'backend_capacity_bytes', 'whole_group_identity', 'custody_authority', 'provisioning_authority',
            'writer_scope', 'resize_policy', 'accounting'))
        need(encode(p) == self.provisioning_raw and p['schema'] == 'hm_exclusive_fixed_block_volume_v1' and
             p['environment'] == plan.body['environment'] and p['observer_source'] == plan.body['observer_source'] and
             p['writer_scope'] == 'original_whole_campaign_only' and
             p['resize_policy'] == 'immutable_provisioned_backend' and
             p['accounting'] == 'allocated_physical_blocks_with_filesystem_metadata',
             'original fixed-capacity/exclusive-writer/no-resize physical domain')
        for key in ('custody_authority', 'provisioning_authority'):
            roots.read(p[key], CAP, metadata=True)
        need(tuple(p['whole_group_identity']) == owner.host.whole_group.identity and
             Path(p['mountpoint']) == owner.host.storage.path,
             'same actual independent whole-group and original volume owner')
        for key in ('mountpoint', 'block_device'):
            path = Path(p[key]);need(path.is_absolute() and '..' not in path.parts and str(path) == p[key],
                                   'literal original native path')
        self.complete = True

    def require_original(self):
        need(self.owner.configuration is self and self.complete and
             encode(self.body) == self.configuration_raw and
             encode(self.provisioning) == self.provisioning_raw,
             'same immutable complete outer provisioning')
        self.owner.plan.require_original();return self


class HMWholeOuterCoordinatorV1:
    def __init__(self, token, *, plan, resources, host, running_host, configuration_roots,
                 terminal_store, expected_outer_identity):
        need(token is _TOKEN and type(plan) is HMWholeJobPlanV1 and type(resources) is RootResources and
             type(host) is HostObserver and type(running_host) is RunningProcess and
             running_host.owner is host and type(host.meter) is Share and type(terminal_store) is Store,
             'actual original plan/resources/O observer/H process and bounded terminal store')
        need(getattr(resources, '_hm_whole_outer_v1', None) is None,
             'one original outer completion attempt including admission failure')
        self.plan = plan;self.resources = resources;self.host = host;self.running = running_host
        self.meter = host.meter;self.terminal_store = terminal_store;self.expected_outer_identity = expected_outer_identity
        self.raw_first = None;self.secondaries = [];self.configuration = None;self.volume = None
        self.entered = False;self.closed = False;self.observation = None;self.terminal = None;self.terminal_pin = None
        self.samples = [];self.final_sample = None;self.report = None;self.report_pin = None
        self.finish_attempted = False;self.resource_close_attempted = False;self.span_end_attempted = False
        self.host_exit = None;self.memberships = [];resources._hm_whole_outer_v1 = self;_LIVE[id(self)] = self
        self.cleanup_owned = False
        self.admitted = False
        try:
            plan.require_original()
            need(not resources.staged and resources.delegated and resources.terminal is None and
                 encode(resources.plan) == plan._resource_raw and resources.pin == plan.resource_plan_pin,
                 'same already delegated original whole opportunity')
            need(any(share is self.meter for share in resources.shares.values()) and
                 self.meter.row['reservation_id'] != plan.body['host_reservation_id'] and
                 self.meter._active is not None and not self.meter._end_attempted and
                 host.outputs.meter is self.meter and terminal_store.meter is self.meter,
                 'distinct existing O Share and earlier open span, never new/refilled H capacity')
            self.original_span = self.meter._active
            hard = plan.resource_plan['hard_envelope'];r = running_host
            need(plan.body['overhead']['pids'] >= 3 and
                 host.active.get(r.spec['nonce']) is r and r.spec['mode'] == 'hm_whole_host' and
                 r.spec['campaign'] == plan.body['campaign_id'] and r.spec['source'] == plan.body['observer_source'] and
                 r.spec['evidence_deadline_ns'] == hard['evidence_deadline_ns'] == self.meter.deadline_ns and
                 r.spec['run_deadline_ns'] <= hard['run_deadline_ns'] and
                 r.identity is not None and r.child is not None and not r.finish_attempted,
                 'actual distinct original H launch under unchanged full cutoffs and O/H/C opportunity')
            self.cleanup_owned = True
            need(r.group.path.is_relative_to(host.whole_group.path) and r.group.path != host.whole_group.path,
                 'H aggregate below the same independent whole domain')
            self._membership()
            from .observer import bind_hm_exit_accounting_v1
            self.host_exit = bind_hm_exit_accounting_v1(host, r, role='H',
                expected_identity=r.identity, clock_mapping=host.mapping,
                poll_interval_ns=plan.body['polling']['interval_ns'])
            # No current source-owned H launcher binds this actual process to
            # its publisher root. Neither an admitted scalar path nor a new
            # dictionary under the old Context selector grants that custody.
            # This explicit runtime hold does not prevent source-only inactive
            # installation; the physical completion methods below are real.
            raise DependencyUnavailable('HM_original_H_launch_publisher_custody',
                'actual source-owned H launch/terminal publisher binding remains missing')
            self.configuration = HMOuterProvisioningV1(self, configuration_roots)
            HMFixedVolumeCustodyV1(self).open_once()
            self.observe_once()
            self.admitted = True
        except BaseException as error:
            self.retain(error, 'outer_admission')
            # Only the verified exact H owner is eligible for this cleanup;
            # an unrelated/foreign RunningProcess is never adopted or killed.
            if self.cleanup_owned:
                try:self.finish_once()
                except BaseException as later:
                    if later is not self.raw_first:self.retain(later, 'partial_outer_cleanup')
            try:BaseException.__setattr__(self.raw_first, 'hm_original_outer_owner', self)
            except BaseException as later:self.retain(later, 'outer_failure_attachment')
            raise self.raw_first

    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((site, error))
        try:self.meter.own_error(error, 'HM_outer:' + site)
        except BaseException as later:
            if later is not self.raw_first:self.secondaries.append((site + ':retention', later))

    def _membership(self):
        self.host.whole_group.own()
        root = Path('/sys/fs/cgroup');whole = self.host.whole_group.path
        need(whole.is_absolute() and whole.is_relative_to(root) and '..' not in whole.parts,
             'selected fixed Linux cgroup mount mapping')
        raw = kernel_read('/proc/self/cgroup', 8192, self.meter)
        lines = raw.decode('utf-8').splitlines();unified = [line[3:] for line in lines if line.startswith('0::')]
        need(len(unified) == 1 and unified[0].startswith('/') and '..' not in Path(unified[0]).parts,
             'one actual unified membership in qualified mount namespace')
        actual = root / unified[0].lstrip('/')
        need(actual.is_relative_to(whole) and not actual.is_relative_to(self.running.group.path),
             'O inside original whole domain, outside actual H aggregate')
        expected = self.expected_outer_identity
        current = process_identity(os.getpid(), launch_nonce=expected['launch_nonce'], source=expected['source'],
            parent_launch=expected['parent_launch'], mapping=self.host.mapping, meter=self.meter)
        need(current == expected and current != self.running.identity and
             current['source'] == self.plan.body['observer_source'], 'same actual distinct original O process')
        self.memberships.append({'monotonic_ns': time.monotonic_ns(), 'path': str(actual), 'identity': current})

    def observe_once(self):
        self.plan.require_original();self._membership()
        row = {'whole': None, 'whole_pids': None, 'volume': None, 'observed_ns': None}
        self.samples.append(row);first = None
        for key, call in (('whole', self.host.whole_group.sample),
                          ('whole_pids', lambda: _group_pids(self.host.whole_group, self.meter, self)),
                          ('volume', self.volume.sample), ('observed_ns', time.monotonic_ns)):
            try:row[key] = call()
            except BaseException as error:
                if first is None:first = error
                self.retain(error, 'outer_observation:' + key)
        if first is not None:raise self.raw_first
        h = self.plan.resource_plan['hard_envelope']
        need(row['whole']['cpu_ns'] <= h['cpu_ns'] and row['whole']['memory_peak'] <= h['memory_bytes'] and
             row['whole_pids'] <= h['pids'] and row['volume']['retained_delta_bytes'] <= h['retained_storage_bytes'] and
             row['observed_ns'] <= self.plan.evidence_deadline_ns,
             'actual enclosing O/H/C/W physical observations inside unchanged original limits')
        return row

    def _capture_terminal(self):
        need(self.admitted is True, 'genuine original H publisher custody before any terminal body read')
        r = self.observation
        need(type(r) is OriginalProcessObservation and r.identity == self.running.identity and
             r.record['group_empty'] is True and r.record['group_removed'] is True,
             'original H and every descendant closed before terminal capture')
        raw, descriptor = self.terminal_store.capture_created('hm_whole_HOST_TERMINAL.json', CAP, metadata=True)
        self.terminal_pin = descriptor;self.terminal = parse(raw, CAP)
        t = self.terminal
        closed(t, ('schema', 'profile', 'resource_plan', 'host', 'controller', 'reference_jobs',
            'conditions', 'qualification_holds', 'stage_returns', 'stage_attempts', 'stage_eligible',
            'worker_launch_attempts', 'descendant_creations', 'final_C_request', 'final_C_request_message',
            'final_C_body', 'final_H_response', 'final_H_response_message', 'native_prefix', 'final_native_tail',
            'controller_observation', 'controller_receipt', 'controller_exit_cpu', 'volume_provisioning',
            'volume_identity', 'native_handles_closed', 'channel_closed', 'source_session_closed',
            'full_original_reservations', 'original_H_share_prefix', 'original_failure', 'secondary_failures',
            'H_exit_observed_here', 'outer_whole_reconciliation_required', 'scientific_qualification'))
        for key in ('reference_jobs', 'conditions', 'qualification_holds'):integer(t[key], 1)
        need(encode(t) == raw and t['schema'] == 'hm_whole_original_H_terminal_v1' and
             t['profile'] == self.plan.pin and t['resource_plan'] == self.plan.resource_plan_pin and
             t['host'] == r.identity and t['volume_provisioning'] == self.plan.body['storage'] and
             t['reference_jobs'] == 8223 and t['conditions'] == 335 and t['qualification_holds'] == 65,
             'same complete original HM terminal, never representative jobs or foreign H')
        return t

    def _reconcile(self):
        t = self.terminal;r = self.observation
        need(r.success and self.host_exit is not None and self.raw_first is None,
             'actual H natural exit/streams/tree/resources/publication before eligibility')
        h = self.host_exit.record();c = t['controller_exit_cpu']
        for role, value, identity in (('H', h, t['host']), ('C', c, t['controller'])):
            closed(value, ('schema', 'body', 'complete', 'identity', 'cpu_upper_ns',
                'cpu_upper_exclusive_ns', 'reaped', 'actual_reap_code', 'pidfd_closed',
                'poll_attempts', 'scientific_qualification'))
            body = value['body']
            closed(body, ('schema', 'role', 'identity', 'waitid', 'stat', 'clock_ticks',
                'utime_ticks', 'stime_ticks', 'cpu_lower_ns', 'cpu_upper_exclusive_ns',
                'observation_monotonic_ns', 'scope', 'kernel_and_clock_qualification_still_required'))
            closed(body['waitid'], ('si_pid', 'si_code', 'si_status'))
            for key in ('clock_ticks', 'cpu_upper_exclusive_ns', 'observation_monotonic_ns'):integer(body[key], 1)
            for key in ('utime_ticks', 'stime_ticks', 'cpu_lower_ns'):integer(body[key])
            integer(value['cpu_upper_ns'], 1);integer(value['cpu_upper_exclusive_ns'], 1)
            integer(value['poll_attempts'], 1)
            hz = body['clock_ticks'];need(1000000000 % hz == 0, 'selected exact integer clock-tick domain')
            tick = 1000000000 // hz
            need(value['schema'] == 'hm_owned_exit_accounting_record_v1' and
                 body['schema'] == 'hm_owned_process_exit_cpu_v1' and body['role'] == role and
                 value['complete'] is True and value['reaped'] is True and value['pidfd_closed'] is True and
                 type(value['actual_reap_code']) is int and value['actual_reap_code'] == 0 and
                 value['identity'] == body['identity'] == identity and
                 type(body['waitid']['si_pid']) is int and body['waitid']['si_pid'] == identity['pid'] and
                 type(body['waitid']['si_status']) is int and body['waitid']['si_status'] == 0 and
                 type(body['waitid']['si_code']) is int and body['waitid']['si_code'] == os.CLD_EXITED and
                 body['cpu_lower_ns'] == (body['utime_ticks'] + body['stime_ticks']) * tick and
                 value['cpu_upper_ns'] == value['cpu_upper_exclusive_ns'] == body['cpu_upper_exclusive_ns'] ==
                    body['cpu_lower_ns'] + 2 * tick and
                 value['scientific_qualification'] is False and body['kernel_and_clock_qualification_still_required'] is True,
                 'complete actual exit identity, own CPU interval, reap and pidfd closure')
        need(h['cpu_upper_ns'] + c['cpu_upper_ns'] <= self.plan.body['overhead']['cpu_ns'],
             'complete H/C CPU upper bounds within original shared overhead; no worker sums')
        need(self.plan.origin_ns <= c['body']['observation_monotonic_ns'] <=
             h['body']['observation_monotonic_ns'] <= self.observation.record['closed_ns'] <=
             self.plan.evidence_deadline_ns, 'actual C then H exit capture before original whole cutoff')
        co = t['controller_observation']
        need(co['identity'] == t['controller'] and co['natural_exit'] is True and
             type(co['exit_code']) is int and co['exit_code'] == 0 and
             co['group_empty'] is True and co['group_removed'] is True and co['physical_final_known'] is True and
             co['publication_complete'] is True and co['streams_eof'] == {'stdout': True, 'stderr': True} and
             co['original_failure'] is None and co['cleanup_errors'] == [] and co['unknown_dimensions'] == [] and
             co['forced'] is False and co['timed_out'] is False,
             'complete actual original C observation, not a final notice or live-clock prefix')
        need(t['native_handles_closed'] is True and t['channel_closed'] is True and t['source_session_closed'] is True and
             t['original_failure'] is None and t['secondary_failures'] == [] and
             type(t['stage_attempts']) is int and t['stage_attempts'] == 3 and
             t['stage_eligible'] == [1, 2, 3] and all(type(s) is int for s in t['stage_eligible']) and
             type(t['worker_launch_attempts']) is int and t['worker_launch_attempts'] == 3 and t['descendant_creations'] is None,
             'all original stages/closures/attempts retained, unknown descendant creations remain unknown')
        b = t['final_C_body']
        closed(b, ('schema', 'profile', 'report', 'stage_returns', 'original_budget',
                   'later_original_whole_reconciliation_required'))
        budget = b['original_budget']
        closed(budget, ('schema', 'original', 'profile', 'sequence', 'pending_sequence', 'active',
            'whole_physical_cost_requires_H_observation', 'whole_physical_cost_known_here',
            'full_reserved_capacity_retained', 'terminal_hold'))
        original = budget['original'];hold = budget['terminal_hold']
        closed(original, ('limits', 'reserved', 'deadline_ns', 'terminal_failed', 'physical_IO_RSS_metered'))
        closed(hold, ('reserved', 'used', 'admitted', 'already_charged_to_original_C_budget', 'new_allowance'))
        need(budget['schema'] == 'hm_whole_controller_logical_prefix_v1' and budget['profile'] == self.plan.pin and
             type(budget['sequence']) is int and budget['sequence'] == 3 and budget['pending_sequence'] is None and
             budget['active'] is True and budget['whole_physical_cost_requires_H_observation'] is True and
             budget['whole_physical_cost_known_here'] is False and budget['full_reserved_capacity_retained'] is True and
             original['limits'] == self.plan.body['controller'] and original['reserved'] == original['limits'] and
             original['deadline_ns'] == self.plan.run_deadline_ns and original['terminal_failed'] is False and
             original['physical_IO_RSS_metered'] is False and hold['admitted'] is True and
             hold['already_charged_to_original_C_budget'] is True and hold['new_allowance'] is False,
             'complete original C logical reservation and terminal hold without invented physical evidence')
        for key in ('read_bytes', 'write_bytes', 'work'):
            integer(original['reserved'][key], 1);integer(hold['reserved'][key]);integer(hold['used'][key])
            need(hold['used'][key] <= hold['reserved'][key] <= original['limits'][key],
                 'actual terminal usage inside already debited original C capacity')
        descriptor(b['report']);need(type(t['stage_returns']) is list and len(t['stage_returns']) == 3,
                                    'all three literal original return descriptors')
        for d in t['stage_returns']:descriptor(d)
        need(len({encode(d) for d in t['stage_returns']}) == 3, 'three distinct original returns')
        request = t['final_C_request_message'];response = t['final_H_response_message']
        closed(request, ('schema', 'campaign', 'launch', 'sequence', 'operation', 'body'))
        closed(response, ('schema', 'campaign', 'source', 'sequence', 'request', 'status', 'result'))
        result = response['result']
        closed(result, ('schema', 'prefix', 'later_original_whole_reconciliation_required', 'scientific_qualification'))
        descriptor(t['native_prefix'])
        need(request['schema'] == 'four_programme_host_request_v1' and request['operation'] == 'final_report' and
             request['body'] == b and request['campaign'] == response['campaign'] == self.plan.body['campaign_id'] and
             request['launch'] == t['controller']['parent_launch'] and
             type(request['sequence']) is int and request['sequence'] == response['sequence'] == 5 and
             pin(encode(request)) == t['final_C_request'] == response['request'] and
             response['schema'] == 'four_programme_host_response_v1' and response['status'] == 'observed' and
             response['source'] == self.plan.body['observer_source'] and
             pin(encode(response)) == t['final_H_response'] and
             result['schema'] == 'hm_whole_final_prefix_response_v1' and result['prefix'] == t['native_prefix'] and
             result['later_original_whole_reconciliation_required'] is True and result['scientific_qualification'] is False,
             'exact actual final request/response bytes, sequence, launch, source and prefix')
        need(b['schema'] == 'hm_whole_original_C_final_request_v1' and b['profile'] == self.plan.pin and
             b['stage_returns'] == t['stage_returns'] and len(t['stage_returns']) == 3 and
             t['final_H_response'] is not None and t['native_prefix'] is not None and
             t['H_exit_observed_here'] is False and t['outer_whole_reconciliation_required'] is True,
             'same full stage chain and finite prefix-to-actual-outer completion handoff')
        reservations = t['full_original_reservations']
        closed(reservations, ('schema', 'profile', 'process_start_accounting', 'resource_plan',
            'programme_delegation', 'stages', 'all_future_stage_limits_locked',
            'unused_capacity_transferred', 'new_allowance', 'qualified_here'))
        need(reservations['schema'] == 'hm_whole_job_retained_reservations_v1' and
             reservations['profile'] == self.plan.pin and reservations['resource_plan'] == self.plan.resource_plan_pin and
             reservations['process_start_accounting'] == self.plan.process_start_accounting and
             reservations['all_future_stage_limits_locked'] is True and reservations['unused_capacity_transferred'] is False and
             reservations['new_allowance'] is False and reservations['qualified_here'] is False,
             'same nonrefundable whole reservation and explicit outer-launch accounting')
        delegation = reservations['programme_delegation']
        closed(delegation, ('schema', 'resource_plan', 'programme', 'budget',
                           'full_reservation_retained_on_failure', 'new_allowance'))
        need(delegation == {'schema': 'four_original_programme_delegation_v1',
             'resource_plan': self.plan.resource_plan_pin, 'programme': PROGRAMME,
             'budget': self.plan.resource_plan['programme_budget'], 'full_reservation_retained_on_failure': True,
             'new_allowance': False} and delegation['full_reservation_retained_on_failure'] is True and
             delegation['new_allowance'] is False, 'unchanged complete original programme delegation')
        need(type(reservations['stages']) is list and len(reservations['stages']) == 3,
             'all three original nonrefundable reservations retained')
        for sequence, row in enumerate(reservations['stages'], 1):
            closed(row, ('sequence', 'stage', 'state', 'begin_ns', 'deadline_ns', 'complete', 'full_original_reservation_retained'))
            integer(row['sequence'], 1);integer(row['begin_ns'], 1);integer(row['deadline_ns'], 1)
            selected = self.plan.stage(sequence)
            need(row['sequence'] == sequence and row['stage'] == selected['stage'] and row['state'] == 'complete' and
                 row['complete'] is True and row['full_original_reservation_retained'] is True and
                 self.plan.origin_ns <= row['begin_ns'] and
                 row['deadline_ns'] == row['begin_ns'] + selected['physical']['wall_ns'] and
                 row['deadline_ns'] <= self.plan.run_deadline_ns,
                 'same complete original stage lifetime, capacity and nonrefundable disposition')
        share = t['original_H_share_prefix']
        selected = [row for row in self.plan.resource_plan['adapter_reservations']
                    if row['reservation_id'] == self.plan.body['host_reservation_id']]
        need(len(selected) == 1 and share['reservation_id'] == selected[0]['reservation_id'] and
             share['limits'] == {k: selected[0][k] for k in ('read_bytes', 'write_bytes', 'work_units', 'retained_bytes')} and
             share['origin_ns'] == self.plan.origin_ns and share['deadline_ns'] == self.plan.evidence_deadline_ns and
             share['first_error'] is None and share['cleanup_errors'] == [] and share['unknown_dimensions'] == [],
             'same earlier H Share without replenishment or erased original failures')
        for key, limit in share['limits'].items():
            integer(share['spent'][key]);need(share['spent'][key] <= limit, 'actual H logical prefix within original hold')
        return {'H_own_cpu': h, 'C_own_cpu': c, 'O_original_share': self.meter.record(),
                'independent_whole_prefix': self.final_sample,
                'overlapping_counters_added_to_whole': False,
                'O_inside_whole_outside_H': True, 'O_exit_observed_here': False,
                'all65qualification_holds_retained': True, 'scientific_qualification': False}

    def finish_once(self):
        need(not self.entered and _LIVE.get(id(self)) is self and
             self.resources._hm_whole_outer_v1 is self, 'one original retained outer completion')
        self.entered = True
        try:
            if self.raw_first is not None:raise self.raw_first
            while True:
                self.observe_once()
                if not self.host.pump(self.running, poll_interval_ns=self.plan.body['polling']['interval_ns']):break
            if self.running.primary is not None:self.retain(self.running.primary, 'actual_H_pump')
        except BaseException as error:self.retain(error, 'outer_observe_H')
        finally:
            if self.raw_first is not None and self.running.primary is None:
                try:self.running.own_failure(self.raw_first, 'actual_outer_prior_failure')
                except BaseException as error:self.retain(error, 'original_H_failure_retention')
            self.finish_attempted = True
            try:self.observation = self.host.finish(self.running)
            except BaseException as error:self.retain(error, 'actual_original_H_finish')
        if self.admitted:
            try:self._capture_terminal()
            except BaseException as error:self.retain(error, 'closed_original_H_terminal_capture')
        try:self.final_sample = self.observe_once()
        except BaseException as error:self.retain(error, 'actual_post_capture_whole_prefix')
        reconciliation = None
        try:reconciliation = self._reconcile()
        except BaseException as error:self.retain(error, 'actual_H_C_whole_reconciliation')
        self.report = {'schema': 'hm_whole_outer_reconciliation_v1', 'profile': self.plan.pin,
            'host_observation': None if self.observation is None else self.observation.record,
            'host_terminal': self.terminal_pin, 'reconciliation': reconciliation,
            'original_failure': None if self.raw_first is None else failure(self.raw_first),
            'secondary_failures': [{'site': site, 'error': failure(error)} for site, error in self.secondaries],
            'O_exit_observed_here': False, 'publication_and_return_tail_not_in_this_prefix': True,
            'scientific_qualification': False, 'submission_ready': False}
        try:self.report_pin = self.host.outputs.publish('hm_whole_OUTER_RECONCILIATION.json', self.report)
        except BaseException as error:self.retain(error, 'outer_reconciliation_publication')
        # Actual return carries costs after publication; the on-disk prefix is
        # never rewritten to claim knowledge of its own later persistence.
        try:self.final_sample = self.observe_once()
        except BaseException as error:self.retain(error, 'actual_post_publication_whole_prefix')
        if self.volume is not None:
            try:self.closed = self.volume.close_once()
            except BaseException as error:self.retain(error, 'actual_outer_volume_close')
        # RootResources.close(H-record) would falsely turn its global
        # unknown_whole_completion flag off while O remains alive. Keep the
        # original whole reservation outstanding and retain this finite prefix.
        self.resources._hm_whole_outer_prefix_v1 = self
        self.span_end_attempted = True
        try:
            need(self.meter._active == self.original_span, 'same earlier O span through publication and native closure')
            self.meter.end()
        except BaseException as error:self.retain(error, 'actual_O_share_close')
        # Include the real closing span work in a later independent whole
        # sample; no closed volume handle is sampled or reopened here.
        try:
            tail = self.host.whole_group.sample();now = time.monotonic_ns()
            hard = self.plan.resource_plan['hard_envelope']
            need(tail['cpu_ns'] <= hard['cpu_ns'] and tail['memory_peak'] <= hard['memory_bytes'] and
                 now <= self.plan.evidence_deadline_ns, 'actual final whole CPU/memory/deadline prefix')
            self.final_whole_after_span = {'whole': tail, 'observed_ns': now}
        except BaseException as error:self.retain(error, 'actual_final_whole_after_span')
        if self.raw_first is not None:
            try:BaseException.__setattr__(self.raw_first, 'hm_original_outer_owner', self)
            except BaseException as error:self.retain(error, 'outer_final_failure_attachment')
            raise self.raw_first
        need(self.closed and self.report_pin is not None, 'actual finite outer publication/volume close')
        return {'descriptor': self.report_pin, 'whole_observed_after_publication': self.final_sample,
                'whole_observed_after_O_span_close': self.final_whole_after_span,
                'actual_O_share': self.meter.record(), 'original_H_observation': self.observation,
                'H_C_completion_observed': True, 'O_exit_observed': False,
                'whole_sampling_and_return_tail_remain_prefix': True, 'scientific_qualification': False}


def open_original_hm_whole_outer_v1(**kwargs):
    return HMWholeOuterCoordinatorV1(_TOKEN, **kwargs)
