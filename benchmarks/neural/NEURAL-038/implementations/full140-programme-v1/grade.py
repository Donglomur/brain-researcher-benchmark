"""Internal numerical worker after independently observed original-producer closure."""
import argparse
import math
from pathlib import Path
import signal
import time
import types

HERE = Path(__file__).absolute().parent
lib = types.ModuleType('_neural038_library')
lib.__file__ = str(HERE / 'library.py')
exec(compile((HERE / 'library.py').read_bytes(), lib.__file__, 'exec'), lib.__dict__)


def external_receipt(c, value, selection, selection_pin, source):
    c.need(value['schema'] == 'neural038_full140_external_v1' and value['status'] == 'complete_unqualified'
           and value['source'] == source and value['selection'] == selection_pin
           and value['attempt'] == selection['output'] and value['error_type'] is None
           and value['full140_source_scope'] is True and value['numerical_grading_performed'] is False
           and value['runtime_qualified'] is False and value['scientific_qualified'] is False
           and value['nested_cli_and_native_recovery_may_be_required'] is False and value['automatic_retry'] is False,
           'Exact successful original external receipt; no unresolved recovery')
    for name in ('origin_monotonic', 'whole_deadline', 'outer_deadline', 'elapsed_before_publication'):
        number = value[name]
        c.need(type(number) in (int, float) and math.isfinite(number), 'Finite original observer clock')
    c.need(value['whole_deadline'] == value['origin_monotonic'] + selection['whole_seconds']
           and value['outer_deadline'] == value['whole_deadline'] + 60
           and 0 <= value['elapsed_before_publication'] < selection['whole_seconds'], 'Original successful whole clock')
    lib.closed(value['child'])
    c.exact_pin(value['report']); c.exact_pin(value['complete'])
    return value


def stopped_report(c, bodies, root, receipt, source, binding, end, read):
    """Reuse every original admit gate and retain its exact candidate-report capture."""
    observer = c.module(bodies, 'observe.py', HERE / 'runtime')
    expected_path = c.path(root) / 'candidate/report.json'
    original = c.capture
    captured = []
    def hold(path, cap, expected=None, tick=lambda: None, charge=lambda n: None):
        if c.path(path) == expected_path:
            c.need(not captured and expected == receipt['report'], 'One exact stopped-report pin/path')
            raw = original(path, cap, expected, tick, charge)
            captured.append(raw)
            return raw
        return original(path, cap, expected, tick, charge)
    c.capture = hold
    try:
        terminal = {'schema': 'neural038_full140_worker_v1', 'status': 'complete_unqualified',
                    'source': source, 'scope': binding['scope'], 'complete': receipt['complete']}
        report_pin, complete_pin = observer.admit(c, c.path(root), terminal, source, binding, end, read)
    finally:
        c.capture = original
    c.need(len(captured) == 1 and report_pin == receipt['report'] and complete_pin == receipt['complete'],
           'Retained exact report from complete original closure admission')
    return captured[0]


def current_numerics(c, evaluator, transport, package, binding, raw_report, budget):
    """Only the current evaluator reads numerical arrays, after full report admission."""
    public = {r['target']: r for r in binding['files'] if r['visibility'] == 'public'}
    c.need(len(public) == 25 and sum(r['bytes'] for r in public.values()) == 938607,
           'Original complete public view')
    panel = transport.decode(c.capture(package / 'public/panel.json', 100000,
                                        c.only_pin(public['public/panel.json']), budget.tick, budget.read))
    inputs = transport.decode(c.capture(package / 'public/input.json', 100000,
                                         c.only_pin(public['public/input.json']), budget.tick, budget.read))
    submission = transport.decode(raw_report)
    # Cross-check every metadata descriptor against the same source-bound public view.
    evaluator.metadata(panel, inputs)
    for block in inputs['blocks']:
        for record in block['arrays'].values():
            target = 'public/' + record['path']
            c.need(target in public and c.only_pin(record) == c.only_pin(public[target]),
                   'Scoring arrays are exactly the candidate-visible arrays')
    original = transport.read
    def charged(path, limit, expected=None):
        path = c.path(path)
        c.need(path.is_relative_to(package / 'public/arrays'), 'Only original public numerical arrays')
        target = path.relative_to(package).as_posix()
        c.need(target in public and expected == c.only_pin(public[target]), 'Exact source-array read')
        budget.read(expected['bytes'] + 1)
        budget.tick()
        value = original(path, limit, expected)
        budget.tick()
        return value
    transport.read = charged
    try:
        return evaluator.evaluate(package / 'public', panel, inputs, submission)
    finally:
        transport.read = original


def grade(source_repository, commit_path, commit_pin, proof_path, proof_pin, output, end):
    c, _, bodies, source = lib.runtime(end)
    commit = c.parse(c.capture(commit_path, 65536, commit_pin, lambda: c.before(end)))
    c.need(commit['schema'] == 'neural038_numerical_bridge_commitment_v1' and commit['source'] == source
           and commit['wrapper_sources'] == lib.source_identity(c), 'Frozen selected bridge source')
    root = c.path(commit_path).parent
    c.need(c.path(output) == root / 'NUMERICAL.json', 'Fixed owned numerical report destination')
    selection_raw = c.capture(root / 'SELECTION.json', 32768, commit['selection'], lambda: c.before(end))
    selection = c.module(bodies, 'policy.py', HERE / 'runtime', c=c).selection(c.parse(selection_raw), source)
    authorization = c.parse(c.capture(root / 'AUTHORITY.json', 65536, commit['authority'], lambda: c.before(end)))
    lib.authority(authorization, selection, commit['wrapper_sources'], commit['profile']['seconds'])
    c.need(commit['profile'] == lib.profile(commit['profile']['seconds'])
           and commit['source_repository'] == str(c.path(source_repository))
           and commit['operator_repository'] == selection['repository'], 'Separate selected roots and numerical budget')
    lib.disjoint_roots(c, selection['repository'], source_repository, selection['output'], root)
    legacy_remaining = max(0, c.RETAIN - c.inventory(c.path(selection['output']), c.RETAIN, 2000)[2])
    budget = lib.NumericalBudget(c, root, selection['other_future_bytes'], end, legacy_remaining)
    lib.floor(c, root, selection['other_future_bytes'], legacy_remaining=legacy_remaining)
    proof = c.parse(c.capture(proof_path, 65536, proof_pin, budget.tick, budget.read))
    c.need(proof['schema'] == 'neural038_original_observer_exit_v1' and proof['commitment'] == commit_pin
           and proof['source'] == source and proof['observed'] < proof['deadline'], 'Actual caller-observed outer exit')
    lib.closed(proof['lifecycle'])
    receipt = external_receipt(c, c.parse(c.capture(root / 'EXTERNAL.json', 8192, proof['external_receipt'],
                                                    budget.tick, budget.read)), selection, commit['selection'], source)
    complete = c.parse(c.capture(c.path(selection['output']) / 'COMPLETE.json', 32768, receipt['complete'],
                                budget.tick, budget.read))
    c.need(complete['program'] == c.only_pin(selection['program']), 'Same stopped source as numerical authority')
    binding = c.parse(bodies['BINDINGS.json'])
    raw_report = stopped_report(c, bodies, selection['output'], receipt, source, binding, end, budget.read)
    operator = c.path(selection['repository'])
    source_descriptor = c.parse(c.capture(operator / binding['source_descriptor']['path'], 100000,
                                          c.only_pin(binding['source_descriptor']), budget.tick, budget.read))
    export = c.parse(c.capture(operator / binding['export_descriptor']['path'], 100000,
                               c.only_pin(binding['export_descriptor']), budget.tick, budget.read))
    c.need(export['task_ids'] == source_descriptor['task_ids'] == ['NEURAL-038']
           and export['files'] == binding['files'] and export['source_manifest'] == binding['source_descriptor']
           and [{k: r[k] for k in ('target', 'bytes', 'sha256', 'role', 'visibility')}
                for r in source_descriptor['files']] == binding['files'], 'Same complete operator source/export binding')
    evaluator, transport, _ = lib.evaluator(source_repository, c)
    result = current_numerics(c, evaluator, transport, operator / binding['package'], binding, raw_report, budget)
    budget.tick()
    # Charge the entire permitted report publication before serializing it.
    budget.write(2 * 2**20)
    report = {'schema': 'neural038_observed_full140_numerical_score_v1', 'commitment': commit_pin,
              'outer_proof': proof_pin, 'stopped_report': receipt['report'], 'scope': binding['scope'],
              'result': result, 'costs': budget.record(), 'scientific_qualified': False, 'runtime_qualified': False,
              'report_write_reservation': 2 * 2**20,
              'interpretation': 'Public numerical investigation; no direct-understanding, independent-animal or SOTA claim.'}
    pin = c.save(output, c.encoded(report), 2 * 2**20, budget.tick)
    budget.tick()
    return pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-repository', 'commitment', 'commitment-pin', 'proof', 'proof-pin', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--end', type=float, required=True)
    args = parser.parse_args()
    if signal.getitimer(signal.ITIMER_REAL) != (0., 0.) or not math.isfinite(args.end) or time.monotonic() >= args.end:
        raise ValueError('Fresh internal numerical process under original deadline')
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Original numerical deadline')))
    signal.setitimer(signal.ITIMER_REAL, args.end - time.monotonic())
    import json
    pin = grade(args.source_repository, args.commitment, json.loads(args.commitment_pin),
                args.proof, json.loads(args.proof_pin), args.output, args.end)
    if time.monotonic() >= args.end: raise TimeoutError('Numerical publication deadline')
    print(json.dumps({'score': pin}), flush=True)
    if time.monotonic() >= args.end: raise TimeoutError('Numerical deadline after final flush')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
