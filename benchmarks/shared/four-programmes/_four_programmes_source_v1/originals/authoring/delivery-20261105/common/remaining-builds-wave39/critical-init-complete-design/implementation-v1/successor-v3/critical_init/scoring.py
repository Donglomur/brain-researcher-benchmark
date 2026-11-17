"""Vector grading on protected complete target banks; no invented composite score."""
from .custody import need
from .guard import real,RequiredUnscorable
from .numerics import matrix

from .metrics import numeric

def grade_bundle(candidate,independent,native,spec):
    """Targets must already have passed protected loading and independent agreement."""
    need(set(candidate)==set(independent)==set(native)==set(spec),'every original output, no extras or omissions')
    rows={}
    for name,rule in spec.items():
        if rule['kind']=='identity':
            need(independent[name]==native[name],'reference scientific identity disagreement')
            rows[name]={'kind':'identity','matches':candidate[name]==independent[name]}
        else:
            agreement=numeric(independent[name],native[name],**rule)
            if not agreement['within_calibrated_tolerance']:
                raise RequiredUnscorable('G12','Independent/native reference disagreement',{'output':name,'comparison':agreement})
            rows[name]=numeric(candidate[name],independent[name],**rule)
    return rows

def report(scope,collection,grade_rows,*,gates,conflicts,costs,failures):
    need(set(gates)=={g['id']for g in scope.gates}and set(conflicts)=={c['id']for c in scope.conflicts},'all original gates and scientific conflicts')
    panels={}
    for p in scope.panel_ids:
        row=collection.get(p,{'status':'required_unscorable','reason':'missing original collection'})
        panels[p]={'collection':row,'metrics':grade_rows.get(p),'mandatory':True}
    unqualified=[g for g,v in gates.items()if v['status']!='qualified']
    return {'canonical_id':'PAPER-FIND-050','panels':panels,'mandatory_panel_count':76,
            'qualified_whole_benchmark':not unqualified and all(r['collection']['status']=='complete'and r['metrics']is not None for r in panels.values()),
            'gates':gates,'conflicts':conflicts,'costs':costs,'failures':failures,
            'overall_composite_score':None,
            'mechanistic_connectivity_or_full_state_DMD_claim':False,
            'benchmark_count_added':0}

