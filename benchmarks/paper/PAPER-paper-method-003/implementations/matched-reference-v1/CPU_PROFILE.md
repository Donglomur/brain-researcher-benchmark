# Explicit CPU operator profile

`cpu-fp32-math` is a prospective execution profile for the released REVE
reference. It uses the authentic constructor, prepared direct-200-Hz data,
StableAdamW, warmup, complete-epoch loop, validation selection and complete
checkpoint structure. It disables autocast and substitutes parameter-free
PyTorch math attention for the author attention dispatch. Its recipe identity
is distinct from `cuda-fp16`; the default CUDA recipe and installation refusal
remain unchanged. CPU operation does not establish CUDA numerical equivalence.

The CPU profile requires an isolated overlay containing exactly einops 0.8.2,
transformers 4.56.2 and tokenizers 0.22.2. The selected shared versions are
Torch 2.12.1, NumPy 2.4.6, safetensors 0.8.0 and packaging 26.3. Runtime checks
verify package versions and whether modules originate in the selected overlay
or shared installation. The enclosing operator must also authenticate all
environment files, source, weights and selected signal bodies. Version strings
alone are not environment authentication.

The implementation selects one Torch numerical and interop thread. This is a
property of this frozen CPU profile, not a general resource limit or
a recommendation for future scientific workloads. Use a fresh process for
each invocation. The entrypoint installs nothing and supplies no OS sandbox,
resource lease or hard RAM quota. Its offline settings and Python audit hook
are cooperative restrictions, not verified isolation. Admission, process/time
bounds, output capture and cleanup belong to the enclosing operator.

## Commands and receipts

`run.py` provides `fit`, `predict` and `compatibility` (`compat` is an alias).
Each takes admitted `--info`, `--packet`, `--author-source` and a fresh
`--output` directory whose parent already exists. CPU selection requires
`--profile cpu-fp32-math --overlay /absolute/path/site-packages`.

- `fit` also requires `--encoder` and `--seed`. It writes `classifier.pt` and
  a recipe-bound `fit.json` only after the complete selection procedure.
- `predict` also requires `--checkpoint`, `--fit-receipt` and an independently
  selected `--fit-identity`. It validates the selected profile, complete trace,
  runtime, attention and checkpoint before producing all 1,803 opaque outputs.
- `compatibility` requires explicit CPU selection, `--encoder` and `--seed`.
  It writes `classifier.pt` and `compatibility.json`, never `fit.json`.

Fit and prediction default to CUDA and retain its closed installation gate.
An explicitly selected CPU interface is callable without that CUDA gate;
this is an operator interface, not scientific execution authorization. None of
the commands chooses a campaign budget or qualifies participant isolation.

Metadata-only checking uses the same explicit profile:

```sh
python3 -I -B metadata.py check-fit \
  --profile cpu-fp32-math \
  --info /absolute/path/info.json --info-sha256 INFO_SHA256 \
  --fit-receipt /absolute/path/fit.json --fit-identity FIT_IDENTITY
```

The metadata checker never opens the referenced checkpoint or verifies a
claimed execution. A compatibility receipt cannot satisfy full-fit admission.

## What the integration diagnostic establishes

The selected diagnostic uses one 32-example training batch and the original
28-example tail. Two LP steps and one FT step call the same `train_batch`
method as full epochs. They test finite gradients, the zero-LR first LP step,
a positive-LR head update, a real encoder FT update, safe weights-only reload,
complete tensor byte equality and bitwise evaluation-logit equality. The
diagnostic uses 60 distinct training examples and 92 presentations. Its
bounded sampler draw does not reproduce a complete epoch's sample order.
It performs no validation/test array access, held predictions or scoring.

The unchanged integrated diagnostic ran once on 23 November 2026. Numerical
checks passed in 46.216 seconds: both batch sizes, LP/FT gradients and changes,
complete checkpoint reload and bitwise evaluation logits. The maintained
maximum child RSS was 9,134,473,216 bytes (8.51 GiB), exceeding the fixed 8 GiB
ceiling by 544,538,624 bytes. The overall compatibility qualification therefore
failed as over budget, despite the numerical pass. Owned processes were closed;
there was no retry. Child RSS is not simultaneous process-tree peak memory,
and the declared ceiling was not an OS hard quota.

The earlier one-example control passed. The first batch32/tail28 attempt was
refused before worker/model registration by the 8 GiB available-memory guard.
Both the earlier refusal and the later over-budget result remain part of the
record. No source repair, reduced batch or replacement success is inferred
from the resource failure.

Full fitting still requires 6,300 training examples and 197 batches per epoch,
1,734 validation examples, the 20-epoch LP/5-epoch FT ceilings and the existing
early-stop, scheduler and selected-checkpoint rules. Full fitting and separate
complete-panel prediction have not been demonstrated by a compatibility pass.
The bound and findings of a diagnostic are not a full-fit resource estimate.

## Scientific and access limits

This remains a prospective refit using the released direct-200-Hz profile.
Its frozen PhysioNet LP+FT sequence is a prospective use of the released
branch, not a recovered Table 12 launch. The released configuration defaults
to seed 42, ten Optuna trials and LP; the README's LP+FT example is for
BCIC-IV2a. Those sources do not authenticate a historical PhysioNet LP+FT run.
Historical Table 12's intermediate 128-Hz preprocessing, original downstream
checkpoint, seed/run roster and SD convention remain unresolved. A successful
diagnostic or future matched refit does not resolve those differences, prove
paper reproduction or establish improvement. The endpoint, split, metrics and
held-out protection are unchanged.

The trusted reference implementation is not a participant common asset.
The primary paper+data arm receives the allowed weights, configuration,
nonexecutable architecture metadata and license without author executable
source; only paper+data+official-code receives the pinned official repository.
Publishing an operator CPU runner does not qualify images or filesystem
isolation for either participant condition. The earlier common executable
encoder interface remains a separately labeled assisted alternative.

## Source checks

`tests/test_reference.py`, `metadata_tests.py` and `cpu_profile_tests.py` exercise
stage rules, metadata, profile separation and command boundaries using generated
values and inert doubles. They do not import Torch/NumPy, run a model, load
original arrays or produce measured neuroscience results. Their generated
receipt fields are consistency controls, not evidence of scientific execution.

The 27 reference, 11 metadata and 18 profile/CLI controls passed on Python 3.11.6.
The two scratch paths below must be fresh directories with existing parents:

```sh
python3 -I -B tests/test_reference.py
python3 -I -B metadata_tests.py /absolute/path/new-metadata-scratch
python3 -I -B cpu_profile_tests.py /absolute/path/new-profile-scratch
```
