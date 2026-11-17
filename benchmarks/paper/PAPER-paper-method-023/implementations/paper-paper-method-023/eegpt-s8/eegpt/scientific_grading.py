"""Protected, full-product adjudication from actual captured primitives.

Numerical code is deliberately dormant during source construction. No submitted
summary score is accepted. A mathematically consistent product can disagree with
its independent reference; that is a valid negative reproduction result.
"""
import math
from .protocol import HandleCustody,boundary,Directory,need,fields,identity,finite,observation,digest
from .products import array_rows,validate_scientific_body
from .diagnostics import channel_similarity,pearson_sufficient,attention_summary,scaling


def arrays(grader,pid):
    import numpy as np
    captured=grader.captured[pid];product=captured['product'];expected=grader.collection.expected[pid]
    total=sum(math.prod(expected['arrays'][k]['shape'])*8 for k in product['arrays'])
    need(total*4<=grader.budget.limits['resident_bytes'],'complete scientific product and full independent check fit selected memory; no thinning')
    with HandleCustody('scientific_product_arrays') as owned:
        root=owned.own(Directory(captured['root']),'capture')
        return {k:np.asarray(list(owned.own(array_rows(root,pin,expected['arrays'][k]['shape'],grader.budget),'array:'+k)),dtype=np.float64).reshape(expected['arrays'][k]['shape']) for k,pin in product['arrays'].items()}


def numeric_compare(a,b,tolerance,path='root'):
    """All scalar/array cells compared; nonnumeric identities remain exact."""
    import numpy as np
    fields(tolerance,('absolute','relative','qualification'),'independently fixed numerical tolerance');digest(tolerance['qualification'])
    atol=finite(tolerance['absolute'],'absolute tolerance');rtol=finite(tolerance['relative'],'relative tolerance');need(atol>=0 and rtol>=0,'nonnegative prior tolerance')
    report={'numeric_values':0,'max_absolute_error':0.,'max_scaled_error':0.,'outside_tolerance':0,'identity_mismatches':[]}
    def walk(x,y,p):
        if isinstance(x,np.ndarray) or isinstance(y,np.ndarray):
            x=np.asarray(x);y=np.asarray(y);need(x.shape==y.shape,'complete matching scientific axes '+p);need(np.isfinite(x).all() and np.isfinite(y).all(),'finite independently compared arrays')
            delta=np.abs(x-y);scale=atol+rtol*np.abs(y);report['numeric_values']+=x.size
            if x.size:
                report['max_absolute_error']=max(report['max_absolute_error'],float(delta.max()));report['outside_tolerance']+=int((delta>scale).sum());ratio=np.zeros_like(delta,dtype=float);np.divide(delta,scale,out=ratio,where=scale>0);ratio[(scale==0)&(delta>0)]=np.finfo(float).max;report['max_scaled_error']=max(report['max_scaled_error'],float(ratio.max()))
        elif type(x) in (int,float) and type(y) in (int,float):
            finite(x,p);finite(y,p);d=abs(x-y);s=atol+rtol*abs(y);report['numeric_values']+=1;report['max_absolute_error']=max(report['max_absolute_error'],d);report['outside_tolerance']+=int(d>s);report['max_scaled_error']=max(report['max_scaled_error'],d/s if s else (0. if d==0 else float.fromhex('0x1.fffffffffffffp+1023')))
        elif type(x) is dict and type(y) is dict:
            if set(x)!=set(y):report['identity_mismatches'].append(p+': key support differs');return
            for k in sorted(x):walk(x[k],y[k],p+'.'+str(k))
        elif type(x) in (list,tuple) and type(y) in (list,tuple):
            if len(x)!=len(y):report['identity_mismatches'].append(p+': full axis length differs');return
            for i,(u,v) in enumerate(zip(x,y,strict=True)):walk(u,v,p+'['+str(i)+']')
        elif x!=y or type(x)!=type(y):report['identity_mismatches'].append(p)
    walk(a,b,path);report['agrees']=report['outside_tolerance']==0 and not report['identity_mismatches'];return report


def _value(body,path):
    need(type(path) is list and path,'explicit original primitive member path');value=body
    for key in path:
        need(type(key) in (str,int),'typed original primitive member path');value=value[key]
    return value


def derive_scaling(grader,expected):
    """A09 seals bindings; only this A12 code opens protected metric values."""
    member=grader.collection.members[expected['product_id']];need(member['status']=='sealed_analysis_specification','actual pretarget A09 analysis receipt')
    s=expected['support'];spec=s['analysis_specification'];fields(spec,('schema','points','recipe','fractions','training_counts','corpus_selection','checkpoints'),'complete original protected scaling programme');need(spec['schema']=='eegpt_scaling_from_primitives_v1','source-owned fixed mathematical reduction')
    need([r['id'] for r in spec['points']]==s['point_ids'] and len(spec['points']) in (4,8),'all original model/fraction points')
    points=[];used=set()
    for plan in spec['points']:
        fields(plan,('id','x','y'),'typed original scaling point');point={'id':plan['id']}
        for axis in ('x','y'):
            binding=plan[axis];fields(binding,('kind','product_ids','field','reduction'),'full primitive binding');ids=binding['product_ids'];need(ids and len(ids)==len(set(ids)) and set(ids)<=set(member['primitives']),'every original bound primitive present before target admission');used.update(ids);values=[]
            for pid in ids:
                if binding['kind']=='classification_metric':
                    need(binding['field'] in ('balanced_accuracy','cohen_kappa','weighted_f1','auroc','log_loss','brier'),'declared whole-case metric');result=grader.results[pid];need(result['status']=='adjudicated','all original protected metrics available');v=result['metrics'][binding['field']]
                elif binding['kind']=='captured_product_scalar':
                    need(pid in grader.captured,'actual full captured primitive');v=_value(grader.captured[pid]['product']['body'],binding['field'])
                else:raise ValueError('no literal paper outcome or caller-defined scaling function')
                values.append(finite(v,'complete original scaling primitive'))
            need(binding['reduction'] in ('single','arithmetic_mean'),'declared fixed original reduction')
            need(binding['reduction']!='single' or len(values)==1,'one scalar primitive');point[spec['recipe'][axis+'_field']]=math.fsum(values)/len(values)
        points.append(point)
    need(used==set(member['primitives']),'no omitted original scaling primitive or post-hoc subset')
    result=boundary(grader.budget, 'nested_scaling', scaling, points, spec['recipe']);body={'points':points,'parameter_convention':spec['recipe']['parameter_convention'],'fractions':spec['fractions'],'training_counts':spec['training_counts'],'corpus_selection':spec['corpus_selection'],'checkpoints':spec['checkpoints'],'formula':spec['recipe']['formula'],'parameters':result['parameters'].tolist(),'residuals':result['residuals'].tolist()}
    product={'status':'complete','type':'T06','body':body};validate_scientific_body(product,expected);return body


def inspect_product(grader,expected,policy):
    """Recompute all claimed diagnostic arithmetic from primitive full arrays."""
    import numpy as np
    pid=expected['product_id'];t=expected['type'];member=grader.collection.members[pid];tol=policy['consistency_tolerance']
    if t=='T06':return {'body':boundary(grader.budget, 'nested_derive_scaling', derive_scaling, grader, expected),'arrays':{},'checks':{'protected_derivation':True},'comparison':None}
    need(member['status']=='complete' and pid in grader.captured,'complete original diagnostic and captured producer')
    p=grader.captured[pid]['product'];b=p['body'];a=boundary(grader.budget, 'nested_arrays', arrays, grader, pid);checks={};comparable={'body':b,'arrays':a}
    if t=='T01':
        # Actual PREPARE receives only those source views. Their independent
        # native product is compared below; candidate prose is never provenance.
        need(grader.issuer.verify(grader.captured[pid]['process'],'process')['body']['call']=='PREPARE','actual original prepare producer');checks['original_process_bound']=True
    elif t=='T02':
        need(all(x in grader.session_artifact_pins[pid] for x in b['states']),'every opaque state is an actual captured file');checks['opaque_original_files_bound']=True
        # Model bytes are not loaded by the grader or compared across random
        # fits. Complete training/state provenance is retained separately.
        comparable={'body':{k:b[k] for k in ('train_support','selection','precision')},'arrays':{}}
    elif t=='T04':
        recomputed=[]
        for row in b['observations']:
            la=row['LA_numerator']/row['LA_denominator'];lr=row['LR_numerator']/row['LR_denominator'];recomputed.append(lr if b['variant']=='A' else la+lr)
        checks['all_raw_loss_identities']=boundary(grader.budget, 'nested_numeric_compare', numeric_compare, [r['total'] for r in b['observations']], recomputed, tol)
        from .diagnostics import loss_reduction
        checks['complete_partition_epoch_loss_reductions']=boundary(grader.budget, 'nested_loss_reduction', loss_reduction, b['observations'], b['variant'])
        comparable={'body':{'normalization':b['normalization'],'variant':b['variant'],'observations':[{k:r[k] for k in ('id','step','epoch','partition','LA_numerator','LA_denominator','LR_numerator','LR_denominator','total','exposure')} for r in b['observations']]},'arrays':{}}
    elif t=='T05':checks['full_architecture_fields_preserved']=True
    elif t=='T07':
        actual=boundary(grader.budget, 'nested_channel_similarity', channel_similarity, a[b['embeddings']], b['channel_ids'], b['physical_layout'], b['equality_policy']);checks['all_cosines_and_edge_sets']=boundary(grader.budget, 'nested_numeric_compare', numeric_compare, {'cosines': a[b['cosines']], 'zero_norm': b['zero_norm'], 'edges': b['edges']}, {'cosines': actual['cosines'], 'zero_norm': actual['zero_norm'], 'edges': actual['edges']}, tol)
    elif t=='T08':
        baseline=a[b['baseline_logits']];noise=a[b['noise']];changed=a[b['perturbed_logits']];delta=a[b['deltas']];need(changed.shape==delta.shape and changed.shape[2:]==baseline.shape and noise.shape==changed.shape[:3],'all original channel/draw/query/class cells')
        checks['every_logit_difference']=boundary(grader.budget, 'nested_numeric_compare', numeric_compare, delta, changed - baseline[None, None, :, :], tol);channels=expected['support']['perturbation_recipe']['channel_ids'];summaries={c:[boundary(grader.budget, 'nested_pearson_sufficient', pearson_sufficient, noise[i].reshape(-1), delta[i, :, :, k].reshape(-1)) for k in range(delta.shape[-1])] for i,c in enumerate(channels)};checks['full_Pearson_sufficient_statistics']=boundary(grader.budget, 'nested_numeric_compare', numeric_compare, b['pearson_sums'], summaries, tol)
        need(b['denominators']=={c:[r['n'] for r in summaries[c]] for c in channels},'all planned perturbation denominators')
    elif t=='T09':
        need(a[b['features']].shape[0]==a[b['tsne']].shape[0]==len(b['row_ids']),'full label-free feature population')
        # Orientation/translation/rotation of t-SNE is not an invariant neural
        # endpoint. Preserve full coordinates; compare original features only.
        comparable={'body':{k:b[k] for k in ('row_ids','layer','pooling','tsne_recipe')},'arrays':{'features':a[b['features']]}};checks['tsne_coordinates_retained_not_pixel_scored']=True
    elif t=='T10':
        raw=a[b['valid_mask']];need(np.isin(raw,[0.,1.]).all(),'actual binary valid-token mask');plan=expected['support']['attention_recipe'];result=boundary(grader.budget, 'nested_attention_summary', attention_summary, a[b['weights']], raw.astype(bool), plan);checks['all_attention_axes_normalization_and_aggregation']={'summary':result['summary'].tolist(),'counts':result['counts'].tolist(),'complete':True}
        comparable={'body':{'axes':b['axes'],'aggregation':b['aggregation']},'arrays':a}
    else:raise ValueError('unexpected source-owned diagnostic product '+t)
    for row in checks.values():
        if type(row) is dict and 'agrees' in row:need(row['agrees'],'scientific arithmetic consistency failed')
    return {'body':b,'arrays':a,'checks':checks,'comparison':comparable}


def grade_full_diagnostics(grader,qualification):
    need(grader.opened and grader.issuer.targets_open and grader.collection.closed,'whole original barrier before protected scientific reductions')
    policies=qualification['diagnostics'];need(set(policies)=={r['product_id'] for r in grader.schedule.diagnostics},'all original diagnostic adjudication policies, no missing difficult family')
    out={};grader.session_artifact_pins={pid:capture['artifact_pins'] for pid,capture in grader.captured.items()}
    # Bound peak retention to one complete candidate/reference pair. Every
    # independent reread is charged; no unreported full-campaign tensor cache.
    for expected in grader.schedule.diagnostics:
        grader.budget.guard('before_next_original_diagnostic')
        pid=expected['product_id'];policy=policies[pid];value=None;reference=None
        try:
            fields(policy,('source_identity','support_identity','consistency_tolerance','comparison_tolerance','reference_product_id','qualification'),'complete pre-outcome diagnostic qualification');digest(policy['source_identity']);digest(policy['qualification']);need(policy['support_identity']==expected['support_identity'] and policy['source_identity']==grader.qualification['operative_source_identity'],'exact full scientific support and selected actual adjudicator source')
            value=boundary(grader.budget,'diagnostic_product',inspect_product,grader,expected,policy);ref=policy['reference_product_id']
            if expected['scope']['actor_role']=='participant':
                need(ref==expected['plan']['reference_pair'] and ref in policies,'actual independent complete matching reference, not a supplied expected score');other=grader.collection.expected[ref];need(other['scope']['actor_role']=='reference' and other['type']==expected['type'],'independent matching scientific producer');need(all(other['scope'][k]==expected['scope'][k] for k in ('mode','access','family','repetition','dataset','outer_fold')),'identical original policy, support and scientific comparison axes')
                reference=boundary(grader.budget,'diagnostic_reference',inspect_product,grader,other,policies[ref]);a=value['comparison'] or {'body':value['body'],'arrays':value['arrays']};b=reference['comparison'] or {'body':reference['body'],'arrays':reference['arrays']};comparison=boundary(grader.budget,'diagnostic_comparison',numeric_compare,a,b,policy['comparison_tolerance']);evidence=[grader.collection.members[pid],grader.collection.members[ref]]
            else:
                need(ref is None,'independent reference is scientifically qualified at its own actual source, not self-scored against a fabricated duplicate');comparison=None;evidence=[grader.collection.members[pid]]
            t=expected['type'];body=value['body'];summary=None
            if t=='T01':summary={'original_cohort_counts':{k:len(set(v)) for k,v in body['cohort'].items()},'complete_split_counts':{k:len(v) for k,v in body['split'].items()},'exclusions':body['exclusions'],'transforms':body['transforms']}
            elif t=='T02':summary={k:body[k] for k in ('train_support','selection','precision')}
            elif t=='T04':summary={'variant':body['variant'],'normalization':body['normalization'],'complete_epoch_curves':value['checks']['complete_partition_epoch_loss_reductions']}
            elif t in ('T05','T06'):summary=body
            elif t=='T07':summary={'channel_ids':body['channel_ids'],'full_cosines':value['arrays'][body['cosines']].tolist(),'edges':body['edges'],'zero_norm':body['zero_norm'],'equality_policy':body['equality_policy']}
            elif t=='T08':summary={'all_Pearson_sufficient_statistics':body['pearson_sums'],'all_denominators':body['denominators'],'noise_policy':body['noise_policy'],'complete_original_draws':expected['support']['perturbation_recipe']['draw_ids']}
            elif t=='T09':summary={'complete_feature_rows':len(body['row_ids']),'layer':body['layer'],'pooling':body['pooling'],'tsne_recipe':body['tsne_recipe'],'pixel_orientation_is_not_scored':True}
            elif t=='T10':summary=value['checks']['all_attention_axes_normalization_and_aggregation']
            out[pid]={'status':'adjudicated','evidence':evidence,'scientific_summary':summary,'complete_internal_checks':value['checks'],'independent_reference':ref,'full_comparison':comparison,'scientific_agreement':None if comparison is None else comparison['agrees'],'derived_product':value['body'] if expected['type']=='T06' else None,'favorable_paper_conclusion_required':False,'native_or_causal_understanding_inferred':False}
        except BaseException as exc:
            status='failed' if grader.collection.members[pid]['status'] in ('complete','sealed_analysis_specification') else 'unavailable';out[pid]={'status':status,'evidence':[grader.collection.members[pid]],'reason':observation(exc),'scientific_agreement':None};grader.failures.append({'phase':'original_complete_diagnostic_adjudication','product_id':pid,**observation(exc)})
        finally:value=None;reference=None;a=None;b=None
    grader.budget.guard('after_complete_original_diagnostics');need(set(out)==set(policies),'every original scientific diagnostic has an explicit outcome');return out
