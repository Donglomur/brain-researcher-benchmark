# ABR native delivery: operator guide

This package prepares and delivers the existing release-annotation agreement task: **936 direct-arm answers and 936 programme-arm answers** over the same 936 cases from 104 animals. Each answer predicts the numeric code stored in the released annotation. This is not a calibrated hearing-threshold measurement or a clinical assessment.

The portable source is not the input dataset. Delivery requires an admitted observation store and its external completion pin. Preparing that store or scoring sealed answers additionally requires the exact private native bundle. This source package contains no observations, private annotations, participant answers, credentials, or author workspace paths.

## Evidence and limits

Authentic preparation produced a complete store with 16,226 traces and 31,689,378 samples: 1,953 samples per trace. Observed cases have 17 traces (831 cases), 19 traces (one case), or 20 traces (104 cases). The numeric store was 338,405,724 bytes. One maximum-trace case was materialized as seven plot pages and independently checked. This establishes complete numeric preparation and one capacity view; it does not establish visual validation of all 936 cases.

Manual persistence evidence comprises six passing methods in the initial campaign and four passing methods in the corrected campaign. The initial failed campaign is retained; this must not be described as a fresh ten-pass campaign. Corrected controls checked bounded underlying ingress, short-read failure, complete 1,872-final reconstruction without reopening annotations, the complete invalid-response panel, and seven dependency/input mutations. These used generated fixtures and a generated private-loader double.

No participant/model study or target scoring was performed during that preparation. The packaged manual source retains that capture behavior and updates its helper pins for the response-recursion correction. The earlier controls and authentic preparation remain historical evidence, not reruns of this successor.

## Files and prerequisites

| File | Role |
| --- | --- |
| manual_session.py | Durable manual/programme session |
| prepare_delivery.py | Complete numeric store and case-view preparation |
| abr_release.py | Accepted Pair, roster, annotation validation and arithmetic |
| raster.py | Accepted deterministic trace-page renderer |
| COMMON_DOCUMENTATION.txt | Identical candidate instructions for both arms |

Keep these package files together. Loaders authenticate exact dependency bytes. The manual source is 35,856 bytes, SHA256 a656f6086a4dcc17e899fccad9bba2683b144335e2e4dce02cf3996bcba0cc50. Do not edit dependencies or common instructions to make a mismatched bundle load.

Use a selected Python environment on a POSIX host with fcntl, ordinary file permissions and directory fsync. Accepted controls used Python 3.11; packaging does not establish compatibility with Windows or arbitrary Python versions. The CLI supplies no process/RAM limiter or candidate sandbox. The operator must enforce selected time, memory, access and cumulative publication limits with an outer runner.

Required inputs:

- For preparation or later scoring: the **exact admitted native bundle**, kept operator-only. Its COMPLETE.json is 22,643 bytes, SHA256 507b7e77a2a4d09f5056e6191efe34db7092ca4eab70a4880e425ae7eade1972. Its pinned compressed annotation projection is 39,816 bytes, SHA256 2fe03bf9e72e92116c08a64b91b4dc882fbd05913dd3f9eccc35b80557f72ec0.
- The matching native bundle depends on the original 32-byte HMAC opaque-ID key and every prepared output hash. Native COMPLETE metadata is independent of host path and timestamp, but the same source ZIPs with an arbitrary fresh key do not recreate the admitted bundle. No key or private projection is distributed here.
- A complete public numeric store and its externally retained COMPLETE.json pin, expressed as BYTES:SHA256. The store stays operator-only because it contains all target cases.
- A nonempty final programme artifact of at most 1 MiB, its command description, and fixed external dependencies. The CLI records programme bytes and the command description; execution remains external.
- A fresh session path with an existing parent directory, disjoint from the store, and a stable operator identifier.

Delivery from init through seal can use the admitted observation store without private native files. Its required files are COMPLETE.json, operator/INDEX.json, operator/ROSTER.json, public/COMMON_DOCUMENTATION.txt and every public/cases/<case_id>.json packet. The unchanged completion manifest can retain a scratch-descriptor hash even when that private artifact is omitted: the delivery loaders do not open it. Preserve the manifest bytes and external pin; do not edit it to remove references. This is a source-supported route, not a claim that a public observation archive is already available. Keep the whole store inaccessible to each candidate, exposing only the current case.

Paths are explicit CLI inputs, with no fallback to the author's workspace. Runtime SESSION.json intentionally records operator-supplied absolute paths; do not publish that private runtime metadata as package provenance. Choose stable locations before initialization, avoid symlinked path components, and do not relocate a live session by editing its journal.

## Prepare or admit the store

Use a preexisting store only with its externally trusted completion pin and the exact source/bundle identities. A locally calculated hash proves byte identity, not provenance by itself.

For separately selected preparation, set the ABR variables to operator-selected paths and limits. This command reads the exact supplied native bundle and creates a fresh store; these examples do not select a study:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/prepare_delivery.py" \
  --implementation "$ABR_PACKAGE/abr_release.py" \
  --raster "$ABR_PACKAGE/raster.py" \
  --documents "$ABR_PACKAGE/COMMON_DOCUMENTATION.txt" \
  --deadline-seconds "$ABR_PREPARE_SECONDS" \
  prepare --native-root "$ABR_NATIVE_BUNDLE" --output "$ABR_STORE"
~~~

Retain the successful store's COMPLETE.json size and SHA256 externally as ABR_STORE_PIN. Do not accept partial output or an arbitrary existing COMPLETE.json merely because it can be hashed. The source binds all 936 variable-length packets, roster/index, native completion identity and common instructions. A new acquisition or native preprocessing recipe is outside this package; there is no assertion that arbitrary native reconstruction matches the fixed bundle pin.

The preparer's standalone view command is for separately selected preparation checks; it does not replace the session's recorded exposure sequence. The manifest's capacity_view_case_id selects the maximum by trace count and packet size, retaining observed-order ties. maximum_packet_case_id separately identifies the largest numeric packet.

## Freeze before case exposure

Set ABR_PACKAGE to the package directory; ABR_STORE and ABR_STORE_PIN to the admitted store; ABR_ATTEMPT to a fresh, stable session path; and ABR_PROGRAMME to the final programme artifact. Run each invocation under your selected outer limits.

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" init \
  --session "$ABR_ATTEMPT" --store "$ABR_STORE" --store-pin "$ABR_STORE_PIN" \
  --representation "$ABR_PACKAGE/prepare_delivery.py" \
  --release "$ABR_PACKAGE/abr_release.py" --raster "$ABR_PACKAGE/raster.py" \
  --programme "$ABR_PROGRAMME" --operator-id "$ABR_OPERATOR_ID" \
  --programme-command "$ABR_PROGRAMME_COMMAND" --attest-pre-exposure
~~~

Retain the printed session_pin externally as ABR_SESSION_PIN. It binds the CLI, programme, documents, dependencies, roster and store. Initialization exposes no case and opens no private annotation. Freeze the programme and its external environment before target exposure; do not change them between cases in response to observations or outcomes.

Before the first exposure, also declare the intended comparison in the external study record. For each arm, freeze the relevant system/model version, configuration and prompt, and either a fixed participant identity or an explicit case-to-participant assignment. A human study may use multiple respondents under that predeclared assignment; this route does not require one person to answer all 936 cases. Keep the condition and assignment record outside candidate-visible files, and retain its reference with the actual run records identified by `external_run_reference`. The common access, fresh-state and resource rules must also be fixed before exposure.

Report outcomes for the declared conditions and respondent assignment. The per-case `participant_id` field records an operator declaration; it does not enforce a fixed assignment or authenticate a model, prompt, human identity or execution environment. Identical observations alone do not establish a same-system tool-use effect, and pooled responses do not establish population exchangeability. These are study-design and external-custody obligations, not a new session field, scoring gate or claim of clinical accuracy.

## Deliver one case to both arms

The journal uses observed-order lockstep: complete both arms for one case, retire its view, and then advance. Every operation uses the same ABR_ATTEMPT and ABR_SESSION_PIN.

1. Expose the direct arm:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" expose \
  --session "$ABR_ATTEMPT" --session-pin "$ABR_SESSION_PIN" \
  --arm direct --deadline-seconds "$ABR_VIEW_SECONDS"
~~~

2. Transfer only the returned case-view directory to a fresh direct-arm context. It contains numeric.json, exact common instructions, all enumerated three-trace PNG pages, VIEW.json and a static HTML index. The direct arm inspects supplied numeric/typed visual information **without executing code**. Do not expose the full store, session journal, prior cases, other-arm answers, native bundle, private annotations, network/source lookup or scoring feedback.

3. Record the actual first response in a preexisting regular, single-link file outside the candidate view. Capture it with an actual custody attestation:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" capture \
  --session "$ABR_ATTEMPT" --session-pin "$ABR_SESSION_PIN" \
  --arm direct --response "$ABR_FIRST_RESPONSE" --attestation "$ABR_ATTESTATION"
~~~

4. Repeat expose/capture with --arm programme. The same complete view is reauthenticated and reused byte-for-byte. Run only the already frozen programme in a fresh isolated environment containing that case and common instructions. The CLI does not execute the programme, select a provider, or prove that the external environment followed its rules.

5. After both first responses, retire the completed view:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" retire-view \
  --session "$ABR_ATTEMPT" --session-pin "$ABR_SESSION_PIN"
~~~

Repeat for all 936 cases. Never assume a uniform trace count or deliver only the first page. Successful export proves materialization, not participant inspection.

## Response and attestation format

Follow COMMON_DOCUMENTATION.txt exactly. The first response is at most 4,096 UTF-8 bytes and has exactly case_id and predicted_annotation_code, with a finite JSON number in the supported numeric representation. No target-derived label alphabet, automatic rounding, censoring interval, replacement abstention or explanatory field is introduced. Numeric code 100 remains numeric; its exact/censored interpretation remains unresolved.

Both arms receive all native samples, repeated levels and zero-valued traces. Axes are sample indices and raw amplitudes. Do not reinterpret them as milliseconds, volts, microvolts, calibrated sound pressure or acoustic arrival time. Plot pixels may combine neighboring samples and display labels round values; numeric.json remains the authority for exact values.

The attestation contains exactly these fields, populated with actual events. fixed_programme_used is false for direct and true for programme:

~~~json
{
  "operator_id": "the frozen operator identifier",
  "participant_id": "the actual participant or system identifier",
  "transport_description": "the actual delivery and capture method",
  "external_run_reference": "the actual operator run or transfer record",
  "fresh_case_context": true,
  "only_current_case_and_common_docs": true,
  "no_targets_or_feedback": true,
  "arm_rules_observed": true,
  "fixed_programme_used": false
}
~~~

These are operator statements, not independent provider or sandbox evidence. Do not attest to conditions that were not satisfied.

## First-final and restart rules

Enforce an external timeout even for regular-file capture: stalled filesystem I/O has no hard wall-clock guarantee. Stdin and FIFO capture are unsupported. Capture opens the file nonblocking, verifies a regular single-link file, reads unbuffered up to 4,097 bytes, checks stable metadata, and rejects a short read that does not cover the expected bounded prefix.

CAPTURE_STARTED.json consumes the slot before response bytes are read. Malformed, empty and oversized complete first responses remain final; no correctness or parsing feedback is returned. An oversized answer retains the first 4,096 bytes, while the capture digest covers the 4,097 bytes actually read. The full response length and digest remain explicitly unknown.

Restart reconstructs authenticated metadata and immutable finals without rereading all prior numeric packets. An exposed slot without a capture marker remains the same available first-final slot. Partial/corrupt exposure or capture aborts the attempt. Deleting artifacts or retrying another answer is not recovery. Short-read failure likewise consumes the attempt without publishing a final. Interrupted retirement can finish deleting the same authenticated view files; it never removes finals or custody receipts.

The advisory lock prevents simultaneous CLI advancement, but cannot stop an owner rewriting files. Keep the journal outside candidate access. Status returns only counts, active arms and seal/scoring state:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" status \
  --session "$ABR_ATTEMPT" --session-pin "$ABR_SESSION_PIN"
~~~

## Seal and later scoring

After 936 first finals per arm and retirement of the final view:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" seal \
  --session "$ABR_ATTEMPT" --session-pin "$ABR_SESSION_PIN"
~~~

Only a separately selected scoring operation may use the private bundle:

~~~sh
"$ABR_PYTHON" -B "$ABR_PACKAGE/manual_session.py" score \
  --session "$ABR_ATTEMPT" --session-pin "$ABR_SESSION_PIN" \
  --native-root "$ABR_NATIVE_BUNDLE" --attest-separately-selected-scoring
~~~

The loader authenticates the complete 1,872-final seal and fixed native metadata, then writes a durable one-shot score marker before opening private annotations. Interrupted scoring cannot reopen them through this CLI.

Scoring uses unchanged Pair.score, reference validation and metrics. Primary exact numeric agreement is averaged within each animal and then equally across animals. Secondary distances describe the stored code, not physical dB error. Invalid answers retain the full denominator and withhold that arm's aggregate.

The result remains unverified_operator_arithmetic with the original false admission/qualification flags. This route does not claim NativeTarget.score_sealed ownership, authenticated provider execution, physiological calibration or scientific qualification. Packaging adds no benchmark count.

## Resource scope

The full store stays operator-only. One live case view is reused by both arms and retired afterward. This bounds retained image storage, not cumulative writes for 936 different views. One accepted seven-page capacity view is not an allocation for a complete participant study.

The representation has a 384 MiB per-view publication cap. Deadlines are cooperative, not outer process limits. Programme bytes are capped at 1 MiB, each journal record at 64 KiB, each retained final record at 12 KiB, and the complete score envelope at 256 KiB. Reconstruction reads the bounded roster/index and completed journal prefix; its cost grows with the attempt. Select total read/write, runtime and memory limits for the entire operation and retain failure artifacts and cumulative costs.

## Response-recursion correction

A first final containing JSON nested beyond the interpreter limit is retained as an invalid response during scoring, rather than aborting the complete one-shot score. The failed arm keeps its full required denominator and withholds aggregate metrics; the other arm can still be scored. No first final is replaced.

The corrected release helper changes only that exception classification. Observation preparation and metric definitions are unchanged. Store admission accepts only the current helper identity or the exact preserved predecessor identity, in addition to all existing external completion, native input, roster, packet and document pins. Existing observation manifests retain their original producer identity. This does not reopen or migrate an existing manual session: its externally pinned source closure remains unchanged.
