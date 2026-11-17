"""Exclusive finite JSON artifacts with complete write, fsync and same-FD readback."""
import hashlib
import json
from .contracts import require
from .custody import Attempt

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'

def write_new(path,value,cap):
    blob=encode(value)
    require(len(blob)<=cap,'artifact exceeds declared cap')
    def operation(owner):
        import os
        f=open(path,'x+b',buffering=0)
        owner.own(f,f.close)
        remaining=memoryview(blob)
        while remaining:
            n=f.write(remaining)
            require(type(n) is int and n>0 and n<=len(remaining),'short/invalid write')
            remaining=remaining[n:]
        f.flush();os.fsync(f.fileno());f.seek(0)
        check=f.read(len(blob)+1)
        require(check==blob,'artifact readback differs')
        return {'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
    return Attempt().run(operation)

def load_json(path,cap):
    def operation(owner):
        f=open(path,'rb');owner.own(f,f.close)
        b=f.read(cap+1)
        require(len(b)<=cap,'JSON extent cap')
        def pairs(rows):
            d={}
            for k,v in rows:
                require(k not in d,'duplicate JSON key')
                d[k]=v
            return d
        return json.loads(b,object_pairs_hook=pairs,
                          parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    return Attempt().run(operation)

def commit_then_score(submission_path,public,private_path,commit_path,cap):
    # Private label file is not even opened until the immutable submission
    # commitment has been fully persisted and its descriptor owner retired.
    submission=load_json(submission_path,cap)
    commitment=write_new(commit_path,{'submission_sha256':hashlib.sha256(encode(submission)).hexdigest()},cap)
    private=load_json(private_path,cap)
    from .grading import score_prediction,score_responses
    require(public['task'] in ('NEURAL-043','NEURAL-044'),'scoring task')
    score=score_prediction if public['task']=='NEURAL-043' else score_responses
    return score(submission,public,private),commitment

def commit_then_grade_investigation(submission_path,truth_path,commit_path,cap,tolerances):
    submission=load_json(submission_path,cap)
    commitment=write_new(commit_path,{'submission_sha256':hashlib.sha256(encode(submission)).hexdigest()},cap)
    truth=load_json(truth_path,cap)
    from .grading import grade_investigation
    return grade_investigation(submission,truth,tolerances),commitment
