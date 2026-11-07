"""Operator-only comparison preserving the original scorer and target gate."""
import os
from pathlib import Path
import sys
import types


def bounded_targets(load_targets, tick):
    """Cooperative boundary; a qualified enclosing process supplies hard cutoff."""
    tick()
    value = load_targets()
    tick()
    return value


def load_original(c, repository, binding, read, tick):
    """Capture both pinned definitions before executing either module.

    Temporary legacy import/path changes are restored. No ordinary search-path
    or bytecode resolution can substitute the selected protocol module.
    """
    captures = {}
    for name in ('protocol.py', 'scorer_core.py'):
        item = binding['scoring_sources'][name]
        path = c.path(repository) / item['path']
        captures[name] = (path, c.capture(path, 131072, c.only_pin(item), tick, read))
    protocol = types.ModuleType('protocol')
    protocol.__file__ = str(captures['protocol.py'][0])
    scorer = types.ModuleType('neural083_selected_original_scorer')
    scorer.__file__ = str(captures['scorer_core.py'][0])
    saved_path = sys.path[:]
    sentinel = object()
    previous = sys.modules.get('protocol', sentinel)
    try:
        exec(compile(captures['protocol.py'][1], protocol.__file__, 'exec'), protocol.__dict__)
        sys.modules['protocol'] = protocol
        exec(compile(captures['scorer_core.py'][1], scorer.__file__, 'exec'), scorer.__dict__)
        if scorer.p is not protocol:
            raise ValueError('Original scorer must use captured protocol definitions')
    finally:
        sys.path[:] = saved_path
        if previous is sentinel:
            sys.modules.pop('protocol', None)
        else:
            sys.modules['protocol'] = previous
    return scorer


def protected_grade(c, source_path, source_pin, selection_spec, external_spec, outer_proof_spec,
                    load_targets, *, deadline, read_limit):
    """Concrete trusted-operator route; never exposed to a candidate.

    Root must independently own and select the exact outer proof and target
    callback after authorizing grading. A syntactically valid proof document
    does not create that authority. This function authenticates the selected
    proof, observer, execution configuration, captured runtime and both panels.
    Clock checks here are cooperative. A separately qualified enclosing process
    must provide the hard cutoff. The callback's private I/O/resource authority
    and costs have a separate trusted allowance, outside this managed read cap.
    """
    c.need(type(read_limit) is int and read_limit > 0, 'Explicit protected-grade read allowance')
    spent = 0
    def tick():
        c.before(deadline)
    def read(number):
        nonlocal spent
        c.need(type(number) is int and number >= 0 and spent + number <= read_limit, 'Protected-grade read budget')
        spent += number
        tick()
    # c.load has a bounded source closure; reserve it before materialization.
    read(1000000)
    manifest, bodies, _source_reads = c.load(source_path, source_pin, deadline)
    here = Path(source_path).parent
    contracts = c.module(bodies, 'contracts.py', here, c=c)
    policy = c.module(bodies, 'policy.py', here, c=c, contracts=contracts)
    admission = c.module(bodies, 'admission.py', here)
    selection = policy.selection(c.parse(c.capture(selection_spec['path'], 32768, c.only_pin(selection_spec), tick, read)), source_pin)
    external = c.parse(c.capture(external_spec['path'], 8192, c.only_pin(external_spec), tick, read))
    proof = c.parse(c.capture(outer_proof_spec['path'], 32768, c.only_pin(outer_proof_spec), tick, read))
    c.need(proof.get('schema') == 'neural083_outer_observer_admission_v1' and
           proof.get('external') == c.only_pin(external_spec) and proof.get('source') == source_pin and
           proof.get('selection') == c.only_pin(selection_spec), 'Exact root-owned independent observer proof')
    for field in ('grading_authorized', 'natural_exit_zero', 'process_reaped', 'process_group_absent',
                  'stdout_eof', 'stderr_eof', 'durably_closed_before_original_deadline'):
        c.need(proof.get(field) is True, 'Independent outer closure and grading authority: ' + field)
    root = c.path(selection['output'])
    c.need(external.get('schema') == 'neural083_sequential_external_v2' and
           external.get('status') == 'complete_unqualified' and external.get('source') == source_pin and
           external.get('selection') == c.only_pin(selection_spec) and external.get('attempt') == str(root) and
           external.get('captured_worker_source') == manifest['files']['worker.py'] and
           external.get('grading_performed') is False, 'Selected natural observer and captured worker')
    child = external['child']
    c.need(child.get('natural_exit') is True and type(child.get('exit_code')) is int and child['exit_code'] == 0 and
           all(child.get(name) is True for name in ('process_reaped', 'process_group_absent', 'streams_closed')),
           'Natural closed worker, no merely written completion marker')
    binding = c.parse(bodies['BINDING.json'])
    c.need(binding['reference'] == c.pin(bodies['reference_program.py']), 'Captured independent reference')
    policy.reviews(selection, source_pin, binding,
                   lambda path, cap, expected: c.capture(path, cap, expected, tick, read))
    # Admission checks the original execution clock using the saved whole
    # deadline, while filesystem reading is separately bounded by this grade's
    # deadline. A clock adapter does not reset any execution deadline evidence.
    execution_deadline = external['whole_deadline']
    wrapped = types.SimpleNamespace(**{name: getattr(c, name) for name in
                                      ('parse', 'capture', 'need', 'only_pin', 'inventory',
                                       'validate_natural_exit', 'validate_cli_commands')})
    wrapped.before = lambda _original: tick()
    admission.admit(wrapped, contracts, c.pin(bodies['reference_program.py']), root,
                    external['worker_terminal'], source_pin, selection, execution_deadline, read)
    canonical = c.parse(c.capture(selection['canonical']['path'], 4000000,
                                  c.only_pin(selection['canonical']), tick, read))
    panel = contracts.canonical(canonical)
    submission = c.parse(c.capture(root / 'submission.json', 2000000,
                                   external['worker_terminal']['submission'], tick, read))
    bundles = {name: dict(schema='neural083_predictions_v1', generation=panel['generation'], outcomes=[])
               for name in contracts.PANELS}
    for item, committed in zip(contracts.schedule(panel), submission['conditions']):
        c.need(committed['condition'] == item and committed['ordinal'] == item['ordinal'], 'Frozen collection schedule')
        directory = root / 'conditions' / ('condition%04d' % item['ordinal'])
        closed = c.parse(c.capture(directory / 'CLOSED.json', 2000000, committed['closed'], tick, read))
        result = c.parse(c.capture(directory / 'infer' / 'predictions.json', 100000, closed['output'], tick, read))
        bundles[item['panel']]['outcomes'].append(result)
    scorer = load_original(c, selection['repository'], binding, read, tick)
    tick()
    result = grade(panel, bundles['candidate'], bundles['reference'], lambda: bounded_targets(load_targets, tick), scorer,
                   external_admission=True)
    tick()
    result['source'] = source_pin
    result['external_observer'] = c.only_pin(external_spec)
    result['root_outer_proof'] = c.only_pin(outer_proof_spec)
    result['managed_read_reservations'] = spent
    result['target_callback_accounting'] = 'Separate trusted allowance; not included in managed_read_reservations'
    result['grade_clock'] = 'Cooperative checks; qualified enclosing hard cutoff required separately'
    tick()
    return result


def grade(panel, candidate, reference, load_targets, original_scorer, *, external_admission):
    """Called only after separately authorized, independently admitted execution.

    The caller supplies the source-authenticated original scorer module and an
    operator-only callback. This is not a candidate-facing entry point.
    """
    if external_admission is not True:
        raise ValueError('Separate independent execution admission required')
    _candidate_predictions, candidate_abstained = original_scorer.admit(panel, candidate)
    _reference_predictions, reference_abstained = original_scorer.admit(panel, reference)
    # Both complete panels are admitted before even one protected target read.
    if candidate_abstained or reference_abstained:
        return dict(status='abstained', private_callbacks=0, primary_score=None,
                    candidate_abstaining_conditions=len(candidate_abstained),
                    reference_abstaining_conditions=len(reference_abstained))
    truth = load_targets()
    first = original_scorer.score(panel, candidate, lambda: truth)
    second = original_scorer.score(panel, reference, lambda: truth)
    if first['status'] != 'scored' or second['status'] != 'scored':
        raise ValueError('Both unchanged original scores required')
    return dict(status='scored', private_callbacks=1, primary_score=first['primary_score'],
                primary=first['primary'], candidate=first, independent_reference=second,
                candidate_minus_reference_balanced_accuracy=first['primary_score'] - second['primary_score'],
                original_contrasts_preserved=True, scientific_success=None,
                scientific_qualified=False, submission_ready=False)
