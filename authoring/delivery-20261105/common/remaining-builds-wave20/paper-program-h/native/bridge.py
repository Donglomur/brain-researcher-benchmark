"""Private source-only H native transport/validation. Nothing runs on import.

This module never launches MATLAB, imports author loaders, fits or scores.
The operator's concrete isolated provider owns command execution, admission,
original clocks, custody, capacities and final OUTPUTS.json transport envelope.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct

TASK = "PAPER-FIND-ADD-003"
VARIANTS = ("source_preprocessing", "no_smoothing_no_flooring")
DAYS = ("standard_minus2", "standard_minus1", "reversal1", "reversal2")
CONDITIONS = ("standcuedshort", "standcuedlong", "revcuedshort", "revcuedlong")
BEHAVIOR = tuple("CD" + str(x) for x in (183,184,185,186,187,188,189,190,191,192,193,194,217,218,219,220,221,242,243,244,245,246,247))
IMAGING = BEHAVIOR[12:]
ORIGINALS = (
    ("all23behavior.mat", 29054400, "321192109e2ea9ec9e8095799aadcbf6f8d209be119d4c999dd1b110c3cbbce7"),
    ("rawtrialsstand2torev2_n11.mat", 10720299345, "2ddee31087cd4ee4d6b133e02e05432a27d5fa5ee5beb81915fae65416b69f61"),
    ("rawtrialsstand2torev2_nosmoothnoflooring_n11.mat", 12292854614, "2bf684b9416299e50dfe5c057392444ecc90c9fa6e49fe9fb7a98d1e850f3475"),
)
SOURCE_PINS = {
    "reference_sources/reference_behavior.m": (5852, "3c2e71bc596a0fb2572061ceddfcb6551002a749543298458824aec072c0ded9"),
    "reference_sources/reference_sequence.m": (11122, "e50b1c6daaf91ff9bfcc9b70645062f3253473055dd07a44a3186c752c7ff0ff"),
    "reference_sources/reference_time.m": (7398, "e8646e51fa9a10d76f6d5bed9cdcc057af8fe9dde0339e61073252449787c1c3"),
    "reference_sources/reference_odor.m": (13917, "b2f74d67cf806a759e2cf301af00cec488b97d28049b132a462585fc155be419"),
    "reference_sources/reference_information.m": (9603, "9887f33672340fe62a178cfb78ccf93a9ff1ca34609ca6bd7739e805329c9aaa"),
    "export_values.m": (5054, "cd062529d9a53c60426a8c97369e13e639484dbc45fb420333911f1f7810628e"),
}
FAMILIES = {
    "behavior_accuracy": (23,16,"fraction"), "behavior_lick_latency": (23,16,"seconds"),
    "sequence_peak_fraction": (11,14,"fraction"), "sequence_index": (11,16,"dimensionless"),
    "time_bin_correlation": (11,16,"correlation"), "time_confusion": (11,784,"fraction"),
    "odor_accuracy": (11,1096,"fraction"), "odor_information": (11,592,"bits_per_cell"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "duplicate JSON key: " + k)
        result[k] = v
    return result


def _finite_float(token):
    value=float(token)
    require(math.isfinite(value),"JSON floating-point overflow")
    return value


def load_json(path, max_bytes=268435456):
    p = Path(path)
    require(p.is_file() and not p.is_symlink(), "regular JSON file required")
    require(p.stat().st_size <= max_bytes, "JSON exceeds admitted parser extent")
    return json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=_pairs,parse_float=_finite_float,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonstandard JSON: " + x)))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1048576):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    """Exclusive, checked strict JSON; an interrupted partial file is retained."""
    data = (json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    with Path(path).open("xb") as stream:
        require(stream.write(data) == len(data), "short JSON write")
        stream.flush()
    return {"path": Path(path).name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def command(operation):
    require(operation in ("prepare", "reference", "fit"), "unknown fixed native entrypoint")
    return ["/opt/matlab/bin/matlab", "-batch", "addpath('/bridge');h_" + operation + "('/job/REQUEST.json')"]


def verify_inputs(request, original_root="/originals", author_root="/author"):
    """Future full-byte authentication, never a substitute for custody admission."""
    require(request.get("schema") == "h_native_request_v2", "request schema")
    require(request.get("operation") in ("prepare", "reference"), "original-consuming operation")
    require(request.get("output_root") == "/output", "fixed output mount")
    expected = [{"filename": n, "path": str(Path(original_root) / n), "bytes": size, "sha256": pin}
                for n, size, pin in ORIGINALS]
    require(request.get("originals") == expected, "exact three selected original declarations")
    if "original_paths" in request:
        require(request["original_paths"] == [x["path"] for x in expected], "original_paths disagree")
    logical_reads = 0
    for item in expected:
        p = Path(item["path"])
        require(p.is_file() and not p.is_symlink() and p.stat().st_size == item["bytes"], "original extent/type mismatch")
        require(sha256(p) == item["sha256"], "original SHA256 mismatch")
        logical_reads += item["bytes"]
    for relative, (size, pin) in SOURCE_PINS.items():
        p = Path(author_root) / relative
        require(p.is_file() and not p.is_symlink() and p.stat().st_size == size, "source extent/type mismatch")
        require(sha256(p) == pin, "source SHA256 mismatch: " + relative)
        logical_reads += size
    return {"schema": "h_input_byte_authentication_v2", "originals": expected,
            "source_pins": SOURCE_PINS, "logical_bytes_read": logical_reads,
            "custody_identity_runtime_and_original_clock_admission": "external_required",
            "scientific_qualification": False}


def safe_path(root, relative):
    require(type(relative) is str and relative and not Path(relative).is_absolute(), "relative artifact path required")
    require(all(x not in ("", ".", "..") for x in relative.split("/")), "noncanonical artifact path")
    root = Path(root).resolve()
    p = root.joinpath(relative)
    require(p.resolve().is_relative_to(root), "artifact escaped private root")
    require(p.is_file() and not p.is_symlink(), "regular inert artifact required")
    cursor = p.parent
    while cursor != root:
        require(not cursor.is_symlink(), "symlink in artifact path")
        cursor = cursor.parent
    return p


def npy_header(path):
    with Path(path).open("rb") as stream:
        require(stream.read(8) == b"\x93NUMPY\x01\x00", "only inert NPY v1 is admitted")
        b = stream.read(2); require(len(b) == 2, "truncated NPY length")
        size = struct.unpack("<H", b)[0]
        require(1 <= size <= 4096, "bounded NPY header")
        header = stream.read(size); require(len(header) == size and header.endswith(b"\n"), "truncated NPY header")
    h = ast.literal_eval(header.decode("ascii"))
    require(type(h) is dict and set(h) == {"descr", "fortran_order", "shape"}, "inert NPY header keys")
    require(h["descr"] in ("<f8", "|u1", "<i8") and type(h["fortran_order"]) is bool, "inert NPY type/order")
    require(type(h["shape"]) is tuple and 0 <= len(h["shape"]) <= 8 and
            all(type(x) is int and x >= 0 for x in h["shape"]), "inert NPY dimensions")
    width = 1 if h["descr"] == "|u1" else 8
    require(Path(path).stat().st_size == 10 + size + math.prod(h["shape"]) * width, "NPY exact extent")
    return h, 10 + size


def check_descriptor(root, descriptor, seen):
    require(type(descriptor) is dict, "typed array descriptor")
    required = {"path", "dtype", "shape", "fortran_order", "bytes", "sha256"}
    require(required <= descriptor.keys(), "missing array descriptor fields")
    require(descriptor["fortran_order"] is True and type(descriptor["shape"]) is list,"preparation source orientation and typed shape")
    path = safe_path(root, descriptor["path"])
    require(descriptor["path"] not in seen, "array reused under different source roles")
    seen.add(descriptor["path"])
    header, _ = npy_header(path)
    require(header == {"descr": descriptor["dtype"], "fortran_order": descriptor["fortran_order"],
                       "shape": tuple(descriptor["shape"])}, "array header/descriptor mismatch")
    require(path.stat().st_size == descriptor["bytes"] and sha256(path) == descriptor["sha256"], "array extent/pin mismatch")
    if "nan_mask" in descriptor:
        mask = descriptor["nan_mask"]
        require(mask["dtype"] == "|u1" and mask["shape"] == descriptor["shape"], "complete same-shape missing mask")
        check_descriptor(root, mask, seen)


def descriptors(value):
    if type(value) is dict:
        if {"path", "dtype", "shape", "fortran_order", "bytes", "sha256"} <= value.keys():
            yield value
        else:
            for item in value.values(): yield from descriptors(item)
    elif type(value) is list:
        for item in value: yield from descriptors(item)


def small_array(root, descriptor, limit=1000000):
    """Only bounded ordinal, mask, label, clock and metadata arrays; no loaders."""
    p = safe_path(root, descriptor["path"]); h, offset = npy_header(p)
    count = math.prod(h["shape"]); require(count <= limit, "small-array reader extent")
    with p.open("rb") as stream:
        stream.seek(offset); body = stream.read()
    code = {"<f8": "d", "<i8": "q", "|u1": "B"}[h["descr"]]
    return list(struct.unpack("<" + str(count) + code, body))


def _identity_gate(root, preparation, evidence, expected_evidence_sha256, evidence_path):
    require(sha256(evidence_path) == expected_evidence_sha256, "identity evidence not bound to trusted admission pin")
    require(evidence.get("schema") == "h_identity_alignment_v2", "identity evidence schema")
    require(evidence.get("original_sha256") == [x[2] for x in ORIGINALS], "identity evidence original binding")
    require(type(evidence.get("independent_review_receipt_sha256")) is str and
            len(evidence["independent_review_receipt_sha256"]) == 64, "independent identity review receipt required")
    require(evidence.get("authority") == "independent_original_identity_review", "independent identity review authority")
    rows = preparation["behavior_sessions"] + preparation["imaging_sessions"]
    joins = evidence.get("sessions")
    require(type(joins) is list and len(joins) == 180, "all 92 behavior and 88 imaging mappings")
    index = {}
    for j in joins:
        key = (j["original_ordinal"],j["animal_source_ordinal"],j["daytype_source_ordinal"],j["source_day_ordinal"])
        require(key not in index, "duplicate authentic identity mapping"); index[key] = j
    used = set(); by_day = {}
    for r in rows:
        key = tuple(r[k] for k in ("original_ordinal","animal_source_ordinal","daytype_source_ordinal","source_day_ordinal"))
        require(key in index, "missing source-ordinal identity mapping"); j = index[key]; used.add(key)
        roster = BEHAVIOR if r["cohort"] == "behavior" else IMAGING
        require(j["animal_id"] == roster[r["animal_ordinal"]] and j["day"] == r["day"], "authentic identity differs from full selected source roster")
        require(type(j["session_id"]) is str and j["session_id"] and type(j["source_evidence_sha256"]) is str and len(j["source_evidence_sha256"]) == 64, "session evidence and identity required")
        require(type(j["trial_ids"]) is list and len(j["trial_ids"]) == 140 and len(set(j["trial_ids"])) == 140 and all(type(x) is str and x for x in j["trial_ids"]), "authentic full ordered trial identities required")
        require(j.get("clock_membership_authenticated") is True and j.get("acquisition_chunks_authenticated") is True, "clock and 20-trial source chunks unresolved")
        require(j.get("first_odor_offset_seconds") == 1 and j.get("first_odor_offset_verified") is True and
                j.get("second_odor_onset_verified") is True, "authenticated odor clock evidence required")
        daykey = (j["animal_id"],j["day"])
        if daykey in by_day:
            previous = by_day[daykey]
            require((previous["session_id"], previous["trial_ids"]) == (j["session_id"],j["trial_ids"]), "behavior/imaging/variant trial identity mismatch")
        else: by_day[daykey] = j
        if r["cohort"] == "imaging":
            nr = r["arrays"]["spks"]["shape"][0]
            require(type(j.get("roi_ids")) is list and len(j["roi_ids"]) == nr and len(set(j["roi_ids"])) == nr and all(type(x) is str and x for x in j["roi_ids"]), "authentic complete original ROI identities required")
    require(used == set(index), "unconsumed or substituted identity mapping")
    for i in range(44):
        a,b = preparation["imaging_sessions"][i], preparation["imaging_sessions"][i+44]
        ka=tuple(a[k] for k in ("original_ordinal","animal_source_ordinal","daytype_source_ordinal","source_day_ordinal"))
        kb=tuple(b[k] for k in ("original_ordinal","animal_source_ordinal","daytype_source_ordinal","source_day_ordinal"))
        require(index[ka]["roi_ids"] == index[kb]["roi_ids"], "variant ROI identities/order differ; no intersection allowed")
    return {"status": "trusted_identity_document_bound", "sha256": expected_evidence_sha256,
            "independent_review_receipt_sha256": evidence["independent_review_receipt_sha256"],
            "admission_authority": "provider_must_authenticate_review_receipt_and_clock"}


def validate_preparation(root, identity_path=None, identity_sha256=None):
    root = Path(root); p = load_json(root / "preparation.json")
    require(p.get("schema") == "h_preparation_v2", "preparation schema")
    expected = [{"filename": n, "path": "/originals/" + n, "bytes": size, "sha256": pin} for n,size,pin in ORIGINALS]
    require(p.get("originals") == expected, "preparation selected-original binding")
    require(len(p["behavior_sessions"]) == 92 and len(p["imaging_sessions"]) == 88, "full preparation row roster")
    failures = []; seen = set()
    for cohort, rows, count in (("behavior",p["behavior_sessions"],23),("imaging",p["imaging_sessions"],22)):
        for k, r in enumerate(rows):
            if r.get("status") != "exported": failures.append({"cohort":cohort,"ordinal":k+1,"reason":"source_row_not_exported"});continue
            a = (k//4) % (23 if cohort == "behavior" else 11)
            require(r["cohort"] == cohort and r["ordinal"] == k+1 and r["animal_ordinal"] == a and r["day"] == DAYS[k%4], "exact source session ordering")
            require(r["animal_source_ordinal"] == a+1 and r["daytype_source_ordinal"] == (k%4)//2+1 and r["within_selected_day_ordinal"] == k%2+1, "source ordinals disagree")
            require(type(r["source_day_ordinal"]) is int and r["source_day_ordinal"] >= 1, "source day ordinal")
            if cohort == "imaging":
                require(r["variant"] == VARIANTS[k//44] and r["original_ordinal"] == k//44+2 and r["source_day_ordinal"] == k%2+1, "exact variant selected-day membership")
            else: require(r["original_ordinal"] == 1, "behavior original")
            arrays = r["arrays"]
            for name in ("beh","first_odor_B","trial_source_ordinal","acquisition_chunk_from_source_position","lick_events_seconds","lick_offsets","lick_chronological","lick_finite"):
                require(name in arrays, "missing complete behavior/nuisance role: " + name)
            require(arrays["beh"]["shape"] == [140,5] and arrays["first_odor_B"]["shape"] == [140,1] and arrays["lick_offsets"]["shape"] == [141,1], "full behavior/event geometry")
            for d in descriptors(arrays): check_descriptor(root,d,seen)
            require(small_array(root,arrays["trial_source_ordinal"]) == list(range(1,141)), "trial source order changed")
            require(small_array(root,arrays["acquisition_chunk_from_source_position"]) == [i//20+1 for i in range(140)], "20-trial positional chunks changed")
            offsets=small_array(root,arrays["lick_offsets"])
            require(offsets[0] == 0 and all(x<=y for x,y in zip(offsets,offsets[1:])) and offsets[-1] == math.prod(arrays["lick_events_seconds"]["shape"]), "ragged original lick support")
            codes=small_array(root,arrays["beh"])[0:140]
            require(all(x in (11,12,21,22,511,512,521,522) for x in codes), "first-odor codes")
            require(small_array(root,arrays["first_odor_B"]) == [int(x in (21,22,521,522)) for x in codes], "first-odor map mismatch")
            if cohort == "imaging":
                nr=arrays["spks"]["shape"][0]
                for name in ("F","Fneu","spks"): require(arrays[name]["shape"] == [nr,140,402], "all original ROIs/trials/frames required")
                for name in ("locomotion","xyoff"): require(arrays[name]["shape"] == [140,402], "full nuisance frame support")
                require(small_array(root,arrays["roi_source_ordinal"]) == list(range(1,nr+1)), "original ROI order changed")
                quality=small_array(root,arrays["iscell"])
                require(len(quality)==nr and all(math.isfinite(x) and 0<=x<=1 for x in quality), "full finite original iscell axis")
                require(small_array(root,arrays["eligible_mask"]) == [int(x>0.3) for x in quality], "exact iscell > 0.3 eligibility")
                require(arrays["roistats"]["kind"] == "cell" and math.prod(arrays["roistats"]["shape"]) == nr, "all original ROI metadata retained")
    require(len(p["variant_metadata"]) == 2, "both original variant clocks")
    for v, meta in enumerate(p["variant_metadata"]):
        if meta.get("status") != "exported": failures.append({"variant":VARIANTS[v],"reason":"variant_metadata_not_exported"});continue
        require(meta["variant"] == VARIANTS[v], "variant clock order")
        for d in descriptors(meta): check_descriptor(root,d,seen)
        t=small_array(root,meta["frametimes"])
        require(len(t)==402 and all(math.isfinite(x) for x in t) and all(x<y for x,y in zip(t,t[1:])), "finite strictly increasing original frame clock")
    identity={"status":"missing_authenticated_identity_document"}
    if not failures:
        # Numeric equality is a consistency check; the independent identity map
        # remains mandatory and cannot be replaced with these comparisons.
        for k in range(44):
            a,b=p["imaging_sessions"][k]["arrays"],p["imaging_sessions"][k+44]["arrays"]
            for name in ("iscell","eligible_mask","roi_source_ordinal","beh","lick_events_seconds","lick_offsets"):
                require(a[name]["shape"] == b[name]["shape"] and a[name]["sha256"] == b[name]["sha256"], "paired variant source support differs: "+name)
        require(p["variant_metadata"][0]["frametimes"]["sha256"] == p["variant_metadata"][1]["frametimes"]["sha256"], "variant clock mismatch")
        if identity_path is not None and identity_sha256 is not None:
            identity=_identity_gate(root,p,load_json(identity_path),identity_sha256,identity_path)
    admitted = None
    if not failures and identity["status"]=="trusted_identity_document_bound":
        for r in p["imaging_sessions"]:
            descriptor=p["variant_metadata"][VARIANTS.index(r["variant"])]["frametimes"]
            clock=small_array(root,descriptor)
            behavior=small_array(root,r["arrays"]["beh"])
            onsets=behavior[420:560]
            require(all(math.isfinite(x) for x in onsets),"complete source second-odor timing")
            left=(clock[93]+clock[94])/2;right=(clock[168]+clock[169])/2
            require(left>=1 and right<min(onsets),"entire current-window temporal cells must lie in the common delay")
            r["clock"]={"frametimes":descriptor,"common_delay_verified":True,
                        "first_odor_offset_verified":True,"second_odor_onset_verified":True,
                        "first_odor_offset_seconds":1,"identity_evidence_sha256":identity_sha256,
                        "evidence_basis":"independently_authenticated_clock_membership_plus_source_numeric_support"}
            r["identity_status"]="bound_to_independent_identity_document"
        p["status"]="structural_export_with_bound_identity_document"
        p["identity_status"]="bound_to_independent_identity_document"
        p["identity_admission"]=identity
        admitted=write_json(root/"admitted-preparation.json",p)
    return {"schema":"h_preparation_result_v2","task_id":TASK,"preparation_sha256":sha256(root/"preparation.json"),
            "status":"complete_structural_and_bound_identity" if not failures and identity["status"]=="trusted_identity_document_bound" else "incomplete",
            "structural_complete":not failures,"identity":identity,"failures":failures,"array_files_verified":len(seen),"admitted_preparation":admitted,
            "behavior_sessions":92,"imaging_sessions":44,"imaging_variant_sessions":88,"prospective_signal":"spks",
            "original_clock_runtime_custody_and_scientific_qualification":"external_required","scientific_qualification":False}


def elements(family):
    if family.startswith("behavior_"): return [d+"_"+c for d in DAYS for c in CONDITIONS]
    if family=="sequence_peak_fraction": return [c+"_bin"+str(b) for c in ("short","long") for b in range(1,8)]
    if family=="sequence_index": return [w+"_"+d+"_"+c for w in ("shortwindow","longwindow") for d in DAYS for c in ("short","long")]
    if family in ("time_bin_correlation","time_confusion"):
        base=[d+"_"+c+"_"+m for d in DAYS for c in ("short","long") for m in ("real","shuffled")]
        return base if family=="time_bin_correlation" else [x+"_pred"+str(p)+"_true"+str(t) for x in base for p in range(1,8) for t in range(1,8)]
    if family=="odor_information": return [d+"_"+c+"_bin"+str(b) for d in DAYS[2:] for c in CONDITIONS for b in range(7,81)]
    if family=="odor_accuracy":
        fields=[("bothstandard",DAYS,26),("bothstandardalignsecond",DAYS,33)]
        fields += [(x,DAYS[2:],26) for x in ("bothshort","bothlong","standshortmnm","standlongmnm","revcuedshortmnm","revcuedlongmnm")]
        return [f+"_"+d+"_"+m+"_bin"+str(b) for f,days,n in fields for d in days for m in ("real","shuffled") for b in range(1,n+1)]
    raise ValueError("unknown native family")


def call_roster():
    calls=[{"ordinal":1,"function":"reference_behavior","original_ordinal":1,"output":"behavior.mat","window":0,"rng_policy":"no_source_rng_reset"}]
    for v,variant in enumerate(VARIANTS):
        for fn,name,window in (("reference_sequence","sequence_short",169),("reference_sequence","sequence_long",247),("reference_time","time",0),("reference_odor","odor",0),("reference_information","information",0)):
            calls.append({"ordinal":len(calls)+1,"function":fn,"original_ordinal":v+2,"output":variant+"/"+name+".mat","window":window,"rng_policy":"source_rng_Default"})
    return calls


def recover_call_ledger(root):
    """Recover interruption dispositions from durable per-call records."""
    root=Path(root); final=root/"call-ledger.json"
    if final.is_file(): ledger=load_json(final)
    else:
        ledger={"schema":"h_native_call_ledger_v2","calls":[],"exporter":{"status":"unstarted","reason":"no_completed_exporter_record"}}
        for expected in call_roster():
            k=expected["ordinal"]; done=root/f"call-{k:02d}.json";started=root/f"call-{k:02d}.started.json"
            if done.is_file(): c=load_json(done)
            elif started.is_file(): c={**load_json(started),"status":"failed","error":{"identifier":"H:Interrupted","message":"Started native call has no durable completion record"}}
            else:c={**expected,"status":"unstarted"}
            ledger["calls"].append(c)
        if (root/"exporter.started.json").is_file(): ledger["exporter"]={"status":"failed","reason":"exporter_started_without_durable_completion"}
    require(ledger.get("schema")=="h_native_call_ledger_v2" and len(ledger["calls"])==11,"complete 11-call ledger required")
    for c,expected in zip(ledger["calls"],call_roster()):
        require(all(c.get(k)==v for k,v in expected.items()),"native source call/argument/RNG roster changed")
        require(c["status"] in ("completed","failed","unstarted"),"native call disposition")
        if c["status"]=="completed":
            p=safe_path(root,c["output"])
            require(p.stat().st_size==c["output_bytes"] and sha256(p)==c["output_sha256"],"native MAT output pin mismatch")
    return ledger


def native_dependency(variant_index,family,element_index):
    if family.startswith("behavior_"): return 1
    base=1+5*variant_index
    if family=="sequence_peak_fraction":return base+1
    if family=="sequence_index":return base+1+(element_index//8)
    if family.startswith("time_"):return base+3
    if family=="odor_accuracy":return base+4
    return base+5


def classify_value(family,element,value):
    structural=(family.startswith("behavior_") and element.startswith("standard_") and "_revcued" in element) or (
        family=="odor_accuracy" and element.startswith("bothstandardalignsecond_") and int(element.rsplit("bin",1)[1])<=7)
    if value is None:
        return ("structural_undefined","source_unpopulated_standard_reversal_condition_or_explicit_alignment_padding") if structural else (
            "computed_undefined","native_NaN_cause_requires_independent_scientific_audit")
    if type(value) not in (int,float) or not math.isfinite(value):return "failed","nonfinite_complex_or_nonnumeric_export"
    if structural:return "failed","finite_value_in_source_structural_undefined_slot"
    unit=FAMILIES[family][2]
    domain=(0<=value<=1 if unit=="fraction" else -1<=value<=1 if unit=="correlation" else 0<value<3 if unit=="seconds" else value>=0 if unit=="bits_per_cell" else True)
    return ("finite","native_computed_value") if domain else ("failed","native_value_outside_contract_domain")


def finalize_reference(root):
    root=Path(root);ledger_error=None
    try: ledger=recover_call_ledger(root)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        ledger_error={"type":type(exc).__name__,"message":str(exc)}
        ledger={"schema":"h_native_call_ledger_v2","calls":[{**c,"status":"failed","error":{"identifier":"H:LedgerAdmission","message":"Native ledger or artifact authentication failed"}} for c in call_roster()],
                "exporter":{"status":"failed","reason":"native_ledger_or_artifact_admission_failed"}}
    exporter=ledger["exporter"];values=None;export_error=None
    if exporter.get("status")=="completed":
        try:
            require(all(c["status"]=="completed" for c in ledger["calls"]),"export without all 11 completed calls")
            require(sha256(root/"export-values.json")==exporter["sha256"],"native exporter output pin")
            values=load_json(root/"export-values.json")
            require(values.get("schema")=="hippocampal_source_values_v1" and set(values["variants"])==set(VARIANTS),"native exporter schema")
            for variant in VARIANTS:
                require(set(values["variants"][variant])==set(FAMILIES),"all eight native families")
                for family,(n,m,_) in FAMILIES.items():
                    rows=values["variants"][variant][family]
                    require(type(rows) is list and len(rows)==n and all(type(r) is list and len(r)==m for r in rows),"full native output shape")
            for family in ("behavior_accuracy","behavior_lick_latency"):
                require(values["variants"][VARIANTS[0]][family]==values["variants"][VARIANTS[1]][family],"behavior changed across variants")
        except (ValueError,KeyError,TypeError,OSError) as exc:
            export_error={"type":type(exc).__name__,"message":str(exc)};values=None
    slots=[]
    for v,variant in enumerate(VARIANTS):
        for family,(n,m,unit) in FAMILIES.items():
            names=elements(family);require(len(names)==m,"native source layout size")
            roster=BEHAVIOR if n==23 else IMAGING
            for a in range(n):
                for e,element in enumerate(names):
                    dep=native_dependency(v,family,e);call=ledger["calls"][dep-1];value=None
                    if call["status"]=="failed":status,reason="failed","native_call_failed"
                    elif call["status"]=="unstarted":status,reason="unstarted","native_call_unstarted"
                    elif values is None:
                        status="failed" if exporter.get("status")=="failed" or export_error else "unstarted"
                        reason="exporter_failure_or_invalid_output" if status=="failed" else "exporter_blocked_by_other_native_calls"
                    else:
                        raw=values["variants"][variant][family][a][e];status,reason=classify_value(family,element,raw)
                        if status=="finite":value=raw
                    undefined_kind = status.removesuffix("_undefined") if status in ("structural_undefined","computed_undefined") else None
                    if undefined_kind is not None:status="source_undefined"
                    slots.append({"ordinal":len(slots),"variant":variant,"family":family,"animal":roster[a],"animal_ordinal":a,
                                  "element":element,"element_ordinal":e,"index":e,"units":unit,"call_ordinal":dep,"status":status,
                                  "undefined_kind":undefined_kind,"reason":reason,"value":value})
    require(len(slots)==56868,"complete native support")
    counts=dict(Counter(x["status"] for x in slots))
    out={"schema":"h_native_dispositions_v2","task_id":TASK,"slots_expected":56868,"slots":slots,"counts":counts,
         "call_ledger":ledger,"ledger_validation_error":ledger_error,"export_validation_error":export_error,"scientific_qualification":False,
         "reference_admission":"requires_independent_original_clock_runtime_competence_and_undefined_cause_audit"}
    artifact=write_json(root/"native-dispositions.json",out)
    return {"schema":"h_native_result_v2","task_id":TASK,"artifact":artifact,"counts":counts,"slot_count":56868,
            "status":"native_outputs_serialized" if not counts.get("failed") and not counts.get("unstarted") else "incomplete",
            "scientific_qualification":False,"reference_qualified":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    p=sub.add_parser("command");p.add_argument("operation",choices=("prepare","reference","fit"))
    p=sub.add_parser("verify-inputs");p.add_argument("--request",required=True);p.add_argument("--output",required=True)
    p=sub.add_parser("validate-preparation");p.add_argument("--root",default="/output");p.add_argument("--identity");p.add_argument("--identity-sha256")
    p=sub.add_parser("finalize-reference");p.add_argument("--root",default="/output")
    args=parser.parse_args(argv)
    if args.action=="command":print(json.dumps(command(args.operation)));return
    if args.action=="verify-inputs":write_json(args.output,verify_inputs(load_json(args.request)));return
    root=Path(args.root)
    try:
        result=validate_preparation(root,args.identity,args.identity_sha256) if args.action=="validate-preparation" else finalize_reference(root)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        result={"schema":"h_native_bridge_failure_v2","task_id":TASK,"status":"failed","operation":args.action,
                "error":{"type":type(exc).__name__,"message":str(exc)},"raw_artifacts_preserved":True,"scientific_qualification":False}
    write_json(root/"RESULT.json",result)
    if result.get("status") in ("failed","incomplete"):raise SystemExit(2)


if __name__=="__main__":main()
