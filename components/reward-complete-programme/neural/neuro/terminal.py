"""Numerical F interpretation programmes: prebank source custody and exact execution.

This is the numerical tier's arbitrary scientific-report programme interface,
not the separately bounded P claim-policy language. Actual protected execution
still requires the independently qualified isolation service described in v1.
"""
from pathlib import Path
from .base import require, finite, digest, sha256, loads, read_member

INPUT_SCHEMA = 'closed_aggregate_interpretation_evidence_v1'
OUTPUT_SCHEMA = 'neural_scientific_interpretation_v1'


def prebank_sources(plan):
    expected = {j for j, value in plan['programs'].items() if value is not None}
    definitions = plan.get('terminal_routines', {})
    require(set(definitions) == expected, 'F_terminal_routine_required_before_bank')
    collected = {}
    for job, descriptor in definitions.items():
        require(set(descriptor) == {'kind', 'source_path', 'source_sha256', 'input_schema',
                                   'output_schema', 'timeout_seconds', 'output_cap_bytes'},
                'terminal_routine_contract')
        require(descriptor['kind'] == 'python_program_v1' and descriptor['input_schema'] == INPUT_SCHEMA
                and descriptor['output_schema'] == OUTPUT_SCHEMA, 'terminal_routine_schema')
        require(0 < finite(descriptor['timeout_seconds']) <= 60, 'terminal_routine_time_cap')
        require(type(descriptor['output_cap_bytes']) is int and 0 < descriptor['output_cap_bytes'] <= 1048576,
                'terminal_routine_output_cap')
        source = Path(descriptor['source_path'])
        body = read_member(source.parent, source.name, 131072)
        require(sha256(body) == descriptor['source_sha256'], 'terminal_prebank_source_pin')
        collected[job] = (descriptor, body)
    return collected


def validate_result(value, packet):
    require(set(value) == {'schema', 'closed_result_digest', 'claims', 'limitations'}, 'terminal_output_keys')
    require(value['schema'] == OUTPUT_SCHEMA and packet['schema'] == INPUT_SCHEMA, 'terminal_schema')
    require(value['closed_result_digest'] == digest(packet), 'terminal_evidence_binding')
    for key in ('claims', 'limitations'):
        require(isinstance(value[key], list) and len(value[key]) <= 128 and
                all(isinstance(v, str) and 0 < len(v) <= 16384 for v in value[key]),
                'terminal_text_shape')
    require(value['claims'], 'terminal_claims_required')
    return value


def collect_result(folder, receipt, commitment, packet):
    require(receipt['engineering_only'] is True and receipt['program_sha256'] == commitment['source_sha256']
            and receipt['process_group_closed'] is True and receipt['returncode'] == 0 and
            not receipt['timeout'] and not receipt['descendants_detected'] and not receipt['program_changed'],
            'terminal_original_process_not_cleanly_committed')
    cap = commitment['output_cap_bytes']
    require(receipt['output_cap'] == cap, 'terminal_resource_contract_changed')
    require(receipt['input_sha256'] == sha256(read_member(folder, 'input.json', 1048576)),
            'terminal_original_input_binding')
    outputs = folder / 'outputs'; members = list(outputs.iterdir())
    require({p.name for p in members} == {'process.log', 'submission.json'} and
            all(p.is_file() and not p.is_symlink() for p in members), 'terminal_output_members')
    require(sum(p.stat().st_size for p in members) <= cap, 'terminal_output_bundle_cap')
    require(receipt['log_sha256'] == sha256(read_member(outputs, 'process.log', cap)), 'terminal_log_binding')
    value = loads(read_member(outputs, 'submission.json', cap), cap)
    return validate_result(value, packet)
