"""Full-source native outputs to separately named biological sensitivities."""
from core import identity, need
from diagnostics import person_evoked, subject_signflip_max_copes, harmonized_age, age_group


def run(admitted, age_records=None, expected_age_identity=None,
        nnmf_output_store=None, nnmf_read_limit=None):
    import numpy as np
    record = admitted['assembled']
    branch = record['branch']
    specs = {r['key']: r for r in record['ordered_fields']}
    def load(key):
        return np.asarray(admitted['load'](specs[key]))
    derived = None
    if branch in ('ctf_tde', 'elekta_tde'):
        from native.assemble import assemble_nnmf_derivations
        need(nnmf_output_store is not None and type(nnmf_read_limit) is int and nnmf_read_limit > 0,
             'Explicit bounded separate all-component derived-map output allocation')
        derived = assemble_nnmf_derivations(record, admitted['read_bytes'], nnmf_output_store,
                                            max_input_bytes=nnmf_read_limit)
    if branch.startswith('elekta_'):
        epochs = load('event.epochs')
        runs = record['context']['runs']
        rows = [{'person': r['person_id'], 'run': int(r['run_id']), 'evoked': epochs[i]}
                for i, r in enumerate(runs)]
        rows.sort(key=lambda x: (x['person'], x['run']))
        if not np.isfinite(epochs).all():
            return {'available': False, 'reason': 'undefined_complete_original_evoked_support'}
        result = subject_signflip_max_copes(person_evoked(rows))
        return {'available': True, 'name': 'nineteen_person_evoked_sensitivity',
                'original_run_inference_retained': True, 'result': result,
                'separate_all_component_maps': derived,
                'event_axis': record['native_axes']['event.t']}
    if branch == 'ctf_bursts':
        return {'available': True, 'required': False,
                'reason': 'no_additional_age_or_event_sensitivity_in_selected_burst_contract'}
    need(identity(age_records) == expected_age_identity and expected_age_identity,
         'Externally pinned complete original person/age metadata')
    endpoints = ({'summary': 'age_summary.values', 'power': 'age_power.values',
                  'coherence': 'age_coherence.values'} if branch == 'ctf_tde' else
                 {'summary': 'age_summary.values'} if branch == 'ctf_dynemo' else
                 {'power': 'static.power', 'aec': 'age_aec.values'})
    assignment_key = 'age_summary.assignments' if branch != 'ctf_static' else 'age_power.assignments'
    source_policy = 'native_static_numeric' if branch == 'ctf_static' else 'native_dynamic_numeric'
    by_person = {r['person']: r for r in age_records}
    runs = record['context']['runs']
    expected = np.array([age_group(by_person[r['person_id']]['age'], source_policy) for r in runs])
    need(np.array_equal(load(assignment_key), expected), 'Exact original age-to-run join and literal policy')
    order = [next(i for i, r in enumerate(runs) if r['person_id'] == a['person']) for a in age_records]
    reports = {name: harmonized_age(age_records, load(key)[order], branch + ':' + name)
               for name, key in endpoints.items()}
    return {'available': all(r['available'] for r in reports.values()),
            'name': 'all_sixty_five_person_harmonized_age_sensitivity',
            'age_identity': expected_age_identity, 'original_assignments_retained': True,
            'endpoints': reports, 'separate_all_component_maps': derived}
