"""Operator-only local model jobs on one original authoring lifetime.

The caller supplies the authenticated, captured S8 runtime namespace and its
actual owners. This is not an I cell, a BrokerLease, a Phase, or an authority
issuer. NativeProviders' legacy field names and TokenLedger's external scope
tag are retained verbatim and explicitly classified in the outer record.
"""
import os
import re
import sys
import types
import uuid
from pathlib import Path


class ModelJobFailure(Exception):
    def __init__(self, host, original):
        self.host = host
        self.original = original
        super().__init__('original offline model job unavailable')


class OperatorJobContext:
    """Only the actual attributes consumed by unchanged NativeProviders."""
    def __init__(self, registry, base, ident, sequence):
        self.registry = registry
        self.base = base
        self.id = ident
        self.sequence = sequence


class OperatorJob:
    def __init__(self, common, ident, label, sequence, origin, deadline):
        self.id = ident
        self.label = label
        self.sequence = sequence
        self.origin = origin
        self.deadline = deadline
        self.actor_deadline = None
        self.resources = []
        self.commands = []
        self.errors = common.FailureCarrier()
        self.native = None
        self.token_reservation = None
        self.request = None
        self.result = None
        self.usage = None
        self.cgroup = None
        self.cgroup_event_chunks = []
        self.cgroup_events_complete = False
        self.scope = None
        self.cpu = None
        self.accounting = None
        self.closed = False
        self.publication = None
        self.status = 'owned_before_admission'

    def document(self):
        return {
            'schema': 'neural055-original-offline-model-job-v1',
            'actual_scope': 'offline_f_authoring',
            'id': self.id, 'label': self.label, 'sequence': self.sequence,
            'origin': self.origin, 'deadline': self.deadline,
            'actor_deadline': self.actor_deadline,
            'status': self.status, 'request': self.request, 'result': self.result,
            'usage': self.usage, 'token_reservation': self.token_reservation,
            'resources': self.resources, 'native_provider_original': self.native,
            'commands': [x.document() for x in self.commands],
            'cgroup': None if self.cgroup is None else
                {k: v for k, v in self.cgroup.items() if k != 'original_events'},
            'cgroup_event_chunks': self.cgroup_event_chunks,
            'cgroup_events_complete': self.cgroup_events_complete,
            'raw_original_cgroup_object_retained': self.scope is not None,
            'accounting': self.accounting,
            'all_owned_native_resources_closed': self.closed,
            'errors': self.errors.document(), 'publication': self.publication,
            'legacy_compatibility': {
                'provider_role': 'investigator_decision',
                'external_ledger_scope': 'current_postscore_operation',
                'native_field_names': ['lease', 'original_phase'],
                'these_names_do_not_mean_a_cell_or_postscore_ran': True,
            },
        }


class ModelJobHost:
    def __init__(self, source, profile, operator_root, authority, runner,
                 journal, budget, carrier, *, runtime, provider_id):
        self.runtime = dict(runtime)
        self.source = source
        self.budget = budget
        self.journal = journal
        self.carrier = carrier
        self.runner = runner
        self.registry = None
        self.native_host = None
        self.provider = None
        self.originals = []
        self.labels = set()
        self.finished = False
        self.finish_record = None
        self.ready = False
        self.common = runtime['common']
        c = self.common
        required = ('common', 'budget', 'journal', 'process', 'cgroup',
                    'native_providers', 'native', 'seals', 'registry',
                    'broker', 'resource_policy', 'source', 'authority')
        c.require(type(runtime) is dict and all(k in runtime for k in required),
                  'complete captured original runtime modules')
        package = runtime['common'].__name__.rsplit('.', 1)[0]
        for name in required:
            module = runtime[name]
            c.require(type(module) is types.ModuleType and
                      module.__name__ == package + '.' + name and
                      sys.modules.get(module.__name__) is module,
                      'one captured runtime namespace')
        c.require(type(budget) is runtime['budget'].Budget and
                  type(journal) is runtime['journal'].Journal and
                  type(runner) is runtime['process'].ProcessRunner and
                  type(carrier) is c.FailureCarrier,
                  'actual original budget, journal, runner and carrier')
        c.require(journal.budget is budget and journal.carrier is carrier and
                  runner.budget is budget and runner.journal is journal and
                  runner.carrier is carrier, 'one original authoring lifetime')
        c.require(type(source) is runtime['source'].Sources and
                  type(authority) is runtime['authority'].Authority,
                  'actual captured source and external authority owners')
        c.require(source.budget is budget and authority.budget is budget,
                  'source and authority capture use the original offline budget')
        carrier.retain(self)  # Before source/model capture or any publication.
        self.profile = c.parse(c.encoded(profile))
        self.provider_id = provider_id
        self.base = journal.root / 'operator-model-jobs'
        self.origin = budget.origin
        self.deadline = budget.deadline
        try:
            budget.admit('before offline model host construction')
            c.require(budget.active_cell is None and budget.token_ledger is None,
                      'offline lifetime has no cell and no previous token ledger')
            specs = self.profile['model_providers']
            c.require(type(specs) is list and len(specs) == 1 and
                      specs[0]['id'] == provider_id and
                      specs[0]['kind'] == 'local_transformers_text_v1',
                      'one explicitly selected local model; no scientific bank')
            self.native_host = runtime['native'].DockerHost(
                self.profile, runner, journal, budget, carrier)
            self.registry = runtime['broker'].BrokerRegistry(
                self.profile, operator_root, source, authority, journal, budget)
            self.provider = self.registry.providers[provider_id]
            self._mkdir(self.base)
            journal.json('OFFLINE_MODEL_HOST.json', {
                'schema': 'neural055-offline-model-host-v1',
                'source': source.identity, 'provider': provider_id,
                'actual_scope': 'offline_f_authoring',
                'origin': self.origin, 'deadline': self.deadline,
                'same_budget_journal_runner': True,
                'provider_registry': self.registry.subject,
                'no_cell_lease_created': True,
                'external_token_scope_tag_is_legacy_compatibility': True,
                'resource_policy': budget.resource_policy,
                'whole_host_memory_qualified': False,
                'native_cumulative_logical_io_observed': False,
            })
            budget.check('after offline model host construction')
            self.ready = True
        except BaseException as original:
            carrier.fail(original, 'offline-model-host-construction')
            raise ModelJobFailure(self, original) from original

    def _mkdir(self, path):
        c = self.common
        self.budget.check('before owned operator directory')
        c.require(path.parent.is_dir() and not path.exists() and
                  path.is_relative_to(self.journal.root) and
                  not any(p.is_symlink() for p in (path.parent, *path.parents)),
                  'fresh literal owned operator directory')
        path.mkdir(mode=0o700)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.budget.check('after owned operator directory')

    def _descriptor(self, publication, role):
        c = self.common
        c.require(publication['status'] == 'complete' and publication['closed'] and
                  publication['expected_bytes'] == publication['observed_bytes'],
                  'actual complete durable publication')
        return {'path': publication['path'], 'bytes': publication['observed_bytes'],
                'sha256': publication['sha256'], 'mode': '0o600', 'role': role}

    def _summary(self, observed):
        return {'id': observed.id, 'label': observed.label,
                'sequence': observed.sequence, 'status': observed.status,
                'closed': observed.closed, 'usage': observed.usage,
                'receipt': None if observed.publication is None else
                    self._descriptor(observed.publication, 'offline_model_job_receipt'),
                'raw_original_object_retained_in_host': True}

    def generate(self, label, messages, max_new_tokens):
        c = self.common
        c.require(self.ready and not self.finished and self.carrier.first is None,
                  'live original host without an earlier failure')
        c.require(self.budget.origin == self.origin and
                  self.budget.deadline == self.deadline and
                  self.budget.active_cell is None, 'same offline lifetime')
        sequence = len(self.originals)
        ident = 'n055-offline-' + uuid.uuid4().hex
        observed = OperatorJob(c, ident, label, sequence,
                               self.budget.clock(), self.deadline)
        self.originals.append(observed)
        self.carrier.retain(observed)
        custody = self.runtime['native_providers'].ProviderCustody()
        scope = None
        scope_record = None
        receipt_reservation = None
        first = None
        value = None
        counter = 0

        def fail(error, stage):
            nonlocal first
            if first is None:
                first = error
            observed.errors.fail(error, stage)
            self.carrier.fail(error, stage + ':' + ident)

        def command(args, cap=131072, end=None, poll_service=None):
            nonlocal counter
            deadline = self.deadline if end is None else end
            c.require(deadline <= self.deadline, 'original job deadline only')
            name = ident + '-control-' + str(counter)
            counter += 1
            before = len(self.runner.originals)
            try:
                result = self.runner.run(
                    name, [self.profile['docker_binary'], '--host',
                           self.profile['docker_host'], *args], deadline, cap,
                    poll_service=poll_service)
                self.budget.check('after original model host control', deadline)
                return bytes(result.stdout)
            finally:
                for item in self.runner.originals[before:]:
                    if not any(item is old for old in observed.commands):
                        observed.commands.append(item)

        def record(kind, name):
            row = {'kind': kind, 'name': name, 'owner': ident,
                   'attempted': False, 'acknowledged': False, 'id': None,
                   'closed': True, 'disposition': 'not_dispatched',
                   'observations': []}
            observed.resources.append(row)
            return row

        def inspect(row):
            actual = self.runtime['native'].one(c.parse(command(
                ['container', 'inspect', row['id'] or row['name']])))
            self.runtime['native'].full_id(actual['Id'])
            c.require(actual['Name'] == '/' + row['name'] and
                      actual['Config']['Labels'].get('org.neurobench.n055') == ident,
                      'only original named and labelled provider')
            c.require(row['id'] is None or row['id'] == actual['Id'],
                      'same original provider instance')
            row['id'] = actual['Id']
            row['observations'].append({'id': actual['Id'],
                                        'state': dict(actual['State'])})
            return actual

        def retire(row):
            if not row['attempted']:
                return True
            try:
                state = inspect(row)['State']
                if state['Running']:
                    command(['container', 'kill', '--signal', 'KILL', row['id']], 4096)
                    row['forced'] = True
                if state['Status'] == 'created' and not state['Running']:
                    row['wait_disposition'] = 'created_no_process_to_wait'
                else:
                    waited = command(['container', 'wait', row['id']], 4096).strip()
                    c.require(re.fullmatch(b'[0-9]+', waited), 'original wait acknowledgment')
                    row['wait_exit'] = int(waited)
                state = inspect(row)['State']
                c.require(not state['Running'] and state['Pid'] == 0 and
                          state['Status'] in ('created', 'exited', 'dead'),
                          'original provider stopped before removal')
                if 'wait_exit' in row:
                    c.require(row['wait_exit'] == state['ExitCode'],
                              'original wait agrees with terminal state')
                if 'natural_state' in row:
                    c.require(all(state[k] == row['natural_state'][k] for k in
                                  ('Status', 'Running', 'Dead', 'Pid', 'ExitCode',
                                   'OOMKilled', 'Error')), 'original natural state preserved')
                row['terminal_state'] = dict(state)
                c.require(command(['container', 'rm', row['id']], 4096).strip() ==
                          row['id'].encode(), 'original removal acknowledgment')
                c.require(command(['container', 'ls', '-a', '--no-trunc', '--filter',
                                   'name=^/' + row['name'] + '$', '--format', '{{.ID}}'],
                                  4096).strip() == b'', 'original provider absent')
                row.update(closed=True, disposition='original_removed_absent')
                return True
            except BaseException as error:
                row['disposition'] = 'unresolved_creation_or_retirement'
                fail(error, 'provider-retirement')
                return False

        def argv_for(row, binds, destination, args):
            c.require(destination is None, 'offline model has no writable output volume')
            argv = ['container', 'create', '--pull', 'never', '--name', row['name'],
                    '--label', 'org.neurobench.n055=' + ident, '--cgroup-parent', parent,
                    '--cpus', '1', '--memory', str(self.profile['memory_bytes']),
                    '--memory-swap', str(self.profile['memory_bytes']),
                    '--pids-limit', str(self.profile['pids']), '--network', 'none',
                    '--cgroupns', 'private', '--ipc', 'private', '--read-only',
                    '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt',
                    'no-new-privileges', '--restart', 'no', '--log-driver', 'none',
                    '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=' + str(self.profile['scratch_bytes']),
                    '--ulimit', 'core=0:0', '--ulimit', 'nofile=128:128',
                    '--ulimit', 'fsize=536870912:536870912']
            c.require(set(binds) == {'/request.json', '/config.json', '/runtime', '/model'}
                      and all(not writable for _, writable in binds.values()),
                      'only model, exact request/config and captured runtime mounts')
            for destination_, (path, _) in binds.items():
                argv += ['--mount', 'type=bind,src=' + str(path) + ',dst=' + destination_ + ',readonly']
            for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                        'NUMEXPR_NUM_THREADS'):
                argv += ['--env', key + '=1']
            return argv + ['--entrypoint', 'python', self.profile['image'], *args]

        try:
            self.budget.admit('before original offline model job')
            c.require(type(label) is str and re.fullmatch('[a-zA-Z0-9_-]{1,64}', label)
                      and label not in self.labels, 'unique finite authoring label')
            self.labels.add(label)
            c.require(type(messages) is list and 0 < len(messages) <= 128 and
                      all(type(m) is dict and set(m) == {'role', 'content'} and
                          m['role'] in ('user', 'assistant') and type(m['content']) is str
                          for m in messages), 'finite user/assistant conversation only')
            config = self.provider['config']
            c.require(sum(len(m['content'].encode('utf-8')) for m in messages) <=
                      config['request_bytes'], 'complete author conversation bound')
            c.require(type(max_new_tokens) is int and
                      0 < max_new_tokens <= config['maximum_output_tokens'],
                      'explicit finite output token cap')
            observed.actor_deadline = self.deadline - self.profile['closure_reserve_seconds']
            c.require(self.budget.clock() < observed.actor_deadline,
                      'closure reserve inside original authoring lifetime')
            receipt_reservation = ident + '-receipt'
            self.budget.reserve(receipt_reservation, 131072, 2)
            self.registry.unchanged(self.provider)
            self.budget.admit('after original source/model revalidation')
            request = {'schema': 'neural055-offline-authoring-request-v1',
                       'actual_scope': 'offline_f_authoring', 'sequence': sequence,
                       'label': label, 'source': self.source.identity,
                       'provider': self.provider_id,
                       'payload': {'messages': messages, 'max_new_tokens': max_new_tokens},
                       'original_deadline': self.deadline}
            raw = c.encoded(request)
            c.require(len(raw) <= 1048576, 'complete bounded offline request')
            observed.request = self.journal.write(ident + '-REQUEST.json', raw)
            c.require(self.budget.model_calls < self.budget.limits['model_calls'],
                      'same offline lifetime model-call cap')
            observed.token_reservation = self.registry.ledger.reserve_external(
                config['maximum_input_tokens'], max_new_tokens)
            self.budget.model_calls += 1  # Attempt reservation; never reset/refunded.
            info = c.parse(command(['info', '--format', '{{json .}}'], end=observed.actor_deadline))
            c.require(info['ID'] == self.profile['daemon_id'] and info['OSType'] == 'linux'
                      and info['CgroupVersion'] == '2' and info['CgroupDriver'] == 'cgroupfs',
                      'exact selected local Linux daemon')
            image = self.runtime['native'].one(c.parse(command(
                ['image', 'inspect', self.profile['image']], end=observed.actor_deadline)))
            c.require(image['Id'] == self.profile['image'] and not image['Config'].get('Volumes')
                      and (not image['Config'].get('Healthcheck') or
                           image['Config']['Healthcheck'].get('Test') == ['NONE']),
                      'cached image without implicit volume/health producers')
            scope = self.runtime['cgroup'].Cgroup(self.profile['delegated_cgroup_root'],
                                                ident, self.budget, self.deadline)
            observed.scope = scope
            observed.errors.retain(scope)
            scope_record = record('cgroup', str(scope.path))
            scope_record.update(attempted=True, closed=False, disposition='creation_pending')
            scope.create(self.profile['memory_bytes'], self.profile['pids'])
            scope_record.update(acknowledged=True, disposition='created')
            parent = str(scope.path.relative_to('/sys/fs/cgroup'))
            native = self.runtime['native_providers'].NativeProviders(
                self.native_host, observed, scope, parent, observed.actor_deadline,
                command, record, retire, argv_for, self.runtime['native'].admitted_container)
            context = OperatorJobContext(self.registry, self.base, ident, sequence)
            invocation = {'schema': 'neural055-provider-request-v3',
                          'role': 'investigator_decision', 'operation': 'generate',
                          'payload': request['payload'], 'request_sha256': c.sha(raw),
                          'deadline': observed.actor_deadline}
            value, original = native.execute(context, self.provider, invocation, custody=custody)
            c.require(original is custody.original, 'same original native provider object')
            observed.native = original
            c.keys(value, ('schema', 'role', 'result', 'usage', 'request_sha256', 'source_identity'))
            c.require(value['schema'] == 'neural055-provider-result-v3' and
                      value['role'] == 'investigator_decision' and
                      value['request_sha256'] == c.sha(raw) and
                      value['source_identity'] == self.source.identity,
                      'actual captured provider/result identity')
            c.keys(value['result'], ('text',))
            c.require(type(value['result']['text']) is str, 'actual model text')
            usage = value['usage']
            c.keys(usage, ('input_tokens', 'output_tokens', 'maximum_input_tokens',
                           'maximum_output_tokens', 'cpu_placement'))
            c.require(usage['maximum_input_tokens'] == config['maximum_input_tokens'] and
                      usage['maximum_output_tokens'] == max_new_tokens and
                      usage['cpu_placement'] == 'same_original_native_cgroup',
                      'actual token and resource bound identity')
            observed.usage = {k: usage[k] for k in ('input_tokens', 'output_tokens')}
            self.registry.ledger.settle_external(observed.token_reservation, observed.usage)
            observed.result = self.journal.json(ident + '-RESULT.json', value)
            self.budget.check('after original offline provider result')
        except BaseException as error:
            fail(error, 'offline-generate')
            self.registry.ledger.uncertain(observed.token_reservation, error)
        finally:
            if custody.original is not None:
                observed.native = custody.original
            if scope is not None and scope.created:
                try:
                    observed.cgroup = scope.finish()
                    observed.cpu = observed.cgroup['cpu_seconds']
                    scope_record.update(closed=True, disposition='original_subtree_empty_removed')
                except BaseException as error:
                    fail(error, 'offline-final-cgroup')
                    observed.cgroup = scope.final
                    if scope.final is not None and scope.final.get('cpu_complete'):
                        observed.cpu = scope.final['cpu_seconds']
                    try:
                        scope.emergency_kill()
                    except BaseException as secondary:
                        fail(secondary, 'offline-emergency-cgroup')
            elif not any(r['attempted'] for r in observed.resources):
                observed.cpu = 0.0  # Observed no native resource dispatch; host commands are separate.
            observed.closed = all(r['closed'] for r in observed.resources)
            end = None
            try:
                end = self.budget.clock()
            except BaseException as error:
                fail(error, 'offline-final-clock')
            memory = (observed.cgroup.get('memory_peak_bytes') if observed.cgroup is not None
                      else 0 if not any(r['attempted'] for r in observed.resources) else None)
            observed.accounting = {
                'kind': 'offline_model_provider', 'cpu_seconds': observed.cpu,
                'wall_seconds': None if end is None else end - observed.origin,
                'memory_peak_bytes': memory,
                'memory_scope': 'owned_model_container_subtree_only',
                'controller_and_docker_daemon_memory_not_observed': True,
                'all_native_resources_closed': observed.closed,
                'native_cumulative_logical_io_observed': False,
                'read_bytes': None, 'write_bytes': None, 'files': None,
                'resource_policy': self.budget.resource_policy,
            }
            try:
                self.budget.physical(ident, observed.accounting)
                for quantity, answer in (('wall_seconds', end), ('memory_peak_bytes', memory)):
                    if answer is None:
                        self.budget.uncertain(ident, quantity)
                c.require(observed.closed, 'all original model resources closed')
                self.budget.check('after original model resource accounting')
            except BaseException as error:
                fail(error, 'offline-final-accounting')
            observed.status = 'complete_original' if first is None else 'unavailable_original'
            if scope is not None:
                try:
                    # Do not put an unbounded poll history in the 64KiB receipt.
                    # Every original counter/control event is retained and written
                    # in order; all bytes/files consume this original lifetime.
                    chunk = []
                    start = 0
                    events = scope.events
                    for event in events:
                        candidate = chunk + [event]
                        body = c.encoded({'job': ident, 'start': start, 'events': candidate})
                        if len(body) > 65536 and chunk:
                            item = self.journal.json(
                                ident + '-CGROUP-' + str(len(observed.cgroup_event_chunks)) + '.json',
                                {'job': ident, 'start': start, 'events': chunk},
                                emergency=first is not None)
                            observed.cgroup_event_chunks.append(item)
                            start += len(chunk)
                            chunk = [event]
                        else:
                            chunk = candidate
                        c.require(len(c.encoded({'job': ident, 'start': start,
                                                'events': chunk})) <= 65536,
                                  'one bounded original cgroup event')
                    if chunk:
                        item = self.journal.json(
                            ident + '-CGROUP-' + str(len(observed.cgroup_event_chunks)) + '.json',
                            {'job': ident, 'start': start, 'events': chunk},
                            emergency=first is not None)
                        observed.cgroup_event_chunks.append(item)
                        start += len(chunk)
                    c.require(start == len(events), 'all original cgroup events published')
                    observed.cgroup_events_complete = True
                except BaseException as error:
                    fail(error, 'offline-cgroup-event-publication')
            if receipt_reservation is not None:
                try:
                    body = c.encoded(observed.document())
                    c.require(len(body) <= 65536, 'bounded complete original job receipt')
                    observed.publication = self.journal.write(
                        ident + '-JOB.json', body, reservation=receipt_reservation,
                        emergency=first is not None)
                except BaseException as error:
                    fail(error, 'offline-job-publication')
                    try:
                        observed.publication = self.journal.json(
                            ident + '-JOB_FAILURE.json', {
                                'id': ident, 'status': 'unavailable_original',
                                'closed': observed.closed,
                                'original_errors': observed.errors.document(),
                                'raw_job_and_commands_retained_in_host': True,
                            }, reservation=receipt_reservation, emergency=True)
                    except BaseException as secondary:
                        fail(secondary, 'offline-job-failure-publication')
                finally:
                    self.budget.reservations.pop(receipt_reservation, None)
            try:
                self.budget.check('after complete original model publication')
            except BaseException as error:
                fail(error, 'offline-post-publication')
        if first is not None:
            observed.status = 'unavailable_original'
            raise ModelJobFailure(self, observed) from first
        return {'text': value['result']['text'], 'usage': dict(observed.usage),
                'operation': self._summary(observed)}

    def finish(self, result=None, error=None):
        c = self.common
        c.require(not self.finished, 'one original model host finish')
        self.finished = True
        if error is not None:
            self.carrier.fail(error, 'offline-author-caller')
        value = {
            'schema': 'neural055-offline-model-host-finish-v1',
            'actual_scope': 'offline_f_authoring',
            'origin': self.origin, 'deadline': self.deadline,
            'provider': self.provider_id, 'result': result,
            'jobs': [self._summary(x) for x in self.originals],
            'errors': self.carrier.document(),
            'all_owned_model_resources_closed': all(x.closed for x in self.originals),
            'whole_host_memory_qualified': False,
            'native_cumulative_logical_io_observed': False,
            'parent_publication_remains_on_same_budget': True,
        }
        self.finish_record = value
        try:
            account = self.journal.json('OFFLINE_MODEL_HOST_ACCOUNTING.json',
                                        self.budget.snapshot(),
                                        emergency=self.carrier.first is not None)
            value['accounting_receipt'] = self._descriptor(account, 'offline_model_host_accounting')
            publication = self.journal.json('OFFLINE_MODEL_HOST_FINISH.json', value,
                                           emergency=self.carrier.first is not None)
            self.budget.check('after original model host finish')
        except BaseException as original:
            self.carrier.fail(original, 'offline-host-finish-publication')
            raise ModelJobFailure(self, value) from original
        return {'schema': 'neural055-offline-model-host-summary-v1',
                'actual_scope': 'offline_f_authoring',
                'origin': self.origin, 'deadline': self.deadline,
                'jobs': len(self.originals),
                'status': 'complete_original' if self.carrier.first is None else 'unavailable_original',
                'receipt': self._descriptor(publication, 'offline_model_host_finish'),
                'accounting_receipt': value['accounting_receipt'],
                'all_owned_model_resources_closed': value['all_owned_model_resources_closed'],
                'whole_host_memory_qualified': False,
                'native_cumulative_logical_io_observed': False,
                'raw_original_objects_retained_in_host': True,
                'costs_through_host_finish_publication': self.budget.cost_point(),
                'parent_publication_remains_on_same_budget': True}
