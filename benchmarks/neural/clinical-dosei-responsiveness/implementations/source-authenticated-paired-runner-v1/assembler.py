"""Thin host assembly of the existing two-arm controller and grading APIs.

Construction is not execution admission. The caller authenticates this package,
loads inherited roles with dependencies.py, supplies immutable metadata bodies,
and owns bounded original evidence, provider transport and external deadlines.
Only the explicit run method projects observations or invokes participants.
"""
import hashlib
import types

QUALIFICATION_SHA256 = 'c713b5519939984aa16210ad05a242dbc6cdc94ae73b530c63f15e264bf9c079'
PROCESS_V2_SHA256 = 'afae111f8dec293391bbf077cd0d700e8061328d5541f5d116ade63c1cf7d219'


class AssemblyRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AssemblyRefusal(message)


def environment_bytes(modules, data, *, call_wall_seconds, max_calls):
    """Prospective assistance declaration, identical in both controller budgets."""
    require(type(call_wall_seconds) is int and 1 <= call_wall_seconds <= 60 and
            type(max_calls) is int and 1 <= max_calls <= 128, 'exact prospective tool limits')
    return modules['controller'].canonical({
        'schema': 'dosei_authenticated_analysis_environment_v1',
        'runtime_profile_sha256': hashlib.sha256(data['runtime_profile']).hexdigest(),
        'owned_code_process_sha256': PROCESS_V2_SHA256,
        'code_backend_sha256': '1a8d96d57e325db0aacd31f2abf8b92ba20de8821bf065aee6b6ef8a9ba3bd9a',
        'qualification_saved_proof_sha256': QUALIFICATION_SHA256,
        'call_wall_seconds': call_wall_seconds, 'max_code_calls_per_case': max_calls,
        'tools': [modules['code_backend'].TOOL],
        'qualification_scope': 'six_fixed_engineering_controls_not_general_isolation',
        'provider_backend_qualified': False})


def _qualify(raw, modules):
    require(type(raw) is bytes and len(raw) <= 131072 and hashlib.sha256(raw).hexdigest() == QUALIFICATION_SHA256,
            'exact accepted engineering proof required')
    p = modules['controller'].strict_json(raw)
    require(p['status'] == 'verified_six_fixed_engineering_controls' and
            type(p['verified_engineering_controls']) is int and p['verified_engineering_controls'] == 6 and
            p['required_engineering_controls'] == 6 and p['fresh_network_necessary_condition_matches'] is True and
            p['general_network_isolation_proven'] is False and p['benchmark_readiness_increment'] is False,
            'qualified source condition differs')


class Runner:
    """Host-owned single-use connector, not a replacement runtime supervisor."""
    def __init__(self, release, *, modules, data, factory_module, budget_bytes,
                 participant_factory, evidence_sink, clock_ms, source_options,
                 code_options, context_ids, projector, renderer, code_factory):
        self._release, self._modules, self._data = release, modules, data
        self._sink, self._result, self._sealed = evidence_sink, None, None
        self._source_budget = source_options['budget']
        self._used = False
        c = modules['controller']
        plan, _ = c.admit_budget(budget_bytes)
        require(plan['code_tools'] == [modules['code_backend'].TOOL], 'exact declared code tool')
        require(code_options['max_calls'] == plan['max_tool_calls'], 'tool budget/backend call bound differs')
        env = environment_bytes(modules, data, call_wall_seconds=code_options['call_wall_seconds'],
                                max_calls=code_options['max_calls'])
        require(plan['analysis_environment_sha256'] == hashlib.sha256(env).hexdigest(),
                'prospective analysis environment differs')
        self._store('authenticated_source_roles', c.canonical({'scope': release.scope,
            'roles': release.source_bindings, 'analysis_environment': c.binding(env),
            'historical_source_acceptance_not_live_namespace_inventory': True}))
        expected = release.observations
        def checked_project(index, receipt, **options):
            packet, projection = projector(index, receipt, **options)
            row = expected[index['case_id']]
            raw = modules['host'].canonical(packet)
            require(c.binding(raw) == {'bytes': row['observation_bytes'], 'sha256': row['observation_sha256']},
                    'projection differs from accepted observation')
            require(packet['case_id'] == row['case_id'] and packet['coverage'] == row['coverage'] and
                    len(packet['relative_time_ms']) == row['source_rows'] and
                    projection['source_rows_read'] == row['source_rows'] and
                    projection['array_identity_binding_sha256'] == row['array_identity_binding_sha256'],
                    'source window/array identity differs from accepted row')
            proof = dict(projection)
            proof['accepted_observation_row'] = c.binding(c.canonical(row))
            proof['historical_projection_receipt_sha256'] = row['projection_receipt_sha256']
            proof['historical_projection_receipt_reproduced'] = False
            return packet, proof
        class VerifiedDefaultRenderer:
            def __init__(self, packet, profile):
                self._renderer = renderer.TraceViewer(packet, profile)
                self._default = self._renderer.action({'action': 'view'})
                png, receipt = self._default
                row = expected[packet['case_id']]
                require(type(png) is bytes and c.binding(png) ==
                        {'bytes': row['default_png_bytes'], 'sha256': row['default_png_sha256']} and
                        receipt['observation_sha256'] == row['observation_sha256'],
                        'fresh default image differs from accepted byte binding')
            def action(self, command):
                cached, self._default = self._default, None
                if command == {'action': 'view'} and cached is not None:
                    return cached
                return self._renderer.action(command)
        self.factory = factory_module.OrderedDeliveryFactory(release.manifest,
            {x['case_id']: x for x in release.indices}, release.receipts,
            project_case=checked_project, projection_options=source_options,
            delivery_module=modules['host'], viewer_module=types.SimpleNamespace(
                TraceViewer=VerifiedDefaultRenderer, validate_packet=modules['viewer'].validate_packet),
            code_backend_factory=code_factory, code_options=code_options,
            context_ids=context_ids, owned_process_v2=modules['owned_process_v2'],
            owned_process_sha256=PROCESS_V2_SHA256, evidence_sink=evidence_sink)
        try:
            self.controller = c.PairController(release.manifest, budget_bytes, data['terminal_policy'],
                transport=modules['transport'], terminal_module=modules['terminal'], interface_module=modules['interface'],
                delivery_factory=self.factory, participant_factory=participant_factory,
                evidence_sink=lambda raw: self._store('controller_original', raw), clock_ms=clock_ms)
        except BaseException as original:
            try:
                self.factory.close()
            except BaseException as cleanup:
                if isinstance(original, Exception) and not isinstance(cleanup, Exception):
                    raise cleanup
            raise original

    def _store(self, kind, raw):
        c = self._modules['controller']
        require(type(raw) is bytes and len(raw) <= 4194304, 'complete bounded host original required')
        actual = c.artifact(self._sink(kind, raw))
        require(actual == c.binding(raw), 'durable sink returned another original')
        return actual

    def run(self):
        require(not self._used, 'single run; no retry or reselection')
        self._used = True
        problem = None
        try:
            result = self.controller.run()
        except BaseException as error:
            problem = error
        try:
            closure = self.factory.close()
        except BaseException as error:
            if problem is None or isinstance(problem, Exception) and not isinstance(error, Exception):
                problem = error
        if problem is not None:
            raise problem
        result['execution_scope'] = self._release.scope
        result['delivery_factory_closure'] = self._modules['controller'].artifact(closure)
        result['delivery_factory_summary'] = self.factory.summary()
        result['accepted_packet_and_default_PNG_bytes_compared'] = (
            result['status'] == 'complete_unsealed' and result['delivery_factory_summary']['all_cases_completed'])
        result['historical_projection_receipts_reproduced'] = False
        result['real_participant_backend_qualified'] = False
        result['source_read_counters'] = self.resource_counters()
        self._result = result
        return result

    def resource_counters(self):
        """Also available after a failed/interrupted run with no returned result."""
        return self._source_budget.counters()

    def seal(self, result):
        """Separate post-collection step; private targets never enter controller."""
        require(result is self._result and result is not None and self._sealed is None and
                result['status'] == 'complete_unsealed' and
                result['delivery_factory_summary']['all_cases_completed'], 'complete owned pair required')
        m, r = self._modules, self._release
        self._targets = m['target'].project_targets(r.manifest, r.indices, secret=r.secret,
            indexed=m['indexed'], core=m['core'], transport=m['transport'])
        self._sealed = m['sealer'].seal_pair(r.manifest, self._targets, result['terminal_snapshots'],
            expected_budget_hashes=result['expected_budget_hashes'],
            terminal_policy_bytes=self._data['terminal_policy'], transport=m['transport'])
        return self._sealed

    def score(self, sealed):
        """Explicit grader invocation, never part of construction or collection."""
        require(sealed is self._sealed and sealed is not None, 'owned complete seal required')
        return self._modules['sealer'].score_sealed(sealed, self._data['scoring_policy'],
            self._release.manifest, self._targets, transport=self._modules['transport'],
            scorer=self._modules['scorer'])


def build_runner(blobs, member_blobs, *, admission_module, factory_module, modules, data,
                 qualification_bytes, budget_bytes, participant_factory, evidence_sink,
                 clock_ms, array_read_limit, staging_parent, docker_executable, docker_socket,
                 call_wall_seconds, context_ids):
    """Production entry: reauthenticate fixed full metadata before making a factory.

    `modules`/`data` must be the unchanged authenticated dependencies loader output.
    The participant factory is an explicitly external trusted backend obligation;
    the connector neither invents a provider nor qualifies one by callback shape.
    No supplied participant field chooses source paths, daemon or role modules.
    """
    release = admission_module.admit_release(blobs, member_blobs, modules=modules)
    _qualify(qualification_bytes, modules)
    plan, _ = modules['controller'].admit_budget(budget_bytes)
    return _build(release, modules=modules, data=data, factory_module=factory_module,
        budget_bytes=budget_bytes, participant_factory=participant_factory, evidence_sink=evidence_sink,
        clock_ms=clock_ms, array_read_limit=array_read_limit, staging_parent=staging_parent,
        docker_executable=docker_executable, docker_socket=docker_socket, call_wall_seconds=call_wall_seconds,
        context_ids=context_ids, max_calls=plan['max_tool_calls'], projector=modules['host'].project_case,
        renderer=modules['viewer'], code_factory=modules['code_backend'].DockerCodeBackend)


def _build(release, *, modules, data, factory_module, budget_bytes, participant_factory, evidence_sink,
           clock_ms, array_read_limit, staging_parent, docker_executable, docker_socket,
           call_wall_seconds, context_ids, max_calls, projector, renderer, code_factory):
    source_options = {'root': release.array_root, 'secret': release.secret,
        'budget': modules['host'].ReadBudget(array_read_limit), 'indexed': modules['indexed'],
        'core': modules['core'], 'policy': modules['numeric_policy']}
    code_options = {'profile_bytes': data['runtime_profile'], 'staging_parent': staging_parent,
        'docker_executable': docker_executable, 'docker_socket': docker_socket,
        'policy_api': modules['code_policy'], 'command_api': modules['command'],
        'call_wall_seconds': call_wall_seconds, 'max_calls': max_calls}
    return Runner(release, modules=modules, data=data, factory_module=factory_module, budget_bytes=budget_bytes,
        participant_factory=participant_factory, evidence_sink=evidence_sink, clock_ms=clock_ms,
        source_options=source_options, code_options=code_options, context_ids=context_ids,
        projector=projector, renderer=renderer, code_factory=code_factory)


def build_generated_runner(blobs, member_blobs, *, generated_pins, admission_module, factory_module,
                           modules, data, projector, renderer, code_factory, **options):
    """Explicit fictional route; no qualification or authentic source claim."""
    release = admission_module.admit_generated_release(blobs, member_blobs, modules=modules,
                                                      generated_pins=generated_pins)
    plan, _ = modules['controller'].admit_budget(options['budget_bytes'])
    return _build(release, modules=modules, data=data, factory_module=factory_module,
        max_calls=plan['max_tool_calls'], projector=projector, renderer=renderer,
        code_factory=code_factory, **options)
