"""Bounded scalar shards preserve full scientific output support without huge JSON RAM."""
from pathlib import Path
import math
from .core import *
CHUNK_CAP=8*1048576
MAX_CHUNKS=4096
def descriptors(value,spec):
 exact(value,("schema","shape","chunks"),"tensor descriptor")
 need(value["schema"]=="critical_init_scalar_shards_v1" and value["shape"]==spec["shape"],"trusted complete tensor geometry")
 count=math.prod(spec["shape"]);need(0<count<=10000000000,"finite full tensor extent")
 rows=value["chunks"];need(type(rows) is list and 0<len(rows)<=MAX_CHUNKS,"finite shard list")
 start=0;paths=set()
 for row in rows:
  exact(row,("path","bytes","sha256","start","count"),"scalar shard")
  relative(row["path"]);sha(row["sha256"])
  need(row["path"] not in paths and row["path"].startswith("tensors/"),"unique tensor namespace");paths.add(row["path"])
  need(type(row["bytes"]) is int and 0<row["bytes"]<=CHUNK_CAP,"bounded shard bytes")
  need(type(row["count"]) is int and 0<row["count"]<=262144 and row["start"]==start,"contiguous full scalar support")
  start+=row["count"]
 need(start==count,"no cropped output population")
 return rows
def values(value,spec,root,cost):
 for row in descriptors(value,spec):
  raw=read(Path(root)/row["path"],row["bytes"],cost,row);v=decode(raw,CHUNK_CAP)
  need(type(v) is list and len(v)==row["count"],"exact scalar shard count")
  for x in v:yield number(x)
def validate(value,spec,root,cost):
 n=0
 for _ in values(value,spec,root,cost):n+=1
 return n
def pair_error(a,b,spec,aroot,broot,cost):
 import itertools
 sentinel=object();total=0;maximum=0.;n=0
 for x,y in itertools.zip_longest(values(a,spec,aroot,cost),values(b,spec,broot,cost),fillvalue=sentinel):
  need(x is not sentinel and y is not sentinel,"same complete tensor support")
  try:e=abs(x-y);finite=math.isfinite(e)
  except OverflowError:raise Refusal("finite residual") from None
  need(finite,"finite residual")
  # Exact sum in binary64's smallest subnormal units (2**-1074).
  # The declared extent bounds this integer to 2132 bits, even when the
  # floating-point sum overflows. No population is materialized or reread.
  numerator,denominator=e.as_integer_ratio()
  total+=numerator<<(1075-denominator.bit_length());maximum=max(maximum,e);n+=1
 need(n>0,"nonempty complete tensor support")
 # Integer division rounds the mean once, without converting the sum first.
 mean=total/(n<<1074)
 need(math.isfinite(mean) and (total==0 or mean>0),"representable tensor mean")
 return {"mae":mean,"max_error":maximum,"count":n}
def store_array(array,name,root,cost):
 # Native result serialization only; not called in construction controls.
 import numpy as np
 relative(name);x=np.asarray(array);need(x.dtype.kind in "fiu" and x.ndim>0,"numeric source result")
 flat=x.reshape(-1);rows=[];folder=Path(root)/"tensors"/name;folder.mkdir(parents=True,exist_ok=False)
 for start in range(0,len(flat),262144):
  values0=flat[start:start+262144].tolist();need(all(type(v) in (int,float) and math.isfinite(v) for v in values0),"finite native result; source failure cannot become a target")
  body=encode(values0);need(len(body)<=CHUNK_CAP,"native shard capacity")
  path=folder/("%06d.json"%(start//262144));write(path,body,cost)
  rows.append({"path":path.relative_to(root).as_posix(),**pin(body),"start":start,"count":len(values0)})
 return {"schema":"critical_init_scalar_shards_v1","shape":list(x.shape),"chunks":rows}
