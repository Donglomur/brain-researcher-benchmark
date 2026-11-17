# NEURAL-034 portable operator package

This package runs the existing complete selected seven-mouse context-prediction task: seven independent folds, 120 training and20 query windows per fold,140 query predictions, equal-mouse balanced accuracy and log loss, and all six fixed comparators. It accepts an arbitrary single Python source program; numerical agreement with a reference program is not required.

This is one already-counted historical finite task. It adds no benchmark ID. The broader original neural-data investigation, unpublished generalization, causal memory interpretation and agent/model evaluation remain separate.

## What is distributed

The existing owner, scheduler, output collector and numeric grader are copied with an explicit source map. The numeric grader and seven-fold execution/scoring order remain unchanged. Adaptations concern relocatable source closure, transport settings and historical cost-lineage admission. There is no new execution controller or scorer.

All authentic input bodies and all historical outcome/authority records remain external. INPUTS.json binds ten exact operator-provisioned objects: seven fold NPZs, the public case roster, private labels and private comparator results. The entire workspace is operator-only. Another fold's training labels can reveal the current fold's answers, so never expose the package's input tree or all seven NPZs to a candidate/model. The existing runtime mounts only the active NPZ and creates fresh writable state for each fold.

SOURCE_MANIFEST.json identifies every distributed member except itself. An operator must authenticate that manifest against the release's independently supplied pin. The runtime SOURCE_FREEZE.json separately pins every executed dependency. History in HISTORICAL_EVIDENCE.json is documentary and grants no authority.

## Provision a workspace

Create an external JSON object mapping exactly these roles to already-authorized local ordinary file paths: fold-00 through fold-06, public_panel, private_targets, private_references. INPUTS.json supplies the immutable extents/hashes; no downloader or data redistribution is provided.

```sh
python3 -I -B provision.py --manifest-sha256 RELEASE_MANIFEST_SHA256 \
  --inputs /operator/input-locators.json --workspace /operator/neural034-workspace
```

This copies only authenticated source and ten complete input members into a new0700 operator workspace. Copies are single-link ordinary files; no symlink or existing destination is followed. The operation preserves partial results and a partial or provisional receipt if it stops. A copied-input receipt never independently establishes terminal success: require natural zero exit within the selected outer deadline. The final setup, receipt and terminal acknowledgment each check the same120-second clock. Source/input traffic is below64MiB and logical copied content below40MiB; source code uses64KiB stream chunks. This is not a hard externally enforced lifetime/RSS admission. Arrange an appropriate bounded owner/admission before authentic provisioning; this source delivery performs no such copy.

The image is exactly `sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`. It is not supplied, built or replaced with9aaf. Its availability, Engine routing and current compatibility require external qualification. Image and per-container limits do not establish Docker VM RSS; no4GiB VM maximum is claimed.

## Prepare and execute a submitted program

The templates directory supplies a complete disabled operator-review/allocation shape and an example ten-input locator map. Nulls and disabled flags must remain inactive until the operator supplies genuinely current evidence and selection. These templates cannot launch the owner and do not stand in for runtime qualification or the original private historical records. All nonempty DOCKER_ settings except the explicitly replaced HOST/CONFIG are refused, including API-version overrides; remove other such inherited settings before a selected invocation.

Read `authoring/glial-context-v1/ordinary-completion-v1/TASK.md`. Supply a UTF-8 Python source of at most65,536 bytes, accepting `--input DIRECTORY --out DIRECTORY` and writing only `probabilities.json`. It receives one NPZ with training labels and20 unlabeled query windows. It may fit any allowed model using only that active training data. The same source is committed before the first fold and cannot be revised between folds.

Place the candidate in the operator workspace's candidates directory. Provision the exact external previous closed cost receipt and its evidence, current complete-image/storage capacity records, whole allocation, independent current source/runtime qualification and a new owner review under operator-controlled paths. The historical 480-second route already completed a reference-derived programme, but its outcomes qualify only the original source/runtime. The last known closed cost3159.932040249051 seconds is not a complete lifetime ledger and must not be reset to an earlier adoption subtotal.

The review must use the existing `go_neural034_ordinary_completion_v1` schema/fields and additionally `portable_runtime`: exact image, absolute docker_binary, local unix docker_host, an exact external qualification descriptor and qualified=true. The qualification record must bind the same task/image/transport. These are trusted operator attestations requiring real evidence, not claims produced by this package. The transported runtime must be qualified for this relocated source before setting them true. The original capacity policy, all-image census,15GB floor, known-cost arithmetic, explicit other reservations and current-freshness checks remain mandatory.

```sh
cd /operator/neural034-workspace
export NEURAL034_DOCKER=/qualified/path/to/docker
export NEURAL034_DOCKER_HOST=unix:///qualified/path/to/docker.sock
unset DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
python3 -I -B authoring/glial-context-v1/ordinary-completion-v1/run.py \
  --program /operator/neural034-workspace/candidates/submission.py \
  --out /operator/neural034-workspace/artifacts-build/candidate-001 \
  --review /operator/neural034-workspace/operator/current-review.json \
  --other-reserve-bytes YOUR_REVIEWED_INTEGER_RESERVE
```

The executable refuses missing or mismatched explicit transport, external qualification and current operator review. Provisioning is not execution admission. The existing owner retains480 seconds total/420 work/60 cleanup; each candidate receives20 seconds,1.75CPU,3GiB and two numerical threads. Those are per-role task limits, not proof of a current host/VM allocation. Every candidate/holder/volume closes before the next fold. Both private metrics and all six comparisons are produced only after all seven outputs close.

## Inspect outputs

```sh
python3 -I -B check_result.py --output /operator/neural034-workspace/artifacts-build/candidate-001
```

The checker verifies the complete commitment chain, all140 probabilities, all seven closed units, exact aggregate/program/grade hashes, both metrics and all six comparators. It does not open labels or recompute science. It checks consistency of trusted-owner records, not independent authenticity of forged receipts or runtime qualification.

Keep failed, incomplete or invalid attempts. Do not score a subset of folds, select only a better metric, replace failures with the reference, or claim a reference-parity threshold. All six comparators and seven per-mouse results remain visible in the preserved grade. Existing baseline observations include a worse log-loss result and must retain that context.

## Source checks and current limits

`python3 -I -B tests/test_relocation.py` uses generated files and pure source/metadata fixtures only. No Docker, neural input, model or baseline programme is run. It checks relocation, exact source pins, complete external-input mappings, once-only workspace destinations, transport refusal and preserved scientific/closure structure. These checks do not establish authentic numerical or deployment compatibility.

Paper/data provenance: DOI10.1038/s41593-026-02448-0, Zenodo21780255, official rsenne/dCA1_Paper. The selected processed subset and unresolved ROI/session normalization, behavior polarity and context/day order retain the historical scientific limits. Source-safe descriptors do not confer input redistribution rights.
