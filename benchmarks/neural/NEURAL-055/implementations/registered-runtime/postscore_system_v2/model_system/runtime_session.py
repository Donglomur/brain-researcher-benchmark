"""One actual S8 source/controller lifetime for offline F system construction."""
import hashlib
import importlib.util
from pathlib import Path
import sys

from source_closure import MANIFEST, RuntimeSupport, absolute, capture_runtime, need, parse, read_exact


class Support(RuntimeSupport):
    NAMES = ('common', 'registry', 'budget', 'journal', 'process', 'cgroup', 'source',
             'participant_contract', 'authority', 'native_providers', 'native',
             'seals', 'broker', 'resource_policy')


def module_file(name, path, *, expected=None, charge=None):
    """Load a selected companion source, never a submitted/generated programme."""
    path = absolute(path)
    spec = importlib.util.spec_from_file_location(name, path)
    need(spec is not None and spec.loader is not None, 'selected companion module')
    module = importlib.util.module_from_spec(spec)
    # A module may legitimately use dataclasses; retain its actual module owner.
    need(name not in sys.modules, 'fresh companion module name')
    sys.modules[name] = module
    try:
        if expected is None:
            need(charge is None, 'legacy metadata loader has no managed-byte claim')
            spec.loader.exec_module(module)
        else:
            need(callable(charge), 'explicit managed companion source accounting')
            raw = read_exact(path, expected, 131072, charge)
            # Production never consumes cached bytecode for these companions.
            exec(compile(raw, str(path), 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


class RuntimeSession:
    def __init__(self, spec, origin, cpu_origin, bootstrap_reads=0):
        self.spec = spec; self.support = None; self.host = None; self.result = None
        self.first_error = None; self.closed = False; self.host_summary = None
        self.source_root = absolute(spec['source_root'])
        self.operator_root = absolute(spec['operator_root'])
        self.output = absolute(spec['output'])
        need(self.operator_root.is_dir() and self.output != self.operator_root
             and self.output.is_relative_to(self.operator_root), 'fresh source bundle under actual operator root')
        limits = spec['limits']
        need(type(limits['read_bytes']) is int and limits['read_bytes'] > bootstrap_reads,
             'explicit whole bootstrap read allowance')
        context, reads = capture_runtime(self.source_root, MANIFEST, limits['read_bytes'] - bootstrap_reads)
        self.support = Support(context); self.modules = self.support.modules
        m = self.modules
        try:
            self.budget = m['budget'].Budget(origin, limits, cpu_origin=cpu_origin)
            self.budget.read(reads + bootstrap_reads)
            self.carrier = m['common'].FailureCarrier()
            self.journal = m['journal'].Journal(self.output, self.budget, self.carrier)
            self.runner = m['process'].ProcessRunner(self.budget, self.journal, self.carrier)
            # The unchanged Sources constructor performs its own complete capture
            # and role joins; both acquisitions are counted, never hidden.
            self.source = m['source'].Sources(self.source_root, context['source_manifest'], self.budget)
            definition_raw = self.source.bodies['contracts/RESOURCE_POLICY_V1.json']
            definition = parse(definition_raw)
            self.resource_identity = {'version': definition['schema'], 'bytes': len(definition_raw),
                                      'sha256': hashlib.sha256(definition_raw).hexdigest()}
            profile = spec['native_profile']
            # Original binding checks the exact definition, broker/profile
            # versions and full resource scope; this is identity metadata only,
            # never a fabricated campaign or participant cell.
            m['resource_policy'].bind({
                'resource_policy': self.resource_identity,
                'policy': {'resource_policy': self.resource_identity,
                           'broker_contract': 'neural055-trusted-host-broker-contract-v4'},
                'native_profile': profile,
                'runtime_environment': {'resource_policy': self.resource_identity},
            }, self.source, self.budget)
            self.authority = m['authority'].Authority(self.operator_root, spec['trust'], self.budget)
            need(self.authority.trust['source_identity'] == self.source.identity
                 and self.authority.trust['deployment_identity'] == profile['deployment_identity'],
                 'actual source and deployment trust')
            self.authority.verify(spec['runtime_qualification'], 'native_runtime_qualification', {
                'source': self.source.identity, 'native_profile': profile,
                'environment': spec['environment_identity'], 'limits': limits,
                'phase_limits': spec['phase_limits']})
            self.public_interface = m['participant_contract'].interface_identity(self.source)
            self.public_documents = {name: raw.decode('utf8') for name, raw in
                                     m['participant_contract'].selected_documents(self.source).items()}
            self.source.stage_actor_runtime(self.journal)
            self.budget.check('after complete offline source/bootstrap')
        except BaseException as error:
            self.first_error = error
            if hasattr(self, 'carrier'):
                self.carrier.fail(error, 'offline-bootstrap')
            # If the original Journal exists, preserve actual partial bootstrap.
            if hasattr(self, 'journal'):
                try:
                    self.journal.terminal({'schema': 'neural055-fi-system-terminal-v1', 'status': 'unavailable',
                                           'stage': 'bootstrap', 'errors': self.carrier.document(),
                                           'scientific_qualification_claimed': False})
                except BaseException as secondary:
                    self.carrier.fail(secondary, 'offline-bootstrap-terminal')
            self.support.close()
            raise

    def attach_host(self, host_type):
        need(self.host is None and not self.closed, 'one actual operator host')
        self.host = host_type(self.source, self.spec['native_profile'], self.operator_root,
                              self.authority, self.runner, self.journal, self.budget, self.carrier,
                              provider_id=self.spec['provider_id'], runtime=self.modules)
        return self.host

    def generate(self, label, messages, max_new_tokens):
        need(self.host is not None and not self.closed, 'actual offline model host attached')
        return self.host.generate(label, messages, max_new_tokens)

    def write(self, name, raw):
        return self.journal.write(name, raw)

    def json(self, name, value):
        return self.journal.json(name, value)

    def finish(self, result=None, error=None):
        """Keep first failures and actual post-publication counters in memory."""
        need(not self.closed, 'one original offline session finalization')
        first = error
        if first is not None:
            self.carrier.fail(first, 'offline-authoring')
        try:
            if self.host is not None:
                try:
                    self.host_summary = self.host.finish(result=result, error=error)
                except BaseException as exc:
                    self.carrier.fail(exc, 'offline-host-finalization')
                    if first is None:
                        first = exc
            terminal = {'schema': 'neural055-fi-system-terminal-v1',
                        'status': 'complete_source_bundle' if first is None else 'unavailable',
                        'result': result, 'host': self.host_summary, 'errors': self.carrier.document(),
                        'costs_before_terminal_publication': self.budget.snapshot(),
                        'post_terminal_costs_are_returned_to_caller_not_claimed_inside_own_body': True,
                        'source_method_review': 'genuine independent input still required before campaign',
                        'scientific_qualification_claimed': False, 'postscore_implemented': False}
            try:
                durable = self.journal.terminal(terminal)
                need(durable, 'durable actual offline terminal')
                self.budget.check('after complete offline terminal publication')
                self.result = {'terminal': terminal, 'actual_closed_costs': self.budget.snapshot(),
                               'actual_terminal_record': dict(self.journal.records[-1])}
            except BaseException as exc:
                self.carrier.fail(exc, 'offline-terminal-publication')
                if first is None:
                    first = exc
            if first is not None:
                raise first
            return self.result
        finally:
            self.closed = True
            self.support.close()
