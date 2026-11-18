"""Operator reference inference adapter using original model/generator source.
Never run during construction. Only the target-free generation output is retained;
the original helper's dummy-image selection is discarded. No new decoder trained here.
"""
from pathlib import Path
import os,sys,io
import numpy as np
import delivery_io as d,array_io,protocol as p,native_bridge

def predict(view_root,view_pin,checkpoint,checkpoint_pin,cache_manifest,output,max_bytes,cache_root):
 view_root=Path(view_root);view=d.json_file(view_root/'VIEW.json',30000000,view_pin);case=view['case'];d.need(case['case_id']in p.CASES,'Full panel case')
 import prepare
 d.need(view['generation']==prepare.generation(),'Current source generation');native_bridge.check_source();d.check_pin(checkpoint_pin,10000000000)
 # All network isolation and exact cache closure are executor obligations, not proved by env vars.
 d.need(cache_manifest.get('offline_cache_complete')is True and cache_manifest.get('source_commit')=='2a3943ff5b619db6f85f16a5e7ff1331d25def55','Authenticated native cache closure required')
 for r in cache_manifest['files']:d.read(d.resolve(cache_root,r['path']),r['bytes'],{k:r[k]for k in('bytes','sha256')},retain=False)
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',HF_HOME=str(d.resolve(cache_root,cache_manifest['hf_home'])),TORCH_HOME=str(d.resolve(cache_root,cache_manifest['torch_home'])))
 import torch
 sys.path.insert(0,str(native_bridge.source_root()/'src'));from models import MindSingle,Clipper
 import data,utils
 from diffusers import VersatileDiffusionDualGuidedPipeline,UniPCMultistepScheduler
 from diffusers.models import DualTransformer2DModel
 utils.seed_everything(42);device='cuda';subject=case['subject'];model=MindSingle(in_dim=8192,out_dim_image=257*768,out_dim_text=77*768,h=2048,n_blocks=4,subj_list=[subject])
 with d.verified_stream(checkpoint,checkpoint_pin)as f:state=torch.load(f,map_location='cpu')
 incompat=model.load_state_dict(state['model_state_dict'],strict=False);d.need(not incompat.missing_keys,'All target decoder keys present; unrelated source builders may remain unexpected');model.eval().requires_grad_(False).to(device)
 pipe=VersatileDiffusionDualGuidedPipeline.from_pretrained(str(d.resolve(cache_root,cache_manifest['vd_path'])),local_files_only=True)
 pipe.scheduler=UniPCMultistepScheduler.from_pretrained(str(d.resolve(cache_root,cache_manifest['vd_path'])),subfolder='scheduler',local_files_only=True)
 pipe.image_unet.eval().requires_grad_(False).to(device);pipe.vae.eval().requires_grad_(False).to(device)
 for module in pipe.image_unet.modules():
  if isinstance(module,DualTransformer2DModel):module.mix_ratio=.5;module.condition_lengths=[77,257];module.transformer_index_for_condition=[1,0]
 import models as native_models
 original_load=native_models.clip.load
 local_clip=d.resolve(cache_root,cache_manifest['openai_clip_file']);d.need(any(r['path']==cache_manifest['openai_clip_file']for r in cache_manifest['files']),'OpenAI CLIP exact cache member')
 native_models.clip.load=lambda variant,device:original_load(str(local_clip),device=device)
 try:clip=Clipper('ViT-L/14',hidden_state=True,norm_embs=True,device=device)
 finally:native_models.clip.load=original_load
 out=Path(output);out.mkdir(parents=True,exist_ok=False);files={r['path']:r for r in view['files']};chunks=[];used=0
 for start,end in p.chunks():
  block=[]
  for q in case['query_ids'][start:end]:
   r=files[f'query/{q}.npy'];raw=d.read(view_root/r['path'],10000000,{k:r[k]for k in('bytes','sha256')});voxel=np.load(io.BytesIO(raw),allow_pickle=False);d.need(voxel.ndim==2 and voxel.shape[0]==3 and np.isfinite(voxel).all(),'Finite three native responses')
   # Native data.py pools each repeated response first, then recon.py averages.
   tensor=data.pool_voxels(torch.from_numpy(voxel)[None],8192,'max').mean(1).float().to(device)
   with torch.no_grad():_,draws,_,_=utils.reconstruction(torch.zeros(1,3,425,425,device=device),tensor,model,clip,pipe.image_unet,pipe.vae,pipe.scheduler,num_inference_steps=20,recons_per_sample=8,guidance_scale=5,img2img_strength=1,seed=42,plotting=False,device=device,mem_efficient=False)
   block.append(draws[0].cpu().numpy())
  name=f'draws_{start:04d}.npy';pin=array_io.write(out/name,np.stack(block),max_bytes-used);used+=pin['bytes'];chunks.append({'path':case['case_id']+'/'+name,**pin})
 row={'case_id':case['case_id'],'query_ids':case['query_ids'],'chunks':chunks};d.put(out/'CASE.json',row,1000000);return row

if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser()
 for n in('view','view-pin','checkpoint','checkpoint-pin','cache','cache-pin','output'):a.add_argument('--'+n,required=True)
 a.add_argument('--max-output-bytes',required=True,type=int);z=a.parse_args()
 predict(z.view,d.json_file(z.view_pin),z.checkpoint,d.json_file(z.checkpoint_pin),d.json_file(z.cache,1000000,d.json_file(z.cache_pin)),z.output,z.max_output_bytes,Path(z.cache).parent)
