"""Authoring-only FCSTAB controls, never production acceptance criteria.

Inputs are a caller's independently authenticated reference and already valid
five-artifact snapshot. No source reconstruction, original-table access or
network. Numerical effectiveness is classified under public tolerances before
the normal unmodified validator sees a detached candidate. No result band.
"""
import copy
from decimal import Decimal
import math

import numpy as np

import output_contract as c

POSITIVES = ("coherent_axis_permutation", "numeric_representations", "descriptive_extras",
             "rounded_evidence_receipts", "own_z_replay")
NUMERICAL = ("reverse_delta_sign", "population_sd", "missing_sqrt_n", "one_sided_p",
             "absolute_reliability", "opposite_tost_tails", "pooled_edge_pearson",
             "average_forward_reverse_as_independent")
BINDING = ("source_hash", "missing_subject", "common_mask", "z_signflip", "training_self")
SUMMARY_FIELDS = ("selection_schemes","equivalence","forward_top_decile_connectivity","reliability")


def prepare(documents, reference):
    z,pairs,axis_map = c.canonical_primitives(documents["connectivity.npz"],reference)
    ids = reference["subject_ids"]
    rows = c.csv_rows(documents["stability.csv"],ids,len(pairs))
    evidence = c.keyed(documents["selection_evidence.json"]["subjects"],"subject_id")
    rel = c.reliability_receipts(evidence,ids)
    kernel = c.load_kernel()
    replay = kernel.analyze(z,reference["fisher_z"],ids,pairs,accepted_rows=rows,accepted_reliability=rel)
    return dict(reference=reference,z=z,pairs=pairs,axis_map=axis_map,rows=rows,rel=rel,kernel=kernel,replay=replay)


def report(mode,category,status,reason="",effect=None):
    return dict(mode=mode,category=category,status=status,reason=reason,
                effect=effect or dict(n_changed=0,n_numeric_changes=0,n_status_changes=0,max_absolute_gap=None,examples=[]))


def scientific_view(documents):
    return {key:documents["summary.json"][key] for key in SUMMARY_FIELDS}


def numeric_effects(actual,expected):
    changes = []
    def walk(a,b,path,key=""):
        if isinstance(b,dict):
            if isinstance(a,dict):
                for k,v in b.items():
                    if k in a: walk(a[k],v,path+"."+k,k)
        elif b is None or isinstance(b,(bool,int,float,Decimal,np.integer,np.floating)):
            try:
                c.match(a,b,atol=1e-8,rtol=1e-6,path=path)
                if a is not None and key in ("p","p_lower","p_upper","tost_p","overlap"):
                    c.need(0 <= c.io.real(a,json_number=True) <= 1,"natural probability domain")
                if a is not None and key in ("delta_sd","delta_se"):
                    c.need(c.io.real(a,json_number=True) >= 0,"natural dispersion domain")
            except ValueError:
                numeric = lambda x:isinstance(x,(int,float,Decimal,np.integer,np.floating)) and not isinstance(x,(bool,np.bool_))
                gap = abs(float(a)-float(b)) if numeric(a) and numeric(b) else None
                changes.append(dict(path=path,kind="numeric",absolute_gap=gap))
        elif isinstance(b,str) and (key=="status" or key.endswith("_status")) and a!=b:
            changes.append(dict(path=path,kind="status",absolute_gap=None))
    walk(actual,expected,"scientific")
    return dict(n_changed=len(changes),n_numeric_changes=sum(v["kind"]=="numeric" for v in changes),
                n_status_changes=sum(v["kind"]=="status" for v in changes),
                max_absolute_gap=max((v["absolute_gap"] for v in changes if v["absolute_gap"] is not None),default=None),
                examples=changes[:12])


def baseline_candidate(documents,context):
    candidate = copy.deepcopy(documents)
    candidate["summary.json"].update(copy.deepcopy(context["replay"]["summaries"]))
    return candidate


def install_replay(candidate,context,replay):
    candidate["stability.csv"] = copy.deepcopy(replay["rows"])
    inverse = {canonical:storage for storage,canonical in context["axis_map"].items()}
    for row in candidate["selection_evidence.json"]["subjects"]:
        sid = row["subject_id"]
        row.update(copy.deepcopy(replay["evidence"][sid]))
        for scheme in c.SCHEMES:
            row[scheme+"_edge_indices"] = [inverse[v] for v in row[scheme+"_edge_indices"]]
    candidate["summary.json"].update(copy.deepcopy(replay["summaries"]))
    candidate["summary.json"]["source_inference_support"] = {
        scheme:{"status":replay["support_diagnostics"][scheme]["status"]} for scheme in c.SCHEMES}
    return candidate


def replace_z(candidate,context,new_z):
    arrays = candidate["connectivity.npz"]
    p = c.text_axis(arrays["subject_ids"],context["reference"]["subject_ids"],"subjects")
    s = c.text_axis(arrays["segment_ids"],c.SEGMENTS,"segments")
    inverse = {canonical:storage for storage,canonical in context["axis_map"].items()}
    e = [inverse[i] for i in range(len(inverse))]
    arrays["fisher_z"] = arrays["fisher_z"].astype(np.float64)
    arrays["fisher_z"][np.ix_(p,s,e)] = new_z


def positive_candidate(mode,documents,context):
    c.need(mode in POSITIVES,"unknown positive mode")
    candidate = copy.deepcopy(documents)
    a,e,s = candidate["connectivity.npz"],candidate["selection_evidence.json"],candidate["summary.json"]
    if mode=="coherent_axis_permutation":
        p = np.arange(len(a["subject_ids"])-1,-1,-1); seg = np.array([2,0,1]); edges = np.arange(len(a["edge_roi_i"])-1,-1,-1)
        a["subject_ids"] = a["subject_ids"][p]; a["segment_ids"] = a["segment_ids"][seg]
        a["fisher_z"] = a["fisher_z"][np.ix_(p,seg,edges)]
        for name in ("roi_ids","common_roi_mask"): a[name] = a[name][::-1]
        for name in ("edge_roi_i","edge_roi_j"): a[name] = a[name][edges]
        inverse = {int(old):new for new,old in enumerate(edges)}
        for row in e["subjects"]:
            row["training_subject_ids"].reverse()
            for scheme in c.SCHEMES: row[scheme+"_edge_indices"] = [inverse[c.io.integer(v,json_number=True)] for v in row[scheme+"_edge_indices"]][::-1]
        e["subjects"].reverse(); candidate["stability.csv"].reverse()
        for name in ("cohort","source_files"): s[name].reverse()
        s["source_observed"]["phenotype_ledger"].reverse()
    elif mode=="numeric_representations":
        for name in ("roi_ids","edge_roi_i","edge_roi_j"): a[name] = a[name].astype(float)
        for row in candidate["stability.csv"]: row["n_edges"] = str(c.io.integer(row["n_edges"]))+"e0"
        for row in e["subjects"]:
            for scheme in c.SCHEMES: row[scheme+"_edge_indices"] = [float(v) for v in row[scheme+"_edge_indices"]]
    elif mode=="descriptive_extras":
        a["descriptive_extra"] = np.zeros((1,1,1,2),dtype=np.int16)
        e["authoring_note"] = "No required outcome direction."
        s["optional_average_not_graded"] = 0.
        for row in candidate["stability.csv"]: row["authoring_note"] = "bounded extra"
    elif mode=="rounded_evidence_receipts":
        rel = {}
        for row in e["subjects"]:
            for values in row["means"].values():
                for key in ("first","second"): values[key] = round(float(values[key]),6)
            for key in ("edge_pearson","edge_spearman"):
                if row["reliability"][key] is not None: row["reliability"][key] = round(float(row["reliability"][key]),6)
            rel[row["subject_id"]] = row["reliability"]
        for name in ("edge_pearson","edge_spearman"):
            values = [rel[sid][name] for sid in context["reference"]["subject_ids"]]
            s["reliability"][name]["mean"] = context["kernel"].mean(values) if all(v is not None for v in values) else None
    else:
        z = context["z"]*(1+2**-32)+2**-40
        try:
            replay = context["kernel"].analyze(z,context["reference"]["fisher_z"],context["reference"]["subject_ids"],context["pairs"])
        except ValueError as exc:
            return None,report(mode,"positive","not_constructed","declared fidelity: "+str(exc))
        replace_z(candidate,context,z)
        install_replay(candidate,context,replay)
    return candidate,report(mode,"positive","constructed")


def restat(record,delta,kernel,*,se_multiplier=1.):
    """An explicitly altered summary component, with original status retained."""
    n = len(delta); m = kernel.mean(delta)
    sd = kernel.stable_l2(kernel.centered(delta))/math.sqrt(n-1)
    se = sd/math.sqrt(n)*se_multiplier
    record.update(delta_mean=m,delta_sd=sd*se_multiplier,delta_se=se,n_negative=int(np.count_nonzero(np.asarray(delta)<0)))
    if record["inference_status"]=="ok":
        if not se>0: return False
        t = m/se; half = float(kernel.stats.t.ppf(.975,n-1))*se
        if not all(map(math.isfinite,(t,half,m-half,m+half))): return False
        record.update(t=t,p=float(2*kernel.stats.t.sf(abs(t),n-1)),ci95_lo=m-half,ci95_hi=m+half)
    return True


def update_equivalence(summary,kernel):
    row,eq = summary["selection_schemes"]["independent"],summary["equivalence"]
    if eq["status"] != "ok": return
    mean,se = float(row["delta_mean"]),float(row["delta_se"])
    pl = float(kernel.stats.t.sf((mean+.05)/se,39)); pu = float(kernel.stats.t.sf((.05-mean)/se,39))
    eq.update(p_lower=pl,p_upper=pu,tost_p=max(pl,pu),equivalent_within_margin=bool(max(pl,pu)<.05))


def numerical_candidate(mode,documents,context):
    c.need(mode in NUMERICAL,"unknown numerical mode")
    candidate = baseline_candidate(documents,context)
    summary,kernel,rows = candidate["summary.json"],context["kernel"],context["rows"]
    available = True
    if mode=="reverse_delta_sign":
        available = restat(summary["selection_schemes"]["reverse"],[-r["reverse_delta"] for r in rows],kernel)
    elif mode in ("population_sd","missing_sqrt_n"):
        for scheme in c.SCHEMES:
            multiplier = math.sqrt(39/40) if mode=="population_sd" else math.sqrt(40)
            available = restat(summary["selection_schemes"][scheme],[r[scheme+"_delta"] for r in rows],kernel,se_multiplier=multiplier) and available
            if mode=="missing_sqrt_n":
                # Only SE loses sqrt(n); sample SD itself is unchanged.
                summary["selection_schemes"][scheme]["delta_sd"] = context["replay"]["summaries"]["selection_schemes"][scheme]["delta_sd"]
        if available: update_equivalence(summary,kernel)
    elif mode=="one_sided_p":
        available = any(r["p"] is not None for r in summary["selection_schemes"].values())
        for record in summary["selection_schemes"].values():
            if record["p"] is not None: record["p"] /= 2
    elif mode=="absolute_reliability":
        available = False
        for name in ("edge_pearson","edge_spearman"):
            values = [context["rel"][sid][name] for sid in context["reference"]["subject_ids"]]
            if all(v is not None for v in values):
                available = True; summary["reliability"][name]["mean"] = kernel.mean([abs(v) for v in values])
    elif mode=="opposite_tost_tails":
        eq = summary["equivalence"]; available = eq["status"]=="ok"
        if available:
            pl,pu = 1-float(eq["p_lower"]),1-float(eq["p_upper"])
            eq.update(p_lower=pl,p_upper=pu,tost_p=max(pl,pu),equivalent_within_margin=bool(max(pl,pu)<.05))
    elif mode=="pooled_edge_pearson":
        available = summary["reliability"]["edge_pearson"]["status"]=="ok"
        if available:
            value = kernel.pearson(context["z"][:,0,:].ravel(),context["z"][:,1,:].ravel())
            available = value is not None
            if available: summary["reliability"]["edge_pearson"]["mean"] = value
    else:
        delta = [(r["forward_delta"]+r["reverse_delta"])/2 for r in rows]
        available = restat(summary["selection_schemes"]["independent"],delta,kernel)
        if available: update_equivalence(summary,kernel)
    if not available: return None,report(mode,"numerical","unavailable","required finite mathematical support absent")
    effect = numeric_effects(scientific_view(candidate),context["replay"]["summaries"])
    # The genuine source/primitive/evidence identity is intentionally retained;
    # this isolates a reported numerical component, not an alternative valid method.
    summary["negative_control"] = dict(altered_operation=mode,nominal_provenance_intentionally_retained=True)
    return candidate,report(mode,"numerical","effective" if effect["n_changed"] else "nondiscriminating",effect=effect)


def binding_candidate(mode,documents,context):
    c.need(mode in BINDING,"unknown binding mode")
    candidate = copy.deepcopy(documents)
    ref = context["reference"]
    if mode=="source_hash":
        row = candidate["summary.json"]["source_files"][0]
        row["sha256"] = ("0" if row["sha256"][0]!="0" else "1")+row["sha256"][1:]
    elif mode=="missing_subject": candidate["stability.csv"].pop()
    elif mode=="common_mask": candidate["connectivity.npz"]["common_roi_mask"][0] = not bool(candidate["connectivity.npz"]["common_roi_mask"][0])
    elif mode=="training_self":
        row = candidate["selection_evidence.json"]["subjects"][0]
        row["training_subject_ids"][0] = row["subject_id"]
    else:
        replace_z(candidate,context,-context["z"])
    try:
        if mode=="source_hash": c.validate_metadata(candidate["summary.json"],ref)
        elif mode=="missing_subject": c.csv_rows(candidate["stability.csv"],ref["subject_ids"],len(context["pairs"]))
        elif mode=="common_mask": c.canonical_primitives(candidate["connectivity.npz"],ref)
        elif mode=="training_self":
            c.need(set(row["training_subject_ids"])==set(ref["subject_ids"])-{row["subject_id"]},"training membership")
        else:
            z,_,_ = c.canonical_primitives(candidate["connectivity.npz"],ref)
            for i in range(40):
                for seg in range(3): context["kernel"].edge_fidelity(z[i,seg],ref["fisher_z"][i,seg])
            if not np.array_equal(z,context["z"]):
                return None,report(mode,"binding","not_constructed","sign transform remains source-close but is not an exact no-op; no stale endpoint assumption")
    except ValueError as exc:
        return candidate,report(mode,"binding","effective","direct required binding discrepancy: "+str(exc),
            effect=dict(n_changed=1,n_numeric_changes=0,n_status_changes=0,max_absolute_gap=None,examples=[]))
    return candidate,report(mode,"binding","nondiscriminating","transformation is a lawful exact no-op")
