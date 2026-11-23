# Bounded MindEye2 retrieval scoring

This component makes the original feature-level retrieval endpoint executable
without copying both complete feature populations into float64 RAM. It advances
the scoring path for both **reproducing the original finding** and **exceeding it
on the same task**. Neither outcome has been demonstrated here.

The predecessor converts each 1,000 × 425,984 array to float64 before scoring:
the two conversions alone allocate 6,815,744,000 bytes, before normalization,
alignment or sampled-pool copies. This implementation authenticates and maps
the input NPY files, obtains overflow-safe normalization in small row blocks,
and accumulates the cosine matrix in feature-column tiles. It then applies the
unchanged 30 frozen pools of 300 images to the shared cosine matrix. Each input
is traversed for normalization and for dot products, in addition to the file
authentication pass. No normalized full-population copy or new output array file
is created.

At the default sizes, one normalization row block holds 27,262,976 float64
bytes, each feature tile holds 8,192,000 bytes, and the complete cosine matrix
holds 8,000,000 bytes. Input conversion, temporary tiles, matrix products, and
library buffers add allocations. These numbers describe array allocations,
**not a measured peak RSS guarantee**: mapped pages and the operating-system
file cache are separate. No production-width workload was run, and no speedup
or native resource qualification is claimed.

## Original comparison preserved

- The admitted reference has all 1,000 shared image identities for one of
  subjects 1, 2, 5, or 7. Candidate rows are reordered by exact identity; no
  rows, subjects or retrieval pools are silently dropped.
- Both feature populations have 256 × 1,664 OpenCLIP ViT-bigG-14 token
  coordinates. Features flatten in C order. Fortran-order storage is rejected
  because reshaping it could silently create the large copy being avoided.
- Image retrieval queries brain rows against image columns; brain retrieval
  reverses the same matrix. Maximal ties fail explicitly, as in the predecessor.
- The existing frozen pool schedule is an input. This module does not resample
  pools, reconstruct the notebook's historical RNG state, or treat overlapping
  pool draws as independent people. It reuses the predecessor's summary code.
- Source normalization exposure, first-session adaptation, post-model repeat
  handling and the seven-other-subject pretraining condition still require
  their own authenticated source path. This scorer does not apply the
  predecessor's prospective session-disjoint exposure restriction to the
  original shared1000 task.
- All four subjects and the complete reconstruction companion panel remain
  required for a paper-level result. Published corrected retrieval 0.574,
  a local author rerun, a candidate score and a current-SOTA result are distinct.

Row normalization and feature-tiled accumulation are mathematically equivalent
to full-vector cosine scoring. Their floating-point reduction order can differ
from a dense CPU operation and from author GPU float16/TF32 arithmetic. The
generated controls test dense agreement and exact retrieval decisions on a
nondegenerate generated population. They do not qualify native parity or
decisions at near-ties. Native numerical/tie behavior remains an explicit gap.

## Use

Python and an existing NumPy environment are sufficient. No installation,
download, learned model execution or neural preprocessing is performed.

```sh
python streaming.py \
  --reference /operator/reference.json \
  --reference-sha256 TRUSTED_RAW_FILE_SHA256 \
  --candidate /operator/candidate.json \
  --image-features /operator/image_features.npy \
  --brain-features /operator/brain_features.npy
```

The reference fields match the predecessor except that `contract_sha256`
now binds the current original-task `improvement.v1.json` at
`97752be74ac2af84fbd8441f50e2f4e9ba1e2a518d0b90ec553f8d08d19890b0`.
This is a contract commitment, not an admission of an improvement win. The
canonical task and historical implementation are unchanged.

Required reference fields are `task_id`, `contract_sha256`, `code_revision`,
`dataset_revision`, `subject`, `image_ids`, `retrieval_pools`, `feature_space`,
`image_features_sha256`, `population_manifest_sha256` and
`feature_extraction_receipt_sha256`. The fixed feature space is
`openclip:ViT-bigG-14:laion2b_s39b_b160k:256x1664-tokens`.
Candidate fields are `reference_manifest_digest` (the predecessor's canonical
JSON digest), `image_ids`, `subject`, `feature_space`, `brain_features_sha256`,
`checkpoint_sha256` and `exposure_ledger_sha256`. A hash commitment does not
independently attest its biological contents or training exposure.

Each feature file must be one complete primitive real-numeric, C-order NPY
version 1 or 2. The loader hashes the same opened file it maps, rejects object
and complex arrays and trailing payloads, keeps the mapping read-only, and
checks for file identity/size/time changes before returning a score. Source
files must remain immutable during evaluation. Arbitrary concurrent filesystem
mutation is not a supported security boundary. The operator must isolate target
features and reference identities from the candidate query interface.

`score_aligned_features` is the numerical control entrypoint and accepts
smaller feature widths. It has no paper admission result. `evaluate` requires
the complete original dimensions and identity commitments. CLI output is
written only after both file mappings finish their final mutation checks.

## Source and qualification

The source is the [author evaluation notebook at revision
76a2609](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/final_evaluations.ipynb),
retrieval cells `4f862220-1df3-49b0-a36c-0aa2f168315d` and
`2e49d57a-9b65-490c-a1e0-61bd05682171`, plus the corrected directions in
the [author README](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/README.md).
Existing official source-cache bytes were reused; no source download, authentic
feature read, target read, data preparation, model trial or installation occurred.

The earlier complete source package already contains original trial joins,
feature metric arithmetic and an unbound native graph bridge. Those were
inspected to avoid duplicating their work. This component specifically repairs
the full-population allocation problem in the currently registered evaluator;
it does not replace or reclassify those historical packages.

Generated tests exercise the complete 1,000-image, 30 × 300-pool numerical
schedule at reduced feature width, permuted candidate storage, dense cosine
agreement, bounded temporary shapes, opposite retrieval directions, scale
invariance, ties, hash and format errors, file mutation, current-contract
binding and native-width rejection. Source custody, native production,
production-width numerical/resource parity, author reproduction, reconstruction
companions, participant-aware uncertainty and a predeclared improvement decision
remain unqualified. Paired paper+data versus paper+data+author-code delivery is
outside this numerical component and remains required by the broader task.

## Complete retrieval query evidence

Pass `--include-decisions` to include protected operator evidence for every query
in both physical retrieval directions. The source-matched admitted geometry
remains 1,000 shared images and 30 frozen pools of 300 candidates: 9,000 queries
per direction and 18,000 decisions per subject. Each draw records its ordered
candidate identities; each direction records the ordered query identity,
predicted paired identity and correctness. The evidence includes the original
population order, pool commitment, explicit direction semantics and a canonical
JSON digest. It is generated from the same cosine matrix and shared winner
routine as the aggregate scores, without a second feature traversal. Default
calls retain the previous metric-only output shape.

`score_aligned_features(..., include_decisions=True)` returns `metrics`,
`decision_evidence` and `decision_evidence_digest`; its default remains the
metric dictionary. `evaluate(..., include_decisions=True)` and the CLI add the
latter two fields to the existing identity-bound result. Complete records add
memory and serialized-output cost; the prior array allocation estimates do not
bound those Python objects or output bytes. A plain three-identity numerical
control may use `retrieval_decisions_from_cosines`, but native `evaluate` still
requires all 1,000 rows and 425,984 coordinates.

These records are **protected scoring evidence** and include reference answer
identities. They must not be exposed to candidate agents as query observations.
The digest detects changes only relative to an independently retained trusted
commitment; it does not attest truthful model execution, native feature parity,
source identity, or training exposure. The records close one output-representation
gap for the feature scorer. They neither supply the complete reconstruction panel
or Figure5 transfer contrast nor justify reproduction, improvement, uncertainty,
readiness or a current-SOTA claim. Native ties remain rejected. All four subjects
and all remaining original-task source and execution requirements still apply.

Nine additional generated controls check complete 18,000-decision coverage,
identity joins after candidate storage permutation, independent dense-oracle
agreement, both physical directions, tie/nonfinite failure, detached identity
snapshots, strict option typing, unchanged native-width/reference gates and admitted-result
routing. The last routing control mocks the feature geometry/numerical result; it
is not a native-width execution.
These controls use reduced feature width and no authentic arrays or model runs.

## Validate the complete four-subject retrieval result

`cohort.py` combines saved `streaming.py --include-decisions` results for subjects
**1, 2, 5 and 7**. It uses only the Python standard library. The [paper's Table 1
caption](https://arxiv.org/html/2403.11207v2) specifies averaging those four
subjects; Section 3.3 describes the 300-way retrieval calculation and 30 draws.
The [pinned author correction](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/README.md)
binds **image retrieval** to a brain query choosing an image and **brain
retrieval** to an image query choosing a brain response. The component preserves
those corrected directions.

Create an operator-private JSON input with schema
`mindeye2-retrieval-cohort-input/v1` and a `subjects` list containing exactly four
objects. Each object has two fields: `reference`, holding the full reference
manifest used by `streaming.py`, and `result`, holding that subject's complete
scorer result with query evidence. This input is saved evaluation evidence, not a
participant submission format. Freeze and independently retain its raw-file SHA256
before invoking the command.

```sh
python3 -I -S -B cohort.py \
  --candidate /operator/candidate-cohort.json \
  --candidate-sha256 TRUSTED_CANDIDATE_FILE_SHA256 \
  --max-input-bytes 67108864
```

For each subject the validator requires the complete 1,000-identity population,
30 frozen pools of 300 candidates, and all 18,000 decisions across the two
retrieval directions. It verifies reference/pool/evidence commitments, query
ordering, each prediction's membership in its pool, and the correctness flag
against query/predicted identity equality. It recomputes each draw's accuracy and
checks the supplied mean, population-SEM and normal interval. The mean/SEM checks
allow only `32 * sys.float_info.epsilon` absolute roundoff between standard-library
and NumPy reductions. This numerical consistency allowance is not a reproduction
tolerance or an improvement margin. No new random draws or feature scoring occur.

All four subjects must declare the same shared1,000 stimulus set. Their pool
schedules may differ; the source contract does not require the union of the
30 random pools to cover every stimulus. The reported cohort mean equally weights
the four validated subject means. Source draw intervals remain Monte Carlo
summaries; the component supplies no pooled cohort confidence interval. Output
omits individual query and predicted identities while retaining commitments and
subject/draw summaries. Keep authentic input evidence and its outcomes under the
operator's protected evaluation custody.

To compare two complete arms, add `--baseline /operator/baseline-cohort.json`
and `--baseline-sha256 TRUSTED_BASELINE_FILE_SHA256`. The byte allowance is shared
across both files. Each candidate/baseline subject pair must bind the identical
complete reference manifest and pool schedule. The result reports candidate
minus baseline for each subject and for the two cohort means. It does not apply
an automatic paper-win rule or reinterpret overlapping query rows as independent
participants.

Internal consistency cannot establish that the recorded winners actually came
from the cosine calculation: fabricated but self-consistent records remain
possible unless protected operator execution authenticates their origin. Feature
production, checkpoint identity, native arithmetic, original population custody
and one-hour training/adaptation exposure still require independent qualification.
Consequently the output keeps native parity, scientific qualification and full
contract completion false and reproduction/improvement unknown. It does not
compare with a historical one-hour anchor based solely on these manifests. The
complete reconstruction panel and Figure 5 transfer comparison remain required
elsewhere for the registered paper task.

Run the generated controls with:

```sh
python3 -I -S -B test_cohort.py
```

They exercise complete four-subject decision records and a paired comparison,
hand-counted asymmetric subject scores, changed targets/references, corrupted
flags/means, missing support, corrected direction labels, digest checks and the
shared CLI input bound. They use no authentic feature arrays, images, models or
scientific scores.
