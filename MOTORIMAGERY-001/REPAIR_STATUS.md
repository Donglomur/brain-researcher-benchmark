# Local repair and validation boundary — 2026-10-01

Role: **easy/method control**, not a named paper finding, online BCI evaluation,
or demonstrated frontier-model difficulty. No push, merge or model run is implied.

## Source and public recipe

Thirty original PhysioNet eegmmidb 1.0.0 EDFs (77,040,000 bytes, ODC-By1.0)
are pinned to the published checksum registry and baked into the offline image.
Manifest SHA256: `939a5725a743d3162f24ac1d10c6088888991559c4a07207ee935a4061fc88c7`.
The public template specifies preprocessing, channel order, held-run folds,
CSP/LDA settings, labels and all 200 conditional null replicates.

Before any genuine fits, direct original annotation inspection established that
all 210 adjacent cue pairs contain one hand and one foot event. The revised null
preserves those original pairs, fixing singleton/orphan labels. This is an
explicit conditional exchangeability assumption, not evidence of the historical
randomization mechanism. No parameters or significance targets were tuned after
observing fitted outcomes.

## Executed native evidence

- Resource pilot: subject 1, five permutations, 18 folds; 45 retained epochs,
  rank 64, no fit warnings. Six independent fold refits agree.
- Production: all ten participants, 450 retained epochs, zero exclusions,
  6,030 training-only fold fits. All ranks are 64 and no fit warnings occurred.
- Mean subject accuracy 0.68444444; mean kappa 0.36826839. Five unadjusted
  permutation p-values and three Holm-adjusted p-values are below 0.05. The
  latter three are at the minimum Monte Carlo p=1/201 and therefore sensitive
  to finite-permutation resolution; they are not a calibrated ability threshold.
- Original EDF annotation parsing, manual epoch slicing, all label permutations,
  every saved-model score and every reported statistic were checked separately.
  Fresh independent covariance/GED-CSP and pooled-covariance LDA calculations
  cover 120 predeclared folds, not all 6,030. Maximum score difference:
  3.4586555841542577e-10. MNE signal reading/FIR and numerical libraries are shared.
- The bank builder independently reopens the original sources and reconstructs
  all saved-fold scores (maximum difference 0). It does not independently refit
  all models. Bank SHA256:
  `95d7dbda50fd6de156f7a284e2aad2e97766c4467e3cec8d82e77c7aeb69fcca`.

The verifier requires complete source/epoch/replicate/fold coverage, source-bound
decision scores and recomputed summaries. It has no performance range,
significance-count, nonconstant-output or prose-keyword gate. Genuine alternate
solver outputs and adversarial mutations are exercised by authoring regressions.
The dated sequential receipt records the final test count, clean commit,
in-container Harbor result, exact image/task digest and output identity; native
execution alone must not be described as clean-commit Harbor acceptance.

## Scientific limits

The visual cue and imagery condition covary; decoding cannot isolate imagery
physiology. The selected ten people are not a random population sample. Offline
nonsignificance does not show inability to use an online BCI. Published reference
answers are contamination-prone, so this repair supplies no new Sol calibration.
Source agreement, independent numerical checks and an oracle reward establish
bounded implementation consistency, not an independent scientific replication.
