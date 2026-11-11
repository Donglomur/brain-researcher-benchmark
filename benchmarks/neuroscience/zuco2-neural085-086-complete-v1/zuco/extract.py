"""Original MAT reference readers with source-pinned field/axis mapping, no guessing.
This code is not an implementation of missing original cleaning, interpolation,
ICA/MARA, Hilbert, FRP or fixation segmentation operators. Their identities and
source outputs must be qualified separately; unavailable stages remain gates.
"""
from .io import *
def scalar(h,obj):
    import numpy as np
    a=np.asarray(h[obj]);need(a.size in (0,1),"scalar_shape")
    if a.size==0:return None
    x=float(a.reshape(-1)[0]);return x if finite(x) else None
def text(h,obj):
    a=h[obj][()];need(a.dtype.kind in "iu" and a.size<=10000,"MAT_string");return "".join(chr(int(c)) for c in a.reshape(-1))
def vector(h,obj,channel_count,axis):
    import numpy as np
    a=np.asarray(h[obj]);need(a.ndim==2 and a.shape[axis]==channel_count and a.shape[1-axis]==1,"qualified_vector_axes")
    return [float(x) if np.isfinite(x) else None for x in a.reshape(-1)]
def original_word_slots(h,word_group,binding):
    need(binding["qualification"]=="source_stage_and_shapes_independently_qualified","word_ABI_unqualified")
    names=binding["field_names"];need("content" in names,"content_mapping");content=word_group[names["content"]]
    for original_index in range(len(content)):
        # Never zip an optional SFD array with mandatory fields, and never use a filtered index for EEG lookup.
        row={"original_word_index":original_index,"word":text(h,content[original_index][0]),"fields":{},"source_dispositions":{}}
        for logical,field in names.items():
            if logical=="content":continue
            if field not in word_group:row["fields"][logical]=None;row["source_dispositions"][logical]="absent_field";continue
            refs=word_group[field];need(len(refs)==len(content),"source_word_field_extent",field)
            obj=refs[original_index][0];role=binding["roles"][logical]
            if role=="scalar":row["fields"][logical]=scalar(h,obj)
            elif role=="scalp_vector":row["fields"][logical]=vector(h,obj,105,binding["vector_channel_axis"])
            elif role=="descriptor_only":row["fields"][logical]={"source_object":h[obj].name,"shape":list(h[obj].shape),"dtype":str(h[obj].dtype)}
            else:raise Refusal("unknown_source_role",logical)
        yield row

def primitive(d,cap):
    import h5py,math
    need(isinstance(d,h5py.Dataset) and d.dtype.kind in 'uif' and math.prod(d.shape)<=cap,'bounded_primitive_source');return d[()]
def dereference(h,table,index):
    import h5py
    need(isinstance(table,h5py.Dataset) and table.ndim==2 and table.shape[1]==1 and h5py.check_dtype(ref=table.dtype)is not None,'MAT_reference_column');ref=table[index,0];need(bool(ref),'present_MAT_reference');return h[ref]
def source_text(d):
    import numpy as np
    a=primitive(d,10000);need(a.dtype.kind=='u' and a.dtype.itemsize==2,'MAT_UTF16_code_units');return np.asarray(a,dtype='<u2').reshape(-1).tobytes().decode('utf-16-le')
def source_scalar(d):
    a=primitive(d,1)
    if a.size==0:return None
    need(a.size==1,'source_scalar');x=float(a.reshape(-1)[0]);return x if finite(x) else None
def source_band(d):
    a=primitive(d,105)
    if a.size==0 or (a.size==1 and not finite(float(a.reshape(-1)[0]))):return [None]*105
    need(a.shape in ((105,1),(1,105),(105,)),'qualified_105_mean_role');return [float(v)if finite(float(v))else None for v in a.reshape(-1)]
def materialize_segments(h,geometry,source_pin,abi,stage,guard):
    """Qualified source intervals only; never infer fixation joins or native filters."""
    import numpy as np
    result=[]
    for g in geometry:
        guard();need(g['source_sha256']==source_pin['sha256'] and g['source_stage']==stage and g['independently_qualified_interval']is True,'qualified_source_interval');d=h[g['object_path']];need(d.ndim==2 and d.dtype.kind in 'fi' and g['time_axis'] in (0,1),'wave_source_axes');axis=g['time_axis'];lo,hi=g['start'],g['stop'];need(type(lo)is int and type(hi)is int and 0<=lo<hi<=g['permitted_stop']<=d.shape[axis] and d.shape[1-axis]==105,'wave_source_interval_extent')
        a=np.asarray(d[lo:hi,:] if axis==0 else d[:,lo:hi].T,float);valid=np.isfinite(a);result.append({'values':np.where(valid,a,0.).tolist(),'valid':valid.tolist(),'channel_ids':abi['scalp_channels'],'sample_rate_hz':500,'source_stage':stage,'source_start':lo,'source_stop':hi,'permitted_stop':g['permitted_stop'],'source_pin':source_pin,'no_boundary_bridge':True,'source_object':g['object_path']})
    return result

def container_rows(source,materials,events,binding,abi,guard):
    """Actual full-slot original MAT projection, derived from retained readers.
    The source-specific binding, original events and geometry are independently
    qualified inputs. Missing original native operators stay explicit gaps.
    """
    import h5py,os,stat
    from .constants import CONDITIONS,COUNTS,CONTEXTS,BANDS,GAZE
    from .panel import exact_text
    pin0=source['pin'];need(binding['source_sha256']==pin0['sha256'] and binding['qualification']=='source_stage_and_shapes_independently_qualified','source_binding');authenticate(pin0['path'],pin0['bytes'],pin0,guard)
    condition=source['condition'];expected=[m for m in materials if m['condition']==condition];need(len(expected)==COUNTS[condition],'all_material_slots');out=[];p=path_guard(pin0['path'],True);fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));before=os.fstat(fd)
    try:
        with os.fdopen(fd,'rb',closefd=False) as stream:
            with h5py.File(stream,'r') as h:
                sentence=h[binding['sentence_group']];names=binding['sentence_fields']
                for logical in ('content','rawData','word','omissionRate',*('mean_'+b for b in BANDS)):
                    need(logical in names and names[logical] in sentence and sentence[names[logical]].shape==(COUNTS[condition],1),'complete_sentence_columns',logical)
                for index,m in enumerate(expected):
                    guard();get=lambda logical:dereference(h,sentence[names[logical]],index);literal=source_text(get('content'));need(exact_text(literal)==exact_text(m['text']),'literal_source_material_join');ev=events[str(index)];need(ev['source_index']==index and ev['source_sha256']==pin0['sha256'] and ev['condition']==condition,'original_event_join')
                    raw=get('rawData');axis=binding['raw_time_axis'];need(axis in (0,1) and raw.ndim==2 and raw.shape[1-axis]==105,'original_source_geometry');duration=raw.shape[axis]/500;omission=source_scalar(get('omissionRate'));need(omission is None or 0<=omission<=1,'source_omission_fraction');word_object=get('word');words=[];fields=binding['word_fields'];roles={}
                    if isinstance(word_object,h5py.Group):
                        content=word_object[fields['content']];n=content.shape[0];need(content.shape==(n,1) and n<=200,'original_word_column')
                        for wi in range(n):
                            guard();w={'word':source_text(dereference(h,content,wi)),'original_word_index':wi,'windows':{},'original_band_roles':{}}
                            def word_field(logical):
                                name=fields.get(logical)
                                if name is None or name not in word_object:return None
                                need(word_object[name].shape==(n,1),'word_column_extent',logical);return dereference(h,word_object[name],wi)
                            for name in set(GAZE)|set(CONTEXTS):
                                d=word_field(name);w[name]=None if d is None else source_scalar(d)
                            for c in CONTEXTS:
                                vals=[]
                                for band in BANDS:
                                    logical=c+'_'+band;d=word_field(logical);v=[None]*105 if d is None else source_band(d);vals.extend(v);w['original_band_roles'][logical]={'status':'absent_source_field' if d is None else 'original_mean_read','shape':None if d is None else list(d.shape)}
                                    diff=word_field(logical+'_diff');w['original_band_roles'][logical+'_diff']={'status':'required_unscorable_native_difference','source_object':None if diff is None else diff.name,'shape':None if diff is None else list(diff.shape),'substitute_used':False}
                                pupil=word_field(c+'_pupilsize');geometry=binding['word_geometry'].get(f'{index}:{wi}:{c}');segments={stage:None for stage in ('raw_waveform','cleaned_waveform')};segments[binding['waveform_stage']]=None if geometry is None else materialize_segments(h,geometry,pin0,abi,binding['waveform_stage'],guard)
                                w['windows'][c]={'duration_ms':w[c],'pupil':None if pupil is None else source_scalar(pupil),'band_values':vals,'segments':segments,'status':'available' if w[c]is not None else 'unavailable','source_pin':{'container':pin0,'word_index':wi,'window':c,'geometry_status':'missing_native_interval' if geometry is None else 'qualified'}}
                            words.append(w)
                    else:
                        a=primitive(word_object,1);need(a.size==0 or (a.size==1 and not finite(float(a.reshape(-1)[0]))),'explicit_missing_word_object')
                    gaze=[];fractions=[]
                    for name in ('FFD','GD','GPT','TRT','nFixations'):
                        values=[w[name]for w in words if w[name]is not None];need(all(v>=0 for v in values),'gaze_nonnegative');fraction=len(values)/len(words) if words else 0.;gaze.extend([sum(values)/len(values)if values else None,fraction]);fractions.append(fraction)
                    gaze.extend([omission,duration]);waveforms={stage:None for stage in ('raw_waveform','cleaned_waveform')};geometry=binding['sentence_geometry'].get(str(index))
                    if geometry is not None:waveforms[binding['waveform_stage']]=materialize_segments(h,geometry,pin0,abi,binding['waveform_stage'],guard)
                    out.append({'person':source['person'],'condition':condition,'index':index,'text':literal,'words':words,'gaze_summary':gaze,'eeg_summary':[v for b in BANDS for v in source_band(get('mean_'+b))],'omission':omission,'duration_seconds':duration,'valid_gaze_fractions':fractions,'scalp_channel_ids':abi['scalp_channels'],'waveform_segments':waveforms,'presentation_order':ev['presentation_order'],'repetition_ordinal':ev['repetition_ordinal'],'block':ev['block'],'screen_instruction_present':ev['screen_instruction_present'],'session_elapsed':ev['session_elapsed'],'source_pin':pin0,'original_frontal_roles':{b:{'status':'required_unscorable_native_frontal_difference'}for b in BANDS}})
        key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns);need(key(before)==key(os.fstat(fd))==key(p.lstat()),'source_mutated_during_projection')
    finally:os.close(fd)
    return out
