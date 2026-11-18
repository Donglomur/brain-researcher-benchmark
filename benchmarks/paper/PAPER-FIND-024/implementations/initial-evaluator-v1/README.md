# Segment-aligned TCI correlation component

For `PAPER-FIND-024`, this original implementation recomputes cross-context Pearson correlations and repeated-presentation noise ceilings from participant-keyed broadband-gamma electrode timecourses. It extracts segment responses at requested lags, matches central segments across distinct contexts, and emits complete declared cohort/condition results plus descriptive participant-balanced summaries.

## Run

Requires an existing Python 3.10+ environment and NumPy (checked with Python 3.11 and NumPy 2.4.6). No installation or data acquisition is performed.

```sh
python3 benchmarks/paper/PAPER-FIND-024/implementations/initial-evaluator-v1/evaluator.py /absolute/path/manifest.json /absolute/path/result.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-024/implementations/initial-evaluator-v1/tests -v
```

The offline CLI consumes SHA-256-pinned NPZ files containing real `D[time, stimulus, electrode, repetition]` arrays and timestamp vector `t`, plus a prospectively frozen JSON cohort/segment map. Each NPZ is captured once: its SHA-256, byte count and loaded arrays refer to that same byte snapshot. The CLI likewise reports the captured manifest it actually evaluated, even if input pathnames change during the run. These byte identities do not establish source authenticity or native scientific parity. It rejects incomplete matched designs, aliased physical contexts, complex/nonfinite active data, and segments outside actual sound intervals. Undefined or overflowing normalized correlations remain null with explicit status. Raw negative correlations and valid corrected values above one are retained.

## Scope

Interpolation, context/repetition weighting, completeness rules and participant balancing are explicit prospective policies. Unsplit recomputation and an optional globally grouped source-story holdout are supported; outputs are operator-only. No authentic data or native scientific computation was run.

Native TCI parity and dependency binding, the empirical MATLAB/epoch-map bridge, authentic cohort pins, gamma-window refitting, absolute-time versus structure-yoking inference, protected references, acceptance tolerance and rights remain held. This is a complete correlation construction component, **not** completion or scientific qualification of the canonical benchmark. Qualification remains unknown.

See [the full interface, source rationale and limitations](../../docs/initial-evaluator-v1.md) and [source provenance/requirements mapping](source-provenance.json). The generated controls establish engineering behavior only.
