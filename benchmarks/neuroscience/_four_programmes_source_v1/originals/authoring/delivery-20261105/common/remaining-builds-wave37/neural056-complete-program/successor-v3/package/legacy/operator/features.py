"""UNRUN fixed image-representation extraction. Performs inference if invoked.
No automatic checkpoint download: exact checkpoint/extractor SHA must be bound
before any actual extraction, model fitting or outer assessment.
"""
import argparse,sys,json,io,zipfile,warnings
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import need,digest,canonical,hash_ok
from array_io import capture,identity,metadata,fresh_output
from source_bindings import checked_metadata,check_source_asset

def low_level(image):
 from PIL import Image
 return np.asarray(image.convert('RGB').resize((16,16),Image.Resampling.BILINEAR),dtype=np.float32).reshape(-1)/255

def extract(images_train,images_test,meta,acquisition,checkpoint,binding,out):
 # Dependencies are loaded only after invocation; this source is not executed at construction.
 import torch,torchvision
 from PIL import Image
 from torchvision.transforms import Compose,Resize,ToTensor,Normalize
 fresh_output(out);b=metadata(binding);need(b['schema']=='neural056_checkpoint_v1' and hash_ok(b['sha256']) and type(b['bytes'])is int and b['bytes']<=260_000_000,'Reviewed checkpoint identity required')
 raw=capture(checkpoint,260_000_000);need(identity(raw)=={'bytes':b['bytes'],'sha256':b['sha256']},'Exact checkpointbytes');torch.set_num_threads(1);torch.use_deterministic_algorithms(True);model=torchvision.models.alexnet(weights=None);model.load_state_dict(torch.load(io.BytesIO(raw),map_location='cpu',weights_only=True));model.eval();del raw
 transform=Compose([Resize((224,224)),ToTensor(),Normalize([.485,.456,.406],[.229,.224,.225])]);m=checked_metadata(metadata(meta,2_000_000));assets=metadata(acquisition);out=Path(out);out.mkdir();records={};Image.MAX_IMAGE_PIXELS=20_000_000
 for part,path in [('train',images_train),('test',images_test)]:
  key='training_images' if part=='train' else 'test_images';pin=next(r for r in assets['assets'] if r['asset_id']==key);check_source_asset(pin,key);raw=capture(path,pin['bytes']);need(identity(raw)=={'bytes':pin['bytes'],'sha256':pin['sha256']},'Full original imagearchive')
  fm=np.empty((len(m[part+'_img_files']),4096),dtype=np.float32);ll=np.empty((len(fm),768),dtype=np.float32)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   names={};wanted=set(m[part+'_img_files'])
   for r in z.infolist():
    if r.is_dir():continue
    base=Path(r.filename).name
    if base in wanted:
     need(base not in names and 0<r.file_size<=10_000_000,'Unique bounded imagebasename');names[base]=r
   need(set(names)==set(m[part+'_img_files']),'All source image identities')
   for i,name in enumerate(m[part+'_img_files']):
    with warnings.catch_warnings():
     warnings.simplefilter('error',Image.DecompressionBombWarning)
     image=Image.open(io.BytesIO(z.read(names[name]))).convert('RGB');ll[i]=low_level(image)
    with torch.inference_mode():
     x=model.features(transform(image).unsqueeze(0));x=model.avgpool(x);x=torch.flatten(x,1);fm[i]=model.classifier[:6](x)[0].numpy()
  need(np.isfinite(fm).all() and np.isfinite(ll).all(),'Finite full features');p=out/(part+'.npz');np.savez_compressed(p,representation=fm,low_level=ll);records[part]=identity(p.read_bytes())
 record={'schema':'neural056_features_v1','image_metadata_sha256':digest(m),'representation':'alexnet_relu7_4096_resize224_imagenet_normalization','checkpoint_sha256':b['sha256'],'extraction_source_sha256':identity(Path(__file__).read_bytes())['sha256'],'arrays':records,'torch_version':torch.__version__,'torchvision_version':torchvision.__version__,'EEG_used':False,'target_person_adaptation':False,'historical_kernel_PCA_reproduction':False}
 (out/'FEATURES.json').write_bytes(canonical(record))
if __name__=='__main__':
 p=argparse.ArgumentParser();
 for k in ['images-train','images-test','metadata','acquisition','checkpoint','binding','output']:p.add_argument('--'+k,required=True)
 a=p.parse_args();extract(a.images_train,a.images_test,a.metadata,a.acquisition,a.checkpoint,a.binding,a.output)
