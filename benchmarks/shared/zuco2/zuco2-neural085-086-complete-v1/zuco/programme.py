"""Exact participant source closure and globally frozen policy admission."""
from pathlib import Path
from .io import *
from .constants import MODES,INFORMATION_SET
FIELDS=("schema","source_root","files","entry","investigation_entry","mode","runtime","controller","prompts","tools","exposure","information_set","output_policy")
def admit(manifest,guard=lambda:None):
    guard();p=path_guard(manifest,True);b=read(p,1024**2,guard=guard);m=decode(b);exact(m,FIELDS);need(m["schema"]=="zuco2-participant-v1" and m["mode"] in MODES and m["information_set"]==INFORMATION_SET,"participant_policy")
    root=below(p.parent,m["source_root"]);need(type(m["files"])is list and m["files"],"source_files")
    seen=set();total=0
    for f in m["files"]:
        descriptor(f);need(f["path"] not in seen,"duplicate_source");seen.add(f["path"]);read(below(root,f["path"]),16*1024**2,f,guard);total+=f["bytes"]
    need(total<=32*1024**2,"source_cap");need(inventory(root,1024,32*1024**2,guard)==sorted(m["files"],key=lambda x:x["path"]),"complete_source_inventory")
    for k in ("entry","investigation_entry"):
        need(type(m[k])is list and len(m[k])==2 and m[k][0]=="python3" and m[k][1] in seen,"entrypoint",k)
    need(type(m["runtime"])is dict and type(m["controller"])is dict and type(m["prompts"])is list and type(m["tools"])is list and type(m["exposure"])is dict,"method_freeze")
    need(m['output_policy']=='complete_files_and_dynamic_trace_v1','output_inventory_policy')
    for tool in m['tools']:
        exact(tool,['name','source_files','mode']);need(tool['mode']=='bundled_offline_code' and tool['source_files'] and set(tool['source_files'])<=seen,'unadmitted_tool_or_decoder')
    need(m['runtime'].get('language')=='python3' and m['runtime'].get('network')=='none','frozen_runtime_policy')
    return {"manifest":m,"manifest_pin":{"path":str(p),**pin(b)},"source_root":str(root),"frozen_policy_sha256":digest(m),"files":m["files"],"source_bytes":total}
def copy_source(program,destination,ledger):
    ledger.guard();need(not Path(destination).exists(),"fresh_source_copy");ledger.reserve_bytes(program["source_bytes"],"complete participant source copy")
    for d in program["files"]:write(below(destination,d["path"]),read(below(program["source_root"],d["path"]),16*1024**2,d,ledger.guard))
    need(inventory(destination,1024,32*1024**2,ledger.guard)==sorted(program["files"],key=lambda x:x["path"]),"copied_source_identity")
