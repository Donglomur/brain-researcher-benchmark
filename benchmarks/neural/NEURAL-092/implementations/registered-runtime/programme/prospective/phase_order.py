"""Validate the exact proposed phase transcript grammar, never scientific authority.

A valid dictionary is only a structurally consistent CLAIM. This function does
not authenticate who produced it, open targets, fit models, freeze files, launch
workers or authorize any operation. Those actual producers remain unimplemented.
"""
EVENTS=(
 ('design_freeze','none'),
 ('prediction_view_issued','none'),
 ('fit_grid_frozen','none'),
 ('validation_scored','none'),
 ('method_selection_frozen','none'),
 ('refit_frozen','none'),
 ('all_predictions_frozen','none'),
 ('private_query_scored','evaluator'),
 ('observed_query_released','candidate_observation'),
 ('investigation_closed','candidate_observation'))
BINDINGS=('source_snapshot','cohort','unit_axes','protocol','method_family','feature_basis')
def validate_phase_claim(transcript):
    if type(transcript)is not dict or set(transcript)!={'schema','task_id','bindings','events'}:
        raise ValueError('closed proposed phase transcript')
    if transcript['schema']!='neural092_phase_claim_v1'or transcript['task_id']!='NEURAL-092':
        raise ValueError('exact N092 phase grammar')
    bindings=transcript['bindings']
    if type(bindings)is not dict or set(bindings)!=set(BINDINGS):
        raise ValueError('complete source/cohort/axis/method binding claims')
    def digest(x):
        return type(x)is str and len(x)==64 and all(c in '0123456789abcdef'for c in x)
    if any(not digest(v)for v in bindings.values()):raise ValueError('closed digest syntax only')
    events=transcript['events']
    if type(events)is not list or len(events)!=len(EVENTS):
        raise ValueError('all phases exactly once, no implicit retry or partial success')
    last=None;frozen_prediction=None;seen=set()
    for i,(row,expected)in enumerate(zip(events,EVENTS)):
        if type(row)is not dict or set(row)!={'sequence','phase','query_visibility','bindings','receipt','previous_receipt','prediction_receipt'}:
            raise ValueError('closed phase event')
        if type(row['sequence'])is not int or row['sequence']!=i or (row['phase'],row['query_visibility'])!=expected:
            raise ValueError('exact order and pre-query blindness claim')
        if row['bindings']!=bindings:raise ValueError('source/cohort/axes/method claim changed')
        if not digest(row['receipt'])or row['receipt']in seen:raise ValueError('distinct receipt digest syntax')
        if row['previous_receipt']!=last:raise ValueError('claimed prior chain mismatch')
        seen.add(row['receipt']);last=row['receipt']
        if i<6:
            if row['prediction_receipt']is not None:raise ValueError('prediction freeze claim not yet issued')
        elif i==6:
            if row['prediction_receipt']!=row['receipt']:raise ValueError('freeze binds this exact claimed receipt')
            frozen_prediction=row['receipt']
        elif row['prediction_receipt']!=frozen_prediction:
            raise ValueError('no prediction replacement after query access')
    return {'status':'structurally_consistent_claim_only','event_count':len(events),
            'query_before_prediction_claim':False,
            'genuine_issuer_authenticated':False,'execution_authorized':False,
            'scientific_qualification':False}

