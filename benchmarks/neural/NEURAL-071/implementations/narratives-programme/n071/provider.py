"""Actual metered author/reviewer gateway. No provider credentials are selected now."""
import os
import urllib.request
from .errors import Custody,need
from .identity import canonical,parse,identity

class Provider:
    def __init__(self,store,journal,binding):
        self.store=store;self.journal=journal;self.binding=binding
        self.observations=[]

    def call(self,messages,tools,phase):
        custody=Custody();self.observations.append(custody)
        try:return self._call(messages,tools,phase,custody)
        except BaseException as exc:
            if custody.first is None or custody.first[1] is not exc:custody.retain(exc,"provider-call")
            custody.raise_first()

    def _call(self,messages,tools,phase,custody):
        b=self.binding;budget=self.store.budget
        # Reviewer transport has an explicit selected encoded-byte bound, before provider effects.
        payload=canonical({"model":b["model"],"messages":messages,"tools":tools,**b["decoding"]})
        if phase in ("S26","S27"):
            cap=b.get("review_request_byte_cap")
            need(type(cap)is int and 0<cap<=64*2**20 and len(payload)<=cap,"review-provider-request-cap")
        need(b["model"] and b["decoding"] and b["price_identity"] and b["monetary_cap"]>0,
             "provider-selection")
        maximum_cost=b["max_input_tokens"]*b["input_price"]+b["max_output_tokens"]*b["output_price"]
        money=budget.reserve("currency_units",maximum_cost,"provider-monetary-reservation")
        # Reserve advertised maximal usage before request publication/dispatch.
        tokens=[budget.reserve("input_tokens",b["max_input_tokens"],"provider-input"),
                budget.reserve("output_tokens",b["max_output_tokens"],"provider-output")]
        read=budget.reserve("read_bytes",b["response_byte_cap"]+1,"provider-response")
        budget.attempt("provider_calls","provider-attempt")
        rid=self.journal.begin(phase,"provider",messages,{"response_cap":b["response_byte_cap"]})
        payload_record=self.store.write("provider-request-"+rid+".json",payload)
        response=None;body=b"";unknown=False
        try:
            request=urllib.request.Request(b["endpoint"],data=payload,method="POST",
                      headers={"Content-Type":"application/json",
                               "Authorization":"Bearer "+os.environ[b["credential_variable"]]})
            response=urllib.request.urlopen(request,timeout=b["timeout_seconds"])
            body=response.read(b["response_byte_cap"]+1)
            need(len(body)<=b["response_byte_cap"],"provider-response-cap")
            out=parse(body)
            need(out["request_id"] and out["model"]==b["model"],"provider-original-response")
            usage=out["usage"]
            budget.settle(tokens[0],usage["input_tokens"]);tokens.pop(0)
            budget.settle(tokens[0],usage["output_tokens"]);tokens.pop(0)
            cost=usage["input_tokens"]*b["input_price"]+usage["output_tokens"]*b["output_price"]
            need(cost<=maximum_cost,"provider-price-reservation")
            budget.settle(money,cost);money=None
        except BaseException as exc:
            unknown=True;custody.retain(exc,"provider")
        finally:
            if response is not None:
                before=custody.first
                custody.close(response,lambda r:r.close(),"provider-close")
                if custody.first is not before:
                    budget.unknown.append({"effect":"provider-response-close","unacknowledged_capacity":"closure"})
            for t in tokens:budget.settle(t,0,unknown=True)
            if money is not None:budget.settle(money,0,unknown=True)
            budget.settle(read,len(body),unknown=unknown)
        custody.raise_first()
        artifact=self.store.write("provider-response-"+rid+".json",body)
        receipt=self.journal.finish(rid,{"response":artifact,"payload":payload_record},
                                    {"provider_request_id":out["request_id"],"provider_model":out["model"],"usage":usage,
                                     "cost":cost,"price_identity":b["price_identity"]})
        return out,receipt
