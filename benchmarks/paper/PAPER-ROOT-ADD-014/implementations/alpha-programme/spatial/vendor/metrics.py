"""Pure prediction metrics; no fitting, scientific inputs or source imports.

Source xval: separately remove the DC of each test fold from observed and
predicted series, concatenate, then calccod(default target mean subtraction).
Exact rational arithmetic evaluates the intended formula on represented finite
floats; it does not claim bitwise MATLAB parity. A supplied support mask is an
operator-bound source asset, never chosen using candidate values.
"""
from fractions import Fraction
import math
import numpy as np

PARTICIPANTS=('p01','p02','p05','p06','p07','p08','p09','p10','p11')
FOLD_LABELS=(1,)*38+(2,)*37


def _inputs(observed,predicted,support_mask):
    y=np.asarray(observed);p=np.asarray(predicted)
    if y.shape!=(75,) or p.shape!=(75,) or y.dtype.kind not in 'fi' or p.dtype.kind not in 'fi':raise ValueError('Exact75real sample support required')
    y=y.astype(float);p=p.astype(float)
    if not np.isfinite(p).all():raise ValueError('Every candidate sample must be finite; no candidate-dependent omission')
    finite=np.isfinite(y)
    if support_mask is None:
        if not finite.all():raise ValueError('Nonfinite source samples require an explicit bound support mask')
        support=finite
    else:
        support=np.asarray(support_mask)
        if support.dtype.kind!='b' or support.shape!=(75,) or not np.array_equal(support,finite):raise ValueError('Fixed support must retain every finite source sample and omit only declared nonfinite source samples')
    return y,p,support


def _finish(y,p,name,support,fold_counts):
    n=len(y)
    out={'metric':name,'status':'defined','value_percent':None,'total_samples':75,'supported_samples':n,'fold_support':fold_counts,'support_mask_applied':not bool(np.all(support)),'arithmetic':'exact rational evaluation of represented finite floats'}
    if not n:out['status']='undefined_no_support';return out
    denominator=sum((a*a for a in y),Fraction(0))
    if denominator==0:out['status']='undefined_zero_target_energy';return out
    error=sum(((a-b)*(a-b) for a,b in zip(y,p)),Fraction(0))
    value=100*(1-error/denominator)
    try:v=float(value)
    except OverflowError:out['status']='numeric_unavailable';return out
    if not math.isfinite(v):out['status']='numeric_unavailable';return out
    out['value_percent']=v;return out


def literal_paper_eq6_percent(observed,predicted,*,support_mask=None):
    """Literal uncentered Eq6:100*(1-SSE/sum(y²)); constant nonzero y defined."""
    y,p,s=_inputs(observed,predicted,support_mask)
    yy=[Fraction.from_float(float(v)) for v in y[s]];pp=[Fraction.from_float(float(v)) for v in p[s]]
    return _finish(yy,pp,'literal_paper_eq6_uncentered_energy_percent',s,[int(s[:38].sum()),int(s[38:].sum())])


def source_fold_projected_xval_percent(observed,predicted,fold_labels,*,support_mask=None):
    """Source75-point xvalmode2 halves; each projected separately, then pooled COD.

For a frozen nonfinite-source mask, center only its retained samples in each
fold; this masked extension is disclosed, not silently called MATLAB NaN parity.
"""
    labels=np.asarray(fold_labels)
    if labels.dtype.kind not in 'iu' or labels.shape!=(75,) or tuple(labels.tolist())!=FOLD_LABELS:raise ValueError('Fixed first38/last37 fold labels1/2 required')
    y,p,s=_inputs(observed,predicted,support_mask);yy=[];pp=[];counts=[]
    for label in (1,2):
        keep=s&(labels==label);n=int(keep.sum());counts.append(n)
        if not n:return {'metric':'source_fold_projected_xval_percent','status':'undefined_empty_test_fold','value_percent':None,'total_samples':75,'supported_samples':int(s.sum()),'fold_support':[int(s[:38].sum()),int(s[38:].sum())],'support_mask_applied':True,'arithmetic':'exact rational evaluation of represented finite floats'}
        a=[Fraction.from_float(float(v)) for v in y[keep]];b=[Fraction.from_float(float(v)) for v in p[keep]]
        ma=sum(a,Fraction(0))/n;mb=sum(b,Fraction(0))/n
        yy.extend(v-ma for v in a);pp.extend(v-mb for v in b)
    # calccod subtracts the concatenated observed mean from both. This is exactly0
    # after the independent fold projections; keeping it explicit fixes semantics.
    target_mean=sum(yy,Fraction(0))/len(yy);yy=[v-target_mean for v in yy];pp=[v-target_mean for v in pp]
    return _finish(yy,pp,'source_fold_projected_xval_percent',s,counts)


def aggregate_participants(values,expected_electrodes):
    """Complete caller-bound9-person roster; pooled vs prospective equal-person; neither is claimed as a published group statistic.

values and expected_electrodes are mappings person→{electrode:value_or_None} and
person→ordered unique electrode IDs. This function never invents a fitted cohort.
"""
    if not isinstance(values,dict) or not isinstance(expected_electrodes,dict) or set(expected_electrodes)!=set(PARTICIPANTS):raise ValueError('Explicit full nine-person source electrode roster required')
    if set(values)!=set(PARTICIPANTS):return {'status':'unavailable_participant_support','pooled_electrode_mean_percent':None,'prospective_equal_person_mean_percent':None,'participants_required':list(PARTICIPANTS)}
    means={};all_values=[];undefined=False;counts={}
    for person in PARTICIPANTS:
        ids=expected_electrodes[person]
        if not isinstance(ids,list) or any(not isinstance(v,str) or not v for v in ids) or len(set(ids))!=len(ids) or not isinstance(values[person],dict) or set(values[person])!=set(ids):raise ValueError('Complete exact electrode identities required')
        v=[values[person][e] for e in ids];counts[person]=len(v)
        if any(x is not None and (type(x) not in (int,float) or not math.isfinite(x)) for x in v):raise ValueError('Finite metric values or explicit undefined None')
        if not v or any(x is None for x in v):undefined=True;means[person]=None
        else:
            qs=[Fraction.from_float(float(x)) for x in v];means[person]=float(sum(qs,Fraction(0))/len(qs));all_values.extend(qs)
    if undefined:return {'status':'unavailable_undefined_electrode_or_empty_person','pooled_electrode_mean_percent':None,'prospective_equal_person_mean_percent':None,'per_person':means,'electrode_counts':counts}
    pooled=float(sum(all_values,Fraction(0))/len(all_values));equal=float(sum((Fraction.from_float(means[p]) for p in PARTICIPANTS),Fraction(0))/9)
    return {'status':'defined','pooled_electrode_mean_percent':pooled,'prospective_equal_person_mean_percent':equal,'per_person':means,'electrode_counts':counts,'independent_population_replication_claim':False}


def published_selection_mask(bb_percent,alpha_percent,bb_ecc_deg,alpha_ecc_deg):
    """Fixed published-threshold diagnostic; not recomputation of permutation fits.

Source strictness is >scorethreshold and <eccentricitylimit. Published31/22%
values are not hardcoded by source INITd (which loads permutation percentiles).
8.3degrees is the paper-level limit; caller must authenticate pixel→degree maps.
Missing/nonfinite entries are unavailable and excluded, unlike unsafe negatedNaN
comparisons. No54/53 fitted-cohort claim follows from a constructed mask.
"""
    arrays=[np.asarray(v,dtype=float) for v in (bb_percent,alpha_percent,bb_ecc_deg,alpha_ecc_deg)]
    if any(a.ndim!=1 or a.shape!=arrays[0].shape for a in arrays):raise ValueError('Common one-dimensional electrode support')
    finite=np.logical_and.reduce([np.isfinite(a) for a in arrays]);a,b,c,d=arrays
    return {'eligible':finite&(a>31)&(b>22)&(c<8.3)&(d<8.3),'available':finite,'policy':'published fixed31/22percent and8.3degree strict diagnostic; not source-permutation threshold reproduction','fitted_cohort_reproduced':False}
