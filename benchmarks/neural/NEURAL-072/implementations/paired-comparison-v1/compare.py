#!/usr/bin/env python3
"""Paired contextual-program assessment on one complete NEURAL-072 panel.

This trusted-operator helper preserves fixed-comparator-v2 and does not provide
participant isolation, authentic data admission, or a direct-observation task.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import types


SCORER_PATH = Path(__file__).resolve().parents[1] / 'fixed-comparator-v2' / 'evaluator.py'
SCORER_SHA256 = 'ef77dccd5d8bae3edcb6c8a4ad41221f531b792ceec7af98c42910faceebd854'
_source = SCORER_PATH.read_bytes()
if hashlib.sha256(_source).hexdigest() != SCORER_SHA256:
    raise RuntimeError('NEURAL-072 fixed-comparator source pin mismatch')
scorer = types.ModuleType('neural072_pinned_fixed_comparator')
scorer.__file__ = str(SCORER_PATH)
exec(compile(_source, str(SCORER_PATH), 'exec'), scorer.__dict__)
legacy = scorer.legacy
require = scorer.require
ContractError = scorer.ContractError
DELTA = 'candidate_minus_baseline_contextual_r2'


def paired_cells(baseline_report, candidate_report):
    """Subtract errors before target/listener macro aggregation, on exact cells."""
    def index(report):
        cells = report['cells']
        result = {(cell['listener'], cell['story_family']): cell for cell in cells}
        require(len(result) == len(cells), 'duplicate listener/family cell')
        return result

    baseline, candidate = index(baseline_report), index(candidate_report)
    require(set(baseline) == set(candidate), 'paired cell support differs')
    result = []
    for key in sorted(baseline):
        left, right = baseline[key], candidate[key]
        require(left['runs'] == right['runs'] and
                left['scored_rows_by_run'] == right['scored_rows_by_run'],
                'paired run/row support differs')
        require(left['sst_by_target'] == right['sst_by_target'], 'paired target variance differs')
        with legacy.np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            delta = ((legacy.np.asarray(left['sse_by_target']['contextual']) -
                      legacy.np.asarray(right['sse_by_target']['contextual'])) /
                     legacy.np.asarray(left['sst_by_target']))
        require(legacy.np.isfinite(delta).all(), 'nonfinite paired variance difference')
        mean = float(legacy.np.mean(delta))
        require(legacy.np.isfinite(mean), 'nonfinite paired target macro')
        result.append({'listener': key[0], 'story_family': key[1],
                       'runs': left['runs'], 'scored_rows_by_run': left['scored_rows_by_run'],
                       'delta_r2_by_target': delta.tolist(), 'contrasts': {DELTA: mean}})
    return result


def validate_pair(protocol, cases, baseline, candidate, reference_bytes, expected_reference_sha256):
    """Validate both submissions and the one protected reference before targets."""
    legacy.validate(protocol, cases)
    reference = scorer.authenticated_reference(protocol, cases, reference_bytes, expected_reference_sha256)
    scorer.joined_prediction(protocol, cases, reference, baseline)
    scorer.joined_prediction(protocol, cases, reference, candidate)


def compare(protocol, cases, test_targets, baseline, candidate,
            reference_bytes, expected_reference_sha256):
    validate_pair(protocol, cases, baseline, candidate, reference_bytes, expected_reference_sha256)
    reports = {
        'baseline': scorer.score(protocol, cases, test_targets, baseline,
                                 reference_bytes, expected_reference_sha256),
        'candidate': scorer.score(protocol, cases, test_targets, candidate,
                                  reference_bytes, expected_reference_sha256),
    }
    cells = paired_cells(reports['baseline'], reports['candidate'])
    uncertainty = legacy.bootstrap(cells, protocol['bootstrap_replicates'], protocol['seed'])
    # Preserve the declared >10% empty-draw failure rule without rounding it
    # down for small requested replicate counts in the predecessor helper.
    require(10 * uncertainty['empty'] <= uncertainty['requested'],
            'too many empty crossed-cluster bootstrap draws')
    return {
        'schema': 'neural072-paired-contextual-comparison/v1', 'task_id': 'NEURAL-072',
        'scientific_qualified': False, 'submission_ready': False,
        'protocol_sha256': legacy.digest(protocol), 'cases_sha256': legacy.digest(cases),
        'reference_file_sha256': expected_reference_sha256,
        'baseline_sha256': legacy.digest(baseline), 'candidate_sha256': legacy.digest(candidate),
        'fixed_comparator_source_sha256': SCORER_SHA256,
        'comparison_source_sha256': scorer.sha256(Path(__file__).read_bytes()),
        'direction': 'positive favors candidate',
        'estimand': 'Paired difference in contextual-minus-fixed-lexical R2; the common lexical reference cancels. Runs pool within listener/family per target, then targets, families within listener, and listeners receive equal weight.',
        'target_ids': cases['target_ids'],
        'test_run_ids': [run['id'] for run in cases['runs'] if run['split'] == 'test'],
        'counts': reports['baseline']['counts'],
        'reports': reports, 'paired_cells': cells,
        'paired_listener_macro_delta_r2': legacy.summarize(cells)[DELTA],
        'paired_by_listener': {listener: legacy.summarize([cell for cell in cells if cell['listener'] == listener])[DELTA]
                               for listener in sorted({cell['listener'] for cell in cells})},
        'paired_by_story_family': {family: legacy.summarize([cell for cell in cells if cell['story_family'] == family])[DELTA]
                                   for family in sorted({cell['story_family'] for cell in cells})},
        'paired_uncertainty': uncertainty,
        'preserved_holds': legacy.HOLDS,
        'limits': [
            'Generated controls do not establish authentic Narratives performance or neural understanding.',
            'Complete means the declared frozen panel; authentic population and NEURAL-071 equivalence remain unqualified.',
            'Both submissions must be frozen prospectively under matched permitted inputs, capacity and resources; this helper cannot certify those conditions or chronology.',
            'The paired interval resamples listener and family weights jointly for both submissions, not independent marginal score intervals; it is descriptive for the observed incidence design.',
            'No direct-observation endpoint, participant runtime, OS isolation, or reference custody root is supplied.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'cases', 'baseline', 'candidate', 'reference', 'targets',
                 'expected-reference-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        names = ('protocol', 'cases', 'baseline', 'candidate', 'reference')
        raw = {name: Path(getattr(args, name)).read_bytes() for name in names}
        protocol, cases, baseline, candidate = (scorer.decode(raw[name]) for name in names[:-1])
        validate_pair(protocol, cases, baseline, candidate, raw['reference'], args.expected_reference_sha256)
        raw['targets'] = Path(args.targets).read_bytes()
        report = compare(protocol, cases, scorer.decode(raw['targets']), baseline, candidate,
                         raw['reference'], args.expected_reference_sha256)
        report['input_file_sha256'] = {name: scorer.sha256(value) for name, value in raw.items()}
        encoded = scorer.encode(report)
        scorer.write_new(args.output, encoded)
        print(scorer.encode({'task_id': 'NEURAL-072', 'artifact_sha256': scorer.sha256(encoded),
                             'scientific_qualified': False}).decode().strip())
    except (ContractError, OSError, ValueError, TypeError, legacy.np.linalg.LinAlgError) as exc:
        parser.exit(2, 'NEURAL-072 paired comparison rejected input: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
