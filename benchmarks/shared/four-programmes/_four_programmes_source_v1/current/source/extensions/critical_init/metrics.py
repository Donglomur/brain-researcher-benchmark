"""Finite, overflow-safe metrics with explicit rank and invariant-subspace policy."""
import math
from fractions import Fraction
from .custody import need
from .guard import real,RequiredUnscorable

def _rms(magnitudes):
    """Scaled norm; never square a large value or an integer in its native dtype."""
    import numpy as np
    a=np.asarray(magnitudes,dtype='float64')
    need(a.size and np.isfinite(a).all()and(a>=0).all(),'representable finite metric magnitudes')
    maximum=float(a.max())
    if maximum==0:return 0.0
    result=maximum*math.sqrt(float(np.mean((a/maximum)**2)))
    need(math.isfinite(result),'representable finite RMS diagnostic')
    return result

def _float_work(a):
    """No implicit lossy integer-to-float conversion in a geometric metric."""
    import numpy as np
    dtype='complex128'if a.dtype.kind=='c'else'float64'
    b=a.astype(dtype)
    need(np.isfinite(b).all(),'finite supported arithmetic conversion')
    if a.dtype.kind in 'biu':
        need(all(int(x)==int(float(y))for x,y in zip(a.flat,b.flat)),
             'geometric metric requires losslessly representable integer inputs')
    # Wider floating types are admitted only if their values survive conversion.
    if a.dtype.itemsize>b.dtype.itemsize:
        need(np.array_equal(b.astype(a.dtype),a),'lossless supported floating conversion')
    return b

def _within(error,reference,atol,rtol):
    import numpy as np
    # Compare the finite stored magnitudes against the mathematical calibrated
    # threshold. Ratios can erase a nonzero complex error beside a huge real
    # reference; a floating product/sum can also overflow or underflow. Exact
    # binary-rational arithmetic avoids all three without a tolerance floor.
    # Work is streamed (no object array). Exact zeros need no rational work.
    absolute=Fraction(atol);relative=Fraction(rtol)
    for observed,scale in zip(np.asarray(error).flat,np.asarray(reference).flat):
        if observed==0:continue
        if Fraction(float(observed))>absolute+relative*Fraction(float(scale)):
            return False
    return True

def _real_integer_comparison(a,b,atol,rtol,exact):
    """Exact integer/mixed-real decisions, including uint64/int64 boundaries."""
    import numpy as np
    errors=[];magnitudes=[];passed=True
    qa=Fraction(atol);qr=Fraction(rtol)
    for av,bv in zip(a.flat,b.flat):
        av=av.item();bv=bv.item()
        av=int(av)if type(av)is bool else av
        bv=int(bv)if type(bv)is bool else bv
        difference=abs(Fraction(av)-Fraction(bv))
        reference=abs(Fraction(bv))
        if exact:passed=passed and difference==0
        else:passed=passed and difference<=qa+qr*reference
        try:ef=float(difference);rf=float(reference)
        except OverflowError as error:raise ValueError('unrepresentable finite metric diagnostic')from error
        need(math.isfinite(ef)and math.isfinite(rf),'representable integer/mixed-real diagnostic')
        errors.append(difference);magnitudes.append(rf)
    # JSON can preserve the exact mathematical integer maximum rather than a
    # rounded float64 value. RMS is explicitly a finite approximate diagnostic.
    largest=max(errors)
    maximum=int(largest)if largest.denominator==1 else float(largest)
    return {'max_abs_error':maximum,'rmse':_rms([float(x)for x in errors]),
            'reference_rms':_rms(magnitudes),'within_calibrated_tolerance':bool(passed),
            'arithmetic':'exact rational integer/mixed-real comparison; scaled float64 RMS'}

def _subspace_projector(value,*,rank_rtol,rank_atol):
    import numpy as np
    magnitude=np.abs(value)
    need(np.isfinite(magnitude).all(),'representable subspace magnitudes')
    scale=float(magnitude.max())
    if scale==0:return np.zeros((value.shape[0],value.shape[0]),dtype=value.dtype),0
    u,s,_=np.linalg.svd(value/scale,full_matrices=False)
    # Evaluate absolute cutoff without unbounded division when scale is tiny.
    if rank_atol>0 and rank_atol/float(s[0])>=scale:rank=0
    else:
        cutoff=max(rank_rtol*float(s[0]),rank_atol/scale)
        rank=int(np.count_nonzero(s>cutoff))
    basis=u[:,:rank]
    projector=basis@basis.conj().T
    need(np.isfinite(projector).all(),'finite Hermitian projector')
    return projector,rank

def numeric(actual,expected,*,kind,atol,rtol,rank_policy='full_column_rank',
            rank_rtol=None,rank_atol=0.0):
    import numpy as np
    a=np.asarray(actual);b=np.asarray(expected)
    real(atol,0);real(rtol,0)
    need(a.dtype.kind in 'biufc'and b.dtype.kind in 'biufc','supported numeric dtypes only')
    need(a.shape==b.shape and a.size and np.isfinite(a).all()and np.isfinite(b).all(),
         'exact finite full output geometry')
    need(kind in ('complex_spectrum','pc_loadings','subspace','array','integer','scalar'),'known metric bank')
    base={'kind':kind,'elements':int(a.size),'atol':atol,'rtol':rtol}
    if kind=='integer':need(a.dtype.kind in 'iu'and b.dtype.kind in 'iu','exact integral predictions')
    if kind in ('array','scalar','integer')and (a.dtype.kind in 'biu'or b.dtype.kind in 'biu')and a.dtype.kind!='c'and b.dtype.kind!='c':
        return dict(base,**_real_integer_comparison(a,b,atol,rtol,kind=='integer'))
    a=_float_work(a);b=_float_work(b);geometry_ok=True;details={}
    if a.dtype.kind=='c'or b.dtype.kind=='c':a=a.astype('complex128');b=b.astype('complex128')
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            if kind=='complex_spectrum':
                from scipy.optimize import linear_sum_assignment
                need(a.ndim==1,'full eigenvalue vector')
                cost=np.abs(a[:,None]-b[None,:])
                need(np.isfinite(cost).all(),'representable finite assignment costs')
                i,j=linear_sum_assignment(cost);a=a[i];b=b[j]
            elif kind=='pc_loadings':
                need(a.ndim==2,'full PC map matrix')
                # Stable phase/sign choice; preserve amplitude rather than normalizing outputs.
                for col in range(a.shape[1]):
                    sa=float(np.max(np.abs(a[:,col])));sb=float(np.max(np.abs(b[:,col])))
                    if sa and sb:
                        inner=np.vdot(a[:,col]/sa,b[:,col]/sb)
                        if abs(inner):a[:,col]*=inner/abs(inner)
            elif kind=='subspace':
                need(a.ndim==2 and 0<a.shape[1]<=a.shape[0],'declared nonempty full-column subspace geometry')
                need(rank_policy=='full_column_rank','explicit supported subspace rank policy')
                real(rank_atol,0)
                tol=np.finfo(float).eps*max(a.shape)if rank_rtol is None else real(rank_rtol,0,1)
                need(tol<1,'rank relative threshold below one')
                pa,arank=_subspace_projector(a,rank_rtol=tol,rank_atol=rank_atol)
                pb,brank=_subspace_projector(b,rank_rtol=tol,rank_atol=rank_atol)
                required=b.shape[1]
                if brank!=required:
                    raise RequiredUnscorable('G12','Deficient reference subspace under declared full-column rank policy',
                                             {'reference_rank':brank,'required_rank':required,'rank_rtol':tol,'rank_atol':rank_atol})
                geometry_ok=arank==required
                details={'rank_policy':rank_policy,'required_rank':required,'candidate_rank':arank,
                         'reference_rank':brank,'rank_rtol':tol,'rank_atol':rank_atol,
                         'candidate_rank_valid':geometry_ok,'projector':'U_rank U_rank.conjugate_transpose'}
                a,b=pa,pb
            error=np.abs(a-b);reference=np.abs(b)
            need(np.isfinite(error).all()and np.isfinite(reference).all(),'representable finite derived errors and reference magnitudes')
            decision=geometry_ok and _within(error,reference,atol,rtol)
            diagnostics={'max_abs_error':float(error.max()),'rmse':_rms(error),'reference_rms':_rms(reference),
                         'within_calibrated_tolerance':bool(decision),'arithmetic':'checked float64/complex128 with scaled RMS'}
    except (FloatingPointError,OverflowError)as error:
        raise ValueError('unrepresentable derived metric; no success recorded')from error
    need(all(math.isfinite(diagnostics[k])for k in ('max_abs_error','rmse','reference_rms')),'all published numeric diagnostics finite')
    return dict(base,**diagnostics,**details)

