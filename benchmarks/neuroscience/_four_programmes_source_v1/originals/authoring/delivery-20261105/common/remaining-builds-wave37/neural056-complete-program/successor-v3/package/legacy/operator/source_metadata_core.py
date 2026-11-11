"""Pure metadata split/identity construction. No dataset access or fitting."""
import hashlib
import hmac
from collections import Counter

PARTICIPANTS = tuple('sub-' + str(i).zfill(2) for i in range(1, 11))


def need(value, reason):
    if not value:
        raise ValueError(reason)


def validate_metadata(meta):
    need(type(meta) is dict, 'image metadata dictionary required')
    required = ('train_img_files', 'test_img_files', 'train_img_concepts_THINGS', 'test_img_concepts_THINGS')
    for key in required:
        need(key in meta and type(meta[key]) is list and all(type(x) is str and x for x in meta[key]), key + ': string list required')
    train_files, test_files = meta['train_img_files'], meta['test_img_files']
    train_concepts, test_concepts = meta['train_img_concepts_THINGS'], meta['test_img_concepts_THINGS']
    need(len(train_files) == len(train_concepts) == 16540 and len(set(train_files)) == 16540, 'complete16540 training identities required')
    need(len(test_files) == len(test_concepts) == 200 and len(set(test_files)) == 200, 'complete200 test identities required')
    need(len(set(train_concepts)) == 1654 and set(Counter(train_concepts).values()) == {10}, '1654 training concepts with10 exemplars each required')
    need(len(set(test_concepts)) == 200 and not (set(train_concepts) & set(test_concepts)), '200 test concepts disjoint from training required')
    need(not (set(train_files) & set(test_files)), 'filenames must be partition-disjoint')
    return {key: meta[key] for key in required}


def split_plan(meta):
    m = validate_metadata(meta)
    concepts = set(m['train_img_concepts_THINGS'])
    ordered = sorted(concepts, key=lambda x: (hashlib.sha256(('NEURAL-055/draft1/concept-development/' + x).encode()).hexdigest(), x))
    development = ordered[:330]
    return {'schema': 'neural055-draft-split-v1', 'design_choice': 'new_prospective_draft_not_author_split',
            'development_concepts': development, 'fit_concepts': ordered[330:],
            'development_training_row_indices': [i for i, x in enumerate(m['train_img_concepts_THINGS']) if x in set(development)],
            'outer_folds': [{'outer_participant': held, 'training_participants': [x for x in PARTICIPANTS if x != held],
                             'inner_participant_holdouts': [x for x in PARTICIPANTS if x != held]} for held in PARTICIPANTS]}


def case_identity(meta, participant, secret):
    """Independent query/candidate permutations; hidden join and secret never public.

    IDs and the candidate tie order are fixed in this public case before any
    predictions. Distinct HMAC domains remove direct order/ID correspondence.
    """
    m = validate_metadata(meta)
    need(participant in PARTICIPANTS and type(secret) is bytes and len(secret) == 32, 'participant and32-byte operator-only ID key required')
    def token(domain, value):
        return hmac.new(secret, (domain + '\0' + participant + '\0' + value).encode(), hashlib.sha256).hexdigest()
    case_id = 'case_' + token('case', 'id')[:24]
    rows = []
    for i, (concept, name) in enumerate(zip(m['test_img_concepts_THINGS'], m['test_img_files'])):
        identity = 'test\0' + concept + '\0' + name
        rows.append((i, 'q_' + token('query', identity)[:24], 'c_' + token('candidate', identity)[:24]))
    query_rows = sorted(rows, key=lambda x: token('query-order', x[1]))
    candidate_rows = sorted(rows, key=lambda x: token('candidate-order', x[2]))
    case = {'schema': 'neural055-public-case-v1', 'case_id': case_id,
            'query_ids': [x[1] for x in query_rows], 'candidate_ids': [x[2] for x in candidate_rows]}
    target = {'schema': 'neural055-private-target-v1', 'case_id': case_id,
              'query_to_candidate': {x[1]: x[2] for x in rows}}
    return case, target, [x[0] for x in query_rows], [x[0] for x in candidate_rows]


def validate_archive_identity(participant, pin):
    """Reviewed participant-to-publisher-asset binding, beyond a caller label."""
    need(participant in PARTICIPANTS and type(pin) is dict, 'participant archive binding required')
    need(pin.get('participant') == participant and pin.get('filename') == participant + '.zip', 'participant must match reviewed original archive identity')
    need(type(pin.get('osf_id')) is str and pin['osf_id'] and type(pin.get('version')) is int and pin['version'] >= 1, 'exact publisher asset and revision required')
    need(type(pin.get('bytes')) is int and pin['bytes'] > 0, 'exact archive bytes required')
    need(type(pin.get('sha256')) is str and len(pin['sha256']) == 64 and all(x in '0123456789abcdef' for x in pin['sha256']), 'exact archive hash required')
    return pin


def validate_staged_participant_bindings(people):
    need(set(people) == set(PARTICIPANTS), 'all ten staged participants required')
    archives=[];training=[]
    for person, staged in people.items():
        need(staged.get('participant') == person, 'staged participant label mismatch')
        pin=validate_archive_identity(person,staged.get('source_archive'))
        archives.append(pin['sha256'])
        train=staged.get('files',{}).get('train_mean.npy',{})
        digest=train.get('sha256')
        need(type(digest) is str and len(digest)==64 and all(x in '0123456789abcdef' for x in digest), 'training mean identity descriptor required')
        training.append(digest)
    need(len(set(archives))==10, 'same source archive cannot stand in for different participants')
    need(len(set(training))==10, 'duplicate staged training EEG cannot stand in for different participants')


def calibration_panels(meta):
    """Fixed200 of330 development concepts; ten matched exemplar panels.

    New prospective recipe: concept and within-concept filename SHA256 rankings.
    Every selected concept supplies exactly one different exemplar per panel.
    No source test-image identity or EEG outcome affects the selection.
    """
    m=validate_metadata(meta);plan=split_plan(m)
    concepts=sorted(plan['development_concepts'],key=lambda x:(hashlib.sha256(('NEURAL-055/draft1/calibration-concepts/'+x).encode()).hexdigest(),x))[:200]
    groups={c:[] for c in concepts}
    for i,c in enumerate(m['train_img_concepts_THINGS']):
        if c in groups:groups[c].append(i)
    for c,rows in groups.items():
        rows.sort(key=lambda i:(hashlib.sha256(('NEURAL-055/draft1/calibration-exemplars/'+m['train_img_files'][i]).encode()).hexdigest(),m['train_img_files'][i]))
    return {'schema':'neural055-calibration-panels-v1','concepts':concepts,
            'panels':[{'exemplar_rank':j,'training_row_indices':[groups[c][j] for c in concepts]} for j in range(10)],
            'truth_convention':'Within each panel use identical selectedimage order for query/candidates then apply anyjoint recordedpermutations; canonicaltruth indices0..199. Innerheldperson EEG is four-repeat trainingmean, not outer80-repeat EEG.',
            'outer_assessment_used':False}
