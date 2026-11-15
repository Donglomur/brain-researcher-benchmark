"""Fixed TMS owner selection; no scientific data or reference payload access."""
import hashlib
import json
import re


def require(value, reason):
    if not value:
        raise ValueError(reason)


def bounded_json(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 65536, 'manifest_extent')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_manifest_key')
            result[key] = value
        return result
    def bad(_):
        raise ValueError('nonfinite_manifest_number')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)


def keys(value, expected, reason):
    require(type(value) is dict and set(value) == set(expected), reason)


def locator(value):
    keys(value, ('path', 'bytes', 'sha256'), 'closed_locator')
    require(type(value['path']) is str and value['path'].startswith('/') and
            '..' not in value['path'].split('/'), 'absolute_locator')
    require(type(value['bytes']) is int and 0 <= value['bytes'] <= 1048576,
            'small_metadata_or_program_locator')
    require(type(value['sha256']) is str and
            re.fullmatch('[0-9a-f]{64}', value['sha256']), 'sha256_locator')
    return {name: value[name] for name in ('bytes', 'sha256')}


def admit_manifest(raw, sha, attempt):
    require(type(sha) is str and hashlib.sha256(raw).hexdigest() == sha,
            'exact_selected_manifest_body')
    require(type(attempt) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,63}', attempt),
            'fresh_attempt_identifier')
    wrapper = bounded_json(raw)
    keys(wrapper, ('schema', 'attempt_id', 'selection'), 'closed_run_wrapper')
    require(wrapper['schema'] == 'tms_behavior_whole_run_v1' and
            wrapper['attempt_id'] == attempt, 'exact_run_wrapper')
    selection = wrapper['selection']
    keys(selection, ('root_execution_selected', 'delivery_selection',
         'reference_selection', 'runtime_evidence', 'study_budget'), 'closed_whole_selection')
    require(selection['root_execution_selected'] is True, 'unselected_template')
    keys(selection['runtime_evidence'], ('image_receipt', 'image_independent_review',
         'source_independent_review'), 'closed_runtime_evidence')
    for entry in selection['runtime_evidence'].values():
        locator(entry)
    return wrapper


def prepare(wrapper, modules, bodies, budget):
    """Read exact selected small evidence, never paper/data/gold or programs.

    The root-selected immutable manifest is authority. Review descriptors are
    authenticated evidence, not authority inferred from a JSON boolean.
    """
    common = modules['common']; owner = modules['docker_owner']; delivery = modules['delivery']
    cfg = bounded_json(bodies['CONFIG.json']); selection = wrapper['selection']
    require(cfg['schema'] == 'tms_behavior_whole_config_v1', 'fixed_config_schema')
    require(common.encode(cfg['study_budget']) == common.encode(selection['study_budget']),
            'fixed_construction_study_budget')
    require(type(selection['study_budget']['model_calls']) is int and
            selection['study_budget']['model_calls'] == 0, 'no_model_campaign')
    require(owner.IMAGE == cfg['image'] and owner.DAEMON_GUARD == cfg['daemon_guard'] and
            str(owner.DAEMON_SOCKET) == cfg['daemon_socket'], 'source_bound_exact_runtime')
    compatibility = cfg['runtime_compatibility']
    require(re.fullmatch('[0-9a-f]{64}', compatibility['method_fixture_sha256']) is not None,
            'complete_normative_fixture_binding')
    evidence = selection['runtime_evidence']
    require(all(common.encode(evidence[k]) == common.encode(value)
                for k, value in cfg['image_evidence'].items()),
            'accepted_image_evidence_identity')
    source_review = locator(evidence['source_independent_review'])
    image_review = locator(evidence['image_independent_review'])
    expected = {
        'schema': 'tms_behavior_delivery_selection_v1', 'task_id': cfg['task_id'],
        'root_execution_selected': True, 'input_files': cfg['input_files'],
        'paper': cfg['paper'], 'official_code': cfg['official_code'],
        'official_code_review': locator(cfg['official_code_review']),
        'behavior_review': locator(cfg['behavior_review']),
        'selected_budget': cfg['study_budget'],
        'runtime_admission': {'image': cfg['image'], 'image_content_review': image_review,
                              'daemon_guard_review': source_review},
    }
    selected = selection['delivery_selection']
    require(type(selected) is dict and set(selected) == set(expected) | {'programs'},
            'complete_fixed_delivery_selection')
    require(all(common.encode(selected[k]) == common.encode(value) for k, value in expected.items()),
            'unchanged_complete_assets_and_conditions')
    require(common.encode(selection['reference_selection']) == common.encode(cfg['reference_selection']),
            'exact_accepted_protected_reference_locator')
    documents = {name: bodies[name] for name in delivery.DOCS}
    delivery.validate_selection(selected, documents)
    # Accepted source/rights provenance is small metadata; full result rows and
    # the protected reference are not part of this read population.
    descriptors = [*evidence.values(), cfg['official_code_review'], cfg['behavior_review'],
                   cfg['behavior_author_summary'], cfg['reference_acceptance']]
    seen = set(); observations = []
    for entry in descriptors:
        key = (entry['path'], entry['bytes'], entry['sha256'])
        if key in seen:
            continue
        seen.add(key); expected_pin = locator(entry)
        raw = common.read(entry['path'], expected_pin, budget, cap=1048576)
        if entry == evidence['image_receipt']:
            image = bounded_json(raw)
            require(image['schema'] == 'tms_p21_official_image_preparation_v1' and
                    image['image'] == cfg['image'] and image['probe_closed'] is True and
                    image['upstream_digest_verified_by_engine'] is True and
                    image['public_recipe_identity_bound'] is True,
                    'accepted_image_preparation_semantics')
        observations.append(entry)
    return {'delivery_selection': selected, 'reference_selection': selection['reference_selection'],
            'documents': documents, 'program_body': bodies['runtime_conventions_probe.py'],
            'runtime_selection': {'image': cfg['image'], 'compatibility': compatibility,
                 'probe_source': common.pin(bodies['runtime_conventions_probe.py']),
                 'config': common.pin(bodies['CONFIG.json'])},
            'source_runtime_metadata': {'authenticated_evidence': observations,
                 'config': common.pin(bodies['CONFIG.json']),
                 'large_asset_reads': 0, 'reference_payload_reads': 0},
            'selected_budget': cfg['budgets']}
