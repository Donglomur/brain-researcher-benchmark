"""Concrete v2 role dispatch and original-controller publication.

No signing authority or generated-code import is provided here. The provider
worker publishes the actual role result before closing; this owner accounts
and authenticates the later control work on the existing campaign Budget.
"""
import importlib
import math
import os
from pathlib import Path
import stat
import time

from .common import (require, keys, integer, finite, relative, descriptor,
                     capture, parse, encoded, sha, pin, stamp, diagnostic_type)
from .postscore_policy import (SCHEMA, RESPONSE_SCHEMA, OPERATION_SCHEMA,
                               RESOURCE_SCOPE, resource_identity, execution_subject)
from . import postscore_services as services

RESOURCES = ('cpu_seconds', 'read_bytes', 'write_bytes', 'files', 'stream_bytes', 'model_calls')
RUNTIME_NAMES = ('common', 'budget', 'journal', 'process', 'cgroup', 'native',
                 'native_providers', 'resource_policy', 'registry', 'seals',
                 'postscore_services', 'source', 'authority')


def completed_descriptor(journal, root, record, role):
    require(record['status'] == 'complete' and record['closed'] is True
            and record['observed_bytes'] == record['expected_bytes'],
            'actual complete publication before descriptor binding')
    path = journal.root / str(relative(record['path']))
    require(path.is_relative_to(root), 'one operator-relative publication namespace')
    return {'path': str(path.relative_to(root)), 'bytes': record['observed_bytes'],
            'sha256': record['sha256'], 'mode': '0o600', 'role': role}


def root_descriptor(journal, root, item):
    descriptor(item)
    path = journal.root / str(relative(item['path']))
    require(path.is_relative_to(root), 'closed role artifact under original operator root')
    return dict(item, path=str(path.relative_to(root)))


def await_ordinary(root, name, maximum, budget, carrier, deadline):
    """One finite exact inbox; retain raw read/close failures before publication."""
    path = root / str(relative(name))
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
            'literal protected current qualification inbox')
    while True:
        budget.check('waiting for current independent qualification', deadline)
        try:
            before = path.lstat()
        except FileNotFoundError:
            time.sleep(min(.05, max(0, deadline - budget.clock())))
            continue
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= maximum and stat.S_IMODE(before.st_mode) == 0o600,
                'bounded ordinary private current qualification')
        observation = {'path': str(path), 'before': stamp(before), 'raw': bytearray(),
                       'closed': False, 'errors': []}
        carrier.retain(observation)
        fd = None; first = None
        budget.admit_read(before.st_size + 1)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            require(stamp(os.fstat(fd)) == stamp(before), 'same original qualification handle')
            while len(observation['raw']) <= before.st_size:
                chunk = os.read(fd, min(65536, before.st_size + 1 - len(observation['raw'])))
                observation['raw'].extend(chunk)
                budget.read(len(chunk))
                budget.check('after qualification prefix capture', deadline)
                if not chunk:
                    break
            require(len(observation['raw']) == before.st_size
                    and stamp(os.fstat(fd)) == stamp(before) == stamp(path.lstat()),
                    'one complete stable qualification body')
        except BaseException as error:
            first = error; observation['errors'].append(('read', error))
            carrier.fail(error, 'postscore-qualification-capture')
        finally:
            if fd is not None:
                try:
                    os.close(fd); observation['closed'] = True
                except BaseException as error:
                    observation['errors'].append(('close', error))
                    carrier.fail(error, 'postscore-qualification-close')
                    budget.uncertain('postscore-qualification:' + name,
                                     'managed_descriptor_closure', error, descriptor=fd)
                    if first is None:
                        first = error
        if first is not None:
            raise first
        raw = bytes(observation['raw'])
        return raw, {'path': name, **pin(raw), 'mode': '0o600',
                     'role': 'current_independent_qualification'}


def _known(value, kind):
    if kind == 'cpu_seconds':
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    return type(value) is int and value >= 0


class LocalPostscoreDispatcher:
    def __init__(self, plan, source, root, authority, journal, budget, carrier):
        require(plan['interpretation']['schema'] == SCHEMA, 'explicit prospective local reporting')
        self.plan = plan; self.policy = plan['interpretation']; self.source = source
        self.root = Path(root); self.authority = authority; self.journal = journal
        self.budget = budget; self.carrier = carrier; self.originals = []; self.joins = {}
        require(self.root.is_absolute() and journal.root.is_relative_to(self.root)
                and journal.root != self.root, 'fresh campaign journal beneath one operator root')
        require(source.budget is budget and authority.budget is budget and journal.budget is budget,
                'one original campaign accounting owner')
        self.resource = resource_identity(source)
        raw = capture(self.root, self.policy['execution']['source'], budget, 1048576)
        self.configuration = parse(raw)
        keys(self.configuration, ('schema', 'deployment', 'qualification_directory'))
        require(self.configuration['schema'] == 'neural055-local-postscore-execution-v2',
                'closed selected local execution configuration')
        self.deployment = self.configuration['deployment']
        require(self.deployment['operator_root'] == str(self.root)
                and self.deployment['whole_memory_bytes'] == self.policy['memory_bytes'],
                'exact operator and selected whole memory cap')
        self.inbox = self.root / str(relative(self.configuration['qualification_directory']))
        require(self.inbox.is_dir() and not any(p.is_symlink() for p in (self.inbox, *self.inbox.parents)),
                'preexisting protected independent qualification inbox')
        self.mailbox = self.root / str(relative(self.policy['control_directory']))
        require(self.mailbox.is_relative_to(journal.root) and self.mailbox != journal.root
                and not self.mailbox.exists(), 'fresh source-owned mailbox beneath current journal')
        self.authority.verify(self.policy['execution']['qualification'],
                              'postscore_execution_runtime_qualification',
                              execution_subject(plan, source, self.configuration))
        self.runtime = {name: importlib.import_module(__package__ + '.' + name)
                        for name in RUNTIME_NAMES}
        from .postscore_role_host import admit_controller
        self.controller = admit_controller(self.runtime, budget, journal, carrier, self.deployment)
        self.host = None
        # Directory namespace is controller-owned; ordinary body creation uses Journal.
        self.mailbox.mkdir(mode=0o700, parents=True)
        (journal.root / 'postscore-subjects').mkdir(mode=0o700)
        (journal.root / 'postscore-operations').mkdir(mode=0o700)
        budget.check('after actual reporting controller admission')

    def selected(self, item, maximum):
        descriptor(item)
        return capture(self.root, item, self.budget, maximum)

    def service(self, role, selected):
        value = parse(self.selected(selected['source'], 16777216))
        services.admit_service(value, role, selected, self.source.identity)
        for name, path in (('dispatcher', 'n055/postscore_dispatch.py'),
                           ('role_adapter', 'n055/postscore_role_host.py')):
            item = value['code'][name]
            require(item['path'] == path and path in self.source.bodies
                    and {k: item[k] for k in ('bytes', 'sha256')} == pin(self.source.bodies[path])
                    and item['mode'] == self.source.descriptors[path]['mode'],
                    'actual selected transitive service source body')
        deployment = parse(self.selected(value['deployment'], 1048576))
        require(deployment == self.deployment, 'same prequalified actual role deployment')
        return value

    def render(self, request, manifest):
        prompt = self.selected(manifest['prompt'], 1048576)
        aggregate = self.selected(request['aggregate'], 16777216)
        kwargs = {}
        if request['role'].startswith('reviewer_'):
            kwargs['report_bytes'] = self.selected(request['input'], 16777216)
        elif request['role'] == 'adjudicator':
            body = self.selected(request['input'], 16777216); value = parse(body)
            keys(value, ('schema', 'aggregate', 'report', 'judgments', 'comparisons', 'rubric'))
            require(value['schema'] == 'neural055-current-adjudication-input-v1'
                    and value['aggregate'] == request['aggregate']
                    and type(value['judgments']) is list and len(value['judgments']) == 2,
                    'current source-owned adjudication input')
            kwargs.update(adjudication_input_bytes=body,
                          report_bytes=self.selected(value['report'], 16777216),
                          judgment_bytes=tuple(self.selected(item, 16777216) for item in value['judgments']),
                          reviewer_identities=tuple(x['identity'] for x in self.policy['reviewers']))
        rendered = services.render_role(
            request, manifest, prompt, aggregate,
            contrast_registry_bytes=self.source.bodies['contracts/CONTRASTS.json'], **kwargs)
        return {name: rendered[name] for name in ('messages', 'authorized_inputs', 'response_contract')} | {
            'output_policy': manifest['output_policy']}

    def join_external(self, owned, observation):
        """Retain/debit every known actual prefix once, even on a failure."""
        digest = owned['request_pin']['sha256']
        require(digest not in self.joins and type(observation) is dict,
                'one actual external role observation owner')
        costs = observation.get('costs')
        lower = observation.get('known_lower_bounds', {})
        require(type(costs) is dict and set(costs) == set(RESOURCES)
                and type(lower) is dict and set(lower) <= set(RESOURCES),
                'explicit six external quantities; absent is not zero')
        row = {'request_sha256': digest, 'original': observation, 'joined': {},
               'unknown': [], 'errors': [], 'complete': False}
        self.joins[digest] = row; owned['external_join'] = row; self.carrier.retain(row)
        values = {}
        for kind in RESOURCES:
            value = costs[kind]
            if _known(value, kind):
                values[kind] = value
            elif value is None and kind in lower and _known(lower[kind], kind):
                values[kind] = lower[kind]
                row['unknown'].append(kind)
            else:
                values[kind] = None
                row['unknown'].append(kind)
        ident = 'postscore-v2-role-' + digest
        first = None
        try:
            self.budget.physical(ident, {'kind': 'postscore_closed_role',
                'cpu_seconds': values['cpu_seconds'],
                'closed_role_only': True, 'original_request': owned['request_pin'],
                'quantity_status': 'complete' if observation.get('costs_complete') is True else 'known_prefix'})
        except BaseException as error:
            first = error; row['errors'].append(error)
        # Do not lose other known quantities if a physical/admission check failed.
        for kind in RESOURCES[1:]:
            if values[kind] is not None:
                setattr(self.budget, kind, getattr(self.budget, kind) + values[kind])
        if values['write_bytes'] is not None:
            self.budget.live_bytes += values['write_bytes']
            row['managed_live_upper_bound_debit'] = values['write_bytes']
        if self.budget.resource_policy is not None:
            from .resource_policy import unobserved
            self.budget.native_unobserved.extend(unobserved(ident, self.budget.resource_policy))
        row['joined'] = dict(values)
        for kind in row['unknown']:
            self.budget.unknown.append({'operation': ident, 'quantity': 'closed_role_' + kind,
                                        'known_lower_bound': values[kind], 'observed': None})
        row['complete'] = (observation.get('costs_complete') is True
                           and observation.get('unknown_quantities') == [] and not row['unknown'])
        row['costs'] = dict(costs)
        if not row['complete']:
            self.budget.unknown.append({'operation': ident, 'quantity': 'closed_role_completion',
                                        'observed': None})
        if first is not None:
            raise first
        rb, rf = self.budget.reserved(); cb, cf = self.budget.capacity()
        require(self.budget.write_bytes + rb <= self.budget.limits['write_bytes']
                and self.budget.live_bytes + rb + cb <= self.budget.limits['live_bytes']
                and self.budget.files + rf + cf <= self.budget.limits['files'],
                'actual role debit preserves original finalization and live capacity reservations')
        self.budget.check('after once-only closed role cost join')
        return row

    def qualification(self, sequence, role, kind, subject, deadline):
        short = 'blinding' if kind == 'postscore_blinded_report' else 'operation'
        name = '%02d-%s.%s.json' % (sequence, role, short)
        record = self.journal.json('postscore-subjects/' + name, {
            'schema': 'neural055-current-independent-subject-v2', 'kind': kind,
            'subject': subject, 'subject_sha256': sha(encoded(subject)),
            'deadline': deadline, 'no_signing_key_or_authority_created': True})
        self.carrier.retain(record)
        inbox_name = str((self.inbox / name).relative_to(self.root))
        raw, item = await_ordinary(self.root, inbox_name, 4194304,
                                  self.budget, self.carrier, deadline)
        actual = self.authority.verify_bytes(raw, kind, subject)
        return item, actual

    def complete_current(self, handoff, owned, selected):
        request = owned['request']; role = request['role']; digest = owned['request_pin']['sha256']
        require(sha(encoded(request)) == digest and request['postscore_resource_policy'] == self.resource,
                'same original visible request and typed resource definition')
        self.budget.admit('actual current role dispatch', handoff.deadline)
        record = {'request': owned, 'role': role, 'response': None, 'native': None,
                  'source_qualification': None, 'status': 'owned_before_role'}
        self.originals.append(record); self.carrier.retain(record)
        try:
            manifest = self.service(role, selected)
            payload = self.render(request, manifest)
            if self.host is None:
                from .postscore_role_host import RoleHost
                self.host = RoleHost(self.runtime, self.budget, self.journal, self.carrier,
                                     self.source, self.controller, self.deployment, authority=self.authority)
            try:
                actual = self.host.run(request, manifest['provider'], payload)
            except BaseException as error:
                original = getattr(error, 'original', None)
                if type(original) is dict and 'costs' in original:
                    try:
                        self.join_external(owned, original)
                    except BaseException as secondary:
                        self.carrier.fail(secondary, 'postscore-failed-role-cost-join')
                else:
                    self.budget.unknown.append({'operation': digest, 'quantity': 'closed_role_cost_observation',
                                                'observed': None})
                raise
            record['native'] = actual
            require(type(actual) is dict, 'actual closed role result')
            observation = actual.get('original')
            require(type(observation) is dict, 'retained actual role owner')
            join = self.join_external(owned, observation)
            require(actual.get('complete') is True and join['complete']
                    and actual['request_sha256'] == digest, 'complete current role, no required unknown')
            require(actual['costs'] == join['costs'], 'one original external cost vector')
            require(actual['costs']['model_calls'] == 1, 'one original role generation, no retry')
            result = root_descriptor(self.journal, self.root, actual['result'])
            raw = self.selected(result, self.policy['result_bytes'])
            require(raw == actual['result_bytes'], 'actual complete role-published result')
            value = parse(raw)
            trusted = payload['authorized_inputs']
            # The provider worker used the same pure validator/binder. Consumer
            # validation below remains authoritative for the original schemas.
            usage = actual['usage']
            keys(usage, ('input_tokens', 'output_tokens'))
            for name in usage:
                integer(usage[name])
                require(usage[name] <= request['token_reservation']['maximum_' + name.split('_')[0]],
                        'actual usage within original prior reservation')
            processes = [root_descriptor(self.journal, self.root, item)
                         for item in actual['original_processes']]
            require(processes and len({p['sha256'] for p in processes}) == len(processes),
                    'complete distinct actual role process census')
            actual_processes = [parse(self.selected(item, 4194304)) for item in processes]
            require(all(item['natural'] is True and item['reaped'] is True
                        and item['group_absent'] is True and item['returncode'] == 0
                        and actual['origin'] <= item['origin'] <= item['end'] <= actual['end']
                        for item in actual_processes), 'actual closed natural role process records')
            observation_pin = root_descriptor(self.journal, self.root, actual['role_observation'])
            observation_body = parse(self.selected(observation_pin, 4194304))
            require(type(observation_body) is dict, 'actual durable role/cgroup/daemon evidence')
            record['role_observation_body'] = observation_body

            operation = {'schema': OPERATION_SCHEMA, 'resource_policy': self.budget.resource_policy,
                'postscore_resource_policy': self.resource, 'resource_scope': RESOURCE_SCOPE,
                'source': self.source.identity, 'actor': selected['identity'], 'actor_source': selected['source'],
                'request_sha256': digest, 'aggregate': request['aggregate'], 'input': request['input'],
                'result': result, 'clock_domain': self.policy['clock_domain'],
                'origin': actual['origin'], 'end': actual['end'],
                'natural': all(item['natural'] for item in actual_processes),
                'reaped': all(item['reaped'] for item in actual_processes),
                'descendants_absent': all(item['group_absent'] for item in actual_processes),
                'status': 'closed_role_original', 'unknown': [],
                'role_costs': actual['costs'], 'original_processes': processes,
                'role_observation': observation_pin,
                'memory': actual['memory'], 'token_usage': usage,
                'controller_finalization': 'actual continuing original Budget; not future costs inside this receipt'}
            op_record = self.journal.json('postscore-operations/%02d-%s.json' % (request['sequence'], role), operation)
            operation_pin = completed_descriptor(self.journal, self.root, op_record, 'closed_role_operation')
            response = {'schema': RESPONSE_SCHEMA, 'role': role, 'request_sha256': digest,
                        'actor': selected['identity'], 'actor_source': selected['source'],
                        'result': result, 'original_operation': operation_pin}
            if role == 'author':
                subject = services.blinded_report_subject(
                    self.source.identity, handoff.campaign, handoff.aggregate, result,
                    [x['identity'] for x in self.policy['reviewers']])
                response['blinding_qualification'], record['blinding_qualification'] = self.qualification(
                    request['sequence'], role, 'postscore_blinded_report', subject, handoff.deadline)
            subject = services.operation_subject(
                self.source.identity, handoff.campaign, self.budget.origin, self.policy,
                owned['request_pin'], response, handoff.aggregate, request['input'], selected)
            response['qualification'], record['source_qualification'] = self.qualification(
                request['sequence'], role, 'postscore_scientific_interpretation_operation', subject, handoff.deadline)
            body = encoded(response)
            require(len(body) <= self.policy['response_bytes'], 'whole original response ceiling')
            path = self.mailbox / ('%02d-%s.json' % (request['sequence'], role))
            publication = self.journal.write(str(path.relative_to(self.journal.root)), body)
            record.update(response=response, response_publication=publication, operation=operation,
                          status='complete_local_response', actual_controller_checkpoint=self.budget.cost_point())
            owned['local_response_owner'] = record
            handoff.check('after actual role and finalizer publication')
            return record
        except BaseException as error:
            record['status'] = 'unavailable'; record['first_error'] = error
            self.carrier.fail(error, 'postscore-current-role')
            raise


def prepare_dispatcher(plan, source, root, authority, journal, budget, carrier):
    if not (type(plan['interpretation']) is dict and plan['interpretation'].get('schema') == SCHEMA):
        return None
    return LocalPostscoreDispatcher(plan, source, root, authority, journal, budget, carrier)

