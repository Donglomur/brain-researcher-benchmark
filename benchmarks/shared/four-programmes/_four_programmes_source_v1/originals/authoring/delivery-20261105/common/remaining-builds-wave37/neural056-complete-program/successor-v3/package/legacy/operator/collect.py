"""Opaque all-ten artifact collection; no candidate execution or private target read."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,ARMS,canonical,need
from array_io import capture,metadata,identity,fresh_output

def collect(roots,out):
 need(len(roots)==10,'Exactlytenisolatedcases');fresh_output(out);rows=[];bodies=[];seen=set();base=None
 for root in roots:
  root=Path(root);m=metadata(root/'case_predictions.json');need(m['schema']=='neural056_case_predictions_v1' and len(m['entries'])==3,'Threecasearms');head=(m['design_sha256'],m['query_image_ids'])
  if base is not None:need(head==base,'Samepaneldesign/order')
  base=head;people={r['person'] for r in m['entries']};need(len(people)==1 and people.issubset(PEOPLE) and not people&seen and {r['arm'] for r in m['entries']}==set(ARMS),'Distinctwholeperson');seen|=people
  for r in m['entries']:
   name=r['person']+'__'+r['arm']+'.npz';need(r['file']==name,'Exact artifactname');b=capture(root/name,4_000_000);need(identity(b)=={'bytes':r['bytes'],'sha256':r['sha256']},'Artifactpin');rows.append(r);bodies.append((name,b))
 need(seen==set(PEOPLE),'Fulltenpeople');out=Path(out);out.mkdir()
 for name,b in bodies:(out/name).write_bytes(b)
 (out/'predictions.json').write_bytes(canonical({'schema':'neural056_predictions_v1','design_sha256':base[0],'query_image_ids':base[1],'entries':rows}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',action='append',required=True);p.add_argument('--output',required=True);a=p.parse_args();collect(a.case,a.output)
