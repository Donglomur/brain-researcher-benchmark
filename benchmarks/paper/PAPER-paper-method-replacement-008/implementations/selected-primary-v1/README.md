# Selected BaRISTA language comparison

This operator scorer implements the already selected scope in
`improvement.primary-scope.v1.json`. The retained six-endpoint scorer still requires
volume, optical flow, all masking scales and two external baselines. Those are
useful wider-paper evidence, but they are not prerequisites of the selected
fixed-channel-mask language comparison. Neither predecessor is modified.

The new input binds the exact selected scope digest and contains all 420 language
contexts: seven people, five fine-tuning seed slots, the original random partition
and all five chronological folds. Source seed slots 1–5 mean the retained source
seeds 0–4; the scorer does not generate partitions or seeds. Every context requires
three pretrained encodings with channel masking, their three matching random
controls, and one unrestricted candidate output in each information arm. This is
5,880 output arrays for one paper task, not additional benchmarks.

Four endpoint reports retain 35 or 175 cells per model, all per-person repeated
results, candidate/reference AUC and paired gain. The 24 source-condition summaries
per arm are separate reproduction evidence. A regression in one endpoint remains
visible; there is no across-task primary score, significance test or paper-win
decision. Random controls are reproduction obligations, not improvement targets.

The trusted parcels/channels comparator is inherited from the existing numerical
comparison route. Its competence, execution, checkpoint history and exposure are
explicitly unqualified. A candidate's submitted source-control probabilities never
replace this independently supplied reference. Authentic input identities, original
partitions, person-6 session correspondence, preprocessing, source SEM parity and
valid improvement criteria remain unresolved. Reporting seven person summaries
does not establish independence from shared movies.

## Inputs and use

The JSON schemas are closed by code:

- Public: `schema=barista_selected_primary_panel_v1`, `task_id`,
  `source_protocol_sha256`, `scope_contract_sha256`, `generation_commitment`,
  `panel_id`, and complete ordered `contexts`. Context fields are the original
  `id,protocol,person,task,fold,seed,query_count,query_ids_sha256`. The panel hash is
  the retained canonical JSON digest excluding `panel_id`.
- Submission: `schema=barista_selected_primary_submission_v1`, `task_id`,
  `panel_id`, and complete ordered `predictions`. Each contains
  `id,arm,model,query_ids_sha256,values`. `outputs(public)` defines the complete order.
- Gold: `schema=barista_selected_primary_gold_v1`, `panel_id`, exact
  `public_sha256`, `baseline_model=barista_parcels_channels`, and 420 ordered
  `contexts`. Each binds `id,query_ids_sha256,labels,trusted_parcels_channels,
  provenance`. Provenance retains the six program/config/checkpoint/exposure/
  execution/artifact digest fields from the existing comparison route.

Array descriptors reuse the pinned primitive finite NPY transport and relative
basename rules. Complete candidate/control admission precedes gold-manifest access.
Arrays are verified again during scoring. Both arms use the same independent
reference, while their candidate/control predictions remain separately reported.
There is no participant execution, sandbox or evaluator-custody claim.

```sh
python3 -I -B score.py --public /operator/PUBLIC.json \
  --gold /operator/GOLD.json --submission /candidate/SUBMISSION.json \
  --out /operator/new-result.json
```

Use a fresh dedicated interpreter with the already required NumPy dependency.
Five exact predecessor source hashes are checked before imports. `_grade_bytes`
is a trusted operator internal seam: its delayed gold supplier is fixed by the CLI
to the private file reader and is never supplied by a participant.

The maintained `test_score.py` controls use a complete generated identity grid and
four tiny invented NPY files. They test scope substitution, omissions, query swaps,
off-primary replacement, independent-reference use, full numerical reporting,
undefined-support retention and last-artifact rejection before gold access. Their
results do not establish scientific reproduction, model performance or readiness.
CI enrollment is proposed as the single component command
`python3 -I -B test_score.py`; no central manifest is changed by this package.

## Assemble per-run predictions

`assemble.py` builds the scorer's submission from independently produced run
receipts. It requires every selected context, source control and candidate in both
information arms. Run receipts may be listed in any order; each probability vector
must already follow its context's frozen query order. The assembler checks the
actual ordered query-ID list against the public digest and refuses omitted,
duplicated or reordered queries. It retains the original probability bytes.

Put all receipt JSON files and their NPY probability files in one directory. A run
receipt has exactly these fields:

```json
{
  "schema": "barista_selected_primary_run_v1",
  "panel_id": "<public panel_id>",
  "id": "random_nonoverlap-sub1-sentence_onset-f0-s1",
  "arm": "<one value from score.ARMS>",
  "model": "barista_parcels_channels",
  "query_ids": ["<each actual query ID, in probability order>"],
  "values": {
    "path": "run-probabilities.npy",
    "bytes": 0,
    "sha256": "<SHA256 of the complete NPY file>",
    "shape": [0],
    "dtype": "<f8"
  }
}
```

The zero values and angle-bracket strings are placeholders, not valid inputs.
`values` is the unchanged primitive NPY descriptor used by the scorer. Provide
one finite class-one probability per original query; the source uses
`torch.softmax(logits, dim=1)[:, 1]` in
[the pinned author training code](https://github.com/ShanechiLab/BaRISTA/blob/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/train.py).
An AUC log, two-column logits, hard labels, or a missing row is not a substitute.

`RUNS.json` has exactly `schema=barista_selected_primary_run_index_v1`, the same
`panel_id`, and `runs`: a list of all 5,880 distinct receipt JSON basenames. Every
receipt binds its own context, arm and model. NPY filenames may be shared where
the actual bytes are identical; identities and obligations remain separate.

```sh
python3 -I -B assemble.py --public /operator/PUBLIC.json \
  --index /candidate/RUNS.json --out /candidate/SUBMISSION.json \
  --max-output-bytes 32000000
```

The output must be fresh and beside the index/NPY files so relative array paths
remain valid. The explicit output allowance includes the manifest's trailing
newline. Complete receipt identity and numeric admission precedes any output.
No gold file is accepted or opened. Python producers can call `write_submission`
with the same complete list of receipt dictionaries to avoid intermediate files.
`test_assemble.py` exercises the real CLI with all 5,880 generated receipt files,
then verifies scorer admission of its output. It also covers shuffled run order,
query-order errors, missing controls, malformed probabilities and refusal before
writing. It uses four-element invented arrays, not neural data.

This is a submission assembly component, not the missing native inference
collector. It cannot recover query IDs or probabilities from rounded logs,
authenticate a checkpoint or execution, repair the author's skipped all-zero
inputs, establish arm isolation, or create an original public panel. Those remain
separate prerequisites for scientific use.

## Source basis

[The primary manuscript](https://arxiv.org/html/2512.12135v1), Tables 2 and 17,
contains the spatial encoding comparisons under fixed channel masking for both
language tasks. These selected cells are already the canonical local scope;
the paper also reports broader comparisons, which this component does not claim.
The scope policy and pinned local author-derived transport/metrics are recorded in
`SOURCE_BINDINGS.json`. Browser inspection is not a fresh authenticated manuscript
capture. No data, checkpoint, fit or model output was acquired or executed here.
