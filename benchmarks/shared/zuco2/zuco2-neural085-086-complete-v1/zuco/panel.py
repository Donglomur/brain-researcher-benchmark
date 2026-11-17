"""Complete source-panel validation and original-source extraction contracts.
Native cleaning/FRP operators are deliberately unavailable until exact original
source operators and independent source-stage qualification exist. No surrogate.
"""
import unicodedata,re,hashlib,copy
from collections import defaultdict
from .io import *
from .constants import *
def exact_text(s):need(type(s)is str and 0<len(s)<=10000,"sentence_text");return " ".join(unicodedata.normalize("NFKC",s).split())
def group_text(s):return " ".join(re.sub(r"[^\w]+"," ",exact_text(s).casefold()).split())
def text_id(s):return hashlib.sha256(exact_text(s).encode()).hexdigest()
def group_id(s):return hashlib.sha256(group_text(s).encode()).hexdigest()
def fold(s,n=5):return int(group_id(s),16)%n
def nullable(x):return x is None or finite(x)
def validate(panel,source_closure,overlap,abi):
    exact(panel,["schema","source_sha256","abi_sha256","rows","event_dispositions"])
    need(panel["schema"]=="zuco2-panel-v1" and panel["source_sha256"]==digest(source_closure) and panel["abi_sha256"]==digest(abi),"panel_source_ABI")
    need(len(source_closure["files"])==36 and {(x["person"],x["condition"]) for x in source_closure["files"]}=={(s,c) for s in PERSONS for c in CONDITIONS},"source_36_census")
    need(abi["sample_rate_hz"]==500 and len(abi["scalp_channels"])==105 and len(set(abi["scalp_channels"]))==105 and len(abi["EOG_channels"])==9 and len(abi["discarded_channels"])==14,"source_channel_clock_ABI")
    need(len(set(abi["scalp_channels"]+abi["EOG_channels"]+abi["discarded_channels"]))==128,"source_channel_roles")
    need(abi["original_reference"] and abi["units"] and abi["source_stage_lineage"] and abi["filter_information_support"],"source_ABI_semantics")
    rows=panel["rows"];need(type(rows)is list and len(rows)==13302,"full_presentation_count");seen=set();strings={};word_shapes={}
    for r in rows:
        need(r["person"]in PERSONS and r["condition"]in CONDITIONS and type(r["index"])is int and 0<=r["index"]<COUNTS[r["condition"]],"presentation_identity")
        need(type(r.get("presentation_order"))is int and 0<=r["presentation_order"]<739 and type(r.get("repetition_ordinal"))is int and r["repetition_ordinal"]>=0 and type(r.get("block"))is int and 0<=r["block"]<14,"original_order_repetition_disposition");key=(r["person"],r["condition"],r["index"]);need(key not in seen,"duplicate_presentation");seen.add(key);exact_text(r["text"])
        need(type(r["words"])is list and type(r["gaze_summary"])is list and len(r["gaze_summary"])==12 and all(nullable(x) for x in r["gaze_summary"]),"source_gaze_ABI")
        need(type(r["eeg_summary"])is list and len(r["eeg_summary"])==840 and all(nullable(x) for x in r["eeg_summary"]),"sentence_840_ABI")
        k=(r["condition"],r["index"]);need(k not in strings or strings[k]==r["text"],"cross_person_text_join");strings[k]=r["text"]
        sig=tuple(exact_text(w["word"]) for w in r["words"]);tid=text_id(r["text"])
        if sig:need(tid not in word_shapes or word_shapes[tid]==sig,"original_word_position_alignment");word_shapes[tid]=sig
        for w in r["words"]:
            need(set(w["windows"])==set(CONTEXTS),"all_five_window_dispositions")
            for c,z in w["windows"].items():
                exact(z,["duration_ms","pupil","band_values","segments","status","source_pin"])
                need(nullable(z["duration_ms"]) and nullable(z["pupil"]),"window_values")
                need(type(z["band_values"])is list and len(z["band_values"])==840 and all(nullable(v) for v in z["band_values"]),"word_840_roles")
                need(type(z["segments"])is dict and set(z["segments"])=={"raw_waveform","cleaned_waveform"} and all(v is None or type(v)is list for v in z["segments"].values()) and z["status"] in ("available","unavailable"),"window_source_disposition")
    need(seen=={(s,c,i) for s in PERSONS for c in CONDITIONS for i in range(COUNTS[c])},"complete_source_slots")
    j=sorted(set(text_id(t) for (c,i),t in strings.items() if c=="NR")&set(text_id(t) for (c,i),t in strings.items() if c=="TSR"))
    need(j==overlap["exact_shared_items"] and overlap["paper63_reconciled"] is True and len(overlap["paper63_obligations"])==63,"qualified_exact_J")
    need(len({x["obligation_id"] for x in overlap["paper63_obligations"]})==63 and all(x["source_evidence"] and x["disposition"] for x in overlap["paper63_obligations"]),"duplicate_obligation_evidence")
    need(all(len({r["presentation_order"] for r in rows if r["person"]==s})==739 for s in PERSONS),"full_original_order");need(set(panel["event_dispositions"])==set(PERSONS),"all_event_dispositions")
    for s,e in panel["event_dispositions"].items():need(e["sessions"]==1 and len(e["blocks"])==14 and e["practice_dispositions"] and e["screen_response_dispositions"],"event_scope")
    return {"rows":rows,"J":j,"source_sha256":digest(source_closure),"abi_sha256":digest(abi),"complete_presentations":13302,"context_capabilities":{c:any(w["windows"][c]["status"]=="available" and finite(w["windows"][c]["duration_ms"]) and w["windows"][c]["duration_ms"]>0 for r in rows for w in r["words"]) for c in CONTEXTS}}
def load_source(review,ledger):
    """Only invoked under future external scientific execution authority."""
    for key in ("source_closure","overlap","representation_ABI","prepared_panel"):
        descriptor(review[key])
    closure=decode(read(review["source_closure"]["path"],8*1024**2,review["source_closure"],ledger.guard))
    for row in closure["files"]:descriptor(row["pin"]);authenticate(row["pin"]["path"],row["pin"]["bytes"],row["pin"],ledger.guard)
    overlap=decode(read(review["overlap"]["path"],16*1024**2,review["overlap"],ledger.guard));abi=decode(read(review["representation_ABI"]["path"],8*1024**2,review["representation_ABI"],ledger.guard))
    panel=decode(read(review["prepared_panel"]["path"],review["prepared_panel"]["bytes"],review["prepared_panel"],ledger.guard))
    descriptor(review['preparation_receipt']);receipt=decode(read(review['preparation_receipt']['path'],8*1024**2,review['preparation_receipt'],ledger.guard))
    need(receipt['source_sha256']==digest(closure) and receipt['panel_pin']==review['prepared_panel'] and receipt['abi_sha256']==digest(abi),'source_preparation_receipt_join')
    from .products import success
    success(receipt['original_process']);need(receipt['independent_source_stage_qualification'] and receipt['exact_operator_source_pins'] and receipt['full_36_13302_scope']is True,'qualified_preparation_required')
    for d in receipt['exact_operator_source_pins']:descriptor(d);authenticate(d['path'],d['bytes'],d,ledger.guard)
    validated=validate(panel,closure,overlap,abi)
    from .controls import chronology,control_dispositions
    observations={'NC04':None,'NC07':None};gaps=[]
    try:observations['NC04']=chronology(validated['rows'])
    except Refusal as e:gaps.append({'control':'NC04','status':'required_unscorable','source_gap':failure(e)})
    from collections import Counter
    counts=Counter((r['person'],text_id(r['text']),r['condition']) for r in validated['rows']);observations['NC07']={'repeat_cells':sum(n>1 for n in counts.values()),'all_presentations':len(validated['rows']),'matched_items':len(validated['J']),'strata':['first','later','matched','exclusive','block','duration_missingness'],'outcome_selected_thresholds':False}
    validated['source_control_observations']=observations;validated['source_control_gaps']=gaps;validated['source_review']=review
    return validated,abi
