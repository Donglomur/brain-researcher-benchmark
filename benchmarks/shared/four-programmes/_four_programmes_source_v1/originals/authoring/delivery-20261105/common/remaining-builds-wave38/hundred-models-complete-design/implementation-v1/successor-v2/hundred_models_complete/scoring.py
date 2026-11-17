"""Full-support comparison. A numeric match never authenticates method execution."""
import math
from .guard import need,Unscorable,encoded,bare
from .scope import condition_rows
from .endpoints import improvement_admission
from .projection import compare_scientific_endpoints,validate_run_custody,validate_shared_support

def score(scope,candidate,reference,qualification):
    """One row per335conditions x17ROIs; layers/ten people are reference-bound.

    Macro-average: subjects -> layers -> ROIs -> conditions -> four source branches.
    Figure trees are separately required, never replaced by this scalar summary.
    """
    need(qualification.get('qualified_reference') is True,'independently qualified reference required')
    need(qualification['reference']==bare(encoded(reference)),'exact original reference identity')
    need(candidate['schema']==reference['schema']=='hundred_models_submission_v2','closed full submission ABI')
    need(candidate['scope']==reference['scope']==bare(encoded(scope)),'complete scientific scope binding')
    validate_run_custody(candidate,qualification['runs']['candidate']);validate_run_custody(reference,qualification['runs']['reference'])
    validate_shared_support(scope,candidate['scientific_support'],reference['scientific_support'],qualification['scientific_support'])
    conditions=condition_rows(scope);rois=[x for group in scope['roi_groups'].values() for x in group]
    expected=[(c['id'],r) for c in conditions for r in rois]
    for document in (candidate,reference):
        need([(r['condition'],r['roi']) for r in document['rsa']]==expected,'complete ordered335x17 biological support')
        need(document['subjects']==scope['subjects'],'all ten participants, original order')
    bycondition={};coverage=[]
    for a,b in zip(candidate['rsa'],reference['rsa']):
        need(a['layers']==b['layers'] and len(b['layers'])==len(set(b['layers']))>0,'all source-evidenced layers in original order')
        need(len(a['values'])==len(b['values'])==len(b['layers']),'complete RSA layer rows')
        errors=[]
        for la,lb in zip(a['values'],b['values']):
            need(len(la)==len(lb)==10,'full participant axis')
            need([v is None for v in la]==[v is None for v in lb],'candidate cannot introduce or remove undefined participant statistics')
            if None in lb:
                need([v is None for v in la]==[v is None for v in lb],'undefined mask unchanged')
                coverage.append({'condition':b['condition'],'roi':b['roi'],'reason':'undefined reference participant statistic'})
            for x,y in zip(la,lb):
                need(x is None or type(x) in (int,float) and math.isfinite(x) and -1<=x<=1,'finite signed candidate rho')
                need(y is None or type(y) in (int,float) and math.isfinite(y) and -1<=y<=1,'finite signed reference rho')
            errors.append(None if None in la or None in lb else sum(abs(x-y) for x,y in zip(la,lb))/10)
        value=None if None in errors else sum(errors)/len(errors)
        bycondition.setdefault(b['condition'],[]).append(value)
    # All22figures/two tables must be present, with exact metadata and undefined support.
    need([x['figure'] for x in reference['figures']]==list(range(1,23)) and [x['table'] for x in reference['tables']]==[1,2],'qualified reference complete paper support')
    from .endpoints import held
    if held(reference['figures']):raise Unscorable('G11/G12/G13','Reference figure obligations still held; no complete reproduction score')
    secondary=compare_scientific_endpoints(candidate,reference)
    branches={}
    for role in ('main','figure16','figure17','figure18'):
        values=[bycondition[c['id']] for c in conditions if c['role']==role]
        branches[role]=None if any(v is None for row in values for v in row) else sum(sum(row)/len(row) for row in values)/len(values)
    return {'status':'required_unscorable' if coverage else 'complete_numerical_comparison','balanced_RSA_MAE':None if coverage else sum(branches.values())/4,'branch_MAE':branches,'undefined_coverage':coverage,'required_figure_tree_diagnostic':secondary,'success_threshold':qualification.get('predeclared_tolerance'),'scientific_qualification':False,'historical_parity_proved':False,'candidate_execution_identity_required':True}

def improvement_protocol(protocol):
    return improvement_admission(protocol)
