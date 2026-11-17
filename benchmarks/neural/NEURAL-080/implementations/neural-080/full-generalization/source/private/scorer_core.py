"""Paired descriptive losses; no claim that candidate controls are competent."""
from decimal import Decimal,localcontext
import math
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from protocol import SUBJECTS,ARMS,BOOTSTRAP_DRAWS,BOOTSTRAP_SEED


def mse(p,y):
    p=np.asarray(p,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
    if p.shape!=y.shape or p.size==0 or not np.isfinite(p).all() or not np.isfinite(y).all():raise ValueError('Finite same-support predictions and targets')
    with np.errstate(over='ignore',invalid='ignore'):d=p-y
    if np.isfinite(d).all():
        scale=float(np.max(np.abs(d)))
        if not scale:return Decimal(0)
        d=d/scale
    else:
        scale=float(max(np.max(np.abs(p)),np.max(np.abs(y))))
        d=p/scale-y/scale
    fraction=float(np.mean(d*d))
    if not math.isfinite(fraction):raise ValueError('Nonfinite scaled error')
    return Decimal.from_float(scale)**2*Decimal.from_float(fraction)


def mean(values):return sum(values,Decimal(0))/len(values)


def quantile(values,numerator,denominator):
    values=sorted(values);position=(len(values)-1)*numerator
    lo,remainder=divmod(position,denominator);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*Decimal(remainder)/denominator


def serialize(x):
    if isinstance(x,Decimal):
        value=float(x)
        return value if math.isfinite(value) and (value!=0 or x==0) else str(x)
    if isinstance(x,dict):return {k:serialize(v) for k,v in x.items()}
    if isinstance(x,list):return [serialize(v) for v in x]
    return x


def evaluate(predictions,gold,*,bootstrap_draws=BOOTSTRAP_DRAWS):
    if set(predictions)!=set(SUBJECTS) or set(gold)!=set(SUBJECTS):raise ValueError('All six participants required')
    with localcontext() as dc:
        dc.prec=80
        details={};contrasts={}
        for person in SUBJECTS:
            if set(predictions[person])!=set(ARMS):raise ValueError('Five complete arms per participant')
            losses={arm:mse(predictions[person][arm],gold[person]) for arm in ARMS}
            details[person]={'arm_mse':losses,'source_calibration_caveat':person=='sub-03'}
            contrasts[person]={
                'dynamic_gain_given_eye':losses['nuisance_eye']-losses['full'],
                'dynamic_gain_without_eye':losses['nuisance']-losses['nuisance_dynamic'],
                'ocular_gain_given_dynamic':losses['nuisance_dynamic']-losses['full'],
                'dynamic_gain_attenuation_after_eye':(losses['nuisance']-losses['nuisance_dynamic'])-(losses['nuisance_eye']-losses['full']),
                'query_shift_increase':losses['full_shift500ms']-losses['full']}
        keys=list(contrasts[SUBJECTS[0]])
        aggregate={arm:mean([details[p]['arm_mse'][arm] for p in SUBJECTS]) for arm in ARMS}
        paired={key:mean([contrasts[p][key] for p in SUBJECTS]) for key in keys}
        if type(bootstrap_draws) is not int or not 1<=bootstrap_draws<=BOOTSTRAP_DRAWS:raise ValueError('Fixed bounded descriptive draws')
        draws=np.random.default_rng(BOOTSTRAP_SEED).integers(0,6,size=(bootstrap_draws,6))
        intervals={}
        for key in keys:
            values=[contrasts[p][key] for p in SUBJECTS]
            boot=[mean([values[int(i)] for i in row]) for row in draws]
            intervals[key]={'lower':quantile(boot,25,1000),'upper':quantile(boot,975,1000)}
        other=[p for p in SUBJECTS if p!='sub-03']
        sensitivity={'arm_mse':{a:mean([details[p]['arm_mse'][a] for p in other]) for a in ARMS},
                     'contrasts':{k:mean([contrasts[p][k] for p in other]) for k in keys}}
        return serialize({'schema':'neural080_score_v1','admitted':True,'primary_full_mse':aggregate['full'],'primary_direction':'lower',
           'arm_mse':aggregate,'participants':details,'participant_contrasts':contrasts,'contrasts':paired,
           'descriptive_participant_bootstrap':{'seed':BOOTSTRAP_SEED,'draws':bootstrap_draws,'pointwise_95_percentile':intervals,
               'unit':'six participants, all repeated videos/trials retained together','conditional_on':'fixed102 source test videos and released joined-trial availability',
               'simultaneous_or_confirmatory':False},
           'fixed_leave_sub03_out_sensitivity':sensitivity,'qualified_dynamic_information':None,
           'eligible_for_dynamic_contribution_ranking':False,'same_method_replay':'unverified','control_competence':'unverified',
           'purely_visual_mechanism_claim':False,'scientific_causality_claim':False})
