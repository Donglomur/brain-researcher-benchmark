# NEURAL-022 artifact-grading software

This MIT-licensed software grades a complete, committed92-row active-to-passive velocity prediction artifact. It includes the existing numerical evaluator and its bounded file readers. It does **not** include the neural data, actual case roster, target/reference arrays or operator manifest. Operators must separately supply an authorized local packet. Installing this component alone does not make the neuroscience benchmark runnable.

The scorer never runs submitted Python or fits a model. Its five runtime source files are unchanged from the repository's reviewed portable scorer, including the bounded JSON snapshot repair. The `private/vendor` directory contains this project's authored helper code, not bundled official Neural Latents Benchmark software. NumPy is an external dependency under its own license; no NumPy source or binaries are vendored. The included MIT notice applies to this software, not external neuroscience data. Existing dataset redistribution permission remains unresolved; this package grants none.

## Install and generated check

Use a POSIX host (Linux or macOS), Python3.12 and the declared dependency in your existing environment:

```sh
python -m pip install -r requirements.txt
python -I -B tests/test_artifact.py
```

The test script uses temporary generated cases and arrays only. It tests the actual CLI from a temporary copy of these source files, strict complete-output validation, all seven comparisons and sixteen direction/mode strata, malformed inputs before private access, finite-overflow handling, file-size changes, symlink/nonregular substitution and descriptor cleanup. It neither downloads nor opens authentic data. Local source validation used Python3.12.14 and NumPy2.3.5. This dependency declaration is for the artifact reader and generated checks; it does not claim recreation of the original model-fitting environment.

## Required operator bindings

Keep real operator bindings and reference data outside public source distribution. Materialize the following files in a private working copy of this package, or use ordinary files with the same package-relative layout. Do not point symlinks at other locations; the unchanged reader rejects symbolic-link ancestors. The optional private/public data directories are ignored by this component's `.gitignore`.

1. `private/operator_manifest.json`: a UTF-8 JSON object containing `task_id:"NEURAL-022"`, `public:{"cases.json":descriptor}`, `private:descriptor`, and `expected_fixed_reference`. A descriptor is exactly the required `path`, `bytes` and `sha256` for an existing ordinary single-link file. Paths are canonical package-relative paths without `..`, backslashes or leading `/`; sizes and SHA256 must match the actual bytes. The operator manifest must fit32768bytes. Optional other public packet descriptors in an existing accepted manifest remain unused by this artifact grader.
2. The public case roster identified by `public["cases.json"]` (at most16384bytes): exactly `{"schema":"neural022_public_cases_v1","cases":[...]}`. Include92 unique ordered rows, each with `id` (24 lowercase hex characters), `mode` (`passive` or `active`) and integer `direction` in0,45,90,135,180,225,270,315. Exactly40 rows must be passive and52 active, with all eight directions present in each mode. Actual identities are not distributed here.
3. The private reference NPZ identified by `private` (at most65536bytes): stored, unencrypted ZIP entries with precisely `ids.npy`, `velocity.npy` and one member for every reference name below. `ids` is little-endian Unicode24, shape(92,), and every velocity/reference array is little-endian float64, shape(92,2), C-order, finite, in the same public ID order. The bounded reader accepts NPY1.0/2.0 headers, rejects extra/object/wrong-shape members and never enables pickle. Authentic data and reference bodies are not included.
4. `expected_fixed_reference`: the operator's independently established fixed scalar checks. It contains `losses`, with `passive` and `active` maps holding all seven reference names and their finite expected losses, plus `primary_active_minus_passive_neural_loss`. These values are not supplied here. The grader recomputes fixed-reference losses and checks them at the unchanged tolerance before judging the candidate; missing or inconsistent operator values are operator failures, not candidate losses. External provenance must bind these values and arrays to the intended accepted packet. Shape agreement alone is not scientific authenticity.

The seven names are `active_neural`, `passive_neural`, `active_mean`, `passive_mean`, `active_direction`, `passive_direction` and `zero`. The candidate is always `candidate_program`; its predictions cannot replace a fixed reference. No source-generated fake reference is a valid authentic benchmark reference. Generated tests demonstrate software behavior only.

## Submission and command

An external producer writes `predictions.json`, at most65536bytes:

```json
{"schema":"neural022_predictions_v1","predictions":[{"id":"<actual roster ID>","velocity":[0.0,0.0]}]}
```

The illustrative single row must be replaced by all92 actual IDs in exact roster order. Each velocity is two finite, nonboolean numbers. Extra fields, reordered/missing/duplicate/unknown IDs and malformed rows are invalid. The producer must use the accepted active-training-only method policy; artifact grading cannot prove fitting provenance, nontransductive selection, access history or producer termination.

After the producer stops, the trusted collector hashes its final prediction bytes and writes a separate commitment, for example `submission.json`, containing exactly `schema_version:1`, `task_id:"NEURAL-022"`, and `file:{path,bytes,sha256}`. Here `path` is relative to the commitment's directory, not the package directory. Do not substitute the prediction JSON itself for the commitment.

From the private package root:

```sh
python -I -B private/score.py \
  --submission /absolute/committed/submission.json \
  --output /absolute/reports/new-result.json
```

Use an existing ordinary report parent and a fresh output file. The reader validates a stable bounded descriptor snapshot and exact committed prediction hash; it does not overwrite reports. The complete public submission is validated before any private target/reference load. An invalid commitment can be reported without any operator data. A valid commitment with absent operator bindings is an operator error; the missing data is not silently replaced.

## Scores and limits

Primary loss is mean squared Euclidean two-axis nominal velocity error over all40 passive queries, in(m/s)². Lower is better. Active52-query results and all16mode/direction strata remain secondary, weighted by trial rather than by equal directions. All seven signed comparisons are candidate loss minus reference loss; negative is better for that reference. The private passive-neural comparator used extra passive calibration labels, so retain same-information active-direction results and do not interpret one favorable gap as neural-information gain. The original fixed active-neural-minus-passive-neural diagnostic remains separate from the arbitrary candidate's score.

The finite task is one exposed Han animal/session shared with other tasks:141 active training trials,65 units and six20ms bins, with a retrospective120ms movement-onset target. The input/refitting dataset is not provided by this grading component. This is not new animal replication, causal/online prediction, an unseen population test, native-LLM capability, whole-paper completion or SOTA evidence. The broader registered research specification and ordinary-program cost/lifecycle requirements remain unchanged.

Read the stored `status`: valid poor predictions remain scored, invalid submissions receive a null score, and extreme finite inputs may return `unsupported_numerical_result` with a null score rather than clipping. A stored `operator_error` returns CLI exit2; other stored dispositions return0. Therefore shell success alone does not mean valid or successful science. Output-writing errors may be nonzero exceptions. `producer_absence_verified` remainsfalse: this command is a trusted operator artifact grader, not a candidate sandbox or process supervisor.
