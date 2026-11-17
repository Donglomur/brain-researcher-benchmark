"""Literal author execution adapter; never a corrected independent reference."""
import math
from .common import require,result,ScientificGate

def execute(payload):
    import numpy as np
    r=payload['request'];p=payload['protocol'];a=payload['arrays'];version=r['literal_version']
    if version=='majaj_numpy_released_draw_v1':
        from .majaj import literal_draw
        return literal_draw(payload)
    require(p.get('literal_source_identity_admitted') is True,'exact literal source/environment binding required','qualification_required')
    x=np.asarray(a['trials'],dtype=float);require(x.ndim==3 and np.isfinite(x).all(),'literal trial array')
    T,P,Q=x.shape;require(P>=4 and Q>=2,'literal minimum support','insufficient_support')
    first=r['first_trial'];second=r.get('second_trial');require(type(first)is int and 0<=first<T,'first trial')
    if second is not None:require(type(second)is int and 0<=second<T,'second trial')
    one=x[first];two=x[second] if second is not None else None
    if version=='author_infinite_f18de358':
        from .literal_author.estimators import participation_ratio
        values=participation_ratio(one,two,return_all=True,return_parts=True)
    elif version=='author_finite_f18de358':
        from .literal_author.finite import participation_ratio_finite
        R,C=r['finite_population'];require(type(R)is int and type(C)is int and R>=P and C>=Q,'finite roster')
        values=participation_ratio_finite(one,R,C,two,return_naive=True,return_parts=True)
    else:
        # Static allowlist, not arbitrary import/exec or a participant callable.
        if version=='notebook_on_Stringer':from .literal_author import notebook_on_Stringer as module
        elif version=='notebook_on_TVSD':from .literal_author import notebook_on_TVSD as module
        elif version=='notebook_Linear_example':from .literal_author import notebook_Linear_example as module
        elif version=='notebook_Final_dim':from .literal_author import notebook_Final_dim as module
        elif version=='notebook_nonlin_manifold':from .literal_author import notebook_nonlin_manifold as module
        else:raise ScientificGate('unavailable_source','literal/printed source version has no authenticated executor: '+version)
        fn=r['literal_function'];require(fn in ('getest_all','getest_all0'),'literal function')
        if fn=='getest_all0':
            require(version in ('notebook_on_Stringer','notebook_on_TVSD','notebook_Linear_example'),'source function unavailable')
            require(two is not None,'source two-trial operand required')
            R,C=r.get('finite_population',[None,None]);raw=module.getest_all0(one,two,P,Q,math.inf if R is None else R,math.inf if C is None else C)
        elif version=='notebook_on_Stringer':
            require(two is not None,'Stringer source function requires two arrays');raw=module.getest_all(one,two,P,Q)
        else:
            require(second is None,'literal single-matrix source must not silently ignore second trial');raw=module.getest_all(one,P,Q)
        values={'source_return':raw}
    nonfinite={}
    def normalize(value,path):
        if isinstance(value,dict):return {k:normalize(v,path+'/'+str(k)) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [normalize(v,path+'/'+str(i)) for i,v in enumerate(value)]
        converted=np.asarray(value)
        if converted.ndim:return normalize(converted.tolist(),path)
        scalar=float(converted)
        if not math.isfinite(scalar):nonfinite[path]=str(scalar);return None
        return scalar
    values=normalize(values,'literal_values')
    return result({'literal_values':values,'source_nonfinite_scalar_kinds':nonfinite},dict(literal_version=version,trial_orientation=[first,second],source_identity=p['literal_source_identity']),['Literal formulas preserve documented symmetry/finite-normalization discrepancies; they are not corrected estimators.'])
