"""Fixed matched 8-frame temporal ablations; scientific worker only.

The released bidirectional M4 checkpoint is held fixed. The static network is
its shift-disabled ablation, not an independently static-trained model.
"""
from .core import need
PERMUTATIONS=((2,5,0,7,1,6,3,4),(7,2,5,0,6,3,1,4),(1,6,3,5,0,7,4,2),(4,0,7,2,5,1,6,3),
              (3,7,1,6,2,4,0,5),(6,1,4,0,7,2,5,3),(5,3,6,1,4,0,7,2),(0,4,2,6,1,5,7,3),
              (2,6,4,1,7,3,0,5),(5,0,3,7,2,6,4,1))
def sample_indices(timestamps):
    import math
    need(len(timestamps)>=45 and all(type(t)in(int,float)and math.isfinite(t)for t in timestamps),"Original finite timestamp sequence")
    need(timestamps[0]>=0 and timestamps[-1]<3 and all(a<b for a,b in zip(timestamps,timestamps[1:])),"Source-clock frame extent")
    need(timestamps[0]<=1/15 and timestamps[-1]>=3-1/15,"Full silent 3-second video")
    chosen=[min(range(len(timestamps)),key=lambda i:(abs(timestamps[i]-(j+.5)*3/8),i))for j in range(8)]
    need(len(set(chosen))==8,"Distinct source frames")
    return chosen
def network(checkpoint,temporal):
    import torch
    from torchvision.models import resnet50
    model=resnet50(weights=None)
    if temporal:
        from .temporal_shift import make_temporal_shift
        make_temporal_shift(model,n_segment=8,n_div=8,place="blockres",temporal_pool=False)
    state={}
    for k,v in checkpoint.items():
        k=k.removeprefix("module.").removeprefix("base_model.")
        if k.startswith(("new_fc.","fc.")):continue
        if not temporal:k=k.replace(".conv1.net.",".conv1.")
        state[k]=v
    model.fc=torch.nn.Identity()
    model.load_state_dict(state,strict=True);model.eval()
    return model
def encode(model,frames):
    import torch
    captured={};handles=[]
    try:
        for layer in ("layer1","layer2","layer3","layer4"):
            handles.append(getattr(model,layer).register_forward_hook(
                lambda module,args,value,layer=layer:captured.__setitem__(layer,value.mean((-1,-2)).detach().cpu().numpy())))
        with torch.inference_mode():model(frames)
        return captured
    finally:
        for handle in handles:handle.remove()
def extract(pil_frames,timestamps,checkpoint):
    import numpy as np
    import torch
    from torchvision.transforms import Compose,Resize,CenterCrop,ToTensor,Normalize,InterpolationMode
    selected=sample_indices(timestamps)
    transform=Compose([Resize(256,interpolation=InterpolationMode.BILINEAR),CenterCrop(224),ToTensor(),
                       Normalize((.485,.456,.406),(.229,.224,.225))])
    frames=torch.stack([transform(pil_frames[i].convert("RGB"))for i in selected])
    static=network(checkpoint,False);dynamic=network(checkpoint,True)
    plain=encode(static,frames);ordered=encode(dynamic,frames);reverse=encode(dynamic,frames.flip(0))
    shuffled=[encode(dynamic,frames[list(p)])for p in PERMUTATIONS]
    return {layer:{"static_center":plain[layer][3],"static_mean":plain[layer].mean(0),
            "static_orderless":np.concatenate((plain[layer].mean(0),plain[layer].std(0))),
            "dynamic":ordered[layer].mean(0),"reverse":reverse[layer].mean(0),
            "shuffled":np.stack([s[layer].mean(0)for s in shuffled]).mean(0)}
            for layer in plain},selected

