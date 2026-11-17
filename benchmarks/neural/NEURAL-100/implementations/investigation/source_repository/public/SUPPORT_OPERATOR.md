# NEURAL100: current support-consistent operator interface

This document selects `private/grade_support.py` as the current operator entrypoint. The command in the preserved `private/README.md` and the standalone `private/grade.py` are historical. Calling that legacy CLI bypasses the current support checks and is not a result from this successor. The scientific procedure in `public/TASK.md`, all 47 recordings from 41 participants, all eight conditions and the two source areas remain unchanged.

The complete successor adds five source/metadata members around the original 177 byte-pinned members. It retains the reviewed v2 companion and its source lock unchanged. The original export manifest is preserved as `private/support_consistency/parent_export_manifest.json`: only the companion's logical manifest lookup uses that alias. Private packet bindings, preparation provenance, selected neural arrays, estimator and numeric comparison are unchanged. The new export manifest must be pinned by a trusted operator outside candidate-writable storage; do not take its expected hash from a candidate.

Use CPython 3.12 with the preserved pinned `public/requirements.txt`. From the package root, after verifying the complete export, a future admission-only command is:

```sh
python -I -B private/grade_support.py \
  --package /absolute/package --export-sha256 OPERATOR_PINNED_EXPORT_SHA256 \
  --submission /absolute/captured/report.json --mode admit \
  --output /absolute/operator/fresh-admission.json
```

Admission captures only source/metadata and the submitted report. It validates all recording identities and every condition's recording-to-participant-to-area support and null propagation, including the unchanged shared 1,000 PCG64(100043) participant bootstrap schedule. Any undefined repeat makes its participant undefined; an undefined participant makes the full-area mean undefined. Observed-only summaries remain explicitly separate. Admission does not validate reported finite numbers against neural observations or certify scientific reasoning.

A future grading command uses the same entrypoint with explicit `--mode grade --packet /absolute/package/public/input`. Only after successful admission does it compute the unchanged reference once and compare once. It does not also invoke the legacy grader's `evaluate` function or CLI. The primary support flag includes every primary recording disposition as well as area support; a mismatch withholds the primary MAE. Finite numerical errors retain the frozen metrics.

Both modes publish at most 2 MB through the reviewed exclusive pending-file, file-fsync, exclusive-link, pending-unlink and directory-fsync sequence. Require an independently observed zero exit from the complete CLI plus the expected result. The marker `requires_observed_cli_exit_zero` is a requirement, not an exit attestation. A post-publication failure can leave a final file; its existence alone is not success. Existing final or pending outputs are not overwritten. There is no implicit retry or cleanup.

**Current qualification:** this is a source integration with generated software checks only. No full successor export has been assembled here; no authentic histogram, onset, candidate, reference or scorer was run. Runtime performance, scientific parity, empirical difficulty and submission readiness remain unverified. Retained historical preparation is not a new scientific result. The unchanged original scope has source area counts 39/8, unresolved against the manuscript's 31/16; native NWB click timing lacks independent calibration; layer assignments may be response-derived; unit observation intervals are absent; most source bodies were fetched as immutable-blob ranges rather than fully hashed. Reconstruction alone does not establish causal pathways or independent scientific reasoning.

The external operator must select and supervise scientific compute, wall time, CPU, RSS and storage; isolate any candidate process from private files; and hold the package and submission immutable. This entrypoint supplies no candidate sandbox or process/resource supervisor. Source hash checks do not protect against a malicious operator or compromised dependencies. Bootstrap validates descriptor identities for all original members and captures the pinned source/metadata needed for admission; it does not reread all 177 payload bodies. The future unchanged data adapter checks prepared members when grading, and a separate complete export verification is required. Candidate JSON retains the original 64 MB cap. Source/bootstrap metadata is individually bounded; these limits are not measured peak memory or runtime.
