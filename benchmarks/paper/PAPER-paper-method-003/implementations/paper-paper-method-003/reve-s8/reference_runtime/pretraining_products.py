"""Concrete complete per-update loss objects and passive pretraining state."""
from .catalog import need,canonical,identity
from .step_trace import profile,rank_exposure

class ReconstructionWriter:
    def __init__(self,io,c,manifest):
        self.io=io;self.c=c;self.manifest=manifest;self.names=[n for n,s in io.r['expected_outputs'].items() if s['kind']=='loss_trace'];self.index=0
    def capture(self,outputs,rows,loss,objective,manifest):
        need(self.index<len(self.names),'every update must have a declared loss product before writing');name=self.names[self.index];step=self.index;components={};objects=[];masks=[]
        for local,(record,row) in enumerate(zip(outputs,rows)):
            example=manifest['events'][row]
            for component,pred in record['components'].items():
                a=pred[0].numpy().astype('<f4');pin=self.io.write_array(f'{name}.{component}.{local}.npy',a);objects.append(pin)
                target=f'{manifest["support"]}|{example}|{component}'
                entry={'id':example,'prediction':{'object':pin,'shape':list(a.shape),'dtype':'<f4'},'mask':record['mask'],'target':target};components.setdefault(component,[]).append(entry);masks.append({'component':component,'example':example,'mask':record['mask'],'target':target})
        # Collector's mask identity uses component-major order.
        order=[{'name':k,'examples':v} for k,v in components.items()];masks=[{'component':component['name'],'example':e['id'],'mask':e['mask'],'target':e['target']} for component in order for e in component['examples']]
        d={'objective_profile':objective,'batch_reduction':'pooled_mask_v1','components':order,'alpha':1.,'lambda':.1 if 'secondary' in components else 0.,'phase':'train','secondary_enabled':'secondary' in components,'backpropagated_scalar':loss,'mask_identity':identity(masks),'optimizer_updates':{'before':step,'after':step+1},'producer':identity(self.io.r),'rank':0,'accumulation':{'index':0,'steps':1},'support':manifest['support']}
        need(self.io.r['expected_outputs'][name]['objective_profile']==objective,'selected original loss profile');self.io.emit(name,d,objects);self.index+=1
    def close(self):need(self.index==len(self.names),'no omitted required loss update')

def emit_pretraining(io,c,view,result):
    import torch
    from reference_actor import emit_state
    for name,s in io.r['expected_outputs'].items():
        if s['kind']=='loss_trace':continue # Already emitted by the fixed writer at the actual update.
        if s['kind']=='state':
            tensors={**{'pretrain.'+k:v for k,v in result['weights'].items()},**result['training_tensors']}
            emit_state(io,name,c,tensors,[],None,list(tensors),[view.summary['support']],None,{'profile':result['recipe'],'channel_ids':view.summary['channel_ids'],'steps':len(result['trace']),'training_tree':result['training_tree']})
        elif s['kind']=='schedule_trace':
            pin=io.write(name+'.json',canonical(result['trace']));io.emit(name,{'profile':profile(io.r,c,result['trace']),'steps':pin,'resume':None,'rank_exposure':rank_exposure(result['trace']),'producer':identity(io.r)},[pin])
        else:raise ValueError('pretraining output kind not implemented')
