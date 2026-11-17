# Frozen component handoff — 2026-11-17

Task: `PAPER-paper-method-replacement-016`. All edits are confined to
`implementations/original-panel-comparison-v1/` in this task. Predecessor code,
original observations, task/contract definitions and shared source are unchanged.

Latest steering treats paper reproduction and same-task improvement as separate
first-class outcomes. This component supports descriptive comparison on the
original panel. It does not demote reproduction to an outcome that only serves
improvement, and it does not merge their scores. Paired paper+data versus
paper+data+author-code delivery remains outside this component.

## What changed

Added an executable original-panel candidate/reference comparator. It performs
the source max-after-ten-subject-mean selection, retains the 17-ROI profile and
compares a new architecture against every one of the 99 original main model
conditions. It retains all 335 source conditions and test/train noise ceilings;
the 92-model reduction comparisons and 51-model training branch remain distinct.
It rejects omitted/reordered support and altered shared-observation declarations,
and preserves undefined statistics without selecting a convenient finite subset.

This fills a specific gap: the existing shared `scoring.py` measures full-source
reproduction error, and `improvement.py` targets a new private biological panel
with a different aggregation rule. The new original-panel difference calculation
is absent from those implementations. It consumes existing native RSA output
rows; it does not duplicate feature extraction/RDM/Spearman producers or claim
to authenticate the missing historical results.

## Exact source and file identities

Author source revision: `5e802ae5e368a1a30940e6b175e47704a3061419` at
[hundred_models_brains](https://github.com/SergeantChris/hundred_models_brains/tree/5e802ae5e368a1a30940e6b175e47704a3061419).
The paper and author-driver links are in README.md. Only existing source and
metadata were inspected. No network acquisition was attempted.

The source protocol dependency is the exact repository-relative path documented
in README.md, SHA-256
`59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c`.
Other inspected provenance pins:

| Existing source | SHA-256 |
| --- | --- |
| Task `improvement.v1.json` | `f0cff295a5bab6fc460916b30fa351a48eafe1ebbbdc93d03b31c2c0304385f6` |
| Shared current `hundred_models_complete/endpoints.py` | `f6295ac9575697c2b0b4fd9a315e4404f272eba98c43b19209041b567196ce9f` |
| Shared current `hundred_models_complete/scope.py` | `cc01253b6641d35cbd22194233d9206eef1fb9407eb4c509bbdd867d8cd0155b` |

Frozen new executable/document files, relative to this directory:

| File | SHA-256 |
| --- | --- |
| `compare.py` | `587669014bf424ce8b528747c682c73eef373438b9c9e3a4f3e8796a9cb0add6` |
| `test_compare.py` | `551e26f92536ea91b9303003dc8d548b53a0de15bc5b1fd160d2a0459d9cab90` |
| `README.md` | `797c8507f5829a34a0f263446f66f6105de5099268ccf4dca43fd927c826f059` |

## Verification and costs

Tests ran exclusively through the verified shared two-slot pool, owner
`paper_02`, one thread, declared 1 GiB, timeout 180 seconds, Python `-I -B`.
First attempt `paper02-replacement016-originalpanel-check01` found both slots
busy and launched nothing. Second attempt
`paper02-replacement016-originalpanel-check02` passed all **9 generated software
tests**. Its 10 separately enumerated malformed-support controls also passed.

The executed child command was `python3 -I -B` on this directory's
`test_compare.py`, from the assigned group worktree. Retained external pool
evidence is identified without publishing local private paths:

| Pool artifact | SHA-256 |
| --- | --- |
| `paper02-replacement016-originalpanel-check01.json` | `2e6c253f8d634fcb773f2f91ccfe204eb6cf304e5ed3420eccd6287cad98bb54` |
| `paper02-replacement016-originalpanel-check02.json` | `3abb89210584575b1d08c529c3b9001fc33e08050f956f8f40983daf99ba8e49` |
| `paper02-replacement016-originalpanel-check02.log` | `787267158c89439dad44c7470d7e078528bcfbde7a34e3676fa96754eb4858f2` |

Successful attempt: 0.536352 user + 0.021020 system CPU seconds; 62,521,344-byte
child peak RSS; 6.646858 seconds wrapper wall time including 6.029562 seconds
waiting for a slot. Child test report: 0.516 seconds. Retained log: 1,058 bytes.
Pool limits are cooperative RAM/thread declarations, not OS hard limits.

Downloads: **0 bytes**. New dependencies: **none**. Authentic numerical data
preparation: **none**. Model/LLM trials: **none**. Generated RSA fixtures stay in
memory; the JSON-rejection test writes only tiny temporary strings and removes
them. No private targets or historical solver answers were opened.

## Qualification and remaining work

State: **software-tested original-panel comparison component; not empirically
qualified; task remains source-unresolved**. Independent peer review is pending.
There is no new reproduction result, scientific improvement or SOTA finding.

The existing source gap register remains relevant: authentic source derivatives
and stimulus joins; full loaded checkpoint/graph/evaluation-layer identities;
historical environment, pooling and reduction settings; exact original reference
vectors; auxiliary checkpoint and original companion branch outputs. Hash syntax
and matching declarations do not close those scientific gaps. Source metadata
still identifies 81 default layer lists as unbound; supplied run catalogs need
independent authentication. This tool has no authority to declare them recovered.

The original panel is public. Candidate freeze verification, allowed feedback,
meaningful minimum effect, selection-aware uncertainty and a primary across-ROI
decision remain unresolved. Descriptive participant differences follow cohort
layer selection and must not be treated as unbiased confirmatory paired tests.
The tool deliberately returns no paper-win or global-improvement decision.

Integration proposal only: register this directory as an additional descriptive
source endpoint component, preserving original source status and separate
reproduction/improvement qualification. Do not alter the global benchmark count.
