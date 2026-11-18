# Figure 3c captured-input binding

This owner-side adapter maps per-sample real and shuffle predictions to the accepted Figure 3c profile scorer. It preserves all 11 mice, seven switch days, three cell classes, both cross-switch directions, ten folds and 100 shuffle repeats: 462 condition rows. It produces the existing 42 cohort profiles and 66 first/last-switch export rows.

The input is a **separately named JSON projection**, not the author's saved dill format. No pickle or dill is opened. An admitted owner capture must first establish the native containers, original observation identities and exact projection. This component fills the projection-to-scorer binding; safe native deserialization and source custody remain unresolved.

## Source mapping

The pinned [author notebook](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/notebooks/Fig3_Decoder.md) defines `pred`, `actual`, `pred_shuffle` and `actual_shuffle`. These have day, animal, cell-class and model keys. Shuffle objects then have integer repeat keys; the Figure 3c consumer indexes repeat and fold separately. The producer rolls neural inputs while retaining the same `y` and `ds` test indices. Both real and shuffled target vectors are required here and must agree; targets are never filled in from aggregate scores.

The JSON projection has exactly `schema`, `source_commit` and those four fields. Its schema is `reward-relative-fig3c-owner-projection-v1`. Day keys become their canonical decimal strings. Each field contains:

```text
day -> animal -> cell_class -> cross_switch_model
real:       ten ordered lists of sample values
shuffle:    {"0": ten lists, ..., "99": ten lists}
```

Only `train0_test1` and `train1_test0` belong to this Figure 3c projection. Each original source `[fold]` access must map to the same numbered list position. Lists are the declared JSON representation, not a claim about the uninspected helper's native container type. Source NaN becomes JSON null without dropping observations; finite radian values remain unchanged. Invalid angles reject. The unchanged profile scorer preserves its tagged NaN and infinity outputs.

The separate support object has exactly `schema`, `source_commit`, `preparation_sha256`, `fold_receipt_sha256` and `sample_ids`; its schema is `reward-relative-fig3c-owner-support-v1`. `sample_ids` maps day to animal to cross-switch model to ten ordered lists of actual observation identifiers. No ID is synthesized from an angle or vector position. Population agreement, fold order/size, duplicate observations, before/after separation and real/shuffle target agreement are checked by the pinned scorer. These checks cannot prove that supplied IDs identify authentic observations or that original fitting used them.

## Dependency and execution

The adapter requires `../fig3c-profiles-v1/fig3c_profiles.py`, exactly 12,881 bytes with SHA-256 `9fd76c464a0e33e3267b8229dca3a6ab256f61866a070d6189c8975885f22444`. An alternative location may be supplied with `--profile-module`; its bytes must still match. The trusted benchmark bytes are loaded after this check. Captured author code is never executed. Missing or changed dependencies fail explicitly; no ambient Python import substitutes for the accepted component.

From this directory, with Python 3.10+ and the standard library:

```sh
python3 -B fig3c_capture.py --capture /owner/projection.json --support /owner/support.json --capture-sha256 CAPTURE_SHA256 --support-sha256 SUPPORT_SHA256 --max-capture-bytes ADMITTED_BYTE_CAP --max-support-bytes ADMITTED_BYTE_CAP --output /owner/fig3c-result.json
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

The file interface checks each externally frozen byte digest and finite size limit before parsing the bytes read. Duplicate JSON keys, nonfinite constants and exponent overflow reject. Both full objects and results are materialized in memory; authentic scale has not been measured. Output creation is exclusive. Inputs, targets, predictions, receipts and outputs remain owner-private.

The 14 new tests cover mapping, complete condition membership, repeat/fold axes, target/support mismatches, dependency identity and bounded file parsing. One complete generated composition calls the unchanged scorer. Its tiny full-cohort fixture stays in memory; small malformed-file controls write under 256 bytes. The previous component's arithmetic tests are not replayed here.

## Scientific limits

The current author notebook identity is verified; the publication-equivalent saved result and native data are not. The notebook names a paper-result timestamp different from the selected loader timestamp. File digests bind bytes, not provider authenticity or input-use proof. This adapter cannot qualify original preprocessing, fitting, observation custody, stochastic equivalence or source missingness admission.

Figure 3b retains its distinct full 1,155-condition requirement and 462 published train-before rows. Figure 3c companions remain fidelity requirements, not rewards for larger z-scores. Reproduction and same-task improvement stay independent; neither a paper win nor scientific readiness is produced. The paper+data and paper+data+author-code arms remain separate, and neither receives private reference outputs through this owner interface.
