"""Selected future prepared-output transformation; no native/scientific replay."""
from collections import Counter
import hashlib
import os
from pathlib import Path
import resource
import secrets
import sys

import census_core
import participant_core as core
import released_profile as profile
import grader
import json_interface
import native_io

MAX_JSON_RECORD = 2*1024*1024+4096
MAX_DOCUMENT = 128*1024*1024
EXPECTED_CONSERVATION = {
    "diagnostics": 10822,
    "status_trials": {"COMPATIBLE_CONDITIONAL_COMMAND_MODEL_NOT_PHYSICAL_DELIVERY":9931,"UNRESOLVED":900},
    "status_rows": {"COMPATIBLE_CONDITIONAL_COMMAND_MODEL_NOT_PHYSICAL_DELIVERY":87266,"UNRESOLVED":7806},
    "old_flags": {"COMMAND_AMPLITUDE_NOT_EXACT_SOURCE_ZERO_OR_100":44754,"COMMAND_RUN_NOT_ONE_50_SAMPLE_PULSE":3150},
}


def records(pin,budget,observations,maximum=MAX_JSON_RECORD):
    """Complete pinned file, prehash/parse/posthash, exact finite JSON lines."""
    reader=native_io.MeteredReader(pin["path"],pin["bytes"],budget)
    count=0;before=after=None
    try:
        before=native_io.full_digest(reader)
        if before["bytes"]!=pin["bytes"] or before["sha256"]!=pin["sha256"]:
            raise ValueError("whole prepared input pin")
        reader.seek(0);pending=b""
        while reader.tell()<reader.size:
            budget.check();chunk=reader.read(min(65536,reader.size-reader.tell()))
            if not chunk:raise ValueError("complete prepared input EOF")
            pending+=chunk
            while b"\n" in pending:
                line,pending=pending.split(b"\n",1)
                if not line or len(line)+1>maximum:raise ValueError("complete ordinary JSON record")
                value=json_interface.decode(line,maximum)
                if type(value) is not dict:raise ValueError("complete object record")
                if core.canonical(value)!=line+b"\n":raise ValueError("canonical reviewed prepared record")
                budget.charge("json_record_bytes",len(line)+1)
                count+=1
                yield value
            if len(pending)>=maximum:raise ValueError("whole record bound; no truncation")
        if pending:raise ValueError("missing final newline")
    finally:
        try:
            after=native_io.full_digest(reader)
            if after["bytes"]!=pin["bytes"] or after["sha256"]!=pin["sha256"]:
                raise ValueError("complete prepared postflight identity")
            identity=reader.identity()
        finally:reader.close()
        observations.append({"path":pin["path"],"before":before,"after":after,"identity":identity,
                             "closed":reader.closed,"records":count})


def bounded_document(store,name,value):
    # Existing metered writer registers output intent and precharges before write.
    with store.line_writer(name) as writer:writer.write(value,maximum=MAX_DOCUMENT)


def prepare(cfg,budget,store,secret=None):
    """All rows/trials/sessions; no fit, source cohort reduction or model access."""
    observations=[]
    diagnostics={}
    for record in records(cfg["prepared_inputs"]["diagnostics"],budget,observations):
        core.exact_keys(record,("diagnostic_sha256","command_multiplicity_owner_only"))
        d=record["command_multiplicity_owner_only"];key=record["diagnostic_sha256"]
        if census_core.fingerprint(d)["sha256"]!=key or key in diagnostics:
            raise ValueError("complete unique typed command diagnostic")
        if d["status"] not in ("COMPATIBLE_CONDITIONAL_COMMAND_MODEL_NOT_PHYSICAL_DELIVERY","UNRESOLVED"):
            raise ValueError("all unresolved branches retained")
        diagnostics[key]=d["status"]
        if len(diagnostics)>EXPECTED_CONSERVATION["diagnostics"]:raise ValueError("whole diagnostic dictionary scope")
    if len(diagnostics)!=EXPECTED_CONSERVATION["diagnostics"]:raise ValueError("all reviewed diagnostics required")
    rows=records(cfg["prepared_inputs"]["rows"],budget,observations,maximum=8192)
    try:
        prepared=core.assemble_prepared_trials(rows,core.FULL_SCOPE)
    finally:
        rows.close()
    # Generator normally reaches its end inside assembly; explicitly close on
    # exceptional consumers as well. Caller failure remains authoritative.
    status_trials=Counter();status_rows=Counter();used=set();old_flags=Counter()
    for trial in prepared["trials"]:
        budget.check()
        key=trial["diagnostic_reference_owner_only"]["diagnostic_sha256"]
        if key not in diagnostics:raise ValueError("complete trial dictionary join")
        status=diagnostics[key];used.add(key);status_trials[status]+=1
        status_rows[status]+=len(trial["source_rows"])
        trial["diagnostic_reference_owner_only"]["status_owner_only"]=status
        for flags in trial["old_flags_by_unit"].values():old_flags.update(flags)
        if (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024))>cfg["observed_rss_soft_stop_bytes"]:
            raise ValueError("observed process RSS soft stop")
    if used!=set(diagnostics):raise ValueError("every reviewed diagnostic referenced")
    if (status_trials!=EXPECTED_CONSERVATION["status_trials"]
            or status_rows!=EXPECTED_CONSERVATION["status_rows"]
            or old_flags!=EXPECTED_CONSERVATION["old_flags"]):
        raise ValueError("complete reviewed status/old-flag conservation")
    key=secrets.token_bytes(32) if secret is None else secret
    if type(key) is not bytes or len(key)!=32:raise ValueError("owner-only pseudonym key")
    store.json("OWNER_PSEUDONYM_KEY.json",{"key_hex":key.hex(),"candidate_readable":False})
    packets={};owners={};readiness={}
    for condition in core.CONDITIONS:
        budget.check()
        public,owner=profile.from_accepted_preparation(prepared,profile.BOUND_SOURCE,key,condition)
        grader.validate_owner(owner)
        # Exact per-record whole bounds plus complete document bounds. No split
        # or renaming of a refused ordinary data record is permitted.
        for d in owner["all_trial_dispositions"]:
            if len(core.canonical(d))>8192:raise ValueError("whole owner disposition bound")
        for c in owner["cases"]:
            if len(core.canonical(c))>1024:raise ValueError("whole owner target-case bound")
        pbytes=core.canonical(public);obytes=core.canonical(owner)
        if len(pbytes)>MAX_DOCUMENT or len(obytes)>MAX_DOCUMENT:
            raise ValueError("whole profile document bound")
        upper=condition.upper()
        bounded_document(store,"PARTICIPANT_"+upper+".json",public)
        bounded_document(store,"OWNER_"+upper+".json",owner)
        packets[condition]={"bytes":len(pbytes),"sha256":hashlib.sha256(pbytes).hexdigest()}
        owners[condition]={"bytes":len(obytes),"sha256":hashlib.sha256(obytes).hexdigest()}
        readiness[condition]={"sessions":len(public["sessions"]),"required_queries":len(owner["cases"]),
            "all_trial_dispositions":len(owner["all_trial_dispositions"]),
            "per_session_serialized_bytes":[{"session_id":s["session_id"],"bytes":len(core.canonical(s)),
                "units":len(s["channel_ids"]),"calibration":len(s["calibration"]),
                "development":len(s["development"]),"queries":len(s["queries"])} for s in public["sessions"]],
            "native_model_context_fit_verified":False,"candidate_process_isolation_established":False}
        if (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024))>cfg["observed_rss_soft_stop_bytes"]:
            raise ValueError("observed process RSS soft stop")
    result={"status":"COMPLETE_DEPOSITED_LABEL_PROFILE_PREPARATION_ONLY","profile":profile.PROFILE,
            "scope":dict(core.FULL_SCOPE),"source_binding":dict(profile.BOUND_SOURCE),
            "all_seven_physical_primary_holds":list(core.HOLDS),"physical_primary_status":"HELD",
            "status_trials":dict(status_trials),"status_rows":dict(status_rows),"old_flags":dict(old_flags),
            "packet_pins":packets,"owner_document_pins":owners,"readiness":readiness,
            "source_observations":observations,"models":0,"fits":0,
            "scientific_qualification":False,"benchmark_count_delta":0}
    store.json("PROFILE_PREPARATION.json",result)
    return result
