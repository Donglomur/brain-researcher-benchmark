"""Fixed full-panel NEURAL056 encoding contract; no scientific execution."""
import json,hashlib,math,re
PEOPLE=tuple('sub-'+str(i).zfill(2) for i in range(1,11))
ARMS=('representation','low_level','response_permuted')
SHAPE=(200,17,100)
def need(ok,why):
 if not ok:raise ValueError(why)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def hash_ok(x):return type(x)is str and re.fullmatch('[0-9a-f]{64}',x)is not None
def validate_design(d):
 need(set(d)=={'schema','task_id','people','arms','query_image_ids','coordinates','roster_sha256','feature_binding_sha256'},'Exact design fields')
 need(d['schema']=='neural056_design_v1' and d['task_id']=='NEURAL-056' and d['people']==list(PEOPLE) and d['arms']==list(ARMS),'Fixed ten-person/three-arm panel')
 q=d['query_image_ids'];need(type(q)is list and len(q)==200 and len(set(q))==200 and all(type(x)is str and re.fullmatch('img_[0-9a-f]{24}',x) for x in q),'Exact200 ordered image IDs')
 c=d['coordinates'];need(type(c)is dict and set(c)=={'channel_names','times_seconds','units','source_binding_sha256'},'Verified source coordinates required')
 names=c['channel_names'];t=c['times_seconds'];need(type(names)is list and len(names)==len(set(names))==17 and all(type(x)is str and x for x in names),'17 distinct source coordinates')
 need(type(t)is list and len(t)==100 and all(type(x)in(int,float) and math.isfinite(x) for x in t) and all(b>a for a,b in zip(t,t[1:])),'Full100 verified times')
 need(c['units']=='released_noise_normalized_EEG_not_microvolts','Source units')
 need(all(hash_ok(x) for x in [c['source_binding_sha256'],d['roster_sha256'],d['feature_binding_sha256']]),'Bound source/roster/feature identities')
 return d
