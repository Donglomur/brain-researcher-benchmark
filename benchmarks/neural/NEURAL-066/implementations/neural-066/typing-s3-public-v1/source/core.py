"""NEURAL066 technical identities and complete logical roster; no scientific imports."""
import hashlib
import json
import math
import re
MODES = ('frozen_program', 'case_adaptive_equal_inputs_tools_compute')
CONDITIONS = ('TIMING', 'EOG', 'NEURAL_PRE', 'NEURAL', 'NEURAL_POST', 'SHUFFLE')
R2_ARMS = ('NEURAL_PRE', 'NEURAL', 'NEURAL_POST', 'SHUFFLE')
CHARS = ('s', 'o', 't', 'e', 'n', 'c', 'i', 'a', ' ', 'd', 'l', 'r', 'b', '@', 'z', 'v', 'f', 'm', 'u', 'h', 'p', 'g', 'q', 'w', 'x', 'y', 'j', 'k', '9')
COUNTS = {'MEG': {'people': 19, 'timelines': 81, 'channels': 306}, 'EEG': {'people': 20, 'timelines': 62, 'channels': 61}}
ENCODING_METER = None

def need(ok, message):
    if not ok:
        raise ValueError(message)

def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if ENCODING_METER is not None:
        ENCODING_METER(len(raw))
    return raw

def identity(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'Exact declared object fields')

def positive(value, label, zero=False):
    need(type(value) is int and value >= (0 if zero else 1), label)
    return value

def digest(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def descriptor(value):
    exact(value, ('bytes', 'sha256'))
    positive(value['bytes'], 'Nonnegative exact byte extent', zero=True)
    need(digest(value['sha256']), 'SHA256 identity')
    return value

def cases():
    for modality, counts in COUNTS.items():
        for person in range(counts['people']):
            for fold in range(2):
                yield {'slot': f'{modality}-{person:02d}-{fold}', 'modality': modality, 'person_slot': person, 'fold': fold}

def roster():
    """All 11,306 adopted phases and exact predecessor IDs, never physical counts."""
    number = 0
    candidate_predictions = []
    reference_predictions = []
    declarations = []

    def row(action, parents=(), **fields):
        nonlocal number
        number += 1
        return {'action': action, 'phase_id': f'P{number:05d}', 'parents': list(parents), **fields}
    start = row('source_admission')
    yield start
    projections = []
    for i in range(143):
        item = row('native_project', [start['phase_id']], timeline_slot=i)
        projections.append(item['phase_id'])
        yield item
    joined = row('membership', projections)
    yield joined
    plans = {}
    for c in cases():
        item = row('case_plan', [joined['phase_id']], **c)
        plans[c['slot']] = item['phase_id']
        yield item
    for c in cases():
        for mode in MODES:
            for condition in CONDITIONS:
                parent = plans[c['slot']]
                for action in ('candidate_view', 'candidate_author', 'candidate_fit', 'candidate_infer'):
                    item = row(action, [parent], **c, mode=mode, condition=condition)
                    parent = item['phase_id']
                    yield item
                candidate_predictions.append((mode, parent))
    for c in cases():
        for condition in CONDITIONS:
            fit = row('r0fit', [plans[c['slot']]], **c, condition=condition)
            yield fit
            infer = row('r0infer', [fit['phase_id']], **c, condition=condition)
            reference_predictions.append(infer['phase_id'])
            yield infer
        fit = row('r1count', [plans[c['slot']]], **c, condition='LANGUAGE_ONLY')
        yield fit
        infer = row('r1infer', [fit['phase_id']], **c, condition='LANGUAGE_ONLY')
        reference_predictions.append(infer['phase_id'])
        yield infer
        for condition in R2_ARMS:
            inners = []
            for grid in range(2):
                for cell in range(9):
                    item = row('r2_inner', [plans[c['slot']]], **c, condition=condition, grid=grid, cell=cell)
                    inners.append(item['phase_id'])
                    yield item
            fit = row('r2_final', inners, **c, condition=condition)
            yield fit
            infer = row('r2_infer', [fit['phase_id']], **c, condition=condition)
            reference_predictions.append(infer['phase_id'])
            yield infer
    for mode in MODES:
        item = row('investigation_declaration', [pid for m, pid in candidate_predictions], mode=mode)
        declarations.append(item['phase_id'])
        yield item
    barrier = row('prescore_barrier', [pid for _, pid in candidate_predictions] + reference_predictions + declarations)
    yield barrier
    parent = barrier['phase_id']
    for action in ('score_primary', 'score_independent', 'report', 'terminal_observation'):
        item = row(action, [parent])
        parent = item['phase_id']
        yield item
    need(number == 11306, 'Complete adopted logical phase census')

def expected_counts():
    return {'source_admission': 1, 'native_project': 143, 'membership': 1, 'case_plan': 78, 'candidate_view': 936, 'candidate_author': 936, 'candidate_fit': 936, 'candidate_infer': 936, 'r2_inner': 5616, 'r2_final': 312, 'r2_infer': 312, 'r0fit': 468, 'r0infer': 468, 'r1count': 78, 'r1infer': 78, 'score_primary': 1, 'score_independent': 1, 'investigation_declaration': 2, 'prescore_barrier': 1, 'report': 1, 'terminal_observation': 1}

def no_science_promotion():
    return {'runtime_qualified': False, 'scientific_qualified': False, 'reference_competence_established': False, 'whole_paper_reproduction': False}
