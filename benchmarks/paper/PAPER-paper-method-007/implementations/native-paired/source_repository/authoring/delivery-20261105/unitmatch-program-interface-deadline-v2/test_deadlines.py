"""Literal UnitMatch producer + BoundEngine.run with fake time/CLI, zero I/O fixtures."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
OLD = HERE.with_name('unitmatch-program-interface-v1')


def function(body, name):
    found = [x for x in ast.parse(body).body if isinstance(x, ast.FunctionDef) and x.name == name]
    assert len(found) == 1
    return found[0]


def literal_run(transport_body):
    bind = function(transport_body, 'bind')
    cls = next(x for x in bind.body if isinstance(x, ast.ClassDef) and x.name == 'BoundEngine')
    return next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'run')


class MemoryPath:
    def __init__(self, value): self.value = value
    def __truediv__(self, part): return MemoryPath(self.value + '/' + part)
    def __str__(self): return self.value
    def mkdir(self, **kwargs): pass


def simulate(task_body, transport_body, completion, mouse='Mouse1'):
    """Entire real run_unit plus real wait wrapper; all external effects injected."""
    clock = [0.0]; pending_delay = [False]; engines = []; validations = []
    cli = []; frames = []; payload = b'{"invented":true}'
    sha = 'a' * 64
    unit = {'unit_id': mouse, 'output_filename': 'fold.json', 'max_output_bytes': 100,
            'public_inputs': [{'invented': True}], 'view': 'A', 'method_name': 'invented'}
    def need(ok, message):
        if not ok: raise ValueError(message)
    fake_time = types.SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda _: None)

    class Budget:
        def charge_read(self, amount):
            if pending_delay[0]:
                clock[0] += 2.0
                pending_delay[0] = False
        def write(self, path, body, **kwargs):
            frames.append(('output', len(body)))

    def call(binary, env, args, deadline, cap):
        cli.append({'argv': list(args), 'deadline': deadline, 'entry': clock[0]})
        stdout = b''
        if args[0] == 'start' and '-worker-' in args[1]:
            clock[0] = 5.0
            pending_delay[0] = True
        elif args[0] == 'wait':
            # The literal wrapper rebased the previously computed15s after
            # charge_read consumed2s: its new CLI deadline is22, not20.
            assert clock[0] == 7.0 and deadline == 22.0
            assert completion < deadline
            clock[0] = completion
        elif args[0] == 'logs':
            stdout = b'HOLDER_READY\n'
        elif args[0] == 'exec':
            stdout = json.dumps({'status': 'captured', 'name': 'fold.json', 'bytes': len(payload),
                'sha256': hashlib.sha256(payload).hexdigest(), 'base64': base64.b64encode(payload).decode()}).encode()
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr=b'')

    wrapper_scope = {'need': need, 'time': fake_time, 'call': call, 'binary': 'invented-never-called', 'env': {}}
    exec(compile(ast.Module([literal_run(transport_body)], []), '<literal BoundEngine.run>', 'exec'), wrapper_scope)

    class Engine:
        def __init__(self, end, out, budget, profile):
            self.end = end; self.out = out; self.budget = budget; self.owned = []
            self.commands = []; self.sequence = 0; self.live = set(); engines.append(self)
        run = wrapper_scope['run']
        def volume(self, name):
            self.owned.append({'kind': 'volume', 'name': name}); self.live.add(('volume', name))
        def create(self, name, role, mounts):
            self.owned.append({'kind': 'container', 'name': name}); self.live.add(('container', name))
            return {'Id': name + '-invented-id'}, {'role': role, 'mounts': mounts}
        def inspect(self, kind, name):
            return {'State': {'Running': '-holder-' in name, 'Pid': 0, 'OOMKilled': False, 'ExitCode': 0}}
        def cleanup(self, kind, name):
            self.live.discard((kind, name))
            return {'kind': kind, 'name': name, 'absence_verified': True}
        def logs(self, name): return {'stdout': '', 'stderr': ''}
        def write(self, name, value, **kwargs):
            frames.append((name, len(json.dumps(value))))
            return MemoryPath('/invented/' + name)

    def validate(raw, got):
        assert raw == payload and got is unit
        validations.append(mouse)
    scope = {'time': fake_time, 'ProfileEngine': Engine, 'runtime': lambda _: {}, 'need': need,
        'digest': lambda _: sha, 'admit_unit': lambda got, program: need(got is unit and program == sha, 'unit'),
        'verified_input_mounts': lambda got, program: {'/input': '/invented/view'},
        'uuid': types.SimpleNamespace(uuid4=lambda: types.SimpleNamespace(hex='0' * 32)),
        'HERE': MemoryPath('/invented/vendor'), 'json': json, 'base64': base64, 'hashlib': hashlib}
    exec(compile(ast.Module([function(task_body, 'run_unit')], []), '<literal run_unit>', 'exec'), scope)
    result = scope['run_unit'](MemoryPath('/invented/program.py'), sha, unit, MemoryPath('/invented/out'),
                              Budget(), 80, 100, None, 'invented-candidate', validate)
    assert len(engines) == 1 and not engines[0].live and result['all_owned_absent']
    assert len(engines[0].owned) == 3
    assert sum(n for _, n in frames) < 50000
    return {'completion': completion, 'status': result['status'], 'validated': bool(validations),
            'capture_calls': sum(x['argv'][0] == 'exec' for x in cli),
            'kill_calls': sum(x['argv'][0] == 'kill' for x in cli), 'all_owned_absent': True,
            'rebased_cli_deadline': next(x['deadline'] for x in cli if x['argv'][0] == 'wait'),
            'original_producer_deadline': 20.0, 'result': result, 'fixture_memory_bytes': sum(n for _, n in frames)}


def main():
    old = (OLD / 'vendor/task_unit.py').read_bytes()
    new = (HERE / 'vendor/task_unit.py').read_bytes()
    transport = (HERE / 'transport.py').read_bytes()
    insertion = b"            need(time.monotonic()-start<20,'Original20-second producer deadline after wait')\n"
    assert new.count(insertion) == 1 and new.replace(insertion, b'') == old
    assert hashlib.sha256(old).hexdigest() == '6f7e0e6560156c7843b48a2c6e93deeb8e6260a9e9a1a67471042ea5b56a3e6a'
    assert hashlib.sha256(transport).hexdigest() == '0a63e1e2958324390e235185bd66a6fabefb9bb6ec85124ff39f9faa3f147da1'
    before = [simulate(old, transport, t) for t in (19.0, 20.0, 21.0)]
    after = [simulate(new, transport, t) for t in (19.0, 20.0, 21.0)]
    assert all(x['status'] == 'unit_committed' for x in before)
    assert after[0]['result'] == before[0]['result']
    for x in after[1:]:
        assert x['status'] == 'execution_failed_preserved' and not x['validated'] and x['capture_calls'] == 0
        assert x['kill_calls'] == 2 and x['all_owned_absent'] and x['completion'] < x['rebased_cli_deadline']
    assert all(x['all_owned_absent'] for x in before + after)
    # Five identifiers are retained; no biological numerical inputs are involved.
    mice = [simulate(new, transport, 19.0, 'Mouse' + str(i)) for i in range(1, 6)]
    assert all(x['status'] == 'unit_committed' and x['validated'] for x in mice)
    for x in before + after + mice: x.pop('result')
    print(json.dumps({'schema': 'unitmatch_original_deadline_generated_controls_v2',
        'literal_real_functions': ['run_unit', 'BoundEngine.run'], 'before': before, 'after': after,
        'all_five_invented_contexts_timely': True, 'memory_fixture_bytes': sum(x['fixture_memory_bytes'] for x in before + after + mice),
        'filesystem_fixture_writes': 0, 'native_calls': 0, 'authentic_arrays_or_scorer_calls': 0}, sort_keys=True))


if __name__ == '__main__': main()
