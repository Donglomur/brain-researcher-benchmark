"""Fieldwise numerical agreement, with no scientific-significance interpretation."""
from __future__ import annotations
import math
from .contract import require

def scalar(candidate,reference,*,absolute_tolerance,relative_tolerance):
    if math.isnan(candidate) or math.isnan(reference):
        return {'pass':math.isnan(candidate) and math.isnan(reference),'residual':float('nan'),'absolute':None,'relative':None,'kind':'undefined'}
    if math.isinf(candidate) or math.isinf(reference):
        return {'pass':candidate==reference,'residual':float('nan'),'absolute':None,'relative':None,'kind':'infinite'}
    delta=candidate-reference
    absolute=abs(delta)
    relative=absolute/abs(reference) if reference!=0 else (0.0 if absolute==0 else float('inf'))
    return {'pass':absolute<=absolute_tolerance+relative_tolerance*abs(reference),'residual':delta,'absolute':absolute,'relative':relative,'kind':'finite'}

def tolerance(absolute_tolerance,relative_tolerance):
    require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in [absolute_tolerance,relative_tolerance]) and (absolute_tolerance>0 or relative_tolerance>0),'explicit nonnegative tolerances with positive allowance')

def numbers(values,reference,*,absolute_tolerance,relative_tolerance):
    tolerance(absolute_tolerance,relative_tolerance)
    require(len(values)==len(reference),'no truncated comparison')
    residual=[];passed=0;finite=0;undefined=0;infinite=0;maximum_absolute=None;maximum_relative=None
    for a,b in zip(values,reference):
        row=scalar(a,b,absolute_tolerance=absolute_tolerance,relative_tolerance=relative_tolerance)
        residual.append(row['residual']);passed+=int(row['pass'])
        finite+=row['kind']=='finite';undefined+=row['kind']=='undefined';infinite+=row['kind']=='infinite'
        if row['absolute'] is not None:maximum_absolute=row['absolute'] if maximum_absolute is None else max(maximum_absolute,row['absolute'])
        if row['relative'] is not None:maximum_relative=row['relative'] if maximum_relative is None else max(maximum_relative,row['relative'])
    def value(v):return '+inf' if v is not None and math.isinf(v) else v
    return {'elements':len(values),'pass_count':passed,'fail_count':len(values)-passed,'finite_pairs':finite,'undefined_pairs':undefined,'infinite_pairs':infinite,'max_absolute_disagreement':value(maximum_absolute),'max_relative_disagreement':value(maximum_relative)},residual
