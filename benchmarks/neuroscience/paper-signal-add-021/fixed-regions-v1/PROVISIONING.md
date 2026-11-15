# Deployment and asset boundary

This is a source-only task specification and scoring release. No data download or candidate execution is triggered by these files.

A deployment needs the following separately provisioned roles:

| Role | Required content | Candidate access |
|---|---|---|
| Common inputs | Complete INPUT.json, values.f64, pair_counts.u8 and missingness.json for the accepted 4 x 7 x 53 x 200 x 15 projection | Both conditions, read-only |
| Common task | TASK.md, METHOD.json, SUBMISSION_SCHEMA.json and lawfully obtained paper | Both conditions, read-only |
| Official-code condition | Exact reviewed official source set, with applicable license/attribution | B only, read-only |
| Candidate program | Frozen participant-supplied program | Its own episode |
| Evaluation | Authenticated complete reference and scorer | Trusted operator only, after both outputs close |

The complete binary input contains 35,616,000 tensor bytes plus 222,600 count bytes; metadata is additional. A full source acquisition can be larger. No smaller region subset is a substitute for this declared input. The input manifest must retain the complete ordered coordinates, all four conditions and all fifteen source positions. Missingness remains explicit. The reference is generated under the declared method and independently verified; it is never a candidate input.

Before distributing research assets, resolve their particular licenses and acquisition terms. Public accessibility, an article's open-access label and a code repository's license do not automatically license a separate dataset or auxiliary repository. This package redistributes none of those assets. The source repositories and data availability statement are linked from the official [paper](https://www.nature.com/articles/s41467-025-57882-8).

## Research-source rights observed

The authored files in this release carry the repository's MIT notice. Separately reviewed primary sources report:

| Research asset | Observed terms | Included here |
|---|---|---|
| [Article](https://www.nature.com/articles/s41467-025-57882-8) | CC BY-NC-ND 4.0, with a third-party-material caveat | No |
| [Publication code at the reviewed commit](https://github.com/clayspacelab/Dake_Curtis_TMSV1_2025/tree/1e2c149e6e61f85b45acb8486c0fb31dc38d2dfa) | Apache-2.0 | No |
| [Auxiliary repository at the reviewed commit](https://github.com/mindemory/mgs_stimul/tree/57c4aeac3028c02f4b886eb4fd05435e126a80fe) | No license/notice file found in the complete reviewed tree; no README license grant | No |
| [OSF research data](https://osf.io/hf5a4/) | Public node; reviewed node metadata has no assigned license | No |

These observations do not establish a separate grant for redistributing the original dataset or the extracted tensor. Missing license evidence is not an explicit prohibition. Obtain or identify applicable permission before bundling those assets; publication of this authored source subset need not wait for that later data-release decision.

The accepted local operation used an existing private owner with exact source/asset pins and a fixed runtime. That host-specific owner and its private paths are not part of this public subset. A portable owner still needs explicit source and asset binding, network isolation, read-only delivery, equal budgets across conditions, source/version admission, a fresh complete output pair, termination/cleanup receipts, and protected scoring. Importing scorer.py alone does not supply those guarantees. Reuse an existing reviewed owner when available; do not claim a new host is admitted from the local validation statement.

The measured local route used a 60-second compatibility allowance and 120 seconds per arm, serially, with one CPU and two GiB per container, inside a 510-second whole-owner ceiling. These are the selected construction limits, not an evaluated LLM budget or a performance guarantee. The normative numerical conventions remain CPython 3.11.6; the observed CPython 3.12.16 compatibility applies to the exact selected image and method.

The next release step is a rights-resolved provisioning packet and a reviewed portable binding to the existing task. Publishing this specification/scorer or recording the selected-host validation does not complete that step.
