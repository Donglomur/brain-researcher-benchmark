# Horrocks construction and synthetic engineering controls

This is source construction for **PAPER-EXP-20261113-002**, one already registered paper task. It adds no tasks, scientific results, ready benchmarks, or model evaluations. The Python core, 42-control harness, admission schema, reference policy and future MATLAB schema auditor are byte-identical to the accepted source versions pinned in `SOURCE_MANIFEST.json`.

The original core/harness passed 42 finite synthetic controls in a separately recorded local invocation. Public-projection verification is separate evidence; it must be established by an explicitly selected invocation and independent result review. Synthetic checks demonstrate behavior on invented inputs; they do not reproduce the paper, fit a reference classifier or validate authentic neural data.

## Files and entry points

- `horrocks_contract_v2.py`: owner-side archive-index, trial-protocol and diagnostic scoring functions; Python standard library only.
- `engineering_controls_v1.py`: imports the adjacent core and creates invented metadata, predictions and tiny ZIP fixtures. It never opens an official dataset or runs MATLAB, an LDA fitter, a model or a provider.
- `INPUT_SCHEMA_AND_GATES_V2.json`: exact accepted construction/admission contract.
- `REFERENCE_POLICY_V1.json`: matched pooled-state LDA extension policy.
- `inspect_horrocks_mat_schema.m`: unexecuted, future owner-only MATLAB structural auditor. It is not used by the Python harness.
- `METHODS.md`: derived method description and unresolved scientific gates.

The constructor's trusted owner supplies a complete, independently authenticated trial census to `make_protocol`; `validate_protocol` reconstructs that census and fixed partition. `public_query_index` emits only opaque identity/window metadata, **not neural tensors**. `score_improvement` compares complete frozen candidate/full-LDA/diagonal-LDA predictions. `compare_reproduction` compares complete arrays against a separately rebuilt owner reference. These functions are neither a candidate isolation boundary nor proof of scientific input/reference lineage.

## Prospective synthetic invocation

After reviewing and independently selecting an existing Python 3.11 runtime, from this directory use the same command on macOS or Linux:

```sh
python3 -I -B engineering_controls_v1.py --work-dir /tmp/horrocks-controls-UNIQUE
```

Replace the output operand with a fresh, nonexistent directory in an operator-owned output parent; do not place outputs in the source tree. The harness creates that directory itself. Do not use optimized Python (`-O`), which disables its assertions. No package installation or data download is needed. Python must support `os.O_NOFOLLOW` and ordinary POSIX symlinks.

The direct command is a payload command, **not an execution owner**. A separately selected local/Linux CI owner must enforce a whole-attempt 30-second deadline and an aggregate 8 MiB fixture/output/stream envelope, retain the exact command, runtime/source identities, complete stdout/stderr and result, and observe child closure on timeout/failure. It must disable network/provider access and admit only this fixed synthetic command. The harness checks elapsed time between controls and counts regular fixture/output bytes at the end; those cooperative checks do not impose a hard wall-time or storage limit. No container/image or CI workflow is selected by this source package. Any local projection check is separately selected and cannot establish Linux CI qualification.

A successful selected engineering invocation must have natural exit zero, exactly 42 unique PASS controls and zero FAIL controls, the expected core digest, `synthetic: true`, `scientific_results: false`, `new_ready_benchmarks: 0`, valid complete retained outputs and independently verified envelope/closure evidence. Preserve failures; do not silently retry. It still would not qualify a benchmark scientifically.

## Interpretation and boundaries

Reproduction preserves five animals, two behavioral states, all 191 sliding within-time windows and complete 20-by-20 cross-time matrices. It remains state-specific. The separate improvement endpoint uses a fixed chronological split, calibration-only fitting and equal animal weights. Both improvement LDA references use pooled states, uniform six-class priors, identical neural access and no privileged state dispatch. Other animals freeze the algorithm and tuning policy; held-animal calibration may fit that fixed policy.

The harness's trial labels, perfect/chance predictions, arrays, ZIP contents and identity substitutions are **invented synthetic fixtures**. The public source-defined animal/session roster and archive checksum are provenance metadata, not authentic trial labels or evidence that the archive was acquired.

No authentic MAT-to-neutral adapter, LDA fitter, protected five-fold outer runner, MATLAB/toolbox environment, complete original trial/unit support, competent full numerical reference or calibrated tolerance is qualified here. Public paper outcomes cannot be presented as an uncontaminated secret test. See the complete admission schema and methods before selecting any future scientific work.
