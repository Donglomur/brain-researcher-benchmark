"""Bounded ordinary operative-source closure; historical evidence is separate."""
from pathlib import Path
import hashlib
from owner.io import Artifact,ByteMeter,ContractError,capture,decode,ordinary
from owner.workflow import verify_implementation,contract_digest
from owner.contract import load_contract
from owner.constructor import interface_union

ROOT=Path(__file__).absolute().parents[1]
PROFILE="complete_omission_programme_v1"
CONDITIONS=[f"{m}-{v}-{t}" for m in ("F","I") for v in ("T","N") for t in ("G","R")]
SCOPE={"mice":107,"sessions":703,"experiments":1936,"published_roi_rows":133066,
       "split_mice":[73,15,19],"history_target_bins":[12,3],"conditions":8,
       "reference_fits":[28,2,5],"stages":28,"entry_predicates":122,"reports":8}

def routes(contract):
    result={"prepare":[],"reference":[],"candidate":[],"collect":[],"grade":[],"report":[]}
    for stage in contract["order"]:
        action=("prepare" if stage.startswith("S") else "reference" if stage.startswith(("R","C"))
                else "candidate" if stage in {"D00","D01","Q00","Q01"}
                else "collect" if stage in {"Q02","Q03"} else "grade" if stage in {"E00","E01"} else "report")
        result[action].append(stage)
    if sum(map(len,result.values()))!=28 or set(result["report"])!={"N00","E02"}:
        raise ContractError("complete concrete route partition required")
    return result

def load_source():
    meter=ByteMeter(8*1024*1024,0)
    path=ROOT/"SOURCE_MANIFEST.json";body=capture(path,1024*1024,meter=meter)
    value=decode(body)
    if value.get("portable_schema")!="neural063_portable_operative_source_v1":
        raise ContractError("portable operative source manifest required")
    ref=Artifact(str(path),len(body),hashlib.sha256(body).hexdigest(),"implementation_source_manifest","operator","source_freeze")
    _,manifest=verify_implementation(ref.object(),meter=meter)
    expected={str(f.relative_to(ROOT)) for folder in ("owner","preparation","references","runtime","central") for f in (ROOT/folder).glob("*.py")}
    expected|={str(f.relative_to(ROOT)) for f in (ROOT/"contract").glob("*.json")}
    expected|={x+"/INTERFACE.json" for x in ("owner","preparation","references","runtime")}
    expected|={"neural063.py","run.py","grade.py","DEPLOYMENT.json"}
    if {x["path"] for x in manifest["files"]}!=expected:
        raise ContractError("exact operative code/contract/configuration set required; no history or conditional-body substitution")
    contract=load_contract(meter=meter);interfaces=interface_union(meter=meter,contract=contract)
    return {"root":ROOT,"manifest":ref,"contract":contract,"contract_sha256":contract_digest(contract),
            "interfaces":interfaces,"routes":routes(contract),"source_reads":meter.read_bytes}

def inspect_source():
    s=load_source()
    return {"schema":"neural063_complete_portable_inspection_v1","task_id":"NEURAL-063","profile":PROFILE,
            "scope":SCOPE,"conditions":CONDITIONS,"routes":s["routes"],"stage_order":s["contract"]["order"],
            "source":s["manifest"].object(),"contract_sha256":s["contract_sha256"],"source_read_bytes":s["source_reads"],
            "external_records":57,"gates":{"captured_metadata":"partial","other_gates_open":27},
            "reference_gain":None,"raw_source_bytes":None,"events":None,"scientific_execution":False,
            "runtime_qualified":False,"historical_evidence_is_runtime_dependency":False}
