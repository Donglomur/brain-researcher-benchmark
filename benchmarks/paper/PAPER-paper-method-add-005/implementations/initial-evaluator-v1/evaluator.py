"""Prospective AJILE12 missing-channel evaluation; no diffusion training or claims."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import sys
import numpy as np

PARTICIPANTS = tuple(f"EC{i:02d}" for i in range(1, 13))
DROPOUTS = (0.5, 0.7, 0.9)
SEEDS = tuple(range(5))
SOURCE_CHANNELS = dict(zip(PARTICIPANTS, (94,86,80,84,106,80,64,92,126,126,106,116)))
SCHEMA = "ajile-reconstruction-v1"
METRICS = ("mse_standardized_all", "mse_standardized_eligible", "mse_source_units_squared_eligible", "pearson_eligible", "psd_db_mae_eligible")
HOLDS = ["No authentic data, diffusion training, native numerical reference or scientific qualification established.", "Reconstruction metrics and ridge are prospective, not published RF accuracy or the trained neural-network baseline.", "Event-day separation does not certify absolute-time guard bands, overlapping-event independence or participant transfer.", "Candidate isolation, dataset rights/component rights and actual pretraining exposure require operator qualification."]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(x, name):
    x = np.asarray(x, dtype=np.float64)
    require(np.isfinite(x).all(), f"{name} must be finite")
    return x


def digest_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_json(path, value, private=False):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    if private:
        os.chmod(path, 0o600)


def load_npz(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def source_arrays(signal, days, times, row_ids):
    """Validate extracted native ECoG, preserving every event/channel in the file."""
    x = finite(signal, "signal")
    d = finite(days, "days")
    t = finite(times, "times")
    ids = np.asarray(row_ids)
    require(x.ndim == 3 and min(x.shape) > 0, "signal must be nonempty events x channels x time")
    require(d.shape == (len(x),) and np.equal(d, np.floor(d)).all(), "days must be one integer per event")
    require(ids.shape == (len(x),) and ids.dtype.kind in "US" and len(set(ids.tolist())) == len(ids) and all(str(v).strip() for v in ids), "row_ids must be unique text, one per event")
    require(t.shape == (x.shape[2],) and len(t) >= 4, "times must match time dimension")
    require(np.all(np.diff(t) > 0) and np.allclose(np.diff(t), np.diff(t)[0], rtol=1e-8, atol=1e-12), "times must be increasing and uniformly sampled")
    require(np.unique(d).size >= 2, "at least two event-days required")
    return x, d.astype(np.int64), t, ids.astype(str)


def fit_preprocessing(train):
    """Pinned author's train-only range IQR filter and population z score."""
    train = finite(train, "train")
    require(train.ndim == 3 and min(train.shape) > 0, "nonempty training tensor required")
    ranges = np.ptp(train, axis=2)
    low, high = np.percentile(ranges, [25, 75], axis=0)
    lower, upper = low - 5.0 * (high - low), high + 5.0 * (high - low)
    valid = (ranges != 0) & (ranges >= lower) & (ranges <= upper)
    count = valid.sum(axis=0) * train.shape[2]
    require(np.all(count > 0), "a channel has no eligible training samples")
    mean = np.where(valid[:, :, None], train, 0).sum(axis=(0, 2)) / count
    variance = np.where(valid[:, :, None], (train - mean[None, :, None]) ** 2, 0).sum(axis=(0, 2)) / count
    scale = np.sqrt(variance)
    require(np.all(scale > 0) and np.isfinite(scale).all(), "training scale is undefined or zero")
    return {"mean": mean, "scale": scale, "lower": lower, "upper": upper}, valid


def quality_mask(x, stats):
    ranges = np.ptp(finite(x, "quality input"), axis=2)
    return (ranges != 0) & (ranges >= stats["lower"]) & (ranges <= stats["upper"])


def standardize(x, stats):
    return (x - stats["mean"][None, :, None]) / stats["scale"][None, :, None]


def observed_channels(channels, dropout, seed):
    require(type(channels) is int and channels >= 2, "at least two channels required")
    require(dropout in DROPOUTS and seed in SEEDS, "unsupported fixed dropout/seed")
    n = int(np.round((1.0 - dropout) * channels))
    require(0 < n < channels, "mask must retain at least one observed and one target channel")
    observed = np.zeros(channels, dtype=bool)
    observed[np.random.default_rng(seed).choice(channels, size=n, replace=False)] = True
    return observed


def condition(test_z, observed, observed_quality):
    """Only fixed observed-channel values/quality reach a candidate."""
    visible = np.asarray(observed, bool)[None, :] & np.asarray(observed_quality, bool)
    return np.concatenate((np.broadcast_to(visible[:, :, None], test_z.shape).astype(float), np.where(visible[:, :, None], test_z, 0.0)), axis=1)


def conditional_ridge(train_z, train_valid, cond, observed, alpha=1e-3):
    """Instantaneous train-only ridge; alpha multiplies mean-square objective."""
    require(np.isfinite(alpha) and alpha > 0, "ridge alpha must be positive")
    train_z = finite(train_z, "train_z")
    cond = finite(cond, "condition")
    n, c, t = train_z.shape
    require(np.asarray(train_valid).shape == (n, c), "train validity shape mismatch")
    require(cond.ndim == 3 and cond.shape[1:] == (2*c, t), "condition shape mismatch")
    obs = np.flatnonzero(observed)
    targets = np.flatnonzero(~np.asarray(observed, dtype=bool))
    prediction = cond[:, c:, :].copy()
    if not len(obs):
        return prediction
    x_all = train_z[:, obs, :].transpose(0, 2, 1)
    # Same zero-filled, explicitly available observations as the test packet.
    x_all = np.where(np.asarray(train_valid)[:, obs][:, None, :], x_all, 0.0)
    x_test = cond[:, c+obs, :].transpose(0, 2, 1)
    for target in targets:
        valid_events = np.asarray(train_valid)[:, target]
        require(np.any(valid_events), "no eligible ridge target training events")
        x = x_all[valid_events].reshape(-1, len(obs))
        y = train_z[valid_events, target, :].reshape(-1)
        mx, my = x.mean(axis=0), y.mean()
        xc, yc = x-mx, y-my
        coef = np.linalg.solve(xc.T @ xc / len(y) + alpha*np.eye(len(obs)), xc.T @ yc / len(y))
        prediction[:, target, :] = (x_test-mx) @ coef + my
    return prediction


def periodogram(x, fs):
    """One-sided rectangular periodogram, constant detrend, density units."""
    x = finite(x, "periodogram input")
    require(x.shape[-1] >= 4 and np.isfinite(fs) and fs > 0, "invalid periodogram length/rate")
    t = x.shape[-1]
    p = np.abs(np.fft.rfft(x-x.mean(axis=-1, keepdims=True), axis=-1))**2/(fs*t)
    p[..., 1:-1 if t % 2 == 0 else None] *= 2.0
    return p


def score_case(reference_z, prediction_z, observed, valid, scale, fs):
    ref, pred = finite(reference_z, "reference"), finite(prediction_z, "prediction")
    require(ref.shape == pred.shape and ref.ndim == 3, "prediction shape mismatch")
    require(np.asarray(observed).shape == (ref.shape[1],), "observed shape mismatch")
    require(np.asarray(valid).shape == ref.shape[:2], "quality shape mismatch")
    scale = finite(scale, "scale")
    require(scale.shape == (ref.shape[1],) and np.all(scale > 0), "invalid scale")
    target = ~np.asarray(observed, bool)
    require(target.any(), "no target channels")
    r, p = ref[:, target, :], pred[:, target, :]
    eligible = np.asarray(valid, bool)[:, target]
    require(eligible.any(), "no eligible target event-channels; case cannot be silently omitted")
    mse = np.mean((p-r)**2, axis=2)
    raw_mse = mse * scale[target][None, :]**2
    rc, pc = r-r.mean(axis=2, keepdims=True), p-p.mean(axis=2, keepdims=True)
    norm_r, norm_p = np.linalg.norm(rc, axis=2), np.linalg.norm(pc, axis=2)
    pearson_valid = eligible & (norm_r > 0)
    require(pearson_valid.any(), "no variable eligible targets")
    corr = np.zeros_like(norm_r)
    np.divide(np.sum(rc*pc, axis=2), norm_r*norm_p, out=corr, where=(norm_r*norm_p)>0)
    corr = np.clip(corr, -1, 1)
    # Fixed prospective floor in standardized-signal^2 / Hz; omit DC after detrend.
    pr, pp = periodogram(r, fs)[..., 1:], periodogram(p, fs)[..., 1:]
    spectral = np.mean(np.abs(10*np.log10(np.maximum(pp, 1e-12))-10*np.log10(np.maximum(pr, 1e-12))), axis=2)
    return {"mse_standardized_all": float(mse.mean()), "mse_standardized_eligible": float(mse[eligible].mean()), "mse_source_units_squared_eligible": float(raw_mse[eligible].mean()), "pearson_eligible": float(corr[pearson_valid].mean()), "psd_db_mae_eligible": float(spectral[eligible].mean()), "target_event_channels": int(eligible.size), "eligible_target_event_channels": int(eligible.sum()), "excluded_target_event_channels": int((~eligible).sum()), "target_samples_all": int(eligible.size*r.shape[2]), "constant_prediction_event_channels": int(((norm_p == 0)&eligible).sum()), "undefined_target_correlations": int((eligible&~pearson_valid).sum())}


def convert_native(input_path, output_path):
    """Optional native schema adapter; does not download or install anything."""
    try:
        import xarray as xr
    except ImportError as exc:
        raise ValueError("native conversion requires an already installed xarray/netCDF reader; installation is not performed") from exc
    require(Path(input_path).stem in {f"{p}_ecog_data" for p in PARTICIPANTS}, "unexpected processed AJILE filename")
    with xr.open_dataset(input_path) as ds:
        require(len(ds.data_vars) == 1 and set(ds.dims) == {"events", "channels", "time"}, "require one variable with events/channels/time dimensions")
        da = ds[next(iter(ds.data_vars))].transpose("events", "channels", "time")
        times = np.asarray(ds.time.values)
        keep = np.flatnonzero((times >= -2.0)&(times <= 2.0))
        require(len(ds.channels) >= 3 and keep.size == 1001, "expected final label channel and 1001 inclusive samples")
        x = np.asarray(da.isel(channels=slice(0,-1), time=keep).values)
        labels = np.asarray(da.isel(channels=-1,time=0).values)-1.0
        require(np.isin(labels,[0,1]).all(), "terminal channel labels must be source codes 1/2")
        days = np.asarray(ds.events.values)
        ids = np.array([f"event-{i:08d}" for i in range(len(days))])
        source_arrays(x,days,times[keep],ids)
    require(not Path(output_path).exists(), "refusing to overwrite extraction")
    np.savez_compressed(output_path, signal=x, days=days, times=times[keep], row_ids=ids, source_sha256=np.array(digest_file(input_path)), source_filename=np.array(Path(input_path).name))


def prepare(manifest_path, public_dir, private_dir):
    manifest_path = Path(manifest_path)
    spec = json.loads(manifest_path.read_text())
    require(spec.get("schema") == SCHEMA and spec.get("kind") in ("authentic_input", "generated_control"), "invalid input schema/kind")
    records = spec.get("participants", [])
    require([r.get("id") for r in records] == list(PARTICIPANTS), "complete ordered EC01-EC12 panel required")
    pub, priv = Path(public_dir).resolve(), Path(private_dir).resolve()
    require(pub != priv and pub not in priv.parents and priv not in pub.parents, "public and private output directories must be disjoint")
    require(not pub.exists() and not priv.exists(), "fresh output directories required")
    # Validate every source before writing any output or fitting preprocessing.
    loaded=[]
    for rec in records:
        path = manifest_path.parent / rec["path"]
        require(digest_file(path) == rec["sha256"], "extraction digest mismatch")
        data=load_npz(path)
        x,days,times,ids=source_arrays(data["signal"],data["days"],data["times"],data["row_ids"])
        require(x.shape[2] == 1001 and np.allclose(times, np.linspace(-2,2,1001),rtol=0,atol=1e-10), "fixed AJILE window is 1001 samples at 250 Hz, [-2,+2] s")
        if spec["kind"] == "authentic_input":
            require(x.shape[1] == SOURCE_CHANNELS[rec["id"]], "authentic participant channel count differs from pinned author script")
        source_hash=str(data.get("source_sha256", ""))
        require(len(source_hash)==64 and all(ch in '0123456789abcdef' for ch in source_hash), "native source SHA256 required (generated controls use a declared synthetic digest)")
        require(str(data.get("source_filename", "")) == rec["id"]+"_ecog_data.nc", "native source filename mismatch")
        loaded.append((rec,x,days,times,ids,source_hash))
    pub.mkdir(parents=True,mode=0o700);priv.mkdir(parents=True,mode=0o700)
    public={"schema":SCHEMA,"distribution":"operator_only_all_masks_not_candidate_packet","kind":spec["kind"],"scope":"all twelve selected human participants; within-participant latest available day","cases":[],"participants":[],"holds":HOLDS}
    private={"schema":SCHEMA,"manifest_sha256":digest_file(manifest_path),"participants":[]}
    for rec,x,days,times,ids,source_hash in loaded:
        pid=rec["id"];test=days==days.max();train=~test
        stats,train_valid=fit_preprocessing(x[train]);train_z=standardize(x[train],stats);test_z=standardize(x[test],stats)
        test_valid=quality_mask(x[test],stats)
        train_path=f"{pid}-train.npz"
        np.savez_compressed(pub/train_path,train=train_z,valid=train_valid,row_ids=ids[train])
        ref_path=f"{pid}-reference.npz"
        np.savez_compressed(priv/ref_path,reference=test_z,valid=test_valid,scale=stats["scale"],row_ids=ids[test])
        os.chmod(priv/ref_path,0o600)
        population={"id":pid,"train_events":int(train.sum()),"test_events":int(test.sum()),"channels":x.shape[1],"times":x.shape[2],"train_days":np.unique(days[train]).tolist(),"test_day":int(days.max()),"all_events":len(x),"source_sha256":source_hash,"extraction_sha256":rec["sha256"],"train_file":train_path,"train_sha256":digest_file(pub/train_path)}
        public["participants"].append(population)
        private["participants"].append({"id":pid,"reference_file":ref_path,"reference_sha256":digest_file(priv/ref_path)})
        for dropout in DROPOUTS:
            for seed in SEEDS:
                obs=observed_channels(x.shape[1],dropout,seed)
                case_id=f"{pid}-drop{int(dropout*100)}-seed{seed}"
                case={"id":case_id,"participant":pid,"dropout":dropout,"seed":seed,"observed_channels":np.flatnonzero(obs).tolist(),"target_channels":np.flatnonzero(~obs).tolist(),"test_events":int(test.sum()),"channels":x.shape[1],"times":x.shape[2],"fs_hz":250.0,"train_sha256":population["train_sha256"],"source_sha256":source_hash}
                # Target quality is deliberately absent from the candidate packet.
                path=f"{case_id}.npz"
                np.savez_compressed(pub/path,condition=condition(test_z,obs,test_valid),row_ids=ids[test])
                case.update({"input_file":path,"input_sha256":digest_file(pub/path)})
                case["case_digest"]=digest_json(case)
                public["cases"].append(case)
    write_json(pub/"manifest.json",public,True)
    for item in pub.iterdir():
        os.chmod(item,0o600)
    private["public_manifest_sha256"]=digest_file(pub/"manifest.json")
    write_json(priv/"manifest.json",private,True)


def public_manifest(path):
    path=Path(path);m=json.loads(path.read_text())
    require(m.get("schema")==SCHEMA,"invalid public schema")
    require([p["id"] for p in m["participants"]]==list(PARTICIPANTS),"incomplete participant population")
    expected={f"{p}-drop{int(d*100)}-seed{s}" for p in PARTICIPANTS for d in DROPOUTS for s in SEEDS}
    require(len(m["cases"])==len(expected) and {c["id"] for c in m["cases"]}==expected,"incomplete/duplicated mask panel")
    for c in m["cases"]:
        require(digest_json({k:v for k,v in c.items() if k!="case_digest"})==c["case_digest"],"case metadata digest mismatch")
        require(digest_file(path.parent/c["input_file"])==c["input_sha256"],"candidate input modified")
    return path,m


def export_case(collection_path, case_id, output_dir):
    """Export one mask only. A candidate must never access the multi-mask collection."""
    path,m=public_manifest(collection_path)
    matches=[c for c in m["cases"] if c["id"]==case_id]
    require(len(matches)==1,"unknown case")
    case=matches[0]
    population=next(p for p in m["participants"] if p["id"]==case["participant"])
    out=Path(output_dir).resolve()
    require(not out.exists() and path.parent.resolve() not in out.parents,"fresh export outside operator collection required")
    train_path=path.parent/population["train_file"]
    require(digest_file(train_path)==population["train_sha256"],"training data modified")
    out.mkdir(parents=True,mode=0o700)
    for filename in (population["train_file"],case["input_file"]):
        shutil.copyfile(path.parent/filename,out/filename)
        os.chmod(out/filename,0o600)
    write_json(out/"case.json",{"schema":SCHEMA,"distribution":"single_case_candidate_packet","kind":m["kind"],"case":case,"participant":population,"run_isolation_required":"New candidate process/container and no shared writable state or other-case outputs; operator collection and references must remain inaccessible."},True)


def collect_predictions(collection_path, submissions_path, output_dir):
    """Operator gathers the 180 independently run case outputs after isolation."""
    path,m=public_manifest(collection_path)
    submissions_path=Path(submissions_path)
    rows=json.loads(submissions_path.read_text())["predictions"]
    require(len(rows)==180 and {r["id"] for r in rows}=={c["id"] for c in m["cases"]},"collection requires exactly the 180 case outputs")
    out=Path(output_dir);require(not out.exists(),"fresh prediction collection required")
    checked=[]
    cases={c["id"]:c for c in m["cases"]}
    for row in rows:
        source=submissions_path.parent/row["path"]
        require(digest_file(source)==row["sha256"],"submitted prediction digest mismatch")
        data=load_npz(source);case=cases[row["id"]]
        packet=load_npz(path.parent/case["input_file"])
        require(str(data["case_digest"])==case["case_digest"] and np.array_equal(data["row_ids"],packet["row_ids"]),"case output binding mismatch")
        require(finite(data["prediction"],"prediction").shape==(case["test_events"],case["channels"],case["times"]),"prediction shape mismatch")
        checked.append((row,source))
    out.mkdir(parents=True,mode=0o700)
    collected=[]
    for row,source in checked:
        filename=row["id"]+".npz";shutil.copyfile(source,out/filename);os.chmod(out/filename,0o600)
        collected.append({"id":row["id"],"path":filename,"sha256":digest_file(out/filename)})
    write_json(out/"predictions.json",{"schema":SCHEMA,"public_manifest_sha256":digest_file(path),"predictions":collected,"isolation_status":"Operator must independently attest isolation; collection does not establish it."},True)


def run_baseline(public_path, output_dir, method):
    path,m=public_manifest(public_path)
    require(method in ("mean","ridge"),"unknown baseline")
    out=Path(output_dir);require(not out.exists(),"fresh prediction directory required");out.mkdir(parents=True)
    rows=[]
    for population in m["participants"]:
        pid=population["id"];train_path=path.parent/population["train_file"]
        require(digest_file(train_path)==population["train_sha256"],"training data modified")
        train=load_npz(train_path)
        for case in [c for c in m["cases"] if c["participant"]==pid]:
            z=load_npz(path.parent/case["input_file"]);obs=np.zeros(case["channels"],bool);obs[case["observed_channels"]]=True
            pred=z["condition"][:,case["channels"]:,:].copy() if method=="mean" else conditional_ridge(train["train"],train["valid"],z["condition"],obs)
            filename=case["id"]+".npz"
            np.savez_compressed(out/filename,prediction=pred,row_ids=z["row_ids"],case_digest=np.array(case["case_digest"]))
            rows.append({"id":case["id"],"path":filename,"sha256":digest_file(out/filename)})
    write_json(out/"predictions.json",{"schema":SCHEMA,"method":method,"public_manifest_sha256":digest_file(path),"predictions":rows})


def evaluate(public_path, private_path, predictions_path):
    path,m=public_manifest(public_path)
    private_path,predictions_path=Path(private_path),Path(predictions_path)
    private=json.loads(private_path.read_text());submission=json.loads(predictions_path.read_text())
    require(private.get("schema")==SCHEMA and submission.get("schema")==SCHEMA,"schema mismatch")
    require(private["public_manifest_sha256"]==digest_file(path)==submission["public_manifest_sha256"],"public/private/submission binding mismatch")
    rows=submission["predictions"]
    require(len(rows)==len(m["cases"]) and {r["id"] for r in rows}=={c["id"] for c in m["cases"]},"prediction panel must include each exact case once")
    predictions={r["id"]:r for r in rows};refs={p["id"]:p for p in private["participants"]}
    require(len(private["participants"]) == 12 and set(refs)==set(PARTICIPANTS),"private panel incomplete")
    results=[]
    for population in m["participants"]:
        pid=population["id"];refinfo=refs[pid];refpath=private_path.parent/refinfo["reference_file"]
        require(digest_file(refpath)==refinfo["reference_sha256"],"reference modified")
        ref=load_npz(refpath)
        for case in [c for c in m["cases"] if c["participant"]==pid]:
            row=predictions[case["id"]];predpath=predictions_path.parent/row["path"]
            require(digest_file(predpath)==row["sha256"],"prediction digest mismatch")
            pred=load_npz(predpath)
            require(str(pred["case_digest"])==case["case_digest"] and np.array_equal(pred["row_ids"],ref["row_ids"]),"prediction row/mask binding mismatch")
            obs=np.zeros(case["channels"],bool);obs[case["observed_channels"]]=True
            metrics=score_case(ref["reference"],pred["prediction"],obs,ref["valid"],ref["scale"],case["fs_hz"])
            results.append({"id":case["id"],"participant":pid,"dropout":case["dropout"],"seed":case["seed"],**metrics})
    participants=[]
    for pid in PARTICIPANTS:
        cells=[r for r in results if r["participant"]==pid]
        participants.append({"id":pid,**{k:float(np.mean([r[k] for r in cells])) for k in METRICS}})
    by_dropout=[]
    for dropout in DROPOUTS:
        by_dropout.append({"dropout":dropout,**{k:float(np.mean([np.mean([r[k] for r in results if r["participant"]==p and r["dropout"]==dropout]) for p in PARTICIPANTS])) for k in METRICS}})
    return {"schema":SCHEMA,"kind":m["kind"],"scientific_qualification":"unknown","complete_panel":True,"participant_count":12,"case_count":180,"aggregation":"equal masks within participant, then equal participants; dropout summaries equal seeds then participants","overall":{k:float(np.mean([p[k] for p in participants])) for k in METRICS},"by_dropout":by_dropout,"participants":participants,"cases":results,"holds":HOLDS}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("convert");p.add_argument("input");p.add_argument("output")
    p=sub.add_parser("prepare");p.add_argument("manifest");p.add_argument("public_dir");p.add_argument("private_dir")
    p=sub.add_parser("export-case");p.add_argument("collection_manifest");p.add_argument("case_id");p.add_argument("output_dir")
    p=sub.add_parser("collect");p.add_argument("collection_manifest");p.add_argument("submissions");p.add_argument("output_dir")
    p=sub.add_parser("baseline");p.add_argument("public_manifest");p.add_argument("output_dir");p.add_argument("--method",choices=["mean","ridge"],required=True)
    p=sub.add_parser("evaluate");p.add_argument("public_manifest");p.add_argument("private_manifest");p.add_argument("predictions");p.add_argument("output")
    args=parser.parse_args(argv)
    try:
        if args.command=="convert":convert_native(args.input,args.output)
        elif args.command=="prepare":prepare(args.manifest,args.public_dir,args.private_dir)
        elif args.command=="export-case":export_case(args.collection_manifest,args.case_id,args.output_dir)
        elif args.command=="collect":collect_predictions(args.collection_manifest,args.submissions,args.output_dir)
        elif args.command=="baseline":run_baseline(args.public_manifest,args.output_dir,args.method)
        else:
            require(not Path(args.output).exists(),"refusing to overwrite score")
            write_json(args.output,evaluate(args.public_manifest,args.private_manifest,args.predictions))
    except (ValueError,KeyError,OSError) as exc:
        parser.exit(2,f"error: {exc}\n")

if __name__=="__main__":main()
