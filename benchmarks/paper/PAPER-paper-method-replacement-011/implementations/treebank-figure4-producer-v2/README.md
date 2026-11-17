# Treebank Figure 4 source producer

This additive owner/reference implementation reconstructs the original sentence-onset versus no-speech decoder through an external, unchanged author checkout. It prepares the full released contact inventory, invokes the original numerical functions, observes their actual samples and splits, and collects the supported Figure 4a–c outputs. It has **not** run on authentic recordings. It does not establish reproduction, improvement, complete Figure 4 agreement, or benchmark readiness.

The selected scientific target remains the complete Figure 4a–c result: the electrode map, the subject 10/T1cIf8 example, and the training-selected temporal/frontal curves. A partial implementation does not replace that target. This directory changes no canonical task, outcome, admission rule, or participant package.

## Original and new code

The external author checkout must be at `c54ba38eab7814538bc03b1b6d29a3f50f034e12` from [brain_treebank_code_release](https://github.com/czlwang/brain_treebank_code_release). `custody.py` checks its complete tracked tree, index and working bytes, rejects extra or ignored files, and checks the two independently recovered raw loader hashes. Git inspection is offline and noninteractive. The author files are never patched or vendored here.

The named wrappers in this directory are new benchmark code. In particular, the released author caller defaults to all contacts. `preparation.py` supplies a new paper-eligibility configuration through the author's existing `test_electrodes_path` interface. It removes the 133 published exclusions while preserving original label order and HDF5 indices. This is an explicit reconstruction decision, not a claim that the historical caller applied that mask.

`replay.py` composes the original Hydra configuration and invokes the original `run_subject_test` function. It preserves sampling, unstratified splitting, window slicing, preprocessing, training and predictions. It uses a new named collector instead of the author's generic summary operation. `observation.py` observes bound original function calls; it does not fit, predict, resample or substitute numerical operations. Its hooks also record actual dependency identities, which are observations rather than a validated runtime image.

## Full input support and outputs

Preparation requires the exact metadata artifacts pinned in `SOURCE_BINDINGS.json` and the verified original `data/all_trials.json`. It retains 10 subjects, 26 recordings, 1,707 recording labels, 19 recording controls, 1,688 neural labels, and 1,574 nominal eligible contacts after excluding 19 controls and 114 neural contacts. Subject 5's 140 eligible contacts remain in prediction support even though that subject is omitted from map and regional plotting. Missing coordinates never remove a contact from prediction support. Original recording IDs, including subject 6's nonconsecutive runs, are retained.

The native producer writes:

- `source_windows.json`: the actual original NumPy grid and integer slice requests, without inventing plot centers or trimming short terminal windows.
- `source_scores.sub_N.json` and `source_scores.json`: unchanged author training-CV and held-out ROC-AUC results, with subject checkpoints retained if a later failure occurs.
- `observations.jsonl.gz`: private scientific evidence containing sampled-event bounds, processed-transcript indices, split membership, labels, fold information and probabilities where observed.
- `figure4_components.json`: all supplied contact curves and peaks, the exact example, and map-coordinate joins with separate omission records. It explicitly leaves incomplete panel conventions unavailable.
- `provenance.json`: observed configuration, input identities, dependency identities, source checks, completion/failure, and same-case consistency as separate fields.

`support_checks.py` reports observed disagreements across contacts/windows without changing source samples, splits or outputs. A completed source computation can coexist with an unavailable same-case claim. Missing hooks or observations are not invented. An exhausted evidence budget fails the run rather than silently truncating required records. Earlier checkpoints and failure evidence remain inspectable.

The standalone `collect_figure4.py` reducer validates coverage only relative to its **supplied** manifest and window table. It does not authenticate original support. The native producer separately rederives preparation from the pinned metadata and obtains the grid from its actual original configuration. Optional regional reduction requires a complete supplied DK-to-group mapping and rejects ambiguous top-ten cutoff ties; an owner-supplied mapping is not thereby authenticated as the paper's mapping.

## Remaining source and execution limits

The original complete temporal/frontal DK grouping, top-ten cutoff tie convention, 95% display-interval formula, and nearest-pial/fsaverage projection artifacts are not qualified here. No SEM formula, new anatomy grouping or alternate plotting coordinate convention is invented. The published anatomy assignment count is distinct from the nominal eligible recording inventory. These gaps keep complete Figure 4 agreement unavailable while preserving usable source outputs.

The source balances the pooled examples and then performs an unstratified test split; the paper's balanced-test description is not silently enforced by changing that split. Actual terminal windows can be shorter than their requested duration. Source sampling and class mappings are observed, not assumed identical across contacts. Transcript indices refer to the processed dataframe rather than original CSV rows.

The published exclusion identities do not settle the historical seizure-interval preprocessing. No interval mask is invented. Input hashes bind bytes to an owner declaration; they do not independently establish original-release identity, upstream preprocessing, or immutable data throughout a long run. Original configuration composition, dependency compatibility, recording readability, memory and wall time remain unexecuted. Missing model/criterion configuration is obtained only from the verified original checkout; no replacement runtime stubs are provided.

## Owner/reference boundary

The original checkout, producer recipe, output scores and observation stream are owner/reference materials. They must not be delivered as participant tools or inputs in the paper+data arm. This implementation does not enforce arm isolation or implement participant packaging. The observation stream includes labels and probabilities and is **not participant-safe**.

Future native execution needs admitted original inputs, a qualified runtime and a separate resource protocol. `--max-evidence-bytes` bounds uncompressed serialized observation records only; it does not bound native peak RAM, total output size, wall time, or the memory used to construct one record. Thread environment variables are not a resource sandbox. No downloads, installation or fallback scientific runtime are implemented.

## Explicit preparation and future execution

The following commands are an interface specification, not evidence of execution. Run from this directory in an admitted environment, with external paths replacing the placeholders. Output directories must not already exist, their parents must exist, and all output/data must remain outside the clean author checkout.

```sh
python -I -B preparation.py \
  --source-checkout /admitted/author-checkout \
  --labels-zip /admitted/metadata/electrode_labels.zip \
  --excluded-json /admitted/metadata/published-exclusions.json \
  --subjects-zip /admitted/metadata/subject_metadata.zip \
  --localization-zip /admitted/metadata/localization.zip \
  --output /private/new-preparation

python -I -B replay.py \
  --source-checkout /admitted/author-checkout \
  --labels-zip /admitted/metadata/electrode_labels.zip \
  --excluded-json /admitted/metadata/published-exclusions.json \
  --subjects-zip /admitted/metadata/subject_metadata.zip \
  --localization-zip /admitted/metadata/localization.zip \
  --prepared /private/new-preparation \
  --data-root /admitted/original-data \
  --transcripts-root /admitted/original-transcripts \
  --input-manifest /private/admitted-inputs.json \
  --runtime-identity qualified-runtime-record-id \
  --max-evidence-bytes OWNER_ALLOCATED_UNCOMPRESSED_BYTES \
  --output /private/new-replay
```

The input manifest schema is `treebank-owner-frozen-inputs/v1`, with `task_id`, a nonempty `source_provenance` object, and `files`. Every file entry has exactly `root` (`data` or `transcripts`), `relative_path`, positive integer `bytes`, and lowercase hexadecimal `sha256`. Its membership must exactly cover the prepared label/recording metadata plus every original HDF5, timing CSV and required movie transcript. Metadata member bytes must match the published ZIP members. `expected_inputs(prepared)` exposes that concrete file join without loading recordings. Source provenance and runtime identity remain owner-supplied accounts until independently admitted.

Use the completion status and successful post-run source check in `provenance.json`, not merely output-file presence. Failed or incomplete execution retains inspectable products but cannot support a completed source-run claim. Even a completed receipt does not qualify scientific outcomes.

## Construction verification

The generated-only suites contain 21 producer/structure controls and 14 observation controls. They passed during construction using fake metadata, fake call frames, mocked numerical entrypoints and temporary Git fixtures. They exercise complete declared support, staged source injection, offline Git, training-only selection, ambiguous ties, multi-subject observer lifetime, failure receipts, missing observation coverage, and observational case disagreement. No original model, recording, fitted reference or scientific result was executed by those tests.

```sh
python -I -B tests/test_producer.py
python -I -B tests/test_observation.py
```

Independent source and technical reviews are retained in the external construction evidence. Passing these controls establishes bounded implementation behavior, not authentic runtime compatibility or scientific agreement.
