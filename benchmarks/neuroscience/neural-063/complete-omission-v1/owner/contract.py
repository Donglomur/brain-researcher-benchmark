"""Load and validate the exact accepted 28-stage design; no study execution."""
from pathlib import Path
import hashlib
from .io import capture, decode, ContractError


FILES = ("PROCESS_GRAPH.json", "REFERENCE_DESIGN.json", "COMPARISON_OUTCOMES.json",
         "EXECUTION_DISPOSITIONS.json", "LIFECYCLE_DESIGN.json",
         "RESOURCE_PLAN.json", "ADMISSION_GATES.json")


# Exact accepted V2 source bodies, not only matching stage counts.
EXPECTED = {'ADMISSION_GATES.json': {'bytes': 16556, 'sha256': 'dd229e1b298a3af1dd820cb891f0609a224b1d1c7abd2bf644ef7ac8568c697b'}, 'COMPARISON_OUTCOMES.json': {'bytes': 5896, 'sha256': '46cb37a0011da1640246acf6c6c51c4662d0daee364b80367e111c7527a09481'}, 'EXECUTION_DISPOSITIONS.json': {'bytes': 4133, 'sha256': 'ce2fd49aa9b4c32cfbb06c3624f632c81a3136b84d0285c5343e49f2ec81cfe9'}, 'LIFECYCLE_DESIGN.json': {'bytes': 8401, 'sha256': 'f66d78639a180909280217c732bd9467848c8e835eef06f13897e49836519e65'}, 'PROCESS_GRAPH.json': {'bytes': 62309, 'sha256': 'f5771c5e7a8f86a6800a560edf6bef066cdfe64800e7416857e98edaa345d150'}, 'REFERENCE_DESIGN.json': {'bytes': 10766, 'sha256': 'fdac67aace2f8feaedc533722b1c3b571f76214a175b8e98ee6bb2f365a1087d'}, 'RESOURCE_PLAN.json': {'bytes': 8688, 'sha256': 'c6d7b91d1371f8b0a44315a5a220a9c1bf4779163caddb2c6a9ceb59524a8226'}}

def load_contract(root=None, *, meter=None):
    root = Path(root) if root else Path(__file__).parent.parent / "contract"
    values, pins = {}, {}
    for name in FILES:
        body = capture(root / name, 2_000_000, meter=meter)
        pins[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        if pins[name] != EXPECTED[name]:
            raise ContractError("accepted scientific contract body changed: " + name)
        values[name] = decode(body)
    graph = values["PROCESS_GRAPH.json"]
    nodes = graph["nodes"]
    if len(nodes) != 28 or graph["node_count"] != 28:
        raise ContractError("all 28 original stages required")
    producers = {e["id"]: e["producer_node"] for e in graph["completion_evidence_registry"]}
    external = {e["id"]: e for e in graph["external_entry_evidence"]}
    if len(producers) != 28 or len(external) != 57:
        raise ContractError("complete 28 completion/57 external evidence roster required")
    ancestors = {}
    predicates = 0
    for node in nodes:
        ident = node["id"]
        if ident in ancestors or any(d not in ancestors for d in node["depends_on"]):
            raise ContractError("graph is not in unique dependency order")
        ancestors[ident] = set(node["depends_on"])
        for dep in node["depends_on"]:
            ancestors[ident].update(ancestors[dep])
        if producers[node["completion_evidence_id"]] != ident:
            raise ContractError("wrong completion producer")
        for eid in node["entry_evidence_ids"]:
            predicates += 1
            required = [eid] if eid in producers else external[eid]["requires_graph_evidence"]
            if any(producers[item] not in ancestors[ident] for item in required):
                raise ContractError("entry depends on own/future completion")
    if predicates != 122:
        raise ContractError("all 122 original entry predicates required")
    ref = values["REFERENCE_DESIGN.json"]
    if (len(ref["bases"]), len(ref["lambda_grid"]), len(ref["information_views"])) != (2, 7, 2):
        raise ContractError("reference grid changed")
    if len(values["LIFECYCLE_DESIGN.json"]["conditions"]) != 8:
        raise ContractError("all eight candidate conditions required")
    return {"documents": values, "pins": pins,
            "nodes": {n["id"]: n for n in nodes},
            "order": [n["id"] for n in nodes], "ancestors": ancestors,
            "external": external, "predicates": predicates}
