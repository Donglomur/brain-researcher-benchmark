"""Whole blocks, chronological purges, and distinct mouse-transfer claims."""
from .contracts import require, prediction_identity, unique

def prediction_folds(rows, track):
    unique([prediction_identity(r) for r in rows], 'prediction case')
    require(track in ('held_block', 'held_mouse'), 'unknown split track')
    if track == 'held_block':
        # Each session has its own ROI axes. All trials from a repeated target
        # block remain together. Neighbor blocks are embargoed from training.
        sessions = sorted({(r['mouse'], r['session'], r['layout']) for r in rows})
        for mouse, session, layout in sessions:
            subset = [i for i,r in enumerate(rows) if (r['mouse'],r['session'],r['layout']) == (mouse,session,layout)]
            blocks = sorted({rows[i]['block'] for i in subset}, key=lambda b:min(rows[i]['time'] for i in subset if rows[i]['block']==b))
            for j, block in enumerate(blocks):
                forbidden = set(blocks[max(0,j-1):j+2])
                test = [i for i in subset if rows[i]['block'] == block]
                train = [i for i in subset if rows[i]['block'] not in forbidden]
                yield {'id': f'block:{mouse}:{session}:{block}', 'train': train, 'test': test,
                       'claim': 'held_block_within_session', 'unit': mouse}
    else:
        for layout in sorted({r['layout'] for r in rows}):
            for mouse in sorted({r['mouse'] for r in rows if r['layout']==layout}):
                test = [i for i,r in enumerate(rows) if r['layout']==layout and r['mouse']==mouse]
                train = [i for i,r in enumerate(rows) if r['layout']==layout and r['mouse']!=mouse]
                yield {'id': f'mouse:{layout}:{mouse}', 'train':train, 'test':test,
                       'claim':'held_mouse_anatomical_alignment', 'unit':mouse}

def validate_fold(rows, fold):
    train, test = fold['train'], fold['test']
    require(train and test and not set(train)&set(test), 'empty/overlapping fold')
    require(len({tuple(map(str, rows[i]['features'])) for i in train+test}) == 1, 'neuron axes differ')
    classes = rows[test[0]]['classes']
    require(all(rows[i]['classes'] == classes for i in train+test), 'class layout mismatch')
    require(set(rows[i]['y'] for i in train) == set(classes), 'training lacks one or more directions')
    if fold['claim'].startswith('held_mouse'):
        require(not {rows[i]['mouse'] for i in train}&{rows[i]['mouse'] for i in test}, 'mouse leakage')
    else:
        require(not {(rows[i]['session'],rows[i]['block']) for i in train}&
                    {(rows[i]['session'],rows[i]['block']) for i in test}, 'block leakage')
    return classes
