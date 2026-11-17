"""Exact candidate ceilings and cumulative, same-context metering.

Arithmetic checks are not process isolation. Linux supervision and trusted model
metering must independently provide the observations consumed by this ledger.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from .custody import CustodyError, digest, require_digest


class BudgetExceeded(RuntimeError):
    def __init__(self, dimension, used, cap):
        self.dimension, self.used, self.cap = dimension, used, cap
        super().__init__(f"resource ceiling exceeded: {dimension}: {used} > {cap}")


@dataclass(frozen=True)
class CandidateCaps:
    model_calls: int = 512
    input_tokens: int = 2097152
    output_tokens: int = 131072
    tool_calls: int = 10000
    wall_ns: int = 172800000000000
    cpu_ns: int = 2764800000000000
    simultaneous_cores: int = 16
    private_rss_bytes: int = 68719476736
    writable_bytes: int = 549755813888
    output_stream_bytes: int = 16777216
    output_line_bytes: int = 8192
    gpu_devices: int = 0

    def __post_init__(self):
        if asdict(self) != {
            "model_calls":512,"input_tokens":2097152,"output_tokens":131072,
            "tool_calls":10000,"wall_ns":172800000000000,"cpu_ns":2764800000000000,
            "simultaneous_cores":16,"private_rss_bytes":68719476736,
            "writable_bytes":549755813888,"output_stream_bytes":16777216,
            "output_line_bytes":8192,"gpu_devices":0}:
            raise CustodyError("changing the selected candidate resource profile requires a new version")

    @property
    def binding_digest(self):
        return digest(asdict(self))


def _counter(value, name):
    if type(value) is not int or value < 0:
        raise CustodyError("nonnegative integer counter required: " + name)
    return value


class ResourceLedger:
    """One context, both phases; no refunds, resetting or budget transfer."""
    def __init__(self, *, context_id: str, started_monotonic_ns: int,
                 caps: CandidateCaps | None = None):
        if not context_id:
            raise CustodyError("context identity required")
        self.context_id = context_id
        self.caps = caps or CandidateCaps()
        self.started_ns = _counter(started_monotonic_ns, "start")
        self.last_ns = self.started_ns
        self.model_calls = self.input_tokens = self.output_tokens = self.tool_calls = 0
        self.cpu_ns = self.peak_private_rss = self.peak_writable = 0
        self.provider_requests = {}
        self.tool_requests = set()
        self.events = []
        self.violation = None
        self.closed = False

    def _event(self, kind, values):
        event = {"context_id":self.context_id,"index":len(self.events),"kind":kind,
                 "values":values,"previous":self.events[-1]["digest"] if self.events else "0"*64}
        event["digest"] = digest(event)
        self.events.append(event)

    def _check(self, name, value, cap):
        if value > cap:
            self.violation = {"dimension":name,"used":value,"cap":cap}
            self._event("violation", self.violation)
            raise BudgetExceeded(name,value,cap)

    def _open(self):
        if self.closed or self.violation is not None:
            raise CustodyError("resource context is closed or exhausted")

    def observe(self, *, monotonic_ns: int, total_cpu_ns: int,
                private_rss_bytes: int, writable_bytes: int,
                simultaneous_cores: int, gpu_devices: int, evidence_digest: str):
        """Total CPU is cumulative over all children, tools and trusted attributed work."""
        if self.closed:
            raise CustodyError("resource context is closed")
        require_digest(evidence_digest)
        values = {"monotonic_ns":monotonic_ns,"total_cpu_ns":total_cpu_ns,
                  "private_rss_bytes":private_rss_bytes,"writable_bytes":writable_bytes,
                  "simultaneous_cores":simultaneous_cores,"gpu_devices":gpu_devices}
        for key,value in values.items():
            _counter(value,key)
        if monotonic_ns < self.last_ns or total_cpu_ns < self.cpu_ns:
            raise CustodyError("resource observations cannot go backwards")
        self.last_ns, self.cpu_ns = monotonic_ns,total_cpu_ns
        self.peak_private_rss = max(self.peak_private_rss,private_rss_bytes)
        self.peak_writable = max(self.peak_writable,writable_bytes)
        self._event("observation",{**values,"evidence_digest":evidence_digest})
        self._check("wall_ns",monotonic_ns-self.started_ns,self.caps.wall_ns)
        self._check("cpu_ns",total_cpu_ns,self.caps.cpu_ns)
        self._check("private_rss_bytes",private_rss_bytes,self.caps.private_rss_bytes)
        self._check("writable_bytes",writable_bytes,self.caps.writable_bytes)
        self._check("simultaneous_cores",simultaneous_cores,self.caps.simultaneous_cores)
        self._check("gpu_devices",gpu_devices,self.caps.gpu_devices)

    def reserve_model(self, request_id: str, *, input_tokens: int, max_output_tokens: int,
                      tokenizer_receipt_digest: str):
        self._open(); require_digest(tokenizer_receipt_digest)
        _counter(input_tokens,"input_tokens"); _counter(max_output_tokens,"max_output_tokens")
        if not request_id or request_id in self.provider_requests:
            raise CustodyError("unique model request ID required")
        self._check("model_calls",self.model_calls+1,self.caps.model_calls)
        self._check("input_tokens",self.input_tokens+input_tokens,self.caps.input_tokens)
        # Reserve the declared response ceiling while requests are in flight.
        reserved=sum(x["max_output_tokens"] for x in self.provider_requests.values() if x["status"]=="reserved")
        self._check("output_tokens_reserved",self.output_tokens+reserved+max_output_tokens,self.caps.output_tokens)
        self.model_calls += 1
        self.input_tokens += input_tokens
        self.provider_requests[request_id] = {"status":"reserved","input_tokens":input_tokens,
            "max_output_tokens":max_output_tokens,"tokenizer_receipt":tokenizer_receipt_digest}
        self._event("model_reserved",{"request_id":request_id,**self.provider_requests[request_id]})

    def complete_model(self, request_id: str, *, charged_input_tokens: int,
                       charged_output_tokens: int, usage_receipt_digest: str,
                       failed: bool = False):
        """Cached inputs and reported/billed hidden reasoning must be included."""
        if self.closed:
            raise CustodyError("resource context is closed")
        require_digest(usage_receipt_digest)
        _counter(charged_input_tokens,"charged_input_tokens"); _counter(charged_output_tokens,"charged_output_tokens")
        req = self.provider_requests.get(request_id)
        if req is None or req["status"]!="reserved":
            raise CustodyError("unknown or completed model request")
        if charged_input_tokens < req["input_tokens"]:
            raise CustodyError("metering cannot refund reserved input tokens")
        self.input_tokens += charged_input_tokens-req["input_tokens"]
        self.output_tokens += charged_output_tokens
        req.update(status="failed" if failed else "completed",actual_input_tokens=charged_input_tokens,
                   actual_output_tokens=charged_output_tokens,usage_receipt_digest=usage_receipt_digest)
        self._event("model_completed",{"request_id":request_id,**req})
        self._check("input_tokens",self.input_tokens,self.caps.input_tokens)
        self._check("per_response_output_tokens",charged_output_tokens,req["max_output_tokens"])
        self._check("output_tokens",self.output_tokens,self.caps.output_tokens)

    def begin_tool(self, request_id: str, *, tool: str, input_digest: str):
        self._open(); require_digest(input_digest)
        if not request_id or request_id in self.tool_requests or not tool:
            raise CustodyError("unique tool request and name required")
        self._check("tool_calls",self.tool_calls+1,self.caps.tool_calls)
        self.tool_calls += 1
        self.tool_requests.add(request_id)
        self._event("tool",{"request_id":request_id,"tool":tool,"input_digest":input_digest})

    def close(self, *, final_monotonic_ns: int, final_meter_digest: str):
        if self.closed:
            raise CustodyError("resource receipt already closed")
        require_digest(final_meter_digest)
        _counter(final_monotonic_ns,"final_monotonic_ns")
        if final_monotonic_ns < self.last_ns:
            raise CustodyError("final wall clock goes backwards")
        if any(x["status"]=="reserved" for x in self.provider_requests.values()):
            raise CustodyError("unresolved provider usage invalidates resource accounting")
        # Exhaustion is retained as a candidate failure; missing metering is an incident.
        wall=final_monotonic_ns-self.started_ns
        if wall > self.caps.wall_ns and self.violation is None:
            self.violation={"dimension":"wall_ns","used":wall,"cap":self.caps.wall_ns}
        self.closed=True
        result={"schema":"n073_resource_receipt_v1","context_id":self.context_id,
                "caps_digest":self.caps.binding_digest,"model_calls":self.model_calls,
                "input_tokens":self.input_tokens,"output_tokens":self.output_tokens,
                "tool_calls":self.tool_calls,"wall_ns":wall,"cpu_ns":self.cpu_ns,
                "peak_private_rss":self.peak_private_rss,"peak_writable":self.peak_writable,
                "violation":self.violation,"events_digest":digest(self.events),
                "final_meter_digest":final_meter_digest}
        result["receipt_digest"]=digest(result)
        return result
