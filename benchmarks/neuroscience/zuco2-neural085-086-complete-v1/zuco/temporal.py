"""Independent complete-sample temporal competence reference; no pretrained model."""
import copy
from .io import need
from .features import Encoder,public_rows,source_eeg
from .reference import view_for,validation_loss
from .splits import weights,inner_groups

def network(non_eeg_dim):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    class MaskedConv(nn.Module):
        def __init__(self,inside,outside,kernel,stride=1,padding=0,groups=1):
            super().__init__();self.conv=nn.Conv1d(inside,outside,kernel,stride,padding,groups=groups);self.groups=groups;self.inside=inside;self.outside=outside
        def forward(self,x,m):
            c=self.conv;k=c.kernel_size[0];count=F.conv1d(m,torch.ones(self.outside,self.inside//self.groups,k,device=x.device),stride=c.stride,padding=c.padding,groups=self.groups);valid=count>0
            raw=c(x*m);bias=c.bias[None,:,None];y=(raw-bias)*(self.inside//self.groups*k)/count.clamp_min(1)+bias;return y*valid,valid.to(x.dtype)
    class Model(nn.Module):
        def __init__(self):
            super().__init__();self.depth=MaskedConv(105,420,31,2,15,105);self.mix=MaskedConv(420,32,1);self.temp=MaskedConv(32,32,15,2,7);self.head=nn.Linear(64+non_eeg_dim,1)
        def chunks(self,x,m):
            x,m=self.depth(x,m);x=F.gelu(x);x,m=self.mix(x,m);x,m=self.temp(x,m);x=F.gelu(x)
            # GroupNorm8 uses supported samples only; query-local moments are explicit.
            shape=x.shape;a=x.reshape(shape[0],8,4,shape[2]);mask=m.reshape(shape[0],8,4,shape[2]);n=mask.sum((2,3),keepdim=True).clamp_min(1);mean=(a*mask).sum((2,3),keepdim=True)/n;var=((a-mean)**2*mask).sum((2,3),keepdim=True)/n;x=((a-mean)/torch.sqrt(var+1e-5)*mask).reshape(shape)
            n=m.sum(2).clamp_min(1);mean=(x*m).sum(2)/n;var=((x-mean[:,:,None])**2*m).sum(2)/n;return torch.cat((mean,var),1)
        def forward(self,chunks,base):
            rows=[]
            for segments in chunks:
                vv=[];ww=[]
                for x,m in segments:
                    valid=m.any(0).sum()
                    if valid>0:vv.append(self.chunks(x[None],m[None])[0]);ww.append(valid)
                rows.append(sum(v*w for v,w in zip(vv,ww))/sum(ww) if vv else torch.zeros(64,device=base.device))
            return self.head(torch.cat((torch.stack(rows),base),1)).reshape(-1)
    return Model()

def tensor_chunks(rows,identity):
    import torch,numpy as np
    out=[];has_eeg=identity["arm"] not in ("TEXT","GAZE","TEXT_GAZE","NUISANCE","NTG","COVARIATES")
    for z in rows:
        chunks=[]
        if has_eeg:
            for seg in source_eeg(z,identity["context"],identity["representation"]):
                a=np.asarray(seg["values"],float);m=np.asarray(seg["valid"],bool)&np.isfinite(a);need(a.shape==m.shape and a.shape[1]==105,"temporal_waveform_ABI")
                for k in range(0,len(a),1000):chunks.append((torch.tensor(np.where(m[k:k+1000],a[k:k+1000],0).T,dtype=torch.float32),torch.tensor(m[k:k+1000].T,dtype=torch.float32)))
        out.append(chunks)
    return out

def without_eeg(view):
    v=copy.deepcopy(view)
    for r in v:r["features"].pop("eeg",None)
    # EEG-only still has explicit nuisance masks, so the shared block never becomes an empty matrix.
    return v
class TemporalReference:
    def __getstate__(self):
        state=dict(self.__dict__);model=state.pop('model');state['model_state_dict']=model.state_dict();return state
    def __setstate__(self,state):
        weights=state.pop('model_state_dict');self.__dict__.update(state);self.model=network(self.model_input_dimensions);self.model.load_state_dict(weights,strict=True);self.model.eval()
    def fit0(self,training,identity):
        import torch
        self.training=training;self.identity=copy.deepcopy(identity);torch.manual_seed(0);view=view_for(training,[],identity);w=weights(training,identity["task"]);self.encoder=Encoder(identity["representation"]);x=self.encoder.fit_transform(without_eeg(view["train"]),w);base=torch.tensor(x,dtype=torch.float32);labels=torch.tensor([r["label"] for r in view["train"]],dtype=torch.float32);weight=torch.tensor(w,dtype=torch.float32);chunks=public_tensor_chunks(view["train"]);self.model_input_dimensions=base.shape[1];self.model=network(base.shape[1]);optimizer=torch.optim.AdamW(self.model.parameters(),lr=.001,weight_decay=.01);generator=torch.Generator().manual_seed(0)
        for epoch in range(50):
            order=torch.randperm(len(training),generator=generator)
            for start in range(0,len(training),32):
                idx=order[start:start+32];optimizer.zero_grad();logits=self.model([chunks[int(i)] for i in idx],base[idx]);loss=(torch.nn.functional.binary_cross_entropy_with_logits(logits,labels[idx],reduction="none")*weight[idx]).sum()/weight[idx].sum();need(bool(torch.isfinite(loss)),"temporal_nonfinite");loss.backward();torch.nn.utils.clip_grad_norm_(self.model.parameters(),1.);optimizer.step()
        self.model.eval();return self
    def fit(self,training,identity,J):
        need(identity["representation"]in("raw_waveform","cleaned_waveform"),"temporal_representation");predictions={}
        for a,b,tr,va in inner_groups(training):
            need(tr and va,"temporal_inner_support");m=TemporalReference().fit0([training[i] for i in tr],identity);probs=m.predict([training[i] for i in va])
            for i,p in zip(va,probs):predictions[i]=p
        need(set(predictions)==set(range(len(training))),"temporal_inner_complete");self.inner_competence={"loss":validation_loss(training,[predictions[i] for i in range(len(training))],identity["task"],J),"epoch_selection":False,"epochs":50};return self.fit0(training,identity)
    def predict(self,query):
        import torch
        if not query:return []
        view=view_for(self.training,query,self.identity);base=torch.tensor(self.encoder.transform(without_eeg(view["query"])),dtype=torch.float32)
        with torch.no_grad():return torch.sigmoid(self.model(public_tensor_chunks(view["query"]),base)).tolist()


def public_tensor_chunks(rows):
    import torch,numpy as np
    out=[]
    for row in rows:
        chunks=[]
        for seg in row["features"].get("eeg",[]):
            a=np.asarray(seg["values"],float);m=np.asarray(seg["valid"],bool)&np.isfinite(a)
            for k in range(0,len(a),1000):chunks.append((torch.tensor(np.where(m[k:k+1000],a[k:k+1000],0).T,dtype=torch.float32),torch.tensor(m[k:k+1000].T,dtype=torch.float32)))
        out.append(chunks)
    return out

def _public_predict(self,query):
    import torch
    if not query:return []
    base=torch.tensor(self.encoder.transform(without_eeg(query)),dtype=torch.float32)
    with torch.no_grad():return torch.sigmoid(self.model(public_tensor_chunks(query),base)).tolist()
TemporalReference.predict_public=_public_predict
