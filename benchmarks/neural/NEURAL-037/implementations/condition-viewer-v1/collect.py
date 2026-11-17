"""Collect twelve externally captured session artifacts; never load targets."""
import argparse
from pathlib import Path
import numpy as np
import source
from viewer import ROW_BYTES, ROW_OUTPUT_TOKEN_RESERVATION, SESSION_BYTES, PANEL_BYTES

FIELDS = ('schema', 'packet_id', 'context_id', 'source_binding', 'instructions_pin', 'input_pin',
    'outcome', 'actions', 'observations', 'response_bytes', 'observation_bytes',
    'external_output_token_reservation', 'provider_tokens_measured',
    'external_model_state_reset_verified', 'runtime_qualified', 'scientific_qualified')


def collect(records, bundle=None):
    b = source.load() if bundle is None else bundle
    io = b.io
    io.need(type(records) is list and len(records) == 12, 'All twelve externally captured results')
    received = {}
    for row in records:
        io.exact(row, ['context_id', 'path', 'bytes', 'sha256'])
        name = row['context_id']
        io.need(name in b.lock['contexts'] and name not in received, 'Exact unique original context')
        expected = {k: row[k] for k in ('bytes', 'sha256')}
        value = io.decode(io.read(Path(row['path']), SESSION_BYTES, expected))
        io.exact(value, FIELDS)
        index, selected = source.selected_rows(b, name)
        descriptor = next(x for x in selected if x['target'] == 'view/input.json')
        io.need(value['schema'] == 'neural037-condition-viewer-session-v1' and
                value['packet_id'] == b.panel['packet_id'] and value['context_id'] == name and
                value['source_binding'] == b.source_binding and value['instructions_pin'] == b.instructions_pin and
                value['input_pin'] == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'Captured source/case/input lineage')
        query = b.panel['contexts'][index]; n = len(query['cell_keys'])
        training_rows = sum(len(x['cell_keys']) for x in b.panel['contexts']) - n
        for field, ceiling in [('actions', 2 * training_rows + n + 2), ('observations', 2 * training_rows),
                               ('response_bytes', n * ROW_BYTES), ('observation_bytes', 2 * training_rows * 2_000_000)]:
            io.need(type(value[field]) is int and 0 <= value[field] <= ceiling, 'Declared session budget')
        io.need(value['actions'] >= value['observations'] and
                value['external_output_token_reservation'] == n * ROW_OUTPUT_TOKEN_RESERVATION,
                'Session counts and separate output-token reservation')
        for field in ('provider_tokens_measured', 'external_model_state_reset_verified', 'runtime_qualified', 'scientific_qualified'):
            io.need(value[field] is False, 'Transport cannot promote external or scientific qualification')
        io.need(type(value['outcome']) is dict and value['outcome'].get('context_id') == name, 'Same captured answer context')
        if value['outcome'].get('status') == 'complete':
            io.need(value['actions'] >= value['observations'] + n + 1,
                    'Complete rows and finish must be explicit actions')
        received[name] = value['outcome']
    result = {'schema': 'neural037-predictions-v1', 'packet_id': b.panel['packet_id'],
              'outcomes': [received[name] for name in b.lock['contexts']]}
    # Exact current public-only admission preserves original rows, frames,
    # finite numbers and complete abstentions. No private callback exists here.
    b.core.admit(b.panel, result, np)
    io.need(len(io.canonical(result)) <= PANEL_BYTES, 'Unchanged64MB canonical panel cap')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    b = source.load()
    records = b.io.json_file(args.captures, 65536)
    result = collect(records, b)
    print(b.io.canonical({'submission': b.io.put(args.output, result, PANEL_BYTES),
        'scored': False, 'native_study_admission': 'unavailable'}).decode('ascii'), end='')


if __name__ == '__main__':
    main()
