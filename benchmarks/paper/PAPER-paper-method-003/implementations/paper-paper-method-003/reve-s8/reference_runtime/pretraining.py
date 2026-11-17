"""Concrete prospective REVE reconstruction producer with explicit objective profiles.

The exact retained StableAdamW implementation is used. Selected source-derived
prospective runs are separately named, and historical run-record rows remain
gated. Every mask and both actual decoder outputs are available to the oracle.
"""
from types import SimpleNamespace as NS
import torch
from .catalog import need
from .engine import seed_all,state_copy,state_digest
from .vendor_reve.mae import MAE
from .vendor_reve.encoder import FourierEmb4D

def make_mae(size,ablation,geometry,samples,purpose):
    d,depth,h,f={'Small':(512,4,8,4),'Base':(512,22,8,4),'Large':(1216,22,19,5)}[size]
    paper=purpose=='R-paper';d=1250 if paper and size=='Large' else d
    back=lambda dim,layers,heads:NS(embed_dim=dim,depth=layers,heads=heads,head_dim=64,mlp_dim_ratio=8/3 if paper else 2.66,use_geglu=ablation.get('component')!='GELU_RMSNorm')
    c=NS(encoder=NS(transformer=back(d,depth,h),freqs=f,patch_size=200,patch_overlap=20,noise_ratio=0. if ablation.get('component')=='remove_position_noise' else (.25 if paper else .0025)),decoder=NS(transformer=back(512,4,8),masking=NS(ratio=ablation.get('ratio_percent',55)/100)),token_avg=ablation.get('loss','primary_and_secondary')!='primary_only',token_avg_lambda=.1,init={'init_method':'full_megatron','init_std':.02,'init_cutoff_factor':3.,'hidden_size':d,'num_hidden_layers':depth+4,'init_cls':True})
    model=MAE(c);model._paper=paper;model._native=purpose=='R-native';model._position_scale=1. if paper else .01
    if paper:
        for name,layer in model.named_modules():
            if isinstance(layer,torch.nn.Linear) and name not in ('to_pixels','cls_to_pixels.2'):layer.register_parameter('bias',None)
        from .models import PaperTimeShift
        model.encoder.fourier4d=PaperTimeShift(model.encoder.fourier4d);model.encoder.mlp4d=PaperTimeShift(model.encoder.mlp4d)
    component=ablation.get('component','base')
    if component=='MLP4D_literal_unqualified':
        from .models import ZeroPositions
        model.encoder.fourier4d=ZeroPositions(d)
    if component=='learnable_PE':
        from .models import LearnedPatchPositions,ZeroPositions
        model.encoder.fourier4d=LearnedPatchPositions(d,torch.as_tensor(geometry,dtype=torch.float32),(samples-200)//180+1,model._position_scale);model.encoder.mlp4d=ZeroPositions(d);model.encoder.noise_ratio=0.
    if component=='GEGLU_LayerNorm':
        from .vendor_reve.backbone import RMSNorm
        def replace(parent):
            for name,child in list(parent.named_children()):
                if isinstance(child,RMSNorm):setattr(parent,name,torch.nn.LayerNorm(child.weight.numel(),eps=child.eps,bias=False))
                else:replace(child)
        replace(model)
    return model

def masks(b,c,p,geometry,ablation,generator,device,native=False):
    """Explicit prospective channel-major blocks; never the unresolved native order."""
    ratio=ablation.get('ratio_percent',55)/100;n=c*p;k=int(n*ratio);need(0<k<n,'nonempty mask and complement')
    masked=[];visible=[]
    if native:
        from .vendor_reve.native_masks import create_block_masks
        for _ in range(b):
            if ablation.get('masking','block')=='random':
                order=torch.rand(c*p,device=device).argsort().tolist();mask,keep=order[:k],order[k:]
            else:
                mask,keep=create_block_masks(c,ratio,.03,1 if ablation.get('component')=='remove_temporal_block' else 3,p,geometry.detach().cpu().numpy()/100.,0. if ablation.get('component')=='remove_dropout_block' else .1,.04);mask=mask.tolist();keep=keep.tolist()
            need(mask and keep and len(mask)==len(set(mask)) and not set(mask)&set(keep),'literal native mask support');masked.append(mask);visible.append(keep)
        return masked,visible
    for _ in range(b):
        order=torch.randperm(n,generator=generator).tolist();chosen=[]
        if ablation.get('masking','block')=='random':chosen=order[:k]
        else:
            for center in order:
                channel,time=divmod(center,p)
                # geometry is centimeters; temporal radius is THREE PATCH INDICES.
                near=torch.linalg.vector_norm(geometry-geometry[channel],dim=-1)<=3.
                for ch in range(c):
                    if not bool(near[ch]):continue
                    for tt in range(p):
                        if (ablation.get('component')=='remove_temporal_block' and tt!=time) or (ablation.get('component')!='remove_temporal_block' and abs(tt-time)>3):continue
                        token=ch*p+tt
                        if token not in chosen:chosen.append(token)
                        if len(chosen)==k:break
                    if len(chosen)==k:break
                if len(chosen)==k:break
        need(len(chosen)==k,'exact mask cardinality');remaining=[i for i in range(n) if i not in set(chosen)]
        if ablation.get('component')!='remove_dropout_block' and int(c*.1)>0:
            # Drop a fixed ceil10% channel set only from encoder visibility;
            # dropped tokens are not silently added as reconstruction targets.
            take=int(c*.1);drop=[]
            for anchor in torch.randperm(c,generator=generator).tolist():
                near=torch.linalg.vector_norm(geometry-geometry[anchor],dim=-1)<=4.
                for ch in range(c):
                    if bool(near[ch]) and ch not in drop:drop.append(ch)
                    if len(drop)==take:break
                if len(drop)==take:break
            remaining=[i for i in remaining if i//p not in set(drop)]
        need(remaining,'nonempty encoder visibility');masked.append(chosen);visible.append(remaining)
    # Ragged visibility is handled per example, never padded into an objective.
    return masked,visible

def reconstruct(m,x,positions,masked,visible,profile):
    need(profile in ('R-paper.patch_L1','R-native.sample_L1','P-sample_mean'),'explicit loss profile')
    outputs=[];losses=[]
    for i,(mask,keep) in enumerate(zip(masked,visible)):
        sample=x[i:i+1];pos=positions[i:i+1].clone()*m._position_scale;enc=m.encoder
        patches=sample.unfold(2,200,180).reshape(1,-1,200);n=patches.shape[1];p=(sample.shape[-1]-200)//180+1
        if m.training:pos=pos+torch.randn_like(pos)*enc.noise_ratio
        pe=enc.ln(enc.fourier4d(FourierEmb4D.add_time_patch(pos,p))+enc.mlp4d(FourierEmb4D.add_time_patch(pos,p)))
        tokens=enc.to_patch_embedding(patches)+pe;mi=torch.tensor(mask,device=x.device);vi=torch.tensor(keep,device=x.device)
        layers=enc.transformer(tokens[:,vi],True);z=layers[-1];dp=m.pos_enc_to_dec(pe)
        dec=torch.zeros(1,n,m.decoder.dim,device=x.device);dec[:,vi]=m.enc_to_dec(z)+dp[:,vi];dec[:,mi]=m.mask_token+dp[:,mi]
        primary=m.to_pixels(m.decoder(dec)[:,mi]);target=patches[:,mi];components={'primary':primary}
        if m.token_avg and m.training:
            all_layers=torch.cat(layers[1:] if m._paper else layers,1);q=m.cls_query_token;context=((q@all_layers.transpose(-1,-2)/enc.embed_dim**.5).softmax(-1)@all_layers).squeeze(1)
            # The retained native MAE adds decoder-width positions to encoder-width
            # context. Its Large defaults are incompatible; do not silently fix
            # that native result. Paper/prospective branches use encoder PE.
            if m._native:need(context.shape[-1]==dp.shape[-1],'retained native Large secondary branch has incompatible encoder/decoder widths; source discrepancy requires explicit unavailable outcome')
            secondary_positions=dp[:,mi] if m._native else pe[:,mi]
            components['secondary']=m.cls_to_pixels(context[:,None,:]+secondary_positions)
        vals={name:(pred-target).abs().sum()/len(mask)/(1 if profile=='R-paper.patch_L1' else 200) for name,pred in components.items()}
        loss=vals['primary']+.1*vals.get('secondary',0.);losses.append(loss)
        outputs.append({'mask':mask,'visible':keep,'target':target.detach().cpu(),'components':{k:v.detach().cpu() for k,v in components.items()},'sums':{k:float((v-target).abs().sum().detach().cpu()) for k,v in components.items()},'patches':len(mask),'samples':len(mask)*200})
    # Current masks have equal counts; this is exactly pooled_mask_v1.
    return torch.stack(losses).mean(),outputs

def fit_pretraining(c,view,profile,trace_limit,writer):
    r=c['recipe'];need(r['base'].startswith('REVE-'),'REVE pretraining producer')
    native=c['purpose']=='R-native';peak=.001 if native else .00024;betas=(.92,.999) if native else (.9,.95)
    epochs=200 if native else 10;batch=300 if native else (4096 if c['purpose']=='R-paper' else 8)
    cycle=view.number_batches(batch);total=epochs*cycle;need(total<=trace_limit and len(writer.names)==total,'complete precommitted trace/loss-product capacity before fitting')
    seed_all(c['seed']);geometry=view.geometry();m=make_mae(r['base'].split('-')[1],c['ablation'],geometry,2000,c['purpose']).to(c['device']);m.train()
    from .vendor_reve.stable_adamw import StableAdamW
    optimizer=StableAdamW(m.parameters(),lr=peak,betas=betas,eps=1e-9,weight_decay=.01)
    generator=torch.Generator().manual_seed(c['seed']);trace=[];step=0
    for epoch in range(epochs):
        for manifest,x,positions_array,ids in view.batches(generator,batch):
            z=torch.as_tensor(x,dtype=torch.float32,device=c['device']);positions=torch.as_tensor(positions_array,dtype=torch.float32,device=c['device']);masked=[];visible=[]
            for i in range(len(z)):
                mi,vi=masks(1,z.shape[1],(z.shape[2]-200)//180+1,positions[i],c['ablation'],generator,z.device,native=native);masked.extend(mi);visible.extend(vi)
            if native:
                warm=int(.1*cycle);decay=int(.1*cycle);plateau=cycle-warm-decay;need(warm>0 and decay>0,'native scheduler integer cycle requires qualified extent');k=step%cycle;start_lr=1e-5 if step<cycle else 1e-6
                lr=start_lr+(peak-start_lr)*k/warm if k<warm else (peak if k<warm+plateau else peak-(peak-1e-6)*(k-warm-plateau)/decay)
            else:
                fraction=step/max(1,total-1);scale=max(.01,fraction/.1) if fraction<.1 else (1. if fraction<.9 else max(.01,1-.99*(fraction-.9)/.1));lr=peak*(m.encoder.embed_dim/512)**(-.90)*scale
            for group in optimizer.param_groups:group['lr']=lr
            before=state_digest(m.state_dict());optimizer.zero_grad(set_to_none=True);loss,outputs=reconstruct(m,z,positions,masked,visible,profile);need(torch.isfinite(loss).item(),'finite actual reconstruction');loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),5.);optimizer.step()
            from .step_trace import step_row
            trace.append(step_row(before,m,step,step,step+1,lr,ids,manifest,z.shape[1]*((z.shape[-1]-200)//180+1),z.shape[1]*z.shape[-1]))
            writer.capture(outputs,ids,float(loss.detach().cpu()),profile,manifest);step+=1
    writer.close()
    from .checkpoint import capture
    training_tensors,training_tree=capture(optimizer,generator,c['device'])
    return {'weights':state_copy(m),'training_tensors':training_tensors,'training_tree':training_tree,'trace':trace,'recipe':'S7-source-defaults-StableAdamW-v1' if native else 'S7-paper-derived-prospective-StableAdamW-v1','historical_qualified':False}
