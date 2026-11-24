"""Operator-only complete-panel comparison of declared direct/program attempts.

This checks supplied identities and information bindings, not authentic cohort
membership, actual delivery, tool restrictions, fitting or scientific validity.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location('neural088_count_endpoint', Path(__file__).with_name('scorer.py'))
scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)

MODES = ('direct_observation', 'frozen_program')
HISTORICAL_EDGE_N = 6691
HISTORICAL_PRE_N = 21
BINDING_FIELDS = {'query_observations_sha256', 'fit_validation_exposure_sha256'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _sha256(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_protocol(protocol):
    """The roster and matching receipts are trusted operator inputs, not answers."""
    scorer.require(type(protocol) is dict and set(protocol) == {
        'rows', 'rate_floor', 'fixed_reference_views', 'information_bindings'}, 'Exact paired protocol fields required')
    rows = scorer.validate_roster(protocol['rows'])
    scorer.require(len(rows) == HISTORICAL_EDGE_N and len({r['pre_id'] for r in rows}) == HISTORICAL_PRE_N,
                   'Complete declared historical panel requires 6691 pairs and 21 presynaptic units')
    scorer.require(scorer.finite_number(protocol['rate_floor'], positive=True), 'Positive frozen floor required')
    scorer.align_views(rows, protocol['fixed_reference_views'])
    bindings = protocol['information_bindings']
    scorer.require(type(bindings) is dict and set(bindings) == set(MODES), 'Exact operator mode bindings required')
    for mode in MODES:
        views = bindings[mode]
        scorer.require(type(views) is dict and set(views) == set(scorer.VIEWS), 'Exact information-view bindings required')
        for view in scorer.VIEWS:
            item = views[view]
            scorer.require(type(item) is dict and set(item) == BINDING_FIELDS and all(_sha256(v) for v in item.values()),
                           'Exact observation and fit/validation SHA-256 bindings required')
    scorer.require(bindings[MODES[0]] == bindings[MODES[1]], 'Direct/program information bindings differ')
    return rows


def compare(protocol, submissions, load_private_counts):
    """Validate every submitted mode before one common target read.

    An invalid mode invalidates the comparison; no intersection, dropped cases,
    successful-mode-only score, or feedback from an earlier mode is emitted.
    """
    rows = validate_protocol(protocol)
    try:
        scorer.require(type(submissions) is dict and set(submissions) == set(MODES), 'Both and only declared access modes required')
        for mode in MODES:
            scorer.align_views(rows, submissions[mode])
    except (ValueError, TypeError, OverflowError) as exc:
        return {'status': 'invalid_submission', 'reason': str(exc), 'private_callback_invocations': 0,
                'mode_results': None, 'direct_minus_program': None}
    counts = load_private_counts()
    # The same in-memory target object and same fixed references serve both modes.
    scorer.align_counts(rows, counts)
    results = {mode: scorer.grade(rows, submissions[mode], protocol['fixed_reference_views'],
                                 lambda: counts, rate_floor=protocol['rate_floor']) for mode in MODES}
    scored = all(result['status'] == 'scored' for result in results.values())
    contrasts = {}
    for view in scorer.VIEWS:
        left = results[MODES[0]]['arms']['candidate'][view]
        right = results[MODES[1]]['arms']['candidate'][view]
        contrast = scorer._contrast(left, right)
        # One unsupported arm prevents a complete paired comparison in any view.
        contrasts[view] = contrast if scored else None
    return {
        'status': 'scored' if scored else 'valid_unscorable_arithmetic',
        'comparison_version': 'NEURAL-088/paired-access-v1',
        'private_callback_invocations': 1,
        'protocol_sha256': digest(protocol),
        'edge_n': len(rows), 'unique_presynaptic_n': HISTORICAL_PRE_N,
        'information_binding_status': 'operator_declared_equal_not_delivery_attested',
        'mode_results': results,
        'direct_minus_program': {
            'direction': 'positive_means_lower_program_loss',
            'by_view': contrasts,
            'joint_view_primary_difference': contrasts['anatomy_plus_in_vivo']['equal_presynaptic_loss_difference'] if scored else None},
        'scope': 'Generated-control-qualified arithmetic only; supplied roster identity and delivery require independent review. '
                 'Processed functional correlation is not raw-neural interpretation. One mouse; no animal-population or causal claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, help='Operator-only full roster, references, floor and information bindings')
    parser.add_argument('--submissions', required=True, help='Both complete direct_observation and frozen_program paired-view outputs')
    parser.add_argument('--targets', required=True, help='Operator-only counts; read after both modes validate')
    parser.add_argument('--output', required=True, help='Operator-only comparison report')
    args = parser.parse_args()
    report = compare(scorer.read_json(args.protocol), scorer.read_json(args.submissions), lambda: scorer.read_json(args.targets))
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return 0 if report['status'] == 'scored' else 2


if __name__ == '__main__':
    raise SystemExit(main())
