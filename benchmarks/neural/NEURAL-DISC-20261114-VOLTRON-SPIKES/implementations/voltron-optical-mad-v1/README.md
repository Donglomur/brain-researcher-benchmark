# Optical MAD baseline on native Voltron frames

`detector.py` produces the missing `optical_mad` role for the existing
[native-frame event scorer](../voltron-native-frame-events-v1/CONTRACT.md).
It consumes the same complete prepared optical packet as the
[optical viewer](../voltron-optical-viewer-v1/README.md): 34 movies, 12 cells,
and six declared held-subject folds. It preserves every core, including empty
answers for extraction failures. The existing scorer and its endpoint are unchanged.

This is a prospective baseline implementation. The source task proposed a
training-only median/MAD detector with refractory control but did not supply a
producer. The precise peak/plateau convention below is an explicit construction
choice, not a recovered acquisition-paper method. The paper's smoothed waveform
error remains distinct from this prospective spike-event task. Source inventory
and synchronization limits remain in [data scope](../../docs/data-scope.md).

## Required calibration

`produce(public, optical, calibration)` takes the existing public geometry,
prepared optical packet, and a complete frozen calibration document. It neither
fits calibration nor opens electrical data or event references.

The calibration has exactly these fields:

```json
{
  "schema": "voltron-optical-mad-calibration/v1",
  "task_id": "NEURAL-DISC-20261114-VOLTRON-SPIKES",
  "public_sha256": "<digest of the complete public geometry>",
  "folds": {
    "<fold ID>": {
      "training_cells": ["<all cells outside this fold>"],
      "fit_sha256": "<digest of the independently retained training fit>",
      "amplitude_unit": "<prepared optical unit>",
      "indicator_polarity": "<literal integer +1 or -1>",
      "center": "<finite training median in original amplitude units>",
      "mad": "<strictly positive training median absolute deviation>",
      "threshold_mads": "<strictly positive frozen multiplier>",
      "refractory_seconds": "<nonnegative exact native-time value>"
    }
  }
}
```

Angle-bracket strings are explanatory placeholders, not executable values.
Supply all six folds. The center, MAD and threshold are literal finite numbers;
time accepts the scorer's integer, finite float or integer-ratio representation.
MAD is **unscaled**: no Gaussian consistency factor is silently applied.
The producer refuses zero MAD rather than estimating a replacement from queries.
There are no default thresholds, refractory periods, clocks or polarity guesses.

The training-cell roster must include exactly every cell outside the held fold.
All training and query movies must declare the same amplitude unit and polarity
as the calibration. Unit labels alone do not establish comparable amplitude
scales across cells. A qualified preparer and calibration procedure must resolve
that limitation before using this pooled-calibration baseline scientifically.
Fit hashes and roster checks identify claims; they cannot prove that fitting
avoided held observations or electrical answers. Model selection and any
normalization must be frozen using training folds before query prediction.

## Deterministic detection

For each valid original frame, the detector computes
`polarity * (sample - center) / MAD`. It selects local maxima at or above the
frozen threshold. Equal-valued plateaus produce one proposal at their earliest
original frame. At a connected valid run's endpoints, the available neighbour
is used; a singleton or constant supra-threshold run proposes its first frame.
Thus baseline drift can generate events. Query recentering, scale fitting and
drift correction are intentionally absent and must not be claimed.

Proposals are visited in native chronological order. A proposal is retained
when its stored timestamp is at least the declared refractory interval after
the previous retained proposal. Equality is accepted using exact arithmetic.
This is an earliest-eligible rule, not highest-amplitude selection inside a
refractory window. No nominal-rate clock, interpolation or subframe timing is used.

Positive validity gaps reset peak detection and refractory state, even if no
stored frame falls inside a gap. Missing or invalid samples cannot supply peaks
or affect calibration. Detection spans complete movies before assigning events
to their original cores, so a core boundary cannot split a plateau or create
an extra event. The existing whole-role event ceiling refuses an oversized
answer; it never truncates a recording.

The output contains the unchanged scorer role fields `program_sha256`,
`calibration_sha256` and `cores`, under `result["role"]`. It also retains input
identities, complete movie/frame counts and explicit unqualified status.
The program identity binds this source plus the pinned viewer/scorer dependencies;
it does not prove execution or protect the surrounding process. An operator
must supply the other three independently produced roles to the scorer.

## Execution and controls

With the complete independently prepared inputs and calibration available:

```sh
python3 -I -S -B detector.py --public public.json --optical optical.json \
  --calibration calibration.json --output optical-mad-output.json
```

The CLI rejects duplicate JSON keys/nonfinite JSON and refuses an existing
output file. It is an operator-side local program, not a resource sandbox or
provider transport. Complete authentic memory/time qualification remains open.

Run `python3 -I -S -B test_detector.py` for generated full-roster controls of
native refractory timing, positive-gap resets, core/plateau boundaries, polarity,
calibration refusal, drift, zero events, extraction failures, complete output
and the unchanged scorer's prediction interface. They establish software
behaviour, not biological accuracy or comparator competence.

No authentic optical trace, electrical label, calibration fit or model result
was produced for this addition. Optical preparation, physical synchronization,
independent electrical annotations, training-only calibration, matched-filter
and metadata baselines, protected execution and empirical comparison remain
unfinished. No task registration or readiness status is added.
