"""Complete ordered native numeric schema for the six pinned empirical scripts.

Dynamic F, E and per-run T are read from literal captured axes/coordinates,
not guessed from old scalar-audit lengths. Field dimensions identify all state
axes, permitting one later covariance-derived permutation without raw rewrites.
"""
from collections import Counter
import re

BRANCHES = {
    'ctf_bursts': dict(people=65, runs=65, states=3, channels=1, features=21, sequence=2000, hz=100),
    'elekta_ae': dict(people=19, runs=114, states=8, channels=38, features=38, sequence=2000, hz=250),
    'elekta_tde': dict(people=19, runs=114, states=8, channels=38, features=80, sequence=2000, hz=250),
    'ctf_tde': dict(people=65, runs=65, states=8, channels=38, features=80, sequence=2000, hz=250),
    'ctf_dynemo': dict(people=65, runs=65, states=7, channels=38, features=80, sequence=200, hz=250),
    'ctf_static': dict(people=65, runs=65, states=None, channels=38, features=38, sequence=None, hz=250),
}
REVISION = 'cded3b2ea95efef7b6c089c5e111fd565b716922'
EVENT_IDS = {'famous/first': 5, 'famous/immediate': 6, 'famous/last': 7,
             'unfamiliar/first': 13, 'unfamiliar/immediate': 14, 'unfamiliar/last': 15,
             'scrambled/first': 17, 'scrambled/immediate': 18, 'scrambled/last': 19}


def semantic_axes(branch):
    b = BRANCHES[branch]
    return {'state_or_mode': list(range(b['states'])) if b['states'] else None,
            'native_feature_index': list(range(b['features'])),
            'source_channel_index': list(range(b['channels'])),
            'channel_anatomy_and_retained_sample_maps': 'externally_authenticated_preparation_binding',
            'static_band_names': ['delta', 'theta', 'alpha', 'beta'] if branch == 'ctf_static' else None,
            'static_band_bounds_Hz': [[1, 4], [4, 7], [7, 13], [13, 30]] if branch == 'ctf_static' else None,
            'burst_envelope_band_names': ['beta', 'alpha', 'delta_theta'] if branch == 'ctf_bursts' else None,
            'burst_envelope_band_bounds_Hz': [[13, 30], [7, 13], [1, 7]] if branch == 'ctf_bursts' else None,
            'regression_psd_term': ['coefficient', 'intercept'] if branch == 'ctf_dynemo' else None,
            'nnmf_components': [0, 1] if branch in ('ctf_tde', 'elekta_tde') else None,
            'age_summary_statistic': (['fractional_occupancy', 'lifetime_s', 'interval_s', 'switching_rate_Hz'] if branch == 'ctf_tde' else ['reweighted_alpha_mean', 'reweighted_alpha_std'] if branch == 'ctf_dynemo' else None),
            'event_ids_pooled_within_source_run': EVENT_IDS if branch.startswith('elekta_') else None,
            'strict_upper_edges': 'numpy.triu_indices(source_channel_count,k=1)_lexicographic_row_order'}


def validate_context(context):
    if context.get('role') not in ('A', 'B', 'reference'):
        raise ValueError('Exact externally authenticated A/B/reference role')
    b = BRANCHES[context['branch']]
    runs = context['runs']
    if len(runs) != b['runs'] or len({r['input_id'] for r in runs}) != b['runs']:
        raise ValueError('Complete unique original native input/run roster')
    counts = Counter(r['person_id'] for r in runs)
    if len(counts) != b['people'] or set(counts.values()) != ({6} if b['runs'] == 114 else {1}):
        raise ValueError('Complete native person/run cohort')
    if len({(r['person_id'], r['run_id']) for r in runs}) != len(runs):
        raise ValueError('Unique run identity within each person')
    if len({r['source_input'] for r in runs}) != len(runs):
        raise ValueError('Unique native input paths in authenticated original order')
    original_people = ([f'sub{i:02d}' for i in range(1, b['people'] + 1)]
                       if context['branch'].startswith('elekta_') else [f'subject{i:02d}' for i in range(b['people'])])
    original_pairs = [(p, str(i)) for p in original_people for i in (range(1, 7) if b['runs'] == 114 else (1,))]
    observed_pairs = [(r['person_id'], r['run_id']) for r in runs]
    if observed_pairs != original_pairs:
        order = context.get('source_order_bijection')
        if type(order) is not list or any(type(i) is not int for i in order) or sorted(order) != list(range(len(original_pairs))):
            raise ValueError('Exact original people/runs/order or authenticated complete source-order bijection')
        if observed_pairs != [original_pairs[i] for i in order] or not re.fullmatch('[a-f0-9]{64}', context.get('source_order_binding', '')):
            raise ValueError('Source-order bijection identity/support')
    for r in runs:
        if any(type(r[k]) is not str or not r[k] for k in ('person_id', 'run_id', 'input_id', 'source_input')):
            raise ValueError('Explicit nonempty run identifiers; no aliases/inference')
    if context['revision'] != REVISION or not re.fullmatch('[a-f0-9]{64}', context['preparation_binding']) or not context['attempt_id']:
        raise ValueError('Historical source and external input/preparation/attempt binding')
    return b


def fields(context, axes):
    """Ordered field list. axes comes from assembler-inspected primitive metadata."""
    b = validate_context(context)
    branch = context['branch']
    R, K, C, D = b['runs'], b['states'], b['channels'], b['features']
    rows = []

    def add(key, shape, axis_names, units='source_native', state_axes=()):
        run_axis = list(axis_names).index('run') if 'run' in axis_names else None
        match = re.fullmatch(r'(?:model\.alpha|event\.stc)/(\d{6})|event_trials/(\d{6})\..+', key)
        run_index = int(next(v for v in match.groups() if v is not None)) if match else None
        panel = key.split('.')[0].split('/')[0]
        level = 'run' if run_axis is not None or run_index is not None else ('model' if panel == 'model' else 'group_or_axis')
        auxiliary = key.startswith(('training/', 'model.weights/', 'coordinates.')) or key == 'model.free_energy'
        rows.append(dict(key=key, shape=list(shape), axes=list(axis_names), units=units,
                         state_axes=list(state_axes), run_axis=run_axis, run_index=run_index,
                         panel=panel, aggregation={'level': level, 'operation': 'none_in_literal_assembly'},
                         auxiliary=auxiliary, comparison=not auxiliary,
                         auxiliary_rationale=('training/network state is reconstruction, provenance or selection; internal-neuron gauge is not resolved by state correspondence' if auxiliary else None),
                         undefined_policy='retain_NaN_and_signed_infinity_pattern'))

    if D == 80:
        add('coordinates.pca_components', (15 * C, 80), ('channel_lag', 'component'))
    if branch != 'ctf_static':
        for ref in axes.get('model_weights', []):
            add(ref['key'], ref['shape'], ['keras_axis_' + str(i) for i in range(len(ref['shape']))], 'literal_model_weight')
            rows[-1]['comparison_role'] = 'operator_reconstruction_only_not_an_observable_score'
        for ref in axes.get('training_arrays', []):
            add(ref['key'], ref['shape'], ['source_axis_' + str(i) for i in range(len(ref['shape']))], 'literal_training_metadata')
        if context['role'] != 'A' or axes.get('include_free_energy', False):
            add('model.free_energy', (), (), 'source_training_selection_statistic')
        add('model.means', (K, D), ('state', 'native_feature'), state_axes=(0,))
        add('model.covs', (K, D, D), ('state', 'native_feature', 'native_feature_2'), state_axes=(0,))
        if branch != 'ctf_dynemo':
            add('model.initial', (K,), ('state',), 'probability', (0,))
            add('model.transition', (K, K), ('from_state', 'to_state'), 'probability', (0, 1))
        for i, T in enumerate(axes['alpha_samples']):
            add('model.alpha/' + str(i).zfill(6), (T, K), ('sample', 'state'), 'probability', (1,))
    if branch != 'elekta_ae':
        F = axes['frequencies']
        add('spectra.f', (F,), ('frequency',), 'Hz')
        if branch == 'ctf_static':
            add('spectra.psd', (R, C, F), ('run', 'channel', 'frequency'))
            add('spectra.coh', (R, C, C, F), ('run', 'channel', 'channel_2', 'frequency'))
        elif branch == 'ctf_dynemo':
            add('spectra.psd', (R, 2, K, C, F), ('run', 'coefficient_or_intercept', 'state', 'channel', 'frequency'), state_axes=(2,))
            add('spectra.coh', (R, K, C, C, F), ('run', 'state', 'channel', 'channel_2', 'frequency'), state_axes=(1,))
        else:
            add('spectra.psd', (R, K, C, F), ('run', 'state', 'channel', 'frequency'), state_axes=(1,))
            if branch == 'ctf_bursts':
                # Internal coherence_spectra squeezes the singleton channel pair
                # before outer multitaper keepdims=True can retain it.
                add('spectra.coh', (R, K, F), ('run', 'state', 'frequency'), state_axes=(1,))
            else:
                add('spectra.coh', (R, K, C, C, F), ('run', 'state', 'channel', 'channel_2', 'frequency'), state_axes=(1,))
        if branch in ('ctf_tde', 'elekta_tde'):
            add('spectra.nnmf', (2, F), ('nnmf_component_peak_order', 'frequency'))
        if branch in ('ctf_tde', 'elekta_tde', 'ctf_dynemo'):
            add('group_spectra.psd', (K, C, F), ('state', 'channel', 'frequency'), state_axes=(0,))
            add('group_spectra.coh', (K, C, C, F), ('state', 'channel', 'channel_2', 'frequency'), state_axes=(0,))
            add('group_spectra.channel_mean', (K, F), ('state', 'frequency'), state_axes=(0,))
            add('group_spectra.channel_sem', (K, F), ('state', 'frequency'), state_axes=(0,))
            prefix = (2,) if branch != 'ctf_dynemo' else ()
            names = ('nnmf_component_peak_order',) if prefix else ()
            sax = (len(prefix),)
            add('network.power', prefix + (K, C), names + ('state', 'channel'), state_axes=sax)
            for name in ('coherence_unthresholded', 'coherence_thresholded'):
                add('network.' + name, prefix + (K, C, C), names + ('state', 'channel', 'channel_2'), state_axes=sax)
    if branch == 'ctf_bursts':
        for key, unit in [('lt', 's'), ('intv', 's'), ('bc', 'Hz_source_diff_onsets'), ('amp', 'source_native')]:
            add('summary.' + key, (R, K), ('run', 'state'), unit, (1,))
        add('burst_group.psd', (K, axes['frequencies']), ('state', 'frequency'), state_axes=(0,))
        add('burst_group.tde_covs', (K, D, D), ('state', 'lag', 'lag_2'), state_axes=(0,))
        add('burst_envelopes.correlation', (3, K), ('beta_alpha_delta_theta_band', 'state'), state_axes=(1,))
        add('burst_envelopes.envelopes', (axes['envelope_samples'], 3), ('concatenated_source_samples', 'beta_alpha_delta_theta_band'))
    elif branch == 'ctf_dynemo':
        for key in ('alp_mean', 'alp_std'):
            add('summary.' + key, (R, K), ('run', 'state'), 'covariance_trace_reweighted_alpha', (1,))
        add('summary.alp_corr', (R, K, K), ('run', 'state', 'state_2'), 'correlation_source_zero_diagonal', (1, 2))
    elif branch != 'ctf_static':
        for key, unit in [('fo', 'fraction'), ('lt', 's'), ('intv', 's'), ('sr', 'Hz_source_diff_onsets')]:
            add('summary.' + key, (R, K), ('run', 'state'), unit, (1,))
    if branch == 'elekta_ae':
        add('ae_network.aecs', (K, C, C), ('state', 'channel', 'channel_2'), 'absolute_covariance_correlation', (0,))
    if branch.startswith('elekta_'):
        E = axes['event_times']
        for i, T in enumerate(axes['alpha_samples']):
            ix = str(i).zfill(6)
            add('event.stc/' + ix, (T, K), ('sample', 'state'), 'hard_argmax_one_hot', (1,))
            add('event_trials/' + ix + '.trials', (axes['event_trials'][i], K, E), ('trial', 'state', 'event_time'), 'hard_state', (1,))
            add('event_trials/' + ix + '.events_found', (axes['events_found'][i], 3), ('found_event', 'mne_event_field'))
            add('event_trials/' + ix + '.events_retained', (axes['event_trials'][i], 3), ('retained_event', 'mne_event_field'))
            add('event_trials/' + ix + '.times', (E,), ('event_time',), 's_before_34ms_correction')
        add('event.t', (E,), ('event_time',), 's_after_minus_34ms')
        add('event.epochs', (R, E, K), ('run', 'event_time', 'state'), 'baseline_corrected_hard_state_trial_mean', (2,))
        add('event.pvalues', (E, K), ('event_time', 'state'), 'native_1000_permutation_pvalue', (1,))
    if branch in ('ctf_tde', 'ctf_dynemo'):
        S = 4 if branch == 'ctf_tde' else 2
        add('age_summary.values', (R, S, K), ('run', 'summary', 'state'), state_axes=(2,))
        add('age_summary.assignments', (R,), ('run',), 'group1_age_le34_group2_gt34')
        for key in ('effect', 'pvalues'):
            add('age_summary.' + key, (S, K), ('summary', 'state'), 'literal_group1_minus_group2_or_pvalue', (1,))
    if branch == 'ctf_tde':
        add('age_power.values', (R, K, C), ('run', 'state', 'channel'), 'nnmf_component0', (1,))
        add('age_power.assignments', (R,), ('run',), 'group1_age_le34_group2_gt34')
        for key in ('effect', 'pvalues', 'masked_effect'):
            add('age_power.' + key, (K, C), ('state', 'channel'), 'nnmf_component0_native_contrast', (0,))
        P = C * (C - 1) // 2
        add('age_coherence.values', (R, K, P), ('run', 'state', 'strict_upper_edge'), 'nnmf_component0', (1,))
        add('age_coherence.assignments', (R,), ('run',), 'group1_age_le34_group2_gt34')
        for key in ('effect', 'pvalues'):
            add('age_coherence.' + key, (K, P), ('state', 'strict_upper_edge'), 'nnmf_component0_native_contrast', (0,))
        add('age_coherence.masked_matrix', (K, C, C), ('state', 'channel', 'channel_2'), state_axes=(0,))
    if branch == 'ctf_static':
        P = C * (C - 1) // 2
        add('static.power', (R, 4, C), ('run', 'band', 'channel'))
        for key in ('coherence', 'aec'):
            add('static.' + key, (R, 4, C, C), ('run', 'band', 'channel', 'channel_2'))
            add('static_group.' + key, (4, C, C), ('band', 'channel', 'channel_2'))
        add('static_group.power', (4, C), ('band', 'channel'))
        add('age_power.assignments', (R,), ('run',), 'group1_age_ge34_group2_lt34')
        for key in ('effect', 'pvalues'):
            add('age_power.' + key, (4, C), ('band', 'channel'))
            add('age_aec.' + key, (4, P), ('band', 'strict_upper_edge'))
        add('age_aec.values', (R, 4, P), ('run', 'band', 'strict_upper_edge'))
        add('age_aec.masked_matrix', (4, C, C), ('band', 'channel', 'channel_2'))
    return rows
