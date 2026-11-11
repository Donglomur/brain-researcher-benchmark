"""Concrete captured-media → original deterministic feature kernels."""
import hashlib
from pathlib import Path
from input_owner import need, integer, capture, Writer

def prepare(media_root,decoded_root,decoded_descriptor,out,owner):
    rec=owner.begin('complete_decoded_feature_projection');answer=None
    try:
        import numpy as np
        import arrays
        from io_contract import decode
        from stimulus_core import appearance,video_features,acoustic
        from decode_media import PROFILE
        raw=capture(decoded_root,decoded_descriptor,owner);doc=decode(raw)
        need(doc['schema']=='neural080_decoded_media_v2' and doc['profile']==PROFILE and doc['hardware_alignment_verified'] is False and doc['complete_media_support'] is True,'Actual decoded source profile; no hardware qualification')
        rows=doc['videos'];need(len(rows)==1102 and [r['video_id'] for r in rows]==list(range(1,1103)),'Full decoded video order')
        projected={k:[] for k in ('static','motion','dynamic','acoustic')};provenance=[]
        # Separate stacked feature retention, before accumulating any values.
        owner.reserve('retained_bytes',1102*(384+30*64+30*192+30*10)*8*2)
        for row in rows:
            # Re-authenticate original media bytes against the decoder's exact
            # selection. This remains identity, not source-map authority.
            capture(media_root,row['source_media'],owner)
            n=row['frame_count'];shape=row['audio_shape']
            need(integer(n,1,1000) and type(shape) is list and len(shape)==2 and integer(shape[0],2,768000) and integer(shape[1],1,8),'Closed decoded array extents before parse')
            need(integer(row['audio_sampling_rate'],8000,192000),'Native sample-rate domain')
            geometries={'cells':(n,8,8,3),'frame_starts':(n,),'frame_ends':(n,),'audio':tuple(shape)}
            values={}
            for key,geometry in geometries.items():
                body=capture(decoded_root,row[key],owner)
                values[key]=arrays.decode(body,geometry,max_bytes=64_000_000)
            features=video_features(appearance(values['cells'],values['frame_starts'],values['frame_ends']))
            features['acoustic']=acoustic(values['audio'],row['audio_sampling_rate'],row['first_audio_sample_s'])
            for key in projected:projected[key].append(features[key])
            provenance.append({'video_id':row['video_id'],'source_media':row['source_media'],'source_bytes_sha256_verified':True,'decoded_arrays':{k:row[k] for k in geometries},'rational_clock':row['rational_clock']})
        writer=Writer(out,owner);desc={}
        for key,values in projected.items():
            r=writer.array(key+'.npy',np.asarray(values,dtype=np.float64));desc[key]={'file':r['path'],'bytes':r['bytes'],'sha256':r['sha256']}
        answer={'schema':'neural080_stimulus_features_v2','recipe':'duration_rgb8x8_audio8band_v1','video_ids':list(range(1,1103)),'arrays':desc,'media':provenance,'decoded_manifest':decoded_descriptor,'source_selection_sha256':doc['source_selection_sha256'],'decoder_profile':PROFILE,'clock_domain':doc['clock_domain'],'hardware_alignment_verified':False,'presentation_trial_warp_or_average':False,'models_run':0,'scientific_scores':0}
        writer.document('FEATURES.json',answer)
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer
