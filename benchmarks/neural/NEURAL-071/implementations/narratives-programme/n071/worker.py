"""Source-owned reference worker entry points for the qualified isolated launcher."""
from .errors import need
from .identity import identity,exact
from .policy import validate_evidence,REFERENCES
from .references import ReferenceEngine,selection_summary
from . import codec,scientific

def dispatch(operation,request,request_record,store,journal):
    common=("generation","source","context","method_prior_identity","clock_conventions_identity",
            "historical_layer8_direct_consumer","evaluation_label")
    exact(request,common+(("case","reference","rows","primitives","y") if operation=="reference-fit"
                          else ("state","parent_fit","query_rows","primitives")),"worker-exact-request")
    need(request["generation"]==journal.generation and request["source"]==journal.source and
         request["context"]==journal.context,"worker-context-source")
    validate_evidence(request,journal.direct)
    def calls(label,fn,*args):
        if label in ("reference-inner-plan","reference-inner-not-applicable"):stage="S14"
        elif label in ("reference-select","reference-one-family-default") or label.startswith("reference-oof/"):stage="S16"
        elif "/inner/" in label or "/inner-train/" in label or "/inner-validation/" in label:stage="S15"
        elif "infer" in label or "/query" in label:stage="S19"
        else:stage="S17"
        return journal.invoke(stage,label,{"context":request["context"],"method":label},
                              {"method_result":True},fn,*args)
    engine=ReferenceEngine(calls)
    prefix=identity(request["context"])
    if operation=="reference-fit":
        need(request["reference"] in REFERENCES and
             request["context"]==request["case"]+"/"+request["reference"],"canonical-worker-context")
        state=engine.fit(request["case"],request["reference"],request["rows"],request["primitives"],request["y"])
        joined={"context":request["context"],"generation":request["generation"],"source":request["source"],
                "state":state,"fit_request":request_record,
                **{k:request[k] for k in ("method_prior_identity","clock_conventions_identity",
                                         "historical_layer8_direct_consumer","evaluation_label")}}
        rid=journal.begin("S18","state-publication",[request_record],{"complete_state":True})
        artifact=codec.pack(store,prefix+"-reference-state",joined)
        check=codec.unpack(store,artifact)
        need(check["fit_request"]==request_record,"state-readback")
        publication=journal.finish(rid,{"state":artifact},{"kind":"immutable-state-readback"})
        summary={"selection":selection_summary(request["case"],state,request["rows"]),
                 "context":request["context"],"generation":request["generation"],"source":request["source"],
                 "fit_request":request_record,"state":artifact,"state_publication":publication}
        return {"state":artifact,"context":request["context"],"inner_complete":True,
                "selection_summary":summary,
                "fit_rows":identity([r["row"] for r in request["rows"]]),
                "inner_receipts":journal.require_complete(),"publication_receipt":publication}
    need(operation=="reference-infer","worker-operation")
    state=codec.unpack(store,request["state"])
    need((state["context"],state["generation"],state["source"])==
         (request["context"],request["generation"],request["source"]),"reference-state-join")
    validate_evidence(state,journal.direct)
    prediction,receipts=engine.infer(state["state"],request["primitives"])
    prediction=scientific.prediction(prediction,len(request["query_rows"]))
    rid=journal.begin("S20","reference-prediction-publication",[request["state"]],{"prediction":True})
    artifact=codec.save_array(store,prefix+"-reference-prediction.npy",prediction,prediction=True)
    publication=journal.finish(rid,{"prediction":artifact},{"kind":"immutable-prediction-readback"})
    return {"context":request["context"],"state":request["state"],"prediction":artifact,
            "row_ids":[r["row"] for r in request["query_rows"]],"receipts":receipts,
            "publication_receipt":publication}
