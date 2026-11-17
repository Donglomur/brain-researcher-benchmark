"""Continuous reconstruction metrics; no selected success threshold or SOTA claim."""
import math
from collections import Counter
from .codec import need, finite_number


def numeric_error(candidate, reference, meter):
    need(type(candidate) is tuple and type(reference) is tuple and len(candidate)==len(reference),
         'complete aligned scalar support')
    meter.admit_pairs(len(reference))
    need(all(finite_number(x) and finite_number(y) for x,y in zip(candidate,reference)),
         'finite numerical metric domain')
    errors=tuple(abs(x-y) for x,y in zip(candidate,reference))
    need(all(finite_number(e) for e in errors), 'subtraction overflow refused')
    n=len(errors)
    maximum=max(errors,default=0.0)
    # Scale before squaring/summing to avoid overflow in the norm itself.
    rmse=0.0 if maximum==0 or n==0 else maximum*math.sqrt(math.fsum((e/maximum)**2 for e in errors)/n)
    absolute_mean=0.0 if maximum==0 or n==0 else maximum*(math.fsum(e/maximum for e in errors)/n)
    reference_scale=max((abs(x) for x in reference),default=0.0)
    relative=None if reference_scale==0 else maximum/reference_scale
    need(all(finite_number(v) for v in (maximum,absolute_mean,rmse)), 'nonfinite derived error refused')
    need(relative is None or finite_number(relative), 'relative metric overflow refused')
    return {'n':n,'maximum_absolute_error':maximum,'mean_absolute_error':absolute_mean,
            'root_mean_squared_error':rmse,'maximum_error_over_reference_maximum':relative,
            'binary_success':None}


def adjusted_rand(candidate, reference, meter):
    need(type(candidate) is tuple and type(reference) is tuple and len(candidate)==len(reference),
         'complete aligned cluster labels')
    need(all(type(x) in (str,int) for x in candidate+reference), 'discrete cluster labels')
    meter.admit_rows(len(candidate))
    n=len(candidate)
    if n<2: return 1.0
    pair=lambda k:k*(k-1)//2
    joint=sum(pair(n) for n in Counter(zip(candidate,reference)).values())
    left=sum(pair(n) for n in Counter(candidate).values())
    right=sum(pair(n) for n in Counter(reference).values())
    total=pair(n)
    # Integer numerator/denominator retain exact combinatorial quantities.
    numerator=2*(joint*total-left*right)
    denominator=(left+right)*total-2*left*right
    return 1.0 if denominator==0 else numerator/denominator


def embedding_distances(coordinates, meter):
    need(type(coordinates) is tuple and coordinates and type(coordinates[0]) is tuple,
         'complete immutable embedding')
    d=len(coordinates[0]);n=len(coordinates)
    need(d>0 and all(len(x)==d and all(finite_number(v) for v in x) for x in coordinates),
         'finite complete equal-width embedding')
    meter.admit_pairs(n*(n-1)//2)
    distances=tuple(math.dist(coordinates[i],coordinates[j]) for i in range(n) for j in range(i+1,n))
    need(all(finite_number(v) for v in distances), 'distance overflow refused')
    return distances


def fixed_quantity_comparison(candidate, baseline, *, identical_estimand, fidelity_qualified):
    """Resource claims require all fixed quantities and separately qualified fidelity."""
    required=('wall_seconds','peak_rss_bytes','output_bytes','failed_attempt_seconds')
    need(set(candidate)==set(required) and set(baseline)==set(required), 'whole-attempt resource fields')
    need(all(finite_number(x) and x>=0 for x in tuple(candidate.values())+tuple(baseline.values())),
         'measured nonnegative resource costs')
    need(identical_estimand is True and fidelity_qualified is True,
         'same complete graph/operator/support and qualified scientific fidelity required')
    result={}
    for k in required:
        ratio=None if baseline[k]==0 else candidate[k]/baseline[k]
        need(ratio is None or finite_number(ratio), 'nonfinite resource ratio refused:'+k)
        result[k]={'candidate':candidate[k],'baseline':baseline[k],'ratio':ratio}
    return result
