"""J14 complete three-branch nonlinear-cell experiment.

Source-derived from the two 04_nonlinear_single_neuron notebooks at
jaxley_experiments 5e7a86282adb9d4603b5546ac5d8dad59aec7cc0 (MIT).
Training retains each literal seed/loss convention. Exports bind each fitted
model to its own generated rows instead of the later notebook plotting alias.
No scientific effects occur at import.
"""
from runtime.strict import require

PARAMETERS=('radius','length','axial_resistivity','HH_gNa','HH_gK','HH_gLeak')
LOWER=(0.1,1.,500.,0.05,0.01,0.0001)
UPPER=(5.,20.,5500.,1.1,0.3,0.001)
PROFILE='J14_LITERAL_TRAINING_KEYED_EXPORT_V1'

def validate(config):
    require(set(config)=={'profile','selection_id'},'J14 closed profile')
    require(config['profile']==PROFILE and type(config['selection_id'])is str and config['selection_id'],'J14 explicit source profile selection')
    return {'runs':20,'gd_steps_per_run':6400,'ga_generations':200,'ga_offspring':10,
            'train_rows':32,'test_rows':16,'grid_rows':6400,'parameters':72,
            'ga_evaluation_count':'actual returned full population history, not assumed fixed count'}

def _data(n):
    import numpy as np
    positive=[];negative=[]
    for blob,(x,y)in enumerate(zip(np.linspace(1.5,3.5,3),np.linspace(3.5,1.5,3))):
        xs=np.random.randn(n)*0.1+x;ys=np.random.randn(n)*0.1+y
        (positive if blob%2==0 else negative).append(np.stack([xs,ys]).T)
    a=np.concatenate(positive);b=np.concatenate(negative)
    a=a[np.random.permutation(np.arange(len(a)))][:n//2]
    b=b[np.random.permutation(np.arange(len(b)))][:n//2]
    images=np.concatenate([a,b]);labels=np.concatenate([np.ones(n//2),np.zeros(n//2)])
    order=np.random.permutation(np.arange(n));images=images[order];labels=labels[order]
    voltage=np.where(labels==0,-70.,35.)
    return images,labels,voltage

def _model():
    import numpy as np
    import jax
    import jax.numpy as jnp
    import jaxley as jx
    from jaxley.channels import HH
    require(jax.config.read('jax_enable_x64'),'J14 selected x64 installation')
    comp=jx.Compartment().initialize()
    branch=jx.Branch([comp for _ in range(4)]).initialize()
    cell=jx.Cell([branch for _ in range(3)],parents=jnp.asarray([-1,0,0])).initialize()
    cell.insert(HH())
    for key,value in {'v':-70.,'HH_m':0.074901,'HH_h':0.4889,'HH_n':0.3644787}.items():cell.set(key,value)
    cell.branch(0).loc(0.).record()
    for key,span,offset in zip(PARAMETERS,(4.5,10.,5000.,1.,.25,.0008),LOWER):
        cell.branch('all').comp('all').make_trainable(key,np.random.rand()*span+offset)
    transform=jx.ParamTransform(lowers=dict(zip(PARAMETERS,LOWER)),uppers=dict(zip(PARAMETERS,UPPER)))
    params=cell.get_parameters()
    require(len(params)==6 and all(list(p)==[k]and p[k].size==12 for p,k in zip(params,PARAMETERS)),'J14 actual 72-parameter identity')
    def simulate(physical,image):
        currents=jx.datapoint_to_step_currents(1.,.9,.05*image,.025,5.95)
        state=None
        for branch_id,current in zip((1,2),currents):
            state=cell.branch(branch_id).loc(1.).data_stimulate(current,data_stimuli=state)
        return jx.integrate(cell,params=physical,data_stimuli=state)
    batch=jax.jit(jax.vmap(simulate,in_axes=(None,0)))
    def prediction(physical,images):return batch(physical,images)[:,0,120]
    def mean_loss(z,images,labels):return jnp.mean(jnp.abs(prediction(transform.forward(z),images)-labels))
    def sum_loss(z,images,labels):return jnp.sum(jnp.abs(prediction(transform.forward(z),images)-labels))
    return cell,params,transform,batch,prediction,jax.jit(jax.value_and_grad(mean_loss)),jax.jit(jax.vmap(sum_loss,in_axes=(0,None,None)))

def _flat(params):
    import numpy as np
    return np.concatenate([np.asarray(p[k]).reshape(-1)for p,k in zip(params,PARAMETERS)]).tolist()

def _physical(vectors):
    import jax.numpy as jnp
    return [{key:jnp.asarray(vectors[:,i*12:(i+1)*12])}for i,key in enumerate(PARAMETERS)]

def run(ctx):
    require(ctx.group=='J14'and ctx.action=='nonlinear_full','J14 action')
    scope=validate(ctx.config)
    import numpy as np
    import jax.numpy as jnp
    import optax
    import tensorflow as tf
    import tensorflow_datasets as tfds
    from jaxley.optimize import TypeOptimizer
    import bluepyopt as bpopt
    from bluepyopt.parameters import Parameter
    from importlib.metadata import version
    require(version('bluepyopt')=='1.14.11','J14 qualified source BluePyOpt version required')
    traces=[];surfaces=[];predictions=[];histories=[]
    gx,gy=np.meshgrid(np.linspace(0.,5.,80),np.linspace(0.,5.,80));grid=np.stack([gx,gy]).reshape(2,6400).T
    for method in ('GD','GA'):
        for seed in range(10):
            ctx.checkpoint();tf.random.set_seed(42+seed);np.random.seed(seed+(1 if method=='GD'else 0))
            cell,initial,transform,simulate,predict,loss_grad,loss_many=_model()
            train,y_train,v_train=_data(32);test,y_test,v_test=_data(16)
            initial_vector=_flat(initial);z=transform.inverse(initial)
            history={'method':method,'seed':seed,'numpy_seed':seed+(1 if method=='GD'else 0),'tensorflow_seed':42+seed,
                     'training_rows':train.tolist(),'test_rows':test.tolist(),'training_labels':y_train.tolist(),'test_labels':y_test.tolist(),
                     'initial_parameters':initial_vector,'parameter_order':[{'name':k,'compartment':i}for k in PARAMETERS for i in range(12)]}
            if method=='GD':
                optimizer=TypeOptimizer(lambda lr:optax.adam(lr),dict.fromkeys(PARAMETERS,.01),z);state=optimizer.init(z)
                # IDs travel through the same original TensorFlow shuffle. They
                # do not change its permutation or numeric training operands.
                dataset=tf.data.Dataset.from_tensor_slices((train,v_train,np.arange(32)))
                dataset=dataset.shuffle(dataset.cardinality()).batch(1)
                steps=[];epochs=[];parameters=[]
                for epoch in range(200):
                    total=0.;row_order=[]
                    for batch in dataset:
                        ctx.checkpoint();images,labels,ids=tfds.as_numpy(batch)
                        loss,gradient=loss_grad(z,images,labels);loss_value=float(loss)
                        require(np.isfinite(loss_value),'J14 nonfinite GD loss')
                        updates,state=optimizer.update(gradient,state);z=optax.apply_updates(z,updates)
                        steps.append(loss_value);total+=loss_value;row_order.extend(ids.tolist())
                    require(sorted(row_order)==list(range(32)),'J14 full epoch support')
                    epochs.append({'epoch':epoch,'sum_of_batch_mean_losses':total,'row_order':row_order})
                    parameters.append(_flat(transform.forward(z)))
                selected=transform.forward(z)
                history.update(loss_reduction='mean_absolute_error_per_batch',steps=steps,epochs=epochs,epoch_parameters=parameters,selected_rule='actual final epoch parameters')
            else:
                evaluated=[];batches=[]
                class Evaluator(bpopt.evaluators.Evaluator):
                    def __init__(self):
                        params=[Parameter(f'{k}_{i}',bounds=[lo,hi])for k,lo,hi in zip(PARAMETERS,LOWER,UPPER)for i in range(12)]
                        super().__init__(objectives=['loss'],params=params)
                    def init_simulator_and_evaluate_with_lists(self,param_list):
                        ctx.checkpoint();vectors=np.asarray(param_list,dtype=np.float64)
                        require(vectors.ndim==2 and vectors.shape[1]==72,'J14 GA complete genome')
                        values=np.asarray(loss_many(transform.inverse(_physical(vectors)),train,v_train))
                        require(np.isfinite(values).all(),'J14 nonfinite GA loss')
                        batches.append({'start':len(evaluated),'count':len(vectors)})
                        for vector,loss in zip(vectors,values):evaluated.append({'parameters':vector.tolist(),'sum_absolute_error':float(loss)})
                        return values[:,None].tolist()
                def map_batch(evaluate,vectors):return evaluate(list(vectors))
                opt=bpopt.deapext.optimisations.IBEADEAPOptimisation(Evaluator(),offspring_size=10,map_function=map_batch,seed=seed,eta=10,mutpb=1.,cxpb=1.)
                population,hof,log,genealogy=opt.run(max_ngen=200)
                require(evaluated and len(hof)>0,'J14 actual GA populations unavailable')
                # The source saves all GA losses, not a fitted surface. Export
                # a separately labelled actual hall-of-fame member plus its
                # complete lineage; never call it the notebook's final fit.
                vector=np.asarray(hof[0],dtype=np.float64)
                selected=[{k:jnp.asarray(vector[i*12:(i+1)*12])}for i,k in enumerate(PARAMETERS)]
                history.update(loss_reduction='sum_absolute_error_over_32_training_rows',evaluations=evaluated,batches=batches,
                               final_population=[list(map(float,p))for p in population],hall_of_fame=[list(map(float,p))for p in hof],
                               genealogy={str(k):list(v)for k,v in genealogy.genealogy_tree.items()},
                               selected_rule='actual hall_of_fame[0], new complete export; source saves loss history only')
            both=np.concatenate([train,test]);volt=np.asarray(simulate(selected,both));surface=np.asarray(predict(selected,grid)).reshape(80,80)
            require(volt.shape[:2]==(48,1)and np.isfinite(volt).all()and np.isfinite(surface).all(),'J14 complete finite voltage/grid')
            traces.append(volt);surfaces.append(surface)
            predictions.append({'method':method,'seed':seed,'row_ids':[f'{method}:{seed}:{split}:{i}'for split,n in (('train',32),('test',16))for i in range(n)],
                                'voltage_predictions_at_3ms':volt[:,0,120].tolist(),'labels':np.concatenate([y_train,y_test]).tolist(),
                                'voltage_targets':np.concatenate([v_train,v_test]).tolist(),'classification_threshold':'UNSELECTED; no invented accuracy threshold'})
            history['selected_parameters']=_flat(selected);histories.append(history)
    ctx.emit_numeric('all_input_voltage',np.stack(traces));ctx.emit_numeric('decision_surface',np.stack(surfaces))
    ctx.emit_json('class_predictions',{'runs':predictions,'coordinate_semantics':'Each fit retains its own original generated rows; no cross-run plotting alias'})
    ctx.emit_json('GD_GA_trajectory',{'scope':scope,'runs':histories,'matched_seed_or_objective_claim':False,
                                   'source_plot_alias_retained_as_issue':True,'native_or_scientific_qualification':False})
