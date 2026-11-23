# REVE prospective matched reference

This package supplies an offline native reference construction, an executable
training-stage controller, default CUDA and explicit CPU fitting/inference
interfaces, and the literal
paper/data versus paper/data/official-code request interface. It does **not**
contain a trained classifier, a qualified GPU installation or a scientific
result. The default CUDA profile retains its existing installation refusal.
The opt-in CPU profile and operator CLI are described in [CPU_PROFILE.md](CPU_PROFILE.md);
resource admission remains the enclosing operator's responsibility.
The integrated CPU batch32/tail28 diagnostic passed numerical checks but
exceeded its selected 8 GiB child-RSS ceiling; overall runtime qualification
failed. This is not an executable scientific benchmark qualification.

`SOURCE.json` is preserved as the original construction-cutoff record: its
member hashes and environment observations describe that prior source state,
not the current CPU additions. See [CPU_PROFILE.md](CPU_PROFILE.md) and the
current source-validation results below for this revision's status.

The examined official release contains a pretrained encoder and query token,
not an authenticated four-class PhysioNet downstream checkpoint. The reference
here is therefore explicitly a **new matched refit using the released profile**.
It cannot authenticate historical Table 12: the paper describes an intermediate
128 Hz preprocessing step while the released code uses direct 200 Hz resampling;
the original checkpoint, seed/run roster and SD convention remain unresolved.
No task or outcome contract is changed.

The endpoint remains all 109 people and 654 imagery recordings, with 9,837
epochs: 6,300 training, 1,734 validation and 1,803 test. Inputs remain 64 channels
by 800 samples in float64 microvolts. Both test conditions use the previously
verified single-epoch opaque view and the same private inverse mapping. The
original public dataset exposure is unchanged.

## Exact source construction

`recipe.py` describes the tensor schema and controls stage selection without
tensor dependencies. `native.py` reuses the existing source-authenticating
author adapter for native classes and imports the pinned official StableAdamW
implementation. It never uses an online Hub call, remote-code loader, permissive
checkpoint load or randomly initialized fallback for missing pretrained weights.

The pinned HF artifact has 140 float32 tensors and 69,189,632 parameters. Its
encoder keys map identically to the native encoder; only `cls_query_token` is
removed and copied into the classifier. The native constructor adds RMSNorm and
the four-output linear head. The complete state has 143 tensors and 69,847,556
parameters. An encoder alone fails complete-classifier admission. Main-source
constructor defaults initialize the new head; the unused legacy `init_cls`
helper is deliberately not called because it can reinitialize encoder layers.

The frozen LP+FT recipe prospectively selects that branch of the released main
path; it is not a recovered historical PhysioNet launch. The released
`config_dt.yaml` defaults to seed 42, `n_runs: 10` and `training_mode: lp`.
`n_runs` supplies Optuna's trial count, not ten historical repeats. The cached
README's LP+FT example is for BCIC-IV2a, so it does not authenticate a PhysioNet
LP+FT command. The original Table 12 run recipe remains uncertain.

The selected branch consumes these settings:

| Operation | Frozen reference behavior |
| --- | --- |
| Scaling | Divide float64 microvolts by 100, then cast float32; no extra normalization or RevIN. |
| Tokenization | Four 200-sample patches at stride 180 per channel. The final 60 of the 800 delivered samples are unused by this encoder. |
| Head | Prepend query-attention context to 256 tokens, flatten 257×512, RMSNorm, dropout 0, Linear to four classes. |
| LP | Up to 20 epochs; only query and the entire head train (658,436 parameters). The encoder stays in training mode, retaining position jitter. |
| FT | Up to five epochs; all parameters train, starting from terminal LP weights, without reloading LP best. |
| Batches | 32, retaining the final partial batch: 197 training and 55 validation batches per full epoch. |
| Optimizer | New native StableAdamW each stage: LR 1e-4, weight decay .01, betas (.92,.999), epsilon 1e-9; one group of all trainable parameters. |
| Default precision | CUDA fp16 autocast; GradScaler explicitly disabled, preserving the source's top-level versus trainer dtype-key mismatch. Global gradient norm cap 2. |
| Warmup | LP five epochs/985 updates; exponential LambdaLR begins at zero LR. No FT warmup. |
| Plateau schedule | Fresh ReduceLROnPlateau each stage, mode max/factor .5/patience 5, using validation **accuracy** only when zero-based epoch > warmup epochs. FT receives only four calls, so cannot reduce LR within five epochs. |
| Selection | Strict improvement in validation **balanced accuracy**, starting from zero separately in each stage. Ties retain the earlier selected state. |
| Stop | Consecutive non-improvements strictly greater than patience: LP 5, FT 11. |
| Test | No test loader, labels, callbacks or feedback during the trusted reference fit. Complete opaque inference only after selected state is frozen. |

As in the source's shared `model_best.pth`, a positive FT improvement replaces an
LP selection even if its score is lower than LP best. If every FT score is zero,
the selected LP checkpoint survives and the receipt explicitly identifies LP as
the selected stage. If neither stage ever exceeds zero, the fit refuses to
produce a selected checkpoint. This is not silently presented as FT-selected.
The final training weights and selected inference weights are distinct.

Selected states own detached CPU tensor copies, so later updates cannot change
them. Only the final selected state is serialized; this replaces repeated source
disk saves with bounded retained snapshots while preserving the selected tensor
values. A complete native fit has not been executed to establish numerical parity.
The separate CPU profile changes precision and attention dispatch and has its
own recipe identity; a bounded compatibility check cannot establish full-fit
or historical-paper equivalence.

## Explicit prospective reproducibility choices

Python, legacy NumPy RNG, Torch and CUDA are seeded once before native encoder
and classifier construction. No transient HF model is instantiated. This does
not reproduce the original RNG consumption, and seeding NumPy is an explicit
addition to the released entrypoint. The fixed single-process loader uses zero
workers, unlike the source's eight persistent workers; actual sampler/RNG
identities are recorded instead of claiming identical historical shuffle order.
The same training generator persists through LP→FT. Validation has no separate
generator, preserving its consumption of the global Torch iterator seed stream.

Native training adds one NumPy-generated 64×3 position-noise draw per batch,
broadcast across examples, including LP. Each batch receives fresh repeated
geometry; the base geometry cannot accumulate jitter. Evaluation uses `eval()`
and inference mode. No model or test-distribution adaptation occurs in the
reference inference function. Initial head, per-epoch order and RNG identities,
observed library versions, attention dispatch and selected checkpoint digest are
recorded. Optional native FlashAttention availability is an observed source
branch, **not** a presently qualified image choice; deployment must freeze it.

No resume implementation is supplied. An interrupted scientific fit consumes
its attempt and accumulated budget; restarting is not a free continuation.

## Primary participant access

`primary_common` admits only exact pinned pretrained weights, the official
configuration, license, and the fixed nonexecutable architecture metadata in this
package. `primary_requests` uses the existing immutable-mount provider ABI with
the same inputs, image, asset hashes and resource operands in both arms. Only
the code arm receives the pinned official research archive.

The paper/data arm receives **no author encoder implementation**, no
`encoder-runtime.py`, no native reference source and no code-backed encoder
tool. It must implement its method from the allowed paper, data, configuration,
architecture description and weights. Thus architecture reconstruction is part
of this primary treatment. Configuration `auto_map` names must not trigger an
online or hidden source import. Participant images must also exclude author
implementation files and credentials; a filename allowlist alone does not
qualify an image.

The earlier `opaque-submission-v1` common trainable encoder interface is an
explicitly **assisted alternative**, not this primary pair or a prerequisite for
it. This package leaves that earlier artifact byte-exact.

The trusted reference's fit/predict input separation is implemented. The generic
participant request still mounts the complete opaque packet in `held_attempt`;
it does **not** itself enforce a participant development/freeze boundary or
prevent arbitrary code from adapting to test-signal distributions. A qualified
participant campaign must establish that boundary, code freeze, allowed access
and accounting before execution. No current route is activated here.

## End-to-end execution plan

1. Select and authenticate the already exported pair through
   `opaque-submission-v1.adapter.pair_info`, retaining the exact data identity,
   both material identities and private map. Preserve all 1,803 test events.
   Provision the exact weights/config/license/common architecture and, privately
   for the operator reference, the pinned source. This cutoff acquired nothing.
2. Select the numerical profile and freeze its exact runtime and physical
   resources. The default CUDA route still requires a real Linux/GPU provider
   and scientific image; the reused provider is CPU-only and rejects GPU
   requests. The explicit CPU profile is a distinct prospective choice, with
   no CUDA equivalence claim. Qualify custody, boundaries, input authentication,
   output capture and cleanup. Toolchain image `229045` is not a scientific image.
3. Adopt equal numerical scientific and agent budgets before either outcome;
   the null fields returned by `required_budget_fields()` identify the actual
   decisions still needed. Separately charge operator reference calibration.
   Do not substitute preparation limits or pretraining cost for these budgets.
4. In the qualified private reference fit phase, call
   `native.fit_reference(info=..., packet_root=..., source=..., encoder_path=...,
   seed=..., checkpoint_output=...)`. It uses only the full training/validation
   rows, runs `drive_fit`, restores the selected state and produces the bare
   complete native checkpoint plus a recipe-bound receipt. The default CUDA
   call refuses before imports or data/model access. Explicit CPU execution
   requires its qualified overlay and separately selected runtime/resource
   admission; exposing a callable API does not supply that admission.
5. Independently admit and freeze the fit receipt/checkpoint identity. Call
   `native.predict_selected(..., fit_receipt=..., expected_fit_identity=...)`
   in a separately qualified inference phase. It checks the exact recipe,
   stage/work trace, selected identity, runtime/attention profile and checkpoint
   before/after loading. It emits the unchanged condition-bound prediction
   schema for all 1,803 opaque events. The same operator reference may be applied
   to both conditions only under the explicit same-data reuse policy; this does
   not permit cross-condition sharing between agent episodes.
6. For each primary agent episode, provide only its allowed source view and
   adopted budget. Freeze reconstruction and improvement methods before test
   scores are released. Use `primary_requests` with the existing protected
   provider interfaces once the missing deployment/development boundary is
   qualified. The capture/observer seam validates the original result envelope;
   it does not become a training-budget enforcer by itself.
7. Keep private inverse mapping and targets exclusively with the operator.
   Restore each accepted opaque prediction panel using the unchanged material
   restorer, then apply the original complete-panel scorer. Report pooled-epoch
   balanced accuracy, kappa and weighted F1 for each frozen seed; aggregate and
   compare only under an adopted uncertainty/acceptance policy. Historical paper
   reproduction and improvement claims remain separate from beating this new
   matched reference.

The source can print the reference and paired work plans without data access:

```sh
python3 -I -B recipe.py
```

## Budget fields and known sizes

The root-provisional design allocates, per condition, five reconstruction fits,
ten development trials and five confirmation fits. Seeds 42–46 are prospective
repeat seeds; development uses 142. Each fit permits at most 157,500 training
window presentations and 25 complete validation panels. The maximum reference
LP+FT horizon is 25 epochs/4,925 optimizer-step attempts. The source's ten Optuna
trials are not historical repeats. One final release contains ten complete test
panels per condition; a separate five-seed operator reference remains separately
charged. These are construction defaults, not an admitted campaign.

Root must choose the physical profile and immutable image/provider; accelerator
allocation time and VRAM for CUDA, or the CPU profile for CPU; CPU time/threads;
wall time; RAM; cumulative writes and
input reads; complete-panel inference deadline; and agent model/scaffold, token,
request, tool-call and time limits. Scientific uncertainty and success criteria
also remain unadopted.

The pinned pretrained file is 276,773,456 bytes. A complete float32 classifier
contains 279,390,224 raw tensor bytes before serialization overhead. Model,
gradient and two optimizer-moment copies alone are roughly 1.12 GB during full
fine-tuning, excluding activation/workspace/framework costs; a retained selected
CPU snapshot adds about 279 MB. These are storage arithmetic, **not** measured
GPU/RAM requirements or recommended caps. Batch 32 itself contains 6,553,600
float32 signal bytes. Maximum 25-pass training plus validation represents
82,268,160,000 logical float64 signal bytes accessed, before caching behavior;
one test pass represents 738,508,800 bytes. Provider before/after full-packet
authentication, common assets, outputs and failed attempts add separate costs.

## Verification and remaining qualification

```sh
python3 -I -B tests/test_reference.py
```

Twenty-seven generated controls cover complete metadata, strict tensor schema,
stage transitions/selection/scheduling, full work horizons, validation accuracy
versus balanced accuracy, exact primary asset exclusions, independently selected
receipt identities, 1,803 opaque outputs and closed native entrypoints.
The earlier source revision also had twenty-five independent controls; those
are historical evidence, not a new run on this CPU revision. All were in memory: no generated
fixture files, scientific package imports, actual arrays, native model runs,
fits, scoring or performance measurements. Inert integer states validate the
controller; they do not establish native tensor/backend parity.

For the CPU-profile publication candidate, the 27 reference controls, 11
metadata controls and 18 profile/CLI controls passed on Python 3.11.6. The new
controls use generated JSON and inert native-call doubles, without scientific
imports or signal/checkpoint reads. See [CPU_PROFILE.md](CPU_PROFILE.md) for
commands and the separate numerical-pass/over-budget runtime outcome.

Remaining concrete execution requirements are a qualified selected-profile
environment (including a real GPU installation/image for CUDA), authenticated
pinned pretrained provision, adopted budgets and participant development
boundary, native source/runtime qualification, and a supervised
reference fit followed by independently admitted complete inference. The
original trained-head identity remains absent; a successful new refit would
not erase that historical limitation.

Sources: [pinned official repository](https://github.com/elouayas/reve_eeg/tree/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7),
[pinned pretrained release](https://huggingface.co/brain-bzh/reve-base/tree/33841986f6cc1438d9dcdbca5a2137d60f6007d9),
and [final paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/20a917f77773ac0fa8bea2bdd6606b66-Paper-Conference.pdf).
All source work here used the existing authenticated cache; no network refresh
was performed.
