# Compare complete direct and viewer conditions

`compare.py` grades the complete matched direct-observation and typed-viewer
collections after validating both sets of operator session audits. It reuses the
existing collectors and the unchanged V3 scorer. Every worm and N/B/NB arm is
required. Any invalid collection fails before target access. If either condition
contains an explicit abstention, the whole comparison is unscored and targets are
not opened; there is no favorable subset or one-condition fallback.

Run only in the trusted operator environment, after both conditions are closed:

```sh
python3 -I -S -B compare.py \
  --panel panel.json --contexts contexts.json --responses responses.json \
  --audits audits.json --private-targets protected-targets.json \
  --output protected-paired-grade.json
```

The public input formats are the paired mappings described in
[audit collection](AUDIT_COLLECTION.md). Expected contexts must be frozen by the
operator independently of participant responses. The private target input has the
existing `neural047-targets-v1` schema. The output and target path belong in the
protected operator environment; neither is participant feedback. A fresh output
path is required.

The external target loader is called once, after both complete audited
collections pass. Each unchanged per-condition scorer calls a cached target
provider once: `private_target_loads` therefore reports one and
`scorer_cached_target_callbacks` reports two. Per-condition grades retain their
original callback fields, metrics, group records and descriptive intervals.

The paired result reports **typed viewer minus direct observation** for each
worm and arm and the equal-worm means. Positive balanced-accuracy differences
and negative log-loss differences favor the viewer descriptively. One single-class
worm makes the entire paired balanced-accuracy mean undefined; all worms and all
log losses remain. No new paired interval, superiority threshold or scientific
success rule is introduced. Existing marginal confidence intervals must not be
subtracted to form a paired confidence interval.

The viewer exposes exact numeric histories with an SVG illustration. It is not
an image-only condition. Saved audit consistency cannot establish process
isolation, actual model behavior, native clock/animal identity or the competence
of the original reference methods. This component does not close those gates,
change source inputs or score previously recorded scientific results.

`test_compare.py` uses generated three-worm histories and completed synthetic
sessions. Its controls cover joint admission, one external target load, exact
reuse of original scores, whole-pair abstention, missing or altered second-mode
records, undefined balanced accuracy, equal-animal aggregation, public-input
freezing across the target callback and operator file output. Run from this
directory with Python 3.11 or later:

```sh
python3 -I -S -B test_compare.py
```
