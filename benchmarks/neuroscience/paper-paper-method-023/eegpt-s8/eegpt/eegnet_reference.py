"""Concrete fixed ARL EEGNet control, using the exact original Keras model.

Only metadata helpers are import-time safe. Numerical imports and every model,
array, fit and query operation occur exclusively inside the selected scientific
worker. Build-time controls must poison those boundaries. The complete method
specification is EEGNET_METHOD.json; this is a prospective comparator, not an
assertion of original EEGPT-paper EEGNet results or numerical qualification.
"""
import hashlib
import importlib.util
import math
from fractions import Fraction
from pathlib import Path
from .protocol import HandleCustody,need,fields,digest,identity
from .scope import CLASSES

SOURCE_PIN={'path':'reference-source/arl-eegmodels/EEGModels.py','bytes':18033,'sha256':'604c7399a2a0e6c90cd8b4cbbc0f78550a3fb5c64b23f311d9c7db44dac94b02'}
VERSIONS={'tensorflow':'2.15.1','keras':'2.15.0','numpy':'1.26.4','scipy':'1.10.1'}
DATASET_ADAPTERS={'BCIC-2A':4,'BCIC-2B':2,'Sleep-EDFx':5,'KaggleERN':2,'PhysioP300':2,'TUAB':2,'TUEV':6}
MODEL={'dropoutRate':.5,'kernLength':64,'F1':8,'D':2,'F2':16,'norm_rate':.25,'dropoutType':'Dropout'}
TRAINING={'epochs':300,'batch_size':16,'optimizer':'Adam','learning_rate':.001,'beta_1':.9,'beta_2':.999,'epsilon':1e-7,'amsgrad':False,'loss':'sparse_categorical_crossentropy','shuffle':'request_seed_local_numpy_rng','selection':'full_validation_dataset_monitor_earliest_strict_best'}
UNIT_TO_MV={'V':1000.,'mV':1.,'uV':.001,'µV':.001,'μV':.001}


def admit_recipe(scope,recipe,seed):
    fields(recipe,('kind','qualification','fit'),'complete fixed EEGNet recipe')
    fields(recipe['fit'],('seed',),'EEGNet has one immutable source-owned training recipe')
    need(recipe['kind']=='arl_eegnet_v1' and scope['method']=='EEGNet' and scope['mode']=='I','fixed required prospective EEGNet control only')
    need(scope['dataset'] in DATASET_ADAPTERS and DATASET_ADAPTERS[scope['dataset']]==CLASSES[scope['dataset']],'all seven exact semantic adapters')
    need(type(seed) is int and 0<=seed<2**32 and recipe['fit']['seed']==seed,'original request-declared seed resolved before construction')
    digest(recipe['qualification'])
    return {'kind':'arl_eegnet_v1','source':SOURCE_PIN,'model':MODEL,'training':TRAINING,'runtime_versions':VERSIONS,'seed':seed,'qualification':recipe['qualification'],'dataset':scope['dataset'],'classes':DATASET_ADAPTERS[scope['dataset']]}


def adapter_for_document(document,dataset):
    """Full metadata-only admission; no array/header access or guessed axes."""
    need(dataset in DATASET_ADAPTERS and document['rows'],'complete known EEGNet dataset document')
    rows=document['rows'];first=rows[0];shape=first['signal']['shape'];channels=first['channels'];units=first['units'];rate=first['sampling_hz']
    need(type(shape) is list and len(shape)==2 and all(type(v) is int and v>0 for v in shape),'complete original C,T shape')
    need(type(channels) is list and len(channels)==shape[0] and len(set(channels))==len(channels),'full ordered original channel axis')
    need(type(rate) in (int,float) and math.isfinite(rate) and rate>0 and units in UNIT_TO_MV,'exact positive sampling rate and explicit physical signal units')
    ratio=Fraction(128,1)/Fraction(str(rate));need(ratio.numerator<=100000 and ratio.denominator<=100000,'finite exact rational rate adapter; no rounding')
    samples=(shape[1]*ratio.numerator+ratio.denominator-1)//ratio.denominator
    need(samples>=32,'complete epoch supports both fixed source pooling layers')
    for row in rows:
        need(row['signal']['shape']==shape and row['channels']==channels and row['units']==units and row['sampling_hz']==rate,'all complete original same-episode signal axes/rate/units; no padding, crop or dropped event')
    return {'dataset':dataset,'classes':DATASET_ADAPTERS[dataset],'channels':channels,'input_shape':shape,'source_hz':rate,'source_units':units,'scale_to_mV':UNIT_TO_MV[units],'up':ratio.numerator,'down':ratio.denominator,'output_hz':128,'output_shape':[shape[0],samples],'window':['kaiser',5.0],'padtype':'constant','full_original_epochs_retained':True,'learned_or_query_fitted_transform':False}


def _runtime():
    import importlib.metadata
    for package,version in VERSIONS.items():need(importlib.metadata.version(package)==version,'exact source-selected EEGNet numerical runtime: '+package)
    import tensorflow as tf
    return tf


def build_model(package,adapter,seed):
    tf=_runtime();path=Path(package)/SOURCE_PIN['path'];raw=path.read_bytes();need(len(raw)==SOURCE_PIN['bytes'] and hashlib.sha256(raw).hexdigest()==SOURCE_PIN['sha256'],'exact original ARL architecture source')
    # No data/example entrypoint is imported. All classes in this fixed module
    # are inert definitions until the selected EEGNet constructor below.
    tf.keras.utils.set_random_seed(seed)
    spec=importlib.util.spec_from_file_location('_original_arl_eegnet_'+SOURCE_PIN['sha256'],path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tf.device('/CPU:0'):
        model=module.EEGNet(nb_classes=adapter['classes'],Chans=adapter['output_shape'][0],Samples=adapter['output_shape'][1],**MODEL)
        optimizer=tf.keras.optimizers.Adam(learning_rate=TRAINING['learning_rate'],beta_1=TRAINING['beta_1'],beta_2=TRAINING['beta_2'],epsilon=TRAINING['epsilon'],amsgrad=TRAINING['amsgrad'])
        model.compile(optimizer=optimizer,loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False))
    return model


def adapt_epoch(value,adapter):
    import numpy as np
    from scipy.signal import resample_poly
    x=np.asarray(value,dtype=np.float64);need(list(x.shape)==adapter['input_shape'] and np.isfinite(x).all(),'complete original finite EEGNet signal epoch')
    x=x*adapter['scale_to_mV']
    if adapter['up']!=adapter['down']:x=resample_poly(x,adapter['up'],adapter['down'],axis=-1,window=tuple(adapter['window']),padtype=adapter['padtype'])
    need(list(x.shape)==adapter['output_shape'] and np.isfinite(x).all(),'entire exact rational output; no trim, crop, pad or dropped support')
    return np.asarray(x,dtype=np.float32)[...,None]


def batches(worker,document,adapter,order):
    import numpy as np
    need(len(order)==len(document['rows']) and set(order)==set(range(len(document['rows']))),'every original row once per complete epoch')
    for start in range(0,len(order),TRAINING['batch_size']):
        indices=order[start:start+TRAINING['batch_size']];values=[];labels=[];ids=[]
        for index in indices:
            row=document['rows'][index];x,y,rid,_=next(worker.epochs({**document,'rows':[row]}));values.append(adapt_epoch(x,adapter));labels.append(y);ids.append(rid)
        yield np.stack(values),labels,ids


def _full_predictions(worker,document,adapter,model):
    import numpy as np
    tf=_runtime();chunks=[];seen=[]
    for x,_labels,ids in batches(worker,document,adapter,list(range(len(document['rows'])))):
        with tf.device('/CPU:0'):p=model(x,training=False).numpy()
        need(p.shape==(len(ids),adapter['classes']) and np.isfinite(p).all() and (p>=0).all() and (p<=1).all() and np.allclose(p.sum(axis=1),1.,atol=1e-6,rtol=0),'actual full semantic softmax output')
        chunks.append(np.asarray(p,dtype=np.float64));seen.extend(ids)
    need(seen==[r['row_id'] for r in document['rows']],'all original query/validation rows in order')
    return np.concatenate(chunks,axis=0)


def architecture_census(model):
    params=[]
    for variable in model.weights:
        params.append({'name':variable.name,'shape':list(variable.shape),'elements':math.prod(variable.shape),'trainable':variable.trainable,'dtype':variable.dtype.name})
    total=sum(x['elements'] for x in params);trainable=sum(x['elements'] for x in params if x['trainable']);head=sum(math.prod(v.shape) for v in model.get_layer('dense').weights);encoder=total-head
    return {'parameters':params,'counts':{'all_modules':total,'encoder_only':encoder,'ema_target_only':0,'non_encoder_parameters':head,'encoder_and_target_included':encoder,'trainable':trainable},'module_types':{layer.name:type(layer).__name__ for layer in model.layers},'module_normalization':{layer.name:{'epsilon':layer.epsilon,'momentum':layer.momentum,'axis':layer.axis} for layer in model.layers if type(layer).__name__=='BatchNormalization'},'source_model':SOURCE_PIN,'framework':'tensorflow.keras','pretrained_parameters':False,'parameter_convention':'Keras model.weights including nontrainable BatchNorm moving statistics; encoder excludes source dense classifier'}


def fit(worker,recipe):
    scientific=admit_recipe(worker.request['scope'],recipe,worker.request['seed'])
    import numpy as np
    from .metrics import classify,BinaryRankStore,MONITOR
    from .reference_worker import source_pin
    from .family_products import training_products
    train=worker.rows('train');validation=worker.rows('validation');adapter=adapter_for_document(train,scientific['dataset']);need(adapter_for_document(validation,scientific['dataset'])==adapter,'same full original input adapter in train and validation')
    model=build_model(Path(__file__).resolve().parent.parent,adapter,scientific['seed']);tf=_runtime();rng=np.random.default_rng(scientific['seed']);records=[];best=None
    for epoch in range(TRAINING['epochs']):
        order=rng.permutation(len(train['rows'])).tolist();loss_numerator=0.;training_rows=0
        for x,labels,_ids in batches(worker,train,adapter,order):
            need(all(type(y) is int and 0<=y<adapter['classes'] for y in labels),'only original complete semantic training labels')
            with tf.device('/CPU:0'):loss=float(model.train_on_batch(x,np.asarray(labels,dtype=np.int64)))
            need(math.isfinite(loss),'finite actual original batch loss');loss_numerator+=loss*len(labels);training_rows+=len(labels)
        need(training_rows==len(train['rows']),'no omitted remainder or training event')
        probabilities=_full_predictions(worker,validation,adapter,model);rank=BinaryRankStore(worker.output/('eegnet-validation-%04d.sqlite'%epoch)) if adapter['classes']==2 else None
        with HandleCustody('original_validation_rank') as owned:
            if rank is not None:owned.own(rank,'rank_store')
            metrics = classify(((row['label'], p.tolist(), 1) for row, p in zip(validation['rows'], probabilities, strict=True)), adapter['classes'], rank_store=rank)
        path=worker.output/('eegnet-epoch-%04d.keras'%epoch);need(not path.exists(),'one original complete epoch model checkpoint');model.save(path);checkpoint=source_pin(path);worker.artifacts.append(checkpoint)
        monitor=metrics[MONITOR[scientific['dataset']]];record={'epoch':epoch,'training_rows':training_rows,'training_loss':loss_numerator/training_rows,'full_validation_rows':len(validation['rows']),'metrics':metrics,'monitor':monitor,'checkpoint':checkpoint,'source_recipe_identity':identity(scientific),'adapter_identity':identity(adapter)};records.append(record)
        if monitor is not None and math.isfinite(monitor) and (best is None or monitor>best['monitor']):best=record
    need(best is not None,'full validation monitor must select an actual finite original checkpoint; no query or last-state fallback')
    metadata={'kind':'arl_eegnet_v1','recipe':recipe,'source_scientific_recipe':scientific,'input_adapter':adapter,'actual_architecture':architecture_census(model),'selected_state':best['checkpoint']['path'],'selected_epoch':best['epoch'],'all_epoch_selection_records':records,'actual_optimizer_membership':[v.name for v in model.trainable_variables],'train_support':train['whole_support_identity'],'validation_support':validation['whole_support_identity'],'historical_parity':False,'new_prospective_control':True,'all_configuration_metrics':{'fixed_recipe_count':1,'epochs':records}}
    meta=worker.json('STATE.json',metadata);worker.state_response([meta['path'],*[r['checkpoint']['path'] for r in records]],train,recipe,'actual_seeded_random_initialization_no_pretrained_input');worker.response['selected_state']['trainability']='all actual original EEGNet trainable Keras weights; BatchNorm moving statistics recorded in complete saved state';training_products(worker,worker.request['output_contract']['products'],metadata)
    worker.response['diagnostics']={'complete_fixed_EEGNet_epochs':len(records),'selected_epoch':best['epoch'],'actual_model_source':SOURCE_PIN,'all_seven_adapters_implemented':True,'scientific_qualification':False}
    return metadata


def reconstruct(worker,state):
    need(state['kind']=='arl_eegnet_v1','actual fixed EEGNet selected state');scientific=admit_recipe(worker.request['scope'],state['recipe'],state['source_scientific_recipe']['seed']);need(scientific==state['source_scientific_recipe'],'same original source-owned fixed method and fit seed; query RNG is a separate declared stream')
    tf=_runtime();root=worker.inputs['fitted'];path=root/state['selected_state'];selected=next(r for r in state['all_epoch_selection_records'] if r['epoch']==state['selected_epoch'])
    from .reference_worker import source_pin
    need(source_pin(path)==selected['checkpoint'],'actual originally selected full model bytes')
    with tf.device('/CPU:0'):model=tf.keras.models.load_model(path,compile=False,safe_mode=True)
    need(tuple(model.input_shape[1:])==tuple(state['input_adapter']['output_shape'])+(1,) and model.output_shape[-1]==scientific['classes'],'actual selected fixed input/class axes')
    # Complete layer topology/weights and semantic constants remain bound by
    # the authenticated original saved model and host-issued state ancestry.
    return model


def predict(worker,state,document):
    need(worker.request['scope']['mode']=='I','EEGNet is the required I control only')
    adapter=adapter_for_document(document,worker.request['scope']['dataset']);need(adapter==state['input_adapter'],'same complete fixed EEGNet adapter at inference; no query fit')
    return _full_predictions(worker,document,adapter,reconstruct(worker,state))
