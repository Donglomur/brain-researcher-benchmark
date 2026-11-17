"""Complete source/event/cohort and deterministic projection source.

No source is opened at import. Native reading and this scientific projection
remain deployment-disabled and unexecuted during construction.
"""
from pathlib import Path
from .io import need, exact, canonical, identity, read, read_json, write_json
from .contract import ROSTER, CHANNELS, ARMS, DURATIONS, ORIENTATIONS, RELEVANCES, require_deployment

def validate_cohort(doc, binding):
    exact(doc,["schema","contract","published","legacy100_disposition","members","source_version","custodian_evidence"])
    need(doc["schema"]=="n097-cohort-v1" and doc["contract"]==binding,"Bound full cohort")
    need(doc["published"]=={"collected":102,"included":97,"optimization":32,"replication":65,"excluded":5},"Published counts")
    need(doc["legacy100_disposition"] and doc["custodian_evidence"],"No invented100/102 reconciliation")
    need([m["source_person"]for m in doc["members"]]==list(ROSTER),"Exact33 source selection")
    for m in doc["members"]:
        exact(m,["source_person","source_phase","paper_membership","site","system","visit","task","runs","source_parts","eligibility","provenance"])
        need(m["source_phase"] and m["paper_membership"] and m["site"] and m["system"] and m["eligibility"] and m["provenance"],"Empirical phase/site/inclusion bridge")
        need(m["visit"]=="V1" and m["task"]=="dur","Selected visit/task")
        need(type(m["runs"])is list and len(m["runs"])==10 and len(set(m["runs"]))==10,"All ten actual source runs")
        need(type(m["source_parts"])is list and m["source_parts"],"Complete native part union")
    return doc

def eligible(m):
    exact(m,["Stim_trigger","Category","Orientation","Duration","Task_relevance","Response"])
    t=m["Stim_trigger"]
    need(type(t)is int and 1<=t<=80,"Exact source stimulus trigger")
    need(m["Category"]==("face","object","letter","false")[(t-1)//20],"Source category/trigger agreement")
    need(m["Orientation"]in ORIENTATIONS and m["Duration"]in DURATIONS and
         m["Task_relevance"]in (*RELEVANCES,"Relevant target") and type(m["Response"])is bool,"Source event fields")
    return t<=40 and m["Task_relevance"]in RELEVANCES and not m["Response"]

def validate_epoch_lineage(row, member, source_version):
    exact(row,["source_person","visit","run","raw_sample","native_sample","onset_trigger","epoch_selection","metadata","image_identity","image_alias_proof","orientation_identity","source_parts","producer_versions","retention_decision","channels","channel_types","bads","times","values","units","preprocessing","lineage_proof"])
    need(row["source_person"]==member["source_person"] and row["visit"]=="V1" and row["run"]in member["runs"],"Observed person/visit/run join")
    need(type(row["raw_sample"])is int and row["raw_sample"]>=0 and type(row["epoch_selection"])is int and row["epoch_selection"]>=0,"Original source clocks and epoch identity")
    need(type(row["native_sample"])is int and row["native_sample"]>=0 and type(row["onset_trigger"])is int and row["onset_trigger"]==row["metadata"]["Stim_trigger"],"Typed native clock and onset/metadata identity")
    need(row["image_identity"] and row["image_alias_proof"] and row["orientation_identity"] and row["lineage_proof"],"Physical image and event provenance")
    need(set(row["source_parts"])<=set(member["source_parts"]) and row["source_parts"],"Complete source part join")
    need(row["producer_versions"]==source_version and row["retention_decision"]=="retained_by_original_preprocessing","Original producer/exclusion history")
    need(row["channels"]==list(CHANNELS) and row["channel_types"]==["mag"]*6 and not set(CHANNELS)&set(row["bads"]),"All six good source magnetometers")
    need(row["units"]=="T" and row["preprocessing"],"Physical units and whole-epoch preprocessing provenance")
    return row

def project_features(times,values):
    import math
    finite=lambda x:type(x)in(int,float)and math.isfinite(x)
    need(type(times)is list and 30<=len(times)<=20000 and all(finite(t)for t in times) and all(a<b for a,b in zip(times,times[1:])),"Complete native clock")
    need(len(values)==6 and all(len(v)==len(times)and all(finite(x)for x in v)for v in values),"Complete finite six-sensor epoch")
    def ix(lo,hi):return [i for i,t in enumerate(times)if lo-1e-9<=t<hi-1e-9]
    baseline=ix(-.5,-.3);need(baseline,"Baseline support")
    mu=[math.fsum(v[i]for i in baseline)/len(baseline)for v in values]
    out={}
    for arm,start in (("SIGNAL",.1),("PRE",-.3)):
        bins=[ix(start+b*.02,start+(b+1)*.02)for b in range(10)]
        need(all(bins),"All ten native sample bins")
        out[arm]=[math.fsum(v[i]-m for i in bucket)/len(bucket)for v,m in zip(values,mu)for bucket in bins]
        need(all(finite(x)for x in out[arm]),"Representable source projection")
    return out

def prepare(cohort, rows, binding, token_source, census, qualification, native_manifest):
    """Trusted private token source; never a candidate callback or supplied key."""
    require_deployment()
    validate_cohort(cohort,binding)
    from .census import validate_census,validate_observed
    census_index=validate_census(cohort,native_manifest,census,qualification,binding)
    members={m["source_person"]:m for m in cohort["members"]}
    seen=set();out=[];exclusions=[];image_half={}
    for row in rows:
        need(row["source_person"]in members,"Declared source person")
        validate_epoch_lineage(row,members[row["source_person"]],cohort["source_version"])
        key=validate_observed(row,census_index)
        need(key not in seen,"Unique compound epoch identity");seen.add(key)
        if not eligible(row["metadata"]):
            exclusions.append({"source":key,"reason":"non_face_object_or_target_or_recorded_response"});continue
        m=row["metadata"];t=m["Stim_trigger"];half=((t-1)%20)%2
        previous=image_half.setdefault(row["image_identity"],half)
        need(previous==half,"True physical image alias crosses fixed half rule")
        x=project_features(row["times"],row["values"])
        n=[float(m["Duration"]==d)for d in DURATIONS]+[float(m["Task_relevance"]==r)for r in RELEVANCES]+[float(m["Orientation"]==o)for o in ORIENTATIONS]
        x["NUISANCE"]=n;x["SIGNAL_NUISANCE"]=x["SIGNAL"]+n;x["PRE_NUISANCE"]=x["PRE"]+n
        out.append({"private_id":token_source(),"person":row["source_person"],"image":row["image_identity"],
                    "session":row["visit"],"run":row["run"],"half":half,"y":int(t<=20),
                    "stratum":[m["Task_relevance"],m["Duration"],m["Orientation"]],"views":x,
                    "source_identity":key})
    need(seen==set(census_index["expected_retained"]),"No original retained epoch omitted or synthesized")
    need({r["person"]for r in out}==set(ROSTER) and len({r["private_id"]for r in out})==len(out),"All33 and unique private observations")
    return {"schema":"n097-private-observations-v1","contract":binding,"rows":out,"exclusions":exclusions,
            "cohort_identity":identity(canonical(cohort)),"source_census_identity":census_index["identity"],
            "census_qualification_identity":census_index["qualification_identity"],"original_run_dispositions":census_index["run_dispositions"],
            "original_rejected_events":[{"source_person":m["source_person"],"run":run["run"],"event":e}for m in census["members"]for run in m["runs"]for e in run["events"]if e["disposition"]=="rejected"],"source_semantics_qualified":False}

def native_inventory(root, manifest, approved_total_bytes):
    """Authenticate the complete explicitly selected ordinary native file union."""
    require_deployment()
    from .io import stream_pin,relative
    need(type(approved_total_bytes)is int and approved_total_bytes>0,"Separately approved complete native byte budget")
    need(sum(x["bytes"]for x in manifest)<=approved_total_bytes,"Complete source union fits explicit selection, never truncate")
    names=set();out=[]
    for row in manifest:
        name=relative(row["path"]).as_posix()
        need(name.casefold()not in names,"Unique native member path");names.add(name.casefold())
        out.append({"path":name,**stream_pin(Path(root)/name,row)})
    return out

def mne_epoch_records(source_root, native_manifest, native_plan, cohort, binding, approved_total_bytes, census, qualification):
    """Read all selected split-aware files only after full native inventory.

    Source-native event/drop/clock lineage is a required trusted input. An absent
    row is refused, never manufactured from Trial_ID or an ordinal alignment.
    """
    require_deployment();validate_cohort(cohort,binding)
    from .census import validate_census,validate_observed
    census_index=validate_census(cohort,native_manifest,census,qualification,binding)
    native_inventory(source_root,native_manifest,approved_total_bytes)
    declared={x["path"]:x for x in native_manifest}
    need(set(native_plan)==set(ROSTER),"Full33 native reader plan")
    import mne
    for person in ROSTER:
        item=native_plan[person]
        member=next(m for m in cohort["members"]if m["source_person"]==person)
        epoch_parts={x for x in member["source_parts"]if census["part_roles"][x]=="epochs"}
        need(set(item["all_parts"])==epoch_parts and len(item["all_parts"])==len(epoch_parts)and item["first_part"]in epoch_parts,"Exact complete selected FIF parts")
        planned={(person,x["visit"],x["run"],x["raw_sample"],x["epoch_selection"])for x in item["lineage_rows"]}
        need(len(planned)==len(item["lineage_rows"])and planned=={k for k in census_index["expected_retained"]if k[0]==person},"Exact original retained epoch universe before native reader")
        # Qualified sandbox must mount exactly this inventoried source union; MNE
        # implicit reads outside it are an unresolved native capability gate.
        epochs=mne.read_epochs(Path(source_root)/item["first_part"],preload=False,proj=False,verbose="ERROR")
        need(len(epochs)==len(item["lineage_rows"]),"Complete externally proven event/epoch lineage")
        for n,lineage in enumerate(item["lineage_rows"]):
            need(int(epochs.selection[n])==lineage["epoch_selection"] and
                 int(epochs.events[n,2])==lineage["onset_trigger"],"Native original selection/onset joins")
            metadata=epochs.metadata.iloc[n]
            for k in ("Stim_trigger","Category","Orientation","Duration","Task_relevance","Response"):
                value=metadata[k]
                if hasattr(value,"item"):value=value.item()
                if k=="Response"and type(value)is str:
                    need(value in ("True","False"),"Literal source boolean");value=value=="True"
                need(value==lineage["metadata"][k],"Native metadata and original event join")
            row={**lineage,"source_person":person,"native_sample":int(epochs.events[n,0]),"channels":list(CHANNELS),
                 "channel_types":epochs.get_channel_types(picks=list(CHANNELS)),
                 "bads":list(epochs.info["bads"]),"times":epochs.times.tolist(),
                 "values":epochs[n:n+1].get_data(picks=list(CHANNELS),copy=True)[0].tolist()}
            validate_observed(row,census_index)
            yield validate_epoch_lineage(row,member,cohort["source_version"])
