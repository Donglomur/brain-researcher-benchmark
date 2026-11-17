# Processed-component linear encoding and readout

This package implements the paper-described supplementary **linear** encoding/readout endpoint from aligned, already resampled component arrays and behavior. It completes selection, epoch extraction, pair pooling, support matching, cross-validated univariate regression, component/parcel averaging, and within-participant consistency contrasts. It is not the main intersection-information endpoint or a numerically qualified reproduction. Scientific qualification remains **unknown**; the canonical task and its historical records are unchanged.

## Primary provenance and scope

The sources are [Park et al., Nature Communications (2025)](https://www.nature.com/articles/s41467-025-61010-x), the [regression entrypoint](https://github.com/DonnerLab/2025_Park_ConfirmationBias-through-Selective-Readout-of-Information-Encoded-in-Human-Parietal-Cortex/blob/8b79caa5b95fadce826ea39bf6c69828991a4b28/confbias_regress_sample_int12_cic.m), and the [Supplementary Figure S11 script](https://github.com/DonnerLab/2025_Park_ConfirmationBias-through-Selective-Readout-of-Information-Encoded-in-Human-Parietal-Cortex/blob/8b79caa5b95fadce826ea39bf6c69828991a4b28/Figures/FigureS11_PK_Decoding_int12_cic_tc.m), all code pinned to `8b79caa5b95fadce826ea39bf6c69828991a4b28`. `provenance.json` records inspected-source hashes and important disagreements. No author code or dataset is bundled.

The primary paper explicitly fitted PCA across all vertices **and all trials**, retaining components explaining 90% of variance. The source components are therefore published all-trial representations. Training-only OLS here does not make the PCA training-only, and grouped trial folds do not create a protected participant-held-out benchmark.

The pinned II script requests `I_min` while the paper describes shared-information optimization preserving pairwise marginals. Resolving that discrepancy requires a pinned MINT version and native dispatch/solver audit. This implementation computes **no MI, II, conditional MI, or substituted information estimate**. Its behavioral slopes and optional participant correlations are linear companion analyses; the latter are prospective sensitivities, not reproduction of the paper's Figure 5 II association.

## Numerical contract

1. Consume each context's components as `[trial, PC, time]`, with 1–15 PCs and exactly 801 samples at 160 Hz from −0.5 through 4.5 seconds. Keep source PCA; perform no new PCA, source localization, or resampling. The native 200-to-160 Hz conversion remains outside this package and unqualified.
2. Require unique behavior trial IDs and exactly matching neural IDs in context order. Cue (`attn`) uses sessions 1–2; Choice uses 3–4. Exclude missed binary choices (`99`), missing estimates and missing generative means. The default uses all finite means, matching the inspected S11 plot's `fgmu=0`. `--generative-limit 4` is an explicitly selected near-zero sensitivity: integer source means −4 through +4, as in MATLAB `ismember`, not all real numbers in that interval.
3. Reproduce the actual source baseline indices: −0.5 through **+0.05 seconds inclusive**. The source comment says zero, but its first-onset index includes +0.05. Extract 129 samples from −0.1 through +0.7 around each of the 12 source onsets.
4. Pool adjacent evidence positions in MATLAB column-major order: all trials at the first sample, followed by all trials at the second. First-interval consistency uses the sign of sample × intermediate cue/choice; zero is neither consistent nor inconsistent. Second-interval consistency uses the supplied nonmissing masks. The `all` category still applies behavior exclusions.
5. Within each context and pair, use the smallest consistent/inconsistent/all support and five without-replacement subsamples per class. The construction conservatively retains the paper's 81-observation information-analysis threshold for this linear endpoint; its use here is **prospective**, not a claim that S11 source enforced that threshold. Insufficient pairs remain in output, and no lower-count fallback occurs.
6. Fit separate intercept-plus-PC OLS models to stimulus and behavioral estimate for each component/time. Use 10 folds and report the arithmetic mean of **within-fold Pearson correlations**, not pooled out-of-fold Pearson. Readout is correlation of held-out predicted stimulus with behavioral estimate. Training-only numerical centering/scaling is algebraically equivalent OLS and consistently applied to prediction. This corrects the inspected source's fit-only `1e12` scaling discrepancy; source-exact predictions are not claimed.
7. Average signed correlations over folds, subsamples and PCs; average signed parcel values within each declared region; average the inclusive 0.1–0.5 second window. Only then take the absolute readout magnitude, separately by consistency class, and subtract inconsistent from consistent. Encoding/report correlation summaries retain their sign. Opposite parcel/PC/time effects therefore cancel before absolute value.
8. Report all six pair contrasts. Equal averaging of the three pairs within each interval and linear behavioral-versus-readout participant correlations are clearly labeled **prospective summaries**. Group associations require all declared participants to have estimable interval endpoints and at least three nonconstant paired values. Otherwise the correlation is null and the missing/undefined support is explicit. Region membership and participant identity are supplied declarations, not an assertion that the authentic full cohort has been audited.

`source_rows` folds reproduce the source's observation-level partition unit; a trial contributes two pooled rows and may cross folds. `grouped_trials` is a prospective sensitivity assigning every selected row of a trial to the same fold. Both modes emit selected pooled row indices, trial IDs, fold IDs and cross-fold trial counts. Deterministic participant/context/pair/class seed streams are construction choices, shared across parcels to keep behavioral matching aligned; they do not reconstruct MATLAB's historical random state.

A constant component/target or undefined fold correlation stays undefined. Strict means propagate this status; `nanmean` never silently removes a component, fold, parcel or participant. JSON emits `null`, while diagnostic counts and pair statuses record why.

## Input packet

Use Python 3.11 and NumPy; no dependency installation is performed by the package. JSON packet paths refer to sibling `.npz` files, each with SHA-256. Loading disables pickle, rejects paths escaping the packet directory, and requires exact participant/context/parcel coverage.

```json
{
  "schema_version": 1,
  "task_id": "PAPER-ROOT-ADD-025",
  "packet_kind": "authorized_processed_input",
  "component_provenance": "author_released_all_trial_PCA_160Hz_export_unqualified",
  "expected_participants": ["S01"],
  "expected_parcels": ["IPS1"],
  "region_groups": {"declared_IPS1_only": ["IPS1"]},
  "contexts": ["choice"],
  "participants": [{
    "id": "S01",
    "behavior": {"path": "S01_behavior.npz", "sha256": "<actual sha256>"},
    "neural": [{
      "context": "choice", "parcel": "IPS1",
      "array": {"path": "S01_choice_IPS1.npz", "sha256": "<actual sha256>"}
    }]
  }]
}
```

This is a format example, **not** the paper's complete population or a ready empirical packet. Authentic acquisition/export is not authorized or performed by this construction. A hash verifies packet bytes, not their scientific provenance. The native behavioral MAT-to-normalized-array adapter and source trial identity mapping remain unverified.

Behavior NPZ contains exactly these fields:

| Field | Shape / interpretation |
|---|---|
| `trial_ids` | Unique nonempty Unicode strings, one per original trial |
| `sess` | Trial vector, integers 1–4 |
| `samples` | Trial × 12, finite angular sample positions |
| `binary_choices` | Trial vector, −1/+1 or 99 for missed choice |
| `interm_cues` | Trial vector, −1/+1 |
| `estimations` | Trial vector; NaN means missing |
| `gen_means` | Trial vector; NaN means missing |
| `consistent_samples`, `inconsistent_samples` | Trial × 12, source samples or NaN; overlapping second-interval masks are rejected |

Neural NPZ contains exactly `trial_ids` and `components`; IDs must equal the complete selected context's behavior IDs, including trials subsequently excluded by behavior eligibility. No positional reordering is guessed. These normalized-field constraints are an intake contract requiring authentic export validation, not evidence that the native MAT schema has been validated.

For generated controls use `packet_kind: generated_engineering_controls` and `component_provenance: generated_reference_shape_160Hz`; generated arrays are never labeled author data.

From the implementation directory:

```sh
python3 evaluator.py packet.json output.json --seed 11 --fold-mode source_rows
python3 evaluator.py packet.json grouped-output.json --seed 11 --fold-mode grouped_trials
python3 -m unittest discover -s tests -v
```

The output records exact packet hash, random seed, source commit, all support and undefined-state diagnostics, parcel and regional endpoints, and preserved qualification gates. Fold correlations averaged over components remain available for audit. Large authentic cohorts have not been profiled; output size and numerical/native parity require measurement before production use.

## Verification and remaining gates

Generated controls exercise analytical OLS against independent least-squares solutions, arbitrary PC signs and physical units, held-out target isolation, mean-fold versus pooled correlation, late absolute value across PC/time/parcel, source baseline indices, integer generative-mean selection, grouped trial isolation, support retention, duplicate/misaligned IDs, bad hashes/rosters and deterministic packet execution. These checks establish engineering behavior only.

The pinned repository's [MIT license](https://github.com/DonnerLab/2025_Park_ConfirmationBias-through-Selective-Readout-of-Information-Encoded-in-Human-Parietal-Cortex/blob/8b79caa5b95fadce826ea39bf6c69828991a4b28/LICENSE) was newly inspected; the canonical historical null license remains unchanged. Data's recorded CC BY 4.0 terms remain separate. No native author code or scientific data was run, no dependency installed, and no dataset/archive downloaded.

Still open: complete authentic participant/parcel inclusion and exclusions (the S11 script excludes ordinal participants 12,14,19,21; main information results use a different population), native MAT/export/resampling validation, upstream `gSCR` aggregation reconciliation, exact figure references and numerical tolerances, MINT II estimator/bias/null equivalence, protected evaluation, grouped participant improvement design, data redistribution review, and authentic runtime/memory. `full_contract_complete`, native reproduction qualification and scientific admission remain false/unknown.
