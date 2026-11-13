"""Closed source API, primitive state and complete original scientific traces.

Only this module and __init__ may be imported without numerical libraries. No
function here grants scientific authority; the enclosing controller owns gates.
"""
import hashlib
import json
import math
from ..contracts import Custody, diagnostic, ScientificFailure



def require(ok, message):
    if not ok:
        raise ScientificFailure(message)


def configuration(config):
    require(type(config) is dict, "Closed scientific configuration required")
    require(set(config) <= {"bindings", "limits", "training_state", "joint_development", "gpfa_qualification"}, "Unknown scientific configuration option")
    require(set(config["bindings"]) in ({"programme", "source", "dependencies", "training"}, {"programme", "source", "dependencies", "training", "query"}), "Exact source/input binding roles")
    for v in config["bindings"].values():
        require(type(v) is str and len(v) == 64 and all(x in "0123456789abcdef" for x in v), "Authenticated SHA256 identity required")
    limits = config["limits"]
    require(set(limits) == {"max_state_bytes", "max_state_nodes", "max_trace_events"}, "Exact scientific resource limits")
    require(all(type(v) is int and v > 0 for v in limits.values()), "Positive selected limits required")
    return config


class Recorder:
    """Original events are held before bounded encoding/publication can fail."""
    def __init__(self, trace, config, reference_id):
        require(callable(trace), "Actual trusted trace sink required")
        self.trace = trace
        self.maximum = config["limits"]["max_trace_events"]
        self.reference_id = reference_id
        self.events = []
        self.custody = Custody("scientific_recorder:" + reference_id)
        self.original_native_optimizer_results = []
        self.original_native_fit_observations = []
        self.original_warning_records = []
        self.custody.original_native_optimizer_results = self.original_native_optimizer_results
        self.custody.original_native_fit_observations = self.original_native_fit_observations
        self.custody.original_warning_records = self.original_warning_records

    def event(self, phase, **facts):
        event = {"reference_id": self.reference_id, "event_index": len(self.events), "phase": phase, **facts}
        self.events.append(event)  # retain original facts before fallible work
        try:
            require(len(self.events) <= self.maximum, "Complete trace exceeds selected event allowance")
            # No scientific arrays belong in these immutable event dictionaries.
            frozen = json.loads(json.dumps(event, allow_nan=False, sort_keys=True))
            self.trace(frozen)
        except BaseException as exc:
            self.custody.fail(exc, "trace_publication")
            raise ScientificFailure("Scientific trace could not be published", self.custody.first_error, self.events, self.custody) from exc

    def failure(self, original):
        # Only this exact source-owned carrier may transfer an owner. Subclasses
        # are opaque raw exceptions: no annotation, attributes or metaclass calls.
        if type(original) is ScientificFailure and type(original.custody) is Custody:
            if original.custody is not self.custody:
                self.custody.fail(None, "scientific_nested", original.custody)
            if self.custody.first_error is None:
                self.custody.fail(original, "scientific_original")
        else:
            self.custody.fail(original, "scientific_original")
        carrier = ScientificFailure("Scientific producer failed", self.custody.first_error, self.events, self.custody)
        carrier.original_native_optimizer_results = self.original_native_optimizer_results
        carrier.original_native_fit_observations = self.original_native_fit_observations
        carrier.original_warning_records = self.original_warning_records
        try:
            self.event("producer_failed", scientific_reason="scientific_producer_failed",
                       original_cause=diagnostic(self.custody.first_error))
        except BaseException as secondary:
            if type(secondary) is not ScientificFailure or secondary.custody is not self.custody:
                self.custody.fail(secondary, "failure_publication")
        return carrier


def primitive_state(value, config):
    """Copy a bounded finite state; sklearn, GPFA and arbitrary objects refuse."""
    import numpy as np
    total = 0
    nodes = 0
    seen = set()

    def visit(x, depth):
        nonlocal total, nodes
        nodes += 1
        require(depth <= 64 and nodes <= config["limits"]["max_state_nodes"], "State graph bound")
        if type(x) is np.ndarray:
            require(x.dtype.kind in "buifUS" and not x.dtype.hasobject, "Non-object numeric/string state arrays only")
            require(x.ndim <= 8, "State array rank bound")
            if x.dtype.kind == "f":
                require(np.isfinite(x).all(), "Finite stored state")
            total += x.nbytes
            require(total <= config["limits"]["max_state_bytes"], "State byte allowance")
            return x.copy(order="C")
        if isinstance(x, np.generic):
            return visit(x.item(), depth+1)
        if x is None or type(x) in (str, bool, int, float):
            if type(x) is float:
                require(math.isfinite(x), "Finite primitive state scalar")
            total += len(json.dumps(x, ensure_ascii=False, allow_nan=False).encode())
            require(total <= config["limits"]["max_state_bytes"], "State scalar byte allowance")
            return x
        require(type(x) in (dict, list, tuple), "Native scientific object cannot escape as state")
        require(id(x) not in seen, "Cyclic state forbidden")
        seen.add(id(x))
        try:
            if type(x) is dict:
                require(all(type(k) is str for k in x), "State mapping keys must be strings")
                total += sum(len(k.encode()) for k in x)
                y = {k: visit(v, depth+1) for k,v in x.items()}
            else:
                y = [visit(v, depth+1) for v in x]
                if type(x) is tuple:
                    y = tuple(y)
        finally:
            seen.remove(id(x))
        require(total <= config["limits"]["max_state_bytes"], "State container byte allowance")
        return y
    return visit(value, 0)


def state_digest(state):
    import numpy as np
    h = hashlib.sha256()
    def add(x):
        if type(x) is np.ndarray:
            h.update(b"array\0" + x.dtype.str.encode() + b"\0" + repr(x.shape).encode()+b"\0")
            h.update(x.tobytes(order="C"))
        elif type(x) is dict:
            h.update(b"dict\0")
            for k in sorted(x):
                add(k); add(x[k])
        elif type(x) in (list, tuple):
            h.update(type(x).__name__.encode()+b"\0"+str(len(x)).encode()+b"\0")
            for v in x: add(v)
        else:
            h.update(json.dumps(x, allow_nan=False, ensure_ascii=False).encode()+b"\0")
    add(state)
    return h.hexdigest()


def check_state(state, config, reference_id=None):
    configuration(config)
    checked = primitive_state(state, config)
    require(checked["schema"] == "nlb017-scientific-state-v1", "Scientific state schema")
    require(checked["reference_id"] in tuple(f"R{i}" for i in range(9)), "Reference identity")
    if reference_id is not None:
        require(checked["reference_id"] == reference_id, "Reference identity mismatch")
    require(checked["bindings"] == {k:config["bindings"][k] for k in ("programme","source","dependencies","training")}, "Original training/source/recipe ancestry mismatch")
    return checked


def finish(reference_id, payload, certificate, training, config, recorder, phase="trained"):
    state = {"schema": "nlb017-scientific-state-v1", "reference_id": reference_id,
             "bindings": {k:config["bindings"][k] for k in ("programme","source","dependencies","training")},
             "phase": phase, "payload": payload, "development": certificate,
             "training_trial_ids": training.get("train_trial_ids"),
             "heldout_unit_ids": training["heldout_unit_ids"],
             "heldin_unit_ids": training.get("heldin_unit_ids"),
             "bin_left_edges_ms": training.get("bin_left_edges_ms"),
             "query_binding": None, "parent_state_digest": None}
    out = primitive_state(state, config)
    recorder.event("training_state_complete", phase_state=phase, state_digest=state_digest(out))
    return out


def counts(value, shape, name):
    import numpy as np
    x = np.asarray(value)
    require(x.shape == shape and x.dtype.kind in "uif" and not x.dtype.hasobject, name+" exact count geometry")
    require(np.isfinite(x).all() and (x >= 0).all() and (x == np.floor(x)).all(), name+" finite nonnegative integral counts")
    return x


def labels(value, length, name, unique=False):
    import numpy as np
    x=np.asarray(value)
    require(x.shape==(length,) and x.dtype.kind=="U" and all(bool(v) for v in x.tolist()), name+" Unicode axis")
    if unique: require(len(set(x.tolist()))==length, name+" unique identities")
    return x


def training_view(training, reference_id):
    import numpy as np
    common={"train_trial_ids","heldout_unit_ids","heldin_unit_ids","bin_left_edges_ms","train_condition_ids","train_counts_heldout","train_counts_heldin","train_count_totals","train_bin_opportunities","panel_fingerprint","source_manifest_sha256"}
    require(type(training) is dict and set(training)<=common, "TrainingView role allowlist; query targets forbidden")
    labels(training["heldout_unit_ids"],45,"withheld units",True)
    if "train_count_totals" in training:
        require(reference_id=="R0" and set(training)<={"train_count_totals","train_bin_opportunities","heldout_unit_ids","panel_fingerprint","source_manifest_sha256"}, "Rate-only physical projection")
        counts(training["train_count_totals"],(45,),"training totals")
        require(type(training["train_bin_opportunities"]) is int and training["train_bin_opportunities"]==1721*140,"all original rate opportunities")
        return
    bins=np.asarray(training["bin_left_edges_ms"])
    require(bins.shape==(140,) and bins.dtype.kind in "uif" and np.isfinite(bins).all() and np.all(np.diff(bins.astype(np.float64))==5), "140 original five-ms bins")
    y=counts(training["train_counts_heldout"],(1721,140,45),"training withheld")
    labels(training["train_trial_ids"],len(y),"training trials",True)
    labels(training["train_condition_ids"],len(y),"training conditions")
    if reference_id not in ("R0","R1","R2"):
        counts(training["train_counts_heldin"],(1721,140,137),"training observed")
        labels(training["heldin_unit_ids"],137,"observed units",True)


def query_view(query, state, config, full=False):
    import numpy as np
    allowed={"eval_counts_heldin","eval_condition_ids","eval_trial_ids","heldin_unit_ids","heldout_unit_ids","bin_left_edges_ms","eval_valid_mask","panel_fingerprint","source_manifest_sha256"}
    require(type(query) is dict and set(query)<=allowed,"QueryPoolView role allowlist; no evaluation targets/mean")
    if state["reference_id"]=="R0" and state["payload"].get("input_projection")=="rate_only":
        require(set(query)<={"eval_trial_ids","heldout_unit_ids","bin_left_edges_ms","eval_valid_mask","panel_fingerprint","source_manifest_sha256"},"rate-only query excludes conditions/observed neurons")
    n=len(query["eval_trial_ids"])
    require(n==574 if full else 1<=n<=574,"complete pool or declared inference slice")
    ids=labels(query["eval_trial_ids"],n,"query trials",True)
    if state["training_trial_ids"] is not None:
        require(not (set(ids.tolist()) & set(state["training_trial_ids"].tolist())),"query and original training trials must be disjoint")
    require(np.array_equal(query["heldout_unit_ids"],state["heldout_unit_ids"]),"query withheld unit identity")
    query_bins=np.asarray(query["bin_left_edges_ms"])
    require(query_bins.shape==(140,) and query_bins.dtype.kind in "uif" and np.isfinite(query_bins).all() and np.all(np.diff(query_bins.astype(np.float64))==5),"complete original query clock")
    if state["bin_left_edges_ms"] is None:
        require(state["reference_id"]=="R0" and state["phase"]=="trained" and state["payload"].get("input_projection")=="rate_only", "only rate-only TrainingState defers output clock")
    else:
        require(np.array_equal(query_bins,state["bin_left_edges_ms"]),"query time identity")
    mask=np.asarray(query["eval_valid_mask"])
    require(mask.shape==(n,140,45) and mask.dtype.kind=="b","full original boolean valid mask")
    if state["reference_id"] not in ("R0","R1","R2"):
        counts(query["eval_counts_heldin"],(n,140,137),"query observed")
        require(np.array_equal(query["heldin_unit_ids"],state["heldin_unit_ids"]),"query observed unit identity")
    if state["reference_id"]!="R0": labels(query["eval_condition_ids"],n,"query conditions")
    require("query" in config["bindings"],"original query pool binding required")
    if state["phase"]=="adapted":
        require(state["query_binding"]==config["bindings"]["query"],"adapted state query lineage")
        require(set(ids.tolist())<=set(state["query_trial_ids"].tolist()),"inference slice must belong to exact adapted pool")
    return n


def split_rows(training, split):
    import numpy as np
    require(type(split) is dict and set(split)=={"fit_indices","validation_indices","descriptor"},"D0 admitted split schema")
    f,v=(np.asarray(split[k]) for k in ("fit_indices","validation_indices"))
    require(f.shape==(1381,) and v.shape==(340,) and f.dtype.kind in "iu" and v.dtype.kind in "iu", "D0 original 1381/340 support")
    require(np.array_equal(np.sort(np.concatenate([f,v])),np.arange(1721)) and np.all(np.diff(f)>0) and np.all(np.diff(v)>0),"D0 exact whole-trial partition")
    require(type(split["descriptor"]) is dict and split["descriptor"].get("source_split_sha256")=="56281244725d7062955bd2be6ab7f2393765acda5d6a19702d1c41f369c0eb5c", "Original admitted D0 split descriptor")
    return f,v


def valid_rates(rates, n):
    import numpy as np
    p=np.asarray(rates)
    require(p.shape==(n,140,45) and p.dtype.kind=="f" and np.isfinite(p).all() and (p>0).all(),"complete positive finite expected-count output")
    return p


def pooled_ll(y,p):
    import numpy as np
    require(y.shape==p.shape and np.isfinite(p).all() and (p>0).all(),"aligned positive development rates")
    z=float(np.sum(np.asarray(y,dtype=np.float64)*np.log(np.asarray(p,dtype=np.float64))-p,dtype=np.float64))
    require(math.isfinite(z),"development likelihood overflow")
    return z


def native_development_bps(y,p):
    """Organizer native inner-fold co-bps convention, not protected assessment."""
    import numpy as np
    from scipy.special import gammaln
    require(y.shape==p.shape and np.isfinite(p).all() and (p>0).all(),"native development domain")
    total=float(np.sum(y));require(math.isfinite(total) and total>0,"undefined zero-total development bps")
    # Preserve organizer zero-null replacement and separate factorial reductions.
    null=np.tile(np.mean(y,axis=(0,1),keepdims=True),y.shape[:-1]+(1,))
    null[null==0]=1e-9
    model_nll=np.sum(p-y*np.log(p)+gammaln(y+1.0))
    null_nll=np.sum(null-y*np.log(null)+gammaln(y+1.0))
    result=float((null_nll-model_nll)/total/np.log(2))
    require(math.isfinite(result),"native development score unavailable")
    return result
