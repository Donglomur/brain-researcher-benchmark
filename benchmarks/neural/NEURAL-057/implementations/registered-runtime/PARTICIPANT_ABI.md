# Complete participant programme ABI

One source file for F and one for I are committed globally before exposure. Both accept exactly:

```
python -I -B program.py fit --train /input/train.json --model-output /output/model.bin
python -I -B program.py infer --query /input/query.json --model /model/model.bin --output /output/prediction.json
```

FIT receives only its current panel's primitive NPY feature and target matrices, people/concept IDs, fixed inner groups/roles, cell, category names/schema digest and source-preparation digest. The outer person's labeled data and every query array are absent. INFER receives only the current panel's 200-row feature matrix, opaque ordered query IDs, taxonomy identity, cell and the same-cell state SHA. It has a separate process, filesystem and tmpfs; only the original immutable FIT state crosses. Both worker containers have no network or service broker. No shared learned state, query-derived scaler or cross-cell file is permitted, including between cells with the same held person.

FIT must publish all three fixed files: model.bin (<=256 MiB), selected_method.json (<=8 MiB), operations.json (<=8 MiB). The model is opaque to the host but bound to its exact cell/source/view/phase; the reference uses safe primitive NPZ. selected_method has exactly schema, cell, category_schema_sha256, state_sha256, method_id, fit_view_sha256 and selection. selection is a bounded plain JSON object for audit, not authority. The producer uses schema `neural057-selected-method-v1`. All identities must equal actual original captured inputs/outputs.

FIT operations has exactly schema, phase=FIT, cell, services=[], query_access=false and native_cost_authority=false. INFER operations has schema, phase=INFER, cell, services=[], query_transform_fitting=false and native_cost_authority=false. The schema is `neural057-participant-declaration-v1`. These are declarations; original host observations and independent source qualification determine custody and semantics.

INFER must publish prediction.json (<=4 MiB) and operations.json (<=8 MiB). Prediction has exactly schema=`neural057-prediction-v1`, cell, fit_state_sha256, query_ids, category_schema_sha256 and probabilities. query_ids must match the complete original order; probabilities is exactly 200×53 finite independent Bernoulli values in [0,1]. No extra row, omitted unsupported-label concept, partial category set, ranking-only output or normalized-exclusive substitute is accepted.

All actual output prefixes, failures and ambiguous retirement/costs remain retained. A model or prediction from a failed phase cannot be admitted as a valid output. All 160 reference+participant cells and 320 original phases must close before the protected scorer runs; a failure produces an unavailable campaign, not a smaller denominator.
