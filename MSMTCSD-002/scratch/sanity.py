import json, sys, time
from pathlib import Path
import numpy as np
ROOT = Path("/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/MSMTCSD-002")
sys.path.insert(0, str(ROOT / "solution"))
sys.path.insert(0, str(ROOT / "synth_build"))
import msmt_pipeline as P
import generate_fixtures as G
DATA = ROOT / "environment" / "data"

for sid, cfg in G.COHORT.items():
    mask, bvals, bvecs, sig, planted = G.build_subject(sid, cfg)
    label = planted["label"]
    counts = {t: int(((mask) & (label == lab)).sum()) for t, lab in [("GM",1),("WM",2),("CSF",3)]}
    t0 = time.time()
    subj = P.load_subject(DATA / sid)
    res = P.analyze(subj)
    dt = time.time() - t0
    m = res["mask"]
    print(f"\n=== {sid} ntissue={res['ntissue']} lmax={res['lmax']} dropped={res['dropped']} "
          f"labelcounts={counts} time={dt:.1f}s ===")
    for t, fk in [("WM","aWM"),("GM","fGM"),("CSF","fCSF")]:
        if t == "GM" and res["ntissue"] < 3:
            print(f"  {t}: OMITTED (2-tissue)"); continue
        got = res["fracs"][t]; ref = planted[fk]
        err = np.abs(got[m] - ref[m])
        print(f"  {t}_frac: median|err vs planted|={np.median(err):.4f} max={np.max(err):.4f} "
              f"  mean got={got[m].mean():.3f} planted={ref[m].mean():.3f}")
    # peaks summary
    npk = res["npeak"][m]
    wmv = (mask & (label==2))[m]
    print(f"  peaks: voxels w/ >=1 peak={int((npk>=1).sum())}/{m.sum()}  "
          f"WM-voxel peak dist: 0={(npk[wmv]==0).sum()} 1={(npk[wmv]==1).sum()} 2={(npk[wmv]==2).sum()} 3={(npk[wmv]==3).sum()}")
