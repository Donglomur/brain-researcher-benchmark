"""Concrete single-context owned Ollama container; no ambient service or retry."""
import failures
import copy, math, time, uuid
from pathlib import Path
from .io import capture, publish, parse, encoded, pin, need, Clock, failure
from .provider_worker import validate_profile
from .vendor.bounds import Meter, tree, mount_identity, fsync_dir
from .vendor.engine import Docker, call, inspect, resource_inventory, retire, validate_natural_exit, validate_cli_records
from .vendor.provider import caps, create_args, admit_container

class Session:

    def __init__(self, configuration, root, context, clock, source_mounts, profile_mount, models_mount):
        self.c = copy.deepcopy(configuration)
        self.root = Path(root)
        self.context = context
        self.clock = Clock(clock['origin'], clock['deadline'])
        c = self.c
        need(c['schema'] == 'neural066_model_transport_configuration_v1', 'Qualified provider configuration')
        self.clock.tick()
        self.meter = Meter(c['read_bytes'], c['write_bytes'], clock['deadline'])
        self.profile = validate_profile(parse(capture(profile_mount['path'], next(iter(profile_mount['files'].values())), meter=self.meter)))
        need(type(context) is str and context and self.root.is_absolute() and (not self.root.exists()) and (not any((p.is_symlink() for p in self.root.parents))), 'One fresh ordinary context')
        for k in ('read_bytes', 'write_bytes', 'cli_bytes', 'max_cli_calls', 'ready_bytes', 'return_bytes', 'close_bytes', 'setup_seconds', 'finish_seconds'):
            need(type(c[k]) is int and c[k] > 0, 'Complete prospective provider cap ' + k)
        need(c['return_bytes'] >= self.profile['wire_bytes'] + self.profile['max_action_bytes'] + 65536 and c['ready_bytes'] >= self.profile['wire_bytes'] + 65536 and (c['close_bytes'] >= self.profile['wire_bytes'] + 2 * self.profile['service_log_bytes'] + 65536), 'Complete worst-case provider evidence reserve, never prefix-only capture')
        need(c['resources']['max_file_bytes'] >= max(c['return_bytes'], c['ready_bytes'], c['close_bytes']), 'Container complete metadata file allowance')
        need(self.clock.left() > c['setup_seconds'] + c['finish_seconds'] + self.profile['setup_seconds'] + self.profile['close_seconds'], 'Full service start/retire interval')
        self.root.mkdir(mode=448)
        fsync_dir(self.root.parent)
        self.requests = self.root / 'requests'
        self.requests.mkdir(mode=493)
        fsync_dir(self.root)
        self.sequence = 0
        self.turns = 0
        self.tokens = 0
        self.closed = False
        self.started = False
        self.failed = False
        self.before = None
        self.evidence = []
        self.item = {'kind': 'container', 'name': 'neural066-' + uuid.uuid4().hex, 'owner': 'neural066/' + uuid.uuid4().hex, 'attempted': False, 'acknowledged': False}
        phase_caps = caps(65536)
        phase_caps.update(model_create=4096, model_start=4096, model_admit=131072, model_image=131072, model_ready=c['ready_bytes'], model_turn=c['return_bytes'], model_close=c['close_bytes'], model_wait=4096, model_exit=131072, model_failed=c['close_bytes'])
        self.d = Docker(c['docker_binary'], c['docker_socket'], max_calls=c['max_cli_calls'], reply_budget=c['cli_bytes'], phase_caps=phase_caps, publish=self.record, account_read=self.meter.read, reserve_read=self.meter.ensure_read)
        self.mounts = {**copy.deepcopy(source_mounts), '/profile.json': copy.deepcopy(profile_mount), '/models': copy.deepcopy(models_mount)}
        need(all((k.startswith('/program/') for k in source_mounts)) and set(source_mounts) == set(c['provider_source_mounts']), 'Exact provider-only source closure')
        need(mount_identity(source_mounts) == c['provider_source_mounts'], 'Complete independently bound provider source inventory')
        self.request = {'image': c['image'], 'command': c['command'], 'resources': c['resources']}
        need(c['command'][0] == c['python'] and c['command'][1:] == ['-I', '-B', '/program/provider_entry.py'], 'Exact qualified provider Python/entry')
        self.admission = parse(capture(c['admission_path'], c['admission_pin'], meter=self.meter))
        need(self.admission['context'] == context and self.admission['image'] == c['image'] and (self.admission['source'] == c['source']) and (self.admission['immutable_mounts'] == mount_identity(self.mounts)) and (self.admission['mailbox_policy'] == 'fresh_readonly_append_only_current_context'), 'Exact independent current-context provider/image/source/model admission')

    def record(self, kind, value):
        self.clock.tick()
        self.sequence += 1
        raw = encoded({'index': self.sequence, 'kind': kind, 'value': value})
        publish(self.root / f'event-{self.sequence:06d}.json', raw, self.meter)
        self.evidence.append({'event': kind, 'file': str(self.root / f'event-{self.sequence:06d}.json'), 'pin': pin(raw)})
        self.clock.tick()

    def _fail(self, where, exc, raw=None):
        self.failed = True
        if raw is not None:
            try:
                publish(self.root / f'unadmitted-{self.sequence + 1:06d}.json', raw, self.meter)
            except BaseException as secondary:
                failures.hold(secondary, 'caught')
                failures.note(exc, 'Unadmitted response publication failed: ' + failures.kind(secondary))
        try:
            self.record('FAILED', {'where': where, 'error': failure(exc), 'custody': 'unknown', 'raw_pin': None if raw is None else pin(raw)})
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            failures.note(exc, 'Failure ledger publication failed: ' + failures.kind(secondary))

    def _read(self, path, end, phase):
        duration = end - self.clock.tick()
        need(duration > 0, 'Original host capture cutoff')
        code = 'import os,sys,time;from pathlib import Path;p=Path(sys.argv[1]);end=time.monotonic()+float(sys.argv[2]);cap=int(sys.argv[3]);failed=Path("/work/FAILED.json");\nwhile not p.exists():\n if failed.exists():p=failed;break\n if time.monotonic()>=end: raise TimeoutError("Guest elapsed wait")\n time.sleep(.01)\ns=p.stat();assert s.st_size<=cap;raw=p.read_bytes();assert len(raw)==s.st_size;sys.stdout.buffer.write(raw)'
        return self.d(['container', 'exec', self.item['id'], self.c['python'], '-I', '-S', '-B', '-c', code, path, str(duration), str(self.d.phase_caps[phase])], end, phase, self.d.phase_caps[phase])

    def start(self):
        need(not self.started and (not self.closed) and (not self.failed), 'One provider lifecycle')
        end = min(self.clock.deadline - self.c['finish_seconds'], self.clock.tick() + self.c['setup_seconds'])
        raw = None
        try:
            life = {'context': self.context, 'duration_seconds': self.clock.deadline - self.clock.tick() - self.c['setup_seconds'] - self.c['finish_seconds']}
            lp = publish(self.root / 'LIFECYCLE.json', encoded(life), self.meter)
            self.mounts['/lifecycle.json'] = {'path': str(self.root / 'LIFECYCLE.json'), 'kind': 'file', 'purpose': 'contract', 'files': {'LIFECYCLE.json': lp}}
            self.binding = {target: ('bind', Path(d['path']), False) for target, d in self.mounts.items()}
            self.binding['/requests'] = ('bind', self.requests, False)
            self.before = {target: tree(desc, self.meter) for target, desc in self.mounts.items()}
            need(resource_inventory(self.d, self.item, self.item['owner'], end, 'before_container') == [], 'Fresh owned container namespace')
            image = parse(call(self.d, ['image', 'inspect', self.c['image'], '--format', '{{json .}}'], end, 'model_image'))
            need(image['Id'] == self.c['image'] and (not image['Config'].get('Volumes')) and (not image['Config'].get('Healthcheck')), 'Existing exact offline provider image')
            self.item['attempted'] = True
            self.record('CREATE-ATTEMPT', self.item.copy())
            ident = call(self.d, create_args(self.item, False, self.binding, self.request, []), end, 'model_create', 4096).decode().strip()
            need(len(ident) == 64 and all((x in '0123456789abcdef' for x in ident)), 'Exact acknowledged container ID')
            self.item.update(id=ident, acknowledged=True)
            self.record('ACK', self.item.copy())
            admit_container(inspect(self.d, 'container', ident, end, 'model_admit'), self.item, False, self.binding, self.request, [], image['Config'].get('Env') or [])
            self.clock.tick()
            call(self.d, ['container', 'start', ident], end, 'model_start', 4096)
            self.started = True
            raw = self._read('/work/READY.json', end, 'model_ready')
            ready = parse(raw)
            need(ready['context'] == self.context and ready['guest_duration_limit'] == life['duration_seconds'], 'Ready joins context/local allowance, never host epoch')
            self.record('READY', ready)
            need(self.clock.tick() < end, 'Host setup complete before original cutoff')
            return ready
        except BaseException as exc:
            failures.hold(exc, 'caught')
            self._fail('start', exc, raw)
            raise

    def generate(self, prompt, schema):
        need(self.started and (not self.closed) and (not self.failed) and (self.turns < self.profile['max_turns']), 'Current isolated provider turn')
        self.turns += 1
        end = min(self.clock.deadline - self.c['finish_seconds'], self.clock.tick() + self.profile['turn_seconds'])
        raw = None
        try:
            request = {'context': self.context, 'turn': self.turns, 'prompt': prompt, 'format': schema, 'duration_seconds': end - self.clock.tick(), 'remaining_tokens': self.profile['max_total_tokens'] - self.tokens}
            body = encoded(request)
            name = f'turn-{self.turns}.json'
            publish(self.requests / name, body, self.meter)
            code = 'import sys;sys.path.insert(0,"/program");from transport.provider_worker import turn;from transport.io import capture,parse,encoded;sys.stdout.buffer.write(encoded(turn(parse(capture(sys.argv[1])))))'
            raw = self.d(['container', 'exec', self.item['id'], self.c['python'], '-I', '-B', '-c', code, '/requests/' + name], end, 'model_turn', self.c['return_bytes'])
            rp = publish(self.root / f'response-{self.turns}.json', raw, self.meter)
            value = parse(raw)
            need(value['context'] == self.context and value['turn'] == self.turns and (value['request'] == pin(body)) and (value['guest_duration_limit'] == request['duration_seconds']), 'Exact response/request/local-clock identity')
            need(type(value['guest_elapsed_seconds']) in (int, float) and math.isfinite(value['guest_elapsed_seconds']) and (0 <= value['guest_elapsed_seconds'] < value['guest_duration_limit']), 'Guest elapsed support, not host timestamp')
            need(value['status'] == 'completed' and value['error'] is None, 'Complete untruncated provider turn')
            self.tokens += value['prompt_tokens'] + value['completion_tokens']
            need(self.tokens <= self.profile['max_total_tokens'], 'Whole-context actual token allowance')
            need(self.clock.tick() < end, 'Capture/admission inside original host turn cutoff')
            self.record('TURN', {'request': pin(body), 'response': rp, 'total_tokens': self.tokens, 'deadline': end})
            need(self.clock.tick() < end, 'Final journal inside original host turn cutoff')
            return (value['action'], {'request': pin(body), 'response': rp, 'response_path': str(self.root / f'response-{self.turns}.json'), 'host_deadline': end, 'guest_elapsed_seconds': value['guest_elapsed_seconds']})
        except BaseException as exc:
            failures.hold(exc, 'caught')
            self._fail('turn', exc, raw)
            raise

    def counter_evidence(self, scope):
        """Known host-transport counters never stand in for whole native usage."""
        meter = getattr(self, 'meter', None)
        config = getattr(self, 'c', {})
        return {'counter_scope': scope, 'read_bytes': getattr(meter, 'read_bytes', None), 'write_bytes': getattr(meter, 'write_bytes', None), 'write_reserved_bytes': getattr(meter, 'write_reserved_bytes', None), 'whole_operation_or_guest_usage_complete': False, 'written_counter_coverage': 'Only paths instrumenting meter.wrote; not every publication or physical I/O', 'conservative_context_reservation': {'read_bytes': config.get('read_bytes'), 'write_bytes': config.get('write_bytes'), 'reservation_is_measured_usage': False}}

    def close(self):
        need(self.started and (not self.closed) and (not self.failed), 'One normal context retirement')
        end = self.clock.deadline
        raw = None
        try:
            publish(self.requests / 'CLOSE.json', encoded({'context': self.context}), self.meter)
            raw = self._read('/work/CLOSED.json', end, 'model_close')
            value = parse(raw)
            need(value['context'] == self.context and value['server_reaped'] is True and (value['model_unloaded'] is True), 'Owned service/model retirement')
            import base64
            log = base64.b64decode(value['log_base64'], validate=True)
            need(pin(log) == value['log'] and len(log) <= self.profile['service_log_bytes'], 'Exact complete service log')
            publish(self.root / 'SERVER.log', log, self.meter)
            self.record('CLOSED', value)
            publish(self.requests / 'ACK.json', encoded({'context': self.context}), self.meter)
            wait = self.d(['container', 'wait', self.item['id']], end, 'model_wait', 4096)
            state = inspect(self.d, 'container', self.item['id'], end, 'model_exit')['State']
            natural = {k: state[k] for k in ('Status', 'Running', 'Dead', 'Pid', 'ExitCode', 'OOMKilled')}
            validate_natural_exit(natural)
            need(wait.strip() == b'0', 'Natural trusted provider container exit')
            closure = retire(self.d, self.item, end)
            need(closure['closed'] is True, 'Independent owned container absence')
            after = {k: tree(v, self.meter) for k, v in self.mounts.items()}
            need(after == self.before, 'Unchanged complete model/source/profile inputs')
            validate_cli_records(self.d.records, self.d.phase_caps)
            value = {'schema': 'neural066_provider_close_v1', 'context': self.context, 'turns': self.turns, 'tokens': self.tokens, 'natural_exit': natural, 'closure': closure, 'all_native_resources_closed': True, **self.counter_evidence('before_FINAL_CLOSURE_publication_known_partial'), 'physical_io_and_rss': None, 'original_host_deadline': end, 'finished': self.clock.tick(), 'science_qualified': False}
            self.record('FINAL-CLOSURE', value)
            self.clock.tick()
            self.closed = True
            value['after_terminal_known_counters'] = self.counter_evidence('after_FINAL_CLOSURE_publication_before_caller_reporting_known_partial')
            return value
        except BaseException as exc:
            failures.hold(exc, 'caught')
            self._fail('close', exc, raw)
            raise

    def abort(self):
        self.failed = True
        try:
            closure = retire(self.d, self.item, self.clock.deadline)
            self.record('FAILED-CLEANUP', closure)
            self.clock.tick()
            self.closed = closure['closed'] is True and self.d.reaped
            return {'status': 'failed', 'closure': closure, 'custody': 'closed' if self.closed else 'unknown', 'automatic_retry': False, **self.counter_evidence('after_failed_cleanup_known_partial'), 'command_metadata': self.d.records}
        except BaseException as exc:
            failures.hold(exc, 'caught')
            return {'status': 'failed', 'custody': 'unknown', 'error': failure(exc), 'owned_resource': self.item, 'automatic_retry': False, **self.counter_evidence('failed_cleanup_exception_known_partial'), 'command_metadata': self.d.records}
