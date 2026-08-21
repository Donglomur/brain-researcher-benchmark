"""Inspect R21 on sub-05's 2-fibre voxels for BOTH impls: is R21 sitting near 0.45?"""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path("/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/NODDIBAYES-002")
sys.path.insert(0, str(ROOT / "solution")); sys.path.insert(0, str(ROOT / "synth_build"))
sys.path.insert(0, str(ROOT / "validation"))
import bas_ref as R, bas_pipeline as P, generate_fixtures as G

sid = "sub-05"
subj = P.load_subject(ROOT / "environment" / "data" / sid)
res = P.analyze(subj)
mask = res["mask"]; _, vtype, _, _, _, planted, _ = G.build_subject(sid, G.COHORT[sid])
bvals, bvecs, dwi = subj["bvals"], subj["bvecs"], subj["dwi"]
s0 = R.estimate_s0(dwi, bvals); norm = dwi / np.clip(s0, 1e-9, None)[None, :]
dropped = res["dropped_volumes"]; keep = np.ones(dwi.shape[0], bool)
for w in dropped: keep[w] = False
bk, gk, nk = bvals[keep], bvecs[keep], norm[keep]
dfix = None

# reference R21 distribution over TRUE 2-fibre voxels
idx = np.where(mask & (planted["count"] == 2))[0]
r21s = []
for i in idx:
    meas = nk[:, i]
    s0v, _ = R._sse0(meas, bk, dfix)
    rank1 = R._coarse_rank(meas, bk, gk); r1 = R._fit(meas, bk, gk, 1, dfix, [rank1[0]])
    _, st1, sse1 = R._parse(r1, 1, dfix)
    rank2 = R._coarse_rank(meas, bk, gk, exclude=st1[0][1], min_sep_cos=np.cos(np.radians(35)))
    r2 = R._fit(meas, bk, gk, 2, dfix, [st1[0][1], rank2[0]]); _, st2, sse2 = R._parse(r2, 2, dfix)
    r21 = (sse1 - sse2) / max(sse1, 1e-12)
    r21s.append(r21)
r21s = np.array(r21s)
print(f"sub-05 REFERENCE R21 over true-2-fibre voxels: min={r21s.min():.3f} p5={np.percentile(r21s,5):.3f} "
      f"p25={np.percentile(r21s,25):.3f} median={np.median(r21s):.3f}  (threshold=0.45)")
print(f"  fraction with R21 in [0.45,0.55] (thin margin): {np.mean((r21s>=0.45)&(r21s<0.55)):.2f}")
print(f"  fraction below 0.45 (ref would prune!): {np.mean(r21s<0.45):.2f}")
