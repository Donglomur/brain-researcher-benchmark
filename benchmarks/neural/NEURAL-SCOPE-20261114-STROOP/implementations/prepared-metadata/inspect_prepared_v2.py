"""Prepared Stroop metadata inspection: stream signal bytes, never decode signals.
Uses the exact previously reviewed MAT5 streaming and small-metadata readers.
No network, native package, clock fitting, marker shifting or scientific scoring.
"""
import hashlib, io, json, math, re, struct, zlib
from decimal import Decimal
from pathlib import PurePosixPath

SMALL_SHA = "8fb8294bc59a04987884f8b46592386fe84def2dcd9a8bbd0a3ddd2a4588ff1e"
FIELDS = ("oxyData","dxyData","totalData","T","nch","vector_onset",
          "probeSet","exception_channel","subject","system","probe2d","probe3d","preprocessSet")
FORMATS = {1:"b",2:"B",3:"h",4:"H",5:"i",6:"I",7:"f",9:"d",12:"q",13:"Q"}
CHUNK = 65536
SMALL_CAP = 65536
MAX_SAMPLES = 1048576
MAX_FILE = 33554432
MAX_MATRIX = 1073741824
MAX_RECORD_REPORT = 1048576

def need(ok, message):
    if not ok: raise ValueError(message)

def readers(small_source, donor_source):
    need(len(small_source)==6884 and hashlib.sha256(small_source).hexdigest()==SMALL_SHA,
         "exact accepted small-metadata source")
    # Three explicit metadata-profile changes: unnamed nested root, 64 KiB
    # extent, and retaining the logical flag at every metadata node.
    old='and item["name"] and item["name"] not in result'
    text=small_source.decode()
    need(text.count(old)==1, "one exact unnamed-nested metadata guard")
    text=text.replace(old,'and item["name"] not in result')
    result_old='result={"class":cls,"name":name,"shape":shape}'
    need(text.count(result_old)==1,"one exact metadata logical-flag projection")
    text=text.replace(result_old,'result={"class":cls,"name":name,"shape":shape,"logical":bool(bits&0x200)}')
    ns={"__name__":"stroop_existing_small_metadata"}
    exec(compile(text,"accepted_small_metadata_nested_profile","exec"),ns)
    ns["MAX_FILE"]=SMALL_CAP+128
    ns["MAX_INFLATED"]=SMALL_CAP
    p=ns["primitives"](donor_source)
    return p,ns["decode"]

class SequentialFile:
    """Hash and CRC the one forward physical read, before any completion claim."""
    def __init__(self, file, size):
        self.file=file; self.size=size; self.pos=0
        self.sha=hashlib.sha256(); self.crc=0; self.maximum_read=0
    def seek(self, pos):
        need(pos==self.pos, "no physical reread or seek over unseen bytes")
        return pos
    def read(self, n):
        need(type(n)is int and 0<=n<=CHUNK and n<=self.size-self.pos,
             "bounded sequential physical read")
        b=self.file.read(n);need(len(b)==n,"complete selected physical read")
        self.pos+=n;self.maximum_read=max(self.maximum_read,n)
        self.sha.update(b);self.crc=zlib.crc32(b,self.crc)
        return b

def _field(p, stream, end, cap=4096):
    return p.metadata(stream,"<",min(cap,end-stream.pos))

def _matrix_header(p, stream, parent_end):
    start=stream.pos;k,n,small=p.tag(stream,"<")
    need(k==14 and small is None and 0<=n<=MAX_MATRIX and stream.pos+n<=parent_end,
         "bounded complete nested matrix")
    end=stream.pos+n
    k,b=_field(p,stream,end);need(k==6 and len(b)==8,"matrix flags")
    bits,nz=struct.unpack("<II",b);cls=bits&255
    need(not bits&0xA00 and nz==0,"dense real nonlogical matrix")
    k,b=_field(p,stream,end);need(k==5 and len(b)%4==0 and 8<=len(b)<=16,"matrix axes")
    shape=list(struct.unpack("<"+"i"*(len(b)//4),b))
    need(all(0<=x<=MAX_SAMPLES for x in shape),"finite declared dimensions")
    k,b=_field(p,stream,end);need(k==1 and len(b)<=255,"matrix name")
    name=b.decode("ascii")
    return {"start":start,"bytes":n,"end":end,"class":cls,"shape":shape,"name":name}

def _close(stream, row):
    need(stream.pos==row["end"],"exact nested matrix consumption")
    need(not any(stream.read((-row["bytes"])%8)),"zero matrix padding")

def _numeric(p, stream, row, visit=None):
    need(row["class"] in range(6,16),"dense numeric field")
    k,n,small=p.tag(stream,"<")
    count=p.product(row["shape"])
    need(k in FORMATS and n==count*p.STORAGE[k] and
         (small is not None or stream.pos+n+(-n)%8<=row["end"]),
         "numeric storage agrees with declared dimensions")
    item=p.STORAGE[k];index=0
    if small is not None:
        blocks=(small,)
    else:
        def chunks():
            remaining=n
            while remaining:
                take=min(remaining,CHUNK-(CHUNK%item))
                yield stream.read(take);remaining-=take
        blocks=chunks()
    for b in blocks:
        if visit is not None:
            for value, in struct.iter_unpack("<"+FORMATS[k],b):
                visit(index,value);index+=1
    if small is None:need(not any(stream.read((-n)%8)),"zero numeric padding")
    _close(stream,row)
    return {"class":row["class"],"storage_type":k,"shape":row["shape"],"stored_bytes":n}

def _small(p, decode, stream, parent_end, header):
    # Read a whole small metadata element only after its finite extent is admitted.
    k,n,inline=p.tag(stream,"<")
    need(k==14 and inline is None and 8+n+(-n)%8<=SMALL_CAP and
         stream.pos+n+(-n)%8<=parent_end,"bounded existing small metadata profile")
    body=stream.read(n);padding=stream.read((-n)%8)
    need(not any(padding),"small metadata zero padding")
    wrapped=header+struct.pack("<II",14,n)+body+padding
    result=decode(wrapped,p)
    need(len(result["variables"])==1,"one nested metadata matrix")
    return next(iter(result["variables"].values()))

def _scalar(value, name):
    need(value["class"] in range(6,16) and value["shape"]==[1,1] and
         len(value.get("values",[]))==1, "saved "+name+" scalar")
    need(not value["logical"],"nonlogical saved "+name)
    n=value["values"][0];need(math.isfinite(n),"finite saved "+name)
    return n

def preprocessing_evidence(value, T):
    """Read ordered function/parameter literals; never execute source strings."""
    result={"status":"unresolved_metadata_form","ordered_steps_private":[],
            "trim":None,"time_preserving_history_verified":False}
    if value["logical"] or value["class"]!=1 or len(value["shape"])!=2 or min(value["shape"]) not in (0,1):
        return result
    steps=[]
    for step in value["cells"]:
        if step["logical"] or step["class"]!=1 or len(step["shape"])!=2 or min(step["shape"]) not in (0,1):
            return result
        if not all(x["class"]==4 and not x["logical"] for x in step["cells"]):return result
        steps.append([x["text"] for x in step["cells"]])
    result["ordered_steps_private"]=steps;result["status"]="literal_cell_steps_observed"
    trim=[(i,x) for i,x in enumerate(steps) if x and x[0]=="NR_segment"]
    # This documents the finite original GUI shape. Unknown/custom steps are not
    # interpreted, and a later resampling step prevents deriving crop sample counts.
    known={"NR_segment","NR_detrend","NR_motioncorrection","NR_filter"}
    time_preserving=all(x and x[0] in known for x in steps)
    result["time_preserving_history_verified"]=False
    result["source_supported_known_step_names_only"]=time_preserving
    if len(trim)!=1:
        result["trim_status"]="missing" if not trim else "ambiguous_multiple_trim_steps"
        return result
    index,step=trim[0]
    decimal=re.compile(r"(?:0|[1-9]\d*)(?:\.\d+)?")
    if len(step)!=3 or not all(decimal.fullmatch(x) for x in step[1:]):
        result["trim_status"]="nonliteral_or_unsupported_trim_parameters";return result
    left,right=map(Decimal,step[1:])
    result["trim"]={"step_index":index,"left_seconds_literal":step[1],
                    "right_seconds_literal":step[2],"source":"saved NR_segment metadata"}
    result["trim_status"]="one_literal_trim_step"
    result["trim"]["removed_sample_counts"]=None
    result["trim"]["sample_count_limit"]="No count inferred: historical runtime/order and pre-trim T not independently authenticated."
    return result

def validate_roster(rows):
    need(type(rows)is list and len(rows)==165,"complete165 prepared-record roster")
    need([r["index"] for r in rows]==list(range(165)),"exact complete ordered indices")
    seen=set();sessions={i:set() for i in (1,2,3)};members=set()
    for r in rows:
        need(type(r["session"])is int and r["session"] in sessions,"one of3 sessions")
        sid=r["source_id"];need(type(sid)is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}",sid),
                               "literal internal recording ID")
        key=(r["session"],sid);need(key not in seen,"unambiguous recording/session join")
        seen.add(key);sessions[r["session"]].add(sid)
        path=PurePosixPath(r["member"])
        need(not path.is_absolute() and ".." not in path.parts and path.suffix==".mat" and
             path.stem==sid and path.parts[-2]=="prep" and
             path.parts[-3]=="test"+str(r["session"]),"exact member/session/embedded marker-ID join")
        need(r["member"] not in members,"unique exact archive member");members.add(r["member"])
        need(type(r["bytes"])is int and 128<=r["bytes"]<=MAX_FILE and
             type(r["crc32"])is int and 0<=r["crc32"]<2**32,"exact ZIP-derived member extent/CRC")
        need(type(r["matrix_bytes"])is int and 1<=r["matrix_bytes"]<=MAX_MATRIX and
             type(r["compressed_element_bytes"])is int and
             r["compressed_element_bytes"]+136==r["bytes"],"exact retained compressed/root extents")
        need(r["fields"]==list(FIELDS),"all165 observed scalar-struct field roster")
        markers=r["marker_onsets"]
        need(type(markers)is dict and set(markers)=={"11","12","13","101","102"},
             "complete observed marker-code columns")
        for code,onsets in markers.items():
            need(type(onsets)is list and len(onsets)<=4096 and
                 all(type(x)is int and 1<=x<=MAX_SAMPLES for x in onsets) and
                 all(a<b for a,b in zip(onsets,onsets[1:])),"strict source-native marker indices")
    need(all(len(v)==55 for v in sessions.values()) and
         sessions[1]==sessions[2]==sessions[3],"complete55-ID×3-session scope")
    return {"records":165,"source_internal_ids":55,"sessions":3}

def inspect_one(file, expected, p, decode):
    f=SequentialFile(file,expected["bytes"]);header=f.read(128)
    need(p.is_mat5(header) and header[126:128]==b"IM" and
         struct.unpack("<H",header[124:126])[0]==256 and
         header[116:124] in (b"\0"*8,b" "*8),"observed little-endian MAT5 profile")
    outer=p.Segment(f,128,expected["bytes"]);k,n,small=p.tag(outer,"<")
    need(k==15 and small is None and n==expected["compressed_element_bytes"] and
         136+n==expected["bytes"],"one exact retained compressed root")
    stream=p.Inflated(p.Segment(f,136,expected["bytes"]),
                      8+expected["matrix_bytes"]+(-expected["matrix_bytes"])%8,CHUNK)
    root=_matrix_header(p,stream,stream.limit)
    need(root["bytes"]==expected["matrix_bytes"] and root["class"]==2 and
         root["shape"]==[1,1] and root["name"]=="nirsdata","observed scalar nirsdata root")
    k,b=_field(p,stream,root["end"]);need(k==5 and len(b)==4,"root field width")
    width=struct.unpack("<i",b)[0];need(1<=width<=64,"root field width bound")
    k,b=_field(p,stream,root["end"]);need(k==1 and len(b)%width==0,"root field table")
    fields=[]
    for off in range(0,len(b),width):
        head,sep,tail=b[off:off+width].partition(b"\0")
        need(sep and head and not any(tail),"literal root field")
        fields.append(head.decode("ascii"))
    need(fields==expected["fields"] and len(set(fields))==len(fields),"exact retained root field roster")
    signals={};metadata={};samples=None;vector=None
    for name in fields:
        if name in ("oxyData","dxyData","totalData"):
            row=_matrix_header(p,stream,root["end"])
            need(row["name"] in ("",name) and len(row["shape"])==2 and
                 1<=row["shape"][0]<=MAX_SAMPLES and row["shape"][1]==35,"source35-channel signal axes")
            if samples is None:samples=row["shape"][0]
            need(samples==row["shape"][0],"same sample axes across all3 Hb fields")
            signals[name]=_numeric(p,stream,row)
        elif name=="vector_onset":
            row=_matrix_header(p,stream,root["end"])
            need(row["name"] in ("",name) and row["shape"]==[samples,1],
                 "prepared onset vector has signal sample axis")
            wanted={int(k):set(v) for k,v in expected["marker_onsets"].items()}
            counts={};matched={k:0 for k in wanted};mismatches={k:0 for k in wanted}
            def observe(i,v):
                need(math.isfinite(v) and int(v)==v and -2147483648<=v<2147483648,
                     "finite integer onset codes")
                code=int(v);pos=i+1
                if code:
                    need(code in counts or len(counts)<256,"finite distinct onset code census")
                    counts[code]=counts.get(code,0)+1
                for desired,indices in wanted.items():
                    if pos in indices:
                        if code==desired:matched[desired]+=1
                        else:mismatches[desired]+=1
            info=_numeric(p,stream,row,observe)
            vector={"schema":info,"nonzero_code_counts":{str(k):v for k,v in counts.items()},
                    "direct_marker_comparison":{str(k):{"expected":len(wanted[k]),"same_index_same_code":matched[k],
                    "wrong_code_at_expected_index":mismatches[k],
                    "expected_indices_outside_sample_axis":sum(x>samples for x in wanted[k]),
                    "vector_count":counts.get(k,0),"exact":matched[k]==len(wanted[k])==counts.get(k,0)}
                    for k in wanted},"indices_shifted":False}
        else:
            value=_small(p,decode,stream,root["end"],header)
            need(value["name"] in ("",name),"literal nested metadata field name")
            metadata[name]=value
    _close(stream,root);stream.finish()
    need(f.pos==expected["bytes"] and f.crc==expected["crc32"],"complete one-pass member extent and ZIP CRC")
    T=_scalar(metadata["T"],"T");need(T>0,"positive saved T")
    nch=_scalar(metadata["nch"],"nch");need(nch==35,"saved channel count agrees with matrices")
    subject=metadata["subject"]
    need(subject["class"]==4 and not subject["logical"] and subject["text"]==expected["source_id"],
         "saved subject exactly matches marker ID and archive basename; no fuzzy join")
    preprocessing=preprocessing_evidence(metadata["preprocessSet"],T)
    result={"schema":"stroop_prepared_schema_clock_inspection_v1","index":expected["index"],
            "saved_subject_join":"exact","session":expected["session"],
            "file_integrity":{"bytes":f.pos,"crc32":f.crc,"sha256":f.sha.hexdigest(),
            "maximum_physical_read_bytes":f.maximum_read,"publisher_SHA256_predeclared":False},
            "signals":signals,"signal_values_decoded":False,"signal_finiteness_verified":False,
            "clock":{"saved_T_seconds":T,"saved_T_source":"nirsdata.T scalar",
                     "explicit_original_time_vector":"absent from observed root field roster",
                     "uniform_time_verified":False,"fitted_or_replaced_clock":False},
            "onsets":vector,"preprocessing":preprocessing,
            "metadata_private":metadata,
            "units":{"concentration_pathlength_scale":"unresolved; no explicit root unit field",
                     "geometry_units_not_concentration_units":True},
            "endpoints":{"original_author":"onset-127 through onset+640 inclusive:768 samples",
                         "proposed_benchmark":"640x70/25 s at advertised25.6 Hz is distinct;40x70 transform unqualified",
                         "relation_inferred":False},
            "scientific_ready":False}
    need(len(json.dumps(result,allow_nan=False).encode())<=MAX_RECORD_REPORT,"bounded private record report")
    return result

def inspect_population(rows, opener, sink, p, decode):
    census=validate_roster(rows)  # Before the first member-body opener.
    total=0;exact=0;T_values=set()
    for row in rows:
        with opener(row) as f:result=inspect_one(f,row,p,decode)
        total+=result["file_integrity"]["bytes"]
        exact+=all(x["exact"] for x in result["onsets"]["direct_marker_comparison"].values())
        T_values.add(result["clock"]["saved_T_seconds"])
        sink(result)  # Caller retires each bounded private report; no cohort array.
    return {"schema":"stroop165_complete_prepared_metadata_inspection_v1",**census,
            "complete":True,"physical_member_bytes":total,"records_with_exact_direct_marker_join":exact,
            "distinct_saved_T_values":sorted(T_values),"signal_arrays_materialized":False,
            "clock_fitted":False,"marker_shifted":False,"scientific_ready":False}

