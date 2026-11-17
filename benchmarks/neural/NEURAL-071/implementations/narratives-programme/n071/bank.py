"""Private independent reference bank, actual state publication and fresh inference."""
from .errors import need
from .identity import identity
from .policy import evidence,REFERENCES
from . import codec

class Bank:
    def __init__(self,runtime,store,journal,worker_programme):
        self.runtime=runtime;self.store=store;self.journal=journal;self.worker=worker_programme
        self.fit_records={};self.captures={}

    def fit(self,context,case,primitives,train_y):
        need(context["kind"]=="reference" and context["id"] not in self.fit_records,"bank-fit-once")
        need(context["reference"] in REFERENCES and
             context["id"]==case["id"]+"/"+context["reference"],"canonical-bank-context")
        payload={"case":case["id"],"reference":context["reference"],"rows":case["train"],
                 "primitives":[primitives[r["row"]] for r in case["train"]],"y":train_y,
                 "generation":self.journal.generation,"source":self.journal.source,
                 "context":context["id"],**evidence(context["reference"]=="R2/CONTEXT")}
        record=codec.pack(self.store,"bank-fit-"+identity(context["id"]),payload)
        result,receipt=self.runtime.invoke("reference-fit",self.worker,record,
            [{"artifact":record,"visibility":"read-only","kind":"packed"},{"artifact":self.worker,"visibility":"read-only","kind":"capsule"}],
            "reference-fit-"+identity(context["id"]),16*2**20)
        need(result["context"]==context["id"] and result["inner_complete"] is True and
             result["fit_rows"]==identity([r["row"] for r in case["train"]]),"bank-fit-return")
        # The complete immutable state is opened/read back; source/state joins survive process exit.
        state=codec.unpack(self.store,result["state"])
        need(state["context"]==context["id"] and state["generation"]==self.journal.generation and
             state["source"]==self.journal.source,"bank-state-ancestry")
        from .references import selection_summary
        summary=result["selection_summary"]
        need(set(summary)=={"selection","context","generation","source","fit_request","state","state_publication"} and
             (summary["context"],summary["generation"],summary["source"],summary["state"])==
             (context["id"],self.journal.generation,self.journal.source,result["state"]) and
             summary["fit_request"]==state["fit_request"] and
             summary["state_publication"]==result["publication_receipt"] and
             summary["selection"]==selection_summary(case["id"],state["state"],case["train"]),
             "bank-actual-selection-summary")
        self.fit_records[context["id"]]={"state":result["state"],"receipt":receipt,
                                        "inner_receipts":result["inner_receipts"],"selection_summary":summary}
        return self.fit_records[context["id"]]

    def infer(self,context,case,primitives):
        need(context["id"] in self.fit_records and context["id"] not in self.captures,"bank-state-before-infer")
        fit=self.fit_records[context["id"]]
        payload={"context":context["id"],"generation":self.journal.generation,"source":self.journal.source,
                 "state":fit["state"],"parent_fit":fit["receipt"],"query_rows":case["query"],
                 "primitives":[primitives[r["row"]] for r in case["query"]],
                 **evidence(context["reference"]=="R2/CONTEXT")}
        request=codec.pack(self.store,"bank-infer-"+identity(context["id"]),payload)
        result,receipt=self.runtime.invoke("reference-infer",self.worker,request,
            [{"artifact":request,"visibility":"read-only","kind":"packed"},{"artifact":fit["state"],"visibility":"read-only","kind":"packed"},
             {"artifact":self.worker,"visibility":"read-only","kind":"capsule"}],"reference-infer-"+identity(context["id"]),16*2**20)
        need(result["context"]==context["id"] and result["state"]==fit["state"] and
             result["row_ids"]==[r["row"] for r in case["query"]],"bank-infer-ancestry")
        prediction=codec.load_array(self.store,result["prediction"],prediction=True)
        need(len(prediction)==len(case["query"]),"bank-complete-prediction")
        self.captures[context["id"]]={"context":context["id"],"generation":self.journal.generation,
            "source":self.journal.source,"prediction":result["prediction"],"support":identity(result["row_ids"]),
            "fit_state":fit["state"],"fit_receipt":fit["receipt"],"infer_receipt":receipt,
            "reference_selection":fit["selection_summary"],
            "original_receipts":self.journal.require_complete(),
            "review_metadata":self.journal.review_metadata(self.journal.require_complete()),
            "bank_private":True,"inner_complete":True,
            **evidence(context["reference"]=="R2/CONTEXT")}
        return self.captures[context["id"]]

    def close_case(self):
        need(len(self.captures)==9,"nine-reference-case")
        cost=self.store.budget.close()
        # One R1 cost owner per case; consumer views refer to it rather than summing nine copies.
        owner=identity({"context":self.journal.context,"cost":cost})
        return [dict(r,cost=cost,cost_owner=owner) for r in self.captures.values()]
