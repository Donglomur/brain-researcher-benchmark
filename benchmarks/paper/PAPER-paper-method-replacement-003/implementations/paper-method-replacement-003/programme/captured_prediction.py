"""Actual captured probability tensor and identity are the scoring input.

The capture owner must belong to the trusted evaluator. These source joins do
not manufacture target/source/native authority from participant dictionaries.
"""
from dataclasses import dataclass
from .cohort import CLASSES,UnitKey,SupportError
from .evaluation import Prediction,validate_prediction,validate_member_support

@dataclass(frozen=True)
class ProbabilityCapture:
    tensor: object
    identity: object

def capture_probabilities(outputs,prefix,raw,units,classes,source_identity,model_identity,*,member_support=None):
    import numpy as np
    tensor=np.asarray(raw)
    units=tuple(units);models=tuple(model_identity)
    support={'layout':'global_members','row_model_indices':None} if member_support is None else member_support
    width=validate_member_support(units,models,support)
    if tensor.ndim!=3 or tensor.shape!=(len(units),5,width):
        raise SupportError('complete unit/class/member tensor required before capture')
    if tuple(classes)!=CLASSES or not source_identity:raise SupportError('captured class/source identity missing')
    validate_prediction(Prediction(units,CLASSES,tensor.mean(axis=2),source_identity,models),units)
    if not np.isfinite(tensor).all() or np.any(tensor<0) or np.any(tensor>1) or not np.allclose(tensor.sum(axis=1),1,rtol=0,atol=1e-6):
        raise SupportError('invalid individual model probability tensor')
    body=outputs.array(prefix+'-probabilities.npy',tensor)
    identity=outputs.json(prefix+'-identity.json',{'schema':'c4_probability_capture_v3',
        'units':units,'classes':CLASSES,'source_identity':source_identity,'models':models,
        'tensor':body,'shape':tensor.shape,'reduction':'equal_member_mean_axis2','member_support':support})
    return ProbabilityCapture(body,identity)

def read_prediction(outputs,capture,expected_units,expected_source):
    import io,json
    import numpy as np
    # Both immutable records are authenticated before targets are consumed.
    identity=json.loads(outputs.read_captured(capture.identity))
    expected={'schema','units','classes','source_identity','models','tensor','shape','reduction','member_support'}
    if set(identity)!=expected or identity['schema']!='c4_probability_capture_v3':raise SupportError('capture identity schema mismatch')
    if identity['tensor']!=capture.tensor.__dict__ or identity['reduction']!='equal_member_mean_axis2':
        raise SupportError('tensor/identity capture join mismatch')
    units=tuple(UnitKey(**row) for row in identity['units'])
    if units!=tuple(expected_units) or tuple(identity['classes'])!=CLASSES or identity['source_identity']!=expected_source:
        raise SupportError('capture biological/class/source identity mismatch')
    models=tuple(identity['models']);support=identity['member_support']
    if type(support) is dict and support.get('layout')=='unit_loo_10':
        decoded=[]
        for model in models:
            if type(model) is not list or len(model)!=2 or type(model[1]) is not dict or set(model[1])!=set(UnitKey.__dataclass_fields__):
                raise SupportError('serialized LOO model identity malformed')
            decoded.append((model[0],UnitKey(**model[1])))
        models=tuple(decoded)
    width=validate_member_support(units,models,support)
    tensor=np.load(io.BytesIO(outputs.read_captured(capture.tensor)),allow_pickle=False)
    if tensor.dtype.hasobject or tensor.ndim!=3 or tensor.shape!=(len(units),5,width) or list(tensor.shape)!=identity['shape'] or not models:
        raise SupportError('captured tensor extent differs from captured identity')
    if not np.isfinite(tensor).all() or np.any(tensor<0) or np.any(tensor>1) or not np.allclose(tensor.sum(axis=1),1,rtol=0,atol=1e-6):
        raise SupportError('invalid captured individual probabilities')
    prediction=Prediction(units,CLASSES,tensor.mean(axis=2),expected_source,models,support)
    validate_prediction(prediction,expected_units)
    return prediction
