"""N007 trusted callback integration; no provider operation occurs on import.

Reuse N077's pinned HTTPS Sender/Custody unchanged. The original canonical
Bridge still refuses both complete people before sending because its image
ceiling is 1500. External token-bound code is not capacity qualification.
"""
from pathlib import Path
from dataclasses import asdict
import hashlib
import http.client
import importlib.util
import json
import math
import os
import re
import stat
import sys
import time

CONDITION = 'whole_person_raw_viewer_zero_shot'
CASES = {'development-001': 2780, 'development-002': 2670}
SOURCES = {
    'benchmarks/neural/NEURAL-007/implementations/viewer-provider-v1/provider.py': {'bytes': 18476, 'sha256': 'a41bff305cfbcba79c4317be59f97c5cbe7f68d3cbd06a942a523ffc491655fb'},
    'benchmarks/neural/NEURAL-007/implementations/viewer-provider-v1/policy.py': {'bytes': 12079, 'sha256': '4201c0cc95b8db65da3bb034651e0abe5fd9f0ac2456ad81c0ad0a79c0241cb2'},
    'benchmarks/neural/NEURAL-007/implementations/viewer-provider-v1/SOURCE_BINDINGS.json': {'bytes': 885, 'sha256': '6a2c5016689e7af0a580382b69aed9a67747afbd947c3a525bedf83d30dfba37'},
    'benchmarks/neural/NEURAL-077/implementations/waveform-provider-v1/client.py': {'bytes': 19747, 'sha256': '299d3effae6db940cf2dcd8498a2b43af0b36978e9f892cdd3b8af39391d9aef'},
}
TRANSPORT_SOURCES = {
    'transport.py': {'bytes': 32953, 'sha256': '06ea9d1658bdb2cde84475f9bd5a10a346c0925ee7c118b871cac1ea290ebb30'},
    'SOURCE_BINDINGS.json': {'bytes': 1291, 'sha256': '4adf6a1dc4075646d40f15e838534327e44adc7d15b13dd5a4290b945e948da4'},
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def decode(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def source_bytes(path, expected):
    """Same bounded ordinary-source capture as the existing trusted sender."""
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and not any(p.is_symlink() for p in (path, *path.parents)), 'Ordinary absolute source path')
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= 131072
         and type(expected['sha256']) is str and re.fullmatch('[0-9a-f]{64}', expected['sha256']), 'Bounded source pin')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'], 'Exact ordinary source extent')
        raw = stream.read(expected['bytes'] + 1)
        need(fields(before) == fields(os.fstat(stream.fileno())) == fields(path.lstat())
             and pin(raw) == expected, 'Source identity changed')
    return raw


def module(path, raw, name, initial=None):
    spec = importlib.util.spec_from_loader(name, loader=None)
    value = importlib.util.module_from_spec(spec)
    value.__file__ = str(path)
    value.__dict__.update(initial or {})
    sys.modules[name] = value
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value


def load_runtime(root, integration_root=None):
    root = Path(root)
    integration_root = Path(__file__).resolve().parent if integration_root is None else Path(integration_root)
    bodies = {name: source_bytes(root / name, expected) for name, expected in SOURCES.items()}
    sender_name = 'benchmarks/neural/NEURAL-077/implementations/waveform-provider-v1/client.py'
    provider_name = 'benchmarks/neural/NEURAL-007/implementations/viewer-provider-v1/provider.py'
    sender = module(root / sender_name, bodies[sender_name], 'n007_reused_https_sender')
    provider = module(root / provider_name, bodies[provider_name], 'n007_original_provider')
    local = {name: source_bytes(integration_root / name, expected) for name, expected in TRANSPORT_SOURCES.items()}
    transport = module(integration_root / 'transport.py', local['transport.py'],
                       'n007_trusted_transport', {'DEPENDENCY_ROOT': root})
    need(transport.v.CASES == CASES and transport.v.MODE == CONDITION, 'Canonical source roster')
    return {'provider': provider, 'sender': sender, 'transport': transport,
            'source': {'dependencies': dict(SOURCES), 'integration': dict(TRANSPORT_SOURCES)},
            'integration_root': str(integration_root)}


def checked_config(value, runtime):
    keys = {'schema', 'root', 'integration_root', 'case_id', 'model', 'budget', 'source', 'token_bound_source'}
    need(type(value) is dict and set(value) == keys
         and value['schema'] == 'neural007_viewer_provider_session_v1', 'Exact session configuration')
    need(value['case_id'] in CASES and value['source'] == runtime['source']
         == {'dependencies': SOURCES, 'integration': TRANSPORT_SOURCES}, 'Canonical case/source')
    need(value['integration_root'] == runtime['integration_root'], 'Exact integration source root')
    need(type(value['model']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', value['model']), 'Explicit model')
    root = Path(value['root'])
    need(root.is_absolute() and '..' not in root.parts, 'Explicit dependency root')
    b = runtime['provider'].Budget(**value['budget'])
    b.validate()
    need(asdict(b) == value['budget'] and b.max_request_bytes <= runtime['sender'].REQUEST_CAP,
         'Unchanged sender request ceiling')
    need(b.wall_seconds > 4 and b.max_total_provider_bytes >= b.max_request_bytes + b.max_response_bytes,
         'Finite exchange and custody reserve')
    bound = value['token_bound_source']
    if bound is not None:
        need(type(bound) is dict and set(bound) == {'path', 'bytes', 'sha256'}
             and type(bound['path']) is str and Path(bound['path']).is_absolute()
             and '..' not in Path(bound['path']).parts
             and type(bound['bytes']) is int and 0 < bound['bytes'] <= 131072
             and type(bound['sha256']) is str and re.fullmatch('[0-9a-f]{64}', bound['sha256']), 'Explicit external token-bound source')
    return b


def write_new(directory, name, raw, cap=32768):
    need(type(raw) is bytes and len(raw) <= cap and '/' not in name, 'Bounded receipt')
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(directory)


class RequestAdapter:
    """Exact-byte adapter used by the unchanged N077 Sender's context checks."""
    decode = staticmethod(decode)

    def __init__(self, request, case_id, model, output_tokens):
        self.request, self.case_id, self.model, self.output_tokens = request, case_id, model, output_tokens
        value = decode(request)
        self.prompt = value['input'][0]['content'][0]['text']
        first = decode(self.prompt)
        need(first['case_id'] == case_id and first['epochs'] == CASES[case_id], 'Original full-person prompt')
        need(value['model'] == model and value['max_output_tokens'] == output_tokens, 'Request identity')

    def query_identity(self, prompt):
        need(prompt == self.prompt, 'Exact initial instructions')
        return self.case_id

    def request_body(self, prompt, model, max_output_tokens):
        need((prompt, model, max_output_tokens) == (self.prompt, self.model, self.output_tokens), 'Exact request context')
        return self.request


class Callbacks:
    """Private bounded sender/recorder; never issues a qualification decision."""
    def __init__(self, runtime, config, credential, directory, alarm, input_token_bound,
                 *, http_factory=http.client.HTTPSConnection):
        self.runtime, self.config, self.credential = runtime, config, credential
        self.directory, self.alarm, self.bound = directory, alarm, input_token_bound
        self.factory, self.config_pin = http_factory, pin(encode(config))
        self.budget = checked_config(config, runtime)
        need(type(credential) is str and 0 < len(credential) <= runtime['sender'].CREDENTIAL_CAP
             and all(33 <= ord(x) <= 126 for x in credential), 'Explicit inherited credential')
        info = os.fstat(directory)
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
             and stat.S_IMODE(info.st_mode) == 0o700 and os.listdir(directory) == [], 'Fresh private session custody')
        need(callable(input_token_bound), 'Explicit external token-bound callback')
        write_new(directory, 'CONFIG.json', encode(config))
        os.mkdir('events', 0o700, dir_fd=directory)
        os.mkdir('turns', 0o700, dir_fd=directory)
        self.events_fd = os.open('events', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        self.turns_fd = os.open('turns', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        self.events = self.turns = self.request_bytes = self.response_bytes = 0
        self.upper = False
        self.pending = self.pending_fd = self.last_request = self.bridge = None
        self.previous = '0' * 64

    def input_token_bound(self, request, deadline):
        need(len(request) <= self.runtime['sender'].REQUEST_CAP, 'Unchanged HTTPS request ceiling')
        value = self.bound(request, deadline)
        need(type(value) is int and 0 < value <= self.budget.context_tokens - self.budget.output_tokens,
             'Explicit complete-input token bound')
        self.last_request = (request, deadline)
        return value

    def send_json(self, request, deadline):
        s, c = self.runtime['sender'], self.config
        need(self.pending is None and self.last_request == (request, deadline), 'Bounded single exchange order')
        need(self.turns < self.budget.max_turns and self.request_bytes + len(request)
             + self.response_bytes + self.budget.max_response_bytes + 1 <= self.budget.max_total_provider_bytes,
             'Reserve complete failed response extent')
        adapter = RequestAdapter(request, c['case_id'], c['model'], self.budget.output_tokens)
        name = f'{self.turns:06d}'
        os.mkdir(name, 0o700, dir_fd=self.turns_fd)
        self.pending_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.turns_fd)
        self.pending = s.Custody(self.pending_fd, self.config_pin, deadline)
        sender_cfg = {'model': c['model'], 'max_output_tokens': self.budget.output_tokens,
                      'deadline': deadline, 'trial_id': c['case_id'],
                      'context_sha256': pin(adapter.prompt.encode())['sha256']}
        sender = s.Sender(sender_cfg, self.config_pin, self.credential, self.pending, adapter, self.alarm,
                          http_factory=self.factory, response_cap=self.budget.max_response_bytes)
        self.turns += 1
        self.request_bytes += len(request)
        self.alarm.arm(deadline - s.CUSTODY_SECONDS)
        received = False
        try:
            raw = sender(request)
            self.response_bytes += len(raw)
            received = True
            # The original sender protects literal echoes; also protect decoded
            # successful output before metadata/action can be emitted.
            need(not decoded_echo(decode(raw), self.credential), 'Decoded credential echo')
            return raw
        except BaseException:
            if not received and 'HTTP.json' in self.pending.created:
                self.response_bytes += self.budget.max_response_bytes + 1
                self.upper = True
            raise
        finally:
            sender.credential = None
            self.last_request = None

    def record(self, meta, request, response):
        p = self.runtime['provider']
        need(self.bridge is not None and meta['sequence'] == self.events
             and meta['previous_sha256'] == self.previous and meta['task'] == 'NEURAL-007'
             and meta['condition'] == CONDITION and meta['viewer_condition'] == CONDITION,
             'Ordered canonical event custody')
        need(meta['request'] == (None if request is None else pin(request))
             and meta['response'] == (None if response is None else pin(response)), 'Exact bridge body pins')
        need(not decoded_echo(meta, self.credential), 'Decoded metadata credential echo')
        value = {'schema': 'neural007_viewer_provider_event_v1', 'config': self.config_pin,
                 'deadline': self.bridge.deadline, 'bridge': meta}
        raw = p.encode(value)
        if meta['event'] == 'exchange' and self.pending is not None:
            try:
                self.pending.json('BRIDGE.json', value)
                need(self.pending.created == self.runtime['sender'].FILES, 'Complete original sender custody')
            finally:
                os.close(self.pending_fd)
                self.pending_fd = self.pending = None
        write_new(self.events_fd, f'{self.events:06d}.json', raw)
        self.previous = pin(p.encode(meta))['sha256']
        self.events += 1
        self.alarm.arm(self.bridge.deadline - self.runtime['sender'].CUSTODY_SECONDS)

    def close(self):
        self.credential = None
        if self.pending_fd is not None:
            os.close(self.pending_fd)
            self.pending_fd = None
        os.close(self.events_fd)
        os.close(self.turns_fd)


def decoded_echo(value, credential):
    if type(value) is str:
        return credential in value
    if type(value) is list:
        return any(decoded_echo(item, credential) for item in value)
    if type(value) is dict:
        return any(decoded_echo(key, credential) or decoded_echo(item, credential) for key, item in value.items())
    return False


def run_session(runtime, config, credential, directory, binary_in, binary_out, input_token_bound,
                *, http_factory=http.client.HTTPSConnection):
    p, s = runtime['provider'], runtime['sender']
    budget = checked_config(config, runtime)
    alarm = s.Alarm(time.monotonic() + budget.wall_seconds)
    callbacks = bridge = None
    terminal = None
    error_type = None
    try:
        callbacks = Callbacks(runtime, config, credential, directory, alarm, input_token_bound, http_factory=http_factory)
        bridge = p.Bridge(task='NEURAL-007', condition=CONDITION, model=config['model'], budget=budget,
                          send_json=callbacks.send_json, input_token_bound=callbacks.input_token_bound,
                          record=callbacks.record)
        callbacks.bridge = bridge
        terminal = bridge.serve(binary_in, binary_out)
        need(bridge.p.case == config['case_id'] and bridge.p.accepted == set(range(CASES[config['case_id']])),
             'Complete configured person with irreversible first finals')
    except BaseException as error:
        error_type = type(error).__name__
    finally:
        try:
            if callbacks is not None:
                try:
                    if bridge is not None and bridge.deadline is not None:
                        alarm.arm(bridge.deadline)
                    value = {'schema': 'neural007_viewer_provider_end_v1', 'config': callbacks.config_pin,
                         'case_id': config['case_id'], 'condition': CONDITION,
                         'status': 'complete_unscored' if terminal is not None and error_type is None else 'failed_no_admission',
                         'events': callbacks.events, 'turns': callbacks.turns,
                         'request_bytes': callbacks.request_bytes, 'response_bytes': callbacks.response_bytes,
                         'response_charge_contains_upper_bound': callbacks.upper,
                         'episode_id': None if bridge is None else bridge.p.episode,
                         'deadline': None if bridge is None else bridge.deadline,
                         'terminal': None if terminal is None else pin(p.encode(terminal)),
                         'provider_capacity_qualified': False, 'provider_context_qualified': False,
                         'scientific_qualification': False, 'token_bound_qualified': False, 'error_type': error_type}
                    write_new(directory, 'CLIENT_END.json', p.encode(value))
                finally:
                    callbacks.close()
        finally:
            alarm.close()
    return terminal is not None and error_type is None


def external_bound(config):
    loaded = None
    def bound(request, deadline):
        nonlocal loaded
        item = config['token_bound_source']
        need(item is not None, 'External complete-input token bound remains unqualified/unavailable')
        if loaded is None:
            expected = {key: item[key] for key in ('bytes', 'sha256')}
            loaded = module(item['path'], source_bytes(item['path'], expected), 'n007_external_token_bound')
        return loaded.input_token_bound(request, deadline)
    return bound


def main(argv=None):
    # No HTTP factory, credentials or qualification toggle is exposed by CLI.
    args = sys.argv[1:] if argv is None else argv
    need(len(args) == 6, 'Three inherited descriptors required')
    fds = {}
    for name, value in zip(args[::2], args[1::2]):
        need(name in ('--credential-fd', '--config-fd', '--custody-fd') and name not in fds
             and value.isascii() and value.isdecimal(), 'Descriptor arguments only')
        fds[name] = int(value)
    need(len(set(fds.values())) == 3 and all(3 <= v <= 1048576 for v in fds.values()), 'Distinct inherited descriptors')
    # Use the identical finite pipe reader after a small credential-free config
    # bootstrap; this preliminary read has a finite poll and size limit.
    import selectors
    raw = bytearray()
    deadline = time.monotonic() + 5
    info = os.fstat(fds['--config-fd'])
    need(stat.S_ISFIFO(info.st_mode) and info.st_uid == os.geteuid(), 'Owned config pipe')
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(fds['--config-fd'], selectors.EVENT_READ)
            while True:
                left = deadline - time.monotonic()
                need(left > 0 and selector.select(left), 'Config deadline')
                piece = os.read(fds['--config-fd'], min(4096, 32769 - len(raw)))
                if not piece:
                    break
                raw.extend(piece)
                need(len(raw) <= 32768, 'Config extent')
        config = decode(bytes(raw))
        runtime = load_runtime(config['root'], config['integration_root'])
        checked_config(config, runtime)
        token = runtime['sender'].pipe_body(fds['--credential-fd'], runtime['sender'].CREDENTIAL_CAP, deadline)
        need(0 < len(token) <= runtime['sender'].CREDENTIAL_CAP and all(33 <= x <= 126 for x in token), 'Credential pipe')
        return 0 if run_session(runtime, config, token.decode('ascii'), fds['--custody-fd'],
                                sys.stdin.buffer, sys.stdout.buffer, external_bound(config)) else 3
    finally:
        for fd in fds.values():
            os.close(fd)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(3) from None
