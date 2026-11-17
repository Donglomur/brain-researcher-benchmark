# Current-turn reasoning compatibility

This additive source component extends the frozen `viewer-provider-v1` bridge
from commit `98093654d4`. It accepts bounded opaque reasoning items before one
final viewer action, preserves the exact response privately, and deliberately
does not replay opaque reasoning across viewer actions. Internal reasoning is
permitted; it is not an external analysis tool.

The execution policy is named `current_turn_reasoning_v1` in private receipts.
It is separate from the earlier visible-message-only implementation, whose
source and evidence remain unchanged. Neither implementation is a qualified
live provider client or an AI performance result.

## What changes

Construct `Bridge` with all existing keyword arguments and an additional
required `reasoning_effort`. `Budget` and the supported task/condition names are
the same as in [the frozen bridge](../viewer-provider-v1/README.md). The effort
must be explicit; there is no selected model or default effort in this module.

Each request adds documented `reasoning.context="current_turn"` and the chosen
effort. The response must report those effective settings exactly. Reasoning
effort values listed in the API schema are not proof that a selected model
supports them. Unsupported settings fail without fallback or retry. All other
request policy, private sender injection and network restrictions are inherited.

The current [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
documents current-turn reasoning and default encrypted output in stateless
mode. The [Responses schema](https://developers.openai.com/api/reference/resources/responses/methods/create)
documents the request setting, effective response setting, output reasoning
items and usage. This component makes no live compatibility claim from those
documents and does not request a reasoning summary or add undocumented fields.

Allowed output is zero through eight opaque reasoning items followed by exactly
one completed assistant message containing the existing action wrapper. Each
reasoning item must have a unique bounded ID, empty summary, nonempty encrypted
content, no raw reasoning text, and either absent or completed status. The total
encrypted-content allowance is 262,144 UTF-8 bytes, inside the inherited maximum
524,288-byte response allowance. These are our local caps, not provider limits;
a smaller declared response budget still wins. No tool, compaction, commentary,
extra message, incomplete action or refusal is converted into a viewer action.

The original visible output message is retained for subsequent input, including
its optional `phase`: absent, null or `final_answer` is preserved exactly as
supplied. A commentary phase is refused instead of treated as a final action.
The [conversation-state guide](https://developers.openai.com/api/docs/guides/conversation-state)
describes manual output/phase preservation. A validation-only copy lets the
original bridge check the scalar/action contract; it does not replace the exact
private body or the original visible message used in subsequent requests.

## Private evidence and deliberate memory limits

Before action emission, the original receipt callback receives the exact entire
provider body, including every opaque item and nested usage value. Metadata
records bounded item identities/order, opaque lengths and hashes, a canonical
item hash, and full nested usage. Original response bytes are the authority for
exact encoding. Nothing decrypts, summarizes or publicly prints opaque content.

Failed/incomplete responses also retain status, error, incomplete details, usage,
effective reasoning and transformations privately when their JSON projection
can be serialized. Unprojectable metadata never replaces or repairs the raw
body: the receipt uses a fixed unavailable marker and still retains exact bytes.
Callback exception text remains suppressed. A receipt failure withholds action.

The known token counts must be integral and consistent. Reasoning tokens cannot
exceed output tokens; cached input cannot exceed total input. Full nested usage
is preserved without inventing an equality between reasoning, visible text and
other formatting tokens. The same complete-input and output budgets still apply.

Every exchange declares `prior_turn_opaque_replay:false`. The bounded list of
unreplayed IDs refers to the immediately preceding turn; a cumulative count and
the private receipt chain preserve the complete audit. No opaque reasoning item
is placed in later input. This is an intentional current-turn-only design, not
a hidden loss of state or a guarantee that provider internals were reset.

The original full-visible-history route and the separately prospective sleep
last32-turn policy are unchanged. The latter retains immutable instructions,
last31 completed visible turns and the current observation, evicting only whole
oldest turns. All original person state and first accepted responses persist;
all 5,450 epochs and the original collectors remain required. EEG remains a
fresh query session with first-final terminal behavior, including invalid scalar
responses. The canonical full-history sleep capacity refusal is unchanged.

The [prefix-preservation guide](https://developers.openai.com/api/docs/guides/preserved-reasoning)
warns that changing earlier input can affect reasoning availability. Rolling
eviction changes that prefix, so no all-turn opaque continuity is claimed.
`input_transformations`, when present, is retained privately. A nonempty value
is an anomaly here because no reasoning input was submitted; the exchange fails
before action emission. Absence of reported transformations does not prove a
provider state reset, image consumption or scientific validity.

## Verification and remaining holds

The implementation imports three pinned runtime files from the prior bridge;
its existing dependency closure still owns task state, framing, probability
validation and scientific contracts. Python 3.11 and existing NumPy suffice.
No SDK, HTTP client, credentials, signal arrays, renderer, model or installation
is included. Actual broker placement, model/effort/context/image support,
resource budgets and remote isolation require separate qualification.

Generated controls use the existing invented fixtures and fake senders. They do
not access authentic inputs or run a provider. The test command is:

```text
python -I -B -m unittest discover -s benchmarks/neural/NEURAL-007/implementations/viewer-provider-reasoning-v1 -p test_reasoning.py -v
```

Repository operators must use the admitted shared test pool. Source controls do
not adopt a canonical condition, authorize live execution or establish neural
understanding, task improvement or an effect of tool use.
