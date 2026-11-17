"""Unrestricted frozen participant programmes with matched case-local F/I authoring."""
from .errors import need
from .identity import identity,canonical,relative
from .policy import evidence
from . import codec,views

DECLARATION=("hypotheses","direction_and_uncertainty","training_analyses","support_and_splits",
             "tool_inspections","selection","source_clock_assumptions","limitations",
             "forbidden_claim_acknowledgement","evidence_receipts","declared_feature_use","transductive_X_use")

class Candidate:
    def __init__(self,context,store,journal,runtime,provider):
        self.context=context;self.store=store;self.journal=journal
        self.runtime=runtime;self.provider=provider;self.sealed=None;self.transcript=[]
        self.author_done=False

    def author(self,view_record,system_prompt):
        need(not self.author_done,"no-continuing-author")
        view=codec.unpack(self.store,view_record)
        allowed=codec.pack(self.store,"author-view",views.author_view(view,self.context["mode"]))
        messages=[{"role":"system","content":system_prompt},
                  {"role":"user","content":{"view":allowed,"context":self.context}}]
        author_receipts=[]
        while True:
            need(not self.author_done,"no-continuing-author")
            reply,receipt=self.provider.call(messages,["python_tool","submit_program"],"S08")
            author_receipts.append(receipt);self.transcript.append({"reply":reply,"receipt":receipt})
            if reply["action"]=="python_tool":
                tool=self._seal_files(reply["files"],reply["entrypoint"],"author-tool-"+str(len(self.transcript)))
                result,actual=self.runtime.invoke("candidate-author-tool",tool,allowed,
                    [{"artifact":allowed,"visibility":"read-only","kind":"packed"}],"author-tool-"+str(len(self.transcript)),
                    8*2**20)
                messages += [{"role":"assistant","content":reply},
                             {"role":"tool","content":{"result":result,"receipt":actual}}]
            else:
                need(reply["action"]=="submit_program","author-action")
                declaration=reply["declaration"]
                need(type(declaration)is dict and set(declaration)==set(DECLARATION),
                     "complete-prescore-declaration")
                need(declaration["forbidden_claim_acknowledgement"] is True,"claim-acknowledgement")
                self.sealed=self._seal_files(reply["files"],reply["entrypoint"],"frozen-program")
                self.author_done=True
                disclosed={"context":self.context["id"],"declaration":declaration,
                           "generation":self.journal.generation,"source":self.journal.source,
                           **evidence(self.context["arm"]=="CONTEXT")}
                return {"programme":self.sealed,"declaration":self.store.put("declaration.json",disclosed),
                        "transcript":self.store.put("author-transcript.json",self.transcript),
                        "receipts":author_receipts,"view":view_record}

    def _seal_files(self,files,entrypoint,prefix):
        need(type(files)is dict and files and type(entrypoint)is list and entrypoint and
             all(type(v)is str for v in entrypoint),"arbitrary-programme-capsule")
        captured={}
        for name,body in sorted(files.items()):
            relative(name);need(type(body)is str,"programme-source-text")
            # Logical paths are restored only within the qualified programme mount.
            captured[name]=self.store.write(prefix+"-"+identity(name)+".txt",body.encode("utf-8"))
        need(entrypoint[0] in files,"entrypoint-in-capsule")
        return self.store.put(prefix+".json",{"files":captured,"entrypoint":entrypoint,
                                             "context":self.context["id"]})

    def execute(self,authored):
        need(self.author_done and authored["programme"]==self.sealed,"frozen-before-final-fit")
        view=codec.unpack(self.store,authored["view"])
        fit_request=codec.pack(self.store,"candidate-fit-view",views.fit_view(view))
        fit_result,fit_receipt=self.runtime.invoke("candidate-fit",self.sealed,fit_request,
            [{"artifact":fit_request,"visibility":"read-only","kind":"packed"},{"artifact":self.sealed,"visibility":"read-only","kind":"capsule"}],
            "candidate-fit",16*2**20)
        need(fit_result["state"] and fit_result["context"]==self.context["id"],"candidate-actual-state")
        infer_request=codec.pack(self.store,"candidate-infer-view",views.infer_view(view,fit_result["state"]))
        infer_result,infer_receipt=self.runtime.invoke("candidate-infer",self.sealed,infer_request,
            [{"artifact":infer_request,"visibility":"read-only","kind":"packed"},{"artifact":self.sealed,"visibility":"read-only","kind":"capsule"},
             {"artifact":fit_result["state"],"visibility":"read-only","kind":"opaque"}],"candidate-infer",16*2**20)
        need(infer_result["context"]==self.context["id"] and
             infer_result["row_ids"]==[r["row"] for r in view["query_rows"]],"candidate-query-support")
        prediction=codec.load_array(self.store,infer_result["prediction"],prediction=True)
        need(len(prediction)==len(view["query_rows"]),"candidate-prediction-complete")
        receipts=self.journal.require_complete()
        cost=self.store.budget.close()
        return {"context":self.context["id"],"generation":self.journal.generation,"source":self.journal.source,
                "prediction":infer_result["prediction"],"support":identity([r["row"] for r in view["query_rows"]]),
                "fit_state":fit_result["state"],"fit_receipt":fit_receipt,"infer_receipt":infer_receipt,
                "author_receipt":authored["receipts"],"declaration":authored["declaration"],
                "sealed_program":self.sealed,"original_receipts":receipts,
                "review_metadata":self.journal.review_metadata(receipts),"cost":cost,
                **evidence(self.context["arm"]=="CONTEXT")}
