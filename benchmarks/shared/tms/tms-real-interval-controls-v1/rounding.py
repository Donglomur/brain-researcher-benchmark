"""Exact secondary rounding-cell diagnostics for invented fixture scores.

Continuous MAE/Linf remain primary. The caller is responsible for keeping
target-dependent diagnostics private; this module supplies no process isolation
or authentic-source authority.
"""
from fractions import Fraction
import math
import struct
from kernel import require as need

def rational(value):
    need(type(value) is dict and set(value)=={'numerator','denominator'},'score_rational_schema')
    n,d=value['numerator'],value['denominator']
    need(type(n) is type(d) is str and n==str(int(n)) and d==str(int(d)) and int(d)>0,'canonical_rational')
    r=Fraction(int(n),int(d))
    need(str(r.numerator)==n and str(r.denominator)==d,'reduced_score_rational')
    return r

def cell(value):
    need(type(value) is float and math.isfinite(value),'finite_rounding_cell')
    if value == 0:
        half = Fraction(1,1<<1075)
        return -half,half,True
    # Targets are in [-1,1]. Avoid nonexistent finite neighbors at extrema.
    if abs(value)>2:
        return None
    previous=math.nextafter(value,-math.inf)
    following=math.nextafter(value,math.inf)
    z=Fraction.from_float(value)
    lo=(Fraction.from_float(previous)+z)/2
    hi=(Fraction.from_float(following)+z)/2
    even=(struct.unpack('<Q',struct.pack('<d',value))[0]&1)==0
    return lo,hi,even

def verdict(value,lo,hi):
    need(type(lo) is Fraction and type(hi) is Fraction and -1<=lo<=hi<=1,'proved_target_interval')
    bounds=cell(value)
    if bounds is None:
        return 'disjoint'
    a,b,even=bounds
    if (a<lo or (even and a==lo)) and (hi<b or (even and hi==b)):
        return 'contained'
    if hi<a or lo>b or (not even and (hi==a or lo==b)):
        return 'disjoint'
    return 'indeterminate'

def from_score(body,score):
    need(type(body) is bytes and len(body)==2232 and
         type(score) is dict and score.get('schema')=='tms_real_interval_248_inert_score_v1' and
         score.get('authentic_source') is False and score.get('production_authority_claimed') is False and
         score['all248_categories_match'] is True and len(score['slots'])==248,
         'complete_successfully_scored_submission')
    values=struct.unpack('<248d',body[:1984]);flags=body[1984:]
    rows=[]
    for i,(value,flag,slot) in enumerate(zip(values,flags,score['slots'])):
        need(type(slot['index']) is int and slot['index']==i and flag in (0,1),'ordered_score_slots')
        if flag:
            need(math.isnan(value) and slot['category']=='source_undefined' and slot['signed'] is None,'categorical_slot')
            rows.append('source_undefined');continue
        need(math.isfinite(value) and slot['category']=='finite','finite_slot')
        z=Fraction.from_float(value)
        # Signed residual = candidate minus target. Reverse endpoints.
        lo=z-rational(slot['signed']['upper']);hi=z-rational(slot['signed']['lower'])
        rows.append(verdict(value,lo,hi))
    finite=sum(x!='source_undefined' for x in rows)
    counts={key:rows.count(key) for key in ('contained','disjoint','indeterminate','source_undefined')}
    return {'schema':'tms_inert_rounding_cell_diagnostic_v1','slots':rows,'counts':counts,
            'finite_slots':finite,'informative':finite>0,
            'certified_fraction_bounds':None if not finite else {
                'lower':{'numerator':str(Fraction(counts['contained'],finite).numerator),'denominator':str(Fraction(counts['contained'],finite).denominator)},
                'upper':{'numerator':str(Fraction(counts['contained']+counts['indeterminate'],finite).numerator),'denominator':str(Fraction(counts['contained']+counts['indeterminate'],finite).denominator)}},
            'zero_signs_identified':True,'bitwise_parity':False,'confidence_interval':False,
            'scientific_tolerance':None,'authentic_source':False,
            'production_authority_claimed':False,'requires_operator_private_handling':True}
