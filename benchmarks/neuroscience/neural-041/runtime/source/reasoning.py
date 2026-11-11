"""Checkable reasoning contract and captured numeric/executable lineage.

Checks do not replace independent scientific assessment of a free-text claim.
"""
from core import need
from schema import exact

def check(value,method,model):
    exact(value,('target','unit','window','estimand','uncertainty','alternatives','limitations'),'complete reasoning report')
    need(value['target']=='memory_load_1_vs_3' and value['unit']=='patient' and value['window']=='half_open_2.5s_maintenance','correct target/unit/epoch')
    for name in('estimand','uncertainty','limitations'):need(type(value[name])is str and 1<=len(value[name])<=8000,'bounded explicit scientific interpretation')
    need(type(value['alternatives'])is list and 1<=len(value['alternatives'])<=16 and all(type(x)is str and 1<=len(x)<=4000 for x in value['alternatives']),'explicit alternatives')
    return {'declaration':value,'method_source':method,'fitted_model':model,'checkable_contract_passed':True,
        'scientific_claim_validated':False,'independent_semantic_review_required':True}
