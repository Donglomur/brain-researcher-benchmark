"""Real-data arterial-input kinetic method case with documented decay footing.
Activity sampling times do not establish activity decay correction status.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
from input_contract import parent_input

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DATASET = "ds005619"
SNAPSHOT = "1.1.0"
SUBJECTS = ["sf02", "sf05", "sf06", "sf07", "sf08", "sf09", "sf10"]
SESSION = "ses-baseline"
HALFLIFE_MIN = 109.771            # 18F
LAMBDA = np.log(2.0) / HALFLIFE_MIN
TSTAR_MIN = 30.0                  # Logan/MA1 linear-phase start
API = "https://openneuro.org/crn/datasets/{ds}/snapshots/{tag}/files/{colon}"


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"dataset": DATASET, "snapshot": SNAPSHOT, "status": "failed_precondition",
         "reason": reason, "target_region": "cerebral_cortex",
         "quantity": "VT", "model": "Logan (arterial input)"}, indent=2))
    (OUT / "findings.md").write_text(
        "# PETVT-001 -- failed precondition\n\n" + reason + "\n")
    (OUT / "vt_estimates.csv").write_text(
        "subject,session,target,input,model,VT\n")
    print("failed_precondition:", reason, file=sys.stderr)
    sys.exit(1)


def fetch(colon_path):
    url = API.format(ds=DATASET, tag=SNAPSHOT, colon=colon_path)
    req = urllib.request.Request(url, headers={"User-Agent": "petvt/1.0"})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def parse_tsv(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    hdr = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        parts = ln.split("\t")
        rows.append([float(x) if x not in ("", "n/a", "NA") else np.nan for x in parts])
    return hdr, np.array(rows, dtype=float)


def _cumtrapz0(t, y):
    out = np.zeros_like(y)
    out[1:] = np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(t))
    return out


def logan_vt(tmid, CT, tin, Cin, tstar):
    tg = np.arange(0.0, tmid[-1] + 0.02, 0.02)
    Cg = np.interp(tg, tin, Cin, left=0.0, right=Cin[-1])
    intCp = np.interp(tmid, tg, _cumtrapz0(tg, Cg))
    intCT = _cumtrapz0(tmid, CT)
    with np.errstate(divide="ignore", invalid="ignore"):
        x = intCp / CT
        y = intCT / CT
    m = (tmid >= tstar) & np.isfinite(x) & np.isfinite(y)
    A = np.vstack([x[m], np.ones(m.sum())]).T
    slope = np.linalg.lstsq(A, y[m], rcond=None)[0][0]
    return float(slope)


def ma1_vt(tmid, CT, tin, Cin, tstar):
    # Ichise MA1: for t >= t*, CT(t) = -(VT/b) * int Cp + (1/b) * int CT
    tg = np.arange(0.0, tmid[-1] + 0.02, 0.02)
    Cg = np.interp(tg, tin, Cin, left=0.0, right=Cin[-1])
    intCp = np.interp(tmid, tg, _cumtrapz0(tg, Cg))
    intCT = _cumtrapz0(tmid, CT)
    m = tmid >= tstar
    A = np.vstack([intCp[m], intCT[m]]).T
    coef = np.linalg.lstsq(A, CT[m], rcond=None)[0]
    return float(-coef[0] / coef[1])


def load_subject(sub):
    blood_colon = ":".join([f"sub-{sub}", SESSION, "pet",
                            f"sub-{sub}_{SESSION}_trc-sf51_recording-manual_blood.tsv"])
    tac_colon = ":".join(["derivatives", "petprep_extract_tacs", f"sub-{sub}", SESSION,
                          f"sub-{sub}_{SESSION}_trc-sf51_desc-gtmseg_tacs.tsv"])
    bh, bd = parse_tsv(fetch(blood_colon))
    th, td = parse_tsv(fetch(tac_colon))
    bi = {c: bd[:, i] for i, c in enumerate(bh)}
    for k in ("time", "plasma_radioactivity", "metabolite_parent_fraction",
              "whole_blood_radioactivity"):
        if k not in bi:
            raise KeyError(f"blood file for {sub} missing column {k}")
    tb = bi["time"]
    plasma = bi["plasma_radioactivity"]
    parent = bi["metabolite_parent_fraction"]
    # drop zero-padding rows (time==0 after the first sample) and NaNs, sort by time
    keep = ~((tb == 0) & (np.arange(len(tb)) > 0)) & np.isfinite(plasma) & np.isfinite(parent)
    tb, plasma, parent = tb[keep], plasma[keep], parent[keep]
    order = np.argsort(tb)
    tb, plasma, parent = tb[order], plasma[order], parent[order]
    tb_min = tb / 60.0
    receipt_path=Path(os.environ.get("BLOOD_DECAY_RECEIPT","/app/data/blood_decay_receipt.json"))
    receipt=json.loads(receipt_path.read_text())
    evidence=receipt[sub]
    if not evidence.get("source"):
        raise ValueError("failed_precondition: source evidence for blood decay footing missing")
    Cp=parent_input(plasma,parent,tb_min,evidence["blood_activity_reference"],LAMBDA)

    fi = {c: i for i, c in enumerate(th)}
    if "frame_start" not in fi or "frame_end" not in fi:
        raise KeyError(f"TAC file for {sub} missing frame timing")
    tmid = ((td[:, fi["frame_start"]] + td[:, fi["frame_end"]]) / 2.0) / 60.0
    ctx_cols = [c for c in th if c.startswith("ctx-")]
    if len(ctx_cols) < 30:
        raise KeyError(f"TAC file for {sub} has too few cortical regions ({len(ctx_cols)})")
    CTX = np.mean([td[:, fi[c]] for c in ctx_cols], axis=0)
    return tb_min, Cp, tmid, CTX


def main():
    rows = []
    try:
        for sub in SUBJECTS:
            tb_min, Cp, tmid, CTX = load_subject(sub)
            vt_logan = logan_vt(tmid, CTX, tb_min, Cp, TSTAR_MIN)
            vt_ma1 = ma1_vt(tmid, CTX, tb_min, Cp, TSTAR_MIN)
            rows.append(dict(subject=f"sub-{sub}", session=SESSION,
                             target="cerebral_cortex",
                             input="metabolite_corrected_arterial_plasma",
                             model="Logan", VT=vt_logan, VT_MA1=vt_ma1))
    except Exception as e:  # noqa: BLE001
        fail(f"could not fetch/parse ds005619 SF51 TACs + arterial blood: {e!r}")

    if len(rows) != 7:
        fail(f"only {len(rows)} subjects usable; expected the 7-participant cohort")

    hdr = ["subject", "session", "target", "input", "model", "VT", "VT_MA1"]
    lines = [",".join(hdr)]
    for r in rows:
        lines.append(",".join(f"{r[h]:.6f}" if isinstance(r[h], float) else str(r[h])
                              for h in hdr))
    (OUT / "vt_estimates.csv").write_text("\n".join(lines) + "\n")

    vts = np.array([r["VT"] for r in rows])
    mean_vt = float(vts.mean())
    ratio = float(vts.max() / vts.min())

    (OUT / "run_metadata.json").write_text(json.dumps({
        "dataset": DATASET, "snapshot": SNAPSHOT, "status": "ok",
        "tracer": "[18F]SF51 (TSPO)", "target_region": "cerebral_cortex",
        "quantity": "VT (total distribution volume, mL/cm3)",
        "input_function": "metabolite-corrected arterial plasma, decay-referenced to injection",
        "model": "Logan graphical (Ichise MA1 cross-check)", "tstar_min": TSTAR_MIN,
        "n_subjects": len(rows),
        "cortex_VT_mean": round(mean_vt, 4),
        "cortex_VT_per_subject": {r["subject"]: round(r["VT"], 4) for r in rows},
        "VT_max_over_min": round(ratio, 3),
    }, indent=2))

    per = "\n".join(f"- {r['subject']}: V_T = {r['VT']:.3f} (MA1 {r['VT_MA1']:.3f})"
                    for r in rows)
    (OUT / "findings.md").write_text(f"""# SF51 cortical V_T method case

Per-subject Logan/MA1 estimates are retained. Mean corticalV_T={mean_vt:.3f}mL/cm³
across{len(rows)}participants. Input is arterial plasma×parent fraction with
source-documented decay footing consistent with PET TACs. Sampling times alone
do not justify a further activity correction. This secondary model/input method
case does not establish genotype effects, original-paper exact findings, or
poor binding from an unverified low V_T. Missing decay evidence is a precondition
failure, not an invitation to choose a secret estimator.
""")
    print("OK cortex VT mean =", round(mean_vt, 3), "ratio =", round(ratio, 2))


if __name__ == "__main__":
    main()
