"""Exact complete artifact collection after observed child completion."""
from .strict import require, canonical_bytes, digest, decode, integer
from .arrays import descriptor,validate_stream
from .views import verify_tree

TERMINAL_FLAGS=("root_wait_observed","stdout_EOF","stderr_EOF","owned_subtree_empty",
                "stdout_persisted","stderr_persisted")

def admitted_observation(o,job,condition,receipt):
    require(o.get("status")=="complete" and o.get("root_exit")==0,"unsuccessful producer")
    require(all(o.get(k) is True for k in TERMINAL_FLAGS),"incomplete original process evidence")
    require(o.get("observation_record"),"missing retained original observation")
    require(o.get("source_execution")=="actual_os_child","invented process cannot qualify")
    require(o.get("original_start_ns")<o.get("observed_end_ns")<=o.get("cleanup_deadline_ns"),"original interval")
    require(receipt["job_id"]==job["job_id"] and receipt["condition"]==condition,"job/condition")
    require(receipt["contract_sha256"]==job["contract_sha256"],"wrong contract")
    require(receipt["source_profile_sha256"]==job["source_profile_sha256"],"source/profile evidence")
    require(receipt["producer_source_sha256"]==job["producer_source_sha256"],"producer source changed")
    return True

def collect(root,job,condition,contract,observation,*,clock,total_cap):
    integer(total_cap,"entire emitted output cap",1)
    receipt_body=root.read("result.json",min(total_cap,2*1024*1024),clock=clock)
    receipt=decode(receipt_body)
    require(receipt.get("schema")=="jaxley_complete_job_output_v1","job output schema")
    admitted_observation(observation,job,condition,receipt)
    expected={x["artifact_id"]:x for x in contract["outputs"]}
    rows=receipt.get("artifacts")
    require(type(rows) is list and len(rows)==len(expected),"complete output roster")
    require(len({x["artifact_id"] for x in rows})==len(rows),"duplicate artifacts")
    require({x["artifact_id"] for x in rows}==set(expected),"missing/extra artifact")
    # The only metadata file allowed is the bounded receipt. No unlisted scratch
    # file, empty extra directory, nested output or alias can be accepted.
    receipt_pin={"path":"result.json","bytes":len(receipt_body),"sha256":digest(receipt_body)}
    namespace=verify_tree(root,[receipt_pin,*rows],byte_cap=total_cap,file_cap=len(rows)+1,clock=clock)
    read_total=len(receipt_body)+namespace["authenticated_bytes"];observed=[]
    for row in rows:
        wanted=expected[row["artifact_id"]]
        for key in ("format","dtype","shape","axes","unit","semantic_role"):
            require(row.get(key)==wanted.get(key),"artifact semantic/coordinate mismatch: "+key)
        require(row["format"] in ("jaxley-flat-numeric-v1","json"),"unknown required product format")
        if row["format"]=="jaxley-flat-numeric-v1":descriptor(row)
        require(row.get("lineage")==wanted["lineage"],"unbound producer lineage")
        # Read cost includes both complete namespace authentication and content
        # validation. The retained-output cap is a separate quantity.
        if row["format"]=="json":
            decode(root.read(row["path"],min(total_cap,2*1024*1024),pin=row,clock=clock))
            read_total+=row["bytes"]
        else:
            checked=validate_stream(root,row,clock=clock,byte_cap=total_cap)
            read_total+=checked["bytes"]
        observed.append({k:row[k] for k in ("artifact_id","path","bytes","sha256","format","dtype","shape","axes","unit","semantic_role","lineage")})
    return {"schema":"jaxley_collected_job_v1","job_id":job["job_id"],"condition":condition,
            "contract_sha256":job["contract_sha256"],"source_profile_sha256":receipt["source_profile_sha256"],
            "producer_source_sha256":receipt["producer_source_sha256"],
            "artifacts":observed,"original_observation":observation["observation_record"],
            "complete":True,"read_bytes":read_total,"output_bytes":namespace["authenticated_bytes"],
            "receipt_pin":receipt_pin,"whole_namespace_authenticated":True,"all_numeric_products_finite":True,
            "collection_sha256":digest(canonical_bytes(observed))}

def complete_collection(manifest,condition,collected):
    expected=[j["job_id"] for j in manifest["jobs"]]
    require(condition in manifest["conditions"],"unknown condition")
    require(type(collected) is list and len(collected)==len(expected),"full job collection required")
    actual=[c["job_id"] for c in collected]
    require(actual==expected,"missing/reordered/duplicate job")
    require(all(c.get("condition")==condition and c.get("complete") is True for c in collected),"failed job in collection")
    return {"condition":condition,"manifest_sha256":digest(canonical_bytes(manifest)),
            "collections":collected,"collection_commit_sha256":digest(canonical_bytes(collected)),
            "all_required_jobs_collected":True}

