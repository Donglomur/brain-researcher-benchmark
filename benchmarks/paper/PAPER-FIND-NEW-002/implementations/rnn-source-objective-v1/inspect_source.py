"""Inspect the exact released RNN source members without importing/executing them."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

PINS = {
    'sequenceFiltering/code/RNN_seqmodel.ipynb': {
        'bytes': 249260,
        'sha256': '31b0c0068f3835e3c10db3f839b0bcbc5b67183baf56521bff1132ceda2f276e',
    },
    'sequenceFiltering/src/modules_simpleRNN.py': {
        'bytes': 13354,
        'sha256': '1db27d131c6be6e41ad6f032df5612f653c97b5a187bf2b658cbc3e9f4d80a63',
    },
}


def inspect(archive):
    """Read only two source members; never read figure NPZ payloads or run code."""
    result = {'source_members': {}, 'code_cells': [], 'source_execution': False}
    with zipfile.ZipFile(archive) as source:
        for member, pin in PINS.items():
            matches = [entry for entry in source.infolist() if entry.filename == member]
            if len(matches) != 1 or matches[0].file_size != pin['bytes']:
                raise ValueError(f'missing, duplicate or wrong-size source member: {member}')
            raw = source.read(matches[0])  # ZIP CRC is checked by the standard library.
            digest = hashlib.sha256(raw).hexdigest()
            if digest != pin['sha256']:
                raise ValueError(f'source SHA-256 mismatch: {member}')
            result['source_members'][member] = {**pin, 'crc32': f'{matches[0].CRC:08x}'}
            if member.endswith('.ipynb'):
                notebook = json.loads(raw)
                for index, cell in enumerate(notebook['cells']):
                    if cell['cell_type'] == 'code':
                        # Do not copy embedded figures or saved training outputs.
                        result['code_cells'].append({'index_zero_based': index, 'source': ''.join(cell['source'])})
            else:
                code = raw.decode('utf-8')
                tree = ast.parse(code)
                loss = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'loss_mse')
                result['loss_function'] = {
                    'first_line_one_based': loss.lineno,
                    'last_line_one_based': loss.end_lineno,
                    'source': ast.get_source_segment(code, loss),
                }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.archive), indent=2))


if __name__ == '__main__':
    main()
