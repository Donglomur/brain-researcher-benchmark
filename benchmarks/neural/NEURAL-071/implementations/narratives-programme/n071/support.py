"""Whole-family metadata plan, deterministic inner folds and biological weighting."""
from collections import Counter
from .errors import need
from .identity import identity
from .policy import ARMS, MODES, RESPONSES, REFERENCES, evidence

def inner_folds(case_id, families):
    unique = sorted(set(families))
    need(unique, "no-training-family")
    if len(unique) == 1:
        return []
    order = sorted(unique, key=lambda f: (identity(["N071-inner-family-v1", case_id, f]), f))
    k = min(3, len(order))
    return [tuple(f for n,f in enumerate(order) if n % k == j) for j in range(k)]

def hierarchy_weights(rows):
    """Rows contain opaque family/run/segment; fitting support only."""
    need(rows and len({r["row"] for r in rows}) == len(rows), "unique-fit-rows")
    families = {r["family"] for r in rows}
    runs = {f: {r["run"] for r in rows if r["family"] == f} for f in families}
    segments = {(f,u): {r["segment"] for r in rows if (r["family"],r["run"]) == (f,u)}
                for f in families for u in runs[f]}
    n = Counter((r["family"],r["run"],r["segment"]) for r in rows)
    return [1/(len(families)*len(runs[r["family"]])*
               len(segments[(r["family"],r["run"])])*n[(r["family"],r["run"],r["segment"])])
            for r in rows]

def validate_case(case):
    need(case["train"] and case["query"], "nonempty-case")
    train, query = case["train"], case["query"]
    need(len({r["row"] for r in train+query}) == len(train)+len(query), "disjoint-case-rows")
    need(all(r["person"] == case["person"] for r in train+query), "within-listener")
    need(all(r["family"] != case["family"] for r in train) and
         all(r["family"] == case["family"] for r in query), "outer-family-boundary")
    for rows in (train,query):
        need(all(n >= 20 for n in Counter((r["run"],r["segment"]) for r in rows).values()),
             "complete-guarded-segment")
    return case

def census(record):
    need(len(record["people"]) == len(set(record["people"])) == 345, "census-345")
    scans = record["scans"]
    need(len(scans) == 873 and len({s["id"] for s in scans}) == 873, "census-873")
    need({s["person"] for s in scans} == set(record["people"]), "census-person-support")
    by_person = {p:[s for s in scans if s["person"] == p] for p in record["people"]}
    eligible = {p for p,ss in by_person.items() if len({s["family"] for s in ss}) >= 2}
    need(len(eligible) == 171 and len(set(record["people"])-eligible) == 174, "eligibility-171-174")
    eligible_scans = {s["id"] for s in scans if s["person"] in eligible}
    need(len(eligible_scans) == 572, "eligible-572")
    cases = record["cases"]
    need(len(cases) == 486 and len({c["id"] for c in cases}) == 486, "case-486")
    expected = {(p,s["family"]) for p in eligible for s in by_person[p]}
    need({(c["person"],c["family"]) for c in cases} == expected, "all-person-family-cases")
    for c in cases:
        validate_case(c)
        selected = by_person[c["person"]]
        need({r["run"] for r in c["train"]} == {s["id"] for s in selected if s["family"] != c["family"]},
             "all-training-runs")
        need({r["run"] for r in c["query"]} == {s["id"] for s in selected if s["family"] == c["family"]},
             "all-query-runs")
    return cases

def release_census(record):
    """Preprojection release metadata; no volumes/targets are opened."""
    need(len(record["people"])==345 and len(set(record["people"]))==345,"release-345")
    scans=record["scans"]
    need(len(scans)==873 and len({s["id"] for s in scans})==873,"release-873")
    by_person={p:[s for s in scans if s["person"]==p] for p in record["people"]}
    eligible={p for p,ss in by_person.items() if len({s["family"] for s in ss})>=2}
    need(len(eligible)==171 and sum(s["person"] in eligible for s in scans)==572,"release-eligibility")
    expected={(p,s["family"]) for p in eligible for s in by_person[p]}
    need(len(expected)==486 and len(record["cases"])==486 and
         {(c["person"],c["family"]) for c in record["cases"]}==expected,"release-cases")
    for c in record["cases"]:
        ss=by_person[c["person"]]
        need(set(c["train"])=={s["id"] for s in ss if s["family"]!=c["family"]} and
             set(c["query"])=={s["id"] for s in ss if s["family"]==c["family"]},"release-family-runs")
    return record["cases"]

def census_report(record,scan_facts,generation,source,release_identity):
    """Actual complete opaque release/eligibility dispositions; no signal bodies."""
    cases=census(record)
    need(set(scan_facts)=={s["id"] for s in record["scans"]},"census-report-all-scans")
    people=[];scans=[]
    eligible={c["person"] for c in cases}
    for person in record["people"]:
        own=[s for s in record["scans"] if s["person"]==person]
        families=sorted({s["family"] for s in own})
        people.append({"person":person,"family_count":len(families),"families":families,
                       "scans":[s["id"] for s in own],"status":"eligible" if person in eligible else "ineligible_single_family"})
    for scan in record["scans"]:
        fact=scan_facts[scan["id"]]
        need(set(fact)=={"tr_seconds","native_clock","projection_receipt","segments","status"},"closed-census-scan-facts")
        required=scan["person"]in eligible
        need(fact["status"]==("projected" if required else "ineligible_not_projected"),"census-projection-disposition")
        if required:
            need(fact["projection_receipt"] and fact["native_clock"] and fact["segments"],"census-actual-projection-facts")
        else:
            need(fact["projection_receipt"]is None and fact["native_clock"]is None and fact["segments"]==[],
                 "ineligible-not-fabricated")
        scans.append(dict(scan,**fact))
    case_rows=[{"case":c["id"],"person":c["person"],"held_family":c["family"],
                "training_family_count":len({r["family"] for r in c["train"]}),
                "train_runs":sorted({r["run"] for r in c["train"]}),
                "query_runs":sorted({r["run"] for r in c["query"]}),
                "fit_support":identity([r["row"] for r in c["train"]]),
                "query_support":identity([r["row"] for r in c["query"]])}for c in cases]
    return {"schema":"n071-complete-census-report-v1","generation":generation,"source":source,
            "census_identity":identity(record),"release_metadata_identity":release_identity,
            "people":people,"scans":scans,"cases":case_rows,
            "counts":{"release_people":len(people),"release_scans":len(scans),"eligible_people":len(eligible),
                      "ineligible_people":len(people)-len(eligible),"cases":len(cases),
                      "eligible_scans":sum(s["person"]in eligible for s in scans),"parcels":400},
            "limitations":["Native TR and derivative clock facts are reported from admitted original metadata, not inferred from feature rows.",
                           "Missing alignment-row counts are original per-segment producer observations; repeated alignment-source counts are not summed as independent omissions.",
                           "Ineligible scans were not projected. Unknown source fields remain null; successful report publication does not recover historical missing alignment variants or establish native qualification."]}

def contexts(cases):
    result = []
    for case in cases:
        cid = case["id"]
        for mode in MODES:
            for arm in ARMS:
                for response in RESPONSES:
                    result.append({"id": cid+"/"+mode+"/"+arm+"/"+response, "case":cid,
                                   "kind":"candidate", "mode":mode, "arm":arm, "response":response,
                                   **evidence(arm=="CONTEXT")})
        for ref in REFERENCES:
            result.append({"id":cid+"/"+ref, "case":cid, "kind":"reference", "reference":ref,
                           **evidence(ref=="R2/CONTEXT")})
    need(len(result)==10206 and len({r["id"] for r in result})==10206, "full-context-graph")
    return result
