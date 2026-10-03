"""Private source-derived algebra, independently composed; no oracle imports.

The declared normalized gelsd rank convention is shared, not an independent
linear-algebra dependency. Integration, model construction and output replay
are separately implemented here from the public equations.
"""
import math

import numpy as np
from scipy import linalg

EPS = np.finfo('f8').eps
ASSUMPTIONS = ('already_image_reference', 'sample_time_reference')
ESTIMATORS = ('logan', 'ma1')


def norm(values): return math.hypot(*map(float, values))


def composite(cortical):
    result=[]
    for row in cortical:
        scale=max(map(abs,row))
        result.append(0. if scale==0 else scale*(math.fsum(float(v/scale) for v in row)/len(row)))
    return np.asarray(result,dtype=np.float64)


def primitives(starts, ends, ct, times_s, plasma, parent):
    starts, ends, ct = (np.asarray(v, dtype=np.float64) for v in (starts, ends, ct))
    mid = (starts/60+ends/60)*.5
    width = (ends-starts)/60
    it = np.array([math.fsum(float(ct[j]*width[j]) for j in range(i))+float(ct[i]*width[i])*.5
                   for i in range(len(ct))], dtype=np.float64)
    times = np.asarray(times_s, dtype=np.float64)/60
    values = np.asarray(plasma)*np.asarray(parent)
    if np.any((np.asarray(plasma)>0)&(np.asarray(parent)>0)&(values==0)):
        raise ValueError('source input product numerical underflow')
    parents = np.column_stack((values, values*np.exp(math.log(2)*np.asarray(times_s)/6586.2)))
    anchor = bool(times[0] > 0)
    if anchor:
        times = np.concatenate(([0.], times)); parents = np.vstack((np.zeros(2), parents))
    ip = np.zeros((len(ct), 2)); defined = np.zeros((len(ct), 2), dtype=bool)
    for i, target in enumerate(mid):
        if len(times) < 2 or target < times[0] or target > times[-1]: continue
        for arm in range(2):
            pieces = []
            for j in range(len(times)-1):
                if target <= times[j]: break
                delta = min(float(target),float(times[j+1]))-float(times[j])
                fraction = delta/float(times[j+1]-times[j])
                height = (1-fraction)*float(parents[j,arm])+fraction*float(parents[j+1,arm])
                pieces.append((float(parents[j,arm])*.5+height*.5)*delta)
            ip[i,arm] = math.fsum(pieces); defined[i,arm] = True
    if not all(np.all(np.isfinite(v)) for v in (mid,it,parents,ip)): raise ValueError('source arithmetic overflow')
    return dict(midpoint_min=mid,tissue_integral=it,knot_time_s=times*60,parent_input=parents,
                plasma_integral=ip,plasma_integral_defined=defined,fit_mask=mid>=30,inserted_anchor=anchor)


def empty(status, n):
    return dict(status=status,n_fit_rows=n,rank=None,coefficients=None,column_scales=None,
                singular_values=None,residual_rss=None,rss_status='unavailable',vt=None,nonpositive_vt=None)


def rss(design, response, coefficients):
    with np.errstate(over='ignore', invalid='ignore'):
        residual = np.asarray(response)-np.asarray(design)@np.asarray(coefficients)
    if not np.all(np.isfinite(residual)): return None,'numerical_overflow'
    magnitude = norm(residual); squared = magnitude*magnitude
    if not math.isfinite(squared): return None,'numerical_overflow'
    if magnitude and squared == 0: return None,'numerical_underflow'
    return squared,'ok'


def denominator_supported(coeff):
    scale = max(abs(float(v)) for v in coeff)
    return bool(scale and abs(float(coeff[1]))/scale > 64*EPS)


def replay(estimator, coeff, source_support=True):
    if estimator == 'ma1' and not source_support:
        return dict(status='ma1_denominator_unresolved',vt=None,nonpositive_vt=None)
    if estimator == 'logan': vt=float(coeff[0])
    else:
        if coeff[1] == 0: return dict(status='numerical_failure',vt=None,nonpositive_vt=None)
        vt=-float(coeff[0])/float(coeff[1])
        if not math.isfinite(vt) or (coeff[0] != 0 and vt == 0):
            return dict(status='numerical_failure',vt=None,nonpositive_vt=None)
    return dict(status='ok',vt=vt,nonpositive_vt=bool(vt<=0))


def fit(ct, primitive, arm, estimator):
    mask=primitive['fit_mask']; n=int(mask.sum())
    if not primitive['plasma_integral_defined'][mask,arm].all(): return empty('input_time_support_unavailable',n)
    if n<3:return empty('insufficient_fit_rows',n)
    tissue=np.asarray(ct)[mask]; it=primitive['tissue_integral'][mask]; ip=primitive['plasma_integral'][mask,arm]
    if estimator=='logan' and np.any(tissue<=0):return empty('nonpositive_tissue_for_logan',n)
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        x=np.column_stack((ip/tissue,np.ones(n))) if estimator=='logan' else np.column_stack((ip,it))
        y=it/tissue if estimator=='logan' else tissue
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):return empty('numerical_failure',n)
    scales=np.array([norm(x[:,j]) for j in range(2)])
    if not np.all(np.isfinite(scales)):return empty('numerical_failure',n)
    if np.any(scales==0):return empty('zero_design_column',n)
    try:
        c,_,rank,s=linalg.lstsq(np.ascontiguousarray(x/scales),np.ascontiguousarray(y),
            cond=max(x.shape)*EPS,lapack_driver='gelsd',check_finite=True)
    except (ValueError,linalg.LinAlgError):return empty('numerical_failure',n)
    result=empty('rank_deficient',n);result.update(rank=int(rank),column_scales=scales,singular_values=s)
    if rank<2:return result
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'): coeff=c/scales
    if not np.all(np.isfinite(coeff)):return empty('numerical_failure',n)
    result.update(coefficients=coeff,design=x,response=y)
    result['residual_rss'],result['rss_status']=rss(x,y,coeff)
    result.update(replay(estimator,coeff,estimator!='ma1' or denominator_supported(coeff)))
    return result


def accept_coefficients(actual, source, estimator, supported):
    actual=np.array(actual,dtype=np.float64,copy=True); source=np.asarray(source,dtype=np.float64)
    if actual.shape!=(2,) or not np.isfinite(actual).all():raise ValueError('coefficient shape/domain')
    if not np.all(np.abs(actual-source)<=1e-8+1e-6*np.abs(source)):raise ValueError('source coefficient mismatch')
    if estimator=='ma1' and supported:
        scale=max(abs(float(v)) for v in source)
        with np.errstate(over='ignore',invalid='ignore'): delta=actual/scale-source/scale
        if not np.isfinite(delta).all() or norm(delta)/norm(source/scale)>1e-6:raise ValueError('MA1 vector fidelity')
        if abs((float(actual[1])-float(source[1]))/float(source[1]))>1e-6:raise ValueError('MA1 denominator fidelity')
    return actual


def group(values):
    if len(values)!=7:raise ValueError('fixed seven-person family')
    finite=[float(v) for v in values if v is not None]
    if not all(math.isfinite(v) for v in finite):raise ValueError('nonfinite group value')
    result=dict(n_expected=7,n_defined=len(finite),status='incomplete',mean=None,sample_sd=None,minimum=None,maximum=None)
    if len(finite)!=7:return result
    exponent=math.frexp(max(map(abs,finite)))[1]
    scaled=[math.ldexp(v,-exponent) for v in finite]
    offsets=[v-scaled[0] for v in scaled]; center=math.fsum(offsets)/7
    try:
        mean=math.ldexp(scaled[0]+center,exponent)
        sd=0. if min(finite)==max(finite) else math.ldexp(norm([v-center for v in offsets])/math.sqrt(6),exponent)
    except OverflowError:result['status']='numerical_failure';return result
    if not math.isfinite(mean) or not math.isfinite(sd) or (sd==0 and min(finite)!=max(finite)):
        result['status']='numerical_failure';return result
    result.update(status='ok',mean=mean,sample_sd=sd,minimum=min(finite),maximum=max(finite));return result
