# AASD report-state evaluation construction, version 1

This independent standard-library package implements evaluator-side report-state labels, fixed common-context eligibility, a complete cohort accounting table, participant/mixture split plans, active and passive scoring, and paired participant uncertainty for `NEURAL-SCOPE-20261114-AASD-REPORT`. It is an executable construction component, not a scientifically qualified benchmark. Native data have not been downloaded or inspected, no decoder has been trained, and the protected execution service is not implemented. The canonical task and its historical identities are unchanged. The registered ID remains `NEURAL-SCOPE-20261114-AASD-REPORT`; its `specification_id` is `HOLD-NEURAL-FRONTIER-AASD-20261114` and `specification_alias` is true. This is one existing task, with no new task or benchmark count.

## Sources and identity

The contract is the task's `task.json`, 16,041 bytes, SHA256 `0ee94e7c532697065e3fe1797c512cf10a8ed08f27f2b63bec8a87150e6b80ba`, frozen 2026-11-14. The primary article is [An Open Non-Invasive EEG Dataset for Spontaneous Auditory Attention Switch Decoding](https://www.nature.com/articles/s41597-026-07244-w), DOI `10.1038/s41597-026-07244-w`; [PMC13261058](https://pmc.ncbi.nlm.nih.gov/articles/PMC13261058/) is an alternate primary full-text endpoint. The dataset identity remains [Zenodo 17413336](https://zenodo.org/records/17413336), including both processed EEG and stimuli; no published file hashes or transfer requirements are replaced.

The official repository was inspected at commit `033856b3f4762b5fa33bc096b0de9f04bf0b5205`, tree `5939f568ed6de3fa4b87e7f6d6dc328a4c9f3875`: [README](https://raw.githubusercontent.com/XXuefeii/AASD-Processing/033856b3f4762b5fa33bc096b0de9f04bf0b5205/README.md) and [preprocessing source](https://raw.githubusercontent.com/XXuefeii/AASD-Processing/033856b3f4762b5fa33bc096b0de9f04bf0b5205/src/AASD_processing.m). No official code is copied or executed here. The tree has no declared reuse license and no model trainer. It selects triggers 11–70, removes the last four recorded channels, merges/filter/resamples/references in that order, and comments out ICA. This does not settle the passive-trial release census, retained channel identities, or native event timing. The paper's trial-level development split is not this registration's prospective double holdout. Paper-reported performance is not used as a threshold.

Dataset CC BY 4.0, article access/license, missing official code permission, and the AISHELL/HRTF stimulus chain remain distinct. Native stimulus notices and the complete rights chain still require review before any redistribution. This package contains only newly written evaluator code and generated test controls.

## Interface and units

Run with Python 3.10 or later and the standard library. From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/neural/NEURAL-SCOPE-20261114-AASD-REPORT/implementations/initial-evaluator-v1/tests -v
python3 benchmarks/neural/NEURAL-SCOPE-20261114-AASD-REPORT/implementations/initial-evaluator-v1/aasd_evaluator.py prepare INVENTORY.json --output PREPARED.json
python3 benchmarks/neural/NEURAL-SCOPE-20261114-AASD-REPORT/implementations/initial-evaluator-v1/aasd_evaluator.py split INVENTORY.json --output SPLITS.json
python3 benchmarks/neural/NEURAL-SCOPE-20261114-AASD-REPORT/implementations/initial-evaluator-v1/aasd_evaluator.py score INVENTORY.json --predictions PREDICTIONS.json --comparator COMPARATOR.json --output SCORES.json
```

The optional comparator must cover exactly the same active and passive cases. `--bootstrap-replicates` defaults to 2,000 and `--seed` to 1729; these are explicit construction policies, not source-paper defaults. No network, data download, fit, installation or model invocation occurs in these commands. `prepare` and `split` produce evaluator-only artifacts containing labels, events-derived strata, and training assignments; do not provide them wholesale to a candidate. The score output likewise remains evaluator-owned.

The inventory JSON is `{"schema":"aasd-inventory-v1","participants":[18 unique strings],"mixture_folds":{"family-A":0,"family-B":1,"family-C":2},"mixture_map_provenance":"...","trials":[1260 objects]}`. Family names are arbitrary native-census identities, not a claim that there are exactly three individual mixtures. Each family maps to one of three folds; all three folds must be represented. The map must represent connected stimulus-overlap components and be frozen from an independently verified stimulus census before outcomes. This code checks use of that map; it cannot validate biological identity from strings.

Each participant must have exactly seven blocks, six active and one passive, each with ten unique `trial_in_block` integers 1–10. `order` is the observed chronological trial ordinal 1–70, not an assumption that passive always comes last. Every trial slot must be included, including documented missing or excluded trials. A trial object contains:

| Field | Meaning |
|---|---|
| `trial_id`, `participant`, `block_id` | Unique trial key, one of the 18 registered participants, observed block identity |
| `trial_in_block`, `order` | Explicit within-block ordinal and chronological ordinal |
| `condition` | `active` or `passive`; never infer from a label |
| `status`, `reason` | `available`, `missing`, or `excluded`; the latter two require an explicit nonempty reason |
| `mixture_family` | A key in the frozen evaluator-owned mixture map, including passive trials |
| `duration_ns` | Integer trial duration in nanoseconds; nominal 60,000,000,000. Any other duration requires `duration_discrepancy_reason` |
| `sample_origin_ns`, `sample_count` | Required when available: time of EEG sample zero relative to trial onset, and number of native derivative samples |
| `valid_spans` | Required when available: ordered nonoverlapping `[start,end)` sample-index intervals valid in all allowed channels; adjacent spans may touch |
| `initial_state` | Required when available: explicit 0=left, 1=right, or null=unknown at trial onset |
| `key_events` | Required when available: strictly time-ordered objects `{"time_ns":integer,"state":0 or 1}` in the trial interval |
| `state_mapping_provenance` | Required when available: evaluator provenance for key-to-side mapping and initialization; a nonempty string is not native validation |

Times are exact integer nanoseconds, and the prospective derivative grid is exactly 128 Hz, one sample every 7,812,500 ns. Native MAT latency/index conversion is deliberately not guessed. The future importer must establish the source clock, inclusive/exclusive indexing and EEG/audio alignment before translating into this interface. No state carries across trials. Duplicate or contradictory simultaneous event times are rejected for explicit upstream adjudication. A missing initial state field is an input error; an explicit null is an unknown state. Every reported keypress counts for motor distance, including repeated same-direction responses. Such a response does not count as a directional switch.

Each submitted prediction is exactly `{"case_id":"...","p_right":0.7}`. Both active and passive eligible cases are mandatory. Missing, duplicate, extra, out-of-range or nonfinite probabilities fail the whole output contract; they never change eligibility. Duplicate JSON object keys and nonfinite JSON constants also fail. Case IDs are deterministic SHA256 hashes of task/trial/window identity for stable joining, not a security or anonymization claim. An execution layer must give candidates opaque approved inputs and keep events, labels and event-coded paths protected.

## Executable scientific semantics

`prepare` enumerates every nonoverlapping one-second target `[k,k+1)` from trial onset. Subsecond trailing duration is reported separately. Report state is integrated by duration, using the state at the target's start and changes strictly inside the target; a key at its start takes effect immediately, and a key at its end belongs to the next target. An unknown start state excludes the window even if the first key later in that window would occupy a majority. Equal left/right duration is an explicit exclusion. These are prospective evaluator policies consistent with the registered majority and initialization requirements; no unpublished paper label rule is claimed.

A window also requires exactly `[k−0.5,k+1.5)` EEG, 256 samples at 128 Hz, aligned on the declared sample grid and wholly covered by the shared valid mask. No padding, neighboring-trial samples or method-specific deletion is allowed. Complete 60-second trials have 60 targets and 58 possible common-context windows, with two edge exclusions. A complete cohort therefore has at most 62,640 active and 10,440 passive eligible windows before label or quality masks. Every exclusion can retain multiple reasons; reason totals can exceed excluded-window counts. The plan gives exact slice bounds, not a tensor export or proof that a model obeyed them. Audio/envelope support and TRF lag orientation remain native/reference implementation holds.

`split` emits 54 cells: 18 held participants × three held mixture folds. Each training set excludes the held participant and every family assigned to the held fold. It never uses passive trials as training data. Active test cases and passive diagnostic cases are assigned exactly once to the corresponding held participant/fold. The version-1 passive diagnostic is frozen-head transfer: predictions must be produced by that cell's attention-trained decoder, with no passive fitting, under the eventual protected runner. A separate motor probe fitted to attention-trained features is not implemented here. The scorer cannot attest how submitted predictions were trained. Inner grouped validation, train-only normalization/class weights/calibration and feature fitting must be implemented and audited with the baseline/runner; this evaluator does not claim they happened.

`score` uses threshold `p_right >= 0.5` for right. Confusion matrices have true classes on rows and predictions on columns, in left/right order. All three mixture-fold counts are pooled within each participant before computing `(left recall + right recall)/2`; participants are then weighted equally. Per-fold results explicitly retain both label counts. A one-class fold contributes its observed counts. A participant with no observations of either class has no balanced accuracy, making the all-18 primary value null. The eligible-participant secondary estimate reports its actual denominator, while observed recalls and log loss on all defined eligible labels remain visible. An entirely absent participant never disappears from the 18-person table.

Log loss is natural-log binary cross entropy, with probabilities clipped only for this numerical calculation to `[1e−15,1−1e−15]`; Brier score uses the original probability. Calibration uses ten fixed right-probability bins, `[0,.1),…,[.9,1]`, and ECE is the count-weighted absolute difference of mean right probability and observed right fraction. These log-loss clipping and calibration-bin choices are explicit prospective policies. Participant-macro log loss/Brier/ECE include all participants having defined labels and expose both eligible and required denominators. No class or subject is silently assigned zero error.

Secondary outputs include a guard whose minimum distance from the entire closed target interval to **any** keypress is at least two seconds; exact distance two seconds passes. With no recorded keys this guard is vacuously true, provided the initial report state is known; it is not evidence of an absence of motor behavior. This full-interval distance is a prospective conservative implementation of the registered sensitivity stratum, not a paper rule. Direction-transition distance uses actual direction changes and is separately reported as none, below two seconds, or at least two seconds. Switch density is the number of such transitions in the one-second target (zero, one, multiple). Block and chronological ten-trial-order-bin tables include completely missing/excluded blocks and their class/undefined-label coverage. Per-participant active/passive accounting includes all trial slots and all window exclusions.

Passive output measures decoding of reported response-key state. It is not passive attention ground truth. Active performance, the two-second guard, or weak passive transfer cannot establish attention specificity: offline filtering, sustained movements, unrecorded horizontal eye movements, response delays, and passive block/order distribution shift remain limitations.

With a comparator, the paired endpoint is each participant's pooled balanced-accuracy difference. All 18 differences must be defined. The evaluator resamples 18 participants with replacement for percentile 95% bootstrap intervals (linear interpolation) and enumerates all `2^18` sign assignments for a two-sided paired sign-flip test. The null requires symmetry/exchangeability of participant differences; this is not a window-independent test or a proof of causal attention specificity. All effects, seed, replicate count and assignment denominator are emitted. A missing class keeps the all-18 comparison unestimable.

## Requirement mapping and retained holds

| Registered requirement | Implementation and limit |
|---|---|
| Full 18 × 60 active + 10 passive trial population | Strict inventory cardinality/block/order validation plus per-trial and per-person coverage; native census remains unverified |
| Initialized duration-majority report labels | Exact integer-time integration, ties/unknown starts explicit, no cross-trial carry |
| Common 2-second EEG information interval | Exact 256-sample aligned slices with shared-mask and edge exclusions; native EEG/audio/channel verification held |
| Participant and mixture separation | 54 concrete split cells over a supplied frozen family map; actual overlap-component discovery and inner model fitting held |
| Pool confusion counts then average 18 people | Primary and one-class rules implemented; source-reported accuracy is not a target |
| Log loss, calibration, guard, transition/switch/block/order/class coverage | Implemented with prospectively documented bins, clipping, distance and strata rules |
| Passive motor diagnostic | All eligible passive predictions required and routed to held cells; attention-trained feature provenance still requires a protected runner |
| Paired participant uncertainty | Bootstrap and exact paired sign flips; no window-level pseudo-replication |
| Competent TRF, EEG classifier, compact network and shortcut challenges | Held: no native training, authentic predictions, audio/EOG/time/phase controls or baseline competence claim |
| Rights, native reference, protected scoring and independent scientific qualification | Explicitly held; independent review here covers construction code only |

Native all-trial census, quality exclusions, event initialization, channel and reference/filter order, stimulus overlap, audio timing/envelopes and lag orientation must be independently verified. Nothing in a JSON provenance string clears those gates. Protected execution, contamination qualification, baseline fitting and valid source/data rights remain required before promotion. Generated tests establish engineering behavior only; scientific and submission readiness remain unknown and the finished task count is unchanged.
