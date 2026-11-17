"""Nonexecutable complete state/array serialization using exact NPY1 artifacts."""
import io
from .errors import need
from .identity import exact

def save_array(store,name,array,prediction=False):
    import numpy as np
    a=np.asarray(array)
    need(a.dtype.kind in "fiu" and np.isfinite(a).all(),"numeric-state-array")
    if prediction:
        a=np.ascontiguousarray(a,dtype="<f4")
        need(a.ndim==2 and a.shape[1]==400 and np.isfinite(a).all(),"prediction-array")
    else:
        a=np.ascontiguousarray(a,dtype=a.dtype.newbyteorder("<"))
    out=io.BytesIO()
    np.lib.format.write_array(out,a,version=(1,0),allow_pickle=False)
    return {"artifact":store.write(name,out.getvalue()),"shape":list(a.shape),"dtype":a.dtype.str}

def load_array(store,record,prediction=False):
    import numpy as np
    exact(record,("artifact","shape","dtype"))
    body=store.read(record["artifact"])
    need(body[:8]==b"\x93NUMPY\x01\x00","npy1")
    stream=io.BytesIO(body)
    array=np.lib.format.read_array(stream,allow_pickle=False)
    need(stream.tell()==len(body) and list(array.shape)==record["shape"] and
         array.dtype.str==record["dtype"] and array.flags.c_contiguous and
         array.dtype.kind in "fiu" and np.isfinite(array).all(),"array-complete")
    if prediction:
        need(array.dtype.str=="<f4" and array.ndim==2 and array.shape[1]==400,"prediction-format")
    return array

def pack(store,prefix,value):
    """Each numeric array has an independent immutable identity; no pickle."""
    import numpy as np
    counter=[0]
    def visit(v):
        if isinstance(v,np.ndarray):
            counter[0]+=1
            return {"__n071_array__":save_array(store,f"{prefix}-{counter[0]:06}.npy",v)}
        if isinstance(v,np.generic):
            return v.item()
        if type(v) in (str,int,float,bool) or v is None:return v
        if type(v) in (tuple,list):return [visit(x) for x in v]
        need(type(v)is dict and all(type(k)is str for k in v),"state-data-only")
        need("__n071_array__" not in v,"state-reserved-key")
        return {k:visit(x) for k,x in v.items()}
    return store.put(prefix+".json",visit(value))

def unpack(store,record):
    def visit(v):
        if type(v)is dict and "__n071_array__" in v:
            exact(v,("__n071_array__",))
            return load_array(store,v["__n071_array__"])
        if type(v)is dict:return {k:visit(x) for k,x in v.items()}
        if type(v)is list:return [visit(x) for x in v]
        return v
    return visit(store.json(record))


def artifacts(store,record):
    """Inspect only the declared JSON+array grammar; never decode an array body.

    Arbitrary descriptors embedded as ordinary scientific/provenance metadata are
    not followed. Additional state capsules are explicit caller mounts.
    """
    from .identity import descriptor
    descriptor(record)
    result={record["path"]:record}
    def visit(value):
        if type(value)is dict and "__n071_array__" in value:
            exact(value,("__n071_array__",))
            a=value["__n071_array__"]
            exact(a,("artifact","shape","dtype"))
            d=descriptor(a["artifact"])
            need(d["path"] not in result or result[d["path"]]==d,"array-artifact-collision")
            result[d["path"]]=d
        elif type(value)is dict:
            for child in value.values():visit(child)
        elif type(value)is list:
            for child in value:visit(child)
    visit(store.json(record))
    return list(result.values())
