"""Frozen full scope and conditional census. No dataset access or fitting."""
import itertools
import hashlib
from .common import need, digest

TASK = 'NEURAL-054'
DOMAIN = 'NEURAL054_AUTHENTIC_V1'
INERT = 'N054_TINY_INERT_CONTROL_ONLY'
PEOPLE = tuple('BIGMEG' + str(i) for i in range(1, 5))
WINDOWS = {'PRE': (-100, -20), 'EARLY_MINUS': (60, 140), 'EARLY': (80, 160),
           'EARLY_PLUS': (100, 180), 'LATE': (200, 280)}
FAMILIES = {'VISUAL': ('visual',), 'OCULAR': ('ocular',),
            'NUISANCE': ('visual', 'ocular'), 'NEURAL': ('neural',),
            'JOINT': ('visual', 'ocular', 'neural')}
DIMS = {'visual': 103, 'ocular': 24, 'neural': 1084}
LABELS = ('animal', 'bird', 'body part', 'clothing', 'clothing accessory', 'container',
          'dessert', 'drink', 'electronic device', 'food', 'fruit', 'furniture', 'home decor',
          'insect', 'kitchen appliance', 'kitchen tool', 'medical equipment', 'musical instrument',
          'office supply', 'part of car', 'plant', 'sports equipment', 'tool', 'toy', 'vegetable',
          'vehicle', 'weapon')
CORE = 'FULL_CORE_REFERENCE_V1'
SUMMARY = 'D_SUMMARY_REFERENCE_V1'
REFS = {CORE: ('R0', 'R1', 'R2', 'R4', 'R5'),
        SUMMARY: ('DG_DIAGONAL_GAUSSIAN', 'DC_NEAREST_CENTROID')}
PROFILE = {CORE: 'FULL_CORE_V1', SUMMARY: 'D_PCA8_SUMMARY_V1'}


def bucket(prefix, value, modulus):
    return int.from_bytes(hashlib.sha256((prefix + str(value)).encode()).digest()[:8], 'big') % modulus


def concept_group(value):
    need(type(value) is int and 1 <= value <= 1854, 'Concept identity')
    return bucket('NEURAL054-concept-v1:', value, 5)


def cases():
    return [{'person': p, 'session': s, 'fold': f} for p in PEOPLE
            for s in range(1, 13) for f in range(5)]


def slot(case, window, arm):
    return {'case': case, 'window': window, 'arm': arm}


def slots():
    return [slot(c, w, a) for c in cases() for w in WINDOWS for a in FAMILIES]


def mode_requirements(modes):
    need(type(modes) is list and modes and len(modes) == len(set(modes)) and set(modes) <= set('PIDR'),
         'Nonempty unique selected mode set')
    selected = set(modes)
    banks = ([CORE] if selected & set('PI') else []) + ([SUMMARY] if 'D' in selected else [])
    return {'modes': sorted(selected), 'banks': banks, 'prediction': bool(selected & set('PID')),
            'standalone_R': selected == {'R'}, 'interpret': 'R' in selected}


def mode_matrix():
    return [mode_requirements(list(m)) for n in range(1, 5) for m in itertools.combinations('PIDR', n)]


def campaign(manifest):
    required = {'schema', 'domain', 'conditions', 'source_generation', 'exposure', 'resources', 'environment', 'comparisons'}
    need(set(manifest) == required and manifest['schema'] == 'n054_campaign_v1', 'Campaign schema')
    need(manifest['domain'] in (DOMAIN, INERT), 'Explicit domain')
    conditions = manifest['conditions']
    need(type(conditions) is list and conditions, 'Selected conditions required')
    ids = set()
    for c in conditions:
        need(set(c) == {'id', 'mode', 'tool', 'replicate', 'program', 'profile'}, 'Condition schema')
        need(c['id'] not in ids and c['mode'] in 'PIDR', 'Condition identity')
        ids.add(c['id'])
        need(type(c['replicate']) is int and c['replicate'] >= 0, 'Replicate')
        if c['mode'] in 'PI':
            need(c['tool'] in ('NUM', 'NUM_REF') and c['profile'] == PROFILE[CORE], 'P/I profile')
        elif c['mode'] == 'D':
            need(c['tool'] == 'NONE' and c['profile'] == PROFILE[SUMMARY], 'D profile')
        else:
            need(c['tool'] == 'REPORT_ONLY' and c['profile'] == 'REPORT_V1', 'R profile')
    need(type(manifest['comparisons']) is list, 'Predeclared comparison roster')
    indexed = {c['id']: c for c in conditions}; comparison_ids = set()
    for pair in manifest['comparisons']:
        need(type(pair) is dict and set(pair) == {'id', 'left', 'right'}, 'Matched comparison schema')
        need(type(pair['id']) is str and pair['id'] and pair['id'] not in comparison_ids, 'Unique comparison ID')
        comparison_ids.add(pair['id'])
        need(pair['left'] in indexed and pair['right'] in indexed and pair['left'] != pair['right'], 'Distinct selected comparison conditions')
        left, right = indexed[pair['left']], indexed[pair['right']]
        need(left['mode'] in ('P', 'I') and right['mode'] in ('P', 'I') and
             left['profile'] == right['profile'] and left['replicate'] == right['replicate'], 'Prospective matched full-core comparison')
    return mode_requirements(sorted({c['mode'] for c in conditions}))


def census(manifest, panel):
    req = campaign(manifest)
    if not req['prediction']:
        return {'requirements': req, 'references': {}, 'candidates': [], 'manifest': digest(manifest), 'panel': None, 'slots': 0}
    if manifest['domain'] == DOMAIN:
        need(len(panel['slots']) == 6000 and {digest(s['logical']) for s in panel['slots']} ==
             {digest(s) for s in slots()}, 'Whole 240 x 5 x 5 scope')
        need(panel['experimental_rows'] == 88992 and panel['recorded_rows'] == 108192,
             'Full trial provenance')
    else:
        need(0 < len(panel['slots']) <= 2 and panel['experimental_rows'] <= 4,
             'Tiny inert limit; cannot masquerade as full cohort')
    need(panel['domain'] == manifest['domain'] and panel['generation'] == manifest['source_generation'],
         'Generation/domain mismatch')
    slot_ids = [s['id'] for s in panel['slots']]
    need(len(slot_ids) == len(set(slot_ids)), 'Duplicate slot')
    refs = {kind: [(f, sid) for f in REFS[kind] for sid in slot_ids] for kind in req['banks']}
    candidates = [(c['id'], sid) for c in manifest['conditions'] if c['mode'] in 'PID' for sid in slot_ids]
    return {'requirements': req, 'references': refs, 'candidates': candidates,
            'manifest': digest(manifest), 'panel': digest(panel), 'slots': len(slot_ids)}
