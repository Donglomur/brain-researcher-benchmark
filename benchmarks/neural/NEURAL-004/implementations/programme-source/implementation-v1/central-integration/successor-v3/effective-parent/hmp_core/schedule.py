"""Complete source identities, without scientific inputs or work execution."""
PEOPLE = tuple(str(i) for i in range(26))
COUNTS = (4, 5, 6)
STAGES = tuple('interval_' + str(i) for i in range(6)) + ('encoding_1_2', 'decision_3_4')


def schedule():
    for held in PEOPLE:
        yield {'kind': 'pca', 'id': f'pca/{held}', 'held': held}
        for k in COUNTS:
            yield {'kind': 'hmp_fit', 'id': f'fit/{held}/{k}', 'held': held, 'events': k}
            for support in ('train', 'held'):
                for gain in ('ordinary', 'zero'):
                    yield {'kind': 'evaluation', 'id': f'eval/{held}/{k}/{support}/{gain}',
                           'held': held, 'events': k, 'support': support, 'gain': gain}


def curve_nodes(held):
    for stage in STAGES:
        for condition in ('speed', 'accuracy'):
            for model in ('linear', 'pieron', 'fechner'):
                for person in PEOPLE:
                    if person != held:
                        yield {'id': f'curve/{held}/{stage}/{condition}/{model}/{person}',
                               'held': held, 'stage': stage, 'condition': condition,
                               'model': model, 'person': person}


def need(test, message):
    if not test:
        raise ValueError(message)
