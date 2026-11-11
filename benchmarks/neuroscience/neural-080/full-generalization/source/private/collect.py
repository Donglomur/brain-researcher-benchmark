"""Collect all30 independently produced arm artifacts; no private target access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_contract import capture,decode
from protocol import SUBJECTS,ARMS
import arrays
from prepare_pool import Writer,need


def collect(query,result_paths,out,cap):
    qraw=capture(query,200000);qsha=hashlib.sha256(qraw).hexdigest();q=decode(qraw)
    need(q['schema']=='neural080_query_v1' and q['subjects']==list(SUBJECTS) and q['arms']==list(ARMS),'Exact whole task query')
    need(type(result_paths) is list and len(result_paths)==30,'Exact30 operator-selected result paths')
    admitted=[];seen=set()
    for path in result_paths:
        root=Path(path);need(root.is_dir() and not root.is_symlink(),'Ordinary single-arm result root')
        r=decode(capture(root/'RESULT.json',10000))
        need(type(r) is dict and set(r)=={'schema','subject','arm','query_sha256','file','bytes','sha256'}
             and r['schema']=='neural080_arm_result_v1' and r['query_sha256']==qsha and r['file']=='prediction.npy','Exact arm result')
        key=(r['subject'],r['arm']);need(key in {(p,a) for p in SUBJECTS for a in ARMS} and key not in seen,'Unique required arm')
        body=capture(root/'prediction.npy',20_000_000)
        need(len(body)==r['bytes'] and hashlib.sha256(body).hexdigest()==r['sha256'],'Exact arm output bytes')
        arrays.decode(body,(102,127,150));admitted.append((r,body));seen.add(key)
    writer=Writer(out,cap);records=[]
    for r,body in admitted:
        name=r['subject']+'_'+r['arm']+'.npy';d=writer.put(name,body)
        records.append({'subject':r['subject'],'arm':r['arm'],'file':name,'bytes':d['bytes'],'sha256':d['sha256']})
    writer.json('submission.json',{'schema':'neural080_submission_v1','query_sha256':qsha,'predictions':records})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('query','result-paths','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    collect(a.query,decode(capture(a.result_paths,100000)),a.out,a.max_output_bytes)
