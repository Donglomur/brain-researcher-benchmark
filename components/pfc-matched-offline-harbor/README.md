# PFC matched offline Harbor delivery

This component prepares two information conditions for the **same existing PFC
conditional reconstruction benchmark**. A receives the paper and data; B receives
the same files plus the selected official method and its license. The conditions
share instructions, tools, base image, resource limits, scorer and all 69 cases.
They are not two new benchmarks.

The source fixes a specific comparison problem in the older portable profile:
its agent had public networking and official code in both conditions. That profile
and the previously accepted local paired protocol remain unchanged. This new
profile uses Harbor's supported `network_mode = "no-network"` for both agent and
separate verifier, distinct fresh sessions, and no verifier feedback until both
complete trial artifacts have been frozen.

## What is implemented

`paired_materialize.py` checks the exact 15-file incumbent source manifest and the
four released public assets plus four notices. It constructs complete A/B tasks:
26 files in A and 28 in B, with complete 8/10-file agent contexts and identical
12-file verifier contexts. It never downloads, builds, launches or scores.
`TASK_PROJECTION.json` enumerates every generated task member and its input or
derivation; unchanged scientific source is reused rather than copied into this
component. The source dependency is `../pfc-science2-package`, whose manifest is
pinned in `upstream/SOURCE_MANIFEST.json`.

`pair_sessions.py prepare` binds three separately admitted complete images and
creates independent A/B trial configurations, host homes and temporary roots.
Both agent episodes have verification disabled and no custom imports, tools,
environment overrides, resume state or collection hooks. The generated execution
overlays omit assets because complete images already contain them. Those overlays
must never be built. A missing complete image is a preflight refusal.

`pair_sessions.py freeze` accepts only closed original trials from that pinned
plan. It checks selected configuration, absence of verifier results/timing,
successful exact submission coverage, and the conventional artifact directory.
It snapshots all consumed `config.json`, `result.json`, `agent/` and `artifacts/`
members, preserving empty directories and rejecting aliases or source mutations.
Only after both snapshots pass does it emit stock local-regrade configurations
pointing to the frozen copies. This is a custody check; stock Harbor still parses
its complete result model during regrade. Closure is supplied by the existing
owned caller and is not inferred from an exit code by this component.

## Scientific interpretation

The unchanged endpoint reconstructs exact conditional hypergeometric moments on a
supplied fixed map/category representation. There are 69 cases: the full fitting
set and 68 whole-animal deletions, with 12 families and 8 categories. The fitting
population contains 19,186 units from 99 recordings and 68 animals; the distinct
scored PFC population contains 10,243 units from 65 animals. Animal deletions are
fixed-map sensitivity analyses, not held-animal prediction.

Both arms receive the existing explicit conditional-method instructions. The
contrast is therefore **method-assisted reconstruction with versus without one
selected official implementation**. It does not measure neutral discovery from
the paper, access to an entire GitHub repository, raw neural-signal understanding,
SOM refitting, population confidence intervals, or a new frontier/SOTA result.

The ordinary trusted scorer grades `submission.jsonl`. Candidate program
execution is not an added requirement. Correct fixed artifacts support endpoint
correctness; they alone do not establish the participant's reasoning or general
ability on unseen inputs. Public release and pretraining exposure remain possible.
An oracle that produces equal results in both arms validates delivery, not the
benefit of official code to an LLM. Estimating that benefit requires independent
model sessions, prespecified repeated-seed/order handling and reported failures.

## Source checks and current status

Run from this component with Python 3.11 or later:

```sh
python3 -I -S -B test_paired_delivery.py
```

The 13 controls use invented complete source tasks and artifacts. They test the
two-file information difference, unchanged common source, offline configuration,
fresh sessions, forbidden source/asset changes, missing or failed artifacts,
preexisting feedback/resume state, hidden mounts or budget/access overrides,
aliases, and mutation during freezing. They do
not read authentic arrays, invoke the oracle, import Harbor, or contact Docker.

**Source checked; native paired delivery not qualified.** The authentic complete
contexts, three task images, network/code-absence isolation, artifact transport,
same-oracle 69-case match, and model runs have not been executed by this component.
The shared base has separate local runtime evidence; its config ID is not a
registry distribution promise. Author/expert metadata remains unchanged and must
be completed before an upstream submission. See `OPERATOR_RECIPE.md` for exact
stages and the limits that remain separate from these source checks.
