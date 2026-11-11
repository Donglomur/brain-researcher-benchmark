"""Prospective fixed negative/alternative-explanation controls, never a causal null."""
import copy,random
from collections import defaultdict,Counter
from .io import need,digest,finite

def common_eeg_support(features,identity):
    """Shared EEG support, never amplitude or outcome information.
    N086 released_summary stores its eight EEG support bits in base[38:46].
    Other representations additionally expose exact masks/segment geometry.
    """
    rep=identity["representation"]
    if identity["task"]=="NEURAL-086":
        base=features["base"];need(type(base)is list and len(base)==46,"N086_common_base46")
        common=base[38:46];need(all(type(x)is int and x in (0,1) for x in common),"N086_common_EEG_support")
        if rep=="released_summary":
            eeg=features["eeg"];need(type(eeg)is list and len(eeg)==8,"N086_summary_geometry")
            need([int(x is None) for x in eeg]==common,"N086_summary_mask_identity");mask=common
        else:
            need("representation_nuisance" in features,"representation_support_missing");mask=features["representation_nuisance"]
        return {"representation":rep,"common_EEG_support":common,"representation_support":mask}
    need("nuisance" in features,"N085_shuffle_nuisance")
    return {"representation":rep,"nuisance":features["nuisance"]}

def shuffle_view(view,train_raw,query_raw,seed=194085):
    out=copy.deepcopy(view);reports=[]
    for group,raw in (("train",train_raw),("query",query_raw)):
        buckets=defaultdict(list);rows=out[group];need(len(rows)==len(raw),"shuffle_partition_alignment")
        for i,(row,z) in enumerate(zip(rows,raw)):
            if "eeg" not in row["features"]:continue
            f=row["features"];e=f["eeg"];mask=common_eeg_support(f,view["identity"]);geometry=[len(s["values"]) for s in e] if e and isinstance(e[0],dict) else [len(e)]
            buckets[(z["sentence"]["person"],digest(mask),tuple(geometry))].append(i)
        rng=random.Random(seed);nonidentity=0;crosslabel=0
        for key,indices in sorted(buckets.items()):
            donors=list(indices);rng.shuffle(donors)
            originals={i:copy.deepcopy(rows[i]["features"]["eeg"]) for i in indices}
            for recipient,donor in zip(indices,donors):
                need(common_eeg_support(rows[recipient]["features"],view["identity"])==common_eeg_support(rows[donor]["features"],view["identity"]),"shuffle_donor_support")
                rows[recipient]["features"]["eeg"]=originals[donor];nonidentity+=recipient!=donor;crosslabel+=raw[recipient]["sentence"]["condition"]!=raw[donor]["sentence"]["condition"]
        reports.append({"partition":group,"seed":seed,"nonidentity_swaps":nonidentity,"crosslabel_swaps":crosslabel,"effective":nonidentity>0 and crosslabel>0,"ineffective_reason":None if nonidentity>0 and crosslabel>0 else ("no_nonidentity_swaps_within_identical_support" if nonidentity==0 else "no_crosslabel_swaps_within_identical_support"),"support_policy":"identical_common_EEG_masks_and_representation_geometry_v1","interpretation":"alignment sensitivity only; no exchangeable conditional/causal null","protected_not_in_candidate_view":True})
    return out,reports

def phase_surrogate(segment,common=False,seed=194085):
    import numpy as np
    from .waveforms import stretches
    out=copy.deepcopy(segment);a=np.asarray(segment["values"],float);mask=np.asarray(segment["valid"],bool)&np.isfinite(a);z=a.copy();rng=np.random.default_rng(seed)
    # Common-channel condition uses only common fully valid stretches. Different validity never bridges a gap.
    masks=[mask.all(1)] if common else [mask[:,c] for c in range(105)]
    for c,m in enumerate(masks):
        for lo,hi in stretches(m):
            if hi-lo<2:continue
            channels=range(105) if common else [c];phi=rng.uniform(0,2*np.pi,(hi-lo)//2+1);phi[0]=0
            if (hi-lo)%2==0:phi[-1]=0
            for channel in channels:z[lo:hi,channel]=np.fft.irfft(np.fft.rfft(a[lo:hi,channel])*np.exp(1j*phi),n=hi-lo)
    out["values"]=z.tolist();return out

def training_label_shuffle(rows,seed=194085):
    out=copy.deepcopy(rows);blocks=defaultdict(list)
    for i,r in enumerate(rows):blocks[r["person"],r["block"]].append(i)
    buckets=defaultdict(list)
    for k,indices in blocks.items():
        need(len({rows[i]["condition"] for i in indices})==1,"single_condition_block");buckets[k[0],len(indices)].append(k)
    rng=random.Random(seed);changes=0
    for _,keys in sorted(buckets.items()):
        donors=list(keys);rng.shuffle(donors)
        for k,d in zip(keys,donors):
            value=rows[blocks[d][0]]["condition"]
            for i in blocks[k]:changes+=rows[i]["condition"]!=value;out[i]["condition"]=value
    need(Counter(r["condition"] for r in rows)==Counter(r["condition"] for r in out),"label_shuffle_class_geometry")
    return out,{"changed_labels":changes,"effective":changes>0,"causal_randomization_p_value":None}

def chronology(rows):
    blocks=defaultdict(set)
    for r in rows:
        need("block" in r and "screen_instruction_present" in r and "session_elapsed" in r,"chronology_source_unavailable");blocks[r["person"],r["block"]].add(r["condition"])
    return {"block_condition_overlap":all(len(v)>1 for v in blocks.values()),"all_blocks_single_condition":all(len(v)==1 for v in blocks.values()),"causal_demand_identified":False,"candidate_ranked_input":False,"source_rows":len(rows)}

def ocular_residualization_fit(training):
    import numpy as np
    xs=[];ys=[]
    for record in training:
        need(record["aligned_500Hz"] and record["EOG_channels"]==9,"ocular_alignment_unavailable");e=np.asarray(record["eog"],float);a=np.asarray(record["scalp"],float);need(e.shape[1]==9 and a.shape[1]==105 and len(e)==len(a),"ocular_ABI")
        for k in range(10,len(e)-10):
            x=np.r_[1.,*[e[k+lag] for lag in (-10,-5,0,5,10)]]
            if np.isfinite(x).all() and np.isfinite(a[k]).all():xs.append(x);ys.append(a[k])
    need(xs,"ocular_training_support");coef,_,rank,_=np.linalg.lstsq(np.asarray(xs),np.asarray(ys),rcond=None);return {"coefficients":coef.tolist(),"rank":int(rank),"lags_ms":[-20,-10,0,10,20],"retrospective":True,"artifact_free_claim":False}
def ocular_residualize(record,state):
    import numpy as np
    e=np.asarray(record["eog"],float);a=np.asarray(record["scalp"],float);out=np.full_like(a,np.nan);coef=np.asarray(state["coefficients"])
    for k in range(10,len(e)-10):
        x=np.r_[1.,*[e[k+lag] for lag in (-10,-5,0,5,10)]]
        if np.isfinite(x).all() and np.isfinite(a[k]).all():out[k]=a[k]-x@coef
    return out.tolist()

def control_dispositions(source):
    # Source gaps remain explicit. Presence alone never establishes effectiveness or competence.
    capabilities=source.get("qualified_control_capabilities",{})
    required={"NC01":"missingness_duration","NC02":"alignment_shuffle","NC03":"waveform_clock","NC04":"chronology_events","NC05":"ocular_screen_alignment","NC06":"complete_block_labels","NC07":"repeat_matched_strata"}
    return {k:{"status":"planned" if capabilities.get(v) else "required_unscorable","capability":v,"scientifically_qualified":False,"effectiveness_evidence":None} for k,v in required.items()}
