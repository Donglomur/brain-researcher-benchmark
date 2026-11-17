# Complete visual-session grading for NEURAL-021

This component connects the existing direct-observation and typed-viewer response
paths to the original numerical scorer. Previously, the complete visual sessions
could emit valid predictions, but the deferred grading route accepted only the
different frozen-program producer graph. This adapter preserves that grader and
uses a separate, explicitly selected visual condition.

The task remains **272 calibration trials and 92 query trials**: 52 active and
40 perturbation queries from one macaque session. Each observation retains all
65 units and the 35 unique count bins represented by the original overlapping
histories. Every query requires all 30 signed x/y velocity pairs in m/s.

## Replay and scoring

`grade.py` authenticates the unchanged `paired-count-delivery-v1/delivery.py`, its
original public interface, and the original private numerical scorer using fixed
byte counts and SHA-256 values. The fixed original public packet and target
generation are recorded in `SOURCE_BINDINGS.json`; no alternative dataset pin is
accepted by the operator CLI.

Replay takes an explicit expected mode, a public `Packet`, the immutable complete
submission, and the visual receipt emitted by the original `Session.finish()`.
It validates all query identities and values before replaying the recorded
calibration views, query views, typed crops and answers through that same Session.
Every SVG is re-rendered and its hash compared. Answers are reconstructed from
the committed submission and compared with their recorded hashes. The adapter
requires the re-created final submission and receipt bytes to match exactly.

All 272 calibration trials remain available. The recorded exposure may contain a
subset, repeated views or no calibration views, as the original Session permits.
The result reports the number actually viewed. The adapter does not silently
require every calibration trial to have been displayed or alter the shared
2,048-view limit. Every query must still receive its complete first view and one
immutable complete answer. Only the typed-viewer condition permits later crops.

After the entire replay succeeds, `evaluate` calls the unchanged original scorer.
The scorer validates the complete public submission again before invoking the
protected target callback exactly once. Public validation or replay failures do
not open that callback. Target-generation failures remain failed grades with no
partial result.

The primary endpoint is the original equal-condition mean of variance-weighted
two-axis trajectory R². Negative R² is retained. Constant-target and
unrepresentable R² remain null with the original squared-loss diagnostics. This
adapter introduces no success threshold, target subset or new benchmark count.

## Interfaces

The pure operator API is useful for generated controls:

```python
sources = grade.load_sources()
# Production packet: sources["delivery"].load_public(public_root, numpy)
# Generated controls may use the original Packet.from_arrays constructor.
lineage = grade.replay(sources, packet, expected_mode,
                      submission_bytes, receipt_bytes)
result = grade.evaluate(sources, packet, expected_mode,
                        submission_bytes, receipt_bytes, load_private_targets)
```

The caller owns the trusted Packet and target callback. `Packet.from_arrays`
validates supplied values; it does not establish authentic provenance. A Python
object or filesystem given to a participant would allow computation and is not a
no-tools condition.

The CLI requires the original public directory and an independently selected
submission/receipt identity. Keep its inputs, output and protected targets in
operator-controlled locations outside the participant public directory and the
source implementation tree. An example invocation, not an execution performed
by this revision:

```text
python -I -B /SOURCE/observation-grade-v1/grade.py \
  --public-root /OPERATOR/original-public \
  --mode direct_observation \
  --submission /OPERATOR/submission.json \
  --submission-bytes EXACT_BYTES --submission-sha256 EXACT_SHA256 \
  --receipt /OPERATOR/visual-receipt.json \
  --receipt-bytes EXACT_BYTES --receipt-sha256 EXACT_SHA256 \
  --private-targets /PROTECTED/original-targets.json \
  --output /OPERATOR/new-result.json
```

Use `--mode typed_viewer` only for that separately selected condition. The original
public loader needs the operator's existing compatible NumPy environment. Replay,
numerical scoring and the generated tests use the standard library. Nothing is
downloaded or installed. The CLI reads the fixed three public files, verifies
exact artifact captures, replays the session, and reads the original target
generation only inside the late callback. The output must be new; failures do
not overwrite an earlier result or automatically retry. CLI errors report their
type without printing protected operand paths or target contents.

Input JSON captures are limited to 4 MiB each, visual history to the original
2,048 views plus 92 answers, and the result to 256 KiB. These are component bounds,
not host CPU/RAM limits or a sandbox. A future authentic invocation needs its own
approved resource budget, source/runtime pins, target custody and observed exit
evidence. This source change does not authorize such a run.

## Evidence and limits

Generated controls cover both complete modes, an independently calculated
non-perfect R², negative R², null constant-target R², malformed final trajectories,
missing/reordered events, repaired hash chains containing wrong views or answers,
changed observations, mode substitution and private-callback ordering. The
recorded author run passed 15 tests. It opened no authentic observations or
targets and performed no participant, model, container or native workload.

The receipt is reproducible local content lineage. An operator can generate a
valid receipt using software; replay cannot establish that a person or model
actually viewed it, identify its producer, or enforce the absence of tools.
Results therefore remain explicitly unqualified for runtime, science and
submission. The frozen-program producer's independent closure evidence is never
fabricated or inherited.

Counts are preserved exactly, but practical visual readability and realized
calibration exposure require study. Same query IDs do not establish equal usable
information across visual and numerical programs. The source onset alignment is
retrospective and uses future acceleration; historically exposed labels and one
animal/session limit interpretation. Actual competent neural and condition/time
comparators, participant performance, and no-tools enforcement remain separate
work. No native understanding, generalization, paper improvement or SOTA result
is claimed by these generated software controls.
