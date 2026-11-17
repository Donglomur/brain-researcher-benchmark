"""Actual SpikeInterface and KS4 calls; historical version resolution is required.

This module is a worker scientific consumer, not an isolation/permission broker.
Library imports and every sorter effect occur only when its functions are called
by a separately qualified native workload. BUILD never calls them.
"""
from pathlib import Path
from importlib import metadata
from .common import require, unique, Unavailable

METHODS = {'Kilosort1':'kilosort', 'Kilosort2':'kilosort2',
           'Kilosort2.5':'kilosort2_5', 'Kilosort3':'kilosort3',
           'Kilosort4':'kilosort4', 'IronClust':'ironclust',
           'MountainSort4':'mountainsort4', 'SpyKING CIRCUS':'spykingcircus',
           'SpyKING CIRCUS 2':'spykingcircus2', 'HDSort':'hdsort',
           'Herding Spikes':'herdingspikes'}
MINIMUM_REFERENCES = ('Kilosort4','IronClust','MountainSort4','SpyKING CIRCUS')


def validate_comparison_matrix(rows, case_ids, *, profile):
    """Require exact supplied incidence; never infer an eleven-by-all grid."""
    require(profile in {'R_source20','R_paper40','I_bijective_full'}, 'scope-collapse')
    cases = set(case_ids)
    require(len(cases) == len(case_ids) and len(cases) >= 11, 'complete-core-case-roster')
    jobs = unique(rows, 'id')
    for row in jobs.values():
        require(row['case_id'] in cases and row['method'] in METHODS, 'comparison-incidence')
        require(row['scope'] == profile, 'comparison-profile-mismatch')
        require(row['version'] and row['wrapper_version'] and row['source_binding']
                and row['environment_binding'], 'historical-version-not-resolved', row['id'])
        require(type(row['parameters']) is dict and row['parameters_complete'] is True,
                'unresolved-comparator-defaults', row['id'])
        require(row['purpose'] in {'original-comparison','original-threshold-sweep',
                                  'original-ablation','fixed-I-reference'}, 'comparison-purpose')
    for case in cases:
        found = {r['method'] for r in rows if r['case_id']==case
                 and r['purpose'] in {'original-comparison','fixed-I-reference'}}
        require(set(MINIMUM_REFERENCES) <= found, 'missing-competent-reference', case)
    require(len(rows) >= 44, 'minimum-forty-four-reference-sorts')
    # Historical additional methods, sweeps and ablations are mandatory separate
    # incidence rows in the complete catalog. Four minimum references do not erase them.
    return jobs


def paper_parameter_constraints(method, parameters, parameter_names):
    """Verify documented values under version-specific, explicit parameter names."""
    require(method in METHODS, 'unknown-sorter')
    required = {}
    if method in {'Kilosort1','Kilosort2','Kilosort2.5','Kilosort3'}:
        required['detection_thresholds'] = [9,8]
    if method == 'Kilosort1': required['passes'] = 2
    if method == 'MountainSort4': required['adjacency_radius'] = 50
    if method == 'SpyKING CIRCUS': required['detection_threshold'] = 4.5
    for logical, value in required.items():
        require(logical in parameter_names, 'historical-wrapper-parameter-name-unresolved', logical)
        key = parameter_names[logical]
        require(key in parameters and parameters[key] == value, 'paper-parameter-mismatch', logical)
    return parameters


def run_spikeinterface(recording, row, output_folder):
    """Fixed real package API, no arbitrary callback or source supplied entrypoint."""
    require(row['method'] in METHODS, 'unknown-sorter')
    require(metadata.version('spikeinterface') == row['wrapper_version'], 'wrapper-version-mismatch')
    require(row['installed_sorter_version'] == row['version'], 'sorter-version-unresolved')
    # This value is only a consistency assertion. Actual executable/source/image
    # identity must be authenticated by the original native launcher before entry.
    require(row['source_binding'] and row['environment_binding'], 'source-environment-binding-missing')
    output = Path(output_folder)
    require(not output.exists(), 'sorter-output-already-exists')
    from spikeinterface.sorters import run_sorter, get_default_params
    sorter = METHODS[row['method']]
    known = get_default_params(sorter)
    require(set(row['parameters']) == set(known), 'complete-version-parameter-vector-required')
    if row['scope'] == 'R_paper40':
        paper_parameter_constraints(row['method'], row['parameters'], row['parameter_names'])
    return run_sorter(sorter_name=sorter, recording=recording,
                      output_folder=output, remove_existing_folder=False,
                      delete_output_folder=False, raise_error=True,
                      docker_image=False, singularity_image=False, **row['parameters'])


def run_literal_ks4(settings, probe, filename, output_folder, *, run_options):
    """Current captured source call; settings are complete, not inferred defaults."""
    require(metadata.version('kilosort') == '4.0.2', 'literal-release-version')
    from kilosort import run_kilosort
    from kilosort.parameters import DEFAULT_SETTINGS
    require(set(settings)==set(DEFAULT_SETTINGS)|{'n_chan_bin'}, 'complete-recording-settings')
    require(set(run_options)=={'data_dtype','do_CAR','invert_sign','device','save_extra_vars'},
            'explicit-KS4-call-options-required')
    require(run_options['data_dtype'] is not None and run_options['device'] is not None,
            'KS4-dtype-device-must-be-selected')
    import torch
    run_options={**run_options,'device':torch.device(run_options['device'])}
    require(not Path(output_folder).exists(), 'ks4-output-already-exists')
    return run_kilosort(settings=dict(settings), probe=probe, filename=filename,
                        results_dir=output_folder,**run_options)


def extract_sorting_events(sorting, expected_segment_count, sample_counts):
    """All units and all segments, including empty trains, retain native sample clocks."""
    require(sorting.get_num_segments() == expected_segment_count == len(sample_counts),
            'sorting-segment-support')
    ids = list(sorting.get_unit_ids())
    require(len(ids) == len(set(ids)), 'duplicate-sorter-unit-id')
    rows = []
    for unit in ids:
        segments = []
        for segment, count in enumerate(sample_counts):
            samples = sorting.get_unit_spike_train(unit_id=unit, segment_index=segment)
            require(samples.dtype.kind in 'iu' and samples.ndim == 1,
                    'invalid-sorter-event-clock')
            require(all(0 <= int(v) < count for v in samples), 'sorter-event-outside-recording')
            segments.append({'segment':segment,'samples':samples})
        rows.append({'native_unit_id':unit,'segments':segments})
    return {'units':rows,'sampling_frequency':sorting.get_sampling_frequency(),
            'native_events_only':True,'quality_labels_trusted':False}


def select_original_threshold(rows, declared_threshold_ids, *, tie_policy):
    """Historical medium-drift tuning only; forbidden as held-out improvement tuning."""
    indexed = unique(rows, 'threshold_id')
    require(set(indexed) == set(declared_threshold_ids) and len(indexed)>0,
            'incomplete-original-threshold-sweep')
    require(tie_policy in {'first-declared','last-declared','unavailable'}, 'unselected-sweep-tie-rule')
    require(all(r['case']=='medium-drift' and r['scope']=='R_paper40'
                and r['status']=='independent-banks-agreed' for r in rows),
            'threshold-sweep-support-or-score-unavailable')
    best = max(r['correctly_identified'] for r in rows)
    ties = [i for i in declared_threshold_ids if indexed[i]['correctly_identified']==best]
    require(len(ties)==1 or tie_policy!='unavailable', 'historical-threshold-tie-unresolved', ties)
    selected = ties[-1] if tie_policy=='last-declared' else ties[0]
    return {'threshold_id':selected,'all_ties':ties,'support':list(declared_threshold_ids),
            'held_out_improvement_evidence':False,'historical_equivalence':False}
