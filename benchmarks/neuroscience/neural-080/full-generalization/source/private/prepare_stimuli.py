"""Fixed feature projection from an externally frozen trusted decoded-media set.

Missing upstream component: an authenticated1102-video ID mapping, exact media
bytes and a reviewed decoder/presentation-clock receipt. This converter does
not invent those identities, decode a movie or establish hardware alignment.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_contract import capture,decode
import arrays
from prepare_pool import Writer,need
from stimulus_core import appearance,video_features,acoustic


def local(root,name):
    need(type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts,'Relative decoded/source file')
    p=root
    for part in Path(name).parts:p=p/part;need(not p.is_symlink(),'No symlink decoded/source components')
    return p


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def original(root,rec):
    need(type(rec['bytes']) is int and 0<rec['bytes']<=100_000_000 and sha(rec['sha256']),'Exact bounded original media descriptor')
    path=local(root,rec['path']);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and before.st_size==rec['bytes'],'Regular exact-size source clip')
        h=hashlib.sha256()
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
        after=os.fstat(f.fileno());named=os.stat(path,follow_symlinks=False)
        state=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(h.hexdigest()==rec['sha256'] and state(before)==state(after)==state(named),'Frozen original media identity')


def prepare(root,manifest_path,manifest_sha,out,output_cap,input_cap):
    raw=capture(manifest_path,10_000_000);need(hashlib.sha256(raw).hexdigest()==manifest_sha,'Root-selected immutable decoded-media manifest')
    manifest=decode(raw)
    need(manifest['schema']=='neural080_decoded_media_v1' and len(manifest['videos'])==1102
         and [r['video_id'] for r in manifest['videos']]==list(range(1,1103)),'All1102 authoritative video IDs in exact order')
    for key in ('video_identity_mapping_receipt_sha256','decoder_source_sha256','presentation_clock_receipt_sha256'):
        need(sha(manifest.get(key)),'Missing actual external identity/decoder/clock receipt operand:'+key)
    required=sum(r['source_media']['bytes']+sum(r[k]['bytes'] for k in ('cells','frame_starts','frame_ends','audio')) for r in manifest['videos'])
    need(type(input_cap) is int and 0<required<=input_cap,'Whole declared source/decoded input cap')
    projected={k:[] for k in ('static','motion','dynamic','acoustic')};provenance=[]
    for r in manifest['videos']:
        original(root,r['source_media']);n=r['frame_count'];shape=r['audio_shape']
        need(type(n) is int and 1<=n<=1000 and type(shape) is list and len(shape)==2
             and all(type(x) is int for x in shape) and 2<=shape[0]<=768000 and 1<=shape[1]<=8,'Bounded actual decoder geometry')
        cells=arrays.load(local(root,r['cells']['path']),r['cells'],(n,8,8,3),max_bytes=2_000_000)
        a=arrays.load(local(root,r['frame_starts']['path']),r['frame_starts'],(n,),max_bytes=20000)
        b=arrays.load(local(root,r['frame_ends']['path']),r['frame_ends'],(n,),max_bytes=20000)
        audio=arrays.load(local(root,r['audio']['path']),r['audio'],tuple(shape),max_bytes=64_000_000)
        v=video_features(appearance(cells,a,b));v['acoustic']=acoustic(audio,r['audio_sampling_rate'],r['first_audio_sample_s'])
        for k in projected:projected[k].append(v[k])
        provenance.append({'video_id':r['video_id'],'source_media':r['source_media'],'source_bytes_sha256_verified':True,
             'clock_receipt_sha256':manifest['presentation_clock_receipt_sha256'],
             'clock_binding_kind':'operator-declared receipt identity, not independent mapping/hardware verification',
             'decoded_records':{k:r[k] for k in ('cells','frame_starts','frame_ends','audio')}})
    writer=Writer(out,output_cap);desc={}
    for k,rows in projected.items():
        d=writer.array(k+'.npy',np.asarray(rows,dtype=np.float64));desc[k]={'file':d['path'],'bytes':d['bytes'],'sha256':d['sha256']}
    result={'schema':'neural080_stimulus_features_v1','recipe':'duration_rgb8x8_audio8band_v1','video_ids':list(range(1,1103)),
            'arrays':desc,'media':provenance,'decoded_manifest_sha256':manifest_sha,
            'external_receipts':{k:manifest[k] for k in ('video_identity_mapping_receipt_sha256','decoder_source_sha256','presentation_clock_receipt_sha256')},
            'independent_identity_mapping_or_hardware_alignment_review':'not established by this converter','models_run':0,'scientific_scores':0}
    writer.json('FEATURES.json',result)
    return {'retained_bytes':writer.used,'videos':1102,'models_run':0,'scientific_scores':0}


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser()
    for key in ('source-root','decoded-manifest','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--decoded-manifest-sha256',required=True)
    for key in ('max-output-bytes','max-input-bytes'):p.add_argument('--'+key,type=int,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.source_root,a.decoded_manifest,a.decoded_manifest_sha256,a.out,a.max_output_bytes,a.max_input_bytes)))
