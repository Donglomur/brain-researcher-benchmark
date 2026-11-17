"""Actual MATv5 mapper and independent source-guided numerical preparation, unexecuted."""
import argparse,io as memory,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import protocol as p
import delivery_io as io
import array_io
import provision

def phase(s,binding):
 import numpy as np
 from scipy.signal import resample_poly,butter,lfilter
 required={'x','t','fs','y_dec','y_logic','chan',binding['class_names_field']}
 p.need(required<=set(s),'Source struct fields')
 x=np.asarray(s['x']);fs=np.asarray(s['fs']).item();times=np.asarray(s['t']).reshape(-1)
 p.need(fs==1000 and x.ndim==2 and x.shape[1]==62 and x.dtype.kind in 'fiu' and x.size*8<=3000000000 and np.isfinite(x).all(),'Native1000Hz62channel finite numeric source with explicitdecode bound')
 channels=[str(q).strip() for q in np.asarray(s['chan']).reshape(-1)]
 p.need(channels==binding['channel_order'] and len(set(channels))==62,'Operator-observed exact62EEG order')
 p.need(times.shape==(100,) and np.isfinite(times).all() and np.all(times==np.floor(times)),'Exact100onsets in native samples')
 onsets=[int(t) for t in times];ii=p.indices(onsets)
 codes=np.asarray(s['y_dec']).reshape(-1);logic=np.asarray(s['y_logic'])
 p.need(codes.shape==(100,) and np.isfinite(codes).all() and np.all(codes==np.floor(codes)) and logic.shape==(2,100) and np.all((logic==0)|(logic==1)) and np.all(logic.sum(0)==1),'Exact100 labels/twoonehot rows')
 labels=binding['class_codes'];p.exact(labels,['left','right']);p.need(all(type(v)is int for v in labels.values()) and labels['left']!=labels['right'],'Explicit observedclasscodebinding')
 y=np.asarray([1 if int(c)==labels['right'] else 0 if int(c)==labels['left'] else -1 for c in codes],dtype=int)
 p.need(np.bincount(y,minlength=2).tolist()==[50,50],'All100 balancedclasses, noselectiveomission')
 names=[str(q).strip().lower() for q in np.asarray(s[binding['class_names_field']]).reshape(-1)]
 p.need(len(names)==2 and set(names)=={'left','right'},'Actual two-classnames left/right required; no guessed semantic mapping')
 for j,name in enumerate(names):p.need(np.array_equal(logic[j].astype(bool),codes==labels[name]),'Classname/onehot/decimal agreement')
 data=np.asarray(x[:,np.asarray(p.CHANNEL_INDEX_1)-1],float)
 # Independent Python counterpart, not claimed MATLAB resample/filter bit parity.
 data=resample_poly(data,1,10,axis=0,window=('kaiser',5.0),padtype='constant')
 b,a=butter(5,[8,30],btype='bandpass',fs=100);data=lfilter(b,a,data,axis=0)
 indexes=np.asarray(ii,int);p.need(indexes.min()>=0 and indexes.max()<len(data),'Every inclusive sourcewindow observed')
 epochs=data[indexes,:];p.need(epochs.shape==(100,251,20) and np.isfinite(epochs).all(),'Complete fixed251×20 windows')
 return epochs,y.tolist(),onsets

def retained_array(arr,max_output_bytes):
 """Count the serialized float32 representation, with bounded metadata reserve."""
 import numpy as np
 with np.errstate(over='raise',invalid='raise'):stored=np.ascontiguousarray(arr,dtype='<f4')
 p.need(stored.shape==(200,251,20) and np.isfinite(stored).all(),'Finite exact retainedrepresentation')
 p.need(stored.nbytes+100000<max_output_bytes,'Float32 retainedarray plus metadata cap')
 return stored

def project(source,source_pin,binding,out,person,session,max_output_bytes):
 from scipy.io import loadmat
 import numpy as np
 out=io.regular(out);p.need(not out.exists(),'Fresh output before source reads')
 p.need(person in p.PEOPLE and session in p.SESSIONS,'Selectedfullpanelidentity')
 p.exact(binding,['schema','channel_order','class_names_field','class_codes']);p.need(binding['schema']=='neural083_observed_mat_schema_v1' and binding['class_names_field'] in ('class','y_class'),'Observed semanticsbinding required')
 body=io.read(source,700000000,source_pin);p.need(body[:19]==b'MATLAB 5.0 MAT-file,','ObservedMAT5format only')
 data=loadmat(memory.BytesIO(body),variable_names=['EEG_MI_train','EEG_MI_test'],simplify_cells=True,verify_compressed_data_integrity=True)
 p.need(all(k in data for k in ('EEG_MI_train','EEG_MI_test')),'Bothnativephases')
 off,yo,to=phase(data['EEG_MI_train'],binding);on,yn,tn=phase(data['EEG_MI_test'],binding)
 arr=retained_array(np.concatenate([off,on]),max_output_bytes)
 io.fresh(out);pin=array_io.write(out/'epochs.npy',arr,max_output_bytes)
 meta={'schema':'neural083_record_v1','person':person,'session':session,'source_pin':source_pin,'schema_binding_pin':io.pin(io.canonical(binding)),'epochs':pin,'offline_labels':yo,'online_labels':yn,'offline_onsets':to,'online_onsets':tn,'array_shape':[200,251,20]}
 io.put(out/'record.json',meta,100000);return meta

def main():
 a=argparse.ArgumentParser();a.add_argument('--source-root',type=Path,required=True);a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--schema-binding',type=Path,required=True);a.add_argument('--person',type=int,required=True);a.add_argument('--session',type=int,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--max-output-bytes',type=int,required=True);q=a.parse_args();rows=provision.load(q.source_manifest);selected=[r for r in rows if (r['person'],r['session'])==(q.person,q.session)];p.need(len(selected)==1,'Exactknownsourcecase');r=selected[0];project(io.resolve(q.source_root,r['path']),{'bytes':r['bytes'],'sha256':r['sha256']},io.json_file(q.schema_binding,65536),q.output,q.person,q.session,q.max_output_bytes)
if __name__=='__main__':main()
