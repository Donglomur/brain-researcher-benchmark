"""R1 independently authored concrete tensor graph and AdamW, no nn model or RNG."""
import hashlib
import math
from .contract import canonical, seed_base, CounterStream


def torch_checked(environment):
    import torch
    if torch.__version__ != environment['torch_version']:
        raise ValueError('torch environment differs')
    if environment['device']=='cuda' and not torch.cuda.is_available():
        raise ValueError('qualified CUDA unavailable')
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    torch.backends.cudnn.allow_tf32=False
    torch.backends.cuda.matmul.allow_tf32=False
    return torch


def shapes(channels,width):
    out={'stem.weight':(width,2*channels,25),'stem.bias':(width,)}
    for k in range(3):
        for conv in (1,2):
            out[f'blocks.{k}.conv{conv}.weight']=(width,width,9)
            out[f'blocks.{k}.conv{conv}.bias']=(width,)
    out.update({'readout1.weight':(width,20*width+6+48*channels),'readout1.bias':(width,),
                'readout2.weight':(1,width),'readout2.bias':(1,)})
    return out


def initialize(np,torch,scope,channels,width,device,budget,stream):
    params={}
    for name,shape in shapes(channels,width).items():
        budget.tick(); a=np.zeros(shape,dtype=np.float32)
        if name.endswith('.weight'):
            fan_in=shape[1]*(shape[2] if len(shape)==3 else 1)
            fan_out=shape[0]*(shape[2] if len(shape)==3 else 1)
            bound=math.sqrt(6.0/(fan_in+fan_out))
            flat=a.reshape(-1)
            for i in range(len(flat)):
                if i%4096==0: budget.tick()
                flat[i]=(2*stream.uniform(name,i)-1)*bound
        params[name]=torch.tensor(a,dtype=torch.float32,device=device,requires_grad=True)
        budget.tick()
    return params


def dropout(np,torch,x,scope,width,epoch,ids,layer,budget,stream):
    mask=np.empty(tuple(x.shape),np.float32)
    if len(x.shape)==3:
        for b,event in enumerate(ids):
            budget.tick()
            for f in range(x.shape[1]):
                for t in range(x.shape[2]): mask[b,f,t]=1/.9 if stream.uniform(epoch,event,layer,f,t)>=.1 else 0.0
    else:
        for b,event in enumerate(ids):
            for f in range(x.shape[1]): mask[b,f]=1/.9 if stream.uniform(epoch,event,layer,f,-1)>=.1 else 0.0
    y=x*torch.tensor(mask,dtype=torch.float32,device=x.device)
    budget.tick(); return y


def gelu(torch,x):
    return .5*x*(1+torch.erf(x/math.sqrt(2.0)))


def graph(np,torch,params,inputs,structural,scope,width,budget,epoch=None,ids=None,streams=None):
    fn=torch.nn.functional
    x=gelu(torch,fn.conv1d(inputs,params['stem.weight'],params['stem.bias'],padding=12))
    x=fn.avg_pool1d(x,kernel_size=5,stride=5)
    if x.shape[-1]!=1000: raise ValueError('full temporal axis lost')
    for k,dilation in enumerate((1,4,16)):
        budget.tick(); prefix=f'blocks.{k}'
        branch=fn.conv1d(x,params[prefix+'.conv1.weight'],params[prefix+'.conv1.bias'],padding=4*dilation,dilation=dilation)
        branch=gelu(torch,branch)
        if epoch is not None: branch=dropout(np,torch,branch,scope,width,epoch,ids,prefix+'.dropout',budget,streams['dropout'])
        branch=fn.conv1d(branch,params[prefix+'.conv2.weight'],params[prefix+'.conv2.bias'],padding=4*dilation,dilation=dilation)
        x=gelu(torch,(x+branch)/math.sqrt(2.0))
    pooled=[]
    for k in range(10):
        block=x[:,:,k*100:(k+1)*100]
        pooled.extend((block.mean(dim=2),block.max(dim=2).values))
    z=torch.cat(pooled+[structural],dim=1)
    z=gelu(torch,fn.linear(z,params['readout1.weight'],params['readout1.bias']))
    if epoch is not None: z=dropout(np,torch,z,scope,width,epoch,ids,'readout.dropout',budget,streams['dropout'])
    result=fn.linear(z,params['readout2.weight'],params['readout2.bias']).reshape(-1)
    budget.tick(); return result


def lr_at(step,total):
    if not 1<=step<=total: raise ValueError('optimizer step identity')
    return .001 if total==1 else 1e-5+(.001-1e-5)*(1+math.cos(math.pi*(step-1)/(total-1)))/2


def adamw_step(torch,params,m,v,step,total,decay,budget):
    # Sum full gradient norm in float64, then round clipped gradients/updates in f32.
    norm2=torch.zeros((),dtype=torch.float64,device=next(iter(params.values())).device)
    for name,p in params.items():
        if p.grad is None: raise ValueError('missing parameter gradient')
        if not bool(torch.isfinite(p.grad).all()): raise ValueError('nonfinite gradient')
        norm2+=torch.sum(p.grad.to(torch.float64)**2,dtype=torch.float64)
    norm=float(torch.sqrt(norm2).item()); budget.tick()
    clip=min(1.0,1.0/norm) if norm>0 else 1.0
    lr=lr_at(step,total)
    with torch.no_grad():
        for name,p in params.items():
            g=p.grad*clip
            m[name].mul_(.9).add_(g,alpha=.1)
            v[name].mul_(.999).addcmul_(g,g,value=.001)
            mh=m[name]/(1-.9**step); vh=v[name]/(1-.999**step)
            wd=0.0 if name.endswith('.bias') else decay
            p.mul_(1-lr*wd).addcdiv_(mh,torch.sqrt(vh)+1e-8,value=-lr)
            if not bool(torch.isfinite(p).all()): raise ValueError('nonfinite updated parameter')
            p.grad=None
    budget.tick()
    return {'step':step,'lr':lr,'unclipped_norm':norm,'clip':clip}


def train(np,features,mask,y,scope,config,budget):
    torch=torch_checked(scope['environment']); device=scope['environment']['device']
    n,c,_=features['wave'].shape; width=config['width']; ids=scope['training_ids']
    prefix_upper=1024+12*(len(scope['base_generation'])+sum(len(x) for x in ids)+len(ids)*8+len(scope['training_days'])*32)
    budget.reserve('counter-prefixes',serialized_bytes=prefix_upper*3,allocation_bytes=prefix_upper*12,
                   live_bytes=prefix_upper*12,elements=prefix_upper*3,work=prefix_upper*3)
    streams={name:CounterStream(seed_base(scope,width,name)) for name in ('weight','shuffle','dropout')}
    params=initialize(np,torch,scope,c,width,device,budget,streams['weight'])
    m={k:torch.zeros_like(v) for k,v in params.items()}; v={k:torch.zeros_like(v) for k,v in params.items()}
    batch_size=min(32,n); total=config['epochs']*((n+batch_size-1)//batch_size)
    step=0; transcript=hashlib.sha256(); updates=[]
    budget.reserve('complete-step-records',allocation_bytes=total*(2048+128*batch_size),
                   live_bytes=total*(2048+128*batch_size),elements=total*128,work=total*128)
    budget.begin('temporal_updates',total)
    initial={k:hashlib.sha256(a.detach().cpu().numpy().tobytes(order='C')).hexdigest() for k,a in params.items()}
    for epoch in range(config['epochs']):
        budget.tick()
        order=sorted(range(n),key=lambda i:(streams['shuffle'].digest(epoch,ids[i]),ids[i]))
        for start in range(0,n,batch_size):
            budget.enter('temporal_updates')
            chosen=order[start:start+batch_size]; batch_ids=[ids[i] for i in chosen]
            a=np.concatenate((features['wave'][chosen],mask[chosen].astype(np.float64)),axis=1).astype(np.float32)
            inputs=torch.tensor(a,dtype=torch.float32,device=device)
            extra=torch.tensor(features['structural'][chosen],dtype=torch.float32,device=device)
            target=torch.tensor(y[chosen],dtype=torch.float64,device=device)
            pred=graph(np,torch,params,inputs,extra,scope,width,budget,epoch,batch_ids,streams)
            # Cast before subtraction/squaring to make the selected loss reduction f64.
            loss=torch.mean((pred.to(torch.float64)-target.to(torch.float64))**2,dtype=torch.float64)
            if not bool(torch.isfinite(loss)): budget.fail('nonfinite temporal loss')
            loss.backward(); budget.tick(); step+=1
            update=adamw_step(torch,params,m,v,step,total,config['decay'],budget)
            record={'epoch':epoch,'step':step,'ids':batch_ids,'update':update}
            updates.append(record); transcript.update(canonical(record))
            budget.complete('temporal_updates')
            del loss,pred,inputs,extra,target,a
    def export(items): return {k:a.detach().cpu().numpy().copy() for k,a in items.items()}
    result={'parameters':export(params),'adam_first':export(m),'adam_second':export(v),
            'completed_epochs':config['epochs'],'optimizer_steps':step,'planned_steps':total,
            'batch_size':batch_size,'batch_transcript_sha256':transcript.hexdigest(),
            'initial_parameter_sha256':initial,'seed_contract':'SEED_ABI_V1','updates':updates}
    if step!=total: budget.fail('temporal schedule incomplete')
    budget.tick(); return result


def infer(np,features,mask,model,scope,config,budget):
    torch=torch_checked(scope['environment']); device=scope['environment']['device']
    params={k:torch.tensor(a,dtype=torch.float32,device=device) for k,a in model['parameters'].items()}
    n=len(features['wave']); out=np.empty(n,np.float64)
    with torch.no_grad():
        for start in range(0,n,32):
            budget.tick(); stop=min(n,start+32)
            a=np.concatenate((features['wave'][start:stop],mask[start:stop].astype(np.float64)),axis=1).astype(np.float32)
            x=torch.tensor(a,dtype=torch.float32,device=device)
            extra=torch.tensor(features['structural'][start:stop],dtype=torch.float32,device=device)
            z=graph(np,torch,params,x,extra,scope,config['width'],budget)
            out[start:stop]=z.detach().cpu().numpy().astype(np.float64)
            del a,x,extra,z
    budget.tick(); return out
