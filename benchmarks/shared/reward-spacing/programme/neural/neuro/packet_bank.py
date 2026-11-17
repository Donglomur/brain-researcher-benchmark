"""P-tier policy custody and control-admissible closed-evidence packet preparation."""
from .base import require, digest, loads, encode, write_json, read_json
from .contracts import cell, assert_endpoint_applicable
from .packet import validate_packet, validate_policy, evaluate


def commit_F_policy(path, raw, cell_id, task, bank_schema_id):
    c = cell(cell_id, task); require(c['tier'] == 'P' and c['mode'] == 'F', 'F_packet_cell')
    mock = {'bank_schema_id': bank_schema_id}
    policy = validate_policy(raw, c, task, mock)
    write_json(path, {'cell_id': cell_id, 'task': task, 'bank_schema_id': bank_schema_id,
                      'policy': policy, 'policy_digest': digest(policy)}, True)
    return digest(policy)


def evaluate_committed(path, packets, rubrics):
    committed = read_json(path)
    require(digest(committed['policy']) == committed['policy_digest'], 'policy_commitment_changed')
    require(len(packets) == len(rubrics) and packets, 'packet_bank_shape')
    require(len({p['packet_id'] for p in packets}) == len(packets), 'duplicate_packet')
    return [evaluate(encode(committed['policy']), p, committed['cell_id'], committed['task'], r)
            for p, r in zip(packets, rubrics)]


def packet_from_closed(result, cell_id, bank_schema_id, packet_id, metadata):
    """Operator-only preparation, outside policy execution; no fit or private target read."""
    c = cell(cell_id, result['task'])
    require(c['tier'] == 'P', 'packet_cell')
    assert_endpoint_applicable(cell_id, result['task'], result['endpoint'], 'packet_evidence')
    source_cell = cell(result['cell_id'], result['task'])
    require(source_cell['tier'] in ('X', 'XM') and source_cell['control'] == c['control'],
            'closed_evidence_wrong_control')
    fields = dict(metadata)
    fields.update(task_id=result['task'], control_id=c['control'])
    allowed = set(c[result['task']]['packet_fields'])
    # A no-response packet has no target-derived errors, even if its X prior was scored.
    if c['input_control_contract']['training_neural_state'] != 'none':
        if result['task'] == 'NEURAL-045':
            fields.update({'predictor.' + k: v for k, v in result['metrics']['animal_macro'].items()})
        else:
            for name, value in result['metrics']['models'].items():
                fields['models.' + name + '.mse'] = value['animal_macro_mse']
            for name, value in result['metrics']['contrasts'].items():
                fields['contrasts.' + name + '.point'] = value
    require(set(fields) <= allowed, 'packet_generation_backfill')
    packet = {'schema': 'closed_control_evidence_packet_v1', 'bank_schema_id': bank_schema_id,
              'packet_id': packet_id, 'task_id': result['task'], 'control_id': c['control'],
              'closed_receipt_digest': digest(result), 'fields': fields}
    validate_packet(packet, c, result['task'])
    return packet
