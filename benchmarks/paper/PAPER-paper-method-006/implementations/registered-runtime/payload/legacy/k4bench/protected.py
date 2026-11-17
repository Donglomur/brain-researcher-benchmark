"""Protected scoring accepts selected receipts, never caller-supplied cases."""
import importlib.util
import sys
from .protocol import require, validate_pin, digest, write_new
from .identity import manifest_digest, plan_digest, job_digest, bind_profile
from .outputs import decode_selected_output, join_protected_case
from .grading import compare_I_banks
from .pipeline import validate_execution_binding


def invoke_bank(bank_id, source_path, request):
    require(bank_id in {'R1', 'R2'}, 'unknown-bank', bank_id)
    spec = importlib.util.spec_from_file_location('protected_k4_' + bank_id, source_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.dispatch(request)


def prepare_scoring(store, authority, manifest, job):
    """Authenticate and construct the entire bank request before any dispatch."""
    authority.permit(manifest, job)
    binding = authority.admission['grading_bindings'][job['id']]
    require(binding['schema'] == 'kilosort4_protected_scoring_binding_v2'
            and binding['job_digest'] == job_digest(job)
            and binding['manifest_digest'] == manifest_digest(manifest), 'grading-binding-identity', job['id'])
    selected = next((x for x in manifest['cases'] if x['id'] == job['query_id']), None)
    require(selected is not None, 'unknown-selected-query', job['id'])
    case = store.json(validate_pin(binding['case_metadata_pin']), 4 * 1024 * 1024)
    require(case == selected and case['id'] == binding['case_id'], 'selected-case-mismatch', job['query_id'])
    require(binding['truth_pin'] == case['truth_payload_pin'], 'selected-truth-pin-mismatch', case['id'])
    truth = store.json(validate_pin(binding['truth_pin']), job['protected_metadata_max_bytes'])
    barrier = store.json(validate_pin(binding['barrier_pin']), 4 * 1024 * 1024)
    require(barrier['status'] == 'barrier-satisfied' and barrier['manifest_digest'] == manifest_digest(manifest),
            'protected-barrier-missing', job['id'])
    require(set(barrier['program_seals']) >= {'A-I', 'B-I'}
            and barrier['submission_receipts_digest'] == digest(barrier['submission_receipts']),
            'incomplete-paired-barrier', job['id'])
    expected = {(cell, query) for cell in ('A-I', 'B-I') for query in manifest['I_query_ids']}
    rows = {(x['cell'], x['query_id']): x for x in barrier['submission_receipts']}
    require(set(rows) == expected and len(rows) == len(barrier['submission_receipts']),
            'incomplete-barrier-query-support', job['id'])
    for (cell, query), submitted in rows.items():
        attempted = store.json(validate_pin(submitted['attempt_receipt_pin']), 4 * 1024 * 1024)
        execution_job = next((x for x in manifest['jobs'] if x['id'] == attempted['job_id']), None)
        require(execution_job is not None and execution_job.get('audience') == 'candidate'
                and execution_job['cell'] == cell and execution_job['query_id'] == query
                and attempted['job_digest'] == job_digest(execution_job)
                and attempted['manifest_digest'] == manifest_digest(manifest)
                and attempted['status'] == 'native-exited' and attempted['failure'] is None,
                'barrier-native-query-binding', query)
        require(submitted['seal_digest'] == digest(barrier['program_seals'][cell])
                and attempted['effective_mounts']['request']['candidate_seal_digest'] == submitted['seal_digest']
                and attempted['effective_mounts']['request']['case_id'] == query,
                'barrier-native-seal-binding', query)
        submitted_meta = store.json(validate_pin(submitted['output_metadata_pin']), 1024 * 1024)
        require(submitted_meta['case_id'] == query
                and submitted_meta['candidate_seal_digest'] == submitted['seal_digest']
                and submitted_meta['native_job_digest'] == attempted['job_digest']
                and submitted_meta['event_output_pin'] == submitted['output_pin'],
                'barrier-output-binding', query)
    row = rows[(job['cell'], job['query_id'])]
    seal = store.json(validate_pin(binding['candidate_seal_pin']), 1024 * 1024)
    require(seal == barrier['program_seals'][job['cell']] and seal['state'] == 'sealed'
            and seal['cell'] == job['cell'] and row['seal_digest'] == digest(seal),
            'grading-program-seal-mismatch', job['id'])
    require(row['output_pin'] == binding['event_output_pin']
            and row['output_metadata_pin'] == binding['output_metadata_pin']
            and row['attempt_receipt_pin'] == binding['native_receipt_pin'],
            'grading-output-barrier-mismatch', job['id'])
    native = store.json(validate_pin(binding['native_receipt_pin']), 4 * 1024 * 1024)
    executed_job = next((x for x in manifest['jobs'] if x['id'] == binding['execution_job_id']), None)
    require(executed_job is not None and executed_job['query_id'] == job['query_id']
            and executed_job['cell'] == job['cell'] and executed_job['audience'] == 'candidate',
            'grading-execution-job-mismatch', job['id'])
    descriptor = manifest['producer_profiles'][executed_job['producer_id']]
    profile = store.json(validate_pin(descriptor['profile_pin']), 4 * 1024 * 1024)
    pd = bind_profile(manifest, executed_job, profile)
    require(native['job_id'] == executed_job['id'] and native['job_digest'] == job_digest(executed_job)
            and native['manifest_digest'] == manifest_digest(manifest) and native['plan_digest'] == plan_digest(manifest)
            and native['profile_digest'] == pd and native['producer_profile_pin'] == descriptor['profile_pin']
            and native['producer_descriptor_digest'] == digest(descriptor),
            'grading-native-producer-mismatch', job['id'])
    require(native['status'] == 'native-exited' and native['failure'] is None
            and native['termination']['custody_complete'] and not native['termination']['residual_processes'],
            'grading-native-failure', job['id'])
    require(native['effective_mounts']['candidate_seal_pin'] == binding['candidate_seal_pin']
            and native['effective_mounts']['request']['candidate_seal_digest'] == digest(seal)
            and native['effective_mounts']['request']['case_id'] == case['id'],
            'grading-native-request-or-program-mismatch', job['id'])
    validated = store.json(validate_pin(binding['validated_job_receipt_pin']), 4 * 1024 * 1024)
    reconstructed_validation = validate_execution_binding(
        store, manifest, executed_job, authority.admission['validated_job_bindings'][executed_job['id']])
    require(validated == reconstructed_validation, 'grading-native-validation-tuple-mismatch', job['id'])
    require(validated['status'] == 'native-output-validated'
            and validated['job_digest'] == native['job_digest']
            and validated['manifest_digest'] == native['manifest_digest']
            and validated['native_receipt_pin'] == binding['native_receipt_pin']
            and validated['producer_profile_digest'] == pd, 'grading-unvalidated-native-output', job['id'])
    output_validation = store.json(validate_pin(validated['output_receipt_pin']), 4 * 1024 * 1024)
    require(output_validation['native_receipt_pin'] == binding['native_receipt_pin']
            and binding['event_output_pin'] in output_validation['output_pins']
            and binding['output_metadata_pin'] in output_validation['output_pins'],
            'grading-output-not-validated', job['id'])
    decoded = decode_selected_output(store, binding, case, seal, native, job['output_limits'])
    request_case = join_protected_case(case, truth, decoded)
    profiles = {}
    require(set(binding['bank_profile_pins']) == {'R1', 'R2'}, 'missing-independent-bank', job['id'])
    for bank in ('R1', 'R2'):
        pin = binding['bank_profile_pins'][bank]
        require(pin == manifest['bank_profiles'][bank], 'unselected-bank-profile', bank)
        bp = store.json(validate_pin(pin), 1024 * 1024)
        require(bp['bank_id'] == bank and bp['entrypoint_pin'] in bp['source_pins'], 'unbound-bank-entry', bank)
        for source_pin in bp['source_pins']:
            store.read(validate_pin(source_pin))
        profiles[bank] = bp
    require(profiles['R1']['independent_author'] != profiles['R2']['independent_author'],
            'bank-authorship-not-independent', job['id'])
    request = {'operation': 'score_I', 'case': request_case, 'limits': job['bank_limits']}
    return request, profiles, {'schema': 'kilosort4_scoring_operands_v2', 'binding_digest': digest(binding),
                              'manifest_digest': manifest_digest(manifest), 'job_digest': job_digest(job),
                              'request_digest': digest(request), 'complete_selected_bindings': binding,
                              'decoded_output_binding': decoded['binding']}


def grade_I(store, authority, manifest, job, result_directory, meter):
    request, profiles, operands = prepare_scoring(store, authority, manifest, job)
    responses = {}
    for bank in ('R1', 'R2'):
        source = store.root / profiles[bank]['entrypoint_pin']['path']
        response = invoke_bank(bank, source, request)
        responses[bank] = response
        write_new(result_directory / f'{bank}.json', response, meter)
    compared = compare_I_banks(request['case'], responses['R1'], responses['R2'])
    receipt = {**compared, 'authenticated_operands': operands, 'scientific_qualification': False}
    write_new(result_directory / 'COMPARISON.json', receipt, meter)
    return receipt
