"""Complete finite parametric roster; no neural data, fitting, or process access."""
from core import ROLES, PROFILES, MODALITIES, BRANCHES, high_level_jobs, need, identity, descriptor

SCHEMA='paper_i_complete_plan_v1'
SLOT_KEYS={'job_id','unit_id','stage','inner_fold','configuration_id','row','time_index','producer_role','profile','branch'}
STAGES=('prepare_originals','prepare_support','prepare_inner','inner_fit','inner_admit','inner_query','inner_error','selection','prepare_final','final_fit','final_admit','outer_query','reconstruct','grade_encoding','grade_native','report')
SLOT_SCHEMA={'keys':sorted(SLOT_KEYS),'stages':list(STAGES),'unused_fields':None,
    'query_granularity':'one source trial/time/modality record produces the full ordered required cell vector',
    'outer_query_configuration_id':None,'source_row_base':'zero-based source-relative coordinates, unchanged from admitted support'}


def integer(v,minimum=0):return type(v) is int and v>=minimum


def rows(value):
    need(type(value) is list and all(integer(x) for x in value) and len(set(value))==len(value),'Exact unique source row coordinate list')
    return set(value)


def partition(parts,whole):
    values=[rows(p) for p in parts]
    need(sum(map(len,values))==len(set().union(*values)) and set().union(*values)==set(whole),'Complete disjoint source partition; no dropped or added row')


def reference_configurations(profile):
    need(profile in PROFILES,'Exact reference information profile')
    result=[] if profile=='M' else [{'id':'context_average','representation':'context_average','penalty':None,'profile':profile}]
    for representation in ('raw','spline'):
        for penalty in (1e6,1e4,1e2,1.0,1e-2,1e-4,1e-6):
            result.append({'id':f'{representation}_ridge_{penalty:.0e}','representation':representation,'penalty':penalty,'profile':profile})
    return result


def validate_configurations(configurations):
    need(type(configurations) is dict and set(configurations)==set(ROLES),'Every complete producer configuration roster')
    for role,profiles in configurations.items():
        need(type(profiles) is dict and set(profiles)==set(PROFILES),'Every profile configuration roster')
        for profile,values in profiles.items():
            need(type(values) is list and values,'Nonempty precommitted finite search')
            if role=='reference':
                need(values==reference_configurations(profile),'Exact source-bound complete independent reference family and order')
                need(all(c['penalty'] is None or type(c['penalty']) in (int,float) for c in values),'No Boolean numerical penalty')
            else:need(all(type(c) is dict and set(c)=={'id','parameters'} and type(c['id']) is str and 0<len(c['id'])<=96 and type(c['parameters']) is dict for c in values),'Exact named configuration records')
            need(len({c['id'] for c in values})==len(values),'Unique configuration identities')
            if role=='reference':need(len(values)==(14 if profile=='M' else 15),'Full accepted raw/spline penalties and strong context option')
    return configurations


def validate_units(units):
    need(type(units) is list and units,'Complete admitted nonempty MainData unit census')
    keys=set();source_keys=set()
    for u in units:
        need(type(u) is dict and set(u)=={'unit_id','source_key','modality','cell_tokens','time_count','selected_rows','outer'},'Exact private unit roster')
        need(type(u['unit_id']) is str and 0<len(u['unit_id'])<=96 and u['unit_id'] not in keys,'Unique admitted unit identity');keys.add(u['unit_id'])
        need(type(u['source_key']) is str and 0<len(u['source_key'])<=1024 and u['modality'] in MODALITIES,'Exact source coordinate and modality')
        source=(u['source_key'],u['modality']);need(source not in source_keys,'No duplicate source-modality view as another unit');source_keys.add(source)
        cells=u['cell_tokens'];need(type(cells) is list and cells and all(type(c) is str and 0<len(c)<=256 for c in cells) and len(set(cells))==len(cells),'Full ordered unique source cell support')
        need(integer(u['time_count'],1),'Complete original target grid extent');selected=rows(u['selected_rows'])
        outer=u['outer'];need(type(outer) is list and len(outer)==5 and [o['fold'] for o in outer]==list(range(5)),'All five original outer folds')
        for o in outer:
            need(set(o)=={'fold','query','train','purged_train','inner'},'Exact outer support partition')
            partition([o['query'],o['train'],o['purged_train']],selected)
            need(o['query'] and o['train'],'Empty required outer support blocks the whole operation; never drop units')
            inners=o['inner'];need(type(inners) is list and len(inners)==4 and [v['fold'] for v in inners]==[f for f in range(5) if f!=o['fold']],'All four nested training-only folds')
            for i in inners:
                need(set(i)=={'fold','train','validation','purged_train'},'Exact inner support partition')
                partition([i['train'],i['validation'],i['purged_train']],o['train'])
                need(set(i['validation'])==set(outer[i['fold']]['query']) & set(o['train']),'Complete original inner validation block after outer purge')
                need(i['train'] and i['validation'],'Every required inner support remains nonempty or the complete operation is blocked')
        queries=[r for o in outer for r in o['query']]
        need(len(queries)==len(set(queries)) and set(queries)==selected,'Every eligible source row is queried exactly once across five folds')
    return units


def count_plan(units,configurations):
    """Arithmetic over complete ranges; never materialize per-time query rows."""
    mandatory=2+27+12+9+1;potential_final=0;inner_queries=outer_queries=0;inner_fit_phases=0;reference_inner_cell_fits=reference_final_cell_fits=0
    for job in high_level_jobs():
        if job['kind']!='encoding':continue
        k=len(configurations[job['role']][job['profile']])
        for unit in units:
            o=unit['outer'][job['fold']];iq=k*sum(len(i['validation']) for i in o['inner'])*unit['time_count'];oq=len(o['query'])*unit['time_count']
            mandatory+=6+12*k+iq+oq;potential_final+=k;inner_queries+=iq;outer_queries+=oq;inner_fit_phases+=4*k
            if job['role']=='reference':
                reference_inner_cell_fits+=4*k*len(unit['cell_tokens']);reference_final_cell_fits+=len(unit['cell_tokens'])
    return {'high_level_producers':87,'encoding_producers':60,'native_reconstruction_producers':27,
        'bootstrap_phases':2,'encoding_grade_phases':12,'native_grade_phases':9,'report_phases':1,
        'mandatory_phase_slots':mandatory,'potential_final_fit_slots':potential_final,'potential_final_admission_slots':potential_final,'maximum_phase_slots':mandatory+2*potential_final,
        'inner_fit_process_phases':inner_fit_phases,'inner_model_admission_phases':inner_fit_phases,'inner_vector_query_process_phases':inner_queries,'outer_vector_query_process_phases':outer_queries,
        'total_vector_query_process_phases':inner_queries+outer_queries,
        'reference_inner_cell_fits':reference_inner_cell_fits,'reference_final_cell_fits':reference_final_cell_fits,
        'reference_total_cell_fits':reference_inner_cell_fits+reference_final_cell_fits,
        'required_acquisition_modality_units':len(units),'required_cell_coordinates':sum(len(u['cell_tokens']) for u in units),
        'cell_fit_cost_is_not_process_count':True,'actual_numerical_cost_or_peak_memory':None}


def build_plan(units,configurations):
    validate_units(units);validate_configurations(configurations)
    plan={'schema':SCHEMA,'high_level_jobs':high_level_jobs(),'units':units,'configurations':configurations,
          'counts':count_plan(units,configurations),'slot_schema':SLOT_SCHEMA}
    validate_plan(plan);return plan


def validate_plan(plan):
    need(type(plan) is dict and set(plan)=={'schema','high_level_jobs','units','configurations','counts','slot_schema'} and plan['schema']==SCHEMA,'Exact full compact plan schema')
    need(plan['high_level_jobs']==high_level_jobs() and plan['slot_schema']==SLOT_SCHEMA,'Original all87 producer and exact slot contract')
    validate_units(plan['units']);validate_configurations(plan['configurations'])
    need(plan['counts']==count_plan(plan['units'],plan['configurations']),'Independently recomputed complete parametric work counts')
    return plan


def slot(stage,**values):
    need(set(values)<=SLOT_KEYS-{'stage'},'Known logical phase keys')
    return {**{k:None for k in sorted(SLOT_KEYS)},'stage':stage,**values}


def valid_slot(plan,s):
    """Validate one exact potential slot. Final fit selection is checked later."""
    try:
        need(type(s) is dict and set(s)==SLOT_KEYS and s['stage'] in STAGES,'Exact complete slot')
        stage=s['stage'];active={'stage'}
        if stage in ('prepare_originals','prepare_support','report'):pass
        elif stage=='grade_encoding':
            active|={'producer_role','profile'};need(s['producer_role'] in ROLES and s['profile'] in PROFILES,'All pooled arm/profile grades')
        elif stage=='grade_native':active.add('branch');need(s['branch'] in BRANCHES,'All three-arm native branch grades')
        else:
            jobs={j['job_id']:j for j in plan['high_level_jobs']};need(s['job_id'] in jobs,'Known exact high-level job')
            j=jobs[s['job_id']];active|={'job_id','producer_role'};need(s['producer_role']==j['role'],'Exact producer arm')
            if stage=='reconstruct':
                active.add('branch');need(j['kind']=='reconstruction' and s['branch']==j['branch'],'Exact original native branch')
            else:
                active|={'unit_id','profile'};need(j['kind']=='encoding' and s['profile']==j['profile'],'Exact encoding information profile')
                units={u['unit_id']:u for u in plan['units']};need(s['unit_id'] in units,'Full admitted unit identity');u=units[s['unit_id']];o=u['outer'][j['fold']]
                configs={c['id'] for c in plan['configurations'][j['role']][j['profile']]}
                if stage.startswith('inner_') or stage=='prepare_inner':
                    active.add('inner_fold');inners={i['fold']:i for i in o['inner']};need(type(s['inner_fold']) is int and s['inner_fold'] in inners,'Original nested fold')
                    if stage!='prepare_inner':active.add('configuration_id');need(s['configuration_id'] in configs,'Complete precommitted inner search')
                    if stage=='inner_query':
                        active|={'row','time_index'};need(type(s['row']) is int and s['row'] in inners[s['inner_fold']]['validation'],'Exact inner query support')
                        need(integer(s['time_index']) and s['time_index']<u['time_count'],'Full original time grid')
                elif stage in ('final_fit','final_admit'):active.add('configuration_id');need(s['configuration_id'] in configs,'Potential final selected fit')
                elif stage=='outer_query':
                    active|={'row','time_index'};need(type(s['row']) is int and s['row'] in o['query'],'Exact outer query support')
                    need(integer(s['time_index']) and s['time_index']<u['time_count'],'Full outer target grid')
                else:need(stage in ('selection','prepare_final'),'Known per-unit stage')
        need(all(s[k] is None for k in SLOT_KEYS-active),'Every irrelevant slot coordinate must be null')
        return True
    except (ValueError,KeyError,TypeError):return False


def validate_selection(plan,s):
    need(type(s) is dict and set(s)=={'job_id','unit_id','groups','selection_pin'},'Authenticated selection descriptor')
    descriptor(s['selection_pin']);jobs={j['job_id']:j for j in plan['high_level_jobs']};units={u['unit_id']:u for u in plan['units']}
    need(s['job_id'] in jobs and jobs[s['job_id']]['kind']=='encoding' and s['unit_id'] in units,'Exact selection producer/unit')
    j=jobs[s['job_id']];u=units[s['unit_id']];configs={c['id'] for c in plan['configurations'][j['role']][j['profile']]};groups=s['groups']
    need(type(groups) is list and groups,'Complete nonempty selected model groups');chosen=set();cells=[]
    for g in groups:
        need(type(g) is dict and set(g)=={'configuration','configuration_id','cell_indices','cell_tokens'} and g['configuration_id'] in configs and g['configuration_id'] not in chosen,'One group per selected precommitted configuration')
        expected=next(c for c in plan['configurations'][j['role']][j['profile']] if c['id']==g['configuration_id'])
        need(g['configuration']==expected,'Exact precommitted selected configuration body')
        need(g['cell_tokens']==[u['cell_tokens'][i] for i in g['cell_indices'] if integer(i) and i<len(u['cell_tokens'])],'Exact full selected cell token axis')
        chosen.add(g['configuration_id']);need(type(g['cell_indices']) is list and g['cell_indices'] and all(integer(i) and i<len(u['cell_tokens']) for i in g['cell_indices']),'Exact nonempty required cell group');cells.extend(g['cell_indices'])
    need(len(cells)==len(set(cells))==len(u['cell_tokens']) and set(cells)==set(range(len(u['cell_tokens']))),'All required cells exactly once, no favourable cell selection')
    return chosen


def summarize_missing(plan,seen,selections=None):
    """Count every potential range without treating unobserved/unused as zero."""
    validate_plan(plan);need(type(seen) is list and type(selections or []) is list,'Observed phase and admitted selection metadata')
    observed={};phases=set();rows=[]
    for r in seen:
        need(type(r) is dict and {'slot','phase_id','status','resources_closed','receipt_pin'}<=set(r),'Complete observed nested disposition')
        need(valid_slot(plan,r['slot']),'Observed exact planned slot');key=identity(r['slot'])
        need(key not in observed and type(r['phase_id']) is str and r['phase_id'] not in phases,'No duplicate logical phase or hidden retry');phases.add(r['phase_id'])
        need(r['status'] in ('captured','failed','unknown') and type(r['resources_closed']) is bool,'Explicit observed phase outcome and custody')
        if r['receipt_pin'] is not None:descriptor(r['receipt_pin'])
        if r['status']=='captured':need(r['receipt_pin'] is not None,'Captured phase needs exact receipt')
        observed[key]=r;rows.append(r)
    selected={};unresolved=0;selected_expected=0;unselected_expected=0
    for s in selections or []:
        key=(s['job_id'],s['unit_id']);need(key not in selected,'One authenticated selection per producer/unit')
        chosen=validate_selection(plan,s);j=next(j for j in plan['high_level_jobs'] if j['job_id']==s['job_id'])
        selector=slot('selection',job_id=j['job_id'],unit_id=s['unit_id'],producer_role=j['role'],profile=j['profile'])
        r=observed.get(identity(selector));need(r and r['status']=='captured' and r['resources_closed'] is True,'Selection must have independently captured closed phase')
        selected[key]=chosen
    for j in plan['high_level_jobs']:
        if j['kind']!='encoding':continue
        k=len(plan['configurations'][j['role']][j['profile']])
        for u in plan['units']:
            chosen=selected.get((j['job_id'],u['unit_id']))
            if chosen is None:unresolved+=k
            else:selected_expected+=len(chosen);unselected_expected+=k-len(chosen)
    mandatory=[r for r in rows if r['slot']['stage'] not in ('final_fit','final_admit')];final=[r for r in rows if r['slot']['stage'] in ('final_fit','final_admit')]
    selected_final=[];unexpected=[]
    for r in final:
        s=r['slot'];chosen=selected.get((s['job_id'],s['unit_id']))
        if chosen is None or s['configuration_id'] not in chosen:unexpected.append(r['phase_id'])
        else:selected_final.append(r)
    def tally(values):
        return {'captured':sum(r['status']=='captured' and r['resources_closed'] for r in values),
                'failed':sum(r['status']=='failed' for r in values),
                'unknown':sum(r['status']=='unknown' or not r['resources_closed'] for r in values)}
    m=tally(mandatory);f=tally(selected_final);missing=plan['counts']['mandatory_phase_slots']-len(mandatory);final_missing=2*selected_expected-len(selected_final)
    need(missing>=0 and final_missing>=0,'Observed work cannot exceed exact planned support')
    complete=missing==0 and final_missing==0 and unresolved==0 and not unexpected and m['captured']==len(mandatory) and f['captured']==len(selected_final)
    return {'schema':'paper_i_full_parametric_coverage_v1','complete':complete,'counts':plan['counts'],
        'mandatory_not_started':missing,'mandatory_observed':len(mandatory),'mandatory_dispositions':m,
        'selected_final_fit_expected':selected_expected,'selected_final_admission_expected':selected_expected,
        'selected_final_fit_not_started':selected_expected-sum(r['slot']['stage']=='final_fit' for r in selected_final),
        'selected_final_admission_not_started':selected_expected-sum(r['slot']['stage']=='final_admit' for r in selected_final),
        'selected_final_phase_not_started':final_missing,'selected_final_phase_dispositions':f,
        'not_selected_configurations':unselected_expected,'not_selected_by_authenticated_training':2*unselected_expected,'selection_unresolved_potential_final_slots':2*unresolved,
        'unadmitted_or_unselected_final_phases':unexpected,'observed_phase_count':len(rows),
        'observed_vector_query_launches':sum(r['slot']['stage'] in ('inner_query','outer_query') for r in rows),
        'query_launches_are_not_neural_cell_count':True,'actual_model_load_count':None,
        'actual_model_load_note':'Must come from admitted per-query worker telemetry; a full vector artifact may contain several fitted model groups.',
        'unknown_actual_cost_is_not_zero':True}
