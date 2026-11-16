# CBraMod paired submitted-program source package

This package prepares and checks the source implementation for **PAPER-paper-method-024**. It compares one frozen submitted Python program under two information conditions: A receives paper and data; B receives the same paper and data plus the pinned official code. It preserves the existing complete artifact scorer and its scientific holds.

The public package contains the executor and 38 authored scientific source roles. A complete runtime additionally requires **all 65 exact official source files** from commit `b9e961003214326972c567eff390e75b0287e32a`. These files are external dependencies. This package is therefore portable but **not a complete runtime out of the box**. Nothing downloads source or data automatically.

`DERIVATION.json` maps every reused public file to its original repository-relative path, original and resulting byte/hash pins, and any change. The executor's eleven runtime Python files and its internal source manifest are byte-identical to the accepted construction. Only the generated test's operator-directory binding changes. The original central operator, full source freeze, and 38 authored roles are byte-identical. No primary article body, private dataset, target values, model weights, or official source body is included.

## Verify and prepare

Use Python 3.11 or a separately qualified compatible interpreter. Packaging-only checks use the standard library. The full generated executor checks also require an existing NumPy installation; this package does not install dependencies or qualify an environment. Source inspection and generated checks do not require Docker, GPUs, an API key, or authentic data.

The release consumer must obtain the verifier byte/hash and public manifest byte/hash pins from an independently reviewed release record. First authenticate `verify_source.py` against that external pin; execute its captured bytes or an equivalently protected verified file. The bootstrap executes before it can verify itself. Computing replacement pins from an untrusted package is not independent authentication. Replace the placeholders below with the reviewed manifest pins, not newly computed trust anchors.

```sh
python3.11 -I -B /ABS/PACKAGE/verify_source.py inspect \
  --manifest-bytes MANIFEST_BYTES --manifest-sha256 MANIFEST_SHA256

python3.11 -I -B /ABS/PACKAGE/verify_source.py check-package \
  --manifest-bytes MANIFEST_BYTES --manifest-sha256 MANIFEST_SHA256

python3.11 -I -B /ABS/PACKAGE/verify_source.py prepare \
  --manifest-bytes MANIFEST_BYTES --manifest-sha256 MANIFEST_SHA256 \
  --official-root /ABS/EXACT_OFFICIAL_CHECKOUT \
  --destination /ABS/FRESH_PREPARED_OPERATOR

python3.11 -I -B /ABS/PACKAGE/verify_source.py check \
  --manifest-bytes MANIFEST_BYTES --manifest-sha256 MANIFEST_SHA256 \
  --official-root /ABS/EXACT_OFFICIAL_CHECKOUT
```

The official root contains the pinned `LICENSE`, `models/`, `preprocessing/`, `utils/`, and other selected upstream files directly. It can be an operator-supplied checkout of the exact commit. The importer authenticates every selected file, including the final role, before creating a fresh destination. It rejects linked or altered members, missing roles, source/destination overlap, noncanonical paths, and an existing destination. Other checkout files are neither copied nor executed. No subset can satisfy the full103-role contract. The resulting operator contains exactly 105 files: the original central operator, source freeze, and all 103 scientific roles. The importer executes none of those source files. Source preparation does not qualify their native dependencies or scientific recipes.

`check-package` runs eight generated importer controls with tiny synthetic source text, without official code. `check` creates a fresh captured package, prepares the complete pinned operator using the supplied external source, then runs those eight checks plus all16 existing generated executor methods. It requires exactly24 successful methods and zero failures, errors, skips, expected failures, or unexpected successes. Tests import the relocated captured code; no original authoring directory is on their module path. The output reports which checks actually ran. A failed check remains a failure; a later successful check does not rewrite earlier evidence.

## License and upstream source boundary

The upstream top-level license is MIT, copyright2025 Jiquan Wang. Its exact license pin is recorded in `DERIVATION.json`. Two upstream file headers override any blanket MIT description: `preprocessing/ISRUC/edf_.py` declares BSD-3-Clause and MNE-Python contributors; `utils/signaltools.py` declares GPL with no version specified in that header and credits Soumick Chatterjee and OvGU:ESF:MEMoRIAL. Accordingly, **all65 official source bodies remain external**. The source importer preserves their exact files and notices in the operator's local prepared runtime. This package does not assert that upstream licensing is uniformly MIT, grant rights to external code, or resolve the GPL version. Operators must obtain and handle that dependency under its applicable terms before redistribution. The license inventory reports observed source headers, not a new license grant.

## Participant and operator interfaces

The participant submits one UTF8 `candidate.py`, at most1MiB, exposing:

```text
python -I -B /program/candidate.py --input /input --output /output
```

The program writes the complete `submission.json` and ordered NPY prediction artifacts described by `science/runtime/source/benchmark/public/contract.py`. Static condition code is at `/view`. Training and validation labels may be supplied in the qualified input packet; test labels have no participant packet slot. A real packet must supply the exact pinned paper text externally, the original full query, and all12 train/validation/test dataset entries with complete source-shaped observations and lineage. The generated metadata controls substitute bulky signal streaming and paper content explicitly; they do not qualify those inputs.

After source preparation, the accepted entrypoint is usable directly:

```sh
python3.11 -I -B /ABS/PACKAGE/executor/run.py inspect \
  --source-bytes 1562 \
  --source-sha256 7180659f275e05ad855bfc871111401537c08066ff2fc4e477f0150cf3b75ca5
```

`ROOT_COMMAND.json` and `REQUEST.template.json` describe an inactive future paired execution. A qualified operator replaces all paths and identity placeholders, selects scientifically justified budgets, supplies authentic input/target provenance, and separately qualifies the immutable runtime image and daemon. The closed request's `operator_root` must name the prepared105-file operator. The package does not invoke that future command. Its minimum memory/storage checks arise from preserving the complete8GB output contract; the template is not a claim that the machine has that capacity or that its time allowance suffices for research.

## Complete case population and interpretation

The primary panel is FACED, SEED-V, PhysioNet-MI, SHU-MI, ISRUC, CHB-MIT, BCIC2020-3, Mumtaz2016, SEED-VIG, MentalArithmetic, TUEV, and TUAB. Reproduction requires800 candidate files and800 reference slots per condition. Improvement requires60 candidate cases and420 comparator slots per condition, retaining all12 datasets and five seed slots. The unchanged panel also lists BCIC-IV-2a and14 additional paper-family obligations; this primary scorer does not qualify the full paper or those additional obligations.

The program is frozen before either public view is staged. Both conditions use that same program, immutable dependency image, budgets, and original query roster. A sees no B official-code material through its mounts, program, or dependency paths under the externally qualified image/program-custody contract. B alone receives the official-code view. Publishing operator/scorer source does not give the participant a mount of that source. A's independence depends on genuine pre-run program custody and a task-free common image; source code and a receipt cannot prove that empirically.

The executor owns resources before attempted creation, captures each complete output, and requires fresh proof that both conditions' owned containers and volumes are absent before launching the private grader. Partial second creation, wait, capture, cleanup, or final-absence failures never grade. Both complete output rosters, including B's final case and every probability array, must pass preflight before private binding access. The direct grading interface independently rejects private-owner aliases, but it proves neither program identity nor container closure. Trusted interpreter/source/request bootstrap reads precede arbitrary path declarations; later path admission does not retroactively blind them. Physical aliases and hostile concurrent filesystem mutations remain part of external host qualification.

New candidate-visible owned directories/files are explicitly0555/0444 even under umask077, while operator-owned paths remain private. Existing source, input, and target paths are not chmod'd. The streaming output contract remains8,000,000,000 bytes per condition, with64KiB chunks and complete manifest validation. Tiny generated artifacts exercise full case counts; no8GB allocation, throughput, capacity, or native container qualification is implied.

Metrics remain the existing dataset/task-specific metrics with matched reference support. Historical paper percentages are context, not a matched baseline or proof of improvement. Authentic source parity, complete lineage, trained model/checkpoint identity, seed identity, reference retraining, native execution, and scientific inference still require external evidence. This package adds neither a new benchmark ID nor a scientific result, readiness promotion, or SOTA claim.
