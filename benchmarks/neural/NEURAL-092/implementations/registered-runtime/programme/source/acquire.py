"""Future full32 acquisition recipe; never automatically invoked by construction."""
import argparse,hashlib,json,os,time,urllib.request
from pathlib import Path
from io_contract import frozen_roster
from packet_io import write_json

def main():
 p=argparse.ArgumentParser();p.add_argument('--roster',required=True);p.add_argument('--output',required=True);p.add_argument('--max-bytes',type=int,required=True);p.add_argument('--timeout-per-object',type=int,default=1800);a=p.parse_args()
 roster,_=frozen_roster(a.roster);dest=Path(a.output)
 if dest.exists() or dest.is_symlink():raise ValueError('fresh output required')
 required=roster['recording_bytes']+100000
 if a.max_bytes<required:raise ValueError(f'full32 selected input requires {required} bytes including receipt; no subset')
 dest.mkdir(parents=True);records=[];used=0
 try:
  for row in roster['sessions']:
   s=row['source'];start=time.monotonic();path=dest/(row['session_id']+'.nwb');h=hashlib.sha256();n=0
   q=urllib.request.Request(s['url'],headers={'Accept-Encoding':'identity','If-Match':s['etag']})
   with urllib.request.urlopen(q,timeout=30) as r,path.open('xb') as out:
    if r.status!=200 or int(r.headers.get('Content-Length','-1'))!=s['bytes'] or r.headers.get('ETag')!=s['etag']:raise ValueError('source transport identity changed; new review required')
    while True:
     if time.monotonic()-start>a.timeout_per_object:raise TimeoutError('object acquisition deadline')
     body=r.read(min(1048576,s['bytes']-n+1))
     if not body:break
     if n+len(body)>s['bytes'] or used+len(body)>a.max_bytes-100000:raise ValueError('bounded source body exceeded')
     out.write(body);h.update(body);n+=len(body);used+=len(body)
   if n!=s['bytes']:raise ValueError('incomplete source object')
   path.chmod(0o444);records.append({'session_id':row['session_id'],'path':path.name,'bytes':n,'sha256':h.hexdigest(),'url':s['url'],'etag':s['etag']})
 finally:
  receipt={'schema':'allen32_raw_binding_v1','roster_sha256':__import__('io_contract').ROSTER_SHA256,'complete':len(records)==32,'files':records,'retained_source_bytes':used,'publisher_checksum_available':False,'identity_note':'SHA256 computed on complete received bytes; public ETag is an opaque version guard, not a cryptographic publisher checksum.'}
  write_json(dest/'RAW_BINDING.json',receipt)
 print(json.dumps({'complete':len(records)==32,'bytes':used,'binding':str(dest/'RAW_BINDING.json')}))
if __name__=='__main__':main()
