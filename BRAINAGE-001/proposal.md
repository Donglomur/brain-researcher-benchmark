## BRAINAGE-001

**Proposal Title:** The brain-age gap — an un-cued regression-to-the-mean / age-bias confound (the *regression-to-the-mean / selection* failure axis — NEW)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Brain-age / imaging biomarkers

**Source finding:** Franke et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.01.005 ("BrainAGE" — predict age from structural MRI; the predicted−chronological "brain-age gap" is a biomarker of accelerated/decelerated ageing). Un-cued check / bias correction: de Lange & Cole (2020), *NeuroImage: Clinical*; Smith et al. (2019). Data: `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **NEW failure axis — regression to the mean / selection** (statistical-inference family) — which the drops-log had listed as an OPEN axis believed to require *longitudinal* data. It is reproduced here **purely cross-sectionally**. Found by the 111-topic Step-0 sweep (topics *prediction / brain age / normative modeling* all point to this one trap).

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
The brain-age gap is one of the most-used imaging biomarkers, and it is routinely interpreted (correlated with disease, cognition, risk) **without** the age-bias correction. The un-cued judgement is that the gap is mechanically confounded with chronological age (regression to the mean) and must be corrected before any interpretation.

### The reproduction (Step-0 validated) — a working brain-age model
OASIS VBM, n≈403, cross-validated Ridge on gray-matter maps: **MAE = 11.9 yr, r(predicted, true) = 0.80** — a legitimate brain-age model, reproducing the Franke (2010) BrainAGE paradigm.

### The trap (Step-0 validated) — the gap is age-confounded, and it distorts inference
| quantity | naive gap | after de Lange–Cole bias correction |
|---|---|---|
| corr(brain-age gap, chronological age) | **r = −0.62** (p = 2.5e-44) | **r = 0.00** |
| dementia (CDR>0) vs healthy gap difference | +2.0 yr, p = **0.21 (n.s.)** | +7.9 yr, p = **0.0015 (sig.)** |

Because an imperfect regressor shrinks predictions toward the sample mean, the gap is spuriously, strongly correlated with age — a **regression-to-the-mean** artifact. The uncorrected gap both **manufactures a spurious age association** and **masks the real dementia effect** (non-significant naively, significant after correction). The whole effect is mathematically forced by r(pred,true) < 1; it is robust across smoothing/resolution.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) a brain-age model / gap was computed; (2) `findings.md` recognises the gap is confounded with chronological age (regression to the mean) and must be age-bias-corrected — a flat report of the uncorrected gap over-claims/misleads. Strong-token guard: the recognition must name the RTM / age-bias concept, linked to the gap. Offline: oracle PASS; flat "gap correlates with age, no dementia difference" adversarial FAIL; vague "noisy" adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** brain-age bias correction is known in the biomarker literature; a strong agent may volunteer it → possible easy control. Mitigated by posing a plain "compute the gap and report what it relates to" analysis.
2. **Prose/judgement verifier** (rigor genre) — strong-token + linked-insight guards mitigate false positives; harden against real agent texts at calibration.
3. **Distinct from built tasks:** not effect-size (BWAS), not CV leakage (DECODE), not smoothing (VBMAGE, though same OASIS data) — this is the regression-to-the-mean bias of a *derived* metric, a genuinely new axis.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM gray-matter maps — NITRC host). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel. Oracle runtime ~1-2 min (masker + cross-validated Ridge).
