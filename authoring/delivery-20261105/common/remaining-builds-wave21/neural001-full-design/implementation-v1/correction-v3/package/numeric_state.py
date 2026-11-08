"""Candidate state is bounded numeric NPY members, never pickle or source.

This format restriction does not prove arbitrary numeric bytes cannot encode a
program. Semantic method review and actual process custody remain separate gates.
"""
import ast
import io
import math
import re
import struct
import zipfile
from .protocol import require


def validate_state(body, *, expanded_cap, progress):
    require(type(body)is bytes and len(body)>=26,'complete bounded candidate state ZIP')
    require(type(expanded_cap)is int and expanded_cap>0,'prospective full expanded state cap')
    end=struct.unpack('<4s4H2LH',body[-22:])
    sig,disk,start,on_disk,total,size,offset,comment=end
    require(sig==b'PK\x05\x06' and disk==start==comment==0 and on_disk==total
            and 1<=total<=64 and 0<size<=65536 and offset+size==len(body)-22,
            'bounded ordinary complete non-ZIP64 state directory')
    progress({'operation':'candidate_state_zip_directory','logical_read_bytes':size,
              'prospective_expanded_bytes':size})
    import numpy as np
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        entries=z.infolist()
        require(len(entries)==total and len({x.filename for x in entries})==total,'unique state members')
        require(all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}\.npy',x.filename)
                    and not(x.flag_bits&1) and x.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                    and 0<x.file_size<=expanded_cap for x in entries),'numeric NPY members only')
        require(sum(x.file_size for x in entries)<=expanded_cap,'complete expanded state admission')
        rows=[]
        for x in entries:
            progress({'operation':'candidate_state_member','logical_read_bytes':x.compress_size,
                      'prospective_expanded_bytes':x.file_size})
            encoded=z.read(x)
            require(encoded[:6]==b'\x93NUMPY' and encoded[6:8] in (b'\x01\x00',b'\x02\x00'),'NPY1/2 state only')
            start=10 if encoded[6]==1 else 12
            count=int.from_bytes(encoded[8:start],'little')
            require(0<count<=4096 and start+count<=len(encoded),'bounded complete literal header')
            header=ast.literal_eval(encoded[start:start+count].decode('ascii').strip())
            require(type(header)is dict and set(header)=={'descr','fortran_order','shape'}
                    and header['fortran_order'] is False,'plain C-order numeric state')
            require(type(header['descr'])is str and re.fullmatch(r'[<|][bifu][1248]',header['descr']),
                    'fixed little-endian scalar numeric dtype, no objects/strings/structures')
            dtype=np.dtype(header['descr']);shape=header['shape']
            require(type(shape)is tuple and len(shape)<=8 and all(type(n)is int and n>=0 for n in shape),
                    'bounded nonnegative shape')
            n=math.prod(shape)
            require(start+count+n*dtype.itemsize==len(encoded),'exact NPY extent')
            values=np.frombuffer(encoded,dtype=dtype,offset=start+count,count=n)
            for lo in range(0,n,65536):
                hi=min(n,lo+65536)
                progress({'operation':'candidate_state_finite_block','logical_read_bytes':(hi-lo)*dtype.itemsize,
                          'prospective_expanded_bytes':hi-lo})
                require(np.isfinite(values[lo:hi]).all(),'finite numeric candidate state')
            rows.append({'name':x.filename,'dtype':dtype.str,'shape':list(shape),'bytes':n*dtype.itemsize})
    return {'format':'numeric_npz_only_v1','members':rows,'expanded_npy_bytes':sum(x.file_size for x in entries),
            'does_not_certify_semantics_or_isolation':True}
