"""Concrete offline DMFC adapter over the accepted immutable-ID unit runner.

No candidate code executes in this host module. No data, Docker or model work
occurs on import. The outer operator still owns current admission and recovery.
All numerical candidate and evaluator work uses the unchanged run_unit function.
"""
from __future__ import annotations

import ast
import base64
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[5]
Q = ROOT / 'authoring/delivery-20261105/common/remaining-builds-wave40'
PRODUCER = Q / 'dmfc-complete-four-cell-owner-source-20261115-v1/adaptive_producer.py'
PRODUCER_PIN = (25769, '8921348561ce08d15c796a2d23c13973c218808e49f4729e694167f4a2c93da3')
UNIT = ROOT / 'authoring/task-ownership-successors-20261102/nlb017-recovery-capacity-v4/nlb_unit.py'
UNIT_PIN = (7541, '9057ff748128ccc1909f7db3c5f77f12584823e60ffd6338750af5bb7abfade9')
ENGINES = UNIT.parent / 'nlb_engines.py'
ENGINES_PIN = (4822, 'c1720005fb9fb0338a6ee2f7c048466909b99f1336fa55418a86f4b64a35ee6d')
METHOD = ROOT / 'authoring/dmfc-timing/paired-program-cli-v1/admission.py'
METHOD_PIN = (1506, '718e2a3bd539223a79a6afbe9c763e370ec36f755832ebc0e2999261b8c9807b')
MEMORY = 4 * 1024**3
UNIT_WALL_SECONDS = 48  # unchanged40s unit plus8s cleanup; no per-trial grant
CPU_TASKS = 80  #64 candidate tasks plus16 holder tasks, conservative wall bound
ARTIFACT_CAP = 65536
STATE_CAP = 65536
JSON_CAP = 262144
MAX_TOOLS = 16
MAX_CELL_UNITS = 292  # preparation +274decisions +16tools +export


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(body, cap=JSON_CAP):
    need(type(body) is bytes and 0 < len(body) <= cap, 'bounded JSON bytes')
    def unique(pairs):
        out = {}
        for key, item in pairs:
            need(key not in out, 'duplicate JSON key')
            out[key] = item
        return out
    value = json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    encode(value)
    return value


def read(path, pin=None, cap=1048576):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'unlinked path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'ordinary bounded file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields),
             'stable complete source or input')
    finally:
        os.close(fd)
    need(pin is None or (len(body), sha(body)) == tuple(pin), 'exact source or input identity')
    return body


def pin(path, body):
    return {'path': str(Path(path).absolute()), 'bytes': len(body), 'sha256': sha(body)}


def write(path, body, cap=1048576):
    need(type(body) is bytes and 0 < len(body) <= cap, 'bounded complete output')
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in path.parents), 'ordinary output ancestors')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        need(stream.write(body) == len(body), 'complete write')
        stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(path, body)


def load_producer():
    """One exact module instance owns Reply/Usage/Limits for every adapter."""
    body = read(PRODUCER, PRODUCER_PIN)
    name = '_dmfc095_live_four_cell_producer'
    if name in sys.modules:
        result = sys.modules[name]
        need(result.__file__ == str(PRODUCER), 'one producer ABI origin')
        return result
    result = types.ModuleType(name); result.__file__ = str(PRODUCER)
    sys.modules[name] = result
    try:
        exec(compile(body, str(PRODUCER), 'exec'), result.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return result


def method_reader():
    """Reuse the exact existing reader without executing its unrelated imports."""
    body = read(METHOD, METHOD_PIN)
    tree = ast.parse(body, filename=str(METHOD))
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == 'read_method') or
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'METHOD_FIELDS' for t in n.targets))]
    need(len(nodes) == 2, 'exact method fields and reader')
    namespace = {'json': json, 'need': need, 'decode': decode}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(METHOD), 'exec'), namespace)
    return namespace['read_method']


class UnitExecutor:
    """Direct call to the admitted immutable-ID runner, no replacement engine.

    unit_module is loaded by the existing source-bound runtime. This checks its
    source origin, not hardware/OS attestation. The operator must authenticate
    its complete engine/contract dependency closure and original parent owner.
    Every unit manifest is durable before dispatch for independent recovery.
    """
    def __init__(self, unit_module, budget, output, whole_end, *, max_units, receipt_cap_bytes):
        read(UNIT, UNIT_PIN)
        need(getattr(unit_module, '__file__', None) == str(UNIT) and
             unit_module.run_unit.__code__.co_filename == str(UNIT), 'exact admitted unit module')
        need(type(max_units) is int and 1 <= max_units <= 594, 'whole four-cell unit bound')
        need(type(receipt_cap_bytes) is int and receipt_cap_bytes >= max_units * 1048576,
             'prospective complete unit receipt allocation')
        need(type(whole_end) in (int, float) and math.isfinite(whole_end) and whole_end > time.monotonic(),
             'original whole-operation deadline')
        self.unit, self.budget, self.root = unit_module, budget, Path(output).absolute()
        need(self.root.is_dir() and stat.S_IMODE(self.root.stat().st_mode) == 0o700 and
             all(not p.is_symlink() for p in (self.root, *self.root.parents)), 'fresh private operator root')
        need(not any(self.root.iterdir()), 'empty unit root')
        self.whole_end, self.max_units, self.count = whole_end, max_units, 0
        self.rows, self.failed = [], False
        namespace = unit_module.ProfileEngine.run.__globals__
        self.transport = {'docker': namespace['DOCKER'], 'environment': dict(namespace['ENV'])}

    def execute(self, source, inputs, *, output_name, output_cap, deadline, cpu_us):
        need(not self.failed and self.count < self.max_units, 'unfailed bounded unit family')
        need(type(source) is bytes and 0 < len(source) <= 65536, 'bounded source')
        need(output_name in ('result.json', 'submission.npz') and type(output_cap) is int and
             0 < output_cap <= 1048576, 'selected bounded single-output profile')
        need(type(cpu_us) is int and cpu_us >= CPU_TASKS * UNIT_WALL_SECONDS * 1000000,
             'reserve complete candidate and holder lifetime before dispatch')
        now = time.monotonic()
        need(now + UNIT_WALL_SECONDS <= deadline <= self.whole_end, 'full unit plus cleanup inside original deadline')
        need(type(inputs) is list and len(inputs) == len({x['mount_destination'] for x in inputs}), 'unique readonly inputs')
        for item in inputs:
            need(set(item) == {'path', 'bytes', 'sha256', 'mount_destination', 'read_only'} and
                 item['read_only'] is True and item['mount_destination'].startswith('/input/') and
                 '..' not in Path(item['mount_destination']).parts, 'exact input descriptor')
        index = self.count; self.count += 1
        folder = self.root / ('unit-%04d' % index); folder.mkdir(mode=0o700)
        program = folder / 'program.py'; write(program, source, 65536)
        spec = {'unit_id': 'dmfc-four-cell/unit-%04d' % index, 'public_inputs': inputs,
                'output_filename': output_name, 'max_output_bytes': output_cap}
        write(folder / 'UNIT_INTENT.json', encode({'unit': spec, 'program': pin(program, source),
              'runner': {'path': str(UNIT), 'bytes': UNIT_PIN[0], 'sha256': UNIT_PIN[1]},
              'transport': self.transport,
              'whole_deadline': self.whole_end, 'call_deadline': deadline,
              'cpu_reservation_us': cpu_us, 'dispatches': 1}), JSON_CAP)
        attempt = folder / 'attempt'
        try:
            result = self.unit.run_unit(program, sha(source), spec, attempt, self.budget,
                min(deadline - 8, now + 40), min(deadline, now + 48), None, 'NEURAL-095',
                lambda raw, _: need(type(raw) is bytes and 0 < len(raw) <= output_cap, 'opaque output'))
            elapsed = time.monotonic() - now
            need(result.get('status') == 'unit_committed' and result.get('all_owned_absent') is True,
                 'actual complete capture and immutable-ID cleanup')
            need(elapsed <= UNIT_WALL_SECONDS and time.monotonic() <= deadline, 'unit original time limit')
            value = result.get('output')
            need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact captured output pin')
            body = read(attempt / output_name, (value['bytes'], value['sha256']), output_cap)
            commit = decode(read(attempt / 'commit.json', cap=JSON_CAP))
            need(commit.get('program_sha256') == sha(source) and commit.get('output') == value and
                 commit.get('public_inputs') == inputs and commit.get('producer_removed_before_capture') is True and
                 commit.get('all_candidate_holder_volume_absent') is True, 'actual source/input/capture commit')
            charged = math.ceil(elapsed * 1000000) * CPU_TASKS
            need(charged <= cpu_us, 'complete CPU upper bound')
            self.rows.append({'index': index, 'folder': str(folder), 'complete': True,
                              'output': value, 'cpu_upper_bound_us': charged})
            return body, charged
        except BaseException:
            self.failed = True
            self.rows.append({'index': index, 'folder': str(folder), 'complete': False,
                              'reserved_cpu_us_not_refunded': cpu_us})
            raise

    def absence(self):
        return not self.failed and self.count == len(self.rows) and all(x['complete'] for x in self.rows)


def recover_units(*, owner, owner_directory, operation_root, engines, budget, until, proc=None):
    """Independent outer fallback after the existing owned host group is absent.

    Reconstruct every exact profile and constructor from its predispatch intent;
    reuse the original immutable-ID recovery. No new candidate is dispatched.
    A missing/unfinished identity is a retained failure, never name-only removal.
    """
    group = owner.stop(Path(owner_directory), until, proc)
    need(group.get('absence_verified') is True, 'owned controller and CLI group closed first')
    read(ENGINES, ENGINES_PIN)
    need(getattr(engines, '__file__', None) == str(ENGINES), 'exact recovery engine origin')
    root = Path(operation_root).absolute()
    need(all(not p.is_symlink() for p in (root, *root.parents)), 'unlinked operation root')
    folders = list(root.iterdir())
    need(len(folders) <= 594 and all(p.is_dir() and re.fullmatch(r'unit-[0-9]{4}', p.name) for p in folders),
         'finite exact operation units')
    rows = []
    def recover_one(index, folder):
        need(folder.name == 'unit-%04d' % index, 'contiguous original unit sequence')
        intent_path = folder / 'UNIT_INTENT.json'
        attempt = folder / 'attempt'
        if not intent_path.exists():
            need(not attempt.exists(), 'no attempted resources without original intent')
            return {'index': index, 'never_dispatched': True, 'all_absent': True}
        intent = decode(read(intent_path, cap=JSON_CAP))
        unit = intent['unit']
        need(intent['runner'] == {'path': str(UNIT), 'bytes': UNIT_PIN[0], 'sha256': UNIT_PIN[1]} and
             unit['unit_id'] == 'dmfc-four-cell/unit-%04d' % index and intent['dispatches'] == 1,
             'exact original runner and unit')
        need(unit['output_filename'] in ('result.json', 'submission.npz') and
             type(unit['max_output_bytes']) is int and 0 < unit['max_output_bytes'] <= 1048576,
             'bounded exact output profile')
        need(Path(intent['program']['path']) == folder / 'program.py', 'only original unit program')
        journal = attempt / 'resource_ownership.json'
        if not journal.exists():
            return {'index': index, 'never_dispatched': True, 'all_absent': True}
        owned = decode(read(journal, cap=65536))['owned']
        need(type(owned) is list and 1 <= len(owned) <= 3, 'original three-resource lifecycle')
        profile = {'public_destinations': tuple(x['mount_destination'] for x in unit['public_inputs']),
                   'output_name': unit['output_filename'], 'max_output_bytes': unit['max_output_bytes']}
        engine = engines.ProfileEngine(until, attempt, budget, profile)
        ns = engine.run.__func__.__globals__
        need(intent['transport'] == {'docker': ns['DOCKER'], 'environment': dict(ns['ENV'])},
             'same configured Docker endpoint and environment')
        engine.owned = owned
        prefixes = ('dmfc-prog-volume-', 'dmfc-prog-holder-', 'dmfc-prog-worker-')
        suffix = None
        for position, row in enumerate(owned):
            name = row.get('name'); prefix = prefixes[position]
            need(type(name) is str and re.fullmatch(prefix + '[0-9a-f]{32}', name) and
                 row.get('kind') == ('volume' if position == 0 else 'container') and
                 row.get('attempted_before_dispatch') is True, 'exact ordered attempted role')
            this_suffix = name[len(prefix):]
            suffix = this_suffix if suffix is None else suffix
            need(this_suffix == suffix, 'one original unit suffix')
            if position == 0:
                expected = engines.volume_expected(name)
            else:
                mounts = ({'/trusted/holder.py': {'type': 'bind', 'source': str(ROOT / 'authoring/shared-large-npz-runner-v1/holder_profile.py'), 'rw': False},
                           '/capture': {'type': 'volume', 'source': prefixes[0] + suffix, 'rw': False}}
                          if position == 1 else {'/program/program.py': {'type': 'bind', 'source': str(folder / 'program.py'), 'rw': False},
                           '/output': {'type': 'volume', 'source': prefixes[0] + suffix, 'rw': True}})
                if position == 2:
                    mounts.update({x['mount_destination']: {'type': 'bind', 'source': str(ROOT / x['path']), 'rw': False}
                                   for x in unit['public_inputs']})
                expected = engines.container_expected(name, 'holder' if position == 1 else 'candidate', mounts, profile)
            # Immutable-ID cleanup validates each original constructor against
            # this independently regenerated value. A mismatch must not skip
            # recovery of the other independently identified resources.
            engine.recovery_expected[(row['kind'], name)] = expected
        recovered = []
        for row in reversed(owned):
            try:
                recovered.append(engine.cleanup(row['kind'], row['name']))
            except BaseException as error:
                recovered.append({'kind': row['kind'], 'name': row['name'], 'absence_verified': False,
                                  'error_type': type(error).__name__})
        return {'index': index, 'resources': recovered,
                'all_absent': all(x.get('absence_verified') is True for x in recovered)}
    for index, folder in enumerate(sorted(folders)):
        try:
            rows.append(recover_one(index, folder))
        except BaseException as error:
            rows.append({'index': index, 'all_absent': False, 'resources_unverified': True,
                         'error_type': type(error).__name__, 'reason': str(error)[:512]})
    return {'group': group, 'units': rows, 'all_owned_absent': all(x['all_absent'] for x in rows),
            'no_new_execution': True}


def operand(path, body, destination):
    return {**pin(path, body), 'mount_destination': destination, 'read_only': True}


class LiveBackend:
    """Offline committed policy/program; tools are source-reviewed fixed programs.

    Candidate outputs never provide accounting. Query mounts cannot alter the
    frozen artifact. Source review still decides whether query-derived fitting
    occurs in computation; readonly files alone cannot prove scientific policy.
    """
    def __init__(self, *, api, mode, view, executor, output, tools, case_ids,
                 limits, reservations, comparison_id, _engineering_fixture=False):
        need(mode in api.MODES and view in api.VIEWS, 'known mode/view')
        need(_engineering_fixture or type(executor) is UnitExecutor, 'production unit executor')
        need(type(case_ids) is tuple and len(case_ids) == 258 and len(set(case_ids)) == 258, 'complete public IDs')
        need(type(tools) is dict and len(tools) <= MAX_TOOLS and all(type(v) is bytes for v in tools.values()), 'fixed source tools')
        for name, body in tools.items():
            need(name.endswith('@' + sha(body)) and len(body) <= 65536, 'tool identity binds reviewed source')
        self.api, self.mode, self.view, self.executor = api, mode, view, executor
        self.root = Path(output).absolute(); self.root.mkdir(mode=0o700)
        self.tools, self.ids = dict(tools), case_ids
        self.limits, self.reservations, self.comparison = limits, dict(reservations), comparison_id
        self.fixture = _engineering_fixture
        self.state = 'new'; self.spec = None; self.source = None; self.artifact = None
        self.context, self.observation, self.predictions = None, None, None
        self.decisions = 0; self.tool_calls = 0; self.operations = 0; self.closed = False
        self.manifest = api.load_manifest()
        self.method = method_reader()

    def admit(self, specification):
        need(self.state == 'new', 'single admission')
        expected = {'protocol': 'NEURAL-095/four-cell-adaptive/v1', 'mode': self.mode,
            'view': self.view, 'comparison_id': self.comparison, 'limits_sha256': self.limits.identity(),
            'case_count': 258, 'training_count': 748, 'case_ids_sha256': sha(encode(self.ids)),
            'public_inputs': self.manifest['public_views'][self.view]['public_inputs'],
            'public_identity': self.manifest['evaluator_only_assets']['identity'],
            'tool_ids': list(self.tools), 'reservation_policy_sha256': sha(encode({k: asdict(v) for k, v in self.reservations.items()})),
            'reset': 'fresh_cell_state_retained_within_all_258_cases',
            'query_transduction': 'forbidden_training_artifacts_read_only_after_freeze'}
        need(set(specification) == set(expected) | {'source', 'method', 'source_sha256', 'method_sha256'} and
             all(specification[k] == v for k, v in expected.items()), 'exact complete cell specification')
        source, method = specification['source'].encode(), specification['method'].encode()
        need(0 < len(source) <= 65536 and sha(source) == specification['source_sha256'] and
             sha(method) == specification['method_sha256'], 'immutable program and method')
        self.method(method)
        # Authentic byte binding stays in the trusted operator, not candidate mounts.
        identity = self.manifest['evaluator_only_assets']['identity']
        body = read(ROOT / identity['path'], (identity['bytes'], identity['sha256']))
        need(tuple(decode(body)['case_id']) == self.ids, 'all canonical258 case IDs')
        self.inputs = {}
        for item in expected['public_inputs']:
            path = ROOT / item['path']; raw = read(path, (item['bytes'], item['sha256']))
            self.inputs[item['mount_destination']] = operand(path, raw, item['mount_destination'])
        write(self.root / 'program.py', source, 65536); write(self.root / 'method.json', method, 32768)
        self.source, self.spec = source, decode(encode(specification))
        write(self.root / 'ADMISSION.json', encode(self.spec), JSON_CAP)
        self.state = 'preparation'
        return {'specification_sha256': sha(encode(specification)), 'fresh_state': True,
                'query_released': False, 'method_wire_validated': True, 'tool_manifest_matched': True,
                'public_assets_verified': True, 'session_id': os.urandom(24).hex()}

    def freeze(self, specification):
        need(self.state == 'prepared' and specification == {'specification_sha256': sha(encode(self.spec)),
             'training_artifacts_sha256': sha(self.artifact), 'source_sha256': sha(self.source),
             'method_sha256': self.spec['method_sha256']}, 'actual prepared artifact freeze')
        write(self.root / 'FREEZE.json', encode(specification))
        self.state = 'query'
        return {'freeze_sha256': sha(encode(specification)), 'query_released': False}

    def _invoke(self, source, operation, payload, reservation, deadline):
        context = encode({'schema': 'dmfc-offline-policy-call-v1', 'operation': operation,
                          'payload': payload, 'state': self.context, 'tool_observation': self.observation})
        need(len(context) <= JSON_CAP, 'complete bounded policy context')
        path = self.root / ('request-%04d.json' % self.operations)
        write(path, context, JSON_CAP); self.operations += 1
        inputs = [x for dest, x in self.inputs.items() if operation != 'prepare' or dest != '/input/query.npz']
        inputs.append(operand(path, context, '/input/operation.json'))
        if operation != 'prepare':
            inputs.append(operand(self.root / 'fitted.bin', self.artifact, '/input/fitted.bin'))
        body, cpu = self.executor.execute(source, inputs, output_name='result.json', output_cap=JSON_CAP,
                                          deadline=deadline, cpu_us=reservation.cpu_us)
        result = decode(body)
        need(type(result) is dict and set(result) == {'payload', 'state'}, 'exact policy result')
        need(len(encode(result['state'])) <= STATE_CAP, 'bounded persistent public reasoning state')
        self.context = result['state']
        return result['payload'], cpu

    def operate(self, request, *, reservation, deadline_us, memory_bytes):
        need(not self.closed and isinstance(reservation, self.api.Usage) and reservation.calls == 1 and
             reservation.model_input_tokens == reservation.model_output_tokens == reservation.model_cost_microusd == 0,
             'offline only; no fabricated provider accounting')
        need(memory_bytes == MEMORY and type(deadline_us) is int and deadline_us > time.monotonic_ns() // 1000,
             'exact aggregate memory and live deadline')
        need(type(request) is dict and set(request) == {'operation', 'payload'}, 'exact operation envelope')
        op, payload = request['operation'], request['payload']; deadline = deadline_us / 1000000
        cpu = 0; peak = 0
        try:
            if op == 'prepare':
                need(self.state == 'preparation' and payload is None, 'once-only TRAIN preparation')
                result, cpu = self._invoke(self.source, op, None, reservation, deadline); peak = MEMORY
                need(type(result) is dict and set(result) == {'artifact_base64'} and type(result['artifact_base64']) is str and
                     len(result['artifact_base64']) <= 4 * ((ARTIFACT_CAP + 2) // 3), 'bounded opaque fitted artifact')
                self.artifact = base64.b64decode(result['artifact_base64'], validate=True)
                need(0 < len(self.artifact) <= ARTIFACT_CAP, 'nonempty bounded artifact')
                write(self.root / 'fitted.bin', self.artifact, ARTIFACT_CAP)
                result = {'training_artifacts_sha256': sha(self.artifact)}; self.state = 'prepared'
            elif op == 'decide':
                need(self.state == 'query' and not hasattr(self, 'pending_tool') and self.decisions < 258 and payload == {
                    'case_id': self.ids[self.decisions], 'completed_cases': self.decisions,
                    'full_query_batch_visible': True}, 'ordered complete query sequence')
                if self.mode == 'frozen_program':
                    if self.predictions is None:
                        answer, cpu = self._invoke(self.source, 'predict_batch', {'case_ids': list(self.ids)}, reservation, deadline)
                        peak = MEMORY
                        need(type(answer) is dict and set(answer) == {'case_id', 'prediction_ms'} and
                             answer['case_id'] == list(self.ids) and type(answer['prediction_ms']) is list and
                             len(answer['prediction_ms']) == 258 and all(type(v) in (int, float) and math.isfinite(v)
                             for v in answer['prediction_ms']), 'complete finite frozen batch')
                        self.predictions = tuple(answer['prediction_ms'])
                    result = {'action': 'predict', 'case_id': self.ids[self.decisions],
                              'prediction_ms': self.predictions[self.decisions]}
                else:
                    result, cpu = self._invoke(self.source, op, payload, reservation, deadline); peak = MEMORY
                need(type(result) is dict and result.get('action') in ('predict', 'tool'), 'policy action')
                if result['action'] == 'predict':
                    need(set(result) == {'action', 'case_id', 'prediction_ms'} and result['case_id'] == self.ids[self.decisions]
                         and type(result['prediction_ms']) in (int, float) and math.isfinite(result['prediction_ms']), 'finite current-case prediction')
                    self.decisions += 1; self.observation = None
                else:
                    need(set(result) == {'action', 'tool_id', 'arguments'} and result['tool_id'] in self.tools and
                         type(result['arguments']) is dict and self.tool_calls < MAX_TOOLS, 'fixed reviewed public tool')
                    self.pending_tool = decode(encode(result))
            elif op == 'tool':
                need(self.state == 'query' and self.mode == 'case_adaptive' and hasattr(self, 'pending_tool') and
                     payload == {'case_id': self.ids[self.decisions], **self.pending_tool}, 'only the pending tool')
                tool = self.pending_tool; del self.pending_tool; self.tool_calls += 1
                result, cpu = self._invoke(self.tools[tool['tool_id']], 'tool', payload, reservation, deadline); peak = MEMORY
                need(len(encode(result)) <= STATE_CAP, 'bounded complete tool observation')
                self.observation = result
            elif op == 'export':
                need(self.state == 'query' and self.decisions == 258 and type(payload) is dict and
                     set(payload) == {'submission'} and type(payload['submission']) is bytes and
                     0 < len(payload['submission']) <= 1048576, 'complete stopped submission export')
                path = self.root / 'opaque-output.bin'; write(path, payload['submission'])
                writer = b"from pathlib import Path\nPath('/output/submission.npz').write_bytes(Path('/input/opaque.bin').read_bytes())\n"
                captured, cpu = self.executor.execute(writer, [operand(path, payload['submission'], '/input/opaque.bin')],
                    output_name='submission.npz', output_cap=1048576, deadline=deadline, cpu_us=reservation.cpu_us)
                need(captured == payload['submission'], 'live-holder capture equals producer encoding')
                peak = MEMORY; self.state = 'exported'
                result = {'submission': captured, 'absence': self._absence()}
            else:
                raise ValueError('unsupported operation or phase')
            return self.api.Reply(result, self.api.Usage(calls=1, cpu_us=cpu), peak, sha(self.source),
                                  'preparation' if op == 'prepare' else self.mode)
        except BaseException:
            self.state = 'failed'; raise

    def _absence(self):
        absent = self.executor.absence()
        return dict.fromkeys(self.api.ABSENCE, absent)

    def commit(self, body, receipt):
        need(self.state == 'exported' and receipt['submission'] == {'bytes': len(body), 'sha256': sha(body)} and
             all(self._absence().values()), 'closed exact submission commitment')
        write(self.root / 'submission.npz', body)
        write(self.root / 'COMMIT.json', encode(receipt), JSON_CAP)
        self.state = 'committed'
        return sha(encode(receipt))

    def stop(self):
        self.closed = True
        # Units already stop/remove before returning. If interrupted, the outer
        # owner must perform independent journal recovery; never invent absence.
        return self._absence()


class PairedEvaluator:
    """The existing pair_worker runs only after a durable all-four barrier."""
    def __init__(self, *, api, executor, output, deadline, cpu_reservation_us, _engineering_fixture=False):
        need(_engineering_fixture or type(executor) is UnitExecutor, 'production evaluator executor')
        self.api, self.executor = api, executor
        self.root = Path(output).absolute(); self.root.mkdir(mode=0o700)
        self.deadline, self.cpu = deadline, cpu_reservation_us
        self.manifest = api.load_manifest(); self.sealed = None; self.validated = {}; self.graded = set()
        self.failed = False

    def seal(self, four_cell_record):
        need(self.sealed is None and not self.failed, 'one all-four barrier')
        value = decode(encode(four_cell_record))
        need(value.get('protocol') == 'NEURAL-095/four-cell-adaptive/v1' and
             value.get('case_count_per_cell') == 258 and value.get('private_grades_so_far') == 0 and
             value.get('delivery_manifest_sha256') == self.api.MANIFEST['sha256'] and
             value.get('reference_names') == list(self.api.REFERENCE_NAMES), 'complete scientific barrier')
        cells = value.get('cells')
        need(type(cells) is list and len(cells) == 4 and
             [(x.get('mode'), x.get('view')) for x in cells] == list(self.api.CELLS) and
             all(all(x.get('absence', {}).get(k) is True for k in self.api.ABSENCE) for x in cells),
             'all four stopped commitments')
        write(self.root / 'ALL_FOUR.json', encode(value), JSON_CAP); self.sealed = value
        return sha(encode(value))

    def _pair(self, mode, outputs, joint, source_manifest, stage, prior=None):
        need(not self.failed and self.sealed is not None and source_manifest == self.manifest and
             mode in self.api.MODES and set(outputs) == set(self.api.VIEWS), 'sealed exact pair inputs')
        pins = {view: {'bytes': len(body), 'sha256': sha(body)} for view, body in outputs.items()}
        expected = {x['view']: x['submission'] for x in self.sealed['cells'] if x['mode'] == mode}
        need(pins == expected and joint == sha(encode({'all_four_sha256': sha(encode(self.sealed)),
             'mode': mode, 'submissions': pins})), 'same sealed outputs and joint')
        folder = self.root / (mode + '-' + stage); folder.mkdir(mode=0o700)
        inputs = []
        for view in self.api.VIEWS:
            path = folder / (view + '.npz'); write(path, outputs[view])
            inputs.append(operand(path, outputs[view], '/input/' + view + '.npz'))
        sources = self.manifest['evaluator_sources']
        for name in ('validator', 'metrics'):
            p = sources[name]; body = read(ROOT / p['path'], (p['bytes'], p['sha256']))
            path = folder / (name + '.py'); write(path, body)
            inputs.append(operand(path, body, '/input/' + name + '.py'))
        identity = self.manifest['evaluator_only_assets']['identity']
        body = read(ROOT / identity['path'], (identity['bytes'], identity['sha256']))
        path = folder / 'identity.json'; write(path, body)
        inputs.append(operand(path, body, '/input/identity.json'))
        config = {'candidate_id': 'NEURAL-095', 'mode': stage,
            'sources': {name + '.py': {k: sources[name][k] for k in ('bytes', 'sha256')} for name in ('validator', 'metrics')},
            'identity': identity, 'submissions': pins, 'joint_commit_sha256': joint}
        if stage == 'grade':
            need(set(self.validated) == set(self.api.MODES), 'both public validations before any private read')
            config['prior_validation'] = {k: prior[k] for k in ('status', 'submissions', 'joint_commit_sha256')}
            assets_path = ROOT / 'benchmarks/neuroscience/neural-095/assets.json'
            # This exact source asset pin is selected from the delivery manifest.
            candidates = [p for p in self.manifest['required_existing_source_and_authority_files']
                          if p['path'] == 'benchmarks/neuroscience/neural-095/assets.json']
            need(len(candidates) == 1, 'exact accepted assets source')
            p = candidates[0]; body = read(assets_path, (p['bytes'], p['sha256']))
            config['assets'] = {'bytes': len(body), 'sha256': sha(body)}
            path = folder / 'assets.json'; write(path, body); inputs.append(operand(path, body, '/input/assets.json'))
            for key, filename in (('targets', 'targets.npz'), ('reference_grade', 'reference_grade.json'),
                                  ('reference_commit', 'reference_commit.json'), ('reference_audit', 'reference_audit.json')):
                p = self.manifest['evaluator_only_assets'][key]
                body = read(ROOT / p['path'], (p['bytes'], p['sha256']))
                path = folder / filename; write(path, body); inputs.append(operand(path, body, '/input/' + filename))
        body = encode(config); path = folder / 'grade_contract.json'; write(path, body, JSON_CAP)
        inputs.append(operand(path, body, '/input/grade_contract.json'))
        p = sources['pair_worker']; source = read(ROOT / p['path'], (p['bytes'], p['sha256']))
        body, _ = self.executor.execute(source, inputs, output_name='result.json', output_cap=100000,
                                       deadline=self.deadline, cpu_us=self.cpu)
        result = decode(body, 100000)
        need(result.get('submissions') == pins and result.get('joint_commit_sha256') == joint and
             result.get('identity') == identity, 'actual pair worker binding')
        return result

    def validate_pair(self, *, mode, outputs, joint_sha256, source_manifest):
        try:
            need(mode not in self.validated and not self.graded, 'one public validation per mode')
            result = self._pair(mode, outputs, joint_sha256, source_manifest, 'validate')
            need(result.get('status') == 'valid_complete_pair' and all(type(result.get(k)) is int and result[k] == 0 for k in
                ('private_target_reads', 'private_target_decodes', 'private_reference_reads')), 'actual target-free validation')
            self.validated[mode] = decode(encode(result))
            return result
        except BaseException:
            self.failed = True; raise

    def grade_pair(self, *, mode, outputs, joint_sha256, prior_validation, source_manifest, all_four_sha256):
        try:
            need(set(self.validated) == set(self.api.MODES) and mode not in self.graded and
                 prior_validation == self.validated[mode] and all_four_sha256 == sha(encode(self.sealed)),
                 'complete immutable barrier and prior validation')
            self.graded.add(mode)  # Failures cannot retry or select a new comparator.
            result = self._pair(mode, outputs, joint_sha256, source_manifest, 'grade', prior_validation)
            counts = {'private_target_reads': 1, 'private_target_decodes': 1, 'private_reference_reads': 3,
                      'new_fits_in_trusted_grader': 0, 'logical_metric_calls': 2}
            need(result.get('status') == 'paired_predictions_scored' and all(type(result.get(k)) is int and result[k] == v
                 for k, v in counts.items()), 'actual complete five-reference paired grade')
            return result
        except BaseException:
            self.failed = True; raise
