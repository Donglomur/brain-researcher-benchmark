## OPTICALIS-002

**Proposal Title:** Hemoglobin mapping from a heterogeneous optical intrinsic-signal cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Optical intrinsic-signal imaging (OISI)

**Source paper:** Kohl et al. 2000, *Phys. Med. Biol.* (spectroscopic model of cortical intrinsic optical signals); Malonek & Grinvald 1996, *Science* (intrinsic-signal haemoglobin spectroscopy, https://doi.org/10.1126/science.272.5261.551). Dataset: a **synthetic** optical intrinsic-signal imaging cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth hemoglobin maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-pixel dHbO/dHbR/dHbT maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the modified-Beer–Lambert inversion **from scratch** (no solver bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded per-pixel against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. The illumination forks: narrow-band **multi-wavelength** acquisitions invert with the pinned extinction spectra sampled at their wavelengths, while **RGB-camera** acquisitions require a *different* matrix — the camera-spectral-sensitivity-weighted integral of `eps·pathlength` over the whole wavelength grid; applying the discrete matrix to RGB data (via nominal center wavelengths) is wrong. Determinability diverges: most acquisitions have ≥2 spectrally-distinct bands so oxy and deoxy separate, but a couple are **single-wavelength at an isosbestic point** where only the total dHbT is determinable and dHbO/dHbR must be **omitted**.
2. **Coupled-physics assembly** — the log-ratio optical density `dOD = −log10(resp/base)`, the per-subject extinction×pathlength assembly (with `dpf_scale` and, for RGB, the folded integral), the estimability decision, and the OLS inversion in the right units must **all** be correct; ignoring `dpf_scale` or the log base rescales every map.
3. **Hidden robustness** — unannounced and biting a majority of the cohort: gross whole-image illumination-transient frames must be **rejected** before the window means are trustworthy, and specular-saturation and large-vessel pixels — where the MBLL model does not apply — must be **excluded (NaN)**, not inverted to spurious hemoglobin.
4. **Convention-invariant grading** — given the pinned extinction spectra, the log base, and the assembly rule, each graded map is uniquely determined, so two independent correct implementations compute them identically (proven below).

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled reflectance with a **held-out reference** pipeline (`oisi_pipeline` + `oisi_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **per-pixel** over the exposed-cortex mask, one parametrized test per (subject × map) panel — 24 panels total. Reward is **fractional** (fraction of panels correct). A determinable map passes when ≥90% of cortex pixels agree within tolerance (rtol 3%, atol 0.15 µM), where a pixel agrees if **both** values are NaN (the reference blanks specular/vessel pixels) or **both** are finite and close; an undeterminable map (dHbO/dHbR for a single isosbestic wavelength) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (different LS backend, batch sigma-clip transient rejection, own artifact thresholds, closed-form single-band total; **no** import of the reference) reproduces every determinable panel to well within tolerance. The plausible-but-wrong pipelines each fail only their own axis: **discrete matrix on RGB** biases only the RGB subjects; **no omit** fails the single-isosbestic-band panels; **no transient rejection** biases only the flicker subjects; **no specular/vessel mask** fails only the subjects carrying those artifacts; **ln instead of log10** or **ignored dpf_scale** rescales every map. Partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/24 panels**; the failures fall on the task's hard axes — the RGB camera-sensitivity-weighted matrix (vs the discrete-wavelength one), the single-isosbestic-band omit rule, the unannounced illumination-transient rejection, and the specular/large-vessel NaN masking. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model inverts the modified-Beer–Lambert physics on the standard multi-wavelength subjects but does not assemble the RGB camera-sensitivity matrix, apply the isosbestic omit rule, or discover-and-reject the unannounced transient frames and artifact pixels, so the residual failures land on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled per-pixel decisions right with no recipe). `instruction.md` names the deliverable and the optics conventions but never enumerates the pitfalls (the RGB matrix, the transient frames, the artifact pixels) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
