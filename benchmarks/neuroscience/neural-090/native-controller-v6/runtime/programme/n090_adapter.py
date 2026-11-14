"""Concrete no-skip phoneme projection with explicit reduced-file clock mapping.

Future scientific source only: never invoked during this construction. This
does not manufacture a release map, clock evidence, channel identity or budget.
It projects complete run windows; fold-specific normalization and actor exposure
remain separate, so no query statistic fits a representation here.
"""
from contextlib import contextmanager
from pathlib import Path
import csv,hashlib,json,os,stat
from .contracts import Pin,Asset,need,rational,identity
from .n090_support import Run,Clock

@contextmanager
def pinned_stream(root,asset,max_read_bytes):
    need(type(asset) is Asset and asset.pin.bytes<=max_read_bytes,'whole input extent admitted before open')
    root=Path(root).resolve();path=root/asset.path
    need(all(not p.is_symlink() for p in (path,*path.parents)),'no symlink input alias')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==asset.pin.bytes,'exact ordinary source file')
        h=hashlib.sha256();size=0
        for b in iter(lambda:f.read(1048576),b''):size+=len(b);need(size<=asset.pin.bytes,'no input growth');h.update(b)
        need(size==asset.pin.bytes and h.hexdigest()==asset.pin.sha256,'source content identity');f.seek(0)
        try:yield f
        finally:
            b=os.fstat(f.fileno());need(all(getattr(a,k)==getattr(b,k) for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')),'source stable through decoder')

def parse_events(body,classes,clock):
    """Source rule plus exact clock conversion; unknown labels/errors are fatal."""
    need(type(clock) is Clock and len(classes)==len(set(classes))==39,'fixed 39-phoneme class identity')
    reader=csv.DictReader(body.decode('utf8').splitlines(),delimiter='\t')
    need(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)) and
         {'kind','segment','timemeg','idx'}<=set(reader.fieldnames),'complete original annotation columns')
    seen=set();events=[];excluded=0
    for ordinal,row in enumerate(reader):
        need(None not in row and None not in row.values() and row['idx'] not in seen,'complete unique original annotation rows')
        identity(row['idx']);seen.add(row['idx'])
        if row['kind']!='phoneme' or row['segment'] in ('sil','oov_S'):
            excluded+=1;continue
        label=row['segment'].split('_')[0];need(label in classes,'unknown class, never silently filtered')
        events.append({'source_row0':ordinal,'source_idx':row['idx'],'start_sample':clock.start(row['timemeg']),
                       'label':classes.index(label),'annotation_seconds':row['timemeg']})
    need(events,'empty target run is not an available run')
    return events,{'source_rows':len(seen),'excluded_non_target_rows':excluded,'target_rows':len(events)}

def inspect(handle,run,channels,np):
    need(set(handle)=={'data','times'},'declared continuous HDF5 layout only')
    data,times=handle['data'],handle['times'];clock=run.clock;n=clock.sample_count
    need(data.shape==(306,n) and data.dtype.kind=='f' and data.dtype.itemsize in (4,8) and
         times.shape==(n,) and times.dtype.kind=='f' and times.dtype.itemsize in (4,8),'complete native axes')
    need(float(handle.attrs['sample_frequency'])==250,'source sample frequency')
    need(handle.attrs['channel_names'].split(', ')==channels['channel_names'] and
         handle.attrs['channel_types'].split(', ')==channels['channel_types'],'full source channel identity/order')
    origin=float(rational(clock.sample_zero_seconds))
    # The times vector, not a filename suffix, decides whether a nonzero origin
    # matches the separately supplied clock mapping. No guessing a reduced shift.
    previous=None
    for first in range(0,n,65536):
        t=times[first:min(first+65536,n)].astype(np.float64)
        expected=origin+np.arange(first,first+len(t),dtype=np.float64)/250
        tolerance=np.finfo(times.dtype).eps*max(1.,abs(float(expected[-1])))
        need(np.isfinite(t).all() and (np.diff(t)>0).all() and
             (previous is None or t[0]>previous) and np.max(np.abs(t-expected))<=tolerance,'complete explicit source clock')
        previous=float(t[-1])
    return data

def project_run(run,root,classes,channels_bytes,output,read_limit,write_limit):
    """Materialize all original eligible windows and private joins, without fitting."""
    need(type(run) is Run,'complete typed source binding')
    # Known logical reservation includes annotation checksum and parse passes,
    # plus recording checksum and one recording-length lower allowance. Repeated
    # overlapping window reads can exceed that allowance; underlying HDF5 and
    # library allocations remain external deployment/capacity qualification.
    known=2*run.recording.pin.bytes+2*run.annotations.pin.bytes+len(channels_bytes)
    need(type(read_limit) is int and known<=read_limit,'aggregate known input reads before source effects')
    need(Pin(len(channels_bytes),hashlib.sha256(channels_bytes).hexdigest())==run.channels,'channel-schema content binding')
    channels=json.loads(channels_bytes);need(len(channels['channel_names'])==len(channels['channel_types'])==306,'full 306-channel schema')
    with pinned_stream(root,run.annotations,run.annotations.pin.bytes) as f:events,disposition=parse_events(f.read(),classes,run.clock)
    output=Path(output);need(not output.exists(),'fresh private projection')
    # Native HDF5 overhead needs separately measured allowance; this exact dense
    # payload lower bound cannot be described as an upper capacity guarantee.
    dense=len(events)*306*125*4
    need(type(write_limit) is int and dense<=write_limit,'full dense output before creation; no truncated prefix')
    import numpy as np
    import h5py
    output.mkdir(mode=0o700)
    try:
        with pinned_stream(root,run.recording,run.recording.pin.bytes) as f, h5py.File(f,'r') as src:
            data=inspect(src,run,channels,np)
            with h5py.File(output/'windows.h5','x') as out:
                dst=out.create_dataset('windows',(len(events),306,125),dtype='<f4',chunks=(1,306,125))
                for i,event in enumerate(events):
                    first=event['start_sample'];window=data[:,first:first+125]
                    need(window.shape==(306,125) and np.isfinite(window).all(),'complete finite source window')
                    dst[i]=window
        pin=hashlib.sha256()
        with (output/'windows.h5').open('rb') as f:
            for b in iter(lambda:f.read(1048576),b''):pin.update(b)
        size=(output/'windows.h5').stat().st_size
        receipt={'status':'projected_unqualified','run_key':list(run.key),'person':run.person,
                 'narrative':run.narrative,'passage_groups':list(run.passage_groups),'representation':run.representation,
                 'recording':run.recording.pin.json(),'annotations':run.annotations.pin.json(),
                 'clock_evidence':run.clock.evidence.json(),'channels':run.channels.json(),'release':run.release.json(),
                 'windows':{'bytes':size,'sha256':pin.hexdigest(),'shape':[len(events),306,125]},
                 'events':events,'disposition':disposition,'normalization':'none; must be fit on selected training/calibration only',
                 'known_input_byte_reservation':known,'physical_cost':'unknown','qualification':False}
        body=(json.dumps(receipt,sort_keys=True,allow_nan=False)+'\n').encode()
        need(size+len(body)<=write_limit,'actual full output exceeds selected bound; no completion on failure')
        with (output/'projection.json').open('xb') as f:f.write(body)
        return receipt
    except BaseException:
        # Retain partial owned output and original failure, never call it complete.
        # Full native lifetime/descendant/cleanup owner is a separate open gate.
        raise
