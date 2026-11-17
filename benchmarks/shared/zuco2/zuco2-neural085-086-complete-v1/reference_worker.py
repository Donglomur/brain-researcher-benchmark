"""Trusted independent producer, itself executed by the bounded worker launcher.
Only the controller can select this exact source. Pickle is confined to this
independently pinned reference worker and its own immutable produced state;
trusted graders never deserialize participant or reference executable state.
"""
import argparse,pickle
from pathlib import Path
from zuco.io import *
from zuco.reference import create

def main(request_path,output):
    request=decode(read(request_path,64*1024**2));phase=request["phase"];output=Path(output)
    if phase=="FIT":
        train=decode(read(request["training_path"],request["training_pin"]["bytes"],request["training_pin"]));model=create(request["identity"]["method"]);model.fit(train["raw_training"],request["identity"],train["J"]);b=pickle.dumps(model,protocol=5);pinstate=write(output/"reference-state.pkl",b)
        diagnostics={'schema':'zuco2-reference-diagnostics-v1','identity':request['identity'],'method':request['identity']['method'],'selection':getattr(model,'selection',None),'linear_state':getattr(model,'state',None),'inner_competence':getattr(model,'inner_competence',None),'scaler_state':getattr(getattr(model,'encoder',None),'states',None),'column_blocks':getattr(getattr(model,'encoder',None),'names',None),'stability_limit':'fold-specific fitted basis; no neural-effect confidence interval; no averaging differently fitted SVD/tangent coefficients'}
        diag=write(output/'reference-diagnostics.json',diagnostics);diag['path']='reference-diagnostics.json'
        write(output/"result.json",{"status":"fit_complete","state_files":[{"path":"reference-state.pkl","bytes":pinstate["bytes"],"sha256":pinstate["sha256"]}],"analysis_trace":[diag]})
    elif phase=="INFER":
        state=request["trusted_reference_state_pin"];need(state["path"]=="/state/reference-state.pkl","trusted_reference_state_path");raw=read(state["path"],state["bytes"],state);model=pickle.loads(raw)
        query=decode(read(request["query_path"],request["query_pin"]["bytes"],request["query_pin"]));probs=model.predict_public(query["query"]);need(len(probs)==len(request["query_ids"]),"reference_query_count")
        write(output/"result.json",{"identity":request["identity"],"state_sha256":request["state_sha256"],"probabilities":[{"id":i,"p_tsr":float(v)} for i,v in zip(request["query_ids"],probs)],"analysis_trace":[]})
    else:raise Refusal("reference_phase")
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--request",required=True);a.add_argument("--output",required=True);q=a.parse_args();main(q.request,q.output)
