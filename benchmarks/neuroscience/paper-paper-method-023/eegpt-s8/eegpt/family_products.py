"""Typed full-family emission from actual numerical/source producer results."""
from .protocol import need,identity,relative


def emit(worker,expected,body,numerical_arrays):
    need(set(numerical_arrays)==set(expected['arrays']),'all prespecified scientific arrays, no guessed omitted columns')
    arrays={}
    for key,value in numerical_arrays.items():
        import numpy as np
        a=np.asarray(value);shape=expected['arrays'][key]['shape'];need(list(a.shape)==shape,'complete original scientific axes for '+key)
        if a.dtype.kind in ('b','i','u'):a=a.astype('<f8')
        else:a=a.astype('<f8',copy=False)
        need(np.isfinite(a).all(),'undefined scientific support is explicit metadata/mask, never unmarked NaN')
        arrays[key]=worker.array(expected['product_id']+'-'+key+'.npy',a)
    product={'schema':'eegpt_product_v1','product_id':expected['product_id'],'type':expected['type'],'status':'complete','scope':expected['scope'],'parents':expected['parents'],'support_identity':expected['support_identity'],'arrays':arrays,'body':body,'reason':None};worker.products.append(product);return product


def architecture(worker,expected,result,state):
    recipe=state['recipe'];parameters=result['parameters'];modules=result['module_types']
    body={'modules':modules,'dimensions':{r['name']:r['shape'] for r in parameters},'tokens':recipe.get('architecture',recipe).get('variant',recipe.get('variant')),'patches':recipe.get('architecture',recipe).get('patch_stride',64),'trainability':{r['name']:r['trainable'] for r in parameters},'parameters':result['counts'],'masks':{'visible_channel_count':12,'missing_time_probability':.5,'other_target_channel_probability':.2,'reject_empty_visible_and_other_targets':True} if state['kind']=='eegpt_pretraining' else {'pretraining_masks_used_in_downstream_query':False},'normalization':{'actual_module_properties':result.get('module_normalization',{}),'pretraining_feature_target_layer_norm_epsilon':1e-5 if state['kind']=='eegpt_pretraining' else None,'pretraining_waveform_target_layer_norm_epsilon':1e-5 if state['kind']=='eegpt_pretraining' and recipe['ablation']!='B' else None},'optimizer':state.get('actual_optimizer_membership',recipe.get('fit')),'scheduler':recipe.get('fit'),'ema':{'initial':.996,'final':1.,'source_recipe':identity(recipe)} if state['kind']=='eegpt_pretraining' else None}
    if state['kind']=='arl_eegnet_v1':
        body['tokens']={'kind':'convolutional_EEGNet_no_transformer_tokens'};body['patches']={'kind':'temporal_convolution','kernel_samples':64,'output_hz':128,'pooling_samples':[4,8]};body['scheduler']=None
        body['optimizer']=state['source_scientific_recipe']['training']
    elif state['kind']=='temple_reference_v1':
        method=state['method'];body['tokens']={'method':method,'kind':'original_source_architecture','source_manifest':state['source_manifest']}
        body['patches']=({'kind':'LaBraM_time_patches','samples':200,'sampling_hz':200} if method.startswith('LaBraM-') else {'kind':'source_STFT','n_fft':200,'hop_length':100 if method=='BIOT' else 10} if method in ('BIOT','CNN-T','ContraWR','FFCL') else {'kind':'direct_source_convolution','sampling_hz':200})
    return emit(worker,expected,body,{})


def diagnostic(worker,expected,result,state):
    import numpy as np
    t=expected['type'];plan=expected['support'];arrays={}
    if t=='T05':return architecture(worker,expected,result,state)
    if t=='T07':
        arrays={'embeddings':result['embeddings'],'cosines':result['cosines']};body={'channel_ids':result['channel_ids'],'embeddings':'embeddings','cosines':'cosines','zero_norm':result['zero_norm'],'physical_layout':result['physical_layout'],'edges':result['edges'],'equality_policy':result['equality_policy']}
    elif t=='T08':
        records=[r for r in result['all_records'] if 'draw' in r];channels=plan['perturbation_recipe']['channel_ids'];draws=plan['perturbation_recipe']['draw_ids'];lookup={(r['channel'],r['draw']):r for r in records};need(set(lookup)=={(c,d) for c in channels for d in draws},'all actual original perturbation cells')
        noise=np.stack([[lookup[c,d]['noise'] for d in draws] for c in channels]);changed=np.stack([[lookup[c,d]['perturbed_logits'] for d in draws] for c in channels]);delta=np.stack([[lookup[c,d]['delta'] for d in draws] for c in channels]);summaries={r['channel']:r['summary'] for r in result['all_records'] if 'summary' in r};arrays={'baseline_logits':result['baseline'],'noise':noise,'perturbed_logits':changed,'deltas':delta};body={'plan_indices':plan['indices'],'baseline_logits':'baseline_logits','noise':'noise','perturbed_logits':'perturbed_logits','deltas':'deltas','noise_policy':plan['noise_policy'],'pearson_sums':summaries,'denominators':{c:[r['n'] for r in summaries[c]] for c in channels}}
    elif t=='T09':
        arrays={'features':result['features'],'tsne':result['coordinates']};body={'row_ids':result['row_ids'],'features':'features','layer':plan['layer'],'pooling':plan['pooling'],'tsne':'tsne','tsne_recipe':plan['tsne_recipe']}
    elif t=='T10':
        arrays={'weights':result['full_weights'],'valid_mask':result['valid_mask']};body={'axes':plan['axes'],'weights':'weights','valid_mask':'valid_mask','aggregation':plan['aggregation'],'state':identity(state),'query':identity(plan['row_ids'])}
    else:raise ValueError('matching full scientific diagnostic producer required')
    return emit(worker,expected,body,arrays)


def training_products(worker,expected_products,state,*,curve_root=None):
    from .reference_worker import load_json
    from .protocol import decode
    for expected in expected_products:
        if type(expected) is str:continue
        t=expected['type'];plan=expected['support']
        if t=='T04':
            observations=[]
            relative(state['full_curve_file'])
            with ((worker.output if curve_root is None else curve_root)/state['full_curve_file']).open('rb') as stream:
                for line in stream:
                    row=decode(line);observations.append({'id':row['id'],'step':row['step'],'epoch':row['epoch'],'partition':row['partition'],'LA_numerator':row['LA_numerator'],'LA_denominator':row['LA_denominator'],'LR_numerator':row['LR_numerator'],'LR_denominator':row['LR_denominator'],'total':row['total'],'checkpoint':row['logical_training_state'],'crop':row['crop_rows'],'mask':{'visible':row['mask_x'],'target':row['mask_y']},'rng':row['rng_state_identity'],'exposure':len(row['crop_rows'])})
            need([r['id'] for r in observations]==plan['observation_ids'],'every prespecified source loss observation')
            body={'observations':observations,'normalization':plan['normalization'],'variant':state['recipe']['ablation'],'checkpoints':state['all_checkpoints'],'mask_crop_rng':{'actual_full_masks_and_crops_in_each_observation':True},'exposure':{'train_support':state['recipe']['fit']['original_support_identity'],'complete_observed_records':len(observations)}};emit(worker,expected,body,{})
        elif t=='T05':architecture(worker,expected,state['actual_architecture'],state)
        elif t=='T02':
            declared=worker.response['selected_state'];arrays={};need(not expected['arrays'],'opaque model files use observed artifact descriptors, never evaluator numeric decoding')
            body={'states':[r for r in worker.artifacts if r['path'] in set(declared['files'])],'initialization':declared['initialization'],'train_support':plan['train_support'],'selection':plan['selection'],'optimizer':state.get('actual_optimizer_membership',state['recipe'].get('fit')),'state_changes':{'actual_producer':worker.request['source_identity'],'fit_kind':declared['fit_kind'],'final_state_artifacts':declared['files']},'rng':declared['rng'],'precision':state['recipe'].get('fit',{}).get('precision','source_recipe_qualified'),'source_ancestry':worker.request['public_parent_identities'],'context_ancestry':worker.request['context_identity']};emit(worker,expected,body,arrays)
        elif t=='T01':
            names=[name for name in ('train','validation','corpus_train','corpus_validation') if name in worker.inputs];documents={name:worker.rows(name) for name in names}
            body={'cohort':{k:[r['person_id'] for r in v['rows']] for k,v in documents.items()},'split':{k:[r['row_id'] for r in v['rows']] for k,v in documents.items()},'exclusions':plan['qualified_exclusions'],'source_axes':{k:[{'row_id':r['row_id'],'channels':r['channels'],'sampling_hz':r['sampling_hz'],'units':r['units'],'interval':r['interval']} for r in v['rows']] for k,v in documents.items()},'transforms':plan['qualified_raw_to_derived_ancestry']};emit(worker,expected,body,{})
        elif t=='T06':
            # Candidate analysis is sealed during A09; protected results are
            # generated only by A12 from all original captured primitives.
            continue
        else:raise ValueError('scientific product requires its actual matching lifecycle producer: '+t)
