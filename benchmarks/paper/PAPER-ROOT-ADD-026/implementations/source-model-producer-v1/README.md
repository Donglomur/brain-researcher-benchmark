# Original DN fitting and biological-summary producer

This additive source component implements the DN, category-input-scaled DN (`S`), and separately indexed output-scaled DN (`P`) equations and fitting recipe from author revision `09cd778fac545d406cba39ba408f0f00fbe39975`. It supplies an explicit operator path from the complete frozen response metadata to individual fits, complete CV accounting, and prospective reconstructions of the biological result family. It is not a scientific result, a participant submission sandbox, or authorization to run authentic fits.

No authentic response array, model fit, score, or biological result was produced while constructing this component. Existing task definitions, source protocols, registered selectors and qualification states are unchanged. The author runtime was Python3.9.7, NumPy1.21.3 and SciPy1.7.1; generated controls here ran with Python3.11, NumPy2.4.6 and SciPy1.17.1. Explicit old solver defaults preserve the inspected recipe, but do not establish cross-version numerical parity.

## Population and information conditions

The source population remains all79 responsive electrodes in four participants:17 V1–V3,15 VOTC and47 LOTC. Each electrode retains72 conditions (two trial types ×six categories ×six temporal conditions) and819 response samples. The producer authenticates the existing `source-cv-replay-v1/replay.py` and `cohort.json` against fixed reviewed identities and uses that replay's externally frozen fold manifest. The old948 prediction targets do not define these source-CV folds.

Default planning emits2,054 separate coordinates:158 full-data fits and1,896 CV fits, for DN `none` and `S`. Every fit starts from the original parameter initialization and bounds. Each CV fit uses66 training conditions and six disjoint queries, one per category. All12 folds and all79 electrode identities are required. Optional `P` adds a separately named diagnostic family; it does not make the active author category-selective/P invocation equivalent to Figure3's responsive/none/S invocation.

The source's full-data fit always uses the named response columns0…818. Its CV code instead uses positional columns2:821, which includes `temp_cond` and omits the last response sample. The plan requires an explicit `source_positional_cv` or `named_response_columns` branch; a corrected named-column branch is not claimed to be the original execution. Full-data outputs are descriptive and never labelled held-out performance.

## Preserved numerical recipe

`model.py` preserves the truncating integer sample delay, normalized discrete causal gamma/exponential kernels, signed linear drive entering the delayed normalization pool, numerator `abs(linear)**n`, denominator `sigma**n + abs(pool)**n`, source bounds, and distinct `none`/`S`/`P` operations. The source objective is unusually a **scalar total SSE** passed to `scipy.optimize.least_squares`; the solver cost is therefore one half of SSE squared. It is not silently replaced with a residual-vector fit. The source limit remains500 function evaluations, with explicit SciPy1.7.1 defaults recorded in each result.

Each individual result retains coordinate and row identities, source digest, fit status, all predictions and exposed observations. Full fits additionally retain all72 linear-drive, numerator, normalization-pool, denominator and final-response traces, semisaturation/category factors, and parameter diagnostics. Failed/nonconverged fits remain present in the complete roster. Numerical exceptions emit an explicit failed coordinate; finite nonconverged parameters are retained but cannot silently enter completed scientific summaries.

CV reduction recomputes condition R² from retained traces, rounds each of six scores to three decimals, averages/rounds a fold to four, then averages12 folds/rounds to four. Figure3 retains separate model/region results:1,000 electrode resamples, median within each draw, median of draw medians and16th/84th percentiles. The parameter file's author `r2` is this separate CV result, not full-fit quality. Bootstrap seeds here are prospective; original unsaved random draws are not recovered. Electrode resampling is descriptive, not four-participant generalization.

Engineering failure policy is stricter than the original writer: any failed/nonconverged job withholds the aggregate Figure3 output; undefined R² is recorded rather than replaced or omitted. Inputs are admitted as finite condition traces; behavior for source NaN-containing arrays is not claimed equivalent.

## Biological family and unresolved callers

Figure3 is only one result in the retained family. `biological.py` supports duration-response traces, six duration FWHMs,533ms onset-to-peak, repeated-stimulus traces, source sequential first-response estimation, isolated second responses, first/second AUCs and their six ratios, average recovery, and a separately labelled heuristic log-recovery extrapolation at one second. Full-fit component traces and parameter records remain available for mechanism inspection without claiming unique mechanistic identification.

The cached author code has Figure3 but not Figure4–9 caller implementations. Exact AUC windows, normalization, FWHM crossing/window conventions, display smoothing versus metric smoothing, log-fit options, and category pooling invocation are not all recoverable. Consequently, **every biological execution is labelled `prospective_not_original_figure_execution`** and requires an externally hashed explicit recipe. There are no guessed executable defaults. The supported reconstruction deliberately performs no additional normalization, equal category averaging, sampled first rise/first decay FWHM relative to zero, and unweighted linear least squares on log seconds. These choices are disclosed engineering recipes, not recovered figure code.

The original `estimate_first_pulse` performs sequential pair averaging in ISI order, starting from the134ms single-pulse condition. Its unequal weights are preserved even though paper prose suggests pooled averaging. Source condition3 is labelled133ms; the paper rounds it to134ms. AUC uses unit sample spacing as in `np.trapz(values)` with no time vector; a caller window that would truncate is refused. For `y=c+a*log(x)` in seconds, the extrapolated one-second value is `c`; it is not a measured condition. Zero/invalid denominators and missing FWHM crossings stay undefined. Bootstrap intervals are withheld if any of their1,000 draws is undefined, preserving the full denominator.

For temporal/recovery metrics, electrode traces are averaged **before** measuring each bootstrap draw. Regional routes preserve the17/15/47 populations and participant nesting. The separate `selected-all` route pools all26 explicitly selected electrodes across regions before preferred/nonpreferred measurement; per-region category companions do not substitute for this main population. A category selection input must name each electrode, preferred category, explicit four-category nonpreferred pool excluding scrambled, threshold0.5, and an authenticated selection evidence file. It remains unqualified input, even when structurally valid. Without it the category family remains explicitly pending. Neither the26 identities nor trial-level d′/onset criteria can be inferred from72 condition means; cached active selection code also differs from the paper's main criteria. The full79 outputs are never discarded to imitate a category count.

## Explicit operator interface

All commands below are future operator examples, not executed authentic work. An authentic run requires separately admitted CPU/wall/disk/exposure limits. One source fit may be expensive despite its500-evaluation limit; this component does not launch an unbounded batch or parallel worker farm. Keep plan, response bindings, source-CV manifest, recipe and result-index digests in the independent run record.

1. Obtain the existing replay's frozen79-electrode fold manifest and its external logical SHA256. Prepare a `temporal026-original-input-bindings/v1` object containing exactly `variables` (`t`, `cond_stim`, `cond_temp`, `timepoints_onepulse`, `timepoints_twopulse`) and `responses` keyed by all79 electrode IDs. Each member is an exact `{path, bytes, sha256}` relative descriptor; response digests must match the replay manifest. No data scan is performed during plan creation.
2. Freeze the complete explicit branch plan:

   ```sh
   python -I -B producer.py plan --manifest folds.json --manifest-sha256 EXTERNAL_FOLD_SHA --inputs input-bindings.json --branch source_positional_cv --output plan.json
   ```

   The returned logical `plan_sha256` covers all identities/recipes/jobs. `--include-P-diagnostic` explicitly adds the separate third model. An old checkout lacking the already-public sibling replay may use the global `--replay-dir` option pointing to **exact authenticated** public replay/cohort copies; this does not accept alternative code.
3. Run a single admitted coordinate (the ID must come from the plan):

   ```sh
   python -I -B producer.py run-coordinate --plan plan.json --plan-sha256 EXTERNAL_PLAN_SHA --manifest folds.json --input-root ORIGINAL_INPUT_ROOT --job 'ELECTRODE_ID/DN-S/fold00' --output NEW_RESULT.json
   ```

   Inputs are exact-size/hash checked with no-follow descriptor traversal, ordinary single-link files and stable metadata. Each response is bounded to4MiB and each variable to128KiB. Results are exclusive new files bounded to16MiB. Failed/nonconverged coordinates exit nonzero and retain their record; no retry is automatic.
4. Collect an exact result index listing all2,054 pinned result bodies (or3,081 withP):

   ```sh
   python -I -B producer.py collect --plan plan.json --plan-sha256 EXTERNAL_PLAN_SHA --manifest folds.json --results complete-result-index.json --bootstrap-seed EXPLICIT_SEED --output NEW_COLLECTION.json
   ```

   The index is a list of complete relative member descriptors. The collector reads at most4GiB cumulatively, one bounded result at a time, retaining compact CV records rather than all full arrays. Duplicate, foreign, omitted, mutated or inconsistent coordinates/rounds are refused. Full-result bodies remain separately pinned artifacts. This is trusted-operator output verification, not an adversarial submission channel.
5. Biological reconstruction requires a recipe with exactly the fields validated by `validate_recipe`: schema, explicit AUC sample window, reference and longest condition indices, six ISIs in seconds, peak/FWHM sample window, normalization/category-pool/FWHM/log-fit policies, bootstrap seed, and reconstruction status. Hash canonical JSON using the producer's `digest`. Use a regional index of exactly17/15/47 full results for one model, or26 results for `selected-all` with its separately pinned selection:

   ```sh
   python -I -B biological.py --plan plan.json --plan-sha256 EXTERNAL_PLAN_SHA --manifest folds.json --input-root ORIGINAL_INPUT_ROOT --results REGION_FULL_INDEX.json --recipe EXPLICIT_RECIPE.json --recipe-sha256 EXTERNAL_RECIPE_SHA --region V1-V3 --scaling S --output NEW_BIOLOGICAL.json
   ```

   Repeat for the three regions and declared model variants. For the main category route use `--region selected-all --selection SELECTION.json --selection-sha256 EXTERNAL_SELECTION_SHA`. No selection input is manufactured here. The route streams full result bodies and retains only category-pooled population arrays for measurement, while source-indexed full traces/components remain in their individual files.

## Generated controls and provenance

Required portable controls use NumPy/SciPy and no authentic data:

```sh
python -I -B test_model.py -v
python -I -B test_producer.py -v
python -I -B test_biological.py -v
```

There are18 numerical-core,16 dispatcher/accounting and13 biological controls. Dispatcher numerical fitting is explicitly a generated seam; real generated model fits/equations are tested separately by `test_model.py`. All biological fixtures are invented. The replay adapter returns fresh parsed copies of the already authenticated cohort bytes, so later path replacement cannot change its population or trigger an unbounded metadata reread. The optional `review_source_parity.py` extracts only authenticated cached author functions for direct generated differential checks; it is not a required hosted test or redistributed author code. Its original source cache is external and rights remain unresolved.

`SOURCE.json` binds this additive implementation, immutable public replay/cohort/task/contract references and cached author provenance. External review receipts retain all successful controls and the initial two test-oracle failures corrected before the dispatcher freeze. Missing publication-release lineage, original runtime/RNG proof, category selection inputs, exact biological caller recipes, authentic execution/resource measurements and numerical figure comparison remain explicit. No generated test pass clears those scientific gates.
