# Original recovery-panel reducer

`reducer.py` reduces a paired reference/candidate scoring export for the complete
main recovery panel: all three original hybrid recordings (100 injected units
each), and all six original full-simulation cases (600 target single units and
600 background MUA identities each). It reports every case separately and pools
only the three hybrid score distributions, matching Fig. 3c. No equal-family
composite, new seed, narrowed unit subset, confidence interval, or paper-win
decision is introduced.

Paper reproduction and paper improvement are separate first-class outcomes.
The report includes per-unit reproduction discrepancies as well as per-case
recovery improvements, and leaves both scientific decisions unset until the
authentic reference and evaluation policy are qualified. The manifest records
one explicit observation condition, `paper+data` or `paper+data+author-code`;
operators run each condition on the same cases and retain separate reports.

The predecessor `registered-runtime/payload/legacy/k4bench/summaries.py` can sort
scores for caller-selected support. Its independent `I_bijective_full` aggregate
changes the original matching problem. This component adds full fixed-panel
identity admission and paired original-condition counts without changing those
historical implementations.

## Inputs and execution

Call `reduce_panel(manifest, exports)` from Python, or:

```sh
python3 reducer.py /operator/manifest.json /operator/exports.json /operator/report.json
```

The CLI creates a new output and refuses to overwrite one. Keep authentic
scoring exports and reports in operator-owned storage outside Git. The generated
`fixture()` in `test_reducer.py` is a complete, executable schema example; its
values are invented software controls, never a source data substitute.

The manifest has schema `kilosort4_original_recovery_inputs_v1` and contains:

- One explicit `observation_condition` so participant access conditions cannot
  be silently pooled or changed while retaining the same manifest hash.
- A `scoring_profile` with `name` (`R_source20` or `R_paper40`), explicit
  `score_encoding: binary64`, and SHA256 strings for the implementation, event
  and unit matching policy, and quality definition.
- Exactly the three source recording UUIDs and six named simulations hard-coded
  in `HYBRIDS` and `SIMULATIONS`. Each case has a source-input hash, a complete
  target-unit roster, and a separate background-unit roster. Hybrids have no
  completely labelled natural-background roster. Synthetic cases preserve all
  600 MUA construction identities and the original 2,700-second duration.

The export has schema `kilosort4_paired_scoring_exports_v1`, the canonical JSON
SHA256 of the manifest, and exactly `reference` and `candidate` arms. Each arm
binds its method artifact and the same scoring-profile hash, and supplies all
nine cases. Each case supplies the original source-input hash, every target's
score/FP/FN, and a complete detected-unit roster with upstream good labels and
matched-target incidence. Hashes join supplied objects; they do not prove that
the caller obtained the original data or ran a competent reference.

Target rows retain original binary64 score and error values. Counts use strict
`score > 0.8` on binary64 values; equality fails. Converting a binary64 score of
`0.8` to an exact rational and comparing it to `4/5` would incorrectly make that
equality recover, so this reducer does not do that. Integer recovery fractions
are emitted as exact rational pairs. It does not recompute rounded scores from
FP/FN in a different arithmetic order. For positive `R_source20` rows, it checks
the released `1 - FN - FP` order against the supplied score. Literal release
scores cannot be negative, and its initialized-zero rows must remain explicitly
marked; that branch cannot be introduced under `R_paper40`. Negative paper-score
rows remain in the distribution. The unpublished paper40 arithmetic/rounding
policy remains an upstream source-recovery requirement.
`R_source20` also rejects an empty detected-unit roster: the released matcher
fails when it accesses its first depth-sorted candidate. Filling the target
roster with initialized zeros must not turn that source failure into a valid
zero-recovery result.

## Companion controls and interpretation

Every simulation reports matched-target and good-matched-target counts for the
Fig. 4k companions, as well as detected, matched-detected, good-detected,
good-matched-detected and unmatched-good counts, with the complete input
incidence retained. Matching and quality classifications must come from the
upstream scorer selected in operator custody. This component does not resolve
the paper's matching/quality policy by guessing one. It checks that matched
targets are within the full target roster and that their union exactly covers
the recovered targets. Each recovered target selects one best detected unit,
as stated in the Methods. Multiple targets may select the same detected unit;
no injective reassignment is silently imposed. Detected units are counted once
each, whereas matched targets retain their original denominator. The primary
Fig. 4k caption explicitly equates its matched-unit bar to Fig. 4j's recovered
target count; these are not silently replaced by distinct detected counts.

For hybrids, unmatched-good is explicitly undefined because natural background
units are unlabelled. For full simulations it is a quality surrogate count,
not proof that every such unit is biologically nonexistent. Each arm retains
per-unit FP/FN and all detected classifications; paired results are integer
candidate-minus-reference differences for every case.
Separate reproduction diagnostics list every unit with a differing binary64
score, FP, FN or source-zero flag, and the maximum absolute score difference per
case. Exact numeric equality alone does not establish scientific reproduction,
and no reproduction tolerance is invented.

## Source and qualification

The source is Pachitariu et al., *Spike sorting with Kilosort4* (2024),
[paper](https://www.nature.com/articles/s41592-024-02232-7), Figs. 3c/e and 4e–k,
Methods “Performance metrics,” “Hybrid simulation” and “Drift simulation”.
The primary article XML was retrieved from the official Europe PMC API and
Fig. 3/4 captions and Methods sections 33, 35 and 37 were checked directly.
The existing source-reviewed `improvement.v1.json`, `ORIGINAL_SCOPE.json`,
`SOURCE_SEMANTICS.md`, and `NUMERICAL_REFERENCE_CONTRACT.md` establish the current
panel and unresolved policy boundaries; exact repository pins are in
`SOURCE_PINS.json`.

This is an executable downstream reporting component, with generated controls
only. No authentic input was prepared, no original score export was read, and no
author/candidate sorter was executed. The original dataset bytes, source
generator lineage/seeds, publication invocation and exact baseline vectors
remain unresolved. `R_source20` is not publication parity: the release checks
20 neighbors while the paper specifies 40, and event reuse/quality policy
remain unresolved. Naming `R_paper40` in an input cannot close those gaps.

This component covers the complete **main recovery panel**, not the whole
paper. Biophysical normal/twice-speed controls, all other original panels,
waveform/ISI lineage, ablations, runtimes, historical comparators, original
train/development exposure, and all 121 registered obligations remain required
for the broader task. The source paper evaluates fixed simulation cases, not a
new supervised train/test split. No benchmark readiness, paper improvement, or
current-SOTA claim follows from this component.
