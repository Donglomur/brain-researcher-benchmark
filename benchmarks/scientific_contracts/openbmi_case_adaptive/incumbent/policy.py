"""Future operator selection; source construction grants no execution authority."""
import math
import re


def selection(value, source):
    fields = ('schema', 'task_id', 'source', 'canonical', 'canonical_root', 'preparation_review',
              'method_review', 'program', 'output', 'repository', 'other_future_bytes', 'limits',
              'docker_binary', 'docker_socket', 'image', 'memory_bytes', 'fit_seconds', 'infer_seconds', 'plan')
    c.need(type(value) is dict and set(value) == set(fields), 'Exact future selection')
    c.need(value['schema'] == 'neural083_full_panel_selection_v1' and value['task_id'] == 'NEURAL-083' and
           value['source'] == source, 'Exact selected source/task')
    for name in ('canonical', 'preparation_review', 'method_review', 'program'):
        row = value[name]
        c.need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'External reviewed operand')
        c.path(row['path'])
        c.only_pin(row)
    c.need(value['program']['bytes'] <= 1048576, 'Bounded single frozen Python source')
    for name in ('canonical_root', 'output', 'repository', 'docker_binary', 'docker_socket'):
        c.path(value[name])
    c.need(type(value['other_future_bytes']) is int and value['other_future_bytes'] >= 0, 'Current other reservations')
    c.need(type(value['image']) is str and re.fullmatch(r'sha256:[a-f0-9]{64}', value['image']), 'Exact selected immutable image')
    c.need(type(value['memory_bytes']) is int and 0 < value['memory_bytes'] <= 17179869184, 'Explicit producer memory')
    for name in ('fit_seconds', 'infer_seconds'):
        c.need(type(value[name]) in (int, float) and math.isfinite(value[name]) and value[name] > 0, 'Finite positive producer duration')
    limits = value['limits']
    c.need(type(limits) is dict and set(limits) == {'reads', 'writes', 'retained', 'free_floor_bytes',
           'whole_seconds', 'observer_seconds', 'observer_reads'}, 'Complete cumulative resource selection')
    for name, number in limits.items():
        c.need(type(number) is int and number > 0, 'Positive integer resource limit')
    c.need(limits['whole_seconds'] > limits['observer_seconds'] + 120, 'Startup and independent closure intervals')
    work = contracts.numerical_work()
    c.need(value['plan'] == work, 'Full scope resource arithmetic')
    c.need(limits['writes'] >= work['training_numeric_copy_bytes'] + work['query_numeric_copy_bytes'] +
           work['all_model_capture_max_bytes'] + work['native_receipt_cap_bytes'] +
           work['condition_metadata_cap_bytes'] + work['prediction_cap_bytes'] + work['phase_intent_cap_bytes'],
           'Complete source-capped construction, model capture and retained metadata allowances')
    c.need(limits['reads'] >= work['native_reply_reservation_bytes'] +
           3 * (work['training_numeric_copy_bytes'] + work['query_numeric_copy_bytes']) +
           2 * work['all_model_capture_max_bytes'], 'Full input/capture/readback lower components')
    c.need(limits['retained'] >= work['retained_upper_components_bytes'],
           'Full source-capped collection and one current view/model; never reduce scope')
    return value


def reviews(selection, source, binding, capture):
    prep = selection['preparation_review']
    p = c.parse(capture(prep['path'], 262144, c.only_pin(prep)))
    c.need(p.get('schema') == 'neural083_full_input_admission_v1' and p.get('task_id') == 'NEURAL-083' and
           p.get('canonical') == c.only_pin(selection['canonical']) and p.get('full108_original_provenance') is True and
           p.get('source_channel_clock_label_order_verified') is True and p.get('actual_values_and_support_verified') is True,
           'Separate authentic full-input admission required')
    review = selection['method_review']
    r = c.parse(capture(review['path'], 262144, c.only_pin(review)))
    c.need(r.get('schema') == 'neural083_program_method_admission_v1' and r.get('source') == source and
           r.get('program') == c.only_pin(selection['program']) and r.get('reference') == binding['reference'] and
           r.get('canonical') == c.only_pin(selection['canonical']), 'Exact independent method/source binding')
    configuration = {key: value for key, value in selection.items() if key != 'method_review'}
    c.need(r.get('execution_configuration') == c.pin(c.encoded(configuration)),
           'Method/resource admission bound to exact image, caps, clocks and execution operands')
    for field in ('execution_authorized', 'environment_and_resources_admitted', 'original_task_preserved',
                  'no_query_batch_adaptation_admitted', 'training_only_tuning_admitted', 'fixed_program_before_cases',
                  'fresh_conditions_and_model_state_admitted', 'reference_state_and_dependency_admitted'):
        c.need(r.get(field) is True, 'Independent method/exposure admission: ' + field)
    c.need(r.get('batch_inference_mechanically_guarantees_no_adaptation') is False,
           'Do not misrepresent the batch interface as a universal adaptation barrier')
    c.need(r.get('original_input_visibility') == 'globally_opaque_monolithic_matrices', 'No donor-session fragment exposure')
    return p, r
