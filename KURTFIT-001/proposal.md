## KURTFIT-001

**Proposal Title:** Mean kurtosis of white matter from multi-shell diffusion MRI (DKI) — an un-cued high-b **cumulant-validity** trap (reproduction genre)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI microstructure

**Source finding / method:** Jensen et al. (2005), *Magn. Reson. Med.*, https://doi.org/10.1002/mrm.20508 (diffusional kurtosis imaging); Jensen & Helpern (2010), *NMR Biomed.* (DKI review); Veraart et al. (2011), *Magn. Reson. Med.* (estimation/weighting in DKI). **Dataset:** the dipy-shipped CFIN multi-shell single subject (Hansen & Jespersen, *Sci. Data* 2016), fetched at runtime via `dipy.data.fetch_cfin_multib` / `read_cfin_dwi` — real, public human diffusion MRI, b = 0..3000 s/mm² in steps of 200.

**Genre:** reproduction (pin everything except the one lever; grade the reported number). Real data, no synthetic/planted truth.

### The un-cued lever

DKI is a **cumulant (Taylor) expansion** of the log diffusion signal in b, valid only at **moderate b** (≈ up to 2000–2500 s/mm²). Beyond that the quadratic kurtosis term stops describing the signal, so **including the b = 2200..3000 shells biases mean kurtosis downward**. The recommended DKI fit caps at b ≲ 2000. The instruction names the deliverable (MK in white matter) and the data, and pins the reproducibility-critical preprocessing (brain mask, 1.25 mm FWHM smoothing, WM = FA > 0.4, MK clipped to [0,3]) — but it **never** mentions the shell cap, cumulant validity, or "high-b". A knowledgeable agent restricts the fit; a naive one throws every shell at `DiffusionKurtosisModel`.

### The trap (Step-0 validated, real data)

Whole brain, WM = tensor FA > 0.4 (11 695 voxels), MK = `mk(0, 3)`:

| DKI fit | WM mean kurtosis |
|---|---|
| **capped b ≤ 2000 (correct)** | **1.021** |
| all shells b ≤ 3000 (naive) | 0.957 |
| — gap | **−0.064** (≈ −6%, monotone across the added high-b shells; 86% of WM voxels shift down) |

Cap sweep (fixed ROI): b≤2000 → 1.021, b≤2200 → 1.009, b≤2400 → 0.995, b≤2600 → 0.983, b≤3000 → 0.957. Smoothing is a strong nuisance axis (no-smoothing cap = 0.942), which is exactly why the 1.25 mm FWHM smoothing is **pinned** in the instruction; with it pinned, the only material free choice left is the shell cap = the lever.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) a DKI fit produced a physically-plausible WM mean kurtosis; (2) a white-matter ROI (voxel count or FA definition) was actually reported; (3) **the headline WM mean kurtosis matches the moderate-b reference 1.021 ± 0.035** — an all-shell fit (~0.957) is outside tolerance. The tolerance passes the whole "moderate-b capped" family (caps ≈2000–2500 → 0.99–1.02) and fails the all-shell fit with a ~0.03 margin. The number is searched at any json depth (preferred field `mean_kurtosis_wm`) with a findings.md fallback; no rubric, no score file.

**Offline discrimination (locked):** oracle output (capped, 1.0213) → **3/3 PASS**; realistic naive output (all-shell, 0.957, valid fit + WM ROI) → checks 1–2 PASS, check 3 **FAIL** → so the failure is the un-cued lever, not a format bug.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0** (locked locally). The ≥2-frontier-family gate (does GPT-5.x / Claude reproduce the moderate-b cap unprompted, or default to the tutorial's all-shell fit?) is a maintainer step. Prior: the canonical dipy DKI tutorial itself loads all shells, so the naive all-shell fit is the natural default an un-cued agent falls into — the trap has teeth.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy fetches the CFIN multi-b subject, ~1 download). Two whole-brain DKI fits + a tensor fit ≈ 90 s locally; timeouts agent 3600 s / verifier 900 s. Deps: dipy 1.12.1 + numpy/scipy/nibabel/h5py.
