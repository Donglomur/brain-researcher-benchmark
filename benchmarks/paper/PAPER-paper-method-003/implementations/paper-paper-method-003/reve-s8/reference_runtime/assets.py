"""Closed passive pretrained tensor adapters; never torch.load or remote code."""
import torch
from .catalog import need

def adapt_asset(tensors,base,model):
    """Input is an operator-qualified safetensors dictionary with asset. prefix."""
    raw={k[len('asset.'):]:v for k,v in tensors.items() if k.startswith('asset.')};need(raw,'qualified passive original asset tensor bank');out={}
    for name,value in raw.items():
        if base.startswith('REVE-'):
            if name=='cls_query_token':key='classifier.cls_query_token'
            elif name.startswith('encoder.'):key='classifier.encoder.'+name[8:]
            else:key='classifier.encoder.'+name
        elif base=='CBraMod':
            if name.startswith('proj_out.'):continue
            key='encoder.'+name
        elif base=='BIOT':
            if name.startswith(('classifier.','prediction.')):continue
            key=name if name.startswith('biot.') else 'biot.'+name
        elif base.startswith('LaBraM-'):
            if name.startswith('head.'):continue
            key=name
            if key=='time_embed' and value.shape!=model.state_dict()[key].shape:
                need(value.shape[1]==16 and model.state_dict()[key].shape[1]>16,'only declared full-epoch temporal interpolation')
                value=torch.nn.functional.interpolate(value.transpose(1,2),size=model.state_dict()[key].shape[1],mode='linear',align_corners=False).transpose(1,2).contiguous()
        else:raise ValueError('method has no fixed pretrained asset adapter')
        need(key not in out,'duplicate adapted tensor');out[key]=value
    return out
