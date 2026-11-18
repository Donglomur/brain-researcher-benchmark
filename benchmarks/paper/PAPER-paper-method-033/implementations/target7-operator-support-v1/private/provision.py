"""Immutable recorded asset authentication; no acquisition, decoding, training or scoring."""
from pathlib import Path
import json
import delivery_io as d
ROOT=Path(__file__).resolve().parent

def designated_records(manifest):
 rows=[r for r in manifest['files']if r['role']=='designated_processed_dataset']
 d.need(len(rows)==88 and len({r['path']for r in rows})==88,'Full88-file processed release')
 for s in (1,2,5,7):
  tag=f'subj{s:02d}'
  d.need(sum('/train/'in r['path']and tag in r['path']for r in rows)==18,'All18training shards/person')
  d.need(sum('/val/'in r['path']and tag in r['path']for r in rows)==1,'Validation shard/person')
  d.need(sum('/test/'in r['path']and tag in r['path']for r in rows)==2,'Both test shards/person')
 return rows

def verify(root,manifest,byte_cap):
 rows=designated_records(manifest);total=sum(r['bytes']for r in rows)
 d.need(type(byte_cap)is int and total<=byte_cap,'Full source budget; no implicit partialcohort')
 pins=[]
 for r in rows:
  d.need(r['sha256']is not None,'SHA256 content binding absent; obtain/authenticate smallmetadata separately')
  p=d.resolve(root,r['path']);observed=d.read(p,r['bytes'],{k:r[k]for k in ('bytes','sha256')},retain=False)
  pins.append({'path':r['path'],**observed})
 return {'source_files_verified':pins,'source_bytes':total,'native_decoded_schema_verified':False,'models_executed':False}

def main():
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--manifest',required=True);a.add_argument('--manifest-pin',required=True);a.add_argument('--max-source-bytes',type=int,required=True);a.add_argument('--output',required=True);z=a.parse_args()
 m=d.json_file(z.manifest,1000000,d.json_file(z.manifest_pin));d.put(z.output,verify(z.root,m,z.max_source_bytes),1000000)
if __name__=='__main__':main()
