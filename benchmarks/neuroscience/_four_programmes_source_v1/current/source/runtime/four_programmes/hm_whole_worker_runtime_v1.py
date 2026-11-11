"""Actual no-argument inherited bootstrap and full scientific HM W caller.

This source has no BUILD execution path. Native isolation, accepted source,
clock and Context dependencies remain independently selected prerequisites.
"""
import fcntl
import os
import stat
import sys
import time
from .common import need, closed, integer, encode, parse, pin, descriptor, failure, bounded_size, Meter, Store
from .channel import RootChannel
from .roots import BoundRoots
from .source_session import SourceSession
from .identity import process_identity
from .hm_whole_job_profile_v1 import compile_original_hm_whole_job_plan_v1
from .hm_whole_worker_contract_v1 import (HM, FD_ENVIRONMENT, BOOTSTRAP_FORMAT_MAXIMUM,
    BODY_FIELDS, validate_worker_bootstrap_body_v1, validate_start_response, wrapped)

_WORKER = object()
_CURRENT = None


class HMWholeWorkerAdapterMeterV1(Meter):
    """Local accounting of an H-prepaid fixed adapter hold; never a new grant."""
    def __init__(self, runtime, limits, *, phase, origin_ns, deadline_ns):
        super().__init__(limits, origin_ns=origin_ns, deadline_ns=deadline_ns,
                         owner='HM-W-' + phase, reservation_id=runtime.lease['workspace_nonce'] + ':' + phase)
        self.runtime = runtime;self.phase = phase;self.raw_errors = []

    def own_error(self, error, dimension=None):
        self.raw_errors.append((error, dimension))
        super().own_error(error, dimension)

    def record(self):
        return {**super().record(), 'H_prepaid_nonrefundable_hold': True,
                'new_allowance': False, 'overlapping_whole_measurement_not_added': True}


class HMWholeWorkerRuntimeV1:
    def __init__(self, token):
        need(token is _WORKER, 'fixed no-argument HM worker entry only')
        self.raw_first = None;self.secondaries = [];self.phase = 'registered'
        self.carrier_fd = None;self.pipe_fds = {};self.carrier_raw = None;self.carrier_pin = None
        self.bootstrap = None;self.lease = None;self.plan = None;self.configuration = None
        self.bootstrap_meter = None;self.terminal_meter = None;self.channel = None
        self.roots = None;self.terminal_store = None;self.start_event = None;self.start = None
        self.worker = None;self.environment = None;self.environment_attempted = False
        self.session = None;self.scientific_budget = None;self.result = None;self.terminal = None
        self.terminal_event = None;self.run_entered = False;self.close_entered = False;self.closed = False
        self.source_close_entered = False;self.terminal_attempted = False
        self.source_closed_known = False;self.channel_closed_known = False;self.untransferred_close_known = True
        self.carrier_close_entered = False;self.carrier_closed = False
        self.bootstrap_requested_bytes = 0;self.bootstrap_read_entries = 0

    def retain(self, error, site):
        if self.raw_first is None:
            self.raw_first = error
        elif error is not self.raw_first:
            self.secondaries.append((site, error))

    def require_current(self):
        need(_CURRENT is self and not self.close_entered and self.bootstrap is not None,
             'same actual registered inherited HM worker')
        if self.raw_first is not None:
            raise self.raw_first
        self.plan.require_original()
        return self

    def close_carrier_once(self):
        if self.carrier_close_entered:
            return self.carrier_closed
        self.carrier_close_entered = True
        fd, self.carrier_fd = self.carrier_fd, None
        if fd is None:
            return False
        try:
            os.close(fd);self.carrier_closed = True
        except BaseException as error:
            self.retain(error, 'carrier_close')
        return self.carrier_closed

    def close_source_once(self):
        if self.source_close_entered:
            return
        self.source_close_entered = True
        if self.session is not None and not self.session.closed:
            try:
                self.session.close()
                need(self.session.closed and not self.session.modules, 'complete original source namespace release')
                self.source_closed_known = True
            except BaseException as error:
                self.retain(error, 'original_source_close')

    def close_once(self):
        if self.close_entered:
            return self.closed
        self.close_entered = True
        self.close_source_once()
        if self.carrier_fd is not None:
            self.close_carrier_once()
        if self.channel is not None:
            try:
                self.channel.close()
                self.channel_closed_known = True
            except BaseException as error:
                self.retain(error, 'original_channel_close')
        for name in tuple(self.pipe_fds):
            fd = self.pipe_fds.pop(name)
            if fd is None:
                continue
            try:
                os.close(fd)
            except BaseException as error:
                self.untransferred_close_known = False
                self.retain(error, 'untransferred_pipe_close:' + name)
        self.closed = (self.carrier_closed and (self.channel is None or self.channel_closed_known) and
                       self.untransferred_close_known and not self.pipe_fds and
                       (self.session is None or self.source_closed_known))
        self.phase = 'closed' if self.closed else 'closure_unknown'
        return self.closed

    def _source_and_call(self):
        from .hm_whole_source_environment_v1 import create_original_hm_source_environment_v1
        self.require_current();config = self.configuration
        cap = config['metadata_cap'];request = self.bootstrap['request']['body']
        subject = self.bootstrap['subject']['body'];row = self.plan.stage(self.lease['sequence'])
        environment_body = self.roots.document(config['environment_record'], cap)
        environment = create_original_hm_source_environment_v1(self, environment_body, config['environment_record'])
        catalog = self.roots.document(config['catalog'], cap)
        need(catalog['programmes'][HM]['source_manifest'] == self.plan.body['source_manifest'],
             'entire original scientific source catalogue matches the selected profile')
        source_store = Store(config['ordinary_source_root'], self.bootstrap_meter)
        # The original concrete SourceSession performs its genuine Context
        # admission before source loading. No local substitute engine is used.
        self.session = SourceSession(HM, catalog=catalog, ordinary_store=source_store,
            extension_sources=config['extension_sources'], root=config['ordinary_source_root'],
            selected_context=config['selected_context'], selected_templates=config['selected_templates'],
            environment=environment)
        self.require_current()
        scientific = {key: self.roots.document(request[key], cap)
                      for key in ('scope', 'inputs', 'full_plan', 'original_authority')}
        scientific['submission'] = None if request['submission'] is None else self.roots.document(request['submission'], cap)
        codec = self.session.module('guard').encoded
        for key in ('scope', 'inputs', 'full_plan', 'submission'):
            actual = None if scientific[key] is None else pin(codec(scientific[key]))
            need(actual == subject[key], 'complete actual original scientific identity ' + key)
        full_plan = scientific['full_plan']
        need(type(full_plan) is dict and type(full_plan.get('jobs')) is list and len(full_plan['jobs']) == 8223 and
             len({j['id'] for j in full_plan['jobs']}) == 8223, 'all 8223 original reference jobs; no subset')
        Budget = self.session.module('guard').Budget
        self.scientific_budget = Budget(**row['logical'], deadline_ns=self.lease['deadline_ns'])
        budget = self.scientific_budget;budget.check()
        budget.charge('work', bounded_size(scientific['scope']) + bounded_size(scientific['inputs']) + bounded_size(full_plan))
        compiled = self.session.module('scope').compile_jobs(scientific['scope'], scientific['inputs'])
        need(codec(compiled) == codec(full_plan), 'entire original compiler agrees with complete immutable plan')
        authority = scientific['original_authority'];submission = scientific['submission']
        need(authority['plan'] == subject['full_plan'], 'same original complete authority plan')
        self.phase = 'original_scientific_API'
        if row['stage'] == 'reference':
            need(submission is None and authority['source'] ==
                 {k: self.plan.body['source_manifest'][k] for k in ('bytes', 'sha256')}, 'full original reference source authority')
            self.result = self.session.api('hm_reference')(request['package'], request['root'],
                scientific['scope'], scientific['inputs'], authority, budget, request['output'],
                {k: self.plan.body['source_manifest'][k] for k in ('bytes', 'sha256')})
        else:
            need(submission is not None and submission['arm'] == row['stage'].split(':')[1] and
                 authority['inputs'] == subject['inputs'] and authority['submission'] == subject['submission'],
                 'complete actual own-run A/B authority and fixed arm')
            self.result = self.session.api('hm_candidate')(request['root'], submission, authority, budget, request['output'])
        descriptor(self.result)
        budget.check()
        self.phase = 'original_scientific_API_returned'

    def _publish_terminal_once(self):
        need(not self.terminal_attempted and self.terminal_store is not None,
             'one actual owned terminal publication attempt')
        self.terminal_attempted = True
        prefix = None
        if self.raw_first is not None:
            attrs = BaseException.__getattribute__(self.raw_first, '__dict__')
            if type(attrs) is dict:
                prefix = {k: attrs[k] for k in ('campaign_prefix', 'known_output_prefix') if k in attrs}
                self.terminal_meter.charge('work_units', bounded_size(prefix))
        request = self.bootstrap['request']['body']
        body = {'schema': 'hm_whole_worker_terminal_v1', 'profile': self.plan.pin,
            'lease': self.bootstrap['lease']['descriptor'], 'subject': self.bootstrap['subject']['descriptor'],
            'request': self.bootstrap['request']['descriptor'], 'stage': self.lease['stage'],
            'sequence': self.lease['sequence'], 'worker': self.worker,
            'start': self.start_event.body['result']['start'], 'result': self.result,
            'result_root': request['output'],
            'scientific_budget': None if self.scientific_budget is None else self.scientific_budget.snapshot(),
            'adapter_cost_prefix': {'bootstrap': self.bootstrap_meter.record(),
                                    'terminal': self.terminal_meter.record(), 'prefix_only': True},
            'original_failure': None if self.raw_first is None else failure(self.raw_first),
            'cleanup_errors': [{'site': site, 'error': failure(error)} for site, error in self.secondaries],
            'known_original_prefix': prefix,
            'source_session_closed': self.source_closed_known,
            'H_original_exit_still_required': True, 'scientific_qualification': False}
        self.terminal = self.terminal_store.publish(request['terminal_name'], body)
        self.channel.meter = self.terminal_meter
        event = self.channel.exchange('stage', {'schema': 'hm_whole_worker_terminal_request_v1',
            'profile': self.plan.pin, 'lease': self.bootstrap['lease']['descriptor'],
            'stage': self.lease['stage'], 'worker': self.worker, 'terminal': self.terminal})
        self.terminal_event = event
        need(self.channel.owns_completed_event(event) and event.body['status'] == 'observed',
             'actual original H terminal publication acknowledgement')
        response = event.body['result']
        closed(response, ('schema', 'terminal', 'received_ns'))
        need(response['schema'] == 'hm_whole_worker_terminal_response_v1' and
             response['terminal'] == self.terminal, 'same actual complete terminal metadata')
        integer(response['received_ns'], 1)
        need(self.start['observed_ns'] <= response['received_ns'] <= self.lease['evidence_deadline_ns'],
             'actual terminal acknowledgement within original stage lifetime')

    def run_once(self):
        need(_CURRENT is self and not self.run_entered and not self.close_entered, 'one original complete scientific attempt')
        self.run_entered = True
        try:
            self._source_and_call()
        except BaseException as error:
            self.retain(error, 'source_or_original_scientific_API')
        self.close_source_once()
        try:
            self._publish_terminal_once()
        except BaseException as error:
            self.retain(error, 'actual_terminal_publication_or_acknowledgement')
        self.close_once()
        if self.raw_first is not None:
            try:
                BaseException.__setattr__(self.raw_first, 'four_HM_whole_worker',
                    {'runtime': self, 'terminal': self.terminal, 'result': self.result,
                     'full_nonrefundable_reservation_retained': True})
            except BaseException as later:
                self.secondaries.append(('failure_attachment', later))
            raise self.raw_first
        need(self.closed and self.terminal is not None and self.terminal_event is not None,
             'actual local publication, acknowledgement and closure; H outer observation still required')
        return self.terminal


def _capture_inherited_bootstrap(runtime):
    need(sys.platform == 'linux' and sys.flags.isolated == 1, 'fixed isolated Linux HM worker entry')
    values = []
    for name in FD_ENVIRONMENT:
        text = os.environ.get(name)
        need(type(text) is str and text.isascii() and text.isdecimal() and str(int(text)) == text,
             'exact launch-only inherited descriptor spelling')
        values.append(integer(int(text), 3))
    need(len(set(values)) == 3, 'three distinct original bootstrap/channel descriptors')
    carrier, read_fd, write_fd = values
    # Retain all launch-only inherited ends before the first fallible native
    # observation. Even a malformed carrier must close the original pipes.
    runtime.carrier_fd = carrier
    runtime.pipe_fds = {'read': read_fd, 'write': write_fd}
    st = os.fstat(carrier)
    need(stat.S_ISREG(st.st_mode) and 0 < st.st_size <= BOOTSTRAP_FORMAT_MAXIMUM and
         fcntl.fcntl(carrier, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY and
         fcntl.fcntl(carrier, fcntl.F_GET_SEALS) & 15 == 15,
         'actual sealed read-only original memfd within complete bootstrap format bound')
    os.set_inheritable(carrier, False)
    chunks = [];count = 0
    try:
        while count < st.st_size:
            requested = min(65536, st.st_size - count)
            runtime.bootstrap_requested_bytes += requested;runtime.bootstrap_read_entries += 1
            chunk = os.pread(carrier, requested, count)
            need(type(chunk) is bytes and chunk, 'actual original bootstrap read progress')
            chunks.append(chunk);count += len(chunk)
        runtime.bootstrap_requested_bytes += 1;runtime.bootstrap_read_entries += 1
        need(os.pread(carrier, 1, st.st_size) == b'', 'exact original sealed bootstrap EOF')
        after = os.fstat(carrier)
        need((st.st_dev, st.st_ino, st.st_mode, st.st_size) ==
             (after.st_dev, after.st_ino, after.st_mode, after.st_size), 'same actual original bootstrap object')
        runtime.carrier_raw = b''.join(chunks);runtime.carrier_pin = pin(runtime.carrier_raw)
    except BaseException as error:
        runtime.retain(error, 'original_bootstrap_read')
    finally:
        runtime.close_carrier_once()
    if runtime.raw_first is not None:
        raise runtime.raw_first
    body = parse(runtime.carrier_raw, BOOTSTRAP_FORMAT_MAXIMUM)
    closed(body, BODY_FIELDS)
    need(body['schema'] == 'hm_whole_worker_bootstrap_v1' and encode(body) == runtime.carrier_raw,
         'complete canonical distinct whole-job bootstrap')
    resource = wrapped(body['resource_plan'])
    plan = compile_original_hm_whole_job_plan_v1(body['profile_body'], resource_plan=resource,
                                               resource_plan_pin=body['resource_plan']['descriptor'])
    need(body['profile_pin'] == plan.pin, 'same actual full profile content')
    expected = validate_worker_bootstrap_body_v1(plan, body)
    need(encode(expected) == runtime.carrier_raw, 'entire source-compiled bootstrap, no unselected fields')
    runtime.bootstrap = body;runtime.plan = plan;runtime.lease = body['lease']['body']
    config = body['worker_configuration']
    runtime.configuration = config
    runtime.bootstrap_meter = HMWholeWorkerAdapterMeterV1(runtime, config['bootstrap_limits'], phase='bootstrap',
        origin_ns=runtime.lease['stage_started_ns'], deadline_ns=runtime.lease['deadline_ns'])
    runtime.terminal_meter = HMWholeWorkerAdapterMeterV1(runtime, config['terminal_limits'], phase='terminal',
        origin_ns=runtime.lease['stage_started_ns'], deadline_ns=runtime.lease['evidence_deadline_ns'])
    # H prepaid this complete read before carrier/native effects. This local
    # ledger records that same consumption; no new programme allowance appears.
    runtime.bootstrap_meter.charge('read_bytes', runtime.bootstrap_requested_bytes)
    runtime.bootstrap_meter.charge('retained_bytes', len(runtime.carrier_raw))
    runtime.bootstrap_meter.charge('work_units', len(runtime.carrier_raw) * 64 + 4096)
    for name, fd in (('read', read_fd), ('write', write_fd)):
        observed = os.fstat(fd)
        expected_access = os.O_RDONLY if name == 'read' else os.O_WRONLY
        need(stat.S_ISFIFO(observed.st_mode) and [observed.st_dev, observed.st_ino, observed.st_mode] ==
             body['pipe_identities'][name] and
             fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == expected_access,
             'actual original private inherited pipe object and direction')
        os.set_inheritable(fd, False)
    runtime.channel = RootChannel(read_fd, write_fd, binding=body['launch_binding'],
        selected_qualification=config['selected_channel_qualification'], meter=runtime.bootstrap_meter)
    runtime.pipe_fds.clear()  # Only after the actual channel constructor returned.
    runtime.roots = BoundRoots(config['roots'], relative_base=config['relative_base'], meter=runtime.bootstrap_meter)
    runtime.terminal_store = Store(config['terminal_root'], runtime.terminal_meter)
    runtime.worker = process_identity(os.getpid(), launch_nonce=runtime.lease['worker_nonce'],
        source=plan.body['worker_source'], parent_launch=body['lease']['descriptor'],
        mapping=config['clock_mapping'], meter=runtime.bootstrap_meter)
    need(os.getppid() == runtime.lease['host']['pid'], 'actual direct original H parent of this W')
    event = runtime.channel.exchange('stage', {'schema': 'hm_whole_worker_start_request_v1',
        'profile': plan.pin, 'lease': body['lease']['descriptor'], 'subject': body['subject']['descriptor'],
        'bootstrap': runtime.carrier_pin, 'worker': runtime.worker, 'stage': runtime.lease['stage']})
    runtime.start_event = event
    runtime.start = validate_start_response(plan, body, runtime.carrier_pin, event, runtime.channel, runtime.worker)
    runtime.require_current();runtime.phase = 'actual_start_admitted'
    return runtime


def open_fixed_hm_worker_runtime_v1():
    global _CURRENT
    need(_CURRENT is None, 'one fixed original HM bootstrap attempt, including failures')
    runtime = HMWholeWorkerRuntimeV1(_WORKER);_CURRENT = runtime
    try:
        return _capture_inherited_bootstrap(runtime)
    except BaseException as error:
        runtime.retain(error, 'fixed_original_worker_bootstrap')
        runtime.close_once()
        raise runtime.raw_first


def run_fixed_hm_whole_worker_v1():
    runtime = open_fixed_hm_worker_runtime_v1()
    return runtime.run_once()
