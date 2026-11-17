"""Full retinal family J09/J15–J19. The main driver alone calls ctx.finish().

The module computes results; it does not issue native, input or scientific
qualification. No native library is imported by importing this module.
"""
from .retina_inputs import (validate_config, validate_manifest, preprocess,
                            field_dataset, require, FIELDS, BASELINE_FIELDS,
                            SIZES, SEEDS, FAMILIES)
from . import retina_model as model


def _serialize_tree(value):
    """Actual parameter/state values with full tree structure, never a sentinel."""
    if isinstance(value, dict):
        return {str(k):_serialize_tree(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):
        return [_serialize_tree(v) for v in value]
    if hasattr(value,"tolist"):
        return value.tolist()
    return value


def _emit(ctx, name, value, *, numeric=False):
    ctx.checkpoint()
    if numeric:
        ctx.emit_numeric(name,value)
    else:
        ctx.emit_json(name,_serialize_tree(value))


def j09_extent(ctx):
    shapes={name:ctx.products[name]["shape"] for name in ("boundary_state_before","boundary_state_after","gradient_cuts","full_voltage")}
    for name,shape in shapes.items():
        require(type(shape)is list and len(shape)==3 and all(type(x)is int and x>0 for x in shape),"closed J09 numeric axes")
    state=shapes["boundary_state_before"]
    require(state[:2]==[15360,3] and shapes["boundary_state_after"]==state and shapes["gradient_cuts"]==state,"full J09 boundary/state coordinates")
    voltage=shapes["full_voltage"]
    require(voltage[:2]==[15360,147] and voltage[2]>=8000,"full J09 voltage coordinates")
    # Native padded-step/timebase must be qualified; never guess T=8000 from dt.
    extent=15360*(147*voltage[2]+9*state[2])*8
    require(2*extent<=ctx.limits["array_memory_bytes"],"whole J09 retained arrays plus stacking capacity")
    return state[2],voltage[2]


def run(ctx):
    # This owner exists before validation, imports, reads and native acquisition.
    # Main JobContext/driver retains the original failure and owns cleanup.
    ctx.checkpoint()
    cfg=validate_config(ctx.group,ctx.config)
    require(ctx.action == "run", "retina action")
    # A necessary allocation bound, not a substitute for outer native/host
    # peak-memory qualification. Refuse the full graph, never select a subset.
    if ctx.group=="J09":
        j09_extent(ctx)
    ctx.record("retina_profile",dict(group=ctx.group,profile=cfg["profile"],choices=cfg["choices"],scope="one biological cell; sites/fields/seeds nested; no independent-animal claim"))
    manifest=validate_manifest(ctx.read_json(cfg["manifest"]))
    cell=model.build_cell(ctx,manifest["morphology"],cfg["choices"]["soma_radius"],cfg["choices"]["jax_platform"])
    data=preprocess(ctx,manifest,cell)
    if ctx.group=="J15":
        return anatomy(ctx,cell,data,cfg)
    if ctx.group=="J19":
        return baseline_matrix(ctx,manifest,data,cfg)
    trained=model.train(ctx,cell,data,data["connections"],cfg)
    if ctx.group=="J09":
        return truncation(ctx,trained,data)
    if ctx.group=="J16":
        return prediction_products(ctx,trained,data)
    if ctx.group=="J17":
        return compartmentalization(ctx,trained,data)
    if ctx.group=="J18":
        return receptive_fields(ctx,trained,data,cfg)
    raise AssertionError("closed dispatch")


def anatomy(ctx,cell,data,cfg):
    opt,states,static=model.initialize(ctx,cell,data["sites"],data["connections"],cfg)
    physical=model.physical(opt,static)
    count=sum(int(v.size) for group in physical for item in group for v in item.values())
    _emit(ctx,"anatomy_parameter_map",dict(cell_id="20161028_1",raw_roi_mapping=data["roi_mapping"],sites=data["sites"],connections=data["connections"],branch_xyzr=cell.xyzr,physical_parameters=physical,actual_parameter_count=count,unresolved_paper_counts=[607,556],basal_indices=static["basal_inds"],somatic_indices=static["somatic_inds"]))
    _emit(ctx,"mechanism_state_map",dict(channels=["Na","K","Leak","KA","CaNernstReversal","CaPump","Ca","KCa"],warmup_ms=5.0,initial_states=states,conductance_unit="source library unit; paper discrepancy requires qualification"))
    _emit(ctx,"observation_transform",dict(kernel=static["kernel"],dt_ms=.025,output_scale=static["output_scale"],output_offset=-1.3,operation="mean(reverse(kernel)*Cai)",op_kernel=data["bc"]["kernel"],bc_nonlinearity=dict(intensity=data["bc"]["intensity"],response=data["bc"]["response"]),centers=data["centers"],delay_steps=data["delay"],delay_scores=data["delay_scores"],loss="sum(mask*abs(pred-label)); mean over batch"))


def truncation(ctx,trained,data):
    """Every original input row has a full trajectory; no chosen-example filter."""
    import numpy as np
    before=[];after=[];cuts=[];voltage=[]
    static=trained["static"];cell=static["cell"]
    from jax.flatten_util import ravel_pytree
    flat,_=ravel_pytree(trained["initial"])
    state_size,time_size=j09_extent(ctx)
    require(int(flat.size)==state_size,"native state layout differs from admitted J09 product")
    # Record voltage as well as the calcium used by the fitted observation model.
    for site in data["sites"]:
        cell.branch(site["branch"]).loc(site["comp"]).record("v",verbose=False)
    for ordinal,current in enumerate(data["currents"]):
        ctx.checkpoint()
        a,b,c,v=model.boundary_trajectory(ctx,trained["selected"],trained["initial"],static,current)
        require(v[len(data["sites"]):].shape==(147,time_size),"native padded split timebase differs from J09 product")
        before.append(a);after.append(b);cuts.append(c);voltage.append(v[len(data["sites"]):])
        ctx.record("retina_truncation_coordinate",dict(row=ordinal,field=ordinal//1024+1,image=ordinal%1024))
    _emit(ctx,"boundary_state_before",np.stack(before),numeric=True)
    _emit(ctx,"boundary_state_after",np.stack(after),numeric=True)
    _emit(ctx,"gradient_cuts",np.stack(cuts),numeric=True)
    _emit(ctx,"full_voltage",np.stack(voltage),numeric=True)


def prediction_products(ctx,trained,data):
    predictions=model.predict_all(ctx,trained["selected"],trained["initial"],trained["static"],data["currents"])
    metrics={}
    for name,indices in trained["splits"].items():
        metrics[name]=model.metrics(predictions[indices],data["labels"][indices],data["mask"][indices])
    metrics["all_exposed"]=model.metrics(predictions,data["labels"],data["mask"])
    _emit(ctx,"full_site_predictions",predictions,numeric=True)
    _emit(ctx,"observation_mask",data["mask"],numeric=True)
    _emit(ctx,"site_metrics",metrics)
    _emit(ctx,"split_lineage",dict(indices=trained["splits"],field_order=list(FIELDS),images_per_field=1024,sites=data["sites"],checkpoint_epoch=ctx.config["choices"]["evaluation_checkpoint_epoch"],physical_parameters=model.physical(trained["selected"],trained["static"]),learning=trained["learning"],evaluations=trained["evaluations"],selection="explicit produced epoch; not historical cached params_16 equivalence"))


def compartmentalization(ctx,trained,data):
    ctx.checkpoint()
    import numpy as np
    static=trained["static"];cell=static["cell"]
    require(len(cell.xyzr)==155 and len(data["connections"])==287, "original compartmentalization anatomy/connection coordinates")
    cell.delete_recordings();cell.delete_stimuli()
    for state in ("Cai","v"):
        for branch in range(155):cell.branch(branch).comp(1).record(state,verbose=False)
    outputs=[];stimuli=[]
    for index in (15,105):
        ctx.checkpoint()
        current=np.zeros(287);current[index]=.015
        outputs.append(np.asarray(model.simulate(*model.physical(trained["selected"],static),current,trained["initial"],static)))
        stimuli.append(current)
    values=np.stack(outputs)
    # Exact source selected stimulated branches and remote branches80/78.
    pairs=[(data["connections"][15]["branch"],80),(data["connections"][105]["branch"],78)]
    _emit(ctx,"all_branch_calcium",values[:,:155,:],numeric=True)
    _emit(ctx,"site_voltage",np.stack([values[i,155+np.asarray(pair),:] for i,pair in enumerate(pairs)]),numeric=True)
    _emit(ctx,"site_calcium",np.stack([values[i,np.asarray(pair),:] for i,pair in enumerate(pairs)]),numeric=True)
    _emit(ctx,"stimulus",dict(connection_indices=[15,105],currents=stimuli,connections=[data["connections"][i] for i in (15,105)],recording_pairs=pairs,amplitude_before_learned_weight=.015,duration_ms=200.,block_ms=50.,weighted_by_trained_synapse=True))


def _asd(ctx,images,response,site,profile):
    """Public RFEST fit caller; actual progress hook retains every real update.

    This is an explicitly prospective fa18170 dependency, not a reconstructed
    historical environment. No optimizer or evidence formula is substituted.
    """
    ctx.checkpoint()
    import numpy as np
    from rfest import ASD
    records=[]
    class RetainedASD(ASD):
        @staticmethod
        def print_progress_header(params):
            return None
        @staticmethod
        def print_progress(i,params,cost):
            ctx.checkpoint()
            records.append(dict(iteration=int(i),parameters=np.asarray(params).tolist(),negative_log_evidence=float(cost)))
    noisy=response + np.random.RandomState(site).randn(*response.shape)*.1
    estimator=RetainedASD(images.T.reshape(len(response),300),noisy.T,dims=(20,15))
    tolerance=20 if profile=="fa18170-full20-tolerance20" else 10
    estimator.fit(p0=[1.2]*5,num_iters=20,verbose=1,step_size=.02,tolerance=tolerance)
    require(0<len(records)<=20 and [r["iteration"] for r in records]==list(range(len(records))), "missing actual ASD progress")
    if tolerance==20:require(len(records)==20,"full20 profile did not execute20updates")
    raw=np.asarray(estimator.w_opt).reshape(20,15)
    shifted=raw-np.min(raw);span=np.max(shifted)
    require(np.isfinite(span) and span>0,"undefined RF normalization")
    return raw,shifted/span,dict(profile=profile,actual_iterations=len(records),updates=records,selected_parameters=np.asarray(estimator.optimized_params).tolist(),dependency_revision="fa18170fabed81e8bdc617d312b52d60e31a82cd",historical_equivalence=False)


def receptive_fields(ctx,trained,data,cfg):
    ctx.checkpoint()
    import numpy as np
    from skimage.transform import resize
    from skimage.measure import find_contours
    predictions=model.predict_all(ctx,trained["selected"],trained["initial"],trained["static"],data["currents"])
    experimental=[];modeled=[];normalized=[];contours=[];histories=[]
    level={"paper-0.6":.6,"author-results-0.5":.5,"author-assembly-0.4":.4}[cfg["choices"]["contour_profile"]]
    for site in range(147):
        ctx.checkpoint();keep=data["mask"][:,site].astype(bool);images=data["images"][:,:,keep]
        er,en,eh=_asd(ctx,images,data["labels"][keep,site],site,cfg["choices"]["rfest_profile"])
        mr,mn,mh=_asd(ctx,images,predictions[keep,site],site,cfg["choices"]["rfest_profile"])
        experimental.append(er);modeled.append(mr);normalized.append([en,mn]);histories.append(dict(site=site,experimental=eh,model=mh))
        field=data["sites"][site]["field"];ox,oy=data["centers"][field]
        # Full source assembly cubic20× upsample/border convention is distinct
        # from raw normalized0.6 paper contours; never silently mix the two.
        family=[]
        for value in (en,mn):
            assembly=cfg["choices"]["contour_profile"]=="author-assembly-0.4"
            value=resize(value,(400,300),order=3,mode="constant") if assembly else value
            if assembly:
                value[:5,:]=1;value[-5:,:]=1;value[:,:5]=1;value[:,-5:]=1
            paths=find_contours(value,level)
            coords=[np.column_stack((np.interp(p[:,1],np.arange(value.shape[1]),np.linspace(-210,210,value.shape[1])+ox),np.interp(p[:,0],np.arange(value.shape[0]),-np.linspace(-285,285,value.shape[0])+oy))).tolist() for p in paths]
            family.append(coords)
        contours.append(dict(site=site,field=field,level=level,experimental=family[0],model=family[1],coordinate_unit="micrometre",extraction="skimage marching-squares; matplotlib path parity unqualified"))
    _emit(ctx,"experimental_RF",np.stack(experimental),numeric=True)
    _emit(ctx,"model_RF",np.stack(modeled),numeric=True)
    _emit(ctx,"normalized_RF",np.stack(normalized),numeric=True)
    _emit(ctx,"contours",contours)
    _emit(ctx,"ASD_evidence_trajectory",histories)


def torch_baseline(ctx,dataset,family,seed,dtype_profile):
    ctx.checkpoint()
    import numpy as np
    import torch
    from torch import nn
    from copy import deepcopy
    require(family in ("linear","MLP"),"baseline family")
    torch.manual_seed(seed)
    outputs=len(dataset["sites"])
    net=nn.Linear(300,outputs) if family=="linear" else nn.Sequential(nn.Linear(300,100),nn.ReLU(),nn.Linear(100,100),nn.ReLU(),nn.Linear(100,50),nn.ReLU(),nn.Linear(50,outputs))
    # Author-inferred dtypes may fail; this is preserved, not silently repaired.
    # The separately named double adapter is prospective, not historical parity.
    data=torch.as_tensor(dataset["images"].reshape(300,-1).T)
    labels=torch.as_tensor(dataset["labels"]);masks=torch.as_tensor(dataset["mask"])
    if dtype_profile=="explicit-float64-adapter":
        data=data.double();labels=labels.double();masks=masks.double();net=net.double()
    else:require(dtype_profile=="author-inferred-dtypes","baseline dtype profile")
    torch.manual_seed(seed+1);permutation=torch.randperm(len(data));n=len(data)
    val_frac=.2*(1-512/n);nt=int(n*(1-val_frac-512/n))
    splits=dict(test=permutation[:512],train=permutation[512:512+nt],val=permutation[512+nt:])
    optimizer=torch.optim.Adam(list(net.parameters()),lr=.001)
    best=-20.;best_state=None;curve=[];evaluation=[]
    def evaluate():
        result={};preds={}
        with torch.no_grad():
            for name,indices in splits.items():
                p=net(data[indices]).detach().numpy();preds[name]=p
                result[name]=model.metrics(p,labels[indices].numpy(),masks[indices].numpy())
        return result,preds
    for epoch in range(500):
        ctx.checkpoint();optimizer.zero_grad();prediction=net(data[splits["train"]])
        loss=torch.mean((prediction-labels[splits["train"]])**2*masks[splits["train"]]);loss.backward();optimizer.step()
        curve.append(dict(epoch=epoch,loss=float(loss.detach())))
        if epoch%10==0:
            result,preds=evaluate();score=result["val"]["mean_pearson"]
            evaluation.append(dict(epoch=epoch,metrics=result))
            if score is not None and score>best:
                best=score;best_state=dict(metrics=result,predictions=preds,epoch=epoch,parameters=deepcopy(net.state_dict()))
    require(best_state is not None,"undefined baseline validation support")
    return dict(best=best_state,splits={k:v.numpy() for k,v in splits.items()},learning=curve,evaluations=evaluation)


def baseline_matrix(ctx,manifest,data,cfg):
    """Complete7×5×3×5, no metric-driven deletion or example-only shortcut."""
    ctx.checkpoint()
    import copy
    import numpy as np
    from scipy import stats
    predictions={name:[] for name in ("train","val","test")};correlations=[];learning=[]
    for field in BASELINE_FIELDS:
        for size,batch in zip(SIZES,(4,4,8,16,32)):
            dataset=field_dataset(data,field,size)
            for family in FAMILIES:
                for seed in SEEDS:
                    ctx.checkpoint();coordinate=dict(field=field,size=size,family=family,seed=seed)
                    ctx.record("retina_baseline_enter",coordinate)
                    if family=="hybrid":
                        local=copy.deepcopy(cfg);local["training"].update(batch_size=batch,test_num=512,seed_ruler=seed)
                        # Source training profile uses complete epochs. The
                        # <=100-paper-step recipe is not silently substituted.
                        cell=model.build_cell(ctx,manifest["morphology"],cfg["choices"]["soma_radius"],cfg["choices"]["jax_platform"])
                        result=model.train(ctx,cell,dataset,data["connections"],local)
                    else:result=torch_baseline(ctx,dataset,family,seed,cfg["choices"]["baseline_dtype"])
                    best=result["best"]
                    for split in predictions:
                        indices=result["splits"][split]
                        predictions[split].append(dict(**coordinate,row_ids=dataset["row_ids"][indices].tolist(),site_indices=dataset["site_indices"],predictions=best["predictions"][split].tolist(),selection_epoch=best["epoch"]))
                    correlations.append(dict(**coordinate,metrics=best["metrics"]))
                    learning.append(dict(**coordinate,steps=result["learning"],evaluations=result["evaluations"]))
    require(len(correlations)==7*5*3*5,"complete baseline support")
    summaries=[]
    for size in SIZES:
        by_family={}
        for family in FAMILIES:
            fields={}
            for split in ("train","val","test"):
                values=[]
                for field in BASELINE_FIELDS:
                    selected=[r["metrics"][split]["mean_pearson"] for r in correlations if r["size"]==size and r["family"]==family and r["field"]==field]
                    require(len(selected)==5,"all five seeds per field")
                    values.append(float(np.mean(selected)) if all(v is not None for v in selected) else None)
                fields[split]=values
            by_family[family]=fields
        for split in ("train","val","test"):
            for family in FAMILIES:
                vector=by_family[family][split];defined=all(v is not None for v in vector)
                summaries.append(dict(size=size,split=split,family=family,field_order=list(BASELINE_FIELDS),seed_mean_field_vector=vector,mean=float(np.mean(vector)) if defined else None,sem=float(stats.sem(vector)) if defined else None,unit="seven fields nested within one cell; seeds averaged first"))
        for reference in ("linear","MLP"):
            a=by_family["hybrid"]["test"];b=by_family[reference]["test"];defined=all(v is not None for v in a+b)
            summaries.append(dict(size=size,comparison="hybrid-vs-"+reference,source_style_independent_t_p=float(stats.ttest_ind(a,b,alternative="greater").pvalue) if defined else None,paired_field_t_p=float(stats.ttest_rel(a,b,alternative="greater").pvalue) if defined else None,qualification="prospective complete paired-field reconstruction; original assembly mixes run/field aggregation and mutates first field; no confirmatory biological inference"))
    for split,product in (("train","train_predictions"),("val","validation_predictions"),("test","test_predictions")):_emit(ctx,product,predictions[split])
    _emit(ctx,"correlations",correlations)
    _emit(ctx,"SEM_tests",summaries)
    _emit(ctx,"learning_curve",learning)
