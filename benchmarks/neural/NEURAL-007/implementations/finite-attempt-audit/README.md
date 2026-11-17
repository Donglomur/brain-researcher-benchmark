# Sleep attempt commitment and completion audit

This component closes the finite sleep programme's observable freeze-order gap. It wraps the existing `benchmarks/shared/frozen-neural-lifecycle-v1` runner; it does not create another runner, benchmark, model condition, or grader. An operator commits the complete source bundle and explicit `CONFIG.json`, retains an external commitment witness, executes the existing independent development-person processes, and receives a separately retained completion witness only after every lifecycle and output check passes.

The complete original panel remains `development-001` (2,780 epochs) and `development-002` (2,670 epochs), with six training people, the same public features/common-model outputs, and the same five classes. The unchanged original candidate adapter validates the combined NPZ. Its probabilities must equal the admitted per-person responses. All 5,450 rows are required before any private scoring; no mask, crop, dropped person, score floor or metric change is introduced. The existing equal-person fixed-five-class macro-F1 grader and YASA/RF comparators remain separate and unchanged.

## What is checked

`commit` calls the existing source commitment, requires a nonempty JSON object in the bundled `CONFIG.json`, and writes a fresh witness outside both the attempt and original method source. Source, configuration, interpreter executable, runner, packet and initial stage records are bound before the first candidate development dispatch. Configuration covers the method's declared choices and should include fitting/selection policy, seed and dependency expectations. The whole submitted tree is committed; source, config or extra-file changes refuse subsequent operations.

`complete` requires the independently retained commitment digest, calls the existing `execute` and `freeze` once, and independently checks the exact 11-stage successful history. It joins both per-person requests, copied source/training/current-person inventories, process identities, successful exit/reaping/group-absence observations, resource receipts, output pins, and native NPZ values. It writes an exclusive-create, fsynced completion witness containing every stage pin and the final head. Failure, incomplete history, source changes or invalid coverage cannot produce that witness. A failed attempt remains in place and needs a new attempt; it cannot resume as success.

`verify` requires the previously retained commitment and completion digests. It checks the complete history and all artifact joins again. This detects a deleted suffix as well as an internally rehashed replacement history. Store the printed digests in independent operator custody when the witnesses are produced; rehashing whatever witness happens to exist later defeats the anchor. Filesystem permissions and SHA256 links alone are not a remote timestamp, signature or adversarial security boundary.

## Scope and limits

This is evidence for the **LLM-written programme condition**. It does not demonstrate native/direct-response signal understanding, scientific improvement, contamination-free evaluation, or training-only prior authorship. The two development people were already exposed. Nothing here repairs or retroactively qualifies historical pilot attempts.

The claim starts at this workflow's commitment. `prepare` already opens/copies public development assets, and neither a receipt nor a source hash proves what an author saw, computed, or selected beforehand. The committed source may itself contain undeclared prior knowledge. The operator must separately assess declared training-only method selection; this audit cannot infer semantic independence from bytes.

Execution is trusted shared-host orchestration, with separate process/scratch/output per person and no previous person's outputs in the request. It is **not hostile-code filesystem/network isolation**. Same-user access, escaped sessions, external files, stdlib/site-package changes, covert state and malicious operator rewriting remain outside the claim. The submitted tree and executable are pinned; the complete dependency environment is not. The existing runner's authentic hard-memory route requires Linux and refuses unsupported hosts before candidate execution. Small generated controls may execute on other hosts; they cannot pass the public authentic audit route.

The retained source implementation includes protected full-153-night machinery, but this audit does not launch, alter, or qualify that programme. The finite lifecycle dependency must be integrated first. Exact reviewed dependencies are in `DEPENDENCIES.json`; changed bytes fail before import. No source-pin override is offered.

## Operator sequence

The following describes a future authorized execution; building/testing this component grants no model, data campaign or grading allocation. Use the existing lifecycle `prepare --task NEURAL-007 --asset-root ... --run ...` with its exact allowlist. Put the entire method, `candidate.py`, `METHOD.md`, and `CONFIG.json` in a separate source directory. The existing ABI is `candidate.py --request REQUEST.json --output predictions.json`; candidate code can read its bundled configuration relative to `__file__`.

From the repository root, use the same qualified Python runtime for all steps:

```sh
python3 benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/audit.py commit \
  --run /operator/attempt --source /operator/method --witness /operator/witnesses/commit.json

python3 benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/audit.py complete \
  --run /operator/attempt --witness /operator/witnesses/commit.json \
  --witness-bytes COMMIT_BYTES --witness-sha256 COMMIT_SHA256 \
  --final-witness /operator/witnesses/complete.json

python3 benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/audit.py verify \
  --run /operator/attempt --witness /operator/witnesses/commit.json \
  --witness-bytes COMMIT_BYTES --witness-sha256 COMMIT_SHA256 \
  --final-witness /operator/witnesses/complete.json \
  --final-bytes COMPLETE_BYTES --final-sha256 COMPLETE_SHA256
```

Use the successful verification's exact `submission` pin when admitting the original `submission.npz` to the existing protected grader. This module never opens private labels or invokes grading. Calling the old finished-file scorer directly still gives only a finished-file score and does not acquire this programme provenance. Preserve the anchored pre-grading history; the existing runner's optional grading operations append additional records and are outside this completion audit's 11-stage contract.

## Engineering controls

```sh
python3 -B -m unittest discover \
  -s benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/tests -v
```

Before integration, `SLEEP_LIFECYCLE_DIR` may locate the exact reviewed lifecycle source; it does not relax its pins. Controls execute tiny generated constant programmes at the real 2,780/2,670 geometry and inspect no authentic predictions or private targets. They cover commitment order, explicit config/source mutation, unsuccessful execution, source/request/resource joins, witness tampering, hash-consistent history rewrites, missing/reordered records, full-clock ID corruption and native/per-person output disagreement. They demonstrate software checks, not decoder performance or scientific reliability.
