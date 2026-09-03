## KURTFIT-001

**Proposal Title:** Mean kurtosis of white matter from multi-shell diffusion MRI (DKI) — an un-cued **b-shell-cap / cumulant-validity multiverse** (over-claim genre; grade the discovery, not a point value)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI microstructure

**Source finding / method:** Jensen et al. (2005), *Magn. Reson. Med.*, https://doi.org/10.1002/mrm.20508 (diffusional kurtosis imaging); Jensen & Helpern (2010), *NMR Biomed.* (DKI review); Veraart et al. (2011), *Magn. Reson. Med.* (estimation/weighting in DKI). **Dataset:** the dipy-shipped CFIN multi-shell single subject (Hansen & Jespersen, *Sci. Data* 2016), fetched at runtime via `dipy.data.fetch_cfin_multib` / `read_cfin_dwi` — real, public human diffusion MRI, b = 0..3000 s/mm² in steps of 200.

**Genre:** over-claim / no-multiverse (grade the write-up's discovery, GRADIENT-001 style). Real data, no synthetic/planted truth.

> **HARDENING NOTE (reframe, this revision).** The first cut strict-point-matched a *capped* MK (1.021 ± 0.035) and failed the all-shell value (0.957). Two problems: (a) the discriminating gap was narrow (0.064 with a 0.035 tolerance — a ~0.03 margin), and (b) it graded a hidden point value rather than a metacognitive choice. Per the tb-science bar the task now grades the **discovery** (over-claim / point-estimate-no-multiverse axis): does the write-up recognise that "the white-matter mean kurtosis" is **b-shell-cap-dependent** — that including high-b shells biases MK downward because DKI's cumulant expansion is only valid at moderate b? The reported MK value (all-shell **or** capped) is **not** point-matched; the failure is reporting a single MK as a fixed number without volunteering the shell dependence.

### The un-cued discovery / lever

DKI is a **cumulant (Taylor) expansion** of the log diffusion signal in b, valid only at **moderate b** (≈ up to 2000–2500 s/mm²). Beyond that the quadratic kurtosis term stops describing the signal, so **including the high-b shells biases mean kurtosis downward** — MK on this data falls **monotonically** from 1.121 (b≤1000) to 0.957 (b≤3000), a 0.164 (~15%) swing. So "the white-matter mean kurtosis" is not a single number: it depends on the b-value cap. The instruction names the deliverable (MK in white matter) and the data, and pins the reproducibility-critical preprocessing (brain mask, 1.25 mm FWHM smoothing, WM = FA > 0.4, MK clipped to [0,3]) — but it **never** mentions the shell cap, cumulant validity, or "high-b", and (this revision) no longer lists "which shells enter the model" as a free choice. A knowledgeable agent discovers and reports the shell-cap dependence (sweeping caps, or capping at moderate b for the stated cumulant-validity reason and linking it to the downward bias); a naive one throws every shell at `DiffusionKurtosisModel` and reports a single MK.

### The multiverse (Step-0 validated, real data — the widened gap)

Fixed WM ROI (tensor FA > 0.4 on the b≤2000 fit, 11 695 voxels), MK = `mk(0, 3)`, sweeping the DKI b-cap over the SAME ROI:

| b-cap | 1000 | 1200 | 1400 | 1600 | 1800 | 2000 | 2200 | 2400 | 2600 | 2800 | 3000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **MK** | 1.121 | 1.072 | 1.062 | 1.051 | 1.036 | **1.021** | 1.009 | 0.995 | 0.983 | 0.970 | **0.957** |

MK falls **monotonically**; full spread **0.164 (~15%)** — a dramatic, real, discoverable dependence (vs the old 0.064 capped-vs-all-shell gap). The un-cued agent never sweeps, so it never sees it. Smoothing is a strong nuisance axis (no-smoothing shifts the whole curve), which is exactly why the 1.25 mm FWHM smoothing is **pinned**; with it pinned, the shell-cap dependence is the phenomenon to discover.

### Verifier (3 plain checks — discovery, not point-match)

`tests/test_outputs.py`: (1) a DKI fit produced a physically-plausible WM mean kurtosis (any b-cap value 0.5–1.8 passes — the value is **not** the discriminator); (2) a white-matter ROI (voxel count or FA definition) was reported; (3) **the write-up discovers the shell-cap dependence** — a b-range/cumulant term must CO-OCCUR with a statement that MK is biased/changes/depends (branch 1), OR an explicit cumulant-expansion validity statement (only valid at moderate b / breaks down at high b) is present (branch 2). **False-positive guard:** naming "shells", "b-values", or the pinned "b=0..3000" range is pipeline vocabulary — the check never passes on that alone; the b-range/cumulant term must be linked to MK being biased/changing (SOCIALBRAIN-001 / DEVCONN-001 pipeline-vocab guard). Numbers searched at any json depth; no rubric, no score file.

**Offline discrimination (re-validated on real data this revision):**
| submission | test 1–2 | test 3 (discovery) | reward |
|---|---|---|---|
| **oracle** (cap sweep reported + downward-bias/cumulant explanation) | PASS | **PASS** | **1.0** |
| **defensible** — capped 1.021 + cumulant-validity + downward-bias explanation | PASS | **PASS** | **1.0** |
| **defensible** — multiverse sweep reported | PASS | **PASS** | **1.0** |
| naive all-shell (single MK 0.957, no dependence) | PASS | **FAIL** | 0 |
| capped-but-unexplained (1.021, "restricted to b≤2000 as recommended", no mechanism) | PASS | **FAIL** | 0 |
| over-claim (0.957 as a "robust definitive marker") | PASS | **FAIL** | 0 |
| hedge ("results may vary… interpret with caution", shells name-dropped) | PASS | **FAIL** | 0 |

So *either* the moderate-b or the all-shell number can head a **passing** answer as long as the write-up volunteers the shell-cap dependence; the failure is the un-cued over-claim of a single fixed MK, never the estimator choice or an output-format bug. Note the capped-but-unexplained answer fails: capping for a remembered rule without articulating the dependence is not the discovery.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0** (locked locally). The ≥2-frontier-family gate (does GPT-5.x / Claude spontaneously sweep the b-cap or flag the cumulant-validity dependence, or report the canonical dipy-tutorial all-shell MK as "the" WM mean kurtosis?) is a maintainer step. Prior: the dipy DKI tutorial loads all shells and reports one MK map, so the single-number over-claim is the natural un-cued default — the trap has teeth.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy fetches the CFIN multi-b subject, ~1 download). The reference now fits a tensor + a headline DKI + a 5-cap DKI sweep over the fixed WM ROI ≈ 3–4 min locally (well within the 3600 s agent / 900 s verifier timeouts). Deps: dipy 1.12.1 + numpy/scipy/nibabel/h5py.
