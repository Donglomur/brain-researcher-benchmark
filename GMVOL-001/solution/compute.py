"""Reference (oracle) for GMVOL-001 — sex difference in gray-matter volume (OASIS VBM).

Paper anchor: sex differences in brain volume and the head-size correction controversy — Barnes et
al. 2010, NeuroImage (10.1016/j.neuroimage.2010.03.025, proportions vs covariate/ANCOVA correction);
O'Brien et al. 2011, AJNR (statistical adjustment for head size). Men have systematically larger
heads/intracranial volume, so any raw brain-volume sex difference is confounded by head size, and —
critically — the three STANDARD ways to adjust for head size give mutually CONTRADICTORY answers.

The task (un-cued) asks whether total gray-matter volume differs by sex in healthy OASIS adults and
how confident one should be. This reference computes the difference three defensible ways and
VOLUNTEERS the check the task never asks for: the DIRECTION of the sex difference flips depending on
the head-size correction method, so there is no robust GM sex difference beyond head size.
  - RAW total GM:            men > women, d ~ +0.47, t ~ +4.0, p ~ 7e-5   (highly sig, M>F)
  - PROPORTION GM / eTIV:    women > men, d ~ -0.36, t ~ -3.1, p ~ 0.002  (SIGN FLIP, sig, F>M)
  - ANCOVA GM ~ sex + eTIV:  null,        t ~ -1.1,  p ~ 0.27            (no effect after covarying)
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "gm_sex.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import nibabel as nib
    from nilearn.datasets import fetch_oasis_vbm
    from scipy import stats
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

import pandas as pd

try:
    o = fetch_oasis_vbm(n_subjects=403)
except Exception as e:
    fail(f"could not fetch OASIS VBM: {e}")

ev = o.ext_vars if isinstance(o.ext_vars, pd.DataFrame) else pd.DataFrame(o.ext_vars)
cols = {c.lower(): c for c in ev.columns}


def col(*names):
    for n in names:
        if n in cols:
            return cols[n]
    fail(f"missing expected phenotypic column {names}")


sex_c, etiv_c, cdr_c = col("mf", "sex", "gender"), col("etiv", "tiv"), col("cdr")

# total GM per subject = sum of the MODULATED GM map (modulation preserves absolute volume)
try:
    totals = np.array([np.asarray(nib.load(f).dataobj, dtype=np.float32).sum() for f in o.gray_matter_maps])
except Exception as e:
    fail(f"could not read GM maps: {e}")

sex = np.array([str(s).strip().upper() for s in ev[sex_c]])
etiv = pd.to_numeric(ev[etiv_c], errors="coerce").values.astype(float)
cdr = pd.to_numeric(ev[cdr_c], errors="coerce").values

# healthy adults only (CDR == 0), valid values
keep = (np.nan_to_num(cdr, nan=0.0) == 0) & np.isfinite(etiv) & np.isfinite(totals)
isM, isF = (sex == "M") & keep, (sex == "F") & keep
if isM.sum() < 20 or isF.sum() < 20:
    fail(f"too few healthy subjects (M={int(isM.sum())} F={int(isF.sum())})")

gmM, gmF = totals[isM], totals[isF]


def cohend(a, b):
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return float((a.mean() - b.mean()) / sp)


# 1) RAW total GM by sex
t_raw, p_raw = stats.ttest_ind(gmM, gmF)
d_raw = cohend(gmM, gmF)

# 2) PROPORTION GM / eTIV by sex
prop = totals / etiv
t_prop, p_prop = stats.ttest_ind(prop[isM], prop[isF])
d_prop = cohend(prop[isM], prop[isF])

# 3) ANCOVA  GM ~ sex + eTIV
kk = isM | isF
y = totals[kk]
X = np.column_stack([np.ones(kk.sum()), isM[kk].astype(float), etiv[kk]])
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
resid = y - X @ beta
dof = kk.sum() - 3
se = float(np.sqrt((resid @ resid / dof) * np.linalg.inv(X.T @ X)[1, 1]))
t_anc = float(beta[1] / se)
p_anc = float(2 * stats.t.sf(abs(t_anc), dof))

sign_flip = (np.sign(t_raw) != np.sign(t_prop)) and (p_raw < 0.05) and (p_prop < 0.05)

(OUT / "gm_sex.json").write_text(json.dumps({
    "dataset": "OASIS VBM (nilearn fetch_oasis_vbm)",
    "n_male": int(isM.sum()), "n_female": int(isF.sum()),
    "raw_total_gm": {"cohens_d_M_minus_F": d_raw, "t": float(t_raw), "p": float(p_raw),
                     "direction": "M>F" if t_raw > 0 else "F>M"},
    "proportion_gm_over_etiv": {"cohens_d_M_minus_F": d_prop, "t": float(t_prop), "p": float(p_prop),
                                "direction": "M>F" if t_prop > 0 else "F>M"},
    "ancova_gm_sex_plus_etiv": {"beta_sex_M": float(beta[1]), "t": t_anc, "p": p_anc,
                                "direction": "M>F" if t_anc > 0 else "F>M"},
    "direction_flips_with_correction_method": bool(sign_flip),
    "method": "total modulated GM by sex under three standard head-size handling methods",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1, nilearn)",
    "n_male": int(isM.sum()), "n_female": int(isF.sum()),
    "method": "modulated-GM total volume; raw t-test vs proportion(GM/eTIV) t-test vs ANCOVA(GM~sex+eTIV)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# GMVOL-001 — sex difference in gray-matter volume (OASIS VBM)

Healthy adults (CDR = 0): {int(isM.sum())} men, {int(isF.sum())} women. Total gray-matter volume is
the sum of each subject's modulated GM map.

## The direction of the sex difference flips with the head-size correction method
Men have systematically larger heads (intracranial volume), so a raw GM sex difference is confounded
by head size. The three standard ways to handle this give **mutually contradictory** answers on the
**same subjects**:

| Head-size handling | Effect (M vs F) | t | p |
|---|---|---|---|
| **Raw** total GM | **M > F**, d = {d_raw:+.2f} | {t_raw:+.2f} | {p_raw:.2g} |
| **Proportion** GM / eTIV | **F > M**, d = {d_prop:+.2f} | {t_prop:+.2f} | {p_prop:.2g} |
| **ANCOVA** GM ~ sex + eTIV | null, β = {beta[1]:+.0f} | {t_anc:+.2f} | {p_anc:.2g} |

Raw volume says men have **significantly more** GM (p ≈ {p_raw:.0e}); dividing by intracranial volume
**reverses the sign** to women having significantly more (p ≈ {p_prop:.2g}); covarying for eTIV
(ANCOVA) makes the effect **vanish** (p ≈ {p_anc:.2g}). All three are standard, defensible choices.

## Conclusion
There is **no robust sex difference in gray-matter volume** here: the reported direction and
significance are an **artifact of the head-size correction method**, not a stable biological finding.
Proportions and ANCOVA answer different questions and are known to disagree (Barnes 2010; O'Brien
2011). Any single-method claim ("men have more GM" / "women have more GM") over-states the evidence —
the honest report is that the conclusion is not robust to the (arbitrary) correction choice.
""")
print(f"OK: nM={int(isM.sum())} nF={int(isF.sum())}; raw t={t_raw:+.2f}(p{p_raw:.1e}) "
      f"prop t={t_prop:+.2f}(p{p_prop:.2g}) ancova t={t_anc:+.2f}(p{p_anc:.2g}) flip={sign_flip}")
