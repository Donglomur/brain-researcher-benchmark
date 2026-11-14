"""Actual local provider adapter consuming one already-reserved role request.

No campaign or component token ledger, reserve, settle, refund, or retry exists
in this module. The original controller owns that one reservation throughout.
"""
import os
import re
from pathlib import Path
from types import SimpleNamespace


def validate_reservation(c, request, config, messages):
    r = request['token_reservation']
    c.keys(r, ('scope', 'maximum_input', 'maximum_output', 'status', 'usage'))
    c.require(r['scope'] == 'current_postscore_operation' and
              r['status'] == 'reserved_before_dispatch' and r['usage'] is None,
              'actual unresolved original reservation')
    c.integer(r['maximum_input'], 1); c.integer(r['maximum_output'], 1)
    c.require(r['maximum_input'] == config['maximum_input_tokens'] and
              r['maximum_output'] <= config['maximum_output_tokens'],
              'exact original input reservation and bounded output operand')
    c.require(type(messages) is list and 0 < len(messages) <= 128,
              'finite authorized model conversation')
    for m in messages:
        c.keys(m, ('role', 'content'))
        c.require(m['role'] in ('user', 'assistant') and type(m['content']) is str,
                  'no substituted system instruction')
    c.require(sum(len(m['content'].encode('utf-8')) for m in messages) <=
              config['request_bytes'], 'entire original prompt within transport bound')
    return r['maximum_output']


def capture_provider(runtime, budget, operator_root, spec, source_identity):
    """Original registry's complete model/config checks without its TokenLedger."""
    c = runtime['common']; c.keys(spec, ('id', 'kind', 'config', 'qualification',
                                        'model_directory', 'model_manifest'))
    c.require(type(spec['id']) is str and re.fullmatch('[a-z][a-z0-9_]{0,47}', spec['id'])
              and spec['kind'] == 'local_transformers_text_v1', 'explicit local provider')
    config = c.parse(c.capture(operator_root, spec['config'], budget, 1048576))
    c.keys(config, ('schema', 'kind', 'source_identity', 'request_bytes', 'seed',
                   'system_prompt', 'maximum_input_tokens', 'maximum_output_tokens'))
    c.require(config['schema'] == 'neural055-provider-configuration-v3' and
              config['kind'] == spec['kind'] and config['source_identity'] == source_identity
              and config['request_bytes'] == 1048576, 'exact selected provider config')
    c.require(type(config['seed']) is int and type(config['system_prompt']) is str,
              'explicit selected generation initialization')
    for key in ('maximum_input_tokens', 'maximum_output_tokens'): c.integer(config[key], 1)
    model = Path(spec['model_directory'])
    c.require(model.is_absolute() and model.is_dir() and
              not any(p.is_symlink() for p in (model, *model.parents)), 'literal original model root')
    manifest = c.parse(c.capture(operator_root, spec['model_manifest'], budget, 16777216))
    c.keys(manifest, ('schema', 'files'))
    c.require(manifest['schema'] == 'neural055-qualified-local-model-files-v3' and
              type(manifest['files']) is list and bool(manifest['files']), 'complete model manifest')
    expected = set(); directories = {''}; stamps = {}
    for desc in manifest['files']:
        c.keys(desc, ('path', 'bytes', 'sha256')); name = str(c.relative(desc['path']))
        c.require(name not in expected, 'unique model member'); expected.add(name)
        path = model/name
        c.require(not any(p.is_symlink() for p in (path, *path.parents)), 'no model links')
        c.require(runtime['seals'].file_identity(path, budget, desc['bytes']) ==
                  {'bytes': desc['bytes'], 'sha256': desc['sha256']}, 'whole original model body')
        stamps[name] = c.stamp(path.lstat())
        directories.update(str(p) for p in Path(name).parents if str(p) != '.')
    actual = set()
    for directory, dirs, files in os.walk(model, followlinks=False):
        here = Path(directory)
        c.require(all(not (here/name).is_symlink() and
                      str((here/name).relative_to(model)) in directories for name in dirs),
                  'no undeclared or linked model directories')
        actual.update(str((here/name).relative_to(model)) for name in files)
        c.require(actual <= expected, 'no undeclared model members')
    c.require(actual == expected, 'exact complete original model namespace')
    return dict(id=spec['id'], kind=spec['kind'], config=config, model=model,
                manifest=manifest, stamps=stamps)


class ModelSource:
    """Concrete readonly single-entry provider capsule; no controller journal mount."""
    def __init__(self, c, budget, root, descriptor, identity):
        self.c = c; self.budget = budget; self.root = Path(root)
        self.descriptor = descriptor; self.identity = identity
    def actor_current(self):
        self.c.capture(self.root, self.descriptor, self.budget, 1048576)
        return self.root


class ReservedAdapter:
    def __init__(self, runtime, budget, journal, carrier, runner, profile,
                 source, provider, scope, poll_daemon):
        self.runtime = runtime; self.c = runtime['common']; self.budget = budget
        self.journal = journal; self.carrier = carrier; self.runner = runner
        self.profile = profile; self.source = source; self.provider = provider
        self.scope = scope; self.poll_daemon = poll_daemon; self.used = False
        self.cli_config = journal.root/'docker_cli'
        if not self.cli_config.exists(): self.cli_config.mkdir(mode=0o700)
        self.c.require(self.cli_config.is_dir() and not self.cli_config.is_symlink() and
                       not any(self.cli_config.iterdir()), 'fresh empty explicit Docker CLI configuration')
        self.host = runtime['native'].DockerHost(profile, runner, journal, budget, carrier)
        self.observed = SimpleNamespace(id='reserved-role-provider', commands=[], resources=[])
        self.original = dict(status='owned_before_admission', native=None, usage=None,
                             resources=self.observed.resources, legacy_role='investigator_decision',
                             actual_role='postscore_reserved_local_model')
        self.counter = 0; carrier.retain(self)

    def command(self, args, cap=131072, end=None, poll_service=None):
        deadline = self.budget.deadline if end is None else end
        def poll(current):
            self.poll_daemon(current)
            if poll_service is not None: poll_service(current)
        before = len(self.runner.originals); name = 'provider-control-'+str(self.counter)
        self.counter += 1
        try:
            obs = self.runner.run(name, [self.profile['docker_binary'], '--config', str(self.cli_config), '--host',
                self.profile['docker_host'], *args], deadline, cap, poll_service=poll)
            return bytes(obs.stdout)
        finally:
            self.observed.commands.extend(self.runner.originals[before:])

    def record(self, kind, name):
        row = dict(kind=kind, name=name, owner=self.observed.id, attempted=False,
                   acknowledged=False, id=None, closed=True, disposition='not_dispatched', observations=[])
        self.observed.resources.append(row); return row

    def inspect(self, row):
        c = self.c
        value = self.runtime['native'].one(c.parse(self.command(
            ['container', 'inspect', row['id'] or row['name']])))
        self.runtime['native'].full_id(value['Id'])
        c.require(value['Name'] == '/'+row['name'] and
                  value['Config']['Labels'].get('org.neurobench.n055') == self.observed.id and
                  (row['id'] is None or row['id'] == value['Id']), 'same original owned provider')
        row['id'] = value['Id']; row['observations'].append(dict(id=value['Id'], state=value['State']))
        return value

    def retire(self, row):
        if not row['attempted']: return True
        c = self.c
        try:
            state = self.inspect(row)['State']
            if state['Running']:
                self.command(['container', 'kill', '--signal', 'KILL', row['id']], 4096)
                row['forced'] = True
            if state['Status'] != 'created':
                waited = self.command(['container', 'wait', row['id']], 4096).strip()
                c.require(re.fullmatch(b'[0-9]+', waited), 'actual provider wait acknowledgment')
                row['wait_exit'] = int(waited)
            state = self.inspect(row)['State']
            c.require(not state['Running'] and state['Pid'] == 0 and
                      state['Status'] in ('created', 'exited', 'dead'), 'provider stopped')
            if 'wait_exit' in row: c.require(row['wait_exit'] == state['ExitCode'], 'wait/inspect join')
            if 'natural_state' in row:
                c.require(all(state[k] == row['natural_state'][k] for k in
                    ('Status', 'Running', 'Dead', 'Pid', 'ExitCode', 'OOMKilled', 'Error')),
                    'original natural provider state preserved')
            c.require(self.command(['container', 'rm', row['id']], 4096).strip() == row['id'].encode(),
                      'actual provider removal')
            c.require(self.command(['container', 'ls', '-a', '--no-trunc', '--filter',
                'name=^/'+row['name']+'$', '--format', '{{.ID}}'], 4096).strip() == b'',
                'original provider absent')
            row.update(closed=True, disposition='original_removed_absent'); return True
        except BaseException as error:
            self.carrier.fail(error, 'reserved-provider-retirement')
            row['disposition'] = 'unresolved_retirement'; return False

    def argv_for(self, row, binds, destination, args):
        c = self.c; p = self.profile
        c.require(destination is None and set(binds) ==
            {'/request.json', '/config.json', '/runtime', '/model'} and
            all(not writable for _, writable in binds.values()), 'fixed readonly model mounts')
        argv = ['container', 'create', '--pull', 'never', '--name', row['name'], '--label',
            'org.neurobench.n055='+self.observed.id, '--cgroup-parent', self.parent,
            '--cpus', '1', '--memory', str(p['memory_bytes']), '--memory-swap', str(p['memory_bytes']),
            '--pids-limit', str(p['pids']), '--network', 'none', '--cgroupns', 'private',
            '--ipc', 'private', '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--restart', 'no', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size='+str(p['scratch_bytes']),
            '--ulimit', 'core=0:0', '--ulimit', 'nofile=128:128', '--ulimit', 'fsize=536870912:536870912']
        for target, (path, _) in binds.items():
            argv += ['--mount', 'type=bind,src='+str(path)+',dst='+target+',readonly']
        for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            argv += ['--env', name+'=1']
        return argv+['--entrypoint', 'python', p['image'], *args]

    def generate(self, request, messages, deadline):
        c = self.c; b = self.budget
        c.require(not self.used and b.token_ledger is None, 'one reserved call without another ledger')
        self.used = True
        maximum = validate_reservation(c, request, self.provider['config'], messages)
        for desc in self.provider['manifest']['files']:
            path = self.provider['model']/desc['path']
            c.require(c.stamp(path.lstat()) == self.provider['stamps'][desc['path']],
                      'same captured model until actual dispatch')
            c.require(self.runtime['seals'].file_identity(path, b, desc['bytes']) ==
                      {'bytes': desc['bytes'], 'sha256': desc['sha256']},
                      'whole model body revalidated before actual dispatch')
        expected = set(self.provider['stamps']); directories = {''}
        for name in expected:
            directories.update(str(p) for p in Path(name).parents if str(p) != '.')
        actual = set()
        for directory, dirs, files in os.walk(self.provider['model'], followlinks=False):
            here = Path(directory)
            c.require(all(not (here/name).is_symlink() and
                str((here/name).relative_to(self.provider['model'])) in directories for name in dirs),
                'model directory namespace unchanged before dispatch')
            actual.update(str((here/name).relative_to(self.provider['model'])) for name in files)
            c.require(actual <= expected, 'no new undeclared model members before dispatch')
        c.require(actual == expected, 'complete unchanged model namespace before dispatch')
        b.admit('reserved local provider attempt', deadline)
        c.require(b.model_calls+1 <= b.limits['model_calls'], 'actual one-call external budget')
        b.model_calls += 1  # Sole external attempt debit. Parent joins once.
        self.parent = str(self.scope.path.relative_to('/sys/fs/cgroup'))
        context = SimpleNamespace(id=request['role'], sequence=request['sequence'],
                                  base=self.journal.root, registry=SimpleNamespace(source=self.source))
        invocation = dict(schema='neural055-provider-request-v3', role='investigator_decision',
            operation='generate', payload=dict(messages=messages, max_new_tokens=maximum),
            request_sha256=c.sha(c.encoded(request)), deadline=deadline)
        native = self.runtime['native_providers'].NativeProviders(self.host, self.observed,
            self.scope, self.parent, deadline, self.command, self.record, self.retire,
            self.argv_for, self.runtime['native'].admitted_container)
        custody = self.runtime['native_providers'].ProviderCustody()
        try:
            value, original = native.execute(context, self.provider, invocation, custody=custody)
            c.require(original is custody.original, 'actual original provider record')
            c.keys(value, ('schema', 'role', 'result', 'usage', 'request_sha256', 'source_identity'))
            c.require(value['schema'] == 'neural055-provider-result-v3' and
                      value['role'] == 'investigator_decision' and
                      value['request_sha256'] == invocation['request_sha256'] and
                      value['source_identity'] == self.source.identity, 'exact actual model response')
            c.keys(value['result'], ('text',)); c.require(type(value['result']['text']) is str, 'actual model text')
            u = value['usage']; c.keys(u, ('input_tokens', 'output_tokens', 'maximum_input_tokens',
                                         'maximum_output_tokens', 'cpu_placement'))
            c.require(u['maximum_input_tokens'] == request['token_reservation']['maximum_input'] and
                      u['maximum_output_tokens'] == maximum and
                      u['cpu_placement'] == 'same_original_native_cgroup', 'reserved token provenance')
            usage = {k: u[k] for k in ('input_tokens', 'output_tokens')}
            for key, cap in (('input_tokens', u['maximum_input_tokens']), ('output_tokens', maximum)):
                c.integer(usage[key], 0, cap)
            self.original.update(usage=usage, status='complete_original')
            return value['result']['text'].encode('utf-8'), usage
        finally:
            self.original['native'] = custody.original
