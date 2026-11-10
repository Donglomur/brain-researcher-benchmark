"""Concrete full scientific reference family producers for the sealed worker."""
import hashlib,json,math,random
from pathlib import Path
from .protocol import need,fields,identity,encode,digest,Refusal


def pretrain(worker):
    import numpy as np
    import torch
    from .neural_kernel import pretraining_model,pretrain as train,architecture_census
    recipe=worker.recipe();need(recipe['kind']=='eegpt_pretraining','actual complete pretraining source recipe')
    need(recipe['pretraining_role']!='predictor:no_predictor','G11: original no-predictor producer absent; no invented replacement')
    torch.manual_seed(worker.request['seed']);np.random.seed(worker.request['seed']);random.seed(worker.request['seed'])
    train_document=worker.rows('corpus_train');validation_document=worker.rows('corpus_validation')
    class CorpusBatches:
        def __init__(self,document,shuffle):self.document=document;self.shuffle=shuffle;self.last_metadata=[]
        def __len__(self):return math.ceil(len(self.document['rows'])/recipe['fit']['batch_size'])
        def __iter__(self):
            order=list(range(len(self.document['rows'])))
            if self.shuffle:random.shuffle(order)
            for start in range(0,len(order),recipe['fit']['batch_size']):
                selected=order[start:start+recipe['fit']['batch_size']];parts=[];meta=[]
                for index in selected:
                    original=self.document['rows'][index];x,_,_,_=next(worker.epochs({**self.document,'rows':[original]}));need(x.shape[0]==58 and x.shape[1]>=1024,'complete source-selected58channel pretraining record')
                    offset=random.randint(0,x.shape[1]-1024) if x.shape[1]>1024 else 0;parts.append(torch.as_tensor(x[:,offset:offset+1024],dtype=torch.float32));meta.append({'row_id':original['row_id'],'crop_start':offset,'crop_samples':1024,'source_identity':original['signal']['sha256']})
                self.last_metadata=meta;yield torch.stack(parts)
    training=CorpusBatches(train_document,True);validation=CorpusBatches(validation_document,False);model=pretraining_model(worker.inputs['author_source'],recipe['source_pins'],recipe['variant'],ablation=recipe['ablation'],layout_policy=recipe['fit']['layout_policy']);curves=worker.output/'loss_observations.jsonl';need(not curves.exists(),'fresh complete original curve transport');observation_ids=[];checkpoints=[]
    with curves.open('xb') as stream:
        def write_observation(partition,epoch,step,batch,primitive,actual_recipe):
            loader=training if partition=='train' else validation;row_id=partition+':'+str(epoch)+':'+str(step)+':'+str(batch);observation_ids.append(row_id)
            mx=primitive['mask_x'].detach().cpu().tolist();my=primitive['mask_y'].detach().cpu().tolist();row={'id':row_id,'partition':partition,'epoch':epoch,'step':step,'batch':batch,'LA_numerator':float(primitive['LA_numerator'].detach().cpu()),'LA_denominator':primitive['LA_denominator'],'LR_numerator':float(primitive['LR_numerator'].detach().cpu()),'LR_denominator':primitive['LR_denominator'],'total':float(primitive['total'].detach().cpu()),'mask_x':mx,'mask_y':my,'crop_rows':loader.last_metadata,'rng_state_identity':hashlib.sha256(torch.random.get_rng_state().numpy().tobytes()).hexdigest(),'logical_training_state':{'source_recipe':identity(actual_recipe),'epoch':epoch,'step':step},'checkpoint_selection':'full original fixed recipe; actual emitted state pins bound after completion'};stream.write(encode(row))
        def save_checkpoint(epoch,actual_model,optimizer,scheduler,actual_recipe):
            # Exact selected epoch set is frozen before source/data exposure.
            # No new favorable-epoch selection occurs inside this writer.
            if epoch not in recipe['checkpoint_epochs']:return None
            path=worker.output/('pretrain-%04d.pt'%epoch);torch.save({'state_dict':actual_model.state_dict(),'target_encoder':actual_model.target_encoder.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'epoch':epoch,'recipe':actual_recipe},path)
            from .reference_worker import source_pin
            pin=source_pin(path);worker.artifacts.append(pin);checkpoints.append({'epoch':epoch,'file':pin});return pin
        result=train(model,training,validation,recipe['fit'],write_observation=write_observation,save_checkpoint=save_checkpoint)
    from .reference_worker import source_pin
    worker.artifacts.append(source_pin(curves));need(checkpoints and recipe['selected_epoch'] in recipe['checkpoint_epochs'],'complete qualified selected pretrain state')
    selected=next(p for p in checkpoints if p['epoch']==recipe['selected_epoch']);encoder=worker.output/'encoder.pt';saved=torch.load(worker.output/selected['file']['path'],map_location='cpu',weights_only=True);torch.save(saved['target_encoder'],encoder);epin=source_pin(encoder);worker.artifacts.append(epin)
    metadata={'kind':'eegpt_pretraining','recipe':recipe,'encoder_state':epin['path'],'selected_state':selected['file']['path'],'all_checkpoints':checkpoints,'loss_observation_ids':observation_ids,'full_curve_file':'loss_observations.jsonl','actual_architecture':architecture_census(model,recipe=recipe),'complete_training_result':result,'conditional_on_one_selected_parent_state':True,'historical_parity':False};meta=worker.json('STATE.json',metadata);worker.state_response([r['path'] for r in worker.artifacts],train_document,recipe,'actual new complete pretraining fit')
    from .family_products import training_products
    training_products(worker,worker.request['output_contract']['products'],metadata)
    worker.response['diagnostics']={'full_original_recipe':recipe['pretraining_role'],'loss_observation_count':len(observation_ids),'selected_state':selected,'all_actual_checkpoints':checkpoints,'no_pretrain_seed_variance_claim':True}
    return metadata


def reconstruct(worker):
    import torch
    from .neural_kernel import downstream_model
    state_root=worker.inputs['fitted'];state=__import__('eegpt.reference_worker',fromlist=['load_json']).load_json(state_root/'STATE.json');recipe=state['recipe']
    if state['kind']=='eegpt_downstream':
        initial=None
        if state['parent'] is not None:
            need('reference_parent' in worker.inputs,'actual original constructor parent');initial=torch.load(worker.inputs['reference_parent']/state['parent']['encoder_state'],map_location='cpu',weights_only=True)
        model=downstream_model(worker.inputs['author_source'],recipe['source_pins'],recipe['architecture'],initial);model.load_state_dict(torch.load(state_root/state['selected_state'],map_location='cpu',weights_only=True)['state_dict'])
    elif state['kind']=='retained_original_class':
        from .legacy_reference import build_original_class
        spec=worker.request['scope'];model,_=build_original_class(worker.inputs['author_source'],spec['method'],spec['dataset'],recipe['class_binding']);model.load_state_dict(torch.load(state_root/state['selected_state'],map_location='cpu',weights_only=True)['state_dict'])
    elif state['kind']=='eegpt_pretraining':
        from .neural_kernel import pretraining_model
        model=pretraining_model(worker.inputs['author_source'],recipe['source_pins'],recipe['variant'],ablation=recipe['ablation'],layout_policy=recipe['fit']['layout_policy']);model.load_state_dict(torch.load(state_root/state['selected_state'],map_location='cpu',weights_only=True)['state_dict'])
    else:raise Refusal('scientific neural diagnostic requires actual eligible fitted neural state, not a prior/statistical surrogate')
    model.eval();return model,state


def _nested_arrays(worker,prefix,value):
    """Preserve every numerical leaf, never summarize away raw diagnostics."""
    import numpy as np
    if isinstance(value,np.ndarray):return {'array':worker.array(prefix+'.npy',value)}
    if isinstance(value,dict):return {k:_nested_arrays(worker,prefix+'-'+k,v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_nested_arrays(worker,prefix+'-'+str(i),v) for i,v in enumerate(value)]
    return value


def diagnose(worker):
    import numpy as np
    import torch
    from . import diagnostics as numerical
    from .neural_kernel import architecture_census
    recipe=worker.recipe();plans=worker.request['output_contract']['products'];model,state=reconstruct(worker);results={}
    for expected in plans:
        kind=expected['type'];plan=expected['support'];name=expected['product_id'];need(type(name) is str and all(c.isalnum() or c in '-_' for c in name),'contained full product id')
        if kind=='T05':result=architecture_census(model,recipe=state['recipe'])
        elif kind=='T07':
            encoder=getattr(model,'target_encoder',getattr(model,'encoder',None));need(encoder is not None and hasattr(encoder,'chan_embed'),'actual source channel embedding module')
            channels=plan['channel_ids'];ids=encoder.prepare_chan_ids(channels);embedding=encoder.chan_embed(ids.to(next(encoder.parameters()).device)).detach().double().cpu().numpy();need(embedding.ndim==3 and embedding.shape[0]==1 and embedding.shape[1]==58,'actual source1x58xD embedding axis');embedding=embedding[0];result=numerical.channel_similarity(embedding,channels,plan['physical_layout'],plan['equality_policy']);result['embeddings']=embedding
        elif kind in ('T08','T09','T10'):
            document=worker.rows('query');rows=list(worker.epochs(document));epochs=np.stack([r[0] for r in rows]);need([r[2] for r in rows]==plan['row_ids'],'full planned diagnostic query population')
            if kind=='T08':result=numerical.perturbation(model,epochs,plan['perturbation_recipe'],device=recipe['device'])
            elif kind=='T09':
                module=dict(model.named_modules()).get(plan['layer']);need(module is not None,'actual predeclared full feature layer');captured=[]
                def record(_module,_args,output):
                    value=output[0] if isinstance(output,tuple) else output;need(isinstance(value,torch.Tensor),'qualified exact feature layer ABI');captured.append(value.detach().double().cpu())
                handle=module.register_forward_hook(record)
                try:
                    with torch.no_grad():model(torch.as_tensor(epochs,dtype=torch.float32,device=recipe['device']))
                finally:handle.remove()
                need(len(captured)==1,'one complete original feature forward');features=captured[0].numpy()
                if plan['pooling']=='flatten_non_sample_axes':features=features.reshape(len(epochs),-1)
                elif plan['pooling']=='mean_tokens':features=features.mean(axis=1)
                else:raise Refusal('unqualified feature pooling; no guessed historical layer')
                result=numerical.representation(features,plan['tsne_recipe'])
            else:
                # Original implementation attention modules need an exact
                # qualified output ABI; hidden candidate heatmaps are not used.
                captures={};handles=[]
                for name in plan['attention_module_paths']:
                    module=dict(model.named_modules()).get(name);need(module is not None,'every actual full planned attention module')
                    need(hasattr(module,'return_attention') and module.return_attention is False,'actual retained Attention module in ordinary prediction mode')
                    def record(_module,_args,name=name):
                        # Retained source returns attention directly when its
                        # return_attention flag is set. Capture the same actual
                        # normalized/rotary q/k input before ordinary forward,
                        # then restore the flag so full prediction is unchanged.
                        prior=_module.return_attention;_module.return_attention=True
                        try:weights=_module.forward(*_args)
                        finally:_module.return_attention=prior
                        need(isinstance(weights,torch.Tensor),'exact retained attention-return branch');captures.setdefault(name,[]).append(weights.detach().double().cpu().numpy())
                    handles.append(module.register_forward_pre_hook(record))
                try:
                    with torch.no_grad():model(torch.as_tensor(epochs,dtype=torch.float32,device=recipe['device']))
                finally:
                    for h in handles:h.remove()
                need(set(captures)==set(plan['attention_module_paths']) and all(len(x)==1 for x in captures.values()),'every original complete attention return captured once');weights=np.stack([captures[k][0] for k in plan['attention_module_paths']]);mask=np.asarray(plan['valid_mask'],dtype=bool);result=numerical.attention_summary(weights,mask,plan['attention_recipe'])
        else:raise Refusal('full scientific product requires its matching producer, not a generic JSON stub: '+kind)
        from .family_products import diagnostic
        diagnostic(worker,expected,result,state)
        stored=_nested_arrays(worker,'diagnostic-'+name,result);worker.json('diagnostic-'+name+'.json',stored);results[name]={'type':kind,'complete_numerical_result':stored,'reference_recipe':identity(recipe),'source_qualification':recipe['qualification']}
    worker.response['diagnostics']={'complete_original_diagnostics':results,'scientific_adjudication_pending':True}
    return results


def analyze(worker):
    from . import diagnostics as numerical
    from .reference_worker import load_json
    action=worker.request['action'];recipe=worker.recipe()
    if action=='seal_complete_analysis_specification':
        expected=worker.request['output_contract']['products'];need(expected and all(p['type']=='T06' for p in expected),'actual full protected scaling analysis declarations')
        specifications={p['product_id']:p['support']['analysis_specification'] for p in expected};worker.json('ANALYSIS_PROGRAM.json',{'language':'closed_declared_scientific_reduction_v1','specifications':specifications,'actual_assessment_execution':'trusted independent A12 only','candidate_code_executed_after_targets':False});worker.response['diagnostics']={'analysis_specifications':specifications,'assessment_metrics_seen':False};return specifications
    if action=='reduce_pretraining_losses':
        source=worker.inputs['fitted'];state=load_json(source/'STATE.json');rows=[]
        with (source/state['full_curve_file']).open('rb') as f:
            for line in f:rows.append(json.loads(line))
        need([r['id'] for r in rows]==state['loss_observation_ids'],'all original selected train/validation loss records');result=numerical.loss_reduction(rows,recipe['ablation'])
        from .family_products import training_products
        training_products(worker,worker.request['output_contract']['products'],state,curve_root=source)
    elif action=='reduce_complete_scaling':
        source=load_json(worker.inputs['scientific_points']/'POINTS.json');result=numerical.scaling(source['points'],recipe['scaling_recipe'])
    else:raise Refusal('unrecognized actual source-owned full scientific reduction')
    stored=_nested_arrays(worker,'analysis',result);worker.json('ANALYSIS.json',stored);worker.response['diagnostics']={'actual_complete_analysis':stored,'recipe':identity(recipe),'scientific_qualification':False};return result


def query_transform(worker):
    """Explicit source-native, case-local EA. Strict primary never invokes A07."""
    import numpy as np
    from .protocol import fields,need,identity
    from .neural_kernel import trusted_author_module
    document=worker.rows('query');recipe=worker.recipe()['query_transform'];fields(recipe,('kind','source_pin','group_by','qualification'),'complete named source-native query transform');need(recipe['kind']=='retained_EA' and recipe['group_by']==['person_id','session_id'],'explicit original case-local session EA; no pooled cross-case transformer')
    module=trusted_author_module(worker.inputs['author_source'],'downstream/Data_process/utils.py',recipe['source_pin']);groups={};epochs=list(worker.epochs(document))
    for i,row in enumerate(document['rows']):need(row['label'] is None,'no query labels in actual transformation');groups.setdefault((row['person_id'],row['session_id']),[]).append(i)
    transformed=[None]*len(epochs)
    for group,indices in groups.items():
        original=np.stack([epochs[i][0] for i in indices]);value=module.EA(original);need(value.shape==original.shape and not np.iscomplexobj(value) and np.isfinite(value).all(),'complete finite real source EA result; no silent ridge regularizer or imaginary-part deletion')
        for i,x in zip(indices,value,strict=True):transformed[i]=x
    rows=[]
    for i,(prior,x) in enumerate(zip(document['rows'],transformed,strict=True)):
        member=worker.array('query-transformed-%08d.npy'%i,np.asarray(x,dtype='<f8'));row={**prior,'signal':{'path':'/inputs/query/'+member['path'],'format':prior['signal']['format'],'shape':list(x.shape),'bytes':member['bytes'],'sha256':member['sha256']}};rows.append(row)
    worker.json('rows.json',{**document,'rows':rows});worker.response['diagnostics']={'actual_recipe':recipe,'original_support_identity':document['whole_support_identity'],'all_group_sizes':[len(v) for v in groups.values()],'case_local_unlabeled_transduction':True,'inductive_primary_result':False,'query_state_exported_to_development':False}
