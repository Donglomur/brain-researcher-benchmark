"""Source-owned original process custody and irreversible target-last workflow.

The host subprocess route is ONLY for tiny invented engineering controls. Actual
candidate isolation must use a separately qualified external executor; no host
subprocess receipt here establishes a protected sandbox.
"""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import time
import math
import resource
from .base import (require, loads, encode, digest, sha256, safe_member, read_member,
                   read_json, write_json, receipt, ContractError)
from .scoring import validate_submission, score, terminal_report


def run_engineering_producer(program, public_path, output_dir, timeout=10., output_cap=1048576):
    public = read_json(public_path)
    require(public.get('synthetic') is True, 'host_executor_engineering_only')
    require(timeout > 0 and output_cap > 0, 'resource_caps')
    program = Path(program).resolve()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    body = read_member(program.parent, program.name, 131072)
    output = output_dir / 'submission.json'
    command = [sys.executable, '-I', '-B', str(program), str(Path(public_path).resolve()),
               str(output.resolve())]
    started = time.time_ns()
    start_mono = time.monotonic()

    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, math.ceil(timeout)), max(2, math.ceil(timeout) + 1)))
        resource.setrlimit(resource.RLIMIT_FSIZE, (output_cap, output_cap))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    log = output_dir / 'process.log'
    timed_out = False
    with log.open('wb') as stream:
        process = subprocess.Popen(command, cwd=output_dir, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'},
                                   start_new_session=True, preexec_fn=limits)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    def alive():
        try: os.killpg(process.pid, 0); return True
        except ProcessLookupError: return False
    descendants = alive()
    if descendants:
        os.killpg(process.pid, signal.SIGKILL)
        # Do not claim closed while reparented descendants remain visible.
        for _ in range(20):
            if not alive(): break
            time.sleep(.01)
    closed = not alive()
    changed = sha256(read_member(program.parent, program.name, 131072)) != sha256(body)
    return {'schema': 'neural_original_process_receipt_v1', 'pid': process.pid,
            'process_group': process.pid, 'started_wall_ns': started, 'ended_wall_ns': time.time_ns(),
            'elapsed_seconds': time.monotonic() - start_mono, 'returncode': code,
            'timeout': timed_out, 'descendants_detected': descendants,
            'process_group_closed': closed, 'program_changed': changed,
            'program_sha256': sha256(body), 'command': command,
            'input_sha256': sha256(Path(public_path).read_bytes()),
            'output_cap': output_cap, 'log_sha256': sha256(read_member(output_dir, 'process.log', output_cap)),
            'engineering_only': True, 'production_sandbox_qualified': False}


def exposure_check(entries, actor, source_digest, query_animals):
    """Consume the common ledger; never write another owner's shared ledger."""
    forbidden = {'paper_reproduction', 'training', 'query_target', 'closed_interpretation'}
    collisions = [e for e in entries if e['actor'] == actor and
                  e['source_digest'] == source_digest and e['role'] in forbidden and
                  set(e['animals']) & set(query_animals)]
    require(not collisions, 'cross_task_or_fold_target_exposure')
    return {'actor': actor, 'source_digest': source_digest, 'query_animals': sorted(query_animals),
            'prior_exposure_checked': True, 'public_pretraining_exposure_not_erased': True}


class Workflow:
    def __init__(self, root):
        self.root = Path(root)
        self.state_path = self.root / 'state.json'

    def begin(self, plan):
        require(not self.root.exists(), 'workflow_root_exists')
        require(plan['synthetic'] is True, 'actual_science_execution_paused')
        require(plan['jobs'] and len(set(plan['jobs'])) == len(plan['jobs']), 'plan_jobs')
        require(set(plan['programs']) == set(plan['jobs']), 'precommitted_producer_for_every_job')
        require(all(x is None or (isinstance(x, str) and len(x) == 64) for x in plan['programs'].values()),
                'precommitment_hash')
        from .terminal import prebank_sources
        terminal_sources = prebank_sources(plan)
        self.root.mkdir(parents=True)
        write_json(self.root / 'plan.json', plan, True)
        state = {'phase': 'preparation', 'plan_digest': digest(plan), 'jobs': {},
                 'history': [], 'private_targets_opened': False, 'terminal_routines': {}}
        for job, (descriptor, body) in terminal_sources.items():
            relative = 'committed_interpreters/' + descriptor['source_sha256'] + '.py'
            source = safe_member(self.root, relative); source.parent.mkdir(exist_ok=True)
            if source.exists(): require(sha256(read_member(source.parent, source.name, 131072)) == sha256(body), 'shared_terminal_source_changed')
            else:
                with source.open('xb') as stream: stream.write(body)
            commitment = {k: v for k, v in descriptor.items() if k != 'source_path'}
            commitment.update(source_relative_path=relative, source_bytes=len(body), state='committed_before_query_bank')
            state['terminal_routines'][job] = commitment
            self._event(state, 'F_terminal_routine_committed_before_bank', job=job,
                        commitment_digest=digest(commitment), source_sha256=descriptor['source_sha256'])
        self._save(state)

    def _state(self):
        state = read_json(self.state_path)
        require(digest(read_json(self.root / 'plan.json')) == state['plan_digest'], 'plan_changed')
        return state

    def _save(self, state):
        pending = self.root / 'state.pending'
        write_json(pending, state)
        pending.replace(self.state_path)

    def _event(self, state, kind, **fields):
        prior = state['history'][-1] if state['history'] else None
        item = receipt(kind, [], [], prior, timestamp_ns=time.time_ns(), **fields)
        state['history'].append(item)
        return item

    def prepare_job(self, job, public, private_query):
        state = self._state()
        plan = read_json(self.root / 'plan.json')
        require(state['phase'] == 'preparation' and job in plan['jobs'] and job not in state['jobs'],
                'job_preparation_state')
        require(public['synthetic'] is True, 'invented_inputs_only')
        from .contracts import cell, assert_endpoint_applicable
        c = cell(public['cell_id'], public['task'])
        assert_endpoint_applicable(public['cell_id'], public['task'], public['endpoint'])
        require(public['endpoint_support']['schema'] == 'endpoint_eligibility_summary_v1' and
                public['endpoint_support']['endpoint'] == public['endpoint'], 'prepared_endpoint_support_binding')
        require((c['mode'] == 'I' and plan['programs'][job] is None) or
                (c['mode'] == 'F' and plan['programs'][job] is not None), 'mode_precommitment')
        if c['tier'] == 'XM':
            from .contracts import validate_model_tool
            validate_model_tool(public['cell_id'], plan['model_tools'][job], digest(public['training']), public['task'])
        if c['mode'] == 'F':
            for previous_job, old in state['jobs'].items():
                if (old['cell_id'] == public['cell_id'] and old['task'] == public['task'] and
                        plan.get('reference_roles', {}).get(previous_job) == plan.get('reference_roles', {}).get(job)):
                    require(plan['programs'][previous_job] == plan['programs'][job],
                            'F_program_changes_across_queries')
                    require(state['terminal_routines'][previous_job]['source_sha256'] ==
                            state['terminal_routines'][job]['source_sha256'],
                            'F_terminal_routine_changes_across_queries')
        folder = safe_member(self.root, 'jobs/' + job)
        write_json(folder / 'public' / 'input.json', public, True)
        write_json(folder / 'operator' / 'targets.json', private_query, True)
        state['jobs'][job] = {'state': 'prepared', 'input_digest': digest(public),
                              'private_digest': digest(private_query),
                              'cell_id': public['cell_id'], 'task': public['task'],
                              'program_sha256': plan['programs'][job]}
        self._event(state, 'prepare', job=job, input_digest=digest(public),
                    private_digest=digest(private_query))
        self._save(state)

    def commit_interactive_program(self, job, program):
        state = self._state()
        from .contracts import cell
        info = state['jobs'][job]
        require(info['state'] == 'prepared' and info['program_sha256'] is None and
                cell(info['cell_id'], info['task'])['mode'] == 'I', 'interactive_commit_state')
        program = Path(program)
        value = sha256(read_member(program.parent, program.name, 131072))
        info['program_sha256'] = value
        self._event(state, 'interactive_program_committed_after_query', job=job, source_sha256=value)
        self._save(state)
        return value

    def collect(self, job, process_receipt, output_name='submission.json'):
        state = self._state()
        require(state['phase'] in ('preparation', 'production') and
                state['jobs'][job]['state'] == 'prepared', 'collect_state')
        state['phase'] = 'production'
        folder = safe_member(self.root, 'jobs/' + job)
        public = read_json(folder / 'public' / 'input.json')
        require(digest(public) == state['jobs'][job]['input_digest'], 'public_input_changed')
        write_json(folder / 'operator' / 'process_receipt.json', process_receipt, True)
        try:
            plan = read_json(self.root / 'plan.json')
            require(process_receipt['program_sha256'] == state['jobs'][job]['program_sha256'],
                    'producer_not_precommitted')
            require(process_receipt['input_sha256'] == sha256((folder / 'public' / 'input.json').read_bytes()),
                    'process_input_receipt_mismatch')
            require(process_receipt['log_sha256'] == sha256(read_member(folder / 'outputs', 'process.log', process_receipt['output_cap'])),
                    'process_log_receipt_mismatch')
            require(process_receipt['engineering_only'] is True and
                    process_receipt['process_group_closed'] is True and
                    process_receipt['returncode'] == 0 and
                    not process_receipt['timeout'] and not process_receipt['program_changed'] and
                    not process_receipt['descendants_detected'], 'producer_not_cleanly_closed')
            raw = read_member(folder / 'outputs', output_name, process_receipt['output_cap'])
            submission = loads(raw, process_receipt['output_cap'])
            validate_submission(submission, public)
            allowed_outputs = {output_name, 'process.log'}
            if public['task'] == 'NEURAL-046':
                allowed_outputs |= {'analysis.json'} | {'model_' + name + '.json' for name in submission['model_artifact_digests']}
            members = list((folder / 'outputs').iterdir())
            require({p.name for p in members} == allowed_outputs and
                    all(p.is_file() and not p.is_symlink() for p in members), 'output_bundle_members')
            require(sum(p.stat().st_size for p in members) <= process_receipt['output_cap'],
                    'aggregate_output_bundle_cap')
            if public['task'] == 'NEURAL-046':
                from .models import audit_models
                artifacts = {}
                for name, expected_digest in submission['model_artifact_digests'].items():
                    artifact = loads(read_member(folder / 'outputs', 'model_' + name + '.json',
                                                  process_receipt['output_cap']),
                                     process_receipt['output_cap'])
                    require(digest(artifact) == expected_digest, 'model_artifact_digest')
                    artifacts[name] = artifact
                audited, analysis = audit_models(public, artifacts, return_evidence=True)
                require(digest(audited) == digest(submission['predictions']),
                        'registered_model_prediction_mismatch')
                write_json(folder / 'operator' / 'sealed_models.json', artifacts, True)
                submitted_analysis = read_json(folder / 'outputs' / 'analysis.json')
                require(digest(submitted_analysis) == digest(analysis), 'analysis_or_sensitivity_mismatch')
                write_json(folder / 'operator' / 'sealed_analysis.json', analysis, True)
                state['jobs'][job]['analysis_digest'] = digest(analysis)
            write_json(folder / 'operator' / 'sealed_submission.json', submission, True)
            state['jobs'][job].update(state='sealed', submission_digest=digest(submission))
            self._event(state, 'collect_seal', job=job, submission_digest=digest(submission),
                        process_receipt_digest=digest(process_receipt))
        except Exception as error:
            state['jobs'][job].update(state='failed', reason=type(error).__name__ + ':' + str(error))
            self._event(state, 'collect_failure', job=job, reason=state['jobs'][job]['reason'])
        self._save(state)
        return state['jobs'][job]['state']

    def close(self):
        state = self._state(); plan = read_json(self.root / 'plan.json')
        require(set(state['jobs']) == set(plan['jobs']), 'unattempted_required_job')
        require(all(j['state'] in ('sealed', 'failed') for j in state['jobs'].values()), 'unclosed_job')
        state['phase'] = 'closed' if all(j['state'] == 'sealed' for j in state['jobs'].values()) else 'failed'
        self._event(state, 'close_panel', result=state['phase'], targets_opened=False)
        self._save(state)
        return state['phase']

    def grade_once(self):
        state = self._state()
        require(state['phase'] == 'closed' and state['private_targets_opened'] is False,
                'irreversible_grade_state')
        # Persist the consumption bit BEFORE opening any private target.
        state['private_targets_opened'] = True
        state['phase'] = 'grading'
        self._event(state, 'grade_consumed')
        self._save(state)
        results = {}
        try:
            plan = read_json(self.root / 'plan.json')
            for job, info in state['jobs'].items():
                folder = safe_member(self.root, 'jobs/' + job)
                public = read_json(folder / 'public' / 'input.json')
                require(digest(public) == info['input_digest'], 'public_changed_after_collection')
                submission = read_json(folder / 'operator' / 'sealed_submission.json')
                require(digest(submission) == info['submission_digest'], 'sealed_output_changed')
                hidden = read_json(folder / 'operator' / 'targets.json')
                require(digest(hidden) == info['private_digest'], 'private_target_changed')
                results[job] = score(submission, public, hidden,
                    {'all_required_producers_closed': True, 'all_required_artifacts_sealed': True,
                     'private_targets_opened_before_closure': False})
                if public['task'] == 'NEURAL-046':
                    analysis = read_json(folder / 'operator' / 'sealed_analysis.json')
                    require(digest(analysis) == info['analysis_digest'], 'sealed_analysis_changed')
                    from .scoring import score_sensitivities
                    results[job]['analysis'] = {k: v for k, v in analysis.items()
                                               if k not in ('sensitivity_models', 'sensitivity_predictions')}
                    results[job]['mandatory_sensitivity'] = score_sensitivities(
                        analysis['sensitivity_predictions'], public, hidden)
            for candidate, reference in plan.get('reference_jobs', {}).items():
                require(candidate in results and reference in results, 'missing_reference_job')
                require(results[candidate]['task'] == results[reference]['task'] == 'NEURAL-045',
                        'reference_wrong_task')
                cc, rr = results[candidate]['metrics'], results[reference]['metrics']
                require(set(cc['animals']) == set(rr['animals']), 'reference_animal_mismatch')
                # Both jobs must bind the exact same protected cases and grid.
                require(state['jobs'][candidate]['private_digest'] == state['jobs'][reference]['private_digest'],
                        'reference_target_mismatch')
                zero = [a for a, v in rr['animals'].items() if v['mse'] == 0]
                cc['undefined_reference_animals'] = zero
                cc['reference_relative_skill'] = None if zero else sum(
                    1 - v['mse'] / rr['animals'][a]['mse'] for a, v in cc['animals'].items()) / len(cc['animals'])
                cc['reference_job'] = reference
            write_json(self.root / 'closed_results.json', results, True)
            from .scoring import interpretation_packet
            packets = {j: interpretation_packet(r) for j, r in results.items()}
            write_json(self.root / 'interpretation_packets.json', packets, True)
            state['phase'] = 'interpretation'
            state['results_digest'] = digest(results)
            state['interpretation_digest'] = digest(packets)
            self._event(state, 'closed_evidence', result_digest=digest(results))
        except Exception as error:
            state['phase'] = 'scorer_failed'
            self._event(state, 'scorer_failure', error=type(error).__name__ + ':' + str(error))
            self._save(state)
            raise
        self._save(state)
        return results

    def run_terminal_routines(self):
        """Apply the exact F programmes only after numerical production/grading closes."""
        state = self._state()
        require(state['phase'] == 'interpretation', 'terminal_execution_state')
        packets = read_json(self.root / 'interpretation_packets.json')
        require(digest(packets) == state['interpretation_digest'], 'terminal_packets_changed')
        from .terminal import collect_result
        for job, commitment in state['terminal_routines'].items():
            if commitment['state'] == 'sealed': continue
            require(commitment['state'] == 'committed_before_query_bank', 'terminal_routine_already_consumed')
            source = safe_member(self.root, commitment['source_relative_path'])
            require(sha256(read_member(source.parent, source.name, 131072)) == commitment['source_sha256'],
                    'committed_terminal_source_changed')
            folder = safe_member(self.root, 'terminal/' + job)
            write_json(folder / 'input.json', packets[job], True)
            # Consume before executing, so a failure cannot become adaptive retries.
            commitment['state'] = 'consumed'
            self._event(state, 'F_terminal_execution_consumed', job=job, packet_digest=digest(packets[job]))
            self._save(state)
            try:
                original = run_engineering_producer(source, folder / 'input.json', folder / 'outputs',
                    commitment['timeout_seconds'], commitment['output_cap_bytes'])
                write_json(folder / 'process_receipt.json', original, True)
                value = collect_result(folder, original, commitment, packets[job])
                write_json(folder / 'sealed_interpretation.json', value, True)
                commitment.update(state='sealed', result_digest=digest(value), process_receipt_digest=digest(original))
                self._event(state, 'F_terminal_committed_result_sealed', job=job,
                            result_digest=digest(value), process_receipt_digest=digest(original))
            except Exception as error:
                commitment.update(state='failed', reason=type(error).__name__ + ':' + str(error))
                state['phase'] = 'terminal_failed'
                self._event(state, 'F_terminal_failure', job=job, reason=commitment['reason'])
                self._save(state)
                raise
            self._save(state)
        return {j: c['state'] for j, c in state['terminal_routines'].items()}

    def finish(self, interpretations):
        state = self._state()
        require(state['phase'] == 'interpretation', 'terminal_report_state')
        results = read_json(self.root / 'interpretation_packets.json')
        # I may adapt its report after evidence. F receives only its prebank programme's result.
        expected_interactive = set(results) - set(state['terminal_routines'])
        require(digest(results) == state['interpretation_digest'] and set(interpretations) == expected_interactive,
                'terminal_evidence_binding')
        self.run_terminal_routines()
        state = self._state(); reports = {}
        for job, packet in results.items():
            if job in state['terminal_routines']:
                commitment = state['terminal_routines'][job]
                value = read_json(self.root / 'terminal' / job / 'sealed_interpretation.json')
                original = read_json(self.root / 'terminal' / job / 'process_receipt.json')
                require(commitment['state'] == 'sealed' and digest(value) == commitment['result_digest'],
                        'terminal_committed_result_changed')
                require(digest(original) == commitment['process_receipt_digest'],
                        'terminal_original_receipt_changed')
                from .terminal import validate_result
                validate_result(value, packet)
                reports[job] = terminal_report(packet, value)
                reports[job]['mode'] = 'F'
                reports[job]['prebank_routine_sha256'] = commitment['source_sha256']
                reports[job]['original_terminal_process_receipt_digest'] = commitment['process_receipt_digest']
            else:
                from .terminal import validate_result
                validate_result(interpretations[job], packet)
                reports[job] = terminal_report(packet, interpretations[job])
                reports[job]['mode'] = 'I'
        write_json(self.root / 'terminal_report.json', reports, True)
        state['phase'] = 'complete_engineering'
        self._event(state, 'terminal_interpretation', report_digest=digest(reports))
        self._save(state)
        return reports
