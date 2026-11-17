"""Same-byte primitive NPZ admission; no candidate pickle/path is executed."""
import io,math,stat,zipfile
from .core import need
def decode(raw, shapes, cap):
    import numpy as np
    need(type(raw)is bytes and 0<len(raw)<=cap,'bounded NPZ')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=z.infolist()
        need(len(members)==len(shapes) and {m.filename for m in members}=={k+'.npy' for k in shapes},'exact unique arrays')
        need(sum(m.file_size for m in members)<=cap,'expanded NPZ bound')
        for m in members:
            need(not m.is_dir() and not m.flag_bits&1 and m.compress_type in (0,8)
                 and not stat.S_ISLNK(m.external_attr>>16),'ordinary array member')
            with z.open(m) as f:
                version=np.lib.format.read_magic(f)
                if version==(1,0):shape,order,dtype=np.lib.format.read_array_header_1_0(f,max_header_size=4096)
                elif version==(2,0):shape,order,dtype=np.lib.format.read_array_header_2_0(f,max_header_size=4096)
                else:raise ValueError('NPYv1/2 required')
                need(tuple(shape)==tuple(shapes[m.filename[:-4]]) and dtype.kind=='f' and dtype.itemsize in (4,8) and dtype.fields is None,'exact float support')
                need(math.prod(shape)*dtype.itemsize+f.tell()==m.file_size,'exact primitive extent')
    with np.load(io.BytesIO(raw),allow_pickle=False,max_header_size=4096) as z:
        out={k:z[k] for k in shapes}
    need(all(np.isfinite(v).all() for v in out.values()),'all coordinates finite');return out
def encode(values):
    import numpy as np
    stream=io.BytesIO();np.savez_compressed(stream,**values);return stream.getvalue()

