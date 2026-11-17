"""Bind every renderer row to actual RSA/null producers, including both dimension panels."""
from .guard import need
from .array_io import load_array
from .scope import METHOD_FOLDERS


def source_group_label(kind,method):
    need(type(kind)is str and kind and method in METHOD_FOLDERS,'source model type and reduction method')
    return kind+'-'+METHOD_FOLDERS[method]

def validate_call(protocol,inputs,call):
    """Both Figure16 native routes use the same complete source folder ABI."""
    if call['groupby']!='ModelTypeFolder':return
    need(call['figure']==16 and call['kind'] in ('best','depth'),'closed Figure16 best/depth grouping')
    models=[m['id'] for m in protocol['models'] if m['type'] in ('image-in1k','image-k400','video-k400')]
    need(len(models)==92 and call['models']==models,'complete ordered92 Figure16 models')
    inverse={v:k for k,v in METHOD_FOLDERS.items()};folders=inputs['dimension_folders']
    need(folders==['models_no_dimred','models','models_pca_rerun'],'admitted source folder display order')
    expected=['test:'+inverse[folder]+':'+model for model in models for folder in folders]
    need(call['conditions']==expected,'all276 ordered model/reduction conditions required')
    need(not call.get('model_type_labels'),'source Figure16 types may not be relabeled')

def rows(session,protocol,receipts,selected_values,call):
    validate_call(protocol,session.inputs,call)
    np=session.np;b=session.budget;out=[];meta={m['id']:m for m in protocol['models']}
    for condition in call['conditions']:
        panel,method,model=condition.split(':',2);m=meta.get(model)
        need(m is not None or model=='videomae_B_pretrainONLY','source model roster')
        for roi in call['rois']:
            receipt=receipts['rsa'][(condition,roi)];lnc,unc=receipt['noise_ceilings']
            if call['include_nulls']:
                need(panel=='test' and method=='pca','no fabricated SRP/train null experiments')
                null=receipts['null'][(model,roi)];a=load_array(np,null['output_root'],null['values'],null['shape'],b,allow_undefined=True);names=[x.replace('.','_') for x in null['layers']]
            for index,(layer,values) in enumerate(selected_values(condition,roi)):
                need(all(np.isfinite(v) for v in values),'undefined participant statistic prevents complete render')
                r=float(np.mean(values));p=None if not call['include_nulls'] else float(np.mean(np.abs(a[names.index(layer)])>=abs(r)))
                if call['include_nulls']:need(np.isfinite(a[names.index(layer)]).all(),'undefined null coverage cannot create p-value')
                cfg={} if m is None else m['config'];kind='video-pretrain' if m is None else m['type']
                out.append({'Condition':condition,'ROI':roi,'Model':model,'ModelType':call.get('model_type_labels',{}).get(model,kind),'ModelTypeFolder':source_group_label(kind,method),'ArchType':None if m is None else m['architecture'],'Layer':index,'Layer_FullNames':layer,'R':r,'R_array':np.asarray(values),'SEM':float(session.stats.sem(values)),'LNC':lnc,'UNC':unc,'pvalue':p,'ModelParams':cfg.get('params'),'ModelFlops':cfg.get('flops'),'ModelAccuracy':cfg.get('accuracy')})
    return out

def nulls(session,receipts,call):
    np=session.np;b=session.budget;out={}
    if not call['include_nulls']:return None
    for condition in call['conditions']:
        panel,method,model=condition.split(':',2);need(panel=='test' and method=='pca','only actual original null branch')
        out[model]={}
        for roi in call['rois']:
            row=receipts['null'][(model,roi)];a=load_array(np,row['output_root'],row['values'],row['shape'],b,allow_undefined=True)
            need(np.isfinite(a).all(),'complete renderer null support')
            for k,layer in enumerate(row['layers']):out[model][layer.replace('.','_')+'_fmri_'+roi]=a[k,:]
    return out
