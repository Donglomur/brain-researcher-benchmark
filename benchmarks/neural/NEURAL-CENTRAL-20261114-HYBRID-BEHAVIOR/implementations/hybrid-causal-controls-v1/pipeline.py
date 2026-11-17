"""Trusted fixed-reference composition and local scoring entry.

The scientific fitting function is defined but never called on import or by the
next controls-only operation. No untrusted agent runs in this Python process.
"""
from consumer import load_accepted_private_cases,outer_fold,GROUPS,OnlineSession,ContractError,decode_reply,ordinary_input,file_identity
from reference import select_reference
from scoring import score_complete
import hashlib,json,secrets
from pathlib import Path

def fit_complete_reference(decisions):
    predictions=[];selection=[]
    for subject,session in sorted(GROUPS):
        train,test=outer_fold(decisions,subject,session)
        model,trace=select_reference(train)
        # Fixed trusted reference sees only the current observation.
        protocol=OnlineSession(test,secrets.token_bytes(32))
        while True:
            query=protocol.next_query()
            if query is None:break
            protocol.commit({"token":query["token"],"probabilities":model.predict(query["observation"])})
        predictions.extend((d.source_row,p) for d,p in protocol.finished_predictions())
        selection.append({"subject":subject,"held_session":session,"training_selection":trace})
    return predictions,selection

def score_submission(cases_path,submission_path,output_path):
    """Curator-local complete scoring, not proof of candidate isolation/provenance.

    A protected comparison additionally requires the admitted stop-and-wait
    transport, exact program/artifact provenance and no hidden-data access.
    """
    decisions=load_accepted_private_cases(cases_path);predictions=[];used=0;digest=hashlib.sha256()
    with ordinary_input(submission_path) as f:
        before=file_identity(f)
        for line in f:
            used+=len(line)
            digest.update(line)
            if used>64*1024**2 or len(line)>4096:raise ContractError("complete submission bound")
            r=decode_reply(line)
            if type(r) is not dict or set(r)!={"source_row","probabilities"}:raise ContractError("curator submission schema")
            predictions.append((r["source_row"],r["probabilities"]))
        if before!=file_identity(f):raise ContractError("submission changed during score intake")
    result=score_complete(decisions,predictions)
    result["submission_bytes"]=used
    result["submission_sha256"]=digest.hexdigest()
    result["provenance_claim"]="trusted local score only; transport admission separate"
    body=(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
    if len(body)>1048576:raise ContractError("aggregate report cap")
    with open(output_path,"xb") as f:f.write(body)
    return {"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases",required=True);p.add_argument("--submission",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();print(json.dumps(score_submission(a.cases,a.submission,a.output)))

