"""Real native producers. No native import occurs until explicit qualified execution admission.

The admitted environment and external isolation must be independently qualified.
These source checks do not create a sandbox or recover missing historical evidence.
"""
import importlib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from .guard import need,Unscorable,capture,strict,descriptor,bare,encoded,ordinary,Publisher
from .array_io import verify_file,load_array,save_array,finite_json

class NativeSession:
    def __init__(self,root,inputs,authority,budget):
        self.root=Path(root).absolute();self.inputs=inputs;self.authority=authority;self.budget=budget
        need(authority['schema']=='hundred_models_external_scientific_selection_v1' and authority['scientific_execution_selected'] is True,'separate explicit scientific selection required')
        need(authority['inputs']==bare(encoded(inputs)) and authority['external_isolation']==inputs['external_isolation'] and authority['environment']==inputs['environment'],'exact selected inputs/environment/isolation')
        env=strict(capture(self.root,inputs['environment'],budget));isolation=strict(capture(self.root,inputs['external_isolation'],budget))
        need(env['schema']=='hundred_models_native_environment_v1' and isolation['schema']=='hundred_models_external_isolation_receipt_v1','qualified environment/lease ABI')
        need(isolation['qualified'] is True and isolation['network']=='disabled' and isolation['deadline_ns']==budget.deadline_ns,'external isolation identity; declaration is not independent qualification')
        need(env['qualified_native_compatibility'] is True and env['python_binary']==authority['python_binary'],'native compatibility and executable identity')
        verify_file(self.root,authority['python_binary'],budget)
        self.env=env
        for row in env['files']:verify_file(self.root,row,budget)
        for spelling in reversed(env['source_roots']):
            p=ordinary(self.root,spelling);need(p.is_dir(),'admitted source import root');sys.path.insert(0,str(p))
        needed=('numpy','scipy.stats','hydra.utils','omegaconf','net2brain.feature_extraction','net2brain.rdm_creation','repralign.models.custom_extraction_functions')
        self.modules={}
        for name in needed:
            need(name in env['modules'],'every imported native entry has a source binding')
            module=importlib.import_module(name);expected=env['modules'][name]
            actual=verify_file(self.root,expected,budget)
            need(Path(module.__file__).resolve()==actual.resolve(),'native module resolved to exact admitted source')
            self.modules[name]=module
        self.np=self.modules['numpy'];self.stats=self.modules['scipy.stats']
        budget.check()
    def close(self):
        # Native process exit owns framework memory; no claim that deleting Python objects tears down CUDA.
        self.budget.check()

def brain(session,panel,row,publisher):
    np=session.np;b=session.budget;source=session.inputs['panels'][panel]
    need(row['stimulus_identity']==source['identity_witness'],'S03/S06 common identities')
    pieces=[load_array(np,session.root,v['file'],v['shape'],b) for v in row['parts']]
    b.charge('work',sum(int(x.size) for x in pieces));joined=np.concatenate(pieces,axis=2)
    need(list(joined.shape)==row['shape'],'full voxel support after source merge')
    mean=joined.mean(axis=1);b.check();rdm=1-np.corrcoef(mean);b.check()
    # Retain nonfinite/constant-response coverage; no neuron/voxel/stimulus deletion.
    result=save_array(np,publisher,'brain.npy',rdm.astype('<f8'))
    response=save_array(np,publisher,'response_mean.npy',mean)
    return {'schema':'hundred_models_brain_production_v1','panel':panel,'subject':row['subject'],'roi':row['roi'],'stimulus_identity':source['identity_witness'],'source_parts':row['parts'],'mean_response':response,'response_shape':list(mean.shape),'shape':list(rdm.shape),'rdm':result,'undefined_cells':int(np.isnan(rdm).sum()),'source_mean_repetitions':source['repetitions'],'output_root':str(publisher.root)}

def features(session,panel,model,config,publisher):
    b=session.budget;np=session.np;inputs=session.inputs;record=inputs['models'][model];support=inputs['panels'][panel]
    for key in ('checkpoint','native_graph_source','preprocessing'):verify_file(session.root,record[key],b)
    loading=strict(capture(session.root,record['loading_witness'],b))
    need(loading['schema']=='hundred_models_qualified_loading_binding_v1' and loading['independently_qualified'] is True,'separate actual loading/weight witness required')
    need(loading['configuration']==bare(encoded(config)) and loading['checkpoint']==record['checkpoint'],'exact configuration/checkpoint load binding')
    for v in support['videos']:verify_file(session.root,v['file'],b)
    video_dir=ordinary(session.root,support['video_directory']);names=[Path(v['file']['path']).name for v in support['videos']]
    need({p.name for p in video_dir.iterdir()}==set(names) and len(set(names))==len(names),'exact complete video directory')
    need(all(ordinary(session.root,v['file']['path']).parent==video_dir for v in support['videos']),'all videos in bound producer directory')
    OmegaConf=session.modules['omegaconf'].OmegaConf;instantiate=session.modules['hydra.utils'].instantiate
    source=session.modules['repralign.models.custom_extraction_functions'];FeatureExtractor=session.modules['net2brain.feature_extraction'].FeatureExtractor
    cfg=OmegaConf.create({'location':str(ordinary(session.root,inputs['source_location'])),'model':config});OmegaConf.resolve(cfg);m=cfg.model
    kwargs={'device':inputs['device']}
    if m.get('set') is not None:
        fx=FeatureExtractor(model=m.name,netset=m.set,feature_cleaner=source.fixed_cleaner if m.set=='Pyvideo' else source.generic_cleaner_tuples,**kwargs)
    else:
        obj=instantiate(m.cfg).to(inputs['device']);pre=instantiate(m.preprocessor) if m.get('preprocessor') else None;ex=instantiate(m.extractor) if m.get('extractor') else None
        fx=FeatureExtractor(model=obj,netset_fallback=m.netset_fallback,preprocessor=pre,extraction_function=ex,feature_cleaner=source.fixed_cleaner if m.netset_fallback=='Pyvideo' else source.generic_cleaner_tuples,**kwargs)
    graph=[name for name,_ in fx.model.named_modules()]
    state_hash=hashlib.sha256()
    for name,tensor in fx.model.state_dict().items():
        size=tensor.numel()*tensor.element_size();b.charge('read_bytes',size);b.check()
        value=tensor.detach().cpu().contiguous().numpy()
        state_hash.update(encoded({'name':name,'shape':list(value.shape),'dtype':value.dtype.str}));state_hash.update(memoryview(value).cast('B'));b.check()
    need(state_hash.hexdigest()==loading['loaded_state_sha256'] and bare(encoded(graph))==loading['named_modules'],'actual loaded graph and weights match qualified witness')
    feature_dir=publisher.root/'features';b.charge('write_bytes',record['maximum_feature_bytes']);b.check()
    try:fx.extract(data_path=str(video_dir),save_path=str(feature_dir),consolidate_per_layer=False,layers_to_extract=m.get('layers'))
    except BaseException as e:e.native_output_prefix={'root':str(publisher.root),'native_feature_directory':str(feature_dir),'extent_unknown_after_native_failure':True};raise
    b.check();files=list(feature_dir.iterdir());need(all(p.is_file() and not p.is_symlink() and p.suffix=='.npz' and p.stat().st_nlink==1 for p in files),'complete ordinary native feature outputs')
    files.sort(key=lambda p:tuple((1,int(t)) if t.isdigit() else (0,t) for t in re.split('(\d+)',p.name)))
    need(len(files)==len(names) and [p.stem for p in files]==[Path(n).stem for n in names],'complete actual stimulus emission order')
    emissions=[];keys=None;total=0
    for p,stimulus in zip(files,support['ordered_ids']):
        n=p.stat().st_size;total+=n;need(total<=record['maximum_feature_bytes'],'native feature extent reservation')
        b.charge('read_bytes',n)
        with np.load(p,allow_pickle=False) as data:
            actual=list(data.files);need(keys is None or actual==keys,'all emitted keysets and order identical');keys=actual
            shapes={k:list(data[k].shape) for k in actual};need(all(data[k].dtype.kind=='f' and np.isfinite(data[k]).all() for k in actual),'finite native features')
        b.charge('read_bytes',n);h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(65536),b''):b.check();h.update(chunk)
        emissions.append({'stimulus':stimulus,'path':str(p.relative_to(publisher.root)),'bytes':n,'sha256':h.hexdigest(),'shapes':shapes})
    for key in ('checkpoint','native_graph_source','preprocessing'):verify_file(session.root,record[key],b)
    for v in support['videos']:verify_file(session.root,v['file'],b)
    return {'schema':'hundred_models_feature_production_v1','panel':panel,'model':model,'stimulus_identity':support['identity_witness'],'ordered_ids':support['ordered_ids'],'named_modules':graph,'loaded_state_sha256':state_hash.hexdigest(),'loading_witness':record['loading_witness'],'emitted_feature_keys':keys,'emissions':emissions,'checkpoint':record['checkpoint'],'native_graph_source':record['native_graph_source'],'preprocessing':record['preprocessing'],'configuration':bare(encoded(config)),'pooling':'source_legacy_clip_pooling','native_feature_extent':total,'source_workspace':str(publisher.root)}

def rdm_layer_bindings(feature_keys, filenames):
    """Exact donor LayerRDM.save dot-to-underscore filename ABI, preserving keys."""
    need(type(feature_keys)is list and bool(feature_keys) and all(type(x)is str and x and not any(c in x for c in ('/', '\\', '\0')) for x in feature_keys),'ordinary original feature keys')
    need(len(feature_keys)==len(set(feature_keys)),'unique original feature keys')
    rows=[{'feature_key':key,'file_key':key.replace('.','_'),'filename':'RDM_'+key.replace('.','_')+'.npz'} for key in feature_keys]
    need(len({x['file_key'] for x in rows})==len(rows),'donor filename normalization collision')
    need(type(filenames)is list and len(filenames)==len(set(filenames)) and set(filenames)=={x['filename'] for x in rows},'every original layer has exactly one donor RDM file; no extras')
    return rows

def model_rdms(session,condition,feature_receipt,publisher):
    b=session.budget;np=session.np;record=session.inputs['models'][condition['model']]
    method=condition['method'];descriptor_key=session.inputs['train_reduction'] if condition['panel']=='train' else session.inputs['reductions'][method]
    reduction=strict(capture(session.root,descriptor_key,b))
    need(reduction['method']==method and reduction['standardize_on_dim'] is None,'exact admitted reduction method')
    if method=='pca':need(reduction['n_components']==100 and reduction['n_samples_estim']==102,'literal source PCA100/102; other historical override requires separately reviewed route')
    need(feature_receipt['panel']==condition['panel'] and feature_receipt['model']==condition['model'] and feature_receipt['stimulus_identity']==session.inputs['panels'][condition['panel']]['identity_witness'],'complete feature/brain common identities')
    root=Path(feature_receipt['source_workspace']);feature_dir=root/'features'
    for x in feature_receipt['emissions']:verify_file(root,{k:x[k] for k in ('path','bytes','sha256')},b)
    out=publisher.root/'rdms';b.charge('write_bytes',record['maximum_rdm_bytes']);b.check()
    Creator=session.modules['net2brain.rdm_creation'].RDMCreator
    kwargs={'feature_path':str(feature_dir),'save_path':str(out),'save_format':'npz','standardize_on_dim':None,'dim_reduction':None if method=='none' else method,'n_samples_estim':reduction['n_samples_estim'],'n_components':reduction['n_components']}
    if reduction['max_dim_allowed'] is not None:kwargs['max_dim_allowed']=reduction['max_dim_allowed']
    try:Creator(device=session.inputs['device'],verbose=True).create_rdms(**kwargs);b.check()
    except BaseException as error:error.native_output_prefix={'directory':str(out),'extent_after_native_failure_unknown':True};raise
    need(all(p.is_file() and not p.is_symlink() and p.stat().st_nlink==1 and p.name.startswith('RDM_') and p.suffix=='.npz' for p in out.iterdir()),'complete ordinary RDM emission directory')
    bindings=rdm_layer_bindings(feature_receipt['emitted_feature_keys'],[p.name for p in out.iterdir()])
    rows=[];n=len(feature_receipt['ordered_ids']);total=0
    for binding in bindings:
        key=binding['feature_key'];p=out/binding['filename'];total+=p.stat().st_size;need(total<=record['maximum_rdm_bytes'],'native RDM output reservation');b.charge('read_bytes',p.stat().st_size)
        with np.load(p,allow_pickle=False) as data:
            a=data['rdm'];actual=data['stimuli_name'].tolist();need(actual==[Path(x['path']).stem for x in feature_receipt['emissions']],'RDM actual order matches emitted feature order')
            need(a.shape==(n*(n-1)//2,), 'complete RDM pair geometry')
            desc=save_array(np,publisher,'layer_'+str(len(rows))+'.npy',a.astype('<f8'))
        rows.append({'layer':key,'rdm':desc,'shape':[n*(n-1)//2]})
    return {'schema':'hundred_models_rdm_production_v1','condition':condition,'feature_receipt':bare(encoded(feature_receipt)),'stimulus_identity':feature_receipt['stimulus_identity'],'layers':rows,'feature_to_file_bindings':bindings,'reduction':reduction,'output_root':str(publisher.root),'shape':[n,n]}

def rsa(session,rdms,brain_receipts,publisher):
    np=session.np;b=session.budget;stats=session.stats;n=rdms['shape'][0];tri=np.triu_indices(n,1);brains=[]
    for row in brain_receipts:
        need(row['stimulus_identity']==rdms['stimulus_identity'],'RSA neural/model identity join')
        a=load_array(np,Path(row['output_root']),row['rdm'],row['shape'],b,allow_undefined=True);brains.append(a[tri])
    values=[];layers=[]
    for row in rdms['layers']:
        model=load_array(np,Path(rdms['output_root']),row['rdm'],row['shape'],b,allow_undefined=True);layers.append(row['layer']);result=[]
        for brain_vector in brains:b.charge('work',n*(n-1)//2);result.append(float(stats.spearmanr(brain_vector,model).statistic));b.check()
        values.append(result)
    means=np.asarray(brains).mean(axis=0);ceilings=[]
    for index,x in enumerate(brains):
        others=np.asarray([v for j,v in enumerate(brains) if j!=index]).mean(axis=0)
        ceilings.append([float(stats.spearmanr(x,others).statistic),float(stats.spearmanr(x,means).statistic)]);b.check()
    desc=save_array(np,publisher,'rsa.npy',np.asarray(values,dtype='<f8'))
    return {'schema':'hundred_models_observed_rsa_v1','condition':rdms['condition'],'layers':layers,'subjects':[x['subject'] for x in brain_receipts],'roi':brain_receipts[0]['roi'],'values':desc,'shape':[len(layers),len(brains)],'noise_ceilings':finite_json(np.asarray(ceilings).mean(axis=0).tolist()),'output_root':str(publisher.root),'rdm_receipt':bare(encoded(rdms)),'undefined_values':int(np.isnan(values).sum())}

def nulls(session,rdms,brain_receipts,schedule,publisher):
    np=session.np;b=session.budget;stats=session.stats;n=rdms['shape'][0]
    need(n==102 and len(schedule)==1000 and all(sorted(p)==list(range(n)) for p in schedule),'exact full shared1000 permutations')
    tri=np.triu_indices(n,1);brains=[load_array(np,Path(v['output_root']),v['rdm'],v['shape'],b,allow_undefined=True)[tri] for v in brain_receipts]
    results=[]
    for layer in rdms['layers']:
        vector=load_array(np,Path(rdms['output_root']),layer['rdm'],layer['shape'],b,allow_undefined=True);full=np.zeros((n,n));full[tri]=vector;full[(tri[1],tri[0])]=vector;values=[]
        for perm in schedule:
            b.charge('work',10*n*(n-1)//2);permuted=full[perm,:][tri]
            values.append(float(np.mean([stats.spearmanr(brain,permuted).statistic for brain in brains])));b.check()
        results.append(values)
    desc=save_array(np,publisher,'null.npy',np.asarray(results,dtype='<f8'))
    return {'schema':'hundred_models_null_production_v1','model':rdms['condition']['model'],'roi':brain_receipts[0]['roi'],'layers':[x['layer'] for x in rdms['layers']],'shape':[len(results),1000],'values':desc,'schedule':bare(encoded(schedule)),'operator':'source_rows_only','summary':'mean_of_all10_subject_signed_spearman','output_root':str(publisher.root),'undefined_values':int(np.isnan(results).sum())}
