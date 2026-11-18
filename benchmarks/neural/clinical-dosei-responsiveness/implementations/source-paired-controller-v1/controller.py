"""Finite host orchestration over byte-only adapters; no runtime qualification.

Injected adapters and evidence custody are trusted host obligations. Calls are
synchronous: this source cannot preempt a blocking adapter or establish an OS
isolation boundary. A real runtime must provide those separately.
"""
import hashlib
import json
import math
import re

ARMS = ('viewer_only', 'code_enabled')
CASES = 7345
PROMPT = ('Predict the source grouped MOAAS responsiveness category 1 through 5 '
          'for this retrospective marker-associated observation. Original scores '
          '0/1 form group 1 and 5/6 form group 5. Use only this case and declared '
          'capabilities, with no training, demonstrations or prior-case feedback. '
          'Request a declared action or return exactly {"status":"ok",'
          '"probabilities":[p1,p2,p3,p4,p5]}, or {"status":"abstain",'
          '"probabilities":null}. Do not include identifiers or failure reasons.')


class ControllerRefusal(ValueError):
    pass


class ProviderFault(Exception):
    """Only a trusted provider adapter may supply this attribution and receipt."""
    def __init__(self, reason, evidence):
        self.reason, self.evidence = reason, evidence


class ParticipantTokenBudgetExceeded(Exception):
    """Trusted adapter reports exhaustion of the frozen model token allowance."""
    def __init__(self, evidence):
        self.evidence = evidence


def require(ok, message):
    if not ok: raise ControllerRefusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'exact SHA256 string required')
    return value


def binding(raw):
    require(type(raw) is bytes, 'exact immutable bytes required')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def artifact(value):
    require(type(value) is dict and set(value) == {'sha256', 'bytes'}, 'exact evidence binding required')
    require(type(value['bytes']) is int and 0 <= value['bytes'] <= 2**63-1, 'exact evidence byte count')
    return {'sha256': sha(value['sha256']), 'bytes': value['bytes']}


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError('duplicate key')
            out[key] = value
        return out
    def finite(value):
        x = float(value)
        if not math.isfinite(x): raise ValueError('nonfinite')
        return x
    def constant(_): raise ValueError('nonfinite')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_float=finite, parse_constant=constant)


def admit_budget(raw):
    require(type(raw) is bytes and len(raw) <= 65536, 'bounded prospective budget bytes required')
    plan = strict_json(raw)
    require(type(plan) is dict and set(plan) == {'schema', 'participant_wall_ms', 'max_tool_calls',
            'participant_token_limit', 'model_configuration_sha256', 'analysis_environment_sha256',
            'code_tools'}, 'exact budget fields required')
    require(plan['schema'] == 'dosei_paired_controller_budget_v1' and canonical(plan) == raw,
            'canonical prospective budget required')
    for key, high in (('participant_wall_ms', 3600000), ('max_tool_calls', 128),
                      ('participant_token_limit', 1000000)):
        require(type(plan[key]) is int and 1 <= plan[key] <= high, 'bounded exact budget integer')
    sha(plan['model_configuration_sha256']); sha(plan['analysis_environment_sha256'])
    require(type(plan['code_tools']) is list and 0 < len(plan['code_tools']) <= 16,
            'explicit code-arm tool declarations required')
    names = set()
    for tool in plan['code_tools']:
        require(type(tool) is dict and set(tool) == {'name','description','input_format'} and
                type(tool['name']) is str and re.fullmatch('[a-z][a-z0-9_]{0,47}', tool['name']) and
                tool['name'] not in names and type(tool['description']) is str and
                0 < len(tool['description'].encode('utf-8')) <= 1024 and
                tool['input_format'] == 'utf8_text', 'exact unique prospective tool declaration')
        names.add(tool['name'])
    return plan, hashlib.sha256(raw).hexdigest()


class PairController:
    """No labels/targets are accepted here; each adapter receives only public bytes.

    Factories, clock, sink and injected modules must be authenticated trusted host
    implementations. A unique context receipt is checked, but uniqueness is not
    evidence of process isolation or absence of provider-side memory.
    """
    def __init__(self, manifest, budget_bytes, terminal_policy_bytes, *, transport,
                 terminal_module, interface_module, delivery_factory, participant_factory,
                 evidence_sink, clock_ms):
        expected = transport.admit_manifest(manifest)
        require(len(expected) == CASES, 'all7345 frozen cases required')
        require([x['case_id'] for x in manifest] == sorted(expected), 'fixed ascending opaque case order')
        self.manifest = [dict(x) for x in manifest]
        self.plan, self.budget_sha = admit_budget(budget_bytes)
        self.policy = terminal_policy_bytes
        self.transport = transport; self.terminal = terminal_module; self.interface = interface_module
        self.delivery_factory = delivery_factory; self.participant_factory = participant_factory
        self.sink = evidence_sink; self.clock = clock_ms
        self._used = False; self._contexts = set(); self._last_clock = None
        self._disclosure = None

    def _store(self, raw):
        require(type(raw) is bytes and len(raw) <= 4194304, 'bounded complete evidence bytes required')
        claimed = artifact(self.sink(raw))
        require(claimed == binding(raw), 'evidence sink returned different content binding')
        return claimed

    def _now(self):
        now = self.clock()
        require(type(now) is int and 0 <= now <= 2**63-1 and
                (self._last_clock is None or now >= self._last_clock), 'trusted monotonic integer clock required')
        self._last_clock = now
        return now

    def _case(self, public, arm):
        state = self.terminal.CaseTerminal(self.policy, public, arm, self.budget_sha, transport=self.transport)
        participant = None; tool_backend = None; iface = None; context_id = None; started = None
        messages = 0; tools = 0; trail = []; setup = None
        def save(kind, raw):
            item = self._store(raw); trail.append({'kind': kind, 'evidence': item}); return item
        def fail(reason, evidence):
            state.infrastructure_failure(reason, artifact(evidence))
        def unknown(problem):
            # Host-private diagnostic. Real provider error bodies use ProviderFault receipts.
            return save('unexpected_host_error', canonical({'exception_type': type(problem).__name__,
                        'exception_message': str(problem),
                        'reason': 'unclassified trusted adapter failure'}))
        try:
            delivered = self.delivery_factory(dict(public), arm)
            require(type(delivered) is dict and set(delivered) == {'backend', 'common_disclosure', 'source_evidence'},
                    'exact trusted delivery factory result required')
            tool_backend = delivered['backend']
            require(callable(getattr(tool_backend, 'close', None)), 'owned tool/view backend closure required')
            source_evidence = artifact(delivered['source_evidence'])
            disclosure = delivered['common_disclosure']
            require(type(disclosure) is bytes and len(disclosure) <= 65536, 'bounded common disclosure required')
            if self._disclosure is None: self._disclosure = disclosure
            require(disclosure == self._disclosure, 'all cases and arms require identical scientific disclosure')
            iface = self.interface.ParticipantInterface(arm, dict(public), backend=delivered['backend'],
                declared_tools=self.plan['code_tools'] if arm == 'code_enabled' else (),
                common_disclosure=disclosure)
            initial_action = b'{"action":"view"}' if arm == 'viewer_only' else b'{"action":"observation"}'
            initial_payload = iface.handle(initial_action)
            description = iface.describe()
            initial = canonical({'schema': 'dosei_controller_initial_message_v1', 'prompt': PROMPT,
                                 'capabilities': strict_json(description), 'initial_input': strict_json(initial_payload)})
            initial_ref = save('initial_participant_message', initial)
            setup = self.participant_factory(arm, binding(canonical(self.plan)))
            require(type(setup) is dict and set(setup) == {'participant', 'context_id', 'setup_evidence'},
                    'exact fresh participant factory result required')
            participant = setup['participant']; context_id = sha(setup['context_id'])
            require(context_id not in self._contexts, 'fresh case/arm context required')
            self._contexts.add(context_id)
            setup_evidence = artifact(setup['setup_evidence'])
            started = self._now()
            ack = artifact(participant.open(initial))
            delivery_ref = save('trusted_delivery_receipt', canonical({'source_evidence': source_evidence,
                'context_setup_evidence': setup_evidence, 'context_id': context_id,
                'delivery_ack': ack, 'initial_message': initial_ref,
                'observation_sha256': public['observation_sha256']}))
            state.establish_delivery(observation_sha256=public['observation_sha256'], delivery_evidence=delivery_ref)
            continuation = None
            while state.snapshot()['state'] == 'active':
                if self._now()-started >= self.plan['participant_wall_ms']:
                    state.budget_exhausted('participant_wall_budget', save('host_wall_budget',
                        canonical({'elapsed_ms': self._now()-started, 'budget_sha256': self.budget_sha})))
                    break
                raw = participant.respond(continuation); messages += 1
                require(type(raw) is bytes and len(raw) <= 2097152, 'complete bounded backend response bytes required')
                raw_ref = save('raw_participant_response', raw)
                if self._now()-started >= self.plan['participant_wall_ms']:
                    state.budget_exhausted('participant_wall_budget', save('host_wall_budget',
                        canonical({'elapsed_ms': self._now()-started, 'budget_sha256': self.budget_sha,
                                   'late_response': raw_ref})))
                    break
                try: decoded = strict_json(raw)
                except (ValueError, UnicodeError, RecursionError): decoded = None
                if type(decoded) is not dict or 'action' not in decoded:
                    state.model_response(raw, retained_response=raw_ref)
                    break
                if tools >= self.plan['max_tool_calls']:
                    state.budget_exhausted('participant_tool_call_budget', save('host_tool_call_budget',
                        canonical({'tool_calls_completed': tools, 'budget_sha256': self.budget_sha,
                                   'next_request': raw_ref})))
                    break
                tools += 1
                try:
                    continuation = iface.handle(raw)
                    payload = strict_json(continuation)['payload']
                    if payload.get('kind') == 'tool_result' and payload.get('status') == 'participant_error':
                        state.participant_tool_error(save('participant_analysis_error', continuation))
                except self.interface.RequestRefusal as refusal:
                    continuation = self.interface.request_error(refusal)
                    state.participant_tool_error(save('participant_request_error',
                        canonical({'request': raw_ref, 'safe_response': strict_json(continuation)})))
                save('participant_tool_response', continuation)
        except self.interface.InterfaceFailure as problem:
            reason = getattr(problem, 'budget_reason', None)
            evidence = save('trusted_interface_failure', canonical({'category': problem.category,
                            'budget_reason': reason,
                            'original_budget_evidence': artifact(problem.budget_evidence)
                            if reason is not None else None}))
            if reason in self.terminal.BUDGET_REASONS and state.snapshot()['state'] == 'active':
                state.budget_exhausted(reason, evidence)
            else: fail('runtime_failure', evidence)
        except ParticipantTokenBudgetExceeded as problem:
            if state.snapshot()['state'] == 'active':
                state.budget_exhausted('participant_token_budget', artifact(problem.evidence))
            else: fail('uncertain_delivery', artifact(problem.evidence))
        except ProviderFault as problem:
            require(problem.reason in self.terminal.INVALID_REASONS, 'trusted provider reason must be explicit')
            fail(problem.reason, problem.evidence)
        except Exception as problem:
            # A trusted call may already have invalidated the terminal object.
            if state.snapshot()['state'] != 'invalid': fail('unclassified_failure', unknown(problem))
        finally:
            cleanup_problem = None
            for owned, kind in ((participant, 'participant_context_closed'),
                                (tool_backend, 'tool_view_context_closed')):
                if owned is None: continue
                try:
                    close_ref = artifact(owned.close())
                    trail.append({'kind': kind, 'evidence': close_ref})
                except BaseException as problem:
                    if not isinstance(problem, Exception) and cleanup_problem is None:
                        cleanup_problem = problem
                    if state.snapshot()['state'] != 'invalid':
                        try: fail('runtime_failure', unknown(problem))
                        except BaseException as reporting_problem:
                            if cleanup_problem is None: cleanup_problem = reporting_problem
            if cleanup_problem is not None: raise cleanup_problem
        snapshot = state.snapshot()
        transcript = save('complete_case_transcript_index', canonical({'context_id': context_id,
            'arm': arm, 'binding': public, 'budget_sha256': self.budget_sha, 'events': trail}))
        return snapshot, {'binding': dict(public), 'arm': arm, 'context_id': context_id,
            'model_responses_received': messages, 'requested_tool_calls': tools,
            'transcript': transcript, 'state': snapshot['state'],
            'participant_isolation_qualified_by_controller': False}

    def run(self):
        require(self._used is False, 'controller is single use; no case retry or reselection')
        self._used = True
        snapshots = {arm: [] for arm in ARMS}; operations = {arm: [] for arm in ARMS}
        failed = None
        for public in self.manifest:
            for arm in ARMS:
                snapshot, operation = self._case(public, arm)
                snapshots[arm].append(snapshot); operations[arm].append(operation)
                if snapshot['state'] != 'terminal':
                    failed = {'case_id': public['case_id'], 'arm': arm, 'reason': snapshot['reason']}
                    break
            if failed is not None: break
        return {'schema': 'dosei_complete_paired_controller_result_v1',
            'status': 'complete_unsealed' if failed is None else 'invalid_incomplete_pair',
            'expected_cases_per_arm': CASES, 'terminal_snapshots': snapshots,
            'operations': operations, 'failure': failed, 'budget_sha256': self.budget_sha,
            'public_manifest_binding': binding(canonical(self.manifest)),
            'common_disclosure_binding': binding(self._disclosure) if self._disclosure is not None else None,
            'expected_budget_hashes': {arm: {x['case_id']: self.budget_sha for x in self.manifest} for arm in ARMS},
            'scoring_performed': False, 'targets_accepted_by_controller': False,
            'participant_isolation_or_hard_adapter_deadlines_qualified': False,
            'evidence_custody_authenticated_by_controller': False}
