"""Render one permitted NEURAL-029 source trace; no target response access.

This is a source-only rendering component, not an interactive provider, response
collector or qualified native-interpretation condition. Uses admitted NumPy 2.2.6.
"""
import argparse
import hashlib
import html
import io
import json
import math
from pathlib import Path
import types
import zipfile


REFERENCE_BYTES = 8635
REFERENCE_SHA256 = '9c217eeddffac4ef3b57ee504bfd32972efad434255e55309c77ec17de64a67b'
REFERENCE_PATH = Path(__file__).resolve().parent.parent / 'public-warp-reference-v1/reference_program.py'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reference(path=REFERENCE_PATH):
    """Compile captured reviewed source rather than importing cached bytecode."""
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), 'ordinary reference source')
    raw = path.read_bytes()
    require(len(raw) == REFERENCE_BYTES and hashlib.sha256(raw).hexdigest() == REFERENCE_SHA256,
            'reviewed reference source changed')
    module = types.ModuleType('neural029_view_reference')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _trace(root, row, split, trial, cell, np, ref):
    pin = row['file']
    raw = ref.read_regular(Path(root) / pin['path'], pin['bytes'])
    require(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'],
            'authenticated selected source pair')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(len(entries) == 2 and {e.filename for e in entries}
                == {'calibration.npy', 'validation.npy'}
                and sum(e.file_size for e in entries) <= ref.ARRAY_CAP,
                'bounded source-only NPZ')
        for entry in entries:
            name = entry.filename[:-4]
            with archive.open(entry) as member:
                version = np.lib.format.read_magic(member)
                require(version in ((1, 0), (2, 0)), 'numeric NPY format')
                reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                          else np.lib.format.read_array_header_2_0)
                shape, _, dtype = reader(member)
                expected = (row[name + '_trials'], len(row['cell_ids']), 61)
                require(shape == expected and dtype == np.dtype('float64')
                        and entry.file_size == member.tell() + 8 * math.prod(expected),
                        'complete numeric NPY extent before allocation')
    selected = None
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        for name in ('calibration', 'validation'):
            array = archive[name]
            require(array.dtype == np.dtype('float64')
                    and array.shape == (row[name + '_trials'], len(row['cell_ids']), 61)
                    and np.isfinite(array).all(), 'finite complete selected-pair source arrays')
            if name == split:
                selected = array[trial, cell].copy()
    return selected


def render(root, pair_id, split, trial_index1, cell_index1, np, *, ref=None):
    """One typed page: exact public pair, split and one-based trial/cell indices.

    All manifest descriptors are admitted; only the selected pair's public NPZ is
    opened. Both source splits in that file are validated. This does not verify
    arrays belonging to unviewed pairs or authenticate biological cohort truth.
    """
    require(np.__version__ == '2.2.6', 'admitted NumPy 2.2.6')
    ref = reference() if ref is None else ref
    public = ref.manifest(root)
    require(type(pair_id) is str, 'public pair identity')
    matches = [row for row in public['pairs'] if row['pair_id'] == pair_id]
    require(len(matches) == 1, 'known public pair identity')
    row = matches[0]
    require(type(split) is str and split in ('calibration', 'validation'), 'public source split')
    require(type(trial_index1) is int and 1 <= trial_index1 <= row[split + '_trials'],
            'one-based source trial index')
    require(type(cell_index1) is int and 1 <= cell_index1 <= len(row['cell_ids']),
            'one-based registered cell index')
    values = _trace(root, row, split, trial_index1 - 1, cell_index1 - 1, np, ref)
    low, high = float(values.min()), float(values.max())
    # Normalize in scaled coordinates to avoid overflowing high-low for finite
    # extreme values. Equal traces receive a stable midpoint without an epsilon.
    magnitude = max(abs(low), abs(high))
    normalized = values / magnitude if magnitude else np.zeros(61, dtype=np.float64)
    minimum, maximum = float(normalized.min()), float(normalized.max())
    ordinate = ((normalized - minimum) / (maximum - minimum)
                if maximum != minimum else np.full(61, 0.5))
    require(np.isfinite(ordinate).all(), 'representable display coordinates')
    x0, y0, width, height = 100, 165, 960, 360
    points = ' '.join(f'{x0 + width * i / 60:.6f},{y0 + height * (1 - float(v)):.6f}'
                      for i, v in enumerate(ordinate))
    metadata = {
        'schema': 'neural029-source-view-v1', 'pair_id': pair_id,
        'cell_id': row['cell_ids'][cell_index1 - 1], 'cell_index1': cell_index1,
        'source_split': split, 'trial_index1': trial_index1,
        'source_trial_index1': trial_index1 + (row['calibration_trials'] if split == 'validation' else 0),
        'source_delay_seconds': 1, 'target_delay_seconds': 2,
        'reward_type': row['reward_type'], 'time_seconds': public['time_seconds'],
        'display_time_samples': 61, 'source_npz_sha256': row['file']['sha256'],
        'display_scaling': 'linear page range; constant trace at midpoint',
        'display_min': low, 'display_max': high,
        'amplitude_units': 'released processed calcium values; physical calibration unqualified',
        'target_values_read': False, 'full_packet_arrays_verified': False,
        'provider_delivery_qualified': False, 'scientific_execution_qualified': False,
    }
    esc = html.escape
    grid = ''.join(f'<line x1="{x0 + width * t / 3:.6f}" x2="{x0 + width * t / 3:.6f}" '
                   f'y1="{y0}" y2="{y0 + height}" stroke="#d8dee8"/>'
                   f'<text x="{x0 + width * t / 3:.6f}" y="{y0 + height + 25}" text-anchor="middle">{t:g}</text>'
                   for t in (0, 0.5, 1, 1.5, 2, 2.5, 3))
    source_line = x0 + width / 3
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="650" viewBox="0 0 1120 650">'
            f'<metadata>{esc(json.dumps(metadata, sort_keys=True, allow_nan=False))}</metadata>'
            '<rect width="1120" height="650" fill="white"/>'
            '<g font-family="sans-serif" font-size="14" fill="#172033">'
            '<text x="30" y="32" font-size="22">NEURAL-029 — public source calcium</text>'
            f'<text x="30" y="60">Source delay: 1 s | {esc(row["reward_type"])} | {split} trial '
            f'{trial_index1}/{row[split + "_trials"]} | source-order trial {metadata["source_trial_index1"]} '
            f'| cell {cell_index1}/{len(row["cell_ids"])}</text>'
            f'<text x="30" y="85">Pair: {pair_id}</text>'
            f'<text x="30" y="110">Cell: {row["cell_ids"][cell_index1 - 1]}</text>'
            '<text x="30" y="138">Target delay: 2 s; target responses are not displayed or read.</text>'
            f'{grid}<line x1="{source_line:.6f}" x2="{source_line:.6f}" y1="{y0}" y2="{y0 + height}" '
            'stroke="#8f4f00" stroke-dasharray="5 4"/>'
            f'<polyline id="source-trace" points="{points}" fill="none" stroke="#1765b4" stroke-width="2"/>'
            f'<text x="90" y="{y0 + 5}" text-anchor="end">max</text>'
            f'<text x="90" y="{y0 + height}" text-anchor="end">min</text>'
            f'<text x="100" y="568">Displayed amplitude range: min {low!r}; max {high!r}</text>'
            '<text x="580" y="585" text-anchor="middle">Seconds after movement end (61 samples; 0.05 s spacing)</text>'
            '<text x="30" y="615">Amplitude: released processed calcium values; page-scaled, physical units unqualified.</text>'
            '<text x="30" y="638">Dashed marker: planned source delay. Rendered page only; participant transport is not qualified.</text>'
            '</g></svg>\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--pair-id', required=True)
    parser.add_argument('--split', choices=('calibration', 'validation'), required=True)
    parser.add_argument('--trial-index1', type=int, required=True)
    parser.add_argument('--cell-index1', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    import numpy as np
    svg = render(args.input, args.pair_id, args.split, args.trial_index1, args.cell_index1, np)
    # Exclusive creation prevents accidental overwrite; no output exists until
    # all selected source values and the complete page have passed validation.
    with Path(args.output).open('x', encoding='utf-8') as stream:
        stream.write(svg)


if __name__ == '__main__':
    main()
