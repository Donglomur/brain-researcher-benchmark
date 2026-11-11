"""Actual PyAV 14.4.0 full-media producer; no claim of hardware presentation.

Required selection is an independently admitted complete ID/byte map. Its hash
does not issue authority. The original 1102-file map is currently unavailable.
"""
from fractions import Fraction
import io
from input_owner import need, integer, digest, descriptor, capture, Writer

PROFILE='pyav_14.4.0_native_pts_rgb24_no_resample_v1'

def rational(value):
    need(type(value) is list and len(value)==2 and type(value[0]) is int and integer(value[1],1,2**63-1),'Explicit rational timeline origin')
    return Fraction(*value)

def validate_selection(selection):
    need(type(selection) is dict and set(selection)=={'schema','profile','library_versions','mapping_evidence','videos'},'Closed media selection')
    need(selection['schema']=='neural080_media_selection_v1' and selection['profile']==PROFILE,'Selected decoder profile')
    descriptor(selection['mapping_evidence'])
    versions=selection['library_versions']
    need(type(versions) is dict and versions and all(type(k) is str and type(v) is list and len(v)==3 and all(integer(x,0,9999) for x in v) for k,v in versions.items()),'Explicit qualified FFmpeg library versions; no inferred defaults')
    videos=selection['videos'];need(type(videos) is list and len(videos)==1102,'Complete 1102-video selection')
    paths=set()
    for i,row in enumerate(videos,1):
        need(type(row) is dict and set(row)=={'video_id','source_media','format','video_stream','audio_stream','timeline_origin','max_frames','max_audio_samples','max_width','max_height'},'Closed per-video source and capacity')
        need(type(row['video_id']) is int and row['video_id']==i,'Exact ordered video identity')
        descriptor(row['source_media']);need(row['source_media']['path'] not in paths,'Unique original media paths');paths.add(row['source_media']['path'])
        need(row['format'] in ('mov','matroska') and integer(row['video_stream'],0,31) and integer(row['audio_stream'],0,31) and row['video_stream']!=row['audio_stream'],'Explicit supported container and distinct streams')
        rational(row['timeline_origin'])
        need(integer(row['max_frames'],1,1000) and integer(row['max_audio_samples'],2,768000) and integer(row['max_width'],8,16384) and integer(row['max_height'],8,16384),'Original explicit decoder extents')
    return selection

def frame_interval(frame, origin):
    need(type(frame.pts) is int and frame.time_base is not None and frame.time_base>0 and type(frame.duration) is int and frame.duration>0 and not frame.is_corrupt,'Actual uncorrupted PTS/timebase/duration; no nominal FPS')
    start=Fraction(frame.pts)*frame.time_base-origin
    return start,start+Fraction(frame.duration)*frame.time_base

def audio_interval(frame, origin):
    need(type(frame.pts) is int and frame.time_base is not None and frame.time_base>0 and integer(frame.sample_rate,8000,192000) and integer(frame.samples,1,768000) and not frame.is_corrupt,'Actual native audio timebase/rate/support')
    start=Fraction(frame.pts)*frame.time_base-origin
    return start,start+Fraction(frame.samples,frame.sample_rate)

def normalized_audio(frame, np):
    channels=len(frame.layout.channels)
    need(integer(channels,1,8),'Native channel count')
    a=frame.to_ndarray()
    if frame.format.is_planar:
        need(a.shape==(channels,frame.samples),'Planar source audio geometry');a=a.T
    else:
        need(a.shape==(1,frame.samples*channels),'Packed source audio geometry');a=a.reshape(frame.samples,channels)
    name=frame.format.name
    expected={'u8':'uint8','u8p':'uint8','s16':'int16','s16p':'int16','s32':'int32','s32p':'int32','flt':'float32','fltp':'float32','dbl':'float64','dblp':'float64'}
    need(name in expected and a.dtype==np.dtype(expected[name]),'Explicit native audio representation')
    a=a.astype(np.float64)
    if name in ('u8','u8p'):a=(a-128.)/128.
    elif name in ('s16','s16p'):a=a/32768.
    elif name in ('s32','s32p'):a=a/2147483648.
    need(np.isfinite(a).all() and (np.abs(a)<=1.000001).all(),'Finite normalized audio, never synthesize silence')
    return a

def decode_clip(root,row,versions,owner):
    rec=owner.begin('decode_clip:'+str(row['video_id']))
    buffer=None;container=None;answer=None
    try:
        # The owner is retained before imports, captures, open and decode effects.
        import av
        import numpy as np
        from stimulus_core import spatial_cells
        need(np.__version__=='2.2.6','Selected NumPy source profile')
        need(av.__version__=='14.4.0' and {k:list(v) for k,v in av.library_versions.items()}==versions,'Exact selected decoder environment; not native qualification')
        raw=capture(root,row['source_media'],owner)
        owner.reserve('retained_bytes',len(raw))
        buffer=io.BytesIO(raw)
        # Explicit container prevents content-selected HLS/playlist routing.
        # Native parser sandbox/codec memory limits remain deployment obligations.
        container=av.open(buffer,mode='r',format=row['format'],options={'protocol_whitelist':'pipe'})
        streams={s.index:s for s in container.streams}
        need(row['video_stream'] in streams and row['audio_stream'] in streams,'Selected streams exist')
        video=streams[row['video_stream']];audio=streams[row['audio_stream']]
        need(video.type=='video' and audio.type=='audio','No stream-type substitution')
        video.codec_context.thread_count=1;audio.codec_context.thread_count=1
        origin=rational(row['timeline_origin']);cells=[];starts=[];ends=[];audio_parts=[]
        audio_start=None;audio_end=None;rate=None;layout=None;sample_count=0
        owner.reserve('retained_bytes',row['max_frames']*(8*8*3*8+16)+row['max_audio_samples']*8*8)
        for packet in container.demux(video,audio):
            # Includes terminal flush packets from the selected PyAV producer.
            for frame in packet.decode():
                if packet.stream.index==video.index:
                    need(len(cells)<row['max_frames'] and integer(frame.width,8,row['max_width']) and integer(frame.height,8,row['max_height']),'Video source capacity before array conversion')
                    a,b=frame_interval(frame,origin)
                    need(not ends or a==ends[-1],'Exact continuous decoded video intervals')
                    owner.reserve('retained_bytes',frame.width*frame.height*3)
                    rgb=frame.to_ndarray(format='rgb24')
                    cells.append(spatial_cells(rgb));starts.append(a);ends.append(b)
                elif packet.stream.index==audio.index:
                    a,b=audio_interval(frame,origin)
                    current_layout=tuple(c.name for c in frame.layout.channels)
                    if rate is None:rate=frame.sample_rate;layout=current_layout;audio_start=a
                    need(rate==frame.sample_rate and layout==current_layout and (audio_end is None or a==audio_end),'Continuous unchanged native audio clock and layout')
                    need(sample_count+frame.samples<=row['max_audio_samples'],'Audio capacity before conversion')
                    audio_parts.append(normalized_audio(frame,np));sample_count+=frame.samples;audio_end=b
                else:raise ValueError('Unexpected decoder stream')
        need(cells and starts[0]<=0 and ends[-1]>=3,'Complete actual video support over[0,3)')
        need(audio_parts and audio_start<=0 and audio_end>=3,'Complete actual audio support over[0,3); missing track is not silence')
        # Reserve separate combined arrays before stacking retained pieces.
        owner.reserve('retained_bytes',len(cells)*(8*8*3*8+16)+sample_count*len(layout)*8)
        answer={'cells':np.asarray(cells,dtype=np.float64),'frame_starts':np.asarray([float(x) for x in starts]),'frame_ends':np.asarray([float(x) for x in ends]),'audio':np.concatenate(audio_parts,axis=0),'frame_count':len(cells),'audio_sampling_rate':rate,'first_audio_sample_s':float(audio_start),'audio_shape':[sample_count,len(layout)],'rational_clock':{'origin':row['timeline_origin'],'video_start':[starts[0].numerator,starts[0].denominator],'video_end':[ends[-1].numerator,ends[-1].denominator],'audio_start':[audio_start.numerator,audio_start.denominator],'audio_end':[audio_end.numerator,audio_end.denominator]},'source_media':row['source_media'],'video_id':row['video_id']}
    except BaseException as exc:owner.failure(rec,exc)
    finally:
        if container is not None:owner.close(rec,container.close)
        if buffer is not None:owner.close(rec,buffer.close)
    owner.complete(rec);return answer

def produce(root,selection,selection_sha,out,owner):
    rec=owner.begin('decode_complete_1102');result=None
    try:
        validate_selection(selection);need(digest(selection_sha),'Exact enclosing selection pin')
        # Authority must already be supplied outside this module; this read only
        # authenticates the selected mapping evidence bytes, not their meaning.
        capture(root,selection['mapping_evidence'],owner)
        writer=Writer(out,owner);records=[]
        for row in selection['videos']:
            decoded=decode_clip(root,row,selection['library_versions'],owner)
            record={k:decoded[k] for k in ('video_id','source_media','frame_count','audio_shape','audio_sampling_rate','first_audio_sample_s','rational_clock')}
            for key in ('cells','frame_starts','frame_ends','audio'):
                record[key]=writer.array('video-%04d-%s.npy'%(row['video_id'],key),decoded[key])
            records.append(record)
        result={'schema':'neural080_decoded_media_v2','profile':PROFILE,'videos':records,'source_selection_sha256':selection_sha,'mapping_evidence':selection['mapping_evidence'],'library_versions':selection['library_versions'],'clock_domain':'selected rational container timeline; not observed display or neural trigger time','hardware_alignment_verified':False,'complete_media_support':True}
        writer.document('DECODED_MEDIA.json',result)
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return result
