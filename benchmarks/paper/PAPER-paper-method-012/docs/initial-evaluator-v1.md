# Initial fixed-bin CA1 mutual-information reference

This additive implementation computes joint neuron-pair information about spatial-bin labels, finite-sample quadratic extrapolation (QE), and shuffled-label or temporal-shift diagnostics from complete prepared session arrays. It supplies a working MAT preparation path, numerical implementation, CLI, and independent algebraic controls. It is a **construction reference**: scientific qualification remains **unknown**, and native MINT equivalence and empirical reproduction are unverified.

The immutable canonical task remains `task.json`, SHA256 `549d5de7931e1cd6fc3b651b3084052e566dc054cf38662bc7d8995a70358ca2`. The implementation does not register a numeric grading target or alter historical evidence.

## Primary source reconciliation

The [article](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012934) and [S1 Appendix](https://journals.plos.org/ploscompbiol/article/file?type=supplementary&id=10.1371/journal.pcbi.1012934.s001) identify the bounded empirical CA1 scope: 11 fields of view from seven animals, 43–104 neurons per session, and 36,158 simultaneously recorded pairs. These population facts have not been checked against payload identities. The two sources disagree about 12 spatial bins: the article describes equal-width bins, whereas the appendix describes equal-population bins. Both describe two equipopulated raw-fluorescence bins. The implementation accepts fixed labels and never guesses a binning transformation.

New source inspection located [MINT_figures/Figure2/CA1.m at a90eb535205c2df668e4e59c8f8d748c37fa815e](https://github.com/panzerilab/MINT_figures/blob/a90eb535205c2df668e4e59c8f8d748c37fa815e/Figure2/CA1.m), a figure wrapper absent from the canonical audit's known evidence. It consumes `Hippocampus_data.<session>.Position` and `.R_neuron_binned` (neurons by samples), enumerates all neuron pairs, clips response labels above four to four, selects `shuffSub` with 30 permutations, and disables rebinning. The actual MI invocation is commented out while its empty results are subsequently consumed. Its population-decoder folds and final shuffled-decoder assignments also conflict with the paper/source intent. We retain those defects as source evidence; this package's direct-MI implementation is an independently written repair, never a claimed historical run. The wrapper filename `Hippocampus_data.mat` and appendix filename `S2_CA1_data.mat` do not prove the uninspected supplement's schema.

Estimator definitions were checked against pinned [MINT MI.m](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/src/MI.m), [extrapolation.m](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/src/core_functions/BiasCorrection/extrapolation.m), [partition.m](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/src/tools/partition.m), and [shuffle_subtraction.m](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/src/core_functions/BiasCorrection/shuffle_subtraction.m). Exact source-response and text-transcription hashes are in `implementations/initial-evaluator-v1/provenance.json`. GitHub HTML rawLines transcription hashes are explicitly distinct from raw-file-byte verification. No third-party implementation files are redistributed. MINT's GPLv3 terms remain applicable to that separate toolbox; article/supplement terms and exposure must be reviewed independently before empirical admission.

## Computational contract

For each complete session roster, every unordered neuron pair is encoded jointly after the explicit source cap `min(label, 4)`. MI is `sum p(r,s) log2[p(r,s)/(p(r)p(s))]`, with no pseudocounts. The package always computes a full-session estimate using all supplied observations. It also evaluates user-selected subsample counts with identical sample and null schedules across neuron pairs and corrections. Continuous traces, missing values, floating labels, duplicate sample/neuron IDs, and incomplete declared session rosters are rejected.

QE uses one common random permutation for two equal halves and four equal quarters and averages repeated intercepts `8/3 I(N) − 2 mean I(N/2) + 1/3 mean I(N/4)`. Prospective finite-sample counts must be at least eight and divisible by four to avoid silently approximating unequal MINT partitions. For a full session whose size is incompatible, full plugin and null-subtracted results remain present; QE is `null` with an explicit reason. Nothing drops the remainder samples.

In `iid_permutation` mode, stimulus labels are permuted only within each selected sample set, preserving its exact label histogram. The response pair is never separated. Subtracting mean shuffled plugin MI implements the shuffSub formula; subtracting mean shuffled QE implements the combined formula. These are distribution-level mathematical counterparts, with native random-stream and numerical parity unverified.

In `circular_shift` mode, a nonzero circular shift is applied to the full stimulus sequence before selecting the common sample indices. This preserves the trajectory's cyclic ordering and is a **prospective temporal diagnostic**, not the author's IID shuffSub protocol. The mode is always reported; its subtracted values must be interpreted as shift-subtracted diagnostics. It requires acquisition-order arrays and does not establish stationarity. Both modes report `(1 + exceedances)/(1 + null_count)` solely as diagnostic exceedance fractions. Neither mode asserts calibrated p-values, false-positive control, causal direction, true empirical MI, FDR, or familywise significance. Negative corrected values remain negative.

All pair-level values and null distributions are retained. Session descriptives average complete pair/repetition rows. At a common sample count, animal descriptives average sessions within animal and then animals equally; they are descriptive, not inferential uncertainty estimates. Unequal full-session lengths are never silently pooled. Animal identities are operator supplied and remain unverified. The 36,158 pairs are not independent animals. No held-out-animal improvement panel or confidence interval is claimed.

## Interfaces and usage

`mint_reference.py` needs only Python 3.10+ standard library. `prepare_mat.py` optionally uses an existing NumPy/SciPy runtime; it never downloads files or installs packages. It requires an explicit MAT root variable, every session's animal ID and complete neuron ID list. Sample IDs created by this adapter are MAT column indices, not authenticated biological trial IDs. The adapter rejects continuous traces instead of inventing discretization. MATLAB v7.3/HDF5 support is not implemented; no file format has been inferred for the actual supplement.

A packet has `schema_version: 1`, `task_id: PAPER-paper-method-012`, `data_kind` equal to `generated_engineering_control` or `operator_prepared_unqualified`, `expected_session_ids`, and `provenance` with `source` and `binning_status: fixed_input_labels_native_provenance_unverified`. Each session has `session_id`, `animal_id`, `neuron_ids`, unique `sample_ids`, `ordering: acquisition_order`, integer `stimulus` labels, and `neural` rows in samples-by-neurons order. At most 12 occupied stimulus states are accepted. The exact binning/support provenance remains a separate gate. See the generated packet fixture in the test file for a complete example.

From the implementation directory:

```sh
python3 prepare_mat.py /approved/local/input.mat /local/packet.json \
  --root-variable Hippocampus_data --identities /local/session-identities.json
python3 mint_reference.py /local/packet.json /local/result.json \
  --sample-sizes 64 128 --null-mode iid_permutation --null-count 30
python3 mint_reference.py /local/packet.json /local/temporal-diagnostic.json \
  --sample-sizes 64 128 --null-mode circular_shift --null-count 30
python3 -m unittest discover -s tests -v
```

The example counts are prospective examples, not published values or validated CA1 choices. Defaults are seed zero, 30 null transformations, two subsample repetitions and four QE repetitions. Only seed zero and 30 IID shuffles correspond to observed figure-wrapper options; other schedule/RNG/aggregation choices are explicit engineering proposals. The output binds the packet, canonical source identity, source revisions, protocol and each schedule by SHA256. Each output holds `scientific_qualification: unknown` and `native_equivalence: unverified`.

## Validation and remaining work

Generated engineering controls cover exact independent/product and binary-noise information values, XOR and redundant responses, exhaustive 24-permutation negative correction, QE polynomial recovery, within-subset IID histogram preservation, cyclic shift ordering, complete pair/session coverage, unbalanced full-recording retention, malformed input rejection, the actual CLI, and generated MAT readthrough. These checks establish numerical/source behavior only. They do not reproduce the paper, validate authentic CA1 observations, measure native MATLAB resources, or establish baseline competence.

Remaining empirical gates are supplement rights and exact bytes/schema; source-to-supplement naming and label provenance; spatial-bin conflict; complete 11-session/seven-animal identity mapping; repaired native MINT comparison; frozen claim-specific outputs, tolerances and grading; protected references and independent improvement population; resource envelope; and model/source exposure. PID/BROJA, detailed information decomposition, population decoding, other electrophysiology datasets, directed-information claims and all-paper reproduction are outside this additive component. No authentic data, native MATLAB run, model run, benchmark attempt, or scientific campaign was performed.
