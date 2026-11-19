# Author-project label correspondence

This component binds two specific POYO author-project source artifacts: the
literal `monkey_dict` in `scripts/sess_types.py` and the browser label metadata
in `assets/sess_md.json`. Both Git objects occur in repository revision
`db43cacd2fc43022e4fb0f8f8470aa51d1aba4a4`, dated 26 October 2023, and in the
inspected current project snapshot. The repository date is not proof of first
public availability or original model execution.

`build_binding(source_body, metadata_body)` authenticates their exact extents,
SHA-256 values and Git blob identities. It parses the source as an AST; it never
imports or executes author code. The output retains every original ordinal,
literal source label, browser label and author type code.

The 158 rows have two observed relationships: 100 labels match literally; 58
browser labels omit a terminal source suffix (`_RT`: 49, `_Maze`: 4, `_CO`: 5).
Both spellings remain in the output. A different pairing, missing row, duplicate
label, changed type or unrecognized suffix is refused. Similar dates and alternate
filename layouts are never collapsed into a presumed physical session.

This is an observed correspondence, not a demonstrated production lineage.
The author script writes `sess_metadata.json`, while the browser reads
`sess_md.json`. The eight type codes are not an authenticated biological-subject
count and do not reconcile the paper's stated seven-primate training scope.
Physical session identity, original data bytes, train/test trials, adaptation
budgets, masks, checkpoints and historical scoring remain unbound.

The finetuning page names two demo MAT files, and its JavaScript displays
precomputed `r2` values rounded to two decimal places. Neither MAT payload was
acquired. The display does not compute or authenticate the original paper metric.
An accompanying JSON-to-MAT conversion script attempts half-precision conversion;
its presence does not establish that it generated those MAT files.

The single source-metadata campaign checks all 158 correspondences, preserves
distinct alias-like spellings, rejects ambiguous AST literals and reordered or
retyped labels, and refuses same-extent source mutations. It executes no neural
arrays, author model, original score calculation or benchmark episode.

Primary sources:

- [Literal author label source](https://github.com/poyo-brain/poyo-brain.github.io/blob/db43cacd2fc43022e4fb0f8f8470aa51d1aba4a4/scripts/sess_types.py)
- [Author browser label metadata](https://github.com/poyo-brain/poyo-brain.github.io/blob/db43cacd2fc43022e4fb0f8f8470aa51d1aba4a4/assets/sess_md.json)
- [Author demo source](https://github.com/poyo-brain/poyo-brain.github.io/blob/db43cacd2fc43022e4fb0f8f8470aa51d1aba4a4/js/finetune-vis.js)

The binding schema is `poyo-author-project-label-correspondence/v1`. It cannot be
passed off as an admitted original-training manifest or as the existing
`poyo_protected_grid_v2` evaluation design. No scientific readiness or benchmark
count changes follow from this source binding.

## Public and private files

The public bundle contains the binding module, this README and three portable
controls using generated source snippets and metadata. Keep the module and test
file in the same directory. Run the portable suite with standard-library Python:

```
python3 test_author_label_correspondence_portable.py
```

The three test methods were exercised in the previously completed five-method
private source campaign; the extracted portable harness has not been separately
executed. They check AST ambiguity, label order/type correspondence and duplicate
JSON keys. They do not authenticate all 158 original labels.

The complete binding requires the two exact source bodies identified above.
Those bodies, their emitted 158-row correspondence and the full five-method
campaign remain private evidence. No author source fixture is distributed here;
redistribution permission for the author script was not established in this
work. Supplying both original bodies to `build_binding` is an explicit caller
responsibility. The module performs no network retrieval or implicit local reads.
