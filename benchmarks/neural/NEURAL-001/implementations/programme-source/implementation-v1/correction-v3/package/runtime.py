"""Full 11-panel source controller. Authenticated external environment is a hard gate.

No injected object's identity, booleans or telemetry alone proves isolation or
science. The independent admission interface is a trusted deployment dependency.
Default CLI has no admitted environment; no authentic operands are opened here.
"""
from dataclasses import dataclass
from fractions import Fraction
from .protocol import (ARMS, MODES, PEOPLE, GATES, DESIGN_SHA256, CONTROL_INTERPRETATION, Phase, Refusal,
                       canonical, check_pin, pin_bytes, require, full_plan,
                       validate_roster, workload_counts)
from .resources import ADDITIVE, PEAK, Ledger, quantities


@dataclass(frozen=True)
class Qualification:
    receipt: dict
    receipt_pin: dict

    def validate(self, independent_admission, *, source_pin):
        # Called before manifest factory, provider, model, target or private operand.
        require(type(self.receipt) is dict, 'bounded operator qualification metadata required')
        check_pin(self.receipt_pin)
        require(pin_bytes(canonical(self.receipt)) == self.receipt_pin, 'exact qualification receipt required')
        r = self.receipt
        require(r.get('schema') == 'neural001_actual_qualification_v1', 'actual qualification schema required')
        require(r.get('task_id') == 'NEURAL-001' and r.get('design_sha256') == DESIGN_SHA256,
                'accepted exact task/design binding required')
        require(r.get('source_pin') == source_pin, 'complete current source closure must be qualified')
        require(r.get('control_interpretation') == CONTROL_INTERPRETATION,
                'root-adopted disclosed-transform interpretation required')
        require(type(r.get('gates')) is dict and set(r['gates']) == set(GATES)
                and all(v is True for v in r['gates'].values()), 'unresolved qualification gates')
        require(r.get('execution_authorized') is True and r.get('scientific_qualification_claim') is False,
                'separate actual execution authority required; no presupposed result')
        # External root-selected verifier must authenticate issuer/evidence custody.
        require(independent_admission.verify(r, self.receipt_pin, source_pin) is True,
                'independent qualification authentication refused')
        return r


class StudyRuntime:
    """Drivers implement real bounded operations; they cannot skip complete phases.

    Reference operation must invoke the pinned reference/reference_engine.py.
    Candidate author/train/predict operation must preserve the accepted broad
    treatment. The operator driver sees canonical metadata; its candidate-facing
    transport must contain only sanitized current views and opaque context IDs.
    That physical/provider mechanism is an unresolved gate, not a Python proof.
    """
    def __init__(self, *, qualification, source_pin, independent_admission,
                 manifest_factory, driver_factory, profile, clock, sink):
        self.qualification = qualification
        self.source_pin = source_pin
        self.independent_admission = independent_admission
        self.manifest_factory = manifest_factory
        self.driver_factory = driver_factory
        self.profile = profile
        self.clock, self.sink = clock, sink
        self.started = False
        self.terminal = False
        self.completed = 0
        self.last_receipt = None
        self.programs = {}
        self.states = {}
        self.predictions = {}
        self.submissions = {}
        self.contexts = set()
        self.ledgers = {}
        self.original_origin = None
        self.original_deadline = None

    def _profile(self, r):
        p = self.profile
        require(type(p) is dict and pin_bytes(canonical(p)) == r.get('resource_profile_pin'),
                'qualified exact full-workload resource profile required')
        required = {'origin', 'deadline', 'whole', 'person_candidate', 'person_reference',
                    'phase', 'prelaunch_usage', 'prelaunch_peaks', 'prelaunch_evidence_pin'}
        require(set(p) == required, 'complete profile; legacy1200s not a default')
        require(p['origin'] == r.get('original_origin') and p['deadline'] == r.get('original_deadline'),
                'preserve original whole-program clock')
        check_pin(p['prelaunch_evidence_pin'])
        phases = {'candidate/author', 'candidate/train', 'candidate/predict',
                  'candidate/assemble', 'reference/train', 'reference/predict',
                  'reference/assemble', 'operator/grade'}
        require(set(p['phase']) == phases, 'complete phase ceilings required')
        for row in [p['whole'], p['person_candidate'], p['person_reference'], *p['phase'].values()]:
            require(set(row) == {'additive', 'peaks'}, 'budget additive and peak fields required')
            quantities(row['additive'], ADDITIVE)
            quantities(row['peaks'], PEAK)
        quantities(p['prelaunch_usage'], ADDITIVE)
        quantities(p['prelaunch_peaks'], PEAK)
        # Single candidate profile deliberately has no mode/arm override.
        self.original_origin, self.original_deadline = p['origin'], p['deadline']
        def fresh(row):
            return Ledger(origin=p['origin'], deadline=p['deadline'], limits=row['additive'],
                          peaks=row['peaks'], clock=self.clock)
        self.ledgers['whole'] = fresh(p['whole'])
        for person in PEOPLE:
            for mode in MODES:
                for arm in ARMS:
                    self.ledgers[f'candidate/{mode}/{arm}/{person}'] = fresh(p['person_candidate'])
            for family, arms in (('R1', ('neural', 'within_query_half_shift')),
                                 ('R2', ('neural', 'within_query_half_shift')),
                                 ('R0', ('no_neural',))):
                for arm in arms:
                    self.ledgers[f'reference/{family}/{arm}/{person}'] = fresh(p['person_reference'])
        self.ledgers['whole'].admit_prelaunch('prelaunch',p['prelaunch_usage'],p['prelaunch_peaks'])

    def _attribution(self, phase):
        if phase.actor == 'operator':
            return {}
        kind = phase.mode if phase.actor == 'candidate' else phase.family
        base = f'{phase.actor}/{kind}'
        arms = ('neural', 'within_query_half_shift') if phase.arm == 'neural' and phase.operation in ('author', 'train') else (phase.arm,)
        persons = PEOPLE if phase.operation == 'author' else (phase.person,)
        share = Fraction(1, len(arms) * len(persons))
        return {f'{base}/{arm}/{person}': share for person in persons for arm in arms}

    def _emit(self, value):
        # Sink is an independent bounded durable journal; failure is terminal.
        try:
            self.sink.emit(value)
        except BaseException:
            self.terminal = True
            raise

    def _dependencies(self, p):
        if p.operation == 'author':
            return {}
        kind = p.mode if p.actor == 'candidate' else p.family
        training_arm = 'neural' if p.arm == 'within_query_half_shift' else p.arm
        group = (p.actor, kind, p.arm, p.person)
        if p.operation == 'grade':
            require(len(self.submissions) == 264, 'all264 complete panel submissions before grade')
            return {'submissions': {'/'.join(k): v for k, v in self.submissions.items()}}
        if p.operation == 'assemble':
            rows = self.predictions.get(group, {})
            require(len(rows) == 120, 'exact120 current-panel predictions before assembly')
            return {'predictions': dict(rows)}
        dep = {}
        if p.actor == 'candidate':
            dep['program'] = self.programs[(p.mode, training_arm)]['program']
            dep['method_recipe'] = self.programs[(p.mode, training_arm)]['method_recipe']
            families = ('R0',) if p.arm == 'no_neural' else ('R1', 'R2')
            dep['reference_tools'] = {f: self.states[('reference', f, p.person, training_arm)]['frozen_state']
                                      for f in families}
        if p.operation == 'predict':
            dep['frozen_state'] = self.states[(p.actor, kind, p.person, training_arm)]['frozen_state']
        return dep

    def _retain(self, p, artifacts):
        kind = p.mode if p.actor == 'candidate' else p.family
        group = (p.actor, kind, p.arm, p.person)
        if p.operation == 'author':
            key = (p.mode, p.arm)
            require(key not in self.programs, 'global program overwrite forbidden')
            self.programs[key] = artifacts
        elif p.operation == 'train':
            key = (p.actor, kind, p.person, p.arm)
            require(key not in self.states, 'trained-state overwrite forbidden')
            self.states[key] = artifacts
        elif p.operation == 'predict':
            rows = self.predictions.setdefault(group, {})
            require(p.query_id not in rows, 'query output overwrite forbidden')
            rows[p.query_id] = artifacts['prediction']
        elif p.operation == 'assemble':
            require(group not in self.submissions, 'person-panel overwrite forbidden')
            self.submissions[group] = artifacts['submission']
            del self.predictions[group]

    def _exposure(self, p):
        if p.operation == 'author':
            return {'views': ['documents', 'environment_documentation'],
                    'llm_numeric_access': False, 'query_count': 0}
        if p.operation in ('assemble', 'grade'):
            return {'views': ['operator_only_complete_outputs'],
                    'llm_numeric_access': False, 'query_count': 0}
        training = 'training_envelope_only' if p.arm == 'no_neural' else 'training_neural_and_envelope'
        views = [training]
        if p.operation == 'predict':
            views.append('current_length_fs_only' if p.arm == 'no_neural' else 'one_current_arm_transformed_query')
        return {'views': views, 'query_count': int(p.operation == 'predict'),
                'llm_numeric_access': p.actor == 'candidate' and p.mode == 'adaptive_case',
                'frozen_tool_parameters_and_preprocessing': p.operation == 'predict',
                'broad_case_synthesis_allowed': p.actor == 'candidate' and p.operation == 'predict',
                'new_supervised_training_allowed': p.operation == 'train',
                'cross_query_state_or_score_feedback': False}

    def _run_phase(self, phase, driver, subjects):
        require(not self.terminal, 'terminal study cannot continue')
        caps = self.profile['phase'][f'{phase.actor}/{phase.operation}']
        allocation = {'whole': Fraction(1), **self._attribution(phase)}
        tokens = {}
        key = phase.internal_key()
        try:
            for name, share in allocation.items():
                amounts = {k: Fraction(str(v)) * share for k, v in caps['additive'].items()}
                tokens[name] = self.ledgers[name].reserve(key, amounts, caps['peaks'])
        except BaseException:
            for name, token in tokens.items():
                self.ledgers[name].abandon(token, 'multi-ledger admission failed before operation')
            self.terminal = True
            raise
        request = None
        request_pin = None
        report = None
        try:
            request = {'schema': 'neural001_operator_phase_v1', 'sequence': phase.sequence,
                       'operation': phase.operation, 'actor': phase.actor, 'mode': phase.mode,
                       'arm': phase.arm, 'person': phase.person, 'query_id': phase.query_id,
                       'reference_family': phase.family, 'source_pin': self.source_pin,
                       'original_origin': self.original_origin,
                       'original_deadline': self.original_deadline, 'caps': caps,
                       'artifacts': self._dependencies(phase),
                       'exposure': self._exposure(phase)}
            # Internal identities are operator-only; provider receives only sanitized
            # whitelisted current views. No prior query output is a prediction dependency.
            request_pin = pin_bytes(canonical(request))
            self._emit({'kind': 'reserved', 'request_pin': request_pin, 'request': request})
            if phase.operation == 'author':
                report = driver.author(request, request_pin)
            elif phase.operation == 'train':
                report = driver.train(request, request_pin)
            elif phase.operation == 'predict':
                report = driver.predict(request, request_pin)
            elif phase.operation == 'assemble':
                report = driver.assemble(request, request_pin)
            else:
                # Driver must independently validate ALL264 outputs before first target body.
                report = driver.grade_all(request, request_pin)
            self._admit_report(phase, request, request_pin, report, driver)
            usage, peaks = report['usage'], report['peaks']
            accounting_errors = []
            for name, token in tokens.items():
                share = allocation[name]
                attributed = {k: Fraction(str(v)) * share for k, v in usage.items()}
                try:
                    self.ledgers[name].finish(token, attributed, peaks,
                                              failed=report['status'] != 'ok')
                except Refusal as error:
                    accounting_errors.append(name + ':' + str(error))
            if accounting_errors:
                raise Refusal(';'.join(accounting_errors))
            if report['status'] != 'ok':
                self.terminal = True
                raise Refusal('phase failed; full comparison not eligible')
            self._emit({'kind': 'completed', 'request_pin': request_pin, 'report': report})
            self._retain(phase, report['artifacts'])
            self.last_receipt = pin_bytes(canonical(report))
            self.completed += 1
        except BaseException as exc:
            self.terminal = True
            failure_observation = None
            try:
                failure_observation = driver.fail_current_phase(type(exc).__name__,request_pin)
            except BaseException as failure_error:
                failure_observation = {'status':'unknown_failure_observation',
                                       'error_type':type(failure_error).__name__}
            for name, token in tokens.items():
                if self.ledgers[name].active is not None:
                    self.ledgers[name].abandon(token, type(exc).__name__)
            # A durable caller observer must retain this failure even if sink fails.
            try:
                self._emit({'kind': 'failed', 'request_pin': request_pin,
                            'error_type': type(exc).__name__,
                            'costs_retained': True, 'unknown_usage_not_zero': True,
                            'unadmitted_report': report,
                            'failure_observation': failure_observation})
            except BaseException:
                pass
            raise

    def _admit_report(self, phase, request, request_pin, report, driver):
        require(type(report) is dict and len(canonical(report)) <= 65536,
                'bounded complete phase report required')
        require(set(report) == {'schema', 'request_pin', 'status', 'usage', 'peaks',
                               'artifacts', 'context_id', 'admission', 'observation'},
                'exact phase report fields required')
        require(report['schema'] == 'neural001_phase_report_v1'
                and report['request_pin'] == request_pin, 'report request binding mismatch')
        require(report['status'] in ('ok', 'failed'), 'explicit success/failure required')
        quantities(report['usage'], ADDITIVE)
        quantities(report['peaks'], PEAK)
        require(type(report['artifacts']) is dict, 'artifact role mapping required')
        for artifact in report['artifacts'].values():
            require(type(artifact) is dict and set(artifact) == {'role', 'pin', 'custody_id'},
                    'typed immutable artifact custody required')
            check_pin(artifact['pin'])
            require(type(artifact['custody_id']) is str and artifact['custody_id'], 'custody identity required')
        required_roles = {'author': {'program', 'method_recipe'}, 'train': {'frozen_state', 'training_report'},
                          'predict': {'prediction', 'method_trace'}, 'assemble': {'submission'},
                          'grade': {'protected_report', 'uncertainty_report'}}[phase.operation]
        require(set(report['artifacts']) == required_roles, 'complete exact operation outputs required')
        require(all(k == v['role'] for k, v in report['artifacts'].items()), 'artifact role binding mismatch')
        ctx = report['context_id']
        require(type(ctx) is str and 1 <= len(ctx) <= 128 and ctx not in self.contexts,
                'fresh independently reset operation context required')
        self.contexts.add(ctx)
        observation = report['observation']
        require(type(observation) is dict, 'independent external observation required')
        # A self-reported process/provider success is insufficient. Trusted admission
        # joins actual original-clock/natural-zero/EOF/namespace/context evidence.
        require(self.independent_admission.admit_phase(request, request_pin, report) is True,
                'independent phase/process/access/method admission refused')
        if phase.operation == 'predict':
            require(driver.confirm_trained_state_unchanged(request, report) is True,
                    'frozen learned state/preprocessing changed')

    def run(self):
        require(not self.started, 'one-shot full study; no silent clock/budget reset')
        self.started = True
        # No factory or scientific operand is touched before independent qualification.
        q = self.qualification.validate(self.independent_admission, source_pin=self.source_pin)
        self._profile(q)
        subjects = validate_roster(self.manifest_factory())
        driver = self.driver_factory(q, self.source_pin, subjects)
        expected = workload_counts(subjects)
        self._emit({'kind': 'full_plan', 'counts': expected, 'design_sha256': DESIGN_SHA256,
                    'no_new_benchmark_ids': True})
        for phase in full_plan(subjects):
            self._run_phase(phase, driver, subjects)
        require(self.completed == expected['phases'] and not self.terminal,
                'complete264 outputs and all phases required')
        # Score/report are provisional until this enclosing caller also closes naturally.
        return {'status': 'provisional_complete_pending_outer_natural_zero',
                'completed_phases': self.completed, 'counts': expected,
                'control_interpretation': CONTROL_INTERPRETATION,
                'half_shift_is_evidence_of_absent_alignment_or_neural_information': False,
                'last_report_pin': self.last_receipt, 'scientifically_qualified': False,
                'submission_ready': False, 'new_benchmarks': 0,
                'ledger_summaries': {k: v.snapshot() for k, v in self.ledgers.items()}}
