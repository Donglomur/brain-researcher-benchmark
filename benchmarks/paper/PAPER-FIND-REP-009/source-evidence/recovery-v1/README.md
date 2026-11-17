# Figure 3C/3G source recovery

The existing operator cache already contains both released workspaces, both
original analysis scripts, and a completed metadata census of Figure 3G. The
current improvement contract's statement that archive contents were not
inspected describes its own review, not the available project evidence. This
recovery connects that evidence to the current task without changing the
original paper endpoint or the historical Figure 3C reconstruction.

**The original-paper comparison remains source-unresolved.** The released 3G
workspace produces 18 experiment groups under the author's own grouping rule;
the paper describes 20 recording sessions. The difference does not identify
two missing sessions, and it cannot be repaired by padding, dropping groups,
renaming UUID tokens, or borrowing Figure 3H pseudopopulation results.

## Recovered support

| Property | Figure 3C | Figure 3G |
|---|---:|---:|
| Paper session count | 17 | 20 |
| Paper animal count | 4 | 4 |
| Released experiment groups | 17 | 18 |
| Released laser-specific groups | 34 | 36 |
| Long-table rows inspected in the historical metadata census | 16,295,010 | 43,869,150 |
| Distinct second UUID tokens | 4 | 5 |
| Preprocessed workspace bytes | 46,260,209 | 163,317,682 |

The paper counts come from the [Figure 3 legend](https://doi.org/10.1016/j.neuron.2026.04.045).
Released counts come from the complete, hash-pinned historical censuses identified
in [evidence.json](evidence.json). These are experiment/token counts, not newly
validated animal identities. No raw workspace was decoded during this recovery.

The 3G census retained all 18 groups and both laser conditions. Its 36 matrices
would contain 16,528 trial rows and 48,782,400 trial-feature slots, of which
4,913,250 have no long-table entry and receive zero under the source pivot.
There are no duplicate trial-feature keys. Individual conditions have 240–480
trial rows and 1,260–4,980 features. Three experiments have fewer than 960
combined trial rows; they remain in the released roster. These are metadata
dimensions, not prepared matrices or new numerical results.

## What the source establishes

The [versioned deposit](https://zenodo.org/records/19465617) contains the original
3G script at `Figure 3/3G/Figure 3G_analysis.R`. At the pinned script hash:

- Lines 20–33 derive experiment IDs from the first three `uuid` tokens and select
  each matching experiment. The name `exp_removed` does not mean leave-one-out.
- Lines 35–58 select OFF and ON independently, pivot `spk.st` by `uuid_tb`, and
  fill absent entries with zero. The script does not establish that absent
  entries represent biological silence.
- Lines 63–83 factor the context target, set seed 101, take a stratified 70%
  training partition with `caret::createDataPartition`, and retain only neural
  `uuid` columns as model inputs. This is within-experiment trial splitting.
- Lines 87–100 specify adaptive cross-validation and random-search `xgbTree`.
  The script does not explicitly set a tuning grid, `tuneLength`, package patch
  versions, or XGBoost threads. A declared reconstruction environment is not
  recovered paper execution provenance.
- Lines 120–121 call pROC on Randomised probability without explicit `levels`
  or `direction`. Source-auto orientation and a fixed Randomised-positive
  predictive AUC must remain separate. The legacy probability-MAE comparator
  is a reconstruction metric, not the paper's predictive endpoint.

The complete restored 3G inventory contains only `.Random.seed` and
`raw_pred_db`; it does not contain saved author models or an AUC table. The raw
table has ten columns: `clu`, `t_num`, `uuid`, `tone`, `time`, `spk.st`, `uuid_tb`,
`context`, `laser_block`, and `exp_id`. It has no explicit anatomical-region,
cell-type, animal-ID, or chronological-block column. The release README's
description of anatomical/cell metadata therefore does not by itself supply an
executable join for these workspaces. This does not establish that the intended
anatomical selection is wrong; it leaves its provenance unresolved.

## Limits that still prevent the paper comparison

The exact published 3C/3G AUC vectors and original run partitions are unavailable
in the inspected sources. The 20-session 3G point-to-experiment map is missing.
Its five second UUID tokens do not establish the four-animal mapping. Earlier
primary-document review also found that the 3C table lists seven mouse names
while its legend gives four. Neither panel supplies an independently reconciled
session-to-animal join.

The [top-level README](https://zenodo.org/api/records/19465617/files/ff_readme.md/content)
describes 3G subsampling, but the original 3G script has no separate
subsampling operation beyond the training partition. The paper's STAR Methods
describe 1.5-second windows and 20-ms bins; the scripts start from a preprocessed
workspace and do not construct those windows. Region selection, upstream
binning, any earlier subsampling, and excluded sessions cannot be inferred from
feature names. Figure 3H and S6N pseudosession controls are distinct endpoints;
their recipe does not resolve the 3G cohort.

The earlier recovery inspected both READMEs, the complete 3G metadata, the
original scripts, Figure 3's archive directory, the paper/supplement, and the
then-current deposit version metadata. The two RIKEN routes returned a
JavaScript shell. Those historical observations do not prove that no resolving
public resource exists today. No new network request or author contact was made
in this recovery.

The needed source is a published 20-row 3G session manifest mapping each point
to its released UUID and animal, or an explicit source correction explaining
the discrepancy; it must also identify the numeric paper outputs, allowed
anatomical features, preprocessing, and original split provenance. Source-only
construction can proceed if that evidence arrives. An 18-group released-source
reconstruction would be a narrower declared result, not the registered
20-session paper improvement.

## Integration proposal and qualification

Preserve `task.json`, `improvement.v1.json`, both historical implementations, and
all past numerical results. The integration owner can use this evidence to
replace the contract's acquisition-absence description with the exact
cohort/provenance mismatch. Keep its disposition `source_unresolved` and both
perturbation panels in scope.

No new preparer or decoder was added: the historical source worker already
implements both released panels, and repeating it cannot supply the missing
paper support. No new data preparation, model run, test suite, score, superiority
result, or benchmark qualification is claimed. This is a negative source finding
and recovery of existing evidence, not a completed benchmark.

Only source text and existing metadata were read; source scripts and metadata
receipts were hashed again. Workspace identities are those recorded by the
historical size/CRC/member-SHA intake. The full 327,348,037-byte archive MD5 was
not verified by that intake and is not claimed here. This recovery downloaded
zero bytes, installed nothing, and launched no R, Docker, or model process.
