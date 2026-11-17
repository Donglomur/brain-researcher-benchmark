"""Inactive trusted operator entry for the complete NEURAL-035 closed pair.

No producer launch, grading CLI, authority factory, model tool or arbitrary
target callback. The operator owns source imports, approval and independent
supervisor observations. A JSON receipt does not authenticate its own origin.
"""
import math
import os
from pathlib import Path
import types
from capture_io import Budget, Captures, descriptor, encode, need, parse, path, pin
import source_loader
from paired_report import summarize

VERSION = 'neural035_authorized_closed_pair_grade_v1'


def _child(row):
    need(type(row) is dict and type(row.get('exit_code')) is int and row['exit_code'] == 0,
         'independent enclosing natural integer zero')
    need(all(row.get(k) is True for k in
             ('natural_exit', 'process_reaped', 'process_group_absent', 'streams_closed')) and
         all(row.get(k) is False for k in ('timed_out', 'kill_sent')) and
         all(row.get(k) is None for k in ('error_type', 'timer_disable_error', 'timer_restore_error')),
         'unforced complete enclosing process closure')
    need(type(row.get('pid')) is int and row['pid'] > 0,
         'supervisor-owned concrete child identity; not proof by itself')


def _outer(observation, terminal_raw, selection, selected, root, sources, budget):
    need(type(observation) is dict and set(observation) == {
        'schema', 'task_id', 'attempt', 'adapter_source', 'controller_source', 'selection',
        'stdout', 'child', 'origin_monotonic', 'whole_deadline', 'outer_deadline', 'finished_monotonic'},
        'exact separately trusted enclosing observation')
    need(observation['schema'] == 'neural035_trusted_adapter_observation_v1' and
         observation['task_id'] == 'NEURAL-035' and observation['attempt'] == str(root) and
         observation['adapter_source'] == sources.adapter_source and
         observation['controller_source'] == sources.source and
         observation['selection'] == selected and observation['stdout'] == pin(terminal_raw),
         'same source, attempt, selection and captured adapter terminal')
    _child(observation['child'])
    origin = observation['origin_monotonic']
    need(type(origin) in (int, float) and math.isfinite(origin) and origin >= 0 and
         type(observation['whole_deadline']) in (int, float) and
         type(observation['outer_deadline']) in (int, float) and
         observation['whole_deadline'] == origin + selection['whole_seconds'] and
         observation['outer_deadline'] == observation['whole_deadline'] + 60,
         'unchanged original producer clocks; new grading deadline does not renew them')
    need(type(observation['finished_monotonic']) in (int, float) and
         math.isfinite(observation['finished_monotonic']) and
         origin <= observation['finished_monotonic'] < observation['whole_deadline'],
         'supervisor observed original adapter termination before original successful deadline')
    need(type(terminal_raw) is bytes and 0 < len(terminal_raw) <= 8192, 'bounded captured terminal')
    terminal = budget.decoded(terminal_raw, 'original adapter terminal')
    need(type(terminal) is dict and set(terminal) == {
        'schema', 'task_id', 'status', 'context_count', 'query_records_per_output',
        'controller_result', 'adapter_source', 'controller_source', 'private_grading_authorized',
        'private_grading_performed', 'runtime_qualified', 'scientific_qualified',
        'adapter_metadata_read_reserved_bytes', 'requires_observed_adapter_exit_zero'},
        'exact original unscored terminal')
    need(terminal['schema'] == 'neural035_full14_unscored_result_v1' and
         terminal['task_id'] == 'NEURAL-035' and terminal['status'] == 'complete_unscored' and
         type(terminal['context_count']) is int and terminal['context_count'] == 2 and
         type(terminal['query_records_per_output']) is int and terminal['query_records_per_output'] == 28 and
         terminal['adapter_source'] == sources.adapter_source and terminal['controller_source'] == sources.source and
         terminal['requires_observed_adapter_exit_zero'] is True and
         all(terminal[k] is False for k in ('private_grading_authorized', 'private_grading_performed',
                                          'runtime_qualified', 'scientific_qualified')) and
         type(terminal['adapter_metadata_read_reserved_bytes']) is int and
         0 < terminal['adapter_metadata_read_reserved_bytes'] <= 4000000,
         'original source-bound complete unscored terminal stays unscored')
    return terminal


def capture_closed_collection(sources, captures, producer_root, selection_operand,
                              terminal_raw, observation):
    """Reuse original admission against immutable cached bodies, without running main.

    Only grade_selected establishes the external authority boundary. This helper
    is not a capability against malicious trusted-host Python.
    """
    budget = captures.budget
    root = path(producer_root)
    need(type(selection_operand) is dict and set(selection_operand) == {'path', 'bytes', 'sha256'},
         'exact selection operand')
    selected = descriptor({k: selection_operand[k] for k in ('bytes', 'sha256')}, 32768)
    selection_raw = captures.read(selection_operand['path'], 32768, selected)
    selection = budget.decoded(selection_raw, 'original producer selection')
    sources.policy.selection(selection, sources.source)
    need(selection['output'] == str(root), 'exact selected producer root')
    terminal = _outer(observation, terminal_raw, selection, selected, root, sources, budget)
    a = sources.adapter
    # outcome is an unchanged historical metadata checker. Set its comparison
    # origin to the independently observed ORIGINAL clock, never the new one.
    a.ORIGIN = observation['origin_monotonic']
    a.parse = lambda raw: budget.decoded(raw, 'original adapter JSON')
    completed = a.outcome(captures, (Path(selection_operand['path']), selected), sources.reg,
        sources.program, root, observation['whole_deadline'], observation['outer_deadline'], selection)
    need(terminal['controller_result'] == completed, 'exact terminal-to-original-outcome join')
    c = types.SimpleNamespace(**sources.c.__dict__)

    def capture(name, cap, expected=None, tick=lambda: None, charge=lambda n: None):
        tick()
        return captures.read(name, cap, expected)

    c.capture = capture
    c.parse = lambda raw: budget.decoded(raw, 'original observer JSON')
    def compile_original(bodies, name, here, **bindings):
        budget.read(len(bodies[name]), 'original observer captured source compilation')
        return sources.c.module(bodies, name, here, **bindings)
    c.module = compile_original
    obs = sources.observer
    obs.BODIES = sources.program
    obs.HERE = sources.base / 'program'
    obs.os, obs.Path = os, Path
    outputs, complete = obs.admit(c, root,
        {'schema': 'neural035_full14_worker_v1', 'status': 'complete_unqualified',
         'source': sources.source, 'outputs': 2, 'complete': completed['complete']},
        sources.source, budget.deadline, budget.read,
        {k: selection['program'][k] for k in ('bytes', 'sha256')})
    need(outputs == completed['outputs'] and complete == completed['complete'],
         'original full observer and adapter closure agree')
    done = budget.decoded(captures.read(root / 'COMPLETE.json', 32768, complete), 'complete join')
    public_raw = captures.read(root / 'PUBLIC_MANIFEST.json', 2000000, done['public_manifest'])
    candidate_raw = captures.read(root / 'cases/00/predictions.json', 2000000, outputs['candidate'])
    operator_raw = captures.read(root / 'cases/01/predictions.json', 2000000, outputs['operator'])
    public, candidate, operator = (budget.decoded(raw, label) for raw, label in
        ((public_raw, 'public identity'), (candidate_raw, 'candidate report'), (operator_raw, 'operator report')))
    sources.contract.admit_pair(candidate, operator, public, sources.core)
    captures.seal()
    return {'complete': complete, 'outputs': outputs, 'public_raw': public_raw,
            'public': public, 'candidate': candidate, 'operator': operator,
            'original_terminal': terminal, 'selection': selected}


def _relative(value):
    need(type(value) is str and value and not value.startswith('/') and '\\' not in value and
         all(v not in ('', '.', '..') for v in value.split('/')), 'fixed relative protected path')
    return value


def grade_selected(repository, producer_root, selection_operand, terminal_raw,
                   enclosing_observation, prepared_root, authority, budget):
    """Future trusted-host API; candidates do not supply any of these operands.

    The separate authority must authenticate the exact independently observed
    enclosing process record and approve private grading; it must return None.
    We provide no implementation that approves arbitrary metadata. Its authenticity,
    source custody and native/exposure qualifications remain external prerequisites.
    """
    need(type(budget) is Budget, 'selected explicit budget')
    need(type(terminal_raw) is bytes and 0 < len(terminal_raw) <= 8192, 'bounded terminal bytes')
    observation_raw = encode(enclosing_observation)
    budget.write(len(observation_raw), 'authority observation serialization')
    selection = {'schema': 'neural035_separate_grading_authority_v1', 'operation': VERSION,
        'repository': str(repository), 'producer_root': str(producer_root),
        'selection_operand': selection_operand, 'terminal': pin(terminal_raw),
        'enclosing_observation': pin(observation_raw), 'prepared_root': str(prepared_root),
        'dependency_manifest': source_loader.DEPENDENCIES_PIN,
        'read_limit': budget.max_read_bytes, 'write_limit': budget.max_write_bytes,
        'deadline': budget.deadline}
    # This callback supplies no source, predictions, targets or process success.
    # It belongs to the external trusted operator; no Boolean approval accepted.
    need(authority.require_neural035_closed_pair_grading(selection, enclosing_observation) is None,
         'separate exact-operation grading and supervisor authority')
    captures = Captures(budget)
    sources = source_loader.load(path(repository), captures)
    pair = capture_closed_collection(sources, captures, producer_root, selection_operand,
                                     terminal_raw, enclosing_observation)
    # All reports, original closure and independent enclosing observation are
    # authenticated before even resolving the separately selected data root.
    binding = sources.target_binding
    need(type(binding) is dict and set(binding) == {'schema', 'public_manifest', 'private_targets'} and
         binding['schema'] == 'neural035-grade-binding-v1', 'fixed original static grade binding')
    root = path(prepared_root)
    for key in ('public_manifest', 'private_targets'):
        row = binding[key]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'fixed bound body')
        descriptor({k: row[k] for k in ('bytes', 'sha256')}, 16000000 if key == 'private_targets' else 2000000)
        _relative(row['path'])
    row = binding['public_manifest']
    raw = captures.read(root / row['path'], 2000000, {k: row[k] for k in ('bytes', 'sha256')})
    original_public = budget.decoded(raw, 'source-bound original public manifest')
    need(original_public == pair['public'], 'original public manifest exactly matches captured producer public identity')
    captures.seal()
    # The sole protected body access is fixed; no reader is caller-supplied.
    row = binding['private_targets']
    target_raw = captures.read(root / row['path'], 16000000, {k: row[k] for k in ('bytes', 'sha256')})
    target = budget.decoded(target_raw, 'protected targets')
    # Reserve explicit primitive-interface traversals: validate_targets in
    # deferred_grade and each of its two core.grade calls; both numeric grades.
    # 2,024 query cells × (99 surrogate peaks + observed peak + active flag),
    # plus 1,012 × 5 public peak/active pairs. This is not Python heap traffic.
    target_scalars = 2024 * 101 + 1012 * 10
    budget.read(target_scalars * 8 * 5, 'three target validations and two numerical grade traversals')
    result = sources.scorer.score(pair['candidate'], pair['operator'], pair['public'],
                                  lambda: target, sources.core, sources.contract)
    budget.tick()
    original_raw = encode(result)
    budget.write(len(original_raw), 'original grade serialization boundary')
    budget.read(len(original_raw), 'paired reducer input boundary')
    budget.write(len(original_raw), 'detached original grade copy boundary')
    budget.write(len(original_raw), 'paired summary construction envelope')
    report = summarize(result)
    captures.seal()
    answer = {'schema': VERSION, 'task_id': 'NEURAL-035', 'closure': {
        'complete': pair['complete'], 'outputs': pair['outputs'], 'selection': pair['selection'],
        'terminal': pin(terminal_raw), 'enclosing_observation': selection['enclosing_observation']},
        'dependency_manifest': source_loader.DEPENDENCIES_PIN,
        'original_binding': pin(encode(binding)), 'target': {k: row[k] for k in ('bytes', 'sha256')},
        'reports': report, 'complete_reports_admitted_before_protected_resolution': 2,
        'private_body_captures': 1, 'runtime_qualified': False, 'scientific_qualified': False,
        'old_collector_grading_authorized': False, 'registration_delta': 0,
        'qualification_delta': 0, 'new_assignment_count': 0,
        'custody_authenticity': 'external trusted operator and supervisor prerequisite; metadata joins alone are insufficient'}
    raw = encode(answer)
    need(len(raw) <= 2**20, 'bounded complete paired report')
    budget.write(len(raw), 'paired result serialization')
    # Usage is a separately returned interface ledger, so serialized-answer
    # accounting has no self-referential size estimate.
    return {'result': answer, 'result_bytes': raw, 'usage': budget.record()}
