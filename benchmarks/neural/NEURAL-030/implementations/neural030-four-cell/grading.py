"""Trusted final phase: unchanged scientific reference and count scorer."""
import hashlib
from pathlib import Path
import io_utils as safe
from native import read_pinned
import views
import budget
from reference import predict_reference, validate_public
from score import score_predictions


def grade(request):
    budget.admit_bytes(request)
    root = Path(request['output'])
    panel = safe.strict(safe.read(root/'PANEL.json', 262144))
    safe.need(set(panel) == {'schema', 'public_pin', 'jobs'} and panel['schema'] == 'neural030-closed-panel-v1'
              and panel['public_pin'] == request['public_pin'] and len(panel['jobs']) == 128,
              'Frozen complete capture panel')
    public = safe.strict(read_pinned(root/'public.json', request['public_pin'], 64000000))
    validate_public(public)
    budget.admit(public, request)
    # These references use train/development counts only. The private packet is
    # deliberately opened after every reference and every candidate capture.
    references = {arm: predict_reference(public, arm) for arm in views.ARMS}
    candidates = {}
    for mode in views.MODES:
        for arm in views.ARMS:
            rows = []
            for i, case in enumerate(public['cases']):
                key = f'{views.MODES.index(mode)}-{views.ARMS.index(arm)}-{i:02d}'
                pin = panel['jobs'][key]
                closure = safe.strict(safe.read(root/'jobs'/key/'closure.json', 2200000))
                safe.need(not closure['errors'] and len(closure['resources']) == 3 and
                    all(x['absence_verified'] is True for x in closure['resources']) and
                    sorted(x['kind'] for x in closure['resources']) == ['container','container','volume'] and
                    len({x['name'] for x in closure['resources']}) == 3, 'Every owned resource closed')
                capture = safe.strict(read_pinned(root/'jobs'/key/'submission.json', pin, request['submission_cap_bytes']))
                rows.extend(views.predictions(capture, case))
            candidates[mode, arm] = rows
    private = safe.strict(read_pinned(request['private'], request['private_pin'], 64000000))
    safe.need(type(private) is dict and set(private) == {'schema', 'cases', 'expected', 'mouse_binding',
        'scientific_qualification', 'input_authenticity_not_established_by_preparer'} and
        private['schema'] == 'neural030_cerebellar_private_v1' and
        private['scientific_qualification'] is False and
        private['input_authenticity_not_established_by_preparer'] is True, 'Accepted private packet')
    expected = private['expected']
    query = {t['trial_id']: (c['session_id'], int(round(t['delay_s']/.1)))
             for c in public['cases'] for t in c['query']}
    safe.need(type(expected) is list and len(expected) == len(query) and
        {x['trial_id']: (x['session_id'], x['bin_count']) for x in expected} == query,
        'Private scoring population exactly matches complete frozen public queries')
    mapping = private['mouse_binding']['session_to_mouse']
    safe.need(set(mapping) == {c['session_id'] for c in public['cases']} and len(set(mapping.values())) == 5,
              'All16 sessions and five declared mice')
    safe.need(type(private['cases']) is list and len(private['cases']) == 16 and
              {c['session_id'] for c in private['cases']} == set(mapping), 'Complete private session records')
    result = {'schema': 'neural030-complete-grade-v1', 'primary_arm': 'joint',
              'primary_metric': 'mouse_macro.mse_gain', 'scientific_qualification': False,
              'identity_authentication': False, 'reference': {}, 'candidates': {}}
    baseline = references['context_handle']
    for arm, rows in references.items():
        result['reference'][arm] = score_predictions(expected, rows, baseline_predictions=baseline,
                                                     mouse_binding=private['mouse_binding'])
    for mode in views.MODES:
        result['candidates'][mode] = {arm: score_predictions(expected, candidates[mode, arm],
            baseline_predictions=baseline, mouse_binding=private['mouse_binding']) for arm in views.ARMS}
    safe.write_new(root/'grade.json', result, 64000000)
    return {'status': 'complete16_session_grade', 'sessions': 16, 'modes': 2, 'arms': 4,
            'query_trials': len(query), 'scientific_qualification': False}
