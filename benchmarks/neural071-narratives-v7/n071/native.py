"""Qualified native decoders and complete bilateral400 projection; never run in build controls."""
import io
import hashlib
import struct
import wave
from .errors import need
from .extraction import aligned_words,guarded_indices,primitives,GPT2Extractor

def pcm(body):
    import numpy as np
    with wave.open(io.BytesIO(body),"rb") as w:
        channels=w.getnchannels();width=w.getsampwidth();rate=w.getframerate();frames=w.getnframes()
        need(channels in (1,2) and width in (2,3,4) and rate>=16000 and
             frames*channels*width<=1500000000 and w.getcomptype()=="NONE","bounded-pcm")
        raw=w.readframes(frames)
        need(len(raw)==frames*channels*width,"complete-pcm")
    if width==3:
        a=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3).astype(np.int32)
        v=a[:,0]+(a[:,1]<<8)+(a[:,2]<<16);v=np.where(v&(1<<23),v-(1<<24),v)
    else:v=np.frombuffer(raw,dtype="<i"+str(width))
    return v.astype(np.float64).reshape(-1,channels).mean(axis=1)/(2**(8*width-1)),rate

def gifti(body,source):
    import numpy as np
    from defusedxml.ElementTree import fromstring
    import nibabel as nib
    need(len(body)==source["bytes"] and len(source["etag"])==32 and
         hashlib.md5(body).hexdigest()==source["etag"],"native-source-etag")
    arrays=fromstring(body).findall("DataArray")
    need(1<=len(arrays)<=10000,"native-time-array-count")
    for a in arrays:
        need(a.get("ExternalFileName","")=="" and a.get("Encoding") in ("GZipBase64Binary","Base64Binary")
             and a.get("DataType")=="NIFTI_TYPE_FLOAT32" and a.get("Dimensionality")=="1" and
             a.get("Dim0")=="40962","internal-fsaverage6-float32")
    image=nib.gifti.GiftiImage.from_bytes(body)
    result=np.stack([a.data for a in image.darrays]).astype(np.float64)
    need(result.shape==(len(arrays),40962) and np.isfinite(result).all(),"native-complete-finite")
    return result

def annotation_layout(body):
    """Bounded format-only parsing. Numeric/native agreement remains unqualified."""
    need(type(body)is bytes and len(body)<=1000000,"annotation-body-cap")
    stream=io.BytesIO(body)
    def integer():
        b=stream.read(4);need(len(b)==4,"annotation-integer")
        return struct.unpack(">i",b)[0]
    def text():
        n=integer();need(0<n<=1000000,"annotation-string-extent")
        b=stream.read(n);need(len(b)==n and b.endswith(b"\0"),"annotation-string")
        return b[:-1]
    n=integer();need(n==40962,"annotation-vertices")
    vertices=[];codes=[]
    for _ in range(n):vertices.append(integer());codes.append(integer())
    need(vertices==list(range(n)) and integer()!=0,"annotation-vertex-order-colortable")
    entries=integer();table={}
    if entries>0:
        need(entries==201,"annotation-table201");text()
        for index in range(entries):
            name=text();rgba=[integer() for _ in range(4)]
            need(all(0<=v<=255 for v in rgba),"annotation-rgba")
            table[index]=(name,rgba[0]+(rgba[1]<<8)+(rgba[2]<<16))
    else:
        need(entries==-2 and integer()==201,"annotation-version2-table201");text()
        count=integer();need(count==201,"annotation-populated201")
        for _ in range(count):
            index=integer();need(index not in table and 0<=index<=200,"annotation-table-index")
            name=text();rgba=[integer() for _ in range(4)]
            need(all(0<=v<=255 for v in rgba),"annotation-rgba")
            table[index]=(name,rgba[0]+(rgba[1]<<8)+(rgba[2]<<16))
    need(stream.tell()==len(body) and len({v[0] for v in table.values()})==201,"annotation-eof-names")
    mapping={v[1]:k for k,v in table.items()}
    need(len(mapping)==201 and all(c==0 or c in mapping for c in codes),"annotation-known-labels")
    labels=[-1 if c==0 else mapping[c] for c in codes]
    need(set(range(1,201))<=set(labels),"nonempty200-positive-parcels")
    return {"labels":labels,"names":[table[i][0] for i in range(201)],
            "color_codes":[table[i][1] for i in range(201)],"version":1 if entries>0 else 2}

def annotation(body):
    """Native conversion is a separate qualified numerical leaf."""
    import numpy as np
    return np.asarray(annotation_layout(body)["labels"],dtype=np.int32)

def project(values,labels):
    import numpy as np
    need(values.ndim==2 and values.shape[1]==40962,"projection-vertices")
    return np.stack([values[:,labels==j].mean(axis=1) for j in range(1,201)],axis=1)

class Preparation:
    def __init__(self,qualification,store,journal):
        self.binding=qualification.require(journal.generation,journal.source)
        self.store=store;self.journal=journal

    def scan(self,scan,source,atlas,clock,extractor):
        import numpy as np
        need(source["scan"]==clock["scan"]==scan["id"] and clock["tr_seconds"]==scan["tr_seconds"] and
             clock["new_query_response_optimization"] is False and
             clock["derivative_clock_verified"] is True,"native-clock-join")
        need(atlas["name"]=="Schaefer2018_400Parcels_17Networks_order_fsaverage6","fixed-atlas")
        selected=self.binding["atlas"]
        need(atlas["L"]==selected["L"] and atlas["R"]==selected["R"] and
             atlas["L"] is not None and atlas["R"] is not None,"selected-atlas-content")
        ys=[]
        for hemi in ("L","R"):
            labels=annotation(self.store.read(atlas[hemi]))
            values=gifti(self.store.read(source["hemispheres"][hemi]),scan["derivatives"][hemi])
            ys.append(project(values,labels))
        need(ys[0].shape==ys[1].shape,"bilateral-support")
        y=np.concatenate(ys,axis=1)
        need(len(y)==clock["n_volumes"],"native-volume-count")
        events=[e for e in scan["events"] if e["trial_type"]=="story"]
        need(len(clock["segments"])==len(events),"all-story-segments")
        parts=[]
        for k,(event,c) in enumerate(zip(events,clock["segments"])):
            need(c["event_index"]==k and c["stim_file"]==event["stim_file"] and
                 c["story_start"]==float(event["onset"]) and
                 c["story_stop"]==float(event["onset"])+float(event["duration"]),"story-event-clock")
            stimulus=source["stimuli"][event["stim_file"]]
            expected=self.binding["alignments"][event["stim_file"]]
            need(expected is not None and stimulus["gentle"]==expected and
                 c["gentle_sha256"]==expected["sha256"] and
                 c["audio_sha256"]==stimulus["audio"]["sha256"],"exact-variant-alignment")
            audio,rate=pcm(self.store.read(stimulus["audio"]))
            words,missing=aligned_words(self.store.read(stimulus["gentle"]))
            words=[dict(w,start=w["start"]-c["gentle_at_audio_zero"],
                        end=w["end"]-c["gentle_at_audio_zero"]) for w in words]
            idx=guarded_indices(len(y),scan["tr_seconds"],clock["first_sample_scanner_seconds"],
                                c["story_start"],c["story_stop"])
            full_clock=dict(c,first_sample_scanner_seconds=clock["first_sample_scanner_seconds"])
            primitive=primitives(audio,rate,words,full_clock,idx,scan["tr_seconds"],extractor)
            parts.append({"segment":k,"indices":idx,"target":y[idx],
                          "primitives":primitive,"missing_alignments":missing})
        return {"scan":scan["id"],"source":source,"atlas":atlas,"clock":clock,"parts":parts}

    def all_scans(self,census,sources,atlas,clocks):
        from .support import release_census
        cases=release_census(census)
        selected={r for c in cases for r in c["train"]+c["query"]}
        need(set(sources)==set(clocks)==selected and len(selected)==572,"complete-preparation-scans")
        model=self.binding["model"]
        need(model["gpt2_commit"]=="607a30d783dfa663caf39e06633721c8d4cfcd7e" and
             model["transformers_commit"]=="8cb5963cc22174954e7dca2c0a3320b7dc2f4edc","fixed-model-source")
        self.store.budget.attempt("creation_attempts","fixed-GPT2-model-creation")
        rid=self.journal.begin("S05","fixed-GPT2-model-load",[model],{"fixed_extractor":True})
        try:
            extractor=GPT2Extractor(model["qualified_local_model"],model["qualified_local_tokenizer"])
        except BaseException:
            self.store.budget.unknown.append({"effect":"fixed-model-load","unacknowledged_capacity":
                                            "native model-loader IO/allocation; original failure retained"})
            raise
        self.journal.finish(rid,{"fixed_extractor":model},{"kind":"actual-model-constructor-return"})
        by_id={s["id"]:s for s in census["scans"]};out={}
        for sid in sorted(selected):
            rid=self.journal.begin("S04-S05","native-primitives",[sources[sid],atlas,clocks[sid]],{"scan":sid})
            value=self.scan(by_id[sid],sources[sid],atlas,clocks[sid],extractor)
            from .codec import pack
            artifact=pack(self.store,"prepared-"+sid,value)
            receipt=self.journal.finish(rid,{"projection":artifact},{"kind":"native-projection-return"})
            out[sid]={"artifact":artifact,"receipt":receipt}
        return out
