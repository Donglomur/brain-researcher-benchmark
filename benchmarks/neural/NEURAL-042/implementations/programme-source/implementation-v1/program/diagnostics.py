"""Post-target sanity references and prespecified status-first paired diagnostics.
These are not additional independent gold reports or task identities.
"""
from contracts import DESIGNS,CONTRASTS,METRICS

def mean(values):return sum(values)/len(values)if values else None

def sanity_references(target):
    lookup={(x['patient'],x['design'],x['contrast']):x for x in target['patients']};zero={};count={}
    people=[x['patient']for x in target['patients']if x['design']==DESIGNS[0]and x['contrast']==CONTRASTS[0]]
    for design in DESIGNS:
        for contrast in CONTRASTS:
            rows=[lookup[(p,design,contrast)]for p in people];support=[x for x in rows if x['metrics']is not None]
            zero[design+'/'+contrast]={'all_people':people,'reference_supported_people':[x['patient']for x in support],
                'unsupported_people':[x['patient']for x in rows if x['metrics']is None],
                'mae':{k:mean([abs(x['metrics'][k])for x in support])for k in METRICS},
                'support_is_conditioned_on_private_reference_not_predicted':True}
    for contrast in CONTRASTS:
        rows=[];matched=[];counted=[];common=[];errors={k:[]for k in METRICS}
        for p in people:
            lo=lookup[(p,'count_only',contrast)];hi=lookup[(p,'nuisance_matched',contrast)]
            if lo['metrics']is not None:counted.append(p)
            if hi['metrics']is not None:matched.append(p)
            both=lo['metrics']is not None and hi['metrics']is not None
            if both:
                common.append(p)
                for k in METRICS:errors[k].append(abs(lo['metrics'][k]-hi['metrics'][k]))
            rows.append({'person':p,'count_only_supported':lo['metrics']is not None,'matched_supported':hi['metrics']is not None,
                         'paired_metric_difference':{k:lo['metrics'][k]-hi['metrics'][k]for k in METRICS}if both else None})
        complete=bool(matched)and set(common)==set(matched)
        count[contrast]={'all36_people':rows,'count_only_support':counted,'matched_support':matched,'paired_intersection':common,
                        'count_only_as_matched_metric_mae_on_full_original_matched_support':{k:mean(v)if complete else None for k,v in errors.items()},
                        'separately_labeled_intersection_mae':{k:mean(v)for k,v in errors.items()},
                        'full_support_covered':complete,'intersection_is_not_the_canonical_estimand':True}
    return {'fixed_zero_metric_sanity':zero,'count_only_lower_reference':count,
            'independent_competent_gold':False,'additional_fits':0,'not_canonical_full_report_support_predictors':True}

def paired_reports(reports,target,per_cell):
    contrasts=[]
    for mode in('F','I'):
        contrasts.extend([(mode+'-O-T1',mode+'-O-T0','tool_access'),(mode+'-D-T0',mode+'-O-T0','disrupted_input'),(mode+'-A-T0',mode+'-O-T0','absent_input')])
    contrasts.extend([('I-'+world+'-'+tool,'F-'+world+'-'+tool,'investigation_access')for world,tool in(('O','T0'),('O','T1'),('D','T0'),('A','T0'))])
    result={}
    for left,right,kind in contrasts:
        ls=per_cell[left]['original_O_reconstruction'];rs=per_cell[right]['original_O_reconstruction']
        canonical_defined=ls['primary_equal_endpoint_mae']is not None and rs['primary_equal_endpoint_mae']is not None
        rows=[];endpoint_errors={d+'/'+c:[]for d in DESIGNS for c in CONTRASTS}
        for a,b,t in zip(reports[left]['patients'],reports[right]['patients'],target['patients']):
            key=t['design']+'/'+t['contrast'];eligible=canonical_defined and ls['endpoints'][key]['status']=='matched_support'and rs['endpoints'][key]['status']=='matched_support'and t['metrics']is not None
            la={k:abs(a['metrics'][k]-t['metrics'][k])for k in METRICS}if eligible else None
            rb={k:abs(b['metrics'][k]-t['metrics'][k])for k in METRICS}if eligible else None
            delta={k:la[k]-rb[k]for k in METRICS}if eligible else None
            if eligible:endpoint_errors[key].append(delta)
            rows.append({'person':t['patient'],'design':t['design'],'contrast':t['contrast'],'original_supported':t['metrics']is not None,
                         'left_supported':a['metrics']is not None,'right_supported':b['metrics']is not None,
                         'left_support_counts':[a['n_sessions'],a['n_channels']],'right_support_counts':[b['n_sessions'],b['n_channels']],
                         'left_absolute_error':la,'right_absolute_error':rb,'left_minus_right_absolute_error':delta})
        means={key:{k:mean([v[k]for v in values])for k in METRICS}for key,values in endpoint_errors.items()}
        result[left+'__versus__'+right]={'left':left,'right':right,'contrast':kind,'canonical_scores_defined':canonical_defined,
            'left_endpoint_status':{k:v['status']for k,v in ls['endpoints'].items()},'right_endpoint_status':{k:v['status']for k,v in rs['endpoints'].items()},
            'all144_person_endpoint_rows':rows,'paired_original_fixed_support_error_differences':means,
            'conditional_on_one_realized_policy_each':True,'author_variance_or_causal_effect_established':False,'neural_gain_scalar':None}
    return result
