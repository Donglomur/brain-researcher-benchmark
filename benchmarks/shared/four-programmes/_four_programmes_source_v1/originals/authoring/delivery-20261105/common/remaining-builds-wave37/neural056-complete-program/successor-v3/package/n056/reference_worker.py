"""Trusted train/query reference ABI used in separate isolated processes."""
from pathlib import Path
from .core import need,read_json,capture,save,write_new,byte_pin
from .arrays import decode,encode
from .bank_a import ridge_fit,ridge_predict
def train(input_dir,output,alpha):
    meta=read_json(Path(input_dir)/'context.json');n=meta['train_rows'];d=meta['feature_count']
    need(n in (13240,16540) and d in (768,4096) and meta['response_shape']==[17,100],'full declared training support')
    row=meta['arrays']['training'];a=decode(capture(Path(input_dir)/'training.npz',row['bytes'],row),{'x':(n,d),'y':(n,17,100)},800000000)
    model=ridge_fit(a['x'],a['y'].reshape(n,1700),alpha);p=write_new(Path(output)/'model.npz',encode(model))
    save(Path(output)/'model.json',{'schema':'neural056_reference_model_v1','alpha':alpha,'feature_count':d,
         'response_coordinates':1700,'array':{k:p[k] for k in ('bytes','sha256')}})
def query(input_dir,model_dir,output):
    meta=read_json(Path(input_dir)/'context.json');n=meta['query_rows'];d=meta['feature_count']
    need(n in (200,3300) and d in (768,4096),'full query support')
    row=meta['arrays']['query'];a=decode(capture(Path(input_dir)/'query.npz',row['bytes'],row),{'x':(n,d)},330000000)
    mm=read_json(Path(model_dir)/'model.json');need(mm['feature_count']==d and mm['response_coordinates']==1700,'frozen model dimensions')
    m=decode(capture(Path(model_dir)/'model.npz',mm['array']['bytes'],mm['array']),
      {'mean_x':(d,),'scale_x':(d,),'mean_y':(1700,),'coef':(d,1700)},100000000)
    pred=ridge_predict(m,a['x']).reshape(n,17,100)
    write_new(Path(output)/'prediction.npz',encode({'prediction':pred}))

