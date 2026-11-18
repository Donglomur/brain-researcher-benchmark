"""Opaque-handle calibrated observation delivery; imports H5 only on actual read.

Visual-only delivery requires the independently selected external renderer and
participant restriction. SVG source is never the participant response. Source
and operator digests do not establish that physical isolation themselves.
"""
import hashlib
import html
import io as pyio
import math
import os
from pathlib import Path
import stat
import common as u


def request(value, allowed, policy):
    u.exact(value, ('kind', 'signal_handle', 'start_sample', 'stop_sample', 'channels'))
    u.need(value['kind'] == 'observe' and value['signal_handle'] in allowed, 'only current fold observation capabilities')
    row = allowed[value['signal_handle']]
    a,b=value['start_sample'],value['stop_sample']
    u.c.integer(a);u.c.integer(b,1)
    u.need(a < b <= row['duration_seconds'] * 256 and b-a <= policy['max_samples_per_request'], 'exact bounded original time window')
    channels=value['channels']
    u.need(type(channels)is list and 0 < len(channels) <= policy['max_channels_per_request'], 'bounded channel request')
    for x in channels:u.c.integer(x,0,len(row['channel_labels'])-1)
    u.need(channels==sorted(set(channels)), 'original channel order; no duplicates/reordering in selection')
    return row


class ChargedFile(pyio.RawIOBase):
    def __init__(self, handle, budget): self.handle,self.budget=handle,budget
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.handle.tell()
    def seek(self,*args):return self.handle.seek(*args)
    def read(self,n=-1):
        u.need(type(n)is int and n>=0, 'bounded numerical library file read')
        self.budget.charge('read_bytes',n)
        return self.handle.read(n)
    def readinto(self,buffer):
        raw=self.read(len(buffer));buffer[:len(raw)]=raw;return len(raw)
    def write(self,_):raise ValueError('read-only scientific source')


def admit_h5(f, h5py, row):
    """Metadata-only rejection of links/VDS/filters before any array read."""
    names={'eeg_digital','scale_to_microvolts','offset_microvolts','channel_labels','source_channel_index'}
    u.need(set(f.keys())==names,'exact original five dataset namespace')
    for name in names:
        u.need(type(f.get(name,getlink=True))is h5py.HardLink,'only original internal hard links')
    u.need(set(f.attrs.keys())=={'sample_rate_hz','duration_seconds','schema_version'},'exact original root attributes')
    for name,wanted in [('sample_rate_hz',256),('duration_seconds',row['duration_seconds']),('schema_version',1)]:
        value=f.attrs[name]
        u.need(getattr(getattr(value,'dtype',None),'kind',None)in ('i','u')and getattr(value,'shape',None)==()
            and int(value)==wanted,'original integral projection attribute')
    n=len(row['channel_labels']);datasets={}
    for name in names:
        ds=f[name]
        u.need(type(ds)is h5py.Dataset and not ds.is_virtual and not ds.external
            and ds.id.get_create_plist().get_nfilters()==0,'original self-contained unfiltered dataset')
        expected_shape=(row['duration_seconds']*256,n)if name=='eeg_digital'else(n,)
        dtype={'eeg_digital':'<i2','source_channel_index':'<i2','channel_labels':'|S32',
               'scale_to_microvolts':'<f8','offset_microvolts':'<f8'}[name]
        u.need(ds.shape==expected_shape and ds.dtype.str==dtype and ds.chunks==((256,n)if name=='eeg_digital'else None),'original dataset dtype shape chunk layout')
        datasets[name]=ds
    return datasets


class H5Signals:
    """Selected original projection provider; not an EDF or arbitrary-file reader."""
    def __init__(self, io, public_root, bindings, support):
        self.io,self.root=io,u.c.absolute(str(public_root))
        self.rows=support
        self.bindings={x['signal_handle']:x for x in bindings}
        u.need(set(self.bindings)=={r['signal_handle']for r in support.values()}, 'complete private opaque signal binding')
        for handle,b in self.bindings.items():
            u.exact(b,('recording_id','signal_handle','projection_path','projection'))
            u.need(b['projection_path']=='signals/'+b['recording_id']+'.h5' and handle=='signal:'+b['recording_id'],'literal source-owned projection binding')
            u.c.descriptor(b['projection'])

    def window(self, row, req):
        b=self.bindings[row['signal_handle']];p=self.io.checked(self.root/b['projection_path'])
        self.io.budget.charge('read_bytes',b['projection']['bytes']+1)
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            u.need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==b['projection']['bytes'],'ordinary exact H5 extent')
            digest=hashlib.sha256();count=0
            while count<=a.st_size:
                self.io.budget.tick();part=os.read(fd,min(65536,a.st_size+1-count))
                if not part:break
                count+=len(part);digest.update(part)
            u.need(count==a.st_size and digest.hexdigest()==b['projection']['sha256'],'authenticated selected complete projection')
            # No numerical/native import precedes the scope and complete source
            # identity checks above. Generated controls replace this provider.
            import h5py
            with os.fdopen(os.dup(fd),'rb',buffering=0)as raw:
                raw.seek(0)
                with h5py.File(ChargedFile(raw,self.io.budget),'r')as f:
                    datasets=admit_h5(f,h5py,row);eeg=datasets['eeg_digital'];n=len(row['channel_labels'])
                    labels=[x.decode('ascii').rstrip('\x00')for x in datasets['channel_labels'][:]]
                    u.need(labels==row['channel_labels'],'same ordered channel multiset')
                    indices=[int(x)for x in datasets['source_channel_index'][:]]
                    u.need(indices==sorted(set(indices))and all(0<=x<512 for x in indices),'original selected source channel order')
                    channels=req['channels'];scales=datasets['scale_to_microvolts'][:];offsets=datasets['offset_microvolts'][:]
                    u.need(all(math.isfinite(float(x))and float(x)>0 for x in scales)
                        and all(math.isfinite(float(x))for x in offsets),'finite original positive calibration')
                    digital=eeg[req['start_sample']:req['stop_sample'],channels]
                    values=[[float(digital[i,j])*float(scales[ch])+float(offsets[ch])for j,ch in enumerate(channels)]for i in range(len(digital))]
            fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
            z,named=os.fstat(fd),p.lstat()
            u.need(all(getattr(a,k)==getattr(z,k)==getattr(named,k)for k in fields),'stable read-only projection through numerical delivery')
            return values
        finally:os.close(fd)


def svg_frame(row, req, samples, gain):
    """Every sample maps to the selected fixed display gain, with explicit clipping."""
    count=len(samples);channels=req['channels'];height=100*len(channels);width=1024
    scale=u.c.finite(gain);u.need(scale>0,'positive prospectively frozen display gain')
    clip=lambda v:max(-scale,min(scale,v))
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']
    for j,ch in enumerate(channels):
        center=100*j+50
        points=' '.join(f'{i*1000/max(1,count-1)+12:.9f},{center-40*(clip(r[j])/scale):.9f}'for i,r in enumerate(samples))
        parts.append(f'<polyline points="{points}" fill="none" stroke="black" stroke-width="1"/>')
        if count==1:parts.append(f'<circle cx="12" cy="{center-40*(clip(samples[0][j])/scale):.9f}" r="2" fill="black"/>')
        parts.append(f'<text x="12" y="{100*j+12}" font-size="10">{html.escape(row["channel_labels"][ch])}</text>')
    parts.append('</svg>')
    return ''.join(parts).encode('ascii'),{'unfiltered':True,'downsampling':False,'clipping_policy':'saturate_to_prospectively_fixed_range','sample_rate_hz':256,
        'start_sample':req['start_sample'],'stop_sample':req['stop_sample'],'channel_indices':channels,
        'vertical_half_range_microvolts':scale,'vertical_half_range_pixels':40,'baseline_pixels':[100*j+50 for j in range(len(channels))],
        'first_sample_x_pixel':12,'last_sample_x_pixel':12 if count==1 else 1012,'image_width':width,'image_height':height,'coordinate_rounding_decimal_places':9}


class Observations:
    def __init__(self, signals, policy, budget, display=None):
        self.signals,self.policy,self.budget,self.display=signals,policy,budget,display

    def observe(self, req, allowed, mode):
        row=request(req,allowed,self.policy)
        self.budget.charge('actions',1)
        # Logical worst-case output/render allocation reservation before numerical
        # delivery. Actual create-only writes are charged separately as well.
        ceiling=4096+(req['stop_sample']-req['start_sample'])*len(req['channels'])*96+len(req['channels'])*4096
        u.need(ceiling<=self.policy['frame_bytes'],'prospective complete observation/frame allocation bound')
        self.budget.charge('write_bytes',ceiling)
        self.budget.charge('signal_samples',(req['stop_sample']-req['start_sample'])*len(req['channels']))
        samples=self.signals.window(row,req)
        u.need(type(samples)is list and len(samples)==req['stop_sample']-req['start_sample'],'complete requested sample rows')
        u.need(all(type(r)is list and len(r)==len(req['channels'])and all(type(v)in(int,float)and math.isfinite(v)for v in r)for r in samples),'finite calibrated observations')
        geometry={'signal_handle':req['signal_handle'],'sample_rate_hz':256,'start_sample':req['start_sample'],
            'stop_sample':req['stop_sample'],'channels':req['channels'],'channel_labels':[row['channel_labels'][i]for i in req['channels']]}
        if mode=='frozen_program':return {'schema':'neural010-programme-observation-v1',**geometry,'microvolts':samples}
        u.need(mode=='typed_viewer' and self.display is not None,'selected visual delivery provider required; no raw fallback')
        raw,render=svg_frame(row,req,samples,self.policy['display_half_range_microvolts'])
        reply=self.display.render(raw,render)
        u.exact(reply,('schema','media_type','image_handle','render_sha256'))
        u.need(reply['schema']=='neural010-rendered-observation-v1'and reply['media_type']=='image/png'
            and reply['render_sha256']==hashlib.sha256(raw).hexdigest(),'exact independently rendered frame binding')
        u.need(type(reply['image_handle'])is str and reply['image_handle'].startswith('image:')and len(reply['image_handle'])==70,'opaque rendered-image handle')
        u.c.digest(reply['image_handle'][6:])
        # The waveform-derived SVG digest stays in the protected renderer RPC.
        return {k:reply[k]for k in ('schema','media_type','image_handle')}|{'geometry':geometry,'rendering':render}
