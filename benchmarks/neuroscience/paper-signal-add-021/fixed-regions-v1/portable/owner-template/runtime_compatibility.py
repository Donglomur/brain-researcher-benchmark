"""One inert image check before authentic staging; accepted method stays fixed."""
import hashlib
import json
import os
from pathlib import Path
import time
from common import encode, need, pin, plain, read, write
from route_config import bounded_json, keys


def verify(body, selection):
    need(type(body) is bytes and 0 < len(body) <= 16384, 'compatibility_output_extent')
    value = bounded_json(body)
    keys(value, ('schema', 'runtime', 'primitive', 'method_fixture', 'authentic_payload_reads'),
         'complete_runtime_probe_output')
    need(value['schema'] == 'tms_whole_runtime_compatibility_v1' and
         type(value['authentic_payload_reads']) is int and value['authentic_payload_reads'] == 0,
         'inert_probe_kind')
    expected = selection['compatibility']
    need(value['runtime'] == {'implementation': expected['implementation'],
                             'version': expected['candidate_python']}, 'exact_image_runtime_version')
    primitive = value['primitive']
    keys(primitive, ('schema', 'runtime', 'conventions', 'conventions_sha256',
         'authentic_input_or_reference_reads', 'scope'), 'complete_primitive_probe')
    need(primitive['schema'] == 'tms_fixed_region_runtime_conventions_v1' and
         primitive['runtime'] == value['runtime'] and
         type(primitive['authentic_input_or_reference_reads']) is int and
         primitive['authentic_input_or_reference_reads'] == 0, 'same_inert_primitive_runtime')
    core = json.dumps(primitive['conventions'], sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')
    need(hashlib.sha256(core).hexdigest() == primitive['conventions_sha256'] ==
         expected['primitive_conventions_sha256'], 'complete_primitive_conventions_match')
    fixture = {'schema': 'tms_fixed_region_method_fixture_v1',
               'complete_artifact_bytes': expected['method_fixture_bytes'],
               'complete_artifact_sha256': expected['method_fixture_sha256'],
               'regions': 12, 'effects': 36, 'omissions': 540,
               'sign_patterns_each': 32768, 'bootstrap_draws_each': 2000,
               'complete_artifact_is_invented': True,
               'authentic_shape_or_scientific_parity_claim': False}
    need(encode(value['method_fixture']) == encode(fixture), 'complete_method_edge_fixture_match')
    return {'schema': 'tms_fixed_region_runtime_conventions_accepted_v1',
            'image': selection['image'], 'config': selection['config'],
            'probe_source': selection['probe_source'], 'observed_runtime': value['runtime'],
            'normative_runtime_version': expected['normative_python'],
            'version_difference_explicit': expected['normative_python'] != expected['candidate_python'],
            'primitive_conventions_sha256': expected['primitive_conventions_sha256'],
            'method_fixture_sha256': expected['method_fixture_sha256'],
            'method_fixture_bytes': expected['method_fixture_bytes'],
            'same_invented_primitives_and_complete_fixture': True,
            'declared_method_or_accepted_reference_changed': False,
            'authentic_scientific_or_native_FieldTrip_parity': False}


def execute(root, owner, program_body, budget, active_deadline, selection):
    need(time.monotonic() < active_deadline < budget.deadline, 'original_probe_window')
    need(owner.IMAGE == selection['image'] and pin(program_body) == selection['probe_source'],
         'source_and_image_bound_probe')
    # This proves only prior source-bound CLI setup; it creates no second one.
    owner.cli_argv([])
    root = plain(root); root.mkdir(mode=0o700)
    inputs = root / 'input'; inputs.mkdir(mode=0o500)
    task = root / 'task'; task.mkdir(mode=0o500)
    program = root / 'probe.py'; write(program, program_body, budget)
    closed = owner.run_candidate(root=root / 'run', input_dir=inputs, task_dir=task,
        program=program, budget=budget, active_deadline=active_deadline)
    # A proved failed probe is still an infrastructure incompatibility. It must
    # never become a candidate score or permit the authentic staging phase.
    owner.require_closed(closed)
    entry = closed.submission
    body = read(entry['path'], {k: entry[k] for k in ('bytes', 'sha256')},
                budget, cap=16384, mode=0o400)
    observation = verify(body, selection)
    observation.update({'closed_probe_output': entry, 'closed_probe_lifecycle': closed.lifecycle,
                        'empty_invented_input_mount': True, 'authentic_assets_staged': False})
    receipt = write(root / 'COMPATIBILITY.private.json', encode(observation), budget)
    return {'receipt': receipt, 'closed_probe': True, 'compatible': True}
