"""Metadata-only boundary for the unchanged selected twelve NEURAL037 contexts.

No NumPy, array decoding, targets, preparation, prediction or scoring imports.
"""
import math
import io_guard as io

SHAPES = ((251,240),(203,240),(139,240),(114,240),(257,200),(168,200))
CONDITIONS = tuple((f'acquisition_{i}', order) for i in range(1,7) for order in ('ABC','CBA'))
CONTEXTS = tuple(a+'_'+o for a,o in CONDITIONS)
SCOPE = 'complete-condition holdout, native source frames, no animal-transfer claim'


def exact(value, keys, reason):
    io.need(type(value) is dict and set(value) == set(keys), reason)


def validate(raw, fold, rows, packet_id):
    io.need(type(fold) is int and 0 <= fold < 12, 'fixed context selector')
    value = io.parse(raw.decode('utf-8', errors='strict'))
    exact(value, ('schema','packet_id','query','training','training_scale','scope'), 'context fields only')
    io.need(value['schema'] == 'neural037-context-v1' and value['packet_id'] == packet_id,
            'selected packet identity')
    io.need(value['scope'] == SCOPE, 'selected within-source scope')
    query = value['query']; acquisition, order = CONDITIONS[fold]
    cells, frames = SHAPES[fold//2]
    exact(query, ('context_id','acquisition','query_order','cell_keys','frames'), 'target-free query fields')
    io.need(query['context_id'] == CONTEXTS[fold] and query['acquisition'] == acquisition and
            query['query_order'] == order and type(query['frames']) is int and query['frames'] == frames,
            'exact selected query condition and frames')
    io.need(query['cell_keys'] == [f'cell_{i:04d}' for i in range(cells)], 'complete ordered source ROI support')
    scale = value['training_scale']
    io.need(type(scale) in (int,float) and math.isfinite(scale) and scale > 0, 'positive finite inherited training scale')
    training = value['training']
    io.need(type(training) is list and len(training) == 11, 'all eleven authorized training conditions')
    wanted = [c for c in CONDITIONS if c != (acquisition,order)]
    by_target = {r['target']:r for r in rows}
    io.need(len(by_target) == len(rows), 'unique context file targets')
    for index,(row,(acq,condition)) in enumerate(zip(training,wanted)):
        exact(row, ('acquisition','order','shape','means','counts'), 'training fields only')
        shape = list(SHAPES[int(acq[-1])-1])
        io.need(row['acquisition'] == acq and row['order'] == condition and row['shape'] == shape and
                all(type(x) is int for x in row['shape']), 'complete fixed training order and native geometry')
        for kind in ('means','counts'):
            item = row[kind]
            exact(item, ('path','bytes','sha256'), 'training array descriptor fields')
            path = f'arrays/train_{index:02d}_{kind}.npy'
            io.need(item['path'] == path and 'view/'+path in by_target, 'only exact selected array paths')
            expected = by_target['view/'+path]
            io.need(type(item['bytes']) is int and item['bytes'] == expected['bytes'] and
                    item['sha256'] == expected['sha256'], 'array descriptors match frozen source pins')
    return value
