"""Exact admission and source guards for one generated Docker qualification.

Importing this module opens no source input or Docker connection. Constructing
Context requires the exact root-approved protocol and registered native child.
Only authenticated source/runtime files and the operational ledger are read.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
ADAPTERS = HERE.parent/'source-runtime-adapters-v1'
LEGACY = HERE.parent/'source-runtime-qualification-v1'
E = Path('/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2')
D = E/'completion2-v1/dosei'
Q = D/'native-runtime-qualification-v1/attempt03/network-diagnostic-v1/host-binding-v1/fresh-successor-v1'
OUTPUT = Q/'native-run-20261117-01'
PROTOCOL = Q/'hygiene-v1/NATIVE_QUALIFICATION_PROTOCOL.json'
LEDGER = E/'RESOURCES.json'
OWNER = 'complete_dosei'
RUN = 'dosei-fresh-six-control-qualification-20261117-01'
APPROVAL = 'dosei-fresh-six-control-admission-20261117-01'
PARENT_RESERVATION = 'dosei-fresh-six-control-native-artifacts-20261117-v1'
SELECTION_SHA256 = 'a951e30f611cbd07bb47ee7234fa97961fc58a169983ec9233f1eabdcb0c5dda'
PYTHON = '/opt/homebrew/bin/python3.11'
PYTHON_REAL = '/opt/homebrew/Cellar/python@3.11/3.11.6/Frameworks/Python.framework/Versions/3.11/bin/python3.11'
DOCKER = '/usr/local/Cellar/docker/29.4.0/bin/docker'
SOCKET = '/Users/nicholas/.docker/run/docker.sock'
GTIMEOUT = '/usr/local/Cellar/coreutils/9.11/bin/gtimeout'
BINARY_PINS = {
    'python': {'path': PYTHON_REAL, 'bytes': 52640, 'sha256': '4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1'},
    'docker': {'path': DOCKER, 'bytes': 29236288, 'sha256': '816765740260f2963e85a9bc75ec7ed0ffd19ee39c1f366f10c9f24701ca298e'},
    'gtimeout': {'path': GTIMEOUT, 'bytes': 47384, 'sha256': '1e26c50fa8c439fe1f4e6c6edd106e95030e16582c1c8c32e73d8a889cdf5b95'},
}
FROZEN = {
    'backend': ('docker_code_backend.py', '1a8d96d57e325db0aacd31f2abf8b92ba20de8821bf065aee6b6ef8a9ba3bd9a'),
    'policy': ('docker_code_policy.py', '6d4d8e952042d6b7a9557ba8c035da80b557b1778ec9b551f55d6b45bbdd6412'),
    'raw': ('raw_command.py', '9c2285abdbca85075bf885a2cf40721d9be1ea843671e69ebf05ddc3a46a87a0'),
    'owned': ('owned_process_v2.py', 'afae111f8dec293391bbf077cd0d700e8061328d5541f5d116ade63c1cf7d219'),
}
PROFILE_PIN = 'c1830439a06254a982279604d645de5969c3444260e74262f7ad0efc7bc3129b'
LEGACY_MODULES = {
    'store': ('evidence_store.py','bc909f0607d3ef70ac720fd5a46b1f5b44283fb5d749dfd6df9d0a132b28eaca'),
    'probe': ('network_state_probe_v1.py','f513ed96f8598d5693fa2dc4e2589d18bc5b92f14ea6d88be7f58311e76f3848'),
    'network_policy': ('network_state_policy_v1.py','c0b703578ef0f7be540c4575ca6949d884641677a782cdfc6e8b122e736f0ec0'),
}
NEW_MODULES = {'cases':'qualification_cases_v3.py','fresh_state':'fresh_runtime_state_v1.py',
               'driver':'qualification_driver_v2.py'}
LIMITS = {
    'host_ram_bytes': 536870912, 'candidate_memory_bytes': 536870912,
    'native_ledger_ram_bytes': 1073741824, 'threads': 1,
    'operation_deadline_seconds': 480, 'cleanup_deadline_seconds': 570,
    'outer_term_seconds': 590, 'outer_kill_after_seconds': 10, 'whole_wall_seconds': 600,
    'worker_cpu_soft_seconds': 40, 'worker_cleanup_cpu_soft_seconds': 55, 'worker_cpu_hard_seconds': 60,
    'controller_cpu_soft_seconds': 20, 'controller_cleanup_cpu_seconds': 22,
    'cli_cpu_soft_seconds': 2, 'cli_cpu_hard_seconds': 3,
    'fixed_candidate_cpu_soft_seconds': 2, 'fixed_candidate_cpu_hard_seconds': 3,
    'owned_cpu_allowance_seconds': 450,
    'source_read_bytes': 67108864, 'evidence_write_bytes': 4194304,
    'report_write_bytes': 65536, 'capture_bytes': 49153, 'staging_write_bytes': 65536,
    'artifact_envelope_bytes': 4390912, 'command_attempts': 80,
    'ordinary_command_attempts': 40, 'cleanup_command_attempts': 40,
    'command_stream_grant_bytes': 12582912, 'observed_command_prefix_bytes': 3145728,
    'automatic_retries': 0,
}
CAPTURE_FILES = {'console.txt':32768, 'overflow.probe':1, 'prefix-dd.stderr':4096,
                 'probe-dd.stderr':4096, 'drain.stderr':4096, 'receiver.status':1024,
                 'launch.status':2048, 'launch.start':1024}
SIG_KEYS = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


def require(ok, message):
    if not ok: raise ValueError(message)


def signature(info): return tuple(getattr(info, key) for key in SIG_KEYS)


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'exact SHA256 required')
    return value


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON field'); result[key] = value
        return result
    def finite(text):
        result = float(text); require(math.isfinite(result), 'nonfinite JSON'); return result
    def nonfinite(_): raise ValueError('nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite, parse_constant=nonfinite)


class ReadMeter:
    def __init__(self, maximum=LIMITS['source_read_bytes']):
        self.maximum = maximum; self.charged = self.known = self.attempts = 0
    def snapshot(self):
        return {'known_bytes':self.known, 'charged_bytes':self.charged,
                'unknown_charge_bytes':self.charged-self.known, 'attempts':self.attempts,
                'scope':'explicit source/profile/ledger/binary file reads; excludes dynamic runtime/kernel/daemon I/O'}


def read_file(path, maximum, pin, meter, *, materialize=True):
    path = Path(path)
    require(path.is_absolute() and path.parent.resolve() == path.parent, 'real bounded input parent')
    require(type(maximum) is int and 0 < maximum <= LIMITS['source_read_bytes'], 'finite input cap')
    require(meter.charged+maximum <= meter.maximum, 'source read grant exhausted')
    if pin is not None: sha(pin)
    meter.charged += maximum; meter.attempts += 1
    fd = None; seen = 0; digest = hashlib.sha256(); chunks = []
    try:
        fd = os.open(path, os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= maximum,
                'bounded ordinary source required')
        while seen < before.st_size:
            data = os.read(fd, min(65536, before.st_size-seen))
            require(data, 'source truncated')
            seen += len(data); meter.known += len(data); digest.update(data)
            if materialize: chunks.append(data)
        require(signature(before) == signature(os.fstat(fd)) == signature(path.lstat()), 'source changed while read')
        require(pin is None or digest.hexdigest() == pin, 'source hash differs')
        meter.charged -= maximum-seen
        return (b''.join(chunks) if materialize else None), signature(before)
    finally:
        if fd is not None: os.close(fd)


def expected_command(p, protocol_sha):
    return [PYTHON, '-I', '-S', '-B', str(HERE/'qualification_entry_v4.py'),
            '--protocol', str(PROTOCOL), '--protocol-sha256', protocol_sha,
            '--approval-id', APPROVAL, '--native-run-id', RUN]


def validate_protocol(p):
    require(type(p) is dict and p.get('schema') == 'dosei_fresh_six_control_protocol_v1', 'protocol schema')
    require(p.get('owner') == OWNER and p.get('native_run_id') == RUN and p.get('approval_id') == APPROVAL,
            'fixed execution identity')
    require(p.get('limits') == LIMITS and all(type(x) is int for x in p['limits'].values()), 'exact finite resource limits')
    require(p.get('output_directory') == str(OUTPUT) and p.get('parent_reservation_id') == PARENT_RESERVATION,
            'existing owned evidence scope')
    require(p.get('docker_executable') == DOCKER and p.get('docker_socket') == SOCKET and
            p.get('python_executable') == PYTHON and p.get('binaries') == BINARY_PINS, 'selected existing runtimes')
    require(p.get('capture_file_caps') == CAPTURE_FILES, 'exact capture cap map')
    require(p.get('source_cutoff') == '1a947dd3163f8dd556146a9721d50feefde21b54', 'immutable qualification predecessor cutoff')
    require(p.get('context_count') == 3 and type(p['context_count']) is int and
            p.get('container_count') == 6 and type(p['container_count']) is int, 'complete fixed control scope')
    for key in ('authentic_input_reads', 'model_calls', 'api_calls', 'scoring', 'image_pull', 'image_build', 'install'):
        require(p.get(key) is False, 'unauthorized execution scope')
    contexts = p.get('context_ids')
    require(type(contexts) is list and len(contexts) == 3 and all(type(x) is str for x in contexts)
            and len(set(contexts)) == 3, 'three fixed unique contexts')
    for value in contexts: sha(value)
    require(p.get('criterion_selection_sha256')==SELECTION_SHA256 and
            p.get('historical_qualified_controls')==0 and type(p['historical_qualified_controls']) is int and
            p.get('historical_failed_attempts')==3 and type(p['historical_failed_attempts']) is int,
            'selected necessary criterion and historical failures must remain explicit')
    require(p.get('case_order')==['runtime','readonly_scratch','fresh_scratch','nonzero','flood','deadline'],
            'all six ordered controls required')
    programs=p.get('generated_programs')
    require(type(programs) is dict and set(programs)==set(p['case_order']),'complete program binding map')
    for row in programs.values():
        require(type(row) is dict and set(row)=={'bytes','sha256'} and type(row['bytes']) is int and
                0<row['bytes']<=65536,'bounded complete program binding');sha(row['sha256'])
    require(p.get('runtime_attach_cap_bytes')==524288 and type(p['runtime_attach_cap_bytes']) is int,
            'fresh runtime output cap')
    expected_paths = {key: ADAPTERS/name for key,(name,_) in FROZEN.items()}
    expected_paths.update({key: LEGACY/name for key,(name,_) in LEGACY_MODULES.items()})
    expected_paths.update({key: HERE/name for key,name in NEW_MODULES.items()})
    require(type(p.get('modules')) is dict and set(p['modules']) == set(expected_paths), 'exact source module roster')
    for key, path in expected_paths.items():
        row = p['modules'][key]
        require(type(row) is dict and set(row) == {'path','sha256'} and row['path'] == str(path), 'fixed source module path')
        sha(row['sha256'])
        if key in FROZEN: require(row['sha256'] == FROZEN[key][1], 'frozen adapter changed')
        if key in LEGACY_MODULES: require(row['sha256'] == LEGACY_MODULES[key][1], 'frozen custody/probe/policy changed')
    require(p.get('profile') == {'path':str(ADAPTERS/'runtime_profile.json'),'sha256':PROFILE_PIN}, 'exact image profile')
    for key, name in (('entry','qualification_entry_v4.py'),('guard','qualification_guard_v4.py'),('cli_shim','cpu_cli_exec.py')):
        row = p.get(key)
        require(type(row) is dict and set(row) == {'path','sha256'} and row['path'] == str((LEGACY if key=='cli_shim' else HERE)/name), 'fixed supervisor source path')
        sha(row['sha256'])


def validate_authority(ledger, p, protocol_sha, *, pid, parent_pid):
    validate_protocol(p)
    binding = {'path':str(PROTOCOL),'sha256':sha(protocol_sha)}
    approvals = [row for row in ledger.get('approved_native_protocols',[]) if row.get('id') == APPROVAL]
    require(len(approvals) == 1 and approvals[0].get('owner') == OWNER and
            approvals[0].get('approved_by') == '/root' and approvals[0].get('protocol') == binding,
            'exact root protocol admission required')
    grants = [row for row in ledger.get('reservations',[]) if row.get('id') == PARENT_RESERVATION]
    require(len(grants) == 1 and grants[0].get('owner') == OWNER and grants[0].get('status') == 'active'
            and grants[0].get('kind') == 'artifact' and grants[0].get('destination') == str(OUTPUT)
            and type(grants[0].get('reserved_bytes')) is int and grants[0]['reserved_bytes'] >= LIMITS['artifact_envelope_bytes'],
            'separate prospective native artifact reservation required')
    own = [row for row in ledger.get('native_runs',[]) if row.get('id') == RUN]
    require(len(own) == 1 and own[0].get('owner') == OWNER and own[0].get('status') == 'running'
            and own[0].get('protocol') == binding and own[0].get('approval_id') == APPROVAL
            and own[0].get('command') == expected_command(p,protocol_sha)
            and own[0].get('cwd') == str(HERE), 'exact registered native command and working directory')
    require(type(own[0].get('child_pid')) is int and own[0]['child_pid'] == pid
            and type(own[0].get('coordinator_pid')) is int and own[0]['coordinator_pid'] == parent_pid,
            'direct registered worker and coordinator required')
    require(type(own[0].get('declared_max_working_ram_bytes')) is int and
            own[0]['declared_max_working_ram_bytes'] == LIMITS['native_ledger_ram_bytes']
            and type(own[0].get('requested_threads')) is int and own[0]['requested_threads'] == 1,
            'combined host and candidate resource declaration')


class Context:
    def __init__(self, args):
        self.started = args.started; self.parent = os.getppid(); self.output_root = OUTPUT
        self.protocol_sha256 = sha(args.protocol_sha256)
        self.read_meter = ReadMeter(); self.modules = {}; self.cancelled = False; self.probe_source=None
        self.output_identity = None; self.runtime_identities = {}
        require(Path(args.protocol) == PROTOCOL and args.approval_id == APPROVAL and args.native_run_id == RUN,
                'fixed exact attempt arguments')
        raw,_ = read_file(PROTOCOL,131072,sha(args.protocol_sha256),self.read_meter)
        self.protocol = unique_json(raw); validate_protocol(self.protocol); p = self.protocol
        require(p['guard']['sha256'] == args.bootstrap_guard_sha256, 'guard bootstrap binding')
        self.read_meter.known += args.bootstrap_guard_read_bytes
        self.read_meter.charged += args.bootstrap_guard_read_bytes
        require(type(args.bootstrap_guard_read_bytes) is int and 0 < args.bootstrap_guard_read_bytes <= 65536
                and self.read_meter.charged <= self.read_meter.maximum, 'bounded bootstrap source charge')
        deadline = time.monotonic()+2
        while True:
            raw,_ = read_file(LEDGER,8388608,None,self.read_meter)
            ledger = unique_json(raw)
            own = [row for row in ledger.get('native_runs',[]) if row.get('id') == RUN]
            if len(own) == 1 and own[0].get('child_pid') is None and time.monotonic() < deadline:
                time.sleep(.05); continue
            validate_authority(ledger,p,args.protocol_sha256,pid=os.getpid(),parent_pid=self.parent); break
        require(Path(PYTHON).resolve() == Path(PYTHON_REAL), 'selected existing Python alias changed')
        for key,row in BINARY_PINS.items():
            _,identity = read_file(row['path'],row['bytes'],row['sha256'],self.read_meter,materialize=False)
            self.runtime_identities[key] = identity
        socket_info = Path(SOCKET).lstat()
        require(stat.S_ISSOCK(socket_info.st_mode) and socket_info.st_uid == os.getuid(), 'owned operator socket type')
        self.socket_identity = (socket_info.st_dev,socket_info.st_ino,socket_info.st_mode)
        for key in ('entry','cli_shim'):
            _,identity = read_file(p[key]['path'],65536,p[key]['sha256'],self.read_meter)
            if key == 'cli_shim': self.runtime_identities['cli_shim'] = identity
        self.profile_bytes,_ = read_file(p['profile']['path'],65536,PROFILE_PIN,self.read_meter)
        for key,row in p['modules'].items():
            raw,_ = read_file(row['path'],65536,row['sha256'],self.read_meter)
            module = types.ModuleType('dosei_qualification_'+key); module.__file__ = row['path']
            sys.modules[module.__name__] = module
            exec(compile(raw,row['path'],'exec'),module.__dict__); self.modules[key] = module
            if key=='probe': self.probe_source=raw
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['worker_cpu_soft_seconds'],LIMITS['worker_cpu_hard_seconds']))
        info = OUTPUT.lstat()
        require(OUTPUT.parent.resolve() == OUTPUT.parent and stat.S_ISDIR(info.st_mode)
                and stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.getuid()
                and {x.name for x in OUTPUT.iterdir()} == {'capture'}, 'exclusive private output namespace')
        capture = OUTPUT/'capture'; info_capture = capture.lstat()
        require(stat.S_ISDIR(info_capture.st_mode) and stat.S_IMODE(info_capture.st_mode) == 0o700
                and info_capture.st_uid == os.getuid() and
                {x.name for x in capture.iterdir()} == set(CAPTURE_FILES), 'bounded outer capture inventory')
        for name,cap in CAPTURE_FILES.items():
            item = (capture/name).lstat()
            require(stat.S_ISREG(item.st_mode) and item.st_nlink == 1 and item.st_uid == os.getuid()
                    and item.st_size <= cap, 'capture type/cap')
        self.output_identity = (info.st_dev,info.st_ino)
        self.command_prefix = [PYTHON,'-I','-S','-B',str(LEGACY/'cpu_cli_exec.py'),'--']
        self.checkpoint()

    def checkpoint(self, *, cleanup=False):
        self.continuity()
        elapsed = time.monotonic()-self.started
        if not cleanup and (self.cancelled or elapsed >= LIMITS['operation_deadline_seconds']):
            self.cancelled = True; raise TimeoutError('qualification operation deadline')
        require(elapsed < LIMITS['cleanup_deadline_seconds'], 'qualification cleanup deadline')
    def continuity(self):
        require(os.getppid() == self.parent, 'native coordinator continuity lost')
        if self.output_identity is not None:
            info = OUTPUT.lstat()
            require(stat.S_ISDIR(info.st_mode) and (info.st_dev,info.st_ino) == self.output_identity, 'output namespace changed')
        for key,path in (('docker',DOCKER),('python',PYTHON_REAL),('cli_shim',str(LEGACY/'cpu_cli_exec.py'))):
            if key in self.runtime_identities:
                require(signature(Path(path).lstat()) == self.runtime_identities[key], 'runtime file identity changed')
        info = Path(SOCKET).lstat()
        require((info.st_dev,info.st_ino,info.st_mode) == self.socket_identity, 'operator socket identity changed')

    def command_runner(self, command, **kwargs):
        require(type(command) is list and command and command[0] == DOCKER, 'exact Docker command receiver')
        # The driver separately admits ordinary versus owned cleanup commands.
        self.continuity()
        return self.modules['raw'].run(self.command_prefix+command, **kwargs)

    def operational_receipt(self):
        return {'source_reads':self.read_meter.snapshot(), 'coordinator_pid':self.parent,
                'worker_pid':os.getpid(), 'elapsed_seconds':time.monotonic()-self.started,
                'cancelled':self.cancelled, 'native_model_or_authentic_input':False}
