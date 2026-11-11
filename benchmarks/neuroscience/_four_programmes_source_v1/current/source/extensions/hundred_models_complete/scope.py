"""Complete immutable source scope, scientific-input admission and work graph."""
from pathlib import Path
from .guard import need,Unscorable,encoded,bare,descriptor,relative
TASK='PAPER-paper-method-replacement-016'
PANELS={'test':(102,10),'train':(1000,3)}
METHOD_FOLDERS={'pca':'models_pca_rerun','srp':'models','none':'models_no_dimred'}

def validate_scope(scope):
    need(scope['task_id']==TASK and scope['benchmark_count']==1,'one exact canonical assignment')
    models=scope['declared_catalog'];ids=[x['model_id'] for x in models]
    need(len(ids)==len(set(ids))==99 and len(scope['main92'])==92 and len(scope['training_figure17_51'])==51,'full99/92/51')
    need(scope['figures_required']==list(range(1,23)) and scope['tables_required']==[1,2],'full22figure/two-table programme')
    need(len(scope['subjects'])==10 and sum(map(len,scope['roi_groups'].values()))==17,'full biological scope')
    need(scope['auxiliary_figure18']['model_id']=='videomae_B_pretrainONLY' and 'videomae_B_pretrainONLY' not in ids,'separate auxiliary control')
    return ids

def condition_rows(scope):
    ids=validate_scope(scope);rows=[]
    for m in ids:rows.append({'id':'test:pca:'+m,'panel':'test','method':'pca','model':m,'role':'main'})
    for method in ('srp','none'):
        for m in scope['main92']:rows.append({'id':'test:'+method+':'+m,'panel':'test','method':method,'model':m,'role':'figure16'})
    for m in scope['training_figure17_51']:rows.append({'id':'train:pca:'+m,'panel':'train','method':'pca','model':m,'role':'figure17'})
    rows.append({'id':'test:pca:videomae_B_pretrainONLY','panel':'test','method':'pca','model':'videomae_B_pretrainONLY','role':'figure18'})
    need(len(rows)==335,'complete condition instances');return rows

def require_evidence(value,gate,why):
    if value is None:raise Unscorable(gate,why)
    descriptor(value);return value

def admit_inputs(scope,manifest):
    """Metadata admission only; input bytes and native claims need later qualification."""
    ids=validate_scope(scope);need(manifest['schema']=='hundred_models_scientific_inputs_v1','input schema')
    need(manifest['task_id']==TASK and manifest['scope']==bare(encoded(scope)),'whole scope identity')
    need(manifest['subjects']==scope['subjects'],'same ten participants')
    rois=[v for group in scope['roi_groups'].values() for v in group]
    need(manifest['rois']==rois,'all ordered17 regions')
    panels=manifest['panels'];need(set(panels)==set(PANELS),'both panels are required')
    for panel,(n,reps) in PANELS.items():
        row=panels[panel];ordered=row['ordered_ids']
        need(type(ordered)is list and len(ordered)==len(set(ordered))==n and all(type(x)is str and x for x in ordered),'complete independent stimulus identities')
        if panel=='test':need(ordered==scope['test_panel']['declared_ids'],'exact test order')
        need(row['repetitions']==reps,'panel-specific repetitions')
        require_evidence(row.get('identity_witness'),'G02','Actual video/derivative stimulus join absent')
        require_evidence(row.get('derivative_witness'),'G01','Original version/conversion/mask witness absent')
        need(len(row['videos'])==n and [x['stimulus'] for x in row['videos']]==ordered,'S06 exact shared S03 stimulus order')
        for x in row['videos']:descriptor(x['file'])
        expected=[(s,roi) for s in scope['subjects'] for roi in rois]
        need([(x['subject'],x['roi']) for x in row['brain']]==expected,'full170 brain units perpanel')
        for x in row['brain']:
            need(x['shape'][:2]==[n,reps] and type(x['shape'][2])is int and x['shape'][2]>1,'declared complete brain shape')
            roi=x['roi'];parts=x['parts'];expected_parts=([(v,h) for v in ((roi+'v',roi+'d') if roi in ('V1','V2') else (('IPS1-2-3',) if roi=='IPS1' else (roi,))) for h in ('left','right')])
            need([(v['parcel'],v['hemisphere']) for v in parts]==expected_parts,'exact source hemisphere/subdivision merge order')
            need(sum(v['shape'][2] for v in parts)==x['shape'][2],'all original voxel widths retained')
            for part in parts:
                need(part['shape'][:2]==[n,reps] and type(part['shape'][2])is int and part['shape'][2]>0,'complete safe part shape')
                descriptor(part['file']);require_evidence(part.get('conversion'),'G01','safe numeric derivative conversion absent')
            need(x['stimulus_identity']==row['identity_witness'],'brain/feature common stimulus identity')
    need(not(set(panels['test']['ordered_ids'])&set(panels['train']['ordered_ids'])),'test/train identities disjoint')
    need(set(manifest['models'])==set(ids+['videomae_B_pretrainONLY']),'all99 plus exact extra control; canonical model order comes from scope')
    for m in manifest['models'].values():
        require_evidence(m.get('checkpoint'),'G03','Exact checkpoint bytes absent')
        require_evidence(m.get('native_graph_source'),'G03','Exact framework graph source absent')
        require_evidence(m.get('preprocessing'),'G07','Actual frame/subclip conventions absent')
        require_evidence(m.get('loading_witness'),'G03','Resolved configuration-to-loaded-checkpoint binding absent')
        for k in ('maximum_feature_bytes','maximum_rdm_bytes'):positive(m[k])
    require_evidence(manifest.get('environment'),'G06','Complete qualified native environment absent')
    require_evidence(manifest.get('external_isolation'),'G15','Independent external isolation receipt absent')
    need(manifest['profile'] in ('current_donor_source_convention','historical_source_parity'),'explicit fidelity profile')
    if manifest['profile']=='historical_source_parity':
        require_evidence(manifest.get('historical_native_identity'),'G06','Historical dependency evidence absent')
        require_evidence(manifest.get('historical_schedule'),'G10','Historical null/cache evidence absent')
    for method in ('pca','srp','none'):
        require_evidence(manifest['reductions'].get(method),'G08','Complete admitted reduction settings absent')
    require_evidence(manifest.get('train_reduction'),'G09','Train PCA historical/literal override absent')
    need(set(manifest['appendix_calls'])=={'F15','F19','F20','F21','F22'},'all unresolved appendix callers remain required')
    for x in manifest['appendix_calls'].values():require_evidence(x,'G12','Exact appendix caller/filter evidence absent')
    for k,gate in (('permutation_schedule','G10'),('auxiliary_configuration','G04'),('render_calls','G13')):
        require_evidence(manifest.get(k),gate,'Complete '+k+' evidence absent')
    for k in ('source_location',):relative(manifest[k])
    for row in panels.values():relative(row['video_directory'])
    need(manifest['dimension_folders']==['models_no_dimred','models','models_pca_rerun'],'full source condition order with PCA base')
    need(type(manifest['train_folder'])is str and manifest['train_folder'],'explicit train folder')
    need(type(manifest['device'])is str and manifest['device'],'explicit selected native device')
    need(type(manifest['native_PATH'])is str and manifest['native_PATH'],'explicit isolated PATH')
    need(type(manifest['hash_seed'])is int and 0<=manifest['hash_seed']<2**32,'explicit Python hash seed; no historical seed claim')
    for limits in (manifest['job_limits'],manifest['process_limits'],manifest['numerical_limits']):
        need(type(limits)is dict and bool(limits),'explicit resource limits')
        for value in limits.values():positive(value)
    need(set(manifest['job_limits'])=={'read_bytes','write_bytes','work','deadline_ns'},'whole job budget ABI')
    need(set(manifest['process_limits'])=={'cpu_seconds','file_bytes','open_files','address_space_bytes'},'owned process resource ABI')
    need(set(manifest['numerical_limits'])=={'work','elements'},'numerical resource ABI')
    positive(manifest['stream_limit_bytes'])
    need(set(manifest['consumer_limits'])=={'inference','dimension'},'both reviewed consumers required')
    for k in ('max_total_layers','max_null_summary_cells','max_result_scalar_cells'):positive(manifest['consumer_limits']['inference'][k])
    need(type(manifest['consumer_limits']['dimension'])is dict,'dimension source limits')
    return {'models':ids,'rois':rois,'conditions':condition_rows(scope),'input_manifest':bare(encoded(manifest)),'scientifically_qualified':False}

def positive(value):
    need(type(value)is int and value>0,'positive explicit resource reservation')

def compile_jobs(scope,manifest):
    admitted=admit_inputs(scope,manifest);jobs=[]
    for panel in PANELS:
        for row in manifest['panels'][panel]['brain']:
            jobs.append({'id':'brain:'+panel+':'+row['subject']+':'+row['roi'],'kind':'brain','panel':panel,'subject':row['subject'],'roi':row['roi'],'dependencies':[]})
    feature_ids=[]
    for c in admitted['conditions']:
        fid='features:'+c['panel']+':'+c['model']
        if fid not in feature_ids:
            feature_ids.append(fid);jobs.append({'id':fid,'kind':'features','panel':c['panel'],'model':c['model'],'stimulus_identity':manifest['panels'][c['panel']]['identity_witness'],'dependencies':[]})
        rid='rdm:'+c['id'];jobs.append({'id':rid,'kind':'rdm',**c,'dependencies':[fid]})
        # The operation id must retain its stage prefix after dictionary expansion.
        jobs[-1]['id']=rid
        for roi in admitted['rois']:
            jobs.append({'id':'rsa:'+c['id']+':'+roi,'kind':'rsa','condition':c['id'],'panel':c['panel'],'model':c['model'],'method':c['method'],'roi':roi,'dependencies':[rid]+['brain:'+c['panel']+':'+s+':'+roi for s in scope['subjects']]})
    for m in admitted['models']+['videomae_B_pretrainONLY']:
        for roi in admitted['rois']:
            jobs.append({'id':'null:'+m+':'+roi,'kind':'null','panel':'test','method':'pca','model':m,'roi':roi,'dependencies':['rsa:test:pca:'+m+':'+roi]})
    downstream=[x['id'] for x in jobs]
    jobs.append({'id':'consume','kind':'consume','dependencies':downstream})
    jobs.append({'id':'report','kind':'report','dependencies':['consume']})
    need(len({x['id'] for x in jobs})==len(jobs),'unique complete native job ids')
    seen=set()
    for row in jobs:need(set(row['dependencies'])<=seen,'topological jobs');seen.add(row['id'])
    return {'schema':'hundred_models_full_native_plan_v1','scope':bare(encoded(scope)),'inputs':admitted['input_manifest'],'jobs':jobs,'counts':{'brain':340,'features':151,'rdm':335,'rsa':5695,'null':1700,'consume':1,'report':1},'scientifically_qualified':False}
