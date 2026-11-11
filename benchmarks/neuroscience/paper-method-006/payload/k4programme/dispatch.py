"""Closed calls to concrete new scientific consumers, with no import-by-name ABI."""
from .common import require, Unavailable

OPERATIONS = {
    'waveform_depth_means': ('voltage','sample_indices','unit_indices','event_depths'),
    'denoise_depth_waveforms': ('means',),
    'kriging_depth_grid': ('waveforms','original_positions','target_positions'),
    'biophysical_twice_speed': ('signal','truth_sample_times'),
    'unwhiten_and_encode': ('voltage','whitening'),
    'depth_interpolation': ('drift','positions','channel_positions'),
    'eleven_source_join': tuple(f'waveforms_{i:02}' for i in range(11)),
    'retained_depth_selection': ('waveforms','retained','variation'),
    'original_threshold_selection': (),
    'spikeinterface_sort': (),
    'literal_ks4_sort': (),
    'inject_signal': ('background','waveforms','events','channel_map','amplitudes'),
    'eligible_depth_selection': ('means','counts'),
    'hybrid_waveform_means': ('voltage','event_samples','event_units'),
    'legacy_summary': (),
    'render_panel': (),
}
JSON_OPERANDS={'legacy_summary':('request','operands'),'render_panel':('series',),
    'waveform_depth_means':('source',), 'eligible_depth_selection':('support',),
    'denoise_depth_waveforms':('support',), 'retained_depth_selection':('support',),
    'kriging_depth_grid':('support',),
    'eleven_source_join':tuple(f'support_{i:02}' for i in range(11))+('isi_records',)}


def execute(operation, inputs, parameters, artifacts):
    require(operation in OPERATIONS, 'absent-scientific-consumer', operation)
    require(set(inputs)==set(OPERATIONS[operation])|set(JSON_OPERANDS.get(operation,())),
            'scientific-operand-support',operation)
    arrays={}
    for role in OPERATIONS[operation]:
        row=inputs[role]
        arrays[role]=artifacts.array(row['pin'],row['dtype'],row['shape'])
    json_inputs={role:(artifacts.json_input(inputs[role]['pin']) if 'pin' in inputs[role]
                       else inputs[role]['value']) for role in JSON_OPERANDS.get(operation,())}
    budget=artifacts.budget
    if operation=='waveform_depth_means':
        from .waveform_chain import waveform_depth_means
        return waveform_depth_means(**arrays,**json_inputs,**parameters,budget=budget)
    if operation=='denoise_depth_waveforms':
        from .waveform_chain import denoise_depth_waveforms
        return denoise_depth_waveforms(**arrays,**json_inputs,**parameters,budget=budget)
    if operation=='retained_depth_selection':
        from .waveform_chain import retained_depth_selection
        return retained_depth_selection(**arrays,**json_inputs,**parameters,budget=budget)
    if operation=='kriging_depth_grid':
        from .waveform_chain import kriging_depth_grid
        return kriging_depth_grid(**arrays,**json_inputs,**parameters,budget=budget)
    if operation=='biophysical_twice_speed':
        from .transforms import biophysical_twice_speed
        return biophysical_twice_speed(**arrays,**parameters,budget=budget)
    if operation=='unwhiten_and_encode':
        from .transforms import unwhiten_and_encode
        return unwhiten_and_encode(**arrays,**parameters,budget=budget)
    if operation=='depth_interpolation':
        from .transforms import depth_interpolation
        return depth_interpolation(**arrays,**parameters,budget=budget)
    if operation=='eleven_source_join':
        from .waveform_chain import assemble_eleven
        return assemble_eleven([arrays[f'waveforms_{i:02}'] for i in range(11)],
            [json_inputs[f'support_{i:02}'] for i in range(11)],
            json_inputs['isi_records'],**parameters,budget=budget)
    if operation=='original_threshold_selection':
        from .comparators import select_original_threshold
        return select_original_threshold(**parameters)
    if operation=='literal_ks4_sort':
        from .comparators import run_literal_ks4
        require('output_folder' not in parameters,'worker-owns-sort-output')
        artifacts.authenticate(parameters['recording_pin'])
        out=artifacts.output/'sort-output'
        run_literal_ks4(parameters['settings'],parameters['probe'],parameters['recording_pin']['path'],out,
                        run_options=parameters['run_options'])
        return {'files':artifacts.inventory_tree(out),'parent_capture_required':True}
    if operation=='spikeinterface_sort':
        return comparator_worker(parameters,artifacts)
    if operation=='inject_signal':
        from .signals import inject_signal
        return inject_signal(**arrays,**parameters,budget=budget)
    if operation=='eligible_depth_selection':
        from .waveform_chain import eligible_depth_selection
        return eligible_depth_selection(**arrays,**json_inputs,**parameters,budget=budget)
    if operation=='hybrid_waveform_means':
        from .signals import hybrid_waveform_means
        return hybrid_waveform_means(**arrays,**parameters,budget=budget)
    if operation=='legacy_summary':
        from k4bench.summaries import dispatch_summary
        require(not parameters,'legacy-summary-parameters-live-in-request')
        return dispatch_summary(json_inputs['request'],json_inputs['operands'])
    if operation=='render_panel':
        from .figures import render_panel
        return render_panel(json_inputs['series'],**parameters,artifacts=artifacts)
    raise AssertionError('closed operation dispatch mismatch')


def comparator_worker(parameters, artifacts):
    """Construct an actual full binary recording, then execute the selected sorter.

    Byte pins are integrity checks, not native/rights/source qualification. The
    caller must have admitted the complete original signal and geometry first.
    No arbitrary serialized extractor is deserialized.
    """
    from .comparators import run_spikeinterface,extract_sorting_events
    from spikeinterface.core import BinaryRecordingExtractor
    descriptor=parameters['recording']
    require(descriptor['time_axis']==0 and descriptor['file_offset']==0,
            'unsupported-original-binary-layout')
    for pin in descriptor['files']: artifacts.authenticate(pin)
    recording=BinaryRecordingExtractor(
        file_paths=[p['path'] for p in descriptor['files']],
        sampling_frequency=descriptor['sampling_frequency'],
        num_chan=descriptor['num_channels'],dtype=descriptor['dtype'],
        time_axis=0,file_offset=0)
    require(recording.get_num_segments()==len(descriptor['sample_counts']), 'raw-segment-count')
    require(all(recording.get_num_samples(segment_index=i)==n
                for i,n in enumerate(descriptor['sample_counts'])), 'raw-duration-mismatch')
    recording.set_channel_locations(descriptor['channel_positions'])
    require('output_folder' not in parameters,'worker-owns-sort-output')
    out=artifacts.output/'sort-output'
    sorting=run_spikeinterface(recording,parameters['row'],out)
    events=extract_sorting_events(sorting,len(descriptor['sample_counts']),descriptor['sample_counts'])
    return {'events':events,'files':artifacts.inventory_tree(out),'parent_capture_required':True}
