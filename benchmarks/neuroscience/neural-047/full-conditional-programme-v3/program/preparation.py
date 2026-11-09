"""Future preparation from externally qualified native export; no automatic acquisition or native conversion."""
from pathlib import Path
from .common import exact,need,Ledger,read_json,object_pin,publish,fresh_dir
from .deployment import load,qualified_outer
from .admission import prepare_sources
from .packets import construct,write_prepared
from .legacy.source_map import SOURCE_PIN
import os
def prepare(request):
    exact(request,["deployment_path","deployment_pin","limits","sources","source_pins","output","complete_retention_cap"])
    L=Ledger(request["limits"]);deployment,docs=load(request["deployment_path"],request["deployment_pin"],L)
    qualified_outer(docs["native_execution"])
    # The external qualified export is a required input. Its actual native conversion
    # must have a separately captured admitted lifetime; passing JSON is insufficient.
    evidence=docs["biological_admission"]
    need(evidence["export_file_pin"]==request["source_pins"]["export"],"Exact independently qualified complete export bytes")
    normalized=prepare_sources(request["sources"],request["source_pins"],{"biological_admission":{k:deployment["authorities"]["biological_admission"][k] for k in ("bytes","sha256")}},L)
    feasibility=docs["retention_feasibility"]
    need(feasibility["raw_export_binding_and_all_contexts_cap"]==request["complete_retention_cap"]<=300000000,"Original total retention ceiling")
    prepared=construct(normalized,os.urandom(32))
    # No secret is written; its derived opaque identifiers are held in the preparation.
    nonprepared=SOURCE_PIN["bytes"]+sum(x["bytes"] for x in request["source_pins"].values())
    remaining=request["complete_retention_cap"]-nonprepared
    need(remaining>0,"Complete original source/export/binding retention exceeds cap")
    return write_prepared(prepared,request["output"],L,remaining),L.summary()

