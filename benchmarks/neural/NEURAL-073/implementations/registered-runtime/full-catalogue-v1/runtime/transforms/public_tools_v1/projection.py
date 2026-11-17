"""Selected public transform DTOs; no fit IDs, source paths or unused banks."""
from dataclasses import dataclass
from types import MappingProxyType
import hashlib
import json
import math
import sys
from ..dependency import numpy_api
from ..numeric import NumericLimits, NumericalError, ViewBank, rms_rows

SCHEMA='n073_public_transform_v1'
FULL_FAMILIES=('ridge','linear_ovr_svm','centroid')
PCA_FAMILIES=('rbf_ovr_svm','extra_trees')


def _limit(limits,elements,workspace,operation):
    if not isinstance(limits,NumericLimits):raise NumericalError('PUBLIC_TRANSFORM_LIMITS_REQUIRED')
    limits.require(int(elements),int(workspace),operation)


def _array(x,limits):
    np=numpy_api()
    if type(x) is not np.ndarray or x.dtype!=np.dtype('float64') or x.ndim not in (1,2):
        raise NumericalError('PUBLIC_FLOAT64_ARRAY_REQUIRED')
    if any(n<1 for n in x.shape):raise NumericalError('PUBLIC_ARRAY_EMPTY')
    _limit(limits,x.size,8*x.size,'public_array')
    if not np.all(np.isfinite(x)):raise NumericalError('PUBLIC_ARRAY_NONFINITE')
    return x


def _exact_backing(x):
    """Return only an immutable buffer covering exactly the selected values."""
    np=numpy_api();current=x
    while type(current) is np.ndarray:current=current.base
    if type(current) is bytes and x.flags.c_contiguous and len(current)==x.nbytes:
        view=np.frombuffer(current,dtype=np.float64)
        if x.__array_interface__['data'][0]==view.__array_interface__['data'][0]:
            return current
    return None


def _public_array(x,limits):
    np=numpy_api();_array(x,limits)
    _limit(limits,x.size,16*x.size,'public_array_freeze')
    backing=_exact_backing(x)
    if backing is None:backing=x.tobytes(order='C')
    # No reference to a private state object or to unused backing-array values.
    return np.frombuffer(backing,dtype=np.float64).reshape(x.shape)


def _plain_algorithm(algorithm):
    return {k:(list(v) if type(v) is tuple else v) for k,v in algorithm.items()}


def _spec(algorithm):
    if type(algorithm) not in (dict,MappingProxyType):raise NumericalError('PUBLIC_ALGORITHM_TYPE')
    if type(algorithm.get('view')) is not str or algorithm['view'] not in ('N','C','NC'):
        raise NumericalError('PUBLIC_VIEW')
    view=algorithm['view'];family=algorithm.get('reference_family')
    if family not in FULL_FAMILIES+PCA_FAMILIES:raise NumericalError('PUBLIC_FAMILY')
    common={'view','reference_family'}
    if view=='C':
        if set(algorithm)!=common:raise NumericalError('C_ONLY_NEURAL_METADATA_FORBIDDEN')
        return {'c_mean':(105,),'c_scale':(105,)}
    base=common|{'representation','geometry_shape','neural_projection'}
    if algorithm.get('representation') not in ('raw','rms'):raise NumericalError('PUBLIC_REPRESENTATION')
    if family=='centroid' and algorithm['representation']!='rms':raise NumericalError('CENTROID_REQUIRES_RMS')
    shape=algorithm.get('geometry_shape')
    if type(shape) not in (list,tuple) or len(shape)!=3 or any(type(n) is not int or n<4 for n in shape):
        raise NumericalError('PUBLIC_GEOMETRY')
    d=math.prod(shape)
    if d<256:raise NumericalError('PUBLIC_FULL_GRID_REQUIRED')
    fields={'n_mean':(d,),'n_scale':(d,)}
    if family in FULL_FAMILIES:
        if set(algorithm)!=base or algorithm.get('neural_projection')!='full':
            raise NumericalError('UNUSED_PCA_FIELDS_FORBIDDEN')
    else:
        if set(algorithm)!=base|{'pca_rank','pca_zero_columns'} or algorithm.get('neural_projection')!='PCA':
            raise NumericalError('PUBLIC_SELECTED_PCA_REQUIRED')
        rank=algorithm['pca_rank']
        if type(rank) is not int or rank not in (64,256):raise NumericalError('PUBLIC_PCA_RANK')
        zeros=algorithm['pca_zero_columns']
        if type(zeros) not in (tuple,list) or len(zeros)>rank or any(type(k) is not int or k<0 or k>=rank for k in zeros) or list(zeros)!=sorted(set(zeros)):
            raise NumericalError('PUBLIC_PCA_ZERO_COLUMNS')
        fields.update({'pca_mean':(d,),'pca_components':(d,rank),'score_mean':(rank,),'score_scale':(rank,)})
    if view=='NC':fields.update({'c_mean':(105,),'c_scale':(105,)})
    return fields


@dataclass(frozen=True)
class PublicTransform:
    algorithm: object
    parameters: object

    def to_dict(self,*,limits):
        _validate(self,limits)
        total=sum(a.size for a in self.parameters.values())
        _limit(limits,total,128*total+16384,'public_JSON_encoding')
        return {'schema':SCHEMA,'algorithm':_plain_algorithm(self.algorithm),
                'parameters':{name:{'shape':list(a.shape),'dtype':'float64','data':a.reshape(-1).tolist()}
                              for name,a in self.parameters.items()}}


def _validate(dto,limits):
    np=numpy_api()
    if type(dto) is not PublicTransform or type(dto.parameters) is not MappingProxyType:
        raise NumericalError('PUBLIC_DTO_TYPE')
    spec=_spec(dto.algorithm)
    if set(dto.parameters)!=set(spec):raise NumericalError('PUBLIC_PARAMETER_FIELDS')
    total=sum(math.prod(s) for s in spec.values());_limit(limits,total,16*total+16384,'public_DTO_validation')
    for name,shape in spec.items():
        a=_array(dto.parameters[name],limits)
        if a.shape!=shape or a.flags.writeable or _exact_backing(a) is None:
            raise NumericalError('PUBLIC_PARAMETER_SHAPE_OR_BACKING')
        if name.endswith('_scale') and np.any(a<=0):raise NumericalError('PUBLIC_NONPOSITIVE_SCALE')
    if 'pca_components' in spec:
        zeros=tuple(dto.algorithm['pca_zero_columns'])
        if zeros and np.any(dto.parameters['pca_components'][:,zeros]!=0):
            raise NumericalError('PUBLIC_ZERO_COMPONENT_CONVENTION')
    return spec


def project_transform(bank,reference_family,*,pca_rank=None,limits):
    np=numpy_api()
    if type(bank) is not ViewBank:raise NumericalError('TRUSTED_VIEW_BANK_TYPE_REQUIRED')
    if reference_family not in FULL_FAMILIES+PCA_FAMILIES:raise NumericalError('PUBLIC_FAMILY')
    if bank.view not in ('N','C','NC'):raise NumericalError('PRIVATE_BANK_VIEW')
    alg={'view':bank.view,'reference_family':reference_family};params={}
    if bank.view=='C':
        if pca_rank is not None:raise NumericalError('C_ONLY_PCA_FORBIDDEN')
    else:
        alg.update({'representation':bank.representation,'geometry_shape':tuple(bank.geometry_shape)})
        params.update({'n_mean':bank.n_scaler.mean,'n_scale':bank.n_scaler.scale})
        if reference_family in FULL_FAMILIES:
            if pca_rank is not None:raise NumericalError('UNUSED_PCA_REQUEST_FORBIDDEN')
            alg['neural_projection']='full'
        else:
            if type(pca_rank) is not int or pca_rank not in (64,256) or bank.pca is None:
                raise NumericalError('SELECTED_FULL_BANK_REQUIRED')
            if bank.pca.components.shape[1]!=256 or bank.pca.eigenvalues.shape!=(256,):
                raise NumericalError('PRIVATE_BANK_NOT_FULL256')
            scaler=bank.score_scaler64 if pca_rank==64 else bank.score_scaler256
            if scaler is None:raise NumericalError('SELECTED_SCORE_SCALER_REQUIRED')
            alg.update({'neural_projection':'PCA','pca_rank':pca_rank,
                        'pca_zero_columns':tuple(int(k) for k in np.flatnonzero(bank.pca.eigenvalues[:pca_rank]==0))})
            params.update({'pca_mean':bank.pca.mean,'pca_components':bank.pca.components[:,:pca_rank],
                           'score_mean':scaler.mean,'score_scale':scaler.scale})
    if bank.view in ('C','NC'):
        params.update({'c_mean':bank.c_scaler.mean,'c_scale':bank.c_scaler.scale})
    # No private metadata, fit IDs, cache keys, paths, receipts or unused child state is read/exported.
    spec=_spec(alg)
    if set(params)!=set(spec):raise NumericalError('PRIVATE_SELECTED_PARAMETER_FIELDS')
    _limit(limits,sum(a.size for a in params.values()),16*sum(a.size for a in params.values())+16384,'public_projection')
    frozen={k:_public_array(a,limits) for k,a in params.items()}
    dto=PublicTransform(MappingProxyType(alg),MappingProxyType(frozen));_validate(dto,limits)
    return dto


def parameter_digest(dto,*,limits):
    _validate(dto,limits)
    if sys.byteorder!='little':raise NumericalError('PUBLIC_NUMERIC_ENDIAN_BINDING_REQUIRED')
    digest=hashlib.sha256()
    digest.update(json.dumps({'schema':SCHEMA,'algorithm':_plain_algorithm(dto.algorithm)},sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    for name in sorted(dto.parameters):
        a=dto.parameters[name]
        digest.update(json.dumps([name,list(a.shape),'float64-le'],separators=(',',':')).encode())
        digest.update(memoryview(a).cast('B'))
    return digest.hexdigest()


def _decode_array(value,shape,*,limits):
    np=numpy_api()
    if type(value) is not dict or set(value)!={'shape','dtype','data'} or value['dtype']!='float64' or value['shape']!=list(shape):
        raise NumericalError('PUBLIC_ARRAY_SCHEMA')
    count=math.prod(shape);_limit(limits,count,64*count+4096,'public_array_decoding')
    if type(value['data']) is not list or len(value['data'])!=count:
        raise NumericalError('PUBLIC_ARRAY_EXTENT')
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in value['data']):
        raise NumericalError('PUBLIC_ARRAY_NUMBERS')
    arr=np.asarray(value['data'],dtype=np.float64).reshape(shape)
    return _public_array(arr,limits)


def from_dict(value,*,limits,expected_digest):
    if type(expected_digest) is not str or len(expected_digest)!=64:
        raise NumericalError('EXPECTED_PUBLIC_DIGEST_REQUIRED')
    try:int(expected_digest,16)
    except ValueError as exc:raise NumericalError('EXPECTED_PUBLIC_DIGEST_REQUIRED') from exc
    if type(value) is not dict or set(value)!={'schema','algorithm','parameters'} or value['schema']!=SCHEMA:
        raise NumericalError('PUBLIC_DTO_SCHEMA')
    alg=value['algorithm'];spec=_spec(alg)
    if type(value['parameters']) is not dict or set(value['parameters'])!=set(spec):
        raise NumericalError('PUBLIC_PARAMETER_FIELDS')
    total=sum(math.prod(s) for s in spec.values());_limit(limits,total,128*total+16384,'public_DTO_decoding')
    pars={k:_decode_array(value['parameters'][k],shape,limits=limits) for k,shape in spec.items()}
    alg=MappingProxyType({k:(tuple(v) if type(v) is list else v) for k,v in alg.items()})
    dto=PublicTransform(alg,MappingProxyType(pars));_validate(dto,limits)
    if parameter_digest(dto,limits=limits)!=expected_digest.lower():
        raise NumericalError('PUBLIC_PARAMETER_DIGEST_MISMATCH')
    return dto


def from_json(body,*,limits,expected_digest,max_bytes):
    if type(body) not in (str,bytes) or type(max_bytes) is not int or max_bytes<1:
        raise NumericalError('PUBLIC_JSON_ARGUMENTS')
    if len(body)>max_bytes:raise NumericalError('PUBLIC_JSON_BYTE_CAP')
    if type(body) is str:_limit(limits,max(1,len(body)),4*len(body)+16384,'public_UTF8_encode')
    raw=body.encode('utf-8') if type(body) is str else body
    if len(raw)>max_bytes:raise NumericalError('PUBLIC_JSON_BYTE_CAP')
    _limit(limits,max(1,len(raw)),128*len(raw)+16384,'public_JSON_parse')
    def unique(pairs):
        out={}
        for key,val in pairs:
            if key in out:raise NumericalError('PUBLIC_JSON_DUPLICATE_KEY')
            out[key]=val
        return out
    def reject_constant(x):raise NumericalError('PUBLIC_JSON_NONFINITE_CONSTANT')
    try:value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=reject_constant)
    except NumericalError:raise
    except (ValueError,UnicodeError,RecursionError) as exc:raise NumericalError('PUBLIC_JSON_PARSE') from exc
    return from_dict(value,limits=limits,expected_digest=expected_digest)


def apply_transform(dto,neural,context,*,limits):
    np=numpy_api();_validate(dto,limits);alg=dto.algorithm;p=dto.parameters;view=alg['view'];blocks=[];n=None
    if view=='C' and neural is not None:raise NumericalError('C_ONLY_NEURAL_INPUT_FORBIDDEN')
    if view=='N' and context is not None:raise NumericalError('N_ONLY_C_INPUT_FORBIDDEN')
    if view in ('N','NC'):
        _array(neural,limits)
        if neural.ndim!=2 or neural.shape[1]!=len(p['n_mean']):raise NumericalError('PUBLIC_N_INPUT_SHAPE')
        n=neural.shape[0];_limit(limits,6*neural.size,48*neural.size+16384,'public_neural_transform')
        x=neural if alg['representation']=='raw' else rms_rows(neural,limits=limits)
        z=(x-p['n_mean'])/p['n_scale']
        if alg['neural_projection']=='full':block=z/math.sqrt(neural.shape[1])
        else:
            rank=alg['pca_rank'];_limit(limits,neural.size+4*n*rank,8*(neural.size+4*n*rank)+16384,'public_PCA_prediction')
            scores=(z-p['pca_mean'])@p['pca_components']
            block=((scores-p['score_mean'])/p['score_scale'])/math.sqrt(rank)
        blocks.append(block)
    if view in ('C','NC'):
        _array(context,limits)
        if context.ndim!=2 or context.shape[1]!=105 or (n is not None and n!=context.shape[0]):
            raise NumericalError('PUBLIC_C_INPUT_SHAPE')
        _limit(limits,3*context.size,24*context.size+16384,'public_C_transform')
        blocks.append(((context-p['c_mean'])/p['c_scale'])/math.sqrt(105))
    total=sum(a.size for a in blocks);_limit(limits,2*total,16*total+16384,'public_feature_join')
    result=blocks[0] if len(blocks)==1 else np.concatenate(blocks,axis=1)
    return _public_array(result,limits)
