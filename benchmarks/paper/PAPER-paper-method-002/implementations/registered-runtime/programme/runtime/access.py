"""Construct condition descriptors without mixing experiment code or private targets."""
from .profiles import CONDITIONS
from .strict import require, relative, unique, canonical_bytes, digest

def make_view(condition, common, author_experiment, private_targets):
    require(condition in CONDITIONS,"condition")
    groups=[common,author_experiment,private_targets]
    for rows in groups:
        require(type(rows) is list,"view roster")
        unique([x["path"] for x in rows],"view paths")
        for row in rows:
            relative(row["path"])
            require(type(row.get("sha256")) is str and len(row["sha256"])==64 and all(c in "0123456789abcdef" for c in row["sha256"]),"view digest")
            require(type(row.get("bytes")) is int and row["bytes"]>=0,"pinned view")
    sets=[{x["path"] for x in xs} for xs in groups]
    require(not(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]),"view overlap")
    for row in common:
        require(row["role"] in {"paper","supplement","permitted_input","generic_dependency","generic_documentation","output_contract","development_context"},"author source inA")
        require(row.get("contains_saved_result") is False,"saved result incommon view")
    for row in author_experiment:
        require(row["role"]=="author_experiment_source" and row.get("output_free") is True,"unstripped author notebook/results")
    public=common+(author_experiment if condition.startswith("B") else [])
    require(not({x["path"] for x in public}&sets[2]),"target disclosure")
    return {"condition":condition,"public":public,"public_view_sha256":digest(canonical_bytes(public)),
            "private_target_count":len(private_targets),"fresh_state_required":True,
            "common_simulator":"library_assisted_Jaxley","internet":False}

def paired_views(a,b):
    require(a["condition"][0]=="A" and b["condition"][0]=="B" and a["condition"][2]==b["condition"][2],"pairedprocedure")
    a_common=[x for x in a["public"]]
    b_common=[x for x in b["public"] if x["role"]!="author_experiment_source"]
    require(a_common==b_common,"A/Bcommonresourcesdiffer")
    return True

