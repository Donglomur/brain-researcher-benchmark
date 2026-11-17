"""Complete metadata-only NEURAL-079 work, not proof of authentic admission."""
from n079_common import require, fields, integer, checked_pin, descriptor, join_unique

PERSONS = tuple('sub-%02d' % i for i in range(1, 7))
TRAIN = tuple(range(1, 1001))
QUERY = tuple(range(1001, 1103))
Q = 127 * 1800
DIMS = (1404928, 1404928, 4214784, 1053696, 1404928, 2634240, 376320,
        401408, 401408, 401408, 413952, 652288, 81536, 81536, 100352, 1024, 400)
D = sum(DIMS)
SHAPES = ((64,7,56,56),(64,7,56,56),(192,7,56,56),(192,7,28,28),(256,7,28,28),
          (480,7,28,28),(480,4,14,14),(512,4,14,14),(512,4,14,14),(512,4,14,14),
          (528,4,14,14),(832,4,14,14),(832,2,7,7),(832,2,7,7),(1024,2,7,7),(1024,1,1,1),(400,1,1,1))
NODES = ('features.1', 'features.2', 'features.3.1', 'features.4', 'features.5.cat',
         'features.6.cat', 'features.7', 'features.8.cat', 'features.9.cat',
         'features.10.cat', 'features.11.cat', 'features.12.cat', 'features.13',
         'features.14.cat', 'features.15.cat', 'avgpool', 'classifier.1')
LAMBDAS = tuple('1e%d' % i for i in range(-6, 4))
FRACTIONS = ('0.80', '0.95', '0.99', 'all')
TEMPLATES = ('all17', 'early7', 'late10', 'avgpool', 'classifier')


def partitions(quartiles):
    require(type(quartiles) is list and len(quartiles) == 4, 'four admitted acquisition quartiles')
    require(all(type(q) is list and len(q) == 250 and all(type(v) is int for v in q) and q == sorted(q) for q in quartiles),
            'sorted complete quartile membership')
    require(sorted(v for q in quartiles for v in q) == list(TRAIN), 'exact1000 unique training identities')
    inner = []
    for fold in range(5):
        validation = sorted(v for q in quartiles for i, v in enumerate(q) if i % 5 == fold)
        training = sorted(set(TRAIN) - set(validation))
        inner.append({'id': 'inner-%d' % fold, 'fold': fold, 'train': training, 'other': validation})
    return inner + [{'id': 'final', 'fold': None, 'train': list(TRAIN), 'other': list(QUERY)}]


def admit_study_metadata(study):
    fields(study, ('schema', 'task', 'recordings', 'videos', 'quartiles', 'quartile_evidence',
                   'channels', 'times', 'feature_outputs', 'feature_source', 'feature_weights',
                   'language_source', 'language_weights', 'annotations', 'derivative_lineage',
                   'rights', 'independent_admission'))
    require(study['schema'] == 'n079_complete_study_v1' and study['task'] == 'NEURAL-079', 'canonical study')
    for key in ('quartile_evidence', 'feature_source', 'feature_weights', 'language_source',
                'language_weights', 'annotations', 'derivative_lineage', 'rights', 'independent_admission'):
        checked_pin(study[key])
    recordings = join_unique(study['recordings'], 'id')
    expected = {'%s/session-%02d' % (p, s) for p in PERSONS for s in range(1, 9)}
    require(set(recordings) == expected, 'all48 recording identities')
    for name, row in recordings.items():
        fields(row, ('id', 'person', 'session', 'object', 'schema_pin', 'trial_roster_pin'))
        require(name == '%s/session-%02d' % (row['person'], integer(row['session'], 1)), 'recording identity join')
        descriptor(row['object']); checked_pin(row['schema_pin']); checked_pin(row['trial_roster_pin'])
    videos = join_unique(study['videos'], 'id')
    require(set(videos) == set(range(1, 1103)), 'all1102 authenticated video identities')
    for row in videos.values():
        fields(row, ('id', 'object', 'decoder_pin', 'annotation_join_pin'))
        descriptor(row['object']); checked_pin(row['decoder_pin']); checked_pin(row['annotation_join_pin'])
    require(type(study['channels']) is list and len(study['channels']) == 127 and
            all(type(n) is str and n for n in study['channels']) and len(set(study['channels'])) == 127, 'exact127 unique ordered channel names')
    require(study['times'] == {'count': 1800, 'start_microseconds': -100000, 'step_microseconds': 2000},
            'full native500Hz time axis')
    require(study['feature_outputs'] == [{'node': n, 'columns': d} for n, d in zip(NODES, DIMS)],
            'all17 exact ordered graph outputs')
    return partitions(study['quartiles'])


def policies():
    return [{'id': '%s-%s-seed%d' % (mode, tool, seed), 'mode': mode, 'tool': tool, 'seed': seed}
            for mode in ('F', 'I') for tool in ('basic', 'fit-helper') for seed in range(3)]


def bundles():
    return [{**p, 'id': p['id'] + '-' + signal, 'policy_id': p['id'], 'signal': signal,
             'persons': list(PERSONS), 'query_ids': list(QUERY)}
            for p in policies() for signal in ('measured', 'mismatch', 'absent')]


def reference_jobs():
    # Yield complete target-head jobs; final selected setting is joined later
    # to the independently recomputed complete inner grid, never guessed here.
    for person in PERSONS:
        for signal in ('measured', 'mismatch'):
            for family, settings in (('R1', [('0.95', '0')]),
                                     ('R2', [(f, l) for f in FRACTIONS for l in LAMBDAS]),
                                     ('R3', [(t, l) for t in TEMPLATES for l in LAMBDAS])):
                for fold in range(5):
                    for setting, lam in settings:
                        yield {'person': person, 'signal': signal, 'family': family,
                               'split': 'inner-%d' % fold, 'parameter': setting, 'lambda': lam}
                yield {'person': person, 'signal': signal, 'family': family,
                       'split': 'final', 'parameter': 'independent_inner_selection', 'lambda': None}


def native_jobs():
    out = [{'id': 'native-visual-features', 'kind': 'visual_features'},
           {'id': 'native-language-features', 'kind': 'language_features'}]
    out += [{'id': 'native-%s-%s' % (branch, person), 'kind': branch + '_fit', 'person': person}
            for branch in ('visual', 'language') for person in PERSONS]
    out += [{'id': 'native-partial-' + person, 'kind': 'partial', 'person': person} for person in PERSONS]
    return out + [{'id': 'native-statistics', 'kind': 'statistics'}, {'id': 'native-plot', 'kind': 'plot'}]


def compile_study(study):
    parts = admit_study_metadata(study)
    return {'schema': 'n079_compiled_complete_v1', 'task': 'NEURAL-079', 'partitions': parts,
            'policies': policies(), 'bundles': bundles(), 'native': native_jobs(),
            'counts': {'persons': 6, 'sessions': 48, 'feature_outputs': 17, 'D': D, 'Q': Q,
                       'policies': 12, 'bundles': 36, 'queries': 3672, 'person_video_predictions': 22032,
                       'person_panels': 216, 'reference_fits': 5496, 'reference_inner': 5460,
                       'reference_final': 36, 'native_jobs': 22, 'native_normalization_applications': 144,
                       'native_normalization_states': 48, 'prospective_session_states': 288,
                       'reference_decompositions': 36, 'reports': 36, 'report_items': 432,
                       'base_producer_starts': 3770, 'service_role_instances': 7,
                       'base_starts_if_all_services_fresh': 3777,
                       'reference_setting_factors': 546},
            'qualification': 'none; descriptors require independent authentic custody and source admission'}
