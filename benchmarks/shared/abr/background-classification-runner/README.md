# ABR protected fold runner source

This component supplies source rendering, protected fold orchestration, strict prediction validation and paired scoring for a 104-animal auditory brainstem response (ABR) classification endpoint. It is a source component with invented-data controls, not a qualified benchmark, a fitted reference, a model result or a ready-to-run authentic deployment.

Each of five waveform and five layout-only contexts receives all current input objects, its outer-training labels and four training-only inner folds. Frozen programs run in separate containers with fresh private state. All 104 predictions from each route must be committed after complete process/container closure before the single private scoring call. No scoring feedback is returned between folds. The primary score is pooled balanced accuracy at a fixed probability cutoff of 0.5; waveform-minus-layout performance is descriptive for this released cohort.

## Private preparation boundary

An authentic deployment requires maintainer-admitted private evaluator artifacts. They are deliberately absent here. A separately reviewed private preparer must validate the original deterministic labels and partitions, then produce an opaque manifest, a rebound completion document and a preparation receipt. Every label, animal order, five outer partitions, twenty inner partitions and state-policy field must match the validated original. Animal file inventories remain unchanged.

The public runner requires the operator-selected exact hashes of the preparation receipt, opaque manifest and completion before any candidate container starts. Its structural validator also checks complete class totals, outer/inner partitions and state policy. Structural validity or a self-authored receipt is not evidence of canonical assignment: the trusted maintainer must independently accept the preparation evidence and pin these artifacts. Candidate-supplied manifests or receipts are not supported. Original release identities, label-derivation code, private preparation source, data and evaluator artifacts are not distributed.

Projection changes the manifest digest. Corresponding prediction hashes and all scoring arithmetic remain unchanged when labels, animal order and assignments are preserved. Private export controls compare complete reports after mapping only that digest and verify every projected partition; public controls use wholly invented manifests and cannot establish authentic preparation.

## Local source checks

A POSIX host with Python 3.11 or later is sufficient for the standard-library source controls:

```sh
python3 -I -S -B verify_export.py
python3 -I -S -B tests/test_runner.py
python3 -I -S -B tests/test_boundary.py
python3 -I -S -B tests/test_lifecycle_edges.py
```

Tests create and remove small invented fixtures. Docker and network transport are forbidden by the fixture audit hook. These checks validate interface behavior and source boundaries; they do not establish real OS isolation, native numerical compatibility or scientific performance.

## Provisioning and remaining prerequisites

`provision.py` renders a fresh source-locked package from a hash-pinned metadata request. It reads source/request metadata only, creates an unselected run template and reports a prospective command. It does not read the packet or method bodies, connect to Docker, install packages or dispatch work. The rendered execution lock covers sixteen exact members, including the preparation boundary. Operator paths are supplied at rendering; no maintainer workstation paths are shipped.

Before any authentic run, maintainers must supply and independently accept the prepared opaque packet and receipt, frozen method pair, complete generated source, a suitable derived runtime image, and fresh capacity/socket/daemon evidence. The image is intentionally unbound. `RUNTIME_CONTRACT.json` preserves the required container versions and the existing host-owner restriction. The actual owner currently requires its reviewed Darwin CPython 3.11.6 executable identity and Docker executable location; portable source tests are not arbitrary-host owner qualification. The Linux/ARM64 scientific image must be built and independently reviewed separately.

The prospective campaign has ten contexts, 600 seconds/one CPU/2 GiB per candidate context, 7,200 active seconds, 7,320 inner seconds and 7,350 outer seconds. It retains the declared 20 GiB managed-read, 8 GiB retention and 1 GiB monitored host-RSS limits. These are allowances, not authentic observed costs. All existing source, runtime, pressure, swap/pageout, capacity, disk and cleanup admission requirements remain in force. No default live image or executable operation selection is provided.

## Interpretation and rights

Previously released data and labels remain exposed; opaque identifiers cannot erase memorization or prove pretraining provenance. Acquisition/batch confounding remains. No causal genotype, clinical, unseen-label, new-laboratory, SOTA or frontier-improvement claim follows from this component or its controls. `REFERENCE_RECIPES.md` describes prospective references, not completed fits.

The included implementation is covered by `LICENSE`. Data and articles are not included and have separate terms. This package contains no original raw data, authentic predictions, authentic label keys, private acquisition locators, signed URLs or private repository history.
