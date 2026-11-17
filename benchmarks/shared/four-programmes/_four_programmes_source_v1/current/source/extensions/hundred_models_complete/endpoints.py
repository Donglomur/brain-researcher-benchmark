"""Complete figure-data builders; native rendering/caller parity stays separately bound."""
from statistics import median
from .guard import need,Unscorable,encoded,bare

def selected_layer(layers,subject_values):
    need(len(layers)==len(subject_values) and bool(layers),'complete layer axis')
    need(all(len(x)==10 for x in subject_values),'all ten participant values')
    if any(v is None for row in subject_values for v in row):
        return {'status':'undefined','layers':layers,'subject_values':subject_values,'selected':None}
    means=[sum(row)/10 for row in subject_values];index=max(range(len(means)),key=lambda k:means[k])
    return {'status':'defined','layers':layers,'subject_values':subject_values,'layer_means':means,'selected':index,'selected_layer':layers[index],'R':means[index],'R_array':subject_values[index]}

def group_rows(models,selection,group_order):
    output=[]
    for label,members in group_order:
        need(members and all(m in selection for m in members),'complete group membership')
        values=[selection[m].get('R') for m in members]
        output.append({'group':label,'members':list(members),'observed':values,'median':None if None in values else median(values),'mean':None if None in values else sum(values)/len(values)})
    return output

def rankings(selection,action_models,image_baseline):
    need(len(action_models)==51 and len(image_baseline)==41,'whole Figure3/8 support')
    values=[selection[m].get('R') for m in action_models]
    baseline=[selection[m].get('R') for m in image_baseline]
    if None in values or None in baseline:return {'status':'undefined','complete_model_order':action_models,'source_records':selection}
    order=sorted(range(51),key=lambda k:values[k])
    sorted_baseline=sorted(baseline)
    return {'status':'defined','source_tie_policy':'stable original model order; native pandas historical tie parity remains G13','models':[action_models[k] for k in order],'records':[selection[action_models[k]] for k in order],'imagenet_reference_values':baseline,'imagenet_reference_median':sorted_baseline[20],'imagenet_reference_IQR':[sorted_baseline[10],sorted_baseline[30]]}

def ceiling_scaling(selection,ceilings):
    lnc,unc=ceilings
    return {'raw':selection,'LNC':lnc,'UNC':unc,'scaled':None if unc in (None,0) else {m:None if r.get('R') is None else r['R']/unc for m,r in selection.items()},'scaled_LNC':None if lnc is None or unc in (None,0) else lnc/unc,'variance_explained_claim':False}

def figure_records(scope,all_results,appendix):
    """Every numbered figure is bound to actual numerical results or explicit holds."""
    need(set(all_results)=={'inference','dimension16','dimension17','selections','depth','rankings','complexity','scaled','auxiliary18'},'complete required endpoint families')
    need(set(appendix)=={'F15','F19','F20','F21','F22'},'remaining appendix outputs or explicit holds')
    mapping={1:['scope'],2:['inference','selections','depth'],3:['rankings'],4:['inference','depth'],5:['inference','depth'],6:['complexity'],7:['depth'],8:['rankings'],9:['inference'],10:['depth'],11:['inference'],12:['depth'],13:['scaled'],14:['depth'],15:['F15'],16:['dimension16'],17:['dimension17'],18:['auxiliary18'],19:['F19'],20:['F20'],21:['F21'],22:['F22']}
    figures=[]
    for n,keys in mapping.items():
        values=[scope if key=='scope' else appendix[key] if key.startswith('F') else all_results[key] for key in keys]
        figures.append({'figure':n,'complete_required_support':not any(held(x) for x in values),'families':keys,'endpoint_pins':[bare(encoded(x)) for x in values],'status':'required_unscorable' if any(held(x) for x in values) else 'source_output_unqualified'})
    tables=[{'table':1,'model_roster':scope['declared_catalog'],'group_counts':scope['primary99_groups'],'original_family_footnote_parity_qualified':False},{'table':2,'model_roster':scope['declared_catalog'],'printed_conflict':'Printed VideoMAEv2 S appears twice; the bound source configurations distinguish S and B.','printed_table_parity_qualified':False}]
    return {'figures':figures,'tables':tables,'scientific_qualification':False}

def held(value):
    if isinstance(value,dict):return value.get('status') in ('required_unscorable','undefined') or any(held(v) for v in value.values())
    if isinstance(value,(tuple,list)):return any(held(v) for v in value)
    return False

def reproduction_errors(candidate,reference):
    """Complete numerical result trees; absence never becomes a smaller denominator."""
    import math
    counts={'numeric':0,'undefined':0,'absolute_error':0.,'max_absolute_error':0.};errors=[]
    def visit(a,b,path):
        if type(b)is dict:
            need(type(a)is dict and set(a)==set(b),'complete metric keys '+path)
            for k in sorted(b):visit(a[k],b[k],path+'/'+k)
        elif type(b)is list:
            need(type(a)is list and len(a)==len(b),'complete metric axis '+path)
            for k,(x,y) in enumerate(zip(a,b)):visit(x,y,path+'/'+str(k))
        elif b is None:
            need(a is None,'exact undefined coverage '+path);counts['undefined']+=1
        elif type(b)is int:
            need(type(a)is int and a==b,'exact discrete endpoint identity '+path)
        elif type(b)is float:
            import math
            need(type(a)in(int,float) and math.isfinite(a) and math.isfinite(b),'finite metric '+path)
            error=abs(a-b);need(math.isfinite(error),'unrepresentable endpoint difference '+path)
            errors.append(error);counts['numeric']+=1;counts['max_absolute_error']=max(counts['max_absolute_error'],error)
        else:need(a==b,'exact metric identity '+path)
    visit(candidate,reference,'')
    try:total=math.fsum(errors)
    except OverflowError as error:raise ValueError('unrepresentable total endpoint error') from error
    need(math.isfinite(total),'finite accumulated endpoint error');counts['absolute_error']=total
    counts['mean_absolute_error']=total/counts['numeric'] if counts['numeric'] else None
    need(counts['mean_absolute_error'] is None or math.isfinite(counts['mean_absolute_error']),'finite final endpoint error')
    return {'status':'numerical_comparison_only','metrics':counts,'success_threshold':None,'native_method_execution_proved':False,'historical_parity_proved':False}

def improvement_admission(protocol):
    required=('generalization_population','development_panel','private_panel','overlap_audit','baseline','candidate_freeze','selection_budget','primary_metric','uncertainty_plan','multiplicity_plan')
    for key in required:
        if not protocol.get(key):raise Unscorable('G17/G18','Improvement '+key+' is not admitted')
    need(protocol['generalization_population'] in ('new_people','new_stimuli','new_people_and_stimuli'),'explicit population before uncertainty calibration')
    need(protocol['private_panel']['published_exposed'] is False,'published panel is not independent improvement evidence')
    return {'admitted_protocol':bare(encoded(protocol)),'execution_qualified':False}
