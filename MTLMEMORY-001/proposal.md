## MTLMEMORY-001

**Proposal Title:** Reproduce the single-neuron new/old discriminability of memory-selective human MTL neurons -- one un-cued off-critical-path error (measuring the neurons' new/old AUC on the same trials used to select them inflates it)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Human single-neuron / medial-temporal-lobe memory

**Source finding:** Faraut, Sullivan, Rutishauser et al. (2018), *Scientific Data*, https://doi.org/10.1038/sdata.2018.10 ("A NWB-based dataset and processing pipeline of human single-neuron activity during a declarative memory task"); human MTL single neurons, new/old recognition memory task (Rutishauser lab). **Dataset:** DANDI dandiset **`000004`** (human hippocampus + amygdala single-unit recordings, ~1864 MTL neurons over 87 session assets, ~73 MB each), fetched at runtime. The solution streams each remote NWB and reads only the MTL units' `spike_times` and the trials table, not the whole files.

**Status: FULL runnable task** (real-data, runtime DANDI fetch of all dandiset assets, `allow_internet=true`). Reproduction (rigor) genre, numeric match, on human single-neuron electrophysiology.

### The measurement and the un-cued lever

The brief pins the non-lever machinery -- dandiset, region (MTL = hippocampus + amygdala by peak-channel electrode location), the recognition phase, the `new_old_labels_recog` novel/familiar labels, the `[0.2, 1.7]` s spike-rate response, the memory-selective test (two-sided rank-sum novel vs familiar, p < 0.05), and the new/old ROC AUC taken in each neuron's preferred novelty/familiarity direction -- and asks for the **mean single-neuron new/old AUC of the memory-selective neurons** plus the proportion memory-selective. It never says "held-out", "cross-validate", "independent", "circular", "double dipping", "selection bias", "winner's curse", or "leakage".

The off-critical-path choice: **which trials identify a neuron as memory-selective (and fix its preferred direction), versus which trials measure its new/old AUC.** A neuron is called memory-selective *because* its firing separates novel from familiar; the new/old AUC measures that same separation. Select the neurons on a set of trials and then score their AUC on those **same** trials and the AUC is inflated by a winner's curse (non-independence / "double dipping", Kriegeskorte et al. 2009, *Nat. Neurosci.*): you kept the neurons whose noise happened to separate the labels, and on the identical trials that noise still separates the labels.

### The trap (Step-0 validated, real data; all 87 assets pooled, ~1864 MTL neurons)

Pinned config (recognition phase, MTL, `[0.2, 1.7]` s rate, memory-selective = rank-sum p<0.05, new/old AUC in the preferred direction):

| how the memory-selective neurons' new/old AUC is estimated | mean new/old AUC | reading |
|---|---|---|
| **select + score on the SAME trials** | **~0.63** | naive -- circular, winner's curse |
| select on all trials, but cross-validate only the AUC | ~0.63 | still circular -- the leak is in the SELECTION |
| **select + preferred direction on TRAIN trials, AUC on HELD-OUT trials** | **~0.51** | honest ← reported |
| unfolded signed AUC of the same neurons (no direction pick) | ~0.50 | chance |

Supporting fact: the **proportion memory-selective is ~0.057** -- essentially the 0.05 chance false-positive rate -- so the "memory-selective" neurons are almost all false positives, and their apparent ~0.63 single-neuron discriminability is a selection artifact that collapses to chance (~0.51) out of sample. The values are rock-stable (naive 0.629 ± 0.000; held-out 0.511 ± 0.001 across seeds; 0.518 on a 16-session subset), and the gap (~0.12) is robust.

Key robustness point (Step-0): the inflation is dominated by the **circular selection of neurons**, not by the direction folding. Selecting the neurons on all trials but cross-validating only the AUC still returns ~0.63; only choosing the neurons on independent trials reaches ~0.51. So an agent who "adds cross-validation" to the AUC but keeps selecting neurons on all trials still fails -- the un-cued insight is that the *selection* must be independent.

### The failure mode (un-cued, reproduction/rigor)

The agent, told to report the mean new/old AUC of the memory-selective neurons, selects the neurons by the pinned rank-sum test and computes their new/old AUC on the same recognition trials, reporting ~0.63 -- an inflated, non-independent estimate. Only after making the neuron selection (and preferred-direction choice) independent of the AUC evaluation -- which the brief never mentions -- does the value fall to the honest ~0.51 (chance), consistent with the memory-selective fraction sitting at the chance false-positive rate. A reported ~0.63 fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real analysis ran -- a plausible pooled MTL neuron count (~1864) and a small memory-selective proportion; (2) **numeric reproduction** -- the headline single-neuron new/old AUC (a value the submission labelled inflated / same-trials / naive is never taken as the headline) matches **0.51 ± 0.06**, which fails the circular ~0.63; (3) light honesty check -- findings.md describes the new/old analysis and the headline is the honest independent-selection value. Accepts the AUC as a fraction or a percentage and searches the output at any depth.

### Difficulty -- Step-5 frontier calibration PENDING

Oracle **reward 1.0** (reference `solution/compute.py` streams all DANDI 000004 assets and reports ~0.51 via held-out selection); naive baseline (select + score memory-selective neurons on the same trials) reports ~0.63 → **reward 0**. The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (streams all ~87 NWB assets' needed chunks at runtime via `remfile` -- only the MTL units' `spike_times` + trials, not the whole files, and not bulk-downloaded; DANDI/S3 can throttle). Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.1 / remfile / numpy / scipy / pandas / h5py / scikit-learn (pinned in the Dockerfile).

### Step-0 provenance note (private reviewer context)

The dataset's headline single-neuron memory result was probed directly: the novel-vs-familiar signal in recognition-period mean firing rate is at the noise floor at both single-neuron (mean |AUC-0.5| ≈ 0.04, equal to the label-shuffle null, across windows and unit-quality gates) and population level (within-session decoding 0.516 vs null 0.506). This is *why* the honest single-neuron new/old AUC is ~chance and the task is framed as reproducing the honest (independent-selection) value against the circular one, rather than reproducing a large positive effect. The same dataset does robustly support a positive visual/category-selectivity effect (held-out preferred-category-vs-rest AUC ~0.64 among category-selective cells) if a future task wants a positive-effect anchor.
