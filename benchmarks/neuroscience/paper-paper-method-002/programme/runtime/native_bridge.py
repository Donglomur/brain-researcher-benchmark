"""Executed only inside an admitted isolated native environment; no training on import."""
import hashlib
import json
import math
import os
import stat
import sys
import types

def read_at(root,path,cap):
    if type(path) is not str or path.startswith("/") or "\\" in path or "\x00" in path:raise ValueError("relative path")
    parts=path.split("/")
    if any(x in ("",".","..") for x in parts):raise ValueError("canonical path")
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for name in parts[:-1]:
            new=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
        f=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    finally:os.close(fd)
    try:
        before=os.fstat(f)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>cap:raise ValueError("bounded regular source")
        chunks=[];total=0
        while True:
            b=os.read(f,min(65536,cap-total+1))
            if not b:break
            total+=len(b)
            if total>cap:raise ValueError("source bound")
            chunks.append(b)
        after=os.fstat(f)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError("source changed")
        return b"".join(chunks)
    finally:os.close(f)

def parse(body):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError("duplicate key")
            result[key]=value
        return result
    def bad(value):raise ValueError("nonfinite JSON")
    result=json.loads(body,object_pairs_hook=pairs,parse_constant=bad)
    def finite(value):
        if type(value) is float and not math.isfinite(value):raise ValueError("nonfinite JSON")
        if isinstance(value,dict):
            for child in value.values():finite(child)
        if isinstance(value,list):
            for child in value:finite(child)
    finite(result);return result

def main(invocation_path, output_path):
    # Inputs are produced by trusted operator; no candidate-supplied module selector.
    if invocation_path!="/inputs/invocation.json" or output_path!="/output":raise ValueError("fixed mounts")
    inv=parse(read_at("/inputs","invocation.json",2*1024*1024))
    if inv["schema"]!="jaxley_exact_native_invocation_v1":raise ValueError("invocation schema")
    if inv["kind"] not in ("native_constructor","native_reference","native_exporter","candidate_method"):raise ValueError("producer kind")
    pin=inv["source"]
    if type(pin["bytes"]) is not int or not 0<pin["bytes"]<=16*1024*1024:raise ValueError("driver source bound")
    body=read_at("/program",pin["path"],pin["bytes"])
    if len(body)!=pin["bytes"] or hashlib.sha256(body).hexdigest()!=pin["sha256"]:raise ValueError("source changed")
    # The selected complete driver is ordinary reviewed source; missing original
    # notebook constructors cannot be supplied by a callable success flag.
    if inv["function"]!="run_exact_job":raise ValueError("unreviewed producer ABI")
    module=types.ModuleType("exact_reviewed_producer");module.__file__="/program/"+pin["path"]
    exec(compile(body,module.__file__,"exec"),module.__dict__)
    result=module.run_exact_job(inv["scientific_job"],"/inputs",output_path)
    if result is not None:raise ValueError("producer must emit contract artifacts, not return success")
    # Exit zero is only process evidence; outer collector must authenticate all
    # artifact identities, full scope, source lineage and numerical output schema.

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("expected invocation and output directory")
    main(sys.argv[1],sys.argv[2])

