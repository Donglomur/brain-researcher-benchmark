"""Separate deposited-label profile; never replaces the physical-event primary.

Target is the immutable deposited integer Total_pulse label. Official compiler
describes an integrated full-vector command-area quantity, but compiler-to-deposit
execution lineage and equivalence to physical delivery remain unproven.
No data access, fits or candidate execution occur on import.
"""
import hashlib
import math

import participant_core as core

PROFILE = "apcx-deposited-total-pulse-within-session-v1"
PROFILE_CONTRACT_SHA256 = "f7338d33fc67d7bc231e1bba7344f30f9c70ce5362f169998dc2b4302c042d0b"
SPLIT_SEED = "apcx-deposited-total-pulse-all43-trial-hash-20261114-v1"
DOCUMENTATION = {
    **core.DOCUMENTATION,
    "schema": "apcx-deposited-label-common-document-v1",
    "profile": PROFILE,
    "endpoint": "Predict the deposited Total_pulse integer label; compiler-described command-area quantity, not verified physical delivery or perception.",
    "target_boundary": "Count target is the deposited label. Optional category is the literal label-derived indicator Total_pulse>=9, not a newly authenticated stimulus category.",
    "split": "Seeded target-blind hash permutation of complete released trial identities within each session: floor(0.60*n) calibration, floor(0.20*n) development, remainder protected.",
    "split_seed": "apcx-deposited-total-pulse-all43-trial-hash-20261114-v1",
    "split_encoding": "SHA256(seed UTF8 plus zero byte plus canonical newline-terminated JSON [Animal,Session,Trial]); tie by exact integer trial identity.",
    "matched_support": "First16 calibration and first8 development trials in the frozen hash order, not original chronology.",
    "signal": "90 half-open50ms spike-count bins for every deposited unit in the session; historical unit selection and preprocessing are part of the conditional estimand.",
    "zero_semantics": "Zero means no event listed in the released representation falls in that bin; original recording validity and missing or discarded spikes are not independently established.",
    "population": "Conditional interpolation within all43 deposited sessions from3 recorded mice. No original-chronology, novel-session, new-mouse, prospective all-QC or physical-delivery generalization.",
    "ascertainment": "Historically selected units and filtered/renumbered trials; unknown original exclusions, spike padding/cap and compiler-to-deposit lineage remain limitations.",
    "unresolved_commands": "All900 command-model-unresolved trials remain eligible. Conditional command reconstruction never supplies labels or filters.",
    "privacy": "Prepared source, target stores, identities, command diagnostics and unselected support are owner-only; target-free query packet is an evidence boundary, not a process sandbox.",
    "uncertainty": "Report all3 animal and43 session values. Paired within-session heldout-trial bootstrap conditional on this release; no independent-neuron/bin resampling or population confidence claim.",
    "secondary_numerical_rules": "Optional complete probability column: threshold0.5, log-loss probability floor1e-15; single-class balanced accuracy and constant-target R2 are explicitly undefined. Optional paired1000-draw within-session trial bootstrap uses seed541731 and is an exchangeability sensitivity, not a population CI.",
}
BOUND_SOURCE = {
    "profile_contract_sha256": PROFILE_CONTRACT_SHA256,
    "canonical_entity_sha256": "83193081d7486e95590f1599cc20943f702d05d2d1ccf4f124038a5f86598598",
    "rows_sha256": core.ACCEPTED_ROWS_SHA256,
    "review_sha256": core.ACCEPTED_REVIEW_SHA256,
    "profile": PROFILE,
}
ACTIVE_STATUS = {
    "source_construction_only": True,
    "authentic_packet_materialized": False,
    "protected_run_selected": False,
    "original_physical_primary": "HELD",
    "remaining_physical_primary_holds": list(core.HOLDS),
    "scientific_qualification": False,
    "benchmark_count_delta": 0,
}


def split_rank(animal, session, trial):
    """No target, command, correctness, neuronal response or difficulty argument."""
    identity = [core.nonempty(animal), core.nonempty(session), core.integer(trial)]
    return hashlib.sha256(SPLIT_SEED.encode() + b"\0" + core.canonical(identity)).hexdigest()


def _pack(trials, secret, condition, documentation, invented):
    if condition not in core.CONDITIONS or not trials:
        raise ValueError("closed complete profile condition")
    sessions = {}; identities = set()
    for t in trials:
        core.exact_keys(t, ("animal", "session", "trial", "target", "spikes", "units", "old_flags_owner_only", "diagnostic_reference_owner_only"))
        a,s,tid = core.nonempty(t["animal"]),core.nonempty(t["session"]),core.integer(t["trial"])
        key=(a,s,tid)
        if key in identities: raise ValueError("duplicate whole trial identity")
        identities.add(key);core.integer(t["target"]);core.signal_matrix(t["spikes"])
        units=t["units"]
        if type(units) is not list or len(units)!=len(t["spikes"]) or len(set(units))!=len(units):
            raise ValueError("complete unit basis")
        for u in units:core.integer(u)
        sessions.setdefault((a,s),[]).append(t)
    if len({x[0] for x in sessions})!=3: raise ValueError("all3 recorded animals required")
    doc=core.canonical(documentation).decode()
    public={"schema":"apcx-deposited-label-participant-v1","profile":PROFILE,"condition":condition,
            "profile_contract_sha256":PROFILE_CONTRACT_SHA256,
            "documentation_utf8":doc,"documentation_sha256":hashlib.sha256(doc.encode()).hexdigest(),
            "sessions":[],"invented":invented}
    owner={"schema":"apcx-deposited-label-owner-v1","profile":PROFILE,"target_kind":"deposited_Total_pulse_label",
           "profile_contract_sha256":PROFILE_CONTRACT_SHA256,
           "profile_document_sha256":core.digest(DOCUMENTATION),
           "invented":invented,"cases":[],"sessions":{},"all_trial_dispositions":[],
           "physical_delivery_verified":False,"remaining_physical_primary_holds":list(core.HOLDS),
           "historical_selection_caveat_required":True,"scientific_qualification":False}
    for (animal,session),ts in sorted(sessions.items()):
        ordered=sorted(ts,key=lambda t:(split_rank(animal,session,t["trial"]),t["trial"]))
        units=ordered[0]["units"]
        if any(t["units"]!=units for t in ordered):raise ValueError("changing unit basis")
        n=len(ordered);nc=3*n//5;nd=n//5;nt=n-nc-nd
        if nc<16 or nd<8 or nt<10:raise ValueError("complete support quota; no dropped session")
        sid=core.opaque(secret,"session",[animal,session])
        pkt={"session_id":sid,"channel_ids":[core.opaque(secret,"unit",[animal,session,u]) for u in units],
             "calibration":[],"development":[],"queries":[]}
        owner["sessions"][sid]={"animal":animal,"n_calibration":nc,"n_development":nd,"n_test":nt,
            "units":len(units),"test_case_order":[],
            "bootstrap_unit":"whole released trial within fixed recorded session",
            "chronology_authenticated":False}
        for rank,t in enumerate(ordered):
            cid=core.opaque(secret,"trial",[animal,session,t["trial"]])
            split="calibration" if rank<nc else "development" if rank<nc+nd else "test"
            exposed=(split=="test" or condition=="full_calibration" or
                     (split=="calibration" and rank<16) or
                     (split=="development" and rank-nc<8))
            owner["all_trial_dispositions"].append({"case_id":cid,"session_id":sid,"split":split,
                "support_exposed":exposed if split!="test" else False,
                "required_query":split=="test","source_identity_owner_only":[animal,session,t["trial"]],
                "deposited_target_owner_only":t["target"],
                "old_flags_owner_only":t["old_flags_owner_only"],
                "diagnostic_reference_owner_only":t["diagnostic_reference_owner_only"]})
            case={"case_id":cid,"spikes":[list(x) for x in t["spikes"]]}
            if split=="test":
                pkt["queries"].append(case)
                owner["cases"].append({"case_id":cid,"session_id":sid,"animal":animal,
                    "count":t["target"],"high":int(t["target"]>=9),"split_rank":rank})
                owner["sessions"][sid]["test_case_order"].append(cid)
            elif exposed:
                case.update(count=t["target"],high=int(t["target"]>=9))
                pkt[split].append(case)
        for field in ("calibration","development","queries"):pkt[field].sort(key=lambda x:x["case_id"])
        public["sessions"].append(pkt)
    public["sessions"].sort(key=lambda x:x["session_id"])
    owner["cases"].sort(key=lambda x:x["case_id"])
    owner["all_trial_dispositions"].sort(key=lambda x:x["case_id"])
    owner["input_trial_count"]=len(trials)
    owner["required_query_count"]=len(owner["cases"])
    owner["condition"]=condition
    owner["participant_packet_sha256"]=core.digest(public)
    owner["split_manifest_sha256"]=core.digest([{k:d[k] for k in
        ("case_id","session_id","split","support_exposed","required_query")}
        for d in owner["all_trial_dispositions"]])
    owner["target_manifest_sha256"]=core.digest(owner["cases"])
    audit_public(public)
    return public,owner


def from_accepted_preparation(prepared, source_binding, secret, condition="matched"):
    """Future complete prepared-output consumption, not native replay.

    A trusted owner must hash the complete prepared input before calling this pure
    transformation. Exact binding is a check, not an independent filesystem audit.
    No candidate can provide source_binding through a participant-facing interface.
    """
    if source_binding!=BOUND_SOURCE:raise ValueError("exact accepted prepared-source binding")
    if (type(prepared) is not dict or prepared.get("observed_scope")!=core.FULL_SCOPE
            or prepared.get("candidate_export") is not False
            or prepared.get("physical_truth_authenticated") is not False
            or prepared.get("original_chronology_authenticated") is not False
            or prepared.get("all_qc_roster_authenticated") is not False
            or prepared.get("remaining_holds")!=list(core.HOLDS)):
        raise ValueError("complete held preparation required")
    trials=[]
    for t in prepared["trials"]:
        if (t["physical_count"] is not None or t["original_chronology"] is not None
                or t["all_qc_roster_authenticated"] is not False or t["scientific_holds"]!=list(core.HOLDS)):
            raise ValueError("no physical/chronology/QC promotion")
        trials.append({"animal":t["animal"],"session":t["session"],"trial":t["released_trial"],
            "target":t["observed_released_labels_owner_only"]["Total_pulse"],
            "spikes":t["spikes_by_unit_90_bins"],"units":t["released_unit_ids_owner_only"],
            "old_flags_owner_only":t["old_flags_by_unit"],
            "diagnostic_reference_owner_only":t["diagnostic_reference_owner_only"]})
    if len(trials)!=core.FULL_SCOPE["trials"]:raise ValueError("all reviewed trial identities required")
    public,owner=_pack(trials,secret,condition,DOCUMENTATION,False)
    if len(public["sessions"])!=core.FULL_SCOPE["sessions"]:raise ValueError("all reviewed sessions required")
    owner["accepted_source_binding"]=dict(source_binding)
    owner["original_scope"]=dict(core.FULL_SCOPE)
    return public,owner


def invented_packet(trials, secret, condition="matched"):
    """Only invented names enter the engineering integration path."""
    if any(not t["animal"].startswith("INVENTED_ANIMAL_") or
           not t["session"].startswith("INVENTED_SESSION_") for t in trials):
        raise core.ScientificHold("fixture route cannot accept actual source identities")
    return _pack(trials,secret,condition,DOCUMENTATION,True)


def audit_public(packet):
    core.exact_keys(packet,("schema","profile","profile_contract_sha256","condition","documentation_utf8","documentation_sha256","sessions","invented"))
    if (packet["schema"]!="apcx-deposited-label-participant-v1" or packet["profile"]!=PROFILE
            or packet["profile_contract_sha256"]!=PROFILE_CONTRACT_SHA256
            or type(packet["invented"]) is not bool or packet["condition"] not in core.CONDITIONS
            or packet["documentation_utf8"]!=core.canonical(DOCUMENTATION).decode()
            or hashlib.sha256(packet["documentation_utf8"].encode()).hexdigest()!=packet["documentation_sha256"]):
        raise ValueError("exact profile and byte-identical common documentation")
    if not packet["invented"] and len(packet["sessions"]) != core.FULL_SCOPE["sessions"]:
        raise ValueError("all43 released sessions in actual profile")
    return core.audit_signal_sessions(packet["sessions"],packet["condition"])


def prior(packet):
    audit_public(packet);out=[]
    for s in packet["sessions"]:
        train=s["calibration"]
        mean=math.fsum(x["count"]/len(train) for x in train)
        probability=sum(x["high"] for x in train)/len(train)
        out.extend({"case_id":x["case_id"],"count":mean,"prob_high":probability} for x in s["queries"])
    return out


def submission(packet, records):
    audit_public(packet)
    return {"schema":"apcx-deposited-label-submission-v1", "profile":PROFILE,
        "profile_contract_sha256":PROFILE_CONTRACT_SHA256,
        "profile_document_sha256":core.digest(DOCUMENTATION), "condition":packet["condition"],
        "participant_packet_sha256":core.digest(packet), "records":records}
