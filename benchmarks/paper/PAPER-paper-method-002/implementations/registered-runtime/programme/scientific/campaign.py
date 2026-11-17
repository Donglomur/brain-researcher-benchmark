"""Prospective full-output scientific source compiler, without execution authority.

The legacy per-unit/2MiB route remains unchanged. This route owns one complete
family producer per information condition and preserves every original unit in
an explicit output-coordinate inverse. Operator-selected extents are capacity
inputs, never observations, receipts, qualification or original-data authority.
"""
from runtime.strict import require,integer,relative,canonical_bytes,digest,unique
from runtime.profiles import GROUPS,CONDITIONS,CONFLICTS,GATES
from runtime.programme import PRODUCTS,DEPENDENCIES
from runtime.catalogue import known_units
from .output_support import require_full_support
from .json_extent import layout_bytes

TASK='PAPER-paper-method-002'
WIDTH={'float64-le':8,'float32-le':4,'int64-le':8,'uint8':1}
DISPATCH={
    **{g:('scientific.technical','run')for g in('J01','J02','J03','J04','J05','J06','J07','J08','J32','J35','J36')},
    'J09':('scientific.retina','run'),'J10':('scientific.synthetic','run'),'J11':('scientific.allen','run'),
    'J12':('scientific.conductance','run'),'J13':('scientific.posterior','run'),'J14':('scientific.nonlinear','run'),
    **{g:('scientific.retina','run')for g in('J15','J16','J17','J18','J19')},
    **{g:('scientific.rnn','run')for g in('J20','J21','J22','J23','J24','J25','J33','J34')},
    **{g:('scientific.vision','run')for g in('J26','J27','J28','J29','J30','J31')},
}
DEPENDENCY_V2={**DEPENDENCIES,'J27':[],'J26':['J27'],
               'J36':['J01','J02','J06','J07','J08','J09','J11','J13','J18','J21']}
LIMITS=('input_bytes','input_member_bytes','output_bytes','output_member_bytes','array_memory_bytes','log_bytes')
RESOURCE_LIMITS=('wall_ns','cleanup_ns','memory_bytes','output_bytes','stdout_bytes','stderr_bytes','pids','cpu_quota_us','cpu_period_us')
REQUIRED_PARENT_PRODUCTS={
    **{g:{('vision-fit-state','J27','fit_parameter_identity')}for g in('J26','J28','J29','J30','J31')},
    **{g:{('trained_rnn_parameters','J22','psychometric_responses')}for g in('J23','J34')},
    'J25':{('dms_checkpoint','J24','curriculum_loss')},
    'J36':{
        ('note1_source_map','J01','architecture_source_map'),
        ('note2_jaxley_voltage','J02','Jaxley_voltage'),('note2_neuron_voltage','J02','NEURON_voltage'),
        ('note2_clock','J02','clock'),
        ('note3_physical','J06','physical_parameters'),('note3_untransformed','J06','untransformed_parameters'),('note3_bounds','J06','bounds'),
        ('note3_optimizer_updates','J07','per_group_updates'),
        ('note3_full_gradient','J08','full_gradient'),('note3_checkpoint_gradient','J08','checkpoint_gradient'),
        ('note3_boundary_before','J09','boundary_state_before'),('note3_boundary_after','J09','boundary_state_after'),('note3_gradient_cuts','J09','gradient_cuts'),
        ('note4_allen_voltage','J11','full_voltage'),
        ('note5_log_density','J13','log_density'),('note5_acceptance','J13','acceptance'),('note5_mixing','J13','mixing_calibration'),
        ('note6_contours','J18','contours'),('note6_evidence','J18','ASD_evidence_trajectory'),
        ('note7_norms','J21','Lyapunov_norms'),('note7_counts','J21','QR_step_counts'),('note7_maximal','J21','maximal_Lyapunov')},
}

def ordered_groups():
    result=[];remaining=set(GROUPS)
    while remaining:
        ready=[g for g in GROUPS if g in remaining and set(DEPENDENCY_V2.get(g,[]))<=set(result)]
        require(ready,'full scientific source dependency cycle')
        result.extend(ready);remaining.difference_update(ready)
    return result

def pin(value):
    require(type(value)is dict and set(value)=={'path','bytes','sha256'},'exact source pin fields')
    relative(value['path']);integer(value['bytes'],'pinned source bytes',0)
    require(type(value['sha256'])is str and len(value['sha256'])==64 and all(c in'0123456789abcdef'for c in value['sha256']),'exact SHA256')
    return value

def product_extent(product):
    require(type(product)is dict,'product descriptor')
    require(product['format']in('json','jaxley-flat-numeric-v1'),'fixed complete product format')
    shape=product['shape'];axes=product['axes'];require(type(shape)is list and type(axes)is list and len(shape)==len(axes),'shape/coordinate inverse')
    elements=1
    for extent,axis in zip(shape,axes):
        integer(extent,'complete axis extent',1);require(type(axis)is list and len(axis)==extent,'literal complete axis identities')
        unique(axis,'scientific axis');elements*=extent
    require(type(product['unit'])is str and product['unit'],'explicit scientific units')
    require(product['lineage']and product['native_source_pin'],'source identity and original lineage required')
    bound=product['extent'];require(set(bound)=={'kind','bytes','derivation'},'complete extent derivation')
    integer(bound['bytes'],'whole product extent',1);require(type(bound['derivation'])is dict and bound['derivation'],'no unexplained allowance')
    if product['format']=='jaxley-flat-numeric-v1':
        require(shape and product['dtype']in WIDTH,'complete numeric dimensions/dtype')
        require(bound['kind']=='exact'and bound['bytes']==elements*WIDTH[product['dtype']],'whole numeric byte inverse')
    else:
        require(product['dtype']is None and bound['kind']=='upper_bound','JSON requires explicit full-schema upper bound')
        require(bound['derivation'].get('covers_all_histories')is True and bound['derivation'].get('variable_count_bound_source'),'unbounded JSON history cannot be silently truncated')
        require(bound['bytes']>=layout_bytes(bound['derivation']['layout'])+1,'whole JSON schema and all admitted rows exceed byte allowance')
    return bound['bytes']

def _scope(group,row,rosters):
    units=row['legacy_units'];require(type(units)is list and units,'whole legacy unit roster')
    unique(units,'legacy units');expected=known_units(group,rosters)
    if expected is not None:require(units==expected,'changed legacy full-family denominator')
    inverse=row['unit_inverse'];require(type(inverse)is list and [r['unit']for r in inverse]==units,'complete ordered unit-to-product inverse')
    for item in inverse:
        require(item['required']is True and item['all_replicates_retained']is True,'available-case/subset inverse')
        require(set(item['product_coordinates'])==set(PRODUCTS[group]),'each original unit maps every required product')
        for role,coordinates in item['product_coordinates'].items():
            require(type(coordinates)is dict and set(coordinates)=={'selector_schema','selection','source_basis'},'closed product coordinate inverse')
            require(coordinates['selector_schema']=='full_family_coordinate_selector_v1'and type(coordinates['source_basis'])is str and coordinates['source_basis'],'explicit source-grounded coordinate selector')
            selected=coordinates['selection'];require(type(selected)is dict,'closed coordinate selection')
            product=next(p for p in row['output_contract']['outputs']if p['artifact_id']==role)
            if selected.get('kind')=='whole_product':require(set(selected)=={'kind'},'whole product selector fields')
            elif selected.get('kind')=='axis_values':
                require(set(selected)=={'kind','axis','values'},'closed axis selector')
                axis=integer(selected['axis'],'axis index',0);require(axis<len(product['axes']),'selected axis exists')
                values=selected['values'];require(type(values)is list and values,'nonempty literal axis values');unique(values,'unit axis values')
                require(all(v in product['axes'][axis]for v in values),'all unit coordinates exist in full output')
            else:
                require(set(selected)=={'kind','path'}and selected['kind']=='json_path'and product['format']=='json','closed JSON output path')
                require(type(selected['path'])is list and selected['path']and all(type(p)is str and p or type(p)is int and p>=0 for p in selected['path']),'literal JSON object/list path')
    cover=row['coverage']
    required={
        'J02':{'morphologies':5,'amplitudes':10,'recording_sites':3},
        'J03':{'hardware':['CPU','A100'],'batch_families_per_device':12},
        'J04':{'recurrent_cells':2000,'duration_ms':200,'solver_steps':8000},
        'J05':{'recurrent_cells':12000,'selected_loss_cells':12},
        'J09':{'scanfields':15,'stimuli_per_field':1024,'cut_ms':[50,100,150],'duration_ms':200},
        'J10':{'GD_runs':10,'GD_steps':10,'GA_runs':10,'GA_generations':10,'GA_offspring':10},
        'J11':{'cells':['485574832','488683425','480353286','473601979'],'budgets':['high','low'],'optimizers':['GD','GA']},
        'J12':{'parameters':1390,'branches':339,'optimizers':['GD','GA']},
        'J13':{'chains':200,'prior_transitions':2000,'posterior_transitions':500,'leapfrog_steps':5,'parameters':1390},
        'J14':{'GD_runs':10,'GA_runs':10,'train_rows':32,'test_rows':16,'parameters':72},
        'J15':{'scanfields':15,'raw_ROIs':232,'sites':147},
        'J16':{'scanfields':15,'stimuli_per_field':1024,'sites':147},
        'J17':{'stimulus_sites':[15,105],'branches':155},
        'J18':{'sites':147,'ASD_required_updates':20},
        'J19':{'fields':[1,2,3,5,7,9,13],'sizes':[32,64,128,256,512],'models':['linear','MLP','hybrid'],'seeds':[0,1,2,3,4]},
        'J20':{'profiles':['untrained','EI','DMS']},
        'J21':{'units':50,'inhibitory_units':10,'transient_ms':4000,'accumulation_ms':6000},
        'J22':{'units':20,'training_batch':4,'test_trials':1000,'paper_training_updates':2000},
        'J23':{'duration_ms':3020,'classes':['positive','negative']},
        'J24':{'units':50,'inhibitory_units':10,'batch':64,'patterns':['AA','AB','BA','BB'],'final_delay_steps':[18000,22000]},
        'J25':{'trajectories':['A_pulse','B_pulse','unforced'],'steps':[40000,40000,400000],'whole_dynamic_state':True},
        'J26':{'hidden_cells':64,'readouts':10},
        'J27':{'linear_fits':50,'MLP_fits':50,'biophysical_fits':1},
        'J28':{'reset_conditions':8},
        'J29':{'models':['biophysical','MLP'],'paired_examples':128,'norm_sweep_points':31},
        'J30':{'hidden_cells':64,'states':['initial','trained']},
        'J31':{'states':['initial','trained']},
        'J33':{'units':20,'inhibitory_units':5,'solver_steps':[1,2,4]},
        'J34':{'classes':['positive','negative'],'same_J22_checkpoint':True},
        'J35':{'rows':9},'J36':{'notes':8},
    }.get(group,{})
    for key,value in required.items():require(cover.get(key)==value,'incomplete '+group+' '+key)
    require(cover.get('source_profile')and cover.get('paper_equivalence')in(True,False),'explicit scientific profile/equivalence')
    return cover

def compile_campaign(selection):
    require(type(selection)is dict and selection['schema']=='jaxley_full_scientific_source_selection_v1','prospective source route schema')
    require(selection['task_id']==TASK and tuple(selection['conditions'])==CONDITIONS,'same task and all information/procedure conditions')
    require(tuple(selection['required_groups'])==GROUPS,'all36 original groups')
    require(selection['scope_complete']is True and selection['scientifically_qualified']is False,'source construction cannot self-qualify')
    require(selection['common_simulator']=='library_assisted_Jaxley','A/B scientific interpretation')
    require(selection['historical_equivalence_by_default']is False,'no silent historical equivalence')
    require(set(selection['legacy_conflicts'])==set(CONFLICTS)and set(selection['qualification_gates'])==set(GATES),'full conflict/gate retention')
    require(all(value is False for value in selection['qualification_gates'].values()),'source plan is not an all-gates-passed issuer')
    source=[pin(p)for p in selection['source_tree']];paths=[p['path']for p in source];unique(paths,'source closure')
    require('scientific_driver.py'in paths and all(module.replace('.','/')+'.py'in paths for module,_ in DISPATCH.values()),'complete fixed scientific source closure')
    specs=selection['groups'];require(type(specs)is list and [s['group']for s in specs]==list(GROUPS),'ordered complete group source specs')
    group_by={r['group']:r for r in specs};source_sha=digest(canonical_bytes(source));plans=[]
    campaign_demand={'input_bytes':0,'output_bytes':0,'local_memory_peak_upper':0,'workload_children':144}
    for group in ordered_groups():
        row=group_by[group];_scope(group,row,selection['rosters'])
        require(type(row['action'])is str and type(row['config'])is dict,'concrete source action/profile')
        require(row['source_module']==DISPATCH[group][0],'fixed producer dispatch')
        outputs=row['output_contract']['outputs'];require([p['artifact_id']for p in outputs]==list(PRODUCTS[group]),'all ordered scientific products')
        require_full_support(group,outputs)
        extents=[product_extent(p)for p in outputs]
        limits=row['producer_limits'];require(set(limits)==set(LIMITS),'explicit producer limits, no defaults')
        for k in LIMITS:integer(limits[k],k,1)
        bounds=row['metadata_limits'];require(set(bounds)=={'receipt_bytes','invocation_bytes','json_member_bytes'},'explicit route metadata limits')
        for key,value in bounds.items():integer(value,key,1)
        require(bounds['json_member_bytes']>=max([p['extent']['bytes']for p in outputs if p['format']=='json']or[1]),'JSON cap cannot silently omit full histories')
        require(bounds['receipt_bytes']<=bounds['json_member_bytes'],'receipt capacity')
        inputs=row['native_inputs'];require(type(inputs)is list,'exact input descriptor roster');unique([x['logical']for x in inputs],'logical native inputs')
        for item in inputs:
            relative(item['path'])
            require(item['origin']in('external_sealed_input','actual_predecessor','actual_parent_observations'),'input origin')
            if item['origin']=='external_sealed_input':pin({k:item[k]for k in('path','bytes','sha256')})
            else:
                require('sha256'not in item and 'bytes'not in item,'future output hash/length cannot be guessed')
                integer(item['max_bytes'],'whole predecessor extent',1)
                if item['origin']=='actual_parent_observations':
                    require(item['format']=='json'and item['dtype']is None,'original observer envelope format')
                    require(item['parent_groups']==DEPENDENCY_V2.get(group,[]),'full ordered native observation parents')
        input_extent=sum(x.get('bytes',x.get('max_bytes'))for x in inputs)
        total_output=sum(extents)+bounds['receipt_bytes']
        require(limits['input_member_bytes']>=max([x.get('bytes',x.get('max_bytes'))for x in inputs]or[0]),'whole input member capacity')
        require(limits['output_member_bytes']>=max(extents+[bounds['receipt_bytes']]),'whole output member capacity')
        require(limits['output_bytes']>=total_output,'full output plus receipt capacity before launch')
        reads=row['read_demand']
        require(set(reads)=={'input_passes','output_readback_passes','other_known_bytes','unknown_bound_source'},'whole source read demand')
        integer(reads['input_passes'],'full input passes',1);integer(reads['output_readback_passes'],'full readback passes',1);integer(reads['other_known_bytes'],'other source reads',0)
        require(reads['unknown_bound_source'],'native/library read coverage remains an explicit qualification dependency')
        demanded=input_extent*reads['input_passes']+total_output*reads['output_readback_passes']+reads['other_known_bytes']+len(inputs)+len(outputs)+1
        require(limits['input_bytes']>=demanded,'complete source read demand before launch')
        allocations=row['working_arrays'];require(type(allocations)is list and allocations,'whole working allocation inventory')
        peak=0
        for allocation in allocations:
            integer(allocation['bytes'],'complete allocation extent',0);integer(allocation['simultaneous_copies'],'simultaneous copies',1)
            require(allocation['derivation']and allocation['includes_full_required_support']is True,'unexplained/partial allocation')
            peak+=allocation['bytes']*allocation['simultaneous_copies']
        numeric_retention=sum(p['extent']['bytes']for p in outputs if p['format']=='jaxley-flat-numeric-v1')
        json_serialization=max([p['extent']['bytes']for p in outputs if p['format']=='json']or[0])
        # Complete products plus one complete conversion/stack and bounded JSON
        # serialization coexist conservatively. Python/native metadata and XLA
        # workspace still require the explicit complete allocation inventory.
        peak=max(peak,2*numeric_retention+3*json_serialization)
        require(limits['array_memory_bytes']>=peak,'complete known working arrays admitted before launch')
        resources=row['resource_limits'];require(set(RESOURCE_LIMITS)<=set(resources),'whole native resource limits')
        for key in RESOURCE_LIMITS:integer(resources[key],key,1)
        require(resources['memory_bytes']>=peak and resources['output_bytes']>=total_output,'native caps below known complete source demand')
        require(resources['includes_search_failures_compile_cleanup']is True,'whole lifecycle accounting')
        require(type(resources.get('io_max'))is str and resources['io_max'],'explicit qualified block-IO control, distinct from logical IO')
        links=row['predecessor_inputs'];require(type(links)is list,'actual predecessor links')
        triples={(l['logical'],l['parent_group'],l['artifact_id'])for l in links}
        require(REQUIRED_PARENT_PRODUCTS.get(group,set())<=triples,'scientific consumer must receive the actual complete trained parent')
        if group=='J35':
            observed=[i for i in inputs if i['logical']=='whole_family_observations']
            require(len(observed)==1 and observed[0]['origin']=='actual_parent_observations','nine-row cost family consumes original capture envelopes')
            require(row['config']['selected_captures']=={'actual_parent_captures':'whole_family_observations'},'J35 actual future capture identity placeholder')
        if group=='J36':
            require(row['config']['selected_upstream_jobs']=={'actual_parent_captures':'all_required_note_products'},'J36 actual future source capture placeholder')
        if group=='J03':
            require(row['config']['hardware']==['CPU','A100'] and resources.get('requires_gpu')is True,'complete CPU/A100 family requires real GPU deployment, not a CPU substitute')
        if group=='J18':
            require(row['config']['choices']['rfest_profile']=='fa18170-full20-tolerance20','full20-update family; literal early-stop profile remains a separate lower-level diagnostic')
        require(len({link['logical']for link in links})==len(links),'duplicate parent input')
        require({link['logical']for link in links}=={i['logical']for i in inputs if i['origin']=='actual_predecessor'},'every dynamic input has one captured parent')
        for link in links:
            parent=link['parent_group'];require(parent in DEPENDENCY_V2.get(group,[]),'unselected dependency')
            require(link['artifact_id']in PRODUCTS[parent]and link['logical']in[x['logical']for x in inputs],'actual captured predecessor artifact')
            require(link['binding']=='actual_collected_parent_object_then_materialized_bytes','hash/dictionary cannot issue parent ownership')
            target=next(i for i in inputs if i['logical']==link['logical'])
            product=next(p for p in group_by[parent]['output_contract']['outputs']if p['artifact_id']==link['artifact_id'])
            require(target['max_bytes']>=product['extent']['bytes'],'full parent product capacity cannot be cropped')
            for field in('format','dtype','shape'):require(target[field]==product[field],'parent/child exact format and axes')
            require(type(link['config_sha256_paths'])is list,'explicit dynamic config hash locations')
            for path in link['config_sha256_paths']:
                require(type(path)is list and path and all(type(x)is str and x for x in path),'closed config path')
                node=row['config']
                for part in path[:-1]:node=node[part]
                require(node[path[-1]]=={'actual_parent_sha256':link['logical']},'config binds actual future parent, not supplied hash')
        for condition in CONDITIONS:
            plan={'job_id':condition+'-'+group+'-complete-family','group':group,'condition':condition,'action':row['action'],'config':row['config'],
                  'native_inputs':inputs,'output_contract':row['output_contract'],'producer_limits':limits,'metadata_limits':bounds,
                  'resource_limits':resources,'source_tree_sha256':source_sha,'source_profile_sha256':digest(canonical_bytes(selection)),
                  'producer_source_sha256':next(p['sha256']for p in source if p['path']=='scientific_driver.py'),
                  'original_units':row['legacy_units'],'unit_inverse':row['unit_inverse'],'coverage':row['coverage'],
                  'dependencies':DEPENDENCY_V2.get(group,[]),'predecessor_inputs':links,'required':True,
                  'authority':'UNISSUED; must be actual protected native source/input/parent observer owners, not this plan'}
            plans.append(plan)
        campaign_demand['input_bytes']+=4*demanded;campaign_demand['output_bytes']+=4*total_output
        campaign_demand['local_memory_peak_upper']=max(campaign_demand['local_memory_peak_upper'],peak)
    return {'schema':'jaxley_full_scientific_source_plan_v1','task_id':TASK,'plans':plans,'family_runs':144,
            'original_group_count':36,'fit_count':'actual full inverse and operation histories, not144 runs',
            'demand':campaign_demand,'source_tree':source,'source_tree_sha256':source_sha,'scientifically_qualified':False,
            'native_authority_issued':False,'legacy_route':'unchanged and incompatible with this full-output route',
            'remaining_native_and_comparator_gates':selection['qualification_gates']}
