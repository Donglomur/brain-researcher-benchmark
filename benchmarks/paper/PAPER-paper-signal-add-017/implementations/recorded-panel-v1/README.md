# Figure 2A and S7A complete-panel support

This operator component binds all three replay-model outputs and the unchanged
recorded control to one externally frozen assessment manifest. It complements
the existing source-training preparation and prospective spectral evaluator;
it does not execute a decoder or admit the benchmark. The two conditions retain separate source manifests and outputs.

The primary paper's Figure 2A uses 21 participants, both class conditions, three
earlier models replayed on Session 2 fine-tuned observations, and the recorded
Session 2 fine-tuned result. The latter is a distinct source role, not another
candidate replay. The figure displays participant distributions with medians.
Methods specify eight runs per class condition/stage and ten trials per class
per run. [Primary paper, Figure 2A and Methods](https://www.nature.com/articles/s41467-025-61064-x).

`validate_assessment` checks every declared run/trial role (336 runs, 8,400 trials),
source-class counts, unique source-file pins and ordered nonoverlapping trial
extents. It generates every complete 1,024-sample window at 128-sample spacing
within the supplied preparation extent. This follows the already inspected
training preparation's window geometry; **original assessment extent/window
eligibility is still unqualified**. The module cannot detect a false but
internally consistent operator manifest. Its SHA256 must come from a separate
freeze, not from an untrusted candidate's self-declared manifest.

`evaluate_panel` consumes hard window classes for `S1-B`, `S1-F`, and `S2-B`;
probability-to-class decisions and their ties require an upstream qualified
producer. Hard-vote ties raise an error for the whole panel. They are never
dropped or resolved using the older prospective smallest-class tie rule.
`S2-F` consumes exactly the frozen operator-recorded trial labels. Those labels'
source computation is not certified here. The output retains 168 individual
participant/model/class cells and eight participant-median summaries.

Every panel/comparison/wrapper includes a machine-readable `units` object.
`accuracy`, medians and paired accuracy differences are fractions, with no
conversion applied. Canonical `reproduction.v2.json` declares
`participant_trial_accuracy` in **percent correct trials**: multiply accuracy
fractions by100 before binding to that endpoint. Multiply a candidate-minus-
author fraction by100 to obtain **percentage points**, not relative percent
improvement. For example,159/160 becomes99.375 percent; a1/160difference becomes
0.625percentage points. The component exposes this conversion boundary without
changing or overwriting the canonical metric.

`compare_complete_panels` recomputes both complete panels against the same
manifest and preserves every one of the 126 replay-cell differences. It returns
no win, significance result, scalar replacement endpoint or SOTA claim. The
recorded control cannot change. Original model/checkpoint provenance, training
access, source membership, windows, original numeric references, competent
baseline execution and an independently accepted comparison rule remain gates.
An offline difference cannot establish new closed-loop human control.

The official supplement, page9/FigureS7A, independently names the analogous ME
comparison with21 participants and the same replay/recorded roles. Its caption
also specifies medians. This is a new source observation, not authenticated
participant-level numerical data. [Official supplement](https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-025-61064-x/MediaObjects/41467_2025_61064_MOESM1_ESM.pdf).

The caller must explicitly request `expected_condition="ME"` for S7A; MI is the
default. The source folder and condition must agree. `compare_mi_me` requires
separate frozen MI/ME assessments and returns both complete comparisons without
pooling or an overall win. Complete pairwise evidence therefore retains336
participant/model/class cells per submitted method and252 replay-cell contrasts.
FBCSP/run-trend human-learning companions remain outside this component. No canonical contracts,
task status, registry, central binder or readiness fields are changed.

Use `python3 -B -m unittest discover -s tests -v` from this directory for the
generated complete-support checks. They use no authentic EEG, trained model or
scientific run. Source-only integration must enroll this exact test command in
the existing component discovery manifest; it is not currently CI-enrolled. Tests for the first MI-only implementation are
preserved in private construction history; the final component adds explicit
source-qualified ME routing and a complete paired-condition wrapper.
