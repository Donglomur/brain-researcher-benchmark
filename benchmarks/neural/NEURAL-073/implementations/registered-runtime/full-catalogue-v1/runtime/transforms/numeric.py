"""Full NEURAL-073 transform/ridge/centroid math; explicit in-memory operands only.

These mathematical calls do not authorize authentic execution. The owner admits
scope, source, operands, environment and process resources before invoking them.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from .dependency import numpy_api

SCHEMA = 'n073_transform_numeric_v1'
CLASSES = 25


class NumericalError(ValueError):
    pass


@dataclass(frozen=True)
class NumericLimits:
    max_elements: int
    max_workspace_bytes: int

    def require(self, elements, workspace_bytes, operation):
        if (type(self.max_elements) is not int or type(self.max_workspace_bytes) is not int
                or self.max_elements <= 0 or self.max_workspace_bytes <= 0):
            raise NumericalError('INVALID_NUMERIC_LIMITS')
        if elements < 0 or workspace_bytes < 0:
            raise NumericalError('INVALID_RESOURCE_ESTIMATE')
        if elements > self.max_elements or workspace_bytes > self.max_workspace_bytes:
            raise NumericalError('NUMERICAL_CAPACITY:' + operation)


def _limits(limits, elements, workspace, operation):
    if not isinstance(limits, NumericLimits):
        raise NumericalError('EXPLICIT_NUMERIC_LIMITS_REQUIRED')
    limits.require(int(elements), int(workspace), operation)


def _finite(x, label):
    np = numpy_api()
    if not np.all(np.isfinite(x)):
        raise NumericalError('NONFINITE:' + label)
    return x


def _matrix(x, limits, name='matrix'):
    np = numpy_api()
    if type(x) is not np.ndarray or x.dtype != np.dtype('float64') or x.ndim != 2:
        raise NumericalError('EXACT_FLOAT64_MATRIX:' + name)
    if min(x.shape) < 1:
        raise NumericalError('EMPTY:' + name)
    _limits(limits, x.size, 8 * x.size, name)
    return _finite(x, name)


def _vector(x, n, limits, name='vector'):
    np = numpy_api()
    if type(x) is not np.ndarray or x.dtype != np.dtype('float64') or x.shape != (n,):
        raise NumericalError('EXACT_FLOAT64_VECTOR:' + name)
    _limits(limits, n, 8 * n, name)
    return _finite(x, name)


def _weights(w, n, limits):
    np = numpy_api()
    _vector(w, n, limits, 'weights')
    if np.any(w <= 0):
        raise NumericalError('NONPOSITIVE_WEIGHT')
    total = math.fsum(float(v) for v in w)
    if not math.isfinite(total) or abs(total - 1.0) > 1e-12:
        raise NumericalError('WEIGHTS_NOT_NORMALIZED')
    result=w.copy()
    for _ in range(4):
        total=math.fsum(float(v) for v in result)
        if total==1.0:
            return _finite(result,'normalized_weights')
        result=result/total
    raise NumericalError('WEIGHT_NORMALIZATION_NOT_IDEMPOTENT')


def _freeze(x):
    np = numpy_api()
    x = _finite(x, 'state')
    # Bytes backing cannot be made writable by setflags(write=True).
    return np.frombuffer(x.tobytes(order='C'), dtype=np.float64).reshape(x.shape)


def _digest(x):
    return hashlib.sha256(x.tobytes(order='C')).hexdigest()


def _identity(dependency_key, fit_record_ids, n):
    if not isinstance(dependency_key, str) or len(dependency_key) != 64:
        raise NumericalError('DEPENDENCY_KEY_SHA256_REQUIRED')
    try:
        int(dependency_key, 16)
    except ValueError as exc:
        raise NumericalError('DEPENDENCY_KEY_SHA256_REQUIRED') from exc
    if not isinstance(fit_record_ids, (tuple, list)) or len(fit_record_ids) != n:
        raise NumericalError('FIT_IDS_EXTENT')
    ids = tuple(fit_record_ids)
    if n<1 or any(not isinstance(x, str) or not x or len(x)>128 for x in ids) or len(set(ids))!=n:
        raise NumericalError('FIT_IDS_UNIQUE_OPAQUE_STRINGS')
    return dependency_key.lower(), ids


def _metadata(dependency_key, fit_record_ids, weights, work, certificate=None):
    key, ids = _identity(dependency_key, fit_record_ids, len(weights))
    return MappingProxyType({'dependency_key': key, 'fit_record_ids': ids,
                             'weight_digest': _digest(weights),
                             'work': MappingProxyType(dict(work)),
                             'certificate': MappingProxyType(dict(certificate or {}))})


def rms_rows(x, *, limits):
    np = numpy_api()
    _matrix(x, limits)
    _limits(limits, 4 * x.size + 3 * x.shape[0], 8 * (4*x.size+3*x.shape[0]), 'rms_rows')
    peak = np.max(np.abs(x), axis=1)
    safe = np.where(peak == 0.0, 1.0, peak)
    scaled = x / safe[:, None]
    rms = safe * np.sqrt(np.mean(scaled * scaled, axis=1))
    out = x / np.where(rms == 0.0, 1.0, rms)[:, None]
    return _freeze(_finite(out, 'rms_rows'))


def _rms1(x):
    np = numpy_api()
    peak = float(np.max(np.abs(x)))
    if peak == 0.0:
        return 0.0
    return float(peak * math.sqrt(float(np.mean((x / peak) ** 2))))


def _quantiles(sorted_x, probabilities):
    out = []
    for p in probabilities:
        pos = (len(sorted_x) - 1) * p
        low = int(math.floor(pos)); high = int(math.ceil(pos)); frac = pos - low
        out.append((1-frac) * float(sorted_x[low]) + frac * float(sorted_x[high]))
    return out


def c_descriptor(volume, *, limits):
    np = numpy_api()
    if type(volume) is not np.ndarray or volume.dtype != np.dtype('float64') or volume.ndim != 3:
        raise NumericalError('C_REQUIRES_FLOAT64_3D')
    if min(volume.shape) < 4:
        raise NumericalError('C_AXIS_SMALLER_THAN_FOUR')
    d = volume.size
    _limits(limits, 32*d + 2048, 256*d + 16384, 'C_descriptor')
    _finite(volume, 'volume')
    x = volume.reshape(-1, order='C')
    mean = float(np.sum(x / d)); center = _finite(x - mean, 'center')
    std = _rms1(center); rms = _rms1(x)
    z = center / (std if std else 1.0)
    skew = float(np.mean(z**3)) if std else 0.0
    kurt = float(np.mean(z**4)-3.0) if std else 0.0
    nonzero = x != 0.0
    values = [float(np.count_nonzero(nonzero)/d), float(np.count_nonzero(x>0)/d),
              float(np.count_nonzero(x<0)/d), mean, std, rms,
              float(np.sum(np.abs(x)/d)), skew, kurt]
    values += _quantiles(np.sort(x), [0,.01,.05,.10,.25,.5,.75,.90,.95,.99,1])
    absx = np.abs(x)
    values += _quantiles(np.sort(absx), [.10,.25,.5,.75,.90,.95,.99])
    values += [float(np.count_nonzero(absx > threshold)/d) for threshold in (1,2,3,4,5)]
    shape = volume.shape
    axes = [np.minimum(3, (4*np.arange(a, dtype=np.int64))//a) for a in shape]
    for a in range(4):
        for b in range(4):
            for c in range(4):
                block = volume[np.ix_(axes[0]==a, axes[1]==b, axes[2]==c)]
                values.append(float(np.count_nonzero(block)/block.size))
    indices = np.flatnonzero(nonzero)
    if len(indices):
        coords = np.column_stack((indices//(shape[1]*shape[2]),
                                  (indices//shape[2]) % shape[1], indices % shape[2])).astype(np.float64)
        coords = 2*coords/np.asarray([a-1 for a in shape], dtype=np.float64)-1
        centroid = np.mean(coords, axis=0)
        centered = coords-centroid
        cov = centered.T @ centered / len(indices)
        values += centroid.tolist() + [float(cov[a,b]) for a,b in ((0,0),(0,1),(0,2),(1,1),(1,2),(2,2))]
    else:
        values += [0.0]*9
    if len(values) != 105:
        raise NumericalError('C_FEATURE_ORDER')
    return _freeze(np.asarray(values, dtype=np.float64))


def batch_c_descriptor(volumes, *, limits):
    np = numpy_api()
    if not isinstance(volumes, (tuple,list)) or not volumes:
        raise NumericalError('EXPLICIT_NONEMPTY_VOLUME_SEQUENCE_REQUIRED')
    _limits(limits, 105*len(volumes), 8*105*len(volumes), 'C_batch_output')
    return _freeze(np.stack([c_descriptor(x, limits=limits) for x in volumes]))


@dataclass(frozen=True)
class Scaler:
    mean: object
    scale: object
    metadata: object

    def to_dict(self): return to_dict(self)


def fit_scaler(x, weights, *, dependency_key, fit_record_ids, limits):
    np = numpy_api(); _matrix(x, limits); n,d=x.shape
    w=_weights(weights,n,limits); _identity(dependency_key,fit_record_ids,n)
    _limits(limits, 4*n*d+6*d+n, 8*(4*n*d+6*d+n), 'fit_scaler')
    mean=_finite(np.sum(x*w[:,None],axis=0),'weighted_mean')
    centered=_finite(x-mean,'centered')
    var=_finite(np.sum(centered*centered*w[:,None],axis=0),'weighted_variance')
    if np.any(var < 0): raise NumericalError('NEGATIVE_VARIANCE')
    scale=np.sqrt(var); scale=np.where(scale==0.0,1.0,scale)
    meta=_metadata(dependency_key,fit_record_ids,w,{'scaler_fits':1,'fit_rows':n,'input_dimensions':d,'input_digest_bytes':8*n*d},
                   {'constant_coordinates':int(np.count_nonzero(var==0)),'fit_input_digest':_digest(x)})
    return Scaler(_freeze(mean),_freeze(scale),meta)


def apply_scaler(state,x,*,limits):
    _matrix(x,limits)
    if x.shape[1] != len(state.mean): raise NumericalError('SCALER_DIMENSIONS')
    _limits(limits,2*x.size,16*x.size,'apply_scaler')
    return _freeze(_finite((x-state.mean)/state.scale,'scaled'))


@dataclass(frozen=True)
class PCA:
    mean: object
    components: object
    eigenvalues: object
    metadata: object

    def to_dict(self): return to_dict(self)


def _canonical_columns(vectors,take):
    np=numpy_api(); d,g=vectors.shape
    if g==1:
        v=vectors[:,0].copy(); pivot=int(np.argmax(np.abs(v)))
        if v[pivot]<0: v=-v
        return v[:,None]
    out=[]; threshold=64*np.finfo(np.float64).eps*max(d,g)
    for coordinate in range(d):
        v=vectors @ vectors[coordinate,:]
        for _ in range(2):
            for basis in out: v=v-float(basis@v)*basis
        norm=float(np.linalg.norm(v))
        if norm>threshold:
            v=v/norm; pivot=int(np.argmax(np.abs(v)))
            if v[pivot]<0: v=-v
            out.append(v)
            if len(out)==take: return np.column_stack(out)
    raise NumericalError('DEGENERATE_EIGENSPACE_CANONICALIZATION')


def fit_pca_primitive(x,weights,rank,*,dependency_key,fit_record_ids,limits):
    np=numpy_api(); _matrix(x,limits); n,d=x.shape
    if type(rank) is not int or rank<1 or rank>min(n-1,d):
        raise NumericalError('PCA_RANK_SUPPORT')
    w=_weights(weights,n,limits); _identity(dependency_key,fit_record_ids,n)
    m=min(n,d)
    # Conservative source-owned arrays + declared LAPACK workspace estimate.
    _limits(limits,15*m*m+8*n*d+12*d*m+8*n*rank,
            8*(15*m*m+8*n*d+12*d*m+8*n*rank),'fit_pca')
    mean=_finite(np.sum(x*w[:,None],axis=0),'PCA_mean')
    z=_finite(x-mean,'PCA_centered'); a=z*np.sqrt(w)[:,None]
    covariance=(a.T@a) if d<=n else (a@a.T)
    _finite(covariance,'PCA_covariance_or_gram')
    evals,evecs=np.linalg.eigh(covariance)
    order=np.arange(len(evals)-1,-1,-1); evals=evals[order]; evecs=evecs[:,order]
    chosen=[]; values=[]; pos=0; groups=[]
    while len(values)<rank:
        end=pos+1
        while end<len(evals) and evals[end]==evals[pos]: end+=1
        lam=float(evals[pos]); take=min(end-pos,rank-len(values))
        if lam<0: raise NumericalError('NEGATIVE_SELECTED_PCA_EIGENVALUE')
        if lam==0:
            block=np.zeros((d,take),dtype=np.float64)
        else:
            eigenspace=evecs[:,pos:end] if d<=n else a.T@evecs[:,pos:end]/math.sqrt(lam)
            block=_canonical_columns(eigenspace,take)
        chosen.append(block); values.extend([lam]*take)
        groups.append({'solver_eigenvalue':lam,'full_tied_dimension':end-pos,'selected':take})
        pos=end
    components=np.concatenate(chosen,axis=1); eigenvalues=np.asarray(values,dtype=np.float64)
    residual=a.T@(a@components)-components*eigenvalues[None,:]
    denom=max(1.0,float(np.sum(a*a)))
    eigen_res=float(np.linalg.norm(residual)/denom)
    positive=components[:,eigenvalues>0]
    orth_res=float(np.linalg.norm(positive.T@positive-np.eye(positive.shape[1])))
    if not math.isfinite(eigen_res+orth_res) or eigen_res>1e-8 or orth_res>1e-8:
        raise NumericalError('PCA_RESIDUAL_QUALIFICATION')
    cert={'normalized_eigen_residual':eigen_res,'orthogonality_residual':orth_res,
          'tie_policy':'exact_float64_eigenvalue_groups_projected_coordinate_order',
          'zero_policy':'selected_exact_zero_eigenvalue_columns_have_zero_scores',
          'solver_dimension':m,'positive_components':int(np.count_nonzero(eigenvalues>0)),
          'groups':tuple(tuple(sorted(g.items())) for g in groups)}
    meta=_metadata(dependency_key,fit_record_ids,w,{'PCA_fits':1,'fit_rows':n,'input_dimensions':d,'rank':rank},cert)
    return PCA(_freeze(mean),_freeze(components),_freeze(eigenvalues),meta)


def predict_pca(state,x,*,rank=None,limits):
    _matrix(x,limits); r=state.components.shape[1] if rank is None else rank
    if type(r) is not int or not 1<=r<=state.components.shape[1] or x.shape[1]!=len(state.mean):
        raise NumericalError('PCA_PREDICT_DIMENSIONS')
    _limits(limits,2*x.size+x.shape[0]*r,8*(2*x.size+x.shape[0]*r),'predict_pca')
    return _freeze(_finite((x-state.mean)@state.components[:,:r],'PCA_scores'))


@dataclass(frozen=True)
class Ridge:
    coefficients: object
    intercept: object
    metadata: object

    def to_dict(self): return to_dict(self)


def _labels(y,n):
    np=numpy_api()
    if type(y) is not np.ndarray or y.dtype.kind not in 'iu' or y.shape!=(n,):
        raise NumericalError('INTEGER_LABEL_VECTOR_REQUIRED')
    if set(int(k) for k in y)!=set(range(CLASSES)):
        raise NumericalError('ALL_25_TRAINING_CLASSES_REQUIRED')
    return y


def fit_ridge(x,y,weights,lam,*,dependency_key,fit_record_ids,limits,solver='auto'):
    np=numpy_api(); _matrix(x,limits); n,d=x.shape; _labels(y,n)
    if type(lam) not in (int,float) or not math.isfinite(lam) or lam<=0:
        raise NumericalError('POSITIVE_RIDGE_LAMBDA_REQUIRED')
    if solver not in ('auto','primal','dual'): raise NumericalError('RIDGE_SOLVER')
    method=('primal' if d<=n else 'dual') if solver=='auto' else solver
    m=d if method=='primal' else n
    _limits(limits,12*n*d+12*m*m+8*(n+d)*CLASSES,
            8*(12*n*d+12*m*m+8*(n+d)*CLASSES),'fit_ridge')
    w=_weights(weights,n,limits); _identity(dependency_key,fit_record_ids,n)
    targets=np.eye(CLASSES,dtype=np.float64)[y]
    xbar=np.sum(x*w[:,None],axis=0); ybar=np.sum(targets*w[:,None],axis=0)
    z=x-xbar; centered_y=targets-ybar
    a=z*np.sqrt(w)[:,None]; b=centered_y*np.sqrt(w)[:,None]
    if method=='primal':
        gram=a.T@a+float(lam)*np.eye(d); rhs=a.T@b
        coef=np.linalg.solve(_finite(gram,'ridge_gram'),_finite(rhs,'ridge_rhs'))
    else:
        gram=a@a.T+float(lam)*np.eye(n)
        dual=np.linalg.solve(_finite(gram,'ridge_gram'),b); coef=a.T@dual
    intercept=ybar-xbar@coef
    error=x@coef+intercept-targets
    gradient=x.T@(w[:,None]*error)+float(lam)*coef
    intercept_gradient=np.sum(w[:,None]*error,axis=0)
    reference=max(1.0,float(np.linalg.norm(x.T@(w[:,None]*targets))),float(lam)*float(np.linalg.norm(coef)))
    residual=float(math.hypot(float(np.linalg.norm(gradient)),float(np.linalg.norm(intercept_gradient)))/reference)
    if not math.isfinite(residual) or residual>1e-8:
        raise NumericalError('RIDGE_OPTIMALITY_RESIDUAL')
    objective=float(.5*np.sum(w[:,None]*error*error)+.5*lam*np.sum(coef*coef))
    meta=_metadata(dependency_key,fit_record_ids,w,
                   {'ridge_shared_solves':1,'output_coordinates':25,'fit_rows':n,'input_dimensions':d,'solver':method},
                   {'normalized_optimality_residual':residual,'objective':objective,'lambda':float(lam)})
    return Ridge(_freeze(coef),_freeze(intercept),meta)


def predict_ridge(state,x,*,limits):
    _matrix(x,limits)
    if x.shape[1]!=state.coefficients.shape[0]: raise NumericalError('RIDGE_DIMENSIONS')
    _limits(limits,x.size+25*x.shape[0],8*(x.size+25*x.shape[0]),'predict_ridge')
    return _freeze(_finite(x@state.coefficients+state.intercept,'ridge_scores'))


@dataclass(frozen=True)
class Centroid:
    centers: object
    metadata: object

    def to_dict(self): return to_dict(self)


def fit_centroid(x,y,weights,*,dependency_key,fit_record_ids,limits):
    np=numpy_api(); _matrix(x,limits); n,d=x.shape; _labels(y,n); w=_weights(weights,n,limits)
    _limits(limits,4*n*d+3*25*d,8*(4*n*d+3*25*d),'fit_centroid')
    _identity(dependency_key,fit_record_ids,n); means=[]
    for cls in range(CLASSES):
        mask=y==cls; mass=float(np.sum(w[mask])); means.append(np.sum(x[mask]*w[mask,None],axis=0)/mass)
    centers=np.stack(means)
    meta=_metadata(dependency_key,fit_record_ids,w,{'centroid_fit_bundles':1,'class_template_aggregations':25,'fit_rows':n,'input_dimensions':d},
                   {'all_classes_present':True,'weighted_class_mean':True})
    return Centroid(_freeze(centers),meta)


def predict_centroid(state,x,*,limits):
    np=numpy_api(); _matrix(x,limits)
    if x.shape[1]!=state.centers.shape[1]: raise NumericalError('CENTROID_DIMENSIONS')
    _limits(limits,3*x.size+3*state.centers.size+25*x.shape[0],8*(3*x.size+3*state.centers.size+25*x.shape[0]),'centroid_predict')
    # Stable scale-before-norm normalization, then a bounded dot product.
    def units(a):
        peak=np.max(np.abs(a),axis=1); z=a/np.where(peak==0,1,peak)[:,None]
        norm=np.sqrt(np.sum(z*z,axis=1)); return z/np.where(norm==0,1,norm)[:,None]
    scores=units(x)@units(state.centers).T
    return _freeze(_finite(scores,'centroid_scores'))


@dataclass(frozen=True)
class ViewBank:
    view: str
    representation: object
    geometry_shape: object
    n_scaler: object
    c_scaler: object
    pca: object
    score_scaler64: object
    score_scaler256: object
    metadata: object

    def to_dict(self): return to_dict(self)


def _component_key(parent,*parts):
    return hashlib.sha256(json.dumps([parent,*parts],separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def fit_view(neural,context,weights,*,view,representation,geometry_shape,
             dependency_key,fit_record_ids,limits,build_pca=True,
             c_dependency_key=None,prefit_c_scaler=None):
    np=numpy_api()
    if view not in ('N','C','NC'): raise NumericalError('VIEW')
    if type(build_pca) is not bool: raise NumericalError('BUILD_PCA_BOOLEAN_REQUIRED')
    if view=='C':
        if neural is not None or representation is not None or geometry_shape is not None:
            raise NumericalError('C_VIEW_NEURAL_OPERANDS_FORBIDDEN')
        _matrix(context,limits,'C'); n=context.shape[0]
    else:
        _matrix(neural,limits,'N'); n,d=neural.shape
        if (not isinstance(geometry_shape,(tuple,list)) or len(geometry_shape)!=3
                or any(type(a) is not int or a<4 for a in geometry_shape)
                or math.prod(geometry_shape)!=d or d<256):
            raise NumericalError('FULL_COMMON_GRID_BINDING_REQUIRED')
        if representation not in ('raw','rms'): raise NumericalError('REPRESENTATION')
    if view=='N' and context is not None: raise NumericalError('N_VIEW_C_OPERAND_FORBIDDEN')
    if view in ('C','NC'):
        _matrix(context,limits,'C')
        if context.shape!=(n,105): raise NumericalError('EXACT_C105_REQUIRED')
        if c_dependency_key is None: raise NumericalError('C_COMPONENT_KEY_REQUIRED')
        _identity(c_dependency_key,fit_record_ids,n)
    if view in ('N','NC') and build_pca and (n<257 or neural.shape[1]<256):
        raise NumericalError('FULL_PCA256_SUPPORT_REQUIRED')
    w=_weights(weights,n,limits); _identity(dependency_key,fit_record_ids,n)
    ns=cs=pca=score64=score256=None
    work={'N_scaler_fits':0,'C_scaler_fits':0,'PCA_fits':0,'PCA_score_scaler_fits':0,
          'fit_rows':n,'view':view}
    if view in ('N','NC'):
        represented=neural if representation=='raw' else rms_rows(neural,limits=limits)
        ns=fit_scaler(represented,w,dependency_key=_component_key(dependency_key,'N_scaler'),fit_record_ids=fit_record_ids,limits=limits)
        standardized=apply_scaler(ns,represented,limits=limits); work['N_scaler_fits']=1
        if build_pca:
            if n<257 or neural.shape[1]<256: raise NumericalError('FULL_PCA256_SUPPORT_REQUIRED')
            pca=fit_pca_primitive(standardized,w,256,dependency_key=_component_key(dependency_key,'PCA256'),fit_record_ids=fit_record_ids,limits=limits)
            train256=predict_pca(pca,standardized,limits=limits)
            score64=fit_scaler(train256[:,:64],w,dependency_key=_component_key(dependency_key,'PCA_score_scaler',64),fit_record_ids=fit_record_ids,limits=limits)
            score256=fit_scaler(train256,w,dependency_key=_component_key(dependency_key,'PCA_score_scaler',256),fit_record_ids=fit_record_ids,limits=limits)
            work['PCA_fits']=1; work['PCA_score_scaler_fits']=2
    if view in ('C','NC'):
        if prefit_c_scaler is None:
            cs=fit_scaler(context,w,dependency_key=c_dependency_key,fit_record_ids=fit_record_ids,limits=limits)
            work['C_scaler_fits']=1
        else:
            if (not isinstance(prefit_c_scaler,Scaler) or len(prefit_c_scaler.mean)!=105
                    or prefit_c_scaler.metadata['dependency_key']!=c_dependency_key.lower()
                    or prefit_c_scaler.metadata['fit_record_ids']!=tuple(fit_record_ids)
                    or prefit_c_scaler.metadata['weight_digest']!=_digest(w)
                    or prefit_c_scaler.metadata['certificate'].get('fit_input_digest')!=_digest(context)):
                raise NumericalError('C_SCALER_CACHE_DEPENDENCY_MISMATCH')
            cs=prefit_c_scaler
    meta=_metadata(dependency_key,fit_record_ids,w,work,{'complete_PCA_bank':pca is not None,'production_geometry_claim':'binding_checked_not_authentic_admission'})
    return ViewBank(view,representation,None if geometry_shape is None else tuple(geometry_shape),ns,cs,pca,score64,score256,meta)


def transform_view(state,neural,context,*,pca_rank=None,limits):
    np=numpy_api(); blocks=[]; n=None
    if state.view=='C':
        if neural is not None or pca_rank is not None: raise NumericalError('C_VIEW_NEURAL_ACCESS_FORBIDDEN')
    if state.view=='N' and context is not None: raise NumericalError('N_VIEW_C_OPERAND_FORBIDDEN')
    if state.view in ('N','NC'):
        _matrix(neural,limits,'N_query'); n=neural.shape[0]
        if neural.shape[1]!=math.prod(state.geometry_shape): raise NumericalError('NEURAL_QUERY_GEOMETRY')
        represented=neural if state.representation=='raw' else rms_rows(neural,limits=limits)
        standardized=apply_scaler(state.n_scaler,represented,limits=limits)
        if pca_rank is None:
            blocks.append(standardized/math.sqrt(neural.shape[1]))
        else:
            if pca_rank not in (64,256) or state.pca is None: raise NumericalError('COMPLETE_PCA_BANK_REQUIRED')
            scores=predict_pca(state.pca,standardized,rank=pca_rank,limits=limits)
            scaler=state.score_scaler64 if pca_rank==64 else state.score_scaler256
            blocks.append(apply_scaler(scaler,scores,limits=limits)/math.sqrt(pca_rank))
    if state.view in ('C','NC'):
        _matrix(context,limits,'C_query')
        if context.shape[1]!=105 or (n is not None and context.shape[0]!=n): raise NumericalError('C_QUERY_DIMENSIONS')
        blocks.append(apply_scaler(state.c_scaler,context,limits=limits)/math.sqrt(105))
    total=sum(b.size for b in blocks); _limits(limits,2*total,16*total,'view_concatenation')
    return _freeze(np.concatenate(blocks,axis=1) if len(blocks)>1 else blocks[0])


def _plain(value):
    if isinstance(value,(dict,MappingProxyType)):
        return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [_plain(v) for v in value]
    if value is None or type(value) in (str,bool,int): return value
    if type(value) is float and math.isfinite(value): return value
    raise NumericalError('NONPLAIN_STATE_METADATA')


def _frozen_json(value,depth=0):
    if depth>16: raise NumericalError('STATE_METADATA_DEPTH')
    if type(value) is dict:
        if any(type(k) is not str for k in value): raise NumericalError('STATE_METADATA_KEY')
        return MappingProxyType({k:_frozen_json(v,depth+1) for k,v in value.items()})
    if type(value) is list: return tuple(_frozen_json(v,depth+1) for v in value)
    if value is None or type(value) in (str,bool,int): return value
    if type(value) is float and math.isfinite(value): return value
    raise NumericalError('STATE_METADATA_VALUE')


def _array_dict(x):
    return {'shape':list(x.shape),'dtype':'float64','data':x.reshape(-1).tolist()}


def to_dict(state):
    if isinstance(state,Scaler): arrays={'mean':state.mean,'scale':state.scale}; kind='scaler'; children={}; settings={}
    elif isinstance(state,PCA): arrays={'mean':state.mean,'components':state.components,'eigenvalues':state.eigenvalues}; kind='pca'; children={}; settings={}
    elif isinstance(state,Ridge): arrays={'coefficients':state.coefficients,'intercept':state.intercept}; kind='ridge'; children={}; settings={}
    elif isinstance(state,Centroid): arrays={'centers':state.centers}; kind='centroid'; children={}; settings={}
    elif isinstance(state,ViewBank):
        arrays={}; kind='view'; settings={'view':state.view,'representation':state.representation,'geometry_shape':None if state.geometry_shape is None else list(state.geometry_shape)}
        children={k:(None if getattr(state,k) is None else to_dict(getattr(state,k))) for k in ('n_scaler','c_scaler','pca','score_scaler64','score_scaler256')}
    else: raise NumericalError('STATE_TYPE')
    return {'schema':SCHEMA,'kind':kind,'metadata':_plain(state.metadata),'arrays':{k:_array_dict(a) for k,a in arrays.items()},'children':children,'settings':settings}


def from_dict(value,*,limits):
    """Validate safe state structure; owner must authenticate the fit receipt."""
    np=numpy_api(); running=[0]
    def load(v):
        if type(v) is not dict or set(v)!={'schema','kind','metadata','arrays','children','settings'} or v['schema']!=SCHEMA:
            raise NumericalError('STATE_SCHEMA')
        kind=v['kind']; expected={'scaler':{'mean','scale'},'pca':{'mean','components','eigenvalues'},'ridge':{'coefficients','intercept'},'centroid':{'centers'},'view':set()}
        if kind not in expected or type(v['arrays']) is not dict or set(v['arrays'])!=expected[kind]: raise NumericalError('STATE_ARRAY_FIELDS')
        meta=v['metadata']
        if type(meta) is not dict or set(meta)!={'dependency_key','fit_record_ids','weight_digest','work','certificate'}:
            raise NumericalError('STATE_METADATA_FIELDS')
        if type(meta['fit_record_ids']) is not list: raise NumericalError('STATE_FIT_IDS')
        _identity(meta['dependency_key'],meta['fit_record_ids'],len(meta['fit_record_ids']))
        if type(meta['weight_digest']) is not str or len(meta['weight_digest'])!=64: raise NumericalError('STATE_WEIGHT_DIGEST')
        try: int(meta['weight_digest'],16)
        except ValueError as exc: raise NumericalError('STATE_WEIGHT_DIGEST') from exc
        if type(meta['work']) is not dict or type(meta['certificate']) is not dict: raise NumericalError('STATE_METADATA_FIELDS')
        if meta['work'].get('fit_rows')!=len(meta['fit_record_ids']): raise NumericalError('STATE_FIT_ROW_COUNT')
        metadata=_frozen_json(meta); arrays={}
        for name,item in v['arrays'].items():
            if type(item) is not dict or set(item)!={'shape','dtype','data'} or item['dtype']!='float64': raise NumericalError('STATE_ARRAY_SCHEMA')
            shape=item['shape']
            if type(shape) is not list or not 1<=len(shape)<=2 or any(type(k) is not int or k<=0 for k in shape): raise NumericalError('STATE_ARRAY_SHAPE')
            count=math.prod(shape); running[0]+=count
            _limits(limits,running[0],24*running[0],'state_decode')
            if type(item['data']) is not list or len(item['data'])!=count or any(type(x) not in (int,float) or not math.isfinite(x) for x in item['data']): raise NumericalError('STATE_ARRAY_DATA')
            arrays[name]=_freeze(np.asarray(item['data'],dtype=np.float64).reshape(shape))
        if kind!='view' and (v['children']!={} or v['settings']!={}): raise NumericalError('STATE_UNEXPECTED_CHILDREN')
        if kind=='scaler':
            if arrays['mean'].ndim!=1 or arrays['scale'].shape!=arrays['mean'].shape or np.any(arrays['scale']<=0): raise NumericalError('STATE_SCALER_DIMENSIONS')
            digest=meta['certificate'].get('fit_input_digest')
            if type(digest) is not str or len(digest)!=64: raise NumericalError('STATE_SCALER_INPUT_DIGEST')
            try: int(digest,16)
            except ValueError as exc: raise NumericalError('STATE_SCALER_INPUT_DIGEST') from exc
            return Scaler(arrays['mean'],arrays['scale'],metadata)
        if kind=='ridge':
            if arrays['coefficients'].ndim!=2 or arrays['coefficients'].shape[1]!=25 or arrays['intercept'].shape!=(25,): raise NumericalError('STATE_RIDGE_DIMENSIONS')
            residual=meta['certificate'].get('normalized_optimality_residual')
            if type(residual) not in (int,float) or not 0<=residual<=1e-8: raise NumericalError('STATE_RIDGE_CERTIFICATE')
            return Ridge(arrays['coefficients'],arrays['intercept'],metadata)
        if kind=='centroid':
            if arrays['centers'].ndim!=2 or arrays['centers'].shape[0]!=25: raise NumericalError('STATE_CENTROID_DIMENSIONS')
            return Centroid(arrays['centers'],metadata)
        if kind=='pca':
            a=arrays; comp=a['components']; ev=a['eigenvalues']
            if comp.ndim!=2 or a['mean'].shape!=(comp.shape[0],) or ev.shape!=(comp.shape[1],) or np.any(ev<0) or np.any(ev[:-1]<ev[1:]): raise NumericalError('STATE_PCA_DIMENSIONS')
            if np.any(comp[:,ev==0]!=0): raise NumericalError('STATE_PCA_ZERO_COMPONENT')
            for field in ('normalized_eigen_residual','orthogonality_residual'):
                val=meta['certificate'].get(field)
                if type(val) not in (int,float) or not 0<=val<=1e-8: raise NumericalError('STATE_PCA_CERTIFICATE')
            pos=comp[:,ev>0]
            if float(np.linalg.norm(pos.T@pos-np.eye(pos.shape[1])))>1e-8: raise NumericalError('STATE_PCA_ORTHOGONALITY')
            return PCA(a['mean'],comp,ev,metadata)
        settings=v['settings']; children=v['children']
        if type(settings) is not dict or set(settings)!={'view','representation','geometry_shape'} or type(children) is not dict or set(children)!={'n_scaler','c_scaler','pca','score_scaler64','score_scaler256'}: raise NumericalError('STATE_VIEW_FIELDS')
        for key,child in children.items():
            expected_kind='pca' if key=='pca' else 'scaler'
            if child is not None and (type(child) is not dict or child.get('kind')!=expected_kind):
                raise NumericalError('STATE_CHILD_KIND')
        ch={k:(None if z is None else load(z)) for k,z in children.items()}; view=settings['view']; geom=settings['geometry_shape']; rep=settings['representation']
        if view not in ('N','C','NC'): raise NumericalError('STATE_VIEW')
        if view=='C':
            if geom is not None or rep is not None or any(ch[k] is not None for k in ('n_scaler','pca','score_scaler64','score_scaler256')): raise NumericalError('STATE_C_ONLY_LEAK')
        else:
            if type(geom) is not list or len(geom)!=3 or any(type(k) is not int or k<4 for k in geom) or math.prod(geom)<256 or rep not in ('raw','rms') or not isinstance(ch['n_scaler'],Scaler) or len(ch['n_scaler'].mean)!=math.prod(geom): raise NumericalError('STATE_N_GEOMETRY')
        if view=='N' and ch['c_scaler'] is not None: raise NumericalError('STATE_N_C_CHILD')
        if view in ('C','NC') and (not isinstance(ch['c_scaler'],Scaler) or len(ch['c_scaler'].mean)!=105): raise NumericalError('STATE_C105_CHILD')
        if ch['pca'] is None:
            if ch['score_scaler64'] is not None or ch['score_scaler256'] is not None: raise NumericalError('STATE_PCA_CHILDREN')
        else:
            if not isinstance(ch['pca'],PCA) or ch['pca'].components.shape!=(math.prod(geom),256) or not isinstance(ch['score_scaler64'],Scaler) or len(ch['score_scaler64'].mean)!=64 or not isinstance(ch['score_scaler256'],Scaler) or len(ch['score_scaler256'].mean)!=256: raise NumericalError('STATE_FULL_PCA_BANK')
        for child in ch.values():
            if child is not None and (child.metadata['fit_record_ids']!=metadata['fit_record_ids'] or child.metadata['weight_digest']!=metadata['weight_digest']): raise NumericalError('STATE_CHILD_TRAINING_CUSTODY')
        return ViewBank(view,rep,None if geom is None else tuple(geom),ch['n_scaler'],ch['c_scaler'],ch['pca'],ch['score_scaler64'],ch['score_scaler256'],metadata)
    return load(value)
