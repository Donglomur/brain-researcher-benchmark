"""Whole-source biological admission; pin identity never establishes biology by itself."""
import copy, re
from .common import exact,need,object_pin,read_json,read,check_pin,pin,decode
from .legacy.source_map import SOURCE_PIN, mapping
from .legacy.history import finite
ROLES=("aggregate_census","animal_identity","native_clock","frame_alignment","anatomical_orientation","SAAV_identity","processed_signal_support")
def admission(export,binding,qualification,expected_qualification_pin,qualification_body):
    """expected pin comes from separately qualified root deployment, never candidate."""
    check_pin(expected_qualification_pin,4194304)
    need(type(qualification_body) is bytes and pin(qualification_body)==expected_qualification_pin and decode(qualification_body)==qualification,"Exact independently admitted original qualification bytes")
    exact(qualification,["schema","source_pin","export_pin","binding_pin","export_file_pin","binding_file_pin","release_roster","records","evidence_pins","limitations"])
    check_pin(qualification["export_file_pin"],64000000);check_pin(qualification["binding_file_pin"],32000000)
    need(qualification["schema"]=="neural047-biological-admission-v1" and qualification["source_pin"]==SOURCE_PIN,"Exact selected WT")
    need(qualification["export_pin"]==object_pin(export) and qualification["binding_pin"]==object_pin(binding),"Full exported fields/clock values bind external review")
    exact(qualification["evidence_pins"],ROLES)
    for desc in qualification["evidence_pins"].values():check_pin(desc,2**63-1)
    need(type(qualification["limitations"]) is list and "retrospective_processed_signal" in qualification["limitations"],"Processed-signal limitation retained")
    exact(export,["schema","source_pin","rows"]);exact(binding,["schema","source_pin","records"])
    need(export["schema"]=="neural047-wb-fields-v1" and binding["schema"]=="neural047-clock-animal-v1" and export["source_pin"]==binding["source_pin"]==SOURCE_PIN,"Exact source schemas")
    rows=export["rows"];anns=binding["records"];proof=qualification["records"]
    need(type(rows) is list and 3<=len(rows)<=256 and type(anns) is list and type(proof) is list and len(rows)==len(anns)==len(proof),"Entire source census")
    roster=qualification["release_roster"];need(type(roster) is list and all(type(x) is str for x in roster) and len(roster)==len(set(roster)),"Unique publisher recording roster")
    seen=set();physical=set();oriented=copy.deepcopy(export)
    for row,a,pr,o in zip(rows,anns,proof,oriented["rows"]):
        exact(row,["Name","velocity","reversal_vec","dv","saav_matches"])
        exact(a,["recording_id","animal_id","time_seconds","native_frame0","evidence"])
        exact(pr,["recording_id","recording_uid","animal_id","time_pin","frame_pin","dorsal_multiplier","saav_row_index1"])
        name=row["Name"];need(type(name) is str and name in roster and name not in seen,"All WT rows uniquely map into publisher roster");seen.add(name)
        need(pr["recording_id"]==a["recording_id"]==name and pr["animal_id"]==a["animal_id"] and type(a["animal_id"]) is str and 0<len(a["animal_id"])<=128,"Verified animal join")
        uid=pr["recording_uid"];need(type(uid) is str and uid and uid not in physical,"No duplicated physical recording representation");physical.add(uid)
        times=a["time_seconds"];frames=a["native_frame0"]
        need(type(times) is list and type(frames) is list and 3<=len(times)<=1000000 and len(times)==len(frames),"Native source clock, no nominal default")
        need(all(finite(t) for t in times) and all(x<y for x,y in zip(times,times[1:])),"Increasing physical time")
        need(all(type(x) is int and x>=0 for x in frames) and all(x<y for x,y in zip(frames,frames[1:])),"Increasing original frame IDs")
        need(pr["time_pin"]==object_pin(times) and pr["frame_pin"]==object_pin(frames),"Exact reviewed clocks/frames")
        for name2 in ("velocity","dv","reversal_vec"):need(type(row[name2]) is list and len(row[name2])==len(times),"Every row, including no-SAAV exclusions, has complete channel alignment")
        need(all(x is None or finite(x) for name2 in ("velocity","dv") for x in row[name2]),"Native missingness explicit")
        need(all(type(x) is int and x in (0,1) for x in row["reversal_vec"]),"Native reversal vector")
        matches=row["saav_matches"];need(type(matches) is list and len(matches)<=1,"No best-cell selection")
        if matches:
            m=matches[0];exact(m,["name","row_index1","trace"])
            need(m["name"]=="SAAV" and type(m["row_index1"]) is int and m["row_index1"]>0 and m["row_index1"]==pr["saav_row_index1"],"Independently established exact SAAV row")
            need(type(m["trace"]) is list and len(m["trace"])==len(times) and all(x is None or finite(x) for x in m["trace"]),"All native SAAV samples")
        else:need(pr["saav_row_index1"] is None,"No-SAAV evidence agrees")
        mult=pr["dorsal_multiplier"];need(type(mult) is int and mult in (-1,1),"Source-derived anatomical orientation")
        o["dv"]=[None if x is None else mult*x for x in row["dv"]]
    normalized=mapping(oriented,binding,set(roster))
    normalized["mapping_status"]="complete_native_mapping_bound_to_independently_selected_qualification"
    return normalized
def prepare_sources(paths,pins,deployment,ledger):
    """No endpoint retrieval. Opens only explicitly selected root inputs after qualification admission."""
    need(deployment["biological_admission"] is not None,"Biological admission is unconfigured")
    exact(paths,["aggregate","export","binding","qualification"])
    exact(pins,["export","binding"])
    original=read(paths["qualification"],deployment["biological_admission"],ledger,"biological qualification")
    qualification=decode(original)
    need(pins["export"]==qualification["export_file_pin"] and pins["binding"]==qualification["binding_file_pin"],"Original native-export and binding byte identities")
    read(paths["aggregate"],SOURCE_PIN,ledger,"all WT source bytes",retain=False)
    export=read_json(paths["export"],pins["export"],ledger,"complete native export")
    binding=read_json(paths["binding"],pins["binding"],ledger,"complete native clock binding")
    return admission(export,binding,qualification,deployment["biological_admission"],original)

