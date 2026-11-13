"""Validate exact complete acquisition binding; no automatic download or decode."""
import argparse,json,re
from pathlib import Path
import delivery_io as io
ROOT=Path(__file__).resolve().parent

def validate(v):
 io.exact(v,['schema','files']);io.need(v['schema']=='neural083_verified_sources_v1','Exactsourcebindingschema')
 inventory=io.json_file(ROOT/'source/MI_ASSETS.json',200000)['files'];rows=v['files'];io.need(type(rows)is list and len(rows)==108,'Every54×2source')
 seen=set()
 for expected,row in zip(inventory,rows):
  io.exact(row,['person','session','path','bytes','sha256'])
  io.need(all(row[k]==expected[k] for k in ('person','session','path','bytes')),'Immutableproviderroster/path/size')
  io.check_pin({k:row[k] for k in ('bytes','sha256')},700000000);io.need(row['sha256'] not in seen,'Distinctsourceobjects');seen.add(row['sha256'])
 return rows

def load(path):return validate(io.json_file(path,100000))
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);a.add_argument('--max-source-bytes',type=int,required=True);q=a.parse_args();rows=load(q.manifest);io.need(sum(x['bytes'] for x in rows)<=q.max_source_bytes,'Fullsourcecap;neverdroprecords')
 for r in rows:io.asset(q.root,{'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256']})
 print('108exact sourceobjects verified opaquely; no decode/model/scoring')
if __name__=='__main__':main()
