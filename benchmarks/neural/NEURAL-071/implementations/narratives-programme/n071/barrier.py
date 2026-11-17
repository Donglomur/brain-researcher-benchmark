"""All-context barrier precedes the scorer's protected target grant."""
from .errors import need
from .identity import identity,canonical,parse,exact,descriptor
from .policy import validate_evidence

class Barrier:
    def __init__(self,generation,source,contexts):
        need(len(contexts)==10206 and len({c["id"] for c in contexts})==10206,"all10206-plan")
        self.generation=generation;self.source=source
        self.expected={c["id"]:c for c in contexts};self.captures={};self.sealed=None

    def capture(self,record):
        need(self.sealed is None,"barrier-already-sealed")
        cid=record["context"]
        need(cid in self.expected and cid not in self.captures,"capture-membership-once")
        expected=self.expected[cid]
        need(record["generation"]==self.generation and record["source"]==self.source,
             "capture-generation-source")
        validate_evidence(record,expected["historical_layer8_direct_consumer"])
        need(record["prediction"] and record["support"] and record["fit_state"] and
             record["fit_receipt"] and record["infer_receipt"] and record["original_receipts"],
             "complete-state-prediction-chain")
        cost=record["cost"]
        need(cost["closed"] is True and not cost["unknown"] and
             not any(cost["reserved"].values()) and cost["live_fds"]==0,"capture-costs")
        if expected["kind"]=="candidate":
            need(record["declaration"] and record["sealed_program"] and record["author_receipt"],
                 "candidate-authoring-chain")
        else:
            need(record["bank_private"] is True and record["inner_complete"] is True,"private-reference-chain")
            summary=record["reference_selection"]
            need(summary["context"]==cid and summary["generation"]==self.generation and
                 summary["source"]==self.source and summary["state"]==record["fit_state"] and
                 summary["selection"]["reference"]==expected["reference"] and
                 summary["selection"]["status"]=="complete","capture-reference-selection")
        need(set(record["review_metadata"])=={identity(r) for r in record["original_receipts"]},
             "capture-owned-review-metadata")
        for projected in record["review_metadata"].values():descriptor(projected)
        need(record.get("globally_independent_layer_selection",False) is False and
             record.get("untouched_test",False) is False,"forbidden-independence-claim")
        # Freeze admitted ordinary values so caller mutation cannot rewrite acceptance.
        self.captures[cid]=parse(canonical(record))

    def seal(self,setup):
        need(self.sealed is None,"barrier-already-sealed")
        need(set(self.captures)==set(self.expected),"missing-required-prediction")
        need(setup["closed"] is True and setup["cost"]["closed"] is True and
             not setup["cost"]["unknown"] and setup["consumers"]==sorted(self.expected),
             "once-only-setup-consumers")
        self.sealed={"generation":self.generation,"source":self.source,
                     "captures":{k:identity(v) for k,v in sorted(self.captures.items())},
                     "setup":identity(setup)}
        return identity(self.sealed)

    def target_grant(self,token,case_id,loader):
        need(self.sealed is not None and token==identity(self.sealed),"target-barrier")
        need(self.sealed["captures"]=={k:identity(v) for k,v in sorted(self.captures.items())},
             "sealed-captures-unchanged")
        need(case_id in {c["case"] for c in self.expected.values()},"target-case")
        return loader(case_id)
