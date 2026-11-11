"""Scientific endpoint view, separate from each run's private execution custody.

Only enumerated provenance fields at their exact producer schema locations are
removed. Every other field, scientific identity, value and coverage record stays.
This is not a recursive blacklist of strings such as hash or path.
"""
from .guard import need,bare,encoded,descriptor

FIGURE_FAMILIES={1:['scope'],2:['inference','selections','depth'],3:['rankings'],4:['inference','depth'],5:['inference','depth'],6:['complexity'],7:['depth'],8:['rankings'],9:['inference'],10:['depth'],11:['inference'],12:['depth'],13:['scaled'],14:['depth'],15:['F15'],16:['dimension16'],17:['dimension17'],18:['auxiliary18'],19:['F19'],20:['F20'],21:['F21'],22:['F22']}
INFERENCE_WRAPPER_CUSTODY={'compiled_catalog','ordered_layer_catalog_sha256','actual_inputs_authenticated_by_this_program','historical_reproduction_claimed','scientific_execution_qualified'}
INFERENCE_RESULT_CUSTODY={'layer_catalog_sha256','shared_schedule_origin_verified','historical_schedule_recovered','native_arithmetic_parity_qualified','authentic_inputs_qualified','scientific_qualification'}
DIMENSION_CUSTODY={'run_binding_sha256','emitted_roi_sha256','aggregate_cells','catalog_global99_complete','input_test102_catalog_prerequisite','historical_execution_proven','scientific_qualified','native_numeric_parity_qualified','renderer_qualified'}
APPENDIX_CUSTODY={'call','admitted_call','historical_rendering_qualified'}

def without(record,fields):
    need(type(record)is dict,'named source endpoint record')
    return {k:v for k,v in record.items() if k not in fields}

def depth_groups(groups):
    out=[]
    for group in groups:
        row=dict(group)
        row['adjustment']=without(row['adjustment'],{'aggregate_cells','native_numeric_parity_qualified','scientific_qualified'})
        row['normalized']=without(row['normalized'],{'native_numeric_parity_qualified','scientific_qualified'})
        out.append(row)
    return out

def family(name,value):
    if name=='inference':
        if value.get('status')=='required_unscorable':return value
        need(value['schema']=='hundred_models_bound_inference_result_v1','known inference producer schema')
        out=without(value,INFERENCE_WRAPPER_CUSTODY)
        out['inference']=without(value['inference'],INFERENCE_RESULT_CUSTODY)
        # Schedule digests are shared scientific inputs, not private execution paths.
        need(out['schedule_sha256']==out['inference']['schedule_sha256'],'same scientific permutation schedule')
        return out
    if name in ('dimension16','dimension17'):
        need(type(value)is list and bool(value),'complete dimension event stream')
        out=[]
        for event in value:
            row=without(event,DIMENSION_CUSTODY)
            if 'depth_traces' in row:
                row['depth_traces']=[without(x,{'aggregate_cells'}) for x in row['depth_traces']]
            out.append(row)
        need(out[-1].get('whole_branch_complete') is True,'actual complete dimension EOF remains scientific coverage')
        return out
    if name in ('F15','F19','F20','F21','F22'):
        out=without(value,APPENDIX_CUSTODY)
        if 'depth_data' in out:out['depth_data']={roi:depth_groups(groups) for roi,groups in out['depth_data'].items()}
        return out
    if name=='depth':
        return {comparison:{roi:depth_groups(groups) for roi,groups in regions.items()} for comparison,regions in value.items()}
    need(name in ('scope','selections','depth','rankings','complexity','scaled','auxiliary18'),'closed scientific endpoint family')
    return value

def scientific_figures(figures):
    need(type(figures)is list and [v['figure'] for v in figures]==list(range(1,23)),'all22 scientific figure identities')
    rows=[]
    for record in figures:
        need(set(record)=={'figure','status','data'},'complete figure record schema')
        names=FIGURE_FAMILIES[record['figure']]
        need(set(record['data'])==set(names),'every required scientific family without omissions or additions')
        rows.append({'figure':record['figure'],'status':record['status'],'data':{name:family(name,record['data'][name]) for name in names}})
    return rows

def compare_scientific_endpoints(candidate,reference):
    from .endpoints import reproduction_errors
    need([x['table'] for x in candidate['tables']]==[1,2] and [x['table'] for x in reference['tables']]==[1,2],'both scientific model tables')
    return reproduction_errors({'figures':scientific_figures(candidate['figures']),'tables':candidate['tables']},{'figures':scientific_figures(reference['figures']),'tables':reference['tables']})

def scientific_support(scope,inputs):
    return {'subjects':list(scope['subjects']),'rois':list(inputs['rois']),'models':[v['model_id'] for v in scope['declared_catalog']]+['videomae_B_pretrainONLY'],'panels':{panel:{'ordered_ids':list(inputs['panels'][panel]['ordered_ids']),'repetitions':inputs['panels'][panel]['repetitions']} for panel in ('test','train')}}

def validate_shared_support(scope,candidate,reference,admitted_pin):
    """Explicit identities are compared, including train stimuli not fixed by scope."""
    need(candidate==reference and bare(encoded(reference))==admitted_pin,'same independently admitted scientific biological/model support')
    need(set(reference)=={'subjects','rois','models','panels'},'closed shared scientific support schema')
    need(reference['subjects']==scope['subjects'] and reference['rois']==[r for rows in scope['roi_groups'].values() for r in rows],'complete ordered people and regions')
    need(reference['models']==[v['model_id'] for v in scope['declared_catalog']]+['videomae_B_pretrainONLY'],'complete99 plus auxiliary model identity')
    need(set(reference['panels'])=={'test','train'},'both panels remain required')
    for panel,n,reps in (('test',102,10),('train',1000,3)):
        row=reference['panels'][panel];need(set(row)=={'ordered_ids','repetitions'},'closed panel support')
        ids=row['ordered_ids'];need(type(ids)is list and len(ids)==len(set(ids))==n and all(type(i)is str and i for i in ids),'complete ordered independent stimulus ids')
        need(row['repetitions']==reps,'complete source repetition support')
    need(reference['panels']['test']['ordered_ids']==scope['test_panel']['declared_ids'],'exact source test102 order')
    need(not set(reference['panels']['test']['ordered_ids'])&set(reference['panels']['train']['ordered_ids']),'test/train identities disjoint')

def validate_run_custody(document,admission):
    """Verify each run against its own independent admission, never against its peer.

    The operator must qualify the real input/plan/runtime/receipt chain externally.
    This function checks that the accepted qualification binds the submitted bytes;
    it cannot turn candidate declarations into a qualified scientific execution.
    """
    need(admission['schema']=='hundred_models_independently_validated_run_custody_v1' and admission['qualified'] is True,'independent own-run custody qualification required')
    need(admission['submission']==bare(encoded(document)),'qualified exact own submission bytes')
    custody=document['custody'];need(custody['schema']=='hundred_models_own_run_custody_v1','own execution custody schema')
    need(set(custody)=={'schema','inputs','plan','runtime_source','environment','source_workspace','raw_endpoint_records'},'closed own-run custody fields')
    for name in ('inputs','plan','runtime_source','environment','raw_endpoint_records'):
        pin=custody[name];need(type(pin)is dict and set(pin)=={'bytes','sha256'},'bare own-run identity')
        descriptor({'path':'identity',**pin})
    need(type(custody['source_workspace'])is str and custody['source_workspace'],'own workspace identity')
    need(admission['custody']==bare(encoded(custody)),'qualified own custody record')
    for name in ('inputs','plan','runtime_source'):
        need(admission[name]==custody[name],'own qualified '+name+' binding')
    descriptor(admission['completed_execution_receipt'])
    return {'custody_checked_against_own_admission':True,'scientific_execution_qualified_by_this_function':False}
