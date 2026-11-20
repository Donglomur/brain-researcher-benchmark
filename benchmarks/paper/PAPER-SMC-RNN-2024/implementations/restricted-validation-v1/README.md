# Restricted VALID reference and paired grading

This component prepares a development reference for the original MC_Maze 20 ms task and provides a bounded, explicitly VALID grading route. It is part of PAPER-SMC-RNN-2024. It does not create another benchmark registration or establish improvement readiness.

## Information available to the worker

VALID inference receives exactly 574 trials × 35 observed bins × 137 held-in neurons. The original author algorithm generates the ten forecast bins. Hidden neurons and future observations are physically absent; they are not represented as observed zero counts. The unchanged loader accepts this input directly with `cosmooth=True`.

The original VALID input file also contains held-out spikes. Only the trusted preparation process accesses that original file. `projection/project_validation.py` creates a fresh packet containing:

- `PACKET.json`, with sanitized source, geometry and order identities;
- `mc_maze/val/eval_input_20ms.h5`, containing only `eval_spikes_heldin`;
- `mc_maze/val/train_input_20ms.h5`, containing the four original TRAIN spike fields.

TRAIN remains 1,721 trials × 45 bins × 182 neurons for the original decoder-rate computation. These reconstruction-style rates are not restricted-input calibration predictions. The old TEST submission's 2,295 TRAIN+VALID rows are also not a replacement for restricted VALID inference; they used additional neurons and bins, and their ordering is a sorted union rather than a concatenation.

The projector preserves source dtype, spike-count units, trial order, neuron order and tensor values. It rejects unsupported fields, links, shapes, content identities and overlapping output paths. Its private receipt records original inputs; the worker packet contains no raw paths or target values. Whole-file byte authentication by the trusted operator is disclosed separately from numerical access to excluded datasets.

## Operator sequence

All descriptors contain exact path, byte count and SHA-256 fields. Inputs and output locations must satisfy the source contracts; the calls below are an interface sequence, not an authorized execution plan.

1. Call `project_validation.project(request_path, request_sha256)`. Its CLI is `project --request REQUEST.json --sha256 SHA256`; `inspect --packet PACKET.json --sha256 SHA256` independently checks a projected packet. Keep the request, output packet and private receipt in disjoint sibling locations.
2. Call `validation_reference.prepare_materials(packet_descriptor, author_source_root, fresh_capsule_root)`. It admits the exact projected inputs and 16 selected original software/noncausal-checkpoint leaves.
3. Call `validation_reference.prepare_reference(runtime_root, runtime_source_sha256, material_descriptor, fresh_method_root, author_reference_resource_profile=profile)`. There is no default CPU budget. The profile is frozen into the method and job.
4. Call `validation_reference.build_invocation(prepared_descriptor, genuine_owner_request_descriptor, retained_worker_descriptor, empty_output_root)`. It returns the exact worker/release commands and leaf mount list. A genuine owner must implement attachment, release, physical containment and complete closure. The old TEST owner does not automatically qualify this VALID phase.
5. After separately selected inference/candidate work, call `validation_grade.freeze_prediction(prediction_path, panel_descriptor, packet_descriptor, method_descriptor, fresh_freeze_root, role=...)` for both `reference` and `candidate`.
6. Invoke `runtime/bounded-grade/validation_grade_host.py --request HOST_REQUEST.json --sha256 SHA256` with the selected host Python and exact bound operands. The host runs one protected child for the pair, then requires complete report and ownership closure. The direct numerical grader CLI remains disabled; `score_pair` is a subordinate library primitive.

The worker mount builder permits only exact ordinary single-link files from the admitted packet, software, checkpoint and contract rosters. Projected inputs are read-only. Directory/ancestor mounts, extra mounts, links and source/output aliases are rejected. An isolated output directory is writable; `/work` and `/tmp` are explicit ephemeral paths whose storage belongs to the future owner's envelope. A source-generated mount list is not evidence that a real sandbox enforced it.

## Scientific contract and resource limits

The reference is the released noncausal checkpoint using the original 192-particle × 32-trajectory recipe, seed 20261118, and unchanged author inference algorithm. The 32 trajectories average inference; they are not independent training or biological replications.

A reference profile requires strict integer fields: 8 GiB memory, six threads, 10,800 seconds wall time, and an explicitly selected CPU budget from 1 to 64,800 seconds. The CPU ceiling is six threads times the wall envelope, not a completion estimate. The profile must equal the genuine owner request and is forwarded to worker and caller limits. No actual budget or runtime adequacy is established here. Existing participant-task budgets remain unchanged. Historical full noncausal TEST inference consumed about 29,393 CPU seconds, so a copied 7,200-second setting is not an adequate established reference quote.

Paired VALID grading uses the unchanged canonical evaluator and all four metrics: co-bps, fp-bps, PSTH R² and velocity R². Velocity R² includes its original TRAIN decoder fit. Both complete prediction freezes and private snapshots precede VALID-target access. Reference and candidate share one 2 GiB child, one numerical thread, 600/605 CPU-second soft/hard limits, and 720 seconds of work plus 60 seconds for cleanup. Host overhead and the bounded outer owner require separate genuine admission.

Reports compare only the same VALID cohort and expose signed candidate-minus-reference deltas. Historical TEST scores and printed Table 2 values are not VALID comparators.

## Evidence and remaining requirements

The generated source controls exercise production shapes, projection bodies, leaf mount builders, freeze ordering, bounded-host wiring and strict refusals. Synthetic authority pins, numerical evaluator spies and OS/process doubles are explicitly disclosed. The real original source-pin refusal is tested separately. These controls are not authentic data delivery, model inference, numerical performance, or physical runtime qualification.

The two byte-identical files under `controls/fixtures/` are source-only control dependencies, retained from the maintained aggregate worker and original NLB evaluator. The controls do not import the evaluator. They are not automatically selected as participant assets or production mounts.

The source-control environment is Python 3.11.6, NumPy 1.26.3 and h5py 3.11.0. A later deployed environment must be declared and qualified; the previously admitted scientific image uses the explicitly documented h5py 3.10.0 I/O variant. No identical-environment claim follows.

Required next evidence includes a genuine VALID inference owner, selected and admitted resource profile, physical realization of the restricted filesystem, complete reference predictions and their freeze, and an independently selected candidate. Original raw file sizes and actual projected compression sizes were not measured during source preparation. The bounded grader source is composed, but its VALID numerical execution remains unqualified.

The released checkpoint's actual historical training cohort remains unresolved. VALID is development data, not proven unseen by that checkpoint. Exact checkpoint-to-paper-Table-2 and original dataset-revision links remain unproved; the original TEST targets have been publicly released. A gain over this SMC reference alone would not establish SOTA.

A later gain-calibration experiment must predeclare its selection rule and freeze the test submission. A TRAIN-fitted gain needs appropriately restricted TRAIN predictions; an explicitly selected VALID-only gain grid is a different design. No calibration fit, original-data inference, protected numerical grading or new performance result is supplied by this source contribution.
