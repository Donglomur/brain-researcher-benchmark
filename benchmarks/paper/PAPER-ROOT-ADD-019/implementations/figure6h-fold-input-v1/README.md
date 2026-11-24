# Figure 6h original-fold participant inputs

The existing source projection returns operator-private predictors and label audits. This additive component prepares the neural inputs for one supplied original CV fold across all 18 sessions from eight rats. It exact-joins that projection to the existing OOF manifest and emits training rows with labels plus held-out rows without labels. It does not create folds, train models, select settings or change the Figure 6h metric.

`prepare_fold(source_panel, manifest, fold)` returns two separate objects:

- **Participant input:** ordered neural predictors, unit/time feature coordinates, training labels and held-out prediction rows. Source session/trial/unit/rat identifiers, raw reaction times, selection masks, audit labels, private source hashes and original-row mappings are absent. Session and role-local trial aliases are used; the private original trial names cannot become a label side channel.
- **Operator receipt:** source-to-alias mappings and the exact source-panel, projected-panel, manifest and participant-input hashes. Keep this object private. Its maps allow later prediction assembly to the unchanged scorer's original trial order; this component does not assemble or score predictions.

The input formats are unchanged: `source_panel` is `figure6h-source-projection-v1`'s full neutral input panel and `manifest` is `figure6h-oof-score-v1`'s operator manifest. Session/rat identities, retained trial order, unit counts and literal captured labels must agree. Both dependencies are pinned to their reviewed bytes; a dependency change needs review. Counts and digest equality establish consistency only, not authentic source provenance.

```sh
python3 -I -S -B prepare.py \
  --source-panel /operator/source-panel.json \
  --manifest /operator/original-oof-manifest.json --fold 2 \
  --participant-output /participant/fold-02.json \
  --operator-receipt /operator/fold-02-receipt.json
```

Both files must be fresh and their parent directories distinct. Directory separation is a preparation guard, not a permissions or execution boundary. The CLI writes the private receipt first; a later output-write failure may leave that private receipt for operator recovery.

## Scientific and execution limits

**Never give a persistent participant multiple fold inputs.** Each held-out label appears in other folds' training sets. Fresh isolated workers with no shared state, artifact access or cross-fold communication require a separately qualified execution controller. Pseudonyms do not prevent matching neural arrays across folds. The entire source panel, target manifest and receipt remain operator private. This exporter neither provisions isolation nor qualifies secure evaluation.

Paper+data and paper+data+author-code conditions can receive identical common neural inputs from this function; official code access is managed externally. No condition protocol, candidate freeze, matched budgets or protected execution is admitted here. Both conditions remain unresolved.

Authentic original observations, the 18-session/eight-rat roster, original fold realization, native source parity and source example traces remain missing. The source `thres`/`thresh` ambiguity, sequential label mutation, inclusive quartile ties, SD/SEM conflict and selected-CV bias remain unchanged. All 11 source ridge settings and every original session remain obligations of the existing scorer. A complete set of generated views is not a reproduction, an improvement or a qualified original-fold replay.

The pinned [author decoder](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/DMS_AChDA/vis/plot_fig6h.m) was reverified at 3,302 bytes, SHA-256 `c963c8b204fee99ca40668a4651e90e0beab44ec4e986b9bb184e8cf93ff3f42`. Lines 86–105 define the neural tensor/reshape and within-session ridge CV. This component only prepares captured fold inputs; it cannot recover the unpinned source partition from that code.

Run `python3 -I -S -B test_prepare.py` for seven generated controls: full-panel neural order, exact private/public fields, withheld-label invariance, identity/label mismatch refusal, original-fold and cohort requirements, complete tenfold partition, and separate CLI output serialization/preservation. They establish software behavior only. This new component requires explicit CI enrollment and source binding by the integrator; historical pins and contracts are unchanged.
