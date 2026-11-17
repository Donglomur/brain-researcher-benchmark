"""Actual closed neural constructors. Imported only by separately authorized actors.

Namespaced author modules retain their original architectures. Library variants
are literal pinned source, with explicit prospective geometry/sequence adapters.
No checkpoint downloader or arbitrary callback is accepted.
"""
from pathlib import Path
import hashlib,importlib
from types import SimpleNamespace
import torch
from torch import nn
from .catalog import need

class EEGNet(nn.Module):
    """ARL EEGNet-8,2 reconstruction with TensorFlow SAME pads and poststep norms."""
    def __init__(self,c,t,k):
        super().__init__();self.temporal=nn.Conv2d(1,8,(1,64),bias=False,padding='same')
        self.bn0=nn.BatchNorm2d(8,eps=.001,momentum=.01)
        self.spatial=nn.Conv2d(8,16,(c,1),groups=8,bias=False)
        self.bn1=nn.BatchNorm2d(16,eps=.001,momentum=.01)
        self.depth=nn.Conv2d(16,16,(1,16),groups=16,bias=False,padding='same')
        self.point=nn.Conv2d(16,16,1,bias=False);self.bn2=nn.BatchNorm2d(16,eps=.001,momentum=.01)
        self.drop=nn.Dropout(.5);self.head=nn.Linear(16*(t//4//8),k)
        for layer in self.modules():
            if isinstance(layer,(nn.Conv2d,nn.Linear)):
                nn.init.xavier_uniform_(layer.weight)
                if layer.bias is not None:nn.init.zeros_(layer.bias)
    def features(self,x):
        x=self.bn0(self.temporal(x[:,None]));x=self.bn1(self.spatial(x));x=self.drop(nn.functional.avg_pool2d(nn.functional.elu(x),(1,4)))
        x=self.bn2(self.point(self.depth(x)));return self.drop(nn.functional.avg_pool2d(nn.functional.elu(x),(1,8))).flatten(1)
    def forward(self,x):return self.head(self.features(x))
    def project(self):
        with torch.no_grad():
            for w,cap in ((self.spatial.weight,1.),(self.head.weight,.25)):
                dims=tuple(range(1,w.ndim));n=w.norm(2,dim=dims,keepdim=True);w.mul_(torch.clamp(cap/(n+1e-7),max=1.))

class CBraModHead(nn.Module):
    def __init__(self,k,c,t,sequence,pooling=None):
        super().__init__();from .vendor_cbramod.cbramod import CBraMod
        self.encoder=CBraMod(in_dim=200,out_dim=200,d_model=200,dim_feedforward=800,seq_len=t//200,n_layer=12,nhead=8);self.encoder.proj_out=nn.Identity()
        need(pooling in (None,'pool','no_pool'),'closed CBraMod pooling condition')
        self.sequence=sequence;self.pooling=pooling
        # Preserve the selected S7 head and sequence templates. Only the
        # required pool/no-pool feature projection and input width differ.
        self.pool_features=(pooling=='pool') if pooling is not None else not sequence
        feature_width=200 if self.pool_features else c*(t//200)*200
        if sequence:
            self.epoch_head=nn.Sequential(nn.Linear(feature_width,512),nn.GELU())
            layer=nn.TransformerEncoderLayer(512,4,2048,batch_first=True,activation=nn.functional.gelu,norm_first=True)
            self.sequence_encoder=nn.TransformerEncoder(layer,1,enable_nested_tensor=False);self.head=nn.Linear(512,k)
        else:self.head=nn.Sequential(nn.Linear(feature_width,200),nn.ELU(),nn.Dropout(.1),nn.Linear(200,k))
    def patch_features(self,z):
        return z.mean((1,2)) if self.pool_features else z.flatten(1)
    def features(self,x):
        if self.sequence:
            b,s,c,t=x.shape;z=self.patch_features(self.encoder(x.reshape(b*s,c,t//200,200))).reshape(b,s,-1);return self.sequence_encoder(self.epoch_head(z))
        b,c,t=x.shape;return self.patch_features(self.encoder(x.reshape(b,c,t//200,200)))
    def forward(self,x):return self.head(self.features(x))

class REVEHead(nn.Module):
    def __init__(self,size,k,c,t,ablation,purpose):
        super().__init__();from .vendor_reve.encoder import REVE,Learnable4DPE
        from .vendor_reve.classifier import ReveClassifier
        from .vendor_reve.backbone import RMSNorm
        d,depth,heads,freq={'Small':(512,4,8,4),'Base':(512,22,8,4),'Large':(1216,22,19,5)}[size]
        paper=purpose=='R-paper';d=1250 if paper and size=='Large' else d;self.position_scale=1. if paper else .01
        component=ablation.get('component','base')
        args=SimpleNamespace(embed_dim=d,depth=depth,heads=heads,head_dim=64,mlp_dim_ratio=8/3 if paper else 2.66,use_geglu=component!='GELU_RMSNorm')
        encoder=REVE(args,freq,200,20,0. if component in ('remove_position_noise','learnable_PE') else (.25 if paper else .0025))
        if paper:
            for layer in encoder.modules():
                if isinstance(layer,nn.Linear):layer.register_parameter('bias',None)
            encoder.fourier4d=PaperTimeShift(encoder.fourier4d);encoder.mlp4d=PaperTimeShift(encoder.mlp4d)
        if component=='MLP4D_literal_unqualified':encoder.fourier4d=ZeroPositions(d)
        if component=='GEGLU_LayerNorm':
            def replace(m):
                for name,child in list(m.named_children()):
                    if isinstance(child,RMSNorm):setattr(m,name,nn.LayerNorm(child.weight.numel(),eps=child.eps,bias=False))
                    else:replace(child)
            replace(encoder)
        self.classifier=ReveClassifier(encoder,k,dropout=.1,pooling='no' if ablation.get('pooling')=='no_pool' else 'last',out_shape=(c*((t-200)//180+1)+1)*d)
        self.learnable_positions=component=='learnable_PE';self._pe_class=LearnedPatchPositions
    def bind_geometry(self,positions,t):
        if self.learnable_positions:
            enc=self.classifier.encoder;enc.fourier4d=self._pe_class(enc.embed_dim,positions,(t-200)//180+1,self.position_scale);enc.mlp4d=ZeroPositions(enc.embed_dim)
    def features(self,x,positions):
        model=self.classifier;z=model.encoder(x,positions.clone(),False)
        if model.pooling=='no':
            q=model.cls_query_token.expand(len(x),-1,-1);a=(q@z.transpose(-1,-2)/model.encoder.embed_dim**.5).softmax(-1);return torch.cat((a@z,z),dim=1).flatten(1)
        q=model.cls_query_token.expand(len(x),-1,-1);return ((q@z.transpose(-1,-2)/model.encoder.embed_dim**.5).softmax(-1)@z).squeeze(1)
    def forward(self,x,positions):return self.classifier(x,positions.clone())

class LearnedPatchPositions(nn.Module):
    def __init__(self,d,positions,patches,scale=.01):
        super().__init__();self.register_buffer('positions',positions*scale);self.spatial=nn.Embedding(len(positions),d);self.temporal=nn.Embedding(patches,d)
    def forward(self,p):
        dist=torch.cdist(p[...,:3],self.positions.to(p));ids=dist.argmin(-1)
        need(bool((dist.gather(-1,ids[...,None])<1e-5).all()),'learned position table has no unseen geometry')
        return self.spatial(ids)+self.temporal(p[...,3].long())

class PaperTimeShift(nn.Module):
    """Explicit paper adapter: centimeters and one-based time, scale0.1."""
    def __init__(self,inner):super().__init__();self.inner=inner
    def forward(self,p):
        q=p.clone();q[...,3]+=1;return self.inner(q)

class ZeroPositions(nn.Module):
    def __init__(self,d):super().__init__();self.d=d
    def forward(self,p):return p.new_zeros((*p.shape[:-1],self.d))

def pinned_library(module):
    need(module in ('eegconformer','deepsleepnet','usleep'),'closed pinned library module')
    spec=importlib.util.find_spec('braindecode');need(spec is not None and spec.submodule_search_locations,'qualified library package required')
    locations=list(spec.submodule_search_locations);need(len(locations)==1,'single qualified library source root')
    installed=Path(locations[0]);retained=Path(__file__).resolve().parent.parent/'reference-source/vendor/braindecode/braindecode'
    for source in retained.rglob('*.py'):
        actual=installed/source.relative_to(retained)
        need(actual.is_file() and hashlib.sha256(actual.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest(),'installed library source/dependency differs from retained exact source')
    return importlib.import_module('braindecode.models.'+module)

class DeepSleepSequence(nn.Module):
    """Retained library CNN/BiLSTM, applied to all20 epochs as one actual sequence."""
    def __init__(self,c,t,k):
        super().__init__();self.model=pinned_library('deepsleepnet').DeepSleepNet(n_chans=c,n_times=t,n_outputs=k,sfreq=200)
    def forward(self,x):
        b,s,c,t=x.shape;m=self.model;z=x.reshape(b*s,c,t).unsqueeze(1)
        z=m.dropout(torch.cat((m.flatten_cnn(m.cnn1(z)),m.flatten_cnn(m.cnn2(z))),dim=1));res=m.residual_shortcut(z).reshape(b,s,-1)
        seq,_=m.bilstm(z.reshape(b,s,-1));z=m.dropout(seq+res).reshape(b*s,-1)
        return m.final_layer(m.features_extractor(z)).reshape(b,s,-1)

def build(base,channels,samples,classes,sequence,ablation,purpose):
    if base.startswith('REVE-'):return REVEHead(base.split('-')[1],classes,channels,samples,ablation,purpose)
    if base=='CBraMod':return CBraModHead(classes,channels,samples,sequence,ablation.get('pooling'))
    if base=='EEGNet':return EEGNet(channels,samples,classes)
    if base=='EEGConformer':return pinned_library('eegconformer').EEGConformer(n_chans=channels,n_times=samples,n_outputs=classes,sfreq=200)
    if base=='DeepSleepNet':return DeepSleepSequence(channels,samples,classes)
    if base=='USleep':return pinned_library('usleep').USleep(n_chans=channels,n_times=samples,n_outputs=classes,sfreq=200,ensure_odd_conv_size=True)
    if base.startswith('LaBraM-'):
        from .vendor_labram import modeling_finetune as m
        constructors={'LaBraM-Base':m.labram_base_patch200_200,'LaBraM-Large':m.labram_large_patch200_200,'LaBraM-Huge':m.labram_huge_patch200_200}
        model=constructors[base](pretrained=False,EEG_size=samples,num_classes=classes,drop_path_rate=.1)
        if samples//200>16:
            model.time_embed=nn.Parameter(nn.functional.interpolate(model.time_embed.transpose(1,2),size=samples//200,mode='linear',align_corners=False).transpose(1,2).contiguous())
        return model
    from .vendor_biot import SPaRCNet,ContraWR,CNNTransformer,FFCL,STTransformer,BIOTClassifier
    if base=='SPaRCNet':return SPaRCNet(in_channels=channels,sample_length=samples,n_classes=classes)
    if base=='ContraWR':return ContraWR(in_channels=channels,n_classes=classes,fft=200,steps=20)
    if base=='CNN-Transformer':return CNNTransformer(in_channels=channels,n_classes=classes,fft=200,steps=20,n_segments=5)
    if base=='FFCL':return FFCL(in_channels=channels,n_classes=classes,fft=200,steps=20,sample_length=samples)
    if base=='ST-Transformer':return STTransformer(emb_size=256,depth=4,n_classes=classes,channel_legnth=samples,n_channels=channels)
    if base=='BIOT':return BIOTClassifier(n_classes=classes,n_channels=channels,n_fft=200,hop_length=100)
    raise ValueError('unregistered neural constructor')

def neural_forward(model,base,x,positions,channel_ids,sequence):
    if base=='CBraMod' or base=='DeepSleepNet':return model(x)
    if base=='USleep':return model(x).transpose(1,2) if sequence else model(x)
    if sequence:
        b,s,c,t=x.shape;x=x.reshape(b*s,c,t);positions=positions.repeat_interleave(s,0)
    if base.startswith('REVE-'):out=model(x,positions*model.position_scale)
    elif base.startswith('LaBraM-'):
        b,c,t=x.shape;out=model(x.reshape(b,c,t//200,200),input_chans=channel_ids)
    else:out=model(x)
    return out.reshape(-1,20,out.shape[-1]) if sequence else out
