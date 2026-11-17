"""Concrete owned persistent model-container lifecycle with exact turn captures.

Uses the captured Linux identity-bound Docker CLI. Mac Docker availability does
not qualify this route: Linux pidfd/proc semantics and exact images are required.
No ambient server, provider cache, network route, model pull or install is used.
"""
from pathlib import Path
import time
import uuid
from .common import capture, decode, encoded, need, pin, publish
from .vendor_transport.engine import Docker, call, inspect, resource_inventory, retire, validate_natural_exit, validate_cli_records
from .vendor_transport.provider import create_args, admit_container, caps
from .vendor_transport.bounds import Meter, tree


class Session:
    def __init__(self, configuration, root, context, clock, source_mounts, profile_mount, models_mount, lifecycle_mount):
        self.c, self.root, self.context, self.clock = configuration, Path(root), context, clock
        need(configuration['schema'] == 'neural007_model_transport_configuration_v1', 'Qualified provider configuration')
        need(not self.root.exists() and self.root.is_absolute(), 'Fresh owned model context')
        self.root.mkdir(mode=0o700); self.requests = self.root / 'requests'; self.requests.mkdir(mode=0o755)
        self.meter = Meter(configuration['read_bytes'], configuration['write_bytes'], clock['deadline'])
        self.sequence = 0; self.turns = 0; self.closed = False; self.started = False; self.before = None
        self.item = {'kind': 'container', 'name': 'neural007-' + uuid.uuid4().hex, 'owner': uuid.uuid4().hex, 'attempted': False, 'acknowledged': False}
        phase_caps = caps(65536)
        phase_caps.update(model_create=4096, model_start=4096, model_admit=131072, model_image=131072,
                          model_ready=2097152, model_turn=8388608, model_close=2097152, model_wait=4096, model_exit=131072)
        def record(kind, value):
            self.sequence += 1
            body = encoded({'kind': kind, 'value': value}); self.meter.write(len(body))
            publish(self.root / f'event-{self.sequence:05d}.json', body); self.meter.wrote(len(body))
        self.record = record
        self.d = Docker(configuration['docker_binary'], configuration['docker_socket'], max_calls=256,
                        reply_budget=configuration['cli_bytes'], phase_caps=phase_caps,
                        publish=record, account_read=self.meter.read, reserve_read=self.meter.ensure_read)
        self.mounts = {**source_mounts, '/profile.json': profile_mount, '/models': models_mount, '/lifecycle.json': lifecycle_mount}
        self.binding = {k: ('bind', Path(v['path']), False) for k, v in self.mounts.items()}
        # Requests are the sole host-appended control channel; immutable inputs
        # are still reauthenticated. No model response is written here.
        self.binding['/requests'] = ('bind', self.requests, False)
        self.request = {'image': configuration['image'], 'command': ['/usr/local/bin/python','-I','-B','/library/program/entry.py','provider_worker'],
                        'resources': {'memory_bytes': 16 * 1024**3, 'cpu_nanos': 4_000_000_000, 'pids': 128,
                                      'max_file_bytes': 8 * 1024**2, 'scratch_bytes': 16 * 1024**3}}
        self.admission = decode(capture(configuration['admission_path'], configuration['admission_pin'],meter=self.meter))
        from .vendor_transport.bounds import mount_identity
        need(self.admission['context'] == context and self.admission['image'] == configuration['image']
             and self.admission['immutable_mounts'] == mount_identity(self.mounts)
             and self.admission['mailbox_policy'] == 'fresh_readonly_append_only_current_context'
             and self.admission['source'] == configuration['source'], 'Independent exact provider/image/source boundary record')

    def start(self):
        need(not self.started and not self.closed, 'One provider lifecycle')
        end = min(self.clock['deadline'] - 120, time.monotonic() + 180)
        self.before = {k: tree(v, self.meter) for k, v in self.mounts.items()}
        need(resource_inventory(self.d, self.item, self.item['owner'], end, 'before_container') == [], 'Fresh owned namespace')
        image = decode(call(self.d, ['image','inspect',self.c['image'],'--format','{{json .}}'], end, 'model_image'))
        need(image['Id'] == self.c['image'] and not image['Config'].get('Volumes') and not image['Config'].get('Healthcheck'), 'Existing qualified image with no hidden volumes/health process')
        self.item['attempted'] = True; self.record('OWNERSHIP', self.item.copy())
        ident = call(self.d, create_args(self.item, False, self.binding, self.request, []), end, 'model_create', 4096).decode().strip()
        need(len(ident) == 64 and all(c in '0123456789abcdef' for c in ident), 'Exact owned container ID')
        self.item.update(id=ident, acknowledged=True); self.record('ACK', self.item.copy())
        admit_container(inspect(self.d, 'container', ident, end, 'model_admit'), self.item, False, self.binding,
                        self.request, [], image['Config'].get('Env') or [])
        call(self.d, ['container','start',ident], end, 'model_start',4096); self.started = True
        while True:
            reply = self._read('/work/READY.json', end, 'model_ready')
            if reply is not None:
                need(reply['context'] == self.context and reply['deadline'] == self.clock['deadline'], 'Exact ready original context clock')
                self.record('READY', reply); return reply
            need(time.monotonic() + .1 < end, 'Setup deadline'); time.sleep(.05)

    def _read(self, path, end, phase):
        # Literal trusted code, no candidate interpolation or general shell.
        code = 'from pathlib import Path;import sys,time;p=Path(sys.argv[1]);end=float(sys.argv[2]);\nwhile not p.exists():\n if time.monotonic()>=end: raise TimeoutError("Original provider wait")\n time.sleep(.05)\nsys.stdout.buffer.write(p.read_bytes())'
        raw = self.d(['container','exec',self.item['id'],'/usr/local/bin/python','-I','-B','-c',code,path,str(end)], end, phase, self.d.phase_caps[phase])
        return decode(raw)

    def generate(self, prompt, schema):
        need(self.started and not self.closed and self.turns < 8, 'Bounded current-context decisions')
        self.turns += 1; end = min(self.clock['deadline'] - 120, time.monotonic() + 180)
        request = {'context': self.context, 'turn': self.turns, 'prompt': prompt, 'format': schema, 'deadline': end}
        body = encoded(request); path = self.requests / f'turn-{self.turns}.json'; self.meter.write(len(body)); publish(path, body); self.meter.wrote(len(body))
        code = 'import sys;sys.path.insert(0,"/library");from program.provider_worker import turn;from program.common import capture,decode,encoded;sys.stdout.buffer.write(encoded(turn(decode(capture(sys.argv[1])))))'
        raw = self.d(['container','exec',self.item['id'],'/usr/local/bin/python','-I','-B','-c',code,'/requests/'+path.name], end, 'model_turn', 8388608)
        response = decode(raw)
        need(response['context'] == self.context and response['turn'] == self.turns and response['request'] == pin(body)
             and response['finished'] < end, 'Captured model response joins exact request/original turn deadline')
        self.meter.write(len(raw)); response_pin = publish(self.root / f'response-{self.turns}.json', raw); self.meter.wrote(len(raw))
        return response['action'], {'request': pin(body), 'response': response_pin, 'deadline': end}

    def close(self):
        need(self.started and not self.closed, 'Close current owned context once')
        end = self.clock['deadline']; close_body=encoded({'context':self.context}); self.meter.write(len(close_body))
        publish(self.requests/'CLOSE.json',close_body); self.meter.wrote(len(close_body))
        while True:
            value = self._read('/work/CLOSED.json', end, 'model_close')
            if value is not None: break
            need(time.monotonic() + .1 < end, 'Unextended close deadline'); time.sleep(.05)
        need(value['context'] == self.context and value['server_reaped'] is True and value['model_unloaded'] is True, 'Owned server/model retirement')
        import base64
        log=base64.b64decode(value['log_base64'],validate=True); need(pin(log)==value['log'] and len(log)<=1048576, 'Complete bounded server stdout/stderr captured before retirement')
        self.meter.write(len(log)); publish(self.root/'SERVER.log',log);self.meter.wrote(len(log))
        self.record('CLOSED', value); ack_body=encoded({'context':self.context});self.meter.write(len(ack_body))
        publish(self.requests/'ACK.json',ack_body);self.meter.wrote(len(ack_body))
        raw = self.d(['container','wait',self.item['id']],end,'model_wait',4096)
        state = inspect(self.d,'container',self.item['id'],end,'model_exit')['State']
        natural = {k: state[k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
        validate_natural_exit(natural); need(raw.strip() == b'0', 'Natural trusted provider-container exit')
        closure = retire(self.d,self.item,end); need(closure['closed'] is True, 'Owned provider container removed')
        after = {k: tree(v,self.meter) for k,v in self.mounts.items()}; need(after == self.before, 'All provider inputs/models unchanged')
        validate_cli_records(self.d.records,self.d.phase_caps)
        self.closed = True
        return {'context': self.context, 'turns': self.turns, 'natural_exit': natural, 'closure': closure,
                'read_bytes': self.meter.read_bytes, 'write_bytes': self.meter.write_bytes,
                'provider_peak_rss_and_physical_io': None, 'scientific_qualification': False}

    def abort(self):
        """Failure cleanup only; never upgrades a failed generation to success."""
        closure = retire(self.d,self.item,self.clock['deadline']); self.record('FAILED-CLEANUP',closure)
        need(closure['closed'] is True,'Explicit unresolved owned resources otherwise'); self.closed = True
        return closure
