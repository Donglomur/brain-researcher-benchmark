# Initial source evaluator: PAPER-FIND-REP-007

This is an executable source-construction component for Zhong et al., *Unsupervised pretraining in biological neural networks* ([paper](https://www.nature.com/articles/s41586-025-09180-y)). It computes four substantive endpoint families from complete supplied sessions: all-cell stimulus selectivity, the pinned code's sequence-similarity measure, reward-predictive activity and reward-zone licking. It also assembles explicit longitudinal animal summaries. **It is not a completed or scientifically qualified whole-paper benchmark.** No authentic recording, model, native campaign or protected reference was run. Scientific qualification remains **unknown**; no score threshold or binary reward is registered.

The package is `../implementations/initial-evaluator-v1/`. `provenance.json` binds the unchanged canonical task and primary code at `ba64ac697f5d9914926baac79399e80707a5f3a6`. The implementation is independent code expressing the documented calculations; author source is not vendored. The upstream license text was confirmed as GPL-3.0. Component redistribution, full-text/stimulus rights and exposure policy still require owner qualification. Figshare version 2 and the original 297-file all-cell release remain the intended source, not a third-party neuron subsample.

## Implemented calculations and source limits

| Endpoint | Implemented semantics | Primary locator |
|---|---|---|
| Stimulus d-prime | `2*(nanmean(first)-nanmean(second))/(nanstd(first)+nanstd(second))`, population SD; raw moving (`ft_move>0`) texture (`ft_CorrSpc`) frames | `utils.py:dprime`, `Get_dprime_selective_neuron` |
| Selective fractions | Thresholds 0.1–1.0 inclusive; either/positive/negative signs; denominator is **every cell in the area**, including undefined d-prime cells | `Get_selective_neuron_fraction_with_dprime`; processing notebook cells 11/15 |
| Areas | V1:8; medial:0,1,2,9; lateral:5,6; anterior:3,4. Outside-area cells remain in input/count diagnostics | `neu_area_ID` |
| Sequence similarity | Select the upper 5% of leaf1-versus-circle1 d-prime among corridor-responsive cells per area, inclusive ties; train on even zero-based frame-trial IDs. Odd zero-based leaf1 trials split alternately into reference and repeat-test subsets. Other stimuli use all trials. Pearson correlation across neurons' peak-position bins `:40` | `Get_sort_spk`, `get_neuID_and_sortID`, `get_seq_corr`; `fig2.py:seq_corr_all_areas` |
| Reward prediction | Mean activity bins `5:40`; cue=`SoundDelPos % 60`; late `>` versus early `<=` **all-trial** mean cue, within stimulus ID2; selected if reward d-prime>=0.3 and stimulus ID2-versus-ID0 d-prime>=0; divide by all area cells | `Get_dprime_rewPred_neuron`; processing notebook cell17 |
| Learning behavior | Any lick in inclusive `[20,40]`; first **200 total trials**, not 200 per stimulus; rewarded and nonrewarded probabilities and their difference | `get_lick_response_in_zone`; `fig5.py` |

D-prime zero-variance NaN/infinity behavior is retained for threshold comparisons. JSON values become `null`, with separate finite/NaN/positive-infinity/negative-infinity counts. This preserves source area denominators rather than deleting undefined cells. Empty required trial/frame groups are rejected. Missing areas return null fractions. Sequence results with undefined selection, nonfinite traces or constant peak positions are explicitly undefined rather than assigning arbitrary peaks/correlations. Pinned NumPy `argsort` peak ties remain a runtime-sensitive native-parity issue.

**A material paper/code disagreement remains open.** The paper's sequence methods describe `|d'|>=0.3` and a split of novel-stimulus trials; the pinned `Get_sort_spk` uses top/bottom 5% and all novel-stimulus trials. A subsequent paper paragraph also refers to top5%. The package names its endpoint `pinned_code_top5pct_leaf1_sequence`; it does not select a unique scientific policy on the owner's behalf. Its full-session per-cell z-scoring reproduces the source variant and is not a claim of prospectively train-only preprocessing. Sequence similarity is not generic pairwise or noise correlation.

The processing notebook's exact experiment/stimulus-pair list is encoded in `SELECTIVITY_RECIPES`. Reward computation is restricted to its four train1 before/after experiments. Sequence processing is restricted to the six naive/unsupervised/supervised test1/test3 experiments listed in source. The component does not implement coding-direction selectivity indices, density maps, all paper panels, numeric figure targets or inferential tests. These omissions remain gates, not substituted endpoints.

## Data boundary and native bridge

Use existing Python 3 and NumPy; no installation or network access is performed. The command consumes safe NPZ files (`allow_pickle=False`) plus an owner-pinned JSON panel. `normalize_author_imaging(neural, retinotopy, behavior)` accepts already decoded official dictionaries: concatenates **all** `neural['spks']` planes, retains all area assignments, applies the source leading-frame alignment, and interpolates moving activity to 60 spatial bins per trial. Its NumPy linear interpolation with endpoint extrapolation implements the pinned `scipy.interp1d` mathematical recipe. Corridor length must equal60 and moving accumulated positions must be strictly increasing; duplicates/resets require source reconciliation. This mathematical control is not authentic SciPy/native parity validation.

`normalize_author_behavior(behavior)` resolves ID2/ID0 from actual reward labels for two-stimulus training sessions and rejects ambiguous categories. Original source NPY dictionaries require pickle; this package deliberately does not deserialize them. An authorized preparation environment must verify provenance and decode those files before calling the in-memory bridges and writing `np.savez(...)`. No source acquisition is implicit.

Imaging NPZ arrays:

- `spks`: cells×frames; `area_ids`: cells; every source cell retained.
- `frame_wall`, `frame_move`, `frame_corridor`: aligned frames. Labels on moving texture frames must map to a declared stimulus; gray labels may differ.
- `trial_wall`: chronological trials; `stimulus_names` and integral `stimulus_ids`: bijective source identity map.
- Reward requires `interp_spks`: cells×trials×60 and `sound_delay_position`: trials.
- Sequence additionally requires `frame_trial`: zero-based integral trial IDs, `frame_gray`: boolean frames and `interp_spks`.

Behavior NPZ arrays: `trial_wall`, `stimulus_names`, `stimulus_ids`, `lick_position`, zero-based integral `lick_trial`. Empty lick arrays are valid; duplicate events in a trial count once. These IDs are source reward-category identities, not a rule that a texture string must always be rewarded.

## Explicit panel and invocation

A panel has `schema_version:1`, `task_id:"PAPER-FIND-REP-007"`, at least two ordered unique `stages` (use all five training sessions for a five-session curve), `population_evidence`, `expected_session_ids`, and `sessions`. Every session supplies:

```json
{
  "session_id": "source-animal-session-key",
  "animal_id": "source-mouse-id",
  "condition": "source-exposure-condition",
  "stage": "one-declared-ordered-stage",
  "kind": "imaging",
  "experiment": "unsup_train1_before_learning",
  "analysis": "source_selectivity",
  "npz_path": "session.npz",
  "sha256": "owner-verified-64-hex-content-hash",
  "expected_counts": {"cell_count": 12000, "frame_count": 90000, "trial_count": 250}
}
```

Those illustrative counts are not an empirical cohort. `analysis` may instead be `source_sequence` with a permitted experiment. Behavior sessions use `kind:"behavior"` and only `trial_count` in `expected_counts`. All sessions in one animal/stage must expose identical metric families; the first and last stages must have the same endpoint identities. Repeated sessions are averaged within animal/stage before descriptive condition summaries. Every animal must occur at all declared stages, its condition must stay fixed, and input hashes cannot be reused as distinct sessions. Source completeness is verified only against the owner's declared inventory; checks cannot establish that this inventory covers the actual release or that declared counts prove all-cell provenance.

The prospective aggregation policy is explicit: equal-session means within animal/stage; equal-animal means and sample SEM by condition/stage; paired last-minus-first changes and their equal-animal summaries. Missing session metrics propagate to the animal-stage mean. This policy is useful preparation, not a retroactive claim about published inference. Full five-session learning curves are retained when five stages are declared. Paper statistical test choices, multiplicity policy and exact full-cohort membership still require scientific freeze.

```bash
python3 benchmarks/paper/PAPER-FIND-REP-007/implementations/initial-evaluator-v1/evaluator.py /path/to/panel.json --output /path/to/report.json
python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-REP-007/implementations/initial-evaluator-v1/tests -v
```

Reports bind the panel/input SHA256s, preserve session/animal/stage identities, include raw frame/trial counts and area yields, descriptive effects, undefined-value diagnostics and the unresolved gates. They always state `scientific_qualification:"unknown"`, `full_contract_complete:false` and no registered grading target. This is a reference-side component; isolation of candidate code from source/protected answers is not established here.

## Population, exposure and validation holds

The actual experiment-info-derived complete animal/session map, all-cell transforms, exact claim-specific subset size, authentic preprocessing and native runtime remain unverified. Trial-count and recording-yield matching, stimulus/area balance and behavioral covariates must be qualified before attributing differences to learning. No hidden independent cohort is identified. This task shares primary paper/data locators with **NEURAL-027 and NEURAL-028**; that family/exposure coupling is preserved, while biological participant overlap still requires verification. The neural decoder and these paper endpoints are distinct implementations and cannot be counted as independent empirical evidence merely because their task IDs differ.

Generated controls check the arithmetic-SD d-prime, NaN/infinity denominators, frame exclusion, cue modulo/all-trial split, positive-stimulus gate, exact35-bin reward window, inclusive lick boundaries/global cutoff, sequence reference/repeat splitting and reversal, native all-plane linear interpolation, animal weighting, omitted stages, duplicate/altered input handling and CLI output. They demonstrate engineering behavior only. Authentic reference agreement, comparator competence, whole-paper reproduction and scientific qualification remain open.
