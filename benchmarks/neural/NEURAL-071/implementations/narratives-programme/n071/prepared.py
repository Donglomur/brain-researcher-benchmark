"""Assemble protected preparation products into complete opaque case support."""
import hashlib
import hmac
from .errors import need
from .identity import canonical,identity
from . import codec,support,scientific
from .policy import evidence

def opaque(key,*parts):
    need(type(key)is bytes and len(key)==32,"operator-opaque-key")
    return hmac.new(key,canonical(list(parts)),hashlib.sha256).hexdigest()

def assemble(release,projected,key,store,journal):
    cases=support.release_census(release)
    selected={sid for c in cases for sid in c["train"]+c["query"]}
    need(set(projected)==selected,"complete-projection-bank")
    scans={s["id"]:s for s in release["scans"]}
    rows={};primitives={};targets={};scan_facts={}
    for scan in release["scans"]:
        scan_facts[opaque(key,scan["id"])]={
            "tr_seconds":scan.get("tr_seconds"),"native_clock":None,"projection_receipt":None,
            "segments":[],"status":"ineligible_not_projected"}
    for sid in sorted(selected):
        value=codec.unpack(store,projected[sid]["artifact"])
        need(value["scan"]==sid,"projection-scan-join")
        clock=value["clock"]
        scan_facts[opaque(key,sid)]={
            "tr_seconds":scans[sid]["tr_seconds"],
            "native_clock":{k:clock[k] for k in ("tr_seconds","first_sample_scanner_seconds",
                             "n_volumes","derivative_clock_verified","new_query_response_optimization")},
            "projection_receipt":projected[sid]["receipt"],"status":"projected",
            "segments":[{"segment":part["segment"],"guarded_rows":len(part["indices"]),
                         "missing_alignment_rows":part["missing_alignments"]} for part in value["parts"]]}
        rows[sid]=[];scan=scans[sid]
        for part in value["parts"]:
            need(len(part["indices"])==len(part["target"])==len(part["primitives"]),"projection-part-shape")
            for index,y,p in zip(part["indices"],part["target"],part["primitives"]):
                rid=opaque(key,sid,part["segment"],index)
                row={"row":rid,"person":opaque(key,scan["person"]),"family":opaque(key,scan["family"]),
                     "run":opaque(key,sid),"segment":part["segment"],"native_index":index}
                need(rid not in targets,"unique-prepared-row")
                rows[sid].append(row);primitives[rid]=p;targets[rid]=y
    expanded=[];private={};protected={}
    for c in cases:
        cid=opaque(key,c["person"],c["family"])
        train=[r for sid in c["train"] for r in rows[sid]]
        query=[r for sid in c["query"] for r in rows[sid]]
        case={"id":cid,"person":opaque(key,c["person"]),"family":opaque(key,c["family"]),
              "train":train,"query":query}
        support.validate_case(case);expanded.append(case)
        ty=[targets[r["row"]] for r in train]
        mu,mean_receipt=journal.invoke("S06","real-training-mean",{"case":cid,
                        "fit_support":identity(train)},{"protected_mean":True},
                        scientific.mean,ty,support.hierarchy_weights(train))
        protected[cid]=codec.pack(store,"protected-"+cid,{"targets":[targets[r["row"]] for r in query],
                                 "real_training_mean":mu,"row_ids":[r["row"] for r in query],
                                 "original_mean_receipt":mean_receipt})
        private[cid]={"train_rows":train,"query_rows":query,"train_y":ty,
                     "primitives":{r["row"]:primitives[r["row"]] for r in train+query}}
    census={"people":[opaque(key,p) for p in release["people"]],
            "scans":[{"id":opaque(key,s["id"]),"person":opaque(key,s["person"]),
                      "family":opaque(key,s["family"])} for s in release["scans"]],"cases":expanded}
    support.census(census)
    result={"generation":journal.generation,"source":journal.source,"cases":private,
            "census":census,"protected":protected,
            "census_report":support.census_report(census,scan_facts,journal.generation,journal.source,identity(release)),
            **evidence(True)}
    rid=journal.begin("S06","prepared-bank-publication",{"projected":projected},
                      {"complete_prepared_bank":True})
    record=codec.pack(store,"prepared-bank",result)
    journal.finish(rid,{"bank":record},{"kind":"immutable-prepared-bank-readback"})
    return record

class TargetReader:
    def __init__(self,protected,source_root,report_store,cases):
        from .store import Store
        self.protected=protected;self.reader=Store(source_root,report_store.budget)
        self.cases={c["id"]:c for c in cases};self.read=set()

    def __call__(self,case_id):
        need(case_id not in self.read and case_id in self.protected,"target-scope-once")
        self.read.add(case_id)
        value=codec.unpack(self.reader,self.protected[case_id])
        need(value["row_ids"]==[r["row"] for r in self.cases[case_id]["query"]],"protected-target-support")
        return value["targets"],value["real_training_mean"]
