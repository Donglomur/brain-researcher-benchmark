"""Closed fixed control-feature projections; query labels never enter these transforms."""
import copy,random
from .io import need

def project(view,raw_train,raw_query,identity):
    method=identity["method"]
    if method in ("candidate","R_LINEAR_NESTED_V1","R_NONLINEAR_V1","R_TEMPORAL_CONV_V1"):return view
    out=copy.deepcopy(view);residual_state=None
    if method=='R_EOG_RESIDUAL':
        from .controls import ocular_residualization_fit,ocular_residualize
        def segments(z):
            r=z['sentence'];need('qualified_ocular_aligned_segments' in r,'ocular_residual_source_unavailable');allsegments=r['qualified_ocular_aligned_segments'];key='sentence' if identity['task']=='NEURAL-085' else str(z['word_index'])+':'+identity['context'];need(key in allsegments,'ocular_residual_source_unavailable');return allsegments[key]
        train_segments=[s for z in raw_train for s in segments(z)];residual_state=ocular_residualization_fit(train_segments)
        out.setdefault('protected_control_observations',{})['NC05']={'training_only':True,'training_rows':len(raw_train),'state':residual_state,'artifact_free_claim':False}
    for kind,raw in (("train",raw_train),("query",raw_query)):
        for row,z in zip(out[kind],raw):
            f=row["features"];r=z["sentence"]
            if method=="R_MASK_ONLY":
                base=f.get("base",[]);n=f.get("nuisance",{});row["features"]={"mask_probe":{"base_missing":base[19:] if base else [],"nuisance":n,"representation":f.get("representation_nuisance",[])}}
            elif method=="R_DURATION_COUNT":
                need("duration_seconds" in r and "valid_gaze_fractions" in r,"duration_control_source_unavailable");w=z.get("word") or {};row["features"]={"duration_count":[r["duration_seconds"],len(r["words"]),r["omission"],w.get("nFixations"),z.get("window",{}).get("duration_ms")]}
            elif method in ("R_PHASE_INDEPENDENT","R_PHASE_COMMON"):
                from .controls import phase_surrogate
                if "eeg" in f:row["features"]["eeg"]=[phase_surrogate(s,common=method=="R_PHASE_COMMON",seed=194085+k) for k,s in enumerate(f["eeg"])]
            elif method=="R_OCULAR":
                need("qualified_ocular_screen_features" in r,"ocular_control_source_unavailable");row["features"]["ocular_screen"]=copy.deepcopy(r["qualified_ocular_screen_features"])
            elif method=="R_EOG_RESIDUAL":
                import numpy as np
                transformed=[]
                for segment in segments(z):
                    residual=ocular_residualize(segment,residual_state);a=np.asarray(residual,float);mask=np.isfinite(a);transformed.append({'values':np.where(mask,a,0.).tolist(),'valid':mask.tolist(),'channel_ids':list(segment['channel_ids']),'sample_rate_hz':500,'source_stage':identity['representation']})
                support={'segments':[{'samples':len(s['values']),'valid':s['valid'],'duration_seconds':len(s['values'])/500} for s in transformed]}
                row['features']['residual_support']=support
                if 'eeg' in f:row['features']['eeg']=transformed
            elif method!="R_LABEL_SHUFFLE":raise ValueError("unregistered fixed control method")
    if method=="R_LABEL_SHUFFLE":
        from collections import defaultdict
        buckets=defaultdict(list);blocks=defaultdict(list)
        for k,z in enumerate(raw_train):
            r=z["sentence"];need("block" in r,"block_control_source_unavailable");blocks[r["person"],r["block"]].append(k)
        for b,indices in blocks.items():buckets[b[0],len(indices)].append(b)
        rng=random.Random(194085);changed=0
        for _,names in sorted(buckets.items()):
            donors=list(names);rng.shuffle(donors)
            labels={b:out["train"][indices[0]]["label"] for b,indices in blocks.items()}
            for b,d in zip(names,donors):
                for k in blocks[b]:changed+=out["train"][k]["label"]!=labels[d];out["train"][k]["label"]=labels[d]
    if method=="R_LABEL_SHUFFLE":out.setdefault("protected_control_observations",{})["NC06"]={"changed_labels":changed,"effective":changed>0,"p_value":None}
    return out
