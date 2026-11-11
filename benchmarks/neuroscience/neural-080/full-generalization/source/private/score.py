"""Complete candidate admission before private target capture, no model runs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import arrays
from io_contract import capture,decode
from protocol import SUBJECTS,ARMS,QUERY,CHANNELS,EEG_BINS
from scorer_core import evaluate

SHAPE=(len(QUERY),CHANNELS,EEG_BINS)


def need(ok,msg):
    if not ok:raise ValueError(msg)


def descriptor(row,keys):
    need(type(row) is dict and set(row)==set(keys),'Exact array descriptor')
    need(type(row['bytes']) is int and 0<row['bytes']<=20_000_000 and type(row['sha256']) is str
         and re.fullmatch('[a-f0-9]{64}',row['sha256']) is not None,'Bounded primitive array identity')


def admit(candidate,qraw,*,owner=None):
    need(candidate.is_dir() and not candidate.is_symlink(),'Ordinary candidate output directory')
    q=decode(qraw)
    need(type(q) is dict and q.get('schema')=='neural080_query_v1' and q.get('subjects')==list(SUBJECTS)
         and q.get('video_ids')==list(QUERY) and q.get('shape_per_subject')==list(SHAPE)
         and q.get('arms')==list(ARMS),'Frozen full query geometry')
    sub=decode(capture(candidate/'submission.json',100000,owner=owner))
    need(type(sub) is dict and set(sub)=={'schema','query_sha256','predictions'} and sub['schema']=='neural080_submission_v1'
         and sub['query_sha256']==hashlib.sha256(qraw).hexdigest(),'Exact candidate/query binding')
    rows=sub['predictions'];need(type(rows) is list and len(rows)==30,'All6×5 arrays required')
    expected={(p,a) for p in SUBJECTS for a in ARMS};seen=set();predictions={p:{} for p in SUBJECTS};total=0
    # Validate every descriptor before opening any candidate numerical file.
    for r in rows:
        descriptor(r,('subject','arm','file','bytes','sha256'))
        key=(r['subject'],r['arm']);need(key in expected and key not in seen,'Unique complete participant/arm roster')
        need(r['file']==r['subject']+'_'+r['arm']+'.npy','Exact basename, no traversal')
        seen.add(key);total+=r['bytes']
    need(seen==expected and total<=512*1024**2,'Full finite candidate channel bound')
    for r in rows:predictions[r['subject']][r['arm']]=arrays.load(candidate/r['file'],r,SHAPE,owner=owner)
    return predictions


def score(candidate,query,binding):
    qraw=capture(query,200000)
    predictions=admit(candidate,qraw)
    # Private descriptors and targets are untouched until all30 arrays pass.
    obj=decode(capture(binding,100000))
    need(type(obj) is dict and set(obj)=={'schema','query_sha256','targets'} and obj['schema']=='neural080_private_v1'
         and obj['query_sha256']==hashlib.sha256(qraw).hexdigest(),'Exact private binding')
    rows=obj['targets'];need(type(rows) is list and len(rows)==6,'All six private target arrays')
    gold={}
    for r in rows:
        descriptor(r,('subject','file','bytes','sha256'));person=r['subject']
        need(person in SUBJECTS and person not in gold and r['file']==person+'.npy','Exact private subject/basename')
        gold[person]=arrays.load(binding.parent/r['file'],r,SHAPE)
    return evaluate(predictions,gold)


def main():
    p=argparse.ArgumentParser()
    for field in ('candidate','query','binding','out'):p.add_argument('--'+field,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and not a.out.is_symlink() and a.out.parent.is_dir()
                         and not a.out.parent.is_symlink(),'Fresh report and ordinary output parent')
    try:result=score(a.candidate,a.query,a.binding)
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OSError,UnicodeError,OverflowError) as e:
        result={'schema':'neural080_score_v1','admitted':False,'primary_full_mse':None,'reason':str(e)}
    with a.out.open('x') as f:json.dump(result,f,allow_nan=False,indent=2)


if __name__=='__main__':main()
