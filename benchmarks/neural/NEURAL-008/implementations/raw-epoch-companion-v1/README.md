# Raw epoch EEG/EOG companion

This is the separately named `neural008_raw_epoch_four_panel_v1` condition for NEURAL-008. It compares restricted waveform viewing and numerical programme access on the same 5,450 expert-labelled sleep epochs, nested in two already exposed people. It is source construction, not an observed model result or a newly qualified benchmark.

The historical whole-night engineered-feature programme and the existing NEURAL-007 epoch condition are unchanged. This companion removes cross-epoch temporal context and supplies no additional labelled training cases or task-model assets. Its results must not be pooled with the historical six-training-person, whole-night feature condition.

| Modality | Complete permitted epoch |
|---|---|
| `eeg_only` | EEG Fpz-Cz and EEG Pz-Oz: two channels × 3,000 samples, plus three clock values |
| `eeg_eog` | Those identical EEG samples and clock values, plus horizontal EOG: three channels × 3,000 samples |

Every epoch is 30 seconds at 100 Hz, with original voltage units and fixed class order W, N1, N2, N3, R. Development-001 contributes 2,780 epochs and development-002 contributes 2,670. The EEG-only numerical file physically omits EOG; the viewer cannot select it. The complete permitted epoch remains available while time/gain/channel actions stay within that epoch.

The four conditions are:

- `neural008_raw_epoch_viewer_eeg_only_v1`
- `neural008_raw_epoch_viewer_eeg_eog_v1`
- `neural008_raw_epoch_programme_eeg_only_v1`
- `neural008_raw_epoch_programme_eeg_eog_v1`

All four complete first-final panels must pass public custody checks and freeze before any private target read. Both raw programme modalities share one committed source/knowledge/image definition and use fresh per-epoch execution. Viewer contexts are fresh; an accepted final answer is irreversible. No other epoch, answer or label becomes an observation.

## Scientific interpretation

The inherited shared-declared-base-prior condition has no added assets. This is an explicit information condition, not a universal prohibition on trained task models. The existing trained-model/richer-information programme routes remain valid separately declared conditions. Unknown LLM pretraining is not asserted equal or used as a construction prerequisite.

A rendered waveform and exact numerical samples differ in precision. These are comparisons of declared access bundles, not a pure causal effect of tools. The renderer is reused unchanged and retains its NEURAL-007 sleep-trace heading; the actual packet/request/receipt explicitly identifies this N008 condition and modality.

The fixed N008 arithmetic is reused separately for viewer and programme panels: signed equal-person macro-F1 difference, EEG+EOG minus EEG, with both absolute arms and per-person values retained. Negative and zero differences are valid. Undefined REM recall is retained as null without dropping the person from the primary denominator. There is no positive-gap reward, new accuracy threshold, population interval or SOTA claim.

Expert labels are protected during execution, but these two development people were previously exposed. Local separation does not create a fresh holdout or turn 5,450 epochs into 5,450 independent subjects.

## Operator entries

All commands below run from the repository root after provisioning the exact separately authorised inputs/runtime. Configuration files and the source binding are operator-owned, byte/hash pinned JSON. Placeholders below are path/pin operands, not fabricated approvals. The new scripts do not install packages or manufacture provider capacity or sandbox evidence.

```sh
python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/raw_provider.py \
  --operation run --config /operator/viewer-run.json --bytes CONFIG_BYTES --sha256 CONFIG_SHA256

python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/raw_programme.py \
  --operation prepare --config /operator/programme-prepare.json --bytes CONFIG_BYTES --sha256 CONFIG_SHA256

python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/raw_programme.py \
  --operation run --config /operator/programme-run.json --bytes CONFIG_BYTES --sha256 CONFIG_SHA256

python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/raw_admission.py \
  --operation collect --config /operator/panel-collection.json --bytes CONFIG_BYTES --sha256 CONFIG_SHA256

python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/raw_compare.py \
  --operation coordinate --config /operator/four-panel-comparison.json --bytes CONFIG_BYTES --sha256 CONFIG_SHA256
```

Programme preparation freezes one code/knowledge/image definition for both modalities. Run one source-bound projected epoch through the existing concrete Provider; collection requires all 5,450 terminal records for the selected condition. Viewer execution uses the maintained HTTPS Sender and independent request/response audit; credentials are supplied by environment-variable name and are not an extra observation. An externally supplied trusted token-bound implementation is a capacity operand, not proof that a real provider accepts the request.

The coordinator authenticates all four collections and emits `FOUR_PANEL_FREEZE` plus a pinned worker request. Invoke the protected entry independently in the operator's target-only execution context:

```sh
python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/raw_compare.py \
  --operation worker --config /operator/emitted-worker-request.json --bytes REQUEST_BYTES --sha256 REQUEST_SHA256
```

The worker repeats all public checks before calling the unchanged N008 historical target loader once and applying both modality contrasts. Two separate Python entries do not themselves establish operating-system confinement. Exact image/exposure approval, producer closure, trusted custody and target-only grading remain external runtime responsibilities.

`SOURCE_BINDINGS.json` pins local production members and the exact maintained N007/N008 dependency closure. The dependency root is explicit for staged source controls; installed source may resolve the published repository layout. Genuine input/source/runtime pins must be checked against the actual installation, not an assumed repository revision.

## Reusable generated controls

```sh
python -I -B benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/tests_pair.py \
  --root /operator/fresh-generated-controls \
  --bindings /absolute/repository/benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1/SOURCE_BINDINGS.json \
  --bytes BINDING_BYTES --sha256 BINDING_SHA256 --dependency-root /absolute/repository
```

The combined public entry runs the new pair and viewer controls in one process. It uses complete four-panel probability rosters and small generated full-epoch signals, exercises real changed entry paths, and rejects EOG leakage, revised/incomplete panels and premature target access. Its generated HTTP boundary exercises the maintained sender/custody/audit code without network or a real provider. These controls do not attest native containment, genuine provider identity, token capacity, authentic assembly or neural interpretation.

Source bindings, exact selected command/resource limits and the observed result belong to the accompanying preparation evidence; no authentic or model execution is implied by this README.

## Remaining authentic operation

The next finite engineering operation should reuse the accepted original 5,450-epoch projection lineage, authenticate the unchanged EEG/clock join, and qualify the new two-channel projection/render path over the complete roster. Do not reduce the cohort, sample extent, action policy or denominator to satisfy a capacity limit. Reuse applicable accepted three-channel/source proofs instead of replaying unrelated historical campaigns.

Actual per-frame/request and cumulative campaign bounds, faithful image delivery, model/provider capacity, immutable image contents, programme isolation and independent reference competence require their own evidence. No AI win or improvement is required to complete infrastructure. Source/generated controls alone do not establish these authentic/runtime requirements.
