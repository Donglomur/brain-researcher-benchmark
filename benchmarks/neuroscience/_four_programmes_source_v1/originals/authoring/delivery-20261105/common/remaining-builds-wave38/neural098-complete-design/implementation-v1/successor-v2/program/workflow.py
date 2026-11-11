"""Complete declared programme: real producers, isolated modes, target-last grade.

All operation paths require a later explicit root scientific selection. Source
inspection is separate. External runtime/model-harness qualifications are
required deployment dependencies, not success callbacks or invented receipts.
"""
import math
import os
from pathlib import Path
import sys
import time
from .custody import Budget, capture, encode, need, new_directory, parse, pin, read_pin, write_json, write_new
from .parents import Parents
from .selection import CONDITIONS, GATES, CAUTIONS, admit, qualification
from .process import admit_original_process, execute, sandbox_argv
from .broker import Harness
from .views import stage, paired_views, sealed_program
from . import independent_reference


ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
       'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
       'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}


def compare_reports(left, right, people, tolerance):
    need(type(tolerance) in (int, float) and math.isfinite(tolerance) and 0 <= tolerance <= 1,
         'independently qualified numerical tolerance')
    maximum = 0.
    for p in people:
        for field in ('cells', 'contrasts'):
            need(set(left['participants'][p][field]) == set(right['participants'][p][field]), 'same reference identity set')
            for key, value in left['participants'][p][field].items():
                maximum = max(maximum, abs(value - right['participants'][p][field][key]))
    need(maximum <= tolerance, 'independent complete reference disagreement')
    return {'maximum_absolute_difference': maximum, 'qualified_tolerance': tolerance,
            'shared_liblinear_core': True, 'independent_numerical_solver_claimed': False}


def paired_condition_losses(outcomes, people):
    """Descriptive complete-case pairs with failures explicit, never a p-value.

    A missing/failed member gives an unavailable pair, not a zero loss or a
    favourable subset. These pairs are the same episode/cohort, not independent
    benchmarks or independent tests of neural-understanding ability.
    """
    need(set(outcomes) == set(CONDITIONS), 'all four original outcomes')
    need(len(people) == len(set(people)) == 33, 'fixed complete biological cohort')
    pairs = {}
    for name, left, right in (('B_minus_A_F', 'B_F', 'A_F'), ('B_minus_A_I', 'B_I', 'A_I'),
                              ('I_minus_F_A', 'A_I', 'A_F'), ('I_minus_F_B', 'B_I', 'B_F')):
        a, b = outcomes[left], outcomes[right]
        if 'grade' not in a or 'grade' not in b:
            pairs[name] = {'available': False, 'left': left, 'right': right,
                          'reason': 'one or both original outcomes failed or unavailable',
                          'loss_difference': None}
            continue
        ga, gb = a['grade'], b['grade']
        need(ga.get('status') == gb.get('status') == 'scored'
             and set(ga['per_participant']) == set(gb['per_participant'])
             and set(ga['per_participant']) == set(people), 'full paired original participant grades')
        participant = {}
        for person in ga['per_participant']:
            participant[person] = {}
            for metric in ('cell_mae', 'contrast_mae'):
                x, y = ga['per_participant'][person][metric], gb['per_participant'][person][metric]
                need(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (x, y)),
                     'finite complete participant losses')
                participant[person][metric] = x - y
        pairs[name] = {'available': True, 'left': left, 'right': right,
            'loss_difference': {metric: math.fsum(p[metric] for p in participant.values()) / 33
                                for metric in ('cell_mae', 'contrast_mae')},
            'per_participant_loss_difference': participant, 'lower_loss_is_better': True,
            'inference': None, 'independent_sample_count_claimed': False}
    return pairs


class Controller:
    def __init__(self, *, root, source_sha, entry, source_bytes, bindings, selection,
                 selection_pin, origin, startup_read_bytes=0):
        self.root, self.entry = Path(root), Path(entry)
        self.source_sha, self.source_bytes = source_sha, source_bytes
        self.selection, self.selection_pin = selection, selection_pin
        self.active_limits = selection['budget']
        admit(selection, selection['operation'], source_sha)
        caps = selection['budget']
        self.budget = Budget(seconds=caps['wall_seconds'], read_bytes=caps['read_bytes'],
                             write_bytes=caps['write_bytes'], origin=origin)
        self.budget.charge_read(startup_read_bytes)
        self.budget.read_completed += startup_read_bytes
        self.bindings = bindings
        self.verify_sources()
        self.parents = Parents(root, bindings, self.budget)
        self.identity = selection['execution_authority']['selection_id']
        self.work = None
        self.state = {'schema': 'neural098-complete-run-v1', 'selection': selection_pin,
                      'source_sha256': source_sha, 'task_id': 'NEURAL-098', 'selection_id': self.identity,
                      'completed_stages': [], 'failures': [], 'io_reservations': [], 'open_gates': list(GATES),
                      'scientific_cautions': CAUTIONS, 'scientific_qualification': False}
        self.packet = None
        self.reference = None

    def verify_sources(self):
        for d in self.bindings['source_files']:
            read_pin(self.root, d, 1_048_576, self.budget)

    def folder(self, name):
        return new_directory(self.work, name, self.budget)

    def record(self, name, value):
        d = write_json(self.work / (name + '.json'), value, self.budget)
        self.state['completed_stages'].append({'name': name, 'record': d})
        return d

    def assurance(self, role):
        return qualification(self.root, self.selection, role, self.source_sha, self.budget)

    def process(self, command, cwd, folder, suffix, *, profile):
        need(profile.get('aggregate_cgroup_custody') is True
             and profile.get('no_descendant_escape') is True
             and profile.get('controller_single_threaded') is True,
             'qualified complete Linux child ownership')
        return execute(command, cwd=cwd, env=ENV, group_parent=profile['cgroup_parent'],
                       group_name='n098-' + self.identity + '-' + suffix,
                       limits=self.active_limits, budget=self.budget, evidence=folder)

    def prepare(self):
        config = self.selection['operands']['preparation']
        need(set(config) == {'selection', 'python', 'observation_parent', 'observation_name'},
             'explicit complete preparation operands')
        selected_raw = read_pin(self.root, config['selection'], 1_048_576, self.budget)
        selected = parse(selected_raw)
        need(selected['enabled'] is True and selected['source_manifest_sha256'] ==
             self.bindings['preparer_source_manifest']['sha256'], 'accepted full33 preparer source')
        provenance = self.assurance('source-provenance')['properties']
        need(provenance.get('source_plan') == selected['source_plan']
             and provenance.get('source_root') == selected['source_root']
             and all(provenance.get(k) is True for k in
                     ('lawful_access_checked', 'complete33_authentic_source_mapping',
                      'actual_preprocessing_and_head_SSS_history_reviewed')),
             'independent actual full-source provenance before native preparation')
        self.record('P01_SOURCE_PROVENANCE', {'source_plan': selected['source_plan'],
                    'qualification': self.selection['qualifications']['source-provenance']})
        # Fixed original observer and worker ceilings, not an estimate of actual
        # source size. Failed or incomplete children never release reservations.
        # Observer counters are not returned by the legacy receipt; their full
        # reservation remains explicit rather than being called measured IO.
        prep_reservation = {'role': 'full33_preparation', 'worker_read_cap': 8 * 2**40,
            'worker_write_cap': 130 * 2**30, 'observer_read_cap': 272_000_000,
            'observer_write_cap': 8_000_000, 'actual_complete_io_known': False}
        self.budget.charge_read(prep_reservation['worker_read_cap'] + prep_reservation['observer_read_cap'])
        self.budget.charge_write(prep_reservation['worker_write_cap'] + prep_reservation['observer_write_cap'])
        self.state['io_reservations'].append(prep_reservation)
        need(self.budget.deadline - time.monotonic() > 21840 + 20,
             'entire original preparation observer allowance and outer cleanup remain')
        # The existing worker independently validates MNE1.13.2 native receipt,
        # full source plan/capacity and original21600/21720/21840 lifecycle.
        launch = self.assurance('trusted-launch')['properties']
        read_pin(self.root, config['python'], 256_000_000, self.budget)
        child = self.folder('preparation-process')
        path = self.root / self.bindings['preparer_entry']['path']
        argv = [config['python']['path'], '-B', str(path), '--repo', str(self.root),
                '--selection', str(self.root / config['selection']['path']),
                '--selection-sha256', config['selection']['sha256'],
                '--observation-parent', config['observation_parent'], '--observation-name', config['observation_name']]
        record = self.process(argv, self.root, child, 'prepare', profile=launch)
        observer_path = Path(config['observation_parent']) / config['observation_name'] / 'OBSERVATION.json'
        raw, observed = capture(observer_path, 4_000_000, self.budget)
        outer = parse(raw)
        need(outer['selection_sha256'] == config['selection']['sha256']
             and outer['source_manifest_sha256'] == self.bindings['preparer_source_manifest']['sha256']
             and outer['provisional_complete_preparation'] is True and outer['failure'] is None,
             'exact original preparation observation')
        life = outer['worker_lifecycle']
        need(life['exit_code'] == 0 and all(life.get(k) is True for k in
             ('natural_exit', 'process_reaped', 'process_group_absent', 'streams_closed', 'streams_eof')),
             'complete original preparation worker')
        work = Path(selected['output_parent']) / selected['output_name']
        completion = parse(read_pin(work, outer['completion_pin'], 4_000_000, self.budget))
        plan_raw = read_pin(self.root, selected['source_plan'], 4_000_000, self.budget)
        need(completion['source_plan_sha256'] == pin(encode(parse(plan_raw)))['sha256'],
             'raw selected plan pin separately joined to canonical-encoded completion digest')
        need(completion['all33_people_preserved'] is True and completion['all_retained_bindings_preserved'] is True,
             'complete original33 preparation')
        prep_reservation['worker_managed_read_reported'] = completion['managed_read_bytes']
        prep_reservation['worker_managed_write_before_completion_reported'] = completion['managed_write_bytes_before_completion']
        need(type(completion['managed_read_bytes']) is int and 0 <= completion['managed_read_bytes'] <= 8 * 2**40
             and type(completion['managed_write_bytes_before_completion']) is int
             and 0 <= completion['managed_write_bytes_before_completion'] <= 130 * 2**30,
             'bounded original preparation managed IO subtotal')
        packet_pin = dict(completion['outputs']['packet.json'], path=str(work / 'public/packet.json'))
        read_pin(self.root, packet_pin, 4_000_000, self.budget)
        self.packet = packet_pin
        return self.record('P03_PREPARATION', {'process': record, 'observation': observed,
                                             'packet': packet_pin, 'payload_admitted': False})

    def worker(self, role, packet, output, folder):
        """Real separate trusted native worker with reserved complete IO bounds."""
        launch = self.assurance('trusted-launch')['properties']
        worker_limits = self.selection['operands']['trusted_worker_limits']
        need(set(worker_limits) == {'read_bytes', 'write_bytes'} and all(type(x) is int and x > 0 for x in worker_limits.values()),
             'selected finite child logical IO reservations')
        self.budget.charge_read(worker_limits['read_bytes'])
        self.budget.charge_write(worker_limits['write_bytes'])
        self.state['io_reservations'].append({'role': role, **worker_limits,
                                             'actual_complete_io_known': False})
        job = {'schema': 'neural098-trusted-worker-job-v1', 'role': role, 'packet': packet,
               'output': str(output), 'selection': self.selection_pin, 'source_sha256': self.source_sha,
               'origin': self.budget.origin, 'deadline': self.budget.deadline,
               'read_bytes': worker_limits['read_bytes'], 'write_bytes': worker_limits['write_bytes']}
        job_pin = write_json(folder / 'JOB.json', job, self.budget)
        python = self.selection['operands']['analysis_python']
        read_pin(self.root, python, 256_000_000, self.budget)
        argv = [python['path'], '-I', '-B', str(self.entry), '--repo', str(self.root),
                '--source-bytes', str(self.source_bytes), '--source-sha256', self.source_sha,
                'trusted-worker', '--job', job_pin['path'], '--job-bytes', str(job_pin['bytes']),
                '--job-sha256', job_pin['sha256']]
        return self.process(argv, self.root, folder, role.lower(), profile=launch)

    def admit_packet(self):
        packet = self.packet or self.selection['operands']['packet']
        if self.packet is None:
            origin = self.assurance('packet-origin')['properties']
            need(origin.get('packet') == packet and all(origin.get(k) is True for k in
                 ('authentic_complete33_preparation_lineage', 'original_outer_natural_exit_zero',
                  'source_plan_and_history_authenticated', 'lawful_access_checked')),
                 'existing packet needs original preparation provenance, not a shape-only receipt')
        folder = self.folder('packet-admission-process')
        result_path = folder / 'RESULT.json'
        process = self.worker('ADMIT', packet, result_path, folder)
        raw, d = capture(result_path, 4_000_000, self.budget)
        result = parse(raw)
        need(result['packet'] == packet and result['source_sha256'] == self.source_sha
             and result['participants'] == 33 and result['support_cells'] == 2376, 'independent full packet join')
        self.packet = packet
        return self.record('P04_PACKET_ADMISSION', {'result': d, 'process': process, 'packet': packet})

    def references(self):
        need(self.packet is not None, 'full packet admission before reference')
        results = {}
        for role in ('R1', 'R2'):
            folder = self.folder('reference-' + role.lower())
            process = self.worker(role, self.packet, folder / 'RESULT.json', folder)
            raw, d = capture(folder / 'RESULT.json', 4_000_000, self.budget)
            result = parse(raw)
            need(result['packet'] == self.packet and result['source_sha256'] == self.source_sha
                 and result['role'] == role and result['fit_count'] == 330, 'complete selected reference identity')
            report = parse(read_pin(self.root, result['report'], 4_000_000, self.budget))
            self.parents.protocol['validate_report'](report, self.parents.people)
            results[role] = (result, report)
            self.record('P05_REFERENCE_' + role, {'result': d, 'process': process})
        policy = self.assurance('reference-numerics')['properties']
        need(policy.get('tolerance_empirically_qualified') is True, 'qualified reference numerical policy')
        audit = compare_reports(results['R1'][1], results['R2'][1], self.parents.people, policy['absolute_tolerance'])
        self.reference = results['R1'][0]['report']
        return self.record('P06_REFERENCE_AUDIT', {'audit': audit, 'reference': self.reference,
                                                'packet': self.packet, 'fit_counts': {'R1': 330, 'R2': 330}})

    def agent_condition(self, condition):
        limits = self.selection['operands']['condition_limits']
        need(type(limits) is dict and set(limits) == set(self.selection['budget'])
             and all(type(v) is int and v > 0 for v in limits.values()), 'same complete condition resource envelope')
        outer, previous_limits = self.budget, self.active_limits
        need(outer.deadline - time.monotonic() > limits['wall_seconds'] + 10,
             'entire condition allowance plus reporting remains before dispatch')
        outer.charge_read(limits['read_bytes']); outer.charge_write(limits['write_bytes'])
        inner = Budget(seconds=limits['wall_seconds'], read_bytes=limits['read_bytes'], write_bytes=limits['write_bytes'])
        cost_record = {'role': condition, 'read_bytes': limits['read_bytes'],
                       'write_bytes': limits['write_bytes'], 'actual_complete_io_known': False}
        self.state['io_reservations'].append(cost_record)
        self.budget, self.parents.budget, self.active_limits = inner, inner, limits
        self.condition_stage = 'qualification'
        try:
            return self._agent_condition(condition)
        except BaseException as error:
            process_record = getattr(error, 'record', {}) or {}
            if process_record:
                error.evaluation_status = 'candidate_timeout' if process_record.get('timed_out') else 'candidate_failure'
            elif self.condition_stage in ('seal_program', 'collect_report'):
                error.evaluation_status = 'invalid_submission' if isinstance(error, (ValueError, TypeError, KeyError, FileNotFoundError)) else 'collection_failure'
            else:
                error.evaluation_status = 'operator_error'
            error.condition_stage = self.condition_stage
            raise
        finally:
            cost_record['controller_io_subtotal'] = inner.record()
            cost_record['elapsed_seconds'] = time.monotonic() - inner.origin
            cost_record['actual_child_cpu_usec'] = getattr(inner, 'cpu_usec', 0)
            outer.read_completed += inner.read_completed
            outer.write_completed += inner.write_completed
            outer.cpu_usec = getattr(outer, 'cpu_usec', 0) + getattr(inner, 'cpu_usec', 0)
            self.budget, self.parents.budget, self.active_limits = outer, outer, previous_limits

    def _agent_condition(self, condition):
        need(condition in CONDITIONS and self.packet is not None and self.reference is not None,
             'whole selected episode prerequisites')
        arm, mode = condition.split('_')
        iso = self.assurance('candidate-isolation')['properties']
        runtime_root = Path(iso['runtime_root'])
        need(runtime_root.is_absolute() and runtime_root != Path('/')
             and not self.root.is_relative_to(runtime_root) and not runtime_root.is_relative_to(self.root),
             'candidate runtime cannot be the operator repository or an ancestor/descendant')
        need(all(iso.get(k) is True for k in ('operator_private_tree_absent', 'bounded_workspace_quota',
             'agent_source_and_model_harness_qualified', 'no_shared_session_cache')),
             'qualified actual candidate isolation, storage and model harness')
        condition_limits = self.selection['operands']['condition_limits']
        need(4 * condition_limits['agent_tokens'] <= self.selection['budget']['agent_tokens']
             and 4 * condition_limits['agent_invocations'] <= self.selection['budget']['agent_invocations'],
             'whole campaign includes four equal agent ceilings')
        namespace = self.folder('condition-' + condition.lower())
        author_view = new_directory(namespace, 'author-input', self.budget)
        author_work = new_directory(namespace, 'author-work', self.budget)
        author_evidence = new_directory(namespace, 'author-evidence', self.budget)
        author = stage(self.root, self.bindings, arm=arm, mode=mode, phase='author',
                       packet_pin=self.packet if mode == 'I' else None, destination=author_view,
                       budget=self.budget, parents=self.parents)
        prompt = read_pin(self.root, self.selection['operands']['prompt'], 65536, self.budget)
        prompt_pin = write_new(author_view / 'AGENT_REQUEST.txt', prompt, self.budget, 65536)
        harness = Harness(iso['harness'], self.budget)
        primary = None; closure = None; author_process = None
        try:
            self.condition_stage = 'candidate_author'
            session = harness.begin(selection_id=self.identity, condition=condition,
                                    prompt_sha256=prompt_pin['sha256'], token_limit=condition_limits['agent_tokens'],
                                    invocation_limit=condition_limits['agent_invocations'])
            cmd = sandbox_argv(iso, view=author_view, work=author_work,
                    command=iso['agent_command'] + ['--request', '/input/AGENT_REQUEST.txt',
                    '--output-program', '/work/program.py', '--model-socket', '/run/model.sock'],
                    model_socket=session['model_socket'])
            author_process = self.process(cmd, namespace, author_evidence,
                                          condition.lower() + '-author', profile=iso)
        except BaseException as error:
            primary = error
        finally:
            try:
                closure = harness.close()
            except BaseException as error:
                if primary is None:
                    primary = error
                else:
                    primary.add_note('Independent harness cleanup failed: ' + type(error).__name__)
                primary.cleanup_uncertain = True
            try:
                write_json(author_evidence / 'HARNESS.json', {'closure': closure, 'transcript': harness.transcript,
                     'failure': None if primary is None else type(primary).__name__}, self.budget)
            except BaseException as error:
                if primary is None:
                    primary = error
            if primary is not None:
                primary.harness_closure = closure
                primary.harness_transcript = harness.transcript
                if not hasattr(primary, 'known_output_prefix'):
                    primary.known_output_prefix = str(namespace)
                raise primary
        self.condition_stage = 'seal_program'
        program_raw, program_pin = sealed_program(author_work / 'program.py', self.budget)
        # F's first packet exposure occurs only after this source seal. I is
        # also replayed without model feedback in a fresh namespace.
        replay_view = new_directory(namespace, 'replay-input', self.budget)
        replay_work = new_directory(namespace, 'replay-work', self.budget)
        replay_evidence = new_directory(namespace, 'replay-evidence', self.budget)
        replay = stage(self.root, self.bindings, arm=arm, mode=mode, phase='replay', packet_pin=self.packet,
                       destination=replay_view, budget=self.budget, parents=self.parents)
        write_new(replay_view / 'program.py', program_raw, self.budget, 1_048_576)
        cmd = sandbox_argv(iso, view=replay_view, work=replay_work,
                command=[iso['python_inside'], '-I', '-B', '/input/program.py',
                         '--packet', '/input/data/packet.json', '--output', '/work/analysis.json'])
        self.condition_stage = 'candidate_replay'
        replay_process = self.process(cmd, namespace, replay_evidence,
                                      condition.lower() + '-replay', profile=iso)
        self.condition_stage = 'collect_report'
        raw, report_pin = capture(replay_work / 'analysis.json', 4_000_000, self.budget)
        candidate = parse(raw)
        self.parents.protocol['validate_report'](candidate, self.parents.people)
        self.condition_stage = 'private_score'
        grade = self.parents.score(candidate, self.reference)
        result = {'schema': 'neural098-condition-result-v1', 'condition': condition,
                  'packet': self.packet, 'program': program_pin, 'report': report_pin, 'grade': grade,
                  'author_view': author, 'replay_view': replay, 'author_process': author_process,
                  'replay_process': replay_process, 'harness_closure': closure,
                  'method_conformance_authenticated': False, 'scientific_qualification': False}
        self.record('P12_' + condition, result)
        return result

    def report(self, outcomes):
        need(set(outcomes) == set(CONDITIONS), 'all condition successes/failures retained')
        for mode in ('F', 'I'):
            a, b = outcomes['A_' + mode], outcomes['B_' + mode]
            if 'replay_view' in a and 'replay_view' in b:
                paired_views(a['replay_view'], b['replay_view'])
        report = self.record('P13_REPORT', {'schema': 'neural098-campaign-report-v1',
            'outcomes': outcomes, 'conditions': list(CONDITIONS), 'task_count': 1,
            'paired_descriptive_loss_differences': paired_condition_losses(outcomes, self.parents.people),
            'participants': 33, 'support_cells': 2376, 'fits_per_complete_pipeline': 330,
            'accuracy_cells': 1386, 'contrasts': 792, 'budget': self.budget.record(),
            'actual_cpu_usec': getattr(self.budget, 'cpu_usec', 0), 'open_gates': list(GATES),
            'io_reservations': self.state['io_reservations'],
            'scientific_cautions': CAUTIONS, 'p_values': None, 'confidence_intervals': None,
            'scientific_qualification': False, 'public_push': False})
        self.record('P14_ROOT_PUBLICATION_AUDIT_INPUT', {'schema': 'neural098-root-publication-audit-input-v1',
            'ordinary_source_dependencies': self.bindings['source_files'], 'whole_source_sha256': self.source_sha,
            'report_identity_operator_private': report, 'approved_for_publication': False,
            'root_audit_required': True, 'private_history_push_allowed': False,
            'raw_data_and_reference_answers_excluded_from_source_proposal': True})
        return report

    def run(self):
        primary = None
        try:
            envelope = self.assurance('controller-envelope')['properties']
            need(envelope.get('controller_pid') == os.getpid()
                 and envelope.get('selection_id') == self.identity
                 and envelope.get('whole_budget') == self.selection['budget']
                 and all(envelope.get(k) is True for k in
                         ('independent_original_supervisor', 'controller_and_descendants_in_aggregate_envelope',
                          'hard_wall_cpu_memory_storage_limits', 'startup_and_cleanup_within_original_deadline')),
                 'independent complete controller lifetime qualification required')
            self.work = new_directory(self.selection['output_parent'], self.selection['output_name'], self.budget)
            self.record('P00_SELECTION', self.state.copy())
            self.record('P02_ENVIRONMENT_SELECTION', {'qualified_controller_envelope':
                self.selection['qualifications']['controller-envelope'],
                'role_specific_native_and_isolation_qualifications': self.selection['qualifications'],
                'all_empirical_gates_closed_here': False})
            operation = self.selection['operation']
            if operation == 'prepare':
                self.prepare()
            elif operation in ('admit-packet', 'derive-reference', 'campaign', 'evaluate'):
                if operation == 'campaign' and 'preparation' in self.selection['operands']:
                    self.prepare()
                self.admit_packet()
                if operation != 'admit-packet':
                    self.references()
                if operation in ('campaign', 'evaluate'):
                    limits = self.selection['operands']['condition_limits']
                    need(self.budget.deadline - time.monotonic() > 4 * limits['wall_seconds'] + 20,
                         'reserve all four equal condition time ceilings and reporting')
                    need(getattr(self.budget, 'cpu_usec', 0) + 4 * limits['cpu_seconds'] * 1_000_000
                         <= self.selection['budget']['cpu_seconds'] * 1_000_000,
                         'whole CPU envelope includes all four equal condition ceilings')
                    self.record('P07_EPISODE_POLICY', {'conditions': list(CONDITIONS), 'condition_limits': limits,
                        'exposure': self.selection['exposure'], 'packet': self.packet,
                        'private_reference': self.reference, 'model_feedback': 'none',
                        'prior_source_exposure': ['NEURAL-097', 'PAPER-paper-method-add-010'],
                        'episode_count': 1, 'task_count': 1})
                    outcomes = {}
                    for condition in CONDITIONS:
                        try:
                            outcomes[condition] = self.agent_condition(condition)
                        except Exception as error:
                            outcomes[condition] = {'condition': condition, 'status': getattr(error, 'evaluation_status', 'operator_error'),
                                'stage': getattr(error, 'condition_stage', None),
                                'error_type': type(error).__name__, 'process': getattr(error, 'record', None),
                                'known_output_prefix': getattr(error, 'known_output_prefix', None),
                                'harness_closure': getattr(error, 'harness_closure', None),
                                'harness_transcript': getattr(error, 'harness_transcript', None),
                                'cleanup_uncertain': getattr(error, 'cleanup_uncertain', False)}
                            self.state['failures'].append(outcomes[condition])
                            # If isolation/cleanup is unresolved, no subsequent
                            # condition starts. Report every unattempted outcome.
                            if getattr(error, 'cleanup_uncertain', False) or (getattr(error, 'record', {}) or {}).get('cleanup_errors'):
                                break
                    for condition in CONDITIONS:
                        outcomes.setdefault(condition, {'condition': condition, 'status': 'not_attempted_after_failure'})
                    self.report(outcomes)
                    need(not self.state['failures'], 'complete campaign contains candidate failures')
            elif operation == 'collect':
                admitted = self.assurance('collection-input')['properties']
                evidence = admit_original_process(root=self.root,
                    process_pin=self.selection['operands']['original_process_record'],
                    candidate_pin=self.selection['operands']['candidate_report'], outer=admitted,
                    stream_cap=self.selection['budget']['stream_bytes'], budget=self.budget)
                raw = read_pin(self.root, self.selection['operands']['candidate_report'], 4_000_000, self.budget)
                report = parse(raw); self.parents.protocol['validate_report'](report, self.parents.people)
                self.record('P11_COLLECTED', {'report': self.selection['operands']['candidate_report'],
                    'process': self.selection['operands']['original_process_record'],
                    'original_process_admission': evidence, 'candidate_admitted': True})
            elif operation == 'grade':
                admitted = self.assurance('grade-input')['properties']
                need(admitted.get('candidate_admitted_before_target') is True
                     and admitted.get('candidate_report') == self.selection['operands']['candidate_report']
                     and admitted.get('reference_report') == self.selection['operands']['reference_report']
                     and admitted.get('same_packet_and_reference_recipe') is True,
                     'independently admitted original candidate/reference lineage')
                raw = read_pin(self.root, self.selection['operands']['candidate_report'], 4_000_000, self.budget)
                candidate = parse(raw)
                self.parents.protocol['validate_report'](candidate, self.parents.people)
                self.record('P12_GRADE', self.parents.score(candidate, self.selection['operands']['reference_report']))
            elif operation == 'report':
                admitted = self.assurance('report-input')['properties']
                need(admitted.get('condition_results') == self.selection['operands']['condition_results']
                     and admitted.get('all_original_outcomes_retained') is True
                     and admitted.get('same_packet_recipe_model_and_budgets') is True,
                     'independently selected whole original comparison lineage')
                outcomes = {k: parse(read_pin(self.root, d, 4_000_000, self.budget))
                            for k, d in self.selection['operands']['condition_results'].items()}
                self.report(outcomes)
            self.verify_sources(); self.parents.unchanged(); self.budget.check()
            self.state['complete_source_programme_operation'] = True
            self.state['independent_outer_natural_exit_required'] = True
            self.state['budget'] = self.budget.record()
            result = self.record('COMPLETE', self.state.copy())
            self.budget.check()
            return result
        except BaseException as error:
            primary = error
            self.state['complete_source_programme_operation'] = False
            self.state['failure'] = {'type': type(error).__name__, 'known_output_prefix':
                getattr(error, 'known_output_prefix', str(self.work) if self.work else None),
                'cleanup_uncertain': getattr(error, 'cleanup_uncertain', False),
                'original_process_admission': getattr(error, 'original_process_admission', None)}
            self.state['budget'] = self.budget.record()
            if self.work is not None:
                try:
                    write_json(self.work / 'FAILURE.json', self.state, self.budget)
                except BaseException as retention:
                    error.add_note('Failure retention uncertainty: ' + type(retention).__name__)
            raise


def trusted_worker(*, root, bindings, selection, source_sha, job, startup_read_bytes):
    need(job['schema'] == 'neural098-trusted-worker-job-v1' and job['role'] in ('ADMIT', 'R1', 'R2')
         and job['source_sha256'] == source_sha, 'closed selected scientific worker role')
    admit(selection, selection['operation'], source_sha)
    need(selection['operation'] in ('campaign', 'evaluate', 'admit-packet', 'derive-reference'), 'selected worker parent operation')
    budget = Budget(seconds=job['deadline'] - job['origin'], read_bytes=job['read_bytes'],
                    write_bytes=job['write_bytes'], origin=job['origin'])
    budget.charge_read(startup_read_bytes)
    qualification(root, selection, 'analysis', source_sha, budget)
    parents = Parents(root, bindings, budget)
    packet, features = parents.packet(job['packet'], native_qualified=True)
    result = {'schema': 'neural098-trusted-worker-result-v1', 'role': job['role'],
              'packet': job['packet'], 'source_sha256': source_sha, 'participants': 33,
              'support_cells': 2376, 'row_count': len(packet['rows']), 'scientific_qualification': False}
    if job['role'] in ('R1', 'R2'):
        try:
            produced = parents.reference_r1(packet, features) if job['role'] == 'R1' else independent_reference.derive(features, packet['rows'], parents.people)
            parents.protocol['validate_report'](produced['report'], parents.people)
            need(len(produced['fit_records']) == 330, 'complete330 scientific fit ledger')
            output = Path(job['output'])
            result['report'] = write_json(output.with_name('REFERENCE.json'), produced['report'], budget)
            result['fit_record'] = write_json(output.with_name('FIT_RECORDS.json'), produced['fit_records'], budget, 8_000_000)
            result['fit_count'] = 330
        except BaseException as error:
            fits = getattr(error, 'completed_fit_records', getattr(error, 'fit_records', []))
            try:
                need(type(fits) is list and len(fits) <= 330, 'bounded known failed-fit prefix')
                prefix = write_json(Path(job['output']).with_name('PARTIAL_FITS.json'), fits, budget, 8_000_000)
                write_json(Path(job['output']).with_name('FAILURE.json'),
                    {'schema': 'neural098-trusted-reference-failure-v1', 'role': job['role'],
                     'error_type': type(error).__name__, 'partial_fits': prefix,
                     'complete_reference': False, 'budget': budget.record()}, budget)
            except BaseException as retention:
                error.add_note('Partial reference retention uncertainty: ' + type(retention).__name__)
            raise
    parents.unchanged(); budget.check()
    result['budget'] = budget.record()
    return write_json(job['output'], result, budget)
