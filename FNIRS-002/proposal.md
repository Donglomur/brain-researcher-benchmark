## FNIRS-002

**Proposal Title:** Haemoglobin concentration changes from a heterogeneous continuous-wave fNIRS cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Functional near-infrared spectroscopy (fNIRS)

**Source paper:** Delpy et al. 1988, *Phys. Med. Biol.* (modified Beer–Lambert law / differential pathlength factor, https://doi.org/10.1088/0031-9155/33/12/008); Bale, Elwell & Tachtsidis 2016, *J. Biomed. Opt.* (broadband NIRS cytochrome-c-oxidase, https://doi.org/10.1117/1.JBO.21.9.091307). Dataset: a **synthetic** continuous-wave fNIRS cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth concentration traces held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce HbO/HbR and, where resolvable, CCO concentration-change traces); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the modified-Beer–Lambert inversion **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need different computations**, with a **hidden robustness** requirement, graded per (channel × chromophore) against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar and the data. Five of eight devices sample **three wavelengths** and resolve a third chromophore (oxidised-minus-reduced cytochrome-c-oxidase, CCO) through a 3×3 solve — and CCO cross-talks into HbO/HbR, so a 2-chromophore fit is biased on those subjects — while the two **two-wavelength** devices resolve only HbO/HbR and the CCO file must be **omitted** entirely. The effective optical pathlength `L = SD_distance · DPF` differs per channel and per wavelength, so the extinction-pathlength matrix must be reassembled for every channel from the pinned base-10 molar extinction table and the sidecar.
2. **Coupled-physics assembly** — the base-10 baseline optical density `dOD = log10(I0/I)`, the wavelength-by-chromophore extinction-pathlength matrix, and the joint linear solve must **all** be assembled correctly; dropping DPF or the log base rescales every concentration, and each realistic mistake compounds across the (subject × channel × chromophore) panels.
3. **Hidden robustness** — every subject is heavily quality-compromised and this is unannounced: of its 8 channels, **three** have grossly poor optode coupling (near-dark, or a railed/flat trace) that carries no recoverable haemoglobin and must be **dropped** (all-NaN), and **two** further channels carry brief gross whole-spectrum motion spikes that must be **flagged** (NaN) rather than converted to spurious concentration — leaving only three clean channels. A majority of the panels are therefore artifact panels; a pipeline that inverts the physics but skips artifact rejection (the observed frontier failure mode) recovers only the clean channels.
4. **Convention-invariant grading** — the solve is exactly determined given the pinned base-10 extinction coefficients, the sidecar DPF/SD-distance and the base-10 dOD definition, so two independent correct implementations compute the traces identically (proven below).

### Verifier

`tests/test_outputs.py` recomputes every concentration trace from the bundled raw intensity with a **held-out reference** pipeline (`fnirs_pipeline` + `fnirs_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **per (subject × channel × chromophore)** over the frames — 171 panels total. Reward is **fractional** (each panel its own test). A good-channel trace passes when ≥90% of usable (non-motion) frames agree within a per-chromophore tolerance (rtol 3%, atol 0.03 µM) and the gross motion frames are handled (non-finite, or kept within a physiological bound); an unusable channel passes only when the submission **drops** it (all-NaN); and CCO passes only when computed for the 3-wavelength devices and **omitted** for the 2-wavelength devices.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (Moore–Penrose pseudo-inverse instead of a per-frame solve, dOD written as `−log10(I/I0)`, its own gross-quality and motion detection; **no** import of the reference) reproduces every computable panel to ~1e-7 µM. The plausible-but-wrong pipelines each fail only their own axis: **ignore-DPF** 66/171, **2-chromophore-fit-on-3-wavelength** 96/171, **force-CCO-on-2-wavelength** 168/171, **ignore-motion** 129/171 (all 42 motion panels), **keep-dead-channels** 108/171 (all 63 must-drop panels). A physics-correct but artifact-blind pipeline (the frontier profile) scores only 66/171 (39%); a lazy all-NaN pipeline also 66/171. Only a submission that both inverts the physics **and** rejects the artifacts passes the majority.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **66/171 panels**; the failures fall on the task's hard axes — the unannounced artifact rejection (dropping the ~3 dead channels per subject and flagging the ~2 motion channels) and the 3-vs-2-wavelength CCO fork. The 66/171 profile is exactly the physics-correct, artifact-blind failure mode (recovers only the clean channels). |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model inverts the modified-Beer–Lambert physics correctly on the clean channels but does not discover-and-reject the unannounced dead and motion channels, so it lands on exactly the physics-correct artifact-blind score of 66/171 rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get a hundred coupled per-channel decisions right with no recipe). `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the dead/motion channels, the CCO fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted traces are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
