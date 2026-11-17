"""Prospective scientific feature transforms. Never run during BUILD ONLY controls."""
import math,copy
from collections import Counter
from .io import need,finite,Refusal
from .constants import *
from .panel import group_text,text_id

def scalp_means(values):
    need(len(values)==840,"scalp_band_vector")
    return [None if any(x is None for x in values[k*105:(k+1)*105]) else sum(values[k*105:(k+1)*105])/105 for k in range(8)]
def source_eeg(z,context,representation):
    r=z["sentence"]
    if representation in ("released_summary","band_spatial"):
        v=r["eeg_summary"] if context=="sentence" else z["window"]["band_values"]
        return list(v) if context=="sentence" or representation=="band_spatial" else scalp_means(v)
    intervals=r["waveform_segments"][representation] if context=="sentence" else z["window"]["segments"][representation]
    need(intervals is not None,"waveform_source_unavailable")
    for s in intervals:
        need(s["source_stage"]==representation and s["sample_rate_hz"]==500 and s["channel_ids"]==r["scalp_channel_ids"],"waveform_segment_ABI")
        need(s["source_start"]<s["source_stop"]<=s["permitted_stop"] and s["source_pin"] and s["no_boundary_bridge"] is True,"source_waveform_interval")
    return [{"values":copy.deepcopy(s["values"]),"valid":copy.deepcopy(s["valid"]),"channel_ids":list(s["channel_ids"]),"sample_rate_hz":500,"source_stage":representation} for s in intervals]
def lexical(train):
    texts={text_id(z["sentence"]["text"]):z["sentence"]["text"] for z in train};c=Counter(t for s in texts.values() for t in group_text(s).split());return c,sum(c.values()),len(c)+1

def base46(z,context,lex):
    r=z["sentence"];w=z["word"];pos=z["word_index"];words=[x["word"] for x in r["words"]];c,total,vocab=lex;ts=group_text(w["word"]).split();ct=sum(c[t] for t in ts);sentence_tokens=group_text(r["text"]).split();need(sentence_tokens,"source_word_support")
    a=[len(w["word"]),pos/max(1,len(words)-1),len(words[pos-1]) if pos else 0,len(words[pos+1]) if pos+1<len(words) else 0,len(words),sum(map(len,words))/len(words),len(set(map(group_text,words)))/len(words),math.log1p(ct),int(ct==0),sum(-math.log((c[t]+1)/(total+vocab)) for t in sentence_tokens)/len(sentence_tokens)]
    a += [w.get(k) for k in GAZE]+[z["window"]["pupil"],r["omission"],r["duration_seconds"]]
    need(len(a)==19 and all(x is None or finite(x) for x in a),"base19_values");e=scalp_means(z["window"]["band_values"])
    return a+[int(x is None) for x in a]+[int(x is None) for x in e]
def representation_nuisance(e,representation):
    if representation in ("released_summary","band_spatial"):return [int(x is None) for x in e]
    # Duration, complete sample masks and segment geometry are non-amplitude information available in BOTH arms.
    return {"segments":[{"samples":len(s["values"]),"valid":s["valid"],"duration_seconds":len(s["values"])/500,"channel_ids":s["channel_ids"]} for s in e]}
def public_rows(partition,identity):
    lex=lexical(partition["train"]);task=identity["task"];arm=identity["arm"];context=identity["context"];rep=identity["representation"]
    wave_masks={}
    if rep in ("raw_waveform","cleaned_waveform"):
        import numpy as np
        from .waveforms import WaveFeatures
        train_eeg=[source_eeg(z,context,rep) for z in partition["train"]];operator=WaveFeatures();operator.fit(train_eeg,partition["weights"])
        for group in ("train","query"):
            rows=partition[group];values=operator.transform([source_eeg(z,context,rep) for z in rows]) if rows else []
            for z,v in zip(rows,values):wave_masks[id(z)]=(~np.isfinite(v)).astype(int).tolist()
    def row(z,rid,training,weight=None):
        r=z["sentence"];e=source_eeg(z,context,rep);mask=representation_nuisance(e,rep)
        if rep in ("raw_waveform","cleaned_waveform"):mask={"sample_geometry":mask,"wave_feature_missing":wave_masks[id(z)]}
        if task=="NEURAL-085":
            gaze=r["gaze_summary"];nuisance={"eeg_support":mask,"gaze_missing":[int(x is None) for x in gaze],"source_word_slots":len(r["words"]),"valid_gaze_fractions":r["valid_gaze_fractions"]};allblocks={"text":r["text"],"gaze":gaze,"nuisance":nuisance,"eeg":e}
            names={"TEXT":["text"],"GAZE":["gaze"],"EEG":["eeg","nuisance"],"TEXT_GAZE":["text","gaze"],"JOINT":["text","gaze","eeg"],"NUISANCE":["nuisance"],"NTG":["text","gaze","nuisance"],"NTGE":["text","gaze","nuisance","eeg"],"NTG_SHUFFLED_E":["text","gaze","nuisance","eeg"]}[arm];blocks={k:allblocks[k] for k in names}
            if arm=="EEG":blocks["nuisance"]={"eeg_support":mask}
        else:
            blocks={"base":base46(z,context,lex)}
            if rep!="released_summary":blocks["representation_nuisance"]=mask
            if arm!="COVARIATES":blocks["eeg"]=e
        out={"id":rid,"features":blocks}
        if training:out.update(label=int(r["condition"]=="TSR"),weight=weight)
        return out
    result={"train":[row(z,i,True,w) for z,i,w in zip(partition["train"],partition["train_ids"],partition["weights"])],"query":[row(z,i,False) for z,i in zip(partition["query"],partition["query_ids"])],"information_set":INFORMATION_SET,"identity":identity,"feature_recipe":"original-source-derived-v1"}
    if arm in ("NTG_SHUFFLED_E","COVARIATES_SHUFFLED_E"):
        from .controls import shuffle_view
        result,shuffle_observations=shuffle_view(result,partition["train"],partition["query"]);result["protected_control_observations"]={"NC02":shuffle_observations}
    from .control_features import project
    return project(result,partition["train"],partition["query"],identity)

def weighted_state(rows,weights):
    import numpy as np
    a=np.asarray(rows,float);w=np.asarray(weights,float);need(a.ndim==2 and len(a)==len(w) and np.all(w>0),"weighted_matrix")
    med=[]
    for j in range(a.shape[1]):
        ok=np.isfinite(a[:,j]);order=np.argsort(a[ok,j],kind="stable");v=a[ok,j][order];ww=w[ok][order]
        med.append(0. if not len(v) else float(v[np.searchsorted(np.cumsum(ww),ww.sum()/2,side="left")]))
    filled=np.where(np.isfinite(a),a,np.asarray(med));mean=np.average(filled,axis=0,weights=w);sd=np.sqrt(np.average((filled-mean)**2,axis=0,weights=w));sd=np.where(sd<=1e-12,1.,sd)
    return {"median":med,"mean":mean.tolist(),"scale":sd.tolist()}
def scale(rows,state):
    import numpy as np
    a=np.asarray(rows,float);a=np.where(np.isfinite(a),a,np.asarray(state["median"]));return (a-np.asarray(state["mean"]))/np.asarray(state["scale"])
def flatten_nuisance(v):
    if isinstance(v,dict):
        if "segments" in v:
            segs=v["segments"];duration=sum(s["duration_seconds"] for s in segs);n=sum(s["samples"] for s in segs);valid=[sum(bool(row[c]) for s in segs for row in s["valid"])/max(1,n) for c in range(105)];return [duration,n,len(segs)]+valid
        return [y for k in sorted(v) for y in flatten_nuisance(v[k])]
    if isinstance(v,list):return [y for x in v for y in flatten_nuisance(x)]
    need(v is None or finite(v),"nuisance_value");return [v]

class Encoder:
    def __init__(self,representation,algorithm="linear"):
        self.representation=representation;self.algorithm=algorithm;self.states={};self.text=None;self.svd=None;self.wave=None;self.names=None
    def blocks(self,rows,fit=False,weights=None):
        import numpy as np
        names=sorted(rows[0]["features"]) if rows else self.names;need(names is not None,"feature_columns");out={}
        for name in names:
            vals=[r["features"][name] for r in rows]
            if name=="text":
                from sklearn.feature_extraction.text import HashingVectorizer,TfidfTransformer
                vector=HashingVectorizer(n_features=4096,alternate_sign=False,ngram_range=(1,2),norm=None,lowercase=True,token_pattern=r"(?u)\b\w\w+\b")
                if fit:self.text=TfidfTransformer();self.text.fit(vector.transform(sorted(set(vals))))
                a=self.text.transform(vector.transform(vals))
                if self.algorithm=="nonlinear":
                    from sklearn.decomposition import TruncatedSVD
                    if fit:
                        rank=min(64,len(set(vals))-1,4095);need(rank>=1,"text_SVD_support");self.svd=TruncatedSVD(n_components=rank,n_iter=7,random_state=0);self.svd.fit(a)
                    a=self.svd.transform(a)
                else:a=a.toarray()
                a=np.column_stack((a,[len(t) for t in vals],[len(group_text(t).split()) for t in vals]))
            elif name=="eeg" and self.representation in ("raw_waveform","cleaned_waveform"):
                from .waveforms import WaveFeatures
                if fit:self.wave=WaveFeatures();self.wave.fit(vals,weights)
                a=self.wave.transform(vals)
            else:a=np.asarray([flatten_nuisance(v) for v in vals],float)
            if fit:self.states[name]=weighted_state(a,weights)
            out[name]=scale(a,self.states[name])/math.sqrt(max(1,a.shape[1]))
        if fit:self.names=names
        need(names==self.names,"identical_feature_blocks");return out
    def fit_transform(self,rows,weights):
        import numpy as np
        x=self.blocks(rows,True,weights);return np.concatenate([x[k] for k in self.names],axis=1)
    def transform(self,rows):
        import numpy as np
        if not rows:return np.empty((0,sum(len(self.states[k]["mean"]) for k in self.names)))
        x=self.blocks(rows);return np.concatenate([x[k] for k in self.names],axis=1)
