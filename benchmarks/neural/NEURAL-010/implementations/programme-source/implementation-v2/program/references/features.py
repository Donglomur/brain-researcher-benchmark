"""Future full-projection features; no authentic read or native call on import."""
import math
from common import need,numpy,records,exact,save_array
from math_core import second_features

BASE=('patient_id','recording_id','duration_seconds','montage_id','channel_count','channel_labels','source_edf','target_free_projection')

def metadata(row):return {k:row[k] for k in BASE}

def extract(request,io,out,identity):
    record=request['record'];records({'schema':'neural010-reference-records-v1','role':'query','records':[record]},'query','matched_no_eeg')
    d,c=record['duration_seconds'],record['channel_count'];lim=io.limits
    # Full outputs plus original 256-second calibration block and its differences.
    required=8*d*34+3*256*256*c*8
    need(d<=lim['max_rows'] and 33<=lim['max_columns'] and required<=lim['max_design_bytes'],'complete feature memory admission')
    waveform=request['waveform'];need({k:waveform[k] for k in ('bytes','sha256')}==record['target_free_projection'],'exact admitted full projection')
    path=io.check(waveform);np=numpy()
    import h5py
    need(h5py.__version__=='3.14.0','prospective h5py3.14.0; native runtime unqualified')
    features=np.empty((d,33),dtype=np.float64);signal=np.empty(d,dtype=np.float64)
    # Full-container exposure reservation covers this logical native open; it
    # is not a measured bound on HDF5 metadata/chunk/paging physical traffic.
    io.charge_read(waveform['bytes'])
    with h5py.File(path,'r') as f:
        # Only in-file hard links are admitted, never external data or virtual arrays.
        for name in ('eeg_digital','scale_to_microvolts','offset_microvolts'):
            need(isinstance(f.get(name,getlink=True),h5py.HardLink),'ordinary internal dataset link')
            ds=f[name];need(isinstance(ds,h5py.Dataset) and not ds.is_virtual and not ds.external,'self-contained HDF5 dataset')
        x=f['eeg_digital'];scale_ds=f['scale_to_microvolts'];offset_ds=f['offset_microvolts']
        rate_id=f.attrs.get_id('sample_rate_hz');need(rate_id.shape==() and rate_id.dtype.kind in 'iuf' and rate_id.dtype.itemsize<=8,'bounded original sampling-rate attribute');io.charge_read(int(rate_id.dtype.itemsize));sample_rate=f.attrs['sample_rate_hz']
        need(x.shape==(d*256,c) and x.dtype.kind=='i' and x.dtype.itemsize==2 and scale_ds.shape==(c,) and offset_ds.shape==(c,) and scale_ds.dtype.kind=='f' and offset_ds.dtype.kind=='f' and sample_rate==256,'complete original digital256Hz geometry')
        io.charge_read(int(scale_ds.size*scale_ds.dtype.itemsize+offset_ds.size*offset_ds.dtype.itemsize))
        scale=scale_ds[:];offset=offset_ds[:];need(bool(np.isfinite(scale).all()) and bool(np.isfinite(offset).all()),'finite exact calibration')
        for start in range(0,d,256):
            end=min(d,start+256);io.charge_read((end-start)*256*c*int(x.dtype.itemsize))
            block=x[start*256:end*256,:].astype(np.float64)*scale+offset
            need(bool(np.isfinite(block).all()),'all finite calibrated observations')
            block=block.reshape(end-start,256,c)
            # Preserve historical NumPy block arithmetic, separately from strong fsum features.
            signal[start:end]=np.median(np.log1p(np.mean(np.abs(np.diff(block,axis=1)),axis=1)),axis=1)
            for local in range(end-start):features[start+local,:]=second_features(block[local])
    need(bool(np.isfinite(features).all()) and bool(np.isfinite(signal).all()),'complete finite features; no row omission')
    fp=save_array(io,out/'features.npy',features);sp=save_array(io,out/'signal.npy',signal)
    result={'schema':'neural010-feature-receipt-v1','source_identity':identity,'feature_schema':'neural010-feature-v1','record':record,'waveform':waveform,'features':fp,'signal':sp,'rows':d,'eeg_columns':33,'calibration':'float64(digital)*scale_to_microvolts+offset_microvolts','historical_signal_arithmetic':'original_numpy_256_second_blocks','numerics':{'numpy':np.__version__,'h5py':h5py.__version__},'qualification':False}
    return io.write_json(out/'FEATURES.json',result)

def authenticate_cache(io,row,condition,identity):
    receipt=io.json(row['feature_receipt'])
    exact(receipt,('schema','source_identity','feature_schema','record','waveform','features','signal','rows','eeg_columns','calibration','historical_signal_arithmetic','numerics','qualification'))
    need(receipt['schema']=='neural010-feature-receipt-v1' and receipt['source_identity']==identity and receipt['feature_schema']=='neural010-feature-v1' and receipt['record']==metadata(row) and receipt['rows']==row['duration_seconds'] and receipt['eeg_columns']==33 and receipt['qualification'] is False,'full immutable feature provenance')
    field='features' if condition=='joint' else 'signal';operand='eeg_features' if condition=='joint' else 'signal_features'
    need(row[operand]==receipt[field] and {k:receipt['waveform'][k] for k in ('bytes','sha256')}==row['target_free_projection'],'exact cache/projection identity')
    need(receipt['calibration']=='float64(digital)*scale_to_microvolts+offset_microvolts' and receipt['historical_signal_arithmetic']=='original_numpy_256_second_blocks' and receipt['numerics']=={'numpy':'2.2.6','h5py':'3.14.0'},'exact declared feature method')
    return row[operand]
