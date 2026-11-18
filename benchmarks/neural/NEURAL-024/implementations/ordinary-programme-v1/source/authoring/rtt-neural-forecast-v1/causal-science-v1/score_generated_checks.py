"""Focused future-worker scorer controls; never executed during source authoring."""
import copy
import math


GUARD_NAMES = (
    'tiny_full_poisson_hand_score_and_six_reference_contrasts',
    'negative_candidate_gain_is_preserved',
    'zero_spike_denominators_remain_undefined_without_dropping_channels',
    'missing_reference_arm_or_changed_channel_identity_is_rejected',
    'reference_counts_and_scalar_aggregates_must_reconcile',
    'nonfinite_or_nonpositive_means_and_wrong_support_are_rejected',
    'finite_extreme_means_report_numerical_failure_without_clipping',
    'public_score_keeps_production_dimensions_and_no_causality_claim',
)


def run_checks(core, tick=None):
    import numpy as np
    import reference_model_core
    names = []

    def check(name, condition):
        if tick is not None:
            tick()
        if not condition:
            raise AssertionError(name)
        names.append(name)

    def rejected(fn):
        try:
            fn()
        except (ValueError, KeyError):
            return True
        return False

    def refs(y, means):
        result = reference_model_core.score(y, means)
        return {'status': 'complete_fixed_development_panel',
                'arms': {name: copy.deepcopy(result) for name in core.ARMS}}

    y = np.asarray([[0, 1], [2, 0]], dtype=np.int64)
    means = np.asarray([[.5, 1.], [2., .25]], dtype=np.float64)
    references = refs(y, means)
    hand = -.5 - 1. + 2. * math.log(2.) - 2. - math.log(2.) - .25
    result = core._score(y, means, references, (2, 2), tick=tick)
    check('tiny_full_poisson_hand_score_and_six_reference_contrasts',
          result['status'] == 'candidate_poisson_score_completed'
          and abs(result['candidate_score']['log_likelihood'] - hand) <= 1e-12
          and abs(result['candidate_score']['mean_nll'] + hand / 4.) <= 1e-12
          and result['support']['observed_spikes'] == 3
          and tuple(result['comparisons']) == core.ARMS
          and all(v['bits_per_spike_gain'] == 0. for v in result['comparisons'].values())
          and result['independent_audit']['counters']['score_cells_checked'] == 4
          and result['calibration_rate_control']['exact_parity'] is True
          and result['calibration_rate_control']['zero_primary_gain'] is True
          and result['calibration_rate_control']['scalar_fields_compared'] == 14
          and result['calibration_rate_control']['maximum_absolute_scalar_difference'] == 0.)
    worse = core._score(y, np.full((2, 2), 20., dtype=np.float64), references, (2, 2), tick=tick)
    check('negative_candidate_gain_is_preserved',
          worse['status'] == 'candidate_poisson_score_completed'
          and all(v['log_likelihood_gain'] < 0. and v['bits_per_spike_gain'] < 0.
                  and v['mean_nll_reduction'] < 0. for v in worse['comparisons'].values())
          and worse['calibration_rate_control']['exact_parity'] is False
          and worse['calibration_rate_control']['zero_primary_gain'] is False
          and worse['calibration_rate_control']['maximum_absolute_scalar_difference'] > 0.)
    no_spikes = np.zeros((2, 2), dtype=np.int64)
    empty = core._score(no_spikes, means, refs(no_spikes, means), (2, 2), tick=tick)
    check('zero_spike_denominators_remain_undefined_without_dropping_channels',
          empty['status'] == 'candidate_poisson_score_completed'
          and empty['bits_per_spike_vs_calibration_rate'] is None
          and empty['bits_per_spike_undefined_reason'] == 'zero_observed_query_spikes'
          and empty['candidate_score']['mean_nll'] > 0.
          and len(empty['candidate_score']['per_channel']) == 2
          and all(item['bits_per_spike_vs_calibration_rate'] is None
                  for item in empty['candidate_score']['per_channel']))
    missing = copy.deepcopy(references)
    missing['arms'].pop('source_rate')
    identity = copy.deepcopy(references)
    identity['arms']['source_rate']['per_channel'][0]['channel_index'] = 1
    check('missing_reference_arm_or_changed_channel_identity_is_rejected',
          rejected(lambda: core._score(y, means, missing, (2, 2), tick=tick))
          and rejected(lambda: core._score(y, means, identity, (2, 2), tick=tick)))
    count = copy.deepcopy(references)
    count['arms']['source_rate']['per_channel'][0]['spikes'] += 1
    aggregate = copy.deepcopy(references)
    aggregate['arms']['source_rate']['log_likelihood'] -= 1.
    nll = copy.deepcopy(references)
    nll['arms']['source_rate']['mean_nll'] += 1.
    check('reference_counts_and_scalar_aggregates_must_reconcile',
          rejected(lambda: core._score(y, means, count, (2, 2), tick=tick))
          and rejected(lambda: core._score(y, means, aggregate, (2, 2), tick=tick))
          and rejected(lambda: core._score(y, means, nll, (2, 2), tick=tick)))
    zero, nonfinite = means.copy(), means.copy()
    zero[0, 0], nonfinite[0, 0] = 0., math.inf
    check('nonfinite_or_nonpositive_means_and_wrong_support_are_rejected',
          rejected(lambda: core._score(y, zero, references, (2, 2), tick=tick))
          and rejected(lambda: core._score(y, nonfinite, references, (2, 2), tick=tick))
          and rejected(lambda: core._score(y, means[:1], references, (2, 2), tick=tick)))
    extreme = np.full((2, 2), 1e308, dtype=np.float64)
    failure = core._score(y, extreme, references, (2, 2), tick=tick)
    check('finite_extreme_means_report_numerical_failure_without_clipping',
          bool(np.isfinite(extreme).all()) and failure['status'] == 'numerical_failure'
          and failure['candidate_score'] is None and failure['comparisons'] is None
          and failure['score_clipped_or_floored'] is False)
    check('public_score_keeps_production_dimensions_and_no_causality_claim',
          core.SHAPE == (22090, 96)
          and rejected(lambda: core.score(y, means, references, tick=tick))
          and result['causal_qualification_inferred_from_batch_arrays'] is False
          and result['new_model_fits'] == 0)
    if tuple(names) != GUARD_NAMES or len(set(names)) != len(names):
        raise AssertionError('Exact unique scorer control roster')
    return {'status': 'synthetic_private_poisson_score_checks_passed', 'checks': len(names), 'names': names,
            'empirical_inputs_opened': 0, 'empirical_array_values_decoded': 0,
            'candidate_invocations': 0, 'model_fits': 0}
