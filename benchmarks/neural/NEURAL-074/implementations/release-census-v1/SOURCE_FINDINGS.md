# NEURAL-074 source construction finding

The complete saved collection 6618 metadata snapshot contains 9,532 unique image
records. Joining the current 13-person × 51-endpoint declaration while preserving
source session and run identities produces:

| Declared cells | Saved FFX metadata matches |
| --- | --- |
| 376 | Exactly one candidate |
| 183 | Multiple candidates; session selection remains unresolved |
| 104 | No FFX match; each has threeAP and threePA run-level matches |

The 104 cells are the eight RSVP-language endpoints across all 13 people. Their
run-level source records exist; treating the explicit `run-XX` token as part
of the contrast name would incorrectly hide that support. This component
preserves run identity and does not combine runs.

The 183 ambiguous cells are 78 ArchiStandard, 65 ArchiSpatial and 40 ArchiSocial
person/endpoint combinations. The complete roster contains 742 FFX metadata
candidates; each has exactly oneAP and onePA metadata match within its own
session/run. All 742 carry the platform's `is_valid:false` flag. Neither that
flag nor metadata matching establishes numerical validity or acquisition
lineage. No image body was read for this census.

The canonical full-population task has not yet frozen its map construction.
This census investigates a prospective FFX choice without selecting it. For
that choice, missing FFX targets cannot be manufactured by averaging released
Z maps. The pinned official analysis code loads effect-size and effect-variance
maps, then combines effects using inverse-variance weights. Released Z scores
alone do not supply those two operands. This follows from the inspected
`_load_summary_stats`, `fixed_effects_analysis` and `fixed_effects` definitions
in [the official source at 2d9a685](https://github.com/individual-brain-charting/public_analysis_code/blob/2d9a6852bc7e3b164adef28b02b4d38d386c53ac/ibc_public/utils_pipeline.py).
That source was viewed through the web tool; its raw body was not downloaded
or authenticated in this construction step.

For an FFX target, the next step is to identify an authenticated equivalent
released map for each RSVP cell, or obtain original effect/variance operands
and qualify the exact aggregation recipe. Alternatively, a different uniform
run/direction construction requires an explicit scientific selection and its
own source, split and estimand qualification. Separately, select repeated
Archi sessions and freeze task-family/dependency policy before inspecting
target outcomes. Neither dropping 104 cells nor silently averaging session/run
Z maps is an implementation of the current complete-population contract.

The saved metadata inventory is pinned by SHA256
`81e873c3ac9f3fb4dcb389685bdae8c905ffba9794fb71a17f70d63f5c52e756`;
its 12 pages total 19,082,147 bytes. The current declaration source is
`agent-operator/source/n074/catalogue.py`, SHA256
`d68aae541c26aeaa08b2038ec21e7cf8e70c43b4504bffc5accdadc80d0e1409`.
The corrected operator-only census output is 73,256 bytes, SHA256
`edc482f0ae46cc055827aff59dace978506c009bb19b53bd4a2af9ef31871f8a`.
These are saved-snapshot findings, not a claim about all currently hosted IBC
releases, neural-map authentication, benchmark completion or model performance.
