# NEURAL-005: next-recorded social choice

This local adapter scores completed rejection probabilities on the fixed816-case,7-person development panel. The target is the next consecutive round's choice within the same five-round partner episode:0=accept,1=reject. Lower equal-participant log loss is better. It also reports Brier score, AUROC, calibration means and signed comparisons with behavioral-history, prestimulus-baseline and full-ERP references. Negative improvements are valid; there is no pass floor.

Submit a UTF-8 JSON file with exactly:

```json
{"schema_version":1,"probabilities":[{"participant":"205","case_id":"205:1:1","probability":0.5}]}
```

The example illustrates fields only; use every exact identity in `public/cases.json` once. Row order is arbitrary. Probabilities must be finite numbers in[0,1], not strings or booleans. No extra keys, duplicated JSON fields, duplicate cases, missing cases or nonfinite constants are accepted. The file is capped at1,000,000bytes and must be an ordinary single-link file. A one-class participant has undefined AUROC but remains in log loss and Brier.

The scientific information contract permits only a completed current-trial prefix, with each prediction committed before the next round is revealed. The earlier trusted-reference experiment enforced that sequence. **This standalone file scorer does not run a candidate program or verify its chronology, training split, provenance or information access.** The public file here supplies case identities; a scientifically valid new candidate study still requires the separately reviewed prefix-delivery controller and training-only workflow. Do not expose the operator development table as a candidate input: its later prefixes reveal earlier targets.

Inputs for the underlying reference were processed ERP amplitudes joined positionally to behavior, not raw EEG. Independent ERP trial alignment and causal online preprocessing remain unresolved. This small historical-cohort development panel is not unseen population confirmation. The adapter is a local numerical-scoring component, not a completed research benchmark, prospective improvement evaluation or LLM comparison.

Run through the repository's common scorer after verification, or its exact declared `score.py --submission PATH --output FRESH_DIRECTORY`. It requires the pinned existing local Docker image and lazy workspace assets in `operator_assets.json`; it is not portable without those private artifacts. Candidate code is never executed by this entrypoint. All result files are written under the fresh output directory; reference and private source files are read-only. Host integrity hashing reads private bytes, while private JSON decoding occurs only after complete public submission validation inside the isolated grader.
