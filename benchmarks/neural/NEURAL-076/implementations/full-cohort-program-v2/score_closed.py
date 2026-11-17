"""Current hierarchy scoring only after the caller observed the original outer exit."""
import argparse
import hashlib
from pathlib import Path
import signal
import time

# Explicit local source loading also works under Python -I.
import types
_path = Path(__file__).absolute().with_name('support.py')
support = types.ModuleType('_neural076_bridge_support')
support.__file__ = str(_path)
exec(compile(_path.read_bytes(), str(_path), 'exec'), support.__dict__)


def admit(common, coordinator, source, selection_pin, terminal, record, observation, complete, submission, commitment):
    """Metadata join after actual parent observation; never sufficient on its own to prove an OS exit."""
    coordinator.child_closed(record)
    common.need(set(terminal) == {'observation', 'complete', 'full_contexts', 'runtime_qualified', 'scientific_qualified'}
                and terminal['full_contexts'] == 650 and terminal['runtime_qualified'] is False
                and terminal['scientific_qualified'] is False, 'Exact original observer terminal')
    common.need(observation['schema'] == 'neural076_whole_command_observation_v1'
                and observation['source'] == source and observation['selection'] == selection_pin
                and observation['complete'] == terminal['complete'] and observation['error'] is None
                and observation['completed'] is True and observation['requires_observed_observer_exit_zero'] is True
                and observation['observed'] < observation['deadline']
                and all(observation[k] is False for k in ('runtime_qualified', 'scientific_scoring', 'scientific_qualified')),
                'Closed observer joins source, selection and complete collection')
    coordinator.child_closed(observation['lifecycle'])
    common.need(complete['schema'] == 'neural076_full650_collection_v1'
                and complete['status'] == 'complete_pending_external_natural_exit'
                and complete['source'] == source and complete['context_count'] == 650
                and all(complete[k] is False for k in ('private_gold_opened', 'scientific_scoring', 'feedback_released',
                                                      'runtime_qualified', 'scientific_qualified')),
                'Full public-only collection')
    common.need(commitment['schema'] == 'neural076_frozen_program_v1' and commitment['source'] == source
                and commitment['keys'] == list(common.KEYS) and commitment['feedback_before_commitment'] is False,
                'One frozen source for all 650 contexts')
    rows = complete['contexts']
    common.need(type(rows) is list and [r['key'] for r in rows] == list(common.KEYS), 'All canonical contexts')
    common.need(submission['schema'] == 'neural076_predictions_v1'
                and submission['parts'] == [{'key': r['key'], 'path': r['path']} for r in rows],
                'Submission joins exact closed contexts')
    for row in rows:
        common.need(row['path'] == row['key'].replace('/', '__') + '.npz', 'Original closed output filename')
        pin = row['prediction']
        common.need(set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int
                    and 0 < pin['bytes'] <= common.PRED and len(pin['sha256']) == 64
                    and all(c in '0123456789abcdef' for c in pin['sha256']), 'Bounded closed prediction pin')
    return {r['path']: r['prediction'] for r in rows}


def assess_bound(scorer, common, submission, public, base, private_loader, closed_pins, before=lambda: None):
    """Inject prior custody pins into BOTH existing scorer passes; no third prehash pass."""
    original = scorer.load
    base = common.path(base)

    def bound(path, ids, units, expected_sha=None):
        before()
        path = common.path(path)
        common.need(path.parent == base and path.name in closed_pins, 'Only closed canonical predictions')
        pin = closed_pins[path.name]
        common.need(expected_sha is None or expected_sha == pin['sha256'], 'Second pass agrees with capture')
        common.need(path.stat().st_size == pin['bytes'], 'Closed archive length')
        result = original(path, ids, units, pin['sha256'])
        before()
        return result

    scorer.load = bound
    try:
        return scorer.assess(submission, public, base, private_loader)
    finally:
        scorer.load = original


def grade(repository, binding_path, binding_sha, proof_path, proof_sha, output, end):
    loader, bodies, _, source = support.runtime()
    common, coordinator = loader('common'), loader('coordinator')
    tick = lambda: common.before(end)
    tick()
    raw, binding_pin = common.capture(binding_path, 262144, tick=tick)
    common.need(binding_pin['sha256'] == binding_sha, 'Frozen pre-execution binding')
    binding = common.decode(raw)
    common.need(binding.get('schema') == 'neural076_current_instructions_binding_v2'
                and binding.get('separate_scoring_explicitly_selected') is True
                and binding['source'] == source and binding['execution_files'] == support.source_identity(common)
                and binding['score_budget'] == support.score_budget(binding['score_budget']['seconds'])
                and binding['current_instructions_acknowledged_before_execution'] is True,
                'Current instruction, software and separate score authority')
    raw, proof_pin = common.capture(proof_path, 262144, tick=tick)
    common.need(proof_pin['sha256'] == proof_sha, 'Observed caller proof pin')
    proof = common.decode(raw)
    common.need(proof['schema'] == 'neural076_observed_outer_exit_v2' and proof['binding'] == binding_pin
                and proof['observed'] < proof['deadline'] and proof['source'] == source,
                'Source-bound actual caller observation')
    root = common.path(binding['collection_output'])
    terminal = proof['terminal']
    raw, _ = common.capture(root.with_name(root.name + '.observer') / 'OBSERVATION.json', 131072,
                            terminal['observation'], tick=tick)
    observation = common.decode(raw)
    raw, _ = common.capture(root / 'COMPLETE.json', 2 * common.MIB, terminal['complete'], tick=tick)
    complete = common.decode(raw)
    raw, _ = common.capture(root / 'submission' / 'submission.json', 131072, complete['submission'], tick=tick)
    submission = common.decode(raw)
    raw, _ = common.capture(root / 'program' / 'COMMIT.json', 131072, complete['commit'], tick=tick)
    commitment = common.decode(raw)
    common.need(commitment['program'] == binding['program'], 'Same pre-query source as current instructions')
    pins = admit(common, coordinator, source, binding['selection'], terminal, proof['lifecycle'],
                 observation, complete, submission, commitment)
    # This metadata-only inventory does not reread prediction payloads.
    files, directories, _ = common.inventory(root / 'submission', 652)
    common.need(set(files) == set(pins) | {'submission.json'} and directories == [root / 'submission'],
                'Only complete original submission files')
    scorer, _, _ = support.current_scorer(repository, common)
    lock = common.decode(bodies['LOCK.json'])
    operator_root = common.path(binding['collection']) / 'packages/neural076/private/operator'
    name = 'packages/neural076/private/operator/operator_manifest.json'
    raw, _ = common.capture(operator_root / 'operator_manifest.json', 65536, lock['collection_files'][name], tick=tick)
    operator = common.decode(raw)
    public = scorer.authenticated_public(operator_root / 'public_manifest.json', operator)
    common.need(submission['source_design_sha256'] == lock['source_design_sha256'], 'Original complete design')
    result = assess_bound(scorer, common, submission, public, root / 'submission',
                          lambda: scorer.load_gold(operator_root, operator['gold']), pins, tick)
    tick()
    report = {'schema': 'neural076_closed_hierarchy_report_v2', 'binding': binding_pin,
              'outer_observation': proof_pin, 'current_score': result, 'source': source,
              'runtime_qualified': False, 'scientific_qualified': False,
              'scope': 'Agent-built full-cohort feature recovery; no direct/viewer or SOTA qualification.'}
    report_pin = common.write(output, common.encode(report), 16 * common.MIB)
    tick()
    common.need(result['status'] in ('scored', 'complete_with_undefined_correlations'), 'Current scorer did not complete')
    return report_pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository', 'binding', 'binding-sha256', 'proof', 'proof-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--end', type=float, required=True)
    args = parser.parse_args()
    if signal.getitimer(signal.ITIMER_REAL) != (0., 0.) or time.monotonic() >= args.end:
        raise ValueError('Fresh scoring process under explicit original deadline')
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Scoring deadline')))
    signal.setitimer(signal.ITIMER_REAL, args.end - time.monotonic())
    pin = grade(args.repository, args.binding, args.binding_sha256, args.proof, args.proof_sha256, args.output, args.end)
    if time.monotonic() >= args.end:
        raise TimeoutError('Scoring publication deadline')
    print(__import__('json').dumps({'report': pin}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
