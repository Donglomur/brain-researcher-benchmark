"""Source-owned prospective EEGPT numerical producers, never run at build time.

The retained author modules supply spatial/rotary temporal architectures. This
adapter makes source versus corrected tensor layout, trainability, masking and
selection explicit. It does not claim historical parity or supply the absent
no-predictor, EEGNet or copied Temple comparator implementations.
"""
from pathlib import Path
import hashlib
import importlib.util
from .protocol import need,fields,digest,identity,Refusal

CHANNELS=('FP1 FPZ FP2 AF3 AF4 F7 F5 F3 F1 FZ F2 F4 F6 F8 FT7 FC5 FC3 FC1 FCZ FC2 FC4 FC6 FT8 T7 C5 C3 C1 CZ C2 C4 C6 T8 TP7 CP5 CP3 CP1 CPZ CP2 CP4 CP6 TP8 P7 P5 P3 P1 PZ P2 P4 P6 P8 PO7 PO3 POZ PO4 PO8 O1 OZ O2').split()
VARIANTS={'tiny1':(64,1,(2,2,4),4),'tiny2':(64,4,(2,2,4),4),'tiny3':(64,4,(8,8,8),4),'little':(128,4,(8,8,8),4),'base1':(256,1,(6,6,6),4),'base2':(256,4,(8,8,8),4),'base3':(512,1,(6,6,6),8),'large':(512,4,(8,8,8),8)}


def trusted_author_module(root,relative,expected):
    """Only fixed exact source-owned module; never a submitted-code import."""
    path=Path(root)/relative;raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==expected,'exact qualified retained architecture source')
    name='_eegpt_reference_'+expected;spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def pretraining_model(author_root,source_pins,variant,*,ablation,layout_policy):
    import copy
    import random
    import torch
    from torch import nn
    from torch.nn import functional as F
    from functools import partial
    need(variant in VARIANTS and ablation in ('A','B','C','D'),'all selected eight sizes and exact four ablation definitions')
    need(layout_policy in ('source_reshape_v1','corrected_time_channel_v1'),'unresolved source permutation is an explicit separately qualified policy')
    m=trusted_author_module(author_root,'pretrain/modeling_pretraining.py',source_pins['pretrain/modeling_pretraining.py']);dim,summary,depths,heads=VARIANTS[variant]
    common={'embed_dim':dim,'embed_num':summary,'num_heads':heads,'mlp_ratio':4.,'drop_rate':0.,'attn_drop_rate':0.,'drop_path_rate':0.,'init_std':.02,'qkv_bias':True,'norm_layer':partial(nn.LayerNorm,eps=1e-6)}
    class Objective(nn.Module):
        def __init__(self):
            super().__init__();self.encoder=m.EEGTransformer(img_size=[58,1024],patch_size=64,depth=depths[0],**common)
            self.predictor=m.EEGTransformerPredictor(num_patches=self.encoder.num_patches,use_part_pred=True,predictor_embed_dim=dim,depth=depths[1],**common)
            self.reconstructor=m.EEGTransformerReconstructor(num_patches=self.encoder.num_patches,patch_size=64,reconstructor_embed_dim=dim,depth=depths[2],**common)
            self.target_encoder=copy.deepcopy(self.encoder);self.target_encoder.requires_grad_(False);self.channel_ids=self.encoder.prepare_chan_ids(CHANNELS)
        def masks(self):
            C,N=self.encoder.num_patches
            while True:
                visible=[];missing=[];other=[]
                for time in range(N):
                    order=torch.randperm(C)+time*C
                    if random.random()>.5:visible.append(order[:12]);other.append(order[12:])
                    else:missing.append(order)
                if not visible or not other:continue
                others=torch.cat(other);others=others[torch.rand(others.shape)<.2]
                if not len(others):continue
                return torch.stack(visible),torch.cat(missing+[others])
        def forward(self,x,masks=None):
            need(x.ndim==3 and list(x.shape[1:])==[58,1024],'full selected pretraining58x1024 crop')
            mx,my=self.masks() if masks is None else masks;channels=self.channel_ids.to(x)
            with torch.no_grad():
                h=self.target_encoder(x,channels);h=F.layer_norm(h,(h.size(-1),));C,N=self.encoder.num_patches
                target=x.view(x.shape[0],C,x.shape[-2]//C,N,x.shape[-1]//N).permute(0,3,1,2,4).contiguous()
                if layout_policy=='source_reshape_v1':target=target.view(x.shape[0],C,N,-1)
                else:target=target.view(x.shape[0],N,C,-1)
                y=m.apply_mask(my.to(x.device),target)
                if ablation!='B':y=F.layer_norm(y,(y.size(-1),))
            z=self.encoder(x,channels,mask_x=mx);z,combined=self.predictor(z,mask_x=mx)
            recon=self.reconstructor(z if ablation=='C' else combined,channels,mask_y=my)
            need(h.shape==z.shape and y.shape==recon.shape,'actual complete target/predictor/reconstruction axes')
            a=(h-z).square();r=(y-recon).square();la=a.mean();lr=r.mean();loss=lr if ablation=='A' else la+lr
            return loss,{'LA_numerator':a.sum(),'LA_denominator':a.numel(),'LR_numerator':r.sum(),'LR_denominator':r.numel(),'total':loss,'mask_x':mx,'mask_y':my}
        def ema(self,coefficient):
            need(.996<=coefficient<=1,'selected source momentum range')
            with torch.no_grad():
                for q,k in zip(self.encoder.parameters(),self.target_encoder.parameters()):k.mul_(coefficient).add_((1-coefficient)*q.detach())
    return Objective()


def architecture_census(model,*,recipe):
    parameters=[];trainable=0;total=0;encoder=0
    for name,p in model.named_parameters():
        n=p.numel();total+=n;trainable+=n if p.requires_grad else 0;encoder+=n if name.startswith(('encoder.','target_encoder.')) else 0
        parameters.append({'name':name,'shape':list(p.shape),'elements':n,'trainable':p.requires_grad,'dtype':str(p.dtype)})
    has_separate_target=hasattr(model,'encoder') and hasattr(model,'target_encoder')
    encoder_only=sum(r['elements'] for r in parameters if r['name'].startswith('encoder.' if has_separate_target else 'target_encoder.'));ema_only=sum(r['elements'] for r in parameters if has_separate_target and r['name'].startswith('target_encoder.'))
    return {'recipe':recipe,'parameters':parameters,'buffers':{n:{'shape':list(b.shape),'dtype':str(b.dtype)} for n,b in model.named_buffers()},'counts':{'all_modules':total,'encoder_only':encoder_only,'ema_target_only':ema_only,'non_encoder_parameters':total-encoder_only-ema_only,'encoder_and_target_included':encoder,'trainable':trainable},'module_types':{n:type(m).__name__ for n,m in model.named_modules()},'module_normalization':{n:{'epsilon':getattr(m,'eps',None),'normalized_shape':list(m.normalized_shape) if hasattr(m,'normalized_shape') else None,'training':m.training} for n,m in model.named_modules() if hasattr(m,'eps')},'paper_rounded_parameter_count_is_not_exact_identity':True}


def pretrain(model,train_loader,validation_loader,recipe,*,write_observation,save_checkpoint):
    """Full specified epochs; callbacks are internal worker file writers only."""
    import torch
    fields(recipe,('epochs','learning_rate_max','batch_size','precision','device','seed','steps_per_epoch','layout_policy','ablation','variant','original_support_identity'),'complete source-owned pretraining recipe')
    need(recipe['precision']=='float32','this producer is explicit float32; mixed precision historical parity requires its own qualified recipe')
    need(len(train_loader)==recipe['steps_per_epoch'],'complete original training loader and no convenience batch subset');total=recipe['epochs']*len(train_loader);need(total>0,'positive complete pretraining schedule')
    groups=[]
    for exclude in (False,True):
        params=[p for name,p in model.named_parameters() if p.requires_grad and (('bias' in name or p.ndim==1)==exclude)]
        groups.append({'params':params,'weight_decay':0. if exclude else 1e-6})
    optimizer=torch.optim.AdamW(groups,lr=6e-5);scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=recipe['learning_rate_max'],total_steps=total,div_factor=2,final_div_factor=8,pct_start=.2)
    model.to(recipe['device']);step=0
    for epoch in range(recipe['epochs']):
        model.train()
        for batch_index,x in enumerate(train_loader):
            x=x.to(recipe['device']);optimizer.zero_grad(set_to_none=True);loss,primitive=model(x);need(bool(torch.isfinite(loss)),'finite actual objective');loss.backward();optimizer.step();model.ema(.996+step*(1-.996)/total);scheduler.step()
            write_observation('train',epoch,step,batch_index,primitive,recipe);step+=1
        model.eval()
        with torch.no_grad():
            for batch_index,x in enumerate(validation_loader):
                _,primitive=model(x.to(recipe['device']));write_observation('validation',epoch,step,batch_index,primitive,recipe)
        save_checkpoint(epoch,model,optimizer,scheduler,recipe)
    need(step==total,'all original training steps complete');return {'steps':step,'epochs':recipe['epochs'],'final':architecture_census(model,recipe=recipe),'historical_parity':False}


def downstream_model(author_root,source_pins,recipe,initial_state):
    import torch
    from torch import nn
    from torch.nn import functional as F
    from functools import partial
    fields(recipe,('dataset','variant','classes','input_channels','channel_names','samples','patch_stride','asf','adaptation','source_binary4','interpolation','average_reference','amplitude_divisor','temple_kernel','temple_dropout','checkpoint_role','positional_policy','qualification'),'complete downstream architecture recipe')
    need(recipe['adaptation'] in ('LP','FT') and recipe['variant'] in VARIANTS,'selected trainability/variant');digest(recipe['qualification'])
    need(recipe['positional_policy'] in ('retained_integer_cast','standard_sinusoid_prospective','not_applicable'),'explicit source versus prospective positional encoding policy')
    position_source=trusted_author_module(author_root,'downstream/Modules/Transformers/pos_embed.py',source_pins['downstream/Modules/Transformers/pos_embed.py']) if recipe['dataset']=='Sleep-EDFx' and recipe['positional_policy']=='retained_integer_cast' else None
    m=trusted_author_module(author_root,'downstream/Modules/models/EEGPT_mcae.py',source_pins['downstream/Modules/models/EEGPT_mcae.py']);constraints=trusted_author_module(author_root,'downstream/Modules/Network/utils.py',source_pins['downstream/Modules/Network/utils.py']);dim,summary,depth,heads=VARIANTS[recipe['variant']];names=recipe['channel_names'];dataset=recipe['dataset'];temple=dataset in ('TUAB','TUEV');sleep=dataset=='Sleep-EDFx'
    class Adaptation(nn.Module):
        def __init__(self):
            super().__init__();self.target_encoder=m.EEGTransformer(img_size=[len(names),recipe['samples']],patch_size=64,patch_stride=recipe['patch_stride'],embed_num=summary,embed_dim=dim,depth=depth[0],num_heads=heads,mlp_ratio=4.,drop_rate=0.,attn_drop_rate=0.,drop_path_rate=0.,init_std=.02,qkv_bias=True,norm_layer=partial(nn.LayerNorm,eps=1e-6));self.channel_ids=self.target_encoder.prepare_chan_ids(names)
            if initial_state is not None:self.target_encoder.load_state_dict(initial_state,strict=True)
            need(initial_state is not None or recipe['checkpoint_role']=='trained_random_init','no silently missing pretrained state')
            if recipe['adaptation']=='LP':self.target_encoder.requires_grad_(False)
            if recipe['asf']:
                if temple:self.asf=nn.Sequential(nn.Conv1d(recipe['input_channels'],len(names),1),nn.BatchNorm1d(len(names)),nn.GELU(),nn.Conv1d(len(names),len(names),recipe['temple_kernel'],padding=recipe['temple_kernel']//2,groups=len(names)),nn.Dropout(recipe['temple_dropout']))
                elif dataset=='PhysioP300':self.channel_scale=nn.Parameter(torch.ones(1,len(names),1)+.001*torch.rand(1,len(names),1));self.asf=None
                else:self.asf=constraints.Conv1dWithConstraint(recipe['input_channels'],len(names),1,max_norm=1)
            else:need(recipe['input_channels']==len(names),'noASF preserves actual original channel support, cannot fabricate remapping');self.asf=None
            tokens=1+(recipe['samples']-64)//recipe['patch_stride'];outputs=4 if recipe['source_binary4'] else recipe['classes'];self.drop=nn.Dropout(.5)
            if temple:self.head=nn.Linear(tokens*summary*dim,1 if dataset=='TUAB' else outputs)
            elif sleep:
                self.probe=constraints.LinearWithConstraint(summary*dim,64,max_norm=1);self.decoder=nn.TransformerDecoder(nn.TransformerDecoderLayer(64,4,256,activation=F.gelu,batch_first=False),4);self.cls=nn.Parameter(torch.rand(1,1,64)*.001);self.head=constraints.LinearWithConstraint(64,outputs,max_norm=.25)
            else:self.probe=constraints.LinearWithConstraint(summary*dim,16,max_norm=1);self.head=constraints.LinearWithConstraint(tokens*16,outputs,max_norm=.25)
        def forward(self,x,*,return_features=False):
            x=x/recipe['amplitude_divisor']
            if recipe['average_reference']:x=x-x.mean(dim=1,keepdim=True)
            if recipe['interpolation'] is not None:x=F.interpolate(x,size=recipe['samples'],mode=recipe['interpolation'])
            need(x.shape[1]==recipe['input_channels'] and x.shape[2]==recipe['samples'],'complete source-selected channel/time axis')
            if self.asf is not None:x=self.asf(x)
            if hasattr(self,'channel_scale'):x=x*self.channel_scale
            if recipe['adaptation']=='LP':self.target_encoder.eval()
            z=self.target_encoder(x,self.channel_ids.to(x));h=z.flatten(2)
            if temple:features=h.flatten(1)
            elif sleep:
                h=self.probe(self.drop(h));position=torch.arange(h.shape[1],device=h.device,dtype=h.dtype)[:,None];frequency=torch.exp(torch.arange(0,64,2,device=h.device,dtype=h.dtype)*(-__import__('math').log(10000.)/64));pos=torch.zeros(h.shape[1],64,device=h.device,dtype=h.dtype);pos[:,0::2]=torch.sin(position*frequency);pos[:,1::2]=torch.cos(position*frequency)
                if position_source is not None:pos=position_source.create_1d_absolute_sin_cos_embedding(h.shape[1],64).to(h)
                else:need(recipe['positional_policy']=='standard_sinusoid_prospective','sleep positional recipe cannot be unspecified')
                h=h+pos;h=torch.cat((self.cls.repeat(h.shape[0],1,1),h),dim=1).transpose(0,1);features=self.decoder(h,h)[0]
            else:features=self.probe(self.drop(h)).flatten(1)
            logit=self.head(features);return (logit,features,z) if return_features else logit
    return Adaptation()


def semantic_probabilities(logits,*,source_binary4=False):
    import torch
    if source_binary4:
        need(logits.ndim==2 and logits.shape[1]==4,'actual original four-logit binary source head');p=torch.softmax(logits,dim=-1)[:,1];return torch.stack((1-p,p),dim=1)
    if logits.shape[1]==1:
        p=torch.sigmoid(logits[:,0]);return torch.stack((1-p,p),dim=1)
    return torch.softmax(logits,dim=-1)


def fit_downstream(model,train_loader,validation_loader,recipe,*,validation_reduce,save_epoch,record_epoch):
    import torch
    fields(recipe,('epochs','max_lr','weight_decay','device','adaptation','source_binary4','monitor','refit_policy','selection_tie','qualification'),'complete fixed downstream fit/search recipe')
    need(recipe['selection_tie']=='earliest' and recipe['refit_policy']=='selected_epoch_no_refit','this explicit source-owned initial policy has earliest validation selection and no implicit refit');digest(recipe['qualification'])
    parameters=[p for p in model.parameters() if p.requires_grad];need(parameters,'actual trained head/encoder parameters');optimizer=torch.optim.AdamW(parameters,weight_decay=recipe['weight_decay']);scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=recipe['max_lr'],steps_per_epoch=len(train_loader),epochs=recipe['epochs'],pct_start=.2);model.to(recipe['device']);best=None;all_selections=[]
    for epoch in range(recipe['epochs']):
        model.train();loss_sum=0.;n=0
        for x,y in train_loader:
            x=x.to(recipe['device']);y=y.to(recipe['device']);optimizer.zero_grad(set_to_none=True);logit=model(x)
            loss=torch.nn.functional.binary_cross_entropy_with_logits(logit[:,0],y.float()) if logit.shape[1]==1 else torch.nn.functional.cross_entropy(logit,y.long());need(bool(torch.isfinite(loss)),'finite trained downstream objective');loss.backward();optimizer.step();scheduler.step();loss_sum+=float(loss.detach())*len(x);n+=len(x)
        model.eval()
        def predictions():
            with torch.no_grad():
                for x,y in validation_loader:
                    p=semantic_probabilities(model(x.to(recipe['device'])),source_binary4=recipe['source_binary4']).double().cpu()
                    for label,prob in zip(y.tolist(),p.tolist()):yield label,prob,1
        metric=validation_reduce(predictions());monitor=metric[recipe['monitor']];state=save_epoch(epoch,model,optimizer,scheduler);record={'epoch':epoch,'train_loss':loss_sum/n,'training_rows':n,'validation':metric,'state':state};record_epoch(record);all_selections.append(record)
        if monitor is not None and (best is None or monitor>best['monitor']):best={'epoch':epoch,'monitor':monitor,'state':state}
    need(best is not None,'no actual complete validation endpoint; no query fallback');return {'selected':best,'all_epoch_selections':all_selections,'optimizer_membership':[name for name,p in model.named_parameters() if p.requires_grad],'historical_parity':False}
