# Purkinje morphology: portable PROGRAM source

This additive component implements the submitted-program interface for the existing **PAPER-FIND-REP-013** task. It reconstructs ten released Purkinje-cell trees from Busch and Hansel (2025), including all thirteen components, then compares every required keyed numerical output. It is one existing benchmark component, not another benchmark ID.

Read `TASK.md` for the scientific question, geometry conventions, units, coverage and interpretation limits. `SCHEMA.json` gives the output interface. The schema (`schema.py`) remains byte-for-byte identical to the accepted PROGRAM route. The current scientific scorer (`numeric_score.py`) includes the separately reviewed identity and signed-bias correction described below. The old binary artifact scorer is separate and unchanged.

This directory can be copied into a clean checkout without any private authoring modules. It contains source, public task text, schemas, input/reference **hash descriptors**, an unselected request template, and invented control cases. It does not contain released SWC arrays, private numerical answers, a model, or a provisioned container image.

## What is implemented and what remains

The public source now freezes the full program interface, stages the fifteen exact public inputs, freezes the chosen program before reading those input bodies, runs the candidate offline in an owned container, captures its five required output files plus optional opaque prose, and loads the five private numerical references only after proved candidate closure. Missing keys or cells receive no matched-subset score. Numerical values receive the original continuous diagnostics.

Source controls exercise those boundaries using invented files and a mocked closed transport. They do **not** qualify the new container bridge. This component remains unselected until an operator supplies an independently reviewed exact source, qualifies this exact runtime/bridge, provisions the original public inputs and private references, and admits a fresh finite action with current capacity and history evidence. No authentic-data run or native container run was made while preparing this export. The earlier accepted full-tree result is reused as provenance; it is not reclassified as a run of this new transport.

## Operator use

1. Run `python3 -I -S -B verify_source.py EXPECTED_SOURCE_LOCK_SHA256` against the externally reviewed source-lock hash. Run `python3 -I -S -B source_controls.py` for the invented unit controls. These steps use no released data, Docker, model or network.
2. Provision exactly the input members in `INPUT_PINS.json`. The original SWC release is [Zenodo 15066697](https://zenodo.org/records/15066697), CC-BY-4.0. The paper is [eLife RP105013](https://doi.org/10.7554/eLife.105013.3). The five accompanying task metadata files must also match their frozen descriptors; this export does not silently regenerate or download them. Private references stay outside this public directory and must match `REFERENCE_PINS.json`.
3. Qualify the exact runtime described in `RUNTIME.md`. A local immutable image identity is specified; obtaining or building a matching qualified runtime is an outstanding operator prerequisite. The legacy task Dockerfiles are not a recipe for this clean candidate image and are deliberately not substituted.
4. Prepare one exact operator-selected request from `SELECTION.template.json`. Supply source and native review receipts, current raw capacity evidence, the complete operator-adjudicated history and a fresh output path. The template deliberately fails admission. Preserve its exact bytes, hash and length with mode `0400`; the operator must serialize admission and reserve this attempt identity in its external ledger before invocation.
5. With the qualified host interpreter, invoke `python3.11 -I -S -B run.py SOURCE_LOCK_SHA256 /absolute/request.json REQUEST_BYTES REQUEST_SHA256`. No automatic retry, search loop or model campaign exists.

Review the full `RESULT.json` metric vector and closure evidence. A zero branch-length error can coexist with incorrect caliber, thin fractions or summary values. `OUTCOME.json` is operational evidence awaiting independent review, not scientific acceptance. If the process is interrupted or cleanup is uncertain, retain the output tree and reconcile the exact owned resources before any further action.

## Scope

This is an exposed-data morphology reproduction audit with source-excerpt and author-total assistance. It establishes neither full-paper reproduction, a paper-only versus official-code advantage, held-out improvement, a new neuroscience finding, donor-level inference nor Terminal-Bench acceptance. The capacity/history receipts are trusted operator adjudications bound by the selected request; the component validates their shape, pins and limits but cannot discover an entire organization's concurrent workloads or authenticate a reviewer's judgment by itself.

## Scorer revision: exact identity and signed bias

The current scorer rejects decimal identity tokens that become integers only after binary64 rounding, consistently rejects nonzero Unicode decimal underflow, and preserves small signed-bias cancellation residuals. RMSE, MAE, maximum absolute error, complete coverage and the output schema are unchanged. Ordinary bias can intentionally change in its last bits. This is a source correction, not a new authentic result. The earlier scientific results and `SOURCE_CONTROL_RESULTS.json` remain tied to the historical scorer/source lock. Fresh native qualification is still required for the revised source.

Submission receipts bind the scorer hash. An old receipt is refused by this revision; preserve historical attempts and grades, and freeze a new submission only under the selected revised source. No automatic regrading occurs.

Run the eight relocated numerical regression methods plus the scorer-receipt boundary check, using invented values only, from the repository root:

```sh
python3.11 -I -S -B components/purkinje-artifacts/test_numeric_score.py
```

The old scorer in `regression_fixtures/old_numeric_score.py` is a pinned regression fixture only. Production loads the single current scorer from `program-v1`; fixtures contain no authentic reconstructions or reference answers.
