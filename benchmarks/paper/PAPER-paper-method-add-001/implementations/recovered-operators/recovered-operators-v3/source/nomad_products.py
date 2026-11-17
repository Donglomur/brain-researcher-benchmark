"""Actual fixed-decoder and position consumers for captured full trajectories."""
from .nomad_math import (need, closed, integer, finite, numpy_for, matrix,
                         seal_array, identity, array_identity)


CHECKPOINT_FIELDS = {'source_pin','configuration_pin','state_pin','epoch',
                     'method','reference_session','feature_ids','normalization_pin',
                     'training_support_pin','inference_profile_pin'}


def checkpoint_binding(record, selection):
    """Closed metadata join, not independent proof that a native job occurred."""
    closed(record, CHECKPOINT_FIELDS, 'closed actual checkpoint capture')
    closed(selection, CHECKPOINT_FIELDS, 'closed independently selected checkpoint')
    need(record == selection, 'exact source/state/epoch/support/normalizer join')
    integer(record['epoch'])
    need(record['feature_ids'] and len(set(record['feature_ids']))==len(record['feature_ids']),
         'complete unique native feature order')
    for key in CHECKPOINT_FIELDS-{'epoch','feature_ids'}:
        need(type(record[key]) is str and record[key], 'nonempty checkpoint lineage')
    return identity(record)


def decode_checkpoint(states, support, decoder, checkpoint, selection, inference, profile, budget):
    """Evaluate a captured fitted method-specific fixed decoder, not its score.

    Every query row has an explicit vector of context-row indexes; absent initial
    history refuses instead of zero padding. All selected state rows are consumed.
    Decoder coefficients are an actual fitted artifact, not a shared cross-method
    matrix or a callable. Native state capture remains an independent prerequisite.
    """
    np=numpy_for(profile)
    closed(support,['state_row_ids','query_row_ids','context_indices','feature_ids',
                    'axes','units','query_times','state_times'], 'complete trace support')
    closed(decoder,['method','reference_session','feature_ids','lag_offsets',
                    'axes','units','weights','fit_support_pin','state_coordinates_pin',
                    'decoder_pin','weights_value_pin'], 'actual captured fixed decoder fields')
    cp=checkpoint_binding(checkpoint,selection)
    closed(inference,['schema','checkpoint_binding','states_value_pin','support_value_pin',
        'input_pins','normalization_pin','coordinates_pin','source_pin','configuration_pin',
        'epoch','method','reference_session','feature_ids'], 'captured checkpoint inference product')
    need(inference['schema']=='nomad_checkpoint_inference_v2' and inference['checkpoint_binding']==cp,
         'inference belongs to the independently selected checkpoint')
    for key in ('normalization_pin','source_pin','configuration_pin','epoch','method','reference_session','feature_ids'):
        need(inference[key]==checkpoint[key], 'checkpoint-to-inference '+key)
    need(type(inference['input_pins']) is dict and inference['input_pins'], 'complete captured inference inputs')
    need(inference['states_value_pin']==array_identity(states)
         and inference['support_value_pin']==identity(support), 'actual state values and complete support belong to inference')
    need(inference['coordinates_pin']==profile['fixed_reference_coordinate_pin'], 'actual inference fixed coordinates')
    need(decoder['weights_value_pin']==array_identity(decoder['weights']), 'actual coefficients belong to fitted decoder')
    need(decoder['method']==checkpoint['method'] and
         decoder['reference_session']==checkpoint['reference_session'], 'method-specific fixed Day0 decoder')
    need(support['feature_ids']==checkpoint['feature_ids']==decoder['feature_ids'],
         'actual neural feature ordering')
    need(support['axes']==decoder['axes'] and support['units']==decoder['units'],
         'complete output axes/units')
    need(decoder['state_coordinates_pin']==profile['fixed_reference_coordinate_pin'],
         'same fitted reference coordinate system')
    need(decoder['fit_support_pin']==profile['decoder_fit_support_pin'] and
         decoder['decoder_pin']==profile['decoder_artifact_pin'], 'selected fixed fit identity')
    n=len(support['state_row_ids']);q=len(support['query_row_ids']);f=len(support['feature_ids'])
    a=len(support['axes']);lags=decoder['lag_offsets'];h=len(lags)
    need(n and q and f and a and h, 'complete nonempty support')
    need(all(type(v) is int for v in lags) and len(set(lags))==h
         and max(lags)==0 and all(v<=0 for v in lags), 'explicit current/past lag offsets')
    need(len(set(support['state_row_ids']))==n and len(set(support['query_row_ids']))==q,
         'unique complete row identities')
    times=support['state_times'];qt=support['query_times']
    need(len(times)==n and len(qt)==q and all(finite(x)==x for x in times+qt)
         and all(x<y for x,y in zip(times,times[1:])), 'exact state/query time support')
    indices=support['context_indices']
    need(type(indices) is list and len(indices)==q, 'every query context supplied')
    for r,when in zip(indices,qt):
        need(type(r) is list and len(r)==h and all(type(i) is int and 0<=i<n for i in r),
             'complete bounded context indexes')
        current=r[lags.index(0)]
        need(times[current]==when and all(i==current+lag for i,lag in zip(r,lags)),
             'actual current/past state-index geometry')
        need(all(times[i]<=when for i in r), 'no future feature state')
    matrix(np,states,(n,f),budget,'checkpoint.states')
    W=matrix(np,decoder['weights'],(1+h*f,a),budget,'checkpoint.decoder')
    budget.reserve('checkpoint.fixed_decode', {'design':q*(1+h*f), 'prediction':q*a,
        'context_copy':q*h*f}, q*(1+h*f)*a)
    X=np.ones((q,1+h*f),dtype=np.float64)
    for i,r in enumerate(indices):X[i,1:]=states[r,:].reshape(h*f)
    predicted=X@W
    need(bool(np.isfinite(predicted).all()), 'finite actual decoder output')
    return {'kind':'captured_checkpoint_trace_v1','checkpoint_binding':cp,'inference_binding':identity(inference),
        'decoder_pin':decoder['decoder_pin'],'support_pin':identity(support),
        'support':support,'predictions':seal_array(np,predicted,budget,'trace.predictions'),
        'state_values_pin':array_identity(states),'decoder_values_pin':array_identity(W),
        'original_native_capture_independently_qualified':False}


def integrate_position(velocity, timestamps, initial_position, profile, budget):
    closed(profile,['numpy_version','rule','velocity_units','position_units','time_units',
                    'velocity_to_position_per_time','profile_id','source_profile_pin'],
           'explicit integration rule/units/origin profile')
    np=numpy_for(profile)
    need(profile['rule'] in ('left_rectangle','trapezoid'), 'no default quadrature')
    need(type(timestamps) is list and len(timestamps)>=1 and
         all(type(x) in (int,float) for x in timestamps), 'full explicit timestamps')
    times=[finite(x) for x in timestamps]
    need(all(a<b for a,b in zip(times,times[1:])), 'strict entire clock')
    n=len(times);need(type(initial_position) is list and initial_position,'explicit initial position')
    initial=[finite(x) for x in initial_position];d=len(initial)
    scale=finite(profile['velocity_to_position_per_time'])
    need(scale>0 and all(type(profile[k]) is str and profile[k] for k in
        ('velocity_units','position_units','time_units','profile_id','source_profile_pin')),
        'selected positive unit conversion, not guessed time units')
    matrix(np,velocity,(n,d),budget,'integration.velocity')
    budget.reserve('position.integration', {'positions':n*d,'increments':(n-1)*d,
        'dt':n-1,'work':3*n*d}, 0)
    position=np.empty((n,d),dtype=np.float64);position[0]=initial
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        for i in range(1,n):
            dt=times[i]-times[i-1]
            v=velocity[i-1] if profile['rule']=='left_rectangle' else velocity[i-1]/2+velocity[i]/2
            position[i]=position[i-1]+v*(dt*scale)
    need(bool(np.isfinite(position).all()), 'finite complete integrated trace')
    return {'positions':seal_array(np,position,budget,'position.output'),
            'timestamps':tuple(times),'initial_position':tuple(initial),
            'profile':dict(profile),'velocity_identity':array_identity(velocity),
            'original_quadrature_authenticated':False}


def stitching_trainable_ownership(branch, session, shared_names, adapters, trainable_names):
    """Actual set calculation prevents cross-session adapter gradient ownership.

    No gradient/model callbacks or trained result are accepted. A future concrete
    native optimizer must pass its actual variable names before applying updates.
    """
    need(branch in ('supervised_fixed','supervised_trainable','random_trainable'),
         'exact three original branch identities')
    need(type(adapters) is dict and session in adapters and len(adapters)>=2,
         'complete multi-session adapter roster')
    shared=set(shared_names);seen=set(shared)
    for sid,row in adapters.items():
        closed(row,['readin','readout'],'session adapter ownership')
        for names in row.values():
            need(type(names) is list and len(set(names))==len(names), 'unique variable list')
            need(not seen.intersection(names), 'no cross-role variable alias')
            seen.update(names)
    expected=shared|set(adapters[session]['readout'])
    if branch!='supervised_fixed':expected|=set(adapters[session]['readin'])
    need(set(trainable_names)==expected and len(trainable_names)==len(expected),
         'exact shared core plus current-session allowed adapters')
    return {'branch':branch,'session':session,'allowed':sorted(expected),
            'prohibited':sorted(seen-expected),'model_was_trained':False}
