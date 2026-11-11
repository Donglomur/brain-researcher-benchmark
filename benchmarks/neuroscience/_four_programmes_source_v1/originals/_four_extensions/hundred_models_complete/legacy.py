"""Compose unchanged reviewed catalogue, inference and dimension consumers."""
import importlib
from pathlib import Path
import sys
from dataclasses import asdict
from .guard import need,bare,encoded,Unscorable

SOURCE_COMPARISONS=('source_default92_ModelType','paper_Fig4_video41_ArchType','paper_Fig5_K4001_vs_K710','paper_Fig5_K4002_vs_SSv2')

def modules(package_root):
    root=Path(package_root).absolute()/'source-donors/consumers';sys.path.insert(0,str(root))
    result={}
    for name in ('hundred_models_program.catalog','hundred_models_program.inference','hundred_models_program.program','hundred_models_dimensions.program','hundred_models_dimensions.consumers','hundred_models_dimensions._depth'):
        m=importlib.import_module(name);need(Path(m.__file__).resolve().is_relative_to(root.resolve()),'exact retained consumer origin');result[name]=m
    return result

def graph_binding(protocol,feature_receipts,environment,inputs,protocol_pin):
    records=[]
    for model in protocol['models']:
        observed=feature_receipts[('test',model['id'])];resource=inputs['models'][model['id']]
        need(observed['configuration']==bare(encoded(model['config'])) and observed['ordered_ids']==protocol['stimuli'],'native feature/configuration and complete emission support')
        records.append({'model_id':model['id'],'configuration':bare(encoded(model['config'])),'profile':'author_5e802ae5_order_with_net2brain_0beb63d3_extraction','framework_identity':environment['identity'],'framework_source_files':[{k:x[k] for k in ('bytes','sha256')} for x in environment['files']],'checkpoint':{k:resource['checkpoint'][k] for k in ('bytes','sha256')},'named_modules':observed['named_modules'],'emitted_feature_keys':observed['emitted_feature_keys'],'stimulus_order':bare(encoded(protocol['stimuli'])),'subjects':protocol['subjects'],'emission_receipt':bare(encoded(observed)),'graph_receipt':bare(encoded(observed['named_modules'])),'all102_emission_keysets_identical':True,'evidence_origin':'operator_admitted_metadata'})
    # This result is an observed producer-to-consumer join, never historical proof.
    return {'schema':'hundred_models_graph_metadata_v1','protocol':protocol_pin,'profile':'author_5e802ae5_order_with_net2brain_0beb63d3_extraction','models':records}

def main_inference(mods,protocol_raw,inventory_raw,graph_raw,schedule,observed_rows,null_rows,limits):
    c=mods['hundred_models_program.catalog'];inf=mods['hundred_models_program.inference'];program=mods['hundred_models_program.program']
    schedule_binding=inf.bind_schedule(tuple(tuple(p) for p in schedule),null_operator='source_rows_only')
    bound=program.bind_program(protocol_raw,inventory_raw,graph_raw,c.pin(graph_raw),schedule=schedule_binding,layer_null_rule='source_observed_best_layer_conditional',comparisons=inf.SOURCE_COMPARISONS,limits=inf.WorkLimits(**limits))
    def observed():
        for roi,models in observed_rows:
            yield inf.ObservedROI(roi,tuple(inf.ObservedModel(model,tuple(inf.ObservedLayer(layer,tuple(values)) for layer,values in layers)) for model,layers in models))
    def null():
        for roi,k,models in null_rows:
            yield inf.NullBatch(roi,k,schedule_binding.permutation_digests[k],schedule_binding.schedule_sha256,'source_rows_only',inf.SUBJECTS,tuple(inf.NullModelMeans(model,tuple(inf.NullLayerMean(layer,value,10) for layer,value in layers)) for model,layers in models))
    result=program.run_program(bound,observed(),null())
    return {**result,'inference':asdict(result['inference'])}

def dimension_run_binding(branch,protocol,catalog,graph,inputs,receipts,protocol_pin):
    folders=inputs['dimension_folders'] if branch=='figure16' else [inputs['train_folder']]
    panel='test' if branch=='figure16' else 'train';n,repetitions=(102,10) if panel=='test' else (1000,3)
    models=[x['id'] for x in protocol['models'] if x['type'] in (('image-in1k','image-k400','video-k400') if branch=='figure16' else ('image-in1k','image-k400'))]
    producer={x['model_id']:tuple(x['emitted_feature_keys']) for x in graph['models']};conditions=[]
    for model in models:
        for folder in folders:
            method={'models_pca_rerun':'pca','models':'srp','models_no_dimred':'none'}[folder] if branch=='figure16' else 'pca'
            key=f'{panel}:{method}:{model}';rdm=receipts['rdm'][key];feature=receipts['features'][(panel,model)]
            reduction=rdm['reduction'];spec={k:reduction[k] for k in ('method','n_samples_estim','n_components','max_dim_allowed')}
            spec['method']=None if method=='none' else method
            spec.update(standardize_on_dim=None,distance='pearson',sklearn_kwargs_policy='constructor-only-n_components;other-keywords-omitted')
            scores=[receipts['rsa'][(key,roi)] for roi in inputs['rois']]
            conditions.append({'model':model,'folder':folder,'stimulus_order':bare(encoded(inputs['panels'][panel]['ordered_ids'])),'layer_order':bare(encoded(tuple(catalog['models'][model]['layers']))),'producer_layer_order':bare(encoded(producer[model])),'n_stimuli':n,'split_emission_receipt':bare(encoded(feature)),'operation_contract':bare(encoded(rdm)),'score_provenance_receipt':bare(encoded(scores)),'operation_profile':{'pca':'literal_held_script_pca100_fit102','srp':'explicit_admitted_srp_run_metadata','none':'explicit_admitted_no_reduction_run_metadata'}[method],'reduction':spec})
    brain=[receipts['brain'][(panel,s,roi)] for s in protocol['subjects'] for roi in inputs['rois']]
    return {'schema':'hundred_models_dimension_run_v1','branch':branch,'protocol':protocol_pin,'evidence_origin':'operator_admitted_run_metadata','split':{'selection':panel,'ordered_ids':inputs['panels'][panel]['ordered_ids'],'n_stimuli':n,'repetitions':repetitions,'order_admission':{k:inputs['panels'][panel]['identity_witness'][k] for k in ('bytes','sha256')}},'brain':{'subjects':protocol['subjects'],'rois':inputs['rois'],'n_stimuli':n,'repetitions':repetitions,'average_external':False,'operation_contract':bare(encoded(brain)),'shape_manifest':bare(encoded([r['shape'] for r in brain])),'noise_ceiling_receipt':bare(encoded([receipts['rsa'][(f'{panel}:pca:{models[0]}',roi)]['noise_ceilings'] for roi in inputs['rois']]))},'base_folder':folders[-1],'comparison_folders':folders[:-1],'conditions':conditions}

def dimension_consume(mods,branch,protocol_raw,inventory_raw,graph_raw,run,frames,limits):
    d=mods['hundred_models_dimensions.program'];c=mods['hundred_models_dimensions.consumers'];cat=mods['hundred_models_program.catalog'];depth=mods['hundred_models_dimensions._depth']
    limits={**limits,'depth':depth.Limits(**limits['depth'])};raw=encoded(run)
    bound=d.bind_branch(branch,protocol_raw,inventory_raw,graph_raw,cat.pin(graph_raw),raw,cat.pin(raw),limits=d.Limits(**limits))
    def stream():
        for roi,rows,ceil in frames:
            yield c.ROIFrame(roi,tuple(c.ModelCondition(m,folder,tuple(c.LayerScore(layer,value) for layer,value in layers)) for m,folder,layers in rows),c.NoiseCeiling(*ceil))
    result=[]
    for event in d.run_branch(bound,stream()):result.append(asdict(event))
    need(result and result[-1].get('whole_branch_complete') is True,'genuine complete branch EOF')
    return result
