"""Complete adopted controller; runtime/qualification dependencies remain explicit."""
from .errors import need,Custody
from .identity import identity
from .policy import evidence
from .resources import Budget,P1,R1
from .store import Store
from .journal import Journal
from .runtime import Runtime
from .provider import Provider
from .candidate import Candidate
from .bank import Bank
from .barrier import Barrier
from .reporting import Reporter
from . import support,views,codec

class Programme:
    def __init__(self,generation,source,qualification,root_factory):
        self.generation=generation;self.source=source;self.qualification=qualification
        self.binding=qualification.require(generation,source)
        # root_factory is the trusted launcher-owned exclusive-directory allocator,
        # not a participant-controlled callback. Its original receipts join setup.
        self.root_factory=root_factory
        self.cost_owners={}

    def environment(self,name,limits,direct=False):
        allocation=self.root_factory(name,limits)
        need(all(allocation.get(k) for k in ("root","original_receipt","setup_owner")),"owned-root-allocation")
        budget=Budget(limits,name,allocation["observer"]);store=Store(allocation["root"],budget)
        journal=Journal(store,self.generation,self.source,name,name,direct)
        runtime=Runtime(self.qualification,store,journal)
        return store,journal,runtime,allocation

    def run(self,census,prepared,setup,contrasts,target_root):
        cases=support.census(census);contexts=support.contexts(cases)
        expected={c["id"]:c for c in contexts};barrier=Barrier(self.generation,self.source,contexts)
        need(prepared["generation"]==self.generation and prepared["source"]==self.source and
             setup["consumers"]==sorted(expected) and prepared["census"]==census,"prepared-full-programme")
        need(target_root==self.binding["protected_target_root"],"protected-target-root")
        need(setup["closed"] is True and setup["cost"]["closed"] is True and
             not setup["cost"]["unknown"],"actual-setup-closure")
        captures={};stores={}
        # References and participants have separate private roots. No bank object is supplied to authors.
        for case in cases:
            cid=case["id"];private=prepared["cases"][cid]
            need(private["train_rows"]==case["train"] and private["query_rows"]==case["query"],
                 "prepared-case-support")
            store,journal,runtime,allocation=self.environment(cid+"/references",R1)
            bank=Bank(runtime,store,journal,self.binding["reference_worker"])
            for context in (c for c in contexts if c["case"]==cid and c["kind"]=="reference"):
                journal.direct=context["historical_layer8_direct_consumer"]
                # A single R1 pool, with exact per-job context identities.
                journal.context=context["id"]
                bank.fit(context,case,private["primitives"],private["train_y"])
                bank.infer(context,case,private["primitives"])
            bank_records=bank.close_case()
            for record in bank_records:
                barrier.capture(record);captures[record["context"]]=record;stores[record["context"]]=store
            self.cost_owners[bank_records[0]["cost_owner"]]=bank_records[0]["cost"]
            for context in (c for c in contexts if c["case"]==cid and c["kind"]=="candidate"):
                profile=dict(P1,currency_units=self.binding["provider"]["monetary_cap"])
                store,journal,runtime,allocation=self.environment(context["id"],profile,context["arm"]=="CONTEXT")
                view=views.make(case,private["primitives"],private["train_y"],context,store,journal)
                provider=Provider(store,journal,self.binding["provider"])
                candidate=Candidate(context,store,journal,runtime,provider)
                authored=candidate.author(view,self.binding["candidate_prompt"])
                record=candidate.execute(authored)
                barrier.capture(record);captures[context["id"]]=record;stores[context["id"]]=store
                self.cost_owners[context["id"]]=record["cost"]
        store,journal,runtime,allocation=self.environment("programme-report",self.binding["report_profile"])
        seal,barrier_receipt=journal.invoke("S21","all-context-barrier",
                            {"captures":{k:identity(v) for k,v in captures.items()}},
                            {"target_grant":True},barrier.seal,setup)
        review_context=None
        if self.binding["interpretation_reviews_selected"]:
            review_context={"selection":self.binding.get("interpretation_review_evidence"),
                            "stores":stores,"setup":setup,"contrasts":contrasts}
        census_report=prepared["census_report"]
        need(census_report["census_identity"]==identity(census) and
             census_report["generation"]==self.generation and census_report["source"]==self.source,
             "actual-complete-census-report")
        reporter=Reporter(barrier,store,journal,review_context,{"census":census_report})
        from .prepared import TargetReader
        target_loader=TargetReader(prepared["protected"],target_root,store,cases)
        # Scorer reads use a separate owned reporting budget. Closed producer pools never reopen.
        def prediction(record):
            source_store=stores[record["context"]]
            reader=Store(source_store.root,store.budget)
            return codec.load_array(reader,record["prediction"],prediction=True)
        published=reporter.grade(seal,cases,contrasts,target_loader,prediction)
        reviews=None
        if self.binding["interpretation_reviews_selected"]:
            providers=[Provider(store,journal,b) for b in self.binding["reviewers"]]
            adjudicator=Provider(store,journal,self.binding["adjudicator"])
            reviews=reporter.review(published,providers,adjudicator)
        # Outside launcher captures this original closure after the publication has closed.
        if reviews is not None and reviews["status"]=="interpretation_review_pending":
            # The independent numeric artifact survives an optional-review failure.
            # Unknown or unclosed accounting remains explicit, never a successful cost receipt.
            closure=Custody()
            try:
                journal.require_complete();report_cost=store.budget.close()
            except BaseException as exc:
                closure.retain(exc,"optional-report-cost-closure")
                reporter.review_failures[-1].retain(exc,"optional-report-cost-closure")
                report_cost=store.budget.report()
            reviews["report_cost_failure"]=closure.diagnostic()
            reviews["report_cost_closed"]=report_cost["closed"]
        else:
            journal.require_complete();report_cost=store.budget.close()
        self.cost_owners["setup"]=setup["cost"];self.cost_owners["report"]=report_cost
        self.cost_owners["administration"]=self.root_factory.close()
        return {"generation":self.generation,"source":self.source,"barrier":seal,
                "numeric_report":published,"reviews":reviews,"report_cost":report_cost,
                "census":census_report,"reference_selection_strata":reporter.reference_selection_strata,
                "barrier_receipt":barrier_receipt,
                "once_only_cost_owners":self.cost_owners,"captures":captures,
                "outside_original_completion_required":True,**evidence(False)}
