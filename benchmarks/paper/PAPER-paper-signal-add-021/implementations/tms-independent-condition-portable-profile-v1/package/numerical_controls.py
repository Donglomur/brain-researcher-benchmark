"""Prospective exact analytic boundary controls; never opens target artifacts."""
from fractions import Fraction as F
import math
from common import Refusal
from rounding import cell,verdict

def check():
    half=F(1,1<<1075);small=math.ldexp(1.,-1074)
    expected=[(0.,(-half,half,True)),(-0.,(-half,half,True)),
              (small,(half,3*half,False)),(-small,(-3*half,-half,False)),
              (1.,(1-F(1,1<<54),1+F(1,1<<53),True)),
              (-1.,(-1-F(1,1<<53),-1+F(1,1<<54),True))]
    count=0
    for value,target in expected:
        assert cell(value)==target;count+=1
    cases=[(0.,-half,half,'contained'),(small,half,half,'disjoint'),
           (small,3*half,3*half,'disjoint'),(small,half,2*half,'indeterminate'),
           (small,2*half,2*half,'contained'),(-small,-half,-half,'disjoint'),
           (1.,1-F(1,1<<54),F(1),'contained'),
           (1.,1-F(1,1<<53),1-F(1,1<<54),'indeterminate'),
           (3.,F(-1),F(1),'disjoint')]
    for value,lo,hi,want in cases:
        assert verdict(value,F(lo),F(hi))==want;count+=1
    for value in (float('nan'),float('inf'),1):
        try:cell(value)
        except Refusal:pass
        else:raise AssertionError('finite exact-float refusal required')
        count+=1
    assert count==18
    return {'schema':'tms_p21_analytic_rounding_controls_v1','controls':count,
            'target_reads':0,'source_only_invented_values':True,'scientific_result':False}
