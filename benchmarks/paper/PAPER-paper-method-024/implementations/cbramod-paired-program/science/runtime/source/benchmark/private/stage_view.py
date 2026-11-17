"""Pinned static A/B source projections; no test targets or execution attestation."""
import argparse,sys
from pathlib import Path
import re
from io_utils import read,capture,encode,need
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from benchmark.native.owners import admit_owners

def stage(root,view,out,manifest_sha,cap=5_000_000):
 need(view in ('A','B'),'A or B')
 owners=admit_owners({'source':root},{'output':out});root=owners['source'];out=owners['output']
 manifest,_=read(root/'benchmark/private/STATIC_VIEWS.json',1_000_000,manifest_sha)
 need(manifest['schema']=='cbramod_static_views_v2','operative current source manifest')
 rows=manifest[view];need(type(rows)is list and 1<=len(rows)<=256,'bounded complete static source roster')
 names=set();sources=set();total=0
 for row in rows:
  need(type(row)is dict and set(row)=={'source_path','path','bytes','sha256'},'exact source projection row')
  src=row['source_path'];dst=row['path']
  public=re.fullmatch(r'benchmark/public/[A-Za-z0-9_.-]+',src)and dst==src.removeprefix('benchmark/')
  official=re.fullmatch(r'official/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+',src)and dst==src
  need(public or view=='B'and official,'exact source-arm visibility')
  need('..'not in Path(src).parts and '..'not in Path(dst).parts and src not in sources and dst not in names,'unique ordinary source/output paths')
  need(type(row['bytes'])is int and 0<=row['bytes']<=1_048_576,'bounded individual source file')
  for n in range(1,len(Path(src).parts)+1):need(not(root/Path(*Path(src).parts[:n])).is_symlink(),'no source symlink')
  sources.add(src);names.add(dst);total+=row['bytes']
 receipt={'schema':'cbramod_static_view_v2','view':view,'manifest_sha256':manifest_sha,'files':rows,
  'development_only':True,'data_provisioned':False,'exact_official_code_available':view=='B',
  'source_commit':manifest['source_commit']if view=='B'else None,'runtime_qualified':False,'access_attested':False}
 meta=encode(receipt);need(type(cap)is int and 0<cap<=5_000_000 and total+len(meta)<=cap,'complete static source/receipt budget')
 bodies=[]
 for row in rows:
  value,_=capture(root/row['source_path'],row['bytes'],row['sha256']);need(len(value)==row['bytes'],'exact source extent');bodies.append(value)
 out.mkdir(parents=True,exist_ok=False)
 for row,b in zip(rows,bodies):
  path=out/row['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b);path.chmod(0o444)
 (out/'VIEW.json').write_bytes(meta)
 return receipt

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--view',choices=['A','B'],required=True);p.add_argument('--output',required=True);p.add_argument('--manifest-sha256',required=True);a=p.parse_args()
 print(encode(stage(a.root,a.view,a.output,a.manifest_sha256)).decode(),end='')
