"""Optional, explicitly admitted Responses HTTPS code-authoring transport.

API shape: https://developers.openai.com/api/docs/guides/function-calling
This module makes no request at import and has no default credential or model.
The provider supplies source and analysis-tool calls, never accepted predictions.
"""
import http.client
import os
import ssl
import time
from .wire import canonical, parse, sha, need

TOOLS=[{"type":"function","name":name,"description":description,"strict":True,
        "parameters":{"type":"object","properties":{"source":{"type":"string"}},
                      "required":["source"],"additionalProperties":False}}
       for name,description in (
           ("probe_source","Run Python probe(packet) in the admitted isolated view. Return a finite JSON diagnostic."),
           ("submit_source","Commit Python source implementing fit(packet), predict(model,query), reproduce(packet)."))]

class ResponsesClient:
    def __init__(self,authority,actor,track,credential_fd,*,clock=time.monotonic_ns):
        self.authority=authority;self.policy=authority.provider(actor,track);self.clock=clock
        self.origin=authority.document["origin_ns"];self.deadline=authority.document["deadline_ns"]
        self.fd=credential_fd;self.calls=0;self.receipts=[];self._credential=None
        p=self.policy
        need(p.get("endpoint")=="https://api.openai.com/v1/responses" and type(p.get("model")) is str and p["model"],
             "Explicit official HTTPS endpoint and qualified model snapshot required")
        for k in ("max_requests","max_output_tokens","request_bytes","response_bytes","source_bytes","reserved_microusd_per_request","spending_cap_microusd"):
            need(type(p.get(k)) is int and p[k]>0,"Explicit provider resource reservation required")
        need(p["max_requests"]*p["reserved_microusd_per_request"]<=p["spending_cap_microusd"],"Provider reservation exceeds cap")
    def _remaining(self):
        now=self.clock();need(self.origin<=now<self.deadline,"Original provider deadline exceeded")
        return (self.deadline-now)/1e9
    def _key(self):
        if self._credential is None:
            self._credential=self.authority.provider_credential(self.fd)
        return self._credential
    def request(self,history):
        self._remaining();p=self.policy
        need(self.calls<p["max_requests"],"Provider request reservation exhausted")
        body=canonical({"model":p["model"],"input":history,"tools":TOOLS,"parallel_tool_calls":False,
                        "max_output_tokens":p["max_output_tokens"],"store":False})
        need(len(body)<=p["request_bytes"],"Full provider input exceeds admitted extent")
        self.authority.reserve_provider_request()
        key=self._key();self.calls+=1
        connection=http.client.HTTPSConnection("api.openai.com",443,timeout=self._remaining(),context=ssl.create_default_context())
        raw=bytearray();status=None
        try:
            connection.request("POST","/v1/responses",body=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
            response=connection.getresponse();status=response.status
            need(status==200,"Provider request failed; no retry or alternate endpoint")
            need(response.getheader("Content-Encoding", "identity")=="identity","Compressed provider body refused")
            while True:
                if connection.sock is not None: connection.sock.settimeout(self._remaining())
                chunk=response.read(min(65536,p["response_bytes"]+1-len(raw)))
                if not chunk: break
                raw.extend(chunk);need(len(raw)<=p["response_bytes"],"Provider response exceeded complete body bound")
            result=parse(bytes(raw),p["response_bytes"])
            need(type(result) is dict and result.get("status")=="completed" and type(result.get("output")) is list,
                 "Provider did not complete an exact response")
            self._remaining();return result
        finally:
            connection.close()
            self.receipts.append({"request_sha256":sha(body),"request_bytes":len(body),"response_sha256":sha(bytes(raw)),
                "response_bytes":len(raw),"http_status":status,"reserved_microusd":p["reserved_microusd_per_request"],
                "finished_ns":self.clock()})

def author_source(client,prompt,probe):
    """`probe` is the concrete isolated execution method, never a result provider."""
    history=[{"role":"user","content":prompt}];seen=set()
    while True:
        result=client.request(history)
        outputs=result["output"]
        calls=[x for x in outputs if x.get("type")=="function_call"]
        need(len(calls)==1,"Exactly one source/probe function required")
        call=calls[0]
        need(call.get("call_id") not in seen and type(call.get("call_id")) is str,"Unique provider call required")
        seen.add(call["call_id"])
        arguments=parse(call["arguments"].encode(),client.policy["response_bytes"])
        need(type(arguments) is dict and set(arguments)=={"source"} and type(arguments["source"]) is str
             and 0<len(arguments["source"].encode())<=client.policy["source_bytes"],"Bounded source text required")
        source=arguments["source"]
        compile(source,"<candidate>","exec") # syntax only; source runs solely in the worker image
        if call["name"]=="submit_source": return source
        need(call["name"]=="probe_source","Unapproved provider tool")
        diagnostic=probe(source)
        # Keep reasoning and tool items in their original order for subsequent calls.
        history.extend(outputs)
        history.append({"type":"function_call_output","call_id":call["call_id"],"output":canonical(diagnostic).decode()})
