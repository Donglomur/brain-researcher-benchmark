"""Complete invented NEURAL-038 fixtures; never import or inspect authentic data.

The closed-form arithmetic and array construction are adapted from accepted
31c05 numerical-investigation-v1/test_generated.py (SHA-256
48a15968ae9796a8975ceabb4a46ef326f4d2bfaae4f992d0df95bbddabe06c1).
Only its fixture helpers are reused; this module does not run that test suite.
"""
import io
from pathlib import Path

import numpy as np

WRITE_LIMIT = 48 * 2**20
COUNTS = {'requested_logical_bytes': 0, 'completed_logical_bytes': 0,
          'write_calls': 0, 'completed_write_calls': 0, 'failed_write_calls': 0}


def snapshot():
    return dict(COUNTS)


def publication(raw, function):
    """Account the whole requested write before calling the actual writer.

    Successful returns count complete logical bytes. A failed writer could have
    written a prefix; requested bytes remain charged, never refunded. This is
    not kernel, directory-metadata, allocation, or physical-I/O measurement.
    """
    if type(raw) is not bytes or COUNTS['requested_logical_bytes'] + len(raw) > WRITE_LIMIT:
        raise ValueError('Generated fixture cumulative write reservation')
    COUNTS['requested_logical_bytes'] += len(raw)
    COUNTS['write_calls'] += 1
    try:
        result = function()
    except BaseException:
        COUNTS['failed_write_calls'] += 1
        raise
    COUNTS['completed_logical_bytes'] += len(raw)
    COUNTS['completed_write_calls'] += 1
    return result


def write(path, raw):
    path = Path(path)
    return publication(raw, lambda: path.write_bytes(raw))


def components(index, row, fields):
    # Independent closed-form oracle, not analysis_core's trace arithmetic.
    matched = (7 if index == 3 else 3 * (index + 1)) + row
    unmatched = (4 if index == 3 else index + 1) + row / 2
    opto = (3 if index == 3 else 2) + row / 4
    return dict(zip(fields, (matched, unmatched, opto, matched - unmatched,
                             matched - opto, unmatched - opto)))


def fixture(root, modules):
    """Write 18 full-shape invented arrays and return panel, inputs, report.

    `modules` contains the source-pinned accepted analysis_core, scorer_core,
    delivery_io and evaluate modules. The caller owns JSON publication. Every
    membership, frame and condition is retained; no authentic file is consulted.
    """
    root = Path(root)
    (root / 'arrays').mkdir()
    algebra, scorer, transport = (modules[n] for n in ('analysis_core', 'scorer_core', 'delivery_io'))
    blocks, inputs, report_blocks = [], [], []
    for index, (name, count) in enumerate(zip(algebra.BLOCKS, (9, 13, 10, 108))):
        revision = index == 3
        frames = 200 if revision else 300
        start, end = (123, 126) if revision else (125, 128)
        keys = [('revision_row_' if revision else 'source_row_') + str(row) for row in range(count)]
        conditions = algebra.REVISION if revision else algebra.ORIGINAL
        arrays = {condition: np.full((count, frames), 9000., dtype=np.float64) for condition in conditions}
        rows = []
        for row, key in enumerate(keys):
            values = components(index, row, algebra.FIELDS)
            matched, unmatched, opto = [values[field] for field in algebra.FIELDS[:3]]
            selected = ({'matched': matched + np.array([-1., 0., 1.]),
                         'unmatched': unmatched + np.array([-2., 0., 2.]),
                         'opto': opto + np.array([-3., 0., 3.])} if revision else
                        {'visF1': 100. + row, 'visF2': 20. - row,
                         'vis1OptoF1': 100. + row + matched + np.array([-1., 0., 1.]),
                         'vis2OptoF1': 20. - row + unmatched + np.array([-2., 0., 2.]),
                         'optoF1': opto + np.array([-3., 0., 3.])})
            for condition, value in selected.items():
                arrays[condition][row, start:end] = value
            rows.append({'cell_key': key, 'availability': 'observed', **values})
        descriptors = {}
        for condition, array in arrays.items():
            stream = io.BytesIO()
            np.save(stream, array, allow_pickle=False)
            raw = stream.getvalue()
            relative = 'arrays/' + name + '_' + condition + '.npy'
            write(root / relative, raw)
            descriptors[condition] = {'path': relative, **transport.pin(raw)}
        kind = 'revision' if revision else 'original'
        blocks.append({'block_id': name, 'kind': kind, 'cells': [
            {'cell_key': key, 'availability': 'observed'} for key in keys]})
        members = (['panelGI_new_' + key for key in algebra.REVISION] if revision else
                   ['panelGI_expt%d_' % (index + 1) + key for key in (*algebra.ORIGINAL, 'stim')])
        inputs.append({'block_id': name, 'kind': kind, 'cell_keys': keys,
                       'shape': [count, frames], 'window': [start, end], 'arrays': descriptors,
                       'source_members': members,
                       'source_full_condition_shape': [108 if revision else (467, 428, 340)[index], frames],
                       'animal_identity': None,
                       **({'revision_independence_established': False} if revision else {})})
        report_blocks.append({'block_id': name, 'cells': rows, 'valid_cells': count,
                              'means': components(index, (count - 1) / 2, algebra.FIELDS)})
    panel = {'schema': 'neural038-panel-v1', 'generation': 'e' * 64, 'blocks': blocks}
    panel['packet_id'] = scorer.fingerprint(panel)
    inputs = {'schema': 'neural038-input-v1', 'packet_id': panel['packet_id'], 'blocks': inputs}
    report = {'schema': 'neural038-investigation-v1', 'packet_id': panel['packet_id'],
              'blocks': report_blocks, 'original_macro_interaction': (4 + 7 + 8.25) / 3,
              'revision_mean_interaction': 29.75}
    return panel, inputs, report
