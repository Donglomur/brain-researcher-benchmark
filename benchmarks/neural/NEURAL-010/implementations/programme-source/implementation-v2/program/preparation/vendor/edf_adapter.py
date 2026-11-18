"""Read-only EDF projection into full continuous target-free numeric recordings.

No feature/model/scorer calls. Exact source index preserves duplicate montage
labels. Auxiliary/dummy/annotation channels never enter candidate data.
"""
import argparse
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
from event_protocol import need

EEG=re.compile(r'^(?:FP|AF|F|FC|FT|C|CP|T|P|PO|O)(?:[0-9]{1,2}|Z)$')


def eeg_label(label):
    parts=label.upper().split('-')
    return (len(parts)==1 and EEG.fullmatch(parts[0])) or (len(parts)==2 and EEG.fullmatch(parts[0])
             and (EEG.fullmatch(parts[1]) or parts[1] in ('REF','CS2')))


def inspect_edf(path):
    with Path(path).open('rb') as stream:
        fixed=stream.read(256);need(len(fixed)==256,'complete EDF fixed header')
        text=lambda a,b:fixed[a:b].decode('ascii').strip()
        need(text(0,8)=='0','EDF version0, notBDF')
        header_bytes=int(text(184,192));reserved=text(192,236);records=int(text(236,244))
        record_seconds=float(text(244,252));channels=int(text(252,256))
        need(0<channels<=512 and header_bytes==256*(1+channels) and records>0
             and math.isfinite(record_seconds) and record_seconds>0,'complete fixed EDF extent')
        need(reserved=='' or reserved.startswith('EDF+C'),'unsupported/discontinuous EDF not counted negative')
        raw=stream.read(header_bytes-256);need(len(raw)==header_bytes-256,'complete EDF channel header')
    offset=0;fields={}
    for name,width in [('label',16),('transducer',80),('unit',8),('pmin',8),('pmax',8),('dmin',8),('dmax',8),('prefilter',80),('samples',8),('reserved',32)]:
        fields[name]=[raw[offset+i*width:offset+(i+1)*width].decode('ascii').strip() for i in range(channels)];offset+=width*channels
    counts=[int(x) for x in fields['samples']];need(all(x>0 for x in counts),'positive samples per source channel')
    duration=records*record_seconds;need(duration.is_integer() and 0<duration<=86400,'complete integer-second recording')
    need(Path(path).stat().st_size==header_bytes+records*sum(counts)*2,'exact complete EDF file extent')
    selected=[];excluded=[];occurrences={}
    for i,label in enumerate(fields['label']):
        if not eeg_label(label):excluded.append({'source_index':i,'label':label,'reason':'nonwhitelisted EEG derivation/dummy/auxiliary'});continue
        unit=fields['unit'][i];factor={'uV':1.,'µV':1.,'mV':1000.,'V':1000000.}.get(unit)
        pmin,pmax=float(fields['pmin'][i]),float(fields['pmax'][i]);dmin,dmax=int(fields['dmin'][i]),int(fields['dmax'][i])
        need(counts[i]/record_seconds==256 and factor is not None and all(math.isfinite(x) for x in (pmin,pmax))
             and pmax>pmin and -32768<=dmin<dmax<=32767,'unsupported EEG rate/calibration fails whole recording')
        scale=(pmax-pmin)/(dmax-dmin)*factor;bias=pmin*factor-dmin*scale
        need(math.isfinite(scale) and math.isfinite(bias) and scale>0,'finite derived microvolt calibration')
        occurrences[label]=occurrences.get(label,0)+1
        selected.append({'source_index':i,'label':label,'occurrence':occurrences[label],'scale_to_microvolts':scale,'offset_microvolts':bias})
    need(selected,'no supported EEG channels; recording cannot be declared background')
    return {'header_bytes':header_bytes,'source_channels':channels,'records':records,'record_seconds':record_seconds,
            'samples_per_source_record':counts,'duration_seconds':int(duration),'sample_rate_hz':256,
            'selected_channels':selected,'excluded_channels':excluded,'unsupported_intervals':[],
            'observed_intervals':[[0,int(duration)]],'interfile_gaps_included':False}


def verify(path,pin):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size==pin['bytes'],'exact original file')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    need(digest.hexdigest()==pin['sha256'],'original content SHA256')


def project(path,destination,pin):
    import h5py
    import numpy as np
    verify(path,pin);header=inspect_edf(path);selected=header['selected_channels'];counts=header['samples_per_source_record']
    offsets=np.cumsum([0]+counts);ns=header['duration_seconds']*256;per=int(header['record_seconds']*256)
    with path.open('rb') as stream,h5py.File(destination,'x') as out:
        stream.seek(header['header_bytes'])
        data=out.create_dataset('eeg_digital',shape=(ns,len(selected)),dtype='<i2',chunks=(256,len(selected)))
        out.create_dataset('scale_to_microvolts',data=[c['scale_to_microvolts'] for c in selected])
        out.create_dataset('offset_microvolts',data=[c['offset_microvolts'] for c in selected])
        out.create_dataset('channel_labels',data=np.array([c['label'].encode() for c in selected],dtype='S32'))
        out.create_dataset('source_channel_index',data=np.array([c['source_index'] for c in selected],dtype=np.int16))
        out.attrs['sample_rate_hz']=256;out.attrs['duration_seconds']=header['duration_seconds'];out.attrs['schema_version']=1
        for record in range(header['records']):
            raw=stream.read(sum(counts)*2);need(len(raw)==sum(counts)*2,'complete source data record')
            values=np.frombuffer(raw,dtype='<i2')
            data[record*per:(record+1)*per,:]=np.column_stack([values[offsets[c['source_index']]:offsets[c['source_index']+1]] for c in selected])
        need(not stream.read(1),'no trailing EDF bytes')
    destination.chmod(0o444);return header


def build(lock_path,annotations_path,staged,output,key,max_output_bytes):
    lock=json.loads(lock_path.read_text());annotations=json.loads(annotations_path.read_text())['records'];rows=lock['records']
    need(lock['version']=='1.0.0' and len(rows)==686 and len({r['path'] for r in rows})==686
         and len({r['patient'] for r in rows})==23 and len(key)==32,'full686record/23person source and private key')
    need(set(annotations)=={r['path'] for r in rows} and not output.exists(),'complete annotation join/fresh output')
    need(sum(r['bytes'] for r in rows)+2000000000<=max_output_bytes,'complete projected source plus conservative HDF5 overhead budget; never truncate')
    output.mkdir(mode=0o700);(output/'signals').mkdir();(output/'private').mkdir(mode=0o700)
    panel=[];targets=[];provenance=[]
    for row in rows:
        src=staged/row['path'];need(src.resolve().is_relative_to(staged.resolve()),'staged path')
        rid=hmac.new(key,('record:'+row['path']).encode(),hashlib.sha256).hexdigest()[:24]
        patient=hmac.new(key,('patient:'+row['patient']).encode(),hashlib.sha256).hexdigest()[:24]
        dest=output/'signals'/(rid+'.h5');header=project(src,dest,row);duration=header['duration_seconds']
        events=annotations[row['path']]['events'];last=-1.
        for a,b in events:need(0<=a<b<=duration and a>=last and a==int(a) and b==int(b),'complete nonoverlapping integral-second within-file annotation');last=b
        digest=hashlib.sha256()
        with dest.open('rb') as stream:
            for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
        panel.append({'recording_id':rid,'patient_id':patient,'duration_seconds':duration,'observed_intervals':[[0,duration]],
                      'path':'signals/'+rid+'.h5','bytes':dest.stat().st_size,'sha256':digest.hexdigest()})
        targets.append({'recording_id':rid,'events':events})
        provenance.append({'recording_id':rid,'source_path':row['path'],'source_sha256':row['sha256'],'header':header,
                           'annotation_evidence':row['annotation_evidence']})
        need(sum(f.stat().st_size for f in (output/'signals').iterdir())+10000000<=max_output_bytes,'actual cumulative projected budget')
    need(len({r['recording_id'] for r in panel})==686,'opaque record collision')
    def save(path,value):
        body=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode();path.write_bytes(body);path.chmod(0o444);return hashlib.sha256(body).hexdigest()
    panel_pin=save(output/'panel.json',{'schema_version':1,'task_id':'NEURAL-009','records':panel})
    target_pin=save(output/'private/targets.json',{'schema_version':1,'task_id':'NEURAL-009','panel_sha256':panel_pin,'records':targets})
    save(output/'private/source_provenance.json',{'records':provenance})
    need(sum(f.stat().st_size for f in output.rglob('*') if f.is_file())+100000<=max_output_bytes,'actual output budget')
    save(output/'private/PREPARATION.json',{'status':'prepared_not_empirically_qualified','records':686,'patients':23,'panel_sha256':panel_pin,
         'targets_sha256':target_pin,'models_fit':0,'empirical_scores':0,'interfile_gaps_counted_as_background':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lock','annotations','staged','output','key'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    build(a.lock,a.annotations,a.staged,a.output,a.key.read_bytes(),a.max_output_bytes)
