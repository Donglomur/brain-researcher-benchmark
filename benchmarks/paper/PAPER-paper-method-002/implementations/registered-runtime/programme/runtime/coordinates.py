"""Operation-specific scientific coordinate admission, before loading operands.

Paired estimands use strict identity/order equality. They never repair a
permutation silently. A native time-warp relation is possible only for soft-DTW,
whose definition explicitly includes that operation, and must be source-bound.
"""
from .strict import require, unique
from .arrays import descriptor

# Scientific array positions and complete positional ABI. Other arguments are
# pinned configuration literals, never undisclosed data-bearing kwargs.
SIGNATURES={
    "paired_errors":(2,(0,1)),"pearson":(2,(0,1)),"masked_metrics":(3,(0,1,2)),
    "window_summaries":(4,(0,)),"window_max":(3,(0,)),"soft_dtw":(4,(0,1)),
    "classification":(2,(0,1)),"regularizer":(2,(0,)),
    "bounded_forward":(3,(0,1,2)),"bounded_log_jacobian":(3,(0,1,2)),
    "posterior_log_density":(4,()),"quantiles":(2,(0,)),
    "distance_binned_quantiles":(4,(0,1)),"lyapunov":(3,(0,1)),
    "jacobian_sign":(1,(0,)),"parameter_reset":(3,(0,1)),
    "perturbation_norms":(2,(0,1)),"receptive_field_normalize":(1,(0,)),
    "paired_mean_difference":(3,(0,1)),
}

def validate(metric,artifact_map):
    op=metric["operation"];require(op in SIGNATURES,"coordinate operation")
    count,positions=SIGNATURES[op];args=metric["arguments"]
    require(type(args) is list and len(args)==count,"complete positional metric signature")
    require(metric.get("kwargs") in (None,{}),"metric kwargs cannot bypass coordinate admission")
    policy=metric.get("coordinate_contract")
    require(type(policy) is dict and policy.get("schema")=="jaxley_metric_coordinates_v1","explicit metric coordinate contract required")
    expected=policy.get("operands")
    require(type(expected) is dict and set(expected)=={str(i) for i in positions},"all scientific operand coordinates required")
    arrays={};kinds={}
    for i,spec in enumerate(args):
        if i not in positions:
            require(set(spec)=={"literal"},"configuration must be a pinned literal")
            continue
        require(set(spec)=={"artifact","shape_as"},"scientific arrays require authenticated artifact identities")
        d=artifact_map[spec["artifact"]]["array"];descriptor(d)
        wanted=expected[str(i)]
        require(set(wanted)=={"shape","axes","axis_kinds","unit"},"scientific operand meaning")
        for key in ("shape","axes","unit"):
            require(d[key]==wanted[key],"operand differs from pinned metric "+key)
        axis_kinds=unique(wanted["axis_kinds"],"semantic axis kinds")
        require(len(axis_kinds)==len(d["shape"]) and all(type(x) is str and x for x in axis_kinds),"dimension meaning")
        require(type(d["unit"]) is str and bool(d["unit"]),"scientific unit required")
        require(spec["shape_as"] in ("vector","matrix","boolean_vector"),"coordinate layout")
        if spec["shape_as"]=="matrix":require(len(d["shape"])==2,"matrix dimensions")
        if spec["shape_as"]=="boolean_vector":require(d["dtype"]=="uint8" and d["unit"]=="boolean","boolean mask semantics")
        arrays[i]=d;kinds[i]=axis_kinds
    def same(a,b,unit=True):
        require(arrays[a]["shape"]==arrays[b]["shape"] and arrays[a]["axes"]==arrays[b]["axes"] and kinds[a]==kinds[b],"scientific identities/order do not align")
        if unit:require(arrays[a]["unit"]==arrays[b]["unit"],"paired scientific units differ")
    def rank(i,n):require(len(arrays[i]["shape"])==n,"operation-specific scientific rank")
    if op in ("paired_errors","pearson","paired_mean_difference","perturbation_norms"):
        same(0,1)
    elif op=="masked_metrics":
        same(0,1);same(0,2,False)
        require(args[2]["shape_as"]=="boolean_vector","masked operand must be boolean")
    elif op in ("bounded_forward","bounded_log_jacobian"):
        same(0,1,False);same(1,2)
        rank(0,1);require(arrays[0]["unit"]=="dimensionless","unconstrained parameter unit")
    elif op=="classification":
        rank(0,2);rank(1,1)
        require(arrays[0]["axes"][0]==arrays[1]["axes"][0] and kinds[0][0]==kinds[1][0],"logit/label case identities differ")
        require(kinds[0][1]=="class" and policy.get("label_class_ids")==arrays[0]["axes"][1],"class-index dictionary")
        require(arrays[0]["unit"] in ("dimensionless","logit") and arrays[1]["unit"]=="class_index","classification units")
        require(arrays[1]["dtype"] in ("int64-le","uint8"),"integer class-index wire format")
        require(args[0]["shape_as"]=="matrix" and args[1]["shape_as"]=="vector","classification layouts")
    elif op=="distance_binned_quantiles":
        rank(0,1);rank(1,2)
        require(arrays[0]["axes"][0]==arrays[1]["axes"][1] and kinds[0][0]==kinds[1][1],"distance/parameter identities differ")
        require(policy.get("configuration_units",{}).get("edges")==arrays[0]["unit"],"distance-bin unit binding")
        require(args[0]["shape_as"]=="vector" and args[1]["shape_as"]=="matrix","binned sample layouts")
    elif op=="lyapunov":
        same(0,1,False);rank(0,1)
        require(arrays[0]["unit"]=="dimensionless" and arrays[1]["unit"]=="steps","norm/step-count units")
        require(arrays[1]["dtype"] in ("int64-le","uint8") and policy.get("configuration_units",{}).get("dt"),"native step/time units")
    elif op=="soft_dtw":
        rank(0,1);rank(1,1)
        require(arrays[0]["unit"]==arrays[1]["unit"],"DTW measured quantity differs")
        relation=policy.get("sequence_relation")
        if relation=="identity_grid":same(0,1)
        else:
            require(type(relation) is dict and relation.get("kind")=="native_time_warp","DTW clock relation")
            require(kinds[0]==kinds[1]==["ordered_time"],"native DTW must declare ordered time")
            require(relation.get("left_axis")==arrays[0]["axes"][0] and relation.get("right_axis")==arrays[1]["axes"][0],"declared warp axes")
            pin=relation.get("definition_source",{})
            require(type(pin.get("sha256")) is str and len(pin["sha256"])==64 and type(pin.get("bytes")) is int and pin["bytes"]>0,"native time-warp source pin")
    elif op in ("regularizer","parameter_reset","window_summaries"):
        rank(0,1)
        if op=="parameter_reset":same(0,1);index_position=2
        else:index_position=1
        require(policy.get("index_axes",{}).get(str(index_position))==arrays[0]["axes"][0],"index configuration is not bound to scientific identities")
    elif op=="window_max":rank(0,1)
    elif op=="jacobian_sign":rank(0,2);require(args[0]["shape_as"]=="matrix","Jacobian matrix layout")
    # Quantiles/RF normalization use one completely declared array. Scalar
    # posterior-density checks have no hidden coordinate-bearing operands.
    return {"schema":policy["schema"],"paired_alignment":"strict_identity_order_no_implicit_permutation"}
