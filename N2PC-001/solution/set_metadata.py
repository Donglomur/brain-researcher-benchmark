"""Bounded metadata-only MAT-v5 reader; adapted from the reviewed structural inspector.

No original signal payload decoding occurs here. The literal external FDT pointer
is checked before selected metadata and before the separately gated MNE reader.
"""
import io
import math
import struct
import zlib
import numpy as np
from scipy.io import loadmat
MAX_EXPANDED_BYTES=128*1024**2
MAX_METADATA_ELEMENTS=2_000_000

def need(ok,reason):
    if not ok:raise ValueError(reason)

class MatScan:
    """MAT-v5 headers only; numeric payload conversion occurs only in decode()."""
    def __init__(self, raw):
        need(len(raw)>=128 and not raw.startswith(b'MATLAB 7.3'),'unsupported_mat_representation')
        need(raw[126:128] in (b'IM',b'MI'),'unsupported_mat_endian')
        self.endian='<' if raw[126:128]==b'IM' else '>'
        need(struct.unpack(self.endian+'H',raw[124:126])[0]==0x0100,'unsupported_mat_version')
        self.header=raw[:128];self.expanded=0;self.nodes=0;self.metadata_elements=0
        self.top=self.elements(raw,128)

    def tag(self, raw, pos):
        need(0<=pos and pos+8<=len(raw),'truncated_mat_tag')
        packed=struct.unpack_from(self.endian+'I',raw,pos)[0]
        typ,small=packed&65535,packed>>16
        if small:
            need(0<small<=4 and 1<=typ<=18,'invalid_small_mat_tag')
            return typ,raw[pos+4:pos+4+small],pos+8
        typ,size=struct.unpack_from(self.endian+'II',raw,pos)
        need(1<=typ<=18 and pos+8+size<=len(raw),'mat_tag_bounds')
        end=pos+8+size
        nxt=end if typ==15 else end+((-size)%8)
        need(nxt<=len(raw),'truncated_mat_padding')
        return typ,raw[pos+8:end],nxt

    def matrix(self, body):
        self.nodes+=1;need(self.nodes<=50000,'matrix_count_bound')
        typ,flags,p1=self.tag(body,0);need(typ==6 and len(flags)==8,'matrix_flags')
        fl=struct.unpack_from(self.endian+'I',flags)[0]
        typ,dims,p2=self.tag(body,p1);need(typ==5 and len(dims)%4==0 and 0<len(dims)<=32,'matrix_dimensions')
        shape=struct.unpack(self.endian+'i'*(len(dims)//4),dims)
        need(all(v>=0 for v in shape) and math.prod(shape)<=128_000_000,'matrix_shape_bound')
        typ,name,p3=self.tag(body,p2);need(typ in (1,16),'matrix_name_storage')
        name=name.decode('utf-8');need('\0' not in name,'matrix_name')
        return dict(name=name,matlab_class=fl&255,shape=list(shape),is_complex=bool(fl&2048),
                    flags_and_dimensions=body[:p2],payload=body[p3:],body=body)

    def elements(self, raw, pos):
        result=[]
        while pos<len(raw):
            typ,payload,pos=self.tag(raw,pos)
            if typ==15:
                z=zlib.decompressobj();remaining=MAX_EXPANDED_BYTES-self.expanded
                block=z.decompress(payload,remaining+1)
                need(len(block)<=remaining and z.eof and not z.unused_data and not z.unconsumed_tail,'compressed_mat_bound_or_stream')
                self.expanded+=len(block)
                # Only one compression level is supported, never nested streams.
                inner_type,body,end=self.tag(block,0)
                need(inner_type==14 and end==len(block),'compressed_mat_structure')
                result.append(self.matrix(body))
            else:
                need(typ==14,'unsupported_top_mat_element');result.append(self.matrix(payload))
        return result

    def fields(self):
        roots={}
        for node in self.top:need(node['name'] not in roots,'duplicate_mat_variable');roots[node['name']]=node
        if 'EEG' not in roots:return roots,'flat_fields'
        need(len(roots)==1,'ambiguous_eeg_and_flat_fields')
        eeg=roots['EEG'];need(eeg['matlab_class']==2 and math.prod(eeg['shape'])==1,'non_scalar_eeg_struct')
        typ,value,p=self.tag(eeg['payload'],0);need(typ==5 and len(value)==4,'struct_field_name_width')
        width=struct.unpack(self.endian+'i',value)[0];need(0<width<=256,'struct_field_width_bound')
        typ,names,p=self.tag(eeg['payload'],p);need(typ==1 and len(names)%width==0,'struct_field_names')
        keys=[names[i:i+width].split(b'\0',1)[0].decode('utf-8') for i in range(0,len(names),width)]
        need(len(keys)<=512 and all(keys) and len(keys)==len(set(keys)),'struct_field_keys')
        fields={}
        for key in keys:
            typ,body,p=self.tag(eeg['payload'],p);need(typ==14,'struct_field_matrix')
            fields[key]=self.matrix(body)
        need(p==len(eeg['payload']),'unexpected_struct_tail')
        return fields,'scalar_EEG_struct'

    def decode(self, node):
        self.validate_metadata(node)
        # Repackage only this already selected field. Neither a whole EEG struct
        # nor a non-character data field enters scipy's value decoder.
        name=b'value';name_tag=struct.pack(self.endian+'II',1,len(name))+name+b'\0'*((-len(name))%8)
        body=node['flags_and_dimensions']+name_tag+node['payload']
        matrix=struct.pack(self.endian+'II',14,len(body))+body+b'\0'*((-len(body))%8)
        value=loadmat(io.BytesIO(self.header+matrix),variable_names=['value'],simplify_cells=True,verify_compressed_data_integrity=True)['value']
        return value

    def validate_metadata(self, node, depth=0):
        """Bound every nested cell/struct before scipy can allocate values."""
        count=math.prod(node['shape']);self.metadata_elements+=count
        need(depth<=32 and not node['is_complex'] and self.metadata_elements<=MAX_METADATA_ELEMENTS,'metadata_decode_bound')
        cls=node['matlab_class'];raw=node['payload'];pos=0
        if cls==2:
            typ,width,pos=self.tag(raw,pos);need(typ==5 and len(width)==4,'metadata_struct_width')
            width=struct.unpack(self.endian+'i',width)[0];need(0<width<=256,'metadata_struct_width_bound')
            typ,names,pos=self.tag(raw,pos);need(typ==1 and len(names)%width==0,'metadata_struct_names')
            keys=[names[i:i+width].split(b'\0',1)[0] for i in range(0,len(names),width)]
            need(len(keys)<=512 and all(keys) and len(keys)==len(set(keys)),'metadata_struct_keys')
            count*=len(keys)
        if cls in (1,2):
            need(count<=MAX_METADATA_ELEMENTS,'metadata_child_count_bound')
            for _ in range(count):
                typ,body,pos=self.tag(raw,pos);need(typ==14,'metadata_child_matrix')
                # Classic MAT-v5 permits a zero-byte miMATRIX child to denote
                # an empty value. Only selected metadata containers admit it;
                # top-level/data/EEG matrices still require ordinary headers.
                if body:self.validate_metadata(self.matrix(body),depth+1)
        elif cls==4:
            typ,data,pos=self.tag(raw,pos)
            need(typ in (1,2,4,16,17,18) and len(data)<=4*count,'metadata_character_storage')
        elif cls in range(6,16):
            typ,data,pos=self.tag(raw,pos)
            widths={1:1,2:1,3:2,4:2,5:4,6:4,7:4,9:8,12:8,13:8}
            need(typ in widths and len(data)==count*widths[typ],'metadata_numeric_storage')
        else:raise ValueError('unsupported_metadata_matlab_class')
        need(pos==len(raw),'metadata_payload_tail')


def scalar(value, budget=None):
    if budget is None:budget=[MAX_METADATA_ELEMENTS]
    budget[0]-=1;need(budget[0]>=0,'metadata_value_count_bound')
    if isinstance(value,np.generic):return scalar(value.item(),budget)
    if isinstance(value,np.ndarray):
        if value.size==0:return None
        if value.size==1:return scalar(value.reshape(-1)[0],budget)
        return scalar(value.tolist(),budget)
    if isinstance(value,bytes):return value.decode('utf-8')
    if value is None or isinstance(value,(str,bool,int)):return value
    if isinstance(value,float):return value if math.isfinite(value) else {'source_nonfinite':repr(value)}
    if isinstance(value,dict):return {str(k):scalar(v,budget) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [scalar(v,budget) for v in value]
    raise ValueError('unsupported_metadata_value_type')


def records(value):
    if value is None:return []
    if isinstance(value,dict):return [value]
    if isinstance(value,np.ndarray):return list(value.reshape(-1))
    if isinstance(value,(list,tuple)):return list(value)
    raise ValueError('unsupported_metadata_record_layout')
