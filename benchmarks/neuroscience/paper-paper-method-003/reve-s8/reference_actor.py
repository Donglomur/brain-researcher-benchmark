"""Fixed, independently registered REVE reference actor; no plugin callbacks."""
import sys,json
from reference_runtime.catalog import need,canonical,identity,validate_configuration
from reference_runtime.io import ActorIO,data_view

def selected(request):
    need(request.get('schema')=='reve-actor-request-v1','actor request schema')
    stage=request['stage'];allowed={'S05','S06','S07','S08','S09','S10','S11','S12','S15','S17','S21','S22'}
    need(stage in allowed,'fixed actor stage');p=request['payload'];need('reference' in p,'fixed reference request')
    ref=p['reference'];need(set(ref)=={'configuration','views','parent_state','members','qualification'},'closed reference call')
    c=validate_configuration(ref['configuration']);need(ref['qualification'],'selected source/numerical/environment qualification')
    if p.get('scientific_cases') is not None:need(p['scientific_cases']==c['scientific_cases'],'immutable state scientific cases')
    if p.get('scientific_identity') is not None:need(p['scientific_identity'] in c['scientific_cases'].values(),'immutable query scientific case')
    need(type(ref['views'])is dict and set(ref['views'])<= {'train','dev','query','calibration','pretrain'},'closed data roles')
    if stage=='S17':need(set(ref['views'])=={'query'} and ref['parent_state'] and not ref['members'],'query has only one frozen parent and one query view')
    if stage in ('S09','S10','S11'):
        from reference_runtime.lineage import fit_stage
        fit_stage(stage,c)
        need(set(ref['views'])=={'train','dev'},'fit has only TRAIN and DEV')
        need(c['recipe']['method']!='REVE-Base-PT','PT representation cannot receive supervised adaptation')
        need(bool(ref['parent_state'])==(c['initialization']!='scratch'),'fit cannot substitute or ignore its selected initialization')
    if stage=='S15':need(set(ref['views'])=={'calibration'} and ref['parent_state'],'calibration has no DEV/query')
    if stage=='S08':need(set(ref['views'])=={'pretrain'},'pretraining has only selected unlabeled corpus')
    return ref,c

def emit_state(io,name,c,tensors,history,selected_trial,mask,deps,initial,schedule):
    pin=io.write_state(name+'.safetensors',tensors);search=io.write(name+'.search.json',canonical(history))
    details={'format':'safetensors','tensor_index':[{'object':pin}],'configuration':c,'trained_mask':mask,'fitted_dependencies':deps,'initial_state':initial,'search_receipts':[search],'selected_trial':selected_trial,'selection_criterion':'DEV_balanced_accuracy_first_chronological' if c['recipe']['base']!='fixed_spectral_ridge' else 'DEV_binary_AUROC_or_multiclass_kappa','objective':io.r['expected_outputs'][name]['objective_profile'],'schedule':schedule}
    io.emit(name,details,[pin,search])

OUTPUT_KINDS={'S05':{'executable'},'S06':{'method_plan'},'S07':{'architecture'},'S08':{'state','loss_trace','schedule_trace'},'S09':{'state','schedule_trace'},'S10':{'state','schedule_trace'},'S11':{'state','schedule_trace'},'S12':{'state','soup'},'S15':{'state'},'S17':{'prediction'},'S21':{'claim'},'S22':{'preprocessing'}}

def actor(request):
    ref,c=selected(request);io=ActorIO(request);stage=request['stage'];specs=request['expected_outputs'];r=c['recipe']
    need({s['kind'] for s in specs.values()}<=OUTPUT_KINDS[stage],'fixed stage/product implementation')
    bykind={}
    for name,spec in specs.items():bykind.setdefault(spec['kind'],[]).append(name)
    if stage=='S05':
        for name,s in specs.items():
            need(s['kind']=='executable','build output');e=s['executable'];io.emit(name,{'kind':'registered_interpreted_entrypoint','source_id':request['source_id'],'entrypoint':e['entrypoint'],'interpreter':e['interpreter'],'environment':request['payload']['environment'],'dependencies':e['dependencies'],'build_request':identity(request)})
    elif stage=='S06':
        for name,s in specs.items():
            need(s['kind']=='method_plan','plan output');io.emit(name,{'families':[f'RV-{i:02d}' for i in range(1,14)],'obligations':[f'O{i:02d}' for i in range(1,55)],'variant_graph':request['payload']['variant_graph'],'search_policy':r,'budget_allocation':request['resource_limits'],'reuse_policy':'exact_state_source_exposure_and_scientific_case_only','confirmatory_manifest':s['confirmatory_manifest'],'scientific_profiles':s['scientific_profiles']})
    elif stage=='S07':
        import torch
        from reference_runtime.engine import construct
        manifest=io.json(ref['views']['train']);geometry=io.array(manifest['positions']);parent_tensors=io.load_state(ref['parent_state'])[1] if ref['parent_state'] else None;model=construct(c,geometry,parent_tensors)
        for name,s in specs.items():
            need(s['kind']=='architecture','architecture output');io.emit(name,{'configuration':c,'parameter_schema':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in model.state_dict().items()},'parameter_counts':{'all':sum(p.numel() for p in model.parameters()),'trainable':sum(p.numel() for p in model.parameters() if p.requires_grad)},'trained_mask':[n for n,p in model.named_parameters() if p.requires_grad],'geometry':manifest['geometry_qualification'],'patches':{'samples':r['samples'],'REVE_stride':180,'other_patch':200},'position':r['geometry'],'mask':c['ablation'],'objective':s['objective_profile'],'schedule':r['stages']})
    elif stage in ('S09','S10','S11'):
        import torch
        from reference_runtime import engine
        if stage=='S10':
            from reference_runtime.xft import xft_view
            need(r['method']=='REVE-Base-XFT','XFT gets its own named condition');train=xft_view(io,ref['views']['train'],'train',c);dev=xft_view(io,ref['views']['dev'],'dev',c)
        else:train=data_view(io,ref['views']['train'],'train',c);dev=data_view(io,ref['views']['dev'],'dev',c)
        need(not set(train[0]['events'])&set(dev[0]['events']),'TRAIN/DEV event disjointness')
        if c['condition']!='source':need(not set(train[0]['people'])&set(dev[0]['people']),'protected TRAIN/DEV biological people disjointness')
        xft_lineage=None
        if stage=='S10':
            from reference_runtime.lineage import training_lineage
            xft_lineage=training_lineage(request,c,train[0],dev[0])
        if r['base']=='fixed_spectral_ridge':
            from reference_runtime.reference_spectral import pooled_features
            from reference_runtime.reference_linear import fit
            def flatten(a):return a.reshape(-1,a.shape[-2],a.shape[-1])
            fitted=fit(pooled_features(flatten(train[1]),input_unit='mV'),train[3].reshape(-1),pooled_features(flatten(dev[1]),input_unit='mV'),dev[3].reshape(-1),r['classes'])
            tensors={'spectral.beta':torch.as_tensor(fitted['beta']),**{'spectral.'+k:torch.as_tensor(v) for k,v in fitted['normalizer'].items()}}
            result={'history':[{'penalty':fitted['penalty'],'DEV_score':fitted['validation_monitor']}],'selected':fitted['penalty'],'trained_mask':list(tensors),'fitted_dependencies':[train[0]['support'],dev[0]['support']],'steps':[],'channel_ids':train[0]['channel_ids']}
        else:
            initial=None
            if ref['parent_state']:
                details,weights=io.load_state(ref['parent_state']);initial={k[6:]:v for k,v in weights.items() if k.startswith('model.')}
                if not initial and r['base'].startswith('REVE-'):
                    initial={'classifier.encoder.'+k[len('pretrain.encoder.'):]:v for k,v in weights.items() if k.startswith('pretrain.encoder.')}
                if not initial:initial={k:v for k,v in weights.items() if k.startswith('asset.')}
                need(initial and details['configuration']['recipe']['base']==r['base'],'same closed architecture parent')
                effect_keys={'component','loss','masking','ratio_percent'}
                need({k:v for k,v in details['configuration']['ablation'].items() if k in effect_keys}=={k:v for k,v in c['ablation'].items() if k in effect_keys},'actual pretrained scientific condition must match downstream case')
            result=engine.fit(c,train,dev,initial,trace_limit=max(1,request['resource_limits']['output_bytes']//2048))
            tensors={**{'model.'+k:v for k,v in result['weights'].items()},'adapter.normalizer':result['normalizer'],'adapter.geometry':result['geometry']}
        need(len(bykind.get('state',[]))==1,'one selected state per fit')
        schedule={'profile':r['profile'],'channel_ids':result['channel_ids'],'steps':len(result['steps'])}
        if stage=='S10':
            schedule['xft']=xft_lineage
        for name in bykind['state']:emit_state(io,name,c,tensors,result['history'],result['selected'],result['trained_mask'],result['fitted_dependencies'],ref['parent_state'],schedule)
        for name in bykind.get('schedule_trace',[]):
            from reference_runtime.step_trace import profile,rank_exposure
            need(result['steps'],'spectral algebra does not invent optimizer steps');pin=io.write(name+'.json',canonical(result['steps']));io.emit(name,{'profile':profile(request,c,result['steps']),'steps':pin,'resume':None,'rank_exposure':rank_exposure(result['steps']),'producer':identity(request)},[pin])
    elif stage=='S12':
        from reference_runtime.engine import soup
        names=ref['members'];need(len(names) in (5,10) and len(set(names))==len(names),'distinct required independently fitted members')
        parents=[io.load_state(n) for n in names];base=parents[0][0]['configuration'];need(all(d['configuration']['recipe']==base['recipe'] and d['configuration']['ablation']==base['ablation'] for d,_ in parents),'same actual soup architecture/recipe')
        need(len({d['configuration']['seed'] for d,_ in parents})==len(parents),'independent soup seeds')
        if bykind.get('state'):
            need(len(bykind['state'])==1 and not bykind.get('soup'),'average is produced before a separate summary job');state_name=bykind['state'][0];tensors=soup([w for _,w in parents])
            emit_state(io,state_name,c,tensors,[{'member':n,'selected_trial':d['selected_trial']} for n,(d,_) in zip(names,parents)],'equal_weight_all_members',parents[0][0]['trained_mask'],sorted({x for d,_ in parents for x in d['fitted_dependencies']}),names,parents[0][0]['schedule'])
        else:
            need(ref['parent_state'],'closed averaged state before summary');details,tensors=io.load_state(ref['parent_state']);state_name=request['parent_products'][ref['parent_state']]
            need(details['initial_state']==names and details['selected_trial']=='equal_weight_all_members','actual averaged member lineage')
        for name in bykind.get('soup',[]):
            io.emit(name,{'state':state_name,'members':[request['parent_products'][n] for n in names],'weights':[1/len(names)]*len(names),'tensor_schema':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in tensors.items()},'buffer_policy':'equal_nonfloating_weighted_floating','member_metrics':[d['selected_trial'] for d,_ in parents],'selection_policy':'all_members_no_query_selection'})
    elif stage=='S17':
        if r['method']=='REVE-Base-XFT':io.xft_parent(ref['parent_state'],calibrated=True)
        import numpy as np
        details,tensors=io.load_state(ref['parent_state']);need(details['configuration']==c,'query cannot relabel frozen scientific configuration');view=data_view(io,ref['views']['query'],'query',c)
        if 'ncm.centers' in tensors:
            from reference_runtime.calibration import embedding
            from reference_runtime.reference_ncm import probabilities
            features=embedding(c,tensors,view,details['schedule']['channel_ids']);scores=probabilities(features,tensors['ncm.centers'].numpy());representation='hard_ncm'
        elif r['base']=='fixed_spectral_ridge':
            from reference_runtime.reference_spectral import pooled_features
            from reference_runtime.reference_linear import predict
            x=view[1];need(len(x)==1,'fresh one epoch/sequence');model={'beta':tensors['spectral.beta'].numpy(),'normalizer':{k:tensors['spectral.'+k].numpy() for k in ('anchor','spread','center','scale','constant')}};scores=predict(model,pooled_features(x.reshape(-1,x.shape[-2],x.shape[-1]),input_unit='mV'));representation='probabilities'
        else:
            from reference_runtime.engine import predict
            scores=predict(c,{'tensors':tensors,'channel_ids':details['schedule']['channel_ids']},view);representation='raw_logits' if c['purpose']=='R-native' else 'probabilities'
        for name,s in specs.items():
            need(s['kind']=='prediction' and s['events']==view[0]['events'] and s['support']==view[0]['support'] and s['state']==request['parent_products'][ref['parent_state']],'exact current query/state/support');pin=io.write_array(name+'.npy',np.asarray(scores,dtype='<f8'));io.emit(name,{'scores':{'object':pin,'shape':list(scores.shape),'dtype':'<f8'},'representation':representation,'events':s['events'],'classes':s['classes'],'state':s['state'],'support':s['support'],'query_policy':s['query_policy']},[pin])
    elif stage=='S15':
        lineage=io.xft_parent(ref['parent_state'],calibrated=False) if r['method']=='REVE-Base-XFT' else None
        from reference_runtime.calibration import calibrate
        details,tensors=io.load_state(ref['parent_state']);view=data_view(io,ref['views']['calibration'],'calibration',c)
        from reference_runtime.calibration import prepare_parent
        tensors=prepare_parent(c,details,tensors,view,lineage);channels=view[0]['channel_ids'] if c['recipe']['method']=='REVE-Base-PT' else details['schedule']['channel_ids'];result=calibrate(c,tensors,view,channels)
        for name,s in specs.items():
            need(s['kind']=='state','calibration state output');emit_state(io,name,c,result,[],None,['ncm.centers'],[*details['fitted_dependencies'],view[0]['support']],ref['parent_state'],{**details['schedule'],'channel_ids':channels,'calibration_recipe':c['recipe']['normalization']})
    elif stage=='S08':
        from reference_runtime.pretraining import fit_pretraining
        from reference_runtime.pretraining_products import emit_pretraining,ReconstructionWriter
        from reference_runtime.corpus import CorpusStream
        view=CorpusStream(io,ref['views']['pretrain'],c);writer=ReconstructionWriter(io,c,view.summary);result=fit_pretraining(c,view,request['payload']['objective_profile'],max(1,request['resource_limits']['output_bytes']//4096),writer);emit_pretraining(io,c,view,result)
    elif stage=='S22':
        from reference_runtime.preprocessing import prepare_products
        prepare_products(io,c,ref)
    elif stage=='S21':
        from reference_runtime.report import scientific_report
        scientific_report(io,c)
    io.finish()

if __name__=='__main__':
    raw=sys.stdin.buffer.read(8*1024*1024+1);need(len(raw)<=8*1024*1024,'request cap');actor(json.loads(raw))
