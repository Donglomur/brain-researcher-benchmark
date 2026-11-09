"""Fixed-schema numeric state transport; never pickle or executable objects."""
from pathlib import Path
import common as c
import protocol as p
import arrays

MODEL_KEYS=('schema','family','configuration','class_ids','n_train','n_features','temperature','scaler_mean','scaler_scale','parameters','diagnostics')

def parameter_shapes(family,n,d):
    if family in ('BP_LDA','TM_LDA','HISTORICAL_BP_LDA'):return {'coefficients':[d,12],'intercepts':[12]}
    c.need(family=='RBF_KRR','known model family')
    return {'training_z':[n,d],'dual':[n,12],'row_kernel_mean':[n],'grand_kernel_mean':[],'class_mean':[12]}

def scalar_tree(value):
    if type(value)is dict:
        c.need(all(type(k)is str for k in value),'plain model metadata keys');return {k:scalar_tree(v)for k,v in value.items()}
    if type(value)is list:return [scalar_tree(x)for x in value]
    c.need(type(value)in(str,int,float,bool,type(None)),'plain JSON numeric diagnostics')
    if type(value)is float:c.finite(value)
    return value

def write(model,root,training_role,selection,source,budget):
    c.exact(model,MODEL_KEYS);c.need(model['schema']=='neural081_numeric_model_v1'and c.typed_equal(model['class_ids'],list(c.CLASSES)),'non-executable complete numerical model')
    n=c.integer(model['n_train'],12);d=c.integer(model['n_features'],1);family=model['family'];shapes=parameter_shapes(family,n,d)
    c.need(d==(1024 if family=='TM_LDA'else 320),'full declared feature width');c.exact(model['parameters'],shapes)
    root=c.new_directory(root,budget);np=arrays.numpy();state={}
    for name,value in [('scaler_mean',model['scaler_mean']),('scaler_scale',model['scaler_scale']),*model['parameters'].items()]:
        shape=[d]if name.startswith('scaler_')else shapes[name]
        if shape==[]:
            value=np.array(c.finite(value),dtype=np.float64)
        arrays.exact_array(value,'float64',shape)
        if name=='scaler_scale':c.need(bool((value>0).all()),'strict positive model scales')
        desc=arrays.write(root/(name+'.npy'),value,budget);state[name]={'array':desc,'dtype':'float64','shape':shape}
    meta={k:scalar_tree(model[k])for k in ('schema','family','configuration','class_ids','n_train','n_features','temperature','diagnostics')}
    meta.update(state=state,training_role=training_role,selection=selection,numeric_source=source)
    return c.publish_json(root/'MODEL.json',meta,budget)

def read(desc,access,*,limits):
    meta=access.json(desc)
    c.exact(meta,('schema','family','configuration','class_ids','n_train','n_features','temperature','diagnostics','state','training_role','selection','numeric_source'))
    c.need(meta['schema']=='neural081_numeric_model_v1'and c.typed_equal(meta['class_ids'],list(c.CLASSES)),'exact full model schema/classes')
    n=c.integer(meta['n_train'],12);d=c.integer(meta['n_features'],1);shapes=parameter_shapes(meta['family'],n,d);c.exact(meta['state'],('scaler_mean','scaler_scale',*shapes))
    c.need(d==(1024 if meta['family']=='TM_LDA'else 320),'full saved feature width')
    complete_bytes=0
    for name,state in meta['state'].items():
        shape=[d]if name.startswith('scaler_')else shapes[name];size=8
        for extent in shape:size*=extent
        c.need(size<=limits['max_array_bytes'],'saved model per-array bound');complete_bytes+=size
    c.need(complete_bytes*3<=limits['max_workspace_bytes'],'saved model plus complete read/decode workspace')
    model={k:meta[k]for k in ('schema','family','configuration','class_ids','n_train','n_features','temperature','diagnostics')};model['parameters']={}
    for name,state in meta['state'].items():
        shape=[d]if name.startswith('scaler_')else shapes[name]
        c.exact(state,('array','dtype','shape'));c.need(state['dtype']=='float64'and c.typed_equal(state['shape'],shape),'exact model array metadata')
        access.admit(state['array']);value=arrays.read(state['array'],'float64',shape,access.budget,[Path(state['array']['path']).parent],max_array_bytes=limits['max_array_bytes'])
        if shape==[]:value=float(value)
        if name=='scaler_scale':c.need(bool((value>0).all()),'strict positive loaded scales')
        if name.startswith('scaler_'):model[name]=value
        else:model['parameters'][name]=value
    return model,meta

def descriptors(meta):
    return [v['array']for v in meta['state'].values()if 'array'in v]

def public_model(meta,handle,temperature,strongest,priors,row_tokens):
    c.need(handle in p.HANDLES and strongest in p.FAMILIES,'fixed public handles')
    scaler={};parameters={}
    for name,state in meta['state'].items():
        value={'relative_path':name+'.npy','dtype':state['dtype'],'shape':state['shape'],'bytes':state['array']['bytes'],'sha256':state['array']['sha256']}
        (scaler if name.startswith('scaler_')else parameters)[name]=value
    return {'schema':'neural081_candidate_model_v2','handle':handle,'family':meta['family'],'configuration':meta['configuration'],'class_ids':list(c.CLASSES),'feature_definition':'TM'if handle=='TM_LDA'else'BP','scaler':scaler,'parameters':parameters,'calibration':{'temperature':c.finite(temperature,0)},'training_row_tokens_or_null':row_tokens if handle=='RBF_KRR'else None,'strongest_family':strongest,'uniform_probabilities':priors['uniform'],'laplace_probabilities':priors['laplace']}
